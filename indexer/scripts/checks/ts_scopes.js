#!/usr/bin/env node
// What TypeScript's own binder binds each name and each `this` of a file to, for checks/ts_scopes.py. A name read
// through the scope chain gets the declarations of its file that the checker's lookup through the scopes finds, for
// what the place means (a value, a type or a namespace), each as where its name starts. An assignment to a property,
// which the binder also records as a declaration in JS and on a function (`f.priority = 1`), and the file itself (a
// CommonJS module's `exports`) declare no name. A JS `const` a `require` initializes, which the binder binds as an
// import in the function around it, where JS binds it in its block, is marked `require`. `this`, also as written in a
// type query (`typeof this`), gets where the body or the initializer of the node that binds it starts, or `program`. A
// position is "line:column", the column in UTF-16 units, both from 0. A script shares the global scope with the
// program's other scripts, two of which may declare one name, so each is bound alone, as a page loads it. The files are
// read and bound; nothing runs.
//
//   AIDD_TYPESCRIPT=/opt/typescript node ts_scopes.js ROOT < relative paths, one per line
"use strict";
const fs = require("fs");
const path = require("path");
const ts = require(process.env.AIDD_TYPESCRIPT || "typescript");

const OPTIONS = {
  allowJs: true, noEmit: true, noLib: true, noResolve: true, types: [], experimentalDecorators: true,
  alwaysStrict: false, moduleDetection: ts.ModuleDetectionKind.Legacy,
  target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext, moduleResolution: ts.ModuleResolutionKind.Bundler,
  jsx: ts.JsxEmit.Preserve,
};
const { LabeledStatement, BreakStatement, ContinueStatement } = ts.SyntaxKind;
const LABELLED = new Set([LabeledStatement, BreakStatement, ContinueStatement]);
const UNDECLARED = [ts.isIdentifier, ts.isPropertyAccessExpression, ts.isElementAccessExpression, ts.isBinaryExpression,
  ts.isCallExpression, ts.isSourceFile];
const MEANINGS = [[ts.SemanticMeaning.Value, ts.SymbolFlags.Value], [ts.SemanticMeaning.Type, ts.SymbolFlags.Type],
  [ts.SemanticMeaning.Namespace, ts.SymbolFlags.Namespace]];

function at(sf, pos) {
  const lc = sf.getLineAndCharacterOfPosition(pos);
  return `${lc.line}:${lc.character}`;
}

function local(node) {
  // the export of a local name (`export { f }`, `export { f as g }`): the name it exports is read through the scope
  const spec = node.parent;
  return ts.isExportSpecifier(spec) && !spec.parent.parent.moduleSpecifier && (spec.propertyName || spec.name) === node;
}

function reference(node) {
  const p = node.parent;
  if (ts.isShorthandPropertyAssignment(p) || local(node)) return true;
  if (ts.isDeclarationName(node) || ts.isRightSideOfQualifiedNameOrPropertyAccess(node)) return false;
  if (LABELLED.has(p.kind) || ts.isMetaProperty(p) || ts.isImportTypeNode(p)) return false;
  const renamed = ts.isImportSpecifier(p) || ts.isExportSpecifier(p) || ts.isBindingElement(p);
  if (renamed && p.propertyName === node) return false;
  if (ts.isJsxAttribute(p) || ts.isJsxNamespacedName(p)) return false;
  return !(tag(node) && /^[a-z]|-/.test(node.text));
}

function tag(node) {
  const p = node.parent;
  const element = ts.isJsxOpeningElement(p) || ts.isJsxSelfClosingElement(p) || ts.isJsxClosingElement(p);
  return element && p.tagName === node;
}

function symbol(checker, node, meaning) {
  const p = node.parent;
  if (ts.isShorthandPropertyAssignment(p)) return checker.getShorthandAssignmentValueSymbol(p);
  if (local(node)) return checker.getExportSpecifierLocalTargetSymbol(p);
  const flags = MEANINGS.reduce((f, [m, s]) => (meaning & m ? f | s : f), 0);
  return checker.resolveName(node.text, node, flags, false);
}

function bound(checker, sf, node) {
  const meaning = ts.getMeaningFromLocation(node);
  const found = symbol(checker, node, meaning);
  const all = found && found.declarations || [];
  const decls = all.filter((d) => d.getSourceFile() === sf && !UNDECLARED.some((is) => is(d))
    && (local(node) || ts.getMeaningFromDeclaration(d) & meaning));
  const required = found && found.flags & ts.SymbolFlags.Alias && all.some(ts.isVariableDeclaration);
  return [[...new Set(decls.map((d) => at(sf, (ts.getNameOfDeclaration(d) || d).getStart(sf))))].sort(),
    required ? "require" : ""];
}

function self(node) {
  // `this`, also as the parser writes it in a type query (`typeof this`), but not a `this` parameter or a member's name
  if (node.kind === ts.SyntaxKind.ThisKeyword) return !ts.isPartOfTypeNode(node);
  return ts.isIdentifier(node) && node.text === "this" && !ts.isDeclarationName(node)
    && !ts.isRightSideOfQualifiedNameOrPropertyAccess(node);
}

function binder(sf, node) {
  const c = ts.getThisContainer(node, false, false);
  if (ts.isSourceFile(c)) return "program";
  const start = c.body || c.initializer;
  return start ? at(sf, start.getStart(sf)) : `${ts.SyntaxKind[c.kind]}@${at(sf, c.getStart(sf))}`;
}

function dump(checker, sf, rel) {
  const names = [];
  const thises = [];
  const visit = (node) => {
    if (self(node)) {
      thises.push([at(sf, node.getStart(sf)), binder(sf, node)]);
    } else if (ts.isIdentifier(node) && reference(node)) {
      names.push([at(sf, node.getStart(sf)), ...bound(checker, sf, node)]);
    }
    ts.forEachChild(node, visit);
  };
  visit(sf);
  return { file: rel, broken: sf.parseDiagnostics.length > 0, names, this: thises };
}

const root = path.resolve(process.argv[2]);
const rels = fs.readFileSync(0, "utf8").split("\n").filter(Boolean);
const program = ts.createProgram({ rootNames: rels.map((r) => path.join(root, r)), options: OPTIONS });
const checker = program.getTypeChecker();
function alone(full) {
  const single = ts.createProgram({ rootNames: [full], options: OPTIONS });
  return [single.getSourceFile(full), single.getTypeChecker()];
}

for (const rel of rels) {
  const full = path.join(root, rel);
  const shared = program.getSourceFile(full);
  const [sf, bound] = shared && !ts.isExternalOrCommonJsModule(shared) ? alone(full) : [shared, checker];
  console.log(JSON.stringify(sf ? dump(bound, sf, rel) : { file: rel, broken: true, names: [], this: [] }));
}
