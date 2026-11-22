param(
    [ValidateRange(1, 3600)]
    [int]$DurationSeconds = 90,

    [ValidateRange(1, 60)]
    [int]$IntervalSeconds = 2,

    [string]$OutputPath = 'reports/semana10/docker_stats.csv'
)

$ErrorActionPreference = 'Stop'
$containerIds = @(docker compose ps -q api mlflow)
if ($LASTEXITCODE -ne 0 -or $containerIds.Count -lt 2) {
    throw 'Inicia primero la API y MLflow con docker compose up -d --build.'
}

$outputFullPath = Join-Path (Get-Location) $OutputPath
$outputDirectory = Split-Path -Parent $outputFullPath
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
Set-Content -LiteralPath $outputFullPath -Value 'timestamp,container,cpu_percent,memory_usage' -Encoding ascii

$endAt = (Get-Date).AddSeconds($DurationSeconds)
while ((Get-Date) -lt $endAt) {
    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $samples = docker stats --no-stream --format '{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}' $containerIds
    if ($LASTEXITCODE -ne 0) {
        throw 'docker stats no pudo obtener las métricas de los contenedores.'
    }

    foreach ($sample in $samples) {
        $fields = $sample -split '\|'
        if ($fields.Count -eq 3) {
            Add-Content -LiteralPath $outputFullPath -Value (
                '{0},{1},{2},{3}' -f $timestamp, $fields[0], $fields[1], $fields[2]
            ) -Encoding ascii
        }
    }

    Start-Sleep -Seconds $IntervalSeconds
}

Write-Output "Métricas guardadas en $outputFullPath"
