# -*- coding: utf-8 -*-
"""
runner.py
=========
Distribui a lista de RAs entre os perfis selecionados pelo usuário (cada
perfil = uma janela do Chrome com login próprio), rodando em threads.
Suporta interrupção via threading.Event (botão "Parar") e reporta início e
resultado de cada RA (pra alimentar o dashboard de Processados/Processando/
Sucesso/Pendentes/Erro na interface).
"""
import threading
import queue
import time

import browser_manager
import config
import perfis
from colaboraread_client import ColaboraClient, aguardar_colaborar, entrar_no_polo


def _dividir_em_blocos(lista, n_blocos):
    """Divide a lista em n_blocos partes o mais equilibradas possível."""
    n_blocos = max(1, min(n_blocos, len(lista)) or 1)
    blocos = [[] for _ in range(n_blocos)]
    for indice, item in enumerate(lista):
        blocos[indice % n_blocos].append(item)
    return [bloco for bloco in blocos if bloco]


def _registro_erro(ra, apelido, polo, mensagem):
    registro = {coluna: "" for coluna in config.COLUNAS_SAIDA}
    registro.update({"RA": str(ra), "Perfil": apelido, "Polo": polo,
                     "Status da Consulta": f"Erro: {mensagem}", "_parcelas_relatorio": []})
    return registro


def registro_teve_sucesso(registro: dict) -> bool:
    """Considera sucesso qualquer 'Status da Consulta' que não comece com
    'Erro' (inclui 'OK', 'OK (CRM: ...)', 'OK (sem mensalidade...)' etc.)."""
    status = (registro.get("Status da Consulta") or "").strip()
    return not status.lower().startswith("erro")


MAX_TENTATIVAS_TIMEOUT = 3  # 1 tentativa original + até 2 novas tentativas


def _e_erro_de_timeout(status: str) -> bool:
    """
    Confere se o 'Status da Consulta' indica um timeout — esses casos
    valem a pena tentar de novo (a página só ficou lenta/travou aquela
    vez específica), diferente de "RA não encontrado" ou outros erros
    que não mudam tentando de novo.
    """
    return "tempo esgotado" in (status or "").lower()


def _worker(perfil_id, ras_do_perfil, resultados_queue, log_callback,
            progresso_callback, inicio_ra_callback, headless, evento_parar: threading.Event):
    apelido = perfis.obter_apelido(perfil_id)
    driver = None
    MAX_REINICIOS_SEGUIDOS = 3
    reinicios_seguidos = 0
    try:
        log_callback(f"[{apelido}] abrindo navegador...")
        driver = browser_manager.criar_driver_worker(perfil_id, headless=headless)
        log_perfil = lambda msg: log_callback(f"[{apelido}] {msg}")  # noqa: E731
        if not aguardar_colaborar(driver, evento_parar, log=log_perfil,
                                  tempo_limite=config.TEMPO_ESPERA_ACESSO_COLABORA):
            log_callback(f"[{apelido}] não entrou no Colaboraread — esse perfil não vai processar RAs.")
            return

        cliente = ColaboraClient(driver, log=log_perfil)

        for ra in ras_do_perfil:
            if evento_parar.is_set():
                log_callback(f"[{apelido}] interrompido pelo usuário.")
                break

            log_callback(f"[{apelido}] consultando RA {ra}...")
            inicio_ra_callback(apelido, ra)  # avisa que esse RA começou (pro dashboard)

            registro = cliente.consultar_ra(ra)

            # timeout: tenta de novo -- até MAX_TENTATIVAS_TIMEOUT no total pro mesmo RA.
            tentativa = 1
            while (_e_erro_de_timeout(registro.get("Status da Consulta", ""))
                   and tentativa < MAX_TENTATIVAS_TIMEOUT and not evento_parar.is_set()):
                tentativa += 1
                log_callback(
                    f"[{apelido}] RA {ra}: tempo esgotado — atualizando a página e tentando de "
                    f"novo (tentativa {tentativa}/{MAX_TENTATIVAS_TIMEOUT})..."
                )
                registro = cliente.consultar_ra(ra)

            registro["Perfil"] = apelido
            resultados_queue.put(registro)
            progresso_callback(registro)  # avisa que terminou, com o resultado (sucesso/erro)

            status = registro.get("Status da Consulta", "")
            log_callback(f"[{apelido}] RA {ra} -> {status}")

            if cliente.sessao_morta:
                # o navegador travou/fechou/ficou sem memória etc. Sem isso,
                # TODOS os RAs seguintes falhariam com o mesmo erro, um atrás
                # do outro, até acabar a lista inteira — reiniciar o
                # navegador do zero resolve e a automação continua de onde
                # parou (próximo RA da lista).
                reinicios_seguidos += 1
                if reinicios_seguidos > MAX_REINICIOS_SEGUIDOS:
                    log_callback(
                        f"[{apelido}] o navegador morreu {reinicios_seguidos} vezes seguidas — "
                        "algo mais sério deve estar errado (memória, antivírus, etc.). Desistindo "
                        "desse perfil pra não ficar reiniciando pra sempre."
                    )
                    break
                log_callback(
                    f"[{apelido}] sessão do navegador morreu — reiniciando o navegador "
                    f"(tentativa {reinicios_seguidos}/{MAX_REINICIOS_SEGUIDOS})..."
                )
                try:
                    driver.quit()
                except Exception:  # pylint: disable=broad-except
                    pass  # o navegador já morreu mesmo, só ignora
                time.sleep(1.5)  # dá tempo do Windows liberar os arquivos do processo morto
                try:
                    driver = browser_manager.criar_driver_worker(perfil_id, headless=headless)
                    if not aguardar_colaborar(driver, evento_parar, log=log_perfil,
                                              tempo_limite=config.TEMPO_ESPERA_ACESSO_COLABORA):
                        log_callback(f"[{apelido}] não voltou pro Colaboraread após reiniciar — parando esse perfil.")
                        break
                    cliente = ColaboraClient(driver, log=log_perfil)
                except Exception as erro_reinicio:  # pylint: disable=broad-except
                    log_callback(f"[{apelido}] não consegui reiniciar o navegador: {erro_reinicio}")
                    break
            else:
                reinicios_seguidos = 0  # RA processou (com erro comum ou não) -- zera o contador

    except Exception as erro:  # pylint: disable=broad-except
        log_callback(f"[{apelido}] ERRO FATAL: {erro}")
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:  # pylint: disable=broad-except
                pass
        log_callback(f"[{apelido}] finalizado.")


