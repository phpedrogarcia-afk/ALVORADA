# RELIABILITY CONTRACT

ALVORADA — codinome. Atualizado em 2026-09-12. **G1 CONDITIONAL; policy v0.1 congelada; E0_PASS / E1_CONDITIONAL.**
Autoridade: Constituição G0 e decisões do fundador. Nenhum hard invariant foi enfraquecido.
Fontes dos fatos Android: [ANDROID-RELIABILITY-RESEARCH.md](ANDROID-RELIABILITY-RESEARCH.md).
Políticas temporais, Direct Boot, retenção e plano experimental: [POLICY-FREEZE.md](POLICY-FREEZE.md) e [EVIDENCE-PLAN.md](EVIDENCE-PLAN.md).

## 1. A promessa de “armado”

**CT-01 — ARMED_VERIFIED:** “No checkpoint indicado, a intenção desta ocorrência estava salva, as condições verificáveis estavam aptas e o agendamento exato foi aceito pelo Android para o horário mostrado. O som básico local estava preparado e a entrega não dependia de serviços opcionais. Desde então, condições externas podem mudar; o estado deve ser revalidado nos eventos e oportunidades definidos.”

`ARMED_VERIFIED` é uma **afirmação temporal sobre o último checkpoint**, não reserva irrevogável no SO, prova de som futuro ou prova de pessoa acordada. `READINESS_STALE` substitui o rótulo completo quando evento, build/boot/generation ou falha de reconciliação invalida sua atualidade. Ao renderizar o estado, revalidar sinais disponíveis; se não puder, exibir “precisa verificar”, não verde antigo. Não existe observador infalível enquanto app/SO estão parados.

Hoje, envelope validado vazio: E0 confirmou a coerência do modelo, não o contrato Android. Não houve alarme real armado nem cenário E1.

## 2. Supported envelope / preconditions

[SUPPORTED-ENVELOPE.md](SUPPORTED-ENVELOPE.md) é a única autoridade para células qualificadas. CT-01 exige intenção durável, ocorrência/generation correspondentes, readiness sem bloqueio, registro sem erro, fallback local íntegro e controles aptos. E-P0 é hipótese de ensaio; não é escolha definitiva de minSdk, aparelhos ou target.

**CT-02 — não mascarar impossibilidade:** permissão exata ausente impede rótulo ARMED_VERIFIED; salvar configuração continua permitido. Não trocar por alarme inexato e manter a mesma promessa. Bloqueio de som/controle pode coexistir com agendamento registrado: remover rótulo completo, preservar tentativa futura já autorizada, orientar reparo.

## 3. Delivery semantics

**CT-03 — entrega mínima:** ao receber ocorrência válida, iniciar sessão local e controles sem esperar internet, LLM, backend, login, sincronização, analytics, clima, calendário, geração de voz ou download. Base sonora local e Escalada Serena são responsabilidades do Wake Core; a versão enriquecida não é requisito.

**CT-04 — resultado honesto:** distinguir receiver recebido, sessão criada, reprodução solicitada, evidência de avanço do áudio, controles apresentados, áudio observado externamente e ação humana. Não marcar sucesso porque um método retornou sem erro. Sem prova suficiente, resultado UNKNOWN; não inventar MISSED nem DELIVERED.

**CT-05 — identidade e concorrência:** `occurrence_id` + `generation` + identidade própria do agendamento; no máximo um `OUTPUT_OWNER` físico por vez. Repetição do mesmo evento não cria outra sessão nem reinicia a escalada. Alarmes distintos são contabilizados separadamente; ocorrência due durante outra sessão entra `OUTPUT_WAITING`, e sua espera conta no próprio timing. Dismiss/snooze de A jamais encerra ou altera B. A arbitragem/UX entre mesclar e enfileirar continua OPEN.

Não há promessa de exactly-once entre armazenamento local, SO e efeito acústico. Propõe-se reconciliação idempotente e deduplicação de efeitos, com falhas/duplicações observáveis.

## 4. Timing semantics

Definições: T = instante resolvido; r = trigger válido recebido; a = avanço interno comprovado no pipeline de áudio; x = onset físico observado externamente. Tempo monotônico mede durações no mesmo boot; tempo civil resolve destinos. Os valores abaixo estão congelados como **thresholds experimentais**, não SLA Android ou promessa ao usuário.

| Medida | TARGET | ACCEPTABLE | FAILURE | UNKNOWN/INCONCLUSIVE |
| --- | --- | --- | --- | --- |
| `r−T` | 0 a +2.000 ms | −500 a <0 ms como `EARLY_TOLERANCE`; >2.000 a +5.000 ms como `ACCEPTABLE_LATE` | <−500 ms ou >+5.000 ms | Incerteza cruza limite ou clock-domain inválido |
| `a−r` | ≤1.000 ms | >1.000 a 3.000 ms | >3.000 ms ou falha interna confirmada | Marco interno ausente/ambíguo |
| `x−r` | ≤1.000 ms | >1.000 a 3.000 ms | >3.000 ms ou ausência acústica confirmada | Oráculo externo ausente/inválido |

