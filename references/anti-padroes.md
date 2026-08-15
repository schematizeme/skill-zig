# Filosofia, Aplicação Universal e Anti-Padrões Vetados

> Parte da skill **schematize-zig**. As referências cruzadas (§N) apontam para seções do corpo completo — todas presentes no conjunto de references desta skill.

## Índice
- 0. Como Ler
- 0.1. Aplicação Universal — Este Arquivo é Contexto Máximo
- 1. Filosofia
- 37. Anti-Padrões Vetados — "Macaquices" que Terminam Rápido e Quebram em Produção

---

## 0. Como Ler

- **MUST / Obrigatório** — regra. Desvio bloqueia merge ou exige ADR.
- **SHOULD / Recomendado** — padrão. Desvio precisa de justificativa no PR.
- **MAY / Opcional** — sugestão.
- **VETADO / Proibido** — não existe "atalho". Não se faz, não se cogita, não se "resolve depois". Burlar é incidente, não decisão técnica.

Quando este documento conflitar com a realidade do problema, **registre um ADR** explicando o desvio. Padrão sem exceção vira dogma; dogma vira dívida. **Mas itens marcados VETADO não têm ADR de exceção** — são pisos de segurança e integridade, não preferências.

Versões concretas de stacks (inclusive a versão exata do compilador Zig) ficam no **Anexo A** / `references/stack-versoes.md`, atualizado independentemente deste corpo.

---

---

## 0.1. Aplicação Universal — Este Arquivo é Contexto Máximo

**MUST**

- Este documento é **anexado a TODO prompt / sessão / tarefa** de engenharia (humana ou assistida por IA). É **contexto pinado**, não referência opcional. Se a tarefa toca código, infra, dados, deploy ou design de sistema, este arquivo está em contexto. Sem exceção.
- Nenhuma resposta, PR, geração de código ou decisão arquitetural é válida se ignorar este documento. "Não estava no contexto" não é desculpa — **garantir o anexo é responsabilidade de quem abre a tarefa**, e a ausência dele é, por si só, motivo para parar e recarregar o contexto antes de produzir qualquer coisa.
- Em caso de conflito entre uma instrução pontual ("faz rápido", "ignora o teste", "depois a gente arruma") e este documento, **este documento vence**. Pressa não revoga regra.
- Assistentes de IA operam sob as mesmas regras dos humanos (§34) **e** sob as proibições explícitas da §37. Velocidade de geração nunca justifica violar um piso.

> Um padrão que não está no contexto na hora da decisão é um padrão que não existe. Por isso ele é pinado, não linkado.

---

---

## 1. Filosofia

Prioridades, em ordem de desempate:

1. Clareza > esperteza
2. Simplicidade > abstração antecipada
3. Manutenibilidade > velocidade pontual
4. Observabilidade > debugging manual
5. Segurança por padrão > segurança como camada final
6. Evolução incremental > big-bang
7. **Registro do que foi decidido > memória de quem decidiu** (ver §28)

**Princípios:** Clean Code, SOLID, KISS, DRY (com bom senso — duplicação acidental ≠ duplicação semântica). Em Zig, soma-se o lema da linguagem: **sem controle de fluxo oculto, sem alocação escondida, sem magia** — o que você lê é o que executa. Manter isso é filosofia, não estilo.

**Regra suprema:** se algo aumenta acoplamento, reduz observabilidade, cria dependência desnecessária, **vaza segredo, vaza memória, mistura contexto, ou pula registro** ou adiciona complexidade sem benefício claro, **provavelmente está errado**.

---

---

## 37. Anti-Padrões Vetados — "Macaquices" que Terminam Rápido e Quebram em Produção

> Atalhos que parecem entregar mais rápido e na real entregam vulnerabilidade, vazamento ou dívida. **Todos VETADOS** — não admitem ADR de exceção, são pisos. Aparecem em diff humano ou de IA → o PR para. Cada item traz o **veto** e o **caminho certo**.

### Segredos e exposição

