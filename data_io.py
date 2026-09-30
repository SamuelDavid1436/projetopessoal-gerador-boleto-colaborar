# -*- coding: utf-8 -*-
"""
data_io.py
==========
Funções para ler a lista de RAs (CSV ou Excel, apenas uma coluna) e para
gravar o resultado final, também em CSV e Excel.
"""
import csv as csv_modulo
import os
from datetime import datetime

import pandas as pd

import config
import validacao


NOME_BACKUP_PARCIAL = "backup_parcial.csv"


def _detectar_separador_csv(caminho_arquivo: str):
    """
    Detecta o separador de um .csv de forma confiável. NÃO usa o
    sep=None/engine='python' do pandas pra isso — foi descoberto que esse
    modo erra sozinho (trunca valores!) em arquivos com uma única coluna
    de números e sem cabeçalho, que é exatamente o formato mais comum de
    planilha de RAs. csv.Sniffer() é bem mais confiável pra esse caso.

    Devolve o separador detectado, ou None se não achar nenhum de forma
    confiável — nesse caso, quem chama deve tratar a linha inteira como
    um campo só (arquivo de uma coluna sem delimitador nenhum).
    """
    with open(caminho_arquivo, "r", encoding="utf-8-sig", errors="ignore") as f:
        amostra = f.read(4096)
    if not amostra.strip():
        return None
    try:
        dialeto = csv_modulo.Sniffer().sniff(amostra, delimiters=",;\t")
        return dialeto.delimiter
    except csv_modulo.Error:
        return None  # sem delimitador confiável -- provavelmente uma coluna só


def extrair_ras_com_erro(caminho_resultado_csv: str) -> list:
    """
    Lê um arquivo resultado.csv de uma execução já concluída e devolve
    só os RAs das linhas cujo "Status da Consulta" indica erro (começa
    com "Erro") — usado pelo botão "Reprocessar erros", pra montar uma
    nova base só com quem falhou, sem precisar filtrar a planilha na mão.
    """
    if not os.path.isfile(caminho_resultado_csv):
        return []
    try:
        df = pd.read_csv(caminho_resultado_csv, sep=";", dtype=str, encoding="utf-8-sig")
    except (OSError, pd.errors.ParserError):
        return []
    if "RA" not in df.columns or "Status da Consulta" not in df.columns:
        return []

    status = df["Status da Consulta"].fillna("").astype(str).str.strip().str.lower()
    mascara_erro = status.str.startswith("erro")
    ras_com_erro = df.loc[mascara_erro, "RA"].dropna().astype(str).tolist()
    return ras_com_erro


def salvar_lista_ras(ras: list, caminho_destino: str, telefones: dict = None):
    """Salva uma lista simples de RAs num .csv (uma coluna, com cabeçalho
    'RA') — usado pra gerar a base de reprocessamento de erros. Sem BOM
    (utf-8 puro): com BOM, o cabeçalho "RA" vira "\\ufeffRA" e o filtro de
    cabeçalho de ler_lista_ras não reconhece mais como cabeçalho."""
    os.makedirs(os.path.dirname(caminho_destino), exist_ok=True)
    df = pd.DataFrame({"RA": ras})
    if telefones:  # preserva o telefone informado pelo usuário na base original
        df["Telefone"] = [telefones.get(ra, "") for ra in ras]
    df.to_csv(caminho_destino, index=False, encoding="utf-8")


