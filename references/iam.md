# IAM — Identidade e Autorização da casa (piso inegociável) — recorte Zig

Piso normativo de **identidade, autenticação e autorização**, válido para toda skill da
casa. **Todo projeto começa com um IAM robusto por desenho** — segurança é inegociável.
Este arquivo é o recorte **Zig** do modelo agnóstico
(`schematize-engineering/references/iam.md`): mantém **todas as regras normativas** e as
concretiza na topologia de serviço e nos idiomas Zig. Liga com `references/seguranca.md`
(boundary C, build mode, CSPRNG, cripto), `references/memoria-concorrencia.md` (allocator,
limites), `references/arquitetura.md §3` (fit de linguagem) e `references/stack-versoes.md`.
Scaffold/auditoria por **`/zig-iam`**; testes adversariais na **schematize-pentest**.

Princípios-âncora: **separar identidade de autorização**; **nunca menos de 2 fatores**
(senha + Email OTP **já conta** como 2FA baseline — fator forte é incentivado e just-in-time,
**nunca muro pré-login**); **força adaptável ao risco** (2FA→3FA + negação deceptiva sob
suspeita); **recuperação tão forte quanto o login**; **deny-by-default**; **enforcement sempre
no servidor**. O buraco clássico é ter 2FA no login e um reset por 1 email que passa por
cima — aqui isso é vetado.

## 0. Posicionamento honesto — auth/cripto muitas vezes encaixa melhor em Rust/Go

**Antes de escrever uma linha de auth em Zig, decida a linguagem com honestidade** (fit guide,
`references/arquitetura.md §3`):

- O serviço de **auth/cripto** é o caso onde **segurança de memória por default** e um
  **ecossistema maduro** (WebAuthn, OIDC server, argon2, clients ReBAC) pesam mais que
  controle manual. Em Zig esse ecossistema é **jovem**. Portanto:
  - **(a) Se o auth em si é o serviço**, o default honesto é **Rust ou Go** — **mesmo num
    sistema majoritariamente Zig**. A escolha de fazer o auth em Rust/Go dentro de um
    ecossistema Zig **registra ADR de fit** e é a recomendação da casa.
  - **(b) Se optar por Zig no auth** (requisito real de **interop C** ou **artefato
    pequeno/sem runtime**), **o piso deste arquivo vale IGUAL** — nada afrouxa. O que muda é
    reconhecer o **custo** (validação de boundary C, cripto por lib revisada, ecossistema
    jovem) e **registrá-lo no ADR**. Cumpra §Z (boundary/validação) de `references/seguranca.md`
    com rigor extra.
- **Um serviço Zig de produto** (não-auth) **consome** o auth por **JWKS público**, como
  qualquer outro cliente da casa — isso é **sempre válido e barato**, independentemente da
  linguagem do IdP. É o caminho comum: produto em Zig, IdP em Rust/Go.

> A regra de ouro: **o piso NUNCA afrouxa; o que muda é o custo e o ADR que o assume.**

## 1. Topologia — auth é uma APLICAÇÃO SEPARADA

- **A autenticação é um serviço próprio, com link próprio e front próprio**, servido em
  **`auth.<domain>`**. **VETADO** apensar o auth ao escopo principal como monolith (nem como
  um módulo `auth/` do serviço principal).
- **Auth como app separada** — se em Zig, **`<projeto>_auth_zig`**; se o ADR de fit (§0)
  apontar Rust/Go, `<projeto>_auth_rs`/`_go` — **+ front de auth** próprio
  (`<projeto>_authfront`), com **repo, deploy, user Linux e systemd/container isolados**
  (casa com o isolamento por app do `ops.md` §3). Comprometer o app principal **não**
  compromete o IdP. O binário do auth é o **único** que carrega a chave privada de assinatura
  e os segredos de provedor (Resend/Twilio/OAuth) — que vêm de secret manager/env, **nunca**
  hardcoded nem por `@embedFile` (`references/seguranca.md §Z.5`).
- **O app principal (e todo cliente) delega ao auth por OIDC/OAuth2.1 + PKCE:** redireciona
  pra `auth.<domain>`, recebe tokens de volta. O serviço de auth é o **IdP da casa**
  (self-hosted, consumido por N apps) — expõe os endpoints padrão (`/authorize`, `/token`,
  `/introspect`, `/revoke`, `/.well-known/openid-configuration`, `/.well-known/jwks.json`).
- **Chave de assinatura de token vive SÓ no serviço de auth.** Consumidores (inclusive um
  **serviço de produto em Zig**) validam por **JWKS público** cacheado — **nunca** guardam a
  chave privada. A assinatura JWT (Ed25519/EdDSA ou RS256) só acontece dentro do auth; a
  rotação de chave é publicada via `kid` no JWKS.

## 2. Modelo de identidade

