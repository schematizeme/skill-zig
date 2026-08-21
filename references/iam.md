# IAM — Identidade e Autorização da casa (piso inegociável) — recorte Zig

Piso normativo de **identidade, autenticação e autorização**, válido para toda skill da
casa. **Todo projeto começa com um IAM robusto por desenho** — segurança é inegociável.
Este arquivo é o recorte **Zig** do modelo agnóstico
(`schematize-engineering/references/iam.md`): mantém **todas as regras normativas** e as
concretiza na topologia de serviço e nos idiomas Zig. Liga com `references/seguranca.md`
(boundary C, build mode, CSPRNG, cripto), `references/memoria-concorrencia.md` (allocator,
limites), `references/arquitetura.md §3` (fit de linguagem) e `references/stack-versoes.md`.
Scaffold/auditoria por **`/zig-iam`**; testes adversariais na **schematize-pentest**.

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

- **Auth como app separada** — se em Zig, **`<projeto>_auth_zig`**; se o ADR de fit (§0)
  apontar Rust/Go, `<projeto>_auth_rs`/`_go` — **+ front de auth** próprio
  (`<projeto>_authfront`), com **repo, deploy, user Linux e systemd/container isolados**
  (casa com o isolamento por app do `ops.md` §3). Comprometer o app principal **não**
  compromete o IdP. O binário do auth é o **único** que carrega a chave privada de assinatura
  e os segredos de provedor (Resend/Twilio/OAuth) — que vêm de secret manager/env, **nunca**
  hardcoded nem por `@embedFile` (`references/seguranca.md §Z.5`).

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

- **Identificador só vale verificado** — não loga nem recupera sem verificação (`verified_at`
  não-nulo).

## 3. Fatores e níveis de garantia (AAL — NIST 800-63B)

- **Passkey/WebAuthn é núcleo** (não roadmap): já é "2 fatores num" (dispositivo + biometria),
  phishing-resistant. Em Zig o ecossistema WebAuthn é **jovem** — use lib Zig madura quando
  existir, ou **lib C revisada via `@cImport`** com o **boundary validado**
  (`references/seguranca.md §Z.4`); se o custo pesar, é sinal para reavaliar o fit (§0).

- **Email OTP (Resend) ligado por padrão, inclusive em HML** — só o operador desliga.
  **Ligado ≠ entregando pra fora:** em `prd` o provider é o real; **fora de `prd` o default é
  o SINK** e o guard recusa destinatário fora do domínio de teste (§3.1) — o fluxo de OTP é
  exercido ponta-a-ponta lendo o código do sink, nunca de uma caixa real.

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
  > **Parâmetros mínimos (`m` ≥ 19 MiB, `t` ≥ 2, `p` = 1, salt ≥ 16 B CSPRNG, string codificada
  > guardada inteira, re-hash preguiçoso):** na base — `schematize-engineering`, seu
  > `references/iam.md`, seção **2.1 ("Hash de senha — argon2id com parâmetros MÍNIMOS")**.
  > **Nenhuma das 8 skills fixava os números** até 2026-08-21 — e argon2id mal parametrizado é
  > mais fraco que bcrypt bem configurado. Calibre para ~0,5–1 s no hardware do auth e registre
  > o valor medido no ADR do serviço; o default da lib normalmente é o mais fraco. Em `std.crypto.pwhash.argon2`, use `Params` explícito (não `Params.interactive_2id` sem medir).

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

/// Ambiente. Fail-closed: **nada** liga o envio real além de um valor explícito de
/// produção; ausente, vazio ou desconhecido vira `.dev` — o modo SEGURO.
///
/// `parse` normaliza (trim + lowercase) e aceita os TRÊS grafismos que circulam no
/// `.env` global da casa: `prd`, `prod` e `production`. Aceitar só a string exata
/// `"prd"` fazia o MESMO `APP_ENV=production` significar coisas opostas em dois
/// serviços do mesmo deploy — um sinkava, o outro entregava de verdade.
pub const Env = enum {
    dev,
    hml,
    prd,

    pub fn parse(raw: ?[]const u8) Env {
        const s0 = raw orelse return .dev;
        const s = std.mem.trim(u8, s0, " \t\r\n\"'");
        if (s.len == 0 or s.len > 16) return .dev;
        var buf: [16]u8 = undefined;
        const low = std.ascii.lowerString(buf[0..s.len], s);
        if (std.mem.eql(u8, low, "prd") or std.mem.eql(u8, low, "prod") or
            std.mem.eql(u8, low, "production")) return .prd;
        if (std.mem.eql(u8, low, "hml") or std.mem.eql(u8, low, "staging") or
            std.mem.eql(u8, low, "stg")) return .hml;
        return .dev;
    }

    /// Lê `APP_ENV` do processo. Variável ausente/ilegível ⇒ `.dev` (não-prd).
    pub fn fromProcess(alloc: std.mem.Allocator) Env {
        const raw = std.process.getEnvVarOwned(alloc, "APP_ENV") catch return .dev;
        defer alloc.free(raw);
        return Env.parse(raw);
    }
};

