# Captura Boleto Colaboraread

Automação que consulta alunos no **Colaboraread** (extranet Kroton/Anhanguera), lê todas as parcelas e captura a **linha digitável do boleto** de cada parcela disponível. Roda em lote a partir de uma planilha de RAs, com a mesma interface do Captura Link de Pagamento: até 3 perfis em paralelo, painel ao vivo, histórico, recuperação e "Reprocessar erros".

## Antes de executar (responsabilidade do usuário)
Em **cada janela do Chrome** que a automação abrir:
1. Faça login em https://prisma.kroton.com.br
2. Selecione o **polo** (canto superior direito)
3. **Portais → Colaborar**

A janela fica esperando (até 15 min) você chegar no Colaboraread e só então começa a processar os RAs. A escolha do polo é sempre do usuário, porque o mesmo login pode ter mais de um polo.

## Base de importação
CSV ou Excel. **RA na 1ª coluna** (com ou sem cabeçalho). **Telefone é opcional**: coluna com cabeçalho Telefone/Celular/Fone/WhatsApp (ou a 2ª coluna, se não houver cabeçalho). Quando informado, **o telefone da base sempre substitui o do Colaboraread**, no relatório e na base de disparo.

## O que a automação faz para cada RA
1. `secretaria/matricula/index.action`: busca a matrícula (nome, CPF, pendência financeira).
   `formmatricula.action` (Alterar Dados): Fone Celular e CPF/Nome do responsável, lidos em segundo plano.
2. `listparcelas.action`: lê **todas** as parcelas (vencimento, situação, valor faturado).
3. Para cada parcela com botão **Gerar boleto**, reenvia o formulário (`listboletos.action`) com a sessão do navegador, lê o PDF **em memória** e extrai a linha digitável, conferindo os dígitos verificadores. Nenhum PDF é salvo.

## Saída (pasta da execução)
**`relatorio_meses.csv/.xlsx`**: todos os códigos do aluno até Dezembro.
`RA | Nome | CPF | Telefone | Situação | <Mês> - Situacao Mensalidade | <Mês> - Valor Pago | <Mês> - Vencimento | <Mês> - Boleto Gerado` (Junho a Dezembro; período em `config.py`).

**`base_disparo.csv/.xlsx`**: arquivo enxuto para disparo, só com o **último** boleto gerado de cada aluno.
`RA | CPF | Nome | Telefone | MÊS | Vencimento | <Mês> - Boleto Gerado`. Alunos sem boleto ficam de fora.

**`resultado.csv/.xlsx`**: resumo técnico por RA (Status da Consulta), usado pelo "Reprocessar erros".

## Desenvolvimento
```
pip install -r requirements.txt
python main.py
```
Teste rápido de um RA, sem interface: `python teste_colabora.py 3771580906`.

## Estrutura
- `colaboraread_client.py`: toda a interação com o Colaboraread (substitui o `crm_client.py`)
- `runner.py`: perfis em paralelo; cada janela aguarda o acesso ao Colaborar
- `data_io.py`: leitura da base e gravação dos resultados
- `config.py`: URLs, pastas, período do relatório
- Demais arquivos (interface, perfis, histórico, recuperação, build do .exe): iguais ao Captura Link de Pagamento.

## Gerar o .exe
`build_exe.bat` (Windows), que gera `dist\CapturaBoletoColabora.exe`. Veja `LEIAME_EMPACOTAMENTO.md`.

Dados e perfis ficam em pastas próprias (`Documentos\CapturaBoletoColabora` e `%LOCALAPPDATA%\CapturaBoletoColabora`), separadas do Captura Link.

**Backup automático:** a cada RA processado o resultado é gravado em `saida\<data-hora>\backup_parcial.csv` (com flush no disco) e num log de retomada. Se o PC desligar, o CSV já tem tudo até ali e, ao reabrir, o programa oferece recuperar e gerar os arquivos finais. Em execução normal o backup é apagado ao final.

## Modo automático por polo (base com coluna POLO)

- Base: `RA` na 1ª coluna e uma coluna com cabeçalho **POLO** (texto exato da lista do Prisma, ex.: `GUARULHOS/SP - I(17111257)A`; o código, ex. `17111257`, também serve). Telefone continua opcional. Sem coluna POLO, vale o modo manual de sempre.
- O usuário faz o **login manual uma vez** (botão "Login manual"). Depois o perfil do Chrome guarda a sessão.
- Para cada polo, a janela faz: abre `prisma.kroton.com.br/login` → clica **ACESSAR** → espera `/home` → escolhe o polo na lista ("Selecione outro polo") e confirma → abre direto `extranet.colaboraread.com.br/index/index` → segue o fluxo normal. Se o login não concluir sozinho (sessão vencida/senha não salva), avisa no log e espera o login manual na janela.
- **Um polo de cada vez:** os polos são ordenados (alfabético) e o log mostra `Rodando POLO X (n RAs) — polo i de N`. Todas as janelas trabalham juntas nos RAs do polo atual (fila compartilhada) e só quando o último RA do polo termina passa para o próximo. Nunca alterna entre polos. RA sem polo na base vira erro sem travar os demais.
- Erros: RA sem polo na base, polo que não existe na lista do usuário (o log mostra os disponíveis) ou seleção não confirmada viram `Erro: ...` no `resultado` (coluna **Polo** nova) e entram no "Reprocessar erros" (que preserva a coluna POLO). Se a seleção do polo falhar, salva um print em `logs\screenshots`.
- Implementação: `colaboraread_client.entrar_no_polo`, `runner._worker` (param `polo_por_ra`), `data_io.ler_polos_base`.
- **Ainda não validado no site real** (seletores do `/login` e da `/home` vieram do HTML informado pelo usuário).