- **ID interno imutável e opaco** (ULID/UUIDv7) é o `sub`. **Email e telefone NUNCA são ID**
  — são *identificadores* ligados ao usuário, cada um com estado de verificação. Em Zig, o
  agregado `User` tem `id` opaco (16 bytes / string opaca); `email`/`phone` são registros
  filhos com `verified_at: ?i64`, **nunca** a PK. No schema (Postgres): `users(id)` +
  `identifiers(user_id, kind, value, verified_at)` 1..N.
- **Identificadores 1..N por usuário** (emails, telefones, identidades SSO, passkeys, apps,
  chaves FIDO2). **Ter mais de um email é incentivado** (resiliência a brick de provedor).
- **Identificador só vale verificado** — não loga nem recupera sem verificação (`verified_at`
  não-nulo).
- **SSO nunca é ponto único de falha:** cadastro via SSO **força ≥1 fator de recuperação
  local** (email de recuperação + códigos de backup), pra provedor banido ≠ conta perdida.
- **Account-linking explícito:** SSO chegando com email já verificado em outra conta →
  linkar vs. bloquear **com confirmação** (anti-takeover). Nunca linkar por email não
  verificado.
- **Nudge de email secundário (anti-brick):** com só 1 email, a UI **sugere adicionar um
  secundário**. **Detecta o provedor** do atual (gmail / hotmail-outlook / yahoo /
  próprio-corporativo) e **recomenda que o secundário seja preferencialmente de OUTRO
  provedor**, com um **"i" de tooltip no hover**: *"Um segundo email, de preferência em outro
  provedor, garante que você não perca o acesso caso perca acesso a este email."* Sugestão,
  não obrigação. (Regra do domínio, exposta pelo auth ao `authfront`.)

## 3. Fatores e níveis de garantia (AAL — NIST 800-63B)

Classificar a **força** de cada fator permite "email sempre disponível" sem abrir mão de
segurança: operação sensível exige fator forte; email/SMS servem de fallback.

| Tier | Fatores | Uso |
|---|---|---|
| **Alto (phishing-resistant)** | **Passkey/WebAuthn (núcleo)**, chave FIDO2, push aprovado no app | Ops sensíveis: trocar fator, admin, cross-tenant, billing, recuperação |
| **Médio** | TOTP (app autenticador), senha + posse | Login + 2º fator |
| **Baixo (fallback)** | **Email OTP (Resend)**, **SMS/voz (Twilio)** | **É o 2º fator baseline da conta** (senha+OTP = 2FA); sempre disponível; **não** autoriza ação sensível sozinho (aí exige step-up forte) |

- **Passkey/WebAuthn é núcleo** (não roadmap): já é "2 fatores num" (dispositivo + biometria),
  phishing-resistant. Em Zig o ecossistema WebAuthn é **jovem** — use lib Zig madura quando
  existir, ou **lib C revisada via `@cImport`** com o **boundary validado**
  (`references/seguranca.md §Z.4`); se o custo pesar, é sinal para reavaliar o fit (§0).
- **Email OTP (Resend) ligado por padrão, inclusive em HML** — só o operador desliga.
  **Ligado ≠ entregando pra fora:** em `prd` o provider é o real; **fora de `prd` o default é
  o SINK** e o guard recusa destinatário fora do domínio de teste (§3.1) — o fluxo de OTP é
  exercido ponta-a-ponta lendo o código do sink, nunca de uma caixa real.
- **Twilio por padrão** para verificação de telefone e 2FA por SMS/voz.
- **Provedores plugáveis como interfaces Zig:** o core depende de uma **abstração**, não do
  SDK concreto. Em Zig, modele o provider como **interface via vtable** (struct com ponteiros
  de função + `*anyopaque`) ou **tagged union** de implementações:
  ```zig
  pub const EmailProvider = struct {
      ptr: *anyopaque,
      sendOtpFn: *const fn (ptr: *anyopaque, to: []const u8, code: []const u8) anyerror!void,
      pub fn sendOtp(self: EmailProvider, to: []const u8, code: []const u8) !void {
          return self.sendOtpFn(self.ptr, to, code);
      }
  };
  ```
  `EmailProvider` (Resend default), `SmsProvider` (Twilio default) e `PushProvider` são
  **trocáveis por config/wiring** sem tocar no core (adaptadores na borda, DDD). Chamadas de
  rede tratam **timeout, retry+backoff+jitter e store-and-forward** em falha; toda alocação
  segue o allocator + limite (`references/memoria-concorrencia.md`).
- **Senha por padrão, opcional por escolha:** o usuário **cria senha no cadastro** (padrão
  cultural; **argon2id** — via `std.crypto` quando disponível, ou **lib C revisada por
  `@cImport`** com boundary validado — + verificação contra base de vazadas/HIBP por
  k-anonymity), mas o **seletor de modos de autenticação permite marcá-la como opcional** e
  viver de passkey/OTP/app. O hashing argon2id é **CPU-bound**: rode-o **fora do caminho que
  serve I/O** (thread pool / job dedicado — `references/memoria-concorrencia.md`), nunca
  bloqueando o event loop.
