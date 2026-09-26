# ◉ Íris

**Claude, Codex e Gemini numa interface só, no seu terminal — com um círculo animado estilo Jarvis e voz 100% local.**

A Íris é um fork do [Toad](https://github.com/batrachianai/toad), de Will McGugan, adaptado para Windows, traduzido para português e com identidade visual própria. Ela não é um modelo nem um agente: é a casca que abre os CLIs oficiais (`claude`, `codex`, `gemini`) pelo protocolo [ACP](https://agentclientprotocol.com). Por isso **usa as suas assinaturas e logins normais, sem API key**.

```
┌─ Íris ─────────────────┐┌─────────────────────────────────────────────┐
│       ⣀⠤⠖⠒⠒⠒⠒⠒⠤⣀       ││ você: por que o get_user retorna nulo?       │
│     ⡠⠚⠁  ⠰⠒⠒⠂  ⠈⠑⢄     ││                                             │
│    ⡜⠁⢀⠆        ⠲⡀⠈⢣    ││ claude: O problema está em main.py:42 ...    │
│   ⢸  ⠏   ⢀⣤⣤⣄   ⠹ ⠈⡇   ││                                             │
│   ⢸      ⣿⣿⣿⣿⡇     ⡧   ││                                             │
│   ⢸  ⣄   ⠙⠿⠿⠟⠁  ⣰ ⢀⡇   ││                                             │
│    ⢣⡀⠈⠦        ⠐⠁⢀⡜    ││                                             │
│     ⠑⢤⡀  ⠠⠤⠤⠖  ⢀⡠⠊     ││                                             │
│       ⠉⠒⠦⠤⠤⠤⠤⠤⠒⠉       ││                                             │
│  PLANEJAMENTO · pronto  │├─────────────────────────────────────────────┤
├─ Projeto ──────────────┤│ > Como posso ajudar hoje?                    │
│ ▾ src                  │└─────────────────────────────────────────────┘
└────────────────────────┘ F9 Falar  ^O Modos  ^B Barra lateral  ^H Início
```

## O que ela tem

- **Três agentes, um lugar** — Claude Code, Codex CLI e Gemini CLI, cada um numa aba de sessão.
- **Círculo animado** que mostra o estado do agente:
  - anel externo **azul** no planejamento e **laranja** na execução (a borda do prompt e da barra lateral acompanham);
  - anel interno na **cor do agente** (Claude terracota, Codex verde, Gemini azul-violeta);
  - respira parado, gira rápido trabalhando, pulsa **amarelo** pedindo permissão e **vermelho** em erro;
  - solta uma **onda** ao concluir um turno e "liga" com animação ao abrir.
- **Voz local e independente do modelo** (opcional) — avisos falados, ditado com F9 e leitura de respostas. Nada sai da sua máquina.
- **Árvore de arquivos** da pasta atual, **plano** do agente e **histórico de sessões**.
- **Tema Íris** (azul-marinho, ciano e laranja), interface em **português** e coleta de dados **desligada**.
- **Windows nativo** (o Toad original só roda em Linux/macOS).

## Instalação (Windows)

### Instalador automático (recomendado)

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/FBR4Z/iris/main/instalar-iris.ps1)))
```

Ou, com o repositório clonado: `powershell -ExecutionPolicy Bypass -File .\instalar-iris.ps1`.

Ele instala o que faltar (uv, Node.js, git), a Íris, os agentes que você escolher e a voz, **detectando GPU e memória** para escolher a versão certa: com GPU NVIDIA usa Kokoro + Whisper turbo; sem GPU instala uma versão leve (Piper + Whisper small, ~3 GB a menos). Parâmetros: `-Agentes claude,codex,gemini`, `-Voz avisos|ditado|ditado_avisos|completa|desligada|pular`, `-Simular` (mostra o que faria, sem instalar). Feche a Íris antes de rodar.

### Manual

Pré-requisitos: [uv](https://docs.astral.sh/uv/) e [Node.js](https://nodejs.org).

```powershell
# 1. uv (se ainda não tiver)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 2. Íris
git clone https://github.com/FBR4Z/iris.git
cd iris
uv tool install --editable .
uv tool update-shell        # coloca o comando `iris` no PATH (reabra o terminal)
```

### Agentes

Instale e faça login nos que você usa:

| Agente | Instalar | Adaptador ACP |
|---|---|---|
| Claude Code | `irm https://claude.ai/install.ps1 \| iex` e rode `claude` uma vez para logar | `npm install -g @agentclientprotocol/claude-agent-acp` |
| Codex CLI | `npm install -g @openai/codex` e rode `codex` para logar | usa `npx @zed-industries/codex-acp` (automático) |
| Gemini CLI | `npm install -g @google/gemini-cli` e rode `gemini` para logar | embutido (`gemini --acp`) |

> O Gemini CLI para contas pessoais (free, AI Pro, Ultra) foi aposentado pelo Google em 18/06/2026. Continua funcionando com licenças **Gemini Code Assist Standard/Enterprise**, Google Cloud / Vertex AI ou API key paga.

### Voz (opcional)