def ler_lista_ras(caminho_arquivo: str) -> list:
    """
    Lê um arquivo CSV ou Excel contendo uma única coluna de RAs (com ou sem
    cabeçalho) e devolve uma lista de strings (RAs), sem valores vazios.

    IMPORTANTE: não remove RAs repetidos — se o mesmo RA aparecer mais de
    uma vez no arquivo importado, ele é processado todas as vezes que
    aparecer. Isso é proposital: a mesma base pode ser rodada várias vezes
    por semana (gerando link atualizado pra quem ainda não pagou), e nada
    aqui trava ou pula RA repetido, nem entre execuções nem dentro do
    mesmo arquivo.
    """
    extensao = os.path.splitext(caminho_arquivo)[1].lower()

    if extensao == ".csv":
        separador = _detectar_separador_csv(caminho_arquivo)
        if separador is None:
            # sem delimitador confiável -- trata a linha inteira como um
            # campo só (caso mais comum: uma coluna de RAs, sem cabeçalho)
            df = pd.read_csv(caminho_arquivo, sep="\x00", engine="python", header=None, dtype=str)
        else:
            df = pd.read_csv(caminho_arquivo, sep=separador, engine="python", header=None, dtype=str)
    elif extensao in (".xlsx", ".xls"):
        df = pd.read_excel(caminho_arquivo, header=None, dtype=str)
    else:
        raise ValueError(
            f"Formato de arquivo não suportado: {extensao}. Use .csv, .xlsx ou .xls."
        )

    # pega a primeira coluna, remove vazios e possível cabeçalho textual
    primeira_coluna = df.iloc[:, 0].dropna().astype(str).str.strip()
    ras = [ra for ra in primeira_coluna.tolist() if ra and ra.upper() not in ("RA", "MATRICULA", "MATRÍCULA")]

    return ras


_NOMES_COLUNA_TELEFONE = ("TELEFONE", "CELULAR", "FONE", "WHATSAPP", "WHATS", "CONTATO")


def ler_telefones_base(caminho_arquivo: str) -> dict:
    """
    Telefone opcional informado pelo usuário na base importada. Se existir,
    SEMPRE tem prioridade sobre o telefone cadastrado no Colaboraread (vale
    pro relatório e pra base de disparo).

    A coluna é reconhecida pelo cabeçalho (Telefone, Celular, Fone,
    WhatsApp...). Sem cabeçalho, a 2ª coluna é considerada telefone.
    RA continua sendo sempre a 1ª coluna. Devolve {ra: telefone}.
    """
    extensao = os.path.splitext(caminho_arquivo)[1].lower()
    if extensao == ".csv":
        separador = _detectar_separador_csv(caminho_arquivo)
        if separador is None:
            return {}  # uma coluna só -- não tem telefone
        df = pd.read_csv(caminho_arquivo, sep=separador, engine="python", header=None, dtype=str)
    elif extensao in (".xlsx", ".xls"):
        df = pd.read_excel(caminho_arquivo, header=None, dtype=str)
    else:
        return {}
    if df.shape[1] < 2 or df.empty:
        return {}

    cabecalho = [str(v or "").strip().upper() for v in df.iloc[0].tolist()]
    tem_cabecalho = not str(df.iloc[0, 0] or "").strip().isdigit()
    if tem_cabecalho:
        idx_tel = next((i for i, c in enumerate(cabecalho)
                        if any(nome in c for nome in _NOMES_COLUNA_TELEFONE)), None)
        if idx_tel is None:
            return {}
        dados = df.iloc[1:]
    else:
        idx_tel, dados = 1, df

    telefones = {}
    for _, linha in dados.iterrows():
        ra = str(linha.iloc[0] or "").strip()
        tel = linha.iloc[idx_tel]
        if ra and ra.lower() != "nan" and pd.notna(tel) and str(tel).strip():
            tel = str(tel).strip()
            if tel.endswith(".0"):  # Excel lê número como 11999999999.0
                tel = tel[:-2]
            telefones[ra] = tel
    return telefones


def nome_final(registro: dict) -> str:
    """Nome do responsável (tela Alterar Dados); se vier vazio ou "." (sem
    responsável), usa o nome do aluno. Nunca devolve ponto."""
    for chave in ("Nome Responsavel", "Nome"):
        if validacao.nome_valido(registro.get(chave)):
            return str(registro[chave]).strip()
    return ""


def cpf_final(registro: dict) -> str:
    """CPF do responsável; se vier vazio/00000000009, usa o CPF do aluno."""
    for chave in ("CPF Responsavel", "CPF"):
        if validacao.cpf_valido(registro.get(chave)):
            return str(registro[chave]).strip()
    return ""


