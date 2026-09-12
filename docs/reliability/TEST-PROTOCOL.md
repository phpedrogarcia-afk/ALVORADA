# TEST PROTOCOL

ALVORADA — codinome. Atualizado em 2026-09-12. **Protocolo normativo G1.1; E0 executado em G1.2, E1 ainda não executado.**
Existe modelo JVM no harness descartável. Não há APK/adapter Android nem aparelho/emulator ligado; portanto nenhum comando ADB ou teste de app foi executado.

## 1. Oráculo e critérios antes de começar

Uma tentativa tem identidade de ocorrência/generation, T esperado, variante de SO/target, precondições observadas, falha injetada e resultado. Oráculo independente: relógio de laboratório sincronizado + observação acústica e visual externa, sem gravar conteúdo pessoal. Logs do app não são prova suficiente de som.

Instrumentar r (receiver), chamada de lifecycle, foco, pedido de reprodução, avanço comprovável a, apresentação de controles e ação. Medir x externamente. Registrar incerteza de sincronização/captura. Captura sintética do áudio digital não demonstra alto-falante audível.

### Parâmetros congelados e parâmetros ainda abertos

| Parâmetro | Significado | Como fechar |
| --- | --- | --- |
| Delivery bands | r−T: TARGET 0–2.000 ms; EARLY_TOLERANCE −500–<0; ACCEPTABLE_LATE >2.000–5.000; fora disso FAILURE | EXPERIMENTAL congelado por F-03-06; incerteza que cruza limite é inconclusiva |
| Trigger-to-audio bands | a−r e x−r, cada um: TARGET ≤1.000 ms; ACCEPTABLE ≤3.000; >3.000 FAILURE | EXPERIMENTAL F-03-07; software e físico aprovam separadamente |
| L_controls | Orçamento até controles utilizáveis | OPEN; caracterizar e aprovar antes de claim de controle |
| A / B | Antecedência mínima para armar; margem mínima de boot recuperável | Ensaios progressivos em torno de T |
| W / M | Late recovery ≤10 min; sessão operacional 30 min | EXPERIMENTAIS congelados por F-03-05/F-03-10 |
| C | Margem de congelamento de enriquecimento | Custo de publicação/validação e carga concorrente |
| N por classe | SMOKE 3; STABILITY 30; FAILURE-INJECTION 10; SOAK 100/≥14 dias; PRE-BETA 300 por célula | Mínimos do plano, não amostra populacional; ver EVIDENCE-PLAN |
| ε | Incerteza máxima de medição | Calibrar instrumento/relógios antes de ensaios |
| τ / n_snooze / k_alarms | τ=5 min; máximo de snoozes e capacidade seguem OPEN | T08 em diferentes quotas/estados |
| R_log | 30 dias ou 1.000 eventos, o que ocorrer primeiro | F-03-14; limpeza pelo usuário, sem conteúdo pessoal |

Parâmetros OPEN permitem caracterização, não aprovação do claim afetado. Não inventar ±1 s acústico, SLO 99,9% nem independência estatística.

## 2. Estratégia em estágios

| Estágio | Objetivo / ambiente | Falhas reveladas | Critério de aprovação |
| --- | --- | --- | --- |
| E0 MODEL / JVM | Modelo, componentes fake, relógio e falhas injetáveis | Transições, DST, journal, generation, concorrência | I-01–I-14; zero contraexemplo aberto |
| E1 ANDROID EMULATOR | APIs 31/34/35/36/37 | API/lifecycle/permission/eventos emulados | Zero S0; sem claim acústico/OEM |
| E2 PHYSICAL REFERENCE | Um aparelho físico de referência + oráculo externo | Som, lockscreen, energia, reboot e rotas reais | Zero S0; bandas e oráculo válidos |
| E3 MULTI-OEM | Pixel/referência, Samsung, Xiaomi e eventual quarto OEM | Divergência de firmware/energia/apresentação | Aprovação por célula, sem média compensatória |
| E4 LONG-RUN / SOAK | Cada célula candidata, ≥14 dias | Raridades, drift, quotas, recorrência | 100 ocorrências/célula; zero S0 aberto |
| E5 PRE-BETA ENVELOPE | Dossiê completo por célula | Suficiência e regressão do claim | ≥300 ocorrências qualificadas/célula + decisão explícita |

Detalhes, repetições e limites de conclusão: [EVIDENCE-PLAN.md](EVIDENCE-PLAN.md). Zero falhas em N ensaios não prova falha impossível. Se ensaios fossem Bernoulli independentes, limite superior unilateral de 95% para taxa de falha com zero falhas seria 1−0,05^(1/N). Uso real correlaciona por noite/build/OEM: não vender essa conta como confiabilidade populacional. Reportar intervalos e estratos, não só média.

