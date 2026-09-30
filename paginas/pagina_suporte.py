# -*- coding: utf-8 -*-
"""
paginas/pagina_suporte.py
===========================
Informações de contato para suporte, e atalho para o manual (Word).
"""
import os

import customtkinter as ctk

import config
import estilo


class PaginaSuporte(ctk.CTkFrame):
    def __init__(self, master, controlador):
        super().__init__(master, fg_color="transparent")
        self.controlador = controlador

        ctk.CTkLabel(self, text="Suporte", font=ctk.CTkFont(size=24, weight="bold"),
                     text_color=estilo.TEXTO_PRIMARIO).pack(anchor="w", padx=24, pady=(24, 4))
        ctk.CTkLabel(self, text="Precisa de ajuda? Fale com a gente ou consulte o manual.",
                     font=ctk.CTkFont(size=13), text_color=estilo.TEXTO_SECUNDARIO).pack(anchor="w", padx=24, pady=(0, 16))

        painel = ctk.CTkFrame(self, fg_color=estilo.FUNDO_CARTAO, corner_radius=estilo.RAIO_CARTAO)
        painel.pack(fill="x", padx=24, pady=(0, 16))

        for rotulo, valor in [
            ("Telefone", "(11) 94727-8128"),
            ("E-mail", "samueldayvid5@icloud.com"),
        ]:
            linha = ctk.CTkFrame(painel, fg_color="transparent")
            linha.pack(fill="x", padx=16, pady=10)
            ctk.CTkLabel(linha, text=rotulo, width=110, anchor="w", font=ctk.CTkFont(weight="bold"),
                         text_color=estilo.TEXTO_PRIMARIO).pack(side="left")
            ctk.CTkLabel(linha, text=valor, text_color=estilo.TEXTO_SECUNDARIO).pack(side="left")

        ctk.CTkLabel(
            painel,
            text="Antes de entrar em contato, confira a página \"Logs\" — a mensagem de erro\nali costuma ajudar a resolver mais rápido.",
            justify="left", text_color=estilo.TEXTO_SECUNDARIO,
        ).pack(anchor="w", padx=16, pady=(0, 16))

        painel_manual = ctk.CTkFrame(self, fg_color=estilo.FUNDO_CARTAO, corner_radius=estilo.RAIO_CARTAO)
        painel_manual.pack(fill="x", padx=24)
        ctk.CTkLabel(painel_manual, text="Manual completo", font=ctk.CTkFont(weight="bold"),
                     text_color=estilo.TEXTO_PRIMARIO).pack(anchor="w", padx=16, pady=(16, 4))
        ctk.CTkLabel(painel_manual, text="Passo a passo em PDF, com todas as telas explicadas.",
                     text_color=estilo.TEXTO_SECUNDARIO).pack(anchor="w", padx=16)
        ctk.CTkButton(
            painel_manual, text="📄  Abrir manual", fg_color=estilo.DOURADO, hover_color=estilo.DOURADO_HOVER,
            height=38, command=self._abrir_manual,
        ).pack(anchor="w", padx=16, pady=16)

    def _abrir_manual(self):
        self.controlador.abrir_arquivo(config.CAMINHO_MANUAL)