def _linha_resultado(registro: dict) -> dict:
    """Linha do resultado/backup: Nome e CPF vêm da tela "Alterar Dados"
    (responsável) quando existirem; se a consulta falhou e a tela não foi
    lida, mantém o Nome/CPF da lista pra não perder a identificação do RA."""
    linha = {c: registro.get(c, "") for c in config.COLUNAS_ARQUIVO_RESULTADO}
    linha["Nome"] = nome_final(registro) or registro.get("Nome", "")
    linha["CPF"] = cpf_final(registro) or registro.get("CPF", "")
    return linha


def salvar_resultado(registros: list, pasta_saida: str = None, momento: datetime = None) -> tuple:
    """
    Salva a lista de registros (lista de dicionários, chaves = config.COLUNAS_SAIDA)
    numa SUBPASTA própria dentro da pasta de saída, nomeada com a data/hora
    da importação (`momento` — normalmente o início da execução). Assim,
    cada vez que uma base é importada e processada, os arquivos ficam
    isolados na pasta daquela execução específica, sem se misturar com
    execuções anteriores ou seguintes.

    Exemplo: duas importações no mesmo dia geram duas pastas diferentes:
        saida/2026-07-20_14-42-05/resultado.csv
        saida/2026-07-20_14-42-05/resultado.xlsx
        saida/2026-07-20_15-00-12/resultado.csv
        saida/2026-07-20_15-00-12/resultado.xlsx

    Retorna (caminho_csv, caminho_xlsx).
    """
    pasta_saida = pasta_saida or config.PASTA_SAIDA
    momento = momento or datetime.now()

    nome_pasta_execucao = momento.strftime("%Y-%m-%d_%H-%M-%S")
    pasta_execucao = os.path.join(pasta_saida, nome_pasta_execucao)
    os.makedirs(pasta_execucao, exist_ok=True)

    df = pd.DataFrame([_linha_resultado(r) for r in registros], columns=config.COLUNAS_ARQUIVO_RESULTADO)

    caminho_csv = os.path.join(pasta_execucao, "resultado.csv")
    caminho_xlsx = os.path.join(pasta_execucao, "resultado.xlsx")

    df.to_csv(caminho_csv, index=False, encoding="utf-8-sig", sep=";")
    df.to_excel(caminho_xlsx, index=False)

    return caminho_csv, caminho_xlsx


# Sub-colunas de cada bloco de mês no relatório largo (mesmo padrão do
# Captura Link de Pagamento, com "Boleto Gerado" no lugar de "Link Pagamento").
_SUBCOLUNAS_POR_MES = ["Situacao Mensalidade", "Valor Pago", "Vencimento", "Boleto Gerado"]

# Ordem final do relatório: RA, Nome, CPF, Telefone, Situação e depois um
# bloco fixo pra cada mês de config.MES_MINIMO_RELATORIO até MES_MAXIMO_RELATORIO.
_COLUNAS_FIXAS_INICIO = ["RA", "Nome", "CPF", "Celular", "Situacao"]


def _meses_fixos_relatorio() -> list:
    """Lista travada de (mês, ano) — de config.MES_MINIMO_RELATORIO/
    ANO_MINIMO_RELATORIO até config.MES_MAXIMO_RELATORIO/ANO_MAXIMO_RELATORIO,
    inclusive nas duas pontas. Suporta virar o ano no meio."""
    idx_ini = config.MESES.index(config.MES_MINIMO_RELATORIO)
    idx_fim = config.MESES.index(config.MES_MAXIMO_RELATORIO)
    ano_ini = int(config.ANO_MINIMO_RELATORIO)
    ano_fim = int(config.ANO_MAXIMO_RELATORIO)

    meses = []
    ano_atual, idx_atual = ano_ini, idx_ini
    while (ano_atual, idx_atual) <= (ano_fim, idx_fim):
        meses.append((config.MESES[idx_atual], str(ano_atual)))
        idx_atual += 1
        if idx_atual > 11:
            idx_atual = 0
            ano_atual += 1
    return meses


