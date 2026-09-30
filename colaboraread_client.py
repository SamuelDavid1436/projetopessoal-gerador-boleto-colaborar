# -*- coding: utf-8 -*-
"""
colaboraread_client.py
======================
Toda a interação Selenium com o Colaboraread (extranet). Substitui o
crm_client.py do Captura Link de Pagamento, mantendo a MESMA interface
usada pelo runner.py:

    cliente = ColaboraClient(driver, log=...)
    registro = cliente.consultar_ra(ra)   # dict, nunca lança exceção
    cliente.sessao_morta                  # True se o navegador morreu

Pré-condição (responsabilidade do usuário, na própria janela do Chrome):
  Prisma (login) -> selecionar o polo -> Portais -> Colaborar.
Ver runner.py / aguardar_colaborar: cada janela espera o usuário chegar no
Colaboraread antes de começar a processar RAs.

Fluxo por RA:
  1. secretaria/matricula/index.action -> campo ematCd -> "Listar matrículas"
  2. lê a linha da matrícula na tabela #lst (nome, CPF, telefone, pendência)
  3. listparcelas.action?edmatric.ematCd=RA -> lê TODAS as parcelas
  4. para cada parcela com botão "Gerar boleto", reenvia o POST do formulário
     (listboletos.action) com os cookies da sessão, recebe o PDF em memória
     e extrai a linha digitável (47 dígitos). Nada é salvo em disco.
"""
import io
import os
import re
import time
from datetime import datetime
from html.parser import HTMLParser

import pdfplumber
import requests