/// `redact` — endereço em log vira `lo***@dominio`. Log de auditoria precisa
/// identificar o envio, não expor a caixa; e **NUNCA** entra segredo (OTP, token,
/// link mágico) em log de nenhum nível.
pub fn redact(buf: []u8, addr: []const u8) []const u8 {
    const at = std.mem.lastIndexOfScalar(u8, addr, '@') orelse return "***";
    // O tipo é explícito: `@min(at, 2)` com um operando comptime NARROWS o resultado
    // (viraria `u2`), e `keep + 3` estouraria — panic de integer overflow em runtime.
    const keep: usize = @min(at, 2);
    const dom = addr[at..];
    const n = keep + 3 + dom.len;
    if (n > buf.len) return "***";
    @memcpy(buf[0..keep], addr[0..keep]);
    @memcpy(buf[keep .. keep + 3], "***");
    @memcpy(buf[keep + 3 ..][0..dom.len], dom);
    return buf[0..n];
}

/// Auditoria da recusa. O guard **não chama `std.log` direto**: ele emite um evento.
///
/// Por quê: (a) biblioteca não escolhe o logger da aplicação; (b) `zig test` FALHA
/// (exit 1) quando um teste chama `std.log.err` — e exercitar o caminho de recusa é
/// exatamente o que a suíte tem de fazer. Com a auditoria injetada, produção usa
/// `logAudit` (severidade `err`, como deve ser) e o teste usa um contador, virando
/// asserção: "a recusa foi auditada". Sem isso, a suíte sai "All tests passed" e
/// mesmo assim `exit code 1` — o CI fica vermelho por acertar.
pub const AuditEvent = union(enum) {
    blocked: struct { to_redacted: []const u8, env: Env },
    cap_exceeded: struct { max_per_run: usize, env: Env },
};

pub const AuditFn = *const fn (event: AuditEvent) void;

/// Auditoria de produção: severidade `err`, mensagem que ensina o caminho certo.
pub fn logAudit(event: AuditEvent) void {
    switch (event) {
        .blocked => |b| std.log.err(
            "bloqueado: destinatario externo '{s}' com env={s}. Use " ++
                "<papel>+<run-id>-<n>@test.<domain> ou registre o ADR de excecao " ++
                "(allowlist <=5 + cap + janela + subdominio). Nada foi enviado.",
            .{ b.to_redacted, @tagName(b.env) },
        ),
        .cap_exceeded => |c| std.log.err(
            "cap de envio estourado (max_per_run={d}, env={s}): laco de envio em massa. Abortando.",
            .{ c.max_per_run, @tagName(c.env) },
        ),
    }
}

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

/// Domínios aceitos fora de `prd`. O 1º é o `test.<domain>` da casa — o que o torna
/// seguro é o **null MX** (RFC 7505: `MX 0 .`) + SPF `-all` + DMARC `p=reject`, não o
/// nome. Os demais são os TLDs **reservados** da RFC 2606/6761, que nenhum resolvedor
/// da internet entrega.
///
/// `example.com` NÃO entra nesta lista: ele **resolve** (a IANA o opera, com A/AAAA
/// públicos) — o que impede a entrega é ele não publicar MX, uma propriedade que não
/// está sob nosso controle e pode mudar. Piso de rota nula é DNS que nós controlamos
/// ou TLD que a IETF reservou; "provavelmente não entrega" não é piso.
pub const default_test_domains: []const []const u8 = &.{
    "test.acme.com", // TROCAR pelo test.<domain> do projeto (null MX + SPF -all + DMARC reject)
    "test",
    "invalid",
    "example",
};