1. **Segredo no bundle do cliente.** API key privada, secret de JWT, senha de banco, service-role key, token de pagamento no código que vai pro browser, ou em `NEXT_PUBLIC_*` / `VITE_*` / `REACT_APP_*`.
   → Segredo **só server-side** (BFF, route handler, secret manager). O navegador não guarda segredo (§13.4, §38).

2. **PII / token / senha em query string ou URL.** Acaba em log de acesso, histórico do browser, header `Referer`.
   → Vai em body ou header apropriado, nunca na URL (§32, §16.1).

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

8. **Confiar em `tenant_id` / `role` / `user_id` vindos do body ou header do cliente** sem validar contra o token.
   → Derivar sempre do token verificado, server-side (§15).

9. **JWT decodado sem validar** assinatura, `exp`, `aud`, `iss`, e `alg` contra allowlist (aceitar `alg: none` ou HS256 com pubkey RS256).
   → Validação completa em toda request (§14).

10. **Hash de senha fraco** — MD5, SHA1, sem salt, ou plaintext.
    → argon2id (ou bcrypt cost ≥ 12) via lib criptográfica revisada (§14).

11. **Rand não-cripto pra token, id de sessão, código de reset, nonce** (`std.rand.DefaultPrng` / RNG sem seed cripto).
    → CSPRNG: `std.crypto.random` (§14).

### CORS, headers e superfície

12. **`Access-Control-Allow-Origin: *` em rota autenticada** (pior ainda com `allow-credentials`).
    → Allowlist explícita de origens (§22.3 hardening).

13. **Endpoint de debug/admin/management sem auth, ou bind em `0.0.0.0`** expondo porta interna.
    → Bind restrito, auth obrigatória, `/debug` e `/actuator` retornam 404 externamente (§22.3).

14. **Mass assignment** — dar bind do body inteiro direto na entidade, deixando passar `is_admin`, `tenant_id`, `created_at`, `password_hash`.
    → Allowlist explícita de campos aceitos por endpoint.

### Erros, tipos e qualidade

15. **Catch que engole erro** — em Zig: `_ = foo()` que descarta um `error union`, `catch {}`, `catch unreachable`, `catch @panic(...)` em caminho de produção só pra calar o compilador, ou ignorar um `!T`.
    → Tratar com `catch |err| { ...trata/loga com trace_id... }`, propagar com `try`, limpar com `errdefer`. Degradar de forma consciente, nunca silenciar (detalhe no item 47).

16. **Calar o compilador à força** — `catch unreachable` / `orelse unreachable` em caminho de produção, `@ptrCast`/`@alignCast` pra contornar o tipo, `anytype` onde cabe tipo concreto, `@setRuntimeSafety(false)` local pra "passar".
    → Tratar o caso de erro/null de verdade (`catch |err|`, `orelse`), tipar concreto. Suprimir checagem **de segurança** (bounds/overflow) inline é VETADO sem ADR.

17. **Logar request/response inteiro, headers ou body cru "pra debugar".**
    → Logar campos específicos, mascarados. Nunca PII/token/senha (§16.1).

### Testes e cobertura

18. **Pular/comentar teste pra passar o CI** — comentar o bloco `test "..."`, remover o `try std.testing.expect(...)`, marcar `if (true) return error.SkipZigTest` sem motivo real.
    → Conserta o código, não silencia o teste (`references/testes-execucao.md`).

19. **Baixar o threshold de cobertura ou editar o gate** pra o número fechar.
    → Cobertura é contrato (§22). Sobe escrevendo teste, não mexendo na régua.

20. **Mockar o próprio sistema sob teste** retornando sucesso fixo, dando "verde" falso.
    → Testar comportamento real; mock só nas bordas externas.

### Dados e migrations

21. **Migration sem `down`, ou destrutiva sem backup** (`DROP`/`ALTER` que perde dado).
    → Reversível, testada com rollback antes do merge (§10).

22. **Cache de resposta autenticada sem chave por usuário/tenant** — um user recebe dado do outro.
    → Chave de cache sempre segmentada por usuário e tenant (§11, §15).

### Operação e entrega

23. **Container root, `chmod 777`, `--privileged`, filesystem RW** "pra funcionar".
    → Não-root, read-only, least-privilege (§13). O binário Zig estático facilita imagem mínima (`FROM scratch`) — use isso.

