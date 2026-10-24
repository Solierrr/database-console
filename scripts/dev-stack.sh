#!/bin/sh
# Stack local de desenvolvimento: Postgres + Redis (docker compose), api-auth e api-core (mvnw) e seed planejado.
# O schema do coredb e do authdb e criado pelo Flyway do api-core e do api-auth ao subirem. So para dev; credenciais
# abertas de proposito.
#
#   scripts/dev-stack.sh db       sobe so o Postgres e o Redis e carrega o seed se o schema ja existir
#   scripts/dev-stack.sh up       sobe tudo (idempotente): as APIs criam o schema e depois roda o seed
#   scripts/dev-stack.sh seed     recarrega o seed (use RESET=1 para limpar antes); exige o schema criado
#   scripts/dev-stack.sh status   mostra o que esta de pe
#   scripts/dev-stack.sh down     para as APIs e o compose (dados do banco sao mantidos)
#   scripts/dev-stack.sh logs     caminho dos logs das APIs
#
# Nao le o .env deste repositorio: as variaveis de conexao sao definidas aqui, sempre para localhost.
set -eu

ROOT=$(cd "$(dirname "$0")/.." && pwd)
INTER=${SOLARIA_REPOS_DIR:-$(cd "$ROOT/.." && pwd)}
API_AUTH_DIR=${API_AUTH_DIR:-$INTER/api-auth}
API_CORE_DIR=${API_CORE_DIR:-$INTER/api-core}
DEV_DIR="$ROOT/.dev"

PG_PORT=${SOLARIA_PG_PORT:-55432}
REDIS_PORT=${SOLARIA_REDIS_PORT:-56379}
AUTH_PORT=${SOLARIA_AUTH_PORT:-8081}
CORE_PORT=${SOLARIA_CORE_PORT:-8080}
CLOUD_NAME=${CLOUDINARY_CLOUD_NAME:-solaria}
KEYSTORE_PASSWORD=devpass123
SERVICE_SECRET=dev-service-client-secret-change-me

say() { printf '%s\n' "$*"; }
die() { printf 'erro: %s\n' "$*" >&2; exit 1; }

port_open() { curl -s -m 2 -o /dev/null "http://localhost:$1$2" 2>/dev/null; }

