# Testes — recorte Zig

> **PONTEIRO, não cópia.** A **disciplina de teste** da casa é da **`schematize-qa`**: a pirâmide,
> teste de COMPORTAMENTO (não "renderizou"), o "verde de verdade" (smoke com asserção de conteúdo +
> assertion negativa + self-check que força uma falha conhecida), cobertura útil, a11y, regressão
> visual, contrato/dados, **flaky** (quarentena com prazo e dono), o fluxo **plan-first**
> (`/qa-plan` → `/qa-run`) e os **gates de CI que travam o merge**. Leia
> `schematize-qa` → `references/estrategia.md`, `references/categorias.md`,
> `references/execucao.md` e `references/flaky.md`.
>
> **Segurança ofensiva** (rejeição rota a rota, injeção/coerção, IDOR/BOLA, cross-tenant) é a
> **`schematize-pentest`** — não é Q.A. e não mora aqui.
>
> Aqui fica **só o que muda em Zig**: o runner, a sintaxe, e as armadilhas do dialeto.
>
> *(Este arquivo e a antiga reference *testes-execucao* eram, juntos, ~450 linhas por skill — 66% já
> duplicado na `schematize-qa`, 23% que pertence à `schematize-pentest` e ~2% idiomático de
> verdade. Deriva por cópia foi o achado da Classe C/D da vistoria de 2026-08-21.)*

## O runner e o comando

```bash
zig build test                         # a suíte do projeto
zig test src/arquivo.zig               # um arquivo
zig build test -Doptimize=ReleaseSafe  # o mesmo modo do que vai para produção
```

## O que muda de forma em Zig

- **`zig test` é NATIVO da linguagem**: o bloco `test "nome" { … }` vive **ao lado do código**, no
  mesmo arquivo, e o compilador o descarta do binário final. Não há framework, não há descoberta
  por convenção de nome de arquivo — e por isso não existe "teste que não foi coletado".
- **Detecção de LEAK é PISO, não extra.** `std.testing.allocator` **falha o teste** se algum
  `alloc` não teve `free`. Todo teste que aloca usa esse allocator; quem usa
  `std.heap.page_allocator` no teste está **desligando o detector de vazamento** — VETADO.

  ```zig
  test "não vaza" {
      const a = std.testing.allocator;          // falha o teste se sobrar alocação
      const buf = try a.alloc(u8, 32);
      defer a.free(buf);                        // sem este defer, o teste REPROVA
      try std.testing.expectEqual(@as(usize, 32), buf.len);
  }
  ```

- **`errdefer` é parte do teste de erro:** o caminho de falha também tem de liberar. Teste o
  caminho de erro com `std.testing.expectError` e o allocator de teste junto — é assim que se prova
  que o `errdefer` existe.
- **`std.testing.FailingAllocator`** injeta falha de alocação na n-ésima chamada: é o único jeito
  de exercitar OOM de verdade.
- **`zig test` REPROVA (exit 1) quando o teste chama `std.log.err`** — e exercitar o caminho de
  recusa de um guard chama. Não rebaixe a severidade do log: **injete a auditoria** (ver
  `references/iam.md` §3.1, `AuditFn`), que mantém `err` em produção e deixa a suíte verde.
- **Ponteiro para `undefined` não é `null`:** `var x: T = undefined` passa em teste em Debug e
  explode em ReleaseFast. Rode a suíte **também** no modo de otimização de produção.
- **`std.testing.refAllDecls(@This())`** força a compilação de tudo no arquivo — pega código morto
  que nem compila mais.

## Onde divergir da base, a base manda

O piso é o mesmo: teste é **visto falhar no vermelho** antes de valer; cobertura é **contrato**
(não se baixa a régua para passar o CI); **teste nunca dispara efeito externo real** — endereço no
domínio de teste em rota nula, provider = sink, cap por execução, e a caixa se confere **lendo do
sink** (`references/iam.md` §3.1 desta skill; normativa em `schematize-engineering` →
`references/efeitos-externos.md`); e **gate não se desliga "por enquanto"**.
