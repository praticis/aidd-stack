#!/usr/bin/env node
// The declarations TypeScript's own checker resolves each method call `x.m(..)` to, in the .ts, .tsx and .js files of
// each project: one JSON line per call, with the project, the file, the line, the method and the declarations, each as
// `path:Owner.name` (its file relative to the project, without the extension), or `outside` for one the project does
// not hold. A union or an intersection gives several; a receiver the checker cannot type, none. The checker reads and
// types the files; nothing runs.
//
//   AIDD_TYPESCRIPT=/opt/typescript node ts_checker.js PROJECT_DIR...
"use strict";
const fs = require("fs");
const path = require("path");
const ts = require(process.env.AIDD_TYPESCRIPT || "typescript");

const OPTIONS = {
  allowJs: true, checkJs: true, noEmit: true, strict: true, skipLibCheck: true, experimentalDecorators: true,
  target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext, moduleResolution: ts.ModuleResolutionKind.Bundler,
  jsx: ts.JsxEmit.Preserve, types: [],
};
const SOURCE = /\.(ts|tsx|js)$/;

function sources(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) return e.name === "node_modules" ? [] : sources(full);
    return SOURCE.test(e.name) && !e.name.endsWith(".d.ts") ? [full] : [];
  });
}

function owners(decl) {
  const names = [];
  for (let n = decl; n; n = n.parent) {
    if (n.name && ts.isIdentifier(n.name) || n.name && ts.isPrivateIdentifier(n.name)) names.unshift(n.name.text);
    else if (n.name && ts.isStringLiteral(n.name)) names.unshift(n.name.text);
  }
  return names.join(".");
}

function where(project, decl) {
  const file = path.relative(project, decl.getSourceFile().fileName);
  if (file.startsWith("..") || file.split(path.sep).includes("node_modules")) return "outside";
  return `${file.replace(/\.(d\.ts|ts|tsx|js)$/, "")}:${owners(decl)}`;
}

function declarations(checker, project, name) {
  let symbol = checker.getSymbolAtLocation(name);
  if (symbol && symbol.flags & ts.SymbolFlags.Alias) symbol = checker.getAliasedSymbol(symbol);
  return [...new Set((symbol && symbol.declarations || []).map((d) => where(project, d)))].sort();
}

let previous;
for (const arg of process.argv.slice(2)) {
  const project = path.resolve(arg);
  const program = ts.createProgram({ rootNames: sources(project), options: OPTIONS, oldProgram: previous });
  const checker = program.getTypeChecker();
  for (const file of program.getSourceFiles()) {
    if (path.relative(project, file.fileName).startsWith("..") || file.isDeclarationFile) continue;
    const visit = (node) => {
      if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression)) {
        const name = node.expression.name;
        console.log(JSON.stringify({
          project: arg, file: path.relative(project, file.fileName),
          line: file.getLineAndCharacterOfPosition(node.getStart(file)).line + 1, method: name.text,
          declared: declarations(checker, project, name),
        }));
      }
      ts.forEachChild(node, visit);
    };
    visit(file);
  }
  previous = program;
}
