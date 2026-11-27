# Despliegue en Windows con Miniconda: crea el entorno y descarga el modelo.
# Ejecútalo desde "Anaconda PowerShell Prompt" (o con conda ya en el PATH).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$envName = "IPM_beat_saber"

if (-not (Get-Command conda -ErrorAction SilentlyContinue)) {
    Write-Host "No se encuentra 'conda'. Instala Miniconda:"
    Write-Host "  https://www.anaconda.com/docs/getting-started/miniconda/install"
    Write-Host "y abre 'Anaconda PowerShell Prompt'."
    exit 1
}

$exists = (conda env list) -match "^\s*$envName\s"
if ($exists) {
    Write-Host "El entorno $envName ya existe: se actualiza."
    conda env update -n $envName -f environment.yml --prune
} else {
    conda env create -f environment.yml
}
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

conda run -n $envName --no-capture-output python download_models.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "Listo. Para jugar:"
Write-Host "  conda activate $envName"
Write-Host "  python main.py"
