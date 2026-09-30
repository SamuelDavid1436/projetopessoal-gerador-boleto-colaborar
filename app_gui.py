# -*- coding: utf-8 -*-
"""
app_gui.py
==========
Janela principal: barra lateral de navegação + área de conteúdo com as
páginas (Início, Perfis, Execuções, Configurações, Logs, Suporte, Sobre).
Concentra o estado compartilhado (execução em andamento, login, tema) que
as páginas usam através do "controlador" (esta própria classe App).
"""
import os
import platform
import queue
import subprocess
import threading
import time
from datetime import datetime
from tkinter import messagebox

import customtkinter as ctk
from PIL import Image

import browser_manager
import config
import data_io
import estilo
import history
import perfis
import recuperacao
import runner
from paginas.pagina_inicio import PaginaInicio
from paginas.pagina_execucoes import PaginaExecucoes
from paginas.pagina_perfis import PaginaPerfis
from paginas.pagina_configuracoes import PaginaConfiguracoes
from paginas.pagina_logs import PaginaLogs
from paginas.pagina_suporte import PaginaSuporte
from paginas.pagina_sobre import PaginaSobre

ITENS_MENU = [
    ("Início", "🏠"),
    ("Perfis", "👤"),
    ("Execuções", "✅"),
    ("Configurações", "⚙"),
    ("Logs", "🗒"),
    ("Suporte", "❓"),
    ("Sobre", "ℹ"),
]


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title(config.NOME_PRODUTO)
        self.geometry("1200x760")
        self.minsize(980, 620)
        self.configure(fg_color=estilo.FUNDO)
        self._definir_icone_janela()
        self.protocol("WM_DELETE_WINDOW", self._ao_fechar_janela)

        browser_manager.garantir_pastas()

        # --- estado compartilhado de execução ---
        self.em_execucao = False
        self.parando = False  # True = pediu pra parar, mas ainda está terminando o RA atual
        self.evento_parar = threading.Event()
        self.progresso_atual = 0.0
        self.concluidos_atual = 0
        self.total_atual = 0
        self.contagem_sucesso = 0
        self.contagem_erro = 0
        self.ras_em_processamento = {}  # apelido do perfil -> RA que está processando agora
        self.inicio_execucao_dt = None  # datetime de início da execução atual (pra calcular previsão de término)
        self.apelidos_execucao_atual = []  # perfis usados na execução atual
        self.polos_base = {}  # {RA: polo} da coluna POLO da base (vazio = modo manual)
        self.telefones_base = {}  # {RA: telefone} informado na base importada (tem prioridade)
        self._lock_progresso = threading.Lock()
        self._fila_log = queue.Queue()

        self.botoes_menu = {}
        self.pagina_ativa = None

        self._montar_layout()
        self._agendar_tick()
        self.after(300, self._checar_recuperacao_pendente)
        self._log(f"Pasta de dados (resultados, backup e logs): {config.PASTA_DOCUMENTOS}")
        self._log(f"Pasta dos perfis do Chrome (logins): {config.PASTA_PERFIS}")

    # ------------------------------------------------------------------
    # Recuperação de execução interrompida (queda/travamento)
    # ------------------------------------------------------------------
    def _checar_recuperacao_pendente(self):
        if not recuperacao.existe_execucao_pendente():
            return
        pendente = recuperacao.carregar_pendente()
        resultados = pendente.get("resultados", [])
        iniciado_em = pendente.get("iniciado_em", "?")
        total = pendente.get("total_ras", "?")

        recuperar = messagebox.askyesno(
            "Execução anterior interrompida",
            f"Encontrei uma execução iniciada em {iniciado_em} que não terminou normalmente "
            f"(provavelmente por uma queda de energia, travamento ou fechamento inesperado). "
            f"Ela tinha {len(resultados)} de {total} RA(s) já processados quando parou.\n\n"
            "Quer salvar esses resultados parciais num arquivo agora?",
        )
        if recuperar and resultados:
            try:
                momento = datetime.strptime(iniciado_em, "%d/%m/%Y %H:%M:%S")
            except ValueError:
                momento = None  # usa o horário atual como reserva
            caminho_csv, caminho_xlsx = data_io.salvar_resultado(resultados, momento=momento)
            self._log(f"Resultados recuperados de uma execução interrompida: {len(resultados)} registro(s).")
            self._log(f"Arquivo CSV: {caminho_csv}")
            self._log(f"Arquivo Excel: {caminho_xlsx}")
            data_io.remover_backup_parcial(momento=momento)
            try:
                data_io.salvar_relatorio_meses(resultados, momento=momento)
                data_io.salvar_base_disparo(resultados, momento=momento)
            except Exception as erro_relatorio:  # pylint: disable=broad-except
                self._log(f"[aviso] não consegui gerar o relatório de meses/base de disparo na recuperação: {erro_relatorio}")
            messagebox.showinfo(
                "Recuperado", f"Resultados parciais salvos.\n\nCSV: {caminho_csv}\nExcel: {caminho_xlsx}",
            )
        recuperacao.descartar()

    # ------------------------------------------------------------------
    # Layout geral: sidebar + área de páginas
    # ------------------------------------------------------------------
    def _ao_fechar_janela(self):
        if self.em_execucao:
            confirmar = messagebox.askyesno(
                "Execução em andamento",
                "Ainda tem uma execução rodando. Fechar agora pode deixar o navegador aberto de "
                "forma inconsistente — o RA que está processando não vai terminar direito.\n\n"
                "O recomendado é clicar em \"Parar\" e esperar a mensagem confirmando que terminou, "
                "antes de fechar o programa.\n\nMesmo assim, quer fechar agora?",
            )
            if not confirmar:
                return
        self.destroy()

    def _definir_icone_janela(self):
        """Define o ícone da janela/barra de tarefas, se o arquivo .ico existir."""
        if os.path.isfile(config.CAMINHO_ICONE):
            try:
                self.iconbitmap(config.CAMINHO_ICONE)
            except Exception:  # pylint: disable=broad-except
                pass  # em Linux/Mac o .ico pode não funcionar; não é crítico

    def _montar_selo_logo(self, container):
        """Mostra o logo real (assets/logo.png). Se não existir, cai para um quadrado verde simples."""
        if os.path.isfile(config.CAMINHO_LOGO):
            imagem = ctk.CTkImage(
                light_image=Image.open(config.CAMINHO_LOGO),
                dark_image=Image.open(config.CAMINHO_LOGO),
                size=(44, 44),
            )
            ctk.CTkLabel(container, text="", image=imagem).pack(anchor="w")
        else:
            selo = ctk.CTkFrame(container, fg_color=estilo.VERDE, width=44, height=44, corner_radius=10)
            selo.pack(anchor="w")
            selo.pack_propagate(False)
            ctk.CTkLabel(selo, text="R$", font=ctk.CTkFont(size=16, weight="bold"),
                         text_color="white").pack(expand=True)

    def _montar_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        sidebar = ctk.CTkFrame(self, fg_color=estilo.FUNDO_SIDEBAR, width=230, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsw")
        sidebar.grid_propagate(False)

        # logo + título
        bloco_logo = ctk.CTkFrame(sidebar, fg_color="transparent")
        bloco_logo.pack(fill="x", padx=20, pady=(24, 16))
        self._montar_selo_logo(bloco_logo)

        ctk.CTkLabel(bloco_logo, text="Captura de Boleto", font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=estilo.TEXTO_PRIMARIO).pack(anchor="w", pady=(10, 0))
        ctk.CTkLabel(bloco_logo, text="Colaboraread", font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=estilo.VERDE).pack(anchor="w")
        ctk.CTkLabel(bloco_logo, text="Automação para consulta\ne extração de dados",
                     font=ctk.CTkFont(size=11), text_color=estilo.TEXTO_SECUNDARIO, justify="left").pack(
            anchor="w", pady=(6, 0))

        # navegação
        bloco_nav = ctk.CTkFrame(sidebar, fg_color="transparent")
        bloco_nav.pack(fill="x", padx=12, pady=(10, 0))
        for nome, icone in ITENS_MENU:
            botao = ctk.CTkButton(
                bloco_nav, text=f"{icone}   {nome}", anchor="w", fg_color="transparent",
                hover_color=estilo.FUNDO_SUTIL, text_color=estilo.TEXTO_PRIMARIO, height=38,
                command=lambda n=nome: self.mostrar_pagina(n),
            )
            botao.pack(fill="x", pady=2)
            self.botoes_menu[nome] = botao

        # rodapé
        ctk.CTkLabel(sidebar, text="© 2026 Captura Boleto Colaboraread", font=ctk.CTkFont(size=10),
                     text_color=estilo.TEXTO_SECUNDARIO).pack(side="bottom", anchor="w", padx=20, pady=(0, 4))
        ctk.CTkLabel(sidebar, text="Todos os direitos reservados", font=ctk.CTkFont(size=10),
                     text_color=estilo.TEXTO_SECUNDARIO).pack(side="bottom", anchor="w", padx=20, pady=(0, 12))

        # área de conteúdo (todas as páginas empilhadas, uma visível por vez)
        area_conteudo = ctk.CTkFrame(self, fg_color=estilo.FUNDO, corner_radius=0)
        area_conteudo.grid(row=0, column=1, sticky="nsew")
        area_conteudo.grid_rowconfigure(0, weight=1)
        area_conteudo.grid_columnconfigure(0, weight=1)

        self.paginas = {
            "Início": PaginaInicio(area_conteudo, self),
            "Perfis": PaginaPerfis(area_conteudo, self),
            "Execuções": PaginaExecucoes(area_conteudo, self),
            "Configurações": PaginaConfiguracoes(area_conteudo, self),
            "Logs": PaginaLogs(area_conteudo, self),
            "Suporte": PaginaSuporte(area_conteudo, self),
            "Sobre": PaginaSobre(area_conteudo, self),
        }
        for pagina in self.paginas.values():
            pagina.grid(row=0, column=0, sticky="nsew")

        self.mostrar_pagina("Início")

    def mostrar_pagina(self, nome: str):
        if nome not in self.paginas:
            return
        self.pagina_ativa = nome
        self.paginas[nome].tkraise()
        for nome_botao, botao in self.botoes_menu.items():
            if nome_botao == nome:
                botao.configure(fg_color=estilo.VERDE, text_color="white")
            else:
                botao.configure(fg_color="transparent", text_color=estilo.TEXTO_PRIMARIO)
        if hasattr(self.paginas[nome], "atualizar"):
            self.paginas[nome].atualizar()

    # ------------------------------------------------------------------
    # Ciclo de atualização (log + estado dinâmico das páginas visíveis)
    # ------------------------------------------------------------------
    def _agendar_tick(self):
        houve_log = False
        try:
            while True:
                mensagem = self._fila_log.get_nowait()
                self.paginas["Logs"].adicionar_linha(mensagem)
                houve_log = True
        except queue.Empty:
            pass

        pagina = self.paginas.get(self.pagina_ativa)
        if pagina is not None and hasattr(pagina, "atualizar") and pagina is not self.paginas["Logs"]:
            pagina.atualizar()

        self.after(400, self._agendar_tick)

    def _log(self, mensagem: str):
        self._fila_log.put(mensagem)

    # ------------------------------------------------------------------
    # Ações usadas pelas páginas — Perfis
    # ------------------------------------------------------------------
    def perfil_tem_dados(self, perfil_id: int) -> bool:
        """Heurística rápida (sem abrir navegador): a pasta desse perfil já tem algo salvo?"""
        return browser_manager.perfil_tem_dados(perfil_id)

    def perfis_configurados_count(self) -> int:
        return sum(1 for i in range(1, config.NUM_PERFIS + 1) if self.perfil_tem_dados(i))

    def login_manual(self, perfil_id: int):
        apelido = perfis.obter_apelido(perfil_id)
        self._log(f"[{apelido}] abrindo janela para login manual no Prisma. Faça login e depois pode fechar a janela.")
        threading.Thread(target=self._abrir_janela_login_thread, args=(perfil_id,), daemon=True).start()

    def _abrir_janela_login_thread(self, perfil_id: int):
        try:
            browser_manager.abrir_janela_login_manual(
                perfil_id, ao_capturar_email=lambda email: self._email_capturado(perfil_id, email)
            )
        except Exception as erro:  # pylint: disable=broad-except
            self._log(f"Erro ao abrir janela de login do perfil {perfil_id}: {erro}")

    def _email_capturado(self, perfil_id: int, email: str):
        ja_tinha_apelido_proprio = perfis.apelido_personalizado(perfil_id)
        perfis.definir_email(perfil_id, email)
        if ja_tinha_apelido_proprio:
            self._log(f"[Perfil {perfil_id}] e-mail detectado: {email} (apelido personalizado mantido).")
        else:
            self._log(f"[Perfil {perfil_id}] e-mail detectado: {email} — usado como apelido.")

    def limpar_perfil(self, perfil_id: int):
        apelido = perfis.obter_apelido(perfil_id)
        browser_manager.limpar_perfil(perfil_id)
        perfis.resetar_perfil(perfil_id)  # também limpa apelido e e-mail salvos na tela
        self._log(f"[{apelido}] perfil limpo (login, apelido e e-mail redefinidos). Use 'Login manual' para logar novamente antes de usar esse perfil.")

    def verificar_login(self, perfil_id: int, callback_concluido=None):
        """Verifica (best-effort, em segundo plano) se o perfil está logado no Prisma/Colaboraread
        e, se estiver, também tenta capturar o e-mail direto da tela."""
        threading.Thread(
            target=self._verificar_login_thread, args=(perfil_id, callback_concluido), daemon=True
        ).start()

    def _verificar_login_thread(self, perfil_id: int, callback_concluido):
        apelido = perfis.obter_apelido(perfil_id)
        self._log(f"[{apelido}] verificando login...")
        status, email = browser_manager.detectar_login(perfil_id, log=self._log)
        perfis.definir_status(perfil_id, status)
        if email:
            perfis.definir_email(perfil_id, email)
        sufixo_email = f" (e-mail detectado: {email})" if email else ""
        self._log(f"[{apelido}] status: {status}{sufixo_email}")
        if callback_concluido:
            self.after(0, callback_concluido)

    def renomear_perfil(self, perfil_id: int, novo_apelido: str):
        perfis.definir_apelido(perfil_id, novo_apelido)

    def definir_email_perfil(self, perfil_id: int, novo_email: str):
        """Define o e-mail manualmente (botão de lápis), pra quando a
        detecção automática não funcionar."""
        perfis.definir_email(perfil_id, novo_email)
        apelido = perfis.obter_apelido(perfil_id)
        self._log(f"[{apelido}] e-mail definido manualmente: {novo_email}")

    # ------------------------------------------------------------------
    # Ações usadas pelas páginas — Geral
    # ------------------------------------------------------------------
    def abrir_pasta(self, caminho: str):
        if not caminho or not os.path.isdir(caminho):
            messagebox.showwarning("Atenção", "Essa pasta não existe (talvez tenha sido movida ou apagada).")
            return
        sistema = platform.system()
        try:
            if sistema == "Windows":
                os.startfile(caminho)  # pylint: disable=no-member
            elif sistema == "Darwin":
                subprocess.Popen(["open", caminho])
            else:
                subprocess.Popen(["xdg-open", caminho])
        except Exception as erro:  # pylint: disable=broad-except
            messagebox.showerror("Erro", f"Não consegui abrir a pasta: {erro}")

    def reprocessar_erros(self, caminho_resultado_csv: str):
        """
        Lê o resultado.csv de uma execução já concluída, pega só os RAs
        que deram erro, e já deixa pronto na tela Execuções pra rodar de
        novo — sem precisar filtrar a planilha na mão. Não muda a regra de
        "cada execução é independente": isso só monta uma base NOVA (só
        com os erros) pra você importar como uma execução normal.
        """
        if self.em_execucao:
            messagebox.showwarning("Atenção", "Espere a execução atual terminar antes de reprocessar erros.")
            return
        if not os.path.isfile(caminho_resultado_csv):
            messagebox.showwarning("Atenção", "O arquivo dessa execução não foi encontrado (talvez tenha sido movido ou apagado).")
            return

        ras_com_erro = data_io.extrair_ras_com_erro(caminho_resultado_csv)
        if not ras_com_erro:
            messagebox.showinfo("Tudo certo", "Essa execução não teve nenhum RA com erro — nada para reprocessar.")
            return

        carimbo = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        caminho_novo = os.path.join(config.PASTA_LOGS, "reprocessamentos", f"erros_{carimbo}.csv")
        data_io.salvar_lista_ras(ras_com_erro, caminho_novo, telefones=self.telefones_base,
                                 polos=self.polos_base)

        self.mostrar_pagina("Execuções")
        pagina = self.paginas["Execuções"]
        pagina.caminho_arquivo_ras = caminho_novo
        pagina.label_arquivo.configure(
            text=f"{len(ras_com_erro)} RA(s) com erro prontos para reprocessar ({os.path.basename(caminho_novo)})",
            text_color=estilo.TEXTO_PRIMARIO,
        )
        self._log(f"{len(ras_com_erro)} RA(s) com erro carregados para reprocessamento: {caminho_novo}")


    def abrir_arquivo(self, caminho: str):
        if not caminho or not os.path.isfile(caminho):
            messagebox.showwarning("Atenção", "Esse arquivo não foi encontrado.")
            return
        sistema = platform.system()
        try:
            if sistema == "Windows":
                os.startfile(caminho)  # pylint: disable=no-member
            elif sistema == "Darwin":
                subprocess.Popen(["open", caminho])
            else:
                subprocess.Popen(["xdg-open", caminho])
        except Exception as erro:  # pylint: disable=broad-except
            messagebox.showerror("Erro", f"Não consegui abrir o arquivo: {erro}")

    # ------------------------------------------------------------------
    # Execução da automação
    # ------------------------------------------------------------------
    def iniciar_execucao(self, ras: list, perfis_selecionados: list):
        if self.em_execucao:
            messagebox.showinfo("Aviso", "Já existe uma execução em andamento.")
            return
        if not perfis_selecionados:
            messagebox.showwarning("Atenção", "Selecione ao menos um perfil para rodar a automação.")
            return

        self.em_execucao = True
        self.parando = False
        self.evento_parar = threading.Event()
        self.total_atual = len(ras)
        self.concluidos_atual = 0
        self.progresso_atual = 0.0
        self.contagem_sucesso = 0
        self.contagem_erro = 0
        self.ras_em_processamento = {}
        self.inicio_execucao_dt = datetime.now()
        self.apelidos_execucao_atual = [perfis.obter_apelido(pid) for pid in perfis_selecionados]

        self._log(f"Backup automático: a cada RA o resultado é gravado em "
                  f"{os.path.join(config.PASTA_SAIDA, self.inicio_execucao_dt.strftime('%Y-%m-%d_%H-%M-%S'), data_io.NOME_BACKUP_PARCIAL)}")
        # começa um ciclo novo do zero — descarta automaticamente qualquer
        # log de retomada de uma execução anterior (mesmo que não tenha
        # terminado). Cada execução é sempre uma "fotografia" só da base
        # importada agora, nunca considera nada de antes.
        recuperacao.iniciar_novo_ciclo(total_ras=len(ras))

        apelidos_usados = [perfis.obter_apelido(pid) for pid in perfis_selecionados]
        self._log(
            f"Iniciando execução: {len(ras)} RA(s), perfis: {', '.join(apelidos_usados)}. "
            + (f"{len(self.telefones_base)} telefone(s) vindos da base (têm prioridade). " if self.telefones_base else "")
            + (f"Modo automático: {len(set(self.polos_base.values()))} polo(s) na base — cada janela entra sozinha no "
               "polo de cada RA (Prisma -> polo -> Colaborar). " if self.polos_base else
               "Cada janela vai esperar você entrar no Colaborar (Prisma -> polo -> Portais -> Colaborar).")
        )
        self.mostrar_pagina("Execuções")

        threading.Thread(
            target=self._executar_thread, args=(ras, perfis_selecionados), daemon=True
        ).start()

    def parar_execucao(self):
        if not self.em_execucao or self.parando:
            return
        self.parando = True
        self.evento_parar.set()
        self._log(
            "Solicitando parada... a automação NÃO fecha o navegador na hora — ela termina o RA "
            "que está processando em cada janela (isso pode levar alguns segundos) e só depois encerra."
        )

    def _callback_inicio_ra(self, apelido: str, ra: str):
        with self._lock_progresso:
            self.ras_em_processamento[apelido] = ra

    def _callback_progresso(self, registro: dict):
        telefone_informado = self.telefones_base.get(str(registro.get("RA", "")).strip())
        if telefone_informado:
            registro["Celular"] = telefone_informado
        with self._lock_progresso:
            apelido = registro.get("Perfil", "")
            self.ras_em_processamento.pop(apelido, None)
            self.concluidos_atual += 1
            self.progresso_atual = self.concluidos_atual / self.total_atual if self.total_atual else 0
            if runner.registro_teve_sucesso(registro):
                self.contagem_sucesso += 1
            else:
                self.contagem_erro += 1
        recuperacao.registrar_resultado(registro)
        # backup visível (CSV na pasta da execução), gravado a cada RA
        data_io.gravar_backup_linha(registro, momento=self.inicio_execucao_dt)

    def _mostrar_conclusao(self, total_registros: int, pasta_saida: str):
        """Mensagem de conclusão simples (sem caminhos de arquivo longos/feios
        na tela) — quem quiser o caminho exato encontra na tabela de
        histórico (botão "Abrir pasta"). Aqui já oferece abrir direto."""
        abrir = messagebox.askyesno(
            "Concluído",
            f"Processamento concluído — {total_registros} registro(s) processado(s).\n\n"
            "Os arquivos CSV e Excel foram salvos. Quer abrir a pasta agora?",
        )
        if abrir:
            self.abrir_pasta(pasta_saida)

    def _executar_thread(self, ras, perfis_selecionados):
        inicio = time.time()
        status_final = "Concluído"
        resultados = []
        caminho_csv, caminho_xlsx = "", ""
        apelidos_usados = [perfis.obter_apelido(pid) for pid in perfis_selecionados]
        try:
            resultados = runner.executar(
                ras, perfis_selecionados=perfis_selecionados,
                log_callback=self._log, progresso_callback=self._callback_progresso,
                inicio_ra_callback=self._callback_inicio_ra,
                evento_parar=self.evento_parar,
                polos=self.polos_base,
            )
            if self.evento_parar.is_set():
                status_final = "Interrompido"

            if resultados:
                caminho_csv, caminho_xlsx = data_io.salvar_resultado(resultados, momento=self.inicio_execucao_dt)
                self._log(f"Arquivo CSV: {caminho_csv}")
                self._log(f"Arquivo Excel: {caminho_xlsx}")
                data_io.remover_backup_parcial(momento=self.inicio_execucao_dt)  # finais gravados: backup não serve mais
                try:
                    caminho_relatorio_csv, _ = data_io.salvar_relatorio_meses(
                        resultados, momento=self.inicio_execucao_dt
                    )
                    self._log(f"Relatório de meses (a partir de {config.MES_MINIMO_RELATORIO}/"
                               f"{config.ANO_MINIMO_RELATORIO}): {caminho_relatorio_csv}")
                except Exception as erro_relatorio:  # pylint: disable=broad-except
                    self._log(f"[aviso] não consegui gerar o relatório de meses: {erro_relatorio}")
                try:
                    caminho_disparo_csv, _ = data_io.salvar_base_disparo(
                        resultados, momento=self.inicio_execucao_dt
                    )
                    self._log(f"Base de disparo (último boleto de cada aluno): {caminho_disparo_csv}")
                except Exception as erro_disparo:  # pylint: disable=broad-except
                    self._log(f"[aviso] não consegui gerar a base de disparo: {erro_disparo}")
            self._log(f"Execução finalizada ({status_final}). {len(resultados)} registro(s) processado(s).")

        except Exception as erro:  # pylint: disable=broad-except
            status_final = "Erro"
            self._log(f"ERRO GERAL: {erro}")
            self.after(0, lambda: messagebox.showerror("Erro", str(erro)))
        finally:
            duracao = time.time() - inicio
            history.registrar_execucao(apelidos_usados, status_final, len(resultados), duracao,
                                        caminho_csv, caminho_xlsx)
            recuperacao.finalizar_ciclo()  # já salvou no CSV/Excel — não precisa mais do log temporário
            self.em_execucao = False
            self.parando = False
            self.ras_em_processamento = {}
            if status_final == "Concluído" and resultados:
                pasta_saida = os.path.dirname(caminho_csv) if caminho_csv else config.PASTA_SAIDA
                self.after(0, lambda: self._mostrar_conclusao(len(resultados), pasta_saida))


def rodar_app():
    app = App()
    app.mainloop()