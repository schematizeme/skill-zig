# Testes, Pentest e Build

> **Dividida:** §22.4–§23 (padrão de script, seeds, CI, pentest §22.7–22.8, Q.A. §22.9, build/Makefile) estão em `references/testes-execucao.md`. Numeração contínua entre os dois.

> Parte da skill **schematize-zig**. As referências cruzadas (§N) apontam para seções do corpo completo — todas presentes no conjunto de references desta skill. Fundamentos de memória/ownership em `references/memoria-concorrencia.md`; toolchain e versões em `references/stack-versoes.md`.

## Índice
- 22. Testes
- 23. Build padrão (`build.zig`)

---

## 22. Testes

**Obrigatório**
- Testes em **dois eixos**: por código (unit/integration, dentro de cada serviço, via `zig test` / `zig build test`) e por sistema vivo (smoke/security/pentest/authz/hardening/chaos/simulated, no repo `<project>_ops`).
- Caminhos críticos (auth, pagamento, autorização, billing, eventos de domínio, multi-tenancy) têm testes explícitos cobrindo sucesso, **caminho de erro** (`!T`) e edge cases — independentemente da cobertura agregada.

**Cobertura mínima (por código)**

| Camada | Mínimo |
|---|---|
| `domain` | 80% |
| `application` | 70% |
| `infrastructure` | 40% |
| Global | 60% |

> Editar o threshold ou pular teste pra "passar o CI" é VETADO (§37). O número é contrato. Cobertura em Zig sai via `kcov` sobre o binário de teste (ver `references/testes-execucao.md` §22.6) — o ecossistema não tem um `--cover` nativo integrado ainda; seja honesto sobre isso e configure `kcov` no CI.

### 22.0 Runner nativo do Zig — `zig test` e blocos `test`

Zig tem test runner **embutido na linguagem**. O teste mora **no próprio arquivo**
que testa (ou num arquivo irmão) como bloco `test`:

```zig
const std = @import("std");
const testing = std.testing;

test "parseToken rejeita assinatura inválida" {
    const bad = "eyJ...".*; // token com HMAC adulterado
    try testing.expectError(error.SignatureInvalid, parseToken(testing.allocator, &bad, key));
}
```

- **`zig test src/foo.zig`** roda os blocos `test` de um arquivo isolado.
- **`zig build test`** roda a suíte inteira via o step `test` do `build.zig` (§23) —
  é o alvo canônico da casa (equivale ao `cargo test`/`go test ./...`).
- Asserções de `std.testing`: **`expect`** (bool), **`expectEqual`**,
  **`expectError`** (prova o ramo de erro de um `!T`), **`expectEqualStrings`**,
  **`expectEqualSlices`**, `expectApproxEqAbs` pra float. `expectError` é o
  instrumento que torna o **caminho de erro obrigatório** verificável.

### 22.0.1 Detecção de leak é PISO, não opcional

Zig não tem GC: memória vazada é bug de correção, e o test runner **detecta leak de
graça** — mas só se você usar o allocator certo.

- **Todo teste que aloca usa `std.testing.allocator`.** Ele rastreia cada alocação e
  **falha o teste** se sobrar memória ao fim do bloco `test`. Provar ausência de leak
  é **obrigatório** — não é "nice to have". Teste que aloca com outro allocator
  (`std.heap.page_allocator`, arena descartada) pra "não se preocupar com free"
  está **cego pra leak** e é reprovado no review.
- Padrão do bloco: alocar com `testing.allocator`, `defer x.deinit(testing.allocator)`
  (ou `defer testing.allocator.free(x)`), e deixar o runner conferir. Vazou → FAIL.
- **Em produção/debug**, o piso equivalente é o `GeneralPurposeAllocator(.{})`: no
  `deinit()` ele **reporta leak** (`.leak`) e o programa trata isso como erro. Todo
  binário da casa em modo debug roda sobre GPA com `defer _ = gpa.deinit();`
  checando o retorno. Liga com `references/memoria-concorrencia.md` (ownership,
  `defer`/`errdefer`, arenas).

> Um `!T` sem um `expectError` que exercite cada erro do set, ou um teste que aloca
> sem `testing.allocator`, é cobertura mentirosa: passa verde e esconde tanto o ramo
> de erro quanto o leak.

---

