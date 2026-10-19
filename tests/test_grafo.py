"""O agente inteiro, com modelo e GitHub de mentira: só o grafo, as ferramentas e o git são de verdade."""

from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

from triagem.codigo import criar_ferramentas
from triagem.grafo import Dependencias, criar_grafo, iniciar, retomar
from triagem.proposta import PropostaDoModelo
from triagem.trace import Tracer, ler_trace, resumo_trace

ISSUE = "# Falcao-Tech/api#42: Erro 500 ao salvar pedido vazio\nA API devolve 500 com 'pedido sem itens'."


class FonteFake:
    def __init__(self):
        self.chamadas = []

    def resumo(self, repo: str, numero: int) -> str:
        self.chamadas.append((repo, numero))
        return ISSUE


class ComentadorFake:
    def __init__(self):
        self.comentarios = []

    def comentar(self, repo: str, numero: int, texto: str) -> str:
        self.comentarios.append((repo, numero, texto))
        return f"https://github.com/{repo}/issues/{numero}#issuecomment-1"


class InvestigadorRoteirizado:
    """Devolve as respostas na ordem; depois do roteiro, repete a última.

    Cada resposta sai como mensagem nova (sem id), como um modelo de verdade faria: o
    add_messages do LangGraph substitui mensagens com o mesmo id em vez de acrescentar.
    """

    def __init__(self, respostas: list[AIMessage]):
        self.respostas, self.recebidas = respostas, []

    def __call__(self, mensagens):
        self.recebidas.append(list(mensagens))
        return self.respostas[min(len(self.recebidas) - 1, len(self.respostas) - 1)].model_copy(update={"id": None})


def chamada(nome: str, args: dict, id_: str) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": nome, "args": args, "id": id_}])


PROPOSTA = PropostaDoModelo(
    label="backend",
    arquivos=["app/pedidos.py", "app/fantasma.py"],
    primeiro_passo="Trocar o ValueError por 422 na rota.",
    justificativa="O erro 'pedido sem itens' é lançado em salvar_pedido.",
)


def montar(repo: Path, tmp_path: Path, respostas: list[AIMessage], max_passos: int = 6):
    fonte, comentador = FonteFake(), ComentadorFake()
    investigador = InvestigadorRoteirizado(respostas)
    propositor_recebeu = []

    def propositor(mensagens):
        propositor_recebeu.append(list(mensagens))
        return PROPOSTA

    tracer = Tracer(tmp_path / "traces", run_id="run-teste")
    deps = Dependencias(
        fonte=fonte,
        comentador=comentador,
        investigador=investigador,
        propositor=propositor,
        ferramentas=criar_ferramentas(repo),
        repo_path=repo,
        labels=["bug", "backend", "frontend"],
        tracer=tracer,
        max_passos=max_passos,
    )
    return criar_grafo(deps), fonte, comentador, investigador, propositor_recebeu, tracer


ROTEIRO = [
    chamada("buscar_codigo", {"termo": "pedido sem itens"}, "c1"),
    chamada("ler_arquivo", {"caminho": "app/pedidos.py"}, "c2"),
    AIMessage(content="O erro sai de app/pedidos.py."),
]


def test_para_e_pede_aprovacao_antes_de_comentar(repo: Path, tmp_path: Path):
    grafo, fonte, comentador, _, _, _ = montar(repo, tmp_path, ROTEIRO)

    pausa = iniciar(grafo, "Falcao-Tech/api", 42, "t1")

    assert fonte.chamadas == [("Falcao-Tech/api", 42)]
    assert comentador.comentarios == []
    assert pausa["proposta"]["arquivos"] == ["app/pedidos.py"]
    assert pausa["proposta"]["descartados"] == ["app/fantasma.py"]
    assert pausa["proposta"]["responsavel"] == "Ana Dev"
    assert "Sugestão do agente de triagem" in pausa["comentario"]


def test_resultado_das_ferramentas_volta_para_o_modelo(repo: Path, tmp_path: Path):
    grafo, _, _, investigador, _, _ = montar(repo, tmp_path, ROTEIRO)

    iniciar(grafo, "Falcao-Tech/api", 42, "t1")

    segunda_rodada = investigador.recebidas[1]
    assert "app/pedidos.py:3" in segunda_rodada[-1].content
    assert len(investigador.recebidas) == 3