def _sem_rs(valor) -> str:
    return str(valor or "").replace("R$", "").strip()


def salvar_relatorio_meses(resultados: list, pasta_saida: str = None, momento: datetime = None) -> tuple:
    """
    Gera o relatorio_meses.csv/.xlsx (o arquivo que o usuário recebe), uma
    linha por aluno, com as colunas:

        RA | Nome | CPF | Telefone | Situação | <Mês> - Situacao Mensalidade |
        <Mês> - Valor Pago | <Mês> - Vencimento | <Mês> - Boleto Gerado | ... (Junho a Dezembro)

    - Situação: Inadimplente/Adimplente (ícone de pendência financeira no
      Colaboraread), "RA não encontrado na base" ou "Erro na consulta: ...".
    - <Mês>: pelo VENCIMENTO da parcela.
      - Situacao Mensalidade: texto do Colaboraread (Recebida (PIX),
        Em Aberto, Não Gerada...) ou "Sem mensalidade" se não há parcela.
      - Valor Pago: coluna "Valor faturado" do Colaboraread, sem "R$".
      - Vencimento: data de vencimento da tabela de parcelas do Colaboraread.
      - Boleto Gerado: linha digitável (só parcelas com botão Gerar boleto).

    `resultados`: registros do runner, cada um com "_parcelas_relatorio"
    (ver colaboraread_client.consultar_ra). Salva na mesma pasta da
    execução que o resultado.csv/.xlsx. Retorna (caminho_csv, caminho_xlsx).
    """
    pasta_saida = pasta_saida or config.PASTA_SAIDA
    momento = momento or datetime.now()

    nome_pasta_execucao = momento.strftime("%Y-%m-%d_%H-%M-%S")
    pasta_execucao = os.path.join(pasta_saida, nome_pasta_execucao)
    os.makedirs(pasta_execucao, exist_ok=True)

    meses_fixos = _meses_fixos_relatorio()

    colunas_finais = list(_COLUNAS_FIXAS_INICIO)
    for mes, _ano in meses_fixos:
        for subcoluna in _SUBCOLUNAS_POR_MES:
            colunas_finais.append(f"{mes} - {subcoluna}")

    linhas = []
    for registro in resultados:
        linha = {coluna: registro.get(coluna, "") for coluna in _COLUNAS_FIXAS_INICIO}
        # Nome e CPF: só os da tela "Alterar Dados" (sem colunas duplicadas)
        linha["Nome"] = nome_final(registro)
        linha["CPF"] = cpf_final(registro)
        parcelas = registro.get("_parcelas_relatorio", []) or []
        parcelas_por_mes = {(p.get("Competencia"), str(p.get("Ano"))): p for p in parcelas}

        algum_mes_preenchido = False
        for mes, ano in meses_fixos:
            dados_mes = parcelas_por_mes.get((mes, ano))
            if dados_mes is not None:
                linha[f"{mes} - Situacao Mensalidade"] = dados_mes.get("Situacao Mensalidade", "")
                linha[f"{mes} - Valor Pago"] = _sem_rs(dados_mes.get("Valor Faturado"))
                linha[f"{mes} - Vencimento"] = dados_mes.get("Vencimento", "")
                linha[f"{mes} - Boleto Gerado"] = dados_mes.get("Boleto Gerado", "")
                algum_mes_preenchido = True
            else:
                linha[f"{mes} - Situacao Mensalidade"] = "Sem mensalidade"
                linha[f"{mes} - Valor Pago"] = ""
                linha[f"{mes} - Vencimento"] = ""
                linha[f"{mes} - Boleto Gerado"] = ""

        sem_situacao = not str(linha.get("Situacao", "")).strip()
        if sem_situacao and not algum_mes_preenchido:
            status_consulta = str(registro.get("Status da Consulta", "") or "")
            eh_outro_erro = (
                status_consulta.lower().startswith("erro")
                and "não encontrado" not in status_consulta.lower()
            )
            if eh_outro_erro:
                linha["Situacao"] = f"Erro na consulta: {status_consulta[len('Erro:'):].strip()}"
            else:
                linha["Situacao"] = "RA não encontrado na base"

        linhas.append(linha)

    df = pd.DataFrame(linhas, columns=colunas_finais)
    # cabeçalho igual ao modelo: "Situação" com acento
    df = df.rename(columns={"Situacao": "Situação", "Celular": "Telefone"})

    caminho_csv = os.path.join(pasta_execucao, "relatorio_meses.csv")
    caminho_xlsx = os.path.join(pasta_execucao, "relatorio_meses.xlsx")

    df.to_csv(caminho_csv, index=False, encoding="utf-8-sig", sep=";")
    df.to_excel(caminho_xlsx, index=False)

    return caminho_csv, caminho_xlsx


