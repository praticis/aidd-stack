;; TypeScript / TSX (also used for JavaScript with the js grammar; patterns
;; referring to type-only nodes simply fail to compile there and are skipped).

(function_declaration name: (identifier) @name) @def.function

(generator_function_declaration name: (identifier) @name) @def.function

(method_definition name: (property_identifier) @name) @def.method

(method_signature name: (property_identifier) @name) @def.method

(abstract_method_signature name: (property_identifier) @name) @def.method

(class_declaration name: (type_identifier) @name) @def.class

(abstract_class_declaration name: (type_identifier) @name) @def.class

(interface_declaration name: (type_identifier) @name) @def.interface

(enum_declaration name: (identifier) @name) @def.enum

(type_alias_declaration name: (type_identifier) @name) @def.type

(lexical_declaration (variable_declarator name: (identifier) @name value: (arrow_function))) @def.function

(lexical_declaration (variable_declarator name: (identifier) @name value: (function_expression))) @def.function

(call_expression function: (identifier) @callee) @call

(call_expression function: (member_expression object: (_) @receiver property: (property_identifier) @callee)) @call

(new_expression constructor: (identifier) @callee) @call

(import_statement source: (string) @import)

(call_expression function: (identifier) @_req arguments: (arguments (string) @import) (#eq? @_req "require"))

;; A class a module declares by an expression: the name its binding gives it.
(program (lexical_declaration (variable_declarator name: (identifier) @name value: (class))) @def.class)

(program (variable_declaration (variable_declarator name: (identifier) @name value: (class))) @def.class)

(program (export_statement declaration: (lexical_declaration (variable_declarator name: (identifier) @name value: (class))) @def.class))

(program (export_statement declaration: (variable_declaration (variable_declarator name: (identifier) @name value: (class))) @def.class))

;; A class field that holds a function is the method its instances run.
(public_field_definition name: (property_identifier) @name value: [(arrow_function) (function_expression)]) @def.method
