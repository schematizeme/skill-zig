# Eventos, Banco de Dados, Cache, APIs, Resiliência e Jobs — Zig

> Parte da skill **schematize-zig**. As referências cruzadas (§N) apontam para seções do
> corpo completo — todas presentes no conjunto de references desta skill. Estes pisos são
> **agnósticos de linguagem** (eventos, outbox, banco dono do schema, cache, APIs,
> resiliência, jobs, idempotência) e valem em Zig **inalterados**. As especializações Zig
> aparecem onde a linguagem muda o **como**: **SQL parametrizado** (Zig não tem `format!`,
> mas `allocPrint` é o mesmo pecado), **drivers jovens** (muitas vezes `@cImport` de
> `libpq`) e **parse de evento defensivo** com allocator explícito. Liga com
> `references/seguranca.md`, `references/memoria-concorrencia.md` e
> `references/cadeia-suprimentos.md`.

## Índice
- 9. Eventos e Mensageria
- 10. Banco de Dados
- 11. Cache
- 12. APIs
- 18. Resiliência
- 19. Jobs e Workers

---

## 9. Eventos e Mensageria

**MUST — produção e consumo**
- Eventos são imutáveis e versionados (`v1`, `v2`).
- Consumidores idempotentes (deduplicação por id de evento).
- Suporte a replay.

**MUST — compatibilidade evolutiva**
- Novos campos são **opcionais**, com default seguro.
- Nunca remover ou renomear campo sem **nova versão** do evento.
- Consumidores **ignoram campos desconhecidos** (forward compatible).
- Coexistência de versões durante janela de migração documentada.

**MUST — entrega**
- **Transactional Outbox** para publicação de eventos. Dual-write (banco + broker no
  mesmo fluxo) é **VETADO** (ver §37). Detalhe do piso de não perder dado em §18.
- DLQ (dead letter queue) configurada para todo consumidor.
- **Retry infinito proibido.** Política de retry explícita com limite e backoff.

**MUST — backpressure**
- Consumidores com limites explícitos de concorrência e prefetch — em Zig, as **filas/
  buffers são bounded** e o produtor rápido **aguarda**, não acumula memória sem teto
  (`references/memoria-concorrencia.md` §M5). Backpressure aqui também é defesa de OOM.
- Throttling em produtores quando broker sinaliza pressão.

**MUST — parse de evento defensivo (Zig)**
- **Todo evento recebido é parseado defensivamente:** **limite de tamanho** do payload
  antes de alocar; **sem alocação ilimitada guiada pelo atacante** (nunca `alloc(n)` com
  `n` vindo do wire sem teto — é OOM/DoS); **allocator explícito** (arena por mensagem,
  liberada de uma vez). Campo desconhecido é ignorado sem estourar. Liga forte com
  `references/seguranca.md` (input hostil) e `references/memoria-concorrencia.md` (§M1).

**Convenção de nome:** `<dominio>.<entidade>.<evento>` no passado.
Exemplos: `catalog.product.created`, `billing.invoice.paid`.

**Brokers**

| Cenário | Stack |
|---|---|
| Eventos leves, baixa latência, pub/sub simples | **NATS** |
| Alto throughput, retenção, replay, streaming | **Kafka** |
| Workflows com routing complexo (caso a caso) | RabbitMQ |

> NATS e Kafka são padrão. RabbitMQ exige justificativa pelo custo operacional. Client
> nativo Zig de broker é jovem — quando faltar, `@cImport` de um client C maduro
> (ex.: `librdkafka`) com o **boundary validado** (`references/seguranca.md`) é o caminho
> idiomático; é custo, pese no ADR (`references/stack-versoes.md`).

---

## 10. Banco de Dados

| Caso | Stack |
|---|---|
| Relacional | PostgreSQL |
| Cache | Redis |
| Busca textual | OpenSearch |
| Analytics / eventos | ClickHouse |

**MUST**
- Migrations versionadas, **reversíveis** (com `down`), automatizadas no deploy. Piso
  mantido — ver §10.1.
- Schema próprio por serviço. O **banco é dono do schema**; o serviço não presume
  estrutura que a migration não garantiu.
- Sem joins cross-service no banco.
- **Timestamps em UTC, sempre.** Conversão de timezone apenas na borda (UI/API response).
- **IDs:** UUIDv7 ou ULID por padrão. IDs sequenciais apenas com justificativa (ex.:
  ordenação natural exigida pelo domínio).
- **Toda query com input externo é parametrizada.** Ver o piso Zig detalhado em §10.2.

**SHOULD — alta escala**
- Separação leitura/escrita (réplicas) quando volume justificar.
- Revisão periódica de índices.
- Análise de query plan em endpoints críticos.
- Particionamento para tabelas com crescimento previsível alto.

### 10.1 Migrations reversíveis

**MUST**
- Toda migration tem **`down` testado** e é versionada. O piso não muda por ser Zig.
- **O runner pode ser externo** ou responsabilidade do **`<projeto>_ops`** — migrations
  SQL versionadas aplicadas no deploy pelo ops, não uma rotina ad-hoc no boot do
  serviço. Ferramenta agnóstica (ex.: `golang-migrate`, `flyway`, ou o runner do ops)
  desde que as migrations sejam **SQL versionado e reversível**. Zig não precisa de um
  runner Zig-native pra isso — a fonte da verdade é o SQL versionado.

### 10.2 SQL parametrizado — o piso inegociável em Zig

