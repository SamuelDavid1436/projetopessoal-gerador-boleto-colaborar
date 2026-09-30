# -*- coding: utf-8 -*-
"""
paginas/pagina_logs.py
========================
Mostra o log completo (mesmo conteúdo que antes ficava só na tela
principal), com opção de limpar a visualização.
"""
import customtkinter as ctk

import estilo


class PaginaLogs(ctk.CTkFrame):
    def __init__(self, master, controlador):
        super().__init__(master, fg_color="transparent")
        self.controlador = controlador

        cabecalho = ctk.CTkFrame(self, fg_color="transparent")
        cabecalho.pack(fill="x", padx=24, pady=(24, 8))
        ctk.CTkLabel(cabecalho, text="Logs", font=ctk.CTkFont(size=24, weight="bold"),
                     text_color=estilo.TEXTO_PRIMARIO).pack(side="left")
        ctk.CTkButton(
            cabecalho, text="Limpar", width=90, fg_color=estilo.FUNDO_SUTIL, hover_color=estilo.BORDA,
            text_color=estilo.TEXTO_PRIMARIO, command=self._limpar,
        ).pack(side="right")

        painel = ctk.CTkFrame(self, fg_color=estilo.FUNDO_CARTAO, corner_radius=estilo.RAIO_CARTAO)
        painel.pack(fill="both", expand=True, padx=24, pady=(0, 24))
        self.caixa_log = ctk.CTkTextbox(painel, wrap="word", fg_color="transparent",
                                        text_color=estilo.TEXTO_PRIMARIO)
        self.caixa_log.pack(fill="both", expand=True, padx=12, pady=12)
        self.caixa_log.configure(state="disabled")

    def adicionar_linha(self, mensagem: str):
        self.caixa_log.configure(state="normal")
        self.caixa_log.insert("end", mensagem + "\n")
        self.caixa_log.see("end")
        self.caixa_log.configure(state="disabled")

    def _limpar(self):
        self.caixa_log.configure(state="normal")
        self.caixa_log.delete("1.0", "end")
        self.caixa_log.configure(state="disabled")

    def atualizar(self):
        pass  # o conteúdo é alimentado via adicionar_linha() pelo controlador