def executar(ras: list, perfis_selecionados: list, headless: bool = False,
             log_callback=print, progresso_callback=lambda registro: None,
             inicio_ra_callback=lambda apelido, ra: None,
             evento_parar: threading.Event = None, polos: dict = None) -> list:
    """
    Executa a consulta de todos os RAs, distribuindo entre os perfis
    selecionados (lista de ids inteiros, ex: [1, 3]). Se `evento_parar` for
    sinalizado, os workers terminam o RA atual e param.

    `inicio_ra_callback(apelido, ra)` é chamado assim que um RA COMEÇA a ser
    processado (antes de qualquer resultado) — usado pra mostrar "Processando"
    no dashboard.
    `progresso_callback(registro)` é chamado quando um RA TERMINA, com o
    dicionário de resultado completo — usado pra contar Sucesso/Erro.

    Retorna a lista de registros (na ordem em que foram concluídos).
    """
    if not perfis_selecionados:
        raise ValueError("Selecione ao menos um perfil para executar a automação.")

    if polos:  # base com coluna POLO: um polo de cada vez, todas as janelas juntas
        return executar_por_polo(ras, polos, perfis_selecionados, headless=headless,
                                 log_callback=log_callback, progresso_callback=progresso_callback,
                                 inicio_ra_callback=inicio_ra_callback, evento_parar=evento_parar)

    evento_parar = evento_parar or threading.Event()
    blocos = _dividir_em_blocos(ras, len(perfis_selecionados))
    # garante correspondência 1:1 entre bloco e perfil, mesmo se houver menos
    # blocos que perfis selecionados (lista de RAs menor que nº de perfis)
    pares = list(zip(perfis_selecionados, blocos))

    resultados_queue = queue.Queue()
    threads = []

    for perfil_id, bloco in pares:
        t = threading.Thread(
            target=_worker,
            args=(perfil_id, bloco, resultados_queue, log_callback,
                  progresso_callback, inicio_ra_callback, headless, evento_parar),
            daemon=True,
        )
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    resultados = []
    while not resultados_queue.empty():
        resultados.append(resultados_queue.get())

    return resultados


# ===========================================================================
# MODO AUTOMÁTICO POR POLO (base com coluna POLO)
# Um polo de cada vez: todas as janelas (perfis) trabalham JUNTAS nos RAs do
# polo atual (fila compartilhada); quando acaba o último RA daquele polo,
# passa pro próximo. Nunca alterna entre polos.
# ===========================================================================
def _consultar_com_tentativas(cliente, ra, apelido, evento_parar, log_callback):
    """consultar_ra + novas tentativas em caso de timeout (igual ao modo manual)."""
    registro = cliente.consultar_ra(ra)
    tentativa = 1
    while (_e_erro_de_timeout(registro.get("Status da Consulta", ""))
           and tentativa < MAX_TENTATIVAS_TIMEOUT and not evento_parar.is_set()):
        tentativa += 1
        log_callback(f"[{apelido}] RA {ra}: tempo esgotado — tentando de novo "
                     f"(tentativa {tentativa}/{MAX_TENTATIVAS_TIMEOUT})...")
        registro = cliente.consultar_ra(ra)
    return registro


