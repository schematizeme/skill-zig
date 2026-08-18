# Entrega: Templates, Flags, IA Assistida, DoD, Evolução e Índice

> Parte da skill **schematize-zig**. Continuação de `operacao.md` (numeração de seções **preservada**, §29+): templates, feature flags, uso de IA assistida, Definition of Done, evolução e índice de funcionalidades. Cross-refs por número de seção continuam válidos.

---

## 29. Templates

```
/templates
├── README.md
├── ADR.md
├── TASK.md
├── PR_TEMPLATE.md
├── ISSUE_TEMPLATE.md
├── RUNBOOK.md
├── INDEX_GLOBAL.md       # índice global da aplicação (§39)
├── INDEX_FUNCTIONS.md    # índice de microfunções (§39)
└── OPENAPI_TEMPLATE.yaml
```

README mínimo: o que é, como rodar, como testar, como deployar, dependências, observabilidade, oncall, runbook.

---

---

## 31. Feature Flags

Obrigatório para features críticas, migrações e rollouts graduais.
Capacidades: rollout por % de tráfego, segmentação por tenant/usuário, kill switch, expiração de flag.
Sugestões: Unleash, OpenFeature, GrowthBook.

---

---

## 34. Uso de IA Assistida

**MUST**
- Código gerado por IA passa pelo mesmo PR review humano que qualquer outro.
- Autor humano é responsável: assina o commit, entende o código, mantém.
- Saídas de IA não substituem ADR.
- **IA opera sob a §37 (anti-padrões vetados) integralmente.** Gerar código que viola um item VETADO é defeito, não estilo — rejeita no review.
- **IA gera o archive (§28) junto com o código**, na mesma entrega.

**MUST NOT / VETADO**
- Colar trecho gerado sem ler.
- Aceitar dependências sugeridas sem verificar nome (typosquatting é real — §37).
- Submeter código que não passa em `zig build test` (o gate local: compila, roda os testes e falha em leak via `std.testing.allocator`) nem em `zig fmt --check`.
- Aceitar "solução rápida" da IA que burla um piso de segurança da §37.

**SHOULD**
- Prompt e contexto relevantes registrados no chat archive quando a decisão for não trivial.
- Verificar licença de snippets longos sugeridos.

### 34.1 Handoff de contexto em sessões longas

Sessões longas de agente degradam quando o contexto enche: o modelo "esquece" decisões e a compactação automática resume de forma lossy. Para não perder estado, o handoff é **proativo e arquivado**, não reativo.

**MUST**
- Definir um **limite de handoff** (tokens) abaixo do teto da janela — cedo o suficiente pra sobrar espaço pra escrever o resumo. Sugestão: ~25% da janela (ex.: 250k numa janela de 1M).
- Ao cruzar o limite, **antes de qualquer compactação**, gerar dois artefatos em `<project>_archive/context/`:
  - `<YYYY-MM-DD-HH-MM-SS>-context.md` — estado do projeto, decisões tomadas, arquivos tocados, onde parou.
  - `<YYYY-MM-DD-HH-MM-SS>-checklist.md` — **feito vs. em aberto**.
- Só então compactar/limpar o contexto. O handoff é archive obrigatório (§28) — armazenar **sempre** em `<project>_archive`.
- **Rede de segurança determinística:** um backup do estado é capturado automaticamente antes de toda compactação (manual ou automática), independente de o agente ter lembrado de gerar os MDs acima.

**SHOULD**
- O limite é configurável por ambiente/projeto (ex.: env var), não hardcoded.
- O resumo de contexto preserva o que **você** escolhe (foco na tarefa corrente), não o que a compactação automática adivinha.

> Compactação automática é rede, não plano. Em sessão longa, o handoff arquivado vem antes do teto — quem controla o que sobrevive é você, não o resumo lossy.

---

---

## 35. Definition of Done

Uma task está pronta quando, cumulativamente:

