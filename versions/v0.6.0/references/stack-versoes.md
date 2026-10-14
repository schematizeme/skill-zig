# Stack e Versões — Zig (pre-1.0), toolchain e quando usar Zig

> **Verificado em: 2026-08-21** — a estável corrente do Zig é a **0.16.0**
> (conferida em `ziglang.org/download/index.json` nesta data, e usada para compilar e rodar os
> exemplos de `references/iam.md` §3.1: `zig test` → *All 6 tests passed*, exit 0). O 0.14.x, que
> este anexo usava como referência, está **duas minors atrás**.
>
> Parte da skill **schematize-zig**. Define a preferência de linguagem desta skill
> dentro do **rol sancionado** da casa e — o ponto mais sensível do Zig — a **política
> de versão do compilador**. Zig é **pre-1.0**: a versão exata é parte do contrato de
> build. Liga com `references/arquitetura.md` (§3, rol/fit), `references/cadeia-suprimentos.md`
> (hash de deps + pin) e `references/memoria-concorrencia.md`.

## Índice
- 1. Zig no rol sancionado (fit, não gosto)
- 2. Zig é pre-1.0 — a versão é contrato
- 3. Pin da toolchain (piso)
- 4. Toolchain e ferramental (piso)
- 5. Quando NÃO é Zig
- 6. Coexistência com as outras skills

---

## 1. Zig no rol sancionado (fit, não gosto)

A casa não tem "a linguagem única"; tem o **rol sancionado** (Go, Rust, Elixir, C#,
**Zig**, Ruby no backend; Node só frontend) e um **guia de fit** (`references/arquitetura.md`
§3, base agnóstica em `schematize-engineering`). Esta skill é a **especialização Zig**
do rol. Escolha Zig por **encaixe com o problema**, registrado em **ADR** (§27):

- **Zig encaixa quando o requisito é:** baixo nível e **performance máxima** com
  **controle explícito de memória** (allocators, sem GC), **embedded**, **interop com C**
  (`@cImport` — uma força de primeira classe), **artefatos estáticos pequenos**,
  **cross-compilation** trivial (`-Dtarget=...`), tooling de sistema, parsers/drivers
  de alto desempenho. Sem controle de fluxo oculto, sem alocação oculta, sem
  sobrecarga de operador — o custo é sempre visível.
- **Regra de fit:** um utilitário de sistema / componente de interop C / artefato
  pequeno pede **Zig**; auth/cripto pede **Rust**; job de rede simples pede **Go**;
  realtime pede **Elixir**; integração .NET pede **C#**; protótipo pede **Ruby**. Em
  empate técnico, siga o desempate pragmático em `schematize-engineering → references/linguagens.md`; registre o porquê no ADR.

> Zig **não** é o default de tudo. É a escolha certa para o recorte de sistema/interop/
> performance com memória manual. Fora desse recorte, prefira a linguagem que o fit
> manda — e registre no ADR.

## 2. Zig é pre-1.0 — a versão é contrato

Zig **ainda não chegou ao 1.0**. Consequências que viram piso:

- **Breaking changes entre versões são esperados** — mudanças de sintaxe, de API da
  `std`, do sistema de build (`build.zig`) e do gerenciador de pacotes acontecem entre
  releases. Código que compila em `0.14.x` pode **não** compilar em `0.15.x` — e de fato não
  compila: entre 0.14 e 0.16 a `std` moveu `std.Thread.Mutex` para `std.Io.Mutex` (com `lock`
  recebendo um `Io`), entre outras quebras. **Pin exato, e o bump é tarefa com teste.**
- A **versão exata do compilador faz parte do contrato de build.** "Roda no meu Zig"
  não é reprodutível se o teu Zig e o do CI diferem. A versão é tão parte do build
  quanto o `build.zig.zon`.
- Prefira **releases marcadas** (hoje: **`0.16.0`**) a `master`/nightly em produção.
  Nightly só em spike de exploração, nunca no artefato que vai pra hml/prd.

## 3. Pin da toolchain (piso)

**MUST**
- **Fixe a versão exata do Zig** e registre-a em **três lugares que têm que concordar**:
  1. **`build.zig.zon`** — campo `minimum_zig_version` (piso mínimo do projeto);
  2. **CI** — instala e usa **a versão exata** (não "a mais recente"); o job falha se
     a versão divergir;
  3. **`<projeto>_ops` / README** — a versão que o dev e o servidor usam, provisionada
     pelo ops (o usuário instala a toolchain do zero pelo ops, `references/ops.md`).