### 22.1 Test Kit do `<project>_ops`

Toda a malha de testes "do sistema vivo" mora num repo dedicado (`<project>_ops`), invocada por um CLI único.

**Estrutura padrão**

```
<project>_ops/
├── bin/
│   └── <project>-test          # CLI: run modes, agrega saída
├── tests/
│   ├── lib.sh                  # helpers compartilhados (cores, assertions, http_call)
│   ├── README.md               # tabela de modos × scripts × duração
│   ├── smoke/                  # health, rotas-chave, shape de respostas
│   ├── integration/            # login real + CRUD ponta-a-ponta
│   ├── security/               # auth bypass, headers, rate-limit
│   ├── pentest/                # OWASP + extensão
│   ├── authz/                  # RBAC + multi-tenancy isolation
│   ├── hardening/              # TLS, cookies, CORS, exposed paths
│   ├── chaos/                  # fuzz, adversarial input, kill, db-disconnect
│   ├── simulated/              # matriz exaustiva: rotas × personas × injections
│   ├── seeds/                  # SQL de setup (personas de teste, superadmin)
│   ├── unit/                   # delega `zig build test` por serviço (leak gate)
│   └── workspace-code.sh       # smell-scan no monorepo (arquivos > N linhas, etc.)
├── Makefile                    # fino, chama `zig build` (ou build.zig steps)
└── README.md
```

**CLI padrão**

```bash
<project> test                  # default: smoke
<project> test smoke
<project> test integration
<project> test security
<project> test pentest
<project> test authz
<project> test hardening
<project> test chaos
<project> test simulated
<project> test unit             # zig build test com testing.allocator (leak gate)
<project> test all              # tudo exceto chaos+unit
<project> test full             # all + chaos + unit
<project> test seed-superadmin  # setup inicial (uma vez)
```

**MUST**
- Cada script é executável standalone: `bash tests/smoke/auth-endpoints.sh` deve rodar e sair `0/1`.
- Cada script declara `TEST_NAME` e usa helpers de `lib.sh` (`test_pass`, `test_fail`, `test_skip`, `test_section`, `test_summary`, `http_call`, `assert_http_in`).
- Banner ENORME em vermelho quando há falha — feedback visual impossível de ignorar em CI.
- Skip sem erro quando dependência opcional falta (ex.: openssl ausente em hardening/tls).

---

### 22.2 Saída estruturada (machine-readable)

Toda execução escreve em `/<project>/logs/test-<YYYY-MM-DD>-<HHMMSS-pid>/`:

| Arquivo | Conteúdo |
|---|---|
| `summary.txt` | PASS/FAIL por script, legível |
| `summary.json` | **fonte única pra dashboards/CI** — schema fixo abaixo |
| `run-totals.txt` | 7 linhas: mode, started, finished, duration, scripts, pass, fail, exit |
| `<mode>-<name>.log` | output completo de cada script |
| `cookies.txt` | sessão dos personas (só em `integration`) |
| `coverage-summary.{txt,json}` | cobertura por serviço via `kcov` (só em `unit`) |

**Schema `summary.json`**

```json
{
  "started_at": "2026-05-11T11:35:50Z",
  "finished_at": "2026-05-11T11:35:57Z",
  "duration_seconds": 7,
  "mode": "smoke",
  "log_dir": "/<project>/logs/test-2026-05-11-083550-448694",
  "scripts": [
    {"category": "smoke", "name": "auth-endpoints", "status": "pass"},
    {"category": "smoke", "name": "services-health", "status": "fail"}
  ],
  "totals": {"pass": 23, "fail": 1, "scripts": 24, "exit_code": 1}
}
```

**MUST**
- Exit code 0 se tudo passou; 1 se qualquer caso falhou.
- `summary.json` é contrato — não quebre os campos `mode`, `totals`, `scripts[]`.
- Logs zipados e enviados pra storage de longo prazo após cada CI run (90 dias mínimo).

---

### 22.3 Categorias de teste (por modo)

#### `smoke` — saúde do sistema, < 2min

Cobre: health/metrics de cada serviço, rotas-chave do dispatcher, frontends, observability stack, endpoints por domínio (auth, catalog, billing, etc.), DB connectivity, microservices-status, shape de health/metrics, response-time p95, CORS preflight, OpenAPI availability, log scan pra PII vazada.