def telefone_disparo(telefone) -> str:
    """Normaliza pro formato do disparo: 55 + DDD + número, só dígitos.
    Ex: (11) 95249-7902 -> 5511952497902. Se não der pra montar um número
    válido (sem DDD, curto demais), devolve só os dígitos originais."""
    d = "".join(c for c in str(telefone or "") if c.isdigit()).lstrip("0")
    if d.startswith("55") and len(d) in (12, 13):
        return d
    if len(d) in (10, 11):  # DDD + fixo (8) ou celular (9)
        return "55" + d
    return d


def _ultimo_boleto(registro: dict):
    """Parcela com boleto (linha digitável válida) de vencimento mais recente
    — o "último código gerado" pro aluno. Devolve (mes, vencimento, linha) ou None."""
    melhor = None
    for p in registro.get("_parcelas_relatorio", []) or []:
        linha = str(p.get("Boleto Gerado") or "")
        if not (linha.isdigit() and len(linha) == 47):
            continue
        try:
            venc = datetime.strptime(p.get("Vencimento", ""), "%d/%m/%Y")
        except ValueError:
            continue
        if melhor is None or venc > melhor[0]:
            melhor = (venc, p.get("Competencia") or config.MESES[venc.month - 1], linha)
    return (melhor[1], melhor[0].strftime("%d/%m/%Y"), melhor[2]) if melhor else None


