# Changelog — schematize-zig

Formato: [Keep a Changelog]; versionamento: SemVer.

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
