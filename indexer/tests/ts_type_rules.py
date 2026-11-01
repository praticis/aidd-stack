"""TS's rules past the case table, as `test_ts_type_index.py` reads them: each the files of a repo, a call written in
one of them, and the type the index gives the call's receiver (its qualified name, `outside:` and the package's
name), or the reason it gives none."""

MODELS = "export class A { run() {} }\nexport class B { run() {} }\nexport const shared = new B();\n"

IMPORT_B = 'import { B } from "./models";\n'
VALUES = {"app/values.ts": 'import { B, shared } from "./models";\nfunction make(): B { return new B(); }\n'
                            "export const cast = {} as B;\nexport const made = make();\nexport const again = shared;\n"}
USE_VALUES = ('import { again, cast, made } from "./values";\n'
              "export const f = () => cast.run();\nexport const g = () => made.run();\n"
              "export const h = () => again.run();\n")
RULES = {
    "a-generic-class-is-its-origin": (
        {"app/repo.ts": "export class Repo<T> { find(): T | null { return null; } }\n",
         "app/use.ts": 'import { Repo } from "./repo";\nexport function f(r: Repo<number>) { return r.find(); }\n'},
        "r.find()", "app/repo:Repo"),
    "a-re-export": (
        {"app/index.ts": 'export { B } from "./models";\n',
         "app/use.ts": 'import { B } from "./index";\nexport const f = () => new B().run();\n'},
        "new B().run()", "app/models:B"),
    "a-renamed-re-export": (
        {"app/index.ts": 'export { B as Bee } from "./models";\n',
         "app/use.ts": 'import { Bee } from "./index";\nexport const f = (x: Bee) => x.run();\n'},
        "x.run()", "app/models:B"),
    "an-export-of-all-of-a-module": (
        {"app/index.ts": 'export * from "./models";\n',
         "app/use.ts": 'import { shared } from "./index";\nexport const f = () => shared.run();\n'},
        "shared.run()", "app/models:B"),
    "a-default-exported-class": (
        {"app/c.ts": "export default class C { run() {} }\n",
         "app/use.ts": 'import C from "./c";\nexport const f = (c: C) => c.run();\n'},
        "c.run()", "app/c:C"),
    "a-default-exported-name": (
        {"app/c.ts": "class C { run() {} }\nexport default C;\n",
         "app/use.ts": 'import Cee from "./c";\nexport const f = (c: Cee) => c.run();\n'},
        "c.run()", "app/c:C"),
    "a-type-or-undefined": (
        {"app/use.ts": IMPORT_B + "export const f = (x: B | undefined) => x!.run();\n"}, "x!.run()", "app/models:B"),
    "a-type-alias": (
        {"app/use.ts": IMPORT_B + "type R = B;\nexport const f = (r: R) => r.run();\n"}, "r.run()", "app/models:B"),
    "a-field-of-an-interface": (
        {"app/use.ts": IMPORT_B + "interface Props { b: B }\nexport const f = (p: Props) => p.b.run();\n"},
        "p.b.run()", "app/models:B"),
    "a-destructured-parameter-of-a-named-type": (
        {"app/use.ts": IMPORT_B + "interface Props { b: B }\nexport const f = ({ b }: Props) => b.run();\n"},
        "b.run()", "app/models:B"),
    "a-destructured-local": (
        {"app/use.ts": IMPORT_B + "interface Props { b: B }\n"
                                  "export function f(p: Props) {\n  const { b } = p;\n  return b.run();\n}\n"},
        "b.run()", "app/models:B"),
    "a-getter": (
        {"app/use.ts": IMPORT_B + "export class C {\n  get b(): B { return new B(); }\n"
                                  "  go() { return this.b.run(); }\n}\n"},
        "this.b.run()", "app/models:B"),
    "a-module-namespace": (
        {"app/use.ts": 'import * as m from "./models";\nexport const f = () => m.shared.run();\n'},
        "m.shared.run()", "app/models:B"),
    "a-require-in-js": (
        {"app/use.js": 'const m = require("./models");\nexports.f = () => m.shared.run();\n'},
        "m.shared.run()", "app/models:B", "app/use.js"),
    "a-package-type": (
        {"app/use.ts": 'import { Client } from "some-package";\nexport const f = (c: Client) => c.send();\n'},
        "c.send()", "outside:some-package"),
    "a-class-a-function-declares": (
        {"app/use.ts": "export function f() {\n  class L { run() {} }\n  return new L().run();\n}\n"},
        "new L().run()", "a type declared in a function"),
    "a-global-type": (
        {"app/use.ts": "export const f = (d: Date) => d.getTime();\n"}, "d.getTime()",
        "its module declares or exports no such name"),
    "a-static-members-this": (
        {"app/use.ts": "export class C {\n  static make() { return this.create(); }\n  static create() {}\n}\n"},
        "this.create()", "a static member's this, the class itself"),
    "a-method-result": (
        {"app/use.ts": IMPORT_B + "export const f = (x: { m(): B }) => x.m().run();\n"}, "x.m().run()",
        "the result of a method call"),
    "a-type-of-a-module-namespace": (
        {"app/use.ts": 'import * as m from "./models";\nexport const f = (x: m.B) => x.run();\n'}, "x.run()",
        "app/models:B"),
    "a-module-value-written-as-a-type": ({**VALUES, "app/use.ts": USE_VALUES}, "cast.run()", "app/models:B"),
    "a-module-value-a-call-returns": ({**VALUES, "app/use.ts": USE_VALUES}, "made.run()", "app/models:B"),
    "a-module-value-another-name-holds": ({**VALUES, "app/use.ts": USE_VALUES}, "again.run()", "app/models:B"),
    "a-function-a-module-value-holds": (
        {"app/make.ts": IMPORT_B + "export const make = (): B => new B();\n",
         "app/use.ts": 'import { make } from "./make";\nexport const f = () => make().run();\n'},
        "make().run()", "app/models:B"),
    "a-declared-value": (
        {"app/decl.ts": IMPORT_B + "declare const held: B;\nexport { held };\n",
         "app/use.ts": 'import { held } from "./decl";\nexport const f = () => held.run();\n'},
        "held.run()", "app/models:B"),
    "an-exported-declared-class": (
        {"app/decl.ts": "export declare class D { run(): void }\n",
         "app/use.ts": 'import { D } from "./decl";\nexport const f = (d: D) => d.run();\n'},
        "d.run()", "app/decl:D"),
    "an-import-of-a-require": (
        {"app/use.ts": 'import m = require("./models");\nexport const f = () => m.shared.run();\n'},
        "m.shared.run()", "app/models:B"),
    "a-namespace-re-export": (
        {"app/index.ts": 'export * as models from "./models";\n',
         "app/use.ts": 'import { models } from "./index";\nexport const f = () => models.shared.run();\n'},
        "models.shared.run()", "app/models:B"),
    "an-export-of-all-leaves-the-default-out": (
        {"app/c.ts": "export default class C { run() {} }\n", "app/index.ts": 'export * from "./c";\n',
         "app/use.ts": 'import C from "./index";\nexport const f = (c: C) => c.run();\n'},
        "c.run()", "its module declares or exports no such name"),
    "a-destructured-require-in-js": (
        {"app/use.js": 'const { shared: s } = require("./models");\nexports.f = () => s.run();\n'},
        "s.run()", "app/models:B", "app/use.js"),
    "a-require-in-a-function": (
        {"app/use.js": 'exports.f = function () {\n  const m = require("./models");\n  return m.shared.run();\n};\n'},
        "m.shared.run()", "a module a function requires, which no module's names hold", "app/use.js"),
    "a-field-of-an-interfaces-base": (
        {"app/use.ts": IMPORT_B + "interface Base { b: B }\ninterface Props extends Base {}\n"
                                  "export const f = (p: Props) => p.b.run();\n"},
        "p.b.run()", "app/models:B"),
    "a-field-of-a-constrained-type-parameter": (
        {"app/box.ts": IMPORT_B + "export class Box<T extends B> { item!: T }\n",
         "app/use.ts": IMPORT_B + 'import { Box } from "./box";\nexport const f = (b: Box<B>) => b.item.run();\n'},
        "b.item.run()", "app/models:B"),
    "a-static-field-is-the-classes": (
        {"app/use.ts": IMPORT_B + "export class C {\n  static b: B = new B();\n}\n"
                                  "export const f = (c: C) => c.b.run();\n"},
        "c.b.run()", "no class or interface of its bases declares the field"),
    "a-member-of-a-package-value": (
        {"app/use.ts": 'import { Client } from "some-package";\nexport const f = (c: Client) => c.inner.send();\n'},
        "c.inner.send()", "a type a package declares"),
    "a-type-a-function-declares": (
        {"app/use.ts": "export function f() {\n  interface L { run(): void }\n  const x: L = { run() {} };\n"
                       "  return x.run();\n}\n"},
        "x.run()", "a type declared in a function"),
    "a-class-a-static-block-declares": (
        {"app/use.ts": "export class C {\n  static {\n    class L { run() {} }\n    new L().run();\n  }\n}\n"},
        "new L().run()", "a type declared in a function"),
    "the-this-of-a-class-a-function-declares": (
        {"app/use.ts": "export function f() {\n  class L {\n    run() {}\n    go() { return this.run(); }\n  }\n"
                       "  return L;\n}\n"},
        "this.run()", "a type declared in a function"),
    "the-this-of-a-class-expression": (
        {"app/use.ts": "export const K = class {\n  run() {}\n  go() { return this.run(); }\n};\n"},
        "this.run()", "the this of a class expression"),
    "the-this-of-an-object-literals-method": (
        {"app/use.ts": "export const o = {\n  run() {},\n  go() { return this.run(); },\n};\n"},
        "this.run()", "the this of an object literal's method"),
    "a-this-outside-a-class": (
        {"app/use.ts": "export const g = () => this.run();\n"}, "this.run()", "a this outside a class"),
    "a-this-in-a-namespace": (
        {"app/use.ts": "export namespace N {\n  export const g = () => this.run();\n}\n"}, "this.run()",
        "a this outside a class"),
    "a-catch-clauses-variable": (
        {"app/use.ts": "export function f() {\n  try {\n    return 1;\n  } catch (e) {\n    return e.run();\n  }\n}\n"},
        "e.run()", "a catch clause's variable"),
    "an-element-of-a-destructured-array": (
        {"app/use.ts": IMPORT_B + "export function f() {\n  const [b] = [new B()];\n  return b.run();\n}\n"},
        "b.run()", "an element of a destructured array"),
    "a-function-a-local-holds": (
        {"app/use.ts": IMPORT_B + "export function f() {\n  const g = () => new B();\n  return g.call(null);\n}\n"},
        "g.call(null)", "a function, not a value of a class"),
}
