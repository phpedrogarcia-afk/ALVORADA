# FAILURE MATRIX

ALVORADA — codinome. Atualizado em 2026-09-12. **Matriz de requisitos/expectativas G1.1; E0 lógico parcial executado, nenhuma célula Android/física executada.**
Fontes normativas e limites: [ANDROID-RELIABILITY-RESEARCH.md](ANDROID-RELIABILITY-RESEARCH.md).
Comportamento exigido é proposta contratual; “esperado” não é resultado medido.

## Convenções

- **Sim*/Esperado*** = obrigação a validar dentro da célula, com demais precondições satisfeitas; não garantia universal.
- **S0**: perda/risco do despertar, controle impossível ou promessa falsa; **S1**: degradação relevante; **S2**: perda opcional sem perda do núcleo.
- Classe descreve origem/dimensão predominante, não absolve defeito. Risco de origem USER/OS pode ter severidade S0.
- Estado é resultado lógico na primeira oportunidade de observação. Não se presume que app parado escreveu INVALIDATED em tempo real.
- Coluna “teste” identifica protocolo reproduzível; alguns componentes lógicos passaram E0, mas nenhuma linha inteira foi validada no Android. OEM_UNKNOWN requer build física; simulação não prova OEM. Nenhum depende de criar conta real ou usar agenda pessoal.
- Defeito do núcleo sob precondições válidas reprova a célula, mesmo quando o cenário é classificado OS_CONTROLLED.
- `ARMED_VERIFIED` descreve o último checkpoint. Evento recebido sem reconciliação concluída produz STALE/RECOVERY_REQUIRED, nunca confiança renovada.
- Thresholds de 10 min, 2/5 s, 1/3 s e sessão de 30 min estão congelados como experimentais em [POLICY-FREEZE.md](POLICY-FREEZE.md).

