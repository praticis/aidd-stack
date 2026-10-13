;; Go — definitions, calls, imports.
;; Patterns are separated by blank lines and compiled one by one, so a
;; pattern that does not match the installed grammar is skipped with a
;; warning instead of breaking the whole language.

(function_declaration name: (identifier) @name) @def.function

(method_declaration name: (field_identifier) @name) @def.method

;; Each spec is captured on its own, so every item of a `type ( ... )` / `const ( ... )` /
;; `var ( ... )` block is a symbol; a declaration with a single spec is still recorded on the
;; declaration itself (GoSupport.def_node), where its doc comment and keyword live.
(type_declaration (type_spec name: (type_identifier) @name type: (struct_type)) @def.struct)

(type_declaration (type_spec name: (type_identifier) @name type: (interface_type)) @def.interface)

(type_declaration (type_spec name: (type_identifier) @name type: (_)) @def.type)

(type_declaration (type_alias name: (type_identifier) @name) @def.type)

(const_declaration (const_spec name: (identifier) @name) @def.const)

;; package-level variables only (sentinel errors, registries) — locals are not symbols
(source_file (var_declaration (var_spec name: (identifier) @name) @def.var))

(source_file (var_declaration (var_spec_list (var_spec name: (identifier) @name) @def.var)))

(call_expression function: (identifier) @callee) @call

(call_expression function: (selector_expression operand: (_) @receiver field: (field_identifier) @callee)) @call

(import_spec path: (interpreted_string_literal) @import)
