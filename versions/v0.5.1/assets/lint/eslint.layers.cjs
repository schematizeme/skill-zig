// schematize-zig — guard de imports por camada (§4, §4.X) para TS/JS (frontend Node
// e Node legado em migração). Copie/mescle no eslint.config / .eslintrc.
// Requer eslint-plugin-import (ou import-x).
module.exports = {
  plugins: ["import"],
  rules: {
    "import/no-restricted-paths": ["error", {
      zones: [
        { target: "./src/domain", from: "./src/infrastructure", message: "domain não importa infrastructure (§4)" },
        { target: "./src/domain", from: "./src/application", message: "domain não importa application (§4)" },
        { target: "./src/domain", from: "./src/interface", message: "domain não importa interface (§4)" },
        { target: "./src/application", from: "./src/interface", message: "application não importa interface (§4)" },
      ],
    }],
    // §37: nada de any/ts-ignore calando o compilador em produção
    "@typescript-eslint/no-explicit-any": "error",
    "@typescript-eslint/ban-ts-comment": "error",
  },
};
