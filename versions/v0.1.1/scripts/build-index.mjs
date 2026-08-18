#!/usr/bin/env node
/**
 * build-index.mjs — gera o índice de microfunções (§39) a partir dos
 * doc-comments obrigatórios das funções (§6).
 *
 * Convenção lida (adapte por linguagem): um doc-comment imediatamente acima da
 * função com as linhas:
 *     O quê: <descrição>
 *     Onde:  <onde é usada / prevista>
 *     Efeitos: <opcional>
 * seguido da declaração da função. Emite uma tabela markdown por arquivo.
 *
 * Uso (o índice mora no archive, nunca no root — §28):
 *   node build-index.mjs <dir-de-origem> > <projeto>_archive/index/INDEX_FUNCTIONS.md
 *
 * SCAFFOLD: cobre TS/JS e Go de forma pragmática (regex). Estenda os padrões de
 * declaração (`declRe`) para a sua stack. A ideia é que o índice seja DERIVADO
 * do código comentado, não mantido à mão — CI compara gerado vs commitado.
 */
import fs from "node:fs";
import path from "node:path";

const ROOT = process.argv[2] ?? "src";
const EXTS = new Set([".ts", ".tsx", ".js", ".mjs", ".go", ".rs", ".zig"]);

// Detecta uma declaração de função logo após o doc-comment (best-effort).
// Zig: `pub fn nome(` / `fn nome(` — doc-comment `///` é comentário de linha (branch //).
const declRe = /(?:export\s+)?(?:async\s+)?function\s+(\w+)|(?:func\s+(?:\([^)]*\)\s+)?(\w+))|(?:(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s*)?\()|(?:(?:pub\s+)?fn\s+(\w+)\s*\()/;

function* walk(dir) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (e.name === "node_modules" || e.name.startsWith(".")) continue;
    const p = path.join(dir, e.name);
    if (e.isDirectory()) yield* walk(p);
    else if (EXTS.has(path.extname(e.name))) yield p;
  }
}

function field(block, label) {
  const m = block.match(new RegExp(`${label}\\s*:\\s*(.+)`, "i"));
  return m ? m[1].trim().replace(/\*\/\s*$/, "").trim() : "";
}

const byFile = new Map();
let missing = 0;

for (const file of walk(ROOT)) {
  const lines = fs.readFileSync(file, "utf8").split("\n");
  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].match(declRe);
    if (!m) continue;
    const name = m[1] || m[2] || m[3];
    if (!name) continue;
    // Olha pra trás: existe doc-comment CONTÍGUO terminando logo acima?
    let j = i - 1;
    while (j >= 0 && lines[j].trim() === "") j--;
    let block = "";
    if (j >= 0 && /\*\//.test(lines[j])) {
      // comentário de bloco: sobe até a abertura /* ou /**
      let k = j;
      while (k >= 0 && !/\/\*/.test(lines[k])) k--;
      if (k >= 0) block = lines.slice(k, j + 1).join("\n");
    } else if (j >= 0 && /^\s*\/\//.test(lines[j])) {
      // comentários de linha contíguos //
      let k = j;
      while (k >= 0 && /^\s*\/\//.test(lines[k])) k--;
      block = lines.slice(k + 1, j + 1).join("\n");
    }
    const what = field(block, "O quê") || field(block, "what");
    const where = field(block, "Onde") || field(block, "usedby");
    const fx = field(block, "Efeitos") || field(block, "effects");
    if (!what || !where) missing++;
    const rel = path.relative(process.cwd(), file);
    if (!byFile.has(rel)) byFile.set(rel, []);
    byFile.get(rel).push({ name, what: what || "⚠ SEM DOC", where: where || "⚠ SEM DOC", fx, line: i + 1 });
  }
}

const out = [];
out.push(`# Índice de Microfunções (gerado)`, "");
out.push(`> Gerado por build-index em ${new Date().toISOString()}. Não editar à mão.`, "");
if (missing) out.push(`> ⚠ ${missing} função(ões) sem doc-comment de contexto completo (§6). Corrija na origem.`, "");
for (const [file, fns] of [...byFile].sort()) {
  out.push(`## ${file}`, "");
  out.push(`| Função | O quê | Onde é usada | Efeitos | Linha |`, `|---|---|---|---|---|`);
  for (const f of fns) out.push(`| \`${f.name}\` | ${f.what} | ${f.where} | ${f.fx} | ${f.line} |`);
  out.push("");
}
process.stdout.write(out.join("\n") + "\n");
// exit 1 se houver função sem doc — pra travar em CI (§6, §39)
process.exit(missing > 0 ? 1 : 0);
