# ============================================================================
# gerar_certificado.ps1
# ============================================================================
# Gera o certificado de assinatura de código da empresa. Roda SÓ UMA VEZ
# (não é por build — é criado uma vez e reaproveitado pra sempre, ou até
# expirar em 5 anos, veja o aviso no final do script).
#
# Uso: clique com botão direito neste arquivo -> "Executar com PowerShell"
# (ou abra um terminal PowerShell nesta pasta e rode: .\gerar_certificado.ps1)
# ============================================================================

Write-Host "============================================" -ForegroundColor Green
Write-Host " Gerando certificado de assinatura de código" -ForegroundColor Green
Write-Host "============================================"
Write-Host ""

$nomeEmpresa = Read-Host "Digite o nome da empresa (aparece na assinatura do programa)"
if ([string]::IsNullOrWhiteSpace($nomeEmpresa)) { $nomeEmpresa = "Captura Boleto Colaboraread" }

$cert = New-SelfSignedCertificate `
    -Type CodeSigningCert `
    -Subject "CN=$nomeEmpresa" `
    -CertStoreLocation "Cert:\CurrentUser\My" `
    -NotAfter (Get-Date).AddYears(5) `
    -KeyUsage DigitalSignature `
    -KeyAlgorithm RSA `
    -KeyLength 2048

Write-Host ""
Write-Host "Certificado criado. Agora defina uma senha para proteger o arquivo" -ForegroundColor Yellow
Write-Host "que sai daqui (o .pfx) -- anote essa senha em lugar seguro, ela vai" -ForegroundColor Yellow
Write-Host "ser pedida toda vez que for assinar um novo .exe." -ForegroundColor Yellow
$senha = Read-Host "Senha para o certificado" -AsSecureString

Export-PfxCertificate -Cert $cert -FilePath ".\certificado_assinatura.pfx" -Password $senha | Out-Null
Export-Certificate -Cert $cert -FilePath ".\certificado_assinatura.cer" | Out-Null

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host " Pronto! Dois arquivos foram gerados:" -ForegroundColor Green
Write-Host "============================================"
Write-Host ""
Write-Host "  certificado_assinatura.pfx" -ForegroundColor Cyan
Write-Host "    -> PRIVADO. Fica com quem gera o build. NUNCA envie pra ninguém,"
Write-Host "       nem suba num repositório público. É o que assina o .exe."
Write-Host ""
Write-Host "  certificado_assinatura.cer" -ForegroundColor Cyan
Write-Host "    -> PÚBLICO. Esse SIM você envia pro TI da empresa -- é só a"
Write-Host "       'chave pública', não dá pra assinar nada com ele, só serve"
Write-Host "       pro Windows confiar em arquivos assinados pelo .pfx acima."
Write-Host ""
Write-Host "Próximo passo: mande o arquivo .cer pro TI seguir o guia" -ForegroundColor Yellow
Write-Host "TI_LEIA_ISTO.md (nessa mesma pasta)." -ForegroundColor Yellow
Write-Host ""
pause
