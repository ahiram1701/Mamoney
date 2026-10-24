<#
.SYNOPSIS
  Publica Mamoney en tu tailnet con HTTPS usando `tailscale serve`.

.DESCRIPTION
  Mamoney escucha solo en 127.0.0.1. `tailscale serve` lo expone únicamente a los
  dispositivos de tu tailnet (no a internet) en https://<equipo>.<tailnet>.ts.net,
  con certificado válido, y añade la cabecera Tailscale-User-Login con tu identidad.

  No uses `tailscale funnel`: Mamoney rechaza esas peticiones a propósito.

.EXAMPLE
  .\scripts\tailscale-serve.ps1          # activar
  .\scripts\tailscale-serve.ps1 -Off     # desactivar
  .\scripts\tailscale-serve.ps1 -Status  # ver configuración
#>
param(
    [int]$Port = 8765,
    [switch]$Off,
    [switch]$Status
)

$ErrorActionPreference = "Stop"

$tailscale = Get-Command tailscale -ErrorAction SilentlyContinue
if (-not $tailscale) {
    $default = "C:\Program Files\Tailscale\tailscale.exe"
    if (Test-Path $default) { $tailscale = $default } else {
        Write-Error "No se encontró Tailscale. Instálalo desde https://tailscale.com/download/windows"
    }
} else {
    $tailscale = $tailscale.Source
}

if ($Status) {
    & $tailscale serve status
    exit $LASTEXITCODE
}

if ($Off) {
    & $tailscale serve --https=443 off
    Write-Host "Mamoney ya no está publicado en tu tailnet."
    exit $LASTEXITCODE
}

& $tailscale serve --bg --https=443 "http://127.0.0.1:$Port"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Si Tailscale pide habilitar HTTPS, actívalo en https://login.tailscale.com/admin/dns y repite." -ForegroundColor Yellow
    exit $LASTEXITCODE
}

$info = & $tailscale status --json | ConvertFrom-Json
$dns = $info.Self.DNSName.TrimEnd(".")
Write-Host ""
Write-Host "Listo. Abre Mamoney desde cualquier dispositivo de tu tailnet:" -ForegroundColor Green
Write-Host "  https://$dns" -ForegroundColor Cyan
Write-Host ""
Write-Host "Recomendado: en Mamoney > Ajustes, limita el acceso a tu usuario de Tailscale y activa un PIN."
