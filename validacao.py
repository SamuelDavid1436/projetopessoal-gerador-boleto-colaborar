# -*- coding: utf-8 -*-
"""
validacao.py
============
Regras pra decidir se um dado lido do Colaboraread é REAL ou só um
"enchimento" do sistema (ex.: nome "." e CPF "00000000009" quando o aluno
não tem responsável cadastrado). Usado na captura (pra tentar de novo) e na
hora de gravar os arquivos (pra nunca sair ponto ou campo vazio).
"""
import re

# CPFs que o Colaboraread usa como "sem responsável"
_CPFS_PLACEHOLDER = {"00000000009"}


def so_digitos(valor) -> str:
    return re.sub(r"\D", "", str(valor or ""))


def nome_valido(nome) -> bool:
    """Tem pelo menos 2 letras (descarta vazio, ".", "-", "0"...)."""
    return len(re.findall(r"[^\W\d_]", str(nome or ""))) >= 2


def cpf_valido(cpf) -> bool:
    """11 dígitos, nem todos iguais, e não é o CPF de enchimento."""
    d = so_digitos(cpf)
    return len(d) == 11 and len(set(d)) > 1 and d not in _CPFS_PLACEHOLDER


def telefone_valido(telefone) -> bool:
    """DDD + número (10 ou 11 dígitos), com ou sem o 55 na frente."""
    d = so_digitos(telefone).lstrip("0")
    if d.startswith("55") and len(d) in (12, 13):
        return True
    return len(d) in (10, 11)
