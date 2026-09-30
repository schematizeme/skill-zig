# Segurança, Auth, Multi-tenancy, LGPD e Frontend


> **PONTEIRO, não cópia.** A normativa deste tema é da base: **`schematize-engineering`** →
> `references/seguranca.md`. Leia lá primeiro; aqui fica **só o que muda em Zig**.
>
> **Onde este arquivo divergir da base, a BASE MANDA** (`SKILL.md` §"Precedência e herança").
> Em 2026-08-21 os blocos idênticos à base foram **podados mecanicamente** (`tools/podar-clone.mjs`),
> e é por isso que a numeração **salta**: o número é o da base, e o item ausente aqui é o que **não
> muda nesta linguagem** — procure-o lá.

## Índice

- Z. Segurança específica de Zig (build mode, memória, overflow, interop C, cripto)

## 13. Segurança

### 13.4 Segredos no Cliente / Frontend / NextJS

- Guardar token de sessão em `localStorage`/`sessionStorage`. Sessão vai em **cookie `HttpOnly` + `Secure` + `SameSite`** (§38, a `schematize-qa` (`references/categorias.md` §§5 e 10) hardening).

## 14. Autenticação e Autorização

- Tokens, ids de sessão e códigos de reset gerados por **CSPRNG** — em Zig, `std.crypto.random` / `std.Random` de fonte segura (§Z.6); nunca PRNG previsível nem `Math.random()` do cliente (§37).

## 38. Frontend / NextJS / SPA — Regras Específicas

- CSP, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy` e `frame-ancestors` configurados (hardening; ver a `schematize-qa`, `references/categorias.md` §§5 e 10).

- Confiar em `redirect`/`next` param sem allowlist (open redirect — a `schematize-qa` (`references/categorias.md` §§5 e 10)).

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
  **`std.Io.Reader`** (✔ 0.16.0 — `std.io` **não existe mais**: `error: root source file struct
  'std' has no member named 'io'`) ou slices com comprimento conhecido, em vez de ponteiro cru +
  tamanho separado.

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
  **CSPRNG do sistema**, obtido pelo `Io`:

  ```zig
  var token: [32]u8 = undefined;
  io.random(&token);                 // CSPRNG, semeado por randomSecure; threadsafe
  var chave: [32]u8 = undefined;
  try io.randomSecure(&chave);       // SEMPRE syscall: sem depender de estado no processo
  ```

  `io.random` serve para o dia a dia (token, `jti`, OTP); **`io.randomSecure`** é para o
  material de vida longa (chave, semente), porque ele não reaproveita estado guardado no
  processo — o que importa depois de `fork` e em imagem/VM clonada, onde estado herdado
  significa **duas máquinas gerando o mesmo "aleatório"**.

  > **Isto mudou, e a API antiga não existe mais.** ✔ Verificado no **0.16.0**:
  > `std.crypto.random` → `error: root source file struct 'crypto' has no member named 'random'`.
  > **O risco aqui não é o erro de compilação** — é o "conserto" que ele provoca: o caminho mais
  > curto para fazer compilar de novo é `std.Random.DefaultPrng`, que **compila**, parece
  > aleatório e é o **Xoshiro previsível** que o item abaixo veta. O erro é barulhento; a
  > correção errada é silenciosa.

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

- **MUST:** comparação de segredo (MAC, hash, OTP) em **tempo constante** —
  **`std.crypto.timing_safe.eql(T, a, b)`** (✔ 0.16.0; o antigo `std.crypto.utils.timingSafeEql`
  saiu: `error: root source file struct 'crypto' has no member named 'utils'`), nunca `==`/`mem.eql`,
  que retorna no primeiro byte diferente e vaza o prefixo correto pelo tempo.

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
