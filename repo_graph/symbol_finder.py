from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from tree_sitter import Language, Parser, Query, QueryCursor  # type: ignore
import tree_sitter_python as tspython


# ------------------------------------------------------------
# Dataclasses para Symbol Usages
# ------------------------------------------------------------

@dataclass
class SymbolLocation:
    """Representa a localização exata de um símbolo no código."""
    file_path: Path
    line: int           # 1-based
    column: int         # 0-based
    end_column: int     # 0-based
    context_line: str   # linha de código para exibição


@dataclass
class SymbolReference:
    """Representa uma referência/uso de um símbolo."""
    location: SymbolLocation
    reference_type: str  # "instantiation", "attribute_access", "type_hint", "import"
    symbol_name: str     # ex: "User.email"


@dataclass
class SymbolUsages:
    """Resultado da busca por usos de um símbolo."""
    symbol_name: str
    definition_location: Optional[SymbolLocation]
    references: List[SymbolReference]

    def find_references_of(self, file_path: str | Path) -> List[SymbolReference]:
        if not self.references:
            return []

        file_path = Path(file_path)

        # Try to find references by the exact file path
        found_references = [
            ref for ref in self.references
            if ref.location.file_path == file_path
        ]
        if found_references:
            return found_references

        # Try to find references by parent and file name
        found_references = [
            ref for ref in self.references
            if ref.location.file_path.parent.name == file_path.parent.name
               and ref.location.file_path.name == file_path.name
        ]
        if found_references:
            return found_references

        # Otherwise, try to find references by file name only
        found_references = [
            ref for ref in self.references
            if ref.location.file_path.name == file_path.name
        ]
        return found_references



    def pretty_print(self):

        file_path = self.definition_location.file_path
        formatted_file_path = f".../{file_path.parent.name}/{file_path.name}"

        print(f"Symbol: {self.symbol_name}")
        print(f"Defined by: {formatted_file_path} ({self.definition_location.context_line})")
        print(f"Found {len(self.references)} usages:")

        for ref in self.references:
            loc = ref.location
            print(f"  {loc.file_path}:{loc.line}:{loc.column} [{ref.reference_type}]")
            print(f"    {loc.context_line}")


# ------------------------------------------------------------
# SymbolFinder - Classe dedicada à busca de símbolos
# ------------------------------------------------------------

