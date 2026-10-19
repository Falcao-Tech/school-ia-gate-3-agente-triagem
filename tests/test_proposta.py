from pathlib import Path

from conftest import commit

from triagem.proposta import LABEL_PADRAO, PropostaDoModelo, comentario_markdown, validar_proposta
from triagem.responsavel import sugerir_responsavel

LABELS = ["bug", "backend", "frontend"]


def bruta(**campos) -> PropostaDoModelo:
    base = {"label": "backend", "arquivos": ["app/pedidos.py"], "primeiro_passo": "Validar itens.", "justificativa": "Erro sai daqui."}
    return PropostaDoModelo(**{**base, **campos})


def test_responsavel_e_quem_mais_mexeu_nos_arquivos(repo: Path):
    assert sugerir_responsavel(repo, ["app/pedidos.py"]) == "Ana Dev"
    assert sugerir_responsavel(repo, ["app/clientes.py", "README.md"]) == "Bruno Back"


def test_bot_nao_e_responsavel(repo: Path):
    for i in range(3):
        commit(repo, "app/clientes.py", f"versao {i}\n", "gpt-engineer-app[bot]")

    assert sugerir_responsavel(repo, ["app/clientes.py"]) == "Bruno Back"


def test_empate_fica_com_quem_mexeu_por_ultimo(repo: Path):
    commit(repo, "app/clientes.py", "def buscar_cliente(id):\n    return {}\n", "Ana Dev")

    assert sugerir_responsavel(repo, ["app/clientes.py"]) == "Ana Dev"


def test_sem_historico_nao_inventa_responsavel(repo: Path):
    assert sugerir_responsavel(repo, ["nao/existe.py"]) is None
    assert sugerir_responsavel(repo, []) is None


def test_arquivo_inventado_pelo_modelo_e_descartado(repo: Path):
    proposta = validar_proposta(bruta(arquivos=["app/pedidos.py", "app/inventado.py", "../../etc/passwd"]), repo, LABELS)

    assert proposta.arquivos == ["app/pedidos.py"]
    assert proposta.descartados == ["app/inventado.py", "../../etc/passwd"]


def test_label_fora_da_lista_vira_padrao(repo: Path):
    assert validar_proposta(bruta(label="urgentíssimo"), repo, LABELS).label == LABEL_PADRAO
    assert validar_proposta(bruta(label=" Backend "), repo, LABELS).label == "backend"


def test_comentario_mostra_proposta_e_que_houve_aprovacao(repo: Path):
    proposta = validar_proposta(bruta(), repo, LABELS)
    proposta.responsavel = "Ana Dev"

    texto = comentario_markdown(proposta, "run-123")

    assert "**Label sugerida:** `backend`" in texto
    assert "**Quem deveria olhar:** Ana Dev" in texto
    assert "- `app/pedidos.py`" in texto
    assert "Aprovado por uma pessoa" in texto
    assert "run-123" in texto
