# Captura Boleto Colaboraread: contexto do projeto

Documento de passagem de contexto: tudo o que foi decidido e construído até agora, para continuar o trabalho em outro chat.

- **Repositório:** https://github.com/SamuelDavid1436/projetopessoal-gerador-boleto-colaborar
- **Versão atual:** 0.9.0 (amostra), enviada a um usuário para teste de 3 dias.
- **Origem:** derivado do **Captura Link de Pagamento** (repo `InovaHUB-CRM/revenuehub-gerador-link-grad`), que gera links de pagamento no CRM Dynamics. Mesma estrutura, outro sistema-alvo.

## 1. O que o programa faz

RPA desktop (Python + Selenium + customtkinter) que recebe uma planilha de RAs e, para cada RA:

1. Busca a matrícula no **Colaboraread** (extranet Kroton/Anhanguera).
2. Lê **todas as parcelas** do aluno.
3. Para cada parcela com botão "Gerar boleto", gera o boleto e **extrai a linha digitável** (47 dígitos) do PDF.
4. Grava os resultados em planilhas (ver seção 5).

## 2. Regra de negócio: acesso (responsabilidade do usuário)

O usuário faz manualmente, **em cada janela do Chrome** que a automação abrir:

1. Login em `https://prisma.kroton.com.br/`. **Não use `/home`**: essa página quebra com "Cannot read properties of null (reading 'id')" quando não há login.
2. Seleciona o **polo** no canto superior direito.
3. **Portais → Colaborar**, que abre `extranet.colaboraread.com.br/index/index`.

A escolha do polo é **sempre do usuário**, porque um mesmo login pode ter vários polos. A automação nunca escolhe e **não confere** qual polo foi selecionado.

**Como o sistema sabe que pode começar** (função `aguardar_colaborar` em `colaboraread_client.py`):

- Primeiro tenta abrir direto a tela de matrícula. Se o campo `ematCd` aparece, a sessão ainda está viva e o processamento começa na hora.
- Senão, abre o Prisma e, a cada 2 s, verifica a URL de **todas as abas** procurando `extranet.colaboraread.com.br`.
- Quando acha, confirma que o campo `ematCd` apareceu e só então começa.
- O limite de espera é de 15 min (`TEMPO_ESPERA_ACESSO_COLABORA` em `config.py`). O botão Parar interrompe a espera.

## 3. Fluxo técnico no Colaboraread

**Busca da matrícula**
- URL: `https://extranet.colaboraread.com.br/secretaria/matricula/index.action`
- Campo: `<input id="ematCd" name="edmatric.ematCd">`
- Botão: `<input type="submit" value="Listar matrículas">`
- Resultado na tabela `table#lst`. Colunas da linha (índices de `td`):
  - `td[5]`: matrícula
  - `td[6]`: nome (link) e `span.sample` com a situação (ex.: "Matricula Ativa")
  - `td[7]`: data da matrícula
  - `td[8]`: CPF
  - `td[9]`: telefone
- Pendência financeira: presença de `img[src*='form_money_no']`, que resulta em "Inadimplente"; sem ela, "Adimplente".
- RA inexistente: o programa detecta o recarregamento da página (staleness do campo) e não espera o timeout inteiro.

**Parcelas**
- O botão do boleto é `javascript:boleto('RA')`. O programa pula esse passo e vai direto em `.../secretaria/matricula/listparcelas.action?edmatric.ematCd=<RA>`.
- A tabela é identificada pelo cabeçalho `th` "Parc.". Colunas:
  - Parc.
  - Vencimento
  - Valor
  - Mat. did.
  - Situação ("Recebida (PIX)", "Em Aberto", "Não Gerada"...)
  - Valor faturado
  - Dt. Receb.
  - Gerar boleto
- Uma parcela só tem boleto quando existe o form, por exemplo:

  ```html
  <form name="form033771580906" action="listboletos.action" method="post">
    <input type="hidden" name="famensed.mendNrParcela" value="03">
    <input type="hidden" name="famensed.edmatric.ematCd" value="3771580906">
  </form>
  ```