find_keytool() {
	if command -v keytool >/dev/null 2>&1 && keytool -help >/dev/null 2>&1; then echo keytool; return; fi
	if [ -n "${JAVA_HOME:-}" ] && [ -x "$JAVA_HOME/bin/keytool" ]; then echo "$JAVA_HOME/bin/keytool"; return; fi
	for k in "/c/Program Files/Java"/*/bin/keytool "/c/Program Files/Eclipse Adoptium"/*/bin/keytool /usr/lib/jvm/*/bin/keytool; do
		[ -x "$k" ] && { echo "$k"; return; }
	done
	return 1
}

ensure_keystore() {
	mkdir -p "$DEV_DIR"
	[ -f "$DEV_DIR/jwt.p12" ] && return
	KT=$(find_keytool) || die "keytool nao encontrado (instale um JDK ou defina JAVA_HOME)"
	say "Gerando keystore JWT de desenvolvimento em .dev/jwt.p12"
	"$KT" -genkeypair -alias dev-key-1 -keyalg RSA -keysize 2048 -validity 3650 -storetype PKCS12 \
		-keystore "$DEV_DIR/jwt.p12" -storepass "$KEYSTORE_PASSWORD" -dname "CN=solaria-dev" >/dev/null 2>&1
}

db_env() {
	export DB_POSTGRES_HOST=localhost DB_POSTGRES_PORT="$PG_PORT" DB_POSTGRES_USER=solaria DB_POSTGRES_PASSWORD=solaria \
		DB_POSTGRES_CORE=coredb DB_POSTGRES_AUTH=authdb DB_POSTGRES_SSLMODE=disable
}

schema_ready() {
	for database in coredb:user_account authdb:auth_user; do
		docker exec local-database-console-postgres psql -U solaria -d "${database%%:*}" -tAc "SELECT to_regclass('public.${database##*:}')" 2>/dev/null | grep -q . || return 1
	done
}

run_seed() {
	db_env
	schema_ready || die "schema ausente no coredb/authdb: ele e criado pelo Flyway do api-core e do api-auth (rode 'sh scripts/dev-stack.sh up')"
	export HOST=localhost PORT="$PG_PORT" USER=solaria PASSWORD=solaria SSLMODE=disable ENVIRONMENT=local CLOUDINARY_CLOUD_NAME="$CLOUD_NAME"
	[ "${RESET:-0}" = 1 ] && (cd "$ROOT" && python -m seed --reset | tail -1)
	say "Seed planejado"
	(cd "$ROOT" && python -m seed | grep -E "^Linhas|users:|Pools" )
}

start_api() { # nome dir porta health
	name=$1; dir=$2; port=$3; health=$4
	if port_open "$port" "$health"; then say "$name ja esta de pe em :$port"; return; fi
	[ -d "$dir" ] || die "repositorio $name nao encontrado em $dir (defina API_AUTH_DIR/API_CORE_DIR)"
	: > "$DEV_DIR/$name.log"
	say "Subindo $name (log em .dev/$name.log)"
	(cd "$dir" && nohup ./mvnw -q spring-boot:run > "$DEV_DIR/$name.log" 2>&1 &)
}

wait_api() { # nome porta health
	name=$1; port=$2; health=$3; n=0
	while [ "$n" -lt 150 ]; do
		port_open "$port" "$health" && { say "$name pronto em :$port"; return; }
		grep -q "Failed to execute goal" "$DEV_DIR/$name.log" 2>/dev/null && die "$name falhou ao subir; veja $DEV_DIR/$name.log"
		n=$((n + 1)); sleep 3
	done
	die "$name nao respondeu a tempo; veja $DEV_DIR/$name.log"
}

kill_port() {
	case "$(uname -s 2>/dev/null)" in
		MINGW*|MSYS*|CYGWIN*)
			for pid in $(netstat -ano 2>/dev/null | grep "LISTENING" | grep ":$1 " | awk '{print $5}' | sort -u); do
				taskkill //PID "$pid" //F //T >/dev/null 2>&1 || true
			done ;;
		*) command -v lsof >/dev/null 2>&1 && kill $(lsof -ti ":$1") 2>/dev/null || true ;;
	esac
}

cmd_up() {
	command -v docker >/dev/null 2>&1 || die "docker nao encontrado"
	command -v python >/dev/null 2>&1 || die "python nao encontrado"
	ensure_keystore
	say "Postgres e Redis (docker compose)"
	(cd "$ROOT" && docker compose up -d --wait >/dev/null)

	export DB_POSTGRES_HOST=localhost DB_POSTGRES_PORT="$PG_PORT" DB_POSTGRES_USER=solaria DB_POSTGRES_PASSWORD=solaria \
		UPSTASH_CORE_HOST=localhost UPSTASH_CORE_PORT="$REDIS_PORT" OTEL_TRACES_SAMPLING_PROBABILITY=0.0 \
		SERVICE_CLIENT_SECRET="$SERVICE_SECRET" CLOUDINARY_CLOUD_NAME="$CLOUD_NAME"
	# api-auth: o schema e do database-console (fonte unica), entao o Flyway proprio do servico fica desligado.
	DB_POSTGRES_AUTH=authdb JWT_KEYSTORE_PATH="$DEV_DIR/jwt.p12" JWT_KEYSTORE_PASSWORD="$KEYSTORE_PASSWORD" JWT_ACTIVE_KID=dev-key-1 \
		PERSISTENCE_BASE_URL="http://localhost:$CORE_PORT" SPRING_FLYWAY_ENABLED=false SERVER_PORT="$AUTH_PORT" \
		start_api api-auth "$API_AUTH_DIR" "$AUTH_PORT" /.well-known/jwks.json
	DB_POSTGRES_CORE=coredb DB_POSTGRES_SSLMODE=disable AUTH_SERVICE_URL="http://localhost:$AUTH_PORT" \
		JWT_JWK_SET_URI="http://localhost:$AUTH_PORT/.well-known/jwks.json" CLOUDINARY_API_KEY=dev CLOUDINARY_API_SECRET=dev \
		CLOUDINARY_FOLDER_PREFIX=solaria SERVER_PORT="$CORE_PORT" \
		start_api api-core "$API_CORE_DIR" "$CORE_PORT" /actuator/health
	wait_api api-auth "$AUTH_PORT" /.well-known/jwks.json
	wait_api api-core "$CORE_PORT" /actuator/health
	run_seed
	say "Stack pronta: api-core :$CORE_PORT, api-auth :$AUTH_PORT, postgres :$PG_PORT, redis :$REDIS_PORT"
	say "Login de dev: <username>@seed.solaria.dev (senha no seed/README.md)"
}

cmd_db() {
	command -v docker >/dev/null 2>&1 || die "docker nao encontrado"
	command -v python >/dev/null 2>&1 || die "python nao encontrado"
	say "Postgres e Redis (docker compose)"
	(cd "$ROOT" && docker compose up -d --wait >/dev/null)
	if schema_ready; then
		run_seed
	else
		say "Schema ainda nao criado: o Flyway do api-core e do api-auth cria o coredb e o authdb. Rode 'sh scripts/dev-stack.sh up'."
	fi
	say "Postgres pronto. Conecte com:"
	say "  postgresql://solaria:solaria@localhost:$PG_PORT/coredb   (authdb no mesmo servidor)"
	say "  psql: PGPASSWORD=solaria psql -h localhost -p $PG_PORT -U solaria -d coredb"
	say "Variaveis para uma API Spring: DB_POSTGRES_HOST=localhost DB_POSTGRES_PORT=$PG_PORT DB_POSTGRES_USER=solaria DB_POSTGRES_PASSWORD=solaria DB_POSTGRES_CORE=coredb DB_POSTGRES_SSLMODE=disable"
	say "Login de dev: <username>@seed.solaria.dev (senha no seed/README.md)"
}

cmd_status() {
	for item in "postgres:$PG_PORT" "redis:$REDIS_PORT"; do
		name=${item%%:*}; port=${item##*:}
		if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "local-database-console-$name"; then say "ok   $name (:$port)"; else say "off  $name"; fi
	done
	port_open "$AUTH_PORT" /.well-known/jwks.json && say "ok   api-auth (:$AUTH_PORT)" || say "off  api-auth"
	port_open "$CORE_PORT" /actuator/health && say "ok   api-core (:$CORE_PORT)" || say "off  api-core"
}

cmd_down() {
	kill_port "$CORE_PORT"; kill_port "$AUTH_PORT"
	(cd "$ROOT" && docker compose down >/dev/null 2>&1) || true
	say "Stack parada (volume do banco mantido; para apagar: docker compose down -v)"
}

case "${1:-}" in
	up) cmd_up ;;
	db) cmd_db ;;
	seed) ensure_keystore; run_seed ;;
	status) cmd_status ;;
	down) cmd_down ;;
	logs) say "$DEV_DIR/api-auth.log"; say "$DEV_DIR/api-core.log" ;;
	*) die "uso: $0 up|db|seed|status|down|logs" ;;
esac
