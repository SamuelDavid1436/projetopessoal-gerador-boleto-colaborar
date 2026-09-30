# -*- coding: utf-8 -*-
"""
recuperacao.py
===============
Log TEMPORÁRIO usado só pra permitir recuperar resultados parciais se a
automação for interrompida de forma anormal no meio de uma execução
(travamento, queda de energia, fechamento inesperado do programa).

Importante — isso NÃO é um histórico permanente de RAs processados:
- Nunca impede nem pula o processamento de nenhum RA.
- Nunca compara a base atual com bases de execuções anteriores.
- É sempre reiniciado do zero (apagado) assim que uma nova importação começa.
- É apagado também quando uma execução termina normalmente (o resultado
  final já está salvo no CSV/Excel, não precisa mais dele).

Ou seja: só existe pra cobrir o cenário de "a luz caiu no meio de 2.000 RAs"
— sem isso, os resultados já capturados até aquele ponto seriam perdidos.
"""
import json
import os
from datetime import datetime

import config


def iniciar_novo_ciclo(total_ras: int):
    """
    Chamado sempre que uma NOVA execução começa (usuário clicou em
    "Importar"). Descarta qualquer log de retomada anterior (de uma
    execução passada, terminada ou não) e começa um arquivo novo do zero.
    """
    os.makedirs(config.PASTA_LOGS, exist_ok=True)
    dados = {
        "iniciado_em": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "total_ras": total_ras,
        "resultados": [],
    }
    _salvar(dados)


def registrar_resultado(registro: dict):
    """Acrescenta mais um resultado já concluído ao log de retomada."""
    dados = _carregar_bruto()
    if dados is None:
        return  # não tem ciclo iniciado (ex: log já foi descartado) — ignora
    dados["resultados"].append(registro)
    _salvar(dados)


def finalizar_ciclo():
    """
    Chamado quando uma execução termina — seja normalmente, seja
    interrompida pelo botão "Parar", seja com erro geral. Em todos esses
    casos o resultado (mesmo que parcial) já foi salvo no CSV/Excel final,
    então o log de retomada não serve mais pra nada — descarta.
    """
    descartar()


def descartar():
    """Apaga o log de retomada, se existir."""
    try:
        if os.path.isfile(config.ARQUIVO_RETOMADA):
            os.remove(config.ARQUIVO_RETOMADA)
    except OSError:
        pass


def existe_execucao_pendente() -> bool:
    """
    True se existe um log de retomada de uma execução que não terminou
    normalmente (indício de queda/travamento) — usado ao abrir o programa
    pra oferecer recuperar os resultados parciais.
    """
    dados = _carregar_bruto()
    return dados is not None and len(dados.get("resultados", [])) > 0


def carregar_pendente() -> dict:
    """Devolve o conteúdo do log de retomada (iniciado_em, total_ras,
    resultados), ou None se não houver nada pendente."""
    return _carregar_bruto()


def _carregar_bruto():
    if not os.path.isfile(config.ARQUIVO_RETOMADA):
        return None
    try:
        with open(config.ARQUIVO_RETOMADA, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _salvar(dados: dict):
    try:
        with open(config.ARQUIVO_RETOMADA, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except OSError:
        pass
