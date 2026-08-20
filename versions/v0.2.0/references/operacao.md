# Operação: Config, Deploy, Git, Archive, ADR, IA e Anexos

> **Dividida:** §29+ (templates, feature flags, IA assistida, DoD §35, evolução, índice §39) estão em `references/entrega.md`. A numeração de seções é contínua entre os dois arquivos.

> Parte da skill **schematize-zig**. As referências cruzadas (§N) apontam para seções do corpo completo — todas presentes no conjunto de references desta skill.

## Índice
- 20. Configuração
- 21. Infraestrutura e Deploy
- 24. Qualidade e Git
- 25. Ownership
- 26. Runbooks e Incidentes
- 27. ADR — Architecture Decision Records
- 28. Archive de Conversas e Tarefas — INEGOCIÁVEL
- 29. Templates
- 31. Feature Flags
- 34. Uso de IA Assistida
- 35. Definition of Done
- 36. Evolução
- 39. Índice de Funcionalidades (fonte da verdade viva)
- Anexo A — Versões Correntes
- Anexo B — Glossário Mínimo

---

## 20. Configuração

- Via environment variables (12-factor).
- Validação tipada no startup — falha rápido.
- Sem hardcode.
- Defaults seguros (fail closed).

---

---

## 21. Infraestrutura e Deploy

**MUST**
- Kubernetes + Helm.
- IaC: Terraform ou OpenTofu.
- CI/CD: GitHub Actions.
- Ambientes isolados: `dev` (local), `hml`/`staging` (homologação), `production`/`prd`.
- Promoção entre ambientes por **artefato imutável** (mesma imagem, commit SHA rastreável).
- **Fluxo de promoção fixo, sem atalho:** `desenvolvimento local → teste local (verde) → GitHub → hml → prd`. Nada pula etapa; **nada vai direto pra hml/prd**.
- **VETADO editar código direto no servidor (hml/prd).** O servidor é **imutável por edição manual** — recebe só artefato promovido do git. Precauções: filesystem read-only, **drift detection** (recusa/alerta divergência com o git), acesso de escrita = break-glass auditado. Hotfix segue o mesmo fluxo, acelerado. Detalhe e o control plane em **`references/ops.md`**.
- **Toda operação no servidor passa pelo `<projeto>_ops`** (§2, `references/ops.md`): install/update/config/migrate/rollback/troubleshoot — nunca à mão. Instalação **paralela por padrão** (= `nproc`); falha no paralelo = serviços não independentes → corrigir a independência é prioridade máxima (piso 10).

### 21.1 Estratégia de Deploy

| Estratégia | Quando usar |
|---|---|
| Rolling update | Default para serviços comuns |
| Blue/green | Serviços críticos, rollback instantâneo necessário |
| Canary | Mudanças de alto impacto, rollouts graduais |

**MUST**
- Rollback automatizado quando healthcheck falhar pós-deploy.
- Healthcheck gating: tráfego só vai pra pod ready.
- Janela de validação antes de declarar deploy bem-sucedido.

### 21.2 Preview Environments

**SHOULD**
- PRs em serviços principais geram ambiente efêmero automaticamente.
- Destruído ao merge ou após X dias de inatividade.

---

---

## 24. Qualidade e Git

**Commits:** Conventional Commits.
**Versionamento:** SemVer.

**Branches — trunk-based como padrão**

```
main      → produção (protegida, linear history)

feature/<ticket>-<slug>
fix/<ticket>-<slug>
hotfix/<ticket>-<slug>
```

GitFlow (`develop`) é opcional e exige justificativa — só vale a pena em times com release cadenciado pesado.

**Pull Requests**
- Tamanho alvo: ≤ 400 linhas alteradas.
- ≥ 1 reviewer (≥ 2 para `domain`, schema, segurança).
- **CODEOWNERS obrigatório.**
- CI verde obrigatório.
- Squash merge na `main`.
- **Merge direto na `main` é VETADO.** Force push em branch protegida idem (§37).

---

---

## 25. Ownership

**MUST**
- Cada serviço tem **owner explícito** (squad ou pessoa).
- `CODEOWNERS` configurado.
- Documentação de **oncall** definida.
- Contato de escalação documentado no README.

---

---

## 26. Runbooks e Incidentes

### 26.1 Runbooks

**MUST**
- Serviços críticos têm runbook em `/docs/runbook.md`.
- Conteúdo mínimo: como diagnosticar falhas comuns, dashboards relevantes, comandos úteis, como fazer rollback, contatos.
- Incidentes recorrentes atualizam o runbook.

