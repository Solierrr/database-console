param(
    [ValidateSet('core', 'auth', 'all')]
    [string] $Target,
    [string] $EnvPath = '.env'
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $EnvPath -PathType Leaf)) {
    throw "Arquivo '$EnvPath' não encontrado. Execute 'make extract-env SERVICE=database-console ENV=qa'."
}

$config = @{}
foreach ($line in [System.IO.File]::ReadAllLines((Resolve-Path -LiteralPath $EnvPath))) {
    if ($line -match '^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
        $value = $Matches[2].Trim()
        if ($value.Length -ge 2 -and (($value[0] -eq '"' -and $value[-1] -eq '"') -or ($value[0] -eq "'" -and $value[-1] -eq "'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        $config[$Matches[1]] = $value
    }
}

foreach ($key in @('DB_POSTGRES_HOST', 'DB_POSTGRES_PORT', 'DB_POSTGRES_USER', 'DB_POSTGRES_PASSWORD')) {
    if (-not $config.ContainsKey($key) -or [string]::IsNullOrWhiteSpace($config[$key])) {
        throw "'$key' não está definido em '$EnvPath'. Extraia o ambiente do database-console antes do backup."
    }
}

if ([string]::IsNullOrWhiteSpace($Target)) {
    Write-Host 'Qual banco deseja salvar?'
    Write-Host '  1. core'
    Write-Host '  2. auth'
    Write-Host '  3. todos (core e auth)'
    do {
        $choice = Read-Host 'Digite 1, 2 ou 3'
    } until ($choice -in @('1', '2', '3'))
    $Target = @{ '1' = 'core'; '2' = 'auth'; '3' = 'all' }[$choice]
}

$dumpCommand = Get-Command pg_dump -ErrorAction SilentlyContinue
if (-not $dumpCommand) {
    throw 'pg_dump não encontrado no PATH. Instale o cliente PostgreSQL antes do backup.'
}

$services = if ($Target -eq 'all') { @('core', 'auth') } else { @($Target) }
$environment = 'unknown'
$header = Get-Content -LiteralPath $EnvPath -TotalCount 1
if ($header -match '\bEnvironment=(local|qa|prod)\b') {
    $environment = $Matches[1].ToLowerInvariant()
}
$backupDir = Join-Path (Get-Location) (Join-Path 'backups' $environment)
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'

$previousPassword = $env:PGPASSWORD
$previousSslMode = $env:PGSSLMODE
$previousTimeout = $env:PGCONNECT_TIMEOUT
try {
    $env:PGPASSWORD = $config['DB_POSTGRES_PASSWORD']
    if ($config.ContainsKey('DB_POSTGRES_SSLMODE') -and $config['DB_POSTGRES_SSLMODE']) {
        $env:PGSSLMODE = $config['DB_POSTGRES_SSLMODE']
    }
    $env:PGCONNECT_TIMEOUT = '15'

    foreach ($service in $services) {
        $nameKey = 'DB_POSTGRES_' + $service.ToUpperInvariant()
        if (-not $config.ContainsKey($nameKey) -or [string]::IsNullOrWhiteSpace($config[$nameKey])) {
            throw "'$nameKey' não está definido em '$EnvPath'."
        }
        $database = $config[$nameKey]
        $fileName = '{0}-{1}.sql' -f $service, $stamp
        $destination = Join-Path $backupDir $fileName
        if (Test-Path -LiteralPath $destination) {
            throw "Backup '$destination' já existe. Execute novamente para gerar outro horário."
        }
        $temporary = Join-Path $backupDir ('.{0}.{1}.tmp' -f $fileName, [guid]::NewGuid().ToString('N'))
        Write-Host "Extraindo $service ($environment)..."
        try {
            & $dumpCommand.Source --host=$($config['DB_POSTGRES_HOST']) --port=$($config['DB_POSTGRES_PORT']) --username=$($config['DB_POSTGRES_USER']) --dbname=$database --no-password --format=plain --file=$temporary
            if ($LASTEXITCODE -ne 0) {
                throw "pg_dump falhou para '$service' (exit code $LASTEXITCODE)."
            }
            if (-not (Test-Path -LiteralPath $temporary) -or (Get-Item -LiteralPath $temporary).Length -eq 0) {
                throw "pg_dump não gerou dados para '$service'."
            }
            Move-Item -LiteralPath $temporary -Destination $destination
            Write-Host "Backup salvo em $destination"
        }
        finally {
            if (Test-Path -LiteralPath $temporary) {
                Remove-Item -LiteralPath $temporary
            }
        }
    }
}
finally {
    $env:PGPASSWORD = $previousPassword
    $env:PGSSLMODE = $previousSslMode
    $env:PGCONNECT_TIMEOUT = $previousTimeout
}
