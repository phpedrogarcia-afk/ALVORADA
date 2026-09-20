# MISSÃO 05R — PROPOSTA DE CATALOG LOCK CANÔNICA (R1)
**Document Version:** 1.0  
**Generated At (UTC):** 2026-09-20T22:30:00Z  
**Contract Identifier:** `ALVORADA_CATALOG_LOCK_PROPOSAL_V1`  
**Proposal Payload SHA-256:** `55087ef875573c7204251cd22ddd5fa92dd35b98321d95bcf41e60bddcc50d9f`  
**Status:** `READY_FOR_HUMAN_REVIEW` — `LOCK_APPROVED=NO`

---

## 1. Origem Empírica e Linhagem da Prova

Esta proposta de lock canônica foi gerada e validada de forma estritamente somente-leitura pelo harness de confiabilidade na infraestrutura oficial de CI (`ubuntu-24.04`), em conformidade com o design congelado `05R-E-CATALOG-DESIGN-R1` e `R1A`.

| Parâmetro | Valor Observado |
| :--- | :--- |
| **Repositório** | `phpedrogarcia-afk/ALVORADA` |
| **Branch de Autonomia** | `fio/autonomy-g1` |
| **Commit SHA de Execução** | `059bd29bd191d5430480c0398f63387b01d866d4` |
| **Workflow GitHub Actions** | `.github/workflows/e1-lab-catalog-discovery.yml` (`E1 lab catalog discovery`) |
| **Run ID** | `35540374123` |
| **Job ID** | `106156808636` |
| **Artifact ID Preservado** | `10614013929` |
| **Artifact SHA-256** | `a8c741a7b2aa1d84df230504bba597f07dd8bac40fe16f4f28721a76b3fd2d1d` |
| **Tempo de Execução** | 13 segundos |
| **Custo Financeiro** | USD 0.00 (minutos inclusos de runner padrão) |

---

## 2. Matriz de Projeção dos 5 Pacotes HARD_LOCK

O parser `CatalogParser` filtrou e projetou exclusivamente os 5 pacotes autorizados da consulta upstream `sdkmanager --list --verbose --channel=0`:

| Pacote Canônico | Estado Classificado | Revisão Catálogo (Canal 0) | Revisão Instalada no Runner | Ação Necessária para Wave 1 |
| :--- | :--- | :--- | :--- | :--- |
| `build-tools;36.0.0` | `PRESENT_MATCHING_CATALOG` | `36.0.0` | `36.0.0` | Nenhuma (revisão já presente na imagem base) |
| `emulator` | `ABSENT` | `37.1.11` | `None` | Instalação efêmera de `emulator` 37.1.11 |
| `platform-tools` | `PRESENT_MATCHING_CATALOG` | `37.0.1` | `37.0.1` | Nenhuma (revisão já presente na imagem base) |
| `platforms;android-36` | `PRESENT_MATCHING_CATALOG` | `2` | `2` | Nenhuma (revisão já presente na imagem base) |
| `system-images;android-36;default;x86_64` | `ABSENT` | `2` | `None` | Instalação efêmera de `system-images;android-36;default;x86_64` rev 2 |

### Descoberta de Eficiência Crítica:
Três dos cinco pacotes essenciais (`build-tools;36.0.0`, `platform-tools` e `platforms;android-36`) já vêm pré-instalados na imagem `ubuntu-24.04` do GitHub com revisões idênticas às do canal estável upstream. Portanto, a Wave 1 só precisa provisionar efemeramente os 2 pacotes ausentes (`emulator` e `system-images;android-36;default;x86_64`), economizando largura de banda, minutos de runner e eliminando risco de mutação desnecessária.

---

## 3. Manifesto de Reprodutibilidade e Verificação Local

Qualquer auditor ou membro da equipe pode verificar a integridade matemática desta proposta executando no terminal:

```bash
# 1. Executar os testes automatizados da engine de catálogo
python experiments/reliability-harness/scripts/test_catalog_discovery.py

# 2. Verificar a política estática do script de descoberta
python experiments/reliability-harness/scripts/catalog_discovery.py verify-script experiments/reliability-harness/scripts/audit-catalog-discovery.sh

# 3. Canonicalizar e validar o payload JSON da proposta
python experiments/reliability-harness/scripts/catalog_discovery.py canonicalize evidence/g1/raw-mission05r/canonical_catalog_proposal.json
```

O arquivo `canonical_catalog_proposal.json` é serializado estritamente sob `ALVORADA_CANONICAL_JSON_V1` (chaves ordenadas lexicograficamente, separadores compactos sem espaços, codificação UTF-8 sem BOM).

---

## 4. Invariantes Negativas Preservadas

Durante toda a realização desta descoberta, as seguintes invariantes foram estritamente mantidas e verificadas:
- `API36=NOT_PROVISIONED`
- `SYSTEM_IMAGE=NOT_PROVISIONED`
- `AVD=NOT_CREATED`
- `P1_P10=UNKNOWN`
- `READY_FOR_E1_WAVE1=NO`
- `LOCK_APPROVED=NO`
- `origin/main` estritamente intocada em `43018b1f9b14cb9e580d2157e6cb623ee18de0d1`.

---

## 5. Checklist de Aprovação Humana (Fundador)

Para autorizar a promoção deste lock para o estado `LOCK_APPROVED=YES` e desbloquear a Wave 1 de provisionamento:
1. [ ] Auditar este documento e o arquivo `canonical_catalog_proposal.json`.
2. [ ] Confirmar que as revisões `emulator: 37.1.11` e `system-images;android-36;default;x86_64: 2` atendem aos requisitos de confiabilidade do Alvorada.
3. [ ] Autorizar formalmente a criação do workflow de provisionamento da Wave 1 (`05R-F`).
