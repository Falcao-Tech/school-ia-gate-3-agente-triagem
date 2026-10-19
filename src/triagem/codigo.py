"""Ferramentas do agente para investigar o código num clone local do repositório."""

import re
from pathlib import Path

from langchain_core.tools import BaseTool, tool

IGNORED_DIRS = {".git", "node_modules", "dist", "build", ".venv", "venv", "__pycache__", ".next", "coverage"}
MAX_FILE_BYTES = 1_000_000
MAX_HITS = 20
MAX_LINES = 200


class ForaDoRepositorio(ValueError):
    """Caminho que escapa da pasta do repositório (ex.: ../../etc/passwd)."""


def resolver_caminho(repo: Path, caminho: str) -> Path:
    """Caminho absoluto dentro do repositório. Qualquer coisa fora dele é recusada.

    O caminho vem do modelo, então trate como entrada não confiável: "../fora.txt",
    "/etc/passwd" e "app/../../fora.txt" devem levantar ForaDoRepositorio com a mensagem
    "Caminho fora do repositório: <caminho>". Dica: Path.resolve() e Path.parents.
    """
    # TODO: implemente.
    raise NotImplementedError("resolver_caminho")


def arquivos_de_texto(repo: Path):
    for path in sorted(repo.rglob("*")):
        if any(part in IGNORED_DIRS for part in path.relative_to(repo).parts):
            continue
        if path.is_file() and path.stat().st_size <= MAX_FILE_BYTES:
            yield path


def buscar_codigo(repo: Path, termo: str) -> str:
    """Linhas que contêm o termo (sem diferenciar maiúscula), no formato caminho:linha: texto."""
    if not termo.strip():
        return "Informe um termo para buscar."
    padrao = re.compile(re.escape(termo.strip()), re.IGNORECASE)
    hits: list[str] = []
    for path in arquivos_de_texto(repo):
        try:
            linhas = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue  # binário
        for numero, linha in enumerate(linhas, start=1):
            if padrao.search(linha):
                hits.append(f"{path.relative_to(repo).as_posix()}:{numero}: {linha.strip()[:200]}")
                if len(hits) >= MAX_HITS:
                    return "\n".join(hits) + f"\n(parei em {MAX_HITS} resultados; refine o termo)"
    return "\n".join(hits) or f"Nada encontrado para '{termo}'."


def ler_arquivo(repo: Path, caminho: str, inicio: int = 1, fim: int | None = None) -> str:
    """Trecho de um arquivo com as linhas numeradas, no máximo MAX_LINES linhas."""
    try:
        alvo = resolver_caminho(repo, caminho)
    except ForaDoRepositorio as erro:
        return str(erro)
    if not alvo.is_file():
        return f"Arquivo não encontrado: {caminho}"
    linhas = alvo.read_text(encoding="utf-8", errors="replace").splitlines()
    inicio = max(inicio, 1)
    fim = min(fim or inicio + MAX_LINES - 1, inicio + MAX_LINES - 1, len(linhas))
    corpo = "\n".join(f"{n:>5}  {linhas[n - 1]}" for n in range(inicio, fim + 1))
    return f"{caminho} (linhas {inicio}-{fim} de {len(linhas)})\n{corpo}"


def criar_ferramentas(repo: Path) -> list[BaseTool]:
    """As ferramentas que o modelo pode chamar, presas ao repositório informado."""

    @tool("buscar_codigo")
    def _buscar(termo: str) -> str:
        """Busca um termo (nome de função, mensagem de erro, rota...) no código do repositório."""
        return buscar_codigo(repo, termo)

    @tool("ler_arquivo")
    def _ler(caminho: str, inicio: int = 1, fim: int | None = None) -> str:
        """Lê um arquivo do repositório (caminho relativo), opcionalmente só um intervalo de linhas."""
        return ler_arquivo(repo, caminho, inicio, fim)

    return [_buscar, _ler]
