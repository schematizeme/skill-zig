# Changelog — schematize-zig

Todas as mudanças relevantes deste pacote, no formato [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
com versionamento [SemVer](https://semver.org/lang/pt-BR/).

## [0.4.0] — 2026-09-30
Regra nova do dono: **orquestração por papéis e escada de modelo**. Por quê (pedido do dono, custo): o orquestrador em modelo padrão não desenvolve; ações onerosas viram micro-tasks baratas; `sonnet` é o default nos subagents e `opus` só após falha.

### Adicionado
- **`assets/CLAUDE.md`**: novo piso 18 — *Orquestrador não desenvolve; subagent barato executa*: o principal só planeja, decompõe, despacha, supervisiona e revisa; micro-tasks; `sonnet` por padrão, escada de correção (mesmo subagent, até 2 rodadas → re-decompor → `opus` com motivo registrado); no overdev cada item é executado por subagent `sonnet` e revisado pelo principal. Remete à `schematize-engineering` -> `references/orquestracao.md` §9.
- **`SKILL.md`**: bullet correspondente na seção de pisos.

### Mantido (piso inalterado)
- Todos os pisos anteriores (segurança, IAM, testes de verdade, efeito externo fora de prd, ops/DoD/archive) permanecem exatamente como estavam; a regra só define **quem executa**, não afrouxa nenhum gate.

## [0.3.0] — 2026-08-21
Saneamento do catálogo conforme a vistoria de 2026-08-21.

### Corrigido — as APIs do 0.16.0, verificadas RODANDO
- **CSPRNG**: `std.crypto.random` **não existe mais**; o certo é **`io.random`** (dia a dia) e **`io.randomSecure`** (material de vida longa: sempre syscall, sem estado de processo — o que importa depois de `fork` e em VM clonada). Com o aviso que é o ponto do achado: *o risco não é o erro de compilação, é o conserto que ele provoca* — `std.Random.DefaultPrng` **compila** e é o Xoshiro previsível que a própria §Z.6 veta.
- **Allocator**: `GeneralPurposeAllocator` → **`DebugAllocator`**, nos 6 lugares.
- **Tempo constante**: `std.crypto.utils.timingSafeEql` → **`std.crypto.timing_safe.eql`**.
- **Reader**: `std.io` não existe mais → **`std.Io.Reader`**.
- **`build.zig.zon`**: `.name` agora é **enum literal** e **`fingerprint` é obrigatório** (o compilador sugere o valor). Com a armadilha registrada: copiar o `fingerprint` de outro projeto ao usar um `.zon` como molde produz **dois pacotes com a mesma digital**.

Todas verificadas com o Zig **0.16.0** baixado e executado: os erros antigos reproduzidos, e um teste com as APIs novas passando (`All 1 tests passed`), mais `zig build` aceitando o `.zon` do exemplo.

### Mudado
- `anti-padroes.md`, `arquitetura.md`, `entrega.md`, `dados-eventos.md`, `seguranca.md`, `observabilidade.md` e `ops.md` viraram **ponteiro** (poda mecânica); os arquivos idiomáticos (memória manual, comptime) ficaram.

## [0.2.0] — 2026-08-20
Piso novo: **efeito externo NUNCA sai de não-produção** — recorte Zig (vtable + error union) da normativa `schematize-engineering` → `references/efeitos-externos.md`.
### Adicionado
- **SKILL.md**: piso inegociável "efeito externo NUNCA sai de não-produção" — sink default fora de `prd`, guard como provider que envelopa o de dentro devolvendo `error{ExternalRecipientBlocked}` (sem `catch {}`/`catch unreachable`), seleção por ambiente na composição, cap por execução, fail-closed, domínio de teste em rota nula.
- **references/iam.md §3.1** (novo): código Zig completo e compilável — `EmailProvider` como vtable, `SinkProvider` (default fora de prd, lido pelo teste), `GuardedProvider` com `assertDeliverable` deny-by-default + `isTestRecipient` (match por domínio, não por substring), `Env.parse`/`Env.fromProcess` **fail-closed** (só `"prd"` liga o real), `capFromEnv` (`MAIL_MAX_PER_RUN`, default 50), `wire()` de composição por ambiente, e os testes `test "guard recusa destinatário externo"` / `test "cap por execução aborta antes de virar 5.000"` / `test "env ausente ou desconhecido NÃO vira produção"` com `std.testing.expectError`. Tabela regra→código e extensão a `SmsProvider`/`PushProvider`.
- **references/iam.md**: bullet do Email OTP agora explicita "ligado ≠ entregando pra fora" (sink + guard); item novo no checklist de DoD do IAM com a prova exigida (`expectError` vermelho + `dig MX` null MX).
- **references/testes.md §22**: item obrigatório — teste nunca dispara efeito externo real (sink no `zig test`, endereço `<papel>+<run-id>-<n>@test.<domain>`, teste vermelho do guard e do cap, grep de CI contra `@gmail.com`/terceiros em fixture/seed/`simulated`).
- **assets/CLAUDE.md**: piso 17 com o recorte Zig (vtable/sink/guard/error union/cap/fail-closed/rota nula) e o motivo (queima de IP e domínio derruba o OTP de produção).

## [0.1.2] — 2026-08-18
Correção da contradição do muro pré-login de IAM (alinha ao `iam.md` da schematize-engineering).
### Mudado
- **/zig-iam**: removido o "2º fator forte obrigatório antes do acesso pleno" e o "força 2º fator no 1º login" — o muro pré-login / deadlock de bootstrap VETADO pela norma. Agora senha+Email OTP = 2FA baseline; fator forte é nudge + step-up just-in-time.

## [0.1.1] — 2026-08-18
Q.A. repointado para a skill dedicada **schematize-qa**.
### Mudado
- **`/zig-qa` virou wrapper fino** da **schematize-qa** (`/qa-plan` → `/qa-run`) no recorte Zig (`zig test`). Referências ao antigo **§22.9** removidas de `SKILL.md`, `references/testes-execucao.md`, `assets/CLAUDE.md` e `/zig-help`.

## [0.1.0] — 2026-08-15
Primeira release da **schematize-zig** — especialização Zig dos padrões normativos de engenharia da casa (status: **beta**).

### Adicionado
- **Corpo normativo completo** fatiado em `references/`, especializado para Zig sobre a base agnóstica da casa:
  - `stack-versoes.md` — **Zig é pre-1.0**: pin da versão exata do compilador (contrato de build), toolchain (`zig build`/`zig fmt`/`build.zig.zon`), Zig no rol sancionado + guia de fit (quando usar Zig / quando NÃO é Zig).
  - `memoria-concorrencia.md` — **memória manual sem GC**: allocators (GeneralPurposeAllocator com leak detection, ArenaAllocator, FixedBufferAllocator), par `alloc`/`free` casado (`defer`/`errdefer`), ownership documentado, **leak gate é piso** (`std.testing.allocator`), build mode (`ReleaseSafe` como padrão de produção), threads/locks/atômicos, async em evolução (honesto), cancelamento/graceful shutdown.
  - `padroes-codigo.md` — clean code com doc-comment `///` (+ campo de disciplina de memória: quem aloca/libera), `zig fmt --check` no CI, arquivo ≤750 linhas (~500 úteis + ~250 comentário; flag >300 úteis), uma unidade lógica por arquivo, MAPA/índice exaustivo.
  - `arquitetura.md` — **rol sancionado** (Go/Rust/Elixir/C#/Zig/Ruby por fit + ADR; Node/PHP legado) com Zig posicionado (baixo nível, interop C, artefato pequeno); camadas/DDD, anti-monólito, estrutura de pastas Zig (`build.zig`/`build.zig.zon`).
  - `seguranca.md` — segurança de memória por build mode (Debug/ReleaseSafe vs ReleaseFast/UB), overflow explícito, parse defensivo de input hostil, **interop C validado no boundary**, segredo nunca no binário; auth/cripto sensível posicionado em Rust (fit).
  - `iam.md` — IAM da casa no recorte Zig com **posicionamento honesto** (auth costuma pedir Rust/Go por fit — registra ADR): auth como app separada (`<projeto>_auth_zig`), ID≠email, ≥2 fatores baseline (senha+Email OTP sempre-on), passkey/WebAuthn, ReBAC deny-default, sessão 7d/90d, logout irreversível, step-up just-in-time, risk engine, migração de legado prioridade 0.
  - `cadeia-suprimentos.md` — `build.zig.zon` com hash (lockfile de fato; VETADO branch móvel), pin da toolchain como parte da cadeia, cross-compile reprodutível, SBOM/scan/imagem mínima assinada.
  - `testes.md` + `testes-execucao.md` — `zig test`/blocos `test`, `std.testing`, **leak gate**, `zig build test`, "verde de verdade", pentest de rejeição, `simulated`, Q.A. plan-first.
  - `observabilidade.md` — `std.log` estruturado (JSON + `trace_id`), métricas Prometheus, traces via OTLP/lib C ou collector (honesto sobre ecossistema jovem), profiling nativo.
  - `dados-eventos.md`, `operacao.md`, `ops.md`, `entrega.md`, `anti-padroes.md`, `contexto-claude-code.md` — pisos agnósticos preservados, idiomas Zig-ificados (SQL parametrizado sem `std.fmt` em query, `zig build` no CI/DoD, anti-padrões específicos de Zig).
- **Comandos:** `/zig-help`, `/zig-load`, `/zig-claude`, `/zig-cc`, `/zig-handoff`, `/zig-qa`, `/zig-review`, `/zig-iam`, `/zig-index` (ripgrep `(pub )?fn ` para Zig), `/zig-ops`.
- **Scripts:** `lib.sh`, `test-skeleton.sh`, `smoke-selfcheck.sh`, `simulated/run.py`, `build-index.mjs` (com suporte a `.zig`/`pub fn`), `check-diff.sh` (gate de tamanho com extensão `.zig`), `archive-secret-scan.sh`, hooks de contexto.
- **Assets:** `CLAUDE.md` (sempre-on, pisos Zig), templates (ADR/TASK/CHAT/PR/RUNBOOK/MAPA/INDEX_*), CI (`ci/` com `zig fmt --check` + `zig build` + `zig build test` + cross-compile), guard de camadas Zig (`lint/zig-layers.md`), pre-commit (`hooks/`), `settings.claude.example.json`.

### Pisos inegociáveis (herdados da base, especializados a Zig)
- Segredo nunca no cliente (nem no binário/`@embedFile`); SQL sempre parametrizado; auth server-side; JWT validado por inteiro; erro nunca engolido (sem `catch unreachable`/`_ =` pra calar); **memória sem vazamento** (leak gate + `defer`/`errdefer`); **ReleaseSafe** em produção; **interop C validado no boundary**; archive obrigatório; migration reversível; ≤750 linhas/arquivo + doc-comment `///`; IAM por desenho como app separada; fluxo de ambientes + `<projeto>_ops`; deploy destrutivo por seed + isolamento por user.
- **Linguagem por fit, com ADR:** novo backend fora do rol sancionado sem ADR é VETADO; Zig é pre-1.0 (versão exata pinada).
