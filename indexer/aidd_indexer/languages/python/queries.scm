;; Python — methods are function_definitions nested in a class; the
;; extractor derives `method` from the enclosing definition.

(function_definition name: (identifier) @name) @def.function

(class_definition name: (identifier) @name) @def.class

(call function: (identifier) @callee) @call

(call function: (attribute object: (_) @receiver attribute: (identifier) @callee)) @call

(import_statement name: (dotted_name) @import)

(import_statement name: (aliased_import name: (dotted_name) @import))

(import_from_statement module_name: (dotted_name) @import)

(import_from_statement module_name: (relative_import) @import)
