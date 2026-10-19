"""Integrações de verdade: o MCP do Gate 2 (leitura) e o GitHub (comentário, só após aprovação)."""

import asyncio
import os

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class McpIssueSource:
    """Lê a issue pelo MCP do issue tracker (Gate 2), subindo o servidor por stdio como o CLI faz."""

    def __init__(self, command: str, args: list[str], env: dict[str, str]):
        self.params = StdioServerParameters(command=command, args=args, env={**os.environ, **env})

    def resumo(self, repo: str, numero: int) -> str:
        return asyncio.run(self._chamar("resumo_do_bug", {"repo": repo, "numero": numero}))

    async def _chamar(self, nome: str, argumentos: dict) -> str:
        async with stdio_client(self.params) as (leitura, escrita), ClientSession(leitura, escrita) as sessao:
            await sessao.initialize()
            resultado = await sessao.call_tool(nome, argumentos)
        texto = "\n".join(c.text for c in resultado.content if getattr(c, "text", None))
        if resultado.is_error:
            raise RuntimeError(f"O MCP recusou {nome}: {texto}")
        return texto


class GitHubCommenter:
    """Publica o comentário na issue. É a única ação com efeito externo do agente."""

    def __init__(self, token: str, base_url: str = "https://api.github.com"):
        self.client = httpx.Client(
            base_url=base_url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30,
        )

    def comentar(self, repo: str, numero: int, texto: str) -> str:
        resposta = self.client.post(f"/repos/{repo}/issues/{numero}/comments", json={"body": texto})
        resposta.raise_for_status()
        return resposta.json()["html_url"]
