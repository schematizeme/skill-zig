# Segurança, Auth, Multi-tenancy, LGPD e Frontend

> Parte da skill **schematize-zig**. As referências cruzadas (§N) apontam para seções do corpo completo — todas presentes no conjunto de references desta skill. Liga com `references/memoria-concorrencia.md` (allocator/limites), `references/iam.md` (auth), `references/arquitetura.md §3` (escolha de linguagem/fit) e `references/stack-versoes.md` (versão do toolchain).

## Índice
- 13. Segurança
- 14. Autenticação e Autorização
- 15. Multi-tenancy
- 32. LGPD e Dados Pessoais
- 38. Frontend / NextJS / SPA — Regras Específicas
- Z. Segurança específica de Zig (build mode, memória, overflow, interop C, cripto)

---

## 13. Segurança

**MUST — pipeline (fail on high/critical)**
- Dependabot ou Renovate
- SAST (Semgrep / CodeQL)
- SCA (dependências + licenças)
- Container scan (Trivy / Grype)
- Secret scan (Gitleaks)
- Commit signing (GPG / SSH / Sigstore)
- SBOM no build (CycloneDX ou SPDX)

**MUST — runtime**
- Containers não-root, read-only filesystem.
- Distroless ou chainguard quando viável.
- Multi-stage build.
- Healthcheck na imagem.

**MUST — segredos**
- Nunca em código, nunca em env file commitado.
- Storage: Vault, AWS/GCP Secret Manager, sealed-secrets.
- Rotação documentada.

**Licenças permitidas:** MIT, Apache 2.0, BSD, MPL 2.0, ISC.
**Bloqueadas sem ADR:** GPL/AGPL, SSPL, proprietárias.

### 13.4 Segredos no Cliente / Frontend / NextJS

**VETADO — sem exceção, sem ADR**

- **Qualquer segredo no bundle que vai pro browser.** API key privada, secret de JWT, senha de banco, service-role key (Supabase/Firebase admin), token de provedor de pagamento, chave de terceiro — **nada** disso entra em código que o cliente baixa. O navegador não guarda segredo. Ponto.
- Prefixar segredo com `NEXT_PUBLIC_` (ou equivalente `VITE_`, `REACT_APP_`, `PUBLIC_`). Esse prefixo **expõe a variável publicamente por definição** — usar só para valor que pode estar num outdoor.
- Chamar API de terceiro com chave secreta **direto do browser**. Toda chamada que usa segredo passa por um **BFF / route handler / server action** server-side (§38).
- Guardar token de sessão em `localStorage`/`sessionStorage`. Sessão vai em **cookie `HttpOnly` + `Secure` + `SameSite`** (§38, a `schematize-qa` (smoke e matriz simulated, `references/categorias.md` secoes 5 e 10) hardening).
- Confiar em validação de auth/role feita no client (`if (user.isAdmin)` no React) como controle de acesso. Isso é UX, não segurança — a decisão é **sempre server-side** (§15, §37).

> "Coloca a senha no NextJS pra funcionar" não é uma solução, é um vazamento agendado. Se o cliente pode ver, o atacante já viu.

---

---

## 14. Autenticação e Autorização

- OAuth2 / OIDC.
- JWT assinado (RS256 ou EdDSA; **nunca HS256** em fluxo público).
- Validação **completa** do JWT em toda request: assinatura, `exp`, `nbf`, `aud`, `iss` e `alg` contra allowlist. Decodar o payload e confiar é VETADO (§37).
- Refresh token rotativo com detecção de reuso.
- RBAC com permissões granulares; ABAC quando necessário.
- Hash de senha: **bcrypt cost ≥ 12** ou **argon2id**. MD5/SHA1/sem-salt/plaintext são VETADOS (§37).
- Tokens, ids de sessão e códigos de reset gerados por **CSPRNG** — em Zig, `std.crypto.random` / `std.Random` de fonte segura (§Z.6); nunca PRNG previsível nem `Math.random()` do cliente (§37).

---

---

## 15. Multi-tenancy

**MUST — quando aplicável (SaaS, plataformas)**
- Isolamento de tenant explícito em todas as camadas.
- `tenant_id` propagado em contexto, logs e traces.
- Autorização validada **server-side** em toda operação. **Nunca** confiar em `tenant_id` (ou role, ou user_id) enviado pelo cliente sem verificação contra o token. Derivar sempre do token, server-side.
- Queries com `tenant_id` no `WHERE`, sempre. Considerar Row Level Security no Postgres.

