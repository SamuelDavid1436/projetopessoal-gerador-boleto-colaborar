# -*- coding: utf-8 -*-
"""
browser_manager.py
===================
Cuida da criação do Chrome com perfis persistentes independentes (até
config.NUM_PERFIS). Cada perfil tem sua própria pasta de dados do Chrome,
então cada um mantém seu próprio login, e todos podem rodar ao mesmo tempo
sem conflito (diferente de antes, quando um único perfil "base" era
clonado para cada janela).
"""
import os
import re
import shutil
import threading
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException, NoSuchElementException

try:
    from webdriver_manager.chrome import ChromeDriverManager
    _TEM_WEBDRIVER_MANAGER = True
except ImportError:
    _TEM_WEBDRIVER_MANAGER = False

import config


def garantir_pastas():
    os.makedirs(config.PASTA_DOCUMENTOS, exist_ok=True)
    os.makedirs(config.PASTA_APP_LOCAL, exist_ok=True)
    os.makedirs(config.PASTA_PERFIS, exist_ok=True)
    _migrar_perfis_antigos_do_onedrive()  # antes de criar as subpastas vazias abaixo
    os.makedirs(config.PASTA_SAIDA, exist_ok=True)
    os.makedirs(config.PASTA_LOGS, exist_ok=True)
    os.makedirs(config.PASTA_SCREENSHOTS, exist_ok=True)
    for i in range(1, config.NUM_PERFIS + 1):
        os.makedirs(pasta_perfil(i), exist_ok=True)


def _migrar_perfis_antigos_do_onedrive():
    """
    Versões anteriores guardavam os perfis do Chrome dentro de
    Documentos (que em muitas máquinas está sincronizado pelo OneDrive —
    isso é o que estava causando os travamentos/corrupção de perfil).
    Se ainda existir algo salvo naquele local antigo e a pasta nova
    (fora do OneDrive) ainda estiver vazia, move os dados pra lá
    automaticamente — assim ninguém perde o login já feito só por causa
    dessa mudança. Roda toda vez que o programa abre, mas não faz nada
    depois da primeira migração (a pasta nova já não estará mais vazia).
    """
    pasta_antiga = os.path.join(config.PASTA_DOCUMENTOS, "perfis")
    meta_antigo = os.path.join(config.PASTA_DOCUMENTOS, "perfis_meta.json")

    try:
        pasta_nova_vazia = not any(os.scandir(config.PASTA_PERFIS))
    except OSError:
        pasta_nova_vazia = True

    if pasta_nova_vazia and os.path.isdir(pasta_antiga):
        try:
            for item in os.listdir(pasta_antiga):
                origem = os.path.join(pasta_antiga, item)
                destino = os.path.join(config.PASTA_PERFIS, item)
                if not os.path.exists(destino):
                    shutil.move(origem, destino)
        except OSError:
            pass  # se não conseguir migrar, segue com pastas novas vazias -- não é crítico

    if os.path.isfile(meta_antigo) and not os.path.isfile(config.ARQUIVO_PERFIS_META):
        try:
            shutil.move(meta_antigo, config.ARQUIVO_PERFIS_META)
        except OSError:
            pass


def pasta_perfil(perfil_id: int) -> str:
    return os.path.join(config.PASTA_PERFIS, f"perfil_{perfil_id}")


def perfil_tem_dados(perfil_id: int) -> bool:
    """Heurística rápida (sem abrir navegador): a pasta do perfil já tem algum dado salvo?"""
    pasta = pasta_perfil(perfil_id)
    return os.path.isdir(pasta) and len(os.listdir(pasta)) > 0


def limpar_perfil(perfil_id: int):
    """Apaga só a sessão daquele perfil (login, cookies etc), sem afetar os outros."""
    pasta = pasta_perfil(perfil_id)
    if os.path.isdir(pasta):
        shutil.rmtree(pasta, ignore_errors=True)
    os.makedirs(pasta, exist_ok=True)


