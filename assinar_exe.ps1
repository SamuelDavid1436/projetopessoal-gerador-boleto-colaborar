# ============================================================================
# assinar_exe.ps1
# ============================================================================
# Assina o CapturaBoletoColabora.exe com o certificado da empresa. Roda
# depois de CADA build novo (o build_exe.bat já chama esse script
# automaticamente no final, se achar o certificado -- não precisa rodar
# na mão, normalmente).
# ============================================================================

param(
    [string]$CaminhoExe = "dist\CapturaBoletoColabora.exe",
    [string]$CaminhoPfx = "certificado_assinatura.pfx"
)

if (-not (Test-Path $CaminhoPfx)) {
    Write-Host "[AVISO] Certificado não encontrado em '$CaminhoPfx'." -ForegroundColor Yellow
    Write-Host "O .exe foi gerado, mas NÃO foi assinado -- ainda vai dar o aviso" -ForegroundColor Yellow
    Write-Host "de bloqueio do Windows. Rode gerar_certificado.ps1 uma vez (veja" -ForegroundColor Yellow
    Write-Host "o LEIAME_EMPACOTAMENTO.md) e depois rode este script de novo." -ForegroundColor Yellow
    exit 0
}

if (-not (Test-Path $CaminhoExe)) {
    Write-Host "[ERRO] Não achei o executável em '$CaminhoExe'." -ForegroundColor Red
    Write-Host "Gere o .exe primeiro (build_exe.bat ou pyinstaller)." -ForegroundColor Red
    exit 1
}

Write-Host "Assinando $CaminhoExe ..." -ForegroundColor Green
$senha = Read-Host "Senha do certificado" -AsSecureString
$certificado = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($CaminhoPfx, $senha)

$resultado = Set-AuthenticodeSignature -FilePath $CaminhoExe -Certificate $certificado `
    -TimestampServer "http://timestamp.digicert.com" -HashAlgorithm SHA256

if ($resultado.Status -eq "Valid") {
    Write-Host ""
    Write-Host "Executável assinado com sucesso!" -ForegroundColor Green
    Write-Host "Status: $($resultado.Status)"
} else {
    Write-Host ""
    Write-Host "[ERRO] Algo deu errado ao assinar: $($resultado.StatusMessage)" -ForegroundColor Red
    exit 1
}
