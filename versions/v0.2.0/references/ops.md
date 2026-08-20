# Operação pelo ops — ambientes, instalação e correção (control plane)

> O **`<projeto>_ops`** é a **interface única** de operação do sistema. Invariantes desta reference, todos **INEGOCIÁVEIS**: (1) nada chega ao servidor sem passar pelo **fluxo de promoção** (dev local → teste local → GitHub → hml → prd); (2) o ops provisiona num **workspace por aplicação** (`/<app>/`) e todo **redeploy é destrutivo na aplicação, semeado pelo `/<app>/.env` global** — mas **nunca destrói dados**; (3) cada serviço roda **isolado por usuário** (user Linux + systemd hardened); (4) **100%** de instalação/atualização/correção/config passa por uma **ferramenta do ops** — nunca à mão; (5) instalar é **paralelo por padrão** (= `nproc`), e falha no paralelo = **bug de independência** (prioridade máxima). Contexto do ops: `arquitetura.md` §2. Deploy/ambientes: `operacao.md` §21. Test kit: `testes.md` §22.1.

## 1. Ambientes e o fluxo de promoção (nada direto no servidor)

Ambientes isolados: **dev** (local) · **hml** (homologação/staging) · **prd** (produção). O caminho de qualquer mudança é **fixo e sem atalho**:

```
desenvolvimento local  →  teste local (verde)  →  GitHub (merge)  →  hml  →  prd
```

- **Nada pula etapa.** Nunca vai direto pra hml ou prd. hml só recebe o que está no GitHub e passou no teste local; prd só recebe o que foi homologado em hml.
- **VETADO editar código direto no servidor (hml/prd).** O servidor é **imutável por edição manual** — recebe apenas **artefato promovido do git** (mesma imagem/commit SHA, §21). "Editei direto no prd pra resolver rápido" é o anti-padrão que esta reference existe pra matar.
- **Hotfix segue o mesmo fluxo, acelerado:** branch → teste local → git → hml → prd. Urgência **não** autoriza mão no servidor.
- **Precauções concretas:** deploy só aceita artefato com **proveniência git** (commit SHA); filesystem **read-only** em hml/prd; **drift detection** (o ops recusa/alerta divergência com o git); acesso de escrita = **exceção auditada** (break-glass no archive), nunca o fluxo.

## 2. Layout no servidor, seed global e redeploy destrutivo

O ops provisiona num **workspace por aplicação**, espelhando no servidor a contenção de workspace local (`arquitetura.md` §2):

- **`/<app>/` é a raiz da aplicação no servidor.** O ops **cria** essa pasta e **clona os repos dentro** dela: `/<app>/<app>_<contexto>` (ex.: `/payle/payle_core`, `/payle/payle_storage`, `/payle/payle_ops`). Nada de repo espalhado pelo host.
- **`/<app>/.env` é o SEEDER GLOBAL — a fonte única.** Toda a configuração da aplicação inteira parte desse arquivo. É a **única** fonte de verdade de config em runtime; **nenhum serviço tem config à parte** fora do seed. (Segredo real via secret manager referenciado pelo seed — segredo nunca versionado no repo.)
- **Redeploy é DESTRUTIVO na aplicação, a partir do seed.** Todo (re)deploy: **apaga a implantação anterior** e **recria um clone novo, zerado**, configurado **exclusivamente** a partir de `/<app>/.env`. Sem patch in-place, sem estado acumulado, sem drift. O estado da app é 100% derivado do seed → **idempotente e reprodutível**: `ops redeploy` sempre entrega o mesmo resultado, do zero.
- **"Destrutivo" é a APLICAÇÃO, nunca os DADOS.** O que é destruído e recriado: o clone dos repos, binários/build, config renderizada, o processo. O que é **preservado**: **dados persistentes** (banco, volumes, uploads, filas), que só mudam por **migration reversível** (com `down` + backup). Apagar dados é comando **separado e gated** (`ops reset`), **só em dev/hml**, com confirmação explícita — **nunca** em prd.

## 3. Isolamento por usuário — um user + systemd por serviço

Cada serviço roda **confinado**, pra que um comprometimento não vaze para os outros nem para o host (**blast radius mínimo**):

- **Um usuário Linux dedicado por serviço/repo.** `payle_core` roda como user `payle_core`; `payle_storage` como user `payle_storage`. **Nunca** dois serviços no mesmo user; **nunca** `root`. A pasta de cada repo pertence ao user do serviço (isolamento a nível de usuário no filesystem).
- **Um systemd unit isolado por serviço**, rodando como o user dedicado, com **hardening**: `User=<svc>`, `NoNewPrivileges=yes`, `ProtectSystem=strict`, `ProtectHome=yes`, `PrivateTmp=yes`, `ReadWritePaths=` só o necessário, `CapabilityBoundingSet=` mínimo.
- **Blast radius contido:** servidor comprometido por um serviço → o atacante mexe **só naquela** aplicação; os outros serviços (users/units/pastas distintos) e o host seguem protegidos. É defesa em profundidade por design.
- **Automatizado pelo ops, SEMPRE.** Criar o user, ajustar permissão da pasta, gerar o systemd unit hardened e fazer o wiring é **feito pelo ops** (`ops install`/`ops redeploy`) — **nunca à mão**. É parte do provisionamento, não um passo manual esquecível.