Falha = bloqueio de deploy. Roda **antes e depois** de cada `update` em todo ambiente.

**MUST — anti "verde mentiroso" (smoke que passa com bug dentro)**

Um smoke que só confere status `200` é teatro: a rota responde, o conteúdo está quebrado, e o deploy passa. Para impedir isso:

- **Assertar conteúdo, não só status.** Toda rota-chave valida o **shape do body** (campos esperados via `jq -e`), não apenas o código HTTP. `200` com body vazio, `{}`, `null`, `[]` onde deveria haver dado, ou HTML de erro com status 200 = **FALHA**.
- **Assertion negativa obrigatória.** Cada rota crítica também testa que o que **não** deveria estar lá não está: sem stack trace, sem `error`/`exception` no body de sucesso, sem `"undefined"`/`"null"`/`"NaN"` serializado, sem placeholder de template não renderizado (`{{`, `${`, `%s`), sem mensagem de `panic`/`unreachable` vazada do runtime Zig.
- **Self-test do próprio smoke (meta-teste).** O suite tem um caso que **força uma falha conhecida** (ex.: bater numa rota fake `/_smoke_canary_should_404` esperando 404, e uma asserção que deve falhar de propósito num modo `--self-check`) pra provar que o runner **consegue reportar FAIL**. **No eixo por código, o equivalente é um `test` que faz `try testing.expect(false)` sob um flag** e prova que `zig build test` retorna exit ≠ 0: **`zig test` que nunca falha está cego.** Se o self-check passa quando deveria falhar, CI quebra. Nenhum teste pode ser estruturalmente incapaz de falhar.
- **Cobertura de rota verificada.** O smoke compara as rotas que testou contra o inventário do OpenAPI/dispatcher. **Rota em produção sem caso de smoke = FALHA**, não silêncio. (Liga com §35 e com `simulated`.)
- **Sem `|| true`, sem swallow.** Proibido `curl ... || true`, `set +e` sem `set -e` de volta, ou condição que transforma erro em pass. Falha de rede/timeout numa dependência obrigatória é FAIL, não skip (skip só pra dependência **opcional** declarada).
- **Latência e dado fresco.** Healthcheck que devolve `200` cacheado/estático não conta — `/ready` valida dependência **de verdade** (ping no DB, no broker), e o smoke afere `response-time p95` contra o SLO (§30). Resposta lenta demais = FALHA.
- **Fail loud.** Banner vermelho ENORME (§22.1) e o `summary.json` com `totals.fail > 0` travando o deploy. Verde só quando **todas** as asserções de conteúdo passaram.

> Smoke que nunca falha não é smoke saudável — é smoke quebrado. Se você não viu o teste falhar de propósito, você não sabe se ele funciona. Vale igual pro `zig test`: rode o self-check e veja o exit ≠ 0.

#### `integration` — fluxos end-to-end com credenciais reais, < 3min

Cobre: login do superadmin com cookie real, CRUD course/user/subscription via API admin, upload de imagem, reset de senha completo. Usa seed `tests/seeds/test-superadmin.sql` pra garantir user existente.

**Requer pré-seed**: rodar `<project> test seed-superadmin` na primeira vez no ambiente.

#### `security` — controles de segurança "óbvios", < 1min

Cobre: auth bypass tentando rotas admin sem cookie, headers de segurança (CSP, X-Content-Type, HSTS), rate limit no login (50 paralelas → expect 429), formato de password hash (argon2id / bcrypt cost ≥ 12), scan de CVE nas deps do `build.zig.zon` (ver `references/stack-versoes.md`), JWT algorithm validation (RS256 only).

#### `pentest` — OWASP Top 10 + extensão, < 3min

