# EVIDENCE PLAN — G1.1

ALVORADA — codinome. Atualizado em 2026-09-12. **Plano normativo G1.1; estado de execução G1.2: E0_PASS / E1_CONDITIONAL.**

`READY_FOR_INSTRUMENTED_EVIDENCE = YES`. O harness E0 descartável já existe; este plano continua governando E1–E5. Ele não define stack de produção, UX ou G2.

## 1. Regras de evidência

Uma cadeia nunca implica a próxima: `CONFIGURED ≠ ARMED_VERIFIED ≠ TRIGGERED ≠ SOFTWARE_AUDIO_STARTED ≠ PHYSICAL_AUDIO_OBSERVED ≠ HUMAN_AWAKE`.

- Cada tentativa tem protocolo e cenário pré-registrados, occurrence/generation, célula, precondições e oráculo.
- `PASS`, `FAIL`, `UNKNOWN/INCONCLUSIVE`, `NOT_TESTABLE/N/A` e `ENVIRONMENT_BLOCKED` são resultados distintos. Ausência de artefato não é PASS.
- Alterar threshold, exclusão ou método depois de ver o resultado cria nova rodada/versionamento; não reescreve a rodada anterior.
- Emulator prova modelo/API/lifecycle no ambiente emulado, nunca alto-falante, OEM físico ou taxa populacional.
- Device farm só vale para os estados que permitir reproduzir e observar. Sem controle verificável de reboot bloqueado, DND, rota, microfone externo ou energia, o cenário fica fora da conclusão.
- Nenhuma etapa usa dados pessoais, única unidade usada como despertador real ou voz/nome reais.

## 2. Estágios E0–E5

### E0 — MODEL / JVM

- **Objetivo:** provar determinismo de hora civil, DST, generation, tombstones, late recovery, snooze, concorrência e reconciliação.
- **APIs:** modelo agnóstico; fixtures equivalentes a regras relevantes de 31–37.
- **Estados:** todos os estados e transições; clocks e eventos injetados.
- **Repetições:** casos determinísticos uma vez por fixture; property/fuzz com pelo menos 10.000 sequências por seed suite e 10 seeds registradas.
- **Métricas/instrumentação:** transições, invariants I-01–I-14, tempos sintéticos, geração de contraexemplos.
- **Evidência:** relatório por fixture/seed, trace mínimo reproduzível e hash da versão.
- **Aprovação:** zero violação de invariant e zero estado inalcançável necessário; todo contraexemplo reduzido e resolvido ou vira blocker.
- **Não conclui:** comportamento Android, scheduling, áudio, permissões ou OEM.

### E1 — ANDROID EMULATOR

- **Objetivo:** verificar integração com contratos Android, lifecycle, permissões e eventos reproduzíveis.
- **APIs:** 31, 34, 35, 36 e 37; target do harness registrado, com variantes necessárias para mudanças de comportamento.
- **Estados:** normal/locked/screen-off simuláveis, Doze comandado, grants, time/timezone, process kill, crash, package replace e restore sintético.
- **Repetições:** 3 SMOKE por cenário/API; depois 10 FAILURE-INJECTION por fronteira crítica; 30 STABILITY para cenário crítico promovido.
- **Métricas/instrumentação:** r/a, readiness, reconciliation, dumps/trace e logs estruturados; áudio apenas digital/interno.
- **Evidência:** EVID IDs, snapshots de configuração, logs brutos e artefatos de cada falha.
- **Aprovação:** zero S0; thresholds internos cumpridos; nenhuma dedução de áudio físico.
- **Não conclui:** audibilidade, potência/rota real, firmware OEM, comportamento sem virtualização ou reliability populacional.

### E2 — SINGLE PHYSICAL REFERENCE DEVICE

