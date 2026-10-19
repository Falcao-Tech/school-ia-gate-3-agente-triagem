"""Trace persistido: cada passo do agente vira uma linha JSON em traces/<run_id>.jsonl."""

import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from langgraph.errors import GraphInterrupt

MAX_TEXT = 4000


def _curto(valor: Any) -> Any:
    if isinstance(valor, str) and len(valor) > MAX_TEXT:
        return valor[:MAX_TEXT] + f"… (+{len(valor) - MAX_TEXT} caracteres)"
    return valor


class Tracer:
    def __init__(self, pasta: Path, run_id: str | None = None):
        self.run_id = run_id or datetime.now(UTC).strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        pasta.mkdir(parents=True, exist_ok=True)
        self.arquivo = pasta / f"{self.run_id}.jsonl"

    def evento(self, tipo: str, **dados: Any) -> None:
        linha = {"ts": datetime.now(UTC).isoformat(), "run_id": self.run_id, "tipo": tipo}
        linha.update({k: _curto(v) for k, v in dados.items()})
        with self.arquivo.open("a", encoding="utf-8") as f:
            f.write(json.dumps(linha, ensure_ascii=False, default=str) + "\n")

    def no(self, nome: str, funcao):
        """Envolve um nó do grafo registrando início, fim, duração e erro."""

        def envolvido(estado):
            inicio = time.perf_counter()
            self.evento("no_inicio", no=nome)
            try:
                saida = funcao(estado)
            except GraphInterrupt:
                self.evento("aguardando_humano", no=nome)
                raise
            except Exception as erro:
                self.evento("no_erro", no=nome, erro=repr(erro), ms=round((time.perf_counter() - inicio) * 1000))
                raise
            self.evento("no_fim", no=nome, ms=round((time.perf_counter() - inicio) * 1000))
            return saida

        return envolvido


def ler_trace(arquivo: Path) -> list[dict]:
    return [json.loads(linha) for linha in arquivo.read_text(encoding="utf-8").splitlines() if linha.strip()]


def resumo_trace(eventos: list[dict]) -> str:
    """Linha do tempo legível de um trace, para `triagem trace <arquivo>`."""
    linhas = []
    for e in eventos:
        hora = e["ts"][11:19]
        tipo = e["tipo"]
        if tipo == "no_fim":
            linhas.append(f"{hora}  ✓ {e['no']} ({e['ms']} ms)")
        elif tipo == "no_erro":
            linhas.append(f"{hora}  ✗ {e['no']}: {e['erro']}")
        elif tipo == "ferramenta":
            linhas.append(f"{hora}    → {e['nome']}({json.dumps(e['args'], ensure_ascii=False)})")
        elif tipo == "modelo":
            linhas.append(f"{hora}    ◆ modelo: {e.get('tokens_entrada', '?')} in / {e.get('tokens_saida', '?')} out")
        elif tipo == "aguardando_humano":
            linhas.append(f"{hora}  ⏸ {e['no']}: aguardando aprovação humana")
        elif tipo in ("inicio", "proposta", "decisao", "comentario"):
            detalhe = {k: v for k, v in e.items() if k not in ("ts", "run_id", "tipo")}
            linhas.append(f"{hora}  ● {tipo}: {json.dumps(detalhe, ensure_ascii=False)[:300]}")
    return "\n".join(linhas)
