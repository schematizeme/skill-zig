# Arquitetura, Camadas, Repositórios e Linguagens

> Parte da skill **schematize-zig**. As referências cruzadas (§N) apontam para seções do corpo completo — todas presentes no conjunto de references desta skill.

## Índice
- 2. Estrutura de Repositórios
- 3. Linguagens
- 4. Arquitetura
- 5. Estrutura de Pastas
- 6. Complexidade e Tamanho
- 7. Dependências Internas e Shared Libraries
- 8. CQRS e Padrões de Aplicação

---

## 2. Estrutura de Repositórios

**MUST**
- Um repositório = uma aplicação ou um bounded context.
- Comunicação entre serviços via HTTP, gRPC, eventos ou mensageria — nunca via banco compartilhado.
- Cada serviço é dono do seu schema.
- **Nome do repositório:** `<projeto>_<contexto>[_<lang>]` em snake_case minúsculo. `<projeto>` = slug do produto/organização; `<contexto>` = a aplicação/bounded context daquele repo (`core`, `gateway`, `worker`, `front`, `backoffice`…); `_<lang>` é sufixo pra desambiguar linguagem (`_zig` Zig, `_go` Go, `_rs` Rust, `_ex` Elixir, `_cs` C#, `_rb` Ruby, `_ts` TypeScript). **Nesta skill, o serviço Zig usa o sufixo `_zig`.** Como um repo = um contexto, o nome espelha isso. Ex.: `loja_core_zig`, `sensor_gateway_zig`, `loja_front`.
- **Independência de runtime (cada serviço é entidade à parte):** todo serviço **sobe e opera sozinho**. A indisponibilidade de qualquer outro serviço **nunca** impede o boot nem derruba este — depender de outro serviço para *iniciar/funcionar* é VETADO (nada de "o `ledger` não sobe se o `core` estiver fora"). Dependente ausente vira **degradação graciosa** (fallback, resposta parcial, enfileira e segue), nunca crash em cascata. Como não perder o dado quando a chamada falha: `references/dados-eventos.md` (§18).
- **`<projeto>_ops` (control plane de desenvolvimento):** todo sistema multi-repo tem um repo **`<projeto>_ops`** — a ferramenta de operação do workspace, rodada por dev/agente e **fora do runtime do produto**. Faz bootstrap/instalação, update, manutenção, troubleshooting e roda os testes unitários/debug **através de todos os repos** (clona, sobe/para, migra, semeia e testa cada serviço; para o Zig, invoca `zig build`, `zig build test` e o binário resultante). Não é microserviço nem é deployado com o produto; é essencial pra tocar um sistema de múltiplos repositórios. Como toda ferramenta, sobe com **observabilidade integrada** (Grafana/LGTM+, ver `references/observabilidade.md` §16).
- **Contenção no workspace (nunca sair da pasta do projeto):** o **diretório de projeto atual é o workspace**; toda aplicação/repo do sistema nasce e mora **dentro dele**. Vai criar uma aplicação nova? Crie uma **pasta pra ela dentro da pasta atual** (`./<projeto>_<contexto>/`) e trabalhe lá — **nunca** largue arquivos soltos no root pra depois **subir de diretório** (`cd ..`, `../`) e criar os outros repos fora. Num sistema multi-repo os repos são **irmãos dentro do mesmo workspace** (clonados ali pelo `<projeto>_ops`), não espalhados pela máquina. **VETADO** criar/ler/escrever fora do workspace: diretório-pai, `~`, `~/Documents`, `~/Downloads`, `/tmp` do usuário, Área de Trabalho. O agente **não sai da pasta do projeto** — nem pra vasculhar, nem pra criar — a menos que o usuário peça explicitamente.

**VETADO**
- **Aplicação monolítica que acopla múltiplos bounded contexts num só deploy/processo.** Não se cogita "começar monolito e quebrar depois" sem ADR explícito de plano e prazo de quebra. Misturar domínios de negócio "pra entregar rápido" é dívida disfarçada de produtividade.
- **Monólito distribuído** — o pior dos dois mundos: serviços separados fisicamente, mas acoplados por banco compartilhado, shared lib de domínio (§7) ou chamadas síncronas em cascata sem fronteira. Tão proibido quanto o monólito clássico.
- **Big ball of mud** — código sem fronteira de contexto, onde tudo importa tudo.

**SHOULD**
- Evitar mais de um domínio de negócio no mesmo repositório.
- Leitura cross-service por réplica read-only só com ADR e contrato documentado.

**MAY**
- *Modular monolith* (módulos com fronteira de contexto rígida, schema separado, comunicação por interface interna) **somente com ADR** que justifique estágio do produto e contenha o plano de extração. É exceção registrada, não default. Nunca usar como atalho para colar domínios.

> Não existe "MVP monolítico que vira microserviço depois" sem o ADR que prova que o depois tem data. Sem isso, "depois" é "nunca", e "nunca" é um big ball of mud em produção.

---

---

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

**MUST**
- **Serviço backend novo só em linguagem do rol** (Go, Rust, Elixir, C#, Zig, Ruby), com ADR (§27) registrando o fit. Fora do rol exige **ADR de exceção** aprovado.
- Versão exata do compilador Zig em uso fica no Anexo A / `references/stack-versoes.md` (Zig é pre-1.0 — breaking entre versões; fixar a versão é piso).
- Não misturar linguagens dentro do **mesmo bounded context** sem ADR.

**SHOULD**
- **Regra de fit:** auth/cripto pede **Rust**; gateway realtime pede **Elixir**; job de rede simples pede **Go**; utilitário de sistema / interop C / artefato pequeno pede **Zig**; integração .NET pede **C#**; script/protótipo pede **Ruby**. **Empatou?** Use o **default pragmático (Go)** e registre o porquê no ADR — não puxe Zig por gosto.
- Frameworks são bem-vindos; abstrações mágicas não. Critério: consigo entender o stack trace? (Em Zig, `comptime` é força, não desculpa pra metaprogramação ilegível — ver `anti-padroes.md`.)

### 3.1 Node legado (backend) — migração para o rol

Node como linguagem de **serviço backend** está em saída (fora do rol). Tudo que existe em Node backend será migrado para uma linguagem do rol, guiado por esforço (não big-bang) e medido **por funcionalidade do módulo**, não por linha.

**Modelo da métrica.** Um módulo tem N funcionalidades (ex.: 10 — cálculo, ABAC, CRUD, etc.). O quanto uma mudança "pesa" é a fração de funcionalidades que ela altera ou cria sobre o total do módulo. Ex.: módulo com 10 funcionalidades — refatorar 2 = 20%; refatorar 3 (ou criar ~4 novas) ≈ 30%.

**MUST**
- **Não mexer no que está feito em Node, a menos que solicitado.** Node backend funcionando fica como está até ser tocado.
- **Gatilho de extração (~30%):** quando uma mudança atingir ~30% das funcionalidades do módulo (alteradas + novas), **não cresça o Node** — extraia essa(s) funcionalidade(s) para um **módulo à parte na linguagem de fit do rol** e incorpore o comportamento Node nessa nova base.
- **Extração incremental:** conforme se mexe no módulo Node ao longo do tempo, vai-se extraindo aos poucos.
- **Virada dos 50%:** quando ~50% do módulo já estiver extraído/inutilizado (substituído pela nova versão), **migra-se os 50% restantes de uma vez** — encerra o módulo Node.
- **Ajuste pontual não porta.** Mudança pequena/localizada (abaixo do gatilho) é feita no próprio Node, sem portabilidade.
- Toda migração registra ADR (§27) e segue o DDD híbrido/coexistência (§4.X, §36): flag de coexistência, sem big-bang.

> Os percentuais (~30% pra extrair, ~50% pra finalizar) são os limiares da casa; ajuste por ADR se um módulo específico exigir. A regra é: parou de ser ajuste pontual, vira extração; passou da metade, termina.

### 3.2 PHP — proibido

**VETADO** — PHP não é linguagem da casa, em nenhuma camada.

- Nenhum código novo em PHP.
- Projeto existente em PHP é **migrado sumariamente** para uma linguagem do rol (backend) — prioridade de migração, com ADR e plano. Não é "quando der"; é dívida ativa a ser zerada.

---

---

## 4. Arquitetura

**MUST — todos os projetos**
- Separação explícita de camadas: `domain`, `application`, `infrastructure`, `interface`.
- Inversão de dependência: domínio não conhece infra.
- Domínio não importa frameworks, drivers de banco nem `@cImport` de bibliotecas externas.

**SHOULD — projetos com regra de negócio relevante**
- DDD tático (agregados, value objects, eventos de domínio).
- Arquitetura hexagonal (ports & adapters). Em Zig, os "ports" são structs de função/interface (vtable ou comptime) definidos no domínio; os adapters vivem em `infrastructure/`.

**MAY — CRUDs simples**
- Manter as 4 camadas, dispensar táticas DDD pesadas.

### Dependências permitidas

```
interface       → application
application     → domain
infrastructure  → domain, application
```

### Dependências proibidas

```
domain          → qualquer outra camada
domain          → frameworks, driver de banco, @cImport, libs de IO
application     → interface
```

### Anti-Corruption Layer

**MUST** em integrações com sistemas externos: adapter dedicado em `infrastructure/external/` que traduz o modelo externo para o modelo de domínio. **Nunca** expor DTOs externos diretamente no domínio. Isto vale em dobro para **interop com C** (`@cImport`): o tipo `[*c]u8`, ponteiros e structs C **não cruzam** o boundary do domínio — o adapter valida e converte para tipos Zig seguros (ver `references/anti-padroes.md`).

### 4.X DDD híbrido durante transição

Projetos legados onde código já existe sem separação de camadas **podem** adotar DDD progressivamente em vez de big-bang. Regras:

**MUST**
- Toda nova feature/refactor em código tocado segue o layout completo (`domain/`, `application/`, `infrastructure/`, `interface/`) — não introduzir mais código "flat".
- Ao mover/quebrar arquivo legado, organize já em folders DDD mesmo que internamente algum módulo ainda misture responsabilidades (ex.: um `application/` ainda chamando SQL direto). Estrutura primeiro, inversão depois.
- Cada PR que toca arquivo híbrido **deve** mover ao menos um pedaço pra direção certa (ex.: extrair entidade pra `domain/`, mover query pra `infrastructure/repositories/`).
- ADR registrando o débito e o plano de remoção: `<projeto>/<projeto>_archive/decisoes/<n>-ddd-migration-<contexto>.md`.

**SHOULD**
- Manter teste de cobertura por camada (ver a `schematize-qa`) durante a transição — domain começa com 0%, sobe a cada PR.
- Guard test (em `zig build test`) que **rejeita imports proibidos** logo que possível (mesmo com whitelist de exceções legadas):
  - `domain/` não importa drivers de banco, `@cImport`, `infrastructure/*`, `application/*`, `interface/*`.
  - `application/` não importa `interface/*`.

**MAY**
- Marcar arquivos híbridos com comment `// @ddd-hybrid` pra busca fácil e cleanup priorizado.

---

---

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

**MUST**
- Build por **`zig build`** dirigido pelo **`build.zig`** — nada de scripts shell soltos compilando `.zig` na mão (o build declarativo é a fonte única de steps, flags e modo de release).
- **Dependências declaradas em `build.zig.zon`** com **hash de integridade** por dependência. Sem hash = sem dependência (cadeia de suprimentos, `references/cadeia-suprimentos.md`). Pin exato da versão do compilador em `references/stack-versoes.md`.
- Testes unitários em blocos `test "..."` junto do código que exercitam; testes de integração em `tests/`. Ambos rodam por `zig build test` — ver a `schematize-qa`.

---

---

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

---

---

## 7. Dependências Internas e Shared Libraries

**MUST**
- Shared libraries são **mínimas** e com escopo claramente delimitado.
- Permitido como shared: observabilidade, autenticação/auth, primitives de infraestrutura, SDKs internos, logging, configuração.
- Dependência externa (módulo Zig ou biblioteca C via `@cImport`) entra por `build.zig.zon` com **hash fixo** e versão pinada; nada de puxar `HEAD` de repositório.

**MUST NOT**
- Criar `commons` / `core-lib` / `platform-utils` genéricos.
- Compartilhar **lógica de domínio** entre bounded contexts.
- Compartilhar entidades de domínio. Cada contexto modela o seu.

> O caminho mais rápido pra um monólito distribuído é uma shared lib chamada `commons`.

**SHOULD**
- Shared libs versionadas com SemVer próprio.
- Breaking changes em shared lib exigem ADR.

---

---

## 8. CQRS e Padrões de Aplicação

- **Commands**: alteram estado, retornam id ou void (`!void` / `!Id`, com o erro propagado por `try`).
- **Queries**: nunca alteram estado, otimizadas para leitura, podem usar projeções.
- CQRS **não exige** event sourcing.

---

---
