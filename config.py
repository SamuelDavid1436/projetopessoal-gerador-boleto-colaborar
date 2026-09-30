# -*- coding: utf-8 -*-
"""
config.py
=========
Todas as configurações "ajustáveis" do projeto ficam aqui, separadas da lógica.
"""

# ---------------------------------------------------------------------------
# URLs — Prisma (acesso manual do usuário) e Colaboraread (automação)
# ---------------------------------------------------------------------------
URL_PRISMA = "https://prisma.kroton.com.br/"   # /home quebra quando não está logado
URL_PRISMA_LOGIN = "https://prisma.kroton.com.br/login"   # tela com o botão ACESSAR
DOMINIO_PRISMA = "prisma.kroton.com.br"
DOMINIO_COLABORA = "extranet.colaboraread.com.br"
URL_COLABORA_BASE = f"https://{DOMINIO_COLABORA}"
URL_COLABORA_INDEX = f"{URL_COLABORA_BASE}/index/index"
URL_COLABORA_MATRICULA = f"{URL_COLABORA_BASE}/secretaria/matricula/index.action"
URL_COLABORA_PARCELAS = (
    f"{URL_COLABORA_BASE}/secretaria/matricula/listparcelas.action?edmatric.ematCd={{ra}}"
)
URL_COLABORA_BOLETO = f"{URL_COLABORA_BASE}/secretaria/matricula/listboletos.action"
# Tela "Alterar Dados" da matrícula: fonte do celular e do responsável financeiro
URL_COLABORA_DADOS = (
    f"{URL_COLABORA_BASE}/secretaria/matricula/formmatricula.action"
    "?alteraDados=true&edmatric.ematCd={ra}&geoferta.gofeCd="
)

# Tempo máximo (segundos) que cada janela espera o usuário fazer
# Prisma -> polo -> Portais -> Colaborar antes de desistir daquele perfil.
TEMPO_ESPERA_ACESSO_COLABORA = 900

# ---------------------------------------------------------------------------
# Pasta onde fica o "perfil" persistente do Chrome (mantém o login salvo
# entre execuções). Cada janela paralela usa uma cópia deste perfil.
# ---------------------------------------------------------------------------
import os


def _pasta_do_programa() -> str:
    """Pasta ONDE O PROGRAMA ESTÁ INSTALADO (ao lado do .exe). Nunca usar
    dirname(__file__) num .exe: lá dentro __file__ aponta pra pasta temporária
    de extração do PyInstaller (_MEIxxxx), que é APAGADA quando o programa
    fecha — tudo que fosse gravado nela (resultados, backup, login) sumiria."""
    import sys
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _pasta_gravavel(caminho: str) -> bool:
    """True se dá pra criar a pasta E gravar um arquivo nela (makedirs sozinho
    não basta: proteções do Windows podem deixar criar a pasta e bloquear a escrita)."""
    try:
        os.makedirs(caminho, exist_ok=True)
        teste = os.path.join(caminho, ".teste_escrita")
        with open(teste, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(teste)
        return True
    except OSError:
        return False


def _descobrir_pasta_documentos() -> str:
    """
    Tenta usar a pasta Documentos do usuário. Em algumas máquinas (comum com
    OneDrive redirecionando a pasta Documentos) essa pasta não existe ou não
    pode ser criada normalmente pelo Python — nesse caso, cai para uma pasta
    "CapturaBoletoColabora_Dados" ao lado do próprio programa, que sempre
    funciona.
    """
    candidatas = [os.path.join(os.path.expanduser("~"), "Documents", "CapturaBoletoColabora")]
    if os.environ.get("LOCALAPPDATA"):
        candidatas.append(os.path.join(os.environ["LOCALAPPDATA"], "CapturaBoletoColabora", "Dados"))
    candidatas.append(os.path.join(_pasta_do_programa(), "CapturaBoletoColabora_Dados"))
    for candidata in candidatas:
        if _pasta_gravavel(candidata):
            return candidata
    return candidatas[-1]


def _descobrir_pasta_local_app() -> str:
    """
    Pasta pra dados "vivos" que mudam o tempo todo — hoje só os perfis do
    Chrome — de propósito FORA do OneDrive/Documentos. Um perfil de
    navegador é basicamente um banco de dados sendo escrito a cada poucos
    segundos; se ficar numa pasta sincronizada (OneDrive, Google Drive
    etc), o sincronizador disputando os mesmos arquivos com o Chrome causa
    exatamente os travamentos/corrupção de perfil vistos na prática
    ("Chrome failed to start: crashed", sessão perdida do nada, perfil
    corrompido). %LOCALAPPDATA% nunca é sincronizado por padrão — é
    literalmente pra esse tipo de dado que ele existe.
    """
    candidatas = []
    if os.environ.get("LOCALAPPDATA"):
        candidatas.append(os.path.join(os.environ["LOCALAPPDATA"], "CapturaBoletoColabora"))
    candidatas.append(os.path.join(os.path.expanduser("~"), "CapturaBoletoColabora"))
    candidatas.append(os.path.join(_pasta_do_programa(), "CapturaBoletoColabora_Perfis"))
    for candidata in candidatas:
        if _pasta_gravavel(candidata):
            return candidata
    return candidatas[-1]


PASTA_DOCUMENTOS = _descobrir_pasta_documentos()
PASTA_SAIDA = os.path.join(PASTA_DOCUMENTOS, "saida")
PASTA_LOGS = os.path.join(PASTA_DOCUMENTOS, "logs")

PASTA_APP_LOCAL = _descobrir_pasta_local_app()
PASTA_SCREENSHOTS = os.path.join(PASTA_LOGS, "screenshots")  # 1 print por erro

# Log temporário só pra permitir retomar em caso de queda/travamento da
# automação NO MEIO de uma execução (não é histórico permanente — é
# descartado assim que a execução termina normalmente, e também é
# descartado/reiniciado sempre que uma NOVA importação é iniciada).
ARQUIVO_RETOMADA = os.path.join(PASTA_LOGS, "execucao_em_andamento.json")


# ---------------------------------------------------------------------------
# Paleta de cores / identidade visual
# ---------------------------------------------------------------------------
# Identidade própria (diferente do Captura Link): índigo + coral.
# Os nomes COR_VERDE/COR_DOURADO foram mantidos só porque a interface
# inteira usa essas constantes -- os valores é que mudaram.
COR_VERDE = "#4052D6"          # 30% - cor de marca: índigo (navegação, cabeçalhos, ícones)
COR_VERDE_ESCURO = "#2F3FB0"   # hover/variação escura do índigo
COR_DOURADO = "#FF7A45"        # 10% - destaque/chamada para ação: coral (botões principais)
COR_DOURADO_ESCURO = "#E0612E"  # hover do coral
COR_CREME = "#F1F3FC"          # 60% - fundo claro da barra lateral (azulado)
COR_CINZA_ESCURO = "#3B3F52"
COR_GELO = "#F8F9FD"           # 60% - fundo claro (variação)

NOME_PRODUTO = "Captura Boleto Colaboraread"

# ---------------------------------------------------------------------------
# Meses (usados no seletor "mês/ano de referência")
# ---------------------------------------------------------------------------
MESES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]