class SymbolFinder:
    """Classe dedicada à busca de símbolos usando Tree-sitter."""

    def __init__(self):
        self._parser = None  # lazy init
        self._language = None

    def _get_parser(self) -> Parser:
        """Cria parser Tree-sitter (lazy init)."""
        if self._parser is None:
            self._language = Language(tspython.language())
            self._parser = Parser(self._language)
        return self._parser

    def _parse_qualified_name(self, name: str) -> tuple:
        """Separa 'User.email' em ('User', 'email')."""
        parts = name.split(".", 1)
        class_name = parts[0]
        attr_name = parts[1] if len(parts) > 1 else None
        return class_name, attr_name

    def _read_file(self, file_path: Path) -> Optional[bytes]:
        """Lê arquivo como bytes."""
        try:
            return file_path.read_bytes()
        except Exception:
            return None

    def _get_context_line(self, code: bytes, line_num: int) -> str:
        """Retorna a linha de código (0-based line_num)."""
        lines = code.decode("utf-8", errors="replace").split("\n")
        if 0 <= line_num < len(lines):
            return lines[line_num].strip()
        return ""

    def _run_query(self, query_str: str, root_node):
        """Executa uma query Tree-sitter e retorna os matches."""
        query = Query(self._language, query_str)
        cursor = QueryCursor(query)
        return cursor.matches(root_node)

    def _find_definition(
        self,
        file_path: Path,
        class_name: str,
        attr_name: Optional[str]
    ) -> Optional[SymbolLocation]:
        """Encontra onde o símbolo é definido."""
        code = self._read_file(file_path)
        if code is None:
            return None

        parser = self._get_parser()
        tree = parser.parse(code)

        # Query para encontrar definição de classe
        query_str = """
            (class_definition
                name: (identifier) @class.name)
        """

        for pattern_index, captures in self._run_query(query_str, tree.root_node):
            for node in captures.get("class.name", []):
                name = code[node.start_byte:node.end_byte].decode("utf-8")
                if name == class_name:
                    if attr_name is None:
                        # Buscando só a classe
                        return SymbolLocation(
                            file_path=file_path,
                            line=node.start_point[0] + 1,
                            column=node.start_point[1],
                            end_column=node.end_point[1],
                            context_line=self._get_context_line(code, node.start_point[0])
                        )
                    else:
                        # Buscando atributo da classe - encontrar no body
                        return self._find_attribute_definition(
                            tree.root_node, code, file_path, class_name, attr_name
                        )

        return None

    def _find_attribute_definition(
        self,
        root_node,
        code: bytes,
        file_path: Path,
        class_name: str,
        attr_name: str
    ) -> Optional[SymbolLocation]:
        """Encontra definição de atributo dentro de uma classe."""
        # Query para encontrar atributos em classe/dataclass
        query_str = """
            (class_definition
                name: (identifier) @class.name
                body: (block
                    (expression_statement
                        (assignment
                            left: (identifier) @attr.name))))
        """

        for pattern_index, captures in self._run_query(query_str, root_node):
            class_nodes = captures.get("class.name", [])
            attr_nodes = captures.get("attr.name", [])

            for class_node in class_nodes:
                cname = code[class_node.start_byte:class_node.end_byte].decode("utf-8")
                if cname == class_name:
                    for attr_node in attr_nodes:
                        aname = code[attr_node.start_byte:attr_node.end_byte].decode("utf-8")
                        if aname == attr_name:
                            return SymbolLocation(
                                file_path=file_path,
                                line=attr_node.start_point[0] + 1,
                                column=attr_node.start_point[1],
                                end_column=attr_node.end_point[1],
                                context_line=self._get_context_line(code, attr_node.start_point[0])
                            )

        return None

    def _find_typed_variables(
        self,
        root_node,
        code: bytes,
        class_name: str
    ) -> List[str]:
        """Encontra nomes de variáveis que são do tipo da classe."""
        var_names = []

        # Query para instanciações: user = User(...)
        instantiation_query = """
            (assignment
                left: (identifier) @var.name
                right: (call
                    function: (identifier) @class.name))
        """

        for pattern_index, captures in self._run_query(instantiation_query, root_node):
            var_nodes = captures.get("var.name", [])
            class_nodes = captures.get("class.name", [])

            for class_node in class_nodes:
                cname = code[class_node.start_byte:class_node.end_byte].decode("utf-8")
                if cname == class_name:
                    for var_node in var_nodes:
                        vname = code[var_node.start_byte:var_node.end_byte].decode("utf-8")
                        if vname not in var_names:
                            var_names.append(vname)

        # Query para type hints: user: User = ...
        typehint_query = """
            (assignment
                left: (identifier) @var.name
                type: (type (identifier) @type.name))
        """

        for pattern_index, captures in self._run_query(typehint_query, root_node):
            var_nodes = captures.get("var.name", [])
            type_nodes = captures.get("type.name", [])

            for type_node in type_nodes:
                tname = code[type_node.start_byte:type_node.end_byte].decode("utf-8")
                if tname == class_name:
                    for var_node in var_nodes:
                        vname = code[var_node.start_byte:var_node.end_byte].decode("utf-8")
                        if vname not in var_names:
                            var_names.append(vname)

        # Query para parâmetros tipados: def foo(user: User):
        param_query = """
            (typed_parameter
                (identifier) @param.name
                type: (type (identifier) @param.type))
        """

        for pattern_index, captures in self._run_query(param_query, root_node):
            param_nodes = captures.get("param.name", [])
            type_nodes = captures.get("param.type", [])

            for type_node in type_nodes:
                tname = code[type_node.start_byte:type_node.end_byte].decode("utf-8")
                if tname == class_name:
                    for param_node in param_nodes:
                        pname = code[param_node.start_byte:param_node.end_byte].decode("utf-8")
                        if pname not in var_names:
                            var_names.append(pname)

        return var_names

    def _find_attribute_accesses(
        self,
        root_node,
        code: bytes,
        file_path: Path,
        var_names: List[str],
        attr_name: str,
        qualified_name: str
    ) -> List[SymbolReference]:
        """Encontra acessos var.attr onde var está em var_names."""
        references = []

        # Query para acessos a atributo
        query_str = """
            (attribute
                object: (identifier) @object.name
                attribute: (identifier) @attr.name)
        """

        for match in self._run_query(query_str, root_node):
            captures = match[1]
            obj_nodes = captures.get("object.name", [])
            attr_nodes = captures.get("attr.name", [])

            for obj_node in obj_nodes:
                obj_name = code[obj_node.start_byte:obj_node.end_byte].decode("utf-8")
                if obj_name in var_names:
                    for attr_node in attr_nodes:
                        aname = code[attr_node.start_byte:attr_node.end_byte].decode("utf-8")
                        if aname == attr_name:
                            location = SymbolLocation(
                                file_path=file_path,
                                line=attr_node.start_point[0] + 1,
                                column=attr_node.start_point[1],
                                end_column=attr_node.end_point[1],
                                context_line=self._get_context_line(code, attr_node.start_point[0])
                            )
                            references.append(SymbolReference(
                                location=location,
                                reference_type="attribute_access",
                                symbol_name=qualified_name
                            ))

        return references

    def _find_class_references(
        self,
        root_node,
        code: bytes,
        file_path: Path,
        class_name: str
    ) -> List[SymbolReference]:
        """Encontra referências à classe (instanciações, type hints, imports)."""
        references = []

        # Instanciações
        instantiation_query = """
            (call
                function: (identifier) @class.name)
        """

        for match in self._run_query(instantiation_query, root_node):
            for node in match[1].get("class.name", []):
                name = code[node.start_byte:node.end_byte].decode("utf-8")
                if name == class_name:
                    location = SymbolLocation(
                        file_path=file_path,
                        line=node.start_point[0] + 1,
                        column=node.start_point[1],
                        end_column=node.end_point[1],
                        context_line=self._get_context_line(code, node.start_point[0])
                    )
                    references.append(SymbolReference(
                        location=location,
                        reference_type="instantiation",
                        symbol_name=class_name
                    ))

        # Type hints
        type_query = """
            (type (identifier) @type.name)
        """

        for match in self._run_query(type_query, root_node):
            for node in match[1].get("type.name", []):
                name = code[node.start_byte:node.end_byte].decode("utf-8")
                if name == class_name:
                    location = SymbolLocation(
                        file_path=file_path,
                        line=node.start_point[0] + 1,
                        column=node.start_point[1],
                        end_column=node.end_point[1],
                        context_line=self._get_context_line(code, node.start_point[0])
                    )
                    references.append(SymbolReference(
                        location=location,
                        reference_type="type_hint",
                        symbol_name=class_name
                    ))

        # Imports
        import_query = """
            (import_from_statement
                name: (identifier) @import.name)
        """

        for match in self._run_query(import_query, root_node):
            for node in match[1].get("import.name", []):
                name = code[node.start_byte:node.end_byte].decode("utf-8")
                if name == class_name:
                    location = SymbolLocation(
                        file_path=file_path,
                        line=node.start_point[0] + 1,
                        column=node.start_point[1],
                        end_column=node.end_point[1],
                        context_line=self._get_context_line(code, node.start_point[0])
                    )
                    references.append(SymbolReference(
                        location=location,
                        reference_type="import",
                        symbol_name=class_name
                    ))

        return references

    def _find_references_in_file(
        self,
        file_path: Path,
        class_name: str,
        attr_name: Optional[str],
        qualified_name: str
    ) -> List[SymbolReference]:
        """Encontra referências ao símbolo em um arquivo."""
        code = self._read_file(file_path)
        if code is None:
            return []

        parser = self._get_parser()
        tree = parser.parse(code)
        root_node = tree.root_node

        references = []

        if attr_name:
            # Buscando atributo: encontrar variáveis tipadas e acessos
            typed_vars = self._find_typed_variables(root_node, code, class_name)
            # Adicionar a própria classe para acessos diretos como User.email
            typed_vars.append(class_name)
            attr_refs = self._find_attribute_accesses(
                root_node, code, file_path, typed_vars, attr_name, qualified_name
            )
            references.extend(attr_refs)
        else:
            # Buscando só a classe: encontrar instanciações, type hints, imports
            class_refs = self._find_class_references(root_node, code, file_path, class_name)
            references.extend(class_refs)

        return references

    def find_references(
        self,
        definition_file: Path,
        dependent_files: List[Path],
        qualified_name: str
    ) -> SymbolUsages:
        """
        Encontra referências a um símbolo.

        Args:
            definition_file: Arquivo onde o símbolo é definido
            dependent_files: Arquivos que dependem do definition_file
            qualified_name: "ClassName" ou "ClassName.attribute"

        Returns:
            SymbolUsages com todas as referências encontradas
        """
        class_name, attr_name = self._parse_qualified_name(qualified_name)

        # 1. Encontrar definição no arquivo fonte
        definition = self._find_definition(definition_file, class_name, attr_name)

        # 2. Buscar referências nos arquivos dependentes
        references = []
        for file_path in dependent_files:
            refs = self._find_references_in_file(file_path, class_name, attr_name, qualified_name)
            references.extend(refs)

        return SymbolUsages(
            symbol_name=qualified_name,
            definition_location=definition,
            references=references
        )