## 3. Preparação e limpeza

Apenas laboratório com aparelhos dedicados e dados sintéticos; nunca testar relógio, reset, reboot ou force-stop no telefone usado como único despertador. Registrar versão de ferramentas, firmware, target, configuração de energia, permissões, canal, volume/rota/DND, horário automático/fuso e boot. Guardar estado original para restaurar; não presumir que era “active”, volume padrão ou grant.

As linhas abaixo são **templates**: substituir SERIAL, PACKAGE_NAME e outros marcadores por valores verificados do futuro APK. O driver reserva `org.alvorada.reliability.harness`, mas nenhum APK existe e o identificador não é escolha de produto. Teste que não comprova estado injetado é INCONCLUSIVE, não PASS. Usar `adb -s SERIAL` evita atingir outro dispositivo.

## 4. Casos reproduzíveis T01–T15

### T01 — intenção, armamento e identidade (E0–E2)

Salvar alarme sintético A; observar CONFIGURED→CHECK→ARMING→ARMED_VERIFIED somente após scheduling aceito e checkpoint persistido. Injetar alteração de capability depois do checkpoint e exigir READINESS_STALE/BLOCKED na próxima oportunidade. Inspecionar `adb -s SERIAL shell dumpsys alarm` no laboratório e comparar identidade/tempo, sem transformar dump em API de produção. Editar A, criar B com mesmo horário e repetir pedidos; verificar que extras não são usados como única identidade. Negar chamada do SO no fake; UI não pode confirmar.

Aprova: I-01–I-05/I-11, intenção antiga preservada durante edição não salva; zero colisões/ARMED_VERIFIED prematuro. Falhas F13/F30/F49/F56. Contratos CT-01/02/05.

### T02 — durabilidade, I/O e recursos locais (E0–E2)

Injetar erro antes/depois de cada escrita, entre registro SO e ACK local, em tombstone, storage cheio simulado, baseline ilegível e retorno parcial. Crash no harness nos mesmos pontos. Não encher indiscriminadamente disco do usuário. Reiniciar componente/app, comparar intenção esperada, registrar órfãos e UNKNOWN. Falha em log não pode impedir start/stop. Áudio em curso deve poder ser parado mesmo sem storage.

Aprova: nenhum falso save/armamento; recovery convergente; sem som interminável e sem replay terminal. F47/F48/F53; CT-07.

### T03 — lifecycle de exact permission (E1–E3)

Ensaiar duas variantes futuras: SCHEDULE e USE, em API/target pertinentes. Na primeira, negar acesso antes de armar; conceder, armar e revogar pelo painel “Alarmes e lembretes”. Não usar `pm revoke` em permissão normal USE como se fosse runtime. Observar cancelamento e oportunidade posterior de recuperação, sem abrir app durante a janela de silêncio esperada. Voltar e revalidar.

Inspeção opcional: `adb -s SERIAL shell cmd appops get PACKAGE_NAME SCHEDULE_EXACT_ALARM`. Se usar mudança appops em build que suporta, registrar modo anterior e comando suportado por `cmd appops help`; painel é teste obrigatório e evita fingir equivalência entre flags.

Aprova: F13/F14, nenhum rótulo armado sem via exata; concessão não duplica; via USE avaliada separadamente de Play. CT-01/02/06.

### T04 — controles e apresentação (E1–E3)

Permissão de notificação runtime em API 33+ pode ser exercitada, com estado anterior registrado:

```bash
adb -s SERIAL shell pm revoke PACKAGE_NAME android.permission.POST_NOTIFICATIONS
adb -s SERIAL shell pm grant PACKAGE_NAME android.permission.POST_NOTIFICATIONS
```

Grant de teste não substitui UX de consentimento. Para estado de instalação nova, flags user-set/user-fixed precisam ser tratadas conforme R22; não apagar flags em aparelho pessoal.

FSI API 34+: negar/conceder pelo painel específico, consultar canUseFullScreenIntent no harness. Cruzar tela bloqueada, apagada, AOD e aparelho em uso; canal HIGH, rebaixado e NONE; notification permission concedida/negada. Esperar mais de 60 s na variante sem FSI: verificar acesso persistente ao dismiss/snooze por superfície permitida, não apenas primeira faixa heads-up. Verificar ausência de toque duplicado de canal+player e de brilho abrupto.