**Boleto (ponto-chave)**
- No site, o clique faz `document.formNN<RA>.submit()`, que é um **POST** para `listboletos.action` e abre o PDF numa nova aba.
- A automação **não clica e não abre aba**. Ela lê o form do HTML (action + campos hidden) e **reenvia o mesmo POST com `requests`**, usando os cookies da sessão do Selenium.
- O PDF volta **em memória**; nada é salvo em disco.
- O texto é extraído com `pdfplumber`, e uma regex acha a linha digitável.
- Os **3 dígitos verificadores (módulo 10) são validados**; se não baterem, a parcela é marcada como erro.

**Validado no site real (RA de teste `3771580906`, Marilia Lima Mendes):**
- A parcela 03 (venc. 08/09/2026, R$ 208,80) gerou `23793396059523018780902999999804415630000020880` (Bradesco 237, DVs ok).
- A parcela 04 (venc. 07/10/2026, R$ 154,20) gerou uma linha diferente, também ok.
- O RA `3772012806` também rodou: Adimplente, 1 boleto.

## 4. Base de importação

- CSV ou Excel. **RA sempre na 1ª coluna**, com ou sem cabeçalho (ignora "RA"/"Matricula"). RAs repetidos são processados de novo, como no Captura Link.
- **Telefone é opcional.** A coluna é reconhecida pelo cabeçalho Telefone/Celular/Fone/WhatsApp; sem cabeçalho, vale a 2ª coluna.
- **Se o usuário informar o telefone, ele SEMPRE substitui o telefone do Colaboraread**, no relatório e na base de disparo. A troca é feita em `app_gui._callback_progresso`, usando `data_io.ler_telefones_base`.
- O "Reprocessar erros" preserva os telefones informados na nova base.

## 5. Arquivos de saída

Os arquivos ficam em `Documentos\CapturaBoletoColabora\saida\<data-hora>\`.

**`relatorio_meses.csv/.xlsx`**: todos os códigos do aluno, até dezembro. Colunas, nesta ordem:

`RA | Nome | CPF | Telefone | Situação | <Mês> - Situacao Mensalidade | <Mês> - Valor Pago | <Mês> - Vencimento | <Mês> - Boleto Gerado`

- Os meses vão de Junho a Dezembro; o período está em `config.MES_MINIMO_RELATORIO` e `config.MES_MAXIMO_RELATORIO`.
- **Mês:** calculado pelo **vencimento** da parcela.
- **Situacao Mensalidade:** o texto do Colaboraread, ou "Sem mensalidade" quando não há parcela naquele mês.
- **Valor Pago:** o "Valor faturado", sem "R$".
- **Vencimento:** a data da tabela de parcelas do Colaboraread (dd/mm/aaaa). Foi escolhida no lugar da data calculada pelo código de barras, que pode diferir em 1 dia (ex.: parcela 03 da Marilia: 08/09 na tabela, 09/09 no código).
- **Situação:** Inadimplente / Adimplente / "RA não encontrado na base" / "Erro na consulta: ...".
- Segue o padrão do `relatorio_meses` do Captura Link, com "Boleto Gerado" no lugar de "Link Pagamento". As colunas Perfil e E-mail foram excluídas.

**`base_disparo.csv/.xlsx`**: arquivo enxuto para disparo, baseado no modelo "Base_Links_para_Disparo". Colunas, nesta ordem:

`RA | CPF | Nome | Telefone | MÊS | Vencimento | <Mês> - Boleto Gerado`

- Traz só o **último código gerado** do aluno, ou seja, a parcela com boleto de vencimento mais recente.
- Alunos sem nenhum boleto ficam de fora.
- **Telefone:** normalizado para `55 + DDD + número`, só dígitos e gravado como número. Ex.: `(11) 95249-7902` vira `5511952497902`. Sem DDD (8–9 dígitos), fica com os dígitos originais e vai falhar no disparo. **Pendente:** decidir se nesses casos o telefone fica em branco, se o aluno sai da base ou se fica como está.
- **Cabeçalho da última coluna:** usa o mês que mais aparece na base. Para quem tiver outro mês, o que vale é a coluna MÊS da linha.
- A linha digitável é gravada como **texto**, para não virar `2,38E+46`.
- A coluna E-mail do modelo foi removida, porque o Colaboraread não mostra e-mail.

**`resultado.csv/.xlsx`**: resumo técnico, uma linha por RA, com o "Status da Consulta". É usado pelo botão "Reprocessar erros".

## 6. Estrutura do código

| Arquivo | Papel |
|---|---|
| `colaboraread_client.py` | Toda a interação com o Colaboraread (substitui `crm_client.py`). Interface igual à do `CrmClient`: `consultar_ra(ra) -> dict` (nunca lança) e `sessao_morta`. Também tem `aguardar_colaborar()`. |
| `runner.py` | Distribui os RAs entre os perfis (threads). Cada janela chama `aguardar_colaborar` antes de começar; no reinício do navegador, espera de novo. |
| `data_io.py` | `ler_lista_ras`, `ler_telefones_base`, `salvar_resultado`, `salvar_relatorio_meses`, `salvar_base_disparo`, `telefone_disparo`. |
| `browser_manager.py` | Perfis do Chrome, login manual (abre o Prisma), `detectar_login` ("Logado" / "Logado no Prisma" / "Não logado") e `criar_driver`. |
| `config.py` | URLs, pastas, cores, período do relatório, colunas, versão. |
| `app_gui.py`, `paginas/` | Interface (customtkinter), igual à do Captura Link, com textos adaptados. |
| `history.py`, `recuperacao.py`, `perfis.py` | Sem mudança de lógica em relação ao Captura Link. |
| `teste_colabora.py` | Testa 1 RA sem a interface: `python teste_colabora.py <RA>`. |
| `CapturaBoletoColabora.spec`, `build_exe.bat` | Build do .exe; inclui pdfplumber, pdfminer e pypdfium2. |

Pastas próprias, separadas das do Captura Link: `Documentos\CapturaBoletoColabora` e `%LOCALAPPDATA%\CapturaBoletoColabora`.

**Identidade visual:** diferente da do Captura Link.
- Cor de marca **índigo** `#4052D6`; no tema escuro, `#7383F2`.
- Botões de ação em **coral** `#FF7A45`.
- Logo: boleto com código de barras e selo coral de "ok" (`assets/logo.png` e `icone.ico`).
- As constantes continuam se chamando `COR_VERDE` / `COR_DOURADO` em `config.py`, porque a interface inteira usa esses nomes; só os valores mudaram.

