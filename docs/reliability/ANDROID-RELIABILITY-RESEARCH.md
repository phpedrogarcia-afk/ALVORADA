# ANDROID RELIABILITY RESEARCH

ALVORADA — codinome. G1, pesquisa documental em **2026-09-11 (UTC)**.
**FACT histórico da pesquisa:** em 2026-09-11 não havia app, dispositivo instrumentado ou execução. Em G1.2 posterior, apenas E0/JVM foi executado; a observação empírica Android continua inexistente.

## Leitura epistemológica

Os FACTs abaixo são sobre o que a documentação afirma, não sobre desempenho demonstrado do ALVORADA. N = comportamento normativo/documentado; P = política de distribuição; OEM = documentação do fabricante, não medição. Confiança alta significa fonte explícita no escopo indicado; média significa composição ou ambiguidade. Observação empírica própria: **nenhuma**. Recomendações de engenharia e inferências são identificadas separadamente.

Cada R-ID é também referência dos outros documentos G1. Data de acesso de **todas** as linhas: 2026-09-11. Não se inferiu suporte a um aparelho a partir da versão de Android. Páginas atuais de Android 17/API 37 foram consultadas; não se presume disponibilidade de uma build em todo aparelho.

## Registro de evidência

| ID / fonte primária | API / target pertinente | Afirmação sustentada | Natureza / confiança |
| --- | --- | --- | --- |
| R01 — [Schedule alarms](https://developer.android.com/develop/background-work/services/alarms) | 19+ repetição; 21+ alarm clock; 23+ idle; target 31+ exatos | Alarmes operam fora da vida do processo. Repetições são inexatas desde API 19. Revogar SCHEDULE_EXACT_ALARM interrompe o app e cancela alarmes exatos futuros; concessão permite reconciliação. Shutdown remove agendamentos. | N / alta, com divergências C01–C03 |
| R02 — [AlarmManager](https://developer.android.com/reference/android/app/AlarmManager) | setExact 19; setAlarmClock 21; allow-idle 23; listeners 24/37 | setAlarmClock implica RTC_WAKEUP e atravessa Doze; setExact isolado não resolve idle. Listeners dependem de ciclo de vida. getNextAlarmClock mostra o próximo alarme de qualquer app, não todos os registros deste app. | N / alta no contrato específico |
| R03 — [Exact alarms no Android 14](https://developer.android.com/about/versions/14/changes/schedule-exact-alarms) | OS 34+, target 33+ | Instalação nova/restauração não deve presumir SCHEDULE_EXACT_ALARM concedida. USE_EXACT_ALARM é alternativa normal para apps elegíveis de alarme/calendário. | N / alta |
| R04 — [Manifest permissions](https://developer.android.com/reference/android/Manifest.permission) | USE_EXACT_ALARM 33; SCHEDULE_EXACT_ALARM 31; FSI 29 | USE dispensa pedido runtime; escolher uma via exata por dispositivo. Compatibilidade pode limitar SCHEDULE às APIs 31–32. Detentores de USE ficam no bucket working_set ou mais favorável; isso não é imunidade a restrição manual. | N / alta |
| R05 — [Política de permissões Play](https://support.google.com/googleplay/android-developer/answer/16558241?hl=en) | USE target 33+; FSI target 34+ | USE_EXACT_ALARM é restrita a funções centrais de precisão, incluindo alarmes; publicação está sujeita a revisão. FSI automático também é limitado a funções centrais elegíveis. | P / alta; aprovação deste produto OPEN |
| R06 — [Doze e App Standby](https://developer.android.com/training/monitoring-device-state/doze-standby) | OS 23+ | Idle restringe trabalho e rede; alarm clocks constituem caminho específico. O guia indica nove minutos por app para métodos allow-while-idle e fornece testes ADB. | N / alta para restrições; média para número transversal |
| R07 — [Power resource limits](https://developer.android.com/topic/performance/power/power-details) | buckets 28+; revisão de jobs 36 | Tabelas de quotas são aproximadas, dependem de estado e não garantem execução; while-idle aparece como sete por hora. Restrição manual é dimensão diferente de bucket. | N / alta; divergência C01 |
| R08 — [Background optimization](https://developer.android.com/topic/performance/background-optimization) | restrição AOSP 28+; target 33+ boot | Restrição manual pode impedir alarmes e FGS; em target 33+, broadcasts de boot podem ser retidos até outro início do app. OEM determina detalhes. | N / alta no exemplo AOSP, não universal |
| R09 — [Android 15: all apps](https://developer.android.com/about/versions/15/behavior-changes-all) | OS 35+, qualquer target | Force-stop cancela PendingIntents e exige interação para sair do stopped state. Espaço privado bloqueado interrompe apps; o app não pode simplesmente detectar que está nele. | N / alta |
| R10 — [Direct Boot](https://developer.android.com/privacy-and-security/direct-boot) | OS 24+ | Antes do primeiro desbloqueio, armazenamento credential-encrypted é inacessível. Componentes direct-boot-aware e armazenamento device-encrypted permitem tarefas mínimas após LOCKED_BOOT_COMPLETED. | N / alta |
| R11 — [Exceções de início de FGS](https://developer.android.com/develop/background-work/services/fgs/restrictions-bg-start) | target 31+; restrições adicionais 34+ | Exact alarm para ação pedida pelo usuário é exceção de início de FGS em background; não elimina requisitos de tipo, permissões e lifecycle. | N / alta |
| R12 — [Tipos de FGS](https://developer.android.com/develop/background-work/services/fgs/service-types) | target 34+ tipos; target 35+ boot | mediaPlayback representa reprodução em background; exige declaração correspondente. BOOT_COMPLETED não pode iniciar esse FGS em target 35+. | N / alta |
| R13 — [Android 17: background audio](https://developer.android.com/about/versions/17/changes/bg-audio) | OS 37 qualquer target; target 37 adicional | Áudio em background requer FGS não shortService ou atividade visível. Target 37 exige WIU, com exceção para permissão exata + USAGE_ALARM. Playback inválido pode falhar silenciosamente; foco retorna falha. | N / alta |
| R14 — [Audio focus](https://developer.android.com/media/optimize/audio-focus) | OS 26/31; target 35+ | Target 35+ exige app top ou FGS para pedir foco. Foco pode falhar/ser perdido. Regras automáticas descritas de mute em chamadas para MEDIA/GAME não provam comportamento de USAGE_ALARM. | N / alta |
| R15 — [AudioAttributes](https://developer.android.com/reference/android/media/AudioAttributes) | 21+ | USAGE_ALARM identifica áudio de alarme; CONTENT_TYPE_SPEECH descreve fala. Não equivalem a garantia acústica nem privilégio para ignorar usuário. | N / alta para atributos; inferência para limites |
| R16 — [AudioManager](https://developer.android.com/reference/android/media/AudioManager) | volume desde APIs iniciais; recursos variam | STREAM_ALARM identifica volume de alarme, separado de STREAM_RING. Consultas de volume, mute, modo e dispositivos dão sinais do sistema, não medem som no ambiente. | N / alta para APIs; inferência para observabilidade |
| R17 — [AudioRouting](https://developer.android.com/reference/android/media/AudioRouting) | 24+; múltiplas rotas 36+ | Dispositivo preferido não comprova rota efetiva; rota consultada depende de reprodução ativa. Mudanças de rota podem ser observadas. | N / alta |
| R18 — [NotificationManager](https://developer.android.com/reference/android/app/NotificationManager) | DND 23+; canUseFullScreenIntent 34+ | DND NONE suprime áudio exceto chamadas; ALARMS permite alarmes. FSI negado tem fallback heads-up documentado. Ler capacidade não substitui permissões e canal ativos. | N / alta |
| R19 — [Android 15: target changes](https://developer.android.com/about/versions/15/behavior-changes-15) | target 35+ | Mudanças de DND via app não desligam livremente a política global; regras se combinam pela mais restritiva. Há proibição de mediaPlayback FGS iniciado por BOOT_COMPLETED. | N / alta |
| R20 — [Full-screen intent limits](https://source.android.com/docs/core/permissions/fsi-limits) | OS 34+ | FSI é acesso revogável, com concessão inicial condicionada a elegibilidade/instalador. AOSP aponta CTS para validação. | N / alta |
| R21 — [Notification.Builder / FSI](https://developer.android.com/reference/android/app/Notification.Builder) | target 29+; OS 33+ | Em uso, heads-up substitui abertura full-screen. Sem FSI, heads-up tem persistência limitada documentada de 60 segundos, não controle permanente na tela. | N / alta; validar build |
| R22 — [Notification runtime permission](https://developer.android.com/develop/ui/compose/notifications/notification-permission?hl=en) | OS 33+ | POST_NOTIFICATIONS é runtime. Negação não proíbe iniciar FGS, mas restringe notificações; FGS ainda exige notificação. Não existe exceção geral de “app despertador”. | N / alta |
| R23 — [Notification channels](https://developer.android.com/develop/ui/compose/notifications/channels) | OS 26+ | IMPORTANCE_HIGH habilita apresentação urgente; usuário controla canal. Recriar canal não restaura importância rebaixada. | N / alta |
| R24 — [Play: FGS e FSI](https://support.google.com/googleplay/android-developer/answer/13392821) | target 34+ | Declarações Play e uso central elegível são exigências separadas da capacidade runtime. Datas diferentes na página devem ser lidas por evento, não como garantia de concessão. | P / alta, datas ambíguas C04 |
| R25 — [PendingIntent](https://developer.android.com/reference/android/app/PendingIntent) | todas; mutabilidade explícita target 31+ | Extras distintos não criam identidades distintas. Identidade precisa variar por request code ou campos comparados; reutilização pode substituir alarme. | N / alta |
| R26 — [Intent](https://developer.android.com/reference/android/content/Intent) | MY_PACKAGE_REPLACED 12+; eventos de tempo/boot | Existem eventos para substituição do próprio pacote, mudança de hora, fuso, locale e boot. Broadcast disponível não é garantia de recuperação concluída antes do deadline. | N / alta; última frase inferência |
| R27 — [Processes and lifecycle](https://developer.android.com/guide/components/activities/process-lifecycle) | restrições cached 33+ | Processo cached pode ser morto ou não receber execução; onDestroy não é garantido. Trabalho crítico não pode depender de timer em processo cached. | N / alta |
| R28 — [Stop de apps com FGS](https://developer.android.com/develop/background-work/services/fgs/handle-user-stopping) | OS 33+ | Stop no Task Manager encerra processo e áudio sem callback, mas preserva alarmes futuros. Não é force-stop. Há comando ADB específico. | N / alta |
| R29 — [ZoneRules](https://developer.android.com/reference/java/time/zone/ZoneRules) | 26+ API nativa | Hora civil pode ter zero offsets válidos (gap) ou dois (fold). A escolha de ocorrência precisa de política de produto; a API não decide intenção. | N / alta |
| R30 — [WorkManager / persistent work](https://developer.android.com/develop/background-work/background-tasks/persistent) | conforme biblioteca/OS | Trabalho persistente tem janelas flexíveis e obedece energia. Não é substituto do disparo de despertador exato. | N / alta |
| R31 — [Android 16: all apps](https://developer.android.com/about/versions/16/behavior-changes-all) | OS 36 | Quotas de jobs alcançam trabalho junto a FGS; afetam WorkManager. Não presumir que pré-computação rodará porque há FGS. | N / alta |
| R32 — [Pixel Battery Saver](https://support.google.com/pixelphone/answer/6187458?hl=en) | Pixel, recursos dependentes do modelo; sem API geral | Extreme Battery Saver pausa a maioria dos apps; apps pausados não notificam. Clock essencial do sistema não prova exceção para ALVORADA. | OEM / alta no produto descrito; inferência para app terceiro |
| R33 — [Android 17: all apps](https://developer.android.com/about/versions/17/behavior-changes-all) | OS 37 | Limites de memória e hardening de áudio adicionam cenários de morte/supressão. Capacidade normativa não valida uma build concreta. | N / alta |
| R34 — [Service](https://developer.android.com/reference/android/app/Service) | FGS/lifecycle conforme API | Serviço executa dentro do processo; modos de restart não constituem deadline acústico nem imunidade a encerramento. | N / alta para lifecycle; inferência para contrato |

## Scheduling: avaliação, não escolha de stack

| Mecanismo | Papel investigado | Conclusão de especificação |
| --- | --- | --- |
| AlarmManager + setAlarmClock + PendingIntent | Ocorrência de despertador visível | Candidato preferido H-G1-01, a validar; corresponde à semântica do produto e não depende de processo vivo. |
| setExact | Exatidão sem requisito idle | Não basta como único caminho para despertar noturno em Doze. |
| setExactAndAllowWhileIdle | Ocorrência exata durante idle, inclusive candidato para duração de soneca | Quotas/ordenação precisam de teste. Não herdar a promessa de alarm clock. |
| OnAlarmListener, inclusive overload novo da API 37 | Callbacks durante lifecycle | Rejeitado como único agendador persistente. |
| setRepeating / setInexactRepeating | Rotina aproximada | Não usar como promessa de hora civil diária exata; propor ocorrências one-shot reconciliadas. |
| WorkManager | Preparação/limpeza adiável | Fora do disparo, handoff de áudio e recuperação com deadline. Não escolhido como biblioteca. |

Referências: R01–R07, R25, R30. A documentação não publica um limite acústico universal em milissegundos; converter “exact” em ±1 s seria extrapolação.

## Divergências que não foram apagadas

- **C01 — frequência:** R06 diz nove minutos; R02 menciona aproximadamente um minuto em operação normal e até quinze em idle; R07 apresenta sete/hora. Escopo, versão e configuração não são intercambiáveis. Não escolher um número universal. Não aplicar automaticamente essas quotas ao setAlarmClock; medir cada método, OS, target e sequência.
- **C02 — repetição:** R01 inclui exemplos/texto que chamam setRepeating de preciso, mas a própria página diz que repetições são inexatas desde API 19; R02 confirma semântica moderna. Contrato usa comportamento API-específico, registra a inconsistência e rejeita o exemplo legado como prova.
- **C03 — listener e permissões:** guias R01/R03 resumem dispensa de permissão para listener; R02 ressalva comportamento em S/T e perda fora do lifecycle em U+. Não usar dispensa como caminho alternativo para alarme persistente.
- **C04 — FSI:** R20 descreve concessão de plataforma e revogação por instalador; R24 mistura marcos de declaração e enforcement. Não assumir pré-concessão. Consultar estado runtime e processo de distribuição.
- **C05 — geral versus exceção:** tabelas de energia R07 não detalham todos os caminhos de alarm clock; R02 trata a exceção específica. Resultado: candidato a ensaio, não “nenhum OEM pode bloquear”.

## Áudio: fronteira de controle

**Controlável pelo app (requisitos propostos):** recurso local íntegro; USAGE_ALARM na base e fala que integra o alarme; lifecycle válido; ordem FGS/foco/reprodução; progressão limitada; uma sessão; observar falha/rota; comandos parar/adiar; não usar stream de chamada para contornar DND.

**Usuário/SO/OEM:** volume efetivo, DND e regras concorrentes, roteamento final, foco em chamada/VoIP, funcionamento do alto-falante, mute do periférico e políticas energéticas. Silent/vibrate de chamadas não significa, sozinho, volume de alarme zero. Volume positivo não significa audibilidade. Fonte: R13–R19; o contrato acústico exige teste externo.

## Reboot, atualização e observabilidade

**Inferência de engenharia:** persistir intenção é diferente de persistir agendamento. Boot deve reconciliar o mínimo antes do deadline; tocar diretamente do receiver de boot não é substituto seguro dessa reconciliação (R10–R13). Reiniciar muito perto do horário continua sendo risco, mesmo com Direct Boot.

Atualização do pacote é evento de reconciliação, não equivalente a reinstalação. Não assumir nem cancelamento universal nem preservação integral em toda atualização. Testar migração, PendingIntents, receiver e build (R25–R27). Limpeza de dados/reinstalação não têm restauração local possível sem cópia; restauração futura deve revalidar, nunca copiar ARMED.

## Hipóteses atacadas e memória

Não se afirma que G0 adotou as hipóteses abaixo; são simplificações examinadas e descartadas nesta missão:

- “Exact significa som em ±1 s”: não sustentada, nenhuma tolerância acústica publicada encontrada.
- “Todo encerrar-app é igual”: refutada documentalmente por R09/R28.
- “BOOT_COMPLETED basta antes do primeiro unlock”: refutada por R10.
- “Chamada de playback sem exceção prova áudio”: refutada por R13.
- “Offline local resolve qualquer falha”: refutada como interpretação universal, não como princípio do projeto.

**SCAR-G1-01 — 2026-09-11, descoberta documental, não incidente em produção.** Ao testar a promessa de armar, ficou demonstrado que sinais indiretos podem mentir por omissão: permissão pode invalidar agendamento sem callback de revogação útil ao app parado; playback pode falhar silenciosamente. Preservar: checkpoints timestampados, estado UNKNOWN e observação acústica independente. Evidência R01/R13/R17; prevenção CT-01, CT-04 e testes T03/T07/T12.

**PATTERN / WIN:** nenhum validado. Não foi realizada pesquisa empírica OEM; Pixel foi usado apenas como exemplo oficial. Fontes Samsung tentadas não forneceram página específica acessível nesta consulta; nenhuma garantia Samsung foi deduzida.
