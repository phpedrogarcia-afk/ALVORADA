# ALARM STATE MODEL

ALVORADA — codinome. Semântica G1.1 de 2026-09-11; execução atualizada em 2026-09-12. **É contrato conceitual, não schema de produto.**
A motivação documental está em [R01/R09/R10/R25/R27](ANDROID-RELIABILITY-RESEARCH.md). Contrato CT-01–CT-10 em [RELIABILITY-CONTRACT.md](RELIABILITY-CONTRACT.md).

## Três eixos, não um booleano

1. **USER INTENT:** DRAFT, ENABLED, DISABLED, DELETED. Durável depois de salvar. Uma recorrência pode continuar ENABLED após dismiss de uma ocorrência.
2. **SYSTEM SCHEDULING OBSERVATION:** UNKNOWN, REQUESTING, REGISTERED, BLOCKED, INVALIDATED, CONSUMED. REGISTERED significa chamada concluída para generation conhecida; não introspecção contínua do SO.
3. **OCCURRENCE / SESSION:** estados abaixo. Somar flags de qualidade: BASELINE_ONLY, PRESENTATION_LIMITED, AUDIO_RISK, CONTROL_BLOCKED, OBSERVATION_STALE. Não multiplicar todos os estados em uma enumeração gigante.

DEGRADED é qualificador, não substituto de `ARMED_VERIFIED`/INVALIDATED/RINGING. Pode haver “scheduling REGISTERED + AUDIO_RISK”, que não autoriza o rótulo público completo. `OUTPUT_OWNER` e `OUTPUT_WAITING` são papéis de arbitragem entre ocorrências, não apagam identidades. Um callback inesperado não reativa intenção desabilitada.

## Persistência conceitual

Não é schema congelado. Necessidades mínimas:
- **P-I:** identificador, regra de horário/repetição, intenção, generation, política de fuso/DST e tombstone.
- **P-O:** occurrence_id, destino civil + instante/offset, clock-domain, boot de origem, relação de soneca, estado.
- **P-R:** resultados de readiness, wall/monotonic timestamp, boot/build/target/cell, capability snapshot, método/identidade do último pedido e resultado conhecido.
- **P-S:** sessão, ocorrências vinculadas, estágio de progressão, deadline máximo, ações e tombstone terminal.
- **P-E:** registro mínimo de resultado com evidência/UNKNOWN; sem conteúdo contextual.

Estados em memória não precisam todos de escrita síncrona. Fronteiras que evitam perda de intenção/reativação exigem durabilidade; instrumentação diagnóstica nunca deve travar áudio.

## Estados e transições permitidas

