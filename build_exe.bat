@echo off
chcp 65001 >nul
echo ============================================
echo  Captura Boleto Colaboraread - Gerar .exe
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERRO] Python nao foi encontrado.
    echo Instale o Python em https://www.python.org/downloads/
    echo IMPORTANTE: marque a caixinha "Add python.exe to PATH" na instalacao.
    pause
    exit /b 1
)

echo [1/4] Instalando as dependencias do projeto...
pip install -r requirements.txt
pip install --upgrade selenium webdriver-manager
if errorlevel 1 (
    echo [ERRO] Falha ao instalar as dependencias. Veja a mensagem acima.
    pause
    exit /b 1
)

echo.
echo [2/4] Instalando o PyInstaller...
pip install pyinstaller
if errorlevel 1 (
    echo [ERRO] Falha ao instalar o PyInstaller.
    pause
    exit /b 1
)

echo.
echo [3/4] Gerando o executavel (pode levar alguns minutos)...
pyinstaller CapturaBoletoColabora.spec --noconfirm
if errorlevel 1 (
    echo [ERRO] Falha ao gerar o executavel. Veja a mensagem acima.
    pause
    exit /b 1
)

echo.
echo [4/4] Assinando o executavel...
if exist certificado_assinatura.pfx (
    powershell -ExecutionPolicy Bypass -File assinar_exe.ps1
) else (
    echo [AVISO] Certificado nao encontrado -- pulei a assinatura.
    echo O .exe funciona, mas ainda pode dar aviso de bloqueio do Windows.
    echo Rode gerar_certificado.ps1 uma vez para resolver isso definitivamente.
)

echo.
echo Pronto!
echo O executavel foi gerado em: dist\CapturaBoletoColabora.exe
echo Copie esse arquivo para a maquina do usuario final.
echo.
pause
