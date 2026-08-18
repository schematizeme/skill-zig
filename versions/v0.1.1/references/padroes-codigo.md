# Padrões de Código — limites, granularidade, comentários e MAPA

Piso normativo de **organização do código** para a skill **schematize-zig**
(backend/sistemas em Zig, com auxiliares em C quando inevitável). É inegociável:
vale para código humano e gerado por IA. O gate `/zig-review` (DoD) reprova o que
violar isto. Os limites de tamanho, granularidade e MAPA são **agnósticos de
linguagem** — idênticos ao resto da casa; o que se especializa aqui é o formato do
doc-comment (`///` / `//!`), a **disciplina de memória** e a formatação canônica.

## 1. Tamanho de arquivo — teto de 750 linhas (≤ 500 de código útil + ~250 de comentário)

Regra **em camadas**: um teto duro generoso e um **flag** mais cedo que sinaliza
cheiro de função extensa. A ideia é dar espaço pra código bem documentado sem
soltar a mão da granularidade.

- **Teto DURO: 750 linhas por arquivo de código** (sem contar `@import`/licença no
  topo). Desse orçamento, **~250 linhas são reservadas a comentário/doc-comment**
  (§3) e **até ~500 são código útil**. Passou de **750 no total** — ou de **~500 de
  código útil** — → **quebre em mais de um arquivo**, por coesão (uma
  responsabilidade por arquivo), nunca por corte arbitrário no meio de uma função.
  O gate `check-diff` **BLOQUEIA** acima do teto.
- **FLAG em > 300 linhas de código útil** (não bloqueia, mas **sempre sinaliza**):
  se o **código útil** de um arquivo — descontando comentário e linha em branco —
  passar de **300 linhas**, isso é **indício** de que a função/arquivo está **muito
  extensa** e provavelmente **pode ser melhorada ou precisa de um nível de abstração
  maior**. Não trava a entrega; o gate **flagueia sempre** e o ponto entra como
  **dívida técnica pra rever quando as prioridades forem resolvidas** (registre no
  archive/ADR). **Nunca engula o flag** — sinalizar é obrigatório, ignorar não é.
- **Observabilidade tem folga natural (~400 úteis):** arquivos dominados por
  instrumentação (tracing, métricas, logging estruturado) incham por natureza —
  olhando de fora, ~400 linhas úteis é esperado. Pra esses, o flag só é significativo
  acima de **~400** de código útil (ainda assim registrado). O teto duro de 750/500
  continua valendo igual.
- **Escopo: código-fonte.** Vale para arquivo de código em qualquer linguagem
  (Zig `.zig`, C `.c`/`.h` de FFI, shell, `build.zig`). **Fora do escopo** (não
  disparam o gate): documentação e Markdown (references, README, ADR, archive,
  MAPA), config, lockfiles/snapshots gerados e fixtures — esses seguem bom senso de
  tamanho, mas o gate mede **código**, não texto. O CI afere arquivos de código.
- Quebrou um arquivo? Atualize o **MAPA** (§4) no mesmo PR.

## 2. Uma função por arquivo (lógica)

- A regra é **uma função pública / "unidade lógica" por arquivo**. O arquivo existe
  para entregar aquela função; auxiliares privadas pequenas da mesma unidade (helpers
  `fn` sem `pub`) podem conviver, desde que sirvam só a ela e o arquivo siga o teto
  (§1: ≤ 750 linhas, ≤ ~500 de código útil). Um `struct` com seus métodos que formam
  **um** conceito coeso (ex.: um `Parser`, um `Pool`) conta como uma unidade lógica.
- **Função com > 300 linhas de código útil dispara o flag** (§1) — indício de
  extensão excessiva / falta de abstração: quebre em sub-funções nomeadas com
  propósito único e mova-as para seus arquivos quando puder. Se não for a prioridade
  agora, **flagueia e revisita depois**; o teto duro do arquivo continua 750/500.
- Sem "arquivo balaio" (`utils.zig`, `helpers.zig`, `common.zig`) que acumula funções
  sem relação. Nome do arquivo = o que ele faz. `comptime` gigante que gera dezenas
  de declarações também conta pro flag — metaprogramação não é desculpa pra esconder
  extensão.

## 3. Tudo comentado: doc-comment `///` + disciplina de memória

Em Zig, o doc-comment é **`///` sobre a declaração** (`pub fn`, `pub const`, `pub
var`, `struct`/`enum`/`union` e seus campos) e **`//!` no topo do arquivo/módulo**
para descrever a unidade inteira. Comentário comum (`//`) **não** é doc-comment e
**não** alimenta o índice.

**TODA função relevante — pública e privada — carrega doc-comment `///`** que
responde, no mínimo:

- **Por quê existe** — o problema que resolve / a decisão que encapsula.
- **Como se espera que funcione** — o passo-a-passo em uma frase, pré-condições e
  invariantes (inclusive as garantidas por `comptime`).
