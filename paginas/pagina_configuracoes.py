# -*- coding: utf-8 -*-
"""
paginas/pagina_configuracoes.py
=================================
Tema claro/escuro (funcionalidade preservada) e informações de onde os
dados ficam salvos.
"""
import customtkinter as ctk

import config
import estilo


class PaginaConfiguracoes(ctk.CTkFrame):
    def __init__(self, master, controlador):
        super().__init__(master, fg_color="transparent")
        self.controlador = controlador

        ctk.CTkLabel(self, text="Configurações", font=ctk.CTkFont(size=24, weight="bold"),
                     text_color=estilo.TEXTO_PRIMARIO).pack(anchor="w", padx=24, pady=(24, 4))
        ctk.CTkLabel(self, text="Preferências gerais do aplicativo.",
                     font=ctk.CTkFont(size=13), text_color=estilo.TEXTO_SECUNDARIO).pack(anchor="w", padx=24, pady=(0, 16))

        painel_tema = ctk.CTkFrame(self, fg_color=estilo.FUNDO_CARTAO, corner_radius=estilo.RAIO_CARTAO)
        painel_tema.pack(fill="x", padx=24, pady=(0, 16))
        linha = ctk.CTkFrame(painel_tema, fg_color="transparent")
        linha.pack(fill="x", padx=16, pady=16)
        bloco_texto = ctk.CTkFrame(linha, fg_color="transparent")
        bloco_texto.pack(side="left")
        ctk.CTkLabel(bloco_texto, text="Tema escuro", font=ctk.CTkFont(weight="bold"),
                     text_color=estilo.TEXTO_PRIMARIO).pack(anchor="w")
        ctk.CTkLabel(bloco_texto, text="Alterna entre o tema claro e o escuro.",
                     text_color=estilo.TEXTO_SECUNDARIO).pack(anchor="w")
        self.switch_tema = ctk.CTkSwitch(linha, text="", command=self._alternar_tema,
                                         progress_color=estilo.VERDE)
        self.switch_tema.pack(side="right")
        if ctk.get_appearance_mode() == "Dark":
            self.switch_tema.select()

        painel_dados = ctk.CTkFrame(self, fg_color=estilo.FUNDO_CARTAO, corner_radius=estilo.RAIO_CARTAO)
        painel_dados.pack(fill="x", padx=24)
        ctk.CTkLabel(painel_dados, text="Onde os dados ficam salvos", font=ctk.CTkFont(weight="bold"),
                     text_color=estilo.TEXTO_PRIMARIO).pack(anchor="w", padx=16, pady=(16, 4))
        ctk.CTkLabel(painel_dados, text=config.PASTA_DOCUMENTOS, text_color=estilo.TEXTO_SECUNDARIO).pack(
            anchor="w", padx=16, pady=(0, 12)
        )
        ctk.CTkButton(
            painel_dados, text="Abrir pasta de dados", fg_color=estilo.FUNDO_SUTIL, hover_color=estilo.BORDA,
            text_color=estilo.TEXTO_PRIMARIO,
            command=lambda: self.controlador.abrir_pasta(config.PASTA_DOCUMENTOS),
        ).pack(anchor="w", padx=16, pady=(0, 16))

    def _alternar_tema(self):
        modo = "dark" if self.switch_tema.get() else "light"
        ctk.set_appearance_mode(modo)