- **Objetivo:** observar caminho real trigger→som→controle num aparelho de referência próximo de AOSP.
- **APIs:** primeiro API 37; depois uma célula de piso API 31 quando hardware/build existir. API intermediária entra por risco identificado em E1.
- **Estados:** normal idle, tela bloqueada/apagada, Doze, saver, morte normal, reboot com/sem unlock, permissões, volume/DND, rotas, crash e sessão de 30 min.
- **Repetições:** 3 SMOKE; 30 STABILITY por cenário S0/célula; 10 por ponto de FAILURE-INJECTION. Áudio físico em toda tentativa que afirme audibilidade.
- **Métricas/instrumentação:** todos os timestamps; microfone/detector externo; vídeo/controle quando necessário; sessões com e sem USB/debugger.
- **Evidência:** registro completo EVID, áudio bruto/checksum, detector/calibração e resultados por ocorrência.
- **Aprovação:** zero S0 sob precondições; nenhum UNKNOWN no claim acústico; bandas congeladas respeitadas.
- **Não conclui:** outro OEM/build, população real, pessoa acordada ou G2.

### E3 — MULTI-OEM

- **Objetivo:** medir divergências de firmware, energia, lockscreen, notificações, rotas e lifecycle.
- **APIs:** builds disponíveis dentro de 31+; incluir ao menos referência/Pixel, Samsung/One UI e Xiaomi/Redmi/POCO. Quarto OEM somente com evidência de relevância.
- **Estados:** suíte E2 mais modos OEM documentados, swipe, auto-start/pausa quando existentes e atualização de build.
- **Repetições:** 3 SMOKE por cenário novo; 30 STABILITY para cada cenário S0 que compõe a célula; 10 de falha injetada quando aplicável.
- **Métricas/instrumentação:** igual a E2, estratificada por fingerprint; device farm apenas para subconjunto observável.
- **Evidência:** resultados não agregados entre OEMs, divergências e exclusões justificadas.
- **Aprovação:** cada célula candidata passa sua suíte; falha de um OEM não é diluída pela média dos demais.
- **Não conclui:** modelos/builds não ensaiados ou compatibilidade global da marca.

### E4 — LONG-RUN / SOAK

- **Objetivo:** revelar falhas raras, drift, quotas, recorrência, recursos e recuperação sem ajuda diária.
- **APIs:** cada célula que pretenda chegar a E5.
- **Estados:** recorrência offline, noites sem abrir app, Doze natural, 30 min, soneca, reboot programado e cenário normal sem debugger.
- **Repetições:** mínimo 100 ocorrências por célula durante pelo menos 14 dias, incluindo 20 execuções naturais desacopladas de USB/debugger; cenários especiais continuam com N próprio.
- **Métricas/instrumentação:** coorte bruta, falhas/UNKNOWN, latências, duração, recursos e evidência acústica amostrada conforme protocolo pré-registrado; claims acústicos exigem observação em todas as tentativas contabilizadas para esse claim.
- **Evidência:** diário imutável EVID, artefatos brutos, uptime e mudanças ambientais.
- **Aprovação:** zero S0 não explicado; nenhum defeito de duplicação/controle; UNKNOWN abaixo de limite pré-registrado para o claim ou rodada inconclusiva.
- **Não conclui:** taxa populacional, probabilidade de falha zero ou pessoa acordada.

### E5 — PRE-BETA RELIABILITY ENVELOPE

- **Objetivo:** decidir células que podem receber o rótulo `VALIDATED`.
- **APIs:** somente células físicas que passaram E2/E3/E4; a faixa 31+ não entra por herança.
- **Estados:** suíte crítica completa e regressões específicas da célula.
- **Repetições:** pelo menos 300 ocorrências qualificadas por célula acumuladas em rodadas pré-registradas, com ≥30 para cada cenário S0 aplicável; executar novamente após correção que afete o caminho.
- **Métricas/instrumentação:** dicionário congelado, intervalos e coorte/exclusões transparentes.
- **Evidência:** dossiê de célula, matriz requisito→T-ID→EVID, falhas abertas e parecer explícito.
- **Aprovação:** zero falha crítica não resolvida, zero falsa afirmação de `ARMED_VERIFIED`, controles acessíveis e critérios quantitativos cumpridos; decisão do fundador inclui a célula no envelope.
- **Não conclui:** suporte a versões, modelos, rotas ou estados ausentes; nem “99,9%” sem desenho estatístico próprio.

