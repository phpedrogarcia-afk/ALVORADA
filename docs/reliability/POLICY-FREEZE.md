# POLICY FREEZE — G1.1

ALVORADA — codinome. 2026-09-11. **Políticas v0.1 congeladas para obtenção de evidência; não são fatos de desempenho nem promessa comercial.**

G0 = PASS. G1 = CONDITIONAL. `READY_FOR_INSTRUMENTED_EVIDENCE = YES`. O envelope validado continua vazio e G2 permanece bloqueado.

## 1. Autoridade e significado de “congelado”

Este documento registra as decisões F-03-01–F-03-15 do fundador. “Congelado” significa: o primeiro harness deve implementar e testar esta semântica sem ajustá-la depois de observar resultados. Um valor marcado **EXPERIMENTAL** é fixo para a primeira rodada, mas pode ser reaberto por evidência e nova decisão. `FACT` continua reservado a resultado demonstrado.

| ID | Política congelada | Status epistêmico |
| --- | --- | --- |
| F-03-01 | Investigar Android 12/API 31+; suporte somente após evidência | DECISION; faixa candidata, não suportada |
| F-03-02 | Alarmes comuns seguem hora civil local no fuso atual | DECISION |
| F-03-03 | Gap DST: primeira hora civil válida após a lacuna; registrar ajuste | DECISION |
| F-03-04 | Fold DST: primeira ocorrência válida, exatamente uma vez | DECISION |
| F-03-05 | Recuperar imediatamente até 10 min inclusive; depois registrar MISSED e não tocar | DECISION; janela EXPERIMENTAL |
| F-03-06 | Bandas de entrega: alvo 0–2 s; aceitável até 5 s; falha acima de 5 s ou antecipação acima de 500 ms | DECISION; thresholds EXPERIMENTAIS |
| F-03-07 | Handoff observado: alvo até 1 s; aceitável até 3 s; falha acima de 3 s; callback não prova áudio físico | DECISION; thresholds EXPERIMENTAIS |
| F-03-08 | Soneca de 5 min, como ocorrência filha; recorrência original independente | DECISION; máximo de sonecas OPEN |
| F-03-09 | Dismiss encerra apenas ocorrência/sessão corrente | DECISION |
| F-03-10 | Sessão máxima de 30 min nos testes | DECISION; parâmetro operacional EXPERIMENTAL, não UX final |
| F-03-11 | Identidades independentes; um output físico por vez; colisões não podem desaparecer | DECISION; arbitragem/UX OPEN |
| F-03-12 | Direct Boot integra o target; alarme previamente armado deve ser investigado em reboot sem primeiro unlock | DECISION; conjunto exato de campos ainda candidato |
| F-03-13 | Restore nunca restaura `ARMED`; readiness precisa ser reconstruída; rearmar automaticamente fica proibido | DECISION |
| F-03-14 | Telemetria de reliability local-first, 30 dias ou 1.000 eventos, o que vier primeiro; limpeza pelo usuário | DECISION; envio remoto OPEN |
| F-03-15 | Uma missão futura pode construir harness descartável, sem UX, stack ou features de produto | DECISION; não autoriza produto nem execução nesta missão |

## 2. Modelo congelado de tempo civil

Uma configuração comum persiste uma **regra civil**, não apenas um instante UTC: hora local, dias aplicáveis, calendário, política DST, `generation` e identidade da ocorrência. Para cada próxima data, o sistema resolve novamente a regra usando o fuso atual do dispositivo e guarda também o instante, offset e versão/identidade das regras de zona observadas.

