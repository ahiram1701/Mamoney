<#
.SYNOPSIS
  Prueba Mamoney.exe tal como queda al descargarlo con el navegador.

.DESCRIPTION
  Copia la app, marca cada archivo como "descargado de internet" (Mark of the Web), la
  arranca oculta y comprueba que el servidor responda, que siga viva tras inicializar la
  ventana y que su registro no tenga errores. Todas las peticiones tienen tiempo límite y al
  final siempre se muestran el registro y, si existen, las pilas de los hilos.

.EXAMPLE
  .\scripts\test-exe.ps1 -AppDir dist\Mamoney -ExpectedVersion 0.2.1
#>
param(
    [string]$AppDir = "dist/Mamoney",
    [string]$ExpectedVersion = "",
    [int]$Port = 8799
)
$ErrorActionPreference = "Stop"

$work = Join-Path ([IO.Path]::GetTempPath()) ("mamoney-exe-test-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
$app = Join-Path $work "Mamoney"
$data = Join-Path $work "data"
Copy-Item $AppDir $app -Recurse

$mark = "[ZoneTransfer]`r`nZoneId=3`r`nHostUrl=https://github.com/`r`n"
$files = Get-ChildItem $app -Recurse -File
foreach ($f in $files) { Set-Content -LiteralPath $f.FullName -Stream Zone.Identifier -Value $mark }
Write-Host "Marcados $($files.Count) archivos como descargados de internet"

$env:MAMONEY_PORT = "$Port"
$env:MAMONEY_DATA_DIR = $data
$env:MAMONEY_FX_AUTO = "0"
$env:MAMONEY_UPDATE_CHECK = "0"
$env:MAMONEY_TRACE_SECONDS = "15"   # el launcher vuelca las pilas de los hilos periódicamente

function Get-Health {
    try { return Invoke-RestMethod -TimeoutSec 3 "http://127.0.0.1:$Port/api/health" } catch { return $null }
}

# Start-Process usa el shell de Windows, que con un .exe marcado muestra el diálogo
# "¿Desea ejecutar este archivo?" y se queda esperando un clic. CreateProcess directo
# (UseShellExecute = false) no lo muestra; las DLL siguen marcadas, que es lo que se prueba.
$psi = [Diagnostics.ProcessStartInfo]::new((Join-Path $app "Mamoney.exe"), "--hidden")
$psi.UseShellExecute = $false
$psi.WorkingDirectory = $app
$p = [Diagnostics.Process]::Start($psi)
$failure = $null
try {
    $health = $null
    for ($i = 0; $i -lt 60 -and -not $health; $i++) {
        Start-Sleep -Seconds 1
        if ($p.HasExited) { break }
        $health = Get-Health
    }
    if (-not $health) {
        $failure = "El servidor no respondió (proceso vivo: $(-not $p.HasExited))"
    } else {
        Write-Host "Servidor responde: v$($health.version)"
        # La ventana (pywebview/.NET) se inicializa después del servidor.
        Start-Sleep -Seconds 15
        $again = Get-Health
        $log = Join-Path $data "mamoney.log"
        $errors = Select-String -Path $log -Pattern " ERROR \[|Traceback" -CaseSensitive -ErrorAction SilentlyContinue
        if ($p.HasExited) { $failure = "Mamoney.exe se cerró solo (código $($p.ExitCode))" }
        elseif (-not $again) { $failure = "El servidor dejó de responder después de iniciar la ventana" }
        elseif ($errors) { $failure = "El registro contiene errores" }
        elseif ($ExpectedVersion -and $health.version -ne $ExpectedVersion) {
            $failure = "El .exe reporta v$($health.version) y se esperaba v$ExpectedVersion"
        }
    }
} finally {
    Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
    Write-Host "----- mamoney.log -----"
    Get-Content (Join-Path $data "mamoney.log") -ErrorAction SilentlyContinue | Select-Object -Last 80
    $stacks = Join-Path $data "stacks.log"
    if (Test-Path $stacks) {
        Write-Host "----- pilas de hilos (última muestra) -----"
        Get-Content $stacks | Select-Object -Last 60
    }
}

if ($failure) { throw $failure }
Write-Host "OK: Mamoney.exe arranca, sigue vivo y sin errores con archivos marcados"
