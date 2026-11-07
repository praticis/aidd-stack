// The compiler host a package manager's links give a project: `<ancestor>/node_modules/<name>[/...]` is the folder of
// the workspace package `<name>`, as the manager would link it, so the clones of a corpus, which hold no
// `node_modules`, resolve a workspace package as TypeScript does in a project that was installed. The workspaces are
// the `workspaces` of a `package.json` (a list or `{packages}`) and the `packages` of a `pnpm-workspace.yaml`, with
// their globs, at any depth, and the folders a `file:`, `link:` or `portal:` dependency of a `package.json` names, which
// a manager links under the dependency's own name; a file sees the packages of each manifest that holds it, the deepest
// first, as the walk up the `node_modules` of its folders does. TypeScript's own `package.json` logic picks the entry.
"use strict";
const fs = require("fs");
const path = require("path");
const ts = require(process.env.AIDD_TYPESCRIPT || "typescript");

const SKIP = new Set(["node_modules", ".git"]);
const LOCAL = /^(file|link|portal):/;
const SECTIONS = ["dependencies", "devDependencies", "peerDependencies", "optionalDependencies"];
const NM = path.sep + "node_modules" + path.sep;
const isDir = (p) => { try { return fs.statSync(p).isDirectory(); } catch (e) { return false; } };
const isFile = (p) => { try { return fs.statSync(p).isFile(); } catch (e) { return false; } };
const readJson = (p) => { try { return JSON.parse(fs.readFileSync(p, "utf8")); } catch (e) { return null; } };
const subdirs = (d) => {
  try {
    const entries = fs.readdirSync(d, { withFileTypes: true });
    return entries.filter((e) => e.isDirectory() && !SKIP.has(e.name)).map((e) => e.name);
  } catch (e) { return []; }
};

function patternsOf(dir) {
  const out = [];
  const json = readJson(path.join(dir, "package.json"));
  const declared = json && json.workspaces;
  if (declared) out.push(...(Array.isArray(declared) ? declared : declared.packages || []));
  const yaml = path.join(dir, "pnpm-workspace.yaml");
  if (!fs.existsSync(yaml)) return out;
  let listed = false;
  for (const line of fs.readFileSync(yaml, "utf8").split("\n")) {
    if (/^packages\s*:/.test(line)) { listed = true; continue; }
    if (listed && /^\S/.test(line) && !/^\s*-/.test(line)) listed = false;
    const item = listed && line.match(/^\s*-\s*['"]?([^'"#]+?)['"]?\s*(#.*)?$/);
    if (item) out.push(item[1].trim());
  }
  return out;
}

function expand(dir, segments, found) {
  if (!segments.length) { if (fs.existsSync(path.join(dir, "package.json"))) found.add(dir); return; }
  const [head, ...rest] = segments;
  if (head === "." || head === "") return expand(dir, rest, found);
  if (head === "**") {
    expand(dir, rest, found);
    for (const sub of subdirs(dir)) expand(path.join(dir, sub), segments, found);
    return;
  }
  if (!head.includes("*")) { const next = path.join(dir, head); if (isDir(next)) expand(next, rest, found); return; }
  const re = new RegExp("^" + head.replace(/[.+^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*") + "$");
  for (const sub of subdirs(dir)) if (re.test(sub)) expand(path.join(dir, sub), rest, found);
}

// The packages of the repo a manifest's local dependencies link, by the name the dependency gives them.
function localOf(dir) {
  const json = readJson(path.join(dir, "package.json")) || {};
  const found = new Map();
  for (const section of SECTIONS) {
    for (const [name, spec] of Object.entries(json[section] || {})) {
      if (typeof spec !== "string" || !LOCAL.test(spec)) continue;
      const target = path.resolve(dir, spec.replace(LOCAL, ""));
      if (!found.has(name) && fs.existsSync(path.join(target, "package.json"))) found.set(name, target);
    }
  }
  return found;
}

function findRoots(dir, roots) {
  if (patternsOf(dir).length || localOf(dir).size) roots.push(dir);
  for (const sub of subdirs(dir)) findRoots(path.join(dir, sub), roots);
}

function membersOf(root) {
  const included = new Set(), excluded = new Set();
  for (const pattern of patternsOf(root)) {
    const negated = pattern.startsWith("!");
    expand(root, pattern.replace(/^!/, "").replace(/\/+$/, "").split("/"), negated ? excluded : included);
  }
  const members = new Map();
  for (const dir of included) {
    const json = readJson(path.join(dir, "package.json"));
    const named = json && typeof json.name === "string" && !members.has(json.name);
    if (named && !excluded.has(dir)) members.set(json.name, dir);
  }
  for (const [name, dir] of localOf(root)) if (!members.has(name)) members.set(name, dir);
  return members;
}

function linkHost(project) {
  const roots = [];
  findRoots(project, roots);
  roots.sort((a, b) => b.length - a.length);
  const members = new Map(roots.map((r) => [r, membersOf(r)]));
  const rootOf = (x) => roots.find((r) => x === r || x.startsWith(r + path.sep));

  const link = (p) => {
    const at = p.indexOf(NM);
    const bare = p.endsWith(path.sep + "node_modules");
    if (at < 0 && !bare) return null;
    const root = rootOf(bare ? p.slice(0, -"/node_modules".length) : p.slice(0, at));
    if (!root) return null;
    const known = members.get(root);
    const segments = bare ? [] : p.slice(at + NM.length).split(path.sep).filter(Boolean);
    if (!segments.length) return { names: [...known.keys()] };
    const length = segments[0].startsWith("@") ? 2 : 1;
    if (length === 2 && segments.length === 1) {
      const scoped = [...known.keys()].filter((n) => n.startsWith(segments[0] + "/")).map((n) => n.split("/")[1]);
      return scoped.length ? { names: scoped } : null;
    }
    const dir = known.get(segments.slice(0, length).join("/"));
    return dir ? { real: path.join(dir, ...segments.slice(length)) } : null;
  };
  const target = (p) => { const l = fs.existsSync(p) ? null : link(p); return l && l.real ? l.real : p; };
  return {
    ...ts.sys,
    fileExists: (p) => isFile(p) || (() => { const l = link(p); return !!l && !!l.real && isFile(l.real); })(),
    directoryExists: (p) => isDir(p) || (() => { const l = link(p); return !!l && (!l.real || isDir(l.real)); })(),
    readFile: (p, encoding) => ts.sys.readFile(target(p), encoding),
    realpath: (p) => (ts.sys.realpath ? ts.sys.realpath(target(p)) : p),
    getDirectories: (p) => {
      const l = fs.existsSync(p) ? null : link(p);
      return !l ? ts.sys.getDirectories(p) : l.real ? ts.sys.getDirectories(l.real) : l.names;
    },
  };
}

// The host of a `ts.createProgram` that reads through the same links.
function programHost(project, options) {
  const { fileExists, directoryExists, readFile, realpath, getDirectories } = linkHost(project);
  return { ...ts.createCompilerHost(options), fileExists, directoryExists, readFile, realpath, getDirectories };
}

module.exports = { linkHost, programHost };