24. **Dependência nova sem verificar** nome (typosquatting), manutenção, licença, e sem pin de versão. Em Zig: entrada em `build.zig.zon` **sem hash de integridade** ou apontando pra `HEAD`.
    → Pin exato + **hash** em `build.zig.zon`, checar nome/manutenção/licença, SCA no pipeline (§13, §34, `references/cadeia-suprimentos.md`).

25. **Retry infinito / sem backoff/jitter** — DoS no próprio sistema ou no terceiro.
    → Limite explícito + backoff exponencial + jitter (§9, §18).

26. **`Idempotency-Key` aceito mas ignorado** (header existe, lógica não).
    → Implementar de fato a deduplicação (§12).

27. **Dual-write** — gravar no banco e publicar no broker no mesmo fluxo, sem outbox.
    → Transactional Outbox (§9, Anexo B).

28. **Pular o archive/MD "pra ir mais rápido"** (§28).
    → Archive é parte da entrega. Sempre gerado. Tarefa sem archive não está pronta (§35).

29. **Merge direto na `main` / force push em branch protegida / pular o PR e o review.**
    → Trunk-based com PR, CI verde, CODEOWNERS (§24).

30. **Desligar rate limit, validação de payload, ou security scan "temporariamente".**
    → "Temporário" vira permanente. Não se desliga piso de segurança (§12, §13).

