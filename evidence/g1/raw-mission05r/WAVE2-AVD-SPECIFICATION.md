# MISSÃO 05R — WAVE 2 AVD SPECIFICATION & VIRTUAL DEVICE DEFINITION (05R-G)

**Document Version:** 1.0  
**Date (UTC):** 2026-09-21T00:30:00Z  
**Lane:** G1 — RELIABILITY / ANDROID LAB  
**Status:** `DESIGN_FORMALIZED`  
**Current Gate:** `G1_RELIABILITY_ANDROID_LAB`  
**Contract Identifier:** `ALVORADA_WAVE2_AVD_SPECIFICATION_V1`  
**Target AVD Identifier:** `alvorada_e1_api36_x86_64`  
**Starting Canonical Main:** `43018b1f9b14cb9e580d2157e6cb623ee18de0d1` (Strictly untouched)  
**Autonomous Working Branch:** `fio/autonomy-g1`  

---

## 1. Sumário e Propósito Arquitetural

Este documento estabelece o design formal, o orçamento de recursos de máquina e os contratos exatos de criação e execução do **Dispositivo Virtual Android Canônico (AVD) da Wave 2** (`05R-G`): `alvorada_e1_api36_x86_64`.

A Wave 2 é o estágio subsequente ao provisionamento dos pacotes da Wave 1 (`emulator 37.1.11` e `system-images;android-36;default;x86_64 rev 2`). Seu objetivo é viabilizar o boot efêmero, headless e determinístico do Android 16 (API 36) no ambiente padrão do GitHub Actions (`ubuntu-24.04`), preparando a comprovação dos pré-requisitos fundamentais **P4** (`adb communicates`), **P5** (`AVD boots`) e **P9** (`cold boot semantics understood`).

---

## 2. Orçamento de Recursos e Restrições do Host (Runner GitHub-Hosted)

A infraestrutura oficial congelada em `D-G1-LAB-02` baseia-se exclusivamente em runners padrão `ubuntu-24.04`:
- **vCPUs do Host:** 4 vCPUs (`EVID-G1-0015`).
- **Memória RAM Total:** 16.373.452 KiB (~15,6 GiB).
- **Disco Livre:** ~85 GiB.
- **Aceleração Hardware:** `/dev/kvm` com ACL R/W de usuário (`EVID-G1-0016`).

### Particionamento de Recursos para a Máquina Virtual (AVD):

| Recurso | Alocação para o AVD (Guest) | Folga para o Host (GitHub Runner) | Racional Arquitetural |
| :--- | :--- | :--- | :--- |
| **Memória RAM** | **2048 MB** (2 GiB) | **~13.6 GiB** | Previne categoricamente que o kernel do host dispare o Linux OOM Killer contra o processo QEMU ou a JVM do runner. |
| **vCPUs** | **2 vCPUs** (`hw.cpu.ncore = 2`) | **2 vCPUs** | Garante que o scheduler do host tenha 2 núcleos dedicados para o daemon do runner, `adb server`, coleta de logs e script de teste, evitando starvation e travamento de I/O. |
| **Partição de Dados** | **2048 MB** (2 GiB) | **>80 GiB** | Espaço suficiente para instalação de APKs de teste e bancos SQLite locais, com formatação rápida em disco efêmero. |
| **Heap ART/JVM** | **256 MB** (`vm.heapSize = 256`) | N/A | Suficiente para o runtime de alarmes e serviços de primeiro plano do Alvorada. |

---

## 3. Matriz Canônica de Configuração de Hardware (`config.ini`)

O dispositivo virtual `alvorada_e1_api36_x86_64` é parametrizado com exclusão rigorosa de periféricos desnecessários para execução headless de testes (Hardening Headless):

| Chave de Configuração | Valor Canônico | Justificativa Técnica |
| :--- | :--- | :--- |
| `AvdId` | `alvorada_e1_api36_x86_64` | Identificador único e inequívoco do dispositivo. |
| `avd.ini.displayname` | `Alvorada E1 API 36 x86_64` | Nome de exibição amigável para tooling. |
| `abi.type` | `x86_64` | Arquitetura nativa idêntica ao host do runner (zero emulação de CPU). |
| `tag.id` | `default` | Imagem AOSP limpa, sem Play Store / Play Services (economiza CPU/RAM). |
| `tag.display` | `Default Android System Image` | Rótulo da imagem upstream. |
| `hw.cpu.arch` | `x86_64` | Target x86_64 para KVM. |
| `hw.cpu.ncore` | `2` | 2 vCPUs dedicados ao guest. |
| `hw.ramSize` | `2048` | 2048 MB de RAM para o guest. |
| `vm.heapSize` | `256` | Heap padrão para processos Android. |
| `hw.lcd.density` | `420` | Densidade padrão (xhdpi). |
| `hw.lcd.width` | `1080` | Resolução FHD (largura). |
| `hw.lcd.height` | `2400` | Resolução FHD (altura). |
| `hw.gpu.enabled` | `yes` | Aceleração gráfica habilitada para renderização interna. |
| `hw.gpu.mode` | `swiftshader_indirect` | Renderizador OpenGL de software seguro para servidores sem GPU física. |
| `hw.keyboard` | `yes` | Suporte a entrada de teclado. |
| `hw.audioInput` | `no` | Microfone desabilitado para evitar disputa de ALSA/PulseAudio no host. |
| `hw.audioOutput` | `yes` | Saída de áudio habilitada para roteamento interno do subsistema de alarme. |
| `hw.camera.back` | `none` | Câmera traseira eliminada (economiza ciclos de CPU). |
| `hw.camera.front` | `none` | Câmera frontal eliminada. |
| `disk.dataPartition.size` | `2048M` | Partição userdata de 2 GiB. |
| `PlayStore.enabled` | `false` | Sem processos em background do Google Play. |
| `image.sysdir.1` | `system-images/android-36/default/x86_64/` | Caminho canônico relativo ao SDK Root. |

