[CmdletBinding()]
param(
    [Parameter()]
    [string]$ModelDirectory
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if ([string]::IsNullOrWhiteSpace($ModelDirectory)) {
    $ModelDirectory = Join-Path (Split-Path -Parent $repoRoot) 'semana-07\mlruns\2\models'
}
if (-not (Test-Path -LiteralPath $ModelDirectory -PathType Container)) {
    throw "No encuentro los artefactos MLflow: $ModelDirectory. Pasa la ruta con -ModelDirectory."
}

$branchName = (git -C $repoRoot branch --show-current).Trim()
if ($LASTEXITCODE -ne 0) { throw 'No pude identificar la rama actual.' }
if ($branchName -ne 'semana10-microservicios-cicd-finops-aws') {
    throw "Cambia a semana10-microservicios-cicd-finops-aws antes de empaquetar. Rama actual: $branchName"
}

$packageDirectory = Join-Path $env:TEMP ('semana10-aws-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $packageDirectory | Out-Null
$sourceZip = Join-Path $packageDirectory 'source.zip'
$modelZip = Join-Path $packageDirectory 'week07-models.zip'

git -C $repoRoot archive --format=zip "--output=$sourceZip" HEAD
if ($LASTEXITCODE -ne 0) { throw 'No pude empaquetar los archivos confirmados de la rama.' }

Compress-Archive -Path (Join-Path $ModelDirectory '*') -DestinationPath $modelZip -CompressionLevel Optimal -Force

$sourceInfo = Get-Item -LiteralPath $sourceZip
$modelInfo = Get-Item -LiteralPath $modelZip
Write-Output "Paquete AWS creado en: $packageDirectory"
Write-Output ("source.zip: {0:N2} MiB" -f ($sourceInfo.Length / 1MB))
Write-Output ("week07-models.zip: {0:N2} MiB" -f ($modelInfo.Length / 1MB))
Write-Output 'Carga source.zip y week07-models.zip en el prefijo week10/ del bucket S3 del stack.'