import validacao
from selenium.common.exceptions import (
    InvalidSessionIdException,
    NoSuchWindowException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import config

# Linha digitável de boleto bancário: 47 dígitos, com ou sem pontos/espaços
LINHA_RE = re.compile(r"\d{5}\.?\d{5}\s*\d{5}\.?\d{6}\s*\d{5}\.?\d{6}\s*\d\s*\d{14}")

_ERROS_SESSAO_MORTA = (
    "invalid session id",
    "no such window",
    "chrome not reachable",
    "disconnected",
    "session deleted",
    "target window already closed",
)


class _LeitorInputs(HTMLParser):
    """Coleta {name: value} e {id: value} de todos os <input> de uma página."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.por_nome, self.por_id = {}, {}

    def handle_starttag(self, tag, attrs):
        if tag != "input":
            return
        a = dict(attrs)
        valor = (a.get("value") or "").strip()
        if a.get("name"):
            self.por_nome.setdefault(a["name"], valor)
        if a.get("id"):
            self.por_id.setdefault(a["id"], valor)


class SessaoColaboraExpirada(Exception):
    """A tela de matrícula não abriu — a sessão do Colaboraread caiu/expirou."""


def _modulo10(numero: str) -> int:
    soma = 0
    for i, c in enumerate(reversed(numero)):
        p = int(c) * (2 if i % 2 == 0 else 1)
        soma += p // 10 + p % 10
    return (10 - soma % 10) % 10


def linha_digitavel_valida(linha: str) -> bool:
    """Confere os 3 dígitos verificadores dos campos da linha digitável."""
    if len(linha) != 47 or not linha.isdigit():
        return False
    return (_modulo10(linha[0:9]) == int(linha[9])
            and _modulo10(linha[10:20]) == int(linha[20])
            and _modulo10(linha[21:31]) == int(linha[31]))


def na_tela_colaboraread(driver) -> bool:
    """True se alguma aba do navegador está no Colaboraread (e já foca nela)."""
    try:
        for aba in driver.window_handles:
            driver.switch_to.window(aba)
            if config.DOMINIO_COLABORA in (driver.current_url or "").lower():
                return True
    except WebDriverException:
        pass
    return False


class ColaboraClient:
    def __init__(self, driver, log=print, timeout=None):
        self.driver = driver
        self.log = log
        self.timeout = timeout or config.TIMEOUT_PADRAO
        self.wait = WebDriverWait(driver, self.timeout)
        self.sessao_morta = False

    # ------------------------------------------------------------------
    # Sessão
    # ------------------------------------------------------------------
    def sessao_ativa(self) -> bool:
        """Abre a tela de matrícula e confere se o campo de busca apareceu."""
        try:
            self.driver.get(config.URL_COLABORA_MATRICULA)
            WebDriverWait(self.driver, 8).until(
                EC.presence_of_element_located((By.ID, "ematCd"))
            )
            return True
        except (TimeoutException, WebDriverException):
            return False

    def _session_requests(self):
        s = requests.Session()
        s.headers["User-Agent"] = self.driver.execute_script("return navigator.userAgent")
        s.headers["Referer"] = self.driver.current_url
        for c in self.driver.get_cookies():
            s.cookies.set(c["name"], c["value"], domain=c.get("domain"), path=c.get("path", "/"))
        return s

    # ------------------------------------------------------------------
    # Passo 1: buscar matrícula
    # ------------------------------------------------------------------
    def buscar_matricula(self, ra):
        self.driver.get(config.URL_COLABORA_MATRICULA)
        try:
            campo = self.wait.until(EC.presence_of_element_located((By.ID, "ematCd")))
        except TimeoutException as erro:
            raise SessaoColaboraExpirada(
                "tela de matrícula não carregou (sessão do Colaboraread expirou? "
                "entre de novo pelo Prisma -> polo -> Portais -> Colaborar)"
            ) from erro
        campo.clear()
        campo.send_keys(str(ra))
        self.driver.find_element(
            By.CSS_SELECTOR, "input[type=submit][value='Listar matrículas']"
        ).click()

        # espera a página recarregar (o campo antigo some) e terminar de carregar,
        # pra não ficar o timeout inteiro esperando quando o RA não existe
        self.wait.until(EC.staleness_of(campo))
        self.wait.until(lambda d: d.execute_script("return document.readyState") == "complete")

        xpath_linha = f"//table[@id='lst']//tr[td[normalize-space()='{ra}']]"
        encontradas = self.driver.find_elements(By.XPATH, xpath_linha)
        if not encontradas:
            return None  # matrícula não encontrada
        linha = encontradas[0]

        tds = linha.find_elements(By.TAG_NAME, "td")
        nome_td = tds[6]
        nome_links = nome_td.find_elements(By.TAG_NAME, "a")
        situacao_span = nome_td.find_elements(By.CSS_SELECTOR, "span.sample")
        return {
            "nome": (nome_links[0].text if nome_links else nome_td.text.split("\n")[0]).strip(),
            "situacao_matricula": situacao_span[0].text.strip() if situacao_span else "",
            "data_matricula": tds[7].text.strip(),
            "cpf": tds[8].text.strip(),
            "telefone": tds[9].text.strip(),
            "pendencia_financeira": bool(
                linha.find_elements(By.CSS_SELECTOR, "img[src*='form_money_no']")
            ),
        }

    # ------------------------------------------------------------------
    # Passo 1b: tela "Alterar Dados" (celular e responsável financeiro)
    # ------------------------------------------------------------------
    def ler_dados_cadastrais(self, ra) -> dict:
        """
        Lê a tela formmatricula.action em segundo plano (requests com a
        sessão do navegador, sem abrir página no Chrome). Campos:
          - celular: Fone Celular do aluno (edmatric.edaluno.ealuNrTelefoneCelular);
            se vazio, o Fone Celular de cobrança (ealuNrFoneCelularCob)
          - cpf_responsavel: edmatric.ematDsCpfFiador
          - nome_responsavel: edmatric.ematNmFiador
        Lança RuntimeError se a página não vier com o formulário.
        """
        r = self._session_requests().get(
            config.URL_COLABORA_DADOS.format(ra=ra), timeout=self.timeout
        )
        r.raise_for_status()
        if not r.encoding or r.encoding.lower() == "iso-8859-1":
            r.encoding = r.apparent_encoding or "iso-8859-1"
        leitor = _LeitorInputs()
        leitor.feed(r.text)
        nome, ids = leitor.por_nome, leitor.por_id
        if "edmatric.edaluno.ealuNrTelefoneCelular" not in nome and "foneCelular" not in ids:
            raise RuntimeError("tela de dados da matrícula não abriu (sessão expirada?)")
        celular = (nome.get("edmatric.edaluno.ealuNrTelefoneCelular")
                   or ids.get("foneCelular")
                   or nome.get("edmatric.edaluno.ealuNrFoneCelularCob") or "")
        return {
            "celular": celular,
            "cpf_responsavel": nome.get("edmatric.ematDsCpfFiador") or ids.get("cpfResponsavel", ""),
            "nome_responsavel": nome.get("edmatric.ematNmFiador") or ids.get("nomeResponsavel", ""),
        }

    def ler_dados_cadastrais_com_tentativas(self, ra, aluno: dict):
        """
        Tenta ler celular, CPF e nome do responsável até
        config.TENTATIVAS_DADOS_CADASTRAIS vezes no MESMO aluno (a tela às
        vezes vem incompleta ou falha na primeira). Junta o melhor de cada
        tentativa. Se depois das tentativas faltar algo, usa os dados do
        próprio aluno (nome/CPF/telefone da lista de matrículas) pra nunca
        ficar ponto ou campo vazio.
        Devolve (dados, avisos): dados = {celular, cpf_responsavel,
        nome_responsavel}; avisos = lista de textos sobre o que foi de reserva.
        """
        melhor = {"celular": "", "cpf_responsavel": "", "nome_responsavel": ""}
        ultimo_erro = None
        total = config.TENTATIVAS_DADOS_CADASTRAIS
        for tentativa in range(1, total + 1):
            try:
                dados = self.ler_dados_cadastrais(ra)
                if validacao.telefone_valido(dados["celular"]):
                    melhor["celular"] = dados["celular"]
                if validacao.cpf_valido(dados["cpf_responsavel"]):
                    melhor["cpf_responsavel"] = dados["cpf_responsavel"]
                if validacao.nome_valido(dados["nome_responsavel"]):
                    melhor["nome_responsavel"] = dados["nome_responsavel"]
                ultimo_erro = None
            except Exception as erro:  # pylint: disable=broad-except
                if self._e_sessao_morta(erro):
                    raise
                ultimo_erro = erro
            if all(melhor.values()):
                break
            if tentativa < total:
                time.sleep(1.0 * tentativa)

        avisos = []
        if not melhor["nome_responsavel"]:
            if validacao.nome_valido(aluno.get("nome")):
                melhor["nome_responsavel"] = aluno["nome"]
            avisos.append("sem nome do responsável: usado o nome do aluno")
        if not melhor["cpf_responsavel"]:
            if validacao.cpf_valido(aluno.get("cpf")):
                melhor["cpf_responsavel"] = aluno["cpf"]
            avisos.append("sem CPF do responsável: usado o CPF do aluno")
        if not melhor["celular"]:
            if validacao.telefone_valido(aluno.get("telefone")):
                melhor["celular"] = aluno["telefone"]
            avisos.append("celular não encontrado" if not melhor["celular"]
                          else "sem celular na tela de dados: usado o telefone da lista")
        if ultimo_erro is not None and avisos:
            avisos.append(f"última falha: {ultimo_erro}")
        return melhor, avisos

    # ------------------------------------------------------------------
    # Passo 2: parcelas
    # ------------------------------------------------------------------
    def listar_parcelas(self, ra):
        self.driver.get(config.URL_COLABORA_PARCELAS.format(ra=ra))
        xpath_linhas = "//table[.//th[normalize-space()='Parc.']]//tr[td]"
        try:
            self.wait.until(EC.presence_of_element_located(
                (By.XPATH, "//table[.//th[normalize-space()='Parc.']]")))
        except TimeoutException:
            return []

        parcelas = []
        for tr in self.driver.find_elements(By.XPATH, xpath_linhas):
            tds = tr.find_elements(By.TAG_NAME, "td")
            if len(tds) < 8:
                continue
            numero = tds[0].text.strip()
            parcelas.append({
                "Parcela": numero,
                "Vencimento": tds[1].text.strip(),
                "Valor": tds[2].text.strip(),
                "Situacao Mensalidade": tds[4].text.strip(),
                "Valor Faturado": tds[5].text.strip(),
                "Data Recebimento": tds[6].text.strip(),
                "_gera_boleto": bool(tr.find_elements(By.NAME, f"form{numero}{ra}")),
            })
        return parcelas

    # ------------------------------------------------------------------
    # Passo 3: gerar boleto (POST) e extrair linha digitável do PDF
    # ------------------------------------------------------------------
    def capturar_linha_digitavel_com_tentativas(self, ra, parcela):
        """Tenta gerar o boleto até config.TENTATIVAS_BOLETO vezes quando a falha
        parece passageira (lentidão/queda de conexão do site, resposta que não
        veio em PDF). Dígito verificador inválido não é repetido."""
        total = config.TENTATIVAS_BOLETO
        for tentativa in range(1, total + 1):
            try:
                return self.capturar_linha_digitavel(ra, parcela)
            except Exception as erro:  # pylint: disable=broad-except
                if self._e_sessao_morta(erro):
                    raise
                passageiro = isinstance(erro, requests.RequestException) or (
                    isinstance(erro, RuntimeError)
                    and ("não veio em PDF" in str(erro) or "não encontrada" in str(erro)))
                if not passageiro or tentativa == total:
                    raise
                self.log(f"RA {ra} parcela {parcela}: falha ao gerar o boleto "
                         f"({type(erro).__name__}) — tentando de novo ({tentativa + 1}/{total})...")
                time.sleep(2 * tentativa)

    def capturar_linha_digitavel(self, ra, parcela):
        form = self.driver.find_element(By.NAME, f"form{parcela}{ra}")
        action = form.get_attribute("action") or config.URL_COLABORA_BOLETO
        metodo = (form.get_attribute("method") or "post").lower()
        dados = {
            i.get_attribute("name"): i.get_attribute("value") or ""
            for i in form.find_elements(By.CSS_SELECTOR, "input[name]")
        }

        s = self._session_requests()
        if metodo == "get":
            r = s.get(action, params=dados, timeout=config.TIMEOUT_BOLETO)
        else:
            r = s.post(action, data=dados, timeout=config.TIMEOUT_BOLETO)
        r.raise_for_status()

        tipo = r.headers.get("Content-Type", "").lower()
        if "pdf" not in tipo:
            raise RuntimeError(f"o boleto não veio em PDF (Content-Type: {tipo or 'vazio'})")

        with pdfplumber.open(io.BytesIO(r.content)) as pdf:
            texto = "\n".join(p.extract_text() or "" for p in pdf.pages)

        m = LINHA_RE.search(texto)
        if not m:
            raise RuntimeError("linha digitável não encontrada no PDF")
        linha = re.sub(r"\D", "", m.group())
        if not linha_digitavel_valida(linha):
            raise RuntimeError(f"linha digitável com dígito verificador inválido ({linha})")
        return linha

    # ------------------------------------------------------------------
    # Fluxo completo de um RA (mesma interface do CrmClient.consultar_ra)
    # ------------------------------------------------------------------
    def consultar_ra(self, ra) -> dict:
        ra = str(ra).strip()
        registro = {coluna: "" for coluna in config.COLUNAS_SAIDA}
        registro["RA"] = ra
        registro["_parcelas_relatorio"] = []

        try:
            aluno = self.buscar_matricula(ra)
            if not aluno:
                registro["Status da Consulta"] = "Erro: RA não encontrado na base"
                return registro

            registro["Nome"] = aluno["nome"]
            registro["CPF"] = aluno["cpf"]
            registro["Situacao Matricula"] = aluno["situacao_matricula"]
            registro["Situacao"] = "Inadimplente" if aluno["pendencia_financeira"] else "Adimplente"

            dados, avisos = self.ler_dados_cadastrais_com_tentativas(ra, aluno)
            registro["Celular"] = dados["celular"]
            registro["CPF Responsavel"] = dados["cpf_responsavel"]
            registro["Nome Responsavel"] = dados["nome_responsavel"]
            aviso_dados = f" (AVISO: {'; '.join(avisos)})" if avisos else ""

            parcelas = self.listar_parcelas(ra)
            boletos, erros_boleto = 0, []
            for p in parcelas:
                p["Boleto Gerado"] = ""
                try:
                    venc = datetime.strptime(p["Vencimento"], "%d/%m/%Y")
                    p["Competencia"] = config.MESES[venc.month - 1]
                    p["Ano"] = str(venc.year)
                except ValueError:
                    p["Competencia"], p["Ano"] = "", ""

                if p.pop("_gera_boleto"):
                    try:
                        p["Boleto Gerado"] = self.capturar_linha_digitavel_com_tentativas(ra, p["Parcela"])
                        boletos += 1
                    except Exception as erro:  # pylint: disable=broad-except
                        if self._e_sessao_morta(erro):
                            raise
                        erros_boleto.append(f"parcela {p['Parcela']}: {erro}")
                        p["Boleto Gerado"] = f"Erro: {erro}"

            registro["_parcelas_relatorio"] = parcelas
            registro["Parcelas Encontradas"] = str(len(parcelas))
            registro["Boletos Gerados"] = str(boletos)

            if erros_boleto:
                registro["Status da Consulta"] = "Erro ao gerar boleto: " + "; ".join(erros_boleto)
                self._screenshot(ra)
            elif not parcelas:
                registro["Status da Consulta"] = "OK (nenhuma parcela encontrada)" + aviso_dados
            else:
                registro["Status da Consulta"] = "OK" + aviso_dados
            return registro

        except Exception as erro:  # pylint: disable=broad-except
            if self._e_sessao_morta(erro):
                self.sessao_morta = True
                registro["Status da Consulta"] = f"Erro: sessão do navegador caiu ({type(erro).__name__})"
                return registro
            if isinstance(erro, TimeoutException):
                registro["Status da Consulta"] = "Erro: tempo esgotado aguardando a página"
            else:
                registro["Status da Consulta"] = f"Erro: {erro}"
            self.log(f"RA {ra}: {registro['Status da Consulta']}")
            self._screenshot(ra)
            return registro

    # ------------------------------------------------------------------
    # Auxiliares
    # ------------------------------------------------------------------
    @staticmethod
    def _e_sessao_morta(erro) -> bool:
        if isinstance(erro, (InvalidSessionIdException, NoSuchWindowException)):
            return True
        texto = str(erro).lower()
        return any(t in texto for t in _ERROS_SESSAO_MORTA)

    def _screenshot(self, ra):
        try:
            os.makedirs(config.PASTA_SCREENSHOTS, exist_ok=True)
            nome = f"{datetime.now():%Y-%m-%d_%H-%M-%S}_RA_{ra}.png"
            self.driver.save_screenshot(os.path.join(config.PASTA_SCREENSHOTS, nome))
        except Exception:  # pylint: disable=broad-except
            pass


def aguardar_colaborar(driver, evento_parar, log=print, tempo_limite=900) -> bool:
    """
    Garante que a janela está no Colaboraread. Se a sessão ainda estiver
    ativa (cookies do perfil), entra direto. Senão, abre o Prisma e ESPERA
    o usuário fazer: login -> polo -> Portais -> Colaborar. A escolha do
    polo é sempre do usuário — a automação nunca faz isso sozinha.
    Devolve True quando chegou no Colaboraread; False se estourou o tempo
    ou o usuário clicou em Parar.
    """
    cliente = ColaboraClient(driver, log=log)
    if cliente.sessao_ativa():
        return True

    driver.get(config.URL_PRISMA)
    log("aguardando você entrar no Colaboraread nesta janela: "
        "Prisma (login) -> selecione o polo -> Portais -> Colaborar...")
    fim = time.time() + tempo_limite
    while time.time() < fim:
        if evento_parar is not None and evento_parar.is_set():
            return False
        if na_tela_colaboraread(driver):
            time.sleep(2)  # deixa a tela terminar de carregar
            log("Colaboraread detectado — começando.")
            return cliente.sessao_ativa()
        time.sleep(2)
    log(f"tempo esgotado ({tempo_limite // 60} min) esperando o acesso ao Colaborar.")
    return False
