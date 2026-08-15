---
description: schematize-zig — força/audita/scaffolda o IAM da casa (identidade≠email, ≥2 fatores, ReBAC multi-tenant, sessão longa/logout irreversível) como app separada em auth.<domain> (auth costuma pedir Rust/Go por fit — registra ADR), ou atualiza um auth existente
argument-hint: "[bootstrap | audit | migrate]"
---

Governe identidade e autorização pelo padrão IAM da casa (`references/iam.md`), no recorte **Zig** (posicionamento honesto: o serviço de auth/cripto costuma encaixar melhor em Rust/Go — fit). Plan-first: **audita, mostra o plano, pede aprovação, então executa.** Use
este comando para **forçar só a parte de IAM** num projeto (novo ou existente) ou
**atualizar/portar um auth legado**.

## 0. Modo
- `audit` — varre o projeto e reporta o gap contra o piso IAM (checklist §iam).
- `bootstrap` — scaffolda o IAM do zero como **app separada** (`<projeto>_auth_zig` — ou Rust/Go por ADR de fit).
- `migrate` — porta um auth legado pro IAM (**prioridade 0**, strangler-fig).

## 1. Topologia primeiro (inegociável)
Confirme/scaffolde que o auth é **aplicação SEPARADA** (`references/iam.md` §1):
- App própria `<projeto>_auth_zig` (ou `_rs`/`_go` por ADR de fit — auth/cripto costuma pedir Rust/Go) + front próprio `<projeto>_authfront`,
  servidos em **`auth.<domain>`** — **VETADO** monolith apensado (nem `internal/auth` do
  serviço principal). **Registre o ADR de fit da linguagem do auth** (`references/iam.md §0`, `references/stack-versoes.md`).
- Repo/deploy/**user Linux + systemd isolados** por conta própria (casa com `ops.md` §3).
- App principal e clientes **delegam por OIDC/OAuth2.1 + PKCE**; a **chave de assinatura só
  no auth**, consumidores validam por **JWKS público** (o PEP cacheia o JWKS). Um serviço **Zig** de produto consome o auth por JWKS como qualquer outro.

## 2. Identidade
- **ID interno imutável** (ULID/UUIDv7) como `sub`; **email/telefone nunca são ID**; **N
  emails** por usuário (incentivado; entidades filhas com `VerifiedAt`, nunca a PK).
  Identificador só vale **verificado**.
- **SSO com recuperação local forçada**; account-linking explícito (anti-takeover).
- **Nudge de email secundário:** detecta provedor e recomenda outro provedor + tooltip "i".

## 3. Fatores (≥2 sempre)
- **Passkey/WebAuthn no núcleo** (lib madura — ecossistema Zig é jovem, considere lib C revisada via `@cImport` com boundary validado, `references/seguranca.md`); TOTP/push;
  **email OTP (Resend) always-on inclusive HML** (só operador desliga); **Twilio** p/
  telefone; providers **plugáveis** (interfaces via vtable/tagged union: `EmailProvider`/`SmsProvider`/
  `PushProvider`, adaptadores na borda).
- **Senha por padrão** (**argon2id** via `std.crypto` ou lib C revisada, CPU-bound fora do loop de I/O, + HIBP), **opcional no seletor**.
- **2º fator forte obrigatório** antes do acesso pleno (bootstrap por email não basta — o
  middleware barra o token de bootstrap fora do enrolamento).
- Invariante de troca: **mutar fator X exige fator Y≠X no maior AAL**; notificar canais;
  remover último fator forte = **atraso cancelável** (job agendado). Recuperação **≥ login**.

## 4. Autorização (multi-tenant, ReBAC)
- **Identidade global, papéis por tenant** (membership). Motor **ReBAC (OpenFGA/SpiceDB)** —
  o auth **fala com o motor via client**, não implementa authz na mão; tuplas
  `(objeto, relação, usuário)`; **RBAC granular** (`recurso:ação`, papéis customizados) +
  **ABAC** (conditional tuples). **PDP = Check API / PEP server-side, deny-default,
  enforcement server-side, token fino, decisão auditada.** Escrita de tupla via outbox
  (nunca dual-write solto).

## 5. Sessão / logout
- **Multi-dispositivo** + **view de remover dispositivos** + "sair de todos" (session store
  Postgres+Redis, 1 linha por sessão com `refresh_family_id`/`device_id`/`jti`).
- **Sessão 7 dias por padrão; pergunta se confiável → 90 dias** (access token curto com
  refresh silencioso rotativo — nada de "15 min e é chutado"). Step-up fresco em ops
  sensível. Refresh opaco (`crypto/rand`), reuso → revoga a **família**.
- **Botão Sair visível → kill IRREVERSÍVEL:** revoga refresh + família, apaga sessão
  server-side, `jti` na **denylist** (Redis/DB, consultada em toda request), desassocia push
  token. Nada recria a sessão.

## 6. Testes (dispare o gate do pentest)
Rode/priorize a rotina agressiva (`schematize-pentest`): **cross-tenant (BOLA/IDOR),
priv-esc (BFLA), abuso de fluxo (bypass 2FA/reset/step-up, replay, refresh reuse, JWT
alg=none/kid, logout que não invalidou)** — gate que trava em vazamento. Ver `/pentest-authz`.

## 7. Migração de legado (modo `migrate`, prioridade 0)
Strangler-fig: dual-run, **re-hash preguiçoso** (→argon2id) no login, mapeia registros →
modelo novo (dedupe emails, cunha IDs ULID/UUIDv7), **força 2º fator no 1º login**, **revoga
sessões legadas**, **re-deriva authz** em tuplas ReBAC (nunca confia na antiga). O auth
migrado nasce app separada (`_zig`/`_rs`/`_go` por ADR de fit). (Legado Node casa com `schematize-node`.)

## 8. Saída
Grave o plano/relatório em `<projeto>_archive/` (§28): topologia (app separada?), gaps do
checklist IAM (`references/iam.md`), plano por fase (F0–F6) e — se `migrate` — o mapa
legado→novo e a ordem de corte. Confirme: auth é app à parte (com ADR de fit da linguagem)? identidade≠email?
≥2 fatores? ReBAC multi-tenant deny-default? sessão longa + logout irreversível? testes
cross-tenant no CI?
