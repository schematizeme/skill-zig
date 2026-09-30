# Arquitetura, Camadas, Repositórios e Linguagens


> **PONTEIRO, não cópia.** A normativa deste tema é da base: **`schematize-engineering`** →
> `references/arquitetura.md`. Leia lá primeiro; aqui fica **só o que muda em Zig**.
>
> **Onde este arquivo divergir da base, a BASE MANDA** (`SKILL.md` §"Precedência e herança").
> Em 2026-08-21 os blocos idênticos à base foram **podados mecanicamente** (`tools/podar-clone.mjs`),
> que é por que a numeração dos itens **salta**: o número é o da base, e o item que não aparece aqui
> é porque **não muda nesta linguagem** — procure-o lá. Manter a cópia era manter a próxima deriva
> (foi assim que o `argon2id-only` da casa virou "ou PBKDF2" numa skill e o rol de 6 linguagens
> virou "só Go e Rust" em três).

## 2. Estrutura de Repositórios

- **Nome do repositório:** `<projeto>_<contexto>[_<lang>]` em snake_case minúsculo. `<projeto>` = slug do produto/organização; `<contexto>` = a aplicação/bounded context daquele repo (`core`, `gateway`, `worker`, `front`, `backoffice`…); `_<lang>` é sufixo pra desambiguar linguagem (`_zig` Zig, `_go` Go, `_rs` Rust, `_ex` Elixir, `_cs` C#, `_rb` Ruby, `_ts` TypeScript). **Nesta skill, o serviço Zig usa o sufixo `_zig`.** Como um repo = um contexto, o nome espelha isso. Ex.: `loja_core_zig`, `sensor_gateway_zig`, `loja_front`.

- **`<projeto>_ops` (control plane de desenvolvimento):** todo sistema multi-repo tem um repo **`<projeto>_ops`** — a ferramenta de operação do workspace, rodada por dev/agente e **fora do runtime do produto**. Faz bootstrap/instalação, update, manutenção, troubleshooting e roda os testes unitários/debug **através de todos os repos** (clona, sobe/para, migra, semeia e testa cada serviço; para o Zig, invoca `zig build`, `zig build test` e o binário resultante). Não é microserviço nem é deployado com o produto; é essencial pra tocar um sistema de múltiplos repositórios. Como toda ferramenta, sobe com **observabilidade integrada** (Grafana/LGTM+, ver `references/observabilidade.md` §16).

## 3. Linguagens

A casa **não tem "a linguagem única"**; tem **o rol sancionado** e um **guia de fit**. Os pisos — segurança, testes, IAM, ops, observabilidade, archive — são **os mesmos em toda linguagem** (`references/anti-padroes.md`, `references/seguranca.md`). A linguagem muda o **como**, não o **o quê**. **Esta skill é a especialização Zig do rol** — leia-a quando o fit mandar escolher Zig (controle manual de memória, interop com C, artefato pequeno).

**Backend (serviço novo) — escolha UMA do rol, com ADR (§27) justificando o fit:**

| Linguagem | Skill | Sufixo de repo | Fit — quando escolher |
|---|---|---|---|
| **Go** | `schematize-go` | `_go` | Serviços de rede/API concorrentes, CLIs, tooling. **Default pragmático.** |
| **Rust** | `schematize-rust` | `_rs` | Correção/segurança de memória crítica, auth, cripto, parsing hostil. **Default quando errar é caro.** |
| **Elixir** | `schematize-elixir` | `_ex` | Realtime, alta concorrência tolerante a falha (BEAM/OTP), pub-sub. |
| **C#** (.NET) | `schematize-csharp` | `_cs` | Ecossistema .NET/enterprise, integração Microsoft, ASP.NET/EF Core. |
| **Zig** | `schematize-zig` | `_zig` | **Baixo nível e performance máxima, controle explícito de memória, embedded, interop com C, artefatos pequenos, tooling de sistema.** |
| **Ruby** | `schematize-ruby` | `_rb` | Prototipagem rápida, scripts/automação, DX de produto (Rails), legado Ruby. |

**Frontend — Node (Next.js principal; Astro e outros consolidados), governado por `schematize-web`. É só frontend** — o server-side do próprio front (route handlers, server actions, BFF) faz parte do frontend e é regido pelo §13.4 e §38 (segredo só server-side). Isso **não** reabre Node como linguagem de serviço backend.

**Fit do Zig (por que esta skill existe):** escolha Zig quando precisar de **controle manual de memória** com allocators explícitos, **interop com C** de primeira classe (`@cImport`), **artefato pequeno** e sem runtime pesado, embedded, ou tooling de sistema. Zig entrega **sem GC e sem controle de fluxo oculto** — nenhuma alocação escondida, nenhum destrutor implícito. Onde Go dá um binário estático com goroutines e Rust dá segurança de memória por borrow-checker, **Zig dá controle e transparência total ao custo de você gerenciar a memória à mão** — o que exige a disciplina de `references/memoria-concorrencia.md` e `references/anti-padroes.md` (§37).

- **Serviço backend novo só em linguagem do rol** (Go, Rust, Elixir, C#, Zig, Ruby), com ADR (§27) registrando o fit. Fora do rol exige **ADR de exceção** aprovado.

- Versão exata do compilador Zig em uso fica no Anexo A / `references/stack-versoes.md` (Zig é pre-1.0 — breaking entre versões; fixar a versão é piso).

- **Regra de fit:** auth/cripto pede **Rust**; gateway realtime pede **Elixir**; job de rede simples pede **Go**; utilitário de sistema / interop C / artefato pequeno pede **Zig**; integração .NET pede **C#**; script/protótipo pede **Ruby**. **Empatou?** Use o **default pragmático (Go)** e registre o porquê no ADR — não puxe Zig por gosto.

- Frameworks são bem-vindos; abstrações mágicas não. Critério: consigo entender o stack trace? (Em Zig, `comptime` é força, não desculpa pra metaprogramação ilegível — ver `anti-padroes.md`.)

### 3.1 Node legado (backend) — migração para o rol

Node como linguagem de **serviço backend** está em saída (fora do rol). Tudo que existe em Node backend será migrado para uma linguagem do rol, guiado por esforço (não big-bang) e medido **por funcionalidade do módulo**, não por linha.

- **Gatilho de extração (~30%):** quando uma mudança atingir ~30% das funcionalidades do módulo (alteradas + novas), **não cresça o Node** — extraia essa(s) funcionalidade(s) para um **módulo à parte na linguagem de fit do rol** e incorpore o comportamento Node nessa nova base.

- **Extração incremental:** conforme se mexe no módulo Node ao longo do tempo, vai-se extraindo aos poucos.

- **Virada dos 50%:** quando ~50% do módulo já estiver extraído/inutilizado (substituído pela nova versão), **migra-se os 50% restantes de uma vez** — encerra o módulo Node.

### 3.2 PHP — proibido

- Projeto existente em PHP é **migrado sumariamente** para uma linguagem do rol (backend) — prioridade de migração, com ADR e plano. Não é "quando der"; é dívida ativa a ser zerada.

## 4. Arquitetura

- Domínio não importa frameworks, drivers de banco nem `@cImport` de bibliotecas externas.

- Arquitetura hexagonal (ports & adapters). Em Zig, os "ports" são structs de função/interface (vtable ou comptime) definidos no domínio; os adapters vivem em `infrastructure/`.

### Anti-Corruption Layer

**MUST** em integrações com sistemas externos: adapter dedicado em `infrastructure/external/` que traduz o modelo externo para o modelo de domínio. **Nunca** expor DTOs externos diretamente no domínio. Isto vale em dobro para **interop com C** (`@cImport`): o tipo `[*c]u8`, ponteiros e structs C **não cruzam** o boundary do domínio — o adapter valida e converte para tipos Zig seguros (ver `references/anti-padroes.md`).

### 4.X DDD híbrido durante transição

- Ao mover/quebrar arquivo legado, organize já em folders DDD mesmo que internamente algum módulo ainda misture responsabilidades (ex.: um `application/` ainda chamando SQL direto). Estrutura primeiro, inversão depois.

- Manter teste de cobertura por camada (ver a `schematize-qa`) durante a transição — domain começa com 0%, sobe a cada PR.

- Guard test (em `zig build test`) que **rejeita imports proibidos** logo que possível (mesmo com whitelist de exceções legadas):
  - `domain/` não importa drivers de banco, `@cImport`, `infrastructure/*`, `application/*`, `interface/*`.
  - `application/` não importa `interface/*`.

## 5. Estrutura de Pastas

O layout DDD é **genérico** (agnóstico de linguagem); o que muda no Zig é a raiz de build (`build.zig` + `build.zig.zon`) e o entrypoint.

### Layout genérico (DDD — vale para todas as linguagens)

```
domain/           # entities, value-objects, services, events, repositories (interfaces/ports)
application/      # use-cases, dto, commands, queries
infrastructure/   # persistence, messaging, external (@cImport), observability
interface/        # http, grpc, cli
shared/
config/
```

### Zig

```
src/
├── main.zig          # entrypoint; monta a composição (wiring) das camadas
├── domain/           # entidades, value-objects, ports (structs de função / vtables)
├── application/      # use-cases, commands, queries
├── infrastructure/   # persistência, mensageria, external/ (@cImport), observabilidade
├── interface/        # http, grpc, cli
├── shared/
└── config/
build.zig            # build declarativo; `zig build`, `zig build test`, steps de release
build.zig.zon        # manifesto de dependências (nome, versão, URL + hash de integridade)
tests/               # testes de integração (unitários ficam junto do código, em blocos `test`)
```

- Build por **`zig build`** dirigido pelo **`build.zig`** — nada de scripts shell soltos compilando `.zig` na mão (o build declarativo é a fonte única de steps, flags e modo de release).

- **Dependências declaradas em `build.zig.zon`** com **hash de integridade** por dependência. Sem hash = sem dependência (cadeia de suprimentos, `references/cadeia-suprimentos.md`). Pin exato da versão do compilador em `references/stack-versoes.md`.

- Testes unitários em blocos `test "..."` junto do código que exercitam; testes de integração em `tests/`. Ambos rodam por `zig build test` — ver a `schematize-qa`.

## 6. Complexidade e Tamanho

> **Canônico em `references/padroes-codigo.md`** (arquivo ≤ 750 linhas — ~500 de código útil + ~250 de comentário; flag em > 300 úteis; uma função/unidade por arquivo; doc-comment obrigatório com motivo/comportamento/entradas/saídas/efeitos; e `MAPA.md`). Esta seção é o recorte de arquitetura desses pisos — não duplica a regra, contextualiza.

**MUST — arquivos pequenos, micro-funções**

- **Teto duro: ≤ 750 linhas/arquivo** (~250 de comentário + até ~500 de código útil). Acima disso, o arquivo **deve ser quebrado** — extraia responsabilidades em módulos menores e a lógica em **micro-funções** com nome que explica a intenção. Não existe "arquivo de 1200 linhas porque é coeso": coesão real cabe em arquivos pequenos colaborando.

- **Flag em > 300 linhas de código útil** (não bloqueia, mas **sempre sinaliza**): passou de 300 úteis (ou ~400 em observabilidade), é **indício** de função muito extensa / falta de abstração — registre como dívida e **revise quando as prioridades forem resolvidas**. Bloco `comptime` denso conta como código útil e é forte candidato a flag.

- **Funções pequenas e de responsabilidade única.** Ideal ≤ 50 linhas; função grande vira micro-funções compostas. Use case: uma responsabilidade.

- Exceções (não disparam quebra): testes, migrations, código gerado (`translate-c`), schemas/fixtures.

**MUST — toda função documentada**

- **TODA função pública tem doc-comment `///`** (o formato de doc do Zig, extraído pelo autodoc). O comentário declara, no mínimo:
  - **O quê** — o que a função faz, em uma linha.
  - **Onde é usada / prevista** — quem chama, em que fluxo/camada ela foi pensada pra servir (ex.: "usado pelo use-case `CreateOrder`", "handler HTTP de `/v1/checkout`"). Isto dá contexto explícito de propósito e evita função órfã.
  - **Parâmetros, retorno e efeitos colaterais** — incluindo, em Zig, **quem é dono da memória**: qual `Allocator` a função usa, o que ela aloca, e de quem é a responsabilidade de liberar (o chamador com `defer`? a própria função com `errdefer` no caminho de erro?). Ownership implícito é bug futuro.

- Esse comentário é a **fonte do índice de microfunções** (§39) — escreva pensando que ele será extraído e indexado, não como enfeite.

Convenção mínima (Zig `///`):

```zig
/// O quê:      valida o payload de checkout e cria o pedido.
/// Onde:       use-case CreateOrder; chamado pelo handler POST /v1/checkout.
/// Memória:    aloca o Order em `alloc`; chamador é dono e deve liberar (errdefer no caminho de erro).
/// Efeitos:    persiste em orders, publica catalog.order.created via outbox.
fn createOrder(alloc: std.mem.Allocator, payload: CheckoutPayload) !*Order { ... }
```

**Bloqueio rígido em CI**

- Arquivo de produção > 750 linhas (ou > ~500 de código útil) sem quebra (exceto as exceções acima) → bloqueia; > 300 úteis (~400 obs) → flag registrado.

- Função pública de produção sem doc-comment `///` → bloqueia.

- Complexidade ciclomática > 15 em função de produção.

- Aninhamento > 4 níveis.

> Linha de código é proxy ruim para complexidade — complexidade ciclomática é a métrica honesta. Mas arquivo gigante e função sem contexto (ou sem contrato de memória) são dívidas óbvias: quebre e documente antes do merge.

## 7. Dependências Internas e Shared Libraries

- Dependência externa (módulo Zig ou biblioteca C via `@cImport`) entra por `build.zig.zon` com **hash fixo** e versão pinada; nada de puxar `HEAD` de repositório.

## 8. CQRS e Padrões de Aplicação

- **Commands**: alteram estado, retornam id ou void (`!void` / `!Id`, com o erro propagado por `try`).