def test_rejeitado_nao_publica_nada(repo: Path, tmp_path: Path):
    grafo, _, comentador, _, _, _ = montar(repo, tmp_path, ROTEIRO)
    iniciar(grafo, "Falcao-Tech/api", 42, "t1")

    final = retomar(grafo, "rejeitar", "t1")

    assert final["decisao"] == "rejeitar"
    assert comentador.comentarios == []
    assert "comentario_url" not in final


def test_aprovado_publica_uma_vez(repo: Path, tmp_path: Path):
    grafo, _, comentador, _, _, _ = montar(repo, tmp_path, ROTEIRO)
    iniciar(grafo, "Falcao-Tech/api", 42, "t1")

    final = retomar(grafo, "aprovar", "t1")

    assert len(comentador.comentarios) == 1
    repo_nome, numero, texto = comentador.comentarios[0]
    assert (repo_nome, numero) == ("Falcao-Tech/api", 42)
    assert "`app/pedidos.py`" in texto
    assert final["comentario_url"].endswith("#issuecomment-1")


def test_resposta_estranha_conta_como_rejeicao(repo: Path, tmp_path: Path):
    grafo, _, comentador, _, _, _ = montar(repo, tmp_path, ROTEIRO)
    iniciar(grafo, "Falcao-Tech/api", 42, "t1")

    retomar(grafo, "sim por favor", "t1")  # type: ignore[arg-type]

    assert comentador.comentarios == []


def test_limite_de_passos_impede_loop_infinito(repo: Path, tmp_path: Path):
    sempre_busca = [chamada("buscar_codigo", {"termo": "pedido"}, "loop")]
    grafo, _, _, investigador, propositor_recebeu, _ = montar(repo, tmp_path, sempre_busca, max_passos=3)

    pausa = iniciar(grafo, "Falcao-Tech/api", 42, "t1")

    assert len(investigador.recebidas) == 3
    assert pausa["proposta"]["arquivos"] == ["app/pedidos.py"]
    # A chamada pendente que estourou o limite não vai para o propositor (a API recusaria).
    ultima_do_historico = propositor_recebeu[0][-2]
    assert not getattr(ultima_do_historico, "tool_calls", None)


def test_trace_registra_cada_passo(repo: Path, tmp_path: Path):
    grafo, _, _, _, _, tracer = montar(repo, tmp_path, ROTEIRO)
    iniciar(grafo, "Falcao-Tech/api", 42, "t1")
    retomar(grafo, "aprovar", "t1")

    eventos = ler_trace(tracer.arquivo)
    tipos = [e["tipo"] for e in eventos]
    nos_concluidos = [e["no"] for e in eventos if e["tipo"] == "no_fim"]

    assert nos_concluidos == ["ler_issue", "investigar", "ferramentas", "investigar", "ferramentas", "investigar", "propor", "aprovar", "comentar"]
    assert "aguardando_humano" in tipos
    assert [e["nome"] for e in eventos if e["tipo"] == "ferramenta"] == ["buscar_codigo", "ler_arquivo"]
    assert next(e for e in eventos if e["tipo"] == "decisao")["decisao"] == "aprovar"
    assert "comentario" in tipos
    assert "⏸ aprovar" in resumo_trace(eventos)


def test_ferramenta_desconhecida_volta_como_erro_para_o_modelo(repo: Path, tmp_path: Path):
    roteiro = [chamada("apagar_repositorio", {}, "x1"), AIMessage(content="ok")]
    grafo, _, _, investigador, _, _ = montar(repo, tmp_path, roteiro)

    iniciar(grafo, "Falcao-Tech/api", 42, "t1")

    assert "Ferramenta desconhecida: apagar_repositorio" in investigador.recebidas[1][-1].content


@pytest.mark.parametrize("decisao", ["aprovar", "rejeitar"])
def test_cada_execucao_tem_seu_proprio_estado(repo: Path, tmp_path: Path, decisao: str):
    grafo, _, comentador, _, _, _ = montar(repo, tmp_path, ROTEIRO)
    iniciar(grafo, "Falcao-Tech/api", 42, "a")
    iniciar(grafo, "Falcao-Tech/api", 42, "b")

    retomar(grafo, decisao, "a")

    assert len(comentador.comentarios) == (1 if decisao == "aprovar" else 0)
