import subprocess
from pathlib import Path

import pytest


def git(repo: Path, *args: str, autor: str = "Ana Dev") -> None:
    email = autor.lower().replace(" ", ".") + "@exemplo.com"
    subprocess.run(
        ["git", "-C", str(repo), "-c", f"user.name={autor}", "-c", f"user.email={email}", *args],
        check=True,
        capture_output=True,
    )


def commit(repo: Path, arquivo: str, conteudo: str, autor: str) -> None:
    caminho = repo / arquivo
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(conteudo, encoding="utf-8")
    git(repo, "add", arquivo, autor=autor)
    git(repo, "commit", "-m", f"altera {arquivo}", autor=autor)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Repositório git de mentira com uma API de pedidos e histórico de dois autores."""
    raiz = tmp_path / "api"
    raiz.mkdir()
    git(raiz, "init", "-q", "-b", "main")
    commit(raiz, "app/pedidos.py", "def salvar_pedido(itens):\n    total = sum(i.preco for i in itens)\n    return total\n", "Ana Dev")
    commit(raiz, "app/pedidos.py", "def salvar_pedido(itens):\n    if not itens:\n        raise ValueError('pedido sem itens')\n    return sum(i.preco for i in itens)\n", "Ana Dev")
    commit(raiz, "app/clientes.py", "def buscar_cliente(id):\n    return None\n", "Bruno Back")
    commit(raiz, "README.md", "# API\n\nServiço de pedidos.\n", "Bruno Back")
    (raiz / "node_modules" / "lib").mkdir(parents=True)
    (raiz / "node_modules" / "lib" / "x.js").write_text("salvar_pedido()", encoding="utf-8")
    return raiz