def salvar_base_disparo(resultados: list, pasta_saida: str = None, momento: datetime = None) -> tuple:
    """
    Arquivo enxuto pra disparo (base_disparo.csv/.xlsx), no modelo
    Base_Links_para_Disparo, uma linha por aluno que tem boleto:

        RA | CPF | Nome | Telefone | MÊS | Vencimento | <Mês> - Boleto Gerado

    - CPF e Nome: os da tela "Alterar Dados" (CPF/nome do responsável, mesma
      origem do celular). Sem colunas duplicadas.

    - Traz só o ÚLTIMO código gerado (parcela com boleto de vencimento mais
      recente). Alunos sem nenhum boleto ficam de fora.
    - MÊS: mês desse último boleto (por aluno).
    - Cabeçalho da última coluna: "<Mês> - Boleto Gerado" com o mês que mais
      aparece na base (normalmente todos são o mesmo). Se houver alunos com
      mês diferente, o MÊS de cada linha é que vale.
    Retorna (caminho_csv, caminho_xlsx).
    """
    pasta_saida = pasta_saida or config.PASTA_SAIDA
    momento = momento or datetime.now()
    pasta_execucao = os.path.join(pasta_saida, momento.strftime("%Y-%m-%d_%H-%M-%S"))
    os.makedirs(pasta_execucao, exist_ok=True)

    linhas = []
    for registro in resultados:
        ultimo = _ultimo_boleto(registro)
        if not ultimo:
            continue
        mes, vencimento, linha = ultimo
        linhas.append({
            "RA": str(registro.get("RA", "")),
            "CPF": cpf_final(registro),  # responsável (tela Alterar Dados); reserva: CPF do aluno
            "Nome": nome_final(registro),  # responsável (tela Alterar Dados); reserva: nome do aluno
            "Telefone": telefone_disparo(registro.get("Celular", "")),
            "MÊS": mes,
            "Vencimento": vencimento,
            "_boleto": linha,
        })

    meses = [l["MÊS"] for l in linhas]
    mes_cabecalho = max(set(meses), key=meses.count) if meses else ""
    coluna_boleto = f"{mes_cabecalho} - Boleto Gerado" if mes_cabecalho else "Boleto Gerado"
    for l in linhas:
        l[coluna_boleto] = l.pop("_boleto")

    colunas = ["RA", "CPF", "Nome", "Telefone",
               "MÊS", "Vencimento", coluna_boleto]
    df = pd.DataFrame(linhas, columns=colunas)

    caminho_csv = os.path.join(pasta_execucao, "base_disparo.csv")
    caminho_xlsx = os.path.join(pasta_execucao, "base_disparo.xlsx")
    df.to_csv(caminho_csv, index=False, encoding="utf-8-sig", sep=";")

    # Excel: tudo como texto (linha digitável de 47 dígitos viraria 2,38E+46)
    with pd.ExcelWriter(caminho_xlsx, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Planilha1")
        ws = writer.sheets["Planilha1"]
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.number_format = "@"
            tel = row[3]  # Telefone como número, igual ao modelo (formato "0")
            if str(tel.value or "").isdigit() and str(tel.value).startswith("55"):
                tel.value = int(tel.value)
                tel.number_format = "0"
        larguras = {"A": 13, "B": 14, "C": 46, "D": 16, "E": 11, "F": 12, "G": 52}
        for col, largura in larguras.items():
            ws.column_dimensions[col].width = largura

    return caminho_csv, caminho_xlsx


def gravar_backup_linha(registro: dict, pasta_saida: str = None, momento: datetime = None) -> str:
    """
    BACKUP em disco, visível pro usuário: acrescenta 1 linha (o RA que acabou
    de ser processado) em saida/<data-hora>/backup_parcial.csv e força a
    gravação no disco (flush + fsync). Se o PC desligar no meio da execução,
    esse arquivo já tem tudo que foi processado até ali (abre direto no Excel).
    Retorna o caminho do arquivo, ou "" se não conseguiu gravar (nunca lança:
    falha de backup não pode derrubar a automação).
    """
    try:
        pasta_saida = pasta_saida or config.PASTA_SAIDA
        momento = momento or datetime.now()
        pasta_execucao = os.path.join(pasta_saida, momento.strftime("%Y-%m-%d_%H-%M-%S"))
        os.makedirs(pasta_execucao, exist_ok=True)
        caminho = os.path.join(pasta_execucao, NOME_BACKUP_PARCIAL)
        novo = not os.path.isfile(caminho)
        with open(caminho, "a", encoding="utf-8", newline="") as f:
            if novo:
                f.write("\ufeff")  # BOM: o Excel abre com acentos corretos
            w = csv_modulo.DictWriter(f, fieldnames=config.COLUNAS_ARQUIVO_RESULTADO, delimiter=";",
                               extrasaction="ignore", restval="")
            if novo:
                w.writeheader()
            w.writerow(_linha_resultado(registro))
            f.flush()
            os.fsync(f.fileno())
        return caminho
    except Exception:  # pylint: disable=broad-except
        return ""


def remover_backup_parcial(pasta_saida: str = None, momento: datetime = None):
    """Apaga o backup_parcial.csv da execução (chamado quando os arquivos
    finais já foram gravados com sucesso)."""
    try:
        pasta_saida = pasta_saida or config.PASTA_SAIDA
        momento = momento or datetime.now()
        caminho = os.path.join(pasta_saida, momento.strftime("%Y-%m-%d_%H-%M-%S"), NOME_BACKUP_PARCIAL)
        if os.path.isfile(caminho):
            os.remove(caminho)
    except OSError:
        pass
