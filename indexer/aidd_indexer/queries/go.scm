;; Go — definitions, calls, imports.
;; Patterns are separated by blank lines and compiled one by one, so a
;; pattern that does not match the installed grammar is skipped with a
;; warning instead of breaking the whole language.

(function_declaration name: (identifier) @name) @def.function

(method_declaration name: (field_identifier) @name) @def.method

(type_declaration (type_spec name: (type_identifier) @name type: (struct_type))) @def.struct

(type_declaration (type_spec name: (type_identifier) @name type: (interface_type))) @def.interface

(type_declaration (type_spec name: (type_identifier) @name type: (_))) @def.type

(const_declaration (const_spec name: (identifier) @name)) @def.const

(call_expression function: (identifier) @callee) @call

(call_expression function: (selector_expression operand: (_) @receiver field: (field_identifier) @callee)) @call

(import_spec path: (interpreted_string_literal) @import)
