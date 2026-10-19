"""O agente de triagem como um grafo do LangGraph.

    ler_issue → investigar ⇄ ferramentas → propor → aprovar ⏸ → comentar
                                                       └──────→ fim (rejeitado)

O modelo investiga e propõe. Quem decide se algo vai para a issue é uma pessoa: o nó `aprovar`
pausa o grafo (interrupt) e só segue para `comentar` com a resposta "aprovar".
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal, Protocol, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph, add_messages  # noqa: F401
from langgraph.types import Command, interrupt  # noqa: F401 -- interrupt é seu no nó aprovar

from triagem.proposta import Proposta, PropostaDoModelo, comentario_markdown, validar_proposta  # noqa: F401
from triagem.responsavel import sugerir_responsavel  # noqa: F401
from triagem.trace import Tracer

SYSTEM_PROMPT = """Você faz a triagem de bugs de um time de desenvolvimento.
Recebe uma issue e investiga o código do repositório com as ferramentas buscar_codigo e
ler_arquivo para descobrir por onde a correção começa. Busque por mensagens de erro, nomes de
rota, de função e de tela citados na issue; leia os trechos que parecerem relevantes.
Não invente arquivo: só cite caminhos que você viu nas ferramentas.
Quando tiver o suficiente (ou depois de {max_passos} rodadas de ferramenta), pare de chamar
ferramentas e responda com um resumo curto do que encontrou."""

PEDIDO_PROPOSTA = """Com base na investigação, preencha a proposta de triagem.
Labels permitidas: {labels}. Arquivos: só caminhos relativos que apareceram nas ferramentas."""


class FonteDeIssues(Protocol):
    def resumo(self, repo: str, numero: int) -> str: ...


class Comentador(Protocol):
    def comentar(self, repo: str, numero: int, texto: str) -> str: ...  # devolve a URL do comentário


@dataclass
class Dependencias:
    fonte: FonteDeIssues
    comentador: Comentador
    investigador: Callable[[list[BaseMessage]], AIMessage]  # modelo com as ferramentas ligadas
    propositor: Callable[[list[BaseMessage]], PropostaDoModelo]  # modelo com saída estruturada
    ferramentas: list[BaseTool]
    repo_path: Path
    labels: list[str]
    tracer: Tracer
    max_passos: int = 6


class Estado(TypedDict, total=False):
    repo: str
    numero: int
    issue: str
    messages: Annotated[list[BaseMessage], add_messages]
    passos: int
    proposta: dict
    decisao: Literal["aprovar", "rejeitar"]
    comentario_url: str


def criar_grafo(deps: Dependencias, checkpointer=None):
    por_nome = {f.name: f for f in deps.ferramentas}
    tracer = deps.tracer

    def ler_issue(estado: Estado) -> Estado:
        issue = deps.fonte.resumo(estado["repo"], estado["numero"])
        tracer.evento("inicio", repo=estado["repo"], numero=estado["numero"], issue=issue)
        return {
            "issue": issue,
            "passos": 0,
            "messages": [
                SystemMessage(SYSTEM_PROMPT.format(max_passos=deps.max_passos)),
                HumanMessage(f"Issue para triagem:\n\n{issue}"),
            ],
        }

    def investigar(estado: Estado) -> Estado:
        resposta = deps.investigador(estado["messages"])
        uso = resposta.usage_metadata or {}
        tracer.evento(
            "modelo",
            no="investigar",
            tokens_entrada=uso.get("input_tokens"),
            tokens_saida=uso.get("output_tokens"),
            chamadas=[c["name"] for c in resposta.tool_calls],
            texto=resposta.content if isinstance(resposta.content, str) else str(resposta.content),
        )
        return {"messages": [resposta], "passos": estado["passos"] + 1}

    def ferramentas(estado: Estado) -> Estado:
        ultima = estado["messages"][-1]
        saidas = []
        for chamada in ultima.tool_calls:
            ferramenta = por_nome.get(chamada["name"])
            try:
                resultado = ferramenta.invoke(chamada["args"]) if ferramenta else f"Ferramenta desconhecida: {chamada['name']}"
            except Exception as erro:  # noqa: BLE001 -- erro de ferramenta volta para o modelo, não derruba o agente
                resultado = f"Erro na ferramenta: {erro}"
            tracer.evento("ferramenta", nome=chamada["name"], args=chamada["args"], resultado=str(resultado))
            saidas.append(ToolMessage(content=str(resultado), tool_call_id=chamada["id"], name=chamada["name"]))
        return {"messages": saidas}

    def rota_investigacao(estado: Estado) -> Literal["ferramentas", "propor"]:
        # TODO: vá para "ferramentas" se a última mensagem for um AIMessage com tool_calls E
        # ainda não bateu deps.max_passos; senão, "propor". Sem isso o agente roda para sempre.
        raise NotImplementedError("rota_investigacao")

    def propor(estado: Estado) -> Estado:
        # TODO: implemente.
        # 1. Pegue o histórico de mensagens. Se a última for um AIMessage com tool_calls (bateu o
        #    limite com chamada pendente), tire ela: a API recusa tool_call sem resposta.
        # 2. Chame deps.propositor com o histórico + HumanMessage(PEDIDO_PROPOSTA com as labels).
        # 3. Confira com validar_proposta e preencha o responsável com sugerir_responsavel.
        # 4. Registre tracer.evento("proposta", **proposta.to_dict()) e devolva {"proposta": proposta.to_dict()}.
        raise NotImplementedError("propor")

    def aprovar(estado: Estado) -> Estado:
        # TODO: implemente.
        # - Pause o grafo com interrupt({"proposta": ..., "comentario": comentario_markdown(...)}).
        #   O valor de retorno do interrupt é a resposta da pessoa (ver retomar, no fim do arquivo).
        # - Só "aprovar" aprova; QUALQUER outra resposta é "rejeitar".
        # - Registre tracer.evento("decisao", decisao=...) e devolva {"decisao": ...}.
        raise NotImplementedError("aprovar")

    def rota_aprovacao(estado: Estado) -> Literal["comentar", "__end__"]:
        # TODO: "comentar" só se a decisão for "aprovar"; senão END.
        raise NotImplementedError("rota_aprovacao")

    def comentar(estado: Estado) -> Estado:
        texto = comentario_markdown(Proposta(**estado["proposta"]), tracer.run_id)
        url = deps.comentador.comentar(estado["repo"], estado["numero"], texto)
        tracer.evento("comentario", url=url)
        return {"comentario_url": url}

    grafo = StateGraph(Estado)
    for nome, funcao in [
        ("ler_issue", ler_issue),
        ("investigar", investigar),
        ("ferramentas", ferramentas),
        ("propor", propor),
        ("aprovar", aprovar),
        ("comentar", comentar),
    ]:
        grafo.add_node(nome, tracer.no(nome, funcao))
    # TODO: ligue os nós conforme o diagrama do topo do arquivo:
    # START → ler_issue → investigar; investigar → (rota_investigacao); ferramentas → investigar;
    # propor → aprovar; aprovar → (rota_aprovacao); comentar → END.
    # Use grafo.add_edge e grafo.add_conditional_edges.
    return grafo.compile(checkpointer=checkpointer or InMemorySaver())


def iniciar(grafo, repo: str, numero: int, thread_id: str) -> dict:
    """Roda até a pausa de aprovação. Devolve o payload do interrupt (proposta + comentário)."""
    resultado = grafo.invoke({"repo": repo, "numero": numero}, {"configurable": {"thread_id": thread_id}})
    pausas = resultado.get("__interrupt__", [])
    if not pausas:
        raise RuntimeError("O agente terminou sem pedir aprovação; isso não deveria acontecer.")
    return pausas[0].value


def retomar(grafo, decisao: Literal["aprovar", "rejeitar"], thread_id: str) -> dict:
    """Continua depois da decisão humana. Devolve o estado final."""
    return grafo.invoke(Command(resume=decisao), {"configurable": {"thread_id": thread_id}})
