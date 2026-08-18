# Testes — Execução, Pentest e Q.A.

> Parte da skill **schematize-zig**. Continuação de `testes.md` (numeração **preservada**, §22.4+): padrão de script de teste, seeds/personas, integração com CI, pentest (§22.7–22.8) e o build padrão (§23). A **disciplina de execução de Q.A.** (plan-first) foi extraída para a skill dedicada **schematize-qa** (`/qa-plan` → `/qa-run`). Toolchain e versões em `references/stack-versoes.md`; ownership/leak em `references/memoria-concorrencia.md`.

---

### 22.4 Padrão de script (`tests/<mode>/<name>.sh`)

O kit de scripts bash (`scripts/lib.sh` + helpers) é **o mesmo da casa** — agnóstico
de linguagem. Skeleton obrigatório:

```bash
#!/usr/bin/env bash
# <Categoria> · <Nome curto>
# Descrição clara do que cobre e o esperado.
# Esperado: status X em caso Y. Falha = significado Z.

set -uo pipefail
_DIR="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib.sh
source "$_DIR/lib.sh"

test_section "<Categoria> · <Nome>"

API="$(api_base)"

# Caso 1
assert_http_in "<descrição do caso>" "200|401" GET "$API/v1/<rota>"

# Caso 2 — body shape
http_call GET "$API/v1/<rota>"
if [[ "$HTTP_CODE" == "200" ]]; then
  if echo "$HTTP_BODY" | jq -e '.data | length > 0' >/dev/null 2>&1; then
    test_pass "<rota> retorna dados"
  else
    test_fail "<rota> sem 'data'" "$HTTP_BODY"
  fi
fi

test_summary "<categoria>/<nome>"
exit $TEST_EXIT_CODE
```

**MUST**
- Banner do `test_section` na primeira linha do output.
- Cada caso assertado vira uma linha `✓` ou `✗` ou `○ skip`.
- `test_summary` no fim agrega contadores pra o runner.
- Falhas incluem `HTTP_BODY` truncado nos primeiros 2000 chars (sem PII).

> O eixo por código (`zig build test`) é invocado pelo script `tests/unit/*.sh`, que
> captura o exit code do `zig build test` e converte em `test_pass`/`test_fail`. O
> **leak gate** (`std.testing.allocator`, `testes.md` §22.0.1) já falha o `zig build
> test` com exit ≠ 0 — o script só propaga.

---

### 22.5 Seeds e personas de teste

**MUST**
- Personas declaradas em `tests/seeds/test-*.sql` ou `tests/<mode>/*.json` — versionadas, reproduzíveis.
- Senhas test-only **explicitamente flagadas** (ex.: prefixo `SimTest!`) e **rejeitadas em produção** por validador de senha fraca.
- Setup idempotente: `INSERT ... ON CONFLICT DO UPDATE` — re-rodar não duplica.
- Cleanup automático no fim de cada run? **Não** — deixa lixo pra inspeção. Limpe via comando explícito (`<project> test clean-seeds`).
- **Semente de geração de casos (`std.Random`) fixa e registrada** — todo modo que gera input adversarial (`chaos/adversarial-input.sh`, property-style no `unit`) grava a semente no log pra reprodução. Semente aleatória sem registro é VETADO (`testes.md` §22.3 unit).

**Personas mínimas pra cobrir RBAC + multi-tenancy**:

1. `superadmin` — platform role, vê tudo.
2. `tenant_admin_A` — escopo do tenant A.
3. `tenant_admin_B` — escopo do tenant B (pra testar isolamento).
4. `normal_user` — sem role, só dados próprios.
5. (Opcional) `viewer`, `editor`, `support` — combinações de roles dentro de A.

---

### 22.6 Integração com CI

O CI da casa pra projeto Zig roda, **em ordem e como gate de merge**:

1. **`zig fmt --check`** — formatação canônica (`padroes-codigo.md` §3.2). Fora do padrão = **BLOQUEIA**.
2. **`zig build`** — compila tudo em ReleaseSafe (e Debug); erro de compilação = bloqueio.
3. **`zig build test`** — suíte de blocos `test` **com `std.testing.allocator` = leak gate** (`testes.md` §22.0.1). Leak, falha de asserção ou ramo de erro não coberto = bloqueio.
4. **`zig build test` sob `kcov`** — gera `coverage-summary.json`; abaixo do threshold (`testes.md` §22) = bloqueio.
5. **Cross-compile de smoke (opcional):** `zig build -Dtarget=<triple>` pra ≥1 alvo além do host (ex.: `x86_64-linux-musl`, `aarch64-linux`) — prova que o código não fixou premissas de plataforma. Falha = flag/bloqueio conforme criticidade.
6. **Scan de segredos** — `gitleaks`/`trufflehog` sobre o diff (segredo nunca no repo, ver `references/seguranca.md`); qualquer hit = bloqueio.
7. **Scan de deps** — CVE nas dependências do `build.zig.zon` (ver `references/stack-versoes.md` e `references/cadeia-suprimentos.md`).