- [ ] Testes passam (`zig build test`, unit + integration), cobertura nos mínimos
- [ ] Caminhos críticos com testes explícitos
- [ ] **Teste emulado por IA (`simulated`, §22.3) executado — 100% das rotas do inventário acessíveis pra quem deve e bloqueadas pra quem não deve; rota fantasma/morta = bloqueio**
- [ ] **Pentest de entrada limpo: sem `500`, sem coerção de tipo, sem eco não-escapado, sem vazamento cross-tenant (§22.3, §22.8)**
- [ ] `zig fmt --check` limpo, `zig build` sem warnings, security scan limpo
- [ ] **Gate de vazamento verde: testes exercitam o caminho com `std.testing.allocator` (aborta em leak) e `defer`/`errdefer`/ownership conferidos — sem leak, sem double-free, sem use-after-free (`references/memoria-concorrencia.md`)**
- [ ] **Nenhum item da §37 (anti-padrões vetados) presente no diff**
- [ ] **Arquivos ≤ 750 linhas (~500 úteis + ~250 comentário); código útil > 300 linhas (~400 obs) flagueado e registrado como dívida (§6); toda função com doc-comment `///` de contexto — o quê + onde é usada**
- [ ] **Índice de funcionalidades atualizado no mesmo PR — global e microfunções (§39)**
- [ ] Observabilidade implementada (logs, métricas, traces, audit se aplicável)
- [ ] OpenAPI atualizada (se for API)
- [ ] Migration testada com rollback (se houver schema change)
- [ ] Documentação atualizada (README, ADR, runbook se aplicável)
- [ ] Smoke tests executados em staging **(com asserção de conteúdo e self-check anti verde-mentiroso — §22.3)**
- [ ] CI verde, code review aprovado
- [ ] **Archive de chat/task gerado e commitado (§28) — gate rígido, não opcional**
- [ ] Feature flag configurada (se aplicável)
- [ ] CODEOWNERS aplicável revisou

> Os itens em negrito são **bloqueantes absolutos**: archive (§28), ausência de macaquice (§37), teste emulado por IA com rota 100% acessível (§22.3), e pentest de entrada limpo (§22.8). Faltando qualquer um, a task **não está pronta** — independente de todo o resto estar verde. Smoke verde não basta: tem que ser smoke que **prova** conteúdo, não só status.

---

---

## 36. Evolução

- Refactors incrementais. Big-bang rewrite exige ADR e plano de rollback.
- Toda migração de runtime/framework tem flag de coexistência.
- DDD e hexagonal podem ser adotados progressivamente — comece pelas bordas e pelos domínios mais complexos.

---

---

## 39. Índice de Funcionalidades (fonte da verdade viva)

O código diz **como** está agora; o índice diz **o que existe, onde mora e como se faz cada coisa** — e é tratado como **fonte da verdade do projeto**, consultado antes de criar algo (pra não duplicar) e atualizado a cada mudança. Índice que apodrece é pior que não ter; por isso ele é gerável/validável e tem gate na DoD.

**MUST — existência e localização**
- Todo projeto mantém o índice versionado em `<project>_archive/index/` (ou `/docs/index/`), em **dois níveis**:
  - **Índice global da aplicação** (`INDEX_GLOBAL.md`) — o mapa macro: repos/serviços/bounded contexts e como se comunicam; a relação de **pastas top-level** de cada repo e a responsabilidade de cada uma; **o que cada coisa faz** e o ponto de entrada de **como se faz** (link pro fluxo/use-case/runbook). É o "mapa do território".
  - **Índice de microfunções** (`INDEX_FUNCTIONS.md`, por serviço) — o catálogo fino: cada função/módulo relevante → **o quê**, **onde é usada/prevista**, dependências e efeitos colaterais. Gerado a partir dos doc-comments `///` obrigatórios (§6).

**MUST — atualização e gate**
- Todo PR que **adiciona, remove ou move** funcionalidade atualiza o índice no mesmo PR. Índice desatualizado **trava o merge** (item da DoD, §35).
- O índice é **fonte da verdade**: ao planejar uma feature, consulte-o primeiro pra não reimplementar o que já existe (anti-duplicação — liga com DRY semântico, §1).
- Formato **machine-friendly** (markdown com tabelas, ou JSON/YAML que renderiza) pra permitir geração e validação automáticas — não prosa solta.

**MUST — completude (uma entrada por função, sem "relevante")**
- O índice de microfunções é **exaustivo**: **uma entrada por unidade chamável** — função, método, handler, hook, closure nomeada, job/consumer — de **cada** serviço/repo do sistema, **pública e privada**. Não existe função "irrelevante": se está no código, está no índice. "Função relevante" **não é filtro** pra pular nada.
- **Invariante verificável (conte, não confie):** por serviço, `nº de entradas no índice == nº de funções declaradas no código`. O `/<slug>-index` e o CI **contam as declarações** (AST/ctags, ou regex de `func `/`fn `/`def `/`function `/métodos) e **reprovam** se o índice tiver **menos** entradas que funções encontradas — listando as que faltam **pelo nome**. Índice com 90 linhas para 100+ funções é **falha dura**, não aviso. O mapa não "resume" o sistema; ele **enumera** o sistema.
- **Cobertura total:** o índice **global** lista **cada** microserviço/repo (nenhum de fora); cada microserviço tem seu índice de funções **completo**. Um sistema de N serviços com M funções tem os N serviços mapeados e as M funções indexadas.

