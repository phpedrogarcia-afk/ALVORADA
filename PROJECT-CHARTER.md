# PROJECT CHARTER

**Projeto:** ALVORADA — codinome, não nome comercial aprovado  
**Estágio:** G0 PASS; G1 RELIABILITY CONDITIONAL; G1.2 `E0_PASS / E1_CONDITIONAL`  
**Atualizado em:** 2026-09-12

## Problema

Despertadores tradicionais conhecem a hora, mas ignoram o dia para o qual a pessoa está acordando. Acrescentar contexto sem disciplina cria o problema oposto: uma manhã invadida por informação, notificações, dependências remotas e linguagem artificial. Produtos excessivamente suaves também podem falhar na função primária de acordar.

O problema a resolver é: **como ajudar alguém a acordar no horário, de maneira serena e eficaz, oferecendo no máximo o contexto que realmente merece chegar naquele instante, sem sacrificar confiabilidade, privacidade ou autonomia?**

## Visão

Criar uma experiência inteligente e serena de despertar. O núcleo é um excelente despertador que funciona localmente. Camadas opcionais podem compreender uma parte limitada do dia e intervir com parcimônia por som, voz e ambiente visual.

A inteligência deve ser percebida pela pertinência da manhã, não por uma conversa com um sistema.

**DECISION pós-G0:** Android primeiro, local-first e promessa limitada ao envelope validado. O envelope validado atual é vazio; E0 demonstrou coerência do modelo, não desempenho Android, acústico ou humano.

### Calibração da identidade

A direção desejada vive entre extremos: serena sem ser sonolenta; positiva sem ser ingênua; filosófica sem ser pedante; inteligente sem se exibir; lúdica sem infantilizar; bonita sem perder função; humana sem fingir ser pessoa. Essa calibração é um princípio de avaliação, não uma especificação visual ou uma licença para adicionar componentes.

## Hipótese de valor

**HYPOTHESIS H-001:** uma combinação de despertar confiável, progressão sensorial cuidadosa e contexto breve e seletivo pode fazer a pessoa sentir-se mais orientada e menos agredida ao acordar do que com um alarme convencional, sem exigir interação adicional.

Isso ainda não foi demonstrado com usuários. A proposta perde valor se qualquer uma destas condições falhar: o alarme não acorda, o conteúdo incomoda, o contexto erra, ou a privacidade deixa de ser confiável.

## Experiência pretendida

O arco pretendido, ainda sujeito a validação, é:

1. o alarme começa no horário por um caminho independente de serviços opcionais;
2. uma paisagem sonora permanece e ganha presença de forma controlada;
3. uma voz serena intervém brevemente com nome, hora e mensagem breve como prioridades de investigação do G2;
4. apenas quando for relevante e confiável, entra um fragmento de contexto ou reflexão;
5. se não houver resposta, a experiência escala com serenidade;
6. se contexto, rede ou inteligência não estiverem disponíveis, permanece um despertar local coerente.

Os exemplos de harpa, sinos, piano, flauta, clima, consulta, reflexões, citações e um possível componente lúdico/afetivo são direções ilustrativas, não catálogo aprovado nem roteiro obrigatório.

D-EXPERIENCE-CORE-01 prioriza paisagem sonora, voz serena, nome, hora, mensagem breve e Escalada Serena. A obrigatoriedade é investigá-los no núcleo G2, não tornar voz/nome dependências do alarme básico em caso de falha. Atmosfera visual é suporte; mascote/personagem permanece HYPOTHESIS.

## Público inicial

**HYPOTHESIS H-AUDIENCE-01 (refina H-002):** pessoas que usam alarme diariamente, consideram o despertar tradicional desagradável e desejam uma transição mais calma para o dia. Não pressupor mercado validado, disposição para pagar, sleepers extremos ou necessidades clínicas.

Permanecem **OPEN**: segmento prioritário, intensidade real da dor, necessidades de acessibilidade, disposição para conceder permissões e diferenças entre quem precisa de um despertar leve ou intenso. Não há persona validada.

## North Star

**A pessoa acorda no horário com uma experiência percebida como serena, eficaz, pertinente e confiável — inclusive quando as camadas inteligentes não estão disponíveis.**

Uma métrica composta e seus limiares ainda são **OPEN**. Nenhuma métrica de engajamento, tempo de tela ou volume de conteúdo substitui esse resultado.

## Critérios de sucesso

O conceito somente avança se houver evidência de que:

- alarmes configurados são entregues de modo confiável nas condições oficialmente suportadas;
- a experiência acorda, não apenas relaxa, sem recorrer a agressão sensorial ou verbal;
- usuários consideram as intervenções curtas, oportunas e fáceis de compreender ao despertar;
- erros ou ausência de contexto são omitidos sem prejudicar o núcleo;
- o modo offline continua sendo um produto coerente, e não um estado quebrado;
- qualquer contexto pessoal usado é mínimo, compreensível e protegido por arquitetura;
- toda atribuição a autor possui procedência verificável;
- o benefício supera o custo de configuração, permissões e confiança exigidas.

G1.1 congelou thresholds experimentais de timing para produzir evidência; eles são decisões de teste, não fatos de desempenho nem promessa ao usuário. Limiares de resultado humano/experiência e uma North Star composta continuam OPEN.

## Principais riscos

1. **Falsa confiança:** o produto parecer confiável sem sobreviver às condições reais do sistema operacional e do dispositivo.
2. **Serenidade ineficaz:** a experiência ser agradável, mas não acordar pessoas com diferentes perfis de sono.
3. **Escalada agressiva:** a tentativa de aumentar eficácia violar a promessa de não agredir.
4. **Contexto errado ou excessivo:** dados incorretos, desatualizados, sensíveis ou irrelevantes atravessarem um momento vulnerável.
5. **Voz intrusiva:** nome, intimidade, prosódia ou frequência gerarem estranheza e rejeição.
6. **Privacidade cosmética:** alegar cuidado enquanto dados pessoais são centralizados ou retidos sem necessidade.
7. **Fabricação editorial:** reflexões ou citações falsas corroerem confiança.
8. **Proposta sem demanda:** a experiência ser admirada em demonstração, mas não adotada diariamente ou valorizada economicamente.

## Limites atuais do escopo

### Dentro do escopo conceitual

- despertar local confiável;
- progressão de som, voz e escalada a serem testadas;
- seleção mínima de contexto com fallback explícito;
- privacidade, proveniência e memória institucional;
- investigação por gates antes de compromissos de implementação.

### Fora do escopo nesta fase

- implementação do aplicativo ou escolha de stack;
- UI final, identidade visual final ou aprovação do nome comercial;
- chatbot matinal, app de meditação, agregador de tarefas ou dashboard de produtividade;
- lista ampla de integrações, features ou fontes de conteúdo;
- recomendações médicas, diagnóstico do sono ou promessas de saúde;
- modelo de negócio, lançamento e escala antes da validação do valor;
- garantias universais além de condições técnicas explicitamente suportadas.
