# SOURCE OF TRUTH

**Snapshot:** 2026-09-14 · **ALVORADA: codinome**
**G0: PASS. G1: CONDITIONAL. G1.1: PASS. G1.2: E0_PASS. G1.3 / MISSÃO 05R: PUBLIC_BINDING_READY_DISCOVERY_NOT_RUN.** `REPOSITORY_BINDING = PASS` e `PUBLICATION_SECURITY_CHECK = PASS_WITH_CAVEAT`; `LAB_DISCOVERY = NOT_RUN`, P1–P10 = `UNKNOWN` e `READY_FOR_E1_WAVE1 = NO`; envelope validado vazio. G2 não liberado.

## Visão atual

Despertar sereno e eficaz, alarme primeiro, contexto seletivo e local-first. Android é a primeira plataforma. Existe somente um harness científico descartável; nenhuma implementação de produto, stack de produto ou UI final foi escolhida.

## FACT — evidência disponível

| ID | Tipo | Fato | Evidência |
| --- | --- | --- | --- |
| F-001 | FACT-EVID | Não há app de produto nem resultado Android ou acústico; só o modelo E0 foi executado | Auditoria G1.2; `E1-RESULTS.md` |
| F-002 | FACT-EVID | ALVORADA não é marca aprovada | Briefings do fundador |
| F-003 | FACT-EVID | Público, valor recorrente e disposição para pagar não foram validados | Nenhum estudo de usuários fornecido/executado |
| F-004 | FACT-EVID | Núcleo de experiência G2 foi priorizado; estética e parâmetros continuam abertos | D-EXPERIENCE-CORE-01 |
| F-005 | FACT-EVID | Contrato G1.1, 56 falhas, policy freeze e plano E0–E5 definidos; envelope validado vazio | `docs/reliability/`; não significa aprovação empírica |
| F-006 | FACT-DOC | Force-stop difere de stop no gerenciador de apps ativos | Pesquisa oficial R09/R28 |
| F-007 | FACT-DOC | Preparação local não resolve por si só lifecycle de áudio nem disponibilidade pré-unlock | Pesquisa oficial R10/R13 |
| F-008 | FACT-DOC + limite de inferência | Callbacks/estado interno documentados não são observação física do som | Pesquisa R13/R17; cadeia epistêmica do contrato |
| F-009 | FACT-EVID | Harness descartável `0.1.0` foi congelado no SHA `06a8cbbc2b75e9b2e415f87574b5a1307b524d8b` e testado clean | `EVID-G1-0001..0003` |
| F-010 | FACT-EVID | E0 passou 72 testes determinísticos + 10 seeds, 100.000 sequências e 935.769 assertions, sem falha na rodada oficial | `EVID-G1-0002`, `EVID-G1-0003`; condições no manifest |
| F-011 | FACT-EVID | E1 executou zero cenários: APIs 31/34/35/36/37 ficaram bloqueadas por ausência de SDK/tools/imagens/AVDs; cinco preflights, nenhum resultado Android | `EVID-G1-0004..0008` |
| F-012 | FACT-DOC / FACT-EVID | O setup oficial classifica API 37 no canal Preview; localmente API 37 está indisponível | Android 17 setup; `EVID-G1-0008` |
| F-013 | FACT-DOC | Em 2026-09-12: Play exige target API 36+ para novos apps/updates; API 37 segue Preview; alarm/timer segue uso legítimo e restrito de exact alarm | Fontes oficiais revalidadas em `EVID-G1-0010` |
| F-014 | FACT-EVID histórico | Na MISSÃO 05, GitHub-hosted Linux tinha aceleração Android documentada, mas o projeto ainda não possuía repo/runner autorizado; capacidade de CI não era binding executável | `EVID-G1-0009..0010`; sete repos então inspecionados, zero ALVORADA |
| F-015 | FACT-EVID | `phpedrogarcia-afk/ALVORADA` é público; o histórico canônico foi sanitizado para o HEAD `e78c80365ab0345247704f5a27fe9fa80f096652` sem alteração das trees técnicas correspondentes. O snapshot Foundation+G1+harness+evidências permanece rastreável a partir da importação histórica de 53 arquivos | `EVID-G1-0012..0013`; SHAs pré-sanitização permanecem somente como proveniência |
| F-016 | FACT-EVID | Actions está habilitado no repo público, o workflow manual está visível e nenhum workflow rodou; custo da missão = USD 0. Runner real, `/dev/kvm`, SDK/emulator/AVD e P1–P10 continuam não observados | `EVID-G1-0013`; `LAB_DISCOVERY = NOT_RUN` |
| F-017 | FACT-EVID / limite de inferência | A auditoria do histórico canônico alcançável não encontrou os padrões pesquisados de e-mail pessoal, tokens, chaves, credenciais, URLs autenticadas, `.env` ou secrets. Isso é `NO_MATCH_FOUND`, não prova de ausência global; clones, caches e objetos fora do histórico alcançável podem persistir | `EVID-G1-0013`; `PUBLICATION_SECURITY_CHECK = PASS_WITH_CAVEAT` |
| F-018 | FACT-EVID | Uma rota de publicação externa materializou um commit com metadados fora da política noreply; o commit foi retirado imediatamente de `main`, que voltou ao HEAD sanitizado. A rota não deve ser usada para publicação canônica | `EVID-G1-0014`; nenhum discovery ou cenário E1 foi executado |

