# Gate 3 · Agente de triagem de bugs com aprovação humana

Desafio da **Fase 3 (Agentes e arquitetura)** da trilha de Engenharia de Software com IA
Aplicada do Noclaf School.

Você vai construir, em Python com **LangGraph**, um agente que recebe uma issue, investiga o
código do repositório e propõe a triagem: label, quem deveria olhar e por onde começar. Ele lê
a issue pelo **MCP do seu Gate 2**, registra cada passo num trace e **só comenta na issue
depois que uma pessoa aprova**. Na fase seguinte, o agente vira uma peça do copiloto do time.

## Critério de aprovação

- Lê uma issue real, encontra o código provável e sugere label e responsável
- Cada execução deixa um trace consultável
- Nada é comentado na issue sem aprovação humana

## Como o agente funciona

```
ler_issue → investigar ⇄ ferramentas → propor → aprovar ⏸ → comentar
                                                   └──────→ fim (rejeitado)
```

| Nó | O que faz | Quem decide |
|---|---|---|
| `ler_issue` | busca a issue pelo MCP do Gate 2 (`resumo_do_bug`) | código |
| `investigar` ⇄ `ferramentas` | o modelo chama `buscar_codigo` e `ler_arquivo` no clone local, até `MAX_PASSOS` rodadas | modelo |
| `propor` | o modelo preenche a proposta; o código descarta arquivo inventado, troca label fora da lista e escolhe o responsável pelo `git log` | modelo propõe, código confere |
| `aprovar` | pausa o grafo (`interrupt`) e espera a decisão | **pessoa** |
| `comentar` | publica o comentário na issue | só se aprovado |

Duas regras de desenho que valem para todo agente do time:

- **O modelo propõe, o código confere.** O responsável sai do histórico do git, não da
  imaginação do modelo; arquivo que não existe não vai para o comentário.
- **Ação com efeito externo passa por aprovação humana.** O MCP do Gate 2 é só de leitura; o
  único efeito externo do agente é o comentário, e ele mora atrás do `interrupt`.

## Como começar

1. Clique em **Use this template** e crie o repositório na **sua conta pessoal**.
2. Instale (precisa de [uv](https://docs.astral.sh/uv/), git e Node para o MCP do Gate 2):

   ```bash
   uv sync
   cp .env.example .env    # token, como subir o MCP e qual modelo usar
   ```

3. Rode os testes. **Eles começam vermelhos de propósito**: cada teste que falha é uma parte
   do desafio. Eles não chamam modelo nem GitHub; só o grafo, as ferramentas e o git são de
   verdade.

   ```bash
   uv run pytest
   ```

## O que você implementa

Já funcionam: leitura da issue pelo MCP, comentário no GitHub, ferramentas de busca e leitura
de código, os nós `ler_issue`, `investigar`, `ferramentas` e `comentar`, o trace e a CLI.
Procure por `TODO`.

| Arquivo | O que fazer | Testes |
|---|---|---|
| `src/triagem/codigo.py` | `resolver_caminho`: impedir que o modelo leia fora do repositório (`../`, caminho absoluto) | `tests/test_codigo.py` |
| `src/triagem/responsavel.py` | `sugerir_responsavel`: autor com mais commits nos arquivos, sem bots, empate para o mais recente | `tests/test_proposta.py` |
| `src/triagem/proposta.py` | `validar_proposta`: descartar arquivo inventado e label fora da lista | `tests/test_proposta.py` |
| `src/triagem/grafo.py` | rotas do grafo, nós `propor` e `aprovar` (com `interrupt`) e as arestas | `tests/test_grafo.py` |

Leia os testes antes de começar: eles são a especificação.

## Usando

Você precisa de um clone local do repositório da issue (é nele que o agente procura o código):

```bash
uv run triagem analisar Falcao-Tech/<repo> <numero> --clone ~/dev/<repo>
```

O agente mostra o comentário que publicaria e pergunta se pode publicar. Qualquer resposta
diferente de `s` não publica nada.

Para ver o que aconteceu numa execução:

```bash
uv run triagem trace <run_id>     # linha do tempo: nós, ferramentas, tokens, decisão
cat traces/<run_id>.jsonl          # o trace completo, uma linha JSON por evento
```

## Escolhendo o modelo

O agente precisa de um modelo com **tool calling**. `openai/gpt-4o-mini` pelo OpenRouter
investiga bem e é barato. No Ollama, use 7B ou maior (`qwen2.5:7b` funciona); modelos menores
tendem a parar na primeira busca e a propor arquivo genérico. Compare as duas opções pelo
trace: é para isso que ele existe.

## Entrega

1. Testes verdes: `uv run pytest`.
2. Rode o agente em pelo menos 3 issues reais do time e guarde os traces.
3. Envie o link do seu repositório na etapa **Gate 3** do Noclaf School (`/school` no NOS).
4. Na revisão, você roda o agente numa issue escolhida na hora, mostra o trace e mostra que
   rejeitar não publica nada.