| Estado | Significado / invariant | Entradas e eventos possíveis | Saídas possíveis | Persistência | Crash / reboot |
| --- | --- | --- | --- | --- | --- |
| DRAFT | Edição não confirmada; sem promessa | Criar ou editar cópia | CONFIGURED ao salvar; descartar | Rascunho opcional, separado do alarme antigo | Não substituir silenciosamente alarme anterior |
| CONFIGURED | Intenção salva, nenhuma afirmação de armamento novo | Save; intent ENABLED | READINESS_CHECK_REQUIRED; DISABLED | P-I/P-O | Próxima execução inicia reconciliação |
| READINESS_CHECK_REQUIRED | Snapshot inexistente/obsoleto; não mostrar ARMED | Save, abrir, tempo, update, grant, sinais alterados | ARMABLE; BLOCKED; RECOVERY_REQUIRED | P-R marca avaliação pendente | Repetir avaliação; não restaurar check verde |
| ARMABLE | Condições locais verificadas, falta registro | Checks passam | ARMING; BLOCKED se perder condição | Snapshot P-R, P-I/P-O | Volta a check antes de confiar |
| ARMING | Pedido externo em trânsito; não é ARMED_VERIFIED | Solicitar scheduling | ARMED_VERIFIED se registro + persistência confirmados; BLOCKED por rejeição; RECOVERY_REQUIRED por ambiguidade | Journal de intenção/pedido P-R | Pode haver registro órfão; reconciliar por identidade/generation |
| ARMED_VERIFIED | Registro e readiness estavam aptos no checkpoint identificado | Sucesso de ARMING/reconciliação | TRIGGERING; READINESS_STALE; INVALIDATED; DISABLED | P-I/P-O/P-R + capability snapshot | É evidência passada, não monitoramento contínuo; novo boot exige reconciliar |
| READINESS_STALE | Checkpoint existe, mas perdeu atualidade por evento/build/boot/generation ou reconciliação incompleta | Evento relevante, retorno/renderização, mudança detectada | READINESS_CHECK_REQUIRED; BLOCKED; RECOVERY_REQUIRED | Motivo, evento e checkpoint anterior | Nunca reapresentar check verde antigo; não presume cancelamento no SO |
| BLOCKED | Condição conhecida impede promessa; intenção pode existir | Permissão negada, baseline inválido, controle/som inelegível | READINESS_CHECK_REQUIRED após reparo; DISABLED | Motivo + estado real do registro | Não inferir que SO foi cancelado; reavaliar |
| INVALIDATED | Registro anterior deixou de servir | Revogação conhecida, generation alterada, boot constatado | RECOVERY_REQUIRED; DISABLED | Motivo, generation, último checkpoint | App pode só detectar depois; não alegar detecção imediata |
| TRIGGERING | Evento válido recebido; som não comprovado | Callback da generation ativa e dentro da política de tempo | RINGING; OUTPUT_WAITING; RECOVERY_REQUIRED; MISSED confirmado; OUTCOME_UNKNOWN | P-S antes de efeitos quando viável + P-E | Reconciliar janela e terminal; crash não prova som ausente |
| OUTPUT_WAITING | Ocorrência due preservada, sem propriedade do output físico | Outro `OUTPUT_OWNER` ativo | RINGING ao adquirir output; RECOVERED_LATE; MISSED/UNKNOWN; DISMISSED apenas por ação com escopo | Fila/ordem, T próprio e identidade | A espera conta contra as bandas da ocorrência; não pode sumir na sessão de outra |
| RINGING | Evidência no app de reprodução em progresso; audibilidade física separada | Handoff válido; retomada permitida | SNOOZE_PENDING; DISMISSED; INTERRUPTED; UNANSWERED | P-S, estágio, deadlines; sem depender de cada frame persistido | Áudio para com processo; retomada não garantida |
| SNOOZE_PENDING | Pedido do usuário aceito para tentativa; filho ainda não confirmado | Snooze em sessão ativa | SNOOZED após filho registrado; BLOCKED/RECOVERY_REQUIRED | Vínculo pai-filho e deadline | Journal permite verificar se filho existe; não mostrar “adiado” prematuro |
| SNOOZED | Pai interrompido por ação; filho efetivamente agendado | Confirmação de scheduling filho | Filho: TRIGGERING; INVALIDATED; DISABLED | P-O filho + P-S pai | Mesmo boot mantém duração; reboot usa política aprovada, nunca elapsed antigo |
| DISMISSED | Ação explícita encerrou esta ocorrência | Dismiss válido de controle | Terminal; recorrência gera nova ocorrência separada | Tombstone antes de reativação; comando repetido idempotente | Callback tardio rejeitado; não retocar a mesma ocorrência |
| DISABLED | Intenção desativada ou removida | Desligar/excluir | Nova edição → CONFIGURED, nova generation | P-I tombstone; cancelamento externo reconciliável | Callback órfão não pode tocar |
| INTERRUPTED | Sessão teve interrupção conhecida | Falha de player/foco, stop do usuário identificado posteriormente | RECOVERY_REQUIRED; DISMISSED por comando; OUTCOME_UNKNOWN | Causa e nível de evidência | Não confundir stop-app com dismiss ou force-stop |
| RECOVERY_REQUIRED | Intenção e execução divergem ou são ambíguas | Crash, boot, update, registro incerto | READINESS_CHECK_REQUIRED se futuro; RECOVERED_LATE se atraso ≤10 min; MISSED/OUTCOME_UNKNOWN; DISABLED | P-I/P-O/P-R/P-S disponíveis | Recovery pode ser adiado pelo SO; sem garantia temporal |
| RECOVERED_LATE | Uma única tentativa iniciou após T, dentro de 10 min | Reconciliação com intenção ainda válida | RINGING; OUTPUT_WAITING; INTERRUPTED; DISMISSED; UNANSWERED | Causa, T original, atraso e evidência | Nunca reclassificar entrega pontual como sucesso |
| MISSED | Entrega pontual falhou com evidência suficiente | Deadline passou + observação confirmatória | Terminal; eventual catch-up ligado, marcado tardio | P-E com causa/evidência | Não reescrever falha como sucesso se recuperação tardia tocar |
| OUTCOME_UNKNOWN | Não há prova conclusiva do resultado | Log incompleto, crash, observador ausente | Refinar para resultado sustentado, sem apagar evidência original | P-E incerteza | Não contar como sucesso; não repetir som só para “confirmar” |
| UNANSWERED | Sessão chegou a M sem ação explícita | Timeout validado, áudio observado no app | Terminal; próxima ocorrência independente | P-S/P-E | Não significa pessoa dormiu; não é automaticamente MISSED |

