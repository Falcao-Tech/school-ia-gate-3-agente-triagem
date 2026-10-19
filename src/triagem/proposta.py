"""A proposta de triagem: o que o modelo sugere e o que o código confere antes de mostrar."""

from dataclasses import asdict, dataclass, field
from pathlib import Path

from pydantic import BaseModel, Field

from triagem.codigo import ForaDoRepositorio, resolver_caminho  # noqa: F401 -- use em validar_proposta

LABEL_PADRAO = "triagem"


class PropostaDoModelo(BaseModel):
    """Saída estruturada que o modelo preenche depois de investigar."""

    label: str = Field(description="Uma das labels permitidas que melhor classifica o bug")
    arquivos: list[str] = Field(description="Caminhos relativos dos arquivos por onde começar, do mais provável ao menos")
    primeiro_passo: str = Field(description="O que a pessoa responsável deve fazer primeiro, em uma frase")
    justificativa: str = Field(description="Por que esses arquivos e essa label, com base no que foi lido no código")


@dataclass
class Proposta:
    label: str
    arquivos: list[str]
    primeiro_passo: str
    justificativa: str
    responsavel: str | None = None
    descartados: list[str] = field(default_factory=list)  # arquivos citados pelo modelo que não existem

    def to_dict(self) -> dict:
        return asdict(self)


def validar_proposta(bruta: PropostaDoModelo, repo: Path, labels: list[str]) -> Proposta:
    """Confere a proposta do modelo contra o repositório antes de mostrar para a pessoa.

    Contrato (ver tests/test_proposta.py):
    - Arquivo que não existe no repositório (ou que escapa dele, ver resolver_caminho) sai de
      `arquivos` e vai para `descartados`, na ordem em que o modelo citou. Sem repetir.
    - Label é comparada sem espaço nas pontas e em minúscula; fora de `labels` vira LABEL_PADRAO.
    - primeiro_passo e justificativa sem espaço nas pontas. `responsavel` fica None (quem
      preenche é o nó propor, com sugerir_responsavel).
    """
    # TODO: implemente.
    raise NotImplementedError("validar_proposta")


def comentario_markdown(proposta: Proposta, run_id: str) -> str:
    """Texto do comentário que vai para a issue, só depois da aprovação humana."""
    arquivos = "\n".join(f"- `{a}`" for a in proposta.arquivos) or "- (nenhum arquivo identificado)"
    return "\n".join([
        "### Sugestão do agente de triagem",
        "",
        f"**Label sugerida:** `{proposta.label}`",
        f"**Quem deveria olhar:** {proposta.responsavel or 'sem histórico no git; defina na mão'}",
        "",
        "**Por onde começar:**",
        arquivos,
        "",
        f"**Primeiro passo:** {proposta.primeiro_passo}",
        "",
        f"<details><summary>Por quê</summary>\n\n{proposta.justificativa}\n\n</details>",
        "",
        f"<sub>Aprovado por uma pessoa antes de publicar. Trace: `{run_id}`</sub>",
    ])
