# E0 RESULTS — G1.2

**Resultado oficial:** PASS  
**EVID:** `EVID-G1-0002`, `EVID-G1-0003`  
**Harness:** `0.1.0` @ `06a8cbbc2b75e9b2e415f87574b5a1307b524d8b` (clean)  
**Manifest:** `evidence/g1/REPRODUCIBILITY-MANIFEST.json`

## Resultado observado

| Suíte | Testes | Sequências | Assertions | PASS | FAIL | Duração observada |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Determinística | 72 | — | 215 | 72 | 0 | 139 ms |
| Property/adversarial | 10 seeds | 100.000 | 935.554 | 10 | 0 | 3.714 ms |
| **Total** | **82** | **100.000** | **935.769** | **82** | **0** | **3.853 ms** |

Seeds: `104729, 130363, 155921, 196613, 249439, 314159, 524287, 786433, 999983, 15485863`; 10.000 sequências por seed. Esses tempos medem apenas execução JVM neste host, não latência de alarme.

Marcador WAV: 12.044 bytes; SHA-256 `b523254e10e300f6e556a2081b2623a13c10ec05cf0a8230282535f49be62477`.

## Decisões de implementação experimentais

- Java 17 standard library e runner próprio, sem Gradle/JUnit: resposta ao ambiente, não seleção de stack.
- IDs SHA-256 sobre chave civil canônica completa; colisão semântica falha fechada.
- Engine de estado pequena + codec binário v1 atômico e descartável; o codec não é schema de produto.
- Wall clock para regra civil; monotônico apenas para duração no mesmo boot. Deadline monotônico não atravessa boot.
- Output ownership é efêmero; reload preserva histórico, remove ownership e exige recovery para estados em voo.
- WAV PCM local gerado por código e fixado por checksum; `ALARM_CLOCK` e `EXACT_ALLOW_IDLE` são rótulos separados, não implementações Android provadas.

## Cobertura

- `I-01..I-14`: generation/intenção ativa, identidade, checkpoint antes de `ARMED_VERIFIED`, dedupe, tombstone, independência opcional, clocks por boot, UNKNOWN acústico, limite de sessão, resultado por ocorrência, readiness stale, reconciliação em duas fases, owner/waiting e cadeia epistêmica.
- Hora civil: fuso repetidamente alterado, time forward/backward, gap e fold DST; primeiro offset do fold e uma ocorrência.
- Fronteiras congeladas: T−501 ms, T−500 ms, T, +2.000, +2.001, +5.000, +5.001, +10 min e +10 min +1 ms; áudio interno nulo/1.000/1.001/3.000/3.001 ms; soneca 5 min e sessão 30 min.
- Crash/replay: após intenção, após scheduling, após checkpoint, durante ringing, callback/comando/reboot/reconciliation duplicados, evento fora de ordem e colisão de IDs.
- Persistência: round-trip determinístico de estado local, dedupe/tombstone após reload e restore de backup sem `ARMED_VERIFIED`.
- Hard invariants modeláveis: HI-01/02/03 e HI-06 diretamente; partes operacionais de HI-04/05. HI-07/08 não têm conteúdo no harness; governança HI-09 é protegida por teste de constantes, mas não é demonstrável apenas em runtime.

E0 não demonstra Android, entrega real, audibilidade, eficácia humana, envelope sensorial nem dispositivo físico.

## Falhas encontradas e reparadas antes da rodada oficial

1. O primeiro run teve 63/64 PASS: o oráculo chamou um callback de áudio já observado de `REJECTED`; a semântica correta era `DUPLICATE_SUPPRESSED`. O teste foi corrigido e um caso separado provou que o primeiro callback após terminal é rejeitado.
2. A revisão adversarial encontrou output ownership efêmero sendo restaurado após crash. O reload agora remove owner e converte estados em voo para `RECOVERY_REQUIRED`.
3. Algumas transições globais de disable/edit não cobriam estados em voo. Elas agora tombstonam, liberam output e preservam fechamento por generation.
4. Uma colisão de `event_id` com tipo diferente podia parecer replay idempotente. Agora falha fechada.
5. Callback em estado apenas `CONFIGURED` dependia de exceção incidental. Agora retorna `INVALID_STATE` sem inferir trigger.

Nenhum threshold foi relaxado, nenhum teste foi removido e nenhum contraexemplo crítico conhecido permaneceu aberto na rodada oficial.

## SCAR real

**SCAR-G1-03:** estado durável de alarme e propriedade efêmera do output não podem compartilhar restauração ingênua. Depois de morte do processo, ownership físico é descartado e estados em voo exigem reconciliação; histórico de software não vira prova de áudio atual.