**MUST**
- PR check (rápido, ~3min): `zig fmt --check` + `zig build` + `zig build test` + `<project> test smoke security authz hardening`.
- Pré-deploy: `<project> test all` (full minus chaos+unit — ~6min).
- Nightly: `<project> test full` (inclui chaos + unit + cross-compile + pentest-light §22.7).
- Bloqueio de merge: fail no `summary.json` (`.totals.fail > 0`) trava merge; `zig fmt --check` e leak gate travam **sozinhos**.

**Substituições explícitas** (não existe `go test`/`go vet`/`cargo` neste projeto):
`go test ./...` → **`zig build test`**; `go vet`/`golangci-lint` → **`zig fmt --check`** + os checks do compilador (`zig build` já é análise estática forte: unused, tipos, `comptime`); `go build` → **`zig build`**.

**Dashboards**
- `summary.json` é parseado por job de métricas pra empurrar `tests_pass_total`, `tests_fail_total`, `tests_duration_seconds_bucket` pra Prometheus.
- Falha em smoke pós-deploy dispara rollback automático.

---

### 22.7 Pentest leve via ferramentas externas (complementar)

**SHOULD** — em CI noturno, não a cada PR:
- **OWASP ZAP baseline** (`zap-baseline.py -t https://api.example.com`) — passive scan.
- **Nuclei** (`nuclei -u https://api.example.com -t cves,exposures,misconfiguration`).
- **trivy fs** ou **grype** sobre o repo + imagens Docker pra CVE em deps + base images.
- **Semgrep** ruleset `p/owasp-top-ten` pra SAST (regras C/genéricas quando não houver ruleset Zig maduro — seja honesto sobre a cobertura).

Resultados em PR comment ou dashboard, **não bloqueiam merge** por default (alto ruído) — mas qualquer **Critical** sem ADR de aceite trava.

---

### 22.8 Diretrizes de Pentest (princípios, não só scripts)

Os scripts da §22.3 são a implementação; estes são os princípios que regem **como** se faz pentest interno e **o que conta como passar**.

**Postura**
- **Assume-breach / hostil por padrão.** Todo input vindo de fora (body, query, header, cookie, path, arquivo, webhook) é tratado como hostil até prova de validação. Não existe "campo interno confiável" exposto numa rota.
- **Cobrir a rota toda, não a amostra.** Pentest roda contra o inventário completo de rotas (mesmo catalog do `simulated`). Rota nova sem caso de pentest correspondente bloqueia (liga com §35).
- **Caixa-cinza.** O time tem o OpenAPI, o schema e as roles — testa sabendo o que **deveria** acontecer, não no escuro. Pentest sem mapa vira teatro de "tentei o `' OR 1=1` e deu 403, tá seguro".

**Critério de resultado — o que é PASS / FAIL**
- **Nunca `500` por input malicioso.** Erro do servidor (5xx) diante de payload hostil é FALHA — significa que o input chegou fundo demais sem validação. Em Zig, isso inclui **`panic`/`unreachable`/overflow que derruba o processo**: input externo jamais pode disparar `unreachable`. O esperado é `400`/`422` (input inválido, via error union) ou `401`/`403`/`404` (sem acesso).
- **Nunca eco sem escape.** XSS/template injection refletido no body/header sem encode = FALHA, mesmo com status 200.
- **Nunca coerção silenciosa.** Tipo do schema aceito por coerção, string vazia virando `0`, `@intCast` que faz wrap em vez de erro = FALHA (liga com `type-confusion.sh`). O tipo do schema é contrato.
- **Nunca vazamento entre tenants/usuários.** Qualquer `200` com dado de outro escopo = FALHA crítica, para o deploy na hora (§15).
- **Nunca diferença observável que ajude o atacante.** Mensagem de erro distinta pra "user existe" vs "senha errada", timing > 30% de variância, stack trace / mensagem de `panic` do runtime Zig no response = FALHA.
- **Idempotência sob ataque.** Replay, duplicação, race no mesmo recurso não corrompe estado (e não vaza/dobra memória — ver `references/memoria-concorrencia.md`).

**Severidade e gate**
- Classificar todo achado: `Critical` / `High` / `Medium` / `Low` / `Info`.
- **`Critical` e `High` bloqueiam merge/deploy.** Sem exceção silenciosa — ou conserta, ou ADR de aceite de risco **com prazo de remediação e dono** (e mesmo assim `Critical` de auth/tenant/injeção **não aceita ADR** — é piso da §37).
- `Medium`/`Low` viram issue rastreável com prazo; acumular não é opção.

