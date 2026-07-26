; Tree-sitter query: Rust semantic units
(function_item
  name: (identifier) @function.name) @function.unit

(struct_item
  name: (type_identifier) @struct.name) @struct.unit

(enum_item
  name: (type_identifier) @enum.name) @enum.unit

(trait_item
  name: (type_identifier) @trait.name) @trait.unit

(impl_item
  type: (type_identifier) @impl.name) @impl.unit

(mod_item
  name: (identifier) @module.name) @module.unit