As duas bandas são julgadas separadamente: `a` não substitui `x`. O timing acústico completo também registra `x−T`, sem confundi-lo com delivery do trigger. Duplicação indevida, impossibilidade de parar e falso `ARMED_VERIFIED` são falhas funcionais independentemente da latência.

### Política temporal aceita F-03-02–F-03-05

- Alarmes comuns representam hora civil no fuso atual; cada recorrência resolve uma ocorrência one-shot, nunca soma fixa de 24 horas. Alarmes vinculados a fuso específico ficam fora do primeiro escopo.
- Gap DST: primeiro horário civil válido após a lacuna, com ajuste registrado. Fold: primeiro offset válido e uma única ocorrência.
- Mudança de fuso recalcula futuros; avanço do relógio que atravessa T entra em late recovery; retrocesso não repete ocorrência terminal; locale só muda apresentação.
- Se capacidade retorna entre T e T+10 min inclusive, tentar uma única vez como `RECOVERED_LATE`. Depois disso, não tocar de surpresa; usar MISSED somente com evidência, senão OUTCOME_UNKNOWN.
- Soneca é filha de cinco minutos; mesmo boot usa monotônico. Reconstrução pós-reboot e mecanismo Android continuam experimentais e precisam de evidência.

Detalhe normativo e reparos de fronteira: [POLICY-FREEZE.md](POLICY-FREEZE.md).

## 5. Recovery semantics

**CT-06 — reconciliar, não copiar ARMED_VERIFIED:** ao boot, update, retorno de permissão, abertura, alteração de tempo ou retomada após falha, confrontar intenção/generation com readiness e registros locais; restabelecer somente ocorrências válidas. Snapshot antigo não é prova de registro atual.

**CT-07 — persistência e crash:** salvar intenção antes de agendar; salvar resultado depois. Não existe transação atômica com AlarmManager. Queda entre etapas produz RECOVERY_REQUIRED; callbacks carregam identidade suficiente para reencontrar intenção. Cancelamento/dismiss geram tombstone durável antes de permitir reativação por callback tardio. Registro de diagnóstico não pode bloquear áudio; registro mínimo operacional não é analytics.

**CT-08 — boot:** Direct Boot faz parte do target experimental. Manter somente horários/identidades/controles/fallback operacional mínimo em device-protected storage, sem nome, agenda, localização, frases ou voz pessoal; restante credential-protected. Reconciliar por `LOCKED_BOOT_COMPLETED`/`BOOT_COMPLETED` e registrar resultado separado do evento. Não iniciar mediaPlayback do receiver de boot como atalho; retorno próximo ao deadline é célula de risco a testar.

**CT-09 — crash enquanto toca:** interromper áudio é falha de continuidade. Na próxima oportunidade legal, reconciliar sessão, checar tombstone, janela tardia de 10 min e limite operacional de 30 min; tentar retomada limitada sem explosão de volume ou laço. Não prometer restart via serviço sticky ou watchdog. Se não houver oportunidade, resultado permanece desconhecido até revisão; documentação não cria ressurreição.

## 6. Degraded states / falhas visíveis

Degradação tem eixos separados: enriquecimento, apresentação, som, scheduling e evidência. Sem clima/voz enriquecida → omissão silenciosa. Sem FSI → apresentação alternativa **se validada**, sem parar som. Sem canal/notificação/volume apto → “configurado com problema”, não promessa completa. Sem permissão exata → configuração não armada.

Falhas de infraestrutura essenciais devem aparecer durante configuração/próxima abertura com instrução útil; HI-03 proíbe narrar erros opcionais durante o despertar, não proíbe informar que o núcleo não está apto. Não solicitar permissão nem explicar stack durante uma sessão.

## 7. Uncontrolled conditions

[Envelope](SUPPORTED-ENVELOPE.md) explicita desligamento, force-stop, perfil parado, restrições OEM, hardware, foco/rotas e alterações externas. **CT-10:** quando detectável, mostrar estado real; quando só detectável depois, registrar atraso de observação; quando indetectável, comunicar limite do suporte. Não criar notificação remota, alarme secreto, overlay ou serviço permanente para driblar controles do usuário.

## 8. Wake Core / Morning Intelligence

| Responsabilidade | Wake Core | Morning Intelligence |
| --- | --- | --- |
| Autoridade | Intenção, readiness, ocorrência, agendamento, reconciliar, trigger | Nenhuma autoridade de armar/cancelar |
| Runtime crítico | Lifecycle permitido, som local, progressão segura, controles, soneca, dismiss, resultado mínimo | Não executa consulta/geração exigida pelo disparo |
| Conteúdo | Baseline local coerente e leitor defensivo de artefatos prontos | Pré-prepara texto/voz/clima/agenda/mensagem/reflexão/atmosfera |
| Falha | Estado explícito ou recuperação limitada | Omissão; não pode segurar lock ou transação do núcleo |
| Dados | Mínimo operacional local | Dados opcionais com autorização e validade próprias |