Scripts cobrem (cada um isolado):
- `sql-injection.sh` — payloads SQLi clássicos em query/body. Esperado: 400/422 ou 401/403/404. **NUNCA 500** e nunca 200 com data revelando "OR 1=1".
- `xss.sh` — `<script>`, `<img onerror>`, `javascript:` em campos refletidos. Resposta não pode incluir payload sem escape.
- `idor.sh` / `user-bola.sh` — IDs de outro tenant/user nos paths.
- `ssrf.sh` — URLs apontando pra `127.0.0.1`, `169.254.169.254`, `file://`, redirect chains.
- `jwt-tampering.sh` / `jwt-claim-tampering.sh` / `jwt-algorithm.sh` — alg=none, alg=HS256-com-RS256-pubkey, exp futuro, sub trocado.
- `path-traversal.sh` — `../`, `..%2f`, null bytes.
- `mass-assignment.sh` — POST com campos extras (`is_admin`, `tenant_id`, `created_at`) que deveriam ser ignorados.
- `open-redirect.sh` — `?next=https://evil.com`.
- `host-header.sh` — Host header arbitrário pra envenenar links em emails.
- `csrf.sh` — POST sem origin/referer válido.
- `http-method-tampering.sh` — TRACE, OPTIONS, métodos não suportados.
- `request-smuggling.sh` — `Transfer-Encoding: chunked` + `Content-Length` conflitantes.
- `cache-poisoning.sh` — headers exóticos que envenenam CDN.
- `cookie-bomb.sh` — flood de cookies grandes → expect 4xx limpo, não 500.
- `session-fixation.sh` — session ID atribuído pré-login persiste pós-login.
- `timing-attack.sh` — diff de latência entre user existente vs inexistente no login (alvo: < 30% variance).
- `redos.sh` — strings catastróficas pra regex (`aaaaaa...aaa!`).
- `billion-laughs.sh` — JSON/XML bomb (nested arrays profundos).
- `clickjacking.sh` — `X-Frame-Options` / CSP `frame-ancestors`.
- `refresh-token-reuse.sh` — usar mesmo refresh duas vezes → 2ª deve revogar família.
- `parameter-pollution.sh` — `?id=1&id=2`.
- `excessive-data-exposure.sh` — endpoint público vaza email/cpf/telefone.
- `header-spoof.sh` — `X-Forwarded-For`, `X-Real-IP`, `X-Original-User` injetados.
- `oversized-payload.sh` — body de 10MB+ → 413, não 500 nem OOM.
- `integer-overflow.sh` — valores que estouram `u32`/`i64` em campos numéricos (length, offset, count): esperado 422, **nunca** wrap silencioso nem `panic` de overflow (ver §22.0 caminho de erro).

**Validação de tipo e sanitização de entrada** — campo só aceita o que deveria, e o que não deveria vira **422/400 limpo, nunca 500 e nunca persistido cru**:
- `type-confusion.sh` — manda o tipo errado em cada campo: string onde o schema espera `int`/`uuid`/`bool`/`enum`/`date`; número onde espera string; array onde espera objeto; objeto aninhado onde espera escalar. Esperado: `422`. **Coerção silenciosa, ou `panic`/`unreachable` estourando 500, é FALHA.**
- `boundary-values.sh` — limites numéricos: negativo onde só positivo, `0`, `maxInt(T)+1`, `-1`, float onde espera int, `NaN`, `Infinity`, notação científica (`1e999`). Em Zig, atenção a `@intCast`/`@truncate` sem checagem — overflow tem que virar erro, não wrap.
- `charset-fuzz.sh` — caracteres estrangeiros e estranhos em **todo** campo de texto: unicode astral (emoji 𝕏, `𝓪`), CJK (中文), árabe/hebraico (RTL), diacríticos combinantes, zero-width (`​`), homoglyphs, ` ` null byte, control chars (`\x01`-`\x1f`), BOM. Esperado: aceitar normalizado (NFC) **ou** rejeitar com 422 — **nunca** quebrar encoding, corromper o slice de bytes, ou refletir sem escape.
- `format-validation.sh` — campos com formato declarado (email, cpf, telefone, url, uuid, cep) recebem lixo que casa o "shape" mas é inválido (`a@b`, cpf com dígito verificador errado, `uuid` de 35 chars). Validação semântica, não só regex frouxa.
- `length-overflow.sh` — string acima do `maxLength` do schema, campo obrigatório vazio/ausente, whitespace-only. Esperado: 422, e o limite **vem do schema**, não de um buffer fixo que estoura.
- `injection-in-every-field.sh` — roda o conjunto SQLi + XSS + path-traversal + command-injection + template-injection (`${7*7}`, `{{7*7}}`) contra **cada** parâmetro de **cada** rota mutável, não só os "óbvios". Tudo que entra é tratado como hostil até prova de sanitização.

