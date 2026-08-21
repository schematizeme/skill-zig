# Memória e Concorrência (Zig)

> Parte da skill **schematize-zig**. Em Zig **não há garbage collector**: a memória é
> gerenciada à mão, por **allocators** passados explicitamente. Os erros mais caros de
> um sistema Zig não são de compilação — são de runtime: **vazamento**, **use-after-free**,
> **double-free**, **corrupção por cancelamento/concorrência**. Esta reference é o piso
> de memória e concorrência. Liga com `references/seguranca.md` (build mode, overflow,
> input hostil), `references/testes.md` (leak gate) e `references/stack-versoes.md`.

## Índice
- M1. Allocators — sempre explícito, nunca oculto
- M2. Ownership e o par alloc/free (`defer`/`errdefer`)
- M3. Leak detection é piso (testar com o allocator certo)
- M4. Build mode e segurança de memória
- M5. Concorrência — threads e o estado compartilhado
- M6. Async em Zig — seja honesto (em evolução)
- M7. Cancelamento, shutdown e não perder dado

---

## M1. Allocators — sempre explícito, nunca oculto

Em Zig, **quem aloca recebe um `std.mem.Allocator`** por parâmetro. Não existe "new"
mágico: a alocação é sempre visível na assinatura e no fluxo.

**MUST**
- **Funções que alocam recebem o `Allocator` por parâmetro** — assinatura idiomática
  `pub fn f(alloc: std.mem.Allocator, ...) !T`. O `Allocator` é **injetado**, nunca
  um global escondido. Isso deixa o chamador dono da política de memória (arena por
  requisição, pool, buffer fixo).
- **Escolha o allocator pelo caso:**
  - **`DebugAllocator` (o antigo `GeneralPurposeAllocator`, renomeado no 0.16)** — de propósito geral em debug/dev, com
    **detecção de leak e de double-free**. Padrão em binário de longa duração.
  - **`ArenaAllocator`** — alocações de vida curta e mesmo escopo (uma requisição, um
    parse) liberadas **todas de uma vez** (`arena.deinit()`). Reduz o risco de free
    esquecido e é rápido. Ótimo por-requisição.
  - **`FixedBufferAllocator`** — buffer de tamanho fixo na stack/estático; zero heap,
    determinístico. Bom em caminho quente / embedded / limite rígido.
  - **`std.heap.page_allocator`** — cru, sem checagem; evite como padrão de app.
  - **`std.heap.c_allocator`** — quando integra com C (`@cImport`) e a memória cruza a
    fronteira; case-a-case (`references/seguranca.md`).
- **Alocação guiada por input externo é limitada.** Nunca aloque `n` bytes onde `n`
  vem do atacante sem teto — é OOM/DoS. Valide o tamanho antes (liga com
  `references/seguranca.md`, parse defensivo).

**VETADO**
- **Allocator global escondido** para "não ter que passar" — quebra a disciplina de
  posse e a testabilidade (não dá pra trocar por um leak-checking allocator no teste).
- Misturar allocators no ciclo de vida de um objeto (alocar com um, liberar com outro).

## M2. Ownership e o par alloc/free (`defer`/`errdefer`)

A regra de ouro: **todo `alloc` tem um `free` casado, e o dono está declarado.**

**MUST**
- **Todo recurso alocado tem caminho de liberação garantido** no mesmo escopo lógico:
  `const buf = try alloc.alloc(u8, n); defer alloc.free(buf);`. O `defer` roda na saída
  do escopo — sucesso ou erro.
- **`errdefer` no caminho de erro:** quando a função pode falhar **depois** de alocar e
  **antes** de transferir a posse ao chamador, use `errdefer alloc.free(x)` — libera só
  se a função retornar erro, e não libera no sucesso (aí a posse foi entregue).
- **A posse é explícita e documentada.** O doc-comment `///` (§3, `references/padroes-codigo.md`)
  declara, para cada função que aloca ou recebe memória: **quem é o dono do buffer
  retornado** (o chamador deve liberar? com qual allocator?), e se a função **toma posse**
  do slice recebido (`take`) ou apenas **empresta** (`borrow`, não libera). Ninguém deve
  precisar ler o corpo pra saber quem libera.