- Mudança legítima de fuso invalida a resolução futura e exige nova `generation`/ocorrência. Não move silenciosamente a intenção de “07:30” para outro horário civil.
- Alarmes presos a um fuso específico ficam fora do primeiro escopo.
- No **gap**, uma intenção para horário inexistente resolve para o primeiro instante cujo horário civil é válido após a lacuna. Exemplo sintético: gap 02:00–02:59; intenção 02:30 → 03:00. O evento recebe `dst_adjustment=GAP_FORWARD`.
- No **fold**, usar o offset da primeira ocorrência válida. A identidade é data civil + regra + `generation` + ordinal escolhido; o segundo offset não cria nova ocorrência.
- Avanço manual/automático que cruza T aciona late recovery. Retrocesso não reabre ocorrência terminal. Mudança de locale altera apresentação, nunca o destino.
- Durações dentro do mesmo boot usam relógio monotônico. Destinos civis e reconciliação entre boots usam pares wall/monotonic registrados; deadline monotônico antigo nunca é reutilizado após reboot.

## 3. Timing e classificação

Seja T o instante resolvido, r a recepção válida do trigger, a o primeiro marco interno que demonstra avanço real do pipeline de áudio e x o onset detectado externamente. Toda medição registra domínio de relógio e incerteza `epsilon`.

### Entrega agendada: `d = r − T`

| Intervalo observado | Classificação |
| --- | --- |
| 0 ≤ d ≤ 2.000 ms | TARGET |
| −500 ms ≤ d < 0 | EARLY_TOLERANCE — aceitável para a rodada, nunca TARGET |
| 2.000 ms < d ≤ 5.000 ms | ACCEPTABLE_LATE |
| d < −500 ms ou d > 5.000 ms | FAILURE |
| Intervalo de incerteza cruza um limite | INCONCLUSIVE_TIMING; calibrar/repetir |

O reparo `EARLY_TOLERANCE` fecha a lacuna lógica entre “TARGET começa em zero” e “antecipação maior que 500 ms falha”, sem promover antecipação a comportamento desejado.

### Trigger-to-audio: `h_sw = a − r` e `h_ph = x − r`

| Intervalo observado | Classificação, aplicada separadamente a software e física |
| --- | --- |
| h ≤ 1.000 ms | TARGET |
| 1.000 ms < h ≤ 3.000 ms | ACCEPTABLE |
| h > 3.000 ms ou ausência confirmada do efeito correspondente | FAILURE |
| Marco/oráculo ausente ou inválido | UNKNOWN |

Essas bandas qualificam separadamente `trigger_to_software_audio_ms` e `trigger_to_physical_audio_ms`. A primeira mede handoff interno; a segunda só existe com oráculo externo válido. Um PASS de software nunca satisfaz a banda física. A entrega acústica total `x−T` também é reportada, sem ser confundida com `scheduled_delivery_delta_ms`. `software_audio_start` nunca substitui `physical_audio_observed`.

## 4. Late recovery

Quando uma ocorrência ativa não foi executada em T e o reconciliador recupera capacidade:

1. calcular atraso contra o T originalmente resolvido;
2. se `0 ≤ atraso ≤ 10 min`, criar uma única tentativa `RECOVERED_LATE`, preservar a ocorrência original e registrar causa, evento e atraso;
3. se `atraso > 10 min`, não iniciar áudio; registrar `MISSED` somente se houver evidência suficiente de não entrega; caso contrário, `OUTCOME_UNKNOWN`;
4. qualquer ocorrência terminal, desabilitada ou com `generation` antiga nunca é recuperada;
5. informar o resultado na próxima interação adequada, sem transformar a manhã seguinte em alerta agressivo.

Recuperação tardia não reclassifica entrega pontual como sucesso. A janela de 10 minutos é experimental e não autoriza avalanche quando várias ocorrências venceram.

## 5. Soneca, dismiss e concorrência

