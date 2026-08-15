---
name: schematize-zig
metadata:
  version: 0.1.0
description: Padrões normativos de engenharia da casa com Zig — baixo nível, performance máxima, controle explícito de memória (allocators, sem GC), comptime, error unions, interop com C e artefatos estáticos pequenos. Use SEMPRE que for projetar, gerar, revisar ou refatorar qualquer serviço, CLI, componente de sistema, parser, driver, tooling ou biblioteca em Zig — mesmo que o usuário não cite "padrão" explicitamente. Aplique também ao decidir arquitetura, escolher stack (rol sancionado + fit), modelar eventos/banco, desenhar auth/identidade, escrever testes/pentest, configurar observabilidade, ou produzir ADR/runbook/archive. Contém pisos inegociáveis de segurança (segredo nunca no cliente, sem SQL concatenado, auth server-side, IAM por desenho — auth como app separada, ID≠email, ≥2 fatores, ReBAC multi-tenant, archive obrigatório) e de memória/código (teste com allocator que detecta leak, todo alloc com free casado, ReleaseSafe salvo perfil, ≤750 linhas/arquivo, uma função por arquivo, doc-comment `///`, MAPA da aplicação) que vetam atalhos inseguros. Frontend delega ao schematize-web; auth/cripto sensível costuma encaixar melhor em Rust (fit).
---

# Padrões de Engenharia da Casa — Zig

Conjunto normativo que rege como software de sistema é projetado, construído, testado e operado aqui **com Zig como linguagem**. Mesma base normativa das demais skills da casa; o que muda é o idioma, o build (`zig build`), o gerenciamento de memória (manual, por **allocators**, sem GC), o modelo de erro (**error unions** `!T`), a interop com C e o ecossistema.

**Versão:** skill `schematize-zig` v0.1.0. Changelog em `CHANGELOG.md`.

## Zig no rol sancionado (fit, não gosto)