- **`deinit()` para tipos que possuem memória.** Struct que segura buffers/coleções
  expõe `deinit(self)` que libera tudo; o dono chama `defer x.deinit()`.

**VETADO**
- `alloc` sem `free`/`defer`/`errdefer` casado — é vazamento.
- Liberar duas vezes (double-free) ou usar depois de liberar (use-after-free). Em
  Debug/ReleaseSafe o runtime pega muitos desses; não conte com a sorte — teste (M3).
- Retornar ponteiro/slice pra memória de escopo que já saiu (stack) — dangling.

## M3. Leak detection é piso (testar com o allocator certo)

Provar **ausência de vazamento** é obrigatório, não opcional.

**MUST**
- **Todo teste que aloca usa `std.testing.allocator`** — ele **falha o teste** se sobrar
  memória ao final. Um `test` que aloca e passa com o testing allocator é prova de que o
  par alloc/free está correto naquele caminho. Detalhe em `references/testes.md` (o recorte Zig) — a **disciplina** de teste é da `schematize-qa`, e a segurança ofensiva da `schematize-pentest`.
- **Binário de longa duração usa `DebugAllocator`** (✔ 0.16.0; era `GeneralPurposeAllocator`) com `defer
  std.debug.assert(gpa.deinit() == .ok)` (ou log do relatório de leak) em debug — o
  `deinit()` do GPA **reporta leaks e double-frees**. Vazamento detectado é bug de
  entrega, entra na DoD (`references/entrega.md` §35).
- **Exercite o caminho de erro na alocação:** teste também o ramo em que a alocação
  falha (`error.OutOfMemory`) — com `std.testing.checkAllAllocationFailures` ou um
  `FailingAllocator` — pra provar que o `errdefer` limpa e não vaza no erro.

**VETADO**
- Rodar a suíte com um allocator que **não** detecta leak "porque é mais simples". Sem
  o leak gate, o verde é mentiroso (liga com `references/testes.md`, "verde de verdade").

## M4. Build mode e segurança de memória

O modo de build **muda as garantias de memória** — é decisão de segurança, não de perf só.

- **`Debug`** — todas as checagens (bounds, overflow de inteiro trapa, undefined em
  `0xaa`, detecção de UB). Padrão de desenvolvimento e teste.
- **`ReleaseSafe`** — **mantém** bounds check e trap de overflow, otimizado. **É o piso
  de produção** para serviço exposto a input hostil (`references/seguranca.md`): sem GC e
  com as checagens, é rápido e defensável.
- **`ReleaseFast` / `ReleaseSmall`** — **removem** as checagens → use-after-free e OOB
  viram **UB explorável**. Só com **profiling** que prove o ganho necessário e **ADR**
  (§27); nunca o default de um serviço de borda.

**Piso:** produção em `ReleaseSafe` salvo ADR + perfil. Overflow de inteiro é **explícito**
em Zig (`+%` faz wrap; `+` trapa) — em cálculo de tamanho/índice a partir de input
externo, trate o overflow, nunca confie no wrap silencioso.

## M5. Concorrência — threads e o estado compartilhado

**MUST**
- **Threads via `std.Thread`;** cada thread com seu escopo de memória claro. Estado
  compartilhado entre threads é protegido — **`std.Thread.Mutex`** (seção crítica curta),
  **`std.Thread.RwLock`** (muita leitura), ou operações **atômicas** (`@atomicRmw`,
  `@atomicLoad`/`@atomicStore`) para contadores/flags.
  > ✔ **Verificado em 2026-08-21:** na `std` da linha estável atual o mutex é **`std.Io.Mutex`** — `std.Thread.Mutex`
  > **não existe mais**. E `lock` recebe um `Io`; para estado compartilhado simples entre threads,
  > prefira **`std.atomic.Value(T)`** com `fetchAdd`/`cmpxchg`, que não depende do runtime de I/O.
  > *(Zig é pre-1.0: a `std` quebra entre minors. A versão exata vive em
  > `references/stack-versoes.md`, com data de verificação.)*

