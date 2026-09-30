# -*- coding: utf-8 -*-
"""
paginas/pagina_inicio.py
========================
Dashboard: cartões de estatística, painel "execução em andamento" e tabela
de execuções recentes — no mesmo espírito do layout de referência.
"""
from datetime import datetime, timedelta

import customtkinter as ctk

import config
import estilo
import history

# Ícones compartilhados entre o painel grande (Início) e os chips pequenos
# (Execuções) — mesma família visual nas duas telas.
ICONE_PROCESSADOS = "📄"
ICONE_PROCESSANDO = "🔄"
ICONE_SUCESSO = "✅"
ICONE_PENDENTES = "⏳"
ICONE_ERRO = "❌"


class CartaoEstatistica(ctk.CTkFrame):
    def __init__(self, master, icone: str, valor: str, rotulo: str):
        super().__init__(master, fg_color=estilo.FUNDO_CARTAO, corner_radius=estilo.RAIO_CARTAO,
                        border_width=1, border_color=estilo.BORDA)

        selo = ctk.CTkFrame(self, fg_color=estilo.VERDE, width=40, height=40, corner_radius=10)
        selo.pack(anchor="w", padx=16, pady=(16, 10))
        selo.pack_propagate(False)
        ctk.CTkLabel(selo, text=icone, font=ctk.CTkFont(size=18), text_color="white").pack(expand=True)

        self.label_valor = ctk.CTkLabel(
            self, text=valor, font=ctk.CTkFont(size=26, weight="bold"), text_color=estilo.TEXTO_PRIMARIO
        )
        self.label_valor.pack(anchor="w", padx=16)

        ctk.CTkLabel(
            self, text=rotulo, font=ctk.CTkFont(size=12), text_color=estilo.TEXTO_SECUNDARIO
        ).pack(anchor="w", padx=16, pady=(0, 16))

    def atualizar_valor(self, valor: str):
        self.label_valor.configure(text=valor)


class ChipStatus(ctk.CTkFrame):
    """Um 'chip' pequeno com ícone/bolinha + número + rótulo — usado no
    mini-dashboard compacto da página Execuções."""

    def __init__(self, master, cor, rotulo: str, icone: str = None):
        super().__init__(master, fg_color=estilo.FUNDO_SUTIL, corner_radius=8)
        linha = ctk.CTkFrame(self, fg_color="transparent")
        linha.pack(padx=12, pady=8)

        if icone:
            ctk.CTkLabel(linha, text=icone, font=ctk.CTkFont(size=13), text_color=cor).pack(side="left", padx=(0, 4))
        else:
            ponto = ctk.CTkFrame(linha, fg_color=cor, width=9, height=9, corner_radius=5)
            ponto.pack(side="left", pady=2)
            ponto.pack_propagate(False)

        self.label_valor = ctk.CTkLabel(
            linha, text="0", font=ctk.CTkFont(size=17, weight="bold"), text_color=estilo.TEXTO_PRIMARIO
        )
        self.label_valor.pack(side="left", padx=(8 if not icone else 4, 4))

        ctk.CTkLabel(
            linha, text=rotulo, font=ctk.CTkFont(size=11), text_color=estilo.TEXTO_SECUNDARIO
        ).pack(side="left")

    def atualizar(self, valor):
        self.label_valor.configure(text=str(valor))


class BlocoGrandeStatus(ctk.CTkFrame):
    """Bloco grande — ícone em cima, número grande colorido no meio, rótulo
    embaixo — usado no painel 'Execução em andamento' da página Início."""

    def __init__(self, master, icone: str, cor, rotulo: str):
        super().__init__(master, fg_color="transparent")
        ctk.CTkLabel(self, text=icone, font=ctk.CTkFont(size=22)).pack(pady=(0, 6))
        self.label_valor = ctk.CTkLabel(
            self, text="0", font=ctk.CTkFont(size=30, weight="bold"), text_color=cor
        )
        self.label_valor.pack()
        ctk.CTkLabel(
            self, text=rotulo, font=ctk.CTkFont(size=12), text_color=estilo.TEXTO_SECUNDARIO
        ).pack(pady=(2, 0))

    def atualizar(self, valor):
        self.label_valor.configure(text=str(valor))


