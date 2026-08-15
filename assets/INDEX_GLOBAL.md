# Índice Global da Aplicação — <projeto>

> **Fonte da verdade** do que existe e onde (§39). Consulte ANTES de criar algo
> (anti-duplicação). Atualizado no MESMO PR que muda funcionalidade.
> Local: `<projeto>_archive/index/INDEX_GLOBAL.md`. Última atualização: <data>.

## Repositórios / Serviços

| Repo/Serviço | Bounded context | O que faz (1 linha) | Linguagem | Owner |
|---|---|---|---|---|
| sensor_gateway_zig | ingest | gateway de telemetria (parser binário, interop C) | Zig 0.14.0 | squad-x |
| ... | ... | ... | ... | ... |

## Mapa de comunicação

> Quem chama quem; eventos publicados/consumidos; contratos.

| Origem | Destino | Como | Contrato |
|---|---|---|---|
| sensor_gateway_zig | metrics_api | evento `ingest.reading.received` | Kafka, v1 |
| ... | ... | ... | ... |

## Estrutura por repo

### <repo>
| Pasta top-level | Responsabilidade | Onde detalhar |
|---|---|---|
| `domain/` | entidades, value-objects, regras | INDEX_FUNCTIONS.md |
| `application/` | use-cases, dto | INDEX_FUNCTIONS.md |
| `infrastructure/` | persistência, mensageria, external | — |
| `interface/` | http, grpc, cli | OpenAPI |

## Links de verdade
- OpenAPI: `/docs/openapi.yaml`
- SLO: `/docs/slo.md`
- Runbook: `/docs/runbook.md`
- ADRs: `/docs/adr/`