A voz roda num serviço separado, `iris-voz` (Python 3.13, por causa das bibliotecas de GPU):

```powershell
uv tool install --editable voz --python 3.13 --excludes voz/excludes-gpu.txt
```

Na primeira execução ela baixa os modelos (~0,4 GB de voz em `%LOCALAPPDATA%\iris-voz\models`, mais o Whisper, ~1,6 GB). Depois ative em **Configurações → Voz**.

## Uso

```powershell
cd C:\caminho\do\projeto
iris                                  # tela inicial: escolha o agente (1, 2, 3)
iris acp "claude-agent-acp"           # abre direto no Claude
iris acp "gemini --acp"               # abre direto no Gemini
```

A pasta onde você abre a Íris é o projeto que o agente enxerga.

### Atalhos

| Tecla | Ação |
|---|---|
| **F9** | Falar (ditado) / cancelar |
| **Ctrl+O** | Trocar o modo do agente (ex.: planejamento) |
| **Ctrl+B** | Barra lateral |
| **Ctrl+H** | Início (abrir outro agente em nova aba) |
| **Ctrl+[ / Ctrl+]** | Sessão anterior / próxima |
| **Ctrl+S** | Lista de sessões |
| **F1** | Ajuda |
| **Ctrl+Q** | Sair |

### Comandos

| Comando | Ação |
|---|---|
| `/fechar` | Fecha a sessão atual |
| `/sair` | Sai da Íris |
| `/toad:rename <nome>` | Renomeia a sessão |
| `/toad:session-new` | Nova sessão na mesma pasta |

### Shell embutido

Comece a linha com `!` (ou digite um comando conhecido, como `git`) para rodá-la num PowerShell dentro da Íris, sem sair da conversa: `!git status`, `!npm test`, `!cd src`. A saída aparece num terminal ao vivo na conversa, o `cd` muda a pasta do projeto e **Ctrl+C** interrompe o comando em andamento.