---

## 4. Contrato de Criação Determinística (`avdmanager`)

A criação do AVD é padronizada de forma estritamente não-interativa e idempotente, sem recurso a comandos arriscados de pipe (`echo |`):

```bash
avdmanager create avd \
  --name "alvorada_e1_api36_x86_64" \
  --package "system-images;android-36;default;x86_64" \
  --tag "default" \
  --abi "x86_64" \
  --device "pixel" \
  --force
```

O argumento `--force` assegura que execuções idempotentes sobrescrevam configurações corrompidas de forma determinística.

---

## 5. Contrato de Execução Headless (`emulator`)

O lançamento do emulador no runner de CI opera sob a seguinte combinação canônica de flags:

```bash
emulator -avd alvorada_e1_api36_x86_64 \
  -no-window \
  -no-boot-anim \
  -no-snapshot \
  -wipe-data \
  -gpu swiftshader_indirect \
  -accel on \
  -timezone America/Sao_Paulo \
  -camera-back none \
  -camera-front none
```

### Propriedades Essenciais:
1. `-no-window`: Execução 100% headless (sem necessidade de servidor X11 ou VNC).
2. `-no-boot-anim`: Elimina a animação de boot do Android, reduzindo a latência de inicialização em até 25 segundos.
3. `-no-snapshot` e `-wipe-data`: Garante que cada boot seja um **Cold Boot limpo e determinístico**, em conformidade estrita com o pré-requisito **P9**.
4. `-accel on`: Força o uso da aceleração KVM verificada no Run `35530880922` (`EMULATOR_ACCEL_CHECK=PASS`).

---

## 6. Contrato de Sincronização e Boot Probe (`adb`)

A prova de inicialização bem-sucedida do AVD é coordenada pelo `adb` com fail-closed estrito por tempo:

```bash
# 1. Aguardar conexão inicial do servidor adb
adb wait-for-device

# 2. Loop de verificação da conclusão do boot do sistema Android
BOOT_TIMEOUT=180
ELAPSED=0
while [ $ELAPSED -lt $BOOT_TIMEOUT ]; do
  BOOT_COMPLETED=$(adb shell getprop sys.boot_completed 2>/dev/null || echo "0")
  if [ "$BOOT_COMPLETED" = "1" ]; then
    echo "AVD_BOOT_SUCCESS=YES"
    break
  fi
  sleep 5
  ELAPSED=$((ELAPSED + 5))
done

if [ $ELAPSED -ge $BOOT_TIMEOUT ]; then
  echo "AVD_BOOT_FAILED=TIMEOUT"
  adb emu kill || true
  exit 2
fi

# 3. Finalização graciosa do emulador para liberar /dev/kvm
adb emu kill
```

---

## 7. Mapeamento de Progresso nos Pré-Checks P1–P10

A especificação da Wave 2 traça a trajetória direta para resolução dos blockers de observabilidade do laboratório:

| ID | Pre-check | Estado Atual | Estado Alvo após Wave 2 |
| :--- | :--- | :--- | :--- |
| **P1** | SDK present | `PROVED_IN_CI` (Run `35540374123`) | `PROVED_IN_CI` |
| **P2** | Android artifact compiles | `UNKNOWN` | Pronto para o probe de compilação mínima |
| **P3** | APK installs | `UNKNOWN` | Desbloqueado via `adb install` no AVD ativo |
| **P4** | adb communicates | `UNKNOWN` | **PASS** (Verificado pelo handshake `adb wait-for-device`) |
| **P5** | AVD boots | `UNKNOWN` | **PASS** (Verificado por `sys.boot_completed == 1`) |
| **P6** | test control works | `UNKNOWN` | Desbloqueado pós-boot |
| **P7** | logs/export work | `PARTIAL` | Desbloqueado via `adb logcat` e artifacts |
| **P8** | guest reboot works | `UNKNOWN` | Desbloqueado pós-boot |
| **P9** | cold boot semantics understood | `UNKNOWN` | **PASS** (Comprovado por `-no-snapshot -wipe-data`) |
| **P10** | evidence artifacts persist outside guest | `PROVED_IN_CI` (Runs `35540374123`, `35544892104`) | `PROVED_IN_CI` |

---

## 8. Verificação e Suíte de Testes da Especificação

A classe executável `Wave2AvdConfigurator` foi implementada no script canônico [`experiments/reliability-harness/scripts/catalog_discovery.py`](file:///C:/Users/phped/Documents/ALVORADA-sanitize/experiments/reliability-harness/scripts/catalog_discovery.py) e validada por testes unitários e de integração em [`experiments/reliability-harness/scripts/test_catalog_discovery.py`](file:///C:/Users/phped/Documents/ALVORADA-sanitize/experiments/reliability-harness/scripts/test_catalog_discovery.py).

Para inspecionar a especificação canônica via CLI a qualquer momento:

```bash
python experiments/reliability-harness/scripts/catalog_discovery.py wave2-avd-spec --pretty
```

---

## 9. Preservação de Invariantes Negativas

- `AVD = NOT_CREATED` (O AVD foi especificado e testado em modelo de harness, mas nenhum AVD foi instanciado no ambiente externo).
- `API36 = NOT_PROVISIONED` (Preservado aguardando aprovação do lock).
- `SYSTEM_IMAGE = NOT_PROVISIONED` (Preservado aguardando aprovação do lock).
- `P1_P10 = UNKNOWN` (Preservado até execução do boot).
- `origin/main` estritamente intocada em `43018b1f9b14cb9e580d2157e6cb623ee18de0d1`.
- Custo financeiro: **USD 0.00**.