Aprova: F15–F17; controles aptos e limitação explícita. Não “corrigir” canal mudando seu ID. CT-02/03.

### T05 — reboot, desligamento e Direct Boot (E1–E3; repetição E4)

Armar sintético, remover rede e reiniciar dispositivo dedicado:

```bash
adb -s SERIAL reboot
```

Não desbloquear na variante E-DB; aguardar evento real LOCKED_BOOT_COMPLETED e observar som/controle mínimo. Repetir desbloqueando antes e depois de T, com boot muito próximo, energia ausente no deadline e reboot durante soneca. Variação de antecedência explora fronteira B. Distinguir boot de receiver sintético: `am broadcast` não substitui reboot nem recria CE bloqueado.

Aprova: F07/F08/F36/F37/F55; sem leitura de dados CE no núcleo E-DB; uma única recuperação até +10 min, sem FGS de mídia indevido iniciado do boot; depois disso nenhum áudio surpresa. `EVENT_RECEIVED` e resultado de reconciliação separados. CT-06/08.

### T06 — tempo, fuso, DST e locale (E0–E3)

Primeiro usar relógio/regras injetados; depois ajustes do SO em emulador descartável e físico dedicado. Registrar e desligar hora/fuso automáticos no painel, alterar, testar e restaurar configuração original. Não presumir que `adb shell date -s` é autorizado numa build de produção; se for negado, usar UI/emulador, sem rootar aparelho para contornar.

Fixtures de modelo: regra sintética com gap 02:00→03:00, alarme 02:30; fold 03:00→02:00, alarme 02:30 com dois offsets; repetição civil através de ambos. No teste de zona real, extrair transições da versão tzdb instalada e registrar esperado, sem assumir regras futuras invariáveis. Testar fuso UTC→outro, avanço além de T, retrocesso antes/depois de dismiss, mudanças automáticas simuladas no domínio do modelo, locale sem mudar fuso.

Aprova: F-03-02–F-03-05; I-05/I-07/I-11/I-12; gap no primeiro válido, fold no primeiro offset uma vez, late ≤10 min, sem hora narrada falsa ou “24 h” tomada como dia civil. F09–F12/F34/F35/F50; CT-04/06.

### T07 — distinguir encerramentos e crash (E1–E3)

```bash
adb -s SERIAL shell am kill PACKAGE_NAME
adb -s SERIAL shell am force-stop PACKAGE_NAME
adb -s SERIAL shell cmd activity stop-app PACKAGE_NAME
```

**Executar em tentativas separadas**, não como sequência única. kill só mata processos elegíveis; comprovar PID/cold start. force-stop é teste negativo: não esperar recovery automático no stopped state nem reabrir o app antes de T para “ajudar”. stop-app aplica-se ao Task Manager com FGS, não ao mesmo contrato de force-stop. Remoção de recentes deve ser gesto real no launcher ensaiado.

Crash antes do trigger, depois do receiver e durante playback: usar failpoints do adapter Android futuro; o modelo E0 já cobre checkpoints lógicos. Não usar force-stop como substituto. Reinício tardio deve respeitar tombstone, janela de 10 min e sessão de 30 min. Registrar som interrompido e causa, sem inferir entrega por logs faltantes.

Aprova: F06/F26/F32/F33/F38/F39 e limites explícitos; no caso ordinário qualificado há entrega; nos casos externos há relato correto sem bypass. CT-04/06/09/10.

### T08 — colisões, duplicação e soneca (E0–E3)

A/B iguais e próximos; identidades distintas; um OUTPUT_OWNER e outro OUTPUT_WAITING; eventos duplicados; callback de generation antiga; dismiss de A preservando B; filho de soneca devido em 5 min; crash no pedido do filho; cancelamento concorrente; sequência exploratória até limites n_snooze/k_alarms. Explorar intervalos abaixo/acima de nove e quinze minutos para caracterização de allow-idle; não tratá-los como garantia ou intervalo comercial decidido.

Aprova: contabilidade por ocorrência e uma sessão; quota não escondida; soneca só confirmada após registro; medidas específicas para filho. F30/F31/F49/F53; CT-05/07.

### T09 — áudio físico, foco e rotas (E2–E3; dossiê E5)

Sem dados pessoais: volume alarme zero/mínimo/faixa aprovada, silent/vibrate de chamada, DND ALL/ALARMS/PRIORITY/NONE e regras concorrentes, mídia/voz de outro app, chamada convencional e VoIP sintéticas, fone fio/USB, Bluetooth e desconexão em T e durante fala. Capturar alto-falante e periférico de forma externa. Ler rota efetiva enquanto playback, não apenas dispositivo preferido.

