import argparse
import os
import shlex
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from triagem.codigo import criar_ferramentas
from triagem.fontes import GitHubCommenter, McpIssueSource
from triagem.grafo import Dependencias, criar_grafo, iniciar, retomar
from triagem.proposta import PropostaDoModelo
from triagem.trace import Tracer, ler_trace, resumo_trace

LABELS_PADRAO = "bug,frontend,backend,infra,banco,docs"


def env(nome: str, padrao: str | None = None) -> str:
    valor = os.getenv(nome, padrao or "").strip()
    if not valor:
        sys.exit(f"Variável {nome} não configurada. Copie .env.example para .env e preencha.")
    return valor


def analisar(args: argparse.Namespace) -> None:
    repo_path = Path(args.clone).expanduser().resolve()
    if not (repo_path / ".git").exists():
        sys.exit(f"{repo_path} não é um clone git do repositório.")
    token = env("GITHUB_TOKEN")
    llm = ChatOpenAI(base_url=env("LLM_BASE_URL"), api_key=env("LLM_API_KEY", "ollama"), model=env("CHAT_MODEL"), temperature=0)
    ferramentas = criar_ferramentas(repo_path)
    tracer = Tracer(Path(os.getenv("TRACES_DIR", "traces")))
    deps = Dependencias(
        fonte=McpIssueSource(
            command=env("MCP_ISSUES_COMMAND", "npx"),
            args=shlex.split(env("MCP_ISSUES_ARGS")),
            env={"GITHUB_TOKEN": token},
        ),
        comentador=GitHubCommenter(token),
        investigador=llm.bind_tools(ferramentas).invoke,
        propositor=llm.with_structured_output(PropostaDoModelo, method="function_calling").invoke,
        ferramentas=ferramentas,
        repo_path=repo_path,
        labels=[label.strip() for label in os.getenv("LABELS", LABELS_PADRAO).split(",") if label.strip()],
        tracer=tracer,
        max_passos=int(os.getenv("MAX_PASSOS", "6")),
    )
    grafo = criar_grafo(deps)

    print(f"Triagem de {args.repo}#{args.numero} (trace: {tracer.arquivo})\n")
    pausa = iniciar(grafo, args.repo, args.numero, tracer.run_id)
    print(pausa["comentario"])
    if pausa["proposta"]["descartados"]:
        print(f"\n(arquivos citados pelo modelo que não existem e foram descartados: {pausa['proposta']['descartados']})")

    resposta = input("\nPublicar este comentário na issue? [s/N] ").strip().lower()
    final = retomar(grafo, "aprovar" if resposta in ("s", "sim") else "rejeitar", tracer.run_id)
    print(f"\nComentário publicado: {final['comentario_url']}" if final.get("comentario_url") else "\nNada foi publicado.")
    print(f"Trace: triagem trace {tracer.arquivo}")


def mostrar_trace(args: argparse.Namespace) -> None:
    arquivo = Path(args.arquivo)
    if not arquivo.exists():
        arquivo = Path(os.getenv("TRACES_DIR", "traces")) / f"{args.arquivo}.jsonl"
    print(resumo_trace(ler_trace(arquivo)))


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="triagem", description="Agente de triagem de bugs")
    comandos = parser.add_subparsers(dest="comando", required=True)
    a = comandos.add_parser("analisar", help="faz a triagem de uma issue")
    a.add_argument("repo", help="dono/repositorio")
    a.add_argument("numero", type=int)
    a.add_argument("--clone", required=True, help="caminho do clone local do repositório")
    a.set_defaults(func=analisar)
    t = comandos.add_parser("trace", help="mostra a linha do tempo de uma execução")
    t.add_argument("arquivo", help="arquivo .jsonl ou run_id")
    t.set_defaults(func=mostrar_trace)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
