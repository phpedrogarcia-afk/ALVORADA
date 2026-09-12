# AI — START HERE

**Projeto:** ALVORADA — codinome provisório  
**Estado canônico:** sempre em `SOURCE-OF-TRUTH.md`; não replique aqui um snapshot que possa envelhecer.

## Ordem mínima de leitura

1. `SOURCE-OF-TRUTH.md` — estado canônico atual.
2. `PRODUCT-CONSTITUTION.md` — limites que nenhuma solução pode contornar.
3. `DECISIONS-LEDGER.md` — decisões aceitas e condições de reabertura.
4. Conforme a tarefa: `PROJECT-CHARTER.md`, `OPEN-QUESTIONS.md` e `ACTIVE-QUEUE.md`.
5. Para confiabilidade: `evidence/g1/e0/E0-RESULTS.md`, `evidence/g1/e1/E1-RESULTS.md`, depois `docs/reliability/POLICY-FREEZE.md`, `EVIDENCE-PLAN.md`, `RELIABILITY-CONTRACT.md`, `SUPPORTED-ENVELOPE.md` e os documentos G1 ali referenciados.

## Autoridade

`PRODUCT-CONSTITUTION.md` prevalece sobre os demais documentos. `SOURCE-OF-TRUTH.md` descreve o presente, mas não pode revogar a Constituição. `DECISIONS-LEDGER.md` preserva o histórico; entre decisões não constitucionais, vale a decisão aceita mais recente. Charter, questões e fila orientam propósito e investigação, sem converter incerteza em compromisso.

## Antes de alterar

- Nunca altere ou contorne um **HARD INVARIANT** silenciosamente. Registre a proposta, o motivo, o impacto e obtenha decisão explícita do fundador.
- Não promova hipótese a fato ou decisão sem evidência adequada e registro no ledger.
- Ao mudar uma decisão, preserve a entrada anterior, altere seu status e crie uma nova entrada; sincronize o `SOURCE-OF-TRUTH.md`.
- Registre todo aprendizado que possa mudar produto, risco ou próximo gate.
- Não finalize nome, estética, público, tecnologia ou feature que permaneça aberta.

## Linguagem obrigatória de memória

| Rótulo | Significado |
| --- | --- |
| **FACT** | Algo demonstrado por evidência identificável. |
| **DECISION** | Escolha consciente e registrada do projeto. |
| **HYPOTHESIS** | Explicação ou aposta plausível ainda não validada. |
| **OPEN** | Incerteza relevante sem resposta suficiente. |
| **SCAR** | Aprendizado persistente originado por erro, falha, surpresa ou descoberta. |
| **PATTERN** | Mecanismo validado e reutilizável. |
| **WIN** | Abordagem excepcionalmente eficaz que merece ser preservada. |

Não invente `SCAR`, `PATTERN` ou `WIN` para preencher lacunas.

Fatos normativos Android não são resultados medidos. Envelope proposto não é envelope validado.
`E0_PASS` não implica Android; preflight bloqueado não é cenário E1 nem `NOT_TESTABLE_E1`.
Capacidade documentada de CI não é binding executável nem precheck aprovado.
