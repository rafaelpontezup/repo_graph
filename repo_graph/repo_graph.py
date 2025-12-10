import os

import networkx as nx
import tree_sitter_python as tspython
from tree_sitter import Language, Parser, Query, QueryCursor


class RepoGraph:
    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        self.graph = nx.DiGraph()

        print(f"[DEBUG] RepoGraph root = {self.root}")
        # Tree-sitter parser
        self.language= Language(tspython.language())
        self.parser = Parser(self.language)

    # ------------------------------------------------------------
    # Build graph
    # ------------------------------------------------------------
    def build(self):
        print("\n[DEBUG] === Building graph ===")

        for dirpath, dirnames, files in os.walk(self.root):
            # Ignores dev directories
            dirnames[:] = [
                d for d in dirnames
                if d not in {".venv", "venv", "env", "libs", "__pycache__"}
            ]
            for f in files:
                if not f.endswith(".py"):
                    continue

                full = os.path.join(dirpath, f)
                rel = os.path.relpath(full, self.root)

                print(f"\n[DEBUG] Parsing file: {rel}")

                self.graph.add_node(rel)

                code = self._read_file(full)
                if code is None:
                    print("[DEBUG]   Could not read file")
                    continue

                tree = self.parser.parse(code)
                root_node = tree.root_node

                print("[DEBUG]   Extracting imports...")
                for module, symbol in self._extract_imports(root_node, code):
                    if symbol:
                        print(f"[DEBUG]     Found import: from '{module}' import '{symbol}'")
                    else:
                        print(f"[DEBUG]     Found import: '{module}'")
                    self._add_edge(rel, module, symbol)

    # ------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------
    def _read_file(self, full_path: str) -> bytes | None:
        try:
            return open(full_path, "rb").read()
        except Exception as e:
            print(f"[DEBUG] Failed to read {full_path}: {e}")
            return None

    # ------------------------------------------------------------
    # Import extraction using Tree-Sitter
    # ------------------------------------------------------------
    def _extract_imports(self, root_node, code: bytes):
        """
        Extrai imports capturando tanto módulos quanto símbolos.

        Retorna tuplas (module, symbol):
        - `import pkg` → ('pkg', None)
        - `import pkg.sub` → ('pkg.sub', None)
        - `from pkg import x` → ('pkg', 'x')
        - `from pkg import x, y` → ('pkg', 'x'), ('pkg', 'y')
        - `from pkg.sub import func` → ('pkg.sub', 'func')
        - `from . import x` → ('.', 'x')
        - `from pkg import *` → ('pkg', None)
        """

        QUERY = """
            ; Rule 1: Simple import statements
            ; import x.y
            ; import x.y as z
            (import_statement
                name: [
                    (dotted_name) @import.module
                    (aliased_import
                        name: (dotted_name) @import.module)
                ])

            ; Rule 2: from...import statements
            ; from x.y import z
            ; from . import z
            ; from ..x import z
            (import_from_statement
                module_name: [
                    (dotted_name) @import.from.module
                    (relative_import) @import.from.module
                ]
                name: [
                    (dotted_name) @import.from.symbol
                    (identifier) @import.from.symbol
                    (aliased_import
                        name: [
                            (dotted_name) @import.from.symbol
                            (identifier) @import.from.symbol
                        ])
                ])
            
            ; Rule 3: from...import * (wildcard)
            ; from x.y import *
            ; from . import *
            (import_from_statement
                module_name: [
                    (dotted_name) @import.from.wildcard.module
                    (relative_import) @import.from.wildcard.module
                ]
                (wildcard_import))
        """

        query = Query(self.language, QUERY)
        cursor = QueryCursor(query)

        def text(node):
            return code[node.start_byte:node.end_byte].decode("utf8")

        seen = set()  # Evita duplicatas

        for pattern_index, captures in cursor.matches(root_node):
            # Case 1: Simple import (import pkg.sub)
            if "import.module" in captures:
                for node in captures["import.module"]:
                    module = text(node).strip()
                    if " as " in module:
                        module = module.split(" as ")[0].strip()

                    key = (module, None)
                    if key not in seen:
                        seen.add(key)
                        yield key

            # Case 2: from...import with symbols
            if "import.from.module" in captures and "import.from.symbol" in captures:
                modules = [text(n).strip() for n in captures["import.from.module"]]
                symbols = [text(n).strip() for n in captures["import.from.symbol"]]

                for module in modules:
                    for symbol in symbols:
                        if " as " in symbol:
                            symbol = symbol.split(" as ")[0].strip()

                        key = (module, symbol)
                        if key not in seen:
                            seen.add(key)
                            yield key

            # Case 3: from...import * (wildcard)
            if "import.from.wildcard.module" in captures:
                modules = [text(n).strip() for n in captures["import.from.wildcard.module"]]

                for module in modules:
                    key = (module, None)  # None = sem símbolo específico, importa tudo
                    if key not in seen:
                        seen.add(key)
                        yield key


    def _add_edge(self, src: str, module: str, symbol: str = None):
        """
        Cria edge de dependência considerando a semântica correta de imports Python:
        - `import pkg` → pkg/__init__.py (apenas)
        - `import pkg.a` → pkg/__init__.py E pkg/a.py
        - `from pkg import a` → pkg/__init__.py OU pkg/a.py (se 'a' for um arquivo)
        - `from pkg.a import func` → pkg/__init__.py E pkg/a.py
        """
        print(f"[DEBUG]     Resolving import module='{module}' symbol='{symbol}' from '{src}'")

        src_abs = os.path.join(self.root, src)
        src_dir = os.path.dirname(src_abs)

        # Resolve module path
        if module.startswith("."):
            dots = len(module) - len(module.lstrip("."))
            tail = module[dots:]

            base = src_dir
            for _ in range(dots - 1):
                base = os.path.dirname(base)

            if tail:
                parts = tail.split(".")
                module_path = os.path.join(base, *parts)
            else:
                module_path = base
        else:
            parts = module.split(".")
            module_path = os.path.join(self.root, *parts)

        print(f"[DEBUG]       Module path: {module_path}")

        # Add dependencies to parent __init__.py files
        self._add_parent_init_deps(src, module_path)

        # Try module as a direct .py file
        module_file = module_path + ".py"
        if os.path.exists(module_file):
            module_rel = os.path.relpath(module_file, self.root)
            self._add_graph_edge(src, module_rel)
            # If there's a symbol, it's a class/function inside this module file
            # The dependency is already captured by adding the module file
            if symbol:
                print(f"[DEBUG]       → Symbol '{symbol}' is defined in {module_rel}")
            return

        # Try module as a package
        if os.path.isdir(module_path):
            init_file = os.path.join(module_path, "__init__.py")
            if os.path.exists(init_file):
                init_rel = os.path.relpath(init_file, self.root)
                self._add_graph_edge(src, init_rel)
                print(f"[DEBUG]       → Package import resolved to __init__.py")

                # If there's a symbol, try to resolve it as a submodule of this package
                if symbol:
                    # Try symbol as a submodule: pkg + symbol = pkg/symbol.py
                    symbol_path = os.path.join(module_path, symbol.replace(".", os.sep) + ".py")
                    if os.path.exists(symbol_path):
                        symbol_rel = os.path.relpath(symbol_path, self.root)
                        print(f"[DEBUG]       ✔ Symbol '{symbol}' resolved to submodule: {symbol_rel}")
                        self._add_graph_edge(src, symbol_rel)
                        return

                    # Try symbol as a sub-package: pkg/symbol/__init__.py
                    symbol_pkg = os.path.join(module_path, symbol.replace(".", os.sep))
                    if os.path.isdir(symbol_pkg):
                        symbol_init = os.path.join(symbol_pkg, "__init__.py")
                        if os.path.exists(symbol_init):
                            symbol_init_rel = os.path.relpath(symbol_init, self.root)
                            print(f"[DEBUG]       ✔ Symbol '{symbol}' resolved to sub-package: {symbol_init_rel}")
                            self._add_graph_edge(src, symbol_init_rel)
                            return

                    # Symbol is not a file/package, must be defined in the __init__.py
                    print(f"[DEBUG]       → Symbol '{symbol}' is not a file, defined in {init_rel}")
                return
            else:
                print(f"[DEBUG]       ⚠ Directory exists but no __init__.py: {module_path}")
                return

        print(f"[DEBUG]       ✖ Target not found: {module_path}")


    def _add_parent_init_deps(self, src: str, tgt_path: str):
        """
        Adiciona dependências para todos os __init__.py no caminho até o módulo alvo.

        Ex: import pkg.sub.module
        → adiciona pkg/__init__.py e pkg/sub/__init__.py

        Isso reflete o fato de que Python executa todos os __init__.py no caminho.
        """
        rel_path = os.path.relpath(tgt_path, self.root)

        # Se o target está fora do repo, não adiciona parent inits
        if rel_path.startswith(".."):
            return

        path_parts = rel_path.split(os.sep)

        # Percorre cada nível do caminho
        current_path = self.root
        for part in path_parts[:-1]:  # Não inclui o arquivo/módulo final
            current_path = os.path.join(current_path, part)
            init_file = os.path.join(current_path, "__init__.py")

            if os.path.exists(init_file):
                init_rel = os.path.relpath(init_file, self.root)
                print(f"[DEBUG]       → Adding parent package dependency: {init_rel}")
                self._add_graph_edge(src, init_rel)


    def _add_graph_edge(self, src: str, target: str):
        """Helper to add edge to graph with logging."""
        # Skip if both are __init__.py files
        if src.endswith("__init__.py") and target.endswith("__init__.py"):
            print(f"[DEBUG]       ⊘ Skipping __init__.py -> __init__.py edge")
            return

        if not self.graph.has_edge(src, target):
            print(f"[DEBUG]       ✔ Edge created: {src} -> {target}")
            self.graph.add_edge(src, target)
        else:
            print(f"[DEBUG]       ↷ Edge already exists: {src} -> {target}")


    # ------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------
    def dependencies_of(self, file: str):
        """Arquivos nos quais 'file' depende."""
        return list(self.graph.successors(file))

    def usages_of(self, file: str):
        """Arquivos que dependem de 'file'."""
        return list(self.graph.predecessors(file))
