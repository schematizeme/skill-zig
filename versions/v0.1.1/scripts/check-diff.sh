#!/usr/bin/env bash
# check-diff.sh — gate determinístico de padrões (§6, §35, §37) sobre o diff.
# Uso: bash scripts/check-diff.sh [base-ref]   (default: origin/main)
# Sai 1 se achar qualquer violação de PISO; imprime achados com arquivo:linha.
#
# Cobre o que dá pra checar por regex/contagem. O julgamento fino (semântica de
# auth, coerção de tipo, etc.) fica pro /schematize-review com leitura humana/da IA.

set -uo pipefail
BASE="${1:-origin/main}"
FAIL=0
RED=$'\033[0;31m'; YLW=$'\033[0;33m'; GRN=$'\033[0;32m'; RST=$'\033[0m'

# Arquivos de código alterados (exclui exceções da §6).
mapfile -t FILES < <(git diff --name-only "$BASE"...HEAD 2>/dev/null \
  | grep -E '\.(zig|go|rs|ts|tsx|js|mjs|jsx)$' \
  | grep -vE '(_test\.|\.test\.|/migrations/|/generated/|\.gen\.|/mocks?/)' || true)

block() { echo "${RED}✗ BLOQUEIA${RST} $1"; FAIL=1; }
warn()  { echo "${YLW}⚠ ATENÇÃO${RST} $1"; }

echo "== schematize-zig check-diff (base: $BASE) =="

# 1) §6 — tamanho de arquivo em camadas: teto DURO 750 (≤500 útil + ~250 comentário),
#    FLAG (não bloqueia) em >300 de código útil (~400 em observabilidade).
useful_lines() { # conta linhas de código útil: exclui branco e linha só-comentário (aprox multi-linguagem)
  grep -vcE '^[[:space:]]*($|//|#|///|/\*|\*/|\*[^/])' "$1" 2>/dev/null || echo 0
}
is_observ() { echo "$1" | grep -qiE '(observ|telemetr|tracing|/metrics?|metric|instrument|logg?(er|ing)|otel|prometheus|opentelemetry)'; }
for f in "${FILES[@]}"; do
  [[ -f "$f" ]] || continue
  total=$(wc -l < "$f"); useful=$(useful_lines "$f")
  if (( total > 750 )); then
    block "$f: $total linhas (>750 teto duro; ~250 são p/ comentário, ~500 úteis) — quebre por coesão (§6)"
  elif (( useful > 500 )); then
    block "$f: $useful linhas de código útil (>500 teto duro) — quebre por coesão (§6)"
  else
    thr=300; ctx=""
    is_observ "$f" && { thr=400; ctx=" [observabilidade infla ~400]"; }
    (( useful > thr )) && warn "$f: $useful linhas de código útil (>$thr)$ctx — indício de função muito extensa / falta de abstração; FLAG, registre como dívida p/ rever quando prioridades permitirem (§6)"
  fi
done

# 2) §37 — macaquices grep-áveis (padrão -> mensagem)
scan() { # scan "regex" "mensagem"
  local re="$1" msg="$2" hit
  for f in "${FILES[@]}"; do
    [[ -f "$f" ]] || continue
    hit=$(grep -nE "$re" "$f" 2>/dev/null || true)
    [[ -n "$hit" ]] && while IFS= read -r l; do block "$f:${l%%:*} — $msg"; done <<< "$hit"
  done
}
scan 'NEXT_PUBLIC_[A-Z_]*(SECRET|KEY|TOKEN|PASSWORD|PRIVATE)' 'segredo exposto via NEXT_PUBLIC_ (§13.4/§37)'
scan 'rejectUnauthorized:\s*false|InsecureSkipVerify:\s*true|verify\s*=\s*False' 'verificação TLS desabilitada (§37)'
scan 'Math\.random\(\).*(token|secret|session|nonce|reset)' 'Math.random em contexto de segredo — use CSPRNG (§14/§37)'
scan 'eslint-disable.*security|//\s*nolint:.*(gosec|sec)|#\s*nosec' 'desabilitando regra de segurança inline (§37)'
scan 'Access-Control-Allow-Origin["'\'' :]*\*' 'CORS * — allowlist explícita (§37)'
scan '(query|exec|raw)\(\s*[`"'\''].*\$\{|"\s*\+\s*.*(req|input|param|body)' 'possível SQL/comando por concatenação (§10/§37)'
scan 'catch\s*\(\s*\)\s*\{\s*\}|except\s*:\s*pass|catch\s*\{\s*\}' 'erro engolido (§37)'
scan '@ts-ignore|: any\b|interface\{\}' 'tipo silenciado (any/@ts-ignore/interface{}) (§37)'
scan '\.(skip|only)\(|t\.Skip\(|xit\(|@Ignore' 'teste pulado/silenciado (§37)'

# 3) §39 — índice atualizado quando muda funcionalidade
if (( ${#FILES[@]} > 0 )); then
  idx=$(git diff --name-only "$BASE"...HEAD 2>/dev/null | grep -E 'INDEX_(GLOBAL|FUNCTIONS)\.md' || true)
  [[ -z "$idx" ]] && warn "diff mexe em código mas não toca INDEX_*.md — índice atualizado? (§39)"
fi

# 4) §3 — backend novo em PHP
php=$(git diff --name-only "$BASE"...HEAD 2>/dev/null | grep -E '\.php$' || true)
[[ -n "$php" ]] && block "arquivo PHP no diff — PHP é proibido, migrar (§3.2): $php"

echo
if (( FAIL )); then
  echo "${RED}== check-diff: BLOQUEADO ==${RST}"; exit 1
else
  echo "${GRN}== check-diff: OK ==${RST}"; exit 0
fi