No Windows ele roda num pseudo-terminal (ConPTY, via [pywinpty](https://github.com/andfoy/pywinpty)). O padrão é `powershell.exe -NoLogo`; em *Configurações → Shell settings → Shell command* dá para trocar por `pwsh`, `cmd.exe` ou o `bash.exe` do Git.

### Uso da assinatura

Com o Claude, embaixo do círculo aparece quanto dos limites da assinatura você já usou:

```
5h 17% ↻14:00 · semana 9%
```

`5h` é a janela de 5 horas (com o horário em que ela zera) e `semana` é o limite semanal. O texto fica amarelo a partir de 70% e vermelho a partir de 90%; quando o limite estoura, aparece **limite atingido** e o horário da volta. Com a voz em modo de avisos, a Íris avisa uma vez ao passar de 80% e de 95%. Os números vêm do próprio Claude Code a cada resposta; Codex e Gemini ainda não informam isso. Para esconder, desmarque *Configurações → Íris → Mostrar uso da assinatura*.

## Voz

Em **Configurações → Voz → Modo**:

| Modo | Avisos | Ditado (F9) | Lê respostas | Peso |
|---|:-:|:-:|:-:|---|
| Desligada | – | – | – | nenhum |
| Só avisos | ✅ | – | – | leve (frases em cache) |
| Só ditado | – | ✅ | – | Whisper |
| Ditado + avisos | ✅ | ✅ | – | ambos |
| Completa | ✅ | ✅ | ✅ | ambos |

**Avisos** são frases curtas em momentos definidos, editáveis em *Frases por evento* (`evento = frase`, vazio silencia):

| Evento | Quando | Padrão |
|---|---|---|
| `saudacao` | ao abrir | "Bom dia, {nome}." |
| `conectado` / `falha` | agente conectou / falhou | "{agente} conectado." |
| `modo_planejamento` / `modo_execucao` | troca de modo | "Modo de planejamento." |
| `executando` | agente roda um comando | "Executando PowerShell." (git, npm, Python, dotnet…) |
| `editando` / `apagando` / `movendo` | agente mexe num arquivo | "Editando main.py." |
| `web` | agente acessa a internet | "Acessando a web." |
| `permissao` | agente pede permissão | "Preciso da sua permissão." |
| `concluido` | terminou (após N segundos) | "Pronto. Terminei em 1 minuto." |
| `erro` / `tchau` | recusa ou limite / ao sair | "Algo deu errado." / "Até logo." |
| `limite` | uso da assinatura passou de 80% / 95% | "Você já usou 80 por cento do limite de cinco horas." |
| `limite_atingido` | limite da assinatura estourou | "Limite de uso atingido." |
| `trabalhando`, `lendo`, `pesquisando`, `plano` | — | silenciados por padrão |

### Comandos de voz

Nos modos com ditado, aperte **F9** e comece a frase com **"Íris"** — em vez de ir para o agente, o comando é executado pela própria Íris (funciona igual com Claude, Codex ou Gemini, e também na tela inicial):

| Diga | Faz |
|---|---|
| "Íris, modo planejamento" / "vamos planejar" | entra no modo de planejamento do agente |
| "Íris, modo execução" / "sai do planejamento" | volta ao modo normal |
| "Íris, abre o Claude / o Codex / o Gemini" | abre o agente numa nova aba |
| "Íris, nova sessão" · "próxima sessão" · "sessão anterior" · "fechar sessão" | sessões |
| "Íris, pode mandar" / "envia" | envia o texto ditado |
| "Íris, apaga o texto" | limpa o campo de digitação |
| "Íris, para" / "cancela" | interrompe o agente |
| "Íris, silêncio" / "para de falar" | cala a leitura em andamento |
| "Íris, repete" | repete a última fala |
| "Íris, que horas são?" · "status" · "ajuda" · "sair" | — |

Sem o "Íris" no começo, é ditado normal. Se ela não reconhecer o comando, o texto vai para o campo de digitação (nada se perde). Desative em *Voz → Comandos de voz*.

**Motores:** fala com [Kokoro](https://github.com/thewh1teagle/kokoro-onnx) (natural, ideal com GPU; vozes Dora, Alex, Santa) ou [Piper](https://github.com/OHF-Voice/piper1-gpl) (leve, processador); escuta com [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (`large-v3-turbo` na GPU, `small` no processador). O modo *Automático* escolhe conforme a máquina.

Medido num notebook com RTX 3050 6 GB: transcrição de 7 s de fala em ~0,8 s; geração de fala ~7× mais rápida que o tempo real.

## Configurações próprias da Íris

Além das do Toad, em **Configurações**:

- **Íris** — cores de planejamento, execução, atenção e erro; cores por agente; palavras que identificam modos de planejamento; mostrar ou não o uso da assinatura; agentes mostrados na tela inicial.
- **Voz** — modo, seu nome, frases por evento, motor, voz, velocidade, modelo do ditado, só CPU, envio automático do ditado.

O arquivo fica em `%USERPROFILE%\.config\toad\toad.json`.

## Como funciona

```
 você ──▶ Íris (Textual, Python 3.14)
            │  ACP (JSON-RPC via stdin/stdout)
            ├──▶ claude-agent-acp ──▶ Claude Code ──▶ sua assinatura Claude
            ├──▶ codex-acp ─────────▶ Codex CLI ────▶ sua assinatura ChatGPT
            ├──▶ gemini --acp ──────▶ Gemini CLI ───▶ sua licença Google
            │
            └──▶ iris-voz (Python 3.13, processo separado)
                   ├─ Kokoro / Piper  (texto → voz)
                   └─ faster-whisper  (voz → texto)
```

Arquivos principais do fork:

| Arquivo | O quê |
|---|---|
| `src/toad/widgets/iris_orb.py` | o círculo |
| `src/toad/iris_voice.py` | cliente da voz, mapa de eventos, resumo falado |
| `src/toad/iris_usage.py` | limites da assinatura (5 h / semana) embaixo do círculo |
| `src/toad/shell.py` | shell embutido (pty no Linux/macOS, ConPTY no Windows) |
| `src/toad/iris_theme.py` | tema |
| `src/toad/iris_i18n.py` | tradução do rodapé |
| `src/toad/iris_crash.py` | registro de falhas |
| `voz/src/iris_voz/server.py` | serviço de voz |
| `tools/fake_agent.py` | agente ACP falso para testes (não gasta cota) |

## Testes

```powershell
uv run pytest
```

São ~90 testes (funções da voz, círculo, bordas, tela inicial, tradução, sessões, avisos falados, uso da assinatura, shell embutido) que rodam a Íris sem tela, com o agente falso — não gastam cota nem tocam nas suas configurações. Rodam também no GitHub Actions (Windows e Linux) a cada envio. Vale rodar depois de puxar atualizações do Toad.

## Solução de problemas

- **A Íris fechou sozinha** — veja `%USERPROFILE%\.local\state\toad\crash.log`.
- **A voz não inicia** — veja `%USERPROFILE%\.local\state\toad\iris-voz.log`; teste com `iris-voz check`.
- **Logs dos agentes** — `%USERPROFILE%\.local\state\toad\logs\`.
- **Testar sem gastar cota** — `iris acp "python tools/fake_agent.py"`.

### Limitações conhecidas no Windows

- Comandos executados pelo agente não aparecem num terminal ao vivo dentro da Íris.
- Os botões de instalar agentes na tela inicial usam comandos Unix; instale pelo terminal (tabela acima).

## Atualizando a partir do Toad

```powershell
git remote add upstream https://github.com/batrachianai/toad.git   # uma vez
git fetch upstream
git merge upstream/main
```

As mudanças da Íris ficam concentradas em arquivos `iris_*` e em poucos pontos do código original, para facilitar esses merges.

## Licença e créditos

A Íris é um trabalho derivado do [Toad](https://github.com/batrachianai/toad), © Will McGugan, distribuído sob a **GNU Affero General Public License v3.0** — veja [LICENSE](LICENSE). As modificações da Íris seguem a mesma licença. O README original do Toad está em [docs/README-toad.md](docs/README-toad.md).

Modelos de voz: Kokoro (Apache-2.0), Piper voice *faber* pt-BR, Whisper (MIT) — cada um sob sua própria licença.