class PaginaInicio(ctk.CTkFrame):
    def __init__(self, master, controlador):
        super().__init__(master, fg_color="transparent")
        self.controlador = controlador
        self._ultima_assinatura_recentes = None

        # --- Cabeçalho ---
        cabecalho = ctk.CTkFrame(self, fg_color="transparent")
        cabecalho.pack(fill="x", padx=24, pady=(24, 16))

        bloco_titulo = ctk.CTkFrame(cabecalho, fg_color="transparent")
        bloco_titulo.pack(side="left", anchor="w")
        ctk.CTkLabel(bloco_titulo, text="Bem-vindo!", font=ctk.CTkFont(size=24, weight="bold"),
                    text_color=estilo.TEXTO_PRIMARIO).pack(anchor="w")
        ctk.CTkLabel(bloco_titulo, text="Gerencie as execuções e acompanhe o progresso da captura de dados.",
                    font=ctk.CTkFont(size=13), text_color=estilo.TEXTO_SECUNDARIO).pack(anchor="w")

        bloco_botoes = ctk.CTkFrame(cabecalho, fg_color="transparent")
        bloco_botoes.pack(side="right")
        self.botao_parar = ctk.CTkButton(
            bloco_botoes, text="⏹  Parar", fg_color=estilo.BOTAO_PARAR, hover_color=estilo.BOTAO_PARAR_HOVER,
            width=100, command=self.controlador.parar_execucao, state="disabled",
        )
        self.botao_parar.pack(side="left", padx=(0, 10))
        ctk.CTkButton(
            bloco_botoes, text="+  Nova Execução", fg_color=estilo.DOURADO, hover_color=estilo.DOURADO_HOVER,
            width=150, command=lambda: self.controlador.mostrar_pagina("Execuções"),
        ).pack(side="left")

        # --- Cartões de estatística ---
        linha_cartoes = ctk.CTkFrame(self, fg_color="transparent")
        linha_cartoes.pack(fill="x", padx=24, pady=(0, 16))
        for i in range(4):
            linha_cartoes.grid_columnconfigure(i, weight=1, uniform="cartoes")

        self.cartao_dados = CartaoEstatistica(linha_cartoes, "📄", "0", "Dados Capturados")
        self.cartao_dados.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        self.cartao_perfis = CartaoEstatistica(linha_cartoes, "👤", "0", "Perfis Configurados")
        self.cartao_perfis.grid(row=0, column=1, sticky="nsew", padx=8)

        self.cartao_execucoes_hoje = CartaoEstatistica(linha_cartoes, "▶", "0", "Execuções Hoje")
        self.cartao_execucoes_hoje.grid(row=0, column=2, sticky="nsew", padx=8)

        self.cartao_tempo_hoje = CartaoEstatistica(linha_cartoes, "⏱", "00:00:00", "Tempo Total Hoje")
        self.cartao_tempo_hoje.grid(row=0, column=3, sticky="nsew", padx=(8, 0))

        # --- Execução em andamento ---
        painel_andamento = ctk.CTkFrame(self, fg_color=estilo.FUNDO_CARTAO, corner_radius=estilo.RAIO_CARTAO,
                                        border_width=0)
        painel_andamento.pack(fill="x", padx=24, pady=(0, 16))
        self.faixa_andamento = ctk.CTkFrame(painel_andamento, fg_color=estilo.VERDE, width=4, corner_radius=0)
        self.faixa_andamento.pack(side="left", fill="y")
        conteudo_andamento = ctk.CTkFrame(painel_andamento, fg_color="transparent")
        conteudo_andamento.pack(side="left", fill="both", expand=True, padx=16, pady=14)

        self.label_titulo_andamento = ctk.CTkLabel(
            conteudo_andamento, text="Execução em andamento", font=ctk.CTkFont(size=14, weight="bold"),
            text_color=estilo.VERDE,
        )
        self.label_titulo_andamento.pack(anchor="w")

        # Linha 1: Perfil (esquerda) | Início (direita)
        linha_perfil = ctk.CTkFrame(conteudo_andamento, fg_color="transparent")
        linha_perfil.pack(fill="x", pady=(10, 2))
        self.label_perfil = ctk.CTkLabel(linha_perfil, text="", font=ctk.CTkFont(size=12),
                                        text_color=estilo.TEXTO_PRIMARIO)
        self.label_perfil.pack(side="left")
        self.label_inicio = ctk.CTkLabel(linha_perfil, text="", font=ctk.CTkFont(size=12),
                                        text_color=estilo.TEXTO_SECUNDARIO)
        self.label_inicio.pack(side="right")

        # Linha 2: Status (esquerda) | Previsão de término (direita)
        linha_status = ctk.CTkFrame(conteudo_andamento, fg_color="transparent")
        linha_status.pack(fill="x", pady=(0, 10))
        self.label_status_andamento = ctk.CTkLabel(
            linha_status, text="Nenhuma execução em andamento no momento. Clique em \"Nova Execução\" para começar.",
            font=ctk.CTkFont(size=12, weight="bold"), text_color=estilo.TEXTO_SECUNDARIO, justify="left",
        )
        self.label_status_andamento.pack(side="left")
        self.label_previsao = ctk.CTkLabel(linha_status, text="", font=ctk.CTkFont(size=12),
                                        text_color=estilo.TEXTO_SECUNDARIO)
        self.label_previsao.pack(side="right")

        # Barra de progresso com percentual
        self.label_progresso_geral = ctk.CTkLabel(
            conteudo_andamento, text="Progresso geral", font=ctk.CTkFont(size=11), text_color=estilo.TEXTO_SECUNDARIO
        )
        linha_barra = ctk.CTkFrame(conteudo_andamento, fg_color="transparent")
        self.barra_andamento = ctk.CTkProgressBar(linha_barra)
        self.barra_andamento.set(0)
        self.barra_andamento.pack(side="left", fill="x", expand=True)
        self.label_percentual = ctk.CTkLabel(linha_barra, text="0%", font=ctk.CTkFont(size=12, weight="bold"),
                                            text_color=estilo.TEXTO_PRIMARIO, width=42)
        self.label_percentual.pack(side="right", padx=(10, 0))
        # esses dois (label + barra) só aparecem quando tem execução rodando
        self.label_progresso_geral.pack_forget()
        linha_barra.pack_forget()
        self._linha_barra = linha_barra

        # --- Blocos grandes: Processados / Sucesso / Pendentes / Erro ---
        self.linha_dashboard = ctk.CTkFrame(conteudo_andamento, fg_color="transparent")
        for i in range(4):
            self.linha_dashboard.grid_columnconfigure(i, weight=1, uniform="blocos")
        self.bloco_processados = BlocoGrandeStatus(self.linha_dashboard, ICONE_PROCESSADOS, estilo.VERDE_SUCESSO, "Processados")
        self.bloco_sucesso = BlocoGrandeStatus(self.linha_dashboard, ICONE_SUCESSO, estilo.VERDE_SUCESSO, "Sucessos")
        self.bloco_pendentes = BlocoGrandeStatus(self.linha_dashboard, ICONE_PENDENTES, estilo.AMARELO_ALERTA, "Pendentes")
        self.bloco_erro = BlocoGrandeStatus(self.linha_dashboard, ICONE_ERRO, estilo.VERMELHO_ERRO, "Erros")
        for i, bloco in enumerate((self.bloco_processados, self.bloco_sucesso,
                                    self.bloco_pendentes, self.bloco_erro)):
            bloco.grid(row=0, column=i, sticky="nsew", pady=(16, 0))
        # começa escondido — só aparece quando tem execução rodando (ver atualizar())

        # --- Execuções recentes ---
        painel_recentes = ctk.CTkFrame(self, fg_color=estilo.FUNDO_CARTAO, corner_radius=estilo.RAIO_CARTAO)
        painel_recentes.pack(fill="both", expand=True, padx=24, pady=(0, 24))
        ctk.CTkLabel(painel_recentes, text="Execuções recentes", font=ctk.CTkFont(size=14, weight="bold"),
                    text_color=estilo.TEXTO_PRIMARIO).pack(anchor="w", padx=16, pady=(16, 8))

        self.frame_tabela = ctk.CTkFrame(painel_recentes, fg_color="transparent")
        self.frame_tabela.pack(fill="both", expand=True, padx=16)

        ctk.CTkButton(
            painel_recentes, text="Ver todas as execuções", fg_color=estilo.FUNDO_SUTIL,
            hover_color=estilo.BORDA, text_color=estilo.TEXTO_PRIMARIO,
            command=lambda: self.controlador.mostrar_pagina("Execuções"),
        ).pack(pady=16)

        self.atualizar()

    # ------------------------------------------------------------------
    def _montar_cabecalho_tabela(self, container):
        colunas = ["Data/Hora", "Perfis", "Status", "Registros", "Duração", ""]
        larguras = [3, 1, 2, 1, 1, 1]
        for i, peso in enumerate(larguras):
            container.grid_columnconfigure(i, weight=peso)
        for i, texto in enumerate(colunas):
            ctk.CTkLabel(container, text=texto, font=ctk.CTkFont(size=11, weight="bold"),
                        text_color=estilo.TEXTO_SECUNDARIO).grid(row=0, column=i, sticky="w", pady=(0, 6), padx=4)

    def _cor_status(self, status):
        if status == "Concluído":
            return estilo.VERDE_SUCESSO
        if status == "Interrompido":
            return estilo.VERMELHO_ERRO
        return estilo.AMARELO_ALERTA

    def _calcular_previsao(self) -> str:
        """Estima a hora de término com base no ritmo até agora (tempo
        decorrido / fração já concluída). Só dá pra estimar depois que pelo
        menos um RA terminou — antes disso, mostra "Calculando..."."""
        inicio_dt = self.controlador.inicio_execucao_dt
        progresso = self.controlador.progresso_atual
        if not inicio_dt or progresso <= 0:
            return "Calculando..."
        decorrido = (datetime.now() - inicio_dt).total_seconds()
        total_estimado = decorrido / progresso
        restante = max(0, total_estimado - decorrido)
        previsao = datetime.now() + timedelta(seconds=restante)
        return previsao.strftime("%d/%m/%Y %H:%M:%S")

    def atualizar(self):
        historico = history.carregar_historico()
        stats = history.estatisticas(historico)

        self.cartao_dados.atualizar_valor(str(stats["total_dados_capturados"]))
        self.cartao_perfis.atualizar_valor(f"{self.controlador.perfis_configurados_count()}/{config.NUM_PERFIS}")
        self.cartao_execucoes_hoje.atualizar_valor(str(stats["execucoes_hoje"]))
        self.cartao_tempo_hoje.atualizar_valor(stats["tempo_total_hoje"])

        # execução em andamento
        if self.controlador.em_execucao:
            pct = int(self.controlador.progresso_atual * 100)

            if self.controlador.parando:
                self.label_titulo_andamento.configure(text="Execução em andamento", text_color=estilo.VERMELHO_ERRO)
                self.faixa_andamento.configure(fg_color=estilo.VERMELHO_ERRO)
                self.label_status_andamento.configure(
                    text="Status: Parando...", text_color=estilo.VERMELHO_ERRO,
                )
                self.botao_parar.configure(state="disabled", text="⏹  Parando...")
            else:
                self.label_titulo_andamento.configure(text="Execução em andamento", text_color=estilo.VERDE)
                self.faixa_andamento.configure(fg_color=estilo.VERDE)
                self.label_status_andamento.configure(
                    text="Status: Capturando dados...", text_color=estilo.VERDE,
                )
                self.botao_parar.configure(state="normal", text="⏹  Parar")

            # Perfil + horário de início
            perfis_texto = " e ".join(self.controlador.apelidos_execucao_atual) or "—"
            self.label_perfil.configure(text=f"Perfil: {perfis_texto}")
            inicio_dt = self.controlador.inicio_execucao_dt
            self.label_inicio.configure(
                text=f"Início: {inicio_dt.strftime('%d/%m/%Y %H:%M:%S')}" if inicio_dt else ""
            )

            # Previsão de término (estimada a partir do ritmo até agora)
            self.label_previsao.configure(text=f"Previsão de término: {self._calcular_previsao()}")

            # Progresso geral + percentual
            self.label_progresso_geral.pack(anchor="w", pady=(0, 4))
            self._linha_barra.pack(fill="x")
            self.barra_andamento.set(self.controlador.progresso_atual)
            self.label_percentual.configure(text=f"{pct}%")

            # blocos grandes: Processados / Sucesso / Pendentes / Erro
            processados = self.controlador.concluidos_atual
            processando = len(self.controlador.ras_em_processamento)  # ainda conta pra "Pendentes" ficar certo
            pendentes = max(0, self.controlador.total_atual - processados - processando)
            self.bloco_processados.atualizar(processados)
            self.bloco_sucesso.atualizar(self.controlador.contagem_sucesso)
            self.bloco_pendentes.atualizar(pendentes)
            self.bloco_erro.atualizar(self.controlador.contagem_erro)
            self.linha_dashboard.pack(fill="x", pady=(12, 4))
        else:
            self.label_titulo_andamento.configure(text="Execução em andamento", text_color=estilo.VERDE)
            self.faixa_andamento.configure(fg_color=estilo.VERDE)
            self.label_progresso_geral.pack_forget()
            self._linha_barra.pack_forget()
            self.linha_dashboard.pack_forget()
            self.label_perfil.configure(text="")
            self.label_inicio.configure(text="")
            self.label_previsao.configure(text="")
            self.label_status_andamento.configure(
                text="Nenhuma execução em andamento no momento. Clique em \"Nova Execução\" para começar.",
                text_color=estilo.TEXTO_SECUNDARIO,
            )
            self.botao_parar.configure(state="disabled", text="⏹  Parar")

        # tabela de recentes (últimas 5) — só reconstrói se o histórico
        # realmente mudou, pra não ficar destruindo/recriando os widgets a
        # cada atualização (era isso que fazia a tabela "piscar")
        assinatura = tuple(
            (item.get("data_hora"), item.get("status"), item.get("registros")) for item in historico[:5]
        )
        if assinatura == self._ultima_assinatura_recentes:
            return
        self._ultima_assinatura_recentes = assinatura

        for widget in self.frame_tabela.winfo_children():
            widget.destroy()
        self._montar_cabecalho_tabela(self.frame_tabela)

        if not historico:
            ctk.CTkLabel(self.frame_tabela, text="Nenhuma execução registrada ainda.",
                        text_color=estilo.TEXTO_SECUNDARIO).grid(row=1, column=0, columnspan=6, pady=10, sticky="w")
        else:
            for linha_idx, item in enumerate(historico[:5], start=1):
                cor_status = self._cor_status(item.get("status", ""))
                ctk.CTkLabel(self.frame_tabela, text=item.get("data_hora", ""),
                            text_color=estilo.TEXTO_PRIMARIO).grid(row=linha_idx, column=0, sticky="w", padx=4, pady=4)
                texto_perfis = ", ".join(item.get("perfis", [])) or str(item.get("janelas", 1))
                ctk.CTkLabel(self.frame_tabela, text=texto_perfis,
                            text_color=estilo.TEXTO_PRIMARIO).grid(row=linha_idx, column=1, sticky="w", padx=4)
                ctk.CTkLabel(self.frame_tabela, text=item.get("status", ""), text_color=cor_status,
                            font=ctk.CTkFont(weight="bold")).grid(row=linha_idx, column=2, sticky="w", padx=4)
                ctk.CTkLabel(self.frame_tabela, text=str(item.get("registros", 0)),
                            text_color=estilo.TEXTO_PRIMARIO).grid(row=linha_idx, column=3, sticky="w", padx=4)
                ctk.CTkLabel(self.frame_tabela, text=history.formatar_duracao(item.get("duracao_segundos", 0)),
                            text_color=estilo.TEXTO_PRIMARIO).grid(row=linha_idx, column=4, sticky="w", padx=4)
                pasta = item.get("pasta_saida", "")
                if pasta:
                    ctk.CTkButton(self.frame_tabela, text="📂", width=30, fg_color=estilo.FUNDO_SUTIL,
                                hover_color=estilo.BORDA, text_color=estilo.TEXTO_PRIMARIO,
                                command=lambda p=pasta: self.controlador.abrir_pasta(p)).grid(
                        row=linha_idx, column=5, sticky="e", padx=4)