FACTs documentais Android, APIs, URLs, confiança e divergências estão em [ANDROID-RELIABILITY-RESEARCH.md](docs/reliability/ANDROID-RELIABILITY-RESEARCH.md), não duplicados aqui.

## DECISION — escolhas vigentes

D-001–D-012 continuam vigentes no ledger: centro estreito, codinome, prioridade do alarme, offline/degradação, serenidade eficaz, parcimônia, som/voz, otimismo lúcido, privacidade, proveniência, humanidade sem engano e evidência antes de código.

| ID novo | Decisão aceita |
| --- | --- |
| D-G0-APPROVAL-01 | G0 PASS, autorizado pelo fundador |
| D-PLATFORM-01 | Android primeiro; nenhum compromisso multiplataforma |
| D-DATA-01 | Local-first: horários, alarmes, lembretes, preferências, histórico necessário e WakePlans locais por padrão; rede opcional |
| D-RELIABILITY-01 | Sem promessa universal; suporte limitado ao envelope efetivamente validado |
| D-EXPERIENCE-CORE-01 | G2 prioriza paisagem sonora, voz serena, nome, hora, mensagem breve e Escalada Serena; visual apoia; mascote não obrigatório |
| D-G1-READINESS-01 | Ausência de capacidade essencial deve ser explícita; intenção salva não é alarme confiável armado |
| D-G1-TELEMETRY-01 | Telemetria mínima local primeiro; envio remoto permanece OPEN |
| D-G1-LAB-01 | **SUPERSEDED.** Binding privado e zero-overage preservado como decisão histórica; não governa mais o laboratório público atual |
| D-G1-LAB-02 | Repo público canônico `ALVORADA`, GitHub Actions standard GitHub-hosted `ubuntu-24.04`; larger runners, infraestrutura e serviços pagos seguem proibidos. Artefatos devem ser mínimos, reter somente 1 dia e nunca incluir SDK, system images ou AVDs |

F-03-01–F-03-15 também estão ACCEPTED no ledger: investigar API 31+; hora civil/fuso; gap/fold; late recovery de 10 min; bandas 2/5 s e 1/3 s; soneca 5 min; dismiss occurrence-scoped; sessão experimental 30 min; concorrência independente; Direct Boot no target; restore sem ARMED; retenção 30 dias/1.000 eventos; e autorização de futura missão de harness descartável. Valores experimentais não são FACT nem promessa comercial.

## HYPOTHESIS — ainda não validadas

| ID | Hipótese preservada de G0 |
| --- | --- |
| H-001 | Confiabilidade, progressão sensorial e contexto mínimo melhoram o despertar sem aumentar carga ou ansiedade |
| H-003 | Paisagem sonora contínua e voz natural breve são aceitas e eficazes no cotidiano |
| H-004 | Escalada progressiva acomoda diferentes profundidades de sono sem agressão |
| H-005 | Visual de noite a amanhecer agrega valor funcional |
| H-006 | Agenda, clima e lembretes podem ser filtrados com precisão suficiente |
| H-007 | Reflexões e citações verificadas são pertinentes, não invasivas |
| H-008 | Voz natural transmite calor sem personificação enganosa |
| H-009 | Pequeno componente lúdico/afetivo cria vínculo sem infantilizar ou ampliar o produto |

Priorizar um elemento no G2 não prova benefício.

**H-AUDIENCE-01** refina H-002: investigar pessoas que usam alarme diariamente, consideram o despertar tradicional desagradável e desejam transição calma. Não pressupor mercado, willingness to pay, sleepers extremos ou aplicação clínica.

