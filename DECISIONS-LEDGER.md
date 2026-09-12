# DECISIONS LEDGER

**Projeto:** ALVORADA — codinome provisório  
**Atualizado em:** 2026-09-12

O ledger registra escolhas reais, não ideias plausíveis. Uma hipótese permanece no `SOURCE-OF-TRUTH.md` ou uma incerteza no `OPEN-QUESTIONS.md` até existir decisão consciente.

## Formato permanente

Cada entrada deve conter: `DECISION-ID`, `data`, `status`, `contexto`, `decisão`, `alternativas consideradas`, `racional`, `evidência`, `consequências`, `reversibilidade` e `condição para reabrir`.

Status permitidos: `ACCEPTED`, `SUPERSEDED`, `REVOKED`. Propostas não aceitas não entram como decisão. Ao substituir uma decisão, nunca apague a anterior; marque-a e aponte para a sucessora.

## Decisões atuais

### D-001 — Centro do produto

- **data:** 2026-09-11
- **status:** ACCEPTED
- **contexto:** Produtos adjacentes podem diluir a função central.
- **decisão:** Criar uma experiência inteligente e serena de despertar; não um chatbot matinal, app de meditação, agregador de tarefas, dashboard de produtividade ou alarme convencional apenas embelezado.
- **alternativas consideradas:** As categorias acima, explicitamente rejeitadas no briefing.
- **racional:** O valor depende da qualidade do instante de despertar, não da amplitude funcional.
- **evidência:** Diretriz do fundador; ainda sem validação de mercado.
- **consequências:** Features futuras precisam demonstrar contribuição direta ao despertar e respeitar a identidade calibrada de DP-09.
- **reversibilidade:** Baixa; mudaria a tese do produto.
- **condição para reabrir:** Evidência forte de que a necessidade central é outra e aprovação explícita do fundador.

### D-002 — Status do nome

- **data:** 2026-09-11
- **status:** ACCEPTED
- **contexto:** Um rótulo de trabalho é necessário, mas a marca não foi avaliada.
- **decisão:** Usar ALVORADA somente como codinome; não tratá-lo como nome comercial aprovado.
- **alternativas consideradas:** Aprovação imediata do nome; adiada.
- **racional:** Evitar cristalizar marca antes de pesquisa e decisão próprias.
- **evidência:** Status declarado pelo fundador.
- **consequências:** Documentos e protótipos devem qualificar o nome como provisório.
- **reversibilidade:** Alta.
- **condição para reabrir:** Gate de brand com pesquisa, disponibilidade e decisão do fundador.

### D-003 — Prioridade e independência do alarme

- **data:** 2026-09-11
- **status:** ACCEPTED
- **contexto:** IA e dados remotos introduzem modos de falha incompatíveis com um alarme.
- **decisão:** O disparo do alarme vem primeiro e não depende de IA, API, rede, clima, calendário ou outro serviço opcional.
- **alternativas consideradas:** Compor toda a experiência no instante do disparo; rejeitada como caminho crítico.
- **racional:** Uma camada de enriquecimento jamais pode impedir a função primária.
- **evidência:** Diretriz do fundador e análise lógica de dependência; confiabilidade empírica ainda aberta.
- **consequências:** O baseline e seus recursos essenciais precisam estar prontos localmente.
- **reversibilidade:** Muito baixa; HARD INVARIANT HI-01.
- **condição para reabrir:** Somente mudança explícita da tese de confiança, com evidência superior e revisão constitucional.

### D-004 — Offline e degradação

- **data:** 2026-09-11
- **status:** ACCEPTED
- **contexto:** Conectividade e serviços opcionais falham rotineiramente.
- **decisão:** Offline é estado normal; cada camada opcional ausente é omitida sem atraso, erro narrado ou perda do despertador.
- **alternativas consideradas:** Tratar offline como modo de emergência ou bloquear a experiência enriquecida inteira; rejeitadas.
- **racional:** A complexidade interna não deve aparecer para quem está acordando.
- **evidência:** Diretriz do fundador; comportamento técnico a validar no G1.
- **consequências:** Cada dependência precisa de isolamento e fallback local coerente.
- **reversibilidade:** Muito baixa; HARD INVARIANTS HI-02 e HI-03.
- **condição para reabrir:** Revisão constitucional explícita; indisponibilidade técnica deve reduzir escopo, não eliminar o princípio.