### 26.2 Incidentes

**MUST**
- Postmortem **blameless** para todo incidente Sev1/Sev2.
- RCA (root cause analysis) documentado.
- Ações preventivas rastreáveis (issue/task) com prazo.
- Repositório central de postmortems acessível ao time.

---

---

## 27. ADR — Architecture Decision Records

Toda decisão arquitetural relevante vira ADR.

```
/docs/adr/
  0001-use-postgresql.md
  0002-adopt-hexagonal-architecture.md
```

Formato MADR. Status: `proposed`, `accepted`, `deprecated`, `superseded by NNNN`.

**Quando criar:** escolha de banco/broker/linguagem, padrão arquitetural, mudança de contrato público, qualquer desvio deste documento (exceto itens VETADO, que não admitem exceção).

---

---

## 28. Archive de Conversas e Tarefas — INEGOCIÁVEL

> **Esta seção não tem modo "pula pra ir mais rápido".** O archive é parte da entrega, não um extra. Tarefa sem archive = tarefa não feita (§35). Gerar os `.md` é tão obrigatório quanto compilar.

**Princípio:** todo trabalho que produz código, decisão ou mudança de estado **gera registro em Markdown, TODA vez, sem exceção**. Não existe "depois eu documento". O `.md` nasce junto com o trabalho e é commitado junto.

### 28.0 Layout canônico — todo MD gerado no archive, root limpo (MUST)

**Todo `.md` gerado pela skill/agente mora em `<projeto>_archive/`, NUNCA no root do projeto.** Isso vale para MAPA, índices, planos, relatórios, handoffs, checkpoints — qualquer artefato gerado. O root do projeto fica **limpo**: só código, config e os poucos MDs de projeto mantidos à mão por humano (`README.md`, `CLAUDE.md`, `LICENSE`, e ADRs se o projeto os versiona em `docs/adr/`). Largar MAPA/índice/plano/relatório no root é **violação** (§37) e fere a contenção de workspace.

Subpastas canônicas (o archive **é versionado** — entra no PR):

```
<projeto>_archive/
  index/         # MAPA.md + INDEX_GLOBAL.md + INDEX_FUNCTIONS.md (ou INDEX_COMPONENTS.md) — regenerados no lugar
  context/       # handoff/checkpoint de contexto (§34.1)
  orchestration/ # plano + checkpoint de fan-out/paralelização (references/orquestracao.md)
  pentest/       # ENDPOINTS.md + relatórios (schematize-pentest)
  chat/          # §28.1
  task/          # §28.2
```

**Regra de bolso:** antes de gravar qualquer `.md`, o caminho começa com `<projeto>_archive/`. Se você ia escrever no root, pare e mova pro archive.

### 28.1 Chat Archive

**MUST — gerar SEMPRE** para conversas/sessões que produzem:
- Decisão arquitetural ou de segurança
- Mudança de contrato público
- Escolha de tecnologia
- Resolução de incidente
- **Qualquer geração de código não trivial** (inclui código assistido por IA — §34)

**SHOULD** para tasks de implementação significativas.
**MAY** para o resto (troca trivial, dúvida pontual).

```
<project>_archive/chat/
  <YYYY-MM-DD-HH-MM-SS>-<contexto>.md
```

Conteúdo mínimo (todos os campos preenchidos, nunca placeholder vazio):
- Pergunta/objetivo original
- Entendimento do problema
- Resposta/decisão tomada
- Alternativas consideradas
- Riscos e trade-offs
- Próximos passos

### 28.2 Task Archive

**MUST — gerar SEMPRE** para toda task de implementação significativa.

```
<project>_archive/task/
  <task-name>.md
```

Conteúdo: contexto, objetivo, checklist, decisões, blockers, progresso. **Atualizar ao fim de cada sessão** — não acumular pra depois.

### 28.3 Garantias de processo

**MUST**
- O archive é **verificável**: PR sem o `.md` correspondente (quando a regra acima exige) **não passa no review** (item de checklist de §35).
- Gerar o archive é passo do fluxo, não tarefa separada que pode ser cortada por falta de tempo. **Falta de tempo não revoga a §28.**
- Assistente de IA que produz código nesta base **gera o `.md` do archive na mesma entrega** — pular isso é violação direta (§37, item 28).

> Registro indiscriminado de toda interação produz ruído. Registro seletivo do que importa produz contexto histórico útil. **Mas "seletivo" é sobre o quê registrar, nunca sobre se registrar quando a regra manda.**

---

---

