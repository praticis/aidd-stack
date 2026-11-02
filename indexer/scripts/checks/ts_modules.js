#!/usr/bin/env node
// The file TypeScript's own module resolution gives each import of each TS and JS file of a project: one JSON line per
// module specifier (`import`, `export from`, `require`, `import()`), with the file, the specifier, the file it resolves
// to relative to the project, `outside` for one in `node_modules` or out of the project, or null; and how the
// specifier is read: `relative`, by a pattern of `paths`, below `baseUrl`, or `bare`. Each file is read with its config
// (`ts_configs.js`), and the files come one per line on stdin, relative to the project. Nothing runs.
//
//   AIDD_TYPESCRIPT=/opt/typescript node ts_modules.js PROJECT_DIR < files
"use strict";
const fs = require("fs");
const path = require("path");
const ts = require(process.env.AIDD_TYPESCRIPT || "typescript");
const { configOf, optionsOf } = require("./ts_configs.js");

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

const project = path.resolve(process.argv[2]);
for (const rel of fs.readFileSync(0, "utf8").split("\n").filter(Boolean)) {
  const file = path.join(project, rel);
  const options = optionsOf(configOf(project, file), OPTIONS);
  for (const { fileName: spec } of ts.preProcessFile(fs.readFileSync(file, "utf8"), true, true).importedFiles) {
    const to = where(project, ts.resolveModuleName(spec, file, options, ts.sys).resolvedModule);
    process.stdout.write(JSON.stringify({ file: rel, spec, to, via: via(spec, options) }) + "\n");
  }
}