### D-005 — Gentileza com eficácia

- **data:** 2026-09-11
- **status:** ACCEPTED
- **contexto:** Um despertar calmo pode não acordar; um eficaz pode se tornar hostil.
- **decisão:** Otimizar simultaneamente eficácia e serenidade. Sem resposta, aumentar presença progressivamente, nunca por punição ou brutalidade.
- **alternativas consideradas:** Suavidade fixa; intensidade abrupta; ambas rejeitadas como regra geral.
- **racional:** As duas qualidades compõem a proposta e precisam ser conciliadas por evidência.
- **evidência:** Diretriz do fundador; limites e curva ainda não testados.
- **consequências:** G2 deve operacionalizar e medir os dois lados da tensão.
- **reversibilidade:** Muito baixa no princípio; alta nos parâmetros.
- **condição para reabrir:** Evidência de incompatibilidade estrutural, seguida de decisão explícita sobre a própria tese do produto.

### D-006 — Inteligência invisível e contexto seletivo

- **data:** 2026-09-11
- **status:** ACCEPTED
- **contexto:** Ao acordar, volume de informação e interação custam mais.
- **decisão:** A inteligência aparece pela pertinência de poucas intervenções; não exige chatbot e não transforma a manhã em boletim.
- **alternativas consideradas:** Conversa matinal, leitura abrangente de agenda, clima ou tarefas; rejeitadas.
- **racional:** O silêncio e a omissão podem ser melhores que conteúdo disponível, porém irrelevante.
- **evidência:** Diretriz editorial do fundador; política de seleção ainda aberta.
- **consequências:** Toda categoria contextual precisa justificar relevância, atualidade e comprimento.
- **reversibilidade:** Baixa no princípio; alta nas regras de seleção.
- **condição para reabrir:** Pesquisa mostrar de forma consistente que interação ou maior densidade melhora o despertar sem elevar carga.

### D-007 — Relação entre som e voz

- **data:** 2026-09-11
- **status:** ACCEPTED
- **contexto:** A experiência combina paisagem sonora e fala.
- **decisão:** O som forma a continuidade; a voz intervém em momentos específicos e breves.
- **alternativas consideradas:** Monólogo contínuo ou sequência fragmentada que elimina a base sonora; rejeitados como direção atual.
- **racional:** Preservar atmosfera e reduzir carga cognitiva da fala.
- **evidência:** Diretriz do fundador; eficácia de mixagem ainda não testada.
- **consequências:** G2 deve investigar pausas, sobreposição, inteligibilidade e duração.
- **reversibilidade:** Média.
- **condição para reabrir:** Testes mostrarem que outro arranjo melhora simultaneamente compreensão, serenidade e eficácia.

### D-008 — Filosofia editorial

- **data:** 2026-09-11
- **status:** ACCEPTED
- **contexto:** Motivação genérica pode mentir, infantilizar ou invalidar dificuldades.
- **decisão:** Adotar otimismo lúcido: positivo sem garantir resultados, negar problemas ou exigir euforia.
- **alternativas consideradas:** Positividade aspiracional absoluta e neutralidade puramente utilitária; a primeira foi rejeitada, a segunda não foi escolhida como identidade.
- **racional:** Respeitar incerteza e preservar agência realista.
- **evidência:** Diretriz e exemplos editoriais do fundador; recepção ainda não validada.
- **consequências:** Conteúdo precisa de revisão editorial e critérios contra promessas falsas.
- **reversibilidade:** Baixa.
- **condição para reabrir:** Evidência de rejeição consistente e proposta editorial substituta compatível com os invariants.

### D-009 — Privacidade por arquitetura