- **CSPRNG obrigatório** para OTP, `jti`, refresh, salt e nonce — `std.crypto.random` / fonte
  segura, **nunca** PRNG previsível (`references/seguranca.md §Z.6`). Comparação de OTP/hash em
  **tempo constante** (§Z.7).
- **2FA por desenho desde o cadastro — senha + Email OTP JÁ é 2FA (fraco, porém válido):**
  a conta **nasce com dois fatores obrigatórios** (senha + código no email verificado,
  always-on) e **já é segura para o baseline**. **VETADO** tratar senha+OTP como "sem 2FA" e
  **barrar o login** até enrolar um fator forte — é o **círculo infinito**. O middleware/PEP
  de sessão **libera o acesso baseline** com a sessão de AAL médio (senha+OTP); **não** barra
  todas as rotas exigindo AAL alto.
- **Fator forte é INCENTIVADO + just-in-time, nunca muro pré-login:** app OTP / passkey / chave
  são **nudge** e **exigidos só na operação sensível** (o PEP checa o AAL mínimo **por rota
  sensível** e dispara **step-up** ali) e **escalados sob risco** (§9). Enrolar um fator forte
  usa o Email OTP como verificação (Y≠X, §4): sem deadlock. A ausência de fator forte **degrada
  o que é sensível** (`403 step_up_required`), não **bloqueia o baseline**.

### 3.1 Efeito externo fora de `prd` — SINK por default e guard DENTRO do provider

O OTP é o fluxo que **mais amplifica envio**: um seed de 5.000 contas dispara 5.000 e-mails. Por
isso **ligado ≠ entregando pra fora**. Em `prd` o `EmailProvider` é o real (sem chave, o serviço
**recusa subir** — não cai no logger silencioso); em **qualquer outro ambiente** o default é o
**SINK** (Mailpit/log, lido pelo teste) e o **guard mora DENTRO do provider** — chamador esquece,
provider não. O porquê (bounce/complaint em massa queima IP e domínio e **derruba o OTP de
produção**, com semanas de warm-up e utilidade zero) e as 4 camadas estão na normativa:
`schematize-engineering` → `references/efeitos-externos.md`. Aqui vai só o **recorte Zig**.

Como a interface já é **vtable** (§3), o guard é **outro `EmailProvider`** que envelopa o de
dentro — composição, sem herança e sem `comptime` mágico. A recusa é **error union**
(`error{ExternalRecipientBlocked}`), tratada com `try`/`expectError`: **VETADO** `catch {}`,
`catch unreachable` ou `_ = send(...)` em cima dela (piso "erro nunca engolido").

