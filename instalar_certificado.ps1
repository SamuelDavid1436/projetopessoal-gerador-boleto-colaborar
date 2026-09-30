# ============================================================================
# instalar_certificado.ps1
# ============================================================================
# Pra empresas SEM domínio/Active Directory (máquinas independentes, cada
# uma administrada por conta própria). Roda UMA VEZ em cada máquina onde o
# programa vai ser instalado -- depois disso, aquela máquina passa a
# confiar em qualquer .exe assinado com o certificado da empresa, incluindo
# versões futuras do programa (não precisa rodar de novo a cada atualização).
#
# IMPORTANTE: precisa rodar como Administrador.
#   Clique com botão direito neste arquivo -> "Executar com PowerShell"
#   Se pedir permissão de administrador, clique em "Sim".
#
# Coloque este script na mesma pasta do certificado_assinatura.cer antes
# de rodar (os dois arquivos precisam estar juntos).
# ============================================================================

# confere se está rodando como Administrador; se não estiver, tenta se
# reabrir sozinho com permissão de administrador
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)
if (-not $admin) {
    Write-Host "Precisa de permissão de administrador -- reabrindo..." -ForegroundColor Yellow
    Start-Process powershell -ArgumentList "-ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

$caminhoCer = Join-Path $PSScriptRoot "certificado_assinatura.cer"

if (-not (Test-Path $caminhoCer)) {
    Write-Host "[ERRO] Não achei 'certificado_assinatura.cer' nesta pasta." -ForegroundColor Red
    Write-Host "Coloque esse arquivo na mesma pasta deste script e rode de novo."
    pause
    exit 1
}

Write-Host "============================================" -ForegroundColor Green
Write-Host " Instalando o certificado da empresa" -ForegroundColor Green
Write-Host "============================================"
Write-Host ""

Import-Certificate -FilePath $caminhoCer -CertStoreLocation "Cert:\LocalMachine\TrustedPublisher" | Out-Null
Write-Host "Certificado importado em: Editores Confiáveis" -ForegroundColor Cyan

Import-Certificate -FilePath $caminhoCer -CertStoreLocation "Cert:\LocalMachine\Root" | Out-Null
Write-Host "Certificado importado em: Autoridades de Certificação Raiz Confiáveis" -ForegroundColor Cyan

Write-Host ""
Write-Host "Pronto! Essa máquina agora confia em qualquer programa assinado" -ForegroundColor Green
Write-Host "com o certificado da empresa -- incluindo atualizações futuras" -ForegroundColor Green
Write-Host "do Captura Boleto Colaboraread, sem precisar repetir esse processo." -ForegroundColor Green
Write-Host ""
pause
