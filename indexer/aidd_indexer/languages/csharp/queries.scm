;; C#

(class_declaration name: (identifier) @name) @def.class

(record_declaration name: (identifier) @name) @def.class

(interface_declaration name: (identifier) @name) @def.interface

(struct_declaration name: (identifier) @name) @def.struct

(enum_declaration name: (identifier) @name) @def.enum

(method_declaration name: (identifier) @name) @def.method

(constructor_declaration name: (identifier) @name) @def.method

(property_declaration name: (identifier) @name) @def.field

(invocation_expression function: (identifier) @callee) @call

(invocation_expression function: (member_access_expression expression: (_) @receiver name: (identifier) @callee)) @call

;; `this` / `base` are anonymous tokens: `(_)` above does not match them
(invocation_expression function: (member_access_expression expression: ["this" "base"] @receiver name: (identifier) @callee)) @call

(invocation_expression function: (generic_name (identifier) @callee)) @call

;; generic methods on a receiver: `repo.FindAsync<T>(id)`, `this.Map<T>()` — the name sits in a `generic_name`
(invocation_expression function: (member_access_expression expression: (_) @receiver name: (generic_name (identifier) @callee))) @call

(invocation_expression function: (member_access_expression expression: ["this" "base"] @receiver name: (generic_name (identifier) @callee))) @call

(object_creation_expression type: (identifier) @callee) @call

(using_directive (qualified_name) @import)

(using_directive (identifier) @import)
