"""Quem deveria olhar o bug: decidido pelo histórico do git, não pelo modelo."""

import subprocess  # noqa: F401 -- você vai precisar para rodar o git log
from collections import Counter  # noqa: F401
from pathlib import Path

COMMITS = 50


def eh_bot(autor: str) -> bool:
    return autor.endswith("[bot]") or autor.lower().endswith("-bot")


def sugerir_responsavel(repo: Path, arquivos: list[str]) -> str | None:
    """Autor (nome) com mais commits recentes nos arquivos, ignorando bots. None se não houver histórico.

    Contrato (ver tests/test_proposta.py):
    - Olhe os últimos COMMITS commits (sem merges) que tocaram os arquivos:
      git -C <repo> log -n50 --no-merges --format=%an -- <arquivos...>
    - Ignore bots (eh_bot). Sem arquivo, sem histórico ou erro do git: None.
    - Empate: quem mexeu por último (o git log vem do mais recente para o mais antigo).
    """
    # TODO: implemente.
    raise NotImplementedError("sugerir_responsavel")
