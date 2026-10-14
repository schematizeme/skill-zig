# Filosofia, Aplicação Universal e Anti-Padrões Vetados


> **PONTEIRO, não cópia.** A normativa deste tema é da base: **`schematize-engineering`** →
> `references/anti-padroes.md`. Leia lá primeiro; aqui fica **só o que muda em Zig**.
>
> **Onde este arquivo divergir da base, a BASE MANDA** (`SKILL.md` §"Precedência e herança").
> Em 2026-08-21 os blocos idênticos à base foram **podados mecanicamente** (`tools/podar-clone.mjs`),
> que é por que a numeração dos itens **salta**: o número é o da base, e o item que não aparece aqui
> é porque **não muda nesta linguagem** — procure-o lá. Manter a cópia era manter a próxima deriva
> (foi assim que o `argon2id-only` da casa virou "ou PBKDF2" numa skill e o rol de 6 linguagens
> virou "só Go e Rust" em três).

## 0. Como Ler

Versões concretas de stacks (inclusive a versão exata do compilador Zig) ficam no **Anexo A** / `references/stack-versoes.md`, atualizado independentemente deste corpo.

## 1. Filosofia

**Princípios:** Clean Code, SOLID, KISS, DRY (com bom senso — duplicação acidental ≠ duplicação semântica). Em Zig, soma-se o lema da linguagem: **sem controle de fluxo oculto, sem alocação escondida, sem magia** — o que você lê é o que executa. Manter isso é filosofia, não estilo.

**Regra suprema:** se algo aumenta acoplamento, reduz observabilidade, cria dependência desnecessária, **vaza segredo, vaza memória, mistura contexto, ou pula registro** ou adiciona complexidade sem benefício claro, **provavelmente está errado**.

## 37. Anti-Padrões Vetados — "Macaquices" que Terminam Rápido e Quebram em Produção

### Segredos e exposição

3. **`.env` com segredo real commitado**, ou segredo hardcoded "temporário" no código (inclusive `const KEY = "..."` num `.zig`).
   → Secret manager + `.env.example` sem valores. Gitleaks no pipeline (§13).

### Injeção e execução

4. **SQL/consulta por concatenação de string** com input externo. Zig não tem `format!`, mas montar query com `std.fmt.allocPrint`/concat de string é **o mesmo pecado**.
   → Prepared statements / query parametrizada, sempre. `std.fmt` só monta a query estática; valores vão por parâmetro do driver, nunca interpolados (§10).

5. **Exec com input** — `std.process.Child` / `std.ChildProcess` montando comando por string com qualquer parte vinda de input, ou passando por shell.
   → Args separados em `argv`, sem shell, allowlist de comandos. Nunca interpolar input no comando.

6. **Desabilitar verificação TLS** (`rejectUnauthorized: false`, `InsecureSkipVerify: true`, pular a validação de cert no cliente HTTP) pra "funcionar logo".
   → Cert válido. mTLS interno. Se o cert está errado, conserta o cert.

### Auth e autorização

7. **Auth/authz só no client** (`if (user.isAdmin)` no front decide acesso).
   → Toda decisão de acesso é **server-side** (§15). Front é UX, não controle.

10. **Hash de senha fraco** — MD5, SHA1, sem salt, ou plaintext.
    → argon2id-only (bcrypt/PBKDF2 só legado a migrar no próximo login) via lib criptográfica revisada (§14).

11. **Rand não-cripto pra token, id de sessão, código de reset, nonce** (`std.rand.DefaultPrng` / RNG sem seed cripto).
    → CSPRNG: **`io.random`** (ou `io.randomSecure` para material de vida longa) — ✔ 0.16.0; `std.crypto.random` saiu, e o "conserto" tentador (`std.Random.DefaultPrng`) é o Xoshiro previsível (§14).

### CORS, headers e superfície

12. **`Access-Control-Allow-Origin: *` em rota autenticada** (pior ainda com `allow-credentials`).
    → Allowlist explícita de origens (hardening; ver a `schematize-qa`, `references/categorias.md` §§5 e 10).

13. **Endpoint de debug/admin/management sem auth, ou bind em `0.0.0.0`** expondo porta interna.
    → Bind restrito, auth obrigatória, `/debug` e `/actuator` retornam 404 externamente (ver a `schematize-qa`, `references/categorias.md` §§5 e 10).

### Erros, tipos e qualidade

15. **Catch que engole erro** — em Zig: `_ = foo()` que descarta um `error union`, `catch {}`, `catch unreachable`, `catch @panic(...)` em caminho de produção só pra calar o compilador, ou ignorar um `!T`.
    → Tratar com `catch |err| { ...trata/loga com trace_id... }`, propagar com `try`, limpar com `errdefer`. Degradar de forma consciente, nunca silenciar (detalhe no item 47).