```zig
//! src/notify/email.zig — provider, sink e guard moram JUNTOS: nenhum chamador
//! escolhe para onde o e-mail vai. A escolha é da composição (`wire`), por ambiente.
const std = @import("std");

/// Erros de envio. `ExternalRecipientBlocked` é erro de PROGRAMAÇÃO (aparece no
/// teste e no CI, com mensagem acionável), não erro do usuário.
pub const SendError = error{
    ExternalRecipientBlocked,
    RunCapExceeded,
    AddressTooLong,
};

/// Ambiente. Fail-closed: só a string exata "prd" liga o envio real; ausente,
/// vazia ou desconhecida vira `.dev` — o modo SEGURO.
pub const Env = enum {
    dev,
    hml,
    prd,

    pub fn parse(raw: ?[]const u8) Env {
        const s = raw orelse return .dev;
        if (std.mem.eql(u8, s, "prd")) return .prd;
        if (std.mem.eql(u8, s, "hml")) return .hml;
        return .dev;
    }

    /// Lê `APP_ENV` do processo. Variável ausente/ilegível ⇒ `.dev` (não-prd).
    pub fn fromProcess(alloc: std.mem.Allocator) Env {
        const raw = std.process.getEnvVarOwned(alloc, "APP_ENV") catch return .dev;
        defer alloc.free(raw);
        return Env.parse(raw);
    }
};

/// Interface do provider (vtable): o core depende DISTO, nunca do SDK concreto.
pub const EmailProvider = struct {
    ptr: *anyopaque,
    vtable: *const VTable,

    pub const VTable = struct {
        sendOtp: *const fn (ptr: *anyopaque, to: []const u8, code: []const u8) anyerror!void,
    };

    pub fn sendOtp(self: EmailProvider, to: []const u8, code: []const u8) anyerror!void {
        return self.vtable.sendOtp(self.ptr, to, code);
    }
};

/// Domínios aceitos fora de `prd`. O 1º é o `test.<domain>` da casa (null MX +
/// SPF `-all` + DMARC `p=reject`); os demais são os TLDs reservados da
/// RFC 2606/6761, que não resolvem em lugar nenhum do mundo.
pub const default_test_domains: []const []const u8 = &.{
    "test.acme.com", // TROCAR pelo test.<domain> do projeto
    "test",
    "invalid",
    "example",
    "example.com",
};

/// SINK — default fora de `prd`. Não abre socket para fora: registra o envio
/// (ou entrega no Mailpit local) para o teste LER o código do OTP.
pub const SinkProvider = struct {
    sent: usize = 0,
    last_to: [254]u8 = undefined,
    last_to_len: usize = 0,

    const vtable = EmailProvider.VTable{ .sendOtp = sendOtp };

    pub fn provider(self: *SinkProvider) EmailProvider {
        return .{ .ptr = self, .vtable = &vtable };
    }

    /// Último destinatário sinkado — o teste assere sobre isto, não sobre caixa real.
    pub fn lastTo(self: *const SinkProvider) []const u8 {
        return self.last_to[0..self.last_to_len];
    }

    fn sendOtp(ptr: *anyopaque, to: []const u8, code: []const u8) anyerror!void {
        const self: *SinkProvider = @ptrCast(@alignCast(ptr));
        if (to.len > self.last_to.len) return SendError.AddressTooLong;
        @memcpy(self.last_to[0..to.len], to);
        self.last_to_len = to.len;
        self.sent += 1;
        std.log.debug("mail sink: to={s} code={s}", .{ to, code });
    }
};

/// GUARD — envelopa QUALQUER `EmailProvider` e é o único ponto de saída.
/// Deny-by-default: fora de `prd`, só o domínio de teste passa; e conta.
pub const GuardedProvider = struct {
    inner: EmailProvider,
    env: Env,
    test_domains: []const []const u8 = default_test_domains,
    /// Teto por execução (`MAIL_MAX_PER_RUN`, default 50). Só vale fora de `prd`
    /// — produção entrega o volume real.
    max_per_run: usize = 50,
    sent: usize = 0,

    const vtable = EmailProvider.VTable{ .sendOtp = sendOtp };

    pub fn provider(self: *GuardedProvider) EmailProvider {
        return .{ .ptr = self, .vtable = &vtable };
    }

    fn sendOtp(ptr: *anyopaque, to: []const u8, code: []const u8) anyerror!void {
        const self: *GuardedProvider = @ptrCast(@alignCast(ptr));
        try self.assertDeliverable(to);
        if (self.env != .prd) {
            if (self.sent >= self.max_per_run) {
                std.log.err(
                    "cap de envio estourado (max_per_run={d}, env={s}): laço de teste em massa. Abortando.",
                    .{ self.max_per_run, @tagName(self.env) },
                );
                return SendError.RunCapExceeded;
            }
            self.sent += 1; // conta a TENTATIVA: falha do provider não zera o teto
        }
        try self.inner.sendOtp(to, code);
    }

    /// Deny-by-default, com mensagem que ensina o caminho certo.
    fn assertDeliverable(self: *const GuardedProvider, to: []const u8) SendError!void {
        if (self.env == .prd) return; // produção entrega de verdade
        if (self.isTestRecipient(to)) return;
        std.log.err(
            "bloqueado: destinatario externo '{s}' com env={s}. Use " ++
                "<papel>+<run-id>-<n>@test.<domain> ou registre o ADR de excecao " ++
                "(allowlist <=5 + cap + janela + subdominio). Nada foi enviado.",
            .{ to, @tagName(self.env) },
        );
        return SendError.ExternalRecipientBlocked;
    }

    fn isTestRecipient(self: *const GuardedProvider, to: []const u8) bool {
        const at = std.mem.lastIndexOfScalar(u8, to, '@') orelse return false;
        const domain = to[at + 1 ..];
        if (domain.len == 0) return false;
        for (self.test_domains) |allowed| {
            if (std.ascii.eqlIgnoreCase(domain, allowed)) return true;
            // subdomínio do domínio de teste: "mx.test.acme.com" casa com "test.acme.com"
            if (domain.len > allowed.len + 1 and
                domain[domain.len - allowed.len - 1] == '.' and
                std.ascii.eqlIgnoreCase(domain[domain.len - allowed.len ..], allowed))
            {
                return true;
            }
        }
        return false;
    }
};

/// Composição (bootstrap/`main`): a seleção por ambiente acontece UMA vez, aqui.
/// O guard envelopa SEMPRE — inclusive em `prd`, onde ele só conta e audita.
/// `real` é o adaptador Resend/SES, construído só quando `env == .prd`.
pub fn wire(
    env: Env,
    sink: *SinkProvider,
    real: EmailProvider,
    guard: *GuardedProvider,
    max_per_run: usize,
) EmailProvider {
    guard.* = .{
        .inner = if (env == .prd) real else sink.provider(),
        .env = env,
        .max_per_run = max_per_run,
    };
    return guard.provider();
}

/// `MAIL_MAX_PER_RUN` com default 50. Valor ausente/ilegível ⇒ default (fail-closed).
pub fn capFromEnv(alloc: std.mem.Allocator) usize {
    const raw = std.process.getEnvVarOwned(alloc, "MAIL_MAX_PER_RUN") catch return 50;
    defer alloc.free(raw);
    return std.fmt.parseInt(usize, raw, 10) catch 50;
}

test "guard recusa destinatário externo" {
    var sink = SinkProvider{};
    var guard = GuardedProvider{ .inner = sink.provider(), .env = .hml };
    const mail = guard.provider();

    // O vermelho que precisa existir: caixa real, fora do domínio de teste, em hml.
    try std.testing.expectError(
        SendError.ExternalRecipientBlocked,
        mail.sendOtp("alguem@gmail.com", "123456"),
    );
    try std.testing.expectEqual(@as(usize, 0), sink.sent); // NADA saiu do processo

    // O endereço canônico da casa passa e cai no sink.
    try mail.sendOtp("login+run42-1@test.acme.com", "123456");
    try std.testing.expectEqual(@as(usize, 1), sink.sent);
    try std.testing.expectEqualStrings("login+run42-1@test.acme.com", sink.lastTo());
}

test "cap por execução aborta antes de virar 5.000" {
    var sink = SinkProvider{};
    var guard = GuardedProvider{ .inner = sink.provider(), .env = .dev, .max_per_run = 2 };
    const mail = guard.provider();

    try mail.sendOtp("a+run7-1@test.acme.com", "111111");
    try mail.sendOtp("b+run7-2@test.acme.com", "222222");
    try std.testing.expectError(
        SendError.RunCapExceeded,
        mail.sendOtp("c+run7-3@test.acme.com", "333333"),
    );
    try std.testing.expectEqual(@as(usize, 2), sink.sent);
}

test "env ausente ou desconhecido NÃO vira produção" {
    try std.testing.expectEqual(Env.dev, Env.parse(null));
    try std.testing.expectEqual(Env.dev, Env.parse(""));
    try std.testing.expectEqual(Env.dev, Env.parse("production")); // só "prd" liga o real
    try std.testing.expectEqual(Env.prd, Env.parse("prd"));
}
```

