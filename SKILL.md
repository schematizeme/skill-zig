---
name: schematize-zig
metadata:
  version: 0.5.0
description: >-
  Padrões de engenharia para Zig: baixo nível, interop C, alocadores explícitos. Use ao projetar ou revisar serviço,
  biblioteca, binding C ou parser com build.zig/*.zig, ou ao escolher Zig no rol (fit + ADR). Leak-test e archive.
---

# Padrões de Engenharia da Casa — Zig

Conjunto normativo que rege como software de sistema é projetado, construído, testado e operado aqui **com Zig como linguagem**. Mesma base normativa das demais skills da casa; o que muda é o idioma, o build (`zig build`), o gerenciamento de memória (manual, por **allocators**, sem GC), o modelo de erro (**error unions** `!T`), a interop com C e o ecossistema.

**Versão:** skill `schematize-zig` v0.5.0. Changelog em `CHANGELOG.md`.

## Zig no rol sancionado (fit, não gosto)

A casa **não tem "a linguagem única"**; tem o **rol sancionado** (Go, Rust, Elixir, C#, **Zig**, Ruby no backend; Node só frontend) e um **guia de fit**. Escolha Zig por **encaixe com o problema**, com ADR (§27):

- **Zig encaixa em:** baixo nível e **performance máxima** com **controle explícito de memória**, embedded, **interop com C** (`@cImport` — uma força), artefatos estáticos pequenos, cross-compilation first-class, tooling de sistema. Sem GC, **sem controle de fluxo oculto, sem alocação oculta**.
- **Zig NÃO é o default de tudo:** um serviço de **auth/cripto** costuma encaixar melhor em **Rust** (segurança de memória por design, ecossistema maduro); um job de rede simples em **Go**; realtime em **Elixir**. Zig entra quando o requisito é **controle manual / interop C / artefato pequeno**. Detalhe em `references/arquitetura.md` (§3) e `references/stack-versoes.md`.
- **Zig é pre-1.0:** a **versão exata do compilador** é parte do contrato de build — fixe-a (`references/stack-versoes.md`).

## Precedência e herança (leia antes de divergir)

<!-- herdado:engineering/precedencia:backend linguagem="Zig" -->Esta skill é o **recorte Zig** da base. Duas regras governam a relação, e elas resolvem sozinhas
quase toda dúvida de "onde está escrito o quê":

1. **Onde esta skill divergir da base, a BASE MANDA.** `schematize-engineering` é a normativa; aqui
   mora a **especialização** — o mecanismo, a lib, a sintaxe, o gate da linguagem. Divergência de
   *piso* entre este arquivo e a base é **defeito desta skill**, não uma variante local aceitável.
   Achou uma? É item de correção, não licença. *(Foi assim que o `argon2id-only` da casa virou
   "argon2id ou PBKDF2" em uma skill só, e o rol de 6 linguagens virou "só Go e Rust" em três.)*
2. **O que não está repetido aqui é HERDADO, não dispensado.** A ausência de um piso neste repo
   nunca significa que ele não vale — significa que ele não muda de forma nesta linguagem. Em
   especial, valem integralmente, sem cópia local:
   - **§28 Archive** — `<projeto>/<projeto>_archive/` é **repositório git próprio, PRIVADO e
     obrigatório**, criticidade 0 (`schematize-archive`; ADR-0005 para a planta canônica).
   - **§39 Índice/MAPA** — enumeração exaustiva (uma entrada por unidade chamável, `M == N`) e o
     **grafo com arestas em ASCII (`A -> B`), NUNCA a seta unicode** — o parser do app lê ASCII.
   - **§35 Definition of Done** e a lista de anti-padrões **§37** (citada por **título**, nunca por
     número: a numeração dos itens diverge entre skills).
   - **IAM** (`schematize-engineering` → `references/iam.md`): identidade ≠ email, ≥2 fatores, ReBAC multi-tenant,
     **alcançabilidade do 2º fator** (o fator de recuperação tem de ser alcançável quando o
     principal cai — senão o 2FA vira bug de bootstrap que tranca o dono para fora), os parâmetros
     mínimos de argon2id, sessão longa e logout irreversível.
   - **Rol sancionado** — Go, Rust, Elixir, C#, Zig, Ruby, por **fit + ADR**
     (`schematize-engineering` → `references/linguagens.md`). Esta skill é **uma** delas, não a
     régua das outras.
   - **Efeito externo** nunca sai de não-produção (`schematize-engineering` →
     `references/efeitos-externos.md`; gate em `scripts/check-external-effects.sh`, distribuído
     aqui — ADR-0008).<!-- /herdado -->

## Comandos (Claude Code)

Digite `/zig-help` pra ver todos. Em resumo:

| Comando | O que faz |
|---|---|
| `/zig-help` | lista todos os comandos do schematize-zig |
| `/zig-load` | carrega à força TODO o corpo normativo no contexto e passa a aplicá-lo como regra inegociável |
| `/zig-claude` | cria ou **atualiza (sobrescreve)** o `CLAUDE.md` da raiz com a versão atual da skill (backup se houver customização) |
| `/zig-cc` | context compact: gera context.md + checklist.md no archive e roda `/compact` |
| `/zig-handoff` | gera o handoff (context.md + checklist.md) **sem** compactar — pra fim de sessão |
| `/zig-qa` | Q.A. no contexto Zig — wrapper fino da **schematize-qa** (`/qa-plan` → `/qa-run`) com `zig test`/`zig build test` |
| `/zig-review` | roda o gate da DoD no diff (arquivo >750 bloqueia / >300 úteis flag, função sem doc `///`, MAPA, índice, macaquices) |
| `/zig-iam` | força/audita/scaffolda o IAM da casa (auth como app separada, ID≠email, ≥2 fatores, ReBAC multi-tenant, sessão longa/logout irreversível) ou migra um auth legado |
| `/zig-index` | (re)gera o índice de microfunções a partir dos doc-comments `///` |
| `/zig-ops` | audita/scaffolda o `<projeto>_ops` (interface única): fluxo de ambientes, instalação paralela (`nproc`), independência |

Todos os comandos são prefixados com o slug (`zig-`), então **convivem sem conflito** com as skills irmãs do rol (`go-*`, `rust-*`, `elixir-*`, `cs-*`, `ruby-*`) e `schematize-web` (`web-*`) na mesma máquina. Ficam em `assets/commands/` e são instalados em `.claude/commands/`.

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
| Testes — o recorte Zig (runner, sintaxe, armadilhas do dialeto). **A disciplina é da `schematize-qa`.** | `references/testes.md` |
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
- **JWT validado por inteiro** (assinatura, exp, aud, iss, alg em allowlist). Senha: argon2id-only para senha nova (bcrypt/PBKDF2 só legado a migrar no próximo login); parâmetros em `schematize-engineering → references/iam.md` §2.1. Token de sessão por CSPRNG (**`io.random`** / `io.randomSecure` — ✔ 0.16.0), nunca PRNG previsível.
- **Erro nunca engolido.** Sem `_ = foo()` descartando um error union, sem `catch unreachable`/`catch @panic(...)`/`catch {}` em caminho de produção pra calar o compilador; trate `!T`/`?T` de verdade (`try`, `catch |err| {...}`, `errdefer`, `orelse`).
- **Memória sem vazamento (piso Zig).** Todo `alloc` tem **caminho de `free` casado** (`defer alloc.free(...)` / `errdefer` no erro); **todo teste roda com o allocator que detecta leak** (`std.testing.allocator`; `std.heap.DebugAllocator` com `.deinit()` que reporta em debug). Vazar memória é bug de entrega, não detalhe. Detalhe em `references/memoria-concorrencia.md`.
- **Build mode seguro.** Produção exposta a input hostil roda em **`ReleaseSafe`** (bounds check + trap de overflow) salvo perfil que justifique `ReleaseFast`/`ReleaseSmall` em ADR — sem as checagens, use-after-free/OOB viram UB explorável. Detalhe em `references/seguranca.md`.
- **Teste nunca silenciado** pra passar CI (comentar assert, remover o bloco `test`, baixar threshold). Conserta o código, não o teste.
- **Sem monólito que mistura bounded contexts**, sem monólito distribuído, sem shared lib `commons` de domínio.
- **Archive SEMPRE gerado.** Toda entrega que produz código/decisão/mudança de estado gera o `.md` de archive. Templates em `assets/`.
- **Migration reversível** (com `down`, testada com rollback). Container não-root, read-only. Dependência nova com nome/licença/versão verificados; no `build.zig.zon`, **com hash fixado** (branch móvel é VETADO).
- **Interop C validado no boundary.** `@cImport` é a superfície de risco: valida ponteiros, tamanhos, strings NUL-terminadas e retorno de erro do C — a garantia de memória do Zig **não** atravessa pra dentro da lib C. Trate o C como não-confiável.
- **Efeito externo NUNCA sai de não-produção.** E-mail, SMS/voz, push, webhook de terceiro e cobrança **não acontecem de verdade** fora de `prd` — por construção. Em Zig: o provider é **vtable** (`EmailProvider`), o **SINK é o default fora de prd** e o **guard é um provider que envelopa o de dentro** — a recusa é **error union** (`error{ExternalRecipientBlocked}`), **VETADO** `catch {}`/`catch unreachable` em cima dela; a seleção por ambiente acontece **uma vez na composição**, nunca no chamador; o ambiente vem de `APP_ENV`. Seeds e fixtures `simulated` seguem o mesmo domínio de teste. <!-- herdado:engineering/efeito-externo:invariantes -->**Cap por execução** (`MAIL_MAX_PER_RUN`, default 50) com abort; **fail-closed** (ambiente ausente/desconhecido ⇒ não-prd; só o valor exato de produção entrega de verdade); **chave sandbox** fora de prd. Todo endereço sintético (fixture, seed, persona, demo, carga) é `<papel>+<run-id>-<n>@test.<domain>` — domínio em **rota nula** (null MX RFC 7505 + SPF `-all` + DMARC `p=reject`) ou TLD reservado (`.test`/`.invalid`/`.example`); **VETADO** `@gmail.com`, domínio de cliente/terceiro, e-mail de pessoa real (**inclusive o seu**) e o domínio de produção. A recusa é **erro**, nunca warning nem sucesso silencioso. Entregar de verdade fora de prd exige **as cinco** (ADR + allowlist ≤5 + cap + janela + subdomínio separado). Motivo: bounce/complaint em massa **queima IP e domínio** e derruba o transacional de prd — inclusive o **OTP de login** — com semanas de warm-up e utilidade zero (o incidente dos 5.000 e-mails só existiu porque nada contava).<!-- /herdado --> Código e teste em `references/iam.md` §3.1; normativa em `schematize-engineering` → `references/efeitos-externos.md`.
- **Pisos de código (`references/padroes-codigo.md`):** arquivos **≤ 750 linhas** (~500 úteis + ~250 comentário; acima → quebrar por coesão), **flag em > 300 úteis** (~400 em observabilidade), **uma função/unidade lógica por arquivo**, **toda função com doc-comment `///`** (motivo, comportamento, entradas — incluindo o `Allocator` e quem é dono da memória —, saídas/erros do `!T`, efeitos), **`zig fmt --check`** no CI, **`MAPA.md`** em `<projeto>_archive/index/` (nunca no root) e **índice de microfunções** regenerado (`/zig-index`). Todo MD gerado mora no archive (§28).
- **Linguagem: Zig por fit, com ADR.** Backend novo sai do **rol sancionado** (Go/Rust/Elixir/C#/Zig/Ruby) por encaixe (§27); **novo backend fora do rol sem ADR é VETADO**; Node backend e PHP são legado/saída (migram por funcionalidade do módulo). Detalhe em `references/arquitetura.md` (§3) e `references/stack-versoes.md`.
- **Fluxo de ambientes e ops (`references/ops.md`).** <!-- herdado:engineering/fluxo-ambientes:corpo -->Toda mudança segue **dev local → teste local → GitHub → hml → prd**; **VETADO editar código direto no servidor** (hml/prd é imutável por edição manual, recebe só artefato do git). **100%** das operações no servidor (install/update/correção/config/migrate/rollback) passam pela **ferramenta do `<projeto>_ops`** — nunca à mão; o ops é **autônomo** (o usuário provisiona o servidor do zero sem a IA). **Instalação sempre paralela** = `nproc`; **falha no paralelo = serviços não independentes → corrigir a independência é prioridade máxima** (não serializar pra mascarar).<!-- /herdado -->
- **Deploy destrutivo por seed + isolamento por usuário (`schematize-engineering` -> `references/ops.md` §2–§3).** <!-- herdado:engineering/deploy-destrutivo:corpo -->O ops provisiona em **`/<app>/`** clonando os repos dentro; **`/<app>/.env` é o seeder global** (fonte única de config). **Todo redeploy é destrutivo na aplicação** — apaga a anterior e recria um clone zerado só com o seed (idempotente/sem drift), **preservando os dados** (migration reversível; `ops reset` de dados só em dev/hml). **Cada serviço roda como user Linux próprio em systemd unit hardened** (blast radius mínimo). Tudo automatizado pelo ops.<!-- /herdado --> (binário estático Zig facilita distroless/scratch).
- **IAM por desenho (`references/iam.md`).** Auth é **app SEPARADA** (`<projeto>_auth_zig` + front em `auth.<domain>`), delega por **OIDC/OAuth2.1 + PKCE**, valida por JWKS público. **Posicionamento honesto:** o serviço de auth costuma encaixar melhor em Rust/Go (fit) — se for Zig, registre o ADR e cumpra o piso igual. <!-- herdado:engineering/iam-desenho:invariantes cmd="zig" -->**ID interno imutável (ULID/UUIDv7) — email/telefone nunca é ID** (N emails por usuário; SSO com recuperação local). **≥2 fatores sempre**: passkey/WebAuthn no núcleo, TOTP/push, email OTP always-on, Twilio para telefone; senha argon2id+HIBP por padrão, mas opcional; invariante de troca de fator (Y≠X no maior AAL); **recuperação ≥ login**. Senha + Email OTP já é **2FA baseline**: o PEP libera o baseline e exige AAL alto **só por rota sensível** (step-up just-in-time), nunca barra o login. **Multi-tenant RBAC/ABAC granular via ReBAC** (OpenFGA/SpiceDB; deny-default, PDP=Check API, PEP no servidor, token fino). **Multi-dispositivo, sessão 7d/90d, logout irreversível** (revoga refresh+família, `jti` na denylist, não só cookie). **Migrar auth legado = prioridade 0.** Scaffold/auditoria por **`/zig-iam`**; testes cross-tenant/priv-esc na `schematize-pentest`.<!-- /herdado -->
- <!-- herdado:engineering/orquestracao:bullet -->**Orquestrador não desenvolve; subagent barato executa** (`schematize-engineering` → `references/orquestracao.md` §9). O principal só planeja/decompõe/despacha/supervisiona/revisa; ação onerosa vira micro-tasks; principal = Claude Opus; executor mais barato que resolve: `haiku` (mecânico) / `sonnet` (código, até 2 rodadas de correção pelo mesmo subagent) → Codex `gpt-5.6-terra` → Cursor → subagent `opus` (motivo no checkpoint) → `park`; **visual direto ao Codex; imagem nunca pelo Claude (pergunta ao usuário: Codex sugerido, ou Gemini), API de imagem paga PROIBIDA**; papéis configuráveis em `agentes.toml` (aba "Agentes" do overdev). No `overdev`, cada item do checklist é executado pelo papel adequado e revisado pelo principal (diff + gate) antes do `- [x]`. **Sem frota ociosa:** agent idle com pendência executável volta ao trabalho; pendência que depende de outro agent → mata e enfileira com gatilho de dependência; terminou → mata (§9.6).<!-- /herdado -->

> Regra de bolso: se a justificativa começa com "só pra funcionar", "depois eu arrumo" ou "é mais rápido assim" e o resultado mexe em segredo, auth, memória, dado ou registro — é anti-padrão vetado. Pare e faça certo.

## Testes — o que conta como "verde de verdade"

Detalhe em `references/testes.md` (o recorte Zig) — a **disciplina** de teste é da `schematize-qa`, e a segurança ofensiva da `schematize-pentest`.

## Andaime pronto (scripts e templates)

Não escreva do zero o que já está bundlado: `scripts/lib.sh`, `scripts/test-skeleton.sh`, `scripts/smoke-selfcheck.sh`, `scripts/simulated/run.py`, os hooks de contexto (`scripts/hooks/*.mjs`), os templates em `assets/` (ADR, TASK, CHAT_ARCHIVE, PR_TEMPLATE, RUNBOOK, **MAPA**), o índice (`assets/INDEX_*` + `scripts/build-index.mjs`) e `assets/CLAUDE.md` pra pinar os padrões na raiz do repo.

## Aplicação sempre-on

Copie `assets/CLAUDE.md` para a raiz do projeto pra garantir os padrões em toda interação do repo, não só quando a skill dispara.