## 3. Classes e disciplina de repetição

| Classe | Mínimo proposto | Uso legítimo | Regra para S0 |
| --- | --- | --- | --- |
| SMOKE | 3 por cenário/célula/API | Confirmar que o protocolo e a instrumentação funcionam | Qualquer S0 interrompe promoção; não mede estabilidade |
| STABILITY | 30 por cenário crítico/célula | Ver recorrência imediata e distribuição de latência | Zero S0; falha reabre causa e rodada |
| FAILURE-INJECTION | 10 por fronteira/ponto de corte/célula pertinente | Crash, I/O, duplicação e eventos concorrentes | Zero estado enganoso, replay terminal ou perda não contabilizada |
| SOAK | 100 por célula, ≥14 dias, ≥20 naturais sem USB | Expor drift/raridades sob operação repetida | Zero S0 não explicado; UNKNOWN nunca contado como sucesso |
| PRE-BETA | 300 ocorrências qualificadas por célula no dossiê | Decidir envelope, não publicidade | Zero S0 aberto; toda exclusão pré-registrada |

Com zero falhas em N tentativas, pode-se reportar apenas a taxa **observada** e um intervalo com método declarado. A aproximação `3/N` para limite unilateral de 95% pressupõe independência e serve só como orientação; noites, builds e aparelhos são correlacionados. Não fazer alegação populacional com estes mínimos.

## 4. Matriz candidata de execução

### Emulator

| Célula | API | Finalidade principal |
| --- | --- | --- |
| EMU-31 | 31 | Piso Android 12, exact alarm e compatibilidade inicial |
| EMU-34 | 34 | FSI e mudanças de permissão relevantes |
| EMU-35 | 35 | Boot/FGS e force-stop atuais |
| EMU-36 | 36 | Regressão intermediária/target |
| EMU-37 | 37 | Lifecycle de áudio em segundo plano |

API 32/33 podem ser adicionadas por um risco ou mudança normativa específica; sua ausência da primeira malha não equivale a suporte por interpolação.

### Dispositivos físicos

| ID candidato | Família | Build/API alvo | Estágio | Situação |
| --- | --- | --- | --- | --- |
| PHY-REF-37 | Pixel/referência próxima de AOSP | API 37, fingerprint estável e patch registrado | E2–E5 | Modelo/disponibilidade OPEN |
| PHY-FLOOR-31 | Referência física do piso | API 31 preservada | E2/E5 | Hardware/build OPEN |
| PHY-SAM | Samsung / One UI | Uma versão dentro de 31+ escolhida após E1 | E3–E5 | Modelo/disponibilidade OPEN |
| PHY-XIA | Xiaomi / Redmi / POCO | Uma versão dentro de 31+ escolhida após E1 | E3–E5 | Modelo/disponibilidade OPEN |
| PHY-OEM4 | OEM adicional | Somente por evidência de distribuição/risco | E3–E5 | Não selecionado |

“Família” não qualifica todos os seus aparelhos. Cada modelo, variante e fingerprint é uma célula. Device farm pode ampliar API/OEM para scheduling, lifecycle, crash e UI quando fornecer controle e artefatos suficientes; reboot sem unlock, rotas, DND e áudio físico exigem capacidade demonstrada ou aparelho local.

## 5. Protocolo de evidência acústica física

Método primário proposto para E2–E5:

1. aparelho dedicado, posição/orientação/distância fixas e ambiente com ruído de fundo medido;
2. microfone ou detector externo ligado a um sistema de aquisição independente; segundo dispositivo é aceitável somente após calibrar clock, latência e drift;
3. Wake Core do harness usa marcador acústico sintético identificável, sem voz ou dado pessoal;
4. relógio externo e relógio do DUT são alinhados antes da rodada; registrar offset, drift e `epsilon`; repetir sem rede quando esse for o cenário;
5. detector por correlação/limiar identifica onset x; calibrar falso positivo com tentativas silenciosas e falso negativo com reprodução controlada;
6. conservar áudio bruto, configuração/calibração, resultado do detector, timestamp, checksum e vínculo ao EVID;
7. `physical_audio_observed=true` somente quando o oráculo externo detecta o marcador; callback, foco concedido, buffer consumido e áudio digital não bastam.

Testar o método primeiro como instrumento: silêncio, som conhecido, diferentes volumes, ruído e rota alternativa. USB/debugger pode alterar energia/lifecycle; repetir a suíte relevante desacoplada, usando aquisição externa contínua. O método prova emissão detectável no ponto do microfone, não percepção humana nem despertar.

## 6. Métricas congeladas

Valores temporais são `int64` em milissegundos e nullable; ausência exige `null_reason`. Enums são versionados. Toda tentativa inclui `evidence_level` e domínios de relógio.

| Métrica | Tipo/unidade | Origem | Significado | Limitação |
| --- | --- | --- | --- | --- |
| `scheduled_delivery_delta_ms` | int64 ms | r e T do Wake Core | atraso/antecipação do trigger válido | wall changes e epsilon podem torná-la inconclusiva |
| `trigger_to_software_audio_ms` | int64 ms monotônico | r→a instrumentados | handoff interno até avanço real | não prova saída física |
| `trigger_to_physical_audio_ms` | int64 ms | r→x, oráculo externo | latência do trigger ao onset detectado | laboratório; depende de sincronização/detector |
| `scheduled_to_physical_audio_ms` | int64 ms | T→x, oráculo externo | entrega acústica total versus horário resolvido | combina atraso de trigger e áudio; não substitui as duas causas separadas |
| `physical_audio_observed` | bool/nullable | detector externo | se marcador físico foi detectado | falso pos/neg devem ser calibrados; não prova pessoa acordada |
| `fallback_used` | bool + enum | seleção local | baseline substituiu enriquecimento | não registrar conteúdo omitido |
| `recovery_mode` | enum | reconciliador | NONE, RECOVERED_LATE, BOOT, CRASH, PERMISSION, TIME_CHANGE, RESTORE_CHECK | categoria não prova sucesso |
| `alarm_missed` | bool + enum | decisão + evidência | entrega confirmadamente perdida | ausência de log produz UNKNOWN, não true |
| `alarm_duplicate` | int count | ocorrência/sessão + oráculo | efeitos indevidos além do primeiro | múltiplas ocorrências legítimas não são duplicata |
| `snooze_delivery_delta_ms` | int64 ms | filho r/T | entrega do filho versus deadline de 5 min | reboot separa clocks; requer política registrada |
| `wake_session_duration_ms` | int64 ms monotônico | start/terminal | duração operacional até dismiss/snooze/timeout/interrupção | não mede tempo para acordar |
| `control_available` | bool por ação | apresentação + teste externo | dismiss/snooze acessíveis na célula | renderizar controle não prova acionabilidade |
| `readiness_state` | enum | avaliador | UNASSESSED/CHECKING/FULL/LIMITED/BLOCKED/UNKNOWN/STALE | snapshot, não garantia contínua |
| `readiness_checkpoint_age` | int64 ms | now−checkpoint | idade da última avaliação | idade sozinha não identifica mudança |
| `reconciliation_result` | enum | reconciliador | RECONCILED/NOOP/BLOCKED/PARTIAL/FAILED/UNKNOWN | evento recebido não implica sucesso |

