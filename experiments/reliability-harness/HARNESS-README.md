# Reliability Harness 0.1.0

> **DISPOSABLE EXPERIMENTAL HARNESS.**  
> **NOT PRODUCT CODE.**  
> **NO API STABILITY GUARANTEED.**

Instrumento de G1.2 para testar o modelo lógico do Wake Core e preparar execuções Android controladas. Não é o aplicativo ALVORADA, não escolhe stack de produto e não contém experiência, contexto pessoal, rede, IA ou UI.

## Escopo executável desta versão

- E0/JVM sem dependências: identidade de ocorrência, `generation`, tombstones, transições, readiness, hora civil/DST, late recovery, recorrência, snooze, concorrência, crash/replay, restore e persistência local do estado mínimo.
- Marcador WAV sintético local e determinístico; seu SHA-256 é emitido pelo teste.
- Eventos técnicos estruturados com whitelist de campos e separação de wall clock/monotonic clock.
- Preflight E1 que recusa execução quando SDK, `adb`, emulator, system image, AVD ou adaptador Android verificável estiverem ausentes.

Não há adapter Android compilado nesta versão porque o ambiente auditado não contém SDK/emulator/imagens utilizáveis. Logo, scheduling Android, Direct Boot e áudio emulado **não foram executados**. Os scripts não convertem essa ausência em PASS.

## G1.3 — recuperação do laboratório

A auditoria de 2026-09-12 manteve `LOCAL_ACCELERATED_AVAILABLE=NO`: este container não expõe `/dev/kvm`. O repo privado `phpedrogarcia-afk/ALVORADA` agora contém o snapshot canônico e o workflow manual, mas Actions habilitado, hard stop de overage e o runner real ainda não foram observados. Portanto `REPOSITORY_BINDING=PASS` não equivale a `LAB_DISCOVERY_PASS`.

O candidato preservado em `lab/github-actions/LAB-MANIFEST.json` é um runner efêmero `ubuntu-24.04`. O workflow `.github/workflows/e1-lab-discovery.yml` executa apenas descoberta e arquiva seu log; ele **não** executa E1 nem satisfaz os dez prechecks. As revisões exatas de emulator e system images permanecem deliberadamente abertas até a primeira descoberta real. Nenhum repositório externo foi criado ou reutilizado, nenhum custo foi incorrido e nenhum adapter Android não compilado foi adicionado.

Próximo passo obrigatório: o fundador deve comprovar hard stop de overage, saldo incluído e Actions habilitado. Depois, executar somente discovery; se passar, congelar as revisões e completar o precheck mínimo API 36. Adapter e Wave 1 pertencem à missão seguinte.

## Poucos comandos

```bash
./scripts/build.sh
./scripts/test-e0.sh
./scripts/run-e1.sh --api 31 --scenario NORMAL_FOREGROUND --strategy ALARM_CLOCK --repeat 3
./scripts/audit-lab-routes.sh
```

`test-e0.sh` executa a suíte determinística e 10 seeds com 10.000 sequências cada. `run-e1.sh` executa primeiro um preflight estrito. Sem ambiente e adapter completos, termina com código diferente de zero e `ENVIRONMENT_BLOCKED`.

## Cadeia epistêmica

O código preserva:

`CONFIGURED != ARMED_VERIFIED != TRIGGERED != SOFTWARE_AUDIO_STARTED != PHYSICAL_AUDIO_OBSERVED != HUMAN_AWAKE`

E0 só testa o modelo. E1, quando existir, poderá observar no máximo o handoff interno no emulator. Apenas E2 com oráculo externo poderá sustentar `PHYSICAL_AUDIO_OBSERVED`.

## Relógios e thresholds congelados

- Hora civil, fuso e DST usam wall clock e regras de zona.
- Latências dentro do mesmo boot usam clock monotônico.
- Entrega: `-500 ms` a `<0` = `EARLY_TOLERANCE`; `0..2.000` = `TARGET`; `>2.000..5.000` = `ACCEPTABLE_LATE`; fora = `FAILURE`.
- Late recovery: até 10 min inclusive; depois `MISSED` somente com evidência, senão `OUTCOME_UNKNOWN`.
- Soneca: 5 min; sessão: 30 min. Todos são thresholds experimentais G1.1, não fatos de desempenho.

## Persistência e privacidade

O codec de estado é deliberadamente simples e versionado, apropriado apenas ao laboratório. O conjunto device-protected candidato contém somente IDs, regra/instante civil, generation, estado/tombstone, checkpoint e marcador fallback. Nome, lembrete, agenda, localização, texto e voz são explicitamente credential-protected e inexistem no harness.

## E1 e estratégias

As estratégias candidatas permanecem separadas: `ALARM_CLOCK` (`setAlarmClock`) e `EXACT_ALLOW_IDLE` (`setExactAndAllowWhileIdle`). Perfis de permissão e elegibilidade de distribuição não são inferidos. Force-stop é um cenário diferente de morte ordinária. Direct Boot exige reboot real + nenhum primeiro unlock; broadcast artificial não é substituto.
