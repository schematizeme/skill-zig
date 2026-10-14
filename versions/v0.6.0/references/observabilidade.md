# Observabilidade, Healthchecks, Performance e FinOps — Zig


> **PONTEIRO, não cópia.** O padrão (OpenTelemetry, Collector, sinais correlacionados, SLO, alertas, dashboards
> como código, stack de referência) é da **`schematize-observability`** (`schematize-observability -> SKILL.md` e
> `references/`); o piso da base está em `schematize-engineering -> references/observabilidade.md`. Aqui fica
> **só o que muda em Zig**: `std.log` com scopes, `/metrics` como chão maduro, o gap honesto do OTel in-process,
> profiling com símbolos nativos. **Onde divergir, a base e a `schematize-observability` mandam**
> (`SKILL.md` §"Precedência e herança"); a numeração salta porque o número é o da base.

## 16. Observabilidade

**Em Zig o binding OpenTelemetry nativo é jovem** — a estratégia real está em §16.3. O piso "todo serviço
observável" (logs estruturados com `trace_id`, `/metrics`, dashboard + alertas + chart, §35) não muda; o COMO
muda. O Collector (Alloy) carrega **mais** peso do enriquecimento (`schematize-observability -> references/padrao-otel.md`),
e **Beyla/eBPF no sidecar é aliado forte**: contorna a imaturidade do binding in-process.

### 16.1 Logs — `std.log` com scopes + handler JSON

Zig tem `std.log` embutido, com **níveis** e **scopes** (`std.log.scoped(.<escopo>)`).
O piso da casa — **log estruturado + correlação por `trace_id`** — vale igual; o
caminho idiomático é um **handler custom** que emite JSON.

- **Instalar um `logFn` custom** (via `pub const std_options = .{ .logFn = ... }`) que
  serializa cada evento como **JSON estruturado** numa linha: `level`, `timestamp`
  (UTC), `scope`, `message` e **campos** (`trace_id`, `correlation_id`, `tenant_id`
  quando aplicável). Nada de `std.debug.print` solto em serviço — isso é `stderr` não
  estruturado (VETADO em produção, §37).

- **`std.log.scoped(.<modulo>)`** por módulo/subsistema, para o campo `scope` sair de
  graça e permitir filtro por área.

- **Níveis:** DEBUG, INFO, WARN, ERROR (mapeados de `std.log.Level`). Nível de produção
  configurável; DEBUG não é o default de prd.

- **`trace_id` em toda request** — propagado pelo contexto da requisição/thread e
  incluído em cada linha daquele fluxo. Sem `trace_id`, log não correlaciona.

- **Proibido logar:** senhas, tokens, JWT, PII (CPF, email, telefone), dados
  financeiros, payloads de pagamento. **Mascaramento obrigatório** — e como não há GC,
  cuide de **não vazar o buffer** do campo mascarado (allocator explícito,
  `references/memoria-concorrencia.md`).

- **VETADO** logar request/response inteiros, headers ou body cru "pra debugar" (§37).
  Logue campos específicos, mascarados.

- O handler de log escreve numa **fila/buffer limitado** e drena numa thread própria, pra
  I/O de log não bloquear o caminho quente nem alocar sem teto sob pressão (bounded,
  `references/memoria-concorrencia.md` §M5).

### 16.2 Métricas — Prometheus `/metrics`

- **Expor `/metrics` no formato Prometheus** (§17). É o caminho **mais maduro e estável**
  de telemetria em Zig hoje — texto de exposição simples, sem depender de binding OTel.

- Contadores/histogramas atualizados sob **atômicas ou lock curto**
  (`references/memoria-concorrencia.md` §M5) — métrica não pode introduzir data race.

### 16.3 Tracing — honesto sobre o gap, e a mitigação

**OpenTelemetry nativo em Zig é imaturo.** Não há binding in-process maduro equivalente
ao `tracing`/OTel SDK de Rust/Go. **Não finja paridade** — o piso "todo serviço
observável" continua; muda o **COMO** exportar trace. Escolha (e registre no ADR §27)
uma das rotas, do mais simples ao mais completo:

- **(a) Métricas primeiro:** `/metrics` (§16.2) + logs estruturados com `trace_id`
  (§16.1) já entregam RED e correlação. Para muitos serviços Zig de sistema, isso é o
  observável mínimo real.

- **(b) OTLP via lib C (`@cImport`):** usar o **OTel C/C++ SDK** por `@cImport` para
  exportar spans OTLP. **O boundary C tem que ser validado** — memória que cruza a
  fronteira segue as regras de `references/seguranca.md` e o par alloc/free casado de
  `references/memoria-concorrencia.md`. É custo (mais uma dep C na cadeia,
  `references/cadeia-suprimentos.md`), mas dá trace de verdade.

- **(c) Collector/sidecar (Alloy) faz o trabalho pesado:** sem binding maduro, o serviço
  emite spans por um **protocolo simples** (ou expõe o suficiente) e **deixa o Alloy
  enriquecer/exportar** para Tempo. **Beyla/eBPF** no sidecar auto-instrumenta o tráfego
  de rede sem tocar o binário — forte aliado enquanto o in-process amadurece.

- Propagação **W3C Trace Context** nos headers de entrada/saída — mesmo que o trace seja
  montado pelo collector, o `trace_id` atravessa a fronteira do serviço.

- **Declarar no MAPA/ADR qual rota (a/b/c) o serviço usa e por quê** — é decisão que
  muda com a maturidade do ecossistema e com a versão do Zig (`references/stack-versoes.md`).

### 16.5 Business Observability

- Métricas de negócio expostas em `/metrics` (pedidos/min, conversão, churn, etc).

### 16.6 Auditoria

- Operações sensíveis (mudança de permissão, transações financeiras, alteração de
  configuração, ações administrativas) registradas em **trilha de auditoria imutável**.

- Campos mínimos: `actor_id`, `tenant_id`, `action`, `resource`, `timestamp`, `ip`,
  `user_agent`, `result`.

- Storage append-only (não usar a mesma tabela de domínio;
  `references/dados-eventos.md`).

## 17. Healthchecks

> Independência (`references/dados-eventos.md` §18): `/ready` reflete a saúde **deste**
> serviço. A queda de uma dependência degrada a prontidão do fluxo que a usa, mas
> **não** derruba o serviço nem impede o boot — degradação graciosa, não crash em
> cascata.

## 30. Performance — Metas Padrão

| Métrica | Alvo |
|---|---|
| API p95 | < 300 ms |
| API p99 | < 1 s |
| Startup | < 10 s (binário Zig sobe rápido; sem warm-up de runtime) |
| Imagem Docker | < 200 MB (Zig — na prática **muito menor**: binário estático em `scratch`/distroless) |

### 30.1 Profiling — meça, não presuma

**Sem GC, a latência do Zig é previsível** (sem pausa de coletor), mas isso **não**
autoriza presumir performance: **meça**.

- **Perfilar com dados reais antes de otimizar** — o binário Zig integra com **`perf`**
  e com **Pyroscope** via **símbolos nativos** (buildar com símbolos preservados no
  perfil de profiling). Decisão de trocar `ReleaseSafe`→`ReleaseFast` exige perfil que
  prove o ganho + ADR (`references/memoria-concorrencia.md` §M4).

- **Alocação é custo visível em Zig** — perfile alocações no caminho quente; arena/
  buffer fixo por requisição costuma bater o allocator geral (§M1). Otimização guiada
  por medição, não por palpite.

- Pyroscope contínuo em produção para flamegraph ao vivo; k6 para carga sintética antes
  de promover mudança sensível a latência.

## 33. FinOps — Gestão de Custos

- Revisão periódica de overprovisioning (CPU/memória/réplicas) — o footprint enxuto do
  binário Zig (imagem pequena, pouca RAM, sem heap de runtime) costuma permitir **request
  e limit agressivamente baixos**; ajuste com base no profiling (§30.1), não no chute.

> Regra de bolso Zig: **o piso "todo serviço observável" não muda — o COMO muda.**
> `/metrics` + log JSON com `trace_id` são o chão maduro; trace nativo é o gap honesto,
> mitigado por lib C (boundary validado) ou collector/eBPF. Sem GC, meça a latência em
> vez de presumir — `perf`/Pyroscope com símbolos nativos.
