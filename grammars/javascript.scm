; Tree-sitter query: JavaScript/TypeScript semantic units
(function_declaration
  name: (identifier) @function.name) @function.unit

(method_definition
  name: (property_identifier) @method.name) @method.unit

(class_declaration
  name: (identifier) @class.name) @class.unit

(lexical_declaration
  (variable_declarator
    name: (identifier) @variable.name)) @variable.unit

(import_statement) @import.unit
(export_statement) @export.unit
