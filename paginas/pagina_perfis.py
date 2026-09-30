# -*- coding: utf-8 -*-
"""
paginas/pagina_perfis.py
=========================
Um cartão por perfil (até config.NUM_PERFIS), cada um com:
- nome do perfil = e-mail detectado automaticamente na tela de login
(editável via botão de lápis, para dar um apelido personalizado)
- status de login (detecção best-effort via botão "Verificar login")
- botão "Login manual" (abre o Chrome daquele perfil para logar)
- botão "Limpar perfil" (apaga só a sessão daquele perfil)
"""
from tkinter import messagebox

import customtkinter as ctk

import config
import estilo
import perfis


class CartaoPerfil(ctk.CTkFrame):
    def __init__(self, master, controlador, perfil_id: int):
        super().__init__(master, fg_color=estilo.FUNDO_CARTAO, corner_radius=estilo.RAIO_CARTAO,
                        border_width=1, border_color=estilo.BORDA)
        self.controlador = controlador
        self.perfil_id = perfil_id
        self._editando = False

        cabecalho = ctk.CTkFrame(self, fg_color="transparent")
        cabecalho.pack(fill="x", padx=16, pady=(16, 4))

        self.label_apelido = ctk.CTkLabel(
            cabecalho, text=perfis.obter_apelido(perfil_id), font=ctk.CTkFont(size=15, weight="bold"),
            text_color=estilo.TEXTO_PRIMARIO, anchor="w",
        )
        self.label_apelido.pack(side="left", fill="x", expand=True)

        self.entry_apelido = ctk.CTkEntry(cabecalho, font=ctk.CTkFont(size=14),
                                        text_color=estilo.TEXTO_PRIMARIO)
        self.entry_apelido.bind("<Return>", lambda e: self._salvar_apelido())

        self.botao_editar = ctk.CTkButton(
            cabecalho, text="✎", width=28, height=28, fg_color="transparent", hover_color=estilo.FUNDO_SUTIL,
            text_color=estilo.TEXTO_SECUNDARIO, command=self._alternar_edicao,
        )
        self.botao_editar.pack(side="right", padx=(6, 0))

        self.selo_status = ctk.CTkLabel(cabecalho, text="", font=ctk.CTkFont(size=11, weight="bold"),
                                        corner_radius=8, width=140)
        self.selo_status.pack(side="right")

        linha_email = ctk.CTkFrame(self, fg_color="transparent")
        linha_email.pack(fill="x", padx=16)
        self.label_email = ctk.CTkLabel(linha_email, text="", font=ctk.CTkFont(size=11),
                                        text_color=estilo.TEXTO_SECUNDARIO, anchor="w")
        self.label_email.pack(side="left", fill="x", expand=True)
        self.entry_email = ctk.CTkEntry(linha_email, font=ctk.CTkFont(size=12),
                                        text_color=estilo.TEXTO_PRIMARIO, placeholder_text="nome@dominio.com")
        self.entry_email.bind("<Return>", lambda e: self._salvar_email())
        self._editando_email = False
        self.botao_editar_email = ctk.CTkButton(
            linha_email, text="✎", width=22, height=22, fg_color="transparent", hover_color=estilo.FUNDO_SUTIL,
            text_color=estilo.TEXTO_SECUNDARIO, command=self._alternar_edicao_email,
        )
        self.botao_editar_email.pack(side="right")

        ctk.CTkLabel(self, text=f"Pasta local: perfil_{perfil_id}", font=ctk.CTkFont(size=11),
                    text_color=estilo.TEXTO_SECUNDARIO).pack(anchor="w", padx=16, pady=(0, 4))

        linha_botoes = ctk.CTkFrame(self, fg_color="transparent")
        linha_botoes.pack(fill="x", padx=16, pady=16)

        self.botao_verificar = ctk.CTkButton(
            linha_botoes, text="Verificar login", fg_color=estilo.FUNDO_SUTIL, hover_color=estilo.BORDA,
            text_color=estilo.TEXTO_PRIMARIO, command=self._verificar_login,
        )
        self.botao_verificar.pack(side="left")

        ctk.CTkButton(
            linha_botoes, text="Login manual", fg_color=estilo.DOURADO, hover_color=estilo.DOURADO_HOVER,
            command=lambda: self.controlador.login_manual(self.perfil_id),
        ).pack(side="left", padx=(10, 0))

        ctk.CTkButton(
            linha_botoes, text="Limpar perfil", fg_color=estilo.BOTAO_PARAR, hover_color=estilo.BOTAO_PARAR_HOVER,
            command=self._limpar_perfil,
        ).pack(side="left", padx=(10, 0))

        self.atualizar()

    # ------------------------------------------------------------------
    # Edição do apelido (botão de lápis)
    # ------------------------------------------------------------------
    def _alternar_edicao(self):
        if not self._editando:
            self._editando = True
            self.label_apelido.pack_forget()
            self.entry_apelido.delete(0, "end")
            self.entry_apelido.insert(0, perfis.obter_apelido(self.perfil_id))
            self.entry_apelido.pack(side="left", fill="x", expand=True, before=self.botao_editar)
            self.entry_apelido.focus_set()
            self.entry_apelido.icursor("end")
            self.botao_editar.configure(text="✓")
        else:
            self._salvar_apelido()

    def _salvar_apelido(self):
        novo = self.entry_apelido.get().strip()
        self.controlador.renomear_perfil(self.perfil_id, novo)
        self.entry_apelido.pack_forget()
        self.label_apelido.configure(text=perfis.obter_apelido(self.perfil_id))
        self.label_apelido.pack(side="left", fill="x", expand=True, before=self.botao_editar)
        self.botao_editar.configure(text="✎")
        self._editando = False

    # ------------------------------------------------------------------
    # Edição do e-mail (botão de lápis) — pra quando a detecção automática
    # não funcionar, o usuário pode digitar direto.
    # ------------------------------------------------------------------
    def _alternar_edicao_email(self):
        if not self._editando_email:
            self._editando_email = True
            self.label_email.pack_forget()
            self.entry_email.delete(0, "end")
            self.entry_email.insert(0, perfis.obter_email(self.perfil_id))
            self.entry_email.pack(side="left", fill="x", expand=True, before=self.botao_editar_email)
            self.entry_email.focus_set()
            self.entry_email.icursor("end")
            self.botao_editar_email.configure(text="✓")
        else:
            self._salvar_email()

    def _salvar_email(self):
        novo = self.entry_email.get().strip()
        if novo:
            self.controlador.definir_email_perfil(self.perfil_id, novo)
        self.entry_email.pack_forget()
        self.label_email.pack(side="left", fill="x", expand=True, before=self.botao_editar_email)
        self.botao_editar_email.configure(text="✎")
        self._editando_email = False
        self.atualizar()

    # ------------------------------------------------------------------
    def _verificar_login(self):
        self.botao_verificar.configure(state="disabled", text="Verificando...")
        self.selo_status.configure(text="verificando...", fg_color=estilo.FUNDO_SUTIL,
                                    text_color=estilo.TEXTO_SECUNDARIO)
        self.controlador.verificar_login(self.perfil_id, callback_concluido=self._apos_verificacao)

    def _apos_verificacao(self):
        self.botao_verificar.configure(state="normal", text="Verificar login")
        self.atualizar()

    def _limpar_perfil(self):
        confirmar = messagebox.askyesno(
            "Limpar perfil",
            f"Isso vai apagar o login salvo de \"{perfis.obter_apelido(self.perfil_id)}\". "
            "Você vai precisar logar de novo nesse perfil. Os outros perfis não são afetados. Confirma?",
        )
        if confirmar:
            self.controlador.limpar_perfil(self.perfil_id)
            self.atualizar()

    def _cor_status(self, status: str):
        if status == "Logado":
            return estilo.VERDE_SUCESSO
        if status == "Não logado":
            return estilo.VERMELHO_ERRO
        if status == "verificando...":
            return estilo.TEXTO_SECUNDARIO
        return estilo.AMARELO_ALERTA

    def atualizar(self):
        if not self._editando:
            self.label_apelido.configure(text=perfis.obter_apelido(self.perfil_id))

        if not self._editando_email:
            email = perfis.obter_email(self.perfil_id)
            self.label_email.configure(text=f"E-mail: {email}" if email else "E-mail: ainda não detectado")

        status = perfis.obter_status(self.perfil_id)
        if not self.controlador.perfil_tem_dados(self.perfil_id) and status == "Desconhecido":
            texto = "sem login salvo"
        else:
            texto = status
        self.selo_status.configure(text=texto, text_color=self._cor_status(status if status != "Desconhecido" else texto))


