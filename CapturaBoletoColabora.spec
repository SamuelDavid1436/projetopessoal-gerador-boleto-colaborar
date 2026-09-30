# -*- mode: python ; coding: utf-8 -*-
"""
CapturaBoletoColabora.spec
==========================
Configuração do PyInstaller para gerar o executável Windows.

IMPORTANTE: o PyInstaller NÃO faz build cruzado — rode este arquivo em uma
máquina Windows (não dá pra gerar o .exe a partir de Linux/Mac). Veja o
LEIAME_EMPACOTAMENTO.md para o passo a passo completo.

Uso (dentro da pasta do projeto, no Windows, com o venv ativado):
    pyinstaller CapturaBoletoColabora.spec
"""

import sys
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# customtkinter precisa dos próprios arquivos de tema/fonte (não são .py) —
# collect_all garante que tudo isso vai junto no executável.
datas = []
binaries = []
hiddenimports = []

# pdfplumber -> pdfminer (tabelas cmap) e pypdfium2 (DLL) também têm arquivos não-.py
for pacote in ("customtkinter", "pdfplumber", "pdfminer", "pypdfium2", "pypdfium2_raw"):
    try:
        d, b, h = collect_all(pacote)
    except Exception:
        continue
    datas += d
    binaries += b
    hiddenimports += h

# recursos do próprio projeto (ícone, logo, manual)
datas += [
    ("assets/icone.ico", "assets"),
    ("assets/logo.png", "assets"),
    ("assets/manual.pdf", "assets"),
    ("assets/manual.docx", "assets"),
]

hiddenimports += [
    "selenium",
    "selenium.webdriver",
    "webdriver_manager",
    "webdriver_manager.chrome",
    "PIL",
    "PIL._tkinter_finder",
    "pandas",
    "requests",
    "pdfplumber",
    "pdfminer",
    "colaboraread_client",
    "openpyxl",
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="CapturaBoletoColabora",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # False = sem janela preta de terminal atrás do programa
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/icone.ico",
)
