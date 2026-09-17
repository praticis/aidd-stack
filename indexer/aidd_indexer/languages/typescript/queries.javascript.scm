;; JavaScript (plain) — same shape as typescript.scm without type-only nodes.

(function_declaration name: (identifier) @name) @def.function

(generator_function_declaration name: (identifier) @name) @def.function

(method_definition name: (property_identifier) @name) @def.method

(class_declaration name: (identifier) @name) @def.class

(lexical_declaration (variable_declarator name: (identifier) @name value: (arrow_function))) @def.function

(lexical_declaration (variable_declarator name: (identifier) @name value: (function_expression))) @def.function

(variable_declaration (variable_declarator name: (identifier) @name value: (arrow_function))) @def.function

(call_expression function: (identifier) @callee) @call

(call_expression function: (member_expression object: (_) @receiver property: (property_identifier) @callee)) @call

(new_expression constructor: (identifier) @callee) @call

(import_statement source: (string) @import)

(call_expression function: (identifier) @_req arguments: (arguments (string) @import) (#eq? @_req "require"))