class PaginaPerfis(ctk.CTkFrame):
    def __init__(self, master, controlador):
        super().__init__(master, fg_color="transparent")
        self.controlador = controlador

        ctk.CTkLabel(self, text="Perfis", font=ctk.CTkFont(size=24, weight="bold"),
                    text_color=estilo.TEXTO_PRIMARIO).pack(anchor="w", padx=24, pady=(24, 4))
        ctk.CTkLabel(
            self,
            text=("Cada perfil guarda um login independente do Chrome. O nome do perfil é\n"
                "preenchido automaticamente com o e-mail detectado no login — use os lápis\n"
                "(✎) pra dar um apelido personalizado ou corrigir o e-mail manualmente,\n"
                "caso a detecção automática não funcione."),
            font=ctk.CTkFont(size=13), text_color=estilo.TEXTO_SECUNDARIO, justify="left",
        ).pack(anchor="w", padx=24, pady=(0, 16))

        area = ctk.CTkFrame(self, fg_color="transparent")
        area.pack(fill="both", expand=True, padx=24, pady=(0, 24))
        area.grid_columnconfigure((0, 1, 2), weight=1, uniform="perfis")

        self.cartoes = {}
        for i in range(1, config.NUM_PERFIS + 1):
            cartao = CartaoPerfil(area, controlador, i)
            cartao.grid(row=0, column=i - 1, sticky="nsew", padx=(0 if i == 1 else 8, 0))
            self.cartoes[i] = cartao

    def atualizar(self):
        for cartao in self.cartoes.values():
            cartao.atualizar()