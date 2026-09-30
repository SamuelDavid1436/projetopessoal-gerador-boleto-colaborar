# Como gerar o .exe (fazer uma única vez, numa máquina Windows)

**Atalho rápido:** dê um duplo clique em `build_exe.bat` (nessa mesma pasta)
— ele faz os passos 1 a 3 abaixo sozinho, automaticamente. Se preferir fazer
manualmente (ou se o `.bat` der algum problema), siga o passo a passo:

O PyInstaller não faz build cruzado — o `.exe` precisa ser gerado NUMA MÁQUINA
WINDOWS com Python instalado. Depois de gerado, o `.exe` final roda em
qualquer Windows, sem precisar de Python nem nada disso.

## Passo a passo

1. Instale o Python (3.10 ou mais novo) nessa máquina Windows, se ainda não tiver: https://www.python.org/downloads/
   - Na instalação, marque a caixinha "Add python.exe to PATH".

2. Abra o Prompt de Comando (cmd) dentro da pasta do projeto e rode:
   ```
   pip install -r requirements.txt
   pip install pyinstaller
   pyinstaller CapturaBoletoColabora.spec
   ```

3. Espere terminar (leva alguns minutos). O executável final fica em:
   ```
   dist\CapturaBoletoColabora.exe
   ```

4. Esse arquivo `.exe` é o que você distribui pros usuários finais — copie
   ele (só ele, é um arquivo único) para qualquer máquina Windows com Chrome
   e internet. Não precisa instalar Python nelas.

## Se der algum erro no passo 2

- Confirme que está na pasta certa (onde tem o arquivo `CapturaBoletoColabora.spec`).
- Se aparecer erro faltando algum pacote, rode `pip install --upgrade pip` e tente de novo.

## Refazendo o .exe depois de qualquer alteração no código

Sempre que eu (ou outra pessoa) mudar algum arquivo `.py` do projeto, é só
repetir o passo 2 (`pyinstaller CapturaBoletoColabora.spec`) — não precisa
reinstalar nada, só gerar de novo.

## Evitando o aviso de "arquivo bloqueado" do Windows (recomendado)

Sem assinatura digital, o Windows trata o `.exe` como suspeito por padrão —
é isso que causa aquele erro de "Uma política de Controle de Aplicativo
bloqueou este arquivo" que os usuários podem ver. Pra resolver isso de vez:

1. Rode `gerar_certificado.ps1` **uma única vez** (clique direito → Executar
   com PowerShell). Ele gera dois arquivos: `certificado_assinatura.pfx`
   (fica com você, protegido por senha) e `certificado_assinatura.cer`
   (esse é o que se distribui).
2. Da próxima vez que rodar `build_exe.bat`, ele já assina o `.exe`
   automaticamente no final (usa o `.pfx` gerado no passo 1). Só vai pedir
   a senha do certificado.
3. **Antes de mandar o `.exe` pra qualquer usuário**, cada máquina precisa
   confiar no certificado uma vez. Como as máquinas de vocês são
   independentes (sem domínio/Active Directory — cada uma é administrada
   por conta própria), use o script `instalar_certificado.ps1`:
   - Copie `instalar_certificado.ps1` **e** `certificado_assinatura.cer`
     (os dois juntos, mesma pasta) pra cada máquina.
   - Rode `instalar_certificado.ps1` como Administrador (ele mesmo pede
     a elevação se precisar) — uma vez por máquina, só isso.
   - A partir daí, aquela máquina confia em qualquer `.exe` assinado com
     esse certificado, **incluindo atualizações futuras do programa** —
     não precisa repetir esse passo a cada versão nova, só na primeira vez
     em cada máquina nova.

Depois desse processo feito em cada máquina, o `.exe` (essa versão e as
próximas) abre direto, sem bloqueio, sem pedir nada pro usuário.

Se a empresa **tiver** domínio/AD no futuro, tem um guia alternativo via
GPO (cobre todas as máquinas de uma vez, sem precisar rodar nada
localmente) no arquivo `TI_LEIA_ISTO.md`.
