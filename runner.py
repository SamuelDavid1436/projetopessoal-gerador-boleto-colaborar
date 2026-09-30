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


def _dividir_contiguo(lista, n_blocos):
    """Divide em n blocos de pedaços CONSECUTIVOS (mantém RAs do mesmo polo
    juntos, pra cada janela trocar de polo o mínimo possível)."""
    n_blocos = max(1, min(n_blocos, len(lista)) or 1)
    base, resto = divmod(len(lista), n_blocos)
    blocos, inicio = [], 0
    for i in range(n_blocos):
        fim = inicio + base + (1 if i < resto else 0)
        blocos.append(lista[inicio:fim])
        inicio = fim
    return [b for b in blocos if b]


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
            progresso_callback, inicio_ra_callback, headless, evento_parar: threading.Event,
            polo_por_ra=None):
    apelido = perfis.obter_apelido(perfil_id)
    auto = bool(polo_por_ra)   # base com coluna POLO: entra sozinho no polo de cada RA
    polo_atual = None
    polos_falhos = {}
    driver = None
    MAX_REINICIOS_SEGUIDOS = 3
    reinicios_seguidos = 0
    try:
        log_callback(f"[{apelido}] abrindo navegador...")
        driver = browser_manager.criar_driver_worker(perfil_id, headless=headless)
        log_perfil = lambda msg: log_callback(f"[{apelido}] {msg}")  # noqa: E731
        if not auto and not aguardar_colaborar(driver, evento_parar, log=log_perfil,
                                               tempo_limite=config.TEMPO_ESPERA_ACESSO_COLABORA):
            log_callback(f"[{apelido}] não entrou no Colaboraread — esse perfil não vai processar RAs.")
            return

        cliente = ColaboraClient(driver, log=log_perfil)

        def _finalizar_registro(registro_final):
            registro_final["Perfil"] = apelido
            resultados_queue.put(registro_final)
            progresso_callback(registro_final)
            log_callback(f"[{apelido}] RA {registro_final.get('RA')} -> {registro_final.get('Status da Consulta', '')}")

        for ra in ras_do_perfil:
            if evento_parar.is_set():
                log_callback(f"[{apelido}] interrompido pelo usuário.")
                break

            polo = ""
            if auto:
                polo = (polo_por_ra.get(str(ra).strip()) or "").strip()
                inicio_ra_callback(apelido, ra)
                if not polo:
                    _finalizar_registro(_registro_erro(ra, apelido, "", "POLO não informado para este RA na base"))
                    continue
                if polo in polos_falhos:
                    _finalizar_registro(_registro_erro(ra, apelido, polo, polos_falhos[polo]))
                    continue
                if polo != polo_atual:
                    ok, motivo = entrar_no_polo(driver, polo, evento_parar, log=log_perfil,
                                                tempo_login=config.TEMPO_ESPERA_ACESSO_COLABORA)
                    if not ok:
                        if evento_parar.is_set():
                            break
                        log_callback(f"[{apelido}] não entrei no polo '{polo}': {motivo}")
                        polos_falhos[polo] = f"não entrou no polo '{polo}': {motivo}"
                        _finalizar_registro(_registro_erro(ra, apelido, polo, polos_falhos[polo]))
                        continue
                    polo_atual = polo

            log_callback(f"[{apelido}] consultando RA {ra}...")
            inicio_ra_callback(apelido, ra)  # avisa que esse RA começou (pro dashboard)

            registro = cliente.consultar_ra(ra)
            registro["Polo"] = polo

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
                    polo_atual = None  # no modo automático, o próximo RA entra no polo de novo
                    if not auto and not aguardar_colaborar(driver, evento_parar, log=log_perfil,
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

    evento_parar = evento_parar or threading.Event()
    if polos:  # modo automático: agrupa por polo e divide em pedaços consecutivos
        ras_ordenadas = sorted(ras, key=lambda r: (polos.get(str(r).strip()) or ""))
        blocos = _dividir_contiguo(ras_ordenadas, len(perfis_selecionados))
    else:
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
                  progresso_callback, inicio_ra_callback, headless, evento_parar, polos),
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