def criar_driver(pasta_perfil_chrome: str, headless: bool = False):
    """
    Cria e devolve um webdriver.Chrome configurado com a pasta de perfil informada.

    Ordem de tentativa (pra sobreviver às atualizações automáticas do Chrome):
    1. Selenium Manager (embutido no Selenium >= 4.6): descobre a versão do
       Chrome instalado e baixa/usa o ChromeDriver certo sozinho.
    2. webdriver-manager (reserva), se o Selenium Manager falhar.
    """
    opcoes = Options()
    opcoes.add_argument(f"--user-data-dir={pasta_perfil_chrome}")
    opcoes.add_argument("--start-maximized")
    opcoes.add_argument("--disable-notifications")
    if headless:
        opcoes.add_argument("--headless=new")
        opcoes.add_argument("--window-size=1366,900")

    erros = []
    try:
        return webdriver.Chrome(options=opcoes)
    except WebDriverException as erro:
        erros.append(f"Selenium Manager: {erro.msg or erro}")

    if _TEM_WEBDRIVER_MANAGER:
        try:
            servico = Service(ChromeDriverManager().install())
            return webdriver.Chrome(service=servico, options=opcoes)
        except Exception as erro:  # pylint: disable=broad-except
            erros.append(f"webdriver-manager: {erro}")

    raise WebDriverException(
        "Não consegui abrir o Google Chrome. Confira se o Chrome está instalado e "
        "atualizado, feche todas as janelas dele e tente de novo.\n" + "\n".join(erros)
    )


def abrir_janela_login_manual(perfil_id: int, ao_capturar_email=None):
    """
    Abre uma janela do Chrome com a pasta de perfil do perfil informado, direto
    no Prisma, para o usuário logar manualmente. Retorna o driver (o
    chamador decide quando fechar).

    Se `ao_capturar_email` for informado, dispara em segundo plano um
    monitoramento que tenta achar o e-mail de duas formas: (1) o que for
    digitado no campo de e-mail da tela de login da Microsoft, e (2) se o
    login acontecer sem digitar nada (sessão já ativa no Windows/navegador),
    varrendo a própria tela do CRM em busca de um e-mail visível. Chama
    `ao_capturar_email(email)` assim que achar algo.
    """
    garantir_pastas()
    driver = criar_driver(pasta_perfil(perfil_id))
    driver.get(config.URL_PRISMA)

    if ao_capturar_email:
        threading.Thread(
            target=_monitorar_email_login, args=(driver, ao_capturar_email), daemon=True
        ).start()

    return driver


_SELETOR_CAMPO_EMAIL_LOGIN = "input[type='email'], input[name='loginfmt'], #i0116"
_REGEX_EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

# Painel de conta do Office 365 (aparece no topo da tela do CRM depois que o
# usuário já está autenticado) — o e-mail fica direto no texto deste
# elemento, então é bem mais confiável que "adivinhar" por atributos.
# Exemplo real do HTML:
#   <div id="mectrl_currentAccount_secondary" class="mectrl_truncate">
#       dulcineia.c.silva@parceiro-kroton.com.br
#   </div>
_SELETOR_EMAIL_CONTA_O365 = "#mectrl_currentAccount_secondary"
_SELETOR_NOME_CONTA_O365 = "#mectrl_currentAccount_primary"

# Script best-effort (reserva, só usado se o painel de conta acima não for
# encontrado): procura um e-mail em atributos title/aria-label e, se não
# achar, no texto visível da página inteira.
_SCRIPT_ENCONTRAR_EMAIL = r"""
const regex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/;
const candidatos = document.querySelectorAll('[title], [aria-label]');
for (const el of candidatos) {
    const valor = el.getAttribute('title') || el.getAttribute('aria-label') || '';
    const m = valor.match(regex);
    if (m) return m[0];
}
const m2 = document.body.innerText.match(regex);
return m2 ? m2[0] : null;
"""


# O painel de conta (com o e-mail) só existe no DOM DEPOIS que alguém clica
# no ícone/foto de perfil no canto superior — antes disso, o
# #mectrl_currentAccount_secondary nem existe na página. Lista de
# candidatos comuns pro botão que abre esse painel (best-effort — nomes
# variam entre diferentes versões do cabeçalho do Office 365).
_SELETORES_BOTAO_CONTA = [
    "#O365_MainLink_Me",
    "#meControlTrigger",
    ".mectrl_trigger",
    "#mectrl_header_account",
    "#mectrl_currentAccount_picture",
    "[aria-label*='conta' i]",
    "[aria-label*='account' i]",
]


def _abrir_painel_conta(driver) -> bool:
    """Tenta clicar no ícone/foto de conta pra abrir o painel que mostra o
    e-mail. Best-effort: tenta uma lista de seletores comuns, um de cada
    vez, e confere se o painel realmente abriu depois de cada clique.
    Devolve True se conseguiu abrir."""
    for seletor in _SELETORES_BOTAO_CONTA:
        try:
            botoes = driver.find_elements(By.CSS_SELECTOR, seletor)
        except WebDriverException:
            continue
        for botao in botoes:
            try:
                if not botao.is_displayed():
                    continue
                botao.click()
            except WebDriverException:
                continue
            time.sleep(0.8)  # dá tempo do painel abrir
            try:
                if driver.find_elements(By.CSS_SELECTOR, _SELETOR_EMAIL_CONTA_O365):
                    return True
            except WebDriverException:
                pass
    return False


