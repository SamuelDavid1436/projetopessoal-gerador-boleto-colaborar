# Para o TI — liberar o Captura Boleto Colaboraread

> **Sem domínio/Active Directory?** Se as máquinas são administradas cada
> uma por conta própria (não fazem parte de um domínio), pule direto pro
> script `instalar_certificado.ps1` (mencionado no `LEIAME_EMPACOTAMENTO.md`)
> — ele faz o equivalente ao passo 1 abaixo, mas direto em cada máquina,
> sem precisar de GPO. O passo 2 (Controle de Aplicativo) ainda vale
> conferir mesmo sem domínio — o Windows 11 tem uma versão local dessa
> proteção (Smart App Control / App & browser control) que também pode
> bloquear, independente de domínio.

O programa vem assinado com um **certificado de código próprio da empresa**
(não é um certificado público pago tipo DigiCert — foi gerado internamente,
só pra uso dentro da própria empresa). Por isso, o Windows não confia nele
automaticamente até vocês fazerem uma liberação — mas essa liberação é
**única**: depois de feita, todo `.exe` novo assinado com esse mesmo
certificado passa direto em qualquer máquina do domínio, sem pedir nada de
novo pro usuário nem pra vocês.

Anexo a este guia (ou junto com o programa) vocês devem ter recebido o
arquivo **`certificado_assinatura.cer`**. Esse arquivo é público — não dá
pra assinar nada com ele, só serve pra Windows confiar em quem já foi
assinado com o `.pfx` correspondente (que fica só com quem gera os builds).

## O que precisa ser feito (duas frentes)

### 1. Confiar no certificado (Trusted Publisher)

Isso resolve o aviso de "arquivo bloqueado" / SmartScreen na maioria dos casos.

**Se as máquinas são de domínio (Active Directory), via GPO — recomendado, cobre tudo de uma vez:**

1. Abra o **Gerenciamento de Política de Grupo** (`gpmc.msc`).
2. Edite (ou crie) uma GPO aplicada às máquinas relevantes.
3. Vá em: `Configuração do Computador` → `Políticas` → `Configurações do Windows` → `Configurações de Segurança` → `Políticas de Chave Pública`.
4. Clique com botão direito em **"Editores Confiáveis" (Trusted Publishers)** → `Importar` → selecione o `certificado_assinatura.cer`.
5. Repita o mesmo em **"Autoridades de Certificação Raiz Confiáveis"** (Trusted Root Certification Authorities) — como é um certificado autoassinado (sem uma CA pública por trás), colocar nos dois locais evita avisos residuais.
6. Aguarde a próxima atualização de política (`gpupdate /force` nas máquinas, se quiser aplicar na hora).

**Se for só uma máquina avulsa (sem domínio):**

1. Dê dois cliques no `certificado_assinatura.cer`.
2. `Instalar Certificado` → `Máquina Local` → `Avançar`.
3. Escolha `Colocar todos os certificados no repositório a seguir` → `Procurar` → **Editores Confiáveis**.
4. `Avançar` → `Concluir`.
5. Repita selecionando **Autoridades de Certificação Raiz Confiáveis** no passo 3.

### 2. Conferir se existe uma política de Controle de Aplicativo (WDAC / AppLocker)

O erro que o usuário recebeu (imagem anexa, se aplicável) menciona
especificamente **"uma política de Controle de Aplicativo bloqueou este
arquivo"** — isso é diferente do SmartScreen/Mark-of-the-Web comum. Se a
empresa usa **AppLocker** ou **Windows Defender Application Control
(WDAC)**, confiar no certificado (passo 1) pode não ser suficiente sozinho:
essas políticas têm suas próprias regras de permissão, separadas.

Se for esse o caso:

- **AppLocker**: `gpmc.msc` → GPO relevante → `Configuração do Computador` → `Políticas` → `Configurações do Windows` → `Configurações de Segurança` → `Políticas de Controle de Aplicativo` → `AppLocker` → `Regras Executáveis` → criar uma regra nova baseada em **"Editor"** (Publisher), apontando pro certificado da empresa. Isso cobre automaticamente qualquer `.exe` futuro assinado com o mesmo certificado, sem precisar recriar a regra a cada versão nova do programa.
- **WDAC**: adicionar uma regra de exceção por **assinatura/editor** (não por hash de arquivo — hash muda a cada build novo, assinatura não) referenciando o mesmo certificado.

**Resumo pra quem só quer saber "o que fazer"**: importar o `.cer` como
Editor Confiável (passo 1) resolve o bloqueio do próprio Windows. Se a
empresa também usa AppLocker/WDAC, precisa **adicionalmente** de uma regra
de exceção por editor nessa política — pergunte pro time responsável por
essas políticas se elas estão ativas antes de descartar esse passo.

## Perguntas

Qualquer dúvida, o contato de suporte está na aba "Suporte" dentro do
próprio programa.