Aprova: nenhuma promessa acústica baseada só em API; nenhuma elevação global/bypass furtivo; perdas/retomadas respeitam teto; cada rota é célula separada. F18–F22/F43/F44; CT-03/04/10.

### T10 — isolamento/precomputação (E0–E2)

Remover rede/login/serviços, corromper e expirar fragmentos, entregar plano de generation/fuso anterior, publicação parcial e tardia após T−C, nenhum job executado. Travar preparador, decoder opcional e acesso ao contexto; saturar orçamento do processo controladamente. Verificar se inicialização global carrega SDK opcional antes do core.

Aprova: baseline e controles iniciam sem esperar qualquer enriquecimento; stale omitido; CPU/locks opcionais não dominam. F01–F05/F46/F52; CT-03 e H-G1-03.

### T11 — Doze, standby, energia (E1–E3)

No aparelho dedicado, registrar estado inicial e colocar tela apagada, sem recarga efetiva. Comandos oficiais de referência:

```bash
adb -s SERIAL shell dumpsys battery unplug
adb -s SERIAL shell dumpsys deviceidle force-idle
adb -s SERIAL shell dumpsys deviceidle
adb -s SERIAL shell dumpsys deviceidle unforce
adb -s SERIAL shell dumpsys battery reset
```

Armar antes de entrar em idle. Verificar que o dispositivo realmente entrou; em ensaio alarm clock, saída próxima de T pode ser comportamento esperado, não defeito do teste. USB/debugger e carregamento podem mudar resultado: repetir sessão natural sem suporte de depuração mantendo processo vivo.

App Standby:

```bash
adb -s SERIAL shell am set-inactive PACKAGE_NAME true
adb -s SERIAL shell am get-inactive PACKAGE_NAME
adb -s SERIAL shell am get-standby-bucket PACKAGE_NAME
adb -s SERIAL shell am set-standby-bucket PACKAGE_NAME rare
```

Registrar/restaurar estado anterior; não impor “active” como limpeza universal. Quotas podem impedir bucket pedido em apps elegíveis USE: comprovar estado real ou registrar N/A justificado. Para restrição manual, usar painel bateria; não confundir com rare/restricted bucket. Testar modo otimizado e restrito, Battery Saver padrão e variante extrema oficial do aparelho.

Aprova: F23–F25/F40–F42; expectativa correta por modo; nenhum precompute necessário. Fontes de comandos: R06/R31; CT-03/10.

### T12 — lifecycle Android 15–17 e pressão de recursos (E1–E3)

Comparar alvo ≥35 e ≥37 quando viável em builds pertinentes. Trigger por exact alarm de usuário → FGS elegível → foco → áudio USAGE_ALARM, sem depender de atividade full-screen. Controle negativo em API 37: playback fora de lifecycle, observando supressão silenciosa. Controle com shortService não pode ser aprovado como equivalente. Não adquirir mic/location ou usar stream de chamada para fabricar elegibilidade.

Pressão de memória em laboratório, bootstrap de dependências travado e startup lento completam o teste. Aprova: F45/F52; r/a/x distintos, sem sucesso fictício e sem prazo de restart inventado. CT-03/04/09.

### T13 — atualização, reinstalação, limpeza e restauração (E0–E3)

Em fixture descartável: update assinado mesmo pacote preservando dados, nova versão compatível/incompatível, restauração de cópia de intenção sem tokens, reinstalação e limpeza pelo painel. Observar MY_PACKAGE_REPLACED, migração e abertura posterior. Não executar remoção em dados reais nem assumir backup disponível.

Aprova: F27–F29; registro anterior não vira ARMED_VERIFIED restaurado, restore não rearma automaticamente, sem alarme órfão após exclusão; política de backup local-first verificada. CT-06/07.

### T14 — OEM/perfis (E3)

Em modelos/fingerprints escolhidos, testar modos documentados de pausa, swipe, auto-start se existente, perfil suspenso e espaço privado bloqueado quando disponível. Não inventar detector de privado. “Nunca dormir” não é certificado de confiabilidade; observar. Fabricante novo exige nova célula, não inferência de Pixel.

Aprova: F42/F51; desconhecidos não são aprovados; modos impeditivos excluídos explicitamente com orientação. CT-10.

### T15 — longitudinal e resultado humano (E4–E5)