**O que isso trava, e o que ainda é sua responsabilidade:**

| Regra | Onde está no código |
|---|---|
| Guard **dentro** do provider, não no chamador | `GuardedProvider.sendOtp` → `assertDeliverable` antes de qualquer I/O |
| Sink default fora de `prd`, escolha **uma vez** | `wire()` na composição; nenhum use-site instancia o adaptador real |
| Fail-closed | `Env.parse`/`Env.fromProcess`: ausente/ilegível ⇒ `.dev`; `capFromEnv` volta ao default |
| Cap por execução + abort | `max_per_run` + `SendError.RunCapExceeded` (conta a tentativa, não o sucesso) |
| Recusa é **erro**, não warning | error union `SendError`; **VETADO** `catch {}`/`catch unreachable` no call-site |
| Destinatário sintético em rota nula | `default_test_domains` (o `test.<domain>` + TLDs RFC 2606/6761) |

- **Fixture/seed/`simulated`:** todo endereço gerado é `<papel>+<run-id>-<n>@test.<domain>`.
  **VETADO** `@gmail.com`/`@hotmail.com`, domínio de terceiro, e-mail de pessoa real (inclusive o
  seu) e o domínio de produção — em qualquer `.zig` de teste, seed ou script.
- **`SmsProvider` (Twilio) e `PushProvider` seguem o MESMO desenho** — mesma vtable, mesmo guard,
  mesmo cap (SMS custa por unidade: o cap importa mais, não menos).
- **Chave de não-prd é sandbox**, nunca a de produção; egress SMTP (25/465/587) bloqueado em
  dev/hml (`references/ops.md`, `schematize-infra`).

## 4. Fluxos

**Onboarding:** cita um email → **verifica** → **cria senha** (ou já passkey/app) → **pronto:
2FA baseline (senha + Email OTP) e acesso baseline pleno**. Só **depois**, já dentro, o sistema
**sugere** (nudge, não obriga) reforçar: 2º email de backup + fator forte. **Nunca se barra o
acesso por não ter fator forte** — ele é pedido *just-in-time* na 1ª ação sensível (step-up)
ou sob risco (§9).

**Login:** (1) sem app de 2FA ativo → **OTP por email** (mesmo sem nada habilitado); (2) com
app → **pergunta app ou email**; (3) com vários fatores (passkey/telefone/app) → **lista todos
e o usuário escolhe** qual usar. App = push-approval ou TOTP.