> Regra do pentest de entrada: **todo campo é um campo de ataque.** Se o schema diz `u32`, prove que `u32` é tudo que entra e que overflow vira erro, não wrap. Se diz texto, prove que sai escapado e normalizado. Coerção silenciosa, `panic` e `500` são as faces do mesmo bug.

#### `authz` — autorização e isolamento, < 1min

- `cross-tenant-idor.sh` — tenant A não vê dados de tenant B (cobre §15: tenant_id sempre no WHERE).
- `rbac-negative.sh` — viewer não consegue write, editor não consegue admin.
- `privilege-escalation.sh` — tenant_admin não consegue virar platform superadmin.
- `permission-boundary.sh` — combinações de roles + recursos → matriz de allow/deny.
- `tenant-isolation.sh` — cookie/JWT de tenant A injetado em rota de tenant B → 403.

#### `hardening` — endurecimento da superfície de ataque, < 1min

- `tls-config.sh` — TLS 1.2/1.3 ok, 1.0/SSLv3 rejeitados, cert válido, HSTS no header, nome bate.
- `headers-full.sh` — CSP, COOP, CORP, Referrer-Policy, Permissions-Policy, X-Content-Type-Options.
- `cookies.sh` / `cookie-attributes.sh` — HttpOnly + Secure + SameSite=Lax|Strict em todos os cookies de sessão.
- `cors.sh` — origens permitidas explícitas, sem `*` em rotas autenticadas.
- `exposed-paths.sh` — `.git/HEAD`, `.env`, `/debug`, `phpinfo.php` retornam 404 (não 200).
- `default-creds.sh` — login com `admin/admin`, `root/root`, `test/test` falha sempre.

#### `chaos` — comportamento sob stress / falha, < 5min

- `input-fuzz.sh` — strings longas (10MB), null bytes, unicode astral, JSON malformado.
- `adversarial-input.sh` — geração de input hostil (property-style, ver `unit` §22.3): idempotência (`POST` com `Idempotency-Key` igual 2x → mesmo resultado), p95 < SLO, enums fora do range, integer overflow. **Semente fixa registrada** pra reprodução.
- `service-kill.sh` — `systemctl stop <service>`, mede recuperação (gated por `<PROJECT>_CHAOS_ALLOW=1` — perigoso).
- `db-disconnect.sh` — derruba conexão DB momentaneamente, valida que pool recupera.
- `concurrent-load.sh` — 50 GETs concorrentes em rotas públicas, mede taxa de sucesso e p50/p95/p99, hang > 10s = falha. Sob concorrência, checar ausência de data race (ver `references/memoria-concorrencia.md`).

#### `simulated` — matriz exaustiva, ~5min

Engine (`tests/simulated/run.py`) que cruza **rotas × personas × injections**:

- **Personas (mínimo 3)** declaradas em `personas.json`:
  - `superadmin` (platform role)
  - `tenant_admin` (escopo de 1 tenant de teste)
  - `normal_user` (sem roles)
  Cada persona declara `expected_access` por categoria de rota (`public`, `auth`, `authenticated`, `admin`, `internal`, `import`).

- **Injections (mínimo 10)** em `injections.json`:
  - SQLi (`' OR 1=1 --`, `'; DROP TABLE users CASCADE; --`)
  - XSS (`<script>alert(1)</script>`)
  - Path traversal (`../../etc/passwd`, `..%2f..%2fetc%2fpasswd`)
  - Null byte, unicode RTL override, long string, integer overflow
  - Mass-assignment keys (`is_admin`, `tenant_id`, `created_at`, `password_hash`)

- **Rota catalog** — JSON gerado a partir do OpenAPI ou inventário de rotas do dispatcher.

**MUST — cobertura total de rotas (garantia de acessibilidade)**
- O engine **enumera 100% das rotas** do catalog e prova, por persona, que cada uma responde como esperado (acessível pra quem deve, `403`/`401` pra quem não deve). **Rota no catalog sem resultado no `raw.jsonl` = FALHA** — não existe rota "não testada".
- **Reconciliação obrigatória:** rota servida em runtime mas ausente do catalog (rota fantasma) **e** rota no catalog que não responde (rota morta / `404` inesperado) **ambas** quebram o run. O número de rotas testadas tem que bater com o inventário.
- Toda rota é exercida com persona autorizada **e** não autorizada — acessibilidade e isolamento no mesmo passe.
- Saída lista explicitamente, no `report.md`, a **matriz rota × persona × esperado × obtido**, com as linhas `REVIEW` destacadas pra olho humano.