- **data:** 2026-09-11
- **status:** ACCEPTED
- **contexto:** Agenda, localização e rotina podem revelar dados sensíveis.
- **decisão:** Minimizar coleta, transmissão, centralização e retenção; preferir fronteiras locais quando viáveis; manter dados opcionais fora do requisito do alarme.
- **alternativas consideradas:** Centralização ampla para conveniência; rejeitada como padrão.
- **racional:** A promessa só é crível se o desenho limitar exposição por construção.
- **evidência:** Diretriz do fundador; fluxos concretos ainda não definidos.
- **consequências:** G3 exige inventário de dados, finalidade, retenção, controle e fallback por permissão.
- **reversibilidade:** Muito baixa; HARD INVARIANT HI-06.
- **condição para reabrir:** Necessidade de produto demonstrada, opção menos invasiva esgotada e decisão explícita com análise de risco.

### D-010 — Procedência de citações

- **data:** 2026-09-11
- **status:** ACCEPTED
- **contexto:** Modelos e compilações populares podem inventar ou distorcer atribuições.
- **decisão:** Não usar citação atribuída sem fonte verificável; na dúvida, omitir.
- **alternativas consideradas:** Publicar com ressalva ou confiar em geração automática; rejeitadas.
- **racional:** A confiança editorial vale mais que preencher um espaço de conteúdo.
- **evidência:** Diretriz do fundador; pipeline de verificação ainda aberto.
- **consequências:** Toda citação futura precisa de proveniência auditável e revisão.
- **reversibilidade:** Muito baixa; HARD INVARIANT HI-07.
- **condição para reabrir:** Apenas substituição por padrão de proveniência mais rigoroso, nunca mais permissivo sem revisão constitucional.

### D-011 — Calor sem engano humano

- **data:** 2026-09-11
- **status:** ACCEPTED
- **contexto:** Voz natural pode parecer acolhedora e também sugerir uma pessoa inexistente.
- **decisão:** Usar linguagem humana sem alegar identidade, sentimentos ou relação pessoal do sistema.
- **alternativas consideradas:** Persona que finge reciprocidade; rejeitada.
- **racional:** Afeto não exige personificação enganosa.
- **evidência:** Identidade desejada no briefing; percepção dos usuários ainda aberta.
- **consequências:** Roteiros e voz devem evitar alegações emocionais falsas.
- **reversibilidade:** Muito baixa; HARD INVARIANT HI-08.
- **condição para reabrir:** Questão ética e de produto formalmente revista pelo fundador, com evidência e salvaguardas explícitas.

### D-012 — Fundação antes de implementação

- **data:** 2026-09-11
- **status:** ACCEPTED
- **contexto:** Código e stack precoces podem cristalizar suposições não testadas.
- **decisão:** Especificar invariants, riscos, evidências, arquitetura conceitual e gates antes de implementar ou escolher tecnologia.
- **alternativas consideradas:** Começar por protótipo de interface ou seleção de framework; explicitamente adiadas.
- **racional:** As decisões de maior risco ainda são de confiabilidade e experiência, não de ferramenta.
- **evidência:** Protocolo da MISSÃO 01.
- **consequências:** G0 e G1 não produzem aplicativo nem compromisso de stack.
- **reversibilidade:** Média após os gates fornecerem evidência.
- **condição para reabrir:** Gate anterior aprovado e experimento técnico claramente delimitado, sem virar implementação prematura.

## Explicitamente não decididos

Público validado, versões/modelos Android suportados, arquitetura técnica concreta, stack, voz específica, sons, curva de volume, duração do roteiro, controles finais, fontes de contexto, estética final, política de seleção, limiares/SLOs, modelo de negócio e nome comercial. Plataforma Android e orientação local-first foram decididas abaixo; métricas foram definidas como propostas no G1.

## Decisões explícitas recebidas na MISSÃO 02

Não são resultados de teste. Data de registro de todas as entradas: 2026-09-11.

### D-G0-APPROVAL-01 — Aprovação de G0