**Gestão de fator — invariante único:**
> **Para mutar o fator X, apresente um fator Y ≠ X, no maior AAL disponível.**
- Desativar/trocar **app** → verifica por **email** (ou outro ≠ app).
- Trocar/adicionar **email complementar** → exige o **app**.
- Add/remover **chave ou telefone** → mesmo princípio, **lista qual usar**.
- Toda mudança **notifica todos os canais verificados**; remover o **último fator forte** =
  **ação com atraso cancelável** (janela pra abortar se for ataque) — job agendado que só
  efetiva após a janela, cancelável até disparar.

**Recuperação:** múltiplos caminhos independentes (vários emails, códigos de backup offline,
telefone). **Força ≥ login** (2 fatores ou processo com atraso + revisão), rate-limit
agressivo, tudo auditado. **Reset nunca é bypass de 1 fator.**

## 5. Multi-tenant + RBAC/ABAC — motor ReBAC (estilo Zanzibar)

- **Identidade global, autorização por tenant:** um usuário (1 identidade) pertence a **N
  tenants** via **membership**, com papéis **diferentes por tenant**.
- **Motor de relação (ReBAC), ex. OpenFGA/SpiceDB** — hand-rolar authz em Zig é onde vazam
  privilégios. O serviço Zig **não implementa o motor**: fala com o OpenFGA/SpiceDB via client
  gRPC/HTTP (lib madura, ou C interop com boundary validado — §Z.4). Autorização em **tuplas**
  `(objeto, relação, usuário/userset)`:
  - `tenant:acme#member@user:01H…`
  - `role:acme/finance-approver#assignee@user:01H…`
  - `invoice:987#parent@tenant:acme` (recurso parenteado ao tenant)
  - permissão computada por *relation rewrite* (member do tenant **E** assignee de papel que
    concede a permissão).
  - **Escrita de tuplas** (conceder/revogar papel, criar membership) passa por um caso de uso
    do auth que chama o `Write` do motor **transacionalmente com o outbox** — nunca dual-write
    solto.
- **RBAC granular:** permissão = **`recurso:ação`** (`invoice:approve`, `user:invite`);
  papéis-padrão (owner/admin/member/viewer) **+ papéis 100% customizados e granulares por
  tenant** (viram relations/usersets). Deve ser possível criar cargos extremamente granulares
  e atribuí-los.
- **ABAC por cima:** condições sobre atributos (usuário/recurso/contexto — hora, IP, risco)
  via **conditional/contextual tuples** (ex.: aprova invoice < 10k do próprio setor).
- **PDP/PEP separados:** PDP = **Check API do motor**; **PEP = middleware Zig** em cada
  serviço, que extrai `sub`+tenant **do token verificado** (nunca do body/header do cliente) e
  chama `check(obj, rel, subject)` antes do handler. **Deny-by-default** (erro/timeout do PDP
  = nega), enforcement **server-side**, **todo endpoint mapeia 1 permissão** (`recurso:ação`).
- **Token fino:** o JWT carrega `sub`/tenant/sessão/AAL — **sem** a lista de permissões (evita
  authz stale em token longo); a decisão é consultada no PDP e cacheada com TTL curto
  (in-memory/Redis) invalidado por evento de mudança de papel.
- **Toda decisão de authz é logada** (quem / o quê / allow-deny / política), com `trace_id`
  (casa com a observabilidade LGTM+ da casa) — auditoria + rotina de testes.

## 6. Sessão, multi-dispositivo e logout

- **Multi-dispositivo de 1ª classe:** N sessões simultâneas por usuário, cada uma atada a um
  **dispositivo** (fingerprint + rótulo amigável "Chrome no Windows", IP/geo, último uso).
  Nenhuma sessão derruba a outra. O **session store** (Postgres + Redis) guarda uma linha por
  sessão com `refresh_family_id`, `device_id`, `jti` corrente.
- **View de dispositivos/sessões:** lista os ativos e **permite remover um** (revoga a sessão
  daquele device), além de **"sair de todos"**.
- **Sessão longa por padrão (fim do "15 min e é chutado"):** o access token continua curto
  (ex.: 15 min) **mas com refresh silencioso** — para o usuário, a sessão **persiste 7 dias por
  padrão**. No login, **pergunta se o dispositivo é confiável**; se sim, **90 dias**. Ops
  sensíveis ainda pedem **step-up fresco** em AAL alto — sessão longa não enfraquece.
- **Refresh rotativo com detecção de reuso** (reusou um refresh já rotacionado → revoga a
  **família** inteira). O refresh token é opaco (CSPRNG, §Z.6), hasheado no store.
- **Botão "Sair" bem visível → kill IRREVERSÍVEL da sessão:** não basta apagar o cookie — o
  handler de logout **revoga o refresh token (e a família), apaga o registro de sessão
  server-side, joga o `jti` na denylist (Redis/DB) até expirar e desassocia o push token do
  device**. Depois do logout, aquela sessão é irrecuperável: nem replay, nem refresh, nem
  "voltar o cookie" reativa. O PEP de validação de access token **consulta a denylist de `jti`**
  em toda request (cache curto).