| FAULT-ID | Cenário | Precondição | Estado esperado | Alarme toca? | Enriquecimento disponível? | Ação automática | Ação do usuário | Detectabilidade | Teste possível? | Severidade | Classe |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F01 | Sem internet | Registro apto; baseline íntegro | ARMED_VERIFIED + BASELINE_ONLY | Sim* | Só local válido | Usar baseline | Nenhuma | Rede observável; não precisa esperar | T10 | S2 | OPTIONAL_CONTEXT_FAILURE |
| F02 | API clima fora | Plano sem clima fresco | BASELINE_ONLY | Sim* | Sem clima | Omitir | Nenhuma | No preparador | T10 | S2 | OPTIONAL_CONTEXT_FAILURE |
| F03 | Calendário indisponível | Permissão/serviço ausente | BASELINE_ONLY | Sim* | Sem agenda | Invalidar fragmento afetado | Autorizar só se desejar depois | No preparador/retorno | T10 | S2 | OPTIONAL_CONTEXT_FAILURE |
| F04 | IA/backend/login/sync/analytics fora | Capacidades opcionais falhando | BASELINE_ONLY | Sim* | Somente pronto local | Não esperar | Nenhuma | Timeout/erro fora do core | T10 | S2 | OPTIONAL_CONTEXT_FAILURE |
| F05 | TTS/voz enriquecida ausente | Recurso não pronto | BASELINE_ONLY | Sim* | Sem voz indisponível | Som local; nenhuma síntese tardia | Nenhuma | Validação local | T10 | S2 | OPTIONAL_CONTEXT_FAILURE |
| F06 | Processo morto pelo SO | PendingIntent registrado; não stopped | ARMED_VERIFIED histórico → TRIGGERING | Esperado* | Local acessível | Cold start mínimo | Nenhuma | A posteriori + observador externo | T07 | S0 | CRITICAL_WAKE_FAILURE |
| F07 | Reboot com antecedência | Intenção persistida; deadline além de B | RECOVERY_REQUIRED → ARMED_VERIFIED | Após recovery* | Somente dados acessíveis | Reconciliar sem copiar flag | Desbloquear se E-DB não qualificada | Evento + resultado + boot ID | T05 | S0 | OS_CONTROLLED |
| F08 | Reboot sobre o horário | Boot/unlock compete com deadline | RECOVERY_REQUIRED/RECOVERED_LATE/MISSED/UNKNOWN | Tentar uma vez até +10 min; depois não | Possivelmente não | Aplicar F-03-05 sem playback direto no boot | Abrir/rever ocorrência | Depois de boot; não em tempo real | T05 | S0 | OS_CONTROLLED |
| F09 | Fuso alterado | Alarme civil futuro | READINESS_STALE → ARMED_VERIFIED | Após reconciliação* | Invalidar hora/contexto dependente | Resolver mesma hora civil, nova generation | Rever horário resolvido | Evento separado do resultado | T06 | S1 | USER_CONTROLLED |
| F10 | Hora manual ou automática alterada | Wall muda; monotônico comparável | CHECK_REQUIRED/RECOVERY_REQUIRED | Condicional à política | Omitir fala temporal stale | Reconciliar domínio de relógio | Confirmar destino se ambíguo | Evento/pares de relógio | T06 | S0 | OS_CONTROLLED |
| F11 | DST gap | Hora civil inexistente | Ocorrência ajustada | Na primeira hora civil válida* | Validar fragmentos | Aplicar `GAP_FORWARD`, registrar ajuste | Nenhuma no trigger | Regras de zona + ID | T06 | S0 | RECOVERABLE_CONFIGURATION |
| F12 | DST fold | Hora civil duplicada | Uma ocorrência no primeiro offset | Uma vez por intenção* | Somente coerente | Usar primeiro offset; deduplicar segundo | Nenhuma no trigger | Regras de zona/ID | T06 | S0 | RECOVERABLE_CONFIGURATION |
| F13 | Permissão exata negada | SCHEDULE sem grant; nenhuma outra via | BLOCKED | Não prometido | Irrelevante | Salvar intenção, não fingir armar | Conceder acesso se desejar | canScheduleExactAlarms | T03 | S0 | RECOVERABLE_CONFIGURATION |
| F14 | Permissão exata revogada após armar | Via SCHEDULE, antes de T | INVALIDATED ao detectar | Não contar com entrega | Pode existir, não resolve | Reconciliar ao retorno/grant | Abrir/conceder/rever | Normalmente posterior; sem callback garantido | T03 | S0 | USER_CONTROLLED |
| F15 | FSI negado/revogado | Notificação/canal ainda aptos | PRESENTATION_LIMITED | Som esperado* | Local válido | Heads-up + controles qualificados | Permitir tela se desejar | canUseFullScreenIntent API 34+ | T04 | S1 | DEGRADED_WAKE |
| F16 | Notifications desabilitadas | Registro pode persistir | CONTROL_BLOCKED | Áudio pode tocar; contrato completo não | Pode existir | Não apagar registro válido; sinalizar | Habilitar ou rever uso | Check no foreground/disparo | T04 | S0 | USER_CONTROLLED |
| F17 | Canal rebaixado/bloqueado | Usuário mudou canal | LIMITED/BLOCKED | Player pode tocar, apresentação comprometida | Pode existir | Não recriar canal para burlar | Rever importância/canal | Consulta canal | T04 | S0 | USER_CONTROLLED |
| F18 | Volume de alarme zero/mute | Mesmo com grant exato | AUDIO_RISK/BLOCKED | Sem som audível esperado | Não corrige volume | Avisar; não elevar global oculto | Ajustar conscientemente | AudioManager + limite acústico | T09 | S0 | USER_CONTROLLED |
| F19 | DND proíbe alarmes | Filtro/política efetiva bloqueia | AUDIO_RISK | Pode ser suprimido | Não corrige DND | Sem bypass furtivo | Permitir alarmes se desejar | Filtro; composição pode ser opaca | T09 | S0 | OS_CONTROLLED |
| F20 | Fone com fio/USB conectado | Rota não qualificada | AUDIO_RISK | Rota/audibilidade OPEN | Pode existir | Observar rota sem aumento abrupto | Desconectar ou validar rota | Rota enquanto ativo + testemunha | T09 | S0 | OEM_UNKNOWN |
| F21 | Bluetooth conectado | Periférico/mute próprios | AUDIO_RISK | Rota/audibilidade OPEN | Pode existir | Não assumir alto-falante interno | Usar rota validada | Conexão não prova audibilidade | T09 | S0 | OEM_UNKNOWN |
| F22 | Bluetooth cai no disparo | Troca durante handoff | INTERRUPTED/RECOVERY_REQUIRED se falha | Pode falhar; retomada limitada | Pode existir | Reavaliar rota e teto seguro | Rever dispositivo | Callback + observação física | T09 | S0 | OEM_UNKNOWN |
| F23 | Bateria baixa sem desligar | Sem pausa/restrição extra | ARMED_VERIFIED com risco de energia | Esperado até energia faltar* | Pode ser omitido | Reduzir trabalho opcional | Carregar | Nível atual não prevê autonomia | T11 | S1 | USER_CONTROLLED |
| F24 | Battery Saver padrão | Célula ainda não ensaiada | ARMED_VERIFIED experimental no checkpoint | A validar* | Jobs podem não preparar | Baseline; não depender de job | Nenhuma no teste | Estado energia + observador | T11 | S0 | OS_CONTROLLED |
| F25 | Doze | Alarme clock candidato registrado | ARMED_VERIFIED → TRIGGERING | Esperado* | Sem requisito de rede | Caminho alarm clock | Nenhuma | dumpsys + áudio externo | T11 | S0 | OS_CONTROLLED |
| F26 | Force-stop | Usuário colocou pacote stopped | INVALIDATED ao retorno | Não durante stopped | Irrelevante | Não tentar contornar | Interagir/abrir e reconciliar | Depois; sem execução para avisar | T07 | S0 | USER_CONTROLLED |
| F27 | App atualizado | Mesmo pacote/dados, versão nova | CHECK_REQUIRED/RECOVERY_REQUIRED | Depende de continuidade/recovery | Revalidar compatibilidade | Reconciliar e migrar mínimo | Abrir se necessário | MY_PACKAGE_REPLACED + versão | T13 | S0 | RECOVERABLE_CONFIGURATION |
| F28 | App reinstalado/restore | Identidade/dados antigos não confiáveis | READINESS_CHECK_REQUIRED; nunca ARMED restaurado | Não herdar promessa nem rearmar automaticamente | Reautorizar/revalidar | Reconstruir readiness sem copiar scheduling | Configurar/confirmar novamente | Primeira abertura | T13 | S0 | USER_CONTROLLED |
| F29 | Storage/data cleared | Intenção apagada | Sem estado local recuperável | Não prometido | Não | Não inventar restauração | Reconfigurar | Pode só parecer instalação nova | T13 | S0 | USER_CONTROLLED |
| F30 | Dois alarmes próximos/simultâneos | IDs diferentes, possível quota | TRIGGERING + OUTPUT_OWNER/OUTPUT_WAITING por ocorrência | Ambos contabilizados; espera conta no timing* | Sem falas sobrepostas | Um output físico; preservar T/IDs/resultados | Ação com escopo occurrence-specific | IDs + registro externo | T08 | S0 | CRITICAL_WAKE_FAILURE |
| F31 | Snooze | Sessão ativa; filho ainda não registrado | SNOOZE_PENDING → SNOOZED | Filho devido em 5 min, só após registro* | Voz temporal revalidada | Persistir parent/boot/deadline; tratar quota | Reparar se adiamento falhar | Checkpoint filho | T08 | S0 | CRITICAL_WAKE_FAILURE |
| F32 | Crash enquanto toca | Sessão em progresso | INTERRUPTED/UNKNOWN → RECOVERY_REQUIRED | Interrompe; retorno não garantido | Omitir ao retomar se inválido | Retomar só se legal e dentro de M/W | Rever falha | Log parcial + acústica | T07 | S0 | CRITICAL_WAKE_FAILURE |
| F33 | Crash imediatamente antes do som | Callback pode ter sido consumido | RECOVERY_REQUIRED/UNKNOWN | Pode faltar | Irrelevante | Não presumir novo callback | Abrir/rever | Injeção entre checkpoints | T07 | S0 | CRITICAL_WAKE_FAILURE |
| F34 | Relógio retorna após ocorrência | Ocorrência já terminal | Terminal preservado | Não repetir mesma ocorrência | Stale omitido | Deduplicar por política civil | Rever próximos | Wall/monotônico/tombstone | T06 | S0 | OS_CONTROLLED |
| F35 | Relógio avança além de T | Ocorrência ainda pendente | RECOVERED_LATE até +10 min; depois MISSED/UNKNOWN | Uma tentativa até +10 min; depois não | Omitir texto temporal errado | Aplicar política sem avalanche | Confirmar próximo | Evento + resultado | T06 | S0 | OS_CONTROLLED |
| F36 | Desligado por período prolongado | Nenhuma CPU/energia disponível | Só observável depois | Não | Não necessário | Reconciliar futuros; registrar limite | Ligar/rever | Posterior, duração pode ser incerta | T05 | S0 | OS_CONTROLLED |
| F37 | Reboot sem primeiro unlock | Mínimo operacional em DE; dados pessoais em CE | RECOVERY_REQUIRED → ARMED_VERIFIED/RECOVERED_LATE | Exigência do target a validar* | Fallback Wake Plan, sem CE | LOCKED_BOOT + mínimo DE | Nenhuma para baseline | UserManager + boot real + áudio externo | T05 | S0 | OS_CONTROLLED |
| F38 | Remover de recentes | Swipe; não force-stop | Registro separado da Activity | Esperado, testar OEM* | Local | Não cancelar por saída da tela | Nenhuma | Observação do gesto/estado | T07 | S0 | OEM_UNKNOWN |
| F39 | Stop no gerenciador de apps ativos | API 33+, FGS em execução | Sessão interrompida; futuro preservado | Atual para; futuro esperado* | Pode existir | Não classificar como force-stop | Rever sessão quando abrir | Sem callback; motivo posterior | T07 | S0 | USER_CONTROLLED |
| F40 | Restrição manual de bateria | App restricted em background | BLOCKED ao detectar | Não prometido | Irrelevante | Orientar ajuste, sem burlar | Remover restrição se desejar | Foreground pode mascarar temporariamente | T11 | S0 | USER_CONTROLLED |
| F41 | App Standby bucket raro/restrito | Via de permissão/método registrada | Readiness conforme célula | A validar, não confundir com manual | Pode faltar | Baseline; medir quotas/exceções | Nenhuma no teste | Bucket real, pode resistir ao comando | T11 | S0 | OS_CONTROLLED |
| F42 | Extreme Battery Saver/OEM kill | App pausado/restrito | UNCONTROLLED/DEVICE-SPECIFIC RISK | Não prometido | Irrelevante | Sem garantia de auto-restauração | Despausar/rever políticas | Parcial e OEM-específica | T11/T14 | S0 | OEM_UNKNOWN |
| F43 | Chamada/VoIP ou foco perdido | Sessão concorrente | AUDIO_RISK/INTERRUPTED | OPEN na célula, pode atrasar | Voz pode ser omitida | Respeitar foco; registrar perda | Encerrar chamada se desejar | Foco/modo; não ler número | T09 | S0 | OS_CONTROLLED |
| F44 | Outro áudio de mídia tocando | Foco em outro app | TRIGGERING ou AUDIO_RISK | A validar* | Mixagem limitada | Pedir foco com lifecycle válido | Nenhuma | Callback foco + captura externa | T09 | S1 | DEGRADED_WAKE |
| F45 | Player fora de lifecycle permitido | API 37, background inválido | TRIGGERING → falha/UNKNOWN | Pode falhar silenciosamente | Irrelevante | Não marcar áudio pelo retorno de chamada | Nenhuma correção pelo usuário | Instrumentação + áudio externo | T12 | S0 | CRITICAL_WAKE_FAILURE |
| F46 | Plano corrompido/stale/parcial | WakePlan inválido; baseline íntegro | BASELINE_ONLY | Sim* | Omitir fragmentos inválidos | Leitor limitado, fallback | Nenhuma | Integridade/validade local | T10 | S1 | OPTIONAL_CONTEXT_FAILURE |
| F47 | Baseline indisponível/corrompido | Recurso essencial falha | BLOCKED ou CRITICAL_WAKE_FAILURE | Pode faltar; não há magia | Não resolve núcleo | Recuperação local se existente; avisar depois | Reparar app | Pré-check ou decoder | T02 | S0 | CRITICAL_WAKE_FAILURE |
| F48 | Armazenamento cheio/I/O falha | Save/ação/journal indisponível | BLOCKED/RECOVERY_REQUIRED | Pode tocar se já pronto; não confirmar save | Omitir preparação | Não bloquear stop nem áudio por logs | Liberar espaço/rever | Erro I/O; perda parcial observável | T02 | S0 | CRITICAL_WAKE_FAILURE |
| F49 | Evento duplicado ou generation antiga | Callback atrasado após edição/dismiss | Terminal/geração atual preservados | Não tocar ocorrência inválida | Não usar plano antigo | Deduplicar/rejeitar | Nenhuma | IDs/tombstone | T08 | S0 | CRITICAL_WAKE_FAILURE |
| F50 | Locale muda | Horário/fuso não mudaram | Estado preservado; UI reformatada | Sim* | Revalidar língua se necessário | Não mudar instante | Nenhuma | Evento/retorno | T06 | S1 | RECOVERABLE_CONFIGURATION |
| F51 | Perfil privado bloqueado/administrativo pausado | App não executável nesse perfil | UNKNOWN externamente | Não prometido | Irrelevante | Aviso geral de instalação; sem detector fictício | Usar perfil pessoal ativo | Privado pode não ser identificável | T14 | S0 | OS_CONTROLLED |
| F52 | Preparação bloqueia CPU/lock/inicialização | Serviço opcional compartilha recurso | Core deve permanecer apto | Exigência a provar* | Descartar | Isolar orçamento e caminho crítico | Nenhuma | Instrumentação de contenção | T10/T12 | S0 | CRITICAL_WAKE_FAILURE |
| F53 | Retorno de dismiss repetido ou não persistido | Ação perto de crash/I/O | DISMISSED ou RECOVERY_REQUIRED | Parar; não reativar por duplicata | Irrelevante | Stop imediato + tombstone quando possível | Rever erro de persistência | Journal parcial + teste | T02/T08 | S0 | CRITICAL_WAKE_FAILURE |
| F54 | Sem resposta por 30 min | Sessão efetivamente iniciada | UNANSWERED | Encerrar no limite operacional experimental | Não falar indefinidamente | Stop seguro; preservar recorrência | Ação opcional | Ausência de ação não prova sono | T15 | S1 | DEGRADED_WAKE |
| F55 | Evento de reconciliação recebido, efeito falha | Broadcast/callback chegou; I/O ou scheduling falha | READINESS_STALE/RECOVERY_REQUIRED | Não inferir rearmamento | Baseline não resolve scheduling | Registrar resultado separado; repetir na oportunidade válida | Rever estado quando possível | EVENT_RECEIVED + result ausente/FAILED | T02/T05/T06 | S0 | CRITICAL_WAKE_FAILURE |
| F56 | Checkpoint envelheceu após mudança não observada | ARMED_VERIFIED anterior; app parado | Estado histórico até observação, depois STALE/BLOCKED | Pode falhar; não apagar da coorte | Pode existir | Revalidar na primeira execução/renderização; não prometer monitoramento contínuo | Corrigir condição detectada | Timestamp/snapshot; detecção posterior | T03/T04/T13 | S0 | USER_CONTROLLED |

## Combinações adversariais obrigatórias

Não basta aprovação de falha isolada. Cruzar:
- F07 + F37 + F18: reboot bloqueado e volume zero não viram “recuperado” só porque receiver rodou.
- F14 + F08: revogação e reboot próximo não podem produzir promessa de reparo sem execução.
- F31 + F25 + F30: soneca, idle e outro alarme revelam quotas/colisões.
- F15 + F17: sem FSI e canal rebaixado podem remover o fallback de controle.
- F32 + F53: crash depois de parar exige distinguir ação persistida e indeterminada.
- F09 + F46: troca de fuso invalida fala de hora sem invalidar som local.
- F52 + F45: pré-computação pesada não pode impedir estabelecimento do lifecycle de áudio.
- F42 + F06: morte OEM não deve ser inferida como morte comum recuperável do processo.
- F55 + F07/F14: receber boot ou grant não renova ARMED_VERIFIED sem reconciliação persistida.
- F56 + F16/F18: check antigo de controles/volume não é prova de prontidão atual.

Resultado de cada combinação precisa de evidência própria; não extrapolar o produto cartesiano de testes isolados.