| ID G1 | Hipótese de solução, não escolha final |
| --- | --- |
| H-G1-01 | setAlarmClock + PendingIntent é o melhor candidato para ocorrência de despertar |
| H-G1-02 | Soneca pode preservar duração e confiabilidade sob quotas/clock changes; método ainda aberto |
| H-G1-03 | Enriquecimento pré-computado como snapshot opcional evita dependência crítica, inclusive sob contenção |
| H-G1-04 | USE_EXACT_ALARM será via adequada/elegível em 33+, com compatibilidade 31–32 por SCHEDULE |

## OPEN — condições para sair de G1 CONDITIONAL

1. Aplicar e publicar a correção de binding via Git local com metadados noreply verificáveis; não usar a rota externa que materializa commits fora dessa política.
2. Executar um único discovery run, observar KVM/runner/tooling e, somente se `LAB_DISCOVERY_PASS`, provisionar API 36 e completar P1–P10; adapter e Wave 1 continuam fora da MISSÃO 05R.
3. Depois da aprovação do laboratório, construir o adapter descartável e executar E1 real nas APIs 31, 34, 35, 36 e 37; E0 já passou.
4. Escolher e obter modelos/fingerprints físicos para E2/E3; nenhuma família OEM é suportada por nome.
5. Calibrar oráculo acústico, clocks e epsilon; escolher limite de disponibilidade de controles.
6. Demonstrar Direct Boot real, lifecycle/foco/áudio em API 37 e contenção de dependências opcionais.
7. Comparar mecanismo de snooze pós-reboot e arbitragem OUTPUT_OWNER/OUTPUT_WAITING sem alterar semântica decidida.
8. Executar repetições E2–E5, resolver S0s e aprovar cada célula explicitamente.
9. Envio remoto, máximo de snoozes, UX concorrente e retenção de artefatos laboratoriais continuam OPEN.

Detalhes em [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md), [POLICY-FREEZE.md](docs/reliability/POLICY-FREEZE.md) e [EVIDENCE-PLAN.md](docs/reliability/EVIDENCE-PLAN.md).

## SCAR / PATTERN / WIN

**SCAR-G1-01:** descoberta documental real — estado indireto pode superestimar entrega; separar registro, trigger, áudio e audibilidade, admitindo UNKNOWN. Evidência e prevenção no registro de pesquisa. Não é incidente de produção.

**SCAR-G1-02:** descoberta de modelagem — prontidão envelhece como conhecimento: um alarme verificado às 22:00 não continua demonstravelmente verificado após uma mudança não reconciliada. Preservar checkpoint, `READINESS_STALE` e resultado separado de `EVENT_RECEIVED`. Não é incidente de produção.

**SCAR-G1-03:** falha de modelo revelada no E0 — estado durável e propriedade efêmera do output não podem compartilhar restauração ingênua. Após morte do processo, descartar `OUTPUT_OWNER` e converter estados em voo para `RECOVERY_REQUIRED`; histórico interno não prova áudio atual. Evidência: `EVID-G1-0002` e relatório E0.

**SCAR-G1-04:** falha de prontidão laboratorial — capacidade documentada do provedor não é laboratório disponível sem repositório/runner autorizado, configuração vinculada, guardrail financeiro comprovado e caminho de retorno de artefatos. Preservar `PLATFORM_CAPABILITY != EXECUTION_BINDING != PRECHECK_PASS`. Evidência: `EVID-G1-0009..0012`.

**SCAR-G1-05:** publicação de repositório — revisar a working tree não basta antes de expor um repositório: auditar também histórico alcançável e metadados Git. Registrar o escopo da busca como `NO_MATCH_FOUND`, sem alegar remoção global de clones, caches ou objetos anteriores. Evidência: `EVID-G1-0013`.

**SCAR-G1-06:** rota de publicação — a configuração Git local não governa commits criados por outra API ou connector. Antes de adotar uma rota de publicação, provar os metadados que ela materializa; se falhar, conter antes de qualquer execução dependente. Evidência: `EVID-G1-0014`.

Nenhum PATTERN ou WIN validado.

## Próxima investigação

**Aplicar e publicar primeiro a correção de binding, por Git local com noreply verificável.** Depois executar somente um discovery; se aprovado, o precheck mínimo API 36. Encerrar a missão antes do adapter/Wave 1. Não iniciar E2, G2, produto, UI final ou stack de produção.