**Higiene**
- **Pentest roda só contra `dev`/`staging`** (ou alvo autorizado). Scripts destrutivos (`service-kill`, `db-disconnect`) gated por env var explícita (§22.3 chaos). Nunca contra produção sem autorização formal e janela.
- **Evidência sempre.** Todo achado tem request/response reproduzível no `raw.jsonl` — "achei uma falha" sem repro não conta. Bug achado por input gerado carrega a **semente** (`std.Random`) que o reproduz.
- **Falso-positivo é bug do teste.** Pentest que grita sem motivo treina o time a ignorar — calibra ou remove. Mas **na dúvida, FAIL** (vai pra `REVIEW`, olho humano decide), nunca silencia por padrão.

**Escopo mínimo coberto** (mapeia OWASP Top 10 + API Top 10): injeção (SQL/NoSQL/command/template), XSS, validação de tipo e sanitização (§22.3), authz/IDOR/BOLA, broken auth (JWT, sessão, refresh), SSRF, mass assignment, exposição excessiva de dados, misconfig (headers, CORS, paths expostos), rate limiting, e abuso de recurso (payload gigante, ReDoS, billion-laughs, integer overflow).

> Pentest não "tenta hackear pra ver se acha algo". Ele **prova, rota por rota, campo por campo, que o sistema rejeita o que deve rejeitar.** Achado é evidência; ausência de achado só vale se a cobertura for total.

---

### Q.A. — disciplina na skill schematize-qa

A execução de Q.A. (plan-first, aprovação obrigatória) foi extraída para a skill dedicada **schematize-qa**: o fluxo `/qa-plan` → `/qa-run` planeja tudo, gera o MD de passo a passo em `<projeto>_archive/qa/`, **pede aprovação antes de rodar** e executa faseado/assistido ou de uma vez com watchdog, travando nos gates.

No recorte **Zig**, o Q.A. usa as ferramentas de teste da linguagem — `zig test` / `zig build test`, blocos `test { ... }` com `std.testing.allocator` (leak vira FAIL) — e o pentest da schematize-pentest. O comando `/zig-qa` é o wrapper fino que aplica a schematize-qa nesse recorte. Nenhum Q.A. roda sem plano aprovado registrado.

---

## 23. Build padrão (`build.zig` + Makefile fino)

O alvo de build/test do projeto Zig é **`zig build`** com **steps nomeados** no
`build.zig`. Essa é a "Makefile da casa" **idiomática** — o `build.zig` é código Zig,
versionado, e declara cada passo. Um `Makefile` fino é aceito **apenas** como fachada
que chama `zig build` (pra manter os verbos da casa: `make test`, `make ci`), nunca
como fonte de verdade paralela.

### 23.1 Steps do `build.zig` (preferido — idiomático)

```zig
// build.zig — declara os steps nomeados da casa.
const test_step = b.step("test", "roda todos os blocos `test` (leak gate)");
test_step.dependOn(&run_unit_tests.step);

const check_step = b.step("check", "zig fmt --check + análise estática");
const run_step   = b.step("run", "sobe o serviço local");
const docs_step  = b.step("docs", "gera/valida openapi");
```

```bash
zig build              # compila (default step)
zig build run          # sobe o serviço local (== make dev/run)
zig build test         # unit + integration por código (leak gate ligado)
zig build check        # zig fmt --check + checks do compilador (== lint)
zig build docs         # gera/valida openapi
zig build -Dtarget=x86_64-linux-musl   # cross-compile de smoke (§22.6)
zig build -Doptimize=ReleaseSafe       # build de release (default da casa: ReleaseSafe)
```

> **ReleaseSafe é o default de produção da casa** (mantém checagens de overflow/bounds).
> ReleaseFast só com ADR justificando, e nunca em fronteira que processa input externo.

### 23.2 Makefile fino (fachada opcional, chama `zig build`)

```bash
make dev              # zig build run
make test             # zig build test  (leak gate)
make test-unit        # zig build test
make lint             # zig fmt --check  (+ zig build check)
make fmt              # zig fmt .
make build            # zig build -Doptimize=ReleaseSafe
make run              # zig build run
make cross            # zig build -Dtarget=... (smoke de cross-compile)
make docs             # zig build docs
make security-scan    # gitleaks + scan de deps do build.zig.zon
make smoketest        # <project> test smoke
make pentest-light    # zap/nuclei/semgrep (§22.7)
make ci               # zig fmt --check && zig build && zig build test && scans
make clean            # rm -rf zig-out .zig-cache
```

**MUST** — o `make ci` (ou o pipeline) roda **exatamente** a sequência do §22.6:
`zig fmt --check` → `zig build` → `zig build test` (leak gate) → cobertura `kcov` →
cross-compile de smoke → scan de segredos → scan de deps. Nenhum passo silenciado.

---
