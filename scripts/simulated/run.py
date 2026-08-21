#!/usr/bin/env python3
"""
simulated/run.py — Engine de teste emulado: cruza ROTAS × PERSONAS × INJECTIONS.

Prova, por persona, que 100% das rotas do inventário estão acessíveis para quem
deve e bloqueadas para quem não deve; e que toda rota mutável rejeita injeções
(SQLi/XSS/path-traversal/mass-assignment/type-confusion) com 4xx limpo — nunca
500, nunca eco sem escape, nunca vazamento cross-tenant.

Saídas (em <LOG_DIR>/simulated-<ts>/):
  raw.jsonl    — uma linha por request, evidência completa
  report.md    — humano, seções AUTO (claro) e REVIEW (status inesperado)
  summary.json — totais por categoria + reconciliação de cobertura de rotas

Exit code: 0 se tudo AUTO-passou e a cobertura de rotas foi total; 1 caso haja
REVIEW, rota fantasma (servida mas fora do catalog) ou rota morta (no catalog,
não responde).

Generalize os env vars <P>_* por projeto. Este é um scaffold: complete os TODO.
"""
from __future__ import annotations
import json
import os
import sys
import time
import datetime as dt
import pathlib
import urllib.request
import urllib.error

# --- config ------------------------------------------------------------------
API_BASE = os.environ.get("PROJECT_TEST_API_BASE", "http://127.0.0.1:13000")
LOG_DIR = pathlib.Path(os.environ.get("PROJECT_TEST_LOG_DIR", "./logs"))
MAX_ROUTES = int(os.environ.get("PROJECT_SIM_MAX_ROUTES", "0"))  # 0 = sem limite
SKIP_MUTATIONS = os.environ.get("PROJECT_SIM_SKIP_MUTATIONS", "") == "1"

HERE = pathlib.Path(__file__).resolve().parent

# Personas mínimas (schematize-qa · references/execucao.md). Carregadas de personas.json se existir.
DEFAULT_PERSONAS = {
    "superadmin":   {"token": None, "expected_access": ["public", "auth", "authenticated", "admin", "internal", "import"]},
    "tenant_admin": {"token": None, "expected_access": ["public", "auth", "authenticated", "admin"]},
    "normal_user":  {"token": None, "expected_access": ["public", "auth", "authenticated"]},
}

# Injeções mínimas (matriz simulated — schematize-qa · references/categorias.md). Carregadas de injections.json se existir.
DEFAULT_INJECTIONS = {
    "sqli":            ["' OR 1=1 --", "'; DROP TABLE users CASCADE; --"],
    "xss":             ["<script>alert(1)</script>", "<img src=x onerror=alert(1)>"],
    "path_traversal":  ["../../etc/passwd", "..%2f..%2fetc%2fpasswd"],
    "type_confusion":  ["not-an-int", "1e999", "true", {"nested": "object"}],
    "charset":         ["𝓪𝓫𝓬", "中文", "\u202eRTL", "a\x00b", "\u200b"],
    "mass_assignment": [{"is_admin": True, "tenant_id": "other", "password_hash": "x"}],
}


def load_json(name, default):
    p = HERE / name
    if p.exists():
        return json.loads(p.read_text())
    return default


def load_route_catalog():
    """Inventário de rotas. TODO: gere a partir do OpenAPI ou do dispatcher.
    Formato esperado: [{"method","path","category","mutates"(bool)}]."""
    cat = load_json("routes.json", None)
    if cat is None:
        print("AVISO: routes.json ausente — gere o catalog do OpenAPI/dispatcher.",
              file=sys.stderr)
        cat = []
    if MAX_ROUTES:
        cat = cat[:MAX_ROUTES]
    return cat