16. **Calar o compilador à força** — `catch unreachable` / `orelse unreachable` em caminho de produção, `@ptrCast`/`@alignCast` pra contornar o tipo, `anytype` onde cabe tipo concreto, `@setRuntimeSafety(false)` local pra "passar".
    → Tratar o caso de erro/null de verdade (`catch |err|`, `orelse`), tipar concreto. Suprimir checagem **de segurança** (bounds/overflow) inline é VETADO sem ADR.

### Testes e cobertura

18. **Pular/comentar teste pra passar o CI** — comentar o bloco `test "..."`, remover o `try std.testing.expect(...)`, marcar `if (true) return error.SkipZigTest` sem motivo real.
    → Conserta o código, não silencia o teste (`schematize-qa`).

19. **Baixar o threshold de cobertura ou editar o gate** pra o número fechar.
    → Cobertura é contrato (ver a `schematize-qa`). Sobe escrevendo teste, não mexendo na régua.

### Operação e entrega

23. **Container root, `chmod 777`, `--privileged`, filesystem RW** "pra funcionar".
    → Não-root, read-only, least-privilege (§13). O binário Zig estático facilita imagem mínima (`FROM scratch`) — use isso.

24. **Dependência nova sem verificar** nome (typosquatting), manutenção, licença, e sem pin de versão. Em Zig: entrada em `build.zig.zon` **sem hash de integridade** ou apontando pra `HEAD`.
    → Pin exato + **hash** em `build.zig.zon`, checar nome/manutenção/licença, SCA no pipeline (§13, §34, `references/cadeia-suprimentos.md`).