“DISMISSED” não prova pessoa acordada; “RINGING” não comprova nível acústico; “SNOOZED” não é intenção vaga de agendar; “EVENT_RECEIVED” não prova reconciliação concluída.

### Transições globais e prioridade

As saídas da tabela são o fluxo ordinário. Em qualquer estado não terminal, desativar/excluir a intenção leva a DISABLED e solicita cancelamento/stop; falha de persistência leva a RECOVERY_REQUIRED sem impedir stop. Perda de informação leva a OUTCOME_UNKNOWN, não sucesso. Em BLOCKED por áudio/apresentação, um callback ainda válido pode entrar em TRIGGERING com flags de risco para tentativa local segura; BLOCKED por permissão sem callback não inventa esse evento. Generation/tombstone são avaliados antes dessas transições. Terminais não reabrem; correção de evidência acrescenta registro auditável.

Recorrência e sessão atual são independentes: resolver/persistir a próxima ocorrência não deve depender de dismiss, de usuário abrir o app ou de job de contexto. O trigger/reconciliador deve assegurar essa continuidade sem colocar trabalho opcional ou a preparação da próxima manhã antes do som atual. Crash nesse avanço exige journal/reconciliação; T02/T15 devem demonstrar que uma noite sem resposta não desarma silenciosamente as seguintes.

## Reconciliação e efeitos

- **I-01:** só generation ativa e intenção ENABLED podem iniciar ocorrência nova.
- **I-02:** cada ocorrência tem identidade distinta no SO; extras não são chave.
- **I-03:** UI não mostra `ARMED_VERIFIED` antes do registro + checkpoint; pedido ambíguo permanece UNKNOWN/RECOVERY_REQUIRED.
- **I-04:** deduplicar callback e comando; uma sessão ativa, sem som sobreposto para a mesma ocorrência.
- **I-05:** tombstone de dismiss/disable prevalece sobre recuperação/callback antigo.
- **I-06:** falha de Morning Intelligence não muda estado de scheduling.
- **I-07:** após reboot não reutilizar deadline monotônico do boot anterior.
- **I-08:** efeito acústico e persistência não são transação única; admitir UNKNOWN.
- **I-09:** ausência de resposta não autoriza escalada ilimitada ou volume além do teto.
- **I-10:** uma ocorrência falhada continua falhada mesmo que outra ocorrência tenha som.
- **I-11:** checkpoint pertence a boot/build/generation/cell; evento relevante o torna stale até reconciliação concluída.
- **I-12:** `EVENT_RECEIVED` e `RECONCILED` são evidências diferentes.
- **I-13:** no máximo um `OUTPUT_OWNER`; cada `OUTPUT_WAITING` conserva T, identidade e resultado próprios.
- **I-14:** CONFIGURED, ARMED_VERIFIED, TRIGGERED, PHYSICAL_AUDIO_OBSERVED e HUMAN_AWAKE nunca são inferidos uns dos outros.

