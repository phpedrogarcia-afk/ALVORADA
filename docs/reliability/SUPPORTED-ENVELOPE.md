# SUPPORTED RELIABILITY ENVELOPE

ALVORADA — codinome. 2026-09-12. **G1 CONDITIONAL; G1.2 = E0_PASS; G1.3/MISSÃO 05 = LAB_BLOCKED**.
**Envelope validado atual: conjunto vazio.** O modelo JVM passou E0; nenhuma combinação Android/aparelho/build/app foi executada. O quadro abaixo é proposta de qualificação, não suporte anunciado.

## Evidência instrumental atual

`EVID-G1-0002..0003` validam somente a coerência executável do modelo no harness `0.1.0`. `EVID-G1-0004..0008` são preflights `ENVIRONMENT_BLOCKED`; `EVID-G1-0009..0010` auditam rotas e FACT-DOC, mas não executam Android. GitHub Linux é capaz em documentação e ainda não está vinculado ao projeto. Total: zero APIs e zero cenários E1; nenhuma célula foi adicionada por interpolação, sucesso JVM ou capacidade do provedor.

## Eixos que identificam uma célula de suporte

Uma célula contém: modelo e variante física, OEM, fingerprint/build e patch do SO, API, target do APK, versão/hash do APK, via de instalação, perfil de usuário, política energética, permissões/canal, estado de boot/desbloqueio, rota de áudio e política temporal. Emulador não qualifica audibilidade física. OTA, atualização de app, target ou política relevante reabrem a célula.

## Faixa de investigação aprovada — F-03-01

| Dimensão | Proposta inicial | O que falta para virar VALIDATED |
| --- | --- | --- |
| Plataforma | Smartphones Android, não Wear/TV/Auto | Aprovar escopo físico e amostra |
| Versões | Android 12/API 31+ é o envelope candidato. Emuladores iniciais: APIs 31, 34, 35, 36 e 37 | Cada API/célula precisa de evidência; 32/33 entram por risco específico, sem interpolação |
| Referência inicial | Pixel/referência próxima de AOSP API 37, depois piso físico API 31; Samsung e Xiaomi/Redmi/POCO em E3 | Escolher modelos/builds concretos; família não significa suporte |
| APK / distribuição | App lançado pelo usuário ao menos uma vez; instalação íntegra; target registrado, exercitando 35 e 37 quando aplicáveis | APK não existe; revisão Play de USE/FSI pendente |
| Perfil | Perfil pessoal principal em execução; sem pausa administrativa | Privado bloqueado/work profile não entram por analogia |
| Energia | Ligado, boot concluído com antecedência validada; sem restrição manual nem pausa extrema | Medir margem de recuperação B; bateria baixa não tem porcentagem mágica |
| Vida do processo | Processo morto por SO, cached e remoção de recentes entram como casos a qualificar | Testes separados de force-stop e stop-app |
| Scheduling | Intenção persistida, ocorrência resolvida, permissão exata vigente, registro concluído | H-G1-01 e recovery instrumentados |
| Apresentação | Notifications e canal aptos; FSI permitido ou variante heads-up explicitamente validada | Controles no escuro, lockscreen, tela apagada e em uso |
| Áudio | Alto-falante interno funcional, volume não zero em faixa validada, DND compatível | Medição física e lifecycle válido; não inferir pelo retorno de API |
| Ambiente | Sem chamada/VoIP ativa na primeira célula; Bluetooth/fones fora da primeira qualificação | Ensaios próprios podem adicionar essas células depois |
| Rede/contexto | Ausentes por padrão de teste; qualquer enriquecimento é opcional | Testes de isolamento incluindo preparação travada |
| Tempo | Hora civil no fuso atual; gap primeiro válido; fold primeiro offset/uma vez; late recovery ≤10 min | Células separadas de DST, mudança de relógio e soneca; valores são experimentais |
| Boot antes de unlock | Target E-DB separado: somente estado mínimo device-protected e fallback local | Ensaio real de reboot bloqueado; broadcast sintético não qualifica |
| Capacidade | Soneca 5 min; sessão operacional 30 min; ocorrências independentes e um output por vez | Máximo de snoozes e arbitragem OPEN; T08/T15, sem suporte ilimitado |

APIs 19–30 foram estudadas para semântica e transições históricas, não constituem minSdk escolhido. Não recomendar reduzir target para fugir de restrições atuais.

## Preconditions do rótulo completo

Intenção ativa e durável; próxima ocorrência identificada; checkpoint `ARMED_VERIFIED` para boot/build/generation correntes; agendamento exato concluído; baseline local acessível; controles disponíveis na célula; nenhum bloqueio conhecido; célula qualificada. Timing experimental: trigger TARGET 0–2 s, aceitável até 5 s, antecipação além de 500 ms falha; handoff interno TARGET ≤1 s, aceitável ≤3 s. Antecedência A, margem B e epsilon ainda serão caracterizados. Até existir célula aprovada, existe “agendamento experimental”, não suporte.

Morte normal do processo, offline e Doze não podem ser excluídos só para melhorar os números: são condições obrigatórias de qualificação do produto.

## UNCONTROLLED / DEVICE-SPECIFIC RISK

Fora do contrato de entrega pontual: desligado/sem bateria; boot sobre o deadline; force-stop; dados apagados/desinstalação; perfil suspenso/privado bloqueado; restrição administrativa; pausa extrema; volume zero/mute; DND impeditivo; hardware avariado; roteamento/periférico não qualificado; chamada ativa não qualificada; alteração de relógio sem janela de reconciliação; OEM/build não ensaiado.

Não é autorização para ignorar esses casos. O app deve preservar intenção quando possível, mostrar risco na próxima oportunidade, reconciliar se autorizado e registrar resultado incerto. Se o evento externo surgiu depois de armar, manter a ocorrência na coorte de confiabilidade bruta e classificá-la; não apagá-la retroativamente do denominador.

## Qualificação e retirada

1. Congelar a policy version e pré-registrar célula, cenário, limites e oráculo.
2. Executar T01–T15 pertinentes nos estágios E0–E5, com testemunha acústica externa quando o claim for físico.
3. Registrar tentativas, latências, faltas, duplicações, resultados desconhecidos e exclusões.
4. Aprovar célula explicitamente; só então incluir no envelope validado.
5. Regressão crítica suspende a célula; nova aprovação exige reparo e repetição da suíte afetada.
6. Exposição do suporte ao usuário deve distinguir suporte validado, experimental, configuração bloqueada e risco externo; não usar um selo global “Android compatível”.

Base documental: [registro R01–R34](ANDROID-RELIABILITY-RESEARCH.md). Políticas: [POLICY-FREEZE.md](POLICY-FREEZE.md). Estágios, repetições e células: [EVIDENCE-PLAN.md](EVIDENCE-PLAN.md). Protocolos: [TEST-PROTOCOL.md](TEST-PROTOCOL.md). Evidência normativa justifica investigar; não substitui qualificação.