- **data:** 2026-09-11
- **status:** ACCEPTED
- **contexto:** G0 era candidato.
- **decisão:** G0 FOUNDATION PASS, conforme declaração do fundador na MISSÃO 02.
- **alternativas consideradas:** Manter G0 pendente; não escolhido pelo fundador.
- **racional:** Estabelecer ponto de partida da investigação.
- **evidência:** Declaração explícita no briefing MISSÃO 02, Texto colado.txt.
- **consequências:** Atualizar status, sem reescrever invariants.
- **reversibilidade:** Histórico não apagável; conteúdo pode ser revisto formalmente.
- **condição para reabrir:** Nova revisão constitucional explícita.

### D-PLATFORM-01 — Android primeiro

- **data:** 2026-09-11
- **status:** ACCEPTED
- **contexto:** Plataforma estava OPEN.
- **decisão:** Primeiro Reliability Contract específico para Android; não assumir compromisso multiplataforma.
- **alternativas consideradas:** Outras plataformas permanecem não escolhidas; nenhuma avaliação comparativa alegada.
- **racional:** Investigar condições reais de uma plataforma.
- **evidência:** Decisão D-PLATFORM-01 do fundador na MISSÃO 02.
- **consequências:** APIs/targets/OEM viram eixos de qualificação; stack segue OPEN.
- **reversibilidade:** Média; expansão de plataforma exige contrato próprio.
- **condição para reabrir:** Mudança de escopo do fundador apoiada em evidência.

### D-DATA-01 — Local-first

- **data:** 2026-09-11
- **status:** ACCEPTED
- **contexto:** G0 estabelecia minimização; fronteira foi refinada.
- **decisão:** Horários, alarmes, lembretes, preferências, histórico necessário e WakePlans locais por padrão. Rede opcional; calendário com autorização explícita; serviços externos proibidos no caminho crítico.
- **alternativas consideradas:** Centralização obrigatória rejeitada pelo briefing; banco e schema não avaliados.
- **racional:** Confiabilidade offline e minimização.
- **evidência:** Decisão D-DATA-01 do fundador.
- **consequências:** Backup, pré-unlock e retenção exigem desenho mínimo; não autorizados por conveniência.
- **reversibilidade:** Baixa no princípio; alta nos mecanismos não escolhidos.
- **condição para reabrir:** Necessidade demonstrada e aprovação explícita compatível com HI-06.

### D-RELIABILITY-01 — Envelope explícito

- **data:** 2026-09-11
- **status:** ACCEPTED
- **contexto:** Confiabilidade universal seria alegação indevida.
- **decisão:** Prometer somente dentro de SUPPORTED RELIABILITY ENVELOPE efetivamente validado.
- **alternativas consideradas:** Garantia universal explicitamente rejeitada.
- **racional:** Escopo verificável e honestidade sobre Android/OEM.
- **evidência:** Decisão D-RELIABILITY-01 do fundador.
- **consequências:** Proposta não vira suporte; estado validado inicial vazio.
- **reversibilidade:** Baixa.
- **condição para reabrir:** Evidência nova amplia células, não transforma promessa em universal.

### D-EXPERIENCE-CORE-01 — Prioridade futura de G2

- **data:** 2026-09-11
- **status:** ACCEPTED
- **contexto:** Elementos de experiência estavam ilustrativos.
- **decisão:** Priorizar paisagem sonora, voz serena, nome, hora, mensagem breve e Escalada Serena no G2. Atmosfera visual apoia; mascote segue hipótese.
- **alternativas consideradas:** Mascote como núcleo obrigatório não escolhido; nenhum estilo/voz final selecionado.
- **racional:** Investigar primeiro o arco de experiência central.
- **evidência:** Decisão D-EXPERIENCE-CORE-01 do fundador.
- **consequências:** Não torna voz remota/nome dependência de entrega; validação perceptiva segue pendente.
- **reversibilidade:** Média na prioridade; alta nos parâmetros.
- **condição para reabrir:** Resultados G2 contradizem valor/aceitação, com revisão registrada.

### D-G1-READINESS-01 — Não mascarar armamento