/// SINK — default fora de `prd`. Não abre socket para fora: registra o envio
/// (ou entrega no Mailpit local) para o teste LER o código do OTP.
///
/// `sent` é **atômico**: este é ponto único de saída de um serviço que roda com
/// `std.Thread`, e `self.sent += 1` é read-modify-write — duas threads perdem
/// contagem, que é exatamente o que o cap existe para não deixar acontecer.
///
/// `last_to` é **inspeção de teste** (single-thread, um caso por vez): não é estado
/// de produção e por isso não carrega lock. Se o seu sink for compartilhado entre
/// threads no teste, troque por uma fila.
pub const SinkProvider = struct {
    sent: std.atomic.Value(usize) = std.atomic.Value(usize).init(0),
    last_to: [254]u8 = undefined,
    last_to_len: usize = 0,

    const vtable = EmailProvider.VTable{ .sendOtp = sendOtp };

    pub fn provider(self: *SinkProvider) EmailProvider {
        return .{ .ptr = self, .vtable = &vtable };
    }

    /// Quantos envios o sink recebeu (o teste assere sobre isto).
    pub fn count(self: *const SinkProvider) usize {
        return self.sent.load(.acquire);
    }

    /// Último destinatário sinkado — o teste assere sobre isto, não sobre caixa real.
    /// O OTP fica acessível ao teste pela API do sink, NUNCA por log.
    pub fn lastTo(self: *const SinkProvider) []const u8 {
        return self.last_to[0..self.last_to_len];
    }

    fn sendOtp(ptr: *anyopaque, to: []const u8, code: []const u8) anyerror!void {
        const self: *SinkProvider = @ptrCast(@alignCast(ptr));
        if (to.len > self.last_to.len) return SendError.AddressTooLong;
        @memcpy(self.last_to[0..to.len], to);
        self.last_to_len = to.len;
        _ = self.sent.fetchAdd(1, .acq_rel);
        // O código do OTP é SEGREDO: nunca vai para log, em nível nenhum. O teste
        // lê o código pela API do sink, não pelo stdout do processo.
        var rb: [280]u8 = undefined;
        std.log.debug("mail sink: to={s}", .{redact(&rb, to)});
        _ = code;
    }
};