def _worker_polo(estado, polo, fila_ras, resultados_queue, log_callback, progresso_callback,
                 inicio_ra_callback, headless, evento_parar, falhas):
    """Uma janela trabalhando no polo atual: entra no polo e puxa RAs da fila
    compartilhada até acabar."""
    perfil_id = estado["perfil_id"]
    apelido = perfis.obter_apelido(perfil_id)
    log_perfil = lambda msg: log_callback(f"[{apelido}] {msg}")  # noqa: E731
    if estado["morto"]:
        return

    def _entrar() -> bool:
        if estado["driver"] is None:
            log_perfil("abrindo navegador...")
            estado["driver"] = browser_manager.criar_driver_worker(perfil_id, headless=headless)
        ok, motivo = entrar_no_polo(estado["driver"], polo, evento_parar, log=log_perfil,
                                    tempo_login=config.TEMPO_ESPERA_ACESSO_COLABORA)
        if not ok:
            falhas.append(f"[{apelido}] {motivo}")
            log_perfil(f"não entrei no polo '{polo}': {motivo}")
            return False
        estado["cliente"] = ColaboraClient(estado["driver"], log=log_perfil)
        return True

    try:
        if not _entrar():
            return
        while not evento_parar.is_set():
            try:
                ra = fila_ras.get_nowait()
            except queue.Empty:
                break
            log_callback(f"[{apelido}] consultando RA {ra}...")
            inicio_ra_callback(apelido, ra)
            cliente = estado["cliente"]
            registro = _consultar_com_tentativas(cliente, ra, apelido, evento_parar, log_callback)
            registro["Perfil"] = apelido
            registro["Polo"] = polo
            resultados_queue.put(registro)
            progresso_callback(registro)
            log_callback(f"[{apelido}] RA {ra} -> {registro.get('Status da Consulta', '')}")

            if cliente.sessao_morta:
                estado["reinicios"] += 1
                if estado["reinicios"] > 3:
                    log_perfil("o navegador morreu várias vezes seguidas — desistindo desse perfil.")
                    estado["morto"] = True
                    break
                log_perfil(f"sessão do navegador morreu — reiniciando ({estado['reinicios']}/3)...")
                try:
                    estado["driver"].quit()
                except Exception:  # pylint: disable=broad-except
                    pass
                estado["driver"] = None
                time.sleep(1.5)
                if not _entrar():
                    estado["morto"] = True
                    break
            else:
                estado["reinicios"] = 0
    except Exception as erro:  # pylint: disable=broad-except
        log_perfil(f"ERRO: {erro}")
        falhas.append(f"[{apelido}] {erro}")


def executar_por_polo(ras: list, polos: dict, perfis_selecionados: list, headless: bool = False,
                      log_callback=print, progresso_callback=lambda registro: None,
                      inicio_ra_callback=lambda apelido, ra: None,
                      evento_parar: threading.Event = None) -> list:
    """Processa polo por polo (em ordem alfabética). Dentro de cada polo as
    janelas dividem os RAs por uma fila compartilhada. Retorna os registros."""
    evento_parar = evento_parar or threading.Event()
    resultados_queue = queue.Queue()

    def _emitir_erro(ra, polo, mensagem):
        registro = _registro_erro(ra, "", polo, mensagem)
        resultados_queue.put(registro)
        progresso_callback(registro)

    por_polo = {}
    for ra in ras:
        polo = (polos.get(str(ra).strip()) or "").strip()
        if not polo:
            log_callback(f"RA {ra}: sem polo na base — não será processado.")
            _emitir_erro(ra, "", "POLO não informado para este RA na base")
            continue
        por_polo.setdefault(polo, []).append(ra)

    ordem = sorted(por_polo, key=lambda p: p.casefold())
    log_callback(f"{len(ras)} RA(s) em {len(ordem)} polo(s). Ordem de execução: " + " | ".join(ordem))

    estados = [{"perfil_id": pid, "driver": None, "cliente": None, "reinicios": 0, "morto": False}
               for pid in perfis_selecionados]
    try:
        for indice, polo in enumerate(ordem, start=1):
            if evento_parar.is_set():
                break
            lista = por_polo[polo]
            log_callback(f"===== Rodando POLO {polo} ({len(lista)} RA(s)) — polo {indice} de {len(ordem)} =====")
            fila = queue.Queue()
            for ra in lista:
                fila.put(ra)
            falhas = []
            threads = []
            for estado in estados:
                t = threading.Thread(
                    target=_worker_polo, daemon=True,
                    args=(estado, polo, fila, resultados_queue, log_callback, progresso_callback,
                          inicio_ra_callback, headless, evento_parar, falhas))
                threads.append(t)
                t.start()
            for t in threads:
                t.join()

            # sobrou RA na fila (nenhuma janela conseguiu entrar/continuar): marca erro
            restantes = 0
            while True:
                try:
                    ra = fila.get_nowait()
                except queue.Empty:
                    break
                if evento_parar.is_set():
                    break
                restantes += 1
                motivo = falhas[0] if falhas else "nenhuma janela disponível"
                _emitir_erro(ra, polo, f"não processado no polo '{polo}': {motivo}")
            if restantes:
                log_callback(f"POLO {polo}: {restantes} RA(s) não processado(s) — veja o motivo nos erros acima.")
            log_callback(f"===== POLO {polo} concluído =====")
    finally:
        for estado in estados:
            if estado["driver"] is not None:
                try:
                    estado["driver"].quit()
                except Exception:  # pylint: disable=broad-except
                    pass

    resultados = []
    while not resultados_queue.empty():
        resultados.append(resultados_queue.get())
    return resultados
