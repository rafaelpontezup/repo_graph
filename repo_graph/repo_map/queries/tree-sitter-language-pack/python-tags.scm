(module (expression_statement (assignment left: (identifier) @name.definition.constant) @definition.constant))

(class_definition
  name: (identifier) @name.definition.class) @definition.class

(function_definition
  name: (identifier) @name.definition.function) @definition.function

(call
  function: [
      (identifier) @name.reference.call
      (attribute
        attribute: (identifier) @name.reference.call)
  ]) @reference.call

; =============================================================================
; EXPANDED TAGS (beyond official tree-sitter-python)
; =============================================================================

; Module-level constants (MAX_SIZE = 100, UserID = int)
(module
  (assignment
    left: (identifier) @name.definition.constant))

; Class attributes and enum members (RED = 1, default_role = "guest")
(class_definition
  body: (block
    (assignment
      left: (identifier) @name.definition.field)))

; Type-annotated class attributes (name: str, id: int)
(class_definition
  body: (block
    (expression_statement
      (assignment
        left: (identifier) @name.definition.field
        type: (type)))))

; Access to attributes/properties (no calls)
(attribute
  attribute: (identifier) @name.reference.field.access) @reference.field.access
