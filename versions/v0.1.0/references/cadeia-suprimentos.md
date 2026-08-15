# Cadeia de Suprimentos de Software (supply chain) — Zig

> Piso de **segurança da cadeia de suprimentos** — consolida num só lugar o que
> antes ficava espalhado (higiene de dependência em `seguranca.md`, imagem/deploy
> em `operacao.md`). O ataque hoje raramente é no seu código: é numa dependência,
> numa imagem base ou no pipeline. Trate build e dependências como superfície de
> ataque de primeira classe. Em Zig há **duas particularidades que puxam a corda**:
> (1) o lockfile de fato é o **hash criptográfico** de cada dependência no
> `build.zig.zon`; (2) a **versão exata do compilador é parte da cadeia** — Zig é
> pre-1.0. Liga forte com `references/stack-versoes.md` (pin da toolchain) e com
> `references/memoria-concorrencia.md`.

## Índice
- S1. Dependências e `build.zig.zon` (o hash é o lockfile)
- S2. Pin da toolchain é parte da cadeia
- S3. Cross-compilation reprodutível e pinada
- S4. SBOM e vulnerabilidades (honesto: scanner Zig-native é jovem)
- S5. Imagem de container
- S6. Pipeline e proveniência (SLSA)
- S7. Segredos no build

---

## S1. Dependências e `build.zig.zon` (o hash é o lockfile)

O gerenciador de pacotes do Zig é o **`build.zig.zon`**: cada dependência é
declarada com **URL do artefato + `hash` criptográfico**. **O hash é o lockfile de
fato** — o build **falha** se o conteúdo baixado não bater com o hash fixado. Não
existe "lockfile separado" a manter: o pin vive no `.zon`, versionado no git.

**MUST**
- **Toda dependência com `hash` fixado** no `build.zig.zon`, commitado. O build é
  reprodutível a partir dele — mesmo hash, mesmo bytes, sempre.
- **Verificar nome, licença e origem** de toda dependência nova: typosquatting é
  real (nome/URL quase igual ao popular); licença na allowlist (MIT/Apache-2.0/BSD/
  MPL-2.0/ISC ok; GPL/AGPL/SSPL/proprietária só com ADR §27). Ao adicionar C via
  `@cImport`, a licença da lib C entra na mesma allowlist.
- **Minimizar superfície:** cada dep (Zig ou C embarcada) é código de terceiro no
  seu artefato estático. Avalie peso, manutenção e árvore transitiva antes de
  adicionar; corte o que não usa. Menos dep transitiva é menos risco.
- **Fixe `minimum_zig_version`** no `build.zig.zon` — o piso mínimo de compilador do
  projeto faz parte do contrato de dependência (detalhe em S2).

**SHOULD**
- Atualização de dep é mudança deliberada: revisa o diff da árvore, roda a suíte com
  leak gate (`references/testes.md`) e o cross-compile de smoke antes de promover.
- Espelhar (mirror) o artefato das deps críticas para o build não depender de um
  upstream no ar no dia do release.

**VETADO**
- **Dependência sem `hash`** ou apontando para **branch/tag móvel** (`main`, `HEAD`)
  em produção — sem hash não há reprodutibilidade nem defesa contra troca silenciosa
  do conteúdo no upstream.
- Instalar de fonte não confiável / `curl | sh` de origem não verificada no build.
- Embarcar lib C via `@cImport` sem registrar origem/licença/versão no ADR e sem o
  **boundary validado** (`references/seguranca.md`).

---

## S2. Pin da toolchain é parte da cadeia

Zig é **pre-1.0**: breaking changes de sintaxe, `std`, `build.zig` e do próprio
gerenciador de pacotes acontecem entre releases. Logo, **a versão exata do
compilador é contrato de build** — tão parte da cadeia quanto o `build.zig.zon`.
"Roda no meu Zig" não é reprodutível se o teu Zig e o do CI diferem.

**MUST**
- **Fixar a versão exata do Zig** e mantê-la concordante em **três lugares**:
  `minimum_zig_version` no `build.zig.zon`; a versão **exata** instalada no CI (não
  "a mais recente"); e a versão provisionada pelo `<projeto>_ops`/README. Detalhe e
  fluxo em **`references/stack-versoes.md` §3**.
- **Uma fonte da verdade da versão** (`.zig-version` ou variável no ops) consumida
  por dev, CI e deploy — ninguém escolhe a sua.
- **Releases marcadas** (`0.14.0`, `0.15.1`, …) no artefato que vai pra hml/prd;
  nightly/`master` só em spike de exploração.

**VETADO**
- Build, CI e servidor em **versões diferentes** do compilador.
- Depender de `master`/nightly no artefato de release.
- Bumpar o compilador direto no servidor "pra ver se resolve" — fere o fluxo de
  ambientes (`references/stack-versoes.md`, `references/operacao.md`).

> O upgrade de versão do Zig é ADR (§27): registra de/para, o que quebrou, e passa
> pelo fluxo normal (dev → local → github → hml → prd).

---

## S3. Cross-compilation reprodutível e pinada

Cross-compilation é força de primeira classe do Zig: `zig build -Dtarget=<arch>-<os>-
<abi>` produz **artefato estático pequeno multi-alvo sem toolchain externa**. Isso é
vantagem de cadeia — menos ferramenta de terceiro no caminho do build.

**MUST**
- **Cada alvo de release é reproduzível e pinado:** o conjunto de `-Dtarget` suportados
  é declarado no `build.zig` (código, versionado), buildado no CID com a versão fixada
  do Zig. Mesmo compilador + mesmo `.zon` + mesmo target ⇒ mesmo binário.