31. **Criar serviço backend novo FORA do rol sancionado sem ADR de fit**, ou qualquer código novo em PHP.
    → Backend novo só em linguagem do **rol** (Go, Rust, Elixir, C#, Zig, Ruby) **com ADR (§27) justificando o fit**; escolher **Zig** quando o fit manda (controle manual de memória, interop C, artefato pequeno) — em empate, default pragmático é Go. Fora do rol exige **ADR de exceção**. Next.js/Astro seguem valendo só pro frontend. **PHP é proibido** e migra; **Node backend é legado** e sai pela regra dos ~30%/~50% (§3, §3.1, §3.2).

32. **Serviço que não sobe / crasha porque outro serviço está fora** (acoplamento de runtime, crash em cascata) — "o `ledger` não sobe sem o `core`".
    → Cada serviço é entidade à parte: sobe e opera sozinho; dependente ausente = degradação graciosa, nunca crash (§2, §18).

33. **Falha ao notificar/chamar outro serviço que derruba o chamador ou perde o dado** sem persistir, alertar e retomar.
    → Store-and-forward: persiste o intento (outbox/fila/Redis/DB), loga com `trace_id`, alerta (Grafana), retoma com retry+backoff+jitter → DLQ + escala (§18).
34. **Criar arquivos ou repos fora da pasta do projeto** (começar largando arquivos no root e depois **subir de diretório** — `cd ..`, `../` — pra criar repos irmãos fora; ou espalhar em `~`, `~/Documents`, `~/Downloads`, `/tmp`, Área de Trabalho).
    → Aplicação nova = **pasta dentro do workspace atual** (`./<projeto>_<contexto>/`). O agente não sai da pasta do projeto (ler ou escrever) sem o usuário pedir (§2).
35. **Editar código direto no servidor** (hml/prd), ou **subir mudança direto pra hml/prd** pulando `dev local → teste local → GitHub`.
    → Servidor é **imutável por edição manual**; recebe só artefato promovido do git. Hotfix segue o mesmo fluxo, acelerado (`references/ops.md` §1).
36. **Operar o servidor por fora do `<projeto>_ops`** — `ssh` + comando ad-hoc, editar arquivo no servidor, `docker`/`kubectl`/`systemctl` na mão, script solto.
    → **100%** de install/update/config/correção passa por comando do ops. Não tem comando? **cria no ops** (`references/ops.md` §2).
37. **Instalar/subir o sistema em série** ("um serviço de cada vez", 20 min).
    → Instalação **paralela por padrão** = `nproc` (`references/ops.md` §3).
38. **Serializar a instalação pra "funcionar"**, mascarando que um serviço depende de outro pra subir.
    → Erro que só ocorre em paralelo = **serviços não independentes** (fere piso 10/6). O ops **expõe** a colisão; corrigir a independência é **prioridade máxima**. Nunca esconder com serialização (`references/ops.md` §6).
39. **Redeploy que faz patch in-place / não parte do seed** (estado acumulado, drift entre implantações).
    → Todo redeploy é **destrutivo na app**: apaga a anterior e recria um clone zerado a partir de `/<app>/.env` (`references/ops.md` §2). Idempotente e reprodutível.
40. **Config/segredo de serviço fora do seed global**, ou repos do sistema espalhados fora de `/<app>/`.
    → `/<app>/.env` é a **fonte única** de config; o ops clona os repos dentro de `/<app>/` (`references/ops.md` §2).
41. **Apagar dados persistentes num redeploy** ("destrutivo" incluindo banco/volumes), ou `ops reset` de dados em prd.
    → Destrutivo é a **aplicação, nunca os dados**: banco/volumes/uploads preservados (migration reversível); apagar dado é `ops reset` **gated a dev/hml** (`references/ops.md` §2).
42. **Dois serviços no mesmo user Linux, serviço rodando como `root`, ou criar user/unit/permissão à mão.**
    → **Um user + systemd unit hardened por serviço**, provisionado **pelo ops** (`references/ops.md` §3). Blast radius mínimo.

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
    → Todo `alloc` tem seu `defer free` / `deinit` casado; erro no meio → `errdefer`. **Testar com `std.testing.allocator` / `GeneralPurposeAllocator`** que **falha o teste em leak** — leak detectado é bug, não warning. Ownership documentado no doc-comment `///` (quem aloca, quem libera). (`references/memoria-concorrencia.md`, `references/testes-execucao.md`).

49. **Rodar produção em `ReleaseFast` sem profiling que justifique** — `ReleaseFast` desliga checagem de bounds e de overflow: acesso fora de faixa e overflow viram **UB (undefined behavior)** silencioso, não crash controlado.
    → **Default seguro é `ReleaseSafe`** (mantém as checagens). Só troque pra `ReleaseFast` num caminho quente com **profiling que prove o ganho** e ADR registrando o trade-off. Segurança de memória não se troca por microssegundo sem evidência (§13).

50. **Abuso de `comptime`** — metaprogramação ilegível, camadas de geração de tipo que ninguém depura, `comptime` transformado em "macro soup".
    → `comptime` é **força** do Zig (sem controle de fluxo nem alocação oculta) — use pra o que ele é bom (validação em compilação, generics, tabelas), com moderação e legibilidade. Bloco `comptime` denso conta como código útil pro limite de tamanho (arquitetura §6). Não jogue a ferramenta fora, mas não a use pra esconder complexidade.

51. **Interop C (`@cImport`) sem validar no boundary** — puxar header C e deixar `[*c]u8`, ponteiros crus, structs C e retornos de erro C vazarem pra dentro do domínio; confiar em ponteiro/len vindos de C sem checar.
    → **Anti-Corruption Layer** (arquitetura §4): o adapter em `infrastructure/external/` valida (null, tamanho, código de erro) e **converte** pra tipos Zig seguros (`[]const u8`, `error union`, `?T`) antes de cruzar o boundary. `@cImport` é superfície de risco — trate como entrada hostil.

52. **Não fixar a versão exata do compilador Zig.** Zig é **pre-1.0**: há breaking changes entre versões, e um `.zig` que compila em uma versão quebra na seguinte. Deixar a versão "flutuar" = build irreprodutível e drift entre dev/CI/prd.
    → **Pin exato** da versão do compilador (Anexo A / `references/stack-versoes.md`), usada igual em dev, CI e prd; upgrade é mudança deliberada com ADR e teste, nunca implícita.

> Regra de bolso: se a justificativa começa com "só pra funcionar", "depois eu arrumo", ou "é mais rápido assim" e o resultado mexe em segredo, auth, dado, registro, **memória (leak/UB), erro engolido, ou toca o servidor por fora do fluxo/ops** — **provavelmente é uma macaquice desta lista. Para e faz certo.**

---

---