def capturar_email_da_pagina(driver):
    """
    Tenta achar o e-mail da conta autenticada, nesta ordem:
    1. Painel de conta do Office 365 (#mectrl_currentAccount_secondary) —
       se já estiver aberto (raro, mas possível).
    2. Clica no ícone/foto de conta pra ABRIR o painel (ele só existe no
       DOM depois desse clique) e tenta ler de novo.
    3. Reserva best-effort: varre atributos title/aria-label e o texto
       visível da página inteira em busca de algo com formato de e-mail.
    Devolve o e-mail encontrado, ou None.
    """
    try:
        elemento = driver.find_element(By.CSS_SELECTOR, _SELETOR_EMAIL_CONTA_O365)
        texto = (elemento.text or "").strip()
        if texto and _REGEX_EMAIL.fullmatch(texto):
            return texto
    except (NoSuchElementException, WebDriverException):
        pass

    if _abrir_painel_conta(driver):
        try:
            elemento = driver.find_element(By.CSS_SELECTOR, _SELETOR_EMAIL_CONTA_O365)
            texto = (elemento.text or "").strip()
            if texto and _REGEX_EMAIL.fullmatch(texto):
                return texto
        except (NoSuchElementException, WebDriverException):
            pass

    try:
        resultado = driver.execute_script(_SCRIPT_ENCONTRAR_EMAIL)
        if resultado and "@" in resultado:
            return resultado.strip()
    except WebDriverException:
        pass
    return None


def _monitorar_email_login(driver, callback, tempo_limite_segundos: int = 900):
    """
    Fica de olho no e-mail enquanto a janela de login manual estiver aberta
    (ou até `tempo_limite_segundos`): tanto o que for digitado no campo de
    e-mail da Microsoft, quanto — se o login passar direto (sessão já
    ativa) — o que aparecer na própria tela do CRM depois de logado. Chama
    `callback(email)` assim que tiver certeza do valor.
    """
    ultimo_email = ""
    fim = time.time() + tempo_limite_segundos

    while time.time() < fim:
        try:
            url_atual = driver.current_url  # se a janela foi fechada, isso lança WebDriverException
        except WebDriverException:
            break

        try:
            campos = driver.find_elements("css selector", _SELETOR_CAMPO_EMAIL_LOGIN)
            for campo in campos:
                valor = (campo.get_attribute("value") or "").strip()
                if valor and "@" in valor:
                    ultimo_email = valor
        except WebDriverException:
            pass
        except Exception:  # pylint: disable=broad-except
            pass


        time.sleep(1.5)

    if ultimo_email:
        callback(ultimo_email)


def criar_driver_worker(perfil_id: int, headless: bool = False):
    """Cria um driver pronto para uso na automação, usando a pasta do perfil informado."""
    garantir_pastas()
    return criar_driver(pasta_perfil(perfil_id), headless=headless)


# ---------------------------------------------------------------------------
# Detecção "best-effort" de login. A sessão do Colaboraread depende do
# usuário entrar pelo Prisma e escolher o polo, então aqui só dá pra saber:
#   - "Logado" ............ o Colaboraread ainda abre direto (sessão viva)
#   - "Logado no Prisma" .. o Prisma abre sem pedir senha
#   - "Não logado" ........ o Prisma mostra a tela de login
# ---------------------------------------------------------------------------
def detectar_login(perfil_id: int, log=print):
    """Devolve (status, email) — email é sempre None aqui (edite pelo lápis)."""
    garantir_pastas()
    driver = None
    try:
        driver = criar_driver(pasta_perfil(perfil_id), headless=True)
        driver.set_page_load_timeout(30)

        driver.get(config.URL_COLABORA_MATRICULA)
        time.sleep(3)
        if driver.find_elements(By.ID, "ematCd"):
            return "Logado", None

        driver.get(config.URL_PRISMA)
        time.sleep(5)  # SPA: dá tempo de renderizar/redirecionar
        if driver.find_elements(By.CSS_SELECTOR, "input[type='password']"):
            return "Não logado", None
        if "prisma.kroton.com.br" in driver.current_url.lower():
            return "Logado no Prisma", None
        return "Não foi possível verificar", None

    except WebDriverException as erro:
        log(f"[verificação de login] erro: {erro}")
        return "Não foi possível verificar", None
    except Exception as erro:  # pylint: disable=broad-except
        log(f"[verificação de login] erro inesperado: {erro}")
        return "Não foi possível verificar", None
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:  # pylint: disable=broad-except
                pass