def served_routes():
    """Rotas SERVIDAS de verdade, para reconciliar contra o catalog (rota fantasma).

    Fontes, em ordem: (1) `PROJECT_SIM_SERVED_URL` ou `<API_BASE>/openapi.json` — documento
    OpenAPI servido pelo próprio alvo; (2) `served.json` ao lado deste script, no mesmo formato
    do catalog. Devolve (conjunto_de_rotas, origem) ou (None, motivo) quando NÃO foi possível
    descobrir — e nesse caso o run REPROVA, em vez de dar cobertura total por omissão (A1).
    """
    url = os.environ.get("PROJECT_SIM_SERVED_URL") or (API_BASE.rstrip("/") + "/openapi.json")
    code, text, _ = request("GET", "", token=None, body=None, absolute=url)
    if code == 200:
        try:
            doc = json.loads(text)
            paths = doc.get("paths", {})
            if paths:
                out = {(m.upper(), p) for p, ops in paths.items()
                       for m in ops if m.lower() in ("get", "post", "put", "patch", "delete", "head", "options")}
                return out, f"OpenAPI em {url}"
        except (ValueError, AttributeError):
            pass
    local = load_json("served.json", None)
    if local:
        return {(r["method"].upper(), r["path"]) for r in local}, "served.json"
    return None, (f"nenhuma fonte de rotas servidas: {url} não devolveu OpenAPI utilizável "
                  "e served.json não existe. Defina PROJECT_SIM_SERVED_URL ou crie served.json.")


def request(method, path, token=None, body=None, absolute=None):
    url = absolute if absolute else API_BASE.rstrip("/") + path
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            code, text = r.status, r.read(8192).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        code, text = e.code, e.read(8192).decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001 — conexão/timeout vira evidência, não crash
        code, text = 0, f"__error__ {e}"
    return code, text, round((time.time() - t0) * 1000)


def classify(category, persona, code, body, injected, personas):
    """Retorna ('AUTO'|'REVIEW', motivo).

    `personas` é o dicionário CARREGADO (personas.json quando existe), nunca a constante
    DEFAULT_PERSONAS: consultar a constante fazia toda persona customizada cair em
    expected_access=[] e transformava todo 200 legítimo em suspeita de vazamento (A4).
    """
    if code >= 500:
        return "REVIEW", "5xx por input — validação não barrou antes do core"
    if injected and isinstance(injected, str) and injected in body:
        return "REVIEW", "payload refletido sem escape (possível XSS)"
    if persona not in personas:
        return "REVIEW", f"persona '{persona}' sem contrato de acesso — não dá para julgar"
    allowed = category in personas.get(persona, {}).get("expected_access", [])
    if allowed and code in (401, 403):
        return "REVIEW", f"{persona} deveria acessar {category} mas levou {code}"
    if not allowed and code == 200:
        return "REVIEW", f"{persona} NÃO deveria acessar {category} e levou 200 (vazamento?)"
    return "AUTO", "ok"


