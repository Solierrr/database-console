# Backup e recuperação de falhas

Procedimento documentado para o banco normalizado (`analytics`) hospedado no
Aiven. Não temos acesso de administrador da conta Aiven para automatizar
backups gerenciados, então o procedimento abaixo é operado manualmente /
via CI.

## Backup

- **Frequência**: diário, antes da carga de dados (`scripts/seed`) e antes
  de aplicar qualquer novo grupo de scripts com `scripts/runner.py`.
- **Ferramenta**: `pg_dump` em formato custom (`-Fc`), que permite restore
  seletivo por tabela/schema.

```bash
pg_dump -Fc \
  -h $DB_ANALYTICS_HOST -p $DB_ANALYTICS_PORT \
  -U $DB_ANALYTICS_USER -d $DB_ANALYTICS_NAME \
  -f backups/analytics_$(date +%Y%m%d_%H%M).dump
```

- Os dumps não são versionados no git (`backups/` está no `.gitignore`);
  guardar em armazenamento externo (ex.: bucket privado ou Google Drive
  institucional) com retenção mínima de 7 dias.

## Recuperação

1. Criar um banco vazio de destino (ou usar um schema temporário) para
   validar o dump antes de sobrescrever o banco real:
   ```bash
   createdb -h $DB_ANALYTICS_HOST -U $DB_ANALYTICS_USER analytics_restore_check
   pg_restore -h $DB_ANALYTICS_HOST -U $DB_ANALYTICS_USER \
     -d analytics_restore_check backups/analytics_YYYYMMDD_HHMM.dump
   ```
2. Validar contagem de linhas das tabelas críticas (`company`, `proposal`,
   `technical_service`) e a integridade dos objetos (`\d+` para functions,
   procedures, triggers e views).
3. Só então restaurar sobre o banco real, com o banco em modo de acesso
   restrito (revogar `CONNECT` temporariamente de usuários não-admin):
   ```bash
   pg_restore -h $DB_ANALYTICS_HOST -U $DB_ANALYTICS_USER \
     -d $DB_ANALYTICS_NAME --clean --if-exists backups/analytics_YYYYMMDD_HHMM.dump
   ```
4. Reaplicar os grupos de scripts que não fazem parte do `pg_dump` de
   dados (nenhum hoje — o dump `-Fc` cobre schema + dados + objetos).
5. Reverter o acesso restrito e comunicar o incidente/janela de
   indisponibilidade.

## Prevenção de falhas de carga

- `scripts/runner.py` aplica cada grupo dentro de uma única transação
  (commit por grupo, rollback automático em caso de erro) — uma falha em
  um arquivo não deixa o grupo parcialmente aplicado.
- Antes de rodar `--group all` em produção, rodar primeiro contra um
  banco de teste/local para validar a ordem de dependências.
