# -*- coding: utf-8 -*-
"""
limpeza.py
==========
"Zerar painel": deixa o programa limpo para começar outra rodada (por
exemplo, o próximo polo).

O que zera: números do painel, histórico de execuções, recuperação
pendente, prints de erro e a pasta de saída.
Os arquivos da saída NÃO são apagados: são movidos para
"saida_arquivadas/<data-hora>" (dentro da pasta de dados).
NUNCA mexe em: perfis do Chrome (logins), credenciais do Windows
(Gerenciador de Credenciais) nem na pasta de perfis em %LOCALAPPDATA%.
"""
import os
import shutil
from datetime import datetime
from tkinter import messagebox

import config
import estilo
import recuperacao

NOME_PASTA_ARQUIVO = "saida_arquivadas"


def pasta_arquivo() -> str:
    return os.path.join(config.PASTA_DOCUMENTOS, NOME_PASTA_ARQUIVO)


def _esvaziar_pasta(pasta: str) -> int:
    """Remove o conteúdo da pasta (mantendo a pasta). Devolve quantos itens falharam."""
    falhas = 0
    if not os.path.isdir(pasta):
        os.makedirs(pasta, exist_ok=True)
        return 0
    for nome in os.listdir(pasta):
        caminho = os.path.join(pasta, nome)
        try:
            if os.path.isdir(caminho) and not os.path.islink(caminho):
                shutil.rmtree(caminho)
            else:
                os.remove(caminho)
        except OSError:
            falhas += 1
    return falhas


def _arquivar_saida() -> tuple:
    """Move o conteúdo da pasta de saída para saida_arquivadas/<data-hora>.
    Devolve (movidos, falhas)."""
    movidos = falhas = 0
    os.makedirs(config.PASTA_SAIDA, exist_ok=True)
    itens = os.listdir(config.PASTA_SAIDA)
    if not itens:
        return 0, 0
    destino = os.path.join(pasta_arquivo(), datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))
    os.makedirs(destino, exist_ok=True)
    for nome in itens:
        try:
            shutil.move(os.path.join(config.PASTA_SAIDA, nome), os.path.join(destino, nome))
            movidos += 1
        except (OSError, shutil.Error):
            falhas += 1  # normalmente: arquivo aberto no Excel
    return movidos, falhas


def zerar_tudo(app) -> int:
    """Zera estatísticas, histórico, recuperação pendente, prints e a saída.
    Devolve quantos itens falharam (ex.: arquivo aberto no Excel)."""
    falhas = 0
    with app._lock_progresso:  # pylint: disable=protected-access
        app.total_atual = 0
        app.concluidos_atual = 0
        app.progresso_atual = 0.0
        app.contagem_sucesso = 0
        app.contagem_erro = 0
        app.ras_em_processamento = {}
        app.inicio_execucao_dt = None
        app.apelidos_execucao_atual = []
    app.telefones_base = {}

    try:  # histórico (cartões do Início + tabelas)
        with open(config.ARQUIVO_HISTORICO, "w", encoding="utf-8") as arquivo:
            arquivo.write("[]")
    except OSError:
        falhas += 1

    recuperacao.descartar()
    falhas += _esvaziar_pasta(config.PASTA_SCREENSHOTS)
    movidos, falhas_saida = _arquivar_saida()
    falhas += falhas_saida

    try:  # aba Logs
        app.paginas["Logs"]._limpar()  # pylint: disable=protected-access
    except Exception:  # pylint: disable=broad-except
        pass
    app._log("Painel zerado. Pronto para uma nova rodada."  # pylint: disable=protected-access
             + (f" {movidos} item(ns) da saída arquivados em {pasta_arquivo()}." if movidos else ""))
    return falhas


def zerar_painel_com_confirmacao(app) -> None:
    if app.em_execucao:
        messagebox.showwarning(
            "Execução em andamento",
            "Não dá pra zerar o painel com uma execução rodando. Pare a execução e tente de novo.",
        )
        return
    if not messagebox.askyesno(
        "Zerar painel",
        "Isto vai zerar:\n"
        "  • os números e o histórico de execuções;\n"
        "  • a aba Logs e os prints de erro;\n"
        "  • a pasta Saída (os arquivos gerados serão movidos para a pasta "
        f"\"{NOME_PASTA_ARQUIVO}\", não são apagados);\n"
        "  • a base de RAs selecionada.\n\n"
        "Seus perfis e logins do Chrome NÃO são apagados.\n\nQuer zerar agora?",
    ):
        return
    falhas = zerar_tudo(app)
    try:
        pagina = app.paginas["Execuções"]
        pagina.caminho_arquivo_ras = None
        pagina.label_arquivo.configure(text="Nenhum arquivo importado.", text_color=estilo.TEXTO_SECUNDARIO)
    except Exception:  # pylint: disable=broad-except
        pass
    app.mostrar_pagina("Início")  # atualiza Início (e Execuções ao abrir)
    try:
        app.paginas["Execuções"].atualizar()
    except Exception:  # pylint: disable=broad-except
        pass
    if falhas:
        messagebox.showwarning(
            "Zerar painel",
            f"Painel zerado, mas {falhas} item(ns) não puderam ser removidos ou movidos "
            "(provavelmente estão abertos no Excel). Feche-os e zere de novo.",
        )