- **Snooze:** a ação cria filho com novo `occurrence_id`, `parent_occurrence_id`, `generation`, checkpoint e destino de 5 minutos. O pai só vira `SNOOZED` quando o filho estiver efetivamente registrado. A recorrência original não muda. No mesmo boot, a duração usa monotônico; política de reconstrução após reboot será comparada no harness e permanece EXPERIMENTAL. Número máximo de sonecas é OPEN para G2.
- **Dismiss:** grava tombstone e encerra apenas a ocorrência/sessão indicada. Não desabilita regra, cancela futuros ou atinge outra ocorrência. Se persistência falhar, o stop físico continua prioritário; o resultado fica `RECOVERY_REQUIRED`, não confirmação falsa.
- **Concorrência:** ocorrências mantêm contabilidade e terminais próprios. Existe no máximo um `OUTPUT_OWNER`; outra ocorrência due entra `OUTPUT_WAITING`, sem ser descartada. Qualquer espera conta no timing da segunda ocorrência. Mesclar, enfileirar ou apresentar controles múltiplos permanece hipótese de UX/arbítrio, mas dismiss/snooze de A jamais encerra B.
- **Sessão máxima:** ao atingir 30 minutos sem ação, o output termina de modo seguro e a ocorrência recebe `UNANSWERED`; isso não prova que a pessoa dormiu nem acordou.

## 6. Estratégia Direct Boot

O cenário `REBOOT + NO_FIRST_UNLOCK + T` é parte do target experimental, nunca extensão por analogia de um teste após unlock.

Conjunto mínimo candidato em device-protected storage:

- `alarm_id`, `generation`, `occurrence_id` e relação pai-filho;
- regra civil, próxima ocorrência resolvida, fuso/offset e metadados de reconciliação;
- identificador de som fallback empacotado e não pessoal;
- metadados mínimos de controles, soneca de 5 min e limite operacional de 30 min;
- estado operacional, tombstones, checkpoint e versão mínima para leitura/migração.

Permanecem credential-protected e indisponíveis antes do primeiro unlock: nome, lembretes, agenda, localização, frases, histórico de mensagens, voz personalizada e enriquecimento. Se CE estiver inacessível, o Wake Core usa apenas `FALLBACK_WAKE_PLAN`. O conjunto de campos será validado por necessidade; “útil” não é justificativa para copiar dados pessoais a DE.

Restore/reinstall não transporta `ARMED`, registro do SO, checkpoint vigente ou tokens de agendamento. Readiness volta a `READINESS_CHECK_REQUIRED`; rearmamento automático após restore permanece proibido.

## 7. ARMED como evidência temporal

`ARMED` deixa de ser tratado como booleano atemporal. O modelo adota:

- **ARMED_VERIFIED:** no checkpoint `c`, intenção/generation/ocorrência estavam coerentes; capacidade exata, baseline, controles e célula candidata foram avaliados; o pedido de scheduling foi aceito e o resultado persistido.
- **READINESS_STALE:** existe checkpoint anterior, mas evento relevante, mudança de generation/build/boot ou falha de reconciliação retirou sua atualidade. Não exibir rótulo verde completo.
- **READINESS_CHANGED:** registro de que uma precondição observável divergiu; leva a `READINESS_STALE`, `BLOCKED` ou `RECOVERY_REQUIRED` conforme o efeito.
- **RECOVERY_REQUIRED:** intenção e efeitos externos podem divergir; nova afirmação depende de reconciliação concluída.

Todo checkpoint contém: timestamp wall + monotônico, boot id, app/build/target, cell id, `alarm_id`, `occurrence_id`, `generation`, T/fuso/offset, via/capacidade exata, baseline e storage acessíveis, estado de notifications/canal/FSI/controle, áudio/volume/DND/rota observáveis, política energética observável e resultado do pedido externo.

Não há TTL universal inventado. Revalidar antes de novo pedido; após cada evento relevante; em toda abertura/renderização do estado; antes de operação editável; e no trigger apenas com checks locais não bloqueantes que não atrasem som. Enquanto o app não executa, ele pode preservar apenas “verificado em c”, não “continuamente garantido”. Mudança detectada é comunicada na primeira oportunidade apropriada, com urgência proporcional à proximidade do próximo alarme e sem burlar controle do usuário.

## 8. Eventos de reconciliação

`EVENT_RECEIVED` é somente evidência de entrada. Cada execução termina em `RECONCILED`, `NOOP`, `BLOCKED`, `PARTIAL`, `FAILED` ou `UNKNOWN`, com evento, checkpoint anterior/novo e gerações afetadas.

