// The config TypeScript reads a file of a project with: the nearest `tsconfig.json` or `jsconfig.json` above it, its
// `extends` followed; where it maps no path and only refers to other projects (`tsconfig.app.json`), the referenced one
// whose files hold the file. What the oracles take from it is `paths`, with the folder its targets are relative to,
// and `baseUrl`.
"use strict";
const fs = require("fs");
const path = require("path");
const ts = require(process.env.AIDD_TYPESCRIPT || "typescript");

const NAMES = ["tsconfig.json", "jsconfig.json"];
const parsed = new Map();

function nearestConfig(project, file) {
  for (let d = path.dirname(file); ; d = path.dirname(d)) {
    const found = NAMES.map((n) => path.join(d, n)).find((p) => fs.existsSync(p));
    if (found) return found;
    if (d === project || path.dirname(d) === d) return null;
  }
}

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

// `base` with the config's `baseUrl` and `paths`.
function optionsOf(config, base) {
  const o = (config && parse(config) && parse(config).options) || {};
  return { ...base, ...(o.baseUrl ? { baseUrl: o.baseUrl } : {}),
           ...(o.paths ? { paths: o.paths, pathsBasePath: o.pathsBasePath || path.dirname(config) } : {}) };
}

module.exports = { configOf, optionsOf };