- **data:** 2026-09-11
- **status:** ACCEPTED
- **contexto:** Configuração e capacidade do SO podem divergir.
- **decisão:** Capacidade essencial ausente exige estado explícito; nunca fingir que um alarme confiável está armado.
- **alternativas consideradas:** Booleano configurado=armado explicitamente insuficiente no briefing.
- **racional:** Evitar falsa confiança.
- **evidência:** Requisito de permissões/modelo da MISSÃO 02.
- **consequências:** Separar intenção, registro e qualidade; checks timestampados. Modelo CT permanece candidato.
- **reversibilidade:** Baixa no princípio.
- **condição para reabrir:** Somente aprimorar observabilidade com evidência, não esconder incerteza.

### D-G1-TELEMETRY-01 — Telemetria mínima local

- **data:** 2026-09-11
- **status:** ACCEPTED
- **contexto:** Reliability precisa de evidência sem vigilância.
- **decisão:** Registrar mínimo necessário de armamento/disparo/áudio/ações/fallback localmente; envio remoto permanece OPEN.
- **alternativas consideradas:** Upload automático não autorizado; ausência total de observação não escolhida.
- **racional:** Permitir diagnóstico com minimização.
- **evidência:** Seção PRIVACIDADE da MISSÃO 02.
- **consequências:** Não registrar conteúdo pessoal; F-03-14 refinou retenção para 30 dias ou 1.000 eventos. Mecanismo e envio remoto seguem OPEN.
- **reversibilidade:** Média nos eventos; remota requer decisão nova.
- **condição para reabrir:** Evidência de custo/risco e finalidade explícita aprovada.

## Decisões explícitas recebidas na MISSÃO 03

Data de registro: 2026-09-11. Todas são políticas para investigação; não são resultados medidos.

### F-03-01 — Faixa candidata Android 12+

- **data:** 2026-09-11
- **status:** ACCEPTED
- **contexto:** O envelope validado está vazio e precisava de piso para investigação.
- **decisão:** Investigar Android 12/API 31+; nenhum API/modelo vira suportado sem evidência.
- **alternativas consideradas:** Abranger Android inteiro ou declarar 31–37 suportado; rejeitadas.
- **racional:** Delimitar trabalho sem confundir candidatura e suporte.
- **evidência:** Decisão do fundador na MISSÃO 03, `Texto colado(1).txt`.
- **consequências:** Emuladores 31/34/35/36/37; células físicas qualificadas separadamente.
- **reversibilidade:** Alta no piso antes de lançamento.
- **condição para reabrir:** Evidência de custo, cobertura ou risco por versão.

### F-03-02 — Semântica de hora civil local

- **data:** 2026-09-11
- **status:** ACCEPTED
- **contexto:** Instante UTC e intenção “07:30” divergem quando o fuso muda.
- **decisão:** Alarmes comuns seguem hora civil no fuso atual; mudança de fuso reconcilia a próxima ocorrência. Fuso fixo fica fora do escopo inicial.
- **alternativas consideradas:** Preservar UTC silenciosamente; rejeitada.
- **racional:** Preservar a intenção reconhecível do usuário.
- **evidência:** Decisão do fundador F-03-02.
- **consequências:** Persistir regra civil e resolver ocorrências one-shot por data/fuso.
- **reversibilidade:** Baixa no primeiro escopo.
- **condição para reabrir:** Pesquisa de produto exigir alarmes com fuso fixo.

### F-03-03 — DST gap

- **data:** 2026-09-11
- **status:** ACCEPTED
- **contexto:** Alguns horários civis não existem no avanço DST.
- **decisão:** Disparar na primeira hora civil válida posterior e registrar `GAP_FORWARD`.
- **alternativas consideradas:** Omitir ou manter minutos relativos após a lacuna; não escolhidas.
- **racional:** Não descartar silenciosamente a ocorrência.
- **evidência:** Decisão do fundador F-03-03.
- **consequências:** T06 e modelo precisam verificar ajuste e não duplicação.
- **reversibilidade:** Média.
- **condição para reabrir:** Evidência de incompreensão ou dano recorrente.

### F-03-04 — DST fold

