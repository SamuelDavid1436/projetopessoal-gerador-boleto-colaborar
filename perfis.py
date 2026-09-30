# -*- coding: utf-8 -*-
"""
perfis.py
=========
Guarda o apelido, o e-mail detectado no login e o último status de login
conhecido de cada perfil (1 a config.NUM_PERFIS), num arquivo JSON simples.

Regra de apelido:
- Enquanto o usuário nunca renomeou manualmente (apelido_personalizado=False),
  o apelido acompanha automaticamente o e-mail detectado na tela de login.
- Assim que o usuário usa o botão de editar (lápis) para renomear, o apelido
  fica "travado" naquele texto — mas o e-mail continua sendo detectado e
  mostrado separadamente.
"""
import json
import os

import config


def _perfil_padrao_unico(i: int) -> dict:
    return {
        "apelido": f"Perfil {i}",
        "apelido_personalizado": False,
        "email": "",
        "status": "Desconhecido",
    }


def _perfis_padrao() -> dict:
    return {str(i): _perfil_padrao_unico(i) for i in range(1, config.NUM_PERFIS + 1)}


def _salvar(dados: dict):
    os.makedirs(config.PASTA_DOCUMENTOS, exist_ok=True)
    with open(config.ARQUIVO_PERFIS_META, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def carregar_perfis() -> dict:
    """Devolve {'1': {'apelido':..., 'apelido_personalizado':..., 'email':..., 'status':...}, ...}."""
    if not os.path.isfile(config.ARQUIVO_PERFIS_META):
        dados = _perfis_padrao()
        _salvar(dados)
        return dados

    try:
        with open(config.ARQUIVO_PERFIS_META, "r", encoding="utf-8") as f:
            dados = json.load(f)
    except (json.JSONDecodeError, OSError):
        dados = {}

    alterado = False
    for chave, padrao in _perfis_padrao().items():
        if chave not in dados:
            dados[chave] = padrao
            alterado = True
        else:
            # completa campos que possam faltar (ex: arquivo salvo por uma versão anterior)
            for campo, valor_padrao in padrao.items():
                if campo not in dados[chave]:
                    dados[chave][campo] = valor_padrao
                    alterado = True
    if alterado:
        _salvar(dados)
    return dados


def definir_apelido(perfil_id: int, apelido: str, personalizado: bool = True):
    """Renomeia o perfil manualmente (via botão de editar). Marca como personalizado
    por padrão, para que futuras detecções de e-mail não sobrescrevam o apelido."""
    dados = carregar_perfis()
    apelido = (apelido or "").strip() or dados[str(perfil_id)].get("email") or f"Perfil {perfil_id}"
    dados[str(perfil_id)]["apelido"] = apelido
    dados[str(perfil_id)]["apelido_personalizado"] = personalizado
    _salvar(dados)


def definir_email(perfil_id: int, email: str):
    """Chamado quando a automação detecta um e-mail digitado na tela de login.
    Sempre guarda o e-mail; só atualiza o apelido automaticamente se o usuário
    ainda não tiver personalizado o nome daquele perfil."""
    email = (email or "").strip()
    if not email:
        return
    dados = carregar_perfis()
    dados[str(perfil_id)]["email"] = email
    if not dados[str(perfil_id)].get("apelido_personalizado", False):
        dados[str(perfil_id)]["apelido"] = email
    _salvar(dados)


def definir_status(perfil_id: int, status: str):
    dados = carregar_perfis()
    dados[str(perfil_id)]["status"] = status
    _salvar(dados)


def obter_apelido(perfil_id: int) -> str:
    return carregar_perfis().get(str(perfil_id), {}).get("apelido", f"Perfil {perfil_id}")


def obter_email(perfil_id: int) -> str:
    return carregar_perfis().get(str(perfil_id), {}).get("email", "")


def obter_status(perfil_id: int) -> str:
    return carregar_perfis().get(str(perfil_id), {}).get("status", "Desconhecido")


def apelido_personalizado(perfil_id: int) -> bool:
    return carregar_perfis().get(str(perfil_id), {}).get("apelido_personalizado", False)


def resetar_perfil(perfil_id: int):
    """
    Volta o perfil para o estado padrão: apelido genérico ('Perfil N'),
    sem e-mail, sem personalização e status desconhecido. Chamado junto com
    a limpeza do login (browser_manager.limpar_perfil), pra não ficar um
    apelido/e-mail "fantasma" de um login que já foi apagado.
    """
    dados = carregar_perfis()
    dados[str(perfil_id)] = _perfil_padrao_unico(perfil_id)
    _salvar(dados)
