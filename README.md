# schematize-zig

> Padrões normativos de engenharia da casa com **Zig** — baixo nível, performance máxima, controle explícito de memória (allocators, sem GC), `comptime`, error unions, interop com C e artefatos estáticos pequenos. Arquitetura, segurança, IAM, testes/pentest, dados, observabilidade, deploy e archive.

Pacote de **skill normativa para [Claude Code](https://claude.com/claude-code)**.
Parte do catálogo **schematize skills** ([skills.schematize.me](https://skills.schematize.me)).

> **Status: beta.** Zig é **pre-1.0** — a skill trata a versão exata do compilador como parte do contrato de build (`references/stack-versoes.md`).

## Instalar

### Última versão (recomendado)

A partir de um clone do repositório:

```bash
git clone https://github.com/schematizeme/skill-zig.git
cd skill-zig && ./install.sh            # instala no projeto atual (diretório corrente)
# ./install.sh /caminho/do/projeto         # ou aponte para outro projeto
```

Ou baixe o `.zip` da última release e descompacte direto em `.claude/skills/`:

```bash
curl -L -o schematize-zig.zip \
  https://github.com/schematizeme/skill-zig/releases/latest/download/skill-zig.zip
unzip schematize-zig.zip -d .claude/skills/
```

### Uma versão específica

Cada versão tem três formas de obter: **(1)** um Release com `.zip` para baixar,
**(2)** uma pasta navegável em `versions/`, e **(3)** uma tag git.

| Versão | Data | Download (.zip) | Pasta navegável | Notas |
|---|---|---|---|---|
| **0.1.0** | 2026-08-15 | [release](https://github.com/schematizeme/skill-zig/releases/download/v0.1.0/skill-zig.zip) | [versions/v0.1.0/](versions/v0.1.0) | [CHANGELOG](CHANGELOG.md) |

```bash
# clonar uma versão exata pela tag:
git clone --branch v0.1.0 https://github.com/schematizeme/skill-zig.git
```

> Todas as versões aparecem na página de **[Releases](https://github.com/schematizeme/skill-zig/releases)**.

## Quando usar Zig (fit, não gosto)

A casa tem um **rol sancionado** (Go/Rust/Elixir/C#/Zig/Ruby no backend) e um **guia de fit**. Escolha **Zig** — com ADR — quando o requisito é **baixo nível / performance máxima com controle manual de memória / interop com C / artefato estático pequeno / embedded / tooling de sistema**. Auth/cripto costuma encaixar melhor em Rust; job de rede simples em Go. Detalhe em `references/arquitetura.md` (§3) e `references/stack-versoes.md`.

## Comandos

Todos prefixados por `zig-` — **sem conflito** com as outras skills na mesma máquina.

| Comando | O que faz |
|---|---|
| `/zig-help` | lista todos os comandos do schematize-zig |
| `/zig-load` | carrega à força todo o corpo normativo e passa a aplicá-lo |
| `/zig-claude` | cria/atualiza o `CLAUDE.md` sempre-on da raiz |
| `/zig-cc` | context compact (handoff no archive + `/compact`) |
| `/zig-handoff` | handoff sem compactar |
| `/zig-qa` | Q.A. plan-first |
| `/zig-review` | gate da DoD/§37 no diff |
| `/zig-iam` | força/audita/scaffolda o IAM da casa |
| `/zig-index` | (re)gera o índice de microfunções (`///`) |
| `/zig-ops` | audita/scaffolda o `<projeto>_ops` |

Digite `/zig-help` dentro do Claude Code para ver a lista completa.

## Conteúdo da skill

- `SKILL.md` — porta de entrada e pisos inegociáveis.
- `references/` — corpo normativo fatiado por domínio (leia o que casa com a tarefa), com `stack-versoes.md` e `memoria-concorrencia.md` específicos de Zig.
- `assets/` — templates (ADR/TASK/RUNBOOK/…), comandos, `CLAUDE.md`, CI, guard de camadas, hooks.
- `scripts/` — andaime de testes, índice e gestão de contexto.
- `skill.toml` — manifesto da skill (slug, nome, versão, descrições).

## Skills irmãs

- [skill-go](https://github.com/schematizeme/skill-go) — backend Go principal.
- [skill-rust](https://github.com/schematizeme/skill-rust) — backend Rust principal (parente sistêmico mais próximo).
- [skill-web](https://github.com/schematizeme/skill-web) — frontend / SEO / performance.

Todas podem ficar habilitadas ao mesmo tempo: os comandos são namespaced por skill
(`zig-*`, `go-*`, `rust-*`, `web-*`). Um sistema real pode ser poliglota — um componente
Zig de performance ao lado de serviços Go/Rust, cada um sob a sua skill e os mesmos pisos.

## Licença

[MIT](LICENSE) © 2026 schematizeme.