- **data:** 2026-09-11
- **status:** ACCEPTED
- **contexto:** Um horário civil pode ocorrer duas vezes no recuo DST.
- **decisão:** Usar a primeira ocorrência válida e tocar apenas uma vez.
- **alternativas consideradas:** Segunda ocorrência ou ambas; rejeitadas.
- **racional:** Evitar duplicação surpreendente.
- **evidência:** Decisão do fundador F-03-04.
- **consequências:** Identidade inclui escolha do offset e preserva terminal no segundo fold.
- **reversibilidade:** Média.
- **condição para reabrir:** Evidência de expectativa diferente no público suportado.

### F-03-05 — Late recovery

- **data:** 2026-09-11
- **status:** ACCEPTED
- **contexto:** Recuperação sem limite pode tocar horas depois.
- **decisão:** Até 10 minutos inclusive, tentar uma vez como `RECOVERED_LATE`; depois, não tocar e registrar MISSED quando comprovado.
- **alternativas consideradas:** Nunca recuperar ou recuperar sem limite; rejeitadas.
- **racional:** Equilibrar utilidade e surpresa.
- **evidência:** Decisão do fundador F-03-05; valor ainda sem teste.
- **consequências:** 10 min é threshold experimental pré-registrado; UNKNOWN permanece quando faltar prova.
- **reversibilidade:** Alta no valor, baixa na necessidade de limite.
- **condição para reabrir:** Distribuição de falhas e pesquisa de experiência.

### F-03-06 — Bandas de entrega agendada

- **data:** 2026-09-11
- **status:** ACCEPTED
- **contexto:** Contrato sem limiar não produz PASS quantitativo.
- **decisão:** TARGET 0–2.000 ms; aceitável até +5.000 ms; antecipação além de 500 ms ou atraso acima de 5.000 ms falham.
- **alternativas consideradas:** ±1 s arbitrário ou tolerância pós-hoc; rejeitadas.
- **racional:** Fixar fronteiras antes de observar resultados.
- **evidência:** Decisão do fundador F-03-06; em G1.2 E0 validou somente a lógica das bandas, sem resultado Android ou físico.
- **consequências:** −500–0 ms é `EARLY_TOLERANCE`, não TARGET; epsilon pode tornar fronteira inconclusiva.
- **reversibilidade:** Alta por evidência; toda mudança cria nova policy version.
- **condição para reabrir:** Caracterização pré-registrada ou necessidade demonstrada, nunca para apagar falha.

### F-03-07 — Bandas trigger-to-audio

- **data:** 2026-09-11
- **status:** ACCEPTED
- **contexto:** Receiver e callback do player não provam áudio físico.
- **decisão:** Trigger-to-audio TARGET ≤1.000 ms, aceitável ≤3.000 ms, falha >3.000 ms, aplicado separadamente às métricas de software e física.
- **alternativas consideradas:** Uma métrica ambígua “áudio iniciado”; rejeitada.
- **racional:** Separar execução interna de efeito acústico.
- **evidência:** Decisão do fundador F-03-07.
- **consequências:** Claim físico exige oráculo externo e `x`; callback não aprova audibilidade.
- **reversibilidade:** Alta nos valores, baixa na separação epistêmica.
- **condição para reabrir:** Evidência/calibração, com policy version nova.

### F-03-08 — Soneca de cinco minutos

- **data:** 2026-09-11
- **status:** ACCEPTED
- **contexto:** Soneca não podia alterar recorrência ou perder identidade.
- **decisão:** Cinco minutos; filho rastreável da ocorrência atual; regra recorrente permanece independente.
- **alternativas consideradas:** Editar regra original ou reutilizar a mesma ocorrência; rejeitadas.
- **racional:** Evitar duplicação e efeitos permanentes implícitos.
- **evidência:** Decisão do fundador F-03-08.
- **consequências:** Pai só vira SNOOZED após registro do filho; máximo e mecanismo pós-reboot seguem OPEN.
- **reversibilidade:** Alta no intervalo; baixa na identidade pai-filho.
- **condição para reabrir:** Evidência G1/G2 sobre quotas, eficácia ou compreensão.

### F-03-09 — Escopo de dismiss

