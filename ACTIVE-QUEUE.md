# ACTIVE QUEUE

**Projeto:** ALVORADA — codinome provisório  
**Atualizado em:** 2026-09-14

Esta é uma fila de gates de conhecimento, não um roadmap de features nem um cronograma. Um gate só abre após aprovação do anterior e pode mandar o projeto voltar, reduzir escopo ou encerrar uma hipótese.

## G0 — FOUNDATION

**Estado:** PASS — aprovação explícita do fundador na MISSÃO 02.

- **Objetivo:** fixar propósito, limites, linguagem de memória, invariants, decisões reais, incertezas e ordem de investigação.
- **Entrada:** briefing fundador da MISSÃO 01.
- **Saída:** os sete documentos do Foundation Kernel, coerentes entre si e sem hipótese disfarçada de fato ou decisão.
- **Critério de aprovação:** fundador confirma visão, hard invariants, decisões registradas, questões P0 e passagem ao G1; revisão cruzada não encontra contradição material ou item sem rótulo epistemológico.
- **Não fazer ainda:** código, stack, UI final, marca final, catálogo de features, integrações ou alegações de desempenho.

## G1 — RELIABILITY

**Estado:** CONDITIONAL — G1.1 PASS; G1.2 `E0_PASS`; G1.3 / MISSÃO 05R `PUBLIC_BINDING_READY_DISCOVERY_NOT_RUN`. Repo público, Actions e snapshot vinculados; nenhum run, precheck, envelope Android ou físico validado.

- **Objetivo:** transformar “o alarme vem primeiro” em contrato verificável e arquitetura conceitual de contenção de falhas.
- **Entrada:** G0 aprovado; HI-01 a HI-06; OQ-REL-01, OQ-REL-02 e OQ-AND-01 priorizadas.
- **Saída:** condições suportadas e não suportadas; modelo de estados do alarme; matriz de falhas e recuperação; fronteira entre núcleo e camadas opcionais; métricas e protocolo de teste; riscos e evidências ainda ausentes.
- **Evidência documental produzida:** nove documentos em `docs/reliability/`, pesquisa oficial até API 37, 56 cenários, 15 protocolos, policy freeze e plano E0–E5.
- **Evidência instrumentada produzida:** harness JVM descartável `0.1.0`; baseline E0 no SHA `06a8cbbc2b75e9b2e415f87574b5a1307b524d8b` passou 82 testes/100.000 sequências (`EVID-G1-0002..0003`). O repo público `phpedrogarcia-afk/ALVORADA` preserva o snapshot de 53 arquivos com mapa explícito de migração/sanitização; a auditoria de publicação e a contenção da rota externa estão em `EVID-G1-0013..0014`. E1 executou zero cenários (`EVID-G1-0004..0014`).
- **Políticas fechadas:** API 31+ candidata; hora civil e DST; late 10 min; bandas 2/5 s e 1/3 s; soneca 5 min; dismiss; sessão 30 min; concorrência independente; Direct Boot; restore e retenção 30 dias/1.000 eventos.
- **Condições restantes para PASS:** aplicar/publicar a correção de binding por Git local com metadados noreply verificáveis; executar um único discovery; se passar, congelar revisões e completar o precheck mínimo API 36; só em missão posterior compilar adapter Android e iniciar Wave 1. Depois executar E1 completa, E2–E5, calibrar áudio/epsilon, selecionar células físicas, resolver mecanismos experimentais e aprovar cada célula. Conjunto validado permanece vazio.
- **Critério de aprovação:** cada modo crítico conhecido tem comportamento esperado e teste proposto; nenhuma camada opcional aparece no caminho crítico; alegações de confiabilidade têm escopo e limiar explícitos; decisões de plataforma são registradas sem escolher stack por conveniência.
- **Não fazer ainda:** implementar o aplicativo, selecionar framework, polir áudio ou UI, conectar clima/calendário, gerar conteúdo ou prometer confiabilidade universal.

## G2 — EXPERIENCE

**Estado:** BLOQUEADO até G1 PASS; não iniciado.

- **Objetivo:** operacionalizar a faixa entre serenidade e eficácia e validar o arco mínimo do despertar.
- **Entrada:** contrato de confiabilidade aprovado; perguntas PRODUCT, UX, AUDIO e VOICE relevantes; protocolo seguro de teste.
- **Prioridade do fundador:** paisagem sonora, voz serena, nome, hora, mensagem breve e Escalada Serena; visual de suporte, mascote não obrigatório.
- **Saída:** especificação experimentável do arco de despertar; estágios de escalada; relação entre som e voz; ações essenciais; limites sensoriais e de acessibilidade; hipóteses isoladas e resultados de testes.
- **Critério de aprovação:** evidência com público definido mostra que o conceito acorda e é percebido como sereno; falhas e subgrupos são descritos; parâmetros permanecem ajustáveis; nenhum elemento estético é promovido a requisito sem benefício demonstrado.
- **Não fazer ainda:** UI final, identidade de marca, biblioteca extensa de conteúdo, inteligência contextual real, integrações, gamificação, dashboard ou escala.

## G3 — CONTEXT INTELLIGENCE

**Estado:** BLOQUEADO por G2

- **Objetivo:** decidir quando o contexto merece atravessar a manhã e fazê-lo com precisão, privacidade e fallback.
- **Entrada:** experiência mínima validada; política inicial de carga cognitiva; OQ-CONTEXT e OQ-PRIVACY; invariants de offline, degradação e proveniência.
- **Saída:** política de seleção e omissão; taxonomia de sensibilidade e consequência; requisitos de atualidade/confiança; inventário e fronteiras de dados; comportamento por permissão e falha; padrão de proveniência editorial; plano de avaliação.
- **Critério de aprovação:** falsos positivos e negativos têm custos e limites definidos; o baseline local permanece inteiro; cada dado tem finalidade e retenção; exemplos de alto risco falham de modo seguro; atribuições são auditáveis.
- **Não fazer ainda:** ler agenda inteira, adicionar feeds/tarefas/chat, buscar muitas integrações, centralizar dados por conveniência, personalização opaca ou geração irrestrita de citações.

## G4 — LEARNING / VALIDATION

**Estado:** BLOQUEADO por G3

- **Objetivo:** testar se a experiência completa cria valor recorrente para um público específico e sustenta uma próxima decisão de produto.
- **Entrada:** núcleo confiável especificado, experiência mínima validada, contexto limitado com regras de segurança e perguntas de produto/negócio explícitas.
- **Saída:** evidência longitudinal de uso e percepção; segmentos e contraindicações; síntese de falhas; `SCAR`, `PATTERN` e `WIN` somente quando demonstrados; recomendação de avançar, pivotar, reduzir ou encerrar; questões de marca e negócio atualizadas.
- **Critério de aprovação:** benefício recorrente supera custo de configuração, permissões e confiança; resultados não dependem apenas de demonstração ou novidade; riscos críticos possuem limites; próxima aposta é explícita e proporcional à evidência.
- **Não fazer ainda:** lançamento amplo, escala operacional, roadmap gigante, promessa comercial, expansão de categoria ou nome definitivo sem sua investigação própria.

## Próxima ação autorizada

MISSÃO 05R está **`PUBLIC_BINDING_READY_DISCOVERY_NOT_RUN`**, custo USD 0 e zero execuções E1. O repo público, Actions e o snapshot estão vinculados; publicar esta correção somente por Git local com metadados noreply verificáveis. Depois, continuar a mesma missão com apenas um discovery e, se aprovado, precheck mínimo API 36. Não iniciar Wave 1, E2, G2, app de produto, UI final, stack de produção ou suporte físico.
