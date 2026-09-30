# -*- coding: utf-8 -*-
"""
paginas/pagina_execucoes.py
============================
Formulário para importar a base de RAs, escolher quais perfis (janelas)
vão trabalhar (qualquer combinação entre os até N perfis configurados) e
iniciar a execução. Também mostra o histórico completo.
"""
import os
from tkinter import filedialog, messagebox

import customtkinter as ctk

import config
import data_io
import estilo
import history
import perfis
from paginas import pagina_inicio
from paginas.pagina_inicio import ChipStatus


class PaginaExecucoes(ctk.CTkFrame):
    def __init__(self, master, controlador):
        super().__init__(master, fg_color="transparent")
        self.controlador = controlador
        self.caminho_arquivo_ras = None
        self.checkboxes_perfil = {}  # perfil_id -> ctk.CTkCheckBox
        self._ultima_assinatura_historico = None

        ctk.CTkLabel(self, text="Execuções", font=ctk.CTkFont(size=24, weight="bold"),
                    text_color=estilo.TEXTO_PRIMARIO).pack(anchor="w", padx=24, pady=(24, 4))
        ctk.CTkLabel(self, text="Importe a base de RAs, escolha os perfis e inicie a captura.",
                    font=ctk.CTkFont(size=13), text_color=estilo.TEXTO_SECUNDARIO).pack(anchor="w", padx=24, pady=(0, 16))

        # --- Formulário de nova execução ---
        painel_form = ctk.CTkFrame(self, fg_color=estilo.FUNDO_CARTAO, corner_radius=estilo.RAIO_CARTAO)
        painel_form.pack(fill="x", padx=24, pady=(0, 16))
        ctk.CTkLabel(painel_form, text="Nova execução", font=ctk.CTkFont(size=14, weight="bold"),
                    text_color=estilo.TEXTO_PRIMARIO).pack(anchor="w", padx=16, pady=(16, 10))

        linha_arquivo = ctk.CTkFrame(painel_form, fg_color="transparent")
        linha_arquivo.pack(fill="x", padx=16, pady=(0, 10))
        ctk.CTkLabel(linha_arquivo, text="Base de RAs:", width=110, anchor="w",
                    text_color=estilo.TEXTO_PRIMARIO).pack(side="left")
        self.label_arquivo = ctk.CTkLabel(linha_arquivo, text="Nenhum arquivo importado.",
                                        text_color=estilo.TEXTO_SECUNDARIO)
        self.label_arquivo.pack(side="left", fill="x", expand=True, padx=10)
        ctk.CTkButton(linha_arquivo, text="Importar base...", width=140, fg_color=estilo.FUNDO_SUTIL,
                    hover_color=estilo.BORDA, text_color=estilo.TEXTO_PRIMARIO,
                    command=self._selecionar_arquivo).pack(side="right")

        # --- Info: como a automação decide o mês (não precisa mais escolher) ---
        aviso_mes = ctk.CTkFrame(painel_form, fg_color=estilo.FUNDO_SUTIL, corner_radius=8)
        aviso_mes.pack(fill="x", padx=16, pady=(0, 16))
        ctk.CTkLabel(
            aviso_mes,
            text=("ℹ  Não é preciso escolher o mês: para cada RA, a automação lê todas as "
                "parcelas no Colaboraread e gera o boleto (linha digitável) de todas as que "
                "estiverem disponíveis. Antes de começar, cada janela do Chrome espera você "
                "entrar pelo Prisma → selecionar o polo → Portais → Colaborar."),
            font=ctk.CTkFont(size=11), text_color=estilo.TEXTO_SECUNDARIO, justify="left", wraplength=560,
        ).pack(anchor="w", padx=12, pady=10)

        # --- Seleção de perfis (checkboxes independentes, qualquer combinação) ---
        linha_perfis = ctk.CTkFrame(painel_form, fg_color="transparent")
        linha_perfis.pack(fill="x", padx=16, pady=(0, 16))
        ctk.CTkLabel(linha_perfis, text="Perfis:", width=110, anchor="w",
                    text_color=estilo.TEXTO_PRIMARIO).pack(side="left", anchor="n")
        bloco_checks = ctk.CTkFrame(linha_perfis, fg_color="transparent")
        bloco_checks.pack(side="left", fill="x", expand=True)
        for perfil_id in range(1, config.NUM_PERFIS + 1):
            var = ctk.BooleanVar(value=(perfil_id == 1))
            apelido = perfis.obter_apelido(perfil_id)
            check = ctk.CTkCheckBox(bloco_checks, text=apelido, variable=var,
                                    fg_color=estilo.VERDE, hover_color=estilo.VERDE_HOVER,
                                    text_color=estilo.TEXTO_PRIMARIO)
            check.pack(anchor="w", pady=2)
            self.checkboxes_perfil[perfil_id] = (check, var)
        ctk.CTkLabel(
            linha_perfis, text="Marque um ou mais — cada um vira uma janela\ntrabalhando em paralelo.",
            font=ctk.CTkFont(size=11), text_color=estilo.TEXTO_SECUNDARIO, justify="left",
        ).pack(side="left", padx=(16, 0), anchor="n")

        linha_acoes = ctk.CTkFrame(painel_form, fg_color="transparent")
        linha_acoes.pack(fill="x", padx=16, pady=(0, 16))
        self.botao_iniciar = ctk.CTkButton(
            linha_acoes, text="⬇  Importar", fg_color=estilo.DOURADO, hover_color=estilo.DOURADO_HOVER,
            height=38, command=self._iniciar,
        )
        self.botao_iniciar.pack(side="left")
        self.botao_parar = ctk.CTkButton(
            linha_acoes, text="⏹  Parar", fg_color=estilo.BOTAO_PARAR, hover_color=estilo.BOTAO_PARAR_HOVER,
            height=38, width=100, state="disabled", command=self.controlador.parar_execucao,
        )
        self.botao_parar.pack(side="left", padx=(10, 0))

        # --- Mini-dashboard: Processados / Sucesso / Pendentes / Erro ---
        self.linha_dashboard = ctk.CTkFrame(painel_form, fg_color="transparent")
        self.chip_processados = ChipStatus(self.linha_dashboard, estilo.VERDE_SUCESSO, "Processados", icone=pagina_inicio.ICONE_PROCESSADOS)
        self.chip_sucesso = ChipStatus(self.linha_dashboard, estilo.VERDE_SUCESSO, "Sucesso", icone=pagina_inicio.ICONE_SUCESSO)
        self.chip_pendentes = ChipStatus(self.linha_dashboard, estilo.AMARELO_ALERTA, "Pendentes", icone=pagina_inicio.ICONE_PENDENTES)
        self.chip_erro = ChipStatus(self.linha_dashboard, estilo.VERMELHO_ERRO, "Erro", icone=pagina_inicio.ICONE_ERRO)
        for chip in (self.chip_processados, self.chip_sucesso, self.chip_pendentes, self.chip_erro):
            chip.pack(side="left", padx=(0, 8))
        # começa escondido — só aparece quando tem execução rodando (ver atualizar())

        # --- Histórico completo ---
        painel_hist = ctk.CTkFrame(self, fg_color=estilo.FUNDO_CARTAO, corner_radius=estilo.RAIO_CARTAO)
        painel_hist.pack(fill="both", expand=True, padx=24, pady=(0, 24))
        ctk.CTkLabel(painel_hist, text="Histórico de execuções", font=ctk.CTkFont(size=14, weight="bold"),
                    text_color=estilo.TEXTO_PRIMARIO).pack(anchor="w", padx=16, pady=(16, 8))

        self.area_tabela = ctk.CTkScrollableFrame(painel_hist, fg_color="transparent")
        self.area_tabela.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self.atualizar()

    # ------------------------------------------------------------------
    def _selecionar_arquivo(self):
        caminho = filedialog.askopenfilename(
            title="Selecione a base de RAs",
            filetypes=[("Planilhas e CSV", "*.csv *.xlsx *.xls"), ("Todos os arquivos", "*.*")],
        )
        if caminho:
            self.caminho_arquivo_ras = caminho
            self.label_arquivo.configure(text=os.path.basename(caminho), text_color=estilo.TEXTO_PRIMARIO)

    def _perfis_marcados(self) -> list:
        return [pid for pid, (_, var) in self.checkboxes_perfil.items() if var.get()]

    def _iniciar(self):
        if not self.caminho_arquivo_ras:
            messagebox.showwarning("Atenção", "Importe a base de RAs primeiro.")
            return

        perfis_selecionados = self._perfis_marcados()
        if not perfis_selecionados:
            messagebox.showwarning("Atenção", "Marque ao menos um perfil para rodar a automação.")
            return

        try:
            ras = data_io.ler_lista_ras(self.caminho_arquivo_ras)
            # telefone informado na base (opcional) sempre vence o do Colaboraread
            self.controlador.telefones_base = data_io.ler_telefones_base(self.caminho_arquivo_ras)
            # polo por RA (opcional): com coluna POLO a automação entra sozinha em cada polo
            self.controlador.polos_base = data_io.ler_polos_base(self.caminho_arquivo_ras)
        except Exception as erro:  # pylint: disable=broad-except
            messagebox.showerror("Erro ao ler arquivo", str(erro))
            return

        if not ras:
            messagebox.showwarning("Atenção", "Não encontrei nenhum RA válido no arquivo selecionado.")
            return

        self.controlador.iniciar_execucao(ras, perfis_selecionados)

    def _cor_status(self, status):
        if status == "Concluído":
            return estilo.VERDE_SUCESSO
        if status == "Interrompido":
            return estilo.VERMELHO_ERRO
        return estilo.AMARELO_ALERTA

    def atualizar(self):
        em_execucao = self.controlador.em_execucao
        parando = self.controlador.parando
        self.botao_iniciar.configure(state="disabled" if em_execucao else "normal",
                                    text="Rodando..." if em_execucao else "⬇  Importar")
        if parando:
            self.botao_parar.configure(state="disabled", text="⏹  Parando...")
        else:
            self.botao_parar.configure(state="normal" if em_execucao else "disabled", text="⏹  Parar")

        if em_execucao:
            processados = self.controlador.concluidos_atual
            processando = len(self.controlador.ras_em_processamento)  # ainda conta pra "Pendentes" ficar certo
            pendentes = max(0, self.controlador.total_atual - processados - processando)
            self.chip_processados.atualizar(processados)
            self.chip_sucesso.atualizar(self.controlador.contagem_sucesso)
            self.chip_pendentes.atualizar(pendentes)
            self.chip_erro.atualizar(self.controlador.contagem_erro)
            self.linha_dashboard.pack(fill="x", padx=16, pady=(0, 16))
        else:
            self.linha_dashboard.pack_forget()

        # mantém os apelidos dos checkboxes atualizados (caso tenham sido renomeados na aba Perfis)
        for perfil_id, (check, _) in self.checkboxes_perfil.items():
            check.configure(text=perfis.obter_apelido(perfil_id))

        historico = history.carregar_historico()

        # só reconstrói a tabela quando o histórico realmente mudou — evita
        # destruir/recriar os widgets a cada atualização (era isso que
        # fazia a tabela "piscar")
        assinatura = tuple((item.get("data_hora"), item.get("status"), item.get("registros")) for item in historico)
        if assinatura == self._ultima_assinatura_historico:
            return
        self._ultima_assinatura_historico = assinatura

        for widget in self.area_tabela.winfo_children():
            widget.destroy()

        colunas = ["Data/Hora", "Perfis", "Status", "Registros", "Duração", "", ""]
        for i, texto in enumerate(colunas):
            ctk.CTkLabel(self.area_tabela, text=texto, font=ctk.CTkFont(size=11, weight="bold"),
                        text_color=estilo.TEXTO_SECUNDARIO).grid(row=0, column=i, sticky="w", padx=6, pady=(0, 6))

        if not historico:
            ctk.CTkLabel(self.area_tabela, text="Nenhuma execução registrada ainda.",
                        text_color=estilo.TEXTO_SECUNDARIO).grid(row=1, column=0, columnspan=7, sticky="w", padx=6, pady=6)
            return

        for linha_idx, item in enumerate(historico, start=1):
            cor_status = self._cor_status(item.get("status", ""))
            texto_perfis = ", ".join(item.get("perfis", [])) or str(item.get("janelas", 1))
            ctk.CTkLabel(self.area_tabela, text=item.get("data_hora", ""),
                        text_color=estilo.TEXTO_PRIMARIO).grid(row=linha_idx, column=0, sticky="w", padx=6, pady=3)
            ctk.CTkLabel(self.area_tabela, text=texto_perfis,
                        text_color=estilo.TEXTO_PRIMARIO).grid(row=linha_idx, column=1, sticky="w", padx=6)
            ctk.CTkLabel(self.area_tabela, text=item.get("status", ""), text_color=cor_status,
                        font=ctk.CTkFont(weight="bold")).grid(row=linha_idx, column=2, sticky="w", padx=6)
            ctk.CTkLabel(self.area_tabela, text=str(item.get("registros", 0)),
                        text_color=estilo.TEXTO_PRIMARIO).grid(row=linha_idx, column=3, sticky="w", padx=6)
            ctk.CTkLabel(self.area_tabela, text=history.formatar_duracao(item.get("duracao_segundos", 0)),
                        text_color=estilo.TEXTO_PRIMARIO).grid(row=linha_idx, column=4, sticky="w", padx=6)
            pasta = item.get("pasta_saida", "")
            if pasta:
                ctk.CTkButton(self.area_tabela, text="Abrir pasta", width=100, fg_color=estilo.FUNDO_SUTIL,
                            hover_color=estilo.BORDA, text_color=estilo.TEXTO_PRIMARIO,
                            command=lambda p=pasta: self.controlador.abrir_pasta(p)).grid(
                    row=linha_idx, column=5, sticky="e", padx=6, pady=2)
            caminho_csv = item.get("csv", "")
            if caminho_csv:
                ctk.CTkButton(self.area_tabela, text="Reprocessar erros", width=140,
                            fg_color=estilo.FUNDO_SUTIL, hover_color=estilo.BORDA,
                            text_color=estilo.DOURADO,
                            command=lambda c=caminho_csv: self.controlador.reprocessar_erros(c)).grid(
                    row=linha_idx, column=6, sticky="e", padx=6, pady=2)