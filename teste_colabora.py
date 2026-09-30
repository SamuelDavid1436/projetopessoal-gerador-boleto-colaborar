"""
Teste rápido de 1 RA, sem interface.
    python teste_colabora.py 3771580906
"""
import sys
import threading
from pprint import pprint

import browser_manager
from colaboraread_client import ColaboraClient, aguardar_colaborar

RA = sys.argv[1] if len(sys.argv) > 1 else "3771580906"

driver = browser_manager.criar_driver_worker(1)  # usa o Perfil 1 do programa
try:
    if aguardar_colaborar(driver, threading.Event(), log=print):
        r = ColaboraClient(driver).consultar_ra(RA)
        parcelas = r.pop("_parcelas_relatorio")
        pprint(r)
        for p in parcelas:
            pprint(p)
finally:
    input("\nENTER para fechar o navegador... ")
    driver.quit()