def main():
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d-%H%M%S")
    out = LOG_DIR / f"simulated-{ts}"
    out.mkdir(parents=True, exist_ok=True)

    personas = load_json("personas.json", DEFAULT_PERSONAS)
    injections = load_json("injections.json", DEFAULT_INJECTIONS)
    catalog = load_route_catalog()

    raw_fh = (out / "raw.jsonl").open("w")
    reviews, autos = [], 0
    tested_paths = set()
    responded_paths = set()   # rota que deu QUALQUER resposta HTTP (mesmo 401/403/404 do servidor)

    for route in catalog:
        method, path = route["method"], route["path"]
        category = route.get("category", "authenticated")
        mutates = route.get("mutates", method in ("POST", "PUT", "PATCH", "DELETE"))
        tested_paths.add((method, path))

        for persona, pdata in personas.items():
            token = pdata.get("token")
            # 1) acesso "limpo": acessibilidade + isolamento
            code, body, ms = request(method, path, token=token)
            # code 0 = falha de conexão; 404 em TODAS as personas = rota que o servidor não tem.
            if code not in (0, 404):
                responded_paths.add((method, path))
            verdict, why = classify(category, persona, code, body, None, personas)
            rec = {"route": f"{method} {path}", "category": category,
                   "persona": persona, "kind": "access", "code": code,
                   "ms": ms, "verdict": verdict, "why": why}
            raw_fh.write(json.dumps(rec) + "\n")
            (reviews.append(rec) if verdict == "REVIEW" else None)
            autos += verdict == "AUTO"

            # 2) injeções (só em rota mutável, se não for SKIP_MUTATIONS)
            if mutates and not SKIP_MUTATIONS:
                for inj_name, payloads in injections.items():
                    for p in payloads:
                        body_payload = p if isinstance(p, dict) else {"q": p}
                        code, body, ms = request(method, path, token=token, body=body_payload)
                        injected = p if isinstance(p, str) else None
                        verdict, why = classify(category, persona, code, body, injected, personas)
                        rec = {"route": f"{method} {path}", "category": category,
                               "persona": persona, "kind": f"inj:{inj_name}",
                               "code": code, "ms": ms, "verdict": verdict, "why": why}
                        raw_fh.write(json.dumps(rec) + "\n")
                        (reviews.append(rec) if verdict == "REVIEW" else None)
                        autos += verdict == "AUTO"
    raw_fh.close()

    # --- reconciliação de cobertura (MUST — schematize-qa · references/categorias.md) -----------------------------
    catalog_paths = {(r["method"], r["path"]) for r in catalog}
    not_exercised = sorted(catalog_paths - tested_paths)      # no catalog e nem chegou a ser chamada
    # Rota MORTA: está no catalog, foi exercida e o servidor não a serve em nenhuma persona.
    dead = sorted((catalog_paths & tested_paths) - responded_paths) + not_exercised
    # Rota FANTASMA: servida pelo alvo e ausente do catalog. Sem fonte de descoberta NÃO existe
    # reconciliação — e a ausência de dado passa a REPROVAR, nunca a dar cobertura total (A1).
    served, served_origem = served_routes()
    if served is None:
        ghost = []
        ghost_status = f"INDISPONIVEL — {served_origem}"
    else:
        ghost = sorted(served - catalog_paths)
        ghost_status = f"reconciliado por {served_origem} ({len(served)} rotas servidas)"

    summary = {
        "started_at": ts,
        "api_base": API_BASE,
        "routes_in_catalog": len(catalog_paths),
        "routes_tested": len(tested_paths),
        "dead_routes": dead,
        "ghost_routes": ghost,
        "ghost_reconciliation": ghost_status,
        "totals": {"auto": autos, "review": len(reviews)},
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2))

    # --- report.md -----------------------------------------------------------
    lines = [f"# Simulated — {ts}", "",
             f"- API: `{API_BASE}`",
             f"- Rotas no catalog: {len(catalog_paths)} · testadas: {len(tested_paths)}",
             f"- AUTO: {autos} · REVIEW: {len(reviews)}", ""]
    lines += [f"- Reconciliação de rota fantasma: {ghost_status}", ""]
    if dead:
        lines += ["## Rotas mortas (no catalog, não responderam)", ""]
        lines += [f"- `{m} {p}`" for m, p in dead] + [""]
    if ghost:
        lines += ["## Rotas fantasma (servidas, fora do catalog)", ""]
        lines += [f"- `{m} {p}`" for m, p in ghost] + [""]
    lines += ["## REVIEW (status inesperado — olho humano)", ""]
    if reviews:
        for r in reviews:
            lines.append(f"- `{r['route']}` · {r['persona']} · {r['kind']} → {r['code']} — {r['why']}")
    else:
        lines.append("_nenhum — tudo AUTO._")
    (out / "report.md").write_text("\n".join(lines) + "\n")

    # Cobertura TOTAL exige reconciliação FEITA. `served is None` (sem fonte) não pode virar
    # "sem rota fantasma": era exatamente o verde vacuamente verdadeiro do A1.
    full_coverage = (len(catalog_paths) > 0 and len(dead) == 0
                     and served is not None and len(ghost) == 0)
    ok = (len(reviews) == 0) and full_coverage
    print(f"simulated: AUTO={autos} REVIEW={len(reviews)} "
          f"dead={len(dead)} ghost={len(ghost)} ({ghost_status}) "
          f"cobertura={'total' if full_coverage else 'INCOMPLETA'} → {out}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