## 7. ChromeDriver (atualização do Chrome em 28/09/2026)

Depois de uma atualização do Chrome, os programas pararam de abrir o navegador.

- **Solução imediata:** fechar o Chrome, apagar `C:\Users\<usuário>\.wdm` (cache do webdriver-manager) e abrir de novo. Na 1ª vez, o Chrome pode levar de 10 a 30 s para abrir.
- **Correção no código** (aqui e no Captura Link): `browser_manager.criar_driver` tenta primeiro o **Selenium Manager** (`webdriver.Chrome(options=...)`) e usa o `webdriver-manager` só como reserva. Se os dois falharem, mostra uma mensagem clara. O `build_exe.bat` passou a rodar `pip install --upgrade selenium webdriver-manager`.

## 8. Gerar o .exe (só no Windows)

1. Copiar o `certificado_assinatura.pfx` da pasta do Captura Link para a raiz. É o mesmo certificado, então as máquinas que já confiam nele não bloqueiam o .exe. **Nunca suba o .pfx no Git.**
2. Rodar o `build_exe.bat`, que gera `dist\CapturaBoletoColabora.exe`.
3. Enviar ao usuário junto com o `GUIA_RAPIDO_AMOSTRA.txt`.

## 9. Pendências / próximos passos

- [ ] Coletar o feedback do teste de 3 dias da amostra.
- [ ] Testar 2 ou 3 perfis em paralelo no site real, para saber se o Colaboraread aceita sessões simultâneas.
- [ ] Decidir o que fazer com telefone sem DDD na base de disparo.
- [ ] Decidir se o cabeçalho da base de disparo fica "<Mês> - Boleto Gerado" ou fixo "Boleto Gerado".
- [ ] Opcional: esconder o `resultado.xlsx` da pasta do usuário, gravando-o só em logs.
- [ ] Opcional: trava de validade da amostra.
- [ ] Opcional: mostrar o polo selecionado e pedir confirmação antes de começar.
- [ ] Atualizar o manual (`assets/manual.pdf` / `manual.docx`), que ainda é o do Captura Link.
- [ ] Testar o .exe gerado. Até agora só a versão em Python foi testada, contra o site real e contra uma cópia local das páginas.
