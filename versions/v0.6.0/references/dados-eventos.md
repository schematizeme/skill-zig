# Eventos, Banco de Dados, Cache, APIs, Resiliência e Jobs — Zig


> **PONTEIRO, não cópia.** A normativa deste tema é da base: **`schematize-engineering`** →
> `references/dados-eventos.md`. Leia lá primeiro; aqui fica **só o que muda em Zig**.
>
> **Onde este arquivo divergir da base, a BASE MANDA** (`SKILL.md` §"Precedência e herança").
> Em 2026-08-21 os blocos idênticos à base foram **podados mecanicamente** (`tools/podar-clone.mjs`),
> e é por isso que a numeração **salta**: o número é o da base, e o item ausente aqui é o que **não
> muda nesta linguagem** — procure-o lá.

## 9. Eventos e Mensageria

- **Transactional Outbox** para publicação de eventos. Dual-write (banco + broker no
  mesmo fluxo) é **VETADO** (ver §37). Detalhe do piso de não perder dado em §18.

- Consumidores com limites explícitos de concorrência e prefetch — em Zig, as **filas/
  buffers são bounded** e o produtor rápido **aguarda**, não acumula memória sem teto
  (`references/memoria-concorrencia.md` §M5). Backpressure aqui também é defesa de OOM.

**MUST — parse de evento defensivo (Zig)**

- **Todo evento recebido é parseado defensivamente:** **limite de tamanho** do payload
  antes de alocar; **sem alocação ilimitada guiada pelo atacante** (nunca `alloc(n)` com
  `n` vindo do wire sem teto — é OOM/DoS); **allocator explícito** (arena por mensagem,
  liberada de uma vez). Campo desconhecido é ignorado sem estourar. Liga forte com
  `references/seguranca.md` (input hostil) e `references/memoria-concorrencia.md` (§M1).

> NATS e Kafka são padrão. RabbitMQ exige justificativa pelo custo operacional. Client
> nativo Zig de broker é jovem — quando faltar, `@cImport` de um client C maduro
> (ex.: `librdkafka`) com o **boundary validado** (`references/seguranca.md`) é o caminho
> idiomático; é custo, pese no ADR (`references/stack-versoes.md`).

## 10. Banco de Dados

- Migrations versionadas, **reversíveis** (com `down`), automatizadas no deploy. Piso
  mantido — ver §10.1.

- Schema próprio por serviço. O **banco é dono do schema**; o serviço não presume
  estrutura que a migration não garantiu.

- **IDs:** UUIDv7 ou ULID por padrão. IDs sequenciais apenas com justificativa (ex.:
  ordenação natural exigida pelo domínio).

- **Toda query com input externo é parametrizada.** Ver o piso Zig detalhado em §10.2.

### 10.1 Migrations reversíveis

- Toda migration tem **`down` testado** e é versionada. O piso não muda por ser Zig.

- **O runner pode ser externo** ou responsabilidade do **`<projeto>_ops`** — migrations
  SQL versionadas aplicadas no deploy pelo ops, não uma rotina ad-hoc no boot do
  serviço. Ferramenta agnóstica (ex.: `golang-migrate`, `flyway`, ou o runner do ops)
  desde que as migrations sejam **SQL versionado e reversível**. Zig não precisa de um
  runner Zig-native pra isso — a fonte da verdade é o SQL versionado.

- **Operar/migrar Postgres tem dona:** `schematize-postgres` → `references/locks-e-migrations.md` (migration segura, expand-contract, lock_timeout) e `references/pooling.md` (pool/PgBouncer, dimensionamento). Desenho de schema: `schematize-database`.

### 10.2 SQL parametrizado — o piso inegociável em Zig

Zig **não tem** `format!` do Rust, mas **montar query com `std.fmt.allocPrint` /
concatenação de string é exatamente o mesmo pecado** — e é **VETADO** (§37). O runtime
não te salva: interpolar input externo no texto do SQL é SQL injection igual ao de
qualquer linguagem.

- **Query sempre parametrizada** — placeholders (`$1`, `$2`, …) + **binds**; o valor do
  input externo **nunca** entra no texto da query. Caminhos aceitos, do mais idiomático:
  - **Driver Zig de Postgres com binds** (ecossistema jovem — valide maturidade/manutenção
    e registre no ADR, `references/cadeia-suprimentos.md`); OU
  - **`libpq` via `@cImport`** usando **`PQexecParams`** (sempre parametrizado, valores em
    array separado do texto). O **boundary C é validado** (`references/seguranca.md`) e a
    memória que cruza a fronteira segue o par alloc/free casado
    (`references/memoria-concorrencia.md`).

- **`std.fmt.allocPrint`/concatenação para montar SQL com input externo** — é o `format!`
  proibido do Rust com outra cara. `PQexec` (não-`Params`) com string montada idem.

- Confiar em "escapar na mão" o input — parametrização é a única defesa aceita.

- Buffers/resultados do driver liberados com `defer`/`errdefer`; cursores e conexões com
  ciclo de vida claro (arena ou pool). Sem GC, o vazamento de resultset é bug de entrega
  (leak gate, `references/memoria-concorrencia.md` §M3).

**Ferramentas sugeridas:** runner de migration agnóstico (`golang-migrate`/`flyway`/ops);
acesso a Postgres via driver Zig com binds **ou** `libpq`/`@cImport` (`PQexecParams`).

## 11. Cache

- Mitigação de cache stampede (single-flight, lock, jitter) — em Zig, o single-flight usa
  `std.Thread.Mutex`/atômicas com **seção crítica curta** (`references/memoria-
  concorrencia.md` §M5).
  > ✔ **Verificado em 2026-08-21:** na `std` da linha estável atual o mutex é **`std.Io.Mutex`** — `std.Thread.Mutex`
  > **não existe mais**. E `lock` recebe um `Io`; para estado compartilhado simples entre threads,
  > prefira **`std.atomic.Value(T)`** com `fetchAdd`/`cmpxchg`, que não depende do runtime de I/O.
  > *(Zig é pre-1.0: a `std` quebra entre minors. A versão exata vive em
  > `references/stack-versoes.md`, com data de verificação.)*

- Resposta autenticada **sempre** tem a chave de cache segmentada por usuário e tenant
  (§37).

## 12. APIs

- **Validação de payload na borda** — em Zig, parse defensivo: limite de tamanho, sem
  alocação guiada pelo atacante, allocator explícito (§9, `references/seguranca.md`).

- Operações de escrita aceitam `Idempotency-Key` **e o implementam de fato** (aceitar o
  header e ignorar é VETADO — §37).

- Quebra de contrato exige nova versão + janela de deprecação ≥ 90 dias com headers
  `Deprecation` e `Sunset`.

- **Contrato de API tem dona:** `schematize-api` → `references/contrato-rest.md` (OpenAPI 3.1 contract-first, erros), `references/idempotencia.md` (`Idempotency-Key`) e `references/versionamento-deprecacao.md` (`Deprecation`/`Sunset`); aqui só o recorte da linguagem.

## 18. Resiliência

- Timeout explícito (nunca infinito) — nada espera pra sempre; toda espera de I/O/rede
  tem teto e caminho de cancelamento (`references/memoria-concorrencia.md` §M7).

- **Serviço sobe e opera sozinho.** A ausência/queda de outra dependência (serviço,
  broker, cache) **nunca** impede o boot nem derruba este serviço — degrada (fallback,
  resposta parcial, enfileira e segue), não crasha em cascata (§2). "O `ledger` não sobe
  sem o `core`" é bug de acoplamento, não requisito.

- **Falha ao chamar/notificar outro serviço não se perde nem trava a cadeia.** Ao não
  conseguir notificar B, o serviço A **obrigatoriamente**: (1) **persiste o intento/dado
  em store durável** para retomar — outbox no mesmo commit, ou fila/Redis/tabela de
  pendências; **nunca só em memória** (e em Zig, "só em memória" ainda tem que respeitar o
  par alloc/free — memória não é durabilidade); (2) **loga com `trace_id`**; (3)
  **dispara alerta** (Grafana/alertmanager) pro ops/dev; (4) **retoma** com
  retry+backoff+jitter idempotente até o limite; estourou → **DLQ** + escala pro humano.
  Nunca falha em silêncio, nunca perde o dado, nunca deixa a cadeia parada sem sinal.

## 19. Jobs e Workers

- Progress/state persistido para jobs longos ou críticos — em **store durável**, não só
  no heap do processo (`references/memoria-concorrencia.md` §M7).

- **Cancelamento gracioso** — respeitar sinal de shutdown; `defer`/`errdefer` limpam o
  estado parcial e liberam a memória do job interrompido, sem invariante quebrada
  (`references/memoria-concorrencia.md` §M7).

> Regra de bolso Zig: **os pisos de dados/eventos são agnósticos e valem inteiros** — o
> que muda é o COMO. Query só parametrizada (`allocPrint` para SQL é o `format!`
> proibido; use binds ou `PQexecParams` via `@cImport`). Parse de evento/payload é
> defensivo (limite de tamanho, allocator explícito, nada guiado pelo atacante).
> Migration reversível versionada, runner no ops. E o piso de não perder dado na falha —
> persiste, loga `trace_id`, alerta, retoma — vale igual: memória não é durabilidade.
