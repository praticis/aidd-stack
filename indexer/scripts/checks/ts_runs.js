#!/usr/bin/env node
// What JS runs on an instance of each class of a test's case, for each name the instance or its prototype chain holds:
// the case's files, compiled by the pinned compiler to CommonJS as an ES2022 class defines its fields, are loaded and
// each class a module declares and exports is constructed with no arguments. A module that does not load (one that
// imports a package) is left out. One JSON line per class and name: `runs` is the class whose prototype holds the
// method (`path:Name`), `own` for a property of the instance, `accessor` for a getter or a setter, `outside` for a
// class of no file of the case. It runs the code it reads, so it is for the tests' own cases only, never a
// repository's.
//
//   AIDD_TYPESCRIPT=/opt/typescript node ts_runs.js CASE_DIR
"use strict";
const fs = require("fs");
const os = require("os");
const path = require("path");
const ts = require(process.env.AIDD_TYPESCRIPT || "typescript");

const SOURCE = /\.(ts|tsx|mts|cts|js|jsx|mjs|cjs)$/;
const COMPILE = {
  module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, useDefineForClassFields: true, allowJs: true,
  esModuleInterop: true, experimentalDecorators: true, jsx: ts.JsxEmit.React,
};

function sources(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) return e.name === "node_modules" ? [] : sources(full);
    return e.isFile() && SOURCE.test(e.name) ? [full] : [];
  });
}

const project = path.resolve(process.argv[2]);
const out = fs.mkdtempSync(path.join(os.tmpdir(), "ts-runs-"));
const modules = [];
for (const file of sources(project)) {
  const rel = path.relative(project, file);
  const text = fs.readFileSync(file, "utf8");
  const dest = path.join(out, rel.replace(SOURCE, ".js"));
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.writeFileSync(dest, ts.transpileModule(text, { compilerOptions: COMPILE, fileName: file }).outputText);
  modules.push({ id: rel.replace(SOURCE, ""), text, dest });
}

const classes = new Map();
for (const m of modules) {
  let exported;
  try {
    exported = require(m.dest);
  } catch (e) {
    continue;
  }
  for (const v of Object.values(exported)) {
    const declared = typeof v === "function" && /^class\b/.test(Function.prototype.toString.call(v))
      && new RegExp(`\\bclass\\s+${v.name}\\b`).test(m.text);
    if (declared && !classes.has(v)) classes.set(v, `${m.id}:${v.name}`);
  }
}

function runs(instance, name) {
  if (Object.prototype.hasOwnProperty.call(instance, name)) return "own";
  for (let p = Object.getPrototypeOf(instance); p; p = Object.getPrototypeOf(p)) {
    const d = Object.getOwnPropertyDescriptor(p, name);
    if (d) return d.get || d.set ? "accessor" : classes.get(p.constructor) || "outside";
  }
  return null;
}

for (const [cls, id] of classes) {
  let instance;
  try {
    instance = new cls();
  } catch (e) {
    continue;
  }
  const names = new Set(Object.getOwnPropertyNames(instance));
  for (let p = cls.prototype; p && p !== Object.prototype; p = Object.getPrototypeOf(p)) {
    Object.getOwnPropertyNames(p).filter((n) => n !== "constructor").forEach((n) => names.add(n));
  }
  for (const name of [...names].sort()) console.log(JSON.stringify({ class: id, name, runs: runs(instance, name) }));
}
fs.rmSync(out, { recursive: true, force: true });
