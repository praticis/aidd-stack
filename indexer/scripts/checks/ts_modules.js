#!/usr/bin/env node
// The file TypeScript's own module resolution gives each import of each TS and JS file of a project: one JSON line per
// module specifier (`import`, `export from`, `require`, `import()`), with the file, the specifier, the file it resolves
// to relative to the project, `outside` for one in `node_modules` or out of the project, or null; and how the
// specifier is read: `relative`, by a pattern of `paths`, below `baseUrl`, or `bare`. Each file is read with its config
// (`ts_configs.js`), and the files come one per line on stdin, relative to the project; where the config references a
// project, as an editor reads it: the output of that project is its source. With `--link`, a workspace package resolves
// as it does in an installed project (`ts_link.js`). Nothing runs.
//
//   AIDD_TYPESCRIPT=/opt/typescript node ts_modules.js [--link] PROJECT_DIR < files
"use strict";
const fs = require("fs");
const path = require("path");
const ts = require(process.env.AIDD_TYPESCRIPT || "typescript");
const { configOf, optionsOf, referencesOf, programOf } = require("./ts_configs.js");
const { linkHost, programHost } = require("./ts_link.js");

const OPTIONS = { allowJs: true, resolveJsonModule: true, module: ts.ModuleKind.ESNext,
                  moduleResolution: ts.ModuleResolutionKind.Bundler, jsx: ts.JsxEmit.Preserve };

function matches(pattern, spec) {
  const star = pattern.indexOf("*");
  return star < 0 ? pattern === spec : spec.startsWith(pattern.slice(0, star)) && spec.endsWith(pattern.slice(star + 1));
}

function via(spec, options) {
  if (spec.startsWith(".")) return "relative";
  if (options.paths && Object.keys(options.paths).some((p) => matches(p, spec))) return "paths";
  return options.baseUrl ? "baseUrl" : "bare";
}

function where(project, resolved) {
  if (!resolved) return null;
  const rel = path.relative(project, resolved.resolvedFileName);
  return rel.startsWith("..") || rel.split(path.sep).includes("node_modules") ? "outside" : rel;
}

// Where the specifier resolves for a file: the program's resolution where its config references a project, which holds
// the redirect from the output of that project to its source, and `resolveModuleName` otherwise, and for a specifier
// the program does not read as an import (a `require` in a TS file).
function resolver(config, options, host, files, project, linked) {
  if (!referencesOf(config).length) return (file, spec) => ts.resolveModuleName(spec, file, options, host).resolvedModule;
  const program = programOf(config, options, files, linked ? programHost(project, options) : undefined);
  return (file, spec) => {
    const at = program.getSourceFile(file);
    const found = [ts.ModuleKind.ESNext, ts.ModuleKind.CommonJS, undefined].map((m) => program.getResolvedModule(at, spec, m))
      .find(Boolean);
    if (!found) return ts.resolveModuleName(spec, file, options, host).resolvedModule;
    const resolved = found.resolvedModule;
    const source = resolved && program.getSourceFile(resolved.resolvedFileName);
    return resolved && { resolvedFileName: source ? source.fileName : resolved.resolvedFileName };
  };
}

const args = process.argv.slice(2);
const project = path.resolve(args.find((a) => !a.startsWith("--")));
const linked = args.includes("--link");
const host = linked ? linkHost(project) : ts.sys;
const groups = new Map();
for (const rel of fs.readFileSync(0, "utf8").split("\n").filter(Boolean)) {
  const config = configOf(project, path.join(project, rel));
  if (!groups.has(config)) groups.set(config, []);
  groups.get(config).push(rel);
}
for (const [config, rels] of groups) {
  const options = optionsOf(config, OPTIONS);
  const resolve = resolver(config, options, host, rels.map((r) => path.join(project, r)), project, linked);
  for (const rel of rels) {
    const file = path.join(project, rel);
    for (const { fileName: spec } of ts.preProcessFile(fs.readFileSync(file, "utf8"), true, true).importedFiles) {
      const to = where(project, resolve(file, spec));
      process.stdout.write(JSON.stringify({ file: rel, spec, to, via: via(spec, options) }) + "\n");
    }
  }
}
