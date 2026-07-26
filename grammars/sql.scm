; Tree-sitter query: SQL semantic units
(create_table_statement
  name: (identifier) @table.name) @table.unit

(create_view_statement
  name: (identifier) @view.name) @view.unit

(create_index_statement) @index.unit

(create_function_statement
  name: (identifier) @function.name) @function.unit

(select_statement) @query.unit