# Relatório separado (ver data_io.salvar_relatorio_meses): as colunas são
# TRAVADAS (fixas) entre esse mês/ano mínimo e o máximo — sempre a mesma
# quantidade de blocos de coluna no arquivo, independente do aluno. Mude
# aqui quando precisar avançar o período (ex: virou o ano, agora é de
# Janeiro a Dezembro/2027).
MES_MINIMO_RELATORIO = "Junho"
ANO_MINIMO_RELATORIO = "2026"
MES_MAXIMO_RELATORIO = "Dezembro"
ANO_MAXIMO_RELATORIO = "2026"

# ---------------------------------------------------------------------------
# Colunas do arquivo de saída (CSV e Excel) — ordem final
# ---------------------------------------------------------------------------
COLUNAS_SAIDA = [
    "RA",
    "Perfil",                 # qual dos perfis (janela) consultou esse RA
    "Polo",                   # polo informado na base (modo automático); vazio no modo manual
    "Nome",
    "CPF",
    "Celular",               # Fone Celular da tela de dados (formmatricula)
    "CPF Responsavel",
    "Nome Responsavel",
    "Situacao",              # Inadimplente / Adimplente (ícone de pendência financeira)
    "Situacao Matricula",    # ex: Matricula Ativa
    "Parcelas Encontradas",
    "Boletos Gerados",
    "Status da Consulta",    # OK / Erro: <mensagem>
]

# Colunas que vão pro resultado.csv/.xlsx e pro backup_parcial.csv: sem as
# colunas de responsável — Nome e CPF já saem com os da tela "Alterar Dados".
COLUNAS_ARQUIVO_RESULTADO = [c for c in COLUNAS_SAIDA if c not in ("CPF Responsavel", "Nome Responsavel")]

# Quantas vezes tentar ler os dados cadastrais (celular, nome e CPF) do MESMO
# aluno antes de desistir e usar os dados de reserva.
TENTATIVAS_DADOS_CADASTRAIS = 3

# Entrada automática (base com coluna POLO): tempos em segundos
TEMPO_LOGIN_AUTOMATICO = 25      # espera o /home depois de clicar em ACESSAR; passou disso, pede login manual
TEMPO_ESPERA_POLO = 40           # espera a lista de polos aparecer na /home
TENTATIVAS_SELECAO_POLO = 3      # quantas vezes tenta selecionar e confirmar o polo

# Tempo máximo de espera (segundos) por elemento na página
TIMEOUT_PADRAO = 25

# ---------------------------------------------------------------------------
# Histórico de execuções (usado no dashboard/página de Execuções)
# ---------------------------------------------------------------------------
ARQUIVO_HISTORICO = os.path.join(PASTA_LOGS, "historico_execucoes.json")

VERSAO_APP = "0.9.0 (amostra)"

# ---------------------------------------------------------------------------
# Ícone, logo e manual do aplicativo (pasta assets/, ao lado deste arquivo)
# Usa sys._MEIPASS quando empacotado com PyInstaller (.exe), senão a pasta
# deste próprio arquivo — assim os caminhos funcionam tanto rodando com
# "python main.py" quanto num .exe empacotado no futuro.
# ---------------------------------------------------------------------------
import sys

PASTA_PROJETO = os.path.dirname(os.path.abspath(__file__))


def caminho_recurso(*partes) -> str:
    base = getattr(sys, "_MEIPASS", PASTA_PROJETO)
    return os.path.join(base, *partes)


CAMINHO_ICONE = caminho_recurso("assets", "icone.ico")
CAMINHO_LOGO = caminho_recurso("assets", "logo.png")
CAMINHO_MANUAL = caminho_recurso("assets", "manual.pdf")
CAMINHO_MANUAL_WORD = caminho_recurso("assets", "manual.docx")  # cópia editável, se precisar

# ---------------------------------------------------------------------------
# Perfis (até 3 logins independentes do Chrome, cada um com apelido próprio)
# ---------------------------------------------------------------------------
NUM_PERFIS = 3
PASTA_PERFIS = os.path.join(PASTA_APP_LOCAL, "perfis")
ARQUIVO_PERFIS_META = os.path.join(PASTA_APP_LOCAL, "perfis_meta.json")