Zig **não tem** `format!` do Rust, mas **montar query com `std.fmt.allocPrint` /
concatenação de string é exatamente o mesmo pecado** — e é **VETADO** (§37). O runtime
não te salva: interpolar input externo no texto do SQL é SQL injection igual ao de
qualquer linguagem.

**MUST**
- **Query sempre parametrizada** — placeholders (`$1`, `$2`, …) + **binds**; o valor do
  input externo **nunca** entra no texto da query. Caminhos aceitos, do mais idiomático:
  - **Driver Zig de Postgres com binds** (ecossistema jovem — valide maturidade/manutenção
    e registre no ADR, `references/cadeia-suprimentos.md`); OU
  - **`libpq` via `@cImport`** usando **`PQexecParams`** (sempre parametrizado, valores em
    array separado do texto). O **boundary C é validado** (`references/seguranca.md`) e a
    memória que cruza a fronteira segue o par alloc/free casado
    (`references/memoria-concorrencia.md`).

**VETADO**
- **`std.fmt.allocPrint`/concatenação para montar SQL com input externo** — é o `format!`
  proibido do Rust com outra cara. `PQexec` (não-`Params`) com string montada idem.
- Confiar em "escapar na mão" o input — parametrização é a única defesa aceita.

**SHOULD**
- Buffers/resultados do driver liberados com `defer`/`errdefer`; cursores e conexões com
  ciclo de vida claro (arena ou pool). Sem GC, o vazamento de resultset é bug de entrega
  (leak gate, `references/memoria-concorrencia.md` §M3).

**Ferramentas sugeridas:** runner de migration agnóstico (`golang-migrate`/`flyway`/ops);
acesso a Postgres via driver Zig com binds **ou** `libpq`/`@cImport` (`PQexecParams`).

---

## 11. Cache

**MUST**
- TTL **sempre explícito**. Sem TTL infinito sem ADR.
- Mitigação de cache stampede (single-flight, lock, jitter) — em Zig, o single-flight usa
  `std.Thread.Mutex`/atômicas com **seção crítica curta** (`references/memoria-
  concorrencia.md` §M5).
- Fallback seguro em cache miss — degradação graciosa, nunca falha total.
- Invalidação documentada por chave.
- Resposta autenticada **sempre** tem a chave de cache segmentada por usuário e tenant
  (§37).

**MUST NOT**
- Cache como source of truth.
- Cache de dados pessoais sensíveis sem criptografia.

---

## 12. APIs

**MUST**
- **OpenAPI 3.1** em `/docs/openapi.yaml` — fonte da verdade.
- Versionamento na URL: `/v1`, `/v2`.
- **Validação de payload na borda** — em Zig, parse defensivo: limite de tamanho, sem
  alocação guiada pelo atacante, allocator explícito (§9, `references/seguranca.md`).
- Erro padrão (compatível com RFC 7807):

```json
{
  "error": {
    "code": "PRODUCT_NOT_FOUND",
    "message": "Product not found",
    "trace_id": "01HXYZ...",
    "details": []
  }
}
```

- Operações de escrita aceitam `Idempotency-Key` **e o implementam de fato** (aceitar o
  header e ignorar é VETADO — §37).
- Quebra de contrato exige nova versão + janela de deprecação ≥ 90 dias com headers
  `Deprecation` e `Sunset`.
- Timestamps em **ISO-8601 com timezone explícito** (preferencialmente `Z`).

**MUST — paginação**
- **Cursor pagination** é o padrão.
- Offset apenas em listas pequenas (< 10k itens) e estáticas.
- Resposta inclui `next_cursor` e `has_more`.

**MUST — rate limiting**
- Rate limiting **distribuído** (Redis, gateway, ou serviço dedicado).
- Chave por usuário, API key e tenant.
- Resposta 429 com header `Retry-After`.

**SHOULD**
- Contratos consumer-driven (Pact) entre serviços.
- gRPC para alta performance interna; HTTP/JSON para externa.

---

## 18. Resiliência

**MUST em chamadas externas:**
- Timeout explícito (nunca infinito) — nada espera pra sempre; toda espera de I/O/rede
  tem teto e caminho de cancelamento (`references/memoria-concorrencia.md` §M7).
- Retry com backoff exponencial + jitter, idempotência garantida.
- Circuit breaker.
- Rate limiting na borda.
- Bulkhead em integrações críticas.

**MUST — independência e falha de dependência (resiliência por design):**
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

---

## 19. Jobs e Workers

**MUST**
- Jobs **idempotentes** (pode executar 2x sem corromper).
- Timeout obrigatório por job.
- Política de retry explícita com limite.
- Progress/state persistido para jobs longos ou críticos — em **store durável**, não só
  no heap do processo (`references/memoria-concorrencia.md` §M7).
- DLQ para jobs que falharem após max retries.

**SHOULD**
- Jobs longos divisíveis em chunks com checkpoint.
- **Cancelamento gracioso** — respeitar sinal de shutdown; `defer`/`errdefer` limpam o
  estado parcial e liberam a memória do job interrompido, sem invariante quebrada
  (`references/memoria-concorrencia.md` §M7).

---

> Regra de bolso Zig: **os pisos de dados/eventos são agnósticos e valem inteiros** — o
> que muda é o COMO. Query só parametrizada (`allocPrint` para SQL é o `format!`
> proibido; use binds ou `PQexecParams` via `@cImport`). Parse de evento/payload é
> defensivo (limite de tamanho, allocator explícito, nada guiado pelo atacante).
> Migration reversível versionada, runner no ops. E o piso de não perder dado na falha —
> persiste, loga `trace_id`, alerta, retoma — vale igual: memória não é durabilidade.
