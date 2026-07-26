; Tree-sitter query: Go semantic units
(function_declaration
  name: (identifier) @function.name) @function.unit

(method_declaration
  name: (field_identifier) @method.name) @method.unit

(type_declaration
  (type_spec
    name: (type_identifier) @type.name)) @type.unit

(import_declaration) @import.unit

(const_declaration) @const.unit
(var_declaration) @var.unit
