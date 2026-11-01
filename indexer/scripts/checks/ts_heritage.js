#!/usr/bin/env node
// The declarations TypeScript's own checker resolves each type a class's or an interface's heritage clause names to, in
// the TS and JS files of each project: one JSON line per type, with the project, the file, the declaration's name and
// line, whether it is a statement of its file (`top`), the clause (`extends` or `implements`) and the declarations,
// each as `path:Name` (its file relative to the project, without its last extension), or `outside` for one the project
// does not hold; `other` where the name is no class or interface, and none where the checker gives the expression no
// symbol (a mixin's call). Each file is read with the `baseUrl` and `paths` of its `tsconfig.json`. With `--members`, also
// each member of each class and interface, with its form; with `--files`, only the files of the one project whose
// paths, relative to it, come one per line on stdin. The checker reads and types the files; nothing runs.
//
//   AIDD_TYPESCRIPT=/opt/typescript node ts_heritage.js [--members] [--files] PROJECT_DIR...
"use strict";
const fs = require("fs");
const path = require("path");
const ts = require(process.env.AIDD_TYPESCRIPT || "typescript");

const OPTIONS = {
  allowJs: true, noEmit: true, strict: true, skipLibCheck: true, experimentalDecorators: true,
  target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext, moduleResolution: ts.ModuleResolutionKind.Bundler,
  jsx: ts.JsxEmit.Preserve, types: [],
};
const SOURCE = /\.(ts|tsx|mts|cts|js|jsx|mjs|cjs)$/;

function sources(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) return e.name === "node_modules" || e.name === ".git" ? [] : sources(full);
    return e.isFile() && SOURCE.test(e.name) ? [full] : [];
  });
}

function nearestConfig(project, file) {
  for (let d = path.dirname(file); ; d = path.dirname(d)) {
    if (fs.existsSync(path.join(d, "tsconfig.json"))) return path.join(d, "tsconfig.json");
    if (d === project || path.dirname(d) === d) return null;
  }
}

const parsed = new Map();

function parse(config) {
  if (!parsed.has(config)) {
    let found = null;
    try {
      const host = { ...ts.sys, onUnRecoverableConfigFileDiagnostic: () => {} };
      found = ts.getParsedCommandLineOfConfigFile(config, {}, host);
    } catch (e) {
      found = null;
    }
    parsed.set(config, found || null);
  }
  return parsed.get(config);
}

// A `tsconfig.json` that only refers to others (`tsconfig.app.json`) maps a file's paths in the one that holds it.
function configOf(project, file) {
  const nearest = nearestConfig(project, file);
  const found = nearest && parse(nearest);
  if (!found || found.options.paths || !found.projectReferences) return nearest;
  for (const ref of found.projectReferences) {
    const config = ts.resolveProjectReferencePath(ref);
    const sub = fs.existsSync(config) ? parse(config) : null;
    if (sub && sub.fileNames.includes(file)) return config;
  }
  return nearest;
}

function optionsOf(config) {
  const o = (config && parse(config) && parse(config).options) || {};
  return { ...OPTIONS, ...(o.baseUrl ? { baseUrl: o.baseUrl } : {}),
           ...(o.paths ? { paths: o.paths, pathsBasePath: o.pathsBasePath || path.dirname(config) } : {}) };
}

function owners(decl) {
  const names = [];
  for (let n = decl; n; n = n.parent) {
    if (n.name && (ts.isIdentifier(n.name) || ts.isPrivateIdentifier(n.name) || ts.isStringLiteral(n.name))) {
      names.unshift(n.name.text);
    }
  }
  return names.join(".");
}

function where(project, decl) {
  const file = path.relative(project, decl.getSourceFile().fileName);
  if (file.startsWith("..") || file.split(path.sep).includes("node_modules")) return "outside";
  return `${file.replace(/\.[mc]?[jt]sx?$/, "")}:${owners(decl)}`;
}