Interface provisória **WakePlan**: snapshot local opcional e somente leitura para o disparo. Não se congela schema, banco, DI ou biblioteca. O plano não determina se o alarme existe. Recursos compartilhados (CPU, armazenamento, inicialização do processo, decoder) também são fronteiras: preparação não pode provocar ANR/OOM ou bloqueio que impeça o núcleo. Isolamento concreto ainda OPEN.

## 9. Precomputation — H-G1-03

Reformulação: “Todo enriquecimento que for usado deve estar pronto e íntegro localmente antes da janela crítica; nenhum enriquecimento é necessário para entregar o despertar básico.”

| Aspecto | Especificação candidata |
| --- | --- |
| Quando | Após configuração/edição e em oportunidade anterior ao próximo despertar; trabalho adiável pode nunca rodar |
| Prazo | Publicação deve terminar antes de T−C; C é margem a medir, não timer remoto obrigatório |
| Configuração em cima da hora | Se já dentro de C, usar baseline; antecedência mínima A de armar continua separada |
| Fallback | Baseline distribuído localmente, não download nem TTS tardio; se impossível verificar baseline ao armar, readiness bloqueada |
| Validade | Por fragmento: finalidade, ocorrência/generation, relógio/fuso, consentimento, fonte e expiração |
| Stale | Omitir fragmento vencido/conflitante; hora narrada obsoleta também é stale |
| Atualização | Publicação atômica de versão completa; não alterar snapshot em uso |
| Integridade | Limites de tamanho, formato e duração; checksum/legibilidade; falha troca por baseline sem bloquear início |
| Revogação | Invalidar fragmentos afetados e apagar conforme política; agendamento não depende deles |
| Sem plano | Caminho normal de baseline; voz/nome indisponíveis podem ser omitidos sem substituir o som |

A hipótese não é que haverá uma janela garantida de preparação Android. R30/R31 mostram por que ela pode faltar. C e TTLs por categoria permanecem OPEN; TTL específico pertence a G3.

## 10. Telemetria e métricas locais

| Métrica (definição, não resultado) | Registro/uso |
| --- | --- |
| scheduled_delivery_delta_ms | r−T; nulo com reason quando clock-domain inválido |
| trigger_to_software_audio_ms | a−r em monotônico; avanço interno, não audibilidade |
| trigger_to_physical_audio_ms | x−r no laboratório; não inferir via callback |
| scheduled_to_physical_audio_ms | x−T no laboratório; entrega acústica total, separada das causas |
| physical_audio_observed | detecção externa calibrada; não prova pessoa acordada |
| wake_session_started | ocorrência + sessão; não equivale a áudio ou usuário acordado |
| fallback_used | motivo categórico; sem conteúdo pessoal |
| recovery_required | motivo, instante detectado, generation e último checkpoint |
| alarm_missed | falha confirmada + origem da evidência; separado de outcome_unknown |
| outcome_unknown | falta de observação conclusiva; conta como inconclusivo, não sucesso |
| snooze_delivery_delta_ms | entrega da ocorrência filha menos deadline da duração |
| permission_readiness_state | bitmap/códigos + instante, sem pacote de apps ou identidade externa |
| control_action | dismiss/snooze + latência; sem inferir estado de sono |
| duplicate_session / control_failure | contagem por ocorrência; defeitos críticos |
| delivery_rate / unknown_rate | coorte de ocorrências, sem eliminar falhas posteriores ao armamento |

**Privacidade F-03-14:** eventos mínimos locais, identificadores aleatórios locais, nenhum nome/fala/agenda/localização/conteúdo de WakePlan em logs. Rotação em 30 dias ou 1.000 eventos, o que ocorrer primeiro, e limpeza pelo usuário; essas rotinas não podem disputar caminho crítico. Envio remoto permanece OPEN. Backup/restore nunca transporta estado `ARMED_VERIFIED` como se o registro do SO permanecesse válido.

## 11. Julgamento do gate

**CONDITIONAL**, não PASS: contrato/políticas existem e E0 passou, porém o envelope validado está vazio e nenhuma célula Android foi executada. `READY_FOR_INSTRUMENTED_EVIDENCE = YES`; G2 não é liberado.

Missão seguinte recomendada: **MISSÃO 05 — G1.3 ANDROID E1 ENVIRONMENT RECOVERY & BASELINE EXECUTION**, limitada ao adapter descartável e à matriz E1 31/34/35/36/37. Não iniciar E2/G2. Testabilidade: [TEST-PROTOCOL.md](TEST-PROTOCOL.md) e [EVIDENCE-PLAN.md](EVIDENCE-PLAN.md).