**MUST — o mapa é um GRAFO, não uma lista**
- O índice/MAPA carrega um **grafo textual** de dependências, navegável em dois níveis:
  - **Grafo de serviços** (cross-service): nós = microserviços; arestas `A → B` rotuladas pelo **contrato** (rota/evento/fila/tópico). Quem chama/notifica quem no sistema inteiro.
  - **Grafo de chamadas** (intra-service): por função, **quem ela chama** (out) e **quem a chama** (in) — adjacência `chamador → chamada`. Percorre-se de um ponto de entrada até a saída, e vê-se o **raio de impacto** de qualquer função.
- **Formato:** bloco **Mermaid** (`flowchart`) — textual **e** renderiza no GitHub/markdown — **mais** a adjacência em lista/tabela (pra diff, busca e grep). O Mermaid é o desenho; a adjacência é a fonte pesquisável. Ambos gerados pelo `/<slug>-index`.

**SHOULD — geração assistida**
- O índice de microfunções é **gerado por script** que varre os doc-comments `///` padronizados (§6) e monta a tabela `função → o quê → onde → arquivo:linha`. CI compara o índice commitado com o gerado; divergência aponta índice ou comentário desatualizado.
- Cada entrada linka pro arquivo/linha de origem.
- Índice global revisado em cada mudança arquitetural (junto com o ADR, §27).

**Conteúdo mínimo**

`INDEX_GLOBAL.md`: lista de repos/serviços com 1 linha de propósito cada; por repo, árvore de pastas top-level com responsabilidade; mapa de comunicação (quem chama quem, quais eventos/contratos); links pra OpenAPI, SLO, runbook.

`INDEX_FUNCTIONS.md` (por serviço, **exaustivo — uma linha por função**): `função | o quê | de onde vem → pra onde vai | chama (out) | é chamada por (in) | efeitos | arquivo:linha`; **nº de linhas == nº de funções do serviço**. Acompanha o **grafo de chamadas** (Mermaid + adjacência). O `INDEX_GLOBAL.md` inclui o **grafo de serviços** (Mermaid) com **todos** os microserviços e seus contratos.

> O índice responde "isso já existe? onde? como faço X?" sem precisar reler o código. Se a resposta exige caçar no código, o índice falhou — ou está desatualizado, e isso é bug.

---

---

## Anexo A — Versões Correntes

> Atualizado independentemente do documento principal. Revisão trimestral.

| Stack | Versão alvo (2026-05) |
|---|---|
| **Zig** | **0.14.x — PRÉ-1.0: versão do compilador PINADA exata (toolchain reproduzível); ver `references/stack-versoes.md`** |
| Node.js | 24 LTS (frontend: Next.js, Astro, etc. / legado backend em migração — §3) |
| Go | 1.25 |
| Rust | 1.85 |
| PostgreSQL | 16+ |
| Redis | 7+ |
| Kubernetes | 1.30+ |
| OpenAPI | 3.1 |
| OpenTelemetry | 1.x (estável) |

Mudanças de versão major exigem ADR. **Zig é pré-1.0:** pinar a versão exata do compilador (linguagem e stdlib ainda mudam entre minors — tratar bump de minor como potencialmente breaking, com ADR e build reproduzível). A matriz de versões da toolchain e das deps (`build.zig.zon` com hash) fica em `references/stack-versoes.md`.

---

---

## Anexo B — Glossário Mínimo

- **Bounded Context** — fronteira explícita dentro da qual um modelo de domínio é consistente.
- **Monólito distribuído** — serviços fisicamente separados mas acoplados por banco compartilhado, shared lib de domínio ou cadeia síncrona sem fronteira. O pior dos dois mundos. Proibido (§2).
- **BFF (Backend for Frontend)** — camada server-side que serve um frontend específico e mantém os segredos fora do browser (§38).
- **Outbox Pattern** — gravar evento em tabela no mesmo commit do dado de negócio; publicador assíncrono lê a tabela e publica no broker. Garante consistência sem dual-write.
- **DLQ** — dead letter queue, fila de mensagens que falharam após retries.
- **Anti-Corruption Layer** — adapter que isola seu domínio do modelo externo.
- **SLO** — service level objective, alvo mensurável de qualidade (ex: 99.9% das requests < 300ms em 30 dias).
- **Error Budget** — quanto você pode falhar dentro do SLO antes de freezar features.
- **Blameless Postmortem** — análise de incidente focada em sistema/processo, não em culpa individual.
- **CSPRNG** — gerador pseudoaleatório criptograficamente seguro. Obrigatório para tokens, ids de sessão e segredos (§14).
- **Macaquice** — atalho que parece entregar mais rápido e entrega vulnerabilidade ou dívida. Catalogadas e vetadas na §37.

---