31. **Criar serviço backend novo FORA do rol sancionado sem ADR de fit**, ou qualquer código novo em PHP.
    → Backend novo só em linguagem do **rol** (Go, Rust, Elixir, C#, Zig, Ruby) **com ADR (§27) justificando o fit**; escolher **Zig** quando o fit manda (controle manual de memória, interop C, artefato pequeno) — em empate, default pragmático é Go. Fora do rol exige **ADR de exceção**. Next.js/Astro seguem valendo só pro frontend. **PHP é proibido** e migra; **Node backend é legado** e sai pela regra dos ~30%/~50% (§3, §3.1, §3.2).

36. **Operar o servidor por fora do `<projeto>_ops`** — `ssh` + comando ad-hoc, editar arquivo no servidor, `docker`/`kubectl`/`systemctl` na mão, script solto.
    → **100%** de install/update/config/correção passa por comando do ops. Não tem comando? **cria no ops** (`schematize-engineering` -> `references/ops.md` §2).

37. **Instalar/subir o sistema em série** ("um serviço de cada vez", 20 min).
    → Instalação **paralela por padrão** = `nproc` (`schematize-engineering` -> `references/ops.md` §3).

### IAM (identidade e autorização)

43. **Auth apensado ao escopo principal como monolith** (login/2FA/authz dentro do serviço principal, num módulo `auth` interno, sem serviço/front próprios).
    → Auth é **app separada** em `auth.<domain>`: microserviço próprio `<projeto>_auth_<lang>` + `<projeto>_authfront`, isolados; apps delegam por OIDC/PKCE e validam por JWKS público (`references/iam.md` §1).

44. **Email/telefone como ID de usuário** (`user_id = email`, FK por email, login que assume 1 email), ou 2FA/recuperação com 1 fator só (reset por 1 email que pula o 2FA).
    → **ID interno imutável** (ULID/UUIDv7) como `sub`; email/telefone são identificadores N e verificáveis; **≥2 fatores sempre** (passkey/WebAuthn no núcleo); **recuperação ≥ força do login**; senha em **argon2id**+HIBP (`references/iam.md` §2–§4).

45. **Autorização hand-rolled / no cliente / permissão embutida em token longo** — `if role == "admin"` espalhado pelos handlers, checagem só no front, sem multi-tenant, papéis não-granulares.
    → **RBAC/ABAC granular por motor ReBAC** (OpenFGA/SpiceDB via client), **deny-default**, PDP=Check API / PEP=**middleware server-side**, **enforcement server-side**, token fino, decisão auditada (`references/iam.md` §5).

46. **Logout que só apaga o cookie** (sessão recuperável por refresh/replay), ou sessão curta que chuta o usuário toda hora sem refresh silencioso.
    → **Logout irreversível** (revoga refresh+família, apaga sessão server-side, `jti` na denylist consultada em toda request); **sessão 7d/90d** com refresh rotativo silencioso e multi-dispositivo (`references/iam.md` §6).

### Específicos de Zig — memória, erros, comptime e interop

> Zig entrega controle total ao custo de você gerenciar a memória à mão e tratar o erro à mão. Os pisos abaixo protegem exatamente essas superfícies. Detalhe de allocators e concorrência em `references/memoria-concorrencia.md`; versão do compilador em `references/stack-versoes.md`.

47. **Engolir o `error union`** — `_ = foo()` descartando um `!T`, `catch unreachable` / `catch @panic(...)` / `catch {}` em caminho de produção só pra calar o compilador, ou ignorar o `!` de uma função falível.
    → **`try`** pra propagar, **`catch |err| { ...trata, loga com trace_id, degrada... }`** pra tratar, **`errdefer`** pra desfazer o já-alocado no caminho de erro. `unreachable` só onde é **provadamente** inalcançável — nunca como atalho pra não tratar (§18, `references/memoria-concorrencia.md`).

48. **Vazamento de memória** — alocar sem `defer alloc.free(...)` / sem um caminho de free casado, perder o ponteiro no caminho de erro (sem `errdefer`), ou **não testar com o allocator que detecta leak**. **VETADO alocador global escondido** (estado alocado por baixo dos panos que ninguém libera).
    → Todo `alloc` tem seu `defer free` / `deinit` casado; erro no meio → `errdefer`. **Testar com `std.testing.allocator` / `std.heap.DebugAllocator`** que **falha o teste em leak** — leak detectado é bug, não warning. Ownership documentado no doc-comment `///` (quem aloca, quem libera). (`references/memoria-concorrencia.md`, a `schematize-qa`).

49. **Rodar produção em `ReleaseFast` sem profiling que justifique** — `ReleaseFast` desliga checagem de bounds e de overflow: acesso fora de faixa e overflow viram **UB (undefined behavior)** silencioso, não crash controlado.
    → **Default seguro é `ReleaseSafe`** (mantém as checagens). Só troque pra `ReleaseFast` num caminho quente com **profiling que prove o ganho** e ADR registrando o trade-off. Segurança de memória não se troca por microssegundo sem evidência (§13).

50. **Abuso de `comptime`** — metaprogramação ilegível, camadas de geração de tipo que ninguém depura, `comptime` transformado em "macro soup".
    → `comptime` é **força** do Zig (sem controle de fluxo nem alocação oculta) — use pra o que ele é bom (validação em compilação, generics, tabelas), com moderação e legibilidade. Bloco `comptime` denso conta como código útil pro limite de tamanho (arquitetura §6). Não jogue a ferramenta fora, mas não a use pra esconder complexidade.

51. **Interop C (`@cImport`) sem validar no boundary** — puxar header C e deixar `[*c]u8`, ponteiros crus, structs C e retornos de erro C vazarem pra dentro do domínio; confiar em ponteiro/len vindos de C sem checar.
    → **Anti-Corruption Layer** (arquitetura §4): o adapter em `infrastructure/external/` valida (null, tamanho, código de erro) e **converte** pra tipos Zig seguros (`[]const u8`, `error union`, `?T`) antes de cruzar o boundary. `@cImport` é superfície de risco — trate como entrada hostil.

52. **Não fixar a versão exata do compilador Zig.** Zig é **pre-1.0**: há breaking changes entre versões, e um `.zig` que compila em uma versão quebra na seguinte. Deixar a versão "flutuar" = build irreprodutível e drift entre dev/CI/prd.
    → **Pin exato** da versão do compilador (Anexo A / `references/stack-versoes.md`), usada igual em dev, CI e prd; upgrade é mudança deliberada com ADR e teste, nunca implícita.

### Efeitos externos (e-mail, SMS, push, webhook, cobrança)

53. **Mandar de verdade fora de produção** — cliente SMTP/HTTP do provedor ligado por default em dev/hml, `@gmail.com` (ou o seu e-mail) em fixture/seed/persona, laço de teste criando N contas com **Email OTP always-on** e nenhum contador no caminho.
    → **Provider por ambiente** (vtable `Mailer` com `SinkMailer` fora de `prd`), **guard dentro do provider** (`error.ExternalRecipientBlocked`, fail-closed quando a config falta), **cap por execução** com `@atomicRmw` (`MAIL_MAX_PER_RUN`) válido em TODOS os ambientes — inclusive `prd`, onde ele conta e audita —, e endereço sintético só em `test.<domain>` com **null MX** (`references/iam.md` §3.1; normativa em `schematize-engineering` → `references/efeitos-externos.md`). Bounce/complaint em massa **queima IP e domínio** e derruba o e-mail transacional de **produção** — inclusive o **OTP de login** —, com semanas de warm-up e utilidade zero. Não tem undo.
    *(Cite este anti-padrão **pelo título**, nunca por número: o mesmo `§37 item N` significa coisas diferentes em cada skill — ver a nota de numeração no topo.)*

> Regra de bolso: se a justificativa começa com "só pra funcionar", "depois eu arrumo", ou "é mais rápido assim" e o resultado mexe em segredo, auth, dado, registro, **memória (leak/UB), erro engolido, ou toca o servidor por fora do fluxo/ops** — **provavelmente é uma macaquice desta lista. Para e faz certo.**