- Cookies **`HttpOnly` + `Secure` + `SameSite`**; token nunca em `localStorage`.

## 7. Migração de auth legado — PRIORIDADE 0

Existe auth no padrão antigo → **portar pra este IAM é prioridade máxima** (segurança
inegociável; pode gastar o que precisar). Estratégia **strangler-fig** (casa com
schematize-node quando o legado é Node): dual-run, **re-hash preguiçoso** no login (verifica no
hash legado, regrava em **argon2id**), mapeia registros legados → modelo novo (dedupe de
emails, cunha IDs internos ULID/UUIDv7), **ativa o Email OTP always-on como 2º fator baseline**
(a conta migrada já entra em 2FA sem muro) e **incentiva enrolar fator forte** (step-up para
sensível), **revoga sessões legadas** e **nunca confia na authz legada** (re-deriva as tuplas
ReBAC). O auth migrado nasce já como **app separada** (§1) — e, sendo auth, o **ADR de fit (§0)
pesa Rust/Go**; se Zig, com o custo assumido.

## 8. Rotina agressiva de testes (detalhe na schematize-pentest)

Suíte adversarial **contínua** (CI + agendada, fixtures multi-tenant, saída machine-readable,
**gate que trava** em qualquer vazamento):
- **Cross-tenant (BOLA/IDOR):** token do tenant B → IDs do tenant A = 403/404; fuzz de IDs.
- **Priv-esc (BFLA):** papel baixo → ação de papel alto (horizontal e vertical).
- **Matriz persona × endpoint** exaustiva.
- **Abuso de fluxo:** bypass de 2FA, reset pulando 2FA, brute-force/rate-limit de OTP, replay
  de token, reuso de refresh, JWT `alg=none`/kid trocado, session fixation, adulteração de
  asserção SSO, IDOR na gestão de identificadores, bypass de step-up, mass-assignment de papel,
  **logout que não invalidou de verdade** (sessão recuperável).
- **Fuzzing do parsing** de todo input de auth (rodado em ReleaseSafe — `references/seguranca.md
  §Z.1/§Z.3`); qualquer trap é bug de segurança.

## 9. Autenticação adaptativa por risco (robusta) + transversais

A resposta ao login **varia com o risco calculado** (não é fixa) — é o que torna a conta
difícil de tomar sem chatear o legítimo:
- **Log de sessões/tentativas:** cada tentativa e sessão gravam IP/ASN+reputação, device
  fingerprint, geo, UA, horário, resultado e **score de risco** — na view de sessões (§6) e em
  audit log imutável. É o insumo do score.
- **Score por tentativa:** IP suspeito/novo (Tor/proxy/ASN de abuso), device novo,
  geovelocidade impossível, velocity/brute, hit de honeypot. Baixo = fluxo normal; alto =
  escala.
- **Escalonamento por risco (2FA→3FA):** sob risco, exige um **fator a mais na ordem de força**
  — **senha → código por email → app OTP/chave**. Acertar senha+email não basta em contexto
  suspeito. Mesmo motor do step-up (§3), disparado pelo **contexto**, não só pela ação.
- **Negação deceptiva / tarpit (falso negativo sob risco):** em contexto suspeito, mesmo com
  **senha correta** o serviço pode responder **genérico `invalid_credentials` uma vez** enquanto
  **computa server-side que a credencial estava certa** e marca que a **próxima** tentativa
  correta **passa** (já com os fatores escalados). Seguro porque: **resposta e tempo IDÊNTICOS**
  ao erro real (sem oráculo — comparação em **tempo constante**, §Z.7, e o mesmo path de
  resposta); estado "próxima passa" **curto e escopado** (conta+IP+device, TTL curto, expira
  sozinho, nunca vira lockout do legítimo); **soma-se** ao 3FA, não substitui; tudo logado.
- **Honeypot:** contas/campos/rotas isca; qualquer interação = sinal forte de hostil → score
  alto, tarpit/deceção, alerta. Nunca serve tráfego real.
- **Anti-automação sempre:** rate-limit + **backoff exponencial** e **lockout progressivo por
  conta+IP**; OTP curto, single-use, `jti` na denylist. Barra o abuso sem derrubar o serviço.
- **Notifica o usuário:** login novo/suspeito, novo device, mudança de credencial → aviso nos
  canais verificados, com "não fui eu" (revoga + força reforço).

### Transversais (sempre)
- **Audit log imutável** de toda decisão authn/authz e mudança de credencial — alimenta a
  forense e os testes (liga com a observabilidade LGTM+ da casa; `trace_id` propagado no fluxo
  de login/authz).
- **Padrões:** OIDC/OAuth2.1 + PKCE; WebAuthn/FIDO2; AALs NIST 800-63B; SCIM (roadmap
  enterprise); FAPI2 se fintech.