A casa **não tem "a linguagem única"**; tem o **rol sancionado** (Go, Rust, Elixir, C#, **Zig**, Ruby no backend; Node só frontend) e um **guia de fit**. Escolha Zig por **encaixe com o problema**, com ADR (§27):

- **Zig encaixa em:** baixo nível e **performance máxima** com **controle explícito de memória**, embedded, **interop com C** (`@cImport` — uma força), artefatos estáticos pequenos, cross-compilation first-class, tooling de sistema. Sem GC, **sem controle de fluxo oculto, sem alocação oculta**.
- **Zig NÃO é o default de tudo:** um serviço de **auth/cripto** costuma encaixar melhor em **Rust** (segurança de memória por design, ecossistema maduro); um job de rede simples em **Go**; realtime em **Elixir**. Zig entra quando o requisito é **controle manual / interop C / artefato pequeno**. Detalhe em `references/arquitetura.md` (§3) e `references/stack-versoes.md`.
- **Zig é pre-1.0:** a **versão exata do compilador** é parte do contrato de build — fixe-a (`references/stack-versoes.md`).

## Comandos (Claude Code)

Digite `/zig-help` pra ver todos. Em resumo:

| Comando | O que faz |
|---|---|
| `/zig-help` | lista todos os comandos do schematize-zig |
| `/zig-cc` | context compact: gera context.md + checklist.md no archive e roda `/compact` |
| `/zig-handoff` | gera o handoff (context.md + checklist.md) **sem** compactar — pra fim de sessão |
| `/zig-qa` | fluxo de Q.A. plan-first (§22.9): planeja, gera MD, pede aprovação, roda |
| `/zig-review` | roda o gate da DoD no diff (arquivo >750 bloqueia / >300 úteis flag, função sem doc `///`, MAPA, índice, macaquices) |
| `/zig-iam` | força/audita/scaffolda o IAM da casa (auth como app separada, ID≠email, ≥2 fatores, ReBAC multi-tenant, sessão longa/logout irreversível) ou migra um auth legado |
| `/zig-index` | (re)gera o índice de microfunções a partir dos doc-comments `///` |
| `/zig-ops` | audita/scaffolda o `<projeto>_ops` (interface única): fluxo de ambientes, instalação paralela (`nproc`), independência |

Todos os comandos são prefixados com o slug (`zig-`), então **convivem sem conflito** com `schematize-go` (`go-*`), `schematize-rust` (`rust-*`) e `schematize-web` (`web-*`) na mesma máquina. Ficam em `assets/commands/` e são instalados em `.claude/commands/`.

## Como usar esta skill

1. Identifique o domínio da tarefa e **leia o(s) reference(s) relevante(s)** antes de produzir código ou decisão. Não trabalhe de memória — versões, limites e convenções estão nos arquivos.
2. **Sempre** aplique os pisos inegociáveis abaixo, independente do reference carregado.
3. Ao terminar, valide contra a Definition of Done (`references/entrega.md`, §35) e **gere o archive** (§28, `references/operacao.md`).

Mapa de references — leia o que casa com a tarefa:

| Tarefa | Reference |
|---|---|
| **Versão do compilador Zig (pre-1.0 — pin exato), toolchain, quando usar Zig no rol** | `references/stack-versoes.md` |
| **Memória e concorrência: allocators (GPA/Arena/FixedBuffer), leak detection, `defer`/`errdefer`, ownership, threads, async em evolução, `ReleaseSafe`** | `references/memoria-concorrencia.md` |
| **Limites de código (arquivo ≤750: ~500 úteis + ~250 comentário; flag >300 úteis), uma função/arquivo, doc-comment `///`, MAPA** | `references/padroes-codigo.md` |
| Arquitetura, camadas, DDD, repositórios, anti-monólito, shared libs, **rol de linguagens/fit**, CQRS | `references/arquitetura.md` |
| Eventos/mensageria, banco, cache, APIs, resiliência, jobs | `references/dados-eventos.md` |
| Segurança, auth, JWT, multi-tenancy, LGPD, **build mode (ReleaseSafe/Fast), interop C, overflow, segredos** | `references/seguranca.md` |
| **IAM — auth como app separada (`auth.<domain>`), ID≠email, ≥2 fatores, ReBAC multi-tenant deny-default, sessão 7d/90d, logout irreversível; posicionamento honesto (auth costuma pedir Rust/Go — fit)** | `references/iam.md` |
| **Cadeia de suprimentos: `build.zig.zon` com hash, pin da toolchain, cross-compile, SBOM, scan que trava, imagem mínima/pinada/assinada** | `references/cadeia-suprimentos.md` |
| Testes — `zig test`, `std.testing`, leak gate, categorias de teste (§22.1–22.3) | `references/testes.md` |
| Testes — `zig build test`, padrão de script, seeds, CI, pentest, Q.A. plan-first (§22.4–23) | `references/testes-execucao.md` |
| Observabilidade, `std.log` estruturado, healthchecks, performance, FinOps (ecossistema jovem — pragmático) | `references/observabilidade.md` |
| Config, deploy/K8s, git/PR, ownership, runbooks/incidentes, ADR, **archive** (§20–28) | `references/operacao.md` |
| **Ops (control plane): fluxo dev→local→github→hml→prd (nada direto no servidor), ops como interface única (100%, autônomo), instalação paralela=`nproc`, independência=invariante** | `references/ops.md` |
| Templates, feature flags, IA assistida, DoD, evolução, índice de funcionalidades (§29+) | `references/entrega.md` |
| Filosofia, aplicação universal e a lista completa de anti-padrões vetados | `references/anti-padroes.md` |
| Gestão de contexto em sessões longas no Claude Code (handoff, hooks) | `references/contexto-claude-code.md` |

## Pisos inegociáveis (VETADO — sem ADR de exceção)

Nunca violados, nem "pra funcionar", nem "pra ir mais rápido". Lista completa em `references/anti-padroes.md`. Os que mais aparecem:

- **Segredo nunca no cliente.** Nada de API key, secret de JWT, senha de banco ou token em bundle do browser nem em `NEXT_PUBLIC_*`/`VITE_*`. Nada de segredo embutido no binário (`@embedFile` de config sensível) ou na fonte. Segredo só server-side. Detalhe em `references/seguranca.md`.
- **SQL sempre parametrizado.** Zig não tem `format!`, mas montar query com `std.fmt.allocPrint`/concatenação é o mesmo pecado — injeção esperando acontecer. Use driver com binds parametrizados (ou `libpq`/`PQexecParams` via `@cImport`).
- **Auth e autorização server-side.** `tenant_id`/role/`user_id` vêm do token verificado, nunca do body/header do cliente.
- **JWT validado por inteiro** (assinatura, exp, aud, iss, alg em allowlist). Senha em argon2id (ou bcrypt cost ≥ 12). Token de sessão por CSPRNG (`std.crypto.random`), nunca PRNG previsível.
- **Erro nunca engolido.** Sem `_ = foo()` descartando um error union, sem `catch unreachable`/`catch @panic(...)`/`catch {}` em caminho de produção pra calar o compilador; trate `!T`/`?T` de verdade (`try`, `catch |err| {...}`, `errdefer`, `orelse`).
- **Memória sem vazamento (piso Zig).** Todo `alloc` tem **caminho de `free` casado** (`defer alloc.free(...)` / `errdefer` no erro); **todo teste roda com o allocator que detecta leak** (`std.testing.allocator`; `GeneralPurposeAllocator` com `.deinit()` que reporta em debug). Vazar memória é bug de entrega, não detalhe. Detalhe em `references/memoria-concorrencia.md`.
- **Build mode seguro.** Produção exposta a input hostil roda em **`ReleaseSafe`** (bounds check + trap de overflow) salvo perfil que justifique `ReleaseFast`/`ReleaseSmall` em ADR — sem as checagens, use-after-free/OOB viram UB explorável. Detalhe em `references/seguranca.md`.
- **Teste nunca silenciado** pra passar CI (comentar assert, remover o bloco `test`, baixar threshold). Conserta o código, não o teste.
- **Sem monólito que mistura bounded contexts**, sem monólito distribuído, sem shared lib `commons` de domínio.
- **Archive SEMPRE gerado.** Toda entrega que produz código/decisão/mudança de estado gera o `.md` de archive. Templates em `assets/`.
- **Migration reversível** (com `down`, testada com rollback). Container não-root, read-only. Dependência nova com nome/licença/versão verificados; no `build.zig.zon`, **com hash fixado** (branch móvel é VETADO).
- **Interop C validado no boundary.** `@cImport` é a superfície de risco: valida ponteiros, tamanhos, strings NUL-terminadas e retorno de erro do C — a garantia de memória do Zig **não** atravessa pra dentro da lib C. Trate o C como não-confiável.
- **Pisos de código (`references/padroes-codigo.md`):** arquivos **≤ 750 linhas** (~500 úteis + ~250 comentário; acima → quebrar por coesão), **flag em > 300 úteis** (~400 em observabilidade), **uma função/unidade lógica por arquivo**, **toda função com doc-comment `///`** (motivo, comportamento, entradas — incluindo o `Allocator` e quem é dono da memória —, saídas/erros do `!T`, efeitos), **`zig fmt --check`** no CI, **`MAPA.md`** em `<projeto>_archive/index/` (nunca no root) e **índice de microfunções** regenerado (`/zig-index`). Todo MD gerado mora no archive (§28).
- **Linguagem: Zig por fit, com ADR.** Backend novo sai do **rol sancionado** (Go/Rust/Elixir/C#/Zig/Ruby) por encaixe (§27); **novo backend fora do rol sem ADR é VETADO**; Node backend e PHP são legado/saída (migram por funcionalidade do módulo). Detalhe em `references/arquitetura.md` (§3) e `references/stack-versoes.md`.
- **Fluxo de ambientes e ops (`references/ops.md`).** Toda mudança segue **dev local → teste local → GitHub → hml → prd**; **VETADO editar código direto no servidor**. **100%** das operações no servidor passam pela **ferramenta do `<projeto>_ops`**; o ops é **autônomo**. **Instalação sempre paralela** = `nproc`; **falha no paralelo = serviços não independentes → corrigir a independência é prioridade máxima** (nunca serializar pra mascarar).
- **Deploy destrutivo por seed + isolamento por usuário (`references/ops.md` §2–§3).** Redeploy destrutivo na aplicação (clone zerado do seed), **preservando dados**; `/<app>/.env` é o seeder global; cada serviço como user Linux próprio em systemd unit hardened (binário estático Zig facilita distroless/scratch).
- **IAM por desenho (`references/iam.md`).** Auth é **app SEPARADA** (`<projeto>_auth_zig` + front em `auth.<domain>`), delega por **OIDC/OAuth2.1 + PKCE**, valida por JWKS público. **ID interno imutável (ULID/UUIDv7) — email/telefone nunca é ID.** **≥2 fatores baseline** (senha + Email OTP Resend always-on; passkey/WebAuthn no núcleo; TOTP/push; Twilio) — o PEP **não barra o login baseline**, exige AAL alto **só por rota sensível** (step-up just-in-time). **Multi-tenant ReBAC deny-default** (OpenFGA/SpiceDB). Sessão 7d/90d; **logout irreversível**. **Posicionamento honesto:** o serviço de auth costuma encaixar melhor em Rust/Go (fit) — se for Zig, registre o ADR e cumpra o piso igual. **Migrar auth legado = prioridade 0.** Scaffold/auditoria por `/zig-iam`.

> Regra de bolso: se a justificativa começa com "só pra funcionar", "depois eu arrumo" ou "é mais rápido assim" e o resultado mexe em segredo, auth, memória, dado ou registro — é anti-padrão vetado. Pare e faça certo.

## Testes — o que conta como "verde de verdade"

Detalhe em `references/testes.md` (§22.1–22.3) e `references/testes-execucao.md` (§22.4–23). Essencial: `zig test`/blocos `test "..." {}` que **rodam com o `std.testing.allocator`** (leak vira FAIL); smoke que assere shape (não só 200) e tem self-check que força um FAIL conhecido; unit agressivo com caminho de erro (`expectError` em todo `!T`), casos hostis (tipo/tamanho errado, unicode, null byte, boundary, overflow de inteiro); pentest que prova rejeição rota a rota; `simulated` cruzando rotas × personas × injections cobrindo 100% das rotas; e Q.A. plan-first (planeja, gera MD, pede aprovação antes de rodar).

## Andaime pronto (scripts e templates)

Não escreva do zero o que já está bundlado: `scripts/lib.sh`, `scripts/test-skeleton.sh`, `scripts/smoke-selfcheck.sh`, `scripts/simulated/run.py`, os hooks de contexto (`scripts/hooks/*.mjs`), os templates em `assets/` (ADR, TASK, CHAT_ARCHIVE, PR_TEMPLATE, RUNBOOK, **MAPA**), o índice (`assets/INDEX_*` + `scripts/build-index.mjs`) e `assets/CLAUDE.md` pra pinar os padrões na raiz do repo.

## Aplicação sempre-on

Copie `assets/CLAUDE.md` para a raiz do projeto pra garantir os padrões em toda interação do repo, não só quando a skill dispara.
