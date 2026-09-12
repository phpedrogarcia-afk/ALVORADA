# PERMISSION READINESS

ALVORADA — codinome. Atualizado em 2026-09-12. **Semântica congelada para o adapter Android descartável**; E0 não solicitou permissões e E1 não foi executado.

## Estados da capacidade

UNASSESSED → CHECKING → AVAILABLE ou DENIED/UNAVAILABLE/UNKNOWN.
AVAILABLE pode virar STALE, REVOKED ou UNAVAILABLE. Concessão não arma sozinha: retorna a check e reconciliação. Toda avaliação registra timestamp, boot, build/target/cell, occurrence/generation e fonte da observação.

Readiness é composição de **scheduling + recursos locais + lifecycle apto + áudio + controles + envelope**, não soma de permissões. FULL, LIMITED, BLOCKED, UNKNOWN e STALE são projeções separadas da intenção salva. FULL no checkpoint permite `ARMED_VERIFIED`; não prova continuidade depois dele.

## Lifecycle por permissão/capacidade

| Capacidade / motivo e escopo | Quando pedir/declarar | Negada ou ausente | Revogada / alteração | Recuperação e UX | Efeito seguro sobre criação/armamento |
| --- | --- | --- | --- | --- | --- |
| SCHEDULE_EXACT_ALARM — exact scheduling; API 31+, target 31+ | Alternativa de acesso especial; pedir ao ativar primeiro alarme, após explicar. API 31–32 se via USE em 33+ | Salvar intenção, não afirmar scheduling exato | Cancela exatos e pode parar app; não esperar callback de revogação | Abrir ajustes por ação; no grant/retorno consultar canScheduleExactAlarms e reconciliar | Criação SIM; ARMED_VERIFIED NÃO sem capacidade. Não usar inexato disfarçado |
| USE_EXACT_ALARM — função central; API/target 33+ | Declaração normal elegível; sem diálogo runtime. Candidata H-G1-04, sujeita a Play | APK sem capacidade não recebe rótulo completo | Não tem toggle comum de revogação como SCHEDULE; update/instalação/estado exigem nova avaliação | Corrigir distribuição/declarar via apropriada; não pedir ambas indiscriminadamente | Criação SIM; confirmar capacidade efetiva antes de armar |
| RECEIVE_BOOT_COMPLETED — restauração | Manifesto, sem pedido runtime ao usuário | Falha de build: reboot fora do envelope | Restrição/force-stop pode impedir execução mesmo declarada | Reconciliação ao abrir/grant; explicar limitação de reboot | Não qualificar recovery de boot sem ela; não confundir com Direct Boot |
| USE_FULL_SCREEN_INTENT — controles urgentes | Manifesto target 29+; em 34+ consultar canUseFullScreenIntent; pedir ajustes só se necessário | Som/agendamento não precisam falhar; usar heads-up/canal se aptos | Atualizar flag PRESENTATION_LIMITED | Mostrar “abertura de tela indisponível”; oferecer configuração fora da sessão | ARMED_VERIFIED com apresentação limitada somente em célula alternativa validada |
| POST_NOTIFICATIONS — notificação/ações, API 33+ | Pedir ao configurar primeiro alarme, contextualizado | Não é impedimento legal universal de FGS; compromete superfície de controle escolhida | Atualizar CONTROL_BLOCKED quando detectado | Retorno dos ajustes → recheck de permissão e canal | Política proposta: salvar SIM; sem promessa completa até controle validado |
| Canal de alarme, API 26+ — não é permissão | Criar canal apropriado; IMPORTANCE_HIGH como candidato de apresentação | Canal NONE/bloqueado → controles comprometidos | Usuário pode mudar importância/som/vibração | Consultar canal; oferecer link aos ajustes. Não recriar IDs para contornar escolha | Manter registro existente quando válido; readiness LIMITED/BLOCKED |
| FOREGROUND_SERVICE + FOREGROUND_SERVICE_MEDIA_PLAYBACK — execução de som | Manifesto conforme API 28+ / target 34+; tipo mediaPlayback candidato | Build incompatível ou falha de início: não mascarar com UI | Atualização e restrição de lifecycle exigem check/teste | Corrigir build; registrar falha; não exigir permissão irrelevante de microfone | Sem lifecycle válido, áudio não qualificado; não armar promessa completa |
| WAKE_LOCK — handoff/execução limitada se necessário | Permissão normal somente se desenho demonstrar necessidade | Não presumir CPU sustentada após receiver | SO/energia ainda limitam execução | Provar propriedade e liberação; não manter lock durante a noite | Falha do handoff bloqueia qualificação; não pede exceção energética automaticamente |
| VIBRATE — se integrado à escalada futura | Normal; apenas se canal sensorial adotado | Omitir vibração, não bloquear áudio | Política usuário/SO pode impedir efeito | Mostrar limitação se parte de configuração escolhida | Não requisito do baseline sonoro proposto |
| ACCESS_NOTIFICATION_POLICY — somente eventual controle de DND | Não é requisito universal do Wake Core; acesso especial apenas com finalidade aprovada | Não desligar DND; orientar usuário a permitir alarmes se desejar | Retorno/alteração reavalia risco | DND NONE ou política opaca → AUDIO_RISK; ações conscientes | Ausência dessa permissão não bloqueia por si só; DND efetivo pode bloquear promessa |
| IGNORE_BATTERY_OPTIMIZATIONS / exclusões OEM | Não exigir por padrão nem usar como prova de confiabilidade | Testar comportamento otimizado; configuração restritiva explícita é risco | Mudança OEM pode não produzir aviso imediato | Instrução específica de build, se documentada; sem garantia de imunidade | Pode bloquear célula; não equivale à permissão exata |
| READ_CALENDAR — enriquecimento opcional futuro | Só ao escolher integração; autorização explícita | Omitir agenda | Invalidar fragmentos autorizados pela permissão retirada | Reconsentir fora da manhã; não reusar cache indevidamente | Não bloqueia intenção, scheduling, som ou controles |
| INTERNET — rede opcional | Normal se função online futura justificar; login não exigido | Baseline local | Falha de rede/serviço omite contexto | Sem pedido no disparo | Nunca bloqueia Wake Core |
| Localização / Bluetooth — integrações/consultas específicas | Nenhuma permissão ampla decidida; justificar API concreta antes de pedir | Sem clima localizado ou diagnóstico específico | Marcar informação desconhecida, não inventar rota | Preferir recursos menos invasivos; sem scan contínuo | Não presumir necessidade de BLUETOOTH_CONNECT só para tocar em rota do SO |