- **data:** 2026-09-11
- **status:** ACCEPTED
- **contexto:** Uma ação terminal podia cancelar recorrência ou alarmes alheios.
- **decisão:** Dismiss encerra somente ocorrência/sessão atual, salvo ação permanente explicitamente diferente.
- **alternativas consideradas:** Desabilitar regra ou cancelar futuros implicitamente; rejeitadas.
- **racional:** Preservar intenção e previsibilidade.
- **evidência:** Decisão do fundador F-03-09.
- **consequências:** Tombstone occurrence-scoped; ação em A não afeta B.
- **reversibilidade:** Baixa.
- **condição para reabrir:** Evidência de controle explícito superior, sem ambiguidade.

### F-03-10 — Limite operacional da wake session

- **data:** 2026-09-11
- **status:** ACCEPTED
- **contexto:** Sessão sem limite impede testar lifecycle, bateria e recuperação.
- **decisão:** Usar 30 minutos como máximo operacional inicial.
- **alternativas consideradas:** Sessão ilimitada ou duração de UX final; rejeitadas nesta fase.
- **racional:** Criar fronteira segura e testável.
- **evidência:** Decisão do fundador F-03-10; valor não validado com usuários.
- **consequências:** Após 30 min, terminar com `UNANSWERED`; G2 pode propor outro valor.
- **reversibilidade:** Alta.
- **condição para reabrir:** Evidência de recursos/confiabilidade ou experiência G2.

### F-03-11 — Concorrência de ocorrências

- **data:** 2026-09-11
- **status:** ACCEPTED
- **contexto:** Alarmes simultâneos podem apagar identidade ou controle uns dos outros.
- **decisão:** Identidades e resultados independentes; um output físico por vez; ocorrência due durante outra não pode ser perdida; ações de A não afetam B.
- **alternativas consideradas:** Cancelamento implícito ou streams sobrepostos; rejeitados.
- **racional:** Manter rastreabilidade e controle acústico.
- **evidência:** Decisão do fundador F-03-11.
- **consequências:** Modelo `OUTPUT_OWNER/OUTPUT_WAITING`; a espera de B conta no timing. UX/arbitragem seguem OPEN.
- **reversibilidade:** Média no mecanismo, baixa na independência.
- **condição para reabrir:** Evidência técnica/UX mantendo todas as garantias mínimas.

### F-03-12 — Direct Boot no target

- **data:** 2026-09-11
- **status:** ACCEPTED
- **contexto:** Reboot sem primeiro unlock pode deixar dados CE inacessíveis.
- **decisão:** Investigar e qualificar alarme previamente armado em reboot + nenhum unlock + T, usando mínimo device-protected.
- **alternativas consideradas:** Excluir pré-unlock do target inicial; rejeitada.
- **racional:** Sobrevivência ao reboot é parte da tese de confiabilidade.
- **evidência:** Decisão do fundador F-03-12; nenhum ensaio real.
- **consequências:** Conteúdo pessoal permanece CE; fallback local mínimo é obrigatório; broadcast simulado não qualifica.
- **reversibilidade:** Média no envelope futuro, baixa no target da investigação autorizada.
- **condição para reabrir:** Impossibilidade demonstrada e decisão explícita de reduzir envelope.

### F-03-13 — Backup/restore não transporta armamento

- **data:** 2026-09-11
- **status:** ACCEPTED
- **contexto:** Dados restaurados não provam scheduling vigente no SO novo.
- **decisão:** Nunca restaurar ARMED; reconstruir readiness; proibir rearmamento automático após restore até política futura.
- **alternativas consideradas:** Copiar flag/tokens e rearmar silenciosamente; rejeitada.
- **racional:** Evitar falsa confiança e alarmes surpresa.
- **evidência:** Decisão do fundador F-03-13.
- **consequências:** Restore volta a READINESS_CHECK_REQUIRED.
- **reversibilidade:** Baixa na proibição de copiar estado; média no futuro fluxo explícito.
- **condição para reabrir:** Política de restore aprovada com consentimento e evidência end-to-end.