- **Uma fonte da verdade da versão** (ex.: um arquivo `.zig-version` ou variável no
  ops) consumida por dev, CI e deploy — nada de cada um escolher a sua.
- **Upgrade de versão do Zig é uma mudança deliberada, com ADR** (§27): registra a
  versão de/para, o que quebrou, e passa pelo fluxo de ambientes normal
  (`references/ops.md`: dev → local → github → hml → prd). Nunca "bumpa o compilador no
  servidor pra ver se resolve".

**VETADO**
- Build/CI/servidor em versões **diferentes** do compilador.
- Depender de `master`/nightly no artefato de release.
- Trocar a versão do Zig direto no servidor (fere o fluxo de ambientes — §21).

**SHOULD**
- Ao subir de versão, rodar a suíte completa (`zig build test` com leak gate,
  `references/testes.md`) e o cross-compile de smoke dos alvos suportados antes de promover.
- Anotar no CHANGELOG/ADR a versão do Zig usada em cada release.

## 4. Toolchain e ferramental (piso)

- **Build:** `zig build` com **`build.zig`** (o build é código Zig, versionado). Steps
  nomeados idiomáticos: `zig build`, `zig build run`, `zig build test`, `zig build check`.
- **Dependências:** **`build.zig.zon`** — cada dep com **URL + `hash` criptográfico**
  (o hash é o lockfile; build falha se o conteúdo não bater), mais os dois campos que o **0.16**
  exige no topo e que quebram `.zon` antigo: **`.name` como enum literal** (`.name = .meu_servico`)
  e **`.fingerprint`** (o compilador sugere o valor no próprio erro). Detalhe e piso em
  `references/cadeia-suprimentos.md`.
- **Formatação:** `zig fmt` é a formatação canônica; **`zig fmt --check` trava o CI**.
- **Erros:** error unions `!T` sempre tratados (`try`, `catch |err|`, `errdefer`);
  **VETADO** `catch unreachable`/`catch @panic`/`_ =` pra silenciar em produção
  (`references/anti-padroes.md`).
- **Memória:** allocator explícito passado nas assinaturas; leak gate nos testes;
  `ReleaseSafe` como padrão de produção. Detalhe em `references/memoria-concorrencia.md`.
- **Cross-compile:** `zig build -Dtarget=<arch>-<os>-<abi>` — artefato estático pequeno,
  sem toolchain externa. Cada alvo de release é reproduzível e pinado.
- **Segurança de deps:** onde não há SCA nativo de Zig, o **hash-pin do `build.zig.zon`
  + revisão manual da árvore** é o piso; secret scan (Gitleaks) e scan de imagem
  (Trivy/Grype) rodam no container final (`references/cadeia-suprimentos.md`).

## 5. Quando NÃO é Zig

Reconheça o custo antes de escolher (e registre no ADR se escolher mesmo assim):

- **Auth/cripto sensível** → o fit manda **Rust** (ou Go): segurança de memória por
  design, ecossistemas WebAuthn/OIDC/ReBAC maduros. O de IAM em Zig é jovem
  (`references/iam.md` é honesto sobre isso).
- **CRUD de rede simples / glue** → **Go** entrega mais rápido, com concorrência e
  ecossistema prontos.
- **Realtime/altíssima concorrência tolerante a falha** → **Elixir**.
- **Ecossistema imaturo é custo real:** drivers de banco, clients de mensageria,
  bindings de observabilidade em Zig são jovens — muitas vezes a resposta é `@cImport`
  de uma lib C madura (com o **boundary validado**, `references/seguranca.md`). Isso é
  aceitável e idiomático em Zig, mas **é custo** — pese no ADR.

## 6. Coexistência com as outras skills

`schematize-zig`, as irmãs do rol e a `schematize-web` podem estar
habilitadas na mesma máquina ao mesmo tempo. Não há conflito: cada skill instala em
`.claude/skills/schematize-<slug>/` e seus comandos são prefixados pelo slug
(`/zig-*`, `/go-*`, `/rust-*`, `/web-*`). Um sistema real pode ser poliglota — um
componente Zig de performance ao lado de um serviço Go e um auth Rust, cada um sob a
sua skill, todos sob os mesmos pisos agnósticos. Escolha a skill pela natureza do
trabalho; o repo Zig usa o sufixo **`_zig`** (`<projeto>_<contexto>_zig`).
