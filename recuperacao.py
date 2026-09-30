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

# Formato "uma linha JSON por evento" (.jsonl): a 1ª linha é o cabeçalho do
# ciclo e cada RA concluído vira UMA linha nova acrescentada no fim, com
# flush + fsync. Assim o custo não cresce com o tamanho da base e, se a luz
# cair no meio de uma gravação, só a última linha (incompleta) se perde —
# todas as anteriores continuam válidas.
_ARQUIVO = os.path.splitext(config.ARQUIVO_RETOMADA)[0] + ".jsonl"


def _anexar(obj: dict, novo_arquivo: bool = False):
    try:
        os.makedirs(os.path.dirname(_ARQUIVO), exist_ok=True)
        with open(_ARQUIVO, "w" if novo_arquivo else "a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
    except OSError:
        pass


def iniciar_novo_ciclo(total_ras: int):
    """
    Chamado sempre que uma NOVA execução começa (usuário clicou em
    "Importar"). Descarta qualquer log de retomada anterior (de uma
    execução passada, terminada ou não) e começa um arquivo novo do zero.
    """
    _anexar({
        "iniciado_em": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "total_ras": total_ras,
    }, novo_arquivo=True)


def registrar_resultado(registro: dict):
    """Acrescenta mais um resultado já concluído ao log de retomada."""
    if not os.path.isfile(_ARQUIVO):
        return  # não tem ciclo iniciado (ex: log já foi descartado) — ignora
    _anexar({"resultado": registro})


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
    for caminho in (_ARQUIVO, config.ARQUIVO_RETOMADA):  # o .json é o formato antigo
        try:
            if os.path.isfile(caminho):
                os.remove(caminho)
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


def _carregar_legado():
    """Log de retomada no formato antigo (.json único), deixado por versões
    anteriores do programa — ainda é recuperável."""
    try:
        with open(config.ARQUIVO_RETOMADA, "r", encoding="utf-8") as f:
            dados = json.load(f)
        if isinstance(dados, dict) and isinstance(dados.get("resultados"), list):
            return {"iniciado_em": dados.get("iniciado_em", "?"),
                    "total_ras": dados.get("total_ras", "?"),
                    "resultados": dados["resultados"]}
    except (OSError, json.JSONDecodeError):
        pass
    return None


def _carregar_bruto():
    if not os.path.isfile(_ARQUIVO):
        return _carregar_legado() if os.path.isfile(config.ARQUIVO_RETOMADA) else None
    dados = {"iniciado_em": "?", "total_ras": "?", "resultados": []}
    try:
        with open(_ARQUIVO, "r", encoding="utf-8") as f:
            for n, linha in enumerate(f):
                linha = linha.strip()
                if not linha:
                    continue
                try:
                    obj = json.loads(linha)
                except json.JSONDecodeError:
                    continue  # linha cortada pela queda — ignora só ela
                if n == 0 and "iniciado_em" in obj:
                    dados["iniciado_em"] = obj.get("iniciado_em", "?")
                    dados["total_ras"] = obj.get("total_ras", "?")
                elif "resultado" in obj:
                    dados["resultados"].append(obj["resultado"])
    except OSError:
        return None
    return dados