Rodadas sem ajustes diários para ajudar o app; usar intenção recorrente, soneca e noites offline. Testar timeout de 30 min sem interação. Medir entrega acústica/controles, não diagnosticar sono nem chamar dismiss de despertar fisiológico. Testes com pessoas e Escalada Serena real pertencem ao G2 sob protocolo próprio.

Não abrir o app nem dar dismiss entre ocorrências na variante de recorrência: comprovar que o próximo dia é registrado independentemente da resposta da sessão anterior; injetar crash durante esse avanço.

Aprova: E4 com mínimo de 100 ocorrências/célula em ≥14 dias e ≥20 sem USB/debugger; sem falha crítica pendente; F54 e recorrência de todas as falhas. Não contar noite sem observação como entrega.

## 5. Rastreabilidade das promessas

| Promessa | Prova necessária |
| --- | --- |
| CT-01 armamento honesto | T01/T03/T04 + célula qualificada |
| CT-02 capacidade não mascarada | T02/T03/T04/T09 |
| CT-03 núcleo independente | T05/T10/T12 |
| CT-04 resultado observável | T07/T09/T12 + oráculo externo |
| CT-05 identidade / concorrência | T01/T08 |
| CT-06 reconciliação | T03/T05/T06/T13 |
| CT-07 crash / durabilidade | T02/T07/T08 |
| CT-08 boot | T05/T11/T12 |
| CT-09 sessão interrompida | T07/T12/T15 |
| CT-10 limites externos explícitos | T03/T07/T09/T11/T14 |

## 6. Relatório mínimo de cada execução

Cada execução recebe `EVID-G1-NNNN` imutável e registra: test_id, fault_ids, cláusulas, célula/device/build/API/target/hash do harness, pré-condições, policy version, passos, injeção, timestamps/clock-domains/epsilon, metric set, evidência acústica/visual e checksums, resultado `PASS/FAIL/UNKNOWN/NOT_TESTABLE/ENVIRONMENT_BLOCKED`, divergência, recuperação e limpeza. `INCONCLUSIVE` mapeia para UNKNOWN e `N/A` para NOT_TESTABLE em registros G1.2+. Esquema completo em [EVIDENCE-PLAN.md](EVIDENCE-PLAN.md).

Reportar coorte bruta de ocorrências armadas, subconjunto com precondições mantidas, falhas externas, observação desconhecida e cancelamentos explícitos. Nenhuma exclusão silenciosa. Medidas desta missão: **não disponíveis**.

## 7. Revisão adversarial G1.1 executada em especificação

| Ataque | Achado | Reparo / estado |
| --- | --- | --- |
| Contradições | −500–0 ms não pertencia a nenhuma banda | Criado EARLY_TOLERANCE, fora de TARGET |
| Números arbitrários | 10 min, 2/5 s, 1/3 s e 30 min poderiam parecer fatos | Marcados EXPERIMENTAL e versionados antes da rodada |
| Estados não observáveis | “continua armado” exige observador permanente inexistente | ARMED_VERIFIED é checkpoint; READINESS_STALE admite lacuna |
| Promessas não testáveis | “áudio iniciou” misturava callback e emissão | r/a/x e oráculo externo separados |
| Dados sensíveis | Direct Boot poderia virar cópia do WakePlan pessoal | DE mínimo operacional; nome/contexto/voz ficam CE |
| ARMED enganoso | Capability pode mudar entre 22:00 e 02:00 | Snapshot temporal, eventos e revalidação na oportunidade real |
| Direct Boot | Broadcast simulado ou unlock precoce mascaram CE | Reboot real, nenhum unlock e áudio externo obrigatórios |
| DST | Gap/fold e clock backward poderiam duplicar ou omitir | Primeiro válido no gap; primeiro offset/uma vez no fold; terminal não reabre |
| Concorrência | Uma sessão podia absorver B e dismiss A apagá-lo | OUTPUT_OWNER/WAITING, T e terminais por ocorrência |
| Crash/recovery | EVENT_RECEIVED podia ser confundido com convergência | Resultado de reconciliação separado; F55 e failpoints |
| Áudio físico | Logs/player poderiam aprovar silêncio | Detector externo calibrado, raw artifact/checksum/epsilon |
| Estatística | Uma execução ou média entre OEMs poderia “validar” | Repetições por classe, zero S0 e aprovação por célula; sem claim populacional |

Resultado do ataque G1.1: G1 permaneceu CONDITIONAL e `READY_FOR_INSTRUMENTED_EVIDENCE = YES`; a revisão documental não substituiu teste. Depois dela, G1.2 executou E0 (`EVID-G1-0002..0003`); E1 continua ausente.