Base: [R01–R05, R10–R24, R32](ANDROID-RELIABILITY-RESEARCH.md). A tabela prescreve UX/segurança do projeto; não afirma que todas as capacidades listadas são permissões runtime.

## Algoritmo de readiness conceitual

1. Carregar intenção/generation e estado local mínimo; falha → BLOCKED.
2. Resolver próxima ocorrência e política de tempo; ambiguidades não aprovadas → CHECK_REQUIRED.
3. Verificar capacidade exata e prazo de antecedência; sem ela não solicitar scheduling “confiável”.
4. Verificar baseline, disponibilidade pré-unlock conforme célula e controles.
5. Ler sinais de volume, DND, canal, FSI, energia e suporte conhecidos. UNKNOWN não vira AVAILABLE.
6. Agendar, tratar rejeição e persistir checkpoint. Só depois projetar `ARMED_VERIFIED`, se a célula estiver validada.
7. Reavaliar no retorno ao foreground/ajustes, `LOCKED_BOOT_COMPLETED`, `BOOT_COMPLETED`, package replace/update, grants/revogações observáveis, alterações de tempo/fuso, edição, snooze, dismiss e crash recovery.
8. No disparo, verificar identidade e condições locais sem consultar serviço opcional; condição perdida não justifica silêncio deliberado se ainda houver tentativa local segura e autorizada.

**Limite de detecção:** `EVENT_RECEIVED` não significa `RECONCILED`. O resultado precisa ser `RECONCILED`, `NOOP`, `BLOCKED`, `PARTIAL`, `FAILED` ou `UNKNOWN`, com checkpoint novo quando houver. Não há polling contínuo necessário nem garantia de observação instantânea enquanto parado. “Última verificação” e risco posterior não podem desaparecer da semântica.

## Apresentação e som são independentes

Tela apagada/bloqueada: FSI autorizado é candidato de abertura; sem FSI, heads-up é fallback condicionado a permissão/canal/política e ao build. Em uso, esperar heads-up, não roubo de foco. Expiração da faixa heads-up não pode deixar som sem controle acessível; testar depois de 60 s e com chave de bloqueio.

Som próprio não deve depender de som da notificação. Evitar duplicação entre canal e player, evitando susto; configuração que preserve heads-up sem som duplicado é **OPEN P-G1-05**, a testar, não contornar com canal falso.

Volume zero/DND impeditivo antes de armar: mostrar motivo e ação; não aumentar volume global escondido. Mudança após armar: manter tentativa permitida, sinalizar quando possível e classificar risco; não cancelar ocorrência só para limpar métricas.
