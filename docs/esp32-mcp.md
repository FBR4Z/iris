# ESP32 com a Íris: servidores MCP para Thonny e ESP-IDF

Avaliação dos servidores MCP para o fluxo ESP32 (MicroPython no Thonny, FreeRTOS/ESP-IDF no
VS Code) e de como ligá-los à Íris. Conferido em 26/09/2026.

## Como a Íris usa MCP

Os servidores MCP ficam no **projeto da Íris** (`iris projeto mcp ...`). Toda sessão aberta
numa pasta do projeto os recebe no `session/new` do ACP, com Claude, Codex ou Gemini, sem
configurar cada agente separadamente. Servidores `stdio` funcionam com todos; os `http` só com
agentes que declaram suporte (Claude e Gemini declaram; os outros são pulados e anotados no log).

```powershell
iris projeto novo Estufa C:\esp\estufa -d "Controle da estufa com ESP32-S3" -a claude
iris projeto adicionar Estufa C:\docs\estufa\pinagem.md
iris projeto mcp Estufa esp-idf -- eim run "idf.py mcp-server"
iris projeto mcp Estufa espressif-docs https://mcp.espressif.com/docs
iris projeto abrir Estufa
```

## Avaliação

| # | Servidor | Faz | Avaliação |
|---|---|---|---|
| 1 | [AstroQuestStudio/thonny-ai](https://github.com/AstroQuestStudio/thonny-ai) | plugin do Thonny + MCP: roda código no board, loops longos, arquivos e sincronização, visível no shell do Thonny | **Usar para MicroPython.** Resolve o conflito da porta serial: o agente fala HTTP com o plugin (`127.0.0.1:47821`, `THONNY_AI_PORT`), que reaproveita a conexão do Thonny. |
| 2 | fatihcvs/thonny-ai | fork do 1 | Dispensável; instalar do original. |
| 3 | ESP-IDF Tools MCP (oficial, `idf.py mcp-server`) | `set_target`, `build_project`, `flash_project`, `clean_project`; recursos `project://status`, `config`, `devices` | **Usar para ESP-IDF.** Oficial, já vem com o ESP-IDF v6.0+ (EIM v0.8.1+ com a feature `mcp`). Não tem monitor. |
| 4 | Espressif Documentation MCP (oficial, http) | documentação e API do ESP-IDF | **Usar**, complementa o 3. Remoto, então precisa de internet liberada na rede da fábrica. |
| 5 | [Maty403/esp-idf-mcp](https://github.com/Maty403/esp-idf-mcp) | build → flash → **monitor** → pytest-embedded | **Usar como complemento do 3 para o monitor.** Ao contrário do levantamento original, hoje ele tem sessões de monitor persistentes (`monitor_open`/`monitor_read`/`monitor_send`/`monitor_close`), filtro de log, histórico em `.esp_monitor_full.log` e foi feito no Windows (com contorno para o `usbser.sys`). |
| 6 | AIRcableLLC/esp-workspace-mcp | build/flash via EIM + arquivos + shell arbitrário com jobs, token Bearer | **Não usar com a Íris.** Os agentes já leem, escrevem e rodam comandos (com o pedido de permissão da Íris); um shell arbitrário via MCP contornaria esse controle. |
| 7 | horw/esp-mcp | build, set-target, flash (PoC) | Só referência; 3 e 5 cobrem o mesmo com mais qualidade. |

## Recomendação

- **FreeRTOS/ESP-IDF:** 3 (build/flash oficial) + 4 (documentação). Para o agente ver o log da
  placa, acrescente o 5 e use o monitor dele **em vez** do `idf.py monitor`: os dois não podem
  abrir a mesma porta COM ao mesmo tempo. Se preferir ver o monitor você mesmo, rode
  `!idf.py monitor` no shell embutido da Íris (ConPTY, ao vivo) e deixe o 5 de fora.
- **MicroPython:** 1, com o Thonny aberto e o plugin conectado.
- Não misture no mesmo projeto um servidor que abre a porta serial (5) com o Thonny conectado
  à mesma placa.

```powershell
# ESP-IDF (monitor pelo 5)
iris projeto mcp Estufa esp-idf -- eim run "idf.py mcp-server"
iris projeto mcp Estufa espressif-docs https://mcp.espressif.com/docs
iris projeto mcp Estufa esp-monitor -- python C:\ferramentas\esp-idf-mcp\esp_idf_mcp.py

# MicroPython (use o Python do Thonny)
iris projeto mcp Horta thonny -- "C:\Program Files (x86)\Thonny\python.exe" -m thonny_ai_mcp
```

O servidor ativo aparece no contexto que a Íris manda ao agente no primeiro pedido
("Servidores MCP ligados a esta sessão: ...").