- **Entradas** — cada parâmetro: o que é, faixa/validação esperada. **Inclui o
  `std.mem.Allocator`**: diga o que é alocado com ele e por quanto tempo vive.
- **Saídas** — o retorno e seu significado. Se a assinatura é um **error union**
  `!T`, **liste cada erro possível do error set e quando ocorre** (campo "Erros:").
  Retorno `?T` (optional): diga o que significa `null`.
- **Efeitos colaterais** — I/O, rede, syscall, mutação de parâmetro `*T`, estado
  global, alocação.
- **Fluxo do dado (começo → meio → fim)** — **de onde vem** (origem/serviço/fila/
  tabela; se vem de **outra aplicação**, nomeie qual e o contrato/evento), **o que é
  feito** (transformação/decisão), e **pra onde vai** (destino: serviço/tópico/
  tabela/resposta). Toda função que **cruza fronteira de aplicação** diz isso
  explícito — ninguém, humano ou agente, deve caçar no código a origem e o destino.

### 3.1 Disciplina de memória é obrigatória no doc-comment (piso do Zig)

Zig não tem GC nem RAII: a posse da memória é **manual e explícita**, e o
doc-comment é onde esse contrato vive. Toda função que aloca, libera ou recebe um
buffer/slice **DEVE** declarar um campo **"Memória:"** respondendo:

- **Quem aloca** — a função aloca internamente com o `Allocator` recebido? Devolve
  algo que **o chamador precisa liberar** (`defer alloc.free(x)` / `x.deinit()`)?
- **Quem libera** — o dono do `free`/`deinit`. Se a função devolve memória, diga
  **com qual allocator** liberar (tem que ser o mesmo que alocou).
- **Posse do parâmetro** — a função **toma posse** (`take ownership`) do slice/buffer
  recebido (passa a ser dona, vai liberar) **ou apenas empresta** (`borrow`: lê/usa
  mas não guarda referência além da chamada, não libera)? Emprestar e guardar a
  referência é bug de lifetime — declare qual é.
- **Tempo de vida** — a referência devolvida vive tão longo quanto qual dono? Aponta
  pra dentro de um buffer do chamador (dangling se ele liberar antes)?

Isso liga com `references/memoria-concorrencia.md` (regras de ownership, `defer`/
`errdefer`, arenas, `GeneralPurposeAllocator` e detecção de leak). **Assinatura
idiomática da casa:** o allocator é o **primeiro** parâmetro e o retorno é error
union:

```zig
//! parse_token.zig — decodifica e valida o token de sessão vindo do gateway.

const std = @import("std");

/// Decodifica um token de sessão opaco em claims tipadas.
///
/// Por quê: o gateway entrega o token cru (bytes do header Authorization); o
///   domínio precisa das claims validadas, não do blob.
/// Comportamento: valida assinatura (HMAC), checa `exp`, decodifica o payload.
///   Pré-condição: `raw` é o valor do header já sem o prefixo "Bearer ".
/// Entradas:
///   - alloc: aloca o buffer das claims decodificadas (dono = chamador, ver Memória).
///   - raw: bytes do token (EMPRESTADO — lido, não guardado, não liberado aqui).
///   - key: chave HMAC (EMPRESTADA — referência não sobrevive à chamada).
/// Saídas: `Claims` alocado; o `sub`/`tenant` apontam pra dentro do buffer do próprio
///   Claims (não pra `raw`).
/// Erros (error set):
///   - error.MalformedToken   → base64/estrutura inválida.
///   - error.SignatureInvalid → HMAC não confere (rejeição de auth, NÃO 500).
///   - error.Expired          → `exp` no passado.
///   - error.OutOfMemory      → allocator sem espaço.
/// Efeitos: nenhum I/O; só alocação via `alloc`.
/// Memória: ALOCA `Claims` com `alloc`; o CHAMADOR é dono e DEVE chamar
///   `claims.deinit(alloc)` (mesmo allocator). NÃO toma posse de `raw` nem de `key`.
/// Fluxo: header do gateway (auth) → validação/decodificação → claims pro domínio.
pub fn parseToken(alloc: std.mem.Allocator, raw: []const u8, key: []const u8) !Claims {
    // ...
}
```

Regras derivadas, inegociáveis:

- Comentário que só repete a assinatura **não conta**. O doc-comment é o contrato:
  quem chama entende a função **sem ler o corpo** — e sabe quem libera a memória.
- Função que devolve memória alocada **sem** declarar o dono do `free`/`deinit` no
  campo "Memória:" é **incompleta** — `/zig-review` reprova.
- Todo error union `!T` tem o campo **"Erros:"** enumerando o error set. Erro de
  auth/tenant/injeção é **rejeição de negócio** (`error.SignatureInvalid`,
  `error.Forbidden`), **nunca** um `unreachable`/`panic` que vira crash.
- `//!` no topo de cada arquivo/módulo resume a unidade e nomeia as fronteiras.

