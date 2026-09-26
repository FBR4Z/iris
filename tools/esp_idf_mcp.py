"""Inicia o servidor MCP oficial do ESP-IDF (`idf.py mcp-server`) para a Íris, no Windows.

Rode com o Python do ESP-IDF (o venv que o instalador EIM cria), que tem o pacote `mcp`:

  iris projeto mcp Estufa esp-idf -- C:\\Espressif\\tools\\python\\v6.1\\venv\\Scripts\\python.exe C:\\caminho\\tools\\esp_idf_mcp.py C:\\esp\\estufa

Sem a pasta do projeto, o agente precisa informá-la em cada chamada.

Faz duas coisas que o `idf.py mcp-server` sozinho não faz no Windows:

1. Carrega o ambiente do ESP-IDF a partir do perfil do PowerShell que o EIM gera
   (`C:\\Espressif\\tools\\Microsoft.v*.PowerShell_profile.ps1`; outro com --perfil), num
   PowerShell separado: nada dele chega à saída padrão, que é o canal do protocolo MCP.
2. Faz os subprocessos não herdarem a entrada padrão. Enquanto o servidor lê o stdin numa
   thread, um subprocess que herda esse pipe trava no Windows; o `project://status` (git),
   o build e o flash do ESP-IDF 6.1 ficavam parados para sempre.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import runpy
import subprocess
import sys

PERFIS = r"C:\Espressif\tools\Microsoft.v*.PowerShell_profile.ps1"


def erro(mensagem: str) -> None:
    print(f"esp_idf_mcp: {mensagem}", file=sys.stderr)
    sys.exit(1)


def carregar_ambiente(perfil: str) -> None:
    """Aplica em os.environ as variáveis que o perfil do ESP-IDF define."""
    script = (
        f". '{perfil}' *> $null; "
        "Get-ChildItem env: | ForEach-Object { @{ n = $_.Name; v = $_.Value } } | ConvertTo-Json -Compress"
    )
    saida = subprocess.run(
        ["powershell", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=120,
    )
    if saida.returncode != 0:
        erro(f"falha ao carregar {perfil}: {saida.stderr.decode(errors='replace')}")
    variaveis = json.loads(saida.stdout.decode("utf-8", errors="replace"))
    os.environ.clear()
    os.environ.update({item["n"]: item["v"] or "" for item in variaveis})


def subprocessos_sem_stdin() -> None:
    """Subprocessos recebem stdin=DEVNULL, salvo quando pedem outra coisa."""
    original = subprocess.Popen.__init__

    def __init__(self, *args, **kwargs):
        if len(args) < 4:  # stdin é o 4º parâmetro posicional de Popen
            kwargs.setdefault("stdin", subprocess.DEVNULL)
        original(self, *args, **kwargs)

    subprocess.Popen.__init__ = __init__


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("projeto", nargs="?", help="pasta do projeto ESP-IDF")
    parser.add_argument("--perfil", help="perfil do PowerShell gerado pelo EIM")
    args = parser.parse_args()

    perfil = args.perfil or max(glob.glob(PERFIS), default=None)
    if not perfil or not os.path.exists(perfil):
        erro("perfil do ESP-IDF não encontrado (use --perfil).")
    carregar_ambiente(perfil)
    if "IDF_PATH" not in os.environ:
        erro(f"{perfil} não definiu IDF_PATH.")

    subprocessos_sem_stdin()

    idf_py = os.path.join(os.environ["IDF_PATH"], "tools", "idf.py")
    sys.argv = [idf_py]
    if args.projeto:
        sys.argv += ["-C", os.path.abspath(args.projeto)]
    sys.argv.append("mcp-server")
    sys.path.insert(0, os.path.dirname(idf_py))
    runpy.run_path(idf_py, run_name="__main__")


if __name__ == "__main__":
    main()
