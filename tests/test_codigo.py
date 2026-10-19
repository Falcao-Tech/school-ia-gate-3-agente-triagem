from pathlib import Path

import pytest

from triagem.codigo import ForaDoRepositorio, buscar_codigo, criar_ferramentas, ler_arquivo, resolver_caminho


def test_busca_acha_linha_com_caminho_e_numero(repo: Path):
    resultado = buscar_codigo(repo, "pedido sem itens")

    assert resultado == "app/pedidos.py:3: raise ValueError('pedido sem itens')"


def test_busca_ignora_maiuscula_e_pastas_de_dependencia(repo: Path):
    resultado = buscar_codigo(repo, "SALVAR_PEDIDO")

    assert "app/pedidos.py:1:" in resultado
    assert "node_modules" not in resultado


def test_busca_sem_resultado_diz_isso(repo: Path):
    assert buscar_codigo(repo, "pagamento_pix") == "Nada encontrado para 'pagamento_pix'."


def test_le_arquivo_com_linhas_numeradas(repo: Path):
    resultado = ler_arquivo(repo, "app/pedidos.py", 2, 3)

    assert resultado.splitlines()[0] == "app/pedidos.py (linhas 2-3 de 4)"
    assert "    2      if not itens:" in resultado


@pytest.mark.parametrize("caminho", ["../fora.txt", "/etc/passwd", "app/../../fora.txt"])
def test_nao_sai_do_repositorio(repo: Path, caminho: str):
    with pytest.raises(ForaDoRepositorio):
        resolver_caminho(repo, caminho)
    assert ler_arquivo(repo, caminho).startswith("Caminho fora do repositório")


def test_ferramentas_tem_nome_e_descricao_para_o_modelo(repo: Path):
    ferramentas = {f.name: f for f in criar_ferramentas(repo)}

    assert set(ferramentas) == {"buscar_codigo", "ler_arquivo"}
    assert all(f.description for f in ferramentas.values())
    assert "app/pedidos.py:3" in ferramentas["buscar_codigo"].invoke({"termo": "pedido sem itens"})