**Outputs**:
- `raw.jsonl` — uma linha por request, toda evidência.
- `report.md` — relatório humano com seções **AUTO** (passou claro) e **REVIEW** (status inesperado, precisa olho humano).
- `summary.json` — totais por categoria.

**Setup**: `bash tests/simulated/setup.sh` cria as 3 personas no DB com hash argon2id.

Vars de ambiente úteis (`<PROJECT>_TEST_*`):
- `<P>_TEST_API_BASE` (default `http://127.0.0.1:13000`)
- `<P>_TEST_LOG_DIR` (default `/<project>/logs`)
- `<P>_SIM_TENANT_ID`
- `<P>_SIM_MAX_ROUTES` (debug: limita)
- `<P>_SIM_SKIP_MUTATIONS=1` (só GET)

#### `unit` — testes por código, 5-15min — **agressivos, não decorativos**

CLI delega para o test runner **nativo do Zig**:
- **Zig (principal):** `zig build test` (roda todos os blocos `test` via step do `build.zig`) **com `std.testing.allocator` = leak gate** (§22.0.1). Cobertura via `kcov` sobre o binário de teste → `coverage-summary.json`.
- Auxiliar em C (FFI), quando houver: o teste do lado Zig exercita a fronteira; memória cruzando FFI segue a disciplina de `references/memoria-concorrencia.md`.

**MUST — teste unitário que realmente caça bug (não só cobre linha)**
- **Leak gate sempre ligado** (§22.0.1): todo teste que aloca usa `testing.allocator`. Vazou = FAIL, não "re-roda". Prova de ausência de leak é obrigatória.
- **Caminho de erro é obrigatório, não opcional.** Para **cada** função com retorno `!T`, um `try testing.expectError(error.X, f(...))` exercita **cada** erro do error set: input inválido, dependência que falha, `error.OutOfMemory` (teste sob `testing.failing_allocator` pra forçar OOM no meio), overflow, slice vazio. Cobertura de 80% só de happy-path é cobertura mentirosa.
- **Tabela de casos hostis por validador/parser:** tipo errado, fora do range, string gigante, vazia, unicode/RTL/null byte, número como string e vice-versa, integer overflow — espelhando o `type-confusion`/`charset-fuzz` do pentest, só que na fronteira da função. Bug de sanitização tem que morrer no unit, antes do pentest achar.
- **Property-based / geração de casos (SHOULD → MUST em domínio crítico):** o ecossistema Zig **ainda não tem** uma lib de property-testing consolidada como `proptest` (Rust) ou `fast-check` (TS) — **seja honesto sobre isso**. O piso da casa: gerar casos com **`std.Random` de semente fixa registrada** (reprodutível), asserir invariantes de round-trip (encode→decode), idempotência e agregado. Semente aleatória sem registro é VETADO — bug não reproduzível não conta.
- **Fuzzing:** o fuzzer nativo do Zig (`zig test --fuzz` / `std.testing.fuzz`) **está em evolução** e nem toda versão da toolchain o expõe estável (ver `references/stack-versoes.md`). Regra honesta: **use o fuzzer nativo quando a versão fixada do projeto o suportar**; senão, gere **adversarial input à mão** (semente fixa) no `chaos/adversarial-input.sh` e nos blocos `test`. Não finja fuzzing que a toolchain não entrega.
- **Boundary obrigatório:** `0`, `-1`, `1`, `maxInt(T)`, `maxInt(T)+1`, `minInt(T)`, vazio, um, muitos. O bug mora na borda — e em Zig, na fronteira de `@intCast`/`@truncate`.
- **Proibido teste que não pode falhar:** `test` sem `try`/asserção, `expect(true)`, mock que devolve o próprio input esperado. Revisão de PR rejeita teste tautológico. Confirme com o self-check (§22.3 smoke) que a suíte **sabe** falhar.

> Cobertura mede o que o teste **executa**, não o que ele **verifica**. Um `!T` sem `expectError` de cada erro, e uma alocação sem `testing.allocator`, são as duas cegueiras mais comuns em Zig — line coverage é piso, não meta.

---