- **Bibliotecas de apoio (Zig):** ID (`ulid`/`uuid` em Zig quando disponível, ou impl própria
  revisada), JWT/JWKS e WebAuthn por lib Zig madura **ou C interop com boundary validado**
  (§Z.4), argon2id (`std.crypto` ou C revisada), TOTP, cliente do motor ReBAC (OpenFGA/SpiceDB).
  Toda dependência C entra no boundary de validação. **Nenhuma chave privada fora do auth.**

## Roadmap de fases
- **F0** Núcleo de identidade (ID imutável, N identificadores, verificação, Resend/Twilio
  plugáveis por interface/vtable Zig, email OTP always-on) — já como **app separada** em
  `auth.<domain>` (ADR de fit §0 decide Zig vs. Rust/Go).
- **F1** 2FA baseline por desenho (senha + Email OTP, sem muro pré-login) + fluxos (TOTP/push,
  **passkey**, escolha de método, invariante de troca, **nudge** de fator forte, step-up
  just-in-time, **risk engine adaptativo**: score, 2FA→3FA, negação deceptiva/tarpit, honeypot).
- **F2** Multi-tenant + **ReBAC** (membership, papéis granulares, PDP/PEP em middleware Zig,
  deny-default, token fino, audit).
- **F3** Recuperação resiliente (múltiplos caminhos, força ≥ login, SSO com recuperação local,
  atraso cancelável, nudge de email secundário).
- **F4** App de 1ª classe + multi-dispositivo (OIDC/PKCE nativo, push-approval, view de remover
  dispositivos, sessão 7d/90d confiável, logout irreversível).
- **F5** Migração de legado (prioridade 0 quando aplicável).
- **F6** Rotina agressiva de testes (cross-tenant, priv-esc, abuso de fluxo, fuzzing — CI +
  agendada).
- **Roadmap+** chave FIDO2 dedicada, SCIM, FAPI2, trusted contacts.

## Checklist (entra na Definition of Done quando o projeto tem auth)
- [ ] **ADR de fit (§0)** registrado: auth/cripto avaliado Zig vs. Rust/Go; se auth é o serviço, Rust/Go é o default honesto; se Zig, o custo (boundary C, cripto, ecossistema jovem) está assumido.
- [ ] Auth é **app separada** (`<projeto>_auth_zig` — ou `_rs`/`_go` por ADR — + front próprio em `auth.<domain>`, isolados) — não monolith.
- [ ] **ID interno imutável** (ULID/UUIDv7); email/telefone não são ID; múltiplos emails suportados.
- [ ] **2FA baseline por desenho** (senha + Email OTP = 2FA desde o cadastro); fator forte é **nudge + just-in-time (step-up)**, **NUNCA muro pré-login** (o PEP libera o baseline, exige AAL alto só por rota sensível); passkey no núcleo; email OTP always-on; Twilio; providers como interfaces/vtables Zig.
- [ ] **Efeito externo só sai em `prd` (§3.1):** `EmailProvider`/`SmsProvider`/`PushProvider` com **default = SINK** fora de prd (escolha na composição, não no chamador), **guard DENTRO do provider** devolvendo `error{ExternalRecipientBlocked}` (sem `catch {}`/`catch unreachable` no call-site), **cap por execução** (`MAIL_MAX_PER_RUN`, default 50) que aborta, **fail-closed** (`APP_ENV` ausente ⇒ não-prd) e chave **sandbox** em não-prd. Prova: `test "guard recusa destinatário externo"` com `std.testing.expectError` (vermelho visto) + `dig MX test.<domain>` = null MX. (`schematize-engineering` → `references/efeitos-externos.md`)
- [ ] **Risk engine adaptativo:** log de sessões/tentativas + score (IP/device/geo/velocity/honeypot); **2FA→3FA** sob risco; **negação deceptiva/tarpit** (falso negativo, resposta idêntica ao erro real em tempo constante, "próxima passa" curta/escopada); notifica login suspeito.
- [ ] Invariante de troca de fator (Y≠X, maior AAL); recuperação ≥ login; SSO com recuperação local; senha em **argon2id** (`std.crypto`/C revisada) + HIBP, CPU-bound fora do event loop.
- [ ] **Multi-tenant + RBAC/ABAC** (ReBAC OpenFGA/SpiceDB), deny-default, PDP=Check API / PEP=middleware Zig, enforcement server-side, token fino.
- [ ] Multi-dispositivo + view de remover; **sessão 7d/90d**; **logout irreversível** (revoga refresh+família, `jti` na denylist, não só cookie).
- [ ] JWKS público (assinatura só no auth); **CSPRNG** para tokens (§Z.6); comparação em tempo constante (§Z.7); **boundary C validado** para toda lib de cripto/WebAuthn/JWT via `@cImport` (§Z.4).
- [ ] Audit log de authn/authz; risk engine/rate-limit; migração de legado tratada como prioridade 0.
- [ ] Rotina agressiva de testes cross-tenant/priv-esc + fuzzing no CI (schematize-pentest).
