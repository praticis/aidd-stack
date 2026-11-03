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

;; A class a module declares by an expression: the name its binding gives it, `module.exports = class X`'s own, or the
;; property it is exported under.
(program (lexical_declaration (variable_declarator name: (identifier) @name value: (class))) @def.class)

(program (variable_declaration (variable_declarator name: (identifier) @name value: (class))) @def.class)

(program (export_statement declaration: (lexical_declaration (variable_declarator name: (identifier) @name value: (class))) @def.class))

(program (export_statement declaration: (variable_declaration (variable_declarator name: (identifier) @name value: (class))) @def.class))

(program (expression_statement (assignment_expression
  left: (member_expression object: (identifier) @_m property: (property_identifier) @_e)
  right: (class name: (_) @name)
  (#eq? @_m "module") (#eq? @_e "exports")) @def.class))

(program (expression_statement (assignment_expression
  left: (member_expression object: (identifier) @_m property: (property_identifier) @name)
  right: (class)
  (#eq? @_m "exports")) @def.class))

(program (expression_statement (assignment_expression
  left: (member_expression object: (member_expression object: (identifier) @_m property: (property_identifier) @_e)
                           property: (property_identifier) @name)
  right: (class)
  (#eq? @_m "module") (#eq? @_e "exports")) @def.class))

;; A class field that holds a function is the method its instances run.
(field_definition property: (property_identifier) @name value: [(arrow_function) (function_expression)]) @def.method