O índice de microfunções (`/zig-index`) é **gerado** desses doc-comments `///` e
**falha o CI** se achar `pub fn` (ou função lógica relevante) sem contexto — em
especial sem o campo **"Memória:"** quando a função mexe com allocator. **Toda
funcionalidade é mapeada** (§4): busca burra que torra token e tempo é sintoma de
mapa incompleto, não de falta de busca.

### 3.2 Formatação canônica trava o CI

- **`zig fmt` é a formatação canônica** e não se discute (sem bikeshed de estilo).
  O CI roda **`zig fmt --check`** e **BLOQUEIA** se algum arquivo não estiver
  formatado (ver `references/testes-execucao.md` §22.6).
- Nomes seguem a convenção do `std`: `TypesAreCamelCase`, `functionsAreCamelCase`,
  `variables_are_snake`, `CONSTANTS` conforme o `std`. Sem inventar dialeto.
- `zig fmt` alinha e organiza, mas **não escreve doc-comment** — o `///` é
  responsabilidade humana/agente e alimenta o `/zig-index`.

## 4. MAPA da aplicação (arquivo-guia obrigatório)

Todo projeto que segue esta skill mantém um **`MAPA.md`** em
**`<projeto>_archive/index/MAPA.md`** (template em `assets/MAPA.md`) — **nunca no
root do projeto**. Todo MD **gerado** (MAPA, índices, planos, relatórios, handoffs)
mora no archive; o root fica limpo (só código, `build.zig`, `build.zig.zon`, config
e os poucos MDs mantidos à mão: README, `CLAUDE.md`, LICENSE). Layout canônico do
archive em `references/operacao.md` (§28). É parte da entrega, atualizado **no mesmo
PR** que mexe no código (o archive é versionado). Ele lista, para **cada** função —
pública e privada, **sem exceção** (uma entrada por função):

- **Onde está** — caminho do arquivo (e símbolo).
- **Para que serve** — propósito em uma linha.
- **Dependências** — o que ela chama (funções/módulos/serviços externos).
- **Auxiliares** — quem a apoia / quem depende dela (chamadores).
- **Entrada e saída** — de onde vêm os dados e para onde vão (args/retorno, rota,
  fila, arquivo, banco).
- **Memória** — quando aplicável, quem aloca / quem libera (espelha o campo "Memória:"
  do doc-comment §3.1), pra medir o raio de impacto de um `free`.

O MAPA tem duas camadas, espelhando o índice de funcionalidades:

- **Global** (mantido à mão): repositórios, pastas, módulos, `build.zig` steps, como
  se comunicam, pontos de entrada (rotas/jobs/CLIs) e de saída (banco/fila/API
  externa).
- **Microfunções** (gerado por `/zig-index` a partir dos doc-comments §3).

O índice de microfunções é **exaustivo e conferível por contagem**: **uma entrada
por função** de **cada** serviço/repo (pública e privada) — o número de entradas
**tem que bater** com o número de funções do código (`nº entradas == nº funções`).
Menos que isso é **falha**, não "resumo": um MAPA de 90 linhas para 100+ funções
está errado. E o MAPA é um **grafo**, não uma lista — traz o **grafo de serviços**
(quem chama/notifica quem, por contrato) e o **grafo de chamadas** por função (quem
chama / é chamada), como **Mermaid + adjacência**, pra percorrer do ponto de entrada
à saída e medir o raio de impacto. Contrato e gate: `references/entrega.md` §39.

Sem MAPA atualizado, o PR não passa na DoD. O objetivo: qualquer pessoa (ou IA)
abre o MAPA e sabe **onde tocar, o que aquilo afeta e por onde entra/sai** antes
de ler o código.

## Checklist (entra na Definition of Done)

- [ ] Nenhum arquivo de código > 750 linhas (nem > ~500 de código útil) — teto duro.
- [ ] Arquivo/função com > 300 linhas de código útil (~400 em observabilidade) **flagueado** e registrado como dívida pra rever (não bloqueia, mas nunca silenciado).
- [ ] Uma função/unidade lógica por arquivo (`struct` coeso conta como uma unidade).
- [ ] Toda função com doc-comment `///` (motivo, comportamento, entradas, saídas, efeitos) e `//!` no topo do módulo.
- [ ] **Campo "Memória:"** presente em toda função que aloca/libera/recebe buffer — quem aloca, quem libera, posse (ownership vs borrow), com qual allocator (liga com `references/memoria-concorrencia.md`).
- [ ] **Campo "Erros:"** enumerando o error set de todo retorno `!T`.
- [ ] `zig fmt --check` passa no CI (formatação canônica).
- [ ] `MAPA.md` atualizado no mesmo PR, em **`<projeto>_archive/index/`** (nunca no root) — camada global à mão + microfunções gerada.
- [ ] Índice de microfunções **exaustivo**: uma entrada por função, `nº entradas == nº funções` do serviço (`/zig-index` **reprova** se faltar e lista as ausentes); nenhuma órfã.
- [ ] **Grafo** presente: serviços (quem chama quem) + chamadas por função (Mermaid + adjacência).