- **Seção crítica curta:** pegue o lock, mute/copie o necessário, **solte** — não segure
  o lock através de I/O ou trabalho pesado.
- **Ordem de aquisição de locks consistente** (evita deadlock A→B / B→A).
- **Prefira passar mensagem a compartilhar memória** quando a contenção aparecer: uma
  fila (canal) e uma thread dona do estado costuma ser mais simples e correto que um
  `Mutex` global disputado.
- **Filas/buffers são limitados** (bounded): produtor mais rápido que consumidor
  **aguarda** (backpressure), não acumula memória sem teto. Política de cheio explícita
  (aguardar / descartar com métrica / rejeitar), nunca acidental.

**VETADO**
- Data race — acessar memória compartilhada mutável sem lock/atômico. Em Zig o
  compilador **não** te salva disso; a disciplina é sua.
- `Mutex` global virando ponto único de contenção sem necessidade.

## M6. Async em Zig — seja honesto (em evolução)

O **modelo async do Zig está em transição**. A sintaxe `async`/`await`/`suspend` de
versões antigas foi **removida/reformulada**, e o desenho de I/O assíncrono na `std`
segue evoluindo entre releases (mais um motivo pra fixar a versão do compilador —
`references/stack-versoes.md`). **Não finja que há um runtime async estável e maduro
como Tokio.**

**MUST**
- **Escolha o modelo de concorrência conscientemente e registre no ADR:** para a maioria
  dos serviços, **threads (`std.Thread`) + pool + filas limitadas** é o caminho estável e
  previsível hoje. Event loop / I/O não-bloqueante entram quando o perfil de carga
  justifica e a API disponível na versão fixada suporta.
- **Se usar o async/event-loop da versão corrente,** encapsule-o atrás de uma fronteira
  clara (o resto do código não depende dos detalhes que podem mudar na próxima versão) e
  cubra com teste.
- **Timeout em operação longa** — nada espera pra sempre; toda espera de I/O/rede tem
  teto e caminho de cancelamento.

**SHOULD**
- Documentar, no ADR e no MAPA, qual modelo de concorrência o serviço usa e por quê — é
  informação que muda com a versão do Zig.

## M7. Cancelamento, shutdown e não perder dado

**MUST**
- **Cancelamento não deixa invariante quebrada.** Se uma operação é interrompida
  (timeout, shutdown, cliente desconectou) no meio, o estado parcial (buffer semi-escrito,
  lock adquirido, alocação pendente) é limpo — `defer`/`errdefer` e commit atômico/
  transação garantem isso. Recurso adquirido é sempre liberado no caminho de interrupção.
- **Graceful shutdown:** ao receber SIGTERM, pare de aceitar trabalho novo, sinalize as
  threads/loops, **drene** o que está em voo com timeout, libere memória (allocators
  `deinit`) e feche conexões/flush de buffers ordenadamente (liga com
  `references/operacao.md`).
- **Independência de runtime + não perder dado (piso da casa, `references/dados-eventos.md`
  §18):** falha ao chamar/notificar outro serviço → **persiste o dado** (outbox/DB),
  **loga com `trace_id`**, **alerta** e **retoma**; nunca perde nem trava a cadeia. A
  queda de outro serviço **nunca** impede o boot nem derruba este — degradação graciosa.

**SHOULD**
- Instrumentar spans/log por thread/requisição (com `trace_id`) pra observar a
  concorrência real (liga com `references/observabilidade.md`).

> Regra de bolso Zig: **todo `alloc` tem um `free` casado e um dono declarado; todo teste
> roda no allocator que detecta leak; produção é `ReleaseSafe`; e o modelo de concorrência
> é uma escolha registrada — não um runtime mágico.** O compilador não tem GC nem
> borrow-checker: a corretude de memória é responsabilidade sua, provada por teste.