/// GUARD — envelopa QUALQUER `EmailProvider` e é o único ponto de saída.
/// Deny-by-default: fora de `prd`, só o domínio de teste passa; e conta SEMPRE.
pub const GuardedProvider = struct {
    inner: EmailProvider,
    env: Env,
    test_domains: []const []const u8 = default_test_domains,
    /// Teto por execução (`MAIL_MAX_PER_RUN`, default 50). Vale em **TODOS** os
    /// ambientes — inclusive `prd`. O cap não é uma das camadas de sandbox: é um
    /// **freio** contra laço em massa, e um laço em massa em produção é pior, não
    /// melhor. Em prd, dimensione o valor para o volume real (ou eleve por config);
    /// desligar o freio é que não é opção. (ADR-0004.)
    max_per_run: usize = 50,
    sent: std.atomic.Value(usize) = std.atomic.Value(usize).init(0),
    /// Para onde vai o registro da recusa. Default: `std.log.err`.
    audit: AuditFn = logAudit,

    const vtable = EmailProvider.VTable{ .sendOtp = sendOtp };

    pub fn provider(self: *GuardedProvider) EmailProvider {
        return .{ .ptr = self, .vtable = &vtable };
    }

    /// Quantas tentativas o guard contabilizou nesta execução.
    pub fn count(self: *const GuardedProvider) usize {
        return self.sent.load(.acquire);
    }

    fn sendOtp(ptr: *anyopaque, to: []const u8, code: []const u8) anyerror!void {
        const self: *GuardedProvider = @ptrCast(@alignCast(ptr));
        try self.assertDeliverable(to);
        // Reserva a vaga ANTES de tentar: conta a TENTATIVA, não o sucesso — falha do
        // provider não zera o teto. `fetchAdd` devolve o valor ANTERIOR, então a
        // comparação e o incremento são um passo só (sem TOCTOU entre threads).
        const anterior = self.sent.fetchAdd(1, .acq_rel);
        if (anterior >= self.max_per_run) {
            self.audit(.{ .cap_exceeded = .{ .max_per_run = self.max_per_run, .env = self.env } });
            return SendError.RunCapExceeded;
        }
        try self.inner.sendOtp(to, code);
    }

    /// Deny-by-default, com mensagem que ensina o caminho certo.
    fn assertDeliverable(self: *const GuardedProvider, to: []const u8) SendError!void {
        if (self.env == .prd) return; // produção entrega de verdade
        if (self.isTestRecipient(to)) return;
        var rb: [280]u8 = undefined;
        self.audit(.{ .blocked = .{ .to_redacted = redact(&rb, to), .env = self.env } });
        return SendError.ExternalRecipientBlocked;
    }

    fn isTestRecipient(self: *const GuardedProvider, to: []const u8) bool {
        const at = std.mem.lastIndexOfScalar(u8, to, '@') orelse return false;
        if (at == 0) return false; // local part vazia: "@test" não é endereço
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
/// O guard envelopa SEMPRE — inclusive em `prd`, onde ele conta, audita e aplica o
/// cap. `real` é o adaptador Resend/SES, construído só quando `env == .prd`.
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

// ---------------------------------------------------------------------------
// Testes. O guard recebe uma auditoria de TESTE (contador) em vez de `logAudit`:
// `zig test` FALHA (exit 1) quando um teste chama `std.log.err`, e exercitar a
// recusa é justamente o que a suíte precisa fazer. Trocar a auditoria mantém a
// severidade certa em produção, deixa a suíte verde, e ainda transforma "a recusa
// foi auditada" em asserção.
// ---------------------------------------------------------------------------
var audited: usize = 0;
var last_event: ?std.meta.Tag(AuditEvent) = null;

fn countAudit(event: AuditEvent) void {
    audited += 1;
    last_event = event;
}

test "guard recusa destinatário externo" {
    audited = 0;
    var sink = SinkProvider{};
    var guard = GuardedProvider{ .inner = sink.provider(), .env = .hml, .audit = countAudit };
    const mail = guard.provider();

    // O vermelho que precisa existir: caixa real, fora do domínio de teste, em hml.
    try std.testing.expectError(
        SendError.ExternalRecipientBlocked,
        mail.sendOtp("alguem@gmail.com", "123456"),
    );
    try std.testing.expectEqual(@as(usize, 0), sink.count()); // NADA saiu do processo
    try std.testing.expectEqual(@as(usize, 1), audited);      // e a recusa foi auditada
    try std.testing.expectEqual(std.meta.Tag(AuditEvent).blocked, last_event.?);

    // O endereço canônico da casa passa e cai no sink.
    try mail.sendOtp("login+run42-1@test.acme.com", "123456");
    try std.testing.expectEqual(@as(usize, 1), sink.count());
    try std.testing.expectEqualStrings("login+run42-1@test.acme.com", sink.lastTo());
}

test "endereço malformado é recusado antes de virar domínio" {
    audited = 0;
    var sink = SinkProvider{};
    var guard = GuardedProvider{ .inner = sink.provider(), .env = .dev, .audit = countAudit };
    const mail = guard.provider();
    for ([_][]const u8{ "semarroba", "@test", "" }) |bad| {
        try std.testing.expectError(SendError.ExternalRecipientBlocked, mail.sendOtp(bad, "1"));
    }
    try std.testing.expectEqual(@as(usize, 0), sink.count());
}

test "cap por execução aborta antes de virar 5.000" {
    var sink = SinkProvider{};
    var guard = GuardedProvider{ .inner = sink.provider(), .env = .dev, .max_per_run = 2, .audit = countAudit };
    const mail = guard.provider();

    try mail.sendOtp("a+run7-1@test.acme.com", "111111");
    try mail.sendOtp("b+run7-2@test.acme.com", "222222");
    try std.testing.expectError(
        SendError.RunCapExceeded,
        mail.sendOtp("c+run7-3@test.acme.com", "333333"),
    );
    try std.testing.expectEqual(@as(usize, 2), sink.count());
}

test "o cap vale TAMBÉM em produção — é freio, não camada de sandbox" {
    var sink = SinkProvider{};
    // `inner` é o sink só para o teste não abrir socket; o que se assere é o cap em .prd.
    var guard = GuardedProvider{ .inner = sink.provider(), .env = .prd, .max_per_run = 1, .audit = countAudit };
    const mail = guard.provider();
    try mail.sendOtp("cliente@acme.com", "111111"); // em prd, destinatário real passa
    try std.testing.expectError(
        SendError.RunCapExceeded,
        mail.sendOtp("outro@acme.com", "222222"),
    );
}

test "env ausente ou desconhecido NÃO vira produção" {
    try std.testing.expectEqual(Env.dev, Env.parse(null));
    try std.testing.expectEqual(Env.dev, Env.parse(""));
    try std.testing.expectEqual(Env.dev, Env.parse("qualquer-coisa"));
    // ...mas os grafismos REAIS de produção viram produção, nos três formatos que
    // circulam no `.env` global — senão o mesmo APP_ENV significa coisas opostas
    // em dois serviços do mesmo deploy.
    try std.testing.expectEqual(Env.prd, Env.parse("prd"));
    try std.testing.expectEqual(Env.prd, Env.parse("prod"));
    try std.testing.expectEqual(Env.prd, Env.parse("production"));
    try std.testing.expectEqual(Env.prd, Env.parse("  PRODUCTION \n"));
    try std.testing.expectEqual(Env.hml, Env.parse("staging"));
}

test "log de auditoria não expõe a caixa nem o segredo" {
    var buf: [280]u8 = undefined;
    try std.testing.expectEqualStrings("al***@acme.com", redact(&buf, "alguem@acme.com"));
    try std.testing.expectEqualStrings("***", redact(&buf, "sem-arroba"));
}
```

**O que isso trava, e o que ainda é sua responsabilidade:**

| Regra | Onde está no código |
|---|---|
| Guard **dentro** do provider, não no chamador | `GuardedProvider.sendOtp` → `assertDeliverable` antes de qualquer I/O |
| Sink default fora de `prd`, escolha **uma vez** | `wire()` na composição; nenhum use-site instancia o adaptador real |
| Fail-closed | `Env.parse`/`Env.fromProcess`: ausente/ilegível ⇒ `.dev`; `capFromEnv` volta ao default |
| Cap por execução + abort, em **TODOS** os ambientes | `max_per_run` + `SendError.RunCapExceeded`; `fetchAdd` conta a **tentativa** (falha do provider não zera o teto) e compara em um passo só — sem TOCTOU entre threads |
| Contador **atômico** | `std.atomic.Value(usize)` no guard e no sink: `sent += 1` é read-modify-write e perde contagem sob `std.Thread` — justo no contador que existe pra travar o laço em massa |
| Segredo **nunca** em log | o OTP não vai pra log em nível nenhum; o teste lê o código pela API do sink. Endereço em log passa por `redact()` (`al***@acme.com`) |
| Recusa **auditável e testável** | `AuditFn` injetada (default `logAudit` → `std.log.err`); o teste injeta um contador — o que mantém a severidade certa em produção **e** a suíte verde (`zig test` reprova quem chama `std.log.err`) |
| Recusa é **erro**, não warning | error union `SendError`; **VETADO** `catch {}`/`catch unreachable` no call-site |
| Destinatário sintético em rota nula | `default_test_domains`: o `test.<domain>` (null MX + SPF `-all` + DMARC `p=reject`) + TLDs **reservados** da RFC 2606/6761. `example.com` **fora** da lista: ele resolve — o que impede a entrega é ele não publicar MX, e isso não está sob nosso controle |
| `APP_ENV` com o **mesmo** significado em todo serviço | `Env.parse` normaliza (trim + lowercase) e aceita `prd`/`prod`/`production`; desconhecido ⇒ `.dev` |

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

**Recuperação:** múltiplos caminhos independentes (vários emails, códigos de backup offline,
telefone). **Força ≥ login** (2 fatores ou processo com atraso + revisão), rate-limit
agressivo, tudo auditado. **Reset nunca é bypass de 1 fator.**

## 5. Multi-tenant + RBAC/ABAC — motor ReBAC (estilo Zanzibar)

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

- **Notifica o usuário:** login novo/suspeito, novo device, mudança de credencial → aviso nos
  canais verificados, com "não fui eu" (revoga + força reforço).

### Transversais (sempre)

- **Audit log imutável** de toda decisão authn/authz e mudança de credencial — alimenta a
  forense e os testes (liga com a observabilidade LGTM+ da casa; `trace_id` propagado no fluxo
  de login/authz).

- **Bibliotecas de apoio (Zig):** ID (`ulid`/`uuid` em Zig quando disponível, ou impl própria
  revisada), JWT/JWKS e WebAuthn por lib Zig madura **ou C interop com boundary validado**
  (§Z.4), argon2id (`std.crypto` ou C revisada), TOTP, cliente do motor ReBAC (OpenFGA/SpiceDB).
  Toda dependência C entra no boundary de validação. **Nenhuma chave privada fora do auth.**

## Roadmap de fases

- **F1** 2FA baseline por desenho (senha + Email OTP, sem muro pré-login) + fluxos (TOTP/push,
  **passkey**, escolha de método, invariante de troca, **nudge** de fator forte, step-up
  just-in-time, **risk engine adaptativo**: score, 2FA→3FA, negação deceptiva/tarpit, honeypot).

- **F2** Multi-tenant + **ReBAC** (membership, papéis granulares, PDP/PEP em middleware Zig,
  deny-default, token fino, audit).

- **F3** Recuperação resiliente (múltiplos caminhos, força ≥ login, SSO com recuperação local,
  atraso cancelável, nudge de email secundário).

- **F4** App de 1ª classe + multi-dispositivo (OIDC/PKCE nativo, push-approval, view de remover
  dispositivos, sessão 7d/90d confiável, logout irreversível).

- **F6** Rotina agressiva de testes (cross-tenant, priv-esc, abuso de fluxo, fuzzing — CI +
  agendada).

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
