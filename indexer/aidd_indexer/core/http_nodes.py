"""Tree-sitter node kinds the HTTP extractor reads, across the parseable languages (Go, TS/JS, C#, Python).

One place for them, so that "is this a call?" or "is this a name?" means the same in every scanner and helper.
"""

from __future__ import annotations

from tree_sitter import Node

STRING_NODES = frozenset({"interpreted_string_literal", "raw_string_literal", "string", "string_literal", "template_string",
                          "verbatim_string_literal", "interpolated_string_expression"})
INTERPOLATION_NODES = frozenset({"interpolation", "template_substitution"})          # f"{x}", $"{x}", `${x}`
STRING_TEXT_NODES = frozenset({"string_content", "string_fragment", "interpolated_string_text", "escape_sequence"})
CALL_NODES = frozenset({"call_expression", "invocation_expression", "call"})
NAME_NODES = frozenset({"identifier", "selector_expression", "member_expression", "member_access_expression", "attribute"})
OBJECT_NODES = frozenset({"composite_literal", "object", "dictionary", "anonymous_object_creation_expression"})
CONCAT_NODES = frozenset({"binary_expression", "binary_operator"})
ASSIGNMENT_NODES = frozenset({"short_var_declaration", "assignment_statement", "assignment", "assignment_expression",
                              "variable_declarator", "var_spec"})
APPEND_NODES = frozenset({"augmented_assignment_expression", "augmented_assignment", "assignment_statement",
                          "assignment_expression"})                                 # `x += e` (checked by operator)
WRAPPED_ARG_NODES = frozenset({"argument", "variadic_argument", "spread_element"})   # C# argument, Go `h...`, JS `...h`

# What delimits the scope of a local variable — an application object is recognised per (scope, name), so a
# `r` that is the application in `main` is not taken for the `r` a helper builds and returns.
FUNCTION_SCOPES = frozenset({"function_declaration", "method_declaration", "func_literal", "function_definition",
                             "arrow_function", "function_expression", "function", "method_definition",
                             "generator_function_declaration", "local_function_statement", "lambda_expression",
                             "anonymous_method_expression", "lambda", "constructor_declaration"})
CLASS_NODES = frozenset({"class_declaration", "class_definition", "class", "struct_declaration", "record_declaration"})
HANDLER_NODES = frozenset({"func_literal", "arrow_function", "function_expression", "function", "lambda_expression",
                           "anonymous_method_expression", "lambda", "method_reference"})
NON_HANDLER_NODES = STRING_NODES | {"nil", "null", "none", "number", "int_literal", "integer", "float_literal", "true", "false",
                                    "composite_literal", "object", "array", "dictionary", "list", "object_creation_expression",
                                    "unary_expression", "boolean_literal", "null_literal", "character_literal"}


def has_interpolation(n: Node) -> bool:
    return any(c.type in INTERPOLATION_NODES for c in n.children)