| Evento | Reação mínima | Sucesso observável |
| --- | --- | --- |
| `LOCKED_BOOT_COMPLETED` | Ler somente DE, invalidar scheduling anterior, resolver e registrar ocorrências pré-unlock elegíveis | Novo checkpoint DE e registros aceitos; nunca inferir CE |
| `BOOT_COMPLETED` | Reconciliar DE/CE após disponibilidade, deduplicar trabalho de locked boot | Todas as intenções acessíveis convergem ou recebem motivo explícito |
| `TIME_CHANGED` | Recalcular futuros; aplicar late recovery aos T atravessados | Destinos e terminais consistentes, sem duplicação |
| `TIMEZONE_CHANGED` | Resolver de novo a regra civil no fuso atual; invalidar fragmentos temporais | Nova `generation`/T persistidos e registros antigos neutralizados |
| Package replace/update | Validar versão/migração, readiness e registros | Estado migrado e cada ocorrência reconciliada |
| Exact-alarm capability change | Marcar stale/bloqueado; no grant, reavaliar e registrar sem duplicar | Snapshot novo e resultado por ocorrência |
| Notification capability change | Reavaliar controles sem confundir com scheduling | Projeção FULL/LIMITED/BLOCKED atualizada |
| Full-screen capability change | Selecionar somente variante de controle já validada | Capability snapshot e superfície escolhida registrados |
| App startup | Comparar intent, geração, terminais, boot/build e capacidades | Convergência ou `RECOVERY_REQUIRED`; abrir app não apaga falha |
| Configuration edit | Incrementar `generation`, tombstone/cancelar ocorrência antiga e armar nova | Antiga não toca; nova só é verificada após ACK persistido |
| Snooze creation | Journal pai-filho, registrar filho, então parar/confirmar estado | Um único filho rastreável e pai terminal correto |
| Dismiss | Parar output, persistir tombstone occurrence-scoped e manter recorrência | Callback tardio rejeitado; outras ocorrências preservadas |
| Crash recovery | Ler journal/tombstones/deadlines e aplicar late/M sem ressurreição cega | Estado converge; ambiguidade permanece explícita |

## 9. Telemetria e backup

Telemetria operacional fica local por padrão e gira quando atingir **30 dias ou 1.000 eventos, o que ocorrer primeiro**. O usuário pode limpá-la. Nunca registrar por padrão nome, texto de lembrete, localização, calendário, frase falada, transcrição ou conteúdo de WakePlan. Envio remoto exige decisão futura. Artefatos sintéticos de laboratório seguem o registro de evidência, não a telemetria pessoal; sua retenção deve ser definida antes de E2.

## 10. Reparos e recusas da revisão adversarial

- Recusado: `ARMED` como estado continuamente verdadeiro. Substituído por afirmação vinculada a checkpoint e atualidade.
- Reparado: intervalo −500–0 ms ganhou classificação própria; não foi absorvido em TARGET.
- Reparado: threshold de 1/3 s é aplicado separadamente ao avanço interno e ao onset físico; um não aprova o outro.
- Recusado: restaurar ou copiar `ARMED_STATE` após boot, restore ou reinstall.
- Recusado: deduzir `MISSED` de ausência de log; usar `OUTCOME_UNKNOWN` quando o oráculo faltar.
- Recusado: concluir Direct Boot por broadcast simulado, CE desbloqueado ou callback do player.
- Mantido OPEN: método de snooze após reboot, arbitragem de outputs, máximo de snoozes, hardware concreto, epsilon e retenção de artefatos laboratoriais.

## 11. Decisão do gate

**G1 continua CONDITIONAL. READY_FOR_INSTRUMENTED_EVIDENCE = YES.** As políticas permanecem congeladas; G1.2 passou E0, mas E1 ficou bloqueado pelo ambiente. Isso não significa que qualquer célula Android seja suportada. A promoção de G1 exige concluir E1–E5 e aprovar explicitamente o primeiro envelope.
