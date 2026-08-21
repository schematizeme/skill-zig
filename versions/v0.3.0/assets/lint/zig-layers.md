# Guard de camadas em Zig (§4, §4.X)

> Zig **não** tem um linter de dependência por camada pronto (equivalente ao
> `depguard`/`golangci-lint` do Go). A fronteira `domain → application → infrastructure
> → interface` (`references/arquitetura.md` §4) é garantida por **estrutura de módulos +
> um guard-test simples** rodado no CI. `zig fmt --check` cobre formatação; este arquivo
> cobre a fronteira de imports. O guard de frontend (Node) fica em `eslint.layers.cjs`.

## 1. Estrutura que já força boa parte da fronteira

- Uma pasta por camada (`src/domain/`, `src/application/`, `src/infrastructure/`,
  `src/interface/`) e **um módulo raiz por camada** exposto via `build.zig`
  (`b.addModule("domain", ...)`, etc.).
- **`domain` não declara dependência de módulo** sobre `application`/`infrastructure`/
  `interface` nem sobre libs de IO no `build.zig` — se o grafo de módulos não dá a
  aresta, o `@import` nem compila. Essa é a primeira linha de defesa (mais forte que
  lint): a dependência proibida **não existe** no grafo de build.

## 2. Guard-test de imports proibidos (roda no CI)

Complementa a estrutura pegando `@import` por caminho relativo que fura a camada.
Rode via `zig build test` ou como passo de CI. Regras (as mesmas do §4):

- `src/domain/**` **não** importa `../application`, `../infrastructure`, `../interface`,
  nem std de IO/rede/persistência (`std.net`, `std.http`, driver de banco, `@cImport`).
- `src/application/**` **não** importa `../interface`.
- Toda integração com sistema externo passa por `src/infrastructure/external/` (ACL),
  e todo `@cImport` mora em `infrastructure` (nunca no `domain`) com boundary validado
  (`references/seguranca.md`).

Esboço de guard (grep-based, plugável no `build.zig` como step ou no CI):

```sh
# domain puro: nenhum import cruzando camada nem IO
if rg -n '@import\("(\.\./)?(application|infrastructure|interface)' src/domain \
   || rg -n '@cImport|std\.(net|http|fs)' src/domain; then
  echo "VIOLAÇÃO §4: domain importa camada externa / IO"; exit 1
fi
# application não importa interface
if rg -n '@import\("(\.\./)?interface' src/application; then
  echo "VIOLAÇÃO §4: application importa interface"; exit 1
fi
```

## 3. Complexidade e tamanho (§6, padroes-codigo.md)

O gate de tamanho/complexidade vem do `scripts/check-diff.sh` (arquivo > 750 bloqueia,
> 300 úteis flag) e da revisão (`/zig-review`). Zig não expõe ciclomática nativa; use o
flag de "> 300 linhas úteis" como proxy e quebre em micro-funções por coesão.