**SHOULD**
- Testes de cross-tenant leak em CI.
- Métricas e logs particionáveis por tenant.

---

---

## 32. LGPD e Dados Pessoais

**MUST**
- Classificação de dados: público, interno, confidencial, pessoal, pessoal sensível.
- PII nunca em logs (ver §16.1).
- Política de retenção documentada por tipo de dado.
- Processo para exercício de direitos (acesso, correção, eliminação, portabilidade).
- Criptografia em trânsito (TLS 1.2+) e em repouso para dados pessoais.
- DPIA para tratamentos de alto risco.
- PII **nunca** em query string / URL (acaba em log, histórico, referer) — §37.

---

---

## 38. Frontend / NextJS / SPA — Regras Específicas

**MUST**
- **Fronteira clara client/server.** Tudo que toca segredo, banco, ou terceiro com credencial roda **server-side** (route handler, server action, BFF, server component que não serializa segredo pra props).
- Sessão em **cookie `HttpOnly` + `Secure` + `SameSite=Lax|Strict`**. Token de auth **nunca** em `localStorage`/`sessionStorage` (XSS lê tudo lá).
- Variáveis públicas (`NEXT_PUBLIC_*` etc.) contêm **apenas** dado não-sensível (URL de API pública, id de analytics público). Tratar esse prefixo como "vai pro outdoor".
- Validação de input no client é **UX**; a validação que importa é a do servidor (§12). Autorização idem é server-side (§15).
- CSP, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy` e `frame-ancestors` configurados (a `schematize-qa` (smoke e matriz simulated, `references/categorias.md` secoes 5 e 10) hardening).
- Chamada a API de terceiro com chave secreta passa por proxy server-side. O browser nunca segura a chave.

**VETADO**
- Service-role key / admin SDK (Supabase, Firebase, etc.) no código do client.
- `dangerouslySetInnerHTML` com conteúdo não sanitizado (XSS).
- Confiar em `redirect`/`next` param sem allowlist (open redirect — a `schematize-qa` (smoke e matriz simulated, `references/categorias.md` secoes 5 e 10)).

> "Bota a senha no NextJS" não existe como solução. Existe como CVE. O front pede ao servidor; o servidor guarda o segredo.

---

---

## Z. Segurança específica de Zig

Zig dá **controle manual de memória** e chega perto do metal. Isso é a força da linguagem
e, ao mesmo tempo, a fonte de toda a superfície de risco: a garantia de segurança **não é
automática** — ela depende do **build mode**, do tratamento **explícito** de overflow, do
**parse defensivo** de input e da **validação rígida** de toda fronteira C. Os pisos abaixo
são **inegociáveis** para qualquer serviço Zig exposto a input hostil. Nenhum deles afrouxa
um piso agnóstico das §13–§38 — eles **concretizam** o "auth server-side / sem UB explorável"
no idioma Zig.

### Z.1 Memory safety é função do build mode — ReleaseSafe é o piso

Em Zig a segurança de memória **muda com o modo de compilação**. Isto não é detalhe de
performance: define se um bug de memória é um **trap controlado** ou um **exploit**.

| Build mode | Bounds check | Overflow de inteiro | UB de memória | Uso |
|---|---|---|---|---|
| **Debug** | Sim (trap) | Trap | Detectado (trap) | Dev/teste local |
| **ReleaseSafe** | **Sim (trap)** | **Trap** | **Trap controlado** | **PRODUÇÃO — piso da casa** |
| **ReleaseFast** | **Não → UB** | **Não → UB** | **UB (explorável)** | Só com ADR + profiling |
| **ReleaseSmall** | **Não → UB** | **Não → UB** | **UB (explorável)** | Só com ADR + profiling |

- **MUST:** rodar produção em **ReleaseSafe** é o piso, salvo perfil que justifique
  ReleaseFast **por ADR + profiling** (`references/arquitetura.md §3`). ReleaseSafe mantém
  bounds check, trap de overflow de inteiro e detecção de acessos ilegais — um bug vira
  **crash determinístico** (falha fechada), não um primitivo de escrita para o atacante.
- **VETADO:** subir serviço **exposto a input hostil** em **ReleaseFast/ReleaseSmall** sem
  **ADR + profiling** que comprove o gargalo e delimite a superfície. Nesses modos as
  checagens somem: `use-after-free`, `out-of-bounds`, `double-free` e overflow silencioso
  viram **UB explorável** (corrupção de heap, ROP, disclosure).
- **SHOULD:** mesmo quando um hot path exige ReleaseFast, isolar esse trecho e manter o
  perímetro que toca input externo (parsing, deserialização, boundary de rede) em código
  com checagem — o UB não pode nascer no ponto onde o atacante escreve.
- **MUST:** rodar a suíte de testes e fuzzing em **Debug/ReleaseSafe** para que os traps
  disparem em CI antes de qualquer bug chegar em produção.

### Z.2 Overflow de inteiro é explícito — trate, nunca confie

Zig separa aritmética que **trapa** da que **envolve (wrapping)**: `a + b` trapa em
ReleaseSafe/Debug; `a +% b` faz wrapping silencioso; `@addWithOverflow` devolve o carry.
Isso é uma **feature de segurança** — mas só se o código a respeitar.

- **MUST:** todo cálculo de **tamanho, índice, offset ou contador** derivado de **input
  externo** (campo de comprimento, header, valor do protocolo) trata overflow
  explicitamente (`std.math.add`/`mul` que retornam erro, `@addWithOverflow`, checagem de
  limite antes da conta). Overflow em cálculo de tamanho é o caminho clássico para
  under-allocation seguido de OOB write.
- **VETADO:** usar operadores wrapping (`+%`, `-%`, `*%`) em aritmética guiada por input
  hostil só para "não dar panic". Wrapping mascara o ataque em vez de barrá-lo — só se usa
  wrapping onde o wrap-around é **semanticamente correto e intencional** (hash, contador
  cíclico), nunca como escape de validação.
- **VETADO:** confiar em `@intCast`/`@truncate` sobre valor de atacante sem checar a faixa
  antes — truncamento silencioso de um tamanho vira alocação/loop errado.

### Z.3 Parse defensivo de input hostil

Todo byte que vem da rede, de arquivo ou de IPC é hostil até prova em contrário. O parser é
a primeira linha e onde mais se sangra.

- **MUST:** **limite de tamanho** em toda leitura e em toda coleção que cresce. **VETADO**
  alocar em cima de um **campo de tamanho controlado pelo atacante** sem teto — é DoS de
  memória imediato. Todo `alloc(n)` onde `n` vem do input passa por um **limite máximo
  configurado** e um **allocator com budget** (liga com `references/memoria-concorrencia.md`:
  allocator + limite + arena por request).
- **MUST:** **bounds em toda leitura** — nunca indexar buffer com offset derivado de input
  sem checar `offset + len <= buf.len` (com a soma protegida contra overflow, §Z.2). Preferir
  `std.io.Reader`/slices com comprimento conhecido a ponteiro cru + tamanho separado.
- **MUST:** tratar **todo `error` de parse** — Zig força o `try`/`catch`; **VETADO**
  engolir erro de parse com `catch unreachable` ou `catch undefined` em path que vê input
  externo (`unreachable` em ReleaseFast é UB puro).
- **SHOULD:** **fuzzing** (ex.: harness com entrada aleatória rodando em ReleaseSafe) do
  parser de todo protocolo/formato exposto; qualquer trap encontrado é bug de segurança.

### Z.4 Interop C (`@cImport`) é A superfície de risco

`@cImport`/`extern` cruzam a fronteira onde as garantias de Zig **param**. Do lado C não há
bounds check, não há trap de overflow, não há `error` — a memória é território não-confiável.

- **MUST — trate a lib C como não-confiável:** toda fronteira com C **valida** antes e depois
  da chamada: **ponteiros** (não-nulos quando exigido, alinhamento, ownership claro de quem
  aloca/libera), **tamanhos** (o `len` que se passa ao C bate com o buffer real; o `len` que
  o C devolve é checado antes de usar), **strings** (NUL-terminação garantida ao entrar,
  comprimento re-derivado ao sair — nunca assumir terminação vinda do C).
- **MUST:** **todo retorno de erro do C é tratado** — código de retorno, `errno`, ponteiro
  nulo de falha. **VETADO** ignorar o status de uma chamada C e seguir usando o resultado.
- **MUST:** a garantia de memória do Zig **não atravessa** para dentro da lib C. Um
  `use-after-free` ou OOB **dentro** do C não é pego pelo ReleaseSafe — o boundary Zig só
  protege o lado Zig. Documente ownership e ciclo de vida de cada ponteiro que cruza.
- **SHOULD:** encapsular cada lib C atrás de um **wrapper Zig fino e único** que faz toda a
  validação num só lugar (uma função por arquivo, comentada — §padrões de código), expondo
  ao resto do sistema uma API Zig segura com `error` idiomático. O resto do código nunca
  chama o C cru.
- **SHOULD:** preferir, quando existir, a implementação **`std`** em vez de linkar C
  (menos superfície); ao escolher Zig **justamente pelo interop C**, o custo de validação
  extra é parte do trade-off e entra no ADR (§Z.8).

### Z.5 Segredos nunca no binário nem na fonte

- **VETADO:** hardcode de segredo no código Zig, e **VETADO** embutir config sensível no
  binário via **`@embedFile`** (chave, credencial, token) — `@embedFile` cola o conteúdo no
  executável em texto recuperável; um binário publicado é um segredo publicado.
- **MUST:** segredos vêm de **secret manager / variável de ambiente server-side** em
  runtime (§13 "MUST — segredos"), nunca compilados. `@embedFile` serve para asset público
  (template, schema, migration), nunca para material sensível.
- **MUST:** nada de segredo no cliente/frontend — vale igual o §13.4; um serviço Zig segue a
  mesma fronteira (o segredo mora no servidor).

### Z.6 CSPRNG — só fonte segura

- **MUST:** token de sessão, `jti`, código OTP/reset, refresh token, salt e nonce vêm de
  **CSPRNG** — `std.crypto.random` (semeado do OS) ou `std.Random` **explicitamente ligado a
  uma fonte segura**. 
- **VETADO:** `std.Random.DefaultPrng`/`Xoshiro` e qualquer PRNG **determinístico/previsível**
  para material de segurança — servem para simulação/teste, nunca para segredo. Um token
  previsível é um bypass de auth (§37, casa com `references/iam.md`).

### Z.7 Cripto — use `std.crypto`, não role a sua

- **MUST:** para primitives sensíveis, usar **algoritmos revisados de `std.crypto`** (AEAD
  como ChaCha20-Poly1305/AES-GCM, curvas Ed25519/X25519, hashes SHA-2/3, HMAC, KDFs) — nunca
  **role a sua própria cripto**, nunca invente construção nova (§37).
- **SHOULD:** o ecossistema Zig ainda é **jovem** — ao sair do `std.crypto`, prefira lib C
  madura e auditada (ex.: libsodium/BoringSSL via `@cImport`, com o boundary validado de
  §Z.4) a implementação artesanal Zig não revisada. Para **hash de senha**, use **argon2id**
  (ou bcrypt cost ≥ 12) de `std.crypto` quando disponível, ou lib C revisada por `@cImport` —
  ver `references/iam.md`.
- **MUST:** comparação de segredo (MAC, hash, OTP) em **tempo constante**
  (`std.crypto.utils.timingSafeEql`), nunca `==`/`mem.eql` que vaza timing.

### Z.8 Posicionamento honesto — quando Zig, quando Rust

- Componentes **sensíveis de auth/cripto** costumam **encaixar melhor em Rust** (segurança de
  memória por default, ecossistema WebAuthn/OIDC/argon2 maduro) — ver o fit guide em
  `references/arquitetura.md §3` e `references/iam.md`.
- **Escolha Zig** quando o requisito real é **controle manual de memória**, **interop C**
  direto, ou **artefato pequeno/sem runtime**. Feita essa escolha, o piso de boundary e
  validação (§Z.1–§Z.7) vale com **rigor extra** — o custo de segurança que o Rust dava de
  graça passa a ser responsabilidade explícita do código Zig, e isso entra no **ADR de fit**.
- **VETADO** escolher Zig para um serviço de auth/cripto "porque é rápido" sem ADR que pese
  esse custo — a decisão é honesta ou não é.

---

---