// A type alias stands for the class or interface it names; what is no class or interface (a value, an object type) is
// `other`.
function declarations(checker, project, expr) {
  const name = ts.isPropertyAccessExpression(expr) ? expr.name : ts.isIdentifier(expr) ? expr : null;
  let symbol = name && checker.getSymbolAtLocation(name);
  if (symbol && symbol.flags & ts.SymbolFlags.Alias) symbol = checker.getAliasedSymbol(symbol);
  if (symbol && symbol.flags & ts.SymbolFlags.TypeAlias) {
    const named = checker.getDeclaredTypeOfSymbol(symbol).symbol;
    if (named && named.flags & (ts.SymbolFlags.Class | ts.SymbolFlags.Interface)) symbol = named;
  }
  const all = (symbol && symbol.declarations) || [];
  const types = all.filter((d) => ts.isClassDeclaration(d) || ts.isInterfaceDeclaration(d));
  return all.length && !types.length ? ["other"] : [...new Set(types.map((d) => where(project, d)))].sort();
}

const has = (node, kind) => (ts.getModifiers(node) || []).some((m) => m.kind === kind);

function form(member) {
  if (ts.isMethodDeclaration(member)) {
    if (has(member, ts.SyntaxKind.StaticKeyword)) return "static";
    if (has(member, ts.SyntaxKind.AbstractKeyword)) return "abstract";
    return member.body ? "method" : "signature";
  }
  if (ts.isGetAccessor(member) || ts.isSetAccessor(member)) return "accessor";
  if (ts.isConstructorDeclaration(member)) return "constructor";
  if (ts.isPropertyDeclaration(member)) return has(member, ts.SyntaxKind.StaticKeyword) ? "static" : "field";
  if (ts.isMethodSignature(member)) return "signature";
  if (ts.isPropertySignature(member)) return "field";
  return null;
}

function members(file, node, row) {
  const line = (n) => file.getLineAndCharacterOfPosition(n.getStart(file)).line + 1;
  for (const m of node.members) {
    const f = form(m);
    if (f && m.name && ts.isIdentifier(m.name)) row({ member: m.name.text, form: f, line: line(m.name) });
    if (ts.isConstructorDeclaration(m)) {
      for (const p of m.parameters.filter((p) => ts.isParameterPropertyDeclaration(p, m) && ts.isIdentifier(p.name))) {
        row({ member: p.name.text, form: "field", line: line(p.name) });
      }
    }
  }
}

function report(program, project, arg, files, withMembers) {
  const checker = program.getTypeChecker();
  for (const fileName of files) {
    const file = program.getSourceFile(fileName);
    if (!file) continue;
    const rel = path.relative(project, fileName);
    const visit = (node) => {
      if ((ts.isClassDeclaration(node) || ts.isInterfaceDeclaration(node)) && node.name) {
        const base = {
          project: arg, file: rel, name: owners(node), kind: ts.isClassDeclaration(node) ? "class" : "interface",
          at: file.getLineAndCharacterOfPosition(node.getStart(file)).line + 1, top: ts.isSourceFile(node.parent),
        };
        for (const clause of node.heritageClauses || []) {
          const which = clause.token === ts.SyntaxKind.ExtendsKeyword ? "extends" : "implements";
          for (const t of clause.types) {
            const declared = declarations(checker, project, t.expression);
            console.log(JSON.stringify({ ...base, clause: which, declared }));
          }
        }
        if (withMembers) members(file, node, (m) => console.log(JSON.stringify({ ...base, ...m })));
      }
      ts.forEachChild(node, visit);
    };
    visit(file);
  }
}

const flags = new Set(process.argv.slice(2).filter((a) => a.startsWith("--")));
const listed = flags.has("--files") ? fs.readFileSync(0, "utf8").split("\n").filter(Boolean) : null;
let previous;
for (const arg of process.argv.slice(2).filter((a) => !a.startsWith("--"))) {
  const project = path.resolve(arg);
  const groups = new Map();
  for (const file of listed ? listed.map((rel) => path.join(project, rel)) : sources(project)) {
    const config = configOf(project, file);
    if (!groups.has(config)) groups.set(config, []);
    groups.get(config).push(file);
  }
  for (const [config, files] of groups) {
    const program = ts.createProgram({ rootNames: files, options: optionsOf(config), oldProgram: previous });
    report(program, project, arg, files, flags.has("--members"));
    previous = program;
  }
}
