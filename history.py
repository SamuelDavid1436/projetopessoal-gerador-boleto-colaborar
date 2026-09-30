# -*- coding: utf-8 -*-
"""
history.py
==========
Guarda e lê o histórico de execuções (data/hora, nº de janelas, status,
quantidade de registros, duração) num arquivo JSON simples, para alimentar
o dashboard ("Início") e a página "Execuções".
"""
import json
import os
from datetime import datetime, date

import config


def _garantir_arquivo():
    os.makedirs(config.PASTA_LOGS, exist_ok=True)
    if not os.path.isfile(config.ARQUIVO_HISTORICO):
        with open(config.ARQUIVO_HISTORICO, "w", encoding="utf-8") as f:
            json.dump([], f)


def carregar_historico() -> list:
    _garantir_arquivo()
    try:
        with open(config.ARQUIVO_HISTORICO, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _salvar_lista(lista: list):
    _garantir_arquivo()
    with open(config.ARQUIVO_HISTORICO, "w", encoding="utf-8") as f:
        json.dump(lista, f, ensure_ascii=False, indent=2)


def registrar_execucao(perfis_usados: list, status: str, n_registros: int,
                        duracao_segundos: float, caminho_csv: str = "", caminho_xlsx: str = "") -> dict:
    """Adiciona uma execução ao histórico e devolve o registro criado.
    `perfis_usados` é uma lista de apelidos (str), ex: ["Secretaria 1", "Secretaria 2"]."""
    historico = carregar_historico()
    registro = {
        "data_hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "perfis": list(perfis_usados),
        "janelas": len(perfis_usados),  # mantido para compatibilidade com telas antigas
        "status": status,  # "Concluído" | "Interrompido" | "Erro"
        "registros": n_registros,
        "duracao_segundos": round(duracao_segundos),
        "pasta_saida": os.path.dirname(caminho_csv) if caminho_csv else config.PASTA_SAIDA,
        "csv": caminho_csv,
        "xlsx": caminho_xlsx,
    }
    historico.insert(0, registro)  # mais recente primeiro
    historico = historico[:200]  # limite razoável
    _salvar_lista(historico)
    return registro


def formatar_duracao(segundos: float) -> str:
    segundos = int(segundos or 0)
    horas, resto = divmod(segundos, 3600)
    minutos, segs = divmod(resto, 60)
    return f"{horas:02d}:{minutos:02d}:{segs:02d}"


def estatisticas(historico: list = None) -> dict:
    """Calcula: total de dados capturados (histórico todo), execuções hoje e tempo total hoje."""
    historico = historico if historico is not None else carregar_historico()
    hoje_str = date.today().strftime("%d/%m/%Y")

    total_dados = sum(item.get("registros", 0) for item in historico)
    execucoes_hoje = [item for item in historico if item.get("data_hora", "").startswith(hoje_str)]
    tempo_total_hoje = sum(item.get("duracao_segundos", 0) for item in execucoes_hoje)

    return {
        "total_dados_capturados": total_dados,
        "execucoes_hoje": len(execucoes_hoje),
        "tempo_total_hoje": formatar_duracao(tempo_total_hoje),
    }
