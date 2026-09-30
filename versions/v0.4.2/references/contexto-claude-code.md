# Gestão de Contexto no Claude Code (handoff em sessões longas)

> Parte da skill **schematize-zig**. **É o DONO do handoff de contexto**: o §34.1 do `entrega.md` **da base** (`schematize-engineering`) é o *gatilho* (quando parar e arquivar); o *como* — formato dos dois MDs, hooks, `/compact`, o que entra em cada seção — é aqui, e só aqui. Implementa também a §28 (archive). Conteúdo específico de ferramenta (Claude Code / VS Code) — o princípio normativo está no `entrega.md` **da base** (`schematize-engineering` -> `references/entrega.md` §34.1) — o recorte local deixou de repeti-lo quando virou ponteiro.

## Por que

Em sessão longa o contexto enche e a compactação automática resume de forma lossy — decisões se perdem, a qualidade cai. A regra: **handoff proativo e arquivado antes do teto**, sempre gravado em `<projeto>_archive`.

## O que o Claude Code expõe

- `/context` — detalhamento ao vivo do uso por categoria (system prompt, tools, MCP, mensagens, espaço livre, buffer de autocompact).
- Barra de status — percentual de tokens no rodapé.
- **StatusLine hook** — o único hook que recebe métricas de contexto em tempo real (JSON com campos de `context_window`). É onde se detecta o limite.
- **PreCompact hook** — dispara logo antes de qualquer compactação (manual `/compact` ou automática). Última chance de capturar estado.

Limitação: um hook executa comando de shell, **não** dispara slash command. Então a compactação no ponto escolhido é feita pelo agente (instruído via `CLAUDE.md`) ou por você; o autocompact é só a rede de segurança lá perto do teto.

## Janela e limite

Janela padrão é 200k; modelos de 1M (Fable 5, Opus 4.6+, Sonnet 4.6 variante `[1m]`) chegam a 1.000.000. O limite de handoff é **configurável** via `CTX_THRESHOLD` (default 250000 — ~25% de uma janela de 1M, cedo o bastante pra sobrar espaço pro resumo). Em janela de 200k, ajuste pra algo como 150000.

## Arquitetura (três peças)

1. **StatusLine monitor** (`scripts/hooks/context-monitor.mjs`) — detecta o cruzamento do `CTX_THRESHOLD`, acende um flag visível na barra e grava um backup bruto de segurança em `<projeto>_archive/context/`.
2. **Instrução no `CLAUDE.md`** — ao ver o flag, o Claude **gera os MDs ricos** (`context.md` + `checklist.md`) e roda `/compact`. (O checklist "feito vs aberto" só fica bom escrito pelo modelo.)
3. **PreCompact hook** (`scripts/hooks/precompact-backup.mjs`) — rede de segurança determinística: dump do estado antes de toda compactação, independente de o modelo ter lembrado.

## Instalação

1. Copie `scripts/hooks/context-monitor.mjs` e `scripts/hooks/precompact-backup.mjs` para `.claude/hooks/` do projeto.
2. Configure `.claude/settings.json` (veja `assets/settings.claude.example.json`).
3. Garanta o trecho de gestão de contexto no `CLAUDE.md` da raiz (veja `assets/CLAUDE.md`).
4. Exporte `PROJECT_ARCHIVE=<caminho>/<projeto>_archive/context` e, se quiser, `CTX_THRESHOLD`.

## Verificação importante

Os nomes dos campos do JSON da StatusLine variam por versão do Claude Code. Antes de confiar no número, rode uma vez com `console.error(JSON.stringify(input))` e compare com a saída do `/context` pra confirmar o shape (`used_tokens` / `remaining_percentage` / `total` / `context_window`). Os scripts tratam mais de um formato, mas confirme.

## Comando `/zig-cc` (context compact) — handoff manual sob demanda

No Claude Code, comandos e skills são unificados: ambos criam um `/nome`. Há dois formatos — `.claude/commands/<nome>.md` (legado, mais simples) e `.claude/skills/<nome>/SKILL.md` (recomendado; suporta `/nome` mais invocação autônoma, e aceita o campo `command:` no frontmatter). Uma pasta de skill = um comando, então um `/zig-cc` próprio é um arquivo de comando dedicado.

Bundlado em `assets/commands/zig-cc.md`. Instalação:

1. Copie `assets/commands/zig-cc.md` para `.claude/commands/zig-cc.md` na raiz do projeto.
2. Digite `/zig-cc` na sessão (ou `/zig-cc <foco>` pra direcionar o resumo, via `$ARGUMENTS`).

O `/zig-cc` gera dois MDs em `<projeto>_archive/context/`:
- `<ts>-context.md` — contexto geral até aqui (objetivo, decisões, arquivos tocados, estado, como retomar).
- `<ts>-checklist.md` — `FEITO` detalhado + `EM ABERTO / A FAZER` com próximo passo + `NÃO REFAZER` (anti-repetição).

E então roda `/compact` com foco. Diferença pro automático: o StatusLine/PreCompact é o gatilho **automático** no limite; o `/zig-cc` é o handoff **manual** que você dispara quando quiser fechar um marco. Os dois gravam no mesmo `<projeto>_archive/context/`.

Alternativa em formato skill (auto-invocável além do `/zig-cc`): criar `.claude/skills/zig-cc/SKILL.md` com frontmatter `name`, `description` e `command: /zig-cc`, e o mesmo corpo do `cc.md`.
