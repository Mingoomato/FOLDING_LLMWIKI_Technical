; Tree-sitter query: Python semantic units
(function_definition
  name: (identifier) @function.name) @function.unit

(class_definition
  name: (identifier) @class.name) @class.unit

(decorated_definition) @decorated.unit

(import_statement) @import.unit
(import_from_statement) @import.unit

(assignment
  left: (identifier) @variable.name) @variable.unit