Campos auxiliares obrigatórios: `outcome`, `evidence_level`, `scheduled_t`, `trigger_r`, `software_audio_a`, `physical_audio_x`, `epsilon_ms`, `occurrence_id`, `generation`, `test_id`, `scenario_id`, `cell_id`, `boot_id` e `policy_version`. `HUMAN_AWAKE` não é inferido nem coletado no G1.

## 7. Evidence IDs e registro

Formato imutável e sequencial por programa: `EVID-G1-NNNN`. Não reutilizar ID invalidado; emitir correção vinculada.

Cada registro aponta para:

- device id laboratorial pseudônimo, fabricante/modelo/variante, fingerprint/build/patch e API;
- target, versão/hash do harness e via de instalação;
- T-ID, versão do protocolo, cenário/fault IDs e cláusulas CT/I relacionadas;
- timestamp UTC, fuso, boot id, estados/precondições e falha injetada;
- resultado, metric set, classificação e justificativa de exclusão/N/A;
- artefatos brutos quando existirem, checksums, calibração e cadeia de correções.

IDs emitidos em G1.2: `EVID-G1-0001..0008`. Somente `0002..0003` são execução E0; `0004..0008` são preflights E1 bloqueados e não contêm comportamento Android. Índice e manifest em `evidence/g1/`.

## 8. Cobertura dos cenários obrigatórios

| Grupo | Cenários | Protocolos / estágio mínimo |
| --- | --- | --- |
| Base | normal idle, locked, screen off, offline, opcionais fora | T10/T11; E1→E2 |
| Energia/processo | Doze, saver, morte normal, force-stop | T07/T11; E1→E3 |
| Boot/tempo | reboot+unlock, reboot sem unlock, timezone, hora ±, gap/fold | T05/T06; E0→E3 |
| Capacidades | exact revogada, notifications off, FSI indisponível | T03/T04; E1→E3 |
| Áudio | volume zero, DND, Bluetooth/conexão perdida, mídia, chamada | T09; E2→E3 |
| Falha | crash antes do trigger/durante ringing, app update | T02/T07/T13; E0→E3 |
| Controle/capacidade | sobreposição, soneca, sessão 30 min | T08/T15; E0→E4 |
| Longitudinal | recorrência sem abrir app, recursos e drift | T15; E4→E5 |

Uma linha mapeada não é evidência executada. Combinações adversariais da matriz de falhas também entram no plano.

## 9. Prontidão, pré-requisitos e blockers

Não resta blocker **conceitual** para o harness. E0 foi construído e aprovado; antes de executar os estágios restantes ainda é obrigatório:

- E1: obter SDK/emulator/system images 31/34/35/36/37; escolher target e mecanismo do adapter descartável, implementar failpoints Android e registrar versão; isso não seleciona stack de produto.
- E2: confirmar aparelho dedicado, aquisição acústica, calibração/epsilon e retenção segura de artefatos.
- E3: obter modelos/builds concretos; indisponibilidade reduz células, nunca produz suporte inferido.
- E4/E5: pré-registrar limites de UNKNOWN, amostragem acústica e orçamento/duração; nenhum ensaio automático em telefone pessoal.

Blockers para **G1 PASS**: E1 não executado; hardware não escolhido; epsilon não calibrado; mecanismo de snooze pós-reboot e arbitragem de outputs ainda experimentais; elegibilidade/distribuição e lifecycle em API 37 não observados; nenhuma célula aprovada. O PASS E0 não remove qualquer blocker Android ou físico.

## 10. Próxima missão autorizável

**MISSÃO 05 — G1.3 ANDROID E1 ENVIRONMENT RECOVERY & BASELINE EXECUTION:** em ambiente com toolchain e imagens oficiais verificáveis, implementar somente o adapter Android descartável e executar E1 nas APIs 31, 34, 35, 36 e 37. Preservar o commit E0 como baseline; não iniciar E2/G2, UI de produto, stack de produção ou suporte físico.