### F-03-14 — Retenção de telemetria

- **data:** 2026-09-11
- **status:** ACCEPTED
- **contexto:** Diagnóstico precisa de limite e minimização.
- **decisão:** Telemetria local-first por 30 dias ou 1.000 eventos, o que ocorrer primeiro; usuário pode limpar; conteúdo pessoal listado é proibido por padrão.
- **alternativas consideradas:** Retenção indefinida, conteúdo completo ou envio remoto automático; rejeitados.
- **racional:** Diagnóstico suficiente com menor exposição.
- **evidência:** Decisão do fundador F-03-14.
- **consequências:** Rotação não pode bloquear o alarme; envio remoto continua OPEN.
- **reversibilidade:** Média, compatível com HI-06.
- **condição para reabrir:** Finalidade e evidência de necessidade, com nova decisão de privacidade.

### F-03-15 — Harness descartável autorizado para missão futura

- **data:** 2026-09-11
- **status:** ACCEPTED
- **contexto:** G1 precisa passar de especificado a observado sem cristalizar o produto.
- **decisão:** Autorizar missão futura para construir harness exclusivo de reliability, sem UX/features G2 ou stack de produção.
- **alternativas consideradas:** Implementar o app ou continuar só documentalmente; não escolhidas.
- **racional:** Produzir evidência isolada do caminho crítico.
- **evidência:** Decisão do fundador F-03-15.
- **consequências:** MISSÃO 03 não implementa; próxima missão pode construir E0/E1 dentro desse limite.
- **reversibilidade:** Alta antes de iniciar a missão futura.
- **condição para reabrir:** Mudança de escopo, risco ou orçamento antes da execução.

## Decisão explícita recebida na MISSÃO 05R

### D-G1-LAB-01 — Binding privado e zero-overage

- **data:** 2026-09-12
- **status:** ACCEPTED
- **contexto:** GitHub-hosted Linux era capacidade documentada, mas ALVORADA não possuía binding executável.
- **decisão:** Usar um único repositório privado canônico `ALVORADA`, GitHub Actions como laboratório E1 primário, runner standard `ubuntu-24.04`, somente minutos incluídos e `PAID_OVERAGE_ALLOWED = FALSE`.
- **alternativas consideradas:** Repo público, vários repos, larger runner pago, infraestrutura paga externa e self-hosted; não escolhidos nesta missão.
- **racional:** Tornar a execução rastreável sem exposição pública, fragmentação ou autorização financeira implícita.
- **evidência:** Decisão do fundador na MISSÃO 05R; repo privado e snapshot confirmados em `EVID-G1-0012`.
- **consequências:** Discovery só pode rodar após hard stop de overage, saldo e Actions habilitado serem observados; adapter/Wave 1 continuam fora da missão.
- **reversibilidade:** Média no provedor/runner; baixa na proibição de cobrança silenciosa.
- **condição para reabrir:** GitHub-hosted standard provar-se inviável, franquia insuficiente ou risco de custo/privacidade exigir nova decisão explícita.

## Propostas G1 que ainda NÃO são decisões aceitas

| ID | Proposta / questão | Condição de aceitação |
| --- | --- | --- |
| P-G1-DB-FIELDS | Campo a campo do mínimo device-protected e migração | Harness demonstra necessidade; revisão de minimização antes de produto |
| P-G1-SNOOZE-REBOOT | Reconstrução da soneca após reboot e mecanismo Android | Comparação E0/E1/E2 sem perda/duplicação |
| P-G1-CONCURRENCY-UX | Arbitragem entre OUTPUT_OWNER/WAITING e controles múltiplos | Evidência técnica G1 + decisão UX futura, preservando F-03-11 |
| P-G1-05 | FSI ou controles alternativos e notificação sem toque duplicado | Testes de apresentação/áudio; não burlar canal |

H-G1-01–H-G1-04 continuam hipóteses de solução. CT-01–CT-10 são obrigações; o harness G1.2 implementou apenas o subconjunto lógico E0, sem alegação Android/produto. Thresholds são experimentais, não SLO comercial nem resultado medido.
