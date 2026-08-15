---
description: Q.A. plan-first — planeja, gera MD de passo a passo, pede aprovação, então roda
argument-hint: "[escopo: smoke|security|all|full|...]"
---

Conduza o fluxo de **Q.A. plan-first** (§22.9). NÃO execute nada antes de aprovar.

## Fase 1 — Planejar (sem executar)
Levante o escopo a partir de $ARGUMENTS (ou pergunte se vazio): modos a rodar
(smoke/integration/security/pentest/authz/hardening/chaos/simulated/unit),
ambiente alvo, rotas/personas afetadas, ordem, dependências, passos **destrutivos**
e riscos.

## Fase 2 — MD do plano
Escreva `<projeto>_archive/qa/<ts>-<contexto>.md` com cada passo: objetivo, comando
exato, ambiente, resultado esperado, critério de pass/fail e flag de destrutivo.
Referencie o `summary.json` que será gerado (§22.2).

## Fase 3 — Aprovação
Apresente o plano e **peça aprovação explícita**. Sem "ok", nada roda. Aprovação
parcial é válida e vira o escopo efetivo.

## Fase 4 — Executar (após aprovado)
Pergunte a modalidade:
- **Faseado e assistido** — roda por fase, pausa entre fases, mostra parcial. Default
  pra staging sensível ou qualquer passo destrutivo.
- **De uma vez (autônomo)** — paraleliza categorias independentes (multiagentes /
  subagents do Claude Code) e usa watchdog que retoma de checkpoint até concluir.
  Condição de parada explícita (tudo concluído OU falha bloqueante escala pro humano);
  sem retry infinito.

Regras: passo destrutivo só roda se estava no plano aprovado E com o gate de ambiente
(ex.: `<PROJECT>_CHAOS_ALLOW=1`). Autônomo só em dev/staging por default; produção exige
confirmação extra. O plano aprovado é o contrato — multiagente/cron aceleram o como,
não dispensam o o quê foi autorizado.
