# -*- coding: utf-8 -*-
"""
paginas/pagina_sobre.py
=========================
"""
import customtkinter as ctk

import config
import estilo


class PaginaSobre(ctk.CTkFrame):
    def __init__(self, master, controlador):
        super().__init__(master, fg_color="transparent")

        ctk.CTkLabel(self, text="Sobre", font=ctk.CTkFont(size=24, weight="bold"),
                     text_color=estilo.TEXTO_PRIMARIO).pack(anchor="w", padx=24, pady=(24, 4))

        painel = ctk.CTkFrame(self, fg_color=estilo.FUNDO_CARTAO, corner_radius=estilo.RAIO_CARTAO)
        painel.pack(fill="x", padx=24, pady=(16, 0))

        ctk.CTkLabel(painel, text=config.NOME_PRODUTO, font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=estilo.TEXTO_PRIMARIO).pack(anchor="w", padx=16, pady=(16, 2))
        ctk.CTkLabel(painel, text=f"Versão {config.VERSAO_APP}",
                     text_color=estilo.TEXTO_SECUNDARIO).pack(anchor="w", padx=16)
        ctk.CTkLabel(
            painel,
            text="Automação para consulta de RAs no Colaboraread, verificação de mensalidades\n"
                 "e captura da linha digitável dos boletos, com exportação para CSV e Excel.",
            justify="left", text_color=estilo.TEXTO_SECUNDARIO,
        ).pack(anchor="w", padx=16, pady=(10, 16))

        ctk.CTkLabel(self, text="© 2026 Captura Boleto Colaboraread — Todos os direitos reservados",
                     text_color=estilo.TEXTO_SECUNDARIO, font=ctk.CTkFont(size=11)).pack(anchor="w", padx=24, pady=16)