- **Build mode de produção é `ReleaseSafe`** salvo ADR + perfil (`references/memoria-
  concorrencia.md` §M4) — mantém bounds check e trap de overflow; a cadeia entrega um
  binário **defensável**, não um `ReleaseFast` com UB explorável.
- **Smoke de cross-compile no CI:** todo alvo suportado compila (e, quando possível,
  roda o smoke test) antes de promover.

**SHOULD**
- O artefato estático pequeno vira **imagem `scratch`/distroless natural** (S5) — sem
  runtime dinâmico a carregar, a superfície da imagem final despenca.

---

## S4. SBOM e vulnerabilidades (honesto: scanner Zig-native é jovem)

Aqui a casa é **pragmática e honesta**: o ecossistema de SCA nativo de Zig é jovem —
não há um `cargo audit`/`govulncheck` maduro equivalente. O piso de "saber o que
embarca e travar em vuln conhecida" **não afrouxa**; muda o **como**.

**MUST**
- **Gerar SBOM** (CycloneDX/SPDX) no build e **versioná-la junto ao artefato** — é o
  inventário do que foi de fato embarcado. Sem gerador Zig-native maduro, **derive a
  SBOM do `build.zig.zon`** (deps + URLs + hashes) e das libs C embarcadas via
  `@cImport` (nome + versão + origem). O `.zon` já é a lista de materiais pinada;
  formalize-a em SBOM.
- **Scan de imagem no CI, travando o merge** em `high`/`critical` sem ADR de aceite:
  **Trivy/Grype** na imagem final (pega CVE da base e de libs de sistema).
- **Secret scan no pipeline** (**Gitleaks**/trufflehog) travando vazamento antes do
  merge (detalhe em S7).
- **Onde não há SCA Zig-native, o piso mínimo é `hash-pin` + revisão manual da árvore
  de dependências** — humano olha o diff das deps a cada bump. Vuln aceita
  conscientemente vira **ADR com prazo de correção**, nunca silêncio.

**SHOULD**
- Acompanhar o amadurecimento das ferramentas Zig-native e adotar SCA automatizado
  assim que houver um confiável; registrar a decisão no ADR.
- Revisão periódica das libs C embarcadas contra os advisories daquele projeto C
  (elas carregam o histórico de CVE da linguagem host).

> Honestidade de ecossistema: **sem SCA Zig-native maduro, o hash-pin do `.zon` + a
> revisão manual da árvore é o chão** — mais trabalho humano, mesmo objetivo. Não
> finja um `audit` automático que a linguagem ainda não tem; declare o gap e a
> mitigação (Trivy/Grype na imagem, Gitleaks no repo, revisão da árvore).

---

## S5. Imagem de container

O binário Zig é **estático e pequeno** — a imagem final quer ser mínima por natureza.

**MUST**
- **Base mínima e pinada por digest** (`@sha256:...`), não por tag móvel
  (`latest`/`1`). Com binário estático, **`scratch`/distroless** é o destino natural
  — quase nenhum pacote, quase nenhuma CVE de base.
- **Multi-stage build:** estágio *builder* com a toolchain Zig (versão fixada, S2)
  compila o binário estático; a imagem final é `scratch`/distroless carregando **só o
  binário** e o mínimo de runtime (certificados, se fizer chamada TLS).
- **Não-root, filesystem read-only**, sem capabilities desnecessárias (liga com o
  piso de container do `operacao`/`seguranca`).

**SHOULD**
- Rebuild periódico pra absorver patch da base; rescan (Trivy/Grype) da imagem
  publicada.

---

## S6. Pipeline e proveniência (SLSA)

**MUST**
- **Build só no CI** (não na máquina do dev pra produção), a partir do código
  versionado e da **versão fixada do Zig** (S2); o pipeline é parte da TCB (base de
  confiança).
- **Assinar o artefato/imagem** (cosign/sigstore) e **verificar a assinatura na
  admissão** (deploy só aceita imagem assinada por pipeline confiável). Assinar sem
  verificar não protege.
- **Proveniência:** emitir atestação de build (quem buildou, de qual commit, com qual
  `build.zig.zon`/hashes, com qual **versão do Zig** e quais `-Dtarget`) — alvo
  **SLSA** crescente. Tag de imagem inclui o commit.
- **Commit signing** obrigatório (branch protegida, review antes de buildar release).

**SHOULD**
- Permissões mínimas no CI (token escopado, sem segredo amplo).
- Anotar no CHANGELOG/ADR a versão do Zig usada em cada release (`references/stack-
  versoes.md`).

---

## S7. Segredos no build

**MUST**
- **Nenhum segredo no artefato/imagem** nem em layer intermediária (layer é
  inspecionável). Segredo de build via mecanismo efêmero (BuildKit secret mount),
  nunca `ARG`/`ENV` persistido nem `COPY .env`.
- **Segredo nunca no `build.zig`/`build.zig.zon`** — o build é código versionado;
  chave, token ou URL com credencial ali é vazamento no git.
- **Secret scan no pipeline** (Gitleaks/trufflehog) travando vazamento antes do
  merge. `.env` real fora do git.

> Regra de bolso Zig: **você entrega tudo que embarca — e a versão do compilador que o
> produziu.** Hash-pin no `.zon` + versão do Zig fixada + SBOM derivada do `.zon` +
> scan de imagem/segredo que trava + imagem `scratch`/distroless pinada e assinada +
> build no CI sem segredo no layer. Sem SCA Zig-native maduro, o hash-pin + revisão
> manual da árvore é o piso. Se não dá pra dizer exatamente o que tem dentro do
> binário, com qual Zig, de qual commit — a cadeia está aberta.