Proposta para falha de gravação de dismiss: parar o som por segurança imediata, mostrar que alteração não pôde ser salva e não confirmar mudança de recorrência. Recuperação deve preferir não reativar sessão ambígua encerrada; risco residual exige ensaio e decisão antes de uso real. A indisponibilidade de armazenamento não pode prender o usuário em som interminável.

Proposta para soneca que não consegue agendar: interromper o som conforme ação do usuário, exibir “não foi possível adiar”, manter vínculo pendente para reparo, nunca retomar brutalmente. O trade-off entre interrupção e continuidade segue OPEN; a duração de cinco minutos e o escopo occurrence-owned estão decididos.

## Eventos e reconciliação

O modelo registra `EVENT_RECEIVED` antes de agir e um resultado separado: `RECONCILED`, `NOOP`, `BLOCKED`, `PARTIAL`, `FAILED` ou `UNKNOWN`. `LOCKED_BOOT_COMPLETED`, `BOOT_COMPLETED`, `TIME_CHANGED`, `TIMEZONE_CHANGED`, package replace/update, alterações de exact alarm/notification/FSI, app startup, edit, snooze, dismiss e crash recovery seguem a tabela normativa de [POLICY-FREEZE.md](POLICY-FREEZE.md). Eventos concorrentes usam a mesma fila idempotente por generation; nenhum deles copia um estado ARMED anterior.

O checkpoint contém timestamp, boot id, build/target/cell, IDs/generation, T/fuso/offset e snapshot das capacidades verificáveis. Não existe TTL universal: revalidar por evento e em toda renderização/ação; no trigger, apenas checks locais não bloqueantes. Enquanto o processo não executa, “verificado em c” não vira “garantido agora”.

## Traços adversariais de especificação

| Traço | Erro ingênuo | Resultado exigido / teste |
| --- | --- | --- |
| Save → registro SO → crash antes de ACK local | Criar outro alarme ao reiniciar | Mesma identidade/generation, reavaliação; T01/T02 |
| Check exato → revogação → callback esperado | Tratar booleano salvo como garantia | BLOCKED/INVALIDATED na próxima observação; sem callback prometido; T03 |
| DISMISSED → evento duplicado atrasado | Recomeçar a tocar | Tombstone vence; T08 |
| Snooze → crash entre filho e confirmação | Exibir adiamento inexistente ou dois filhos | Journal + deduplicação; T08 |
| Boot → CE indisponível | Aguardar senha ou inicializar voz pessoal | E-DB mínimo ou readiness bloqueada, não promessa falsa; T05 |
| Relógio volta após dismiss | Repetir manhã já atendida | Identidade civil/política mantém terminal; T06 |
| Relógio avança além de T | Som horas depois | W/UNKNOWN explícitos; T06 |
| Dois alarmes → sessão compartilhada → dismiss | Segundo alarme desaparecer do histórico | Resultado por ocorrência; T08 |
| Crash durante som → restart tardio | Retomar no volume máximo fora da janela | Guardas de M/W/tombstone e teto; T07 |
| Boot → duas notificações de recovery → grant | Concorrência de três reconciliações | Convergência idempotente; T02/T05 |

O harness G1.2 executou esses traços modeláveis e property tests em E0 (`EVID-G1-0002..0003`). Isso não é model checking exaustivo e não testa efeitos Android; os demais traços continuam pendentes de E1–E3.