## 4. O ops é a interface única (100% das operações)

**Toda** operação sobre o servidor — instalar, subir, atualizar, configurar, migrar, corrigir, reverter, diagnosticar — passa por um **comando do `<projeto>_ops`**. **Zero** exceção:

- **Proibido** `ssh servidor` + comando ad-hoc, editar arquivo no servidor, `docker`/`kubectl`/`systemctl` na mão, script solto. Se **não existe** comando de ops pra aquilo, **cria o comando no ops** — não faz por fora. O que não está no ops não aconteceu (e não é reproduzível).
- **Autonomia e completude (requisito, não meta):** o ops é uma **aplicação/CLI coesa, idempotente e autodescritiva** que instala e opera o sistema inteiro **sem depender da IA**. Um humano — o próprio usuário — provisiona um servidor **do zero** só com o ops. `ops install` sobe tudo; `ops redeploy` recria do seed; `ops doctor` diagnostica tudo.
- **Superfície mínima** (idempotentes, com `--help` e saída machine-readable): `bootstrap` (cria `/<app>/` e clona os repos) · `install`/`up` · `redeploy` (destrutivo, do seed §2) · `update` · `config` (do `/<app>/.env`) · `migrate` (reversível) · `health`/`doctor` · `rollback` · `logs`/`troubleshoot` · `reset` (destrói dados — gated, dev/hml) · `test` (§22.1).
- **Correção/hotfix é `ops update`/`ops redeploy`/`ops rollback`** — nunca mão no servidor (§1). O ops sobe com observabilidade integrada (§16) e **grava o archive** de cada operação (§28).

## 5. Instalação SEMPRE paralela (= nº de cores)

Instalar/subir/recriar um sistema **não pode** levar 20 min em série.

- O ops instala/sobe/recria **módulos e microserviços em paralelo**, grau = **`nproc`** (default; `--jobs N`/`OPS_JOBS` sobrepõe).
- É o análogo em runtime do fan-out de orquestração (`references/orquestracao.md`): decompõe por **serviço independente** e dispara em ondas de `nproc`, com relatório de progresso.
- **Serialização só onde há dependência real e declarada** (ex.: migração de schema antes do serviço que a consome) — o **mínimo**, explícito no grafo de instalação, nunca "serializa tudo por via das dúvidas".

## 6. Independência é invariante — falha no paralelo = bug (PRIORIDADE MÁXIMA)

Se a instalação/subida **paralela falha** (race, porta/arquivo/lock disputado, um serviço que não sobe sem outro, ordem implícita), isso **prova** que os serviços **não são completamente independentes** — fere **independência de runtime** (`CLAUDE.md` piso 10, `arquitetura.md` §2) e **sem monólito distribuído** (piso 6).

- **Corrigir a independência é PRIORIDADE MÁXIMA** — acima de entregar feature. É defeito arquitetural que a instalação paralela apenas **revelou**.
- **O ops NÃO contorna serializando "pra funcionar".** Serializar pra mascarar a dependência é **proibido** — esconde o defeito. O ops **expõe** a colisão (relatório: o que disputou o quê, quem esperou quem) e a correção real é feita: **cada serviço sobe sozinho**, sem exigir outro no boot, com **degradação graciosa** (outbox/retry/fila; piso 10). Só depois o paralelo volta a `nproc`.

## 7. Integração com o resto da casa

| Tema | Onde |
|---|---|
| `<projeto>_ops` como control plane (bootstrap/update/manutenção) | `arquitetura.md` §2 |
| Deploy, ambientes, artefato imutável, rollback, preview | `operacao.md` §21 |
| Test kit do sistema vivo (roda pelo ops) | `testes.md` §22.1 |
| Observabilidade integrada do ops | `observabilidade.md` §16 |
| Independência de runtime / sem monólito distribuído | `CLAUDE.md` pisos 10 e 6 |
| Segredo nunca versionado (o seed referencia o secret manager) | `seguranca.md` |
| Paralelização (o análogo em execução do agente) | `references/orquestracao.md` |
| Archive de cada operação | `operacao.md` §28 (`<projeto>_archive/`) |

Comando: **`/<slug>-ops`** (ex.: `/eng-ops`, `/zig-ops`) — audita/scaffolda o ops, verifica o fluxo de ambientes, o layout `/<app>/` + seed, o isolamento por usuário, a paralelização (`nproc`) e a independência.

> Regra de bolso: **nada toca o servidor fora do ops; nada chega ao servidor sem git + teste local; todo redeploy nasce do `/<app>/.env` (destrói a app, preserva os dados); cada serviço tem seu user.** Instalar é paralelo por padrão; se o paralelo quebra, o bug é de independência — a correção mais urgente que existe.
