#!/usr/bin/env bash
# install.sh — instala a skill schematize-zig no projeto atual (Claude Code).
#
# Motivo: padronizar a instalação de uma skill normativa do catálogo schematize
# skills, sem passos manuais e sem conflito de comandos entre skills.
# Como funciona: copia o corpo da skill para .claude/skills/schematize-zig/ e instala os
# comandos (já no padrão <slug>-*, globalmente únicos) ACHATADOS em
# .claude/commands/. Idempotente: reexecutar sobrescreve a mesma versão.
# Entrada: \$1 opcional = diretório do projeto alvo (default: diretório atual).
# Saída: .claude/skills/schematize-zig/ e .claude/commands/<slug>-*.md no alvo.
set -euo pipefail

SKILL_NAME="schematize-zig"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${1:-$PWD}"
SKILL_DIR="$DEST/.claude/skills/$SKILL_NAME"
CMD_DIR="$DEST/.claude/commands"

mkdir -p "$SKILL_DIR" "$CMD_DIR"

# Copia o corpo da skill, excluindo os artefatos de distribuição do repo.
if command -v rsync >/dev/null 2>&1; then
  rsync -a --exclude .git --exclude versions --exclude install.sh \
        --exclude README.md --exclude LICENSE "$SRC"/ "$SKILL_DIR"/
else
  ( cd "$SRC" && tar --exclude=.git --exclude=versions --exclude=install.sh \
      --exclude=README.md --exclude=LICENSE -cf - . ) | ( cd "$SKILL_DIR" && tar -xf - )
fi

# Comandos achatados: nomes já são <slug>-* (únicos), convivem sem colidir.
if [ -d "$SKILL_DIR/assets/commands" ]; then
  cp "$SKILL_DIR"/assets/commands/*.md "$CMD_DIR"/ 2>/dev/null || true
fi

echo "✓ $SKILL_NAME instalada em $SKILL_DIR"
echo "✓ comandos em $CMD_DIR (use /<slug>-help para listar)"
