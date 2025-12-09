from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import os
import ast
import networkx as nx

import os
import networkx as nx
from tree_sitter import Language, Parser, Query, QueryCursor  # type: ignore
import tree_sitter_python as tspython


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

            ; Rule 2: from...import with module name
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
            
            ; Rule 3: from...import without explicit name (catches the module only)
            (import_from_statement
                module_name: [
                    (dotted_name) @import.from.module.only
                    (relative_import) @import.from.module.only
                ])
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
            
            # Case 2: from...import with both module and symbol
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
            
            # Case 3: from...import without symbols captured (just module)
            if "import.from.module.only" in captures:
                for node in captures["import.from.module.only"]:
                    module = text(node).strip()
                    key = (module, None)
                    if key not in seen:
                        seen.add(key)
                        yield key



    # ------------------------------------------------------------
    # Graph edge creation
    # ------------------------------------------------------------
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

        # If there's a symbol, try to resolve it as a file first
        if symbol:
            # Try symbol as a submodule: pkg + symbol = pkg/symbol.py
            symbol_path = os.path.join(module_path, symbol.replace(".", os.sep) + ".py")
            if os.path.exists(symbol_path):
                symbol_rel = os.path.relpath(symbol_path, self.root)
                print(f"[DEBUG]       ✔ Symbol '{symbol}' resolved to file: {symbol_rel}")
                self._add_graph_edge(src, symbol_rel)
                return
            
            # Try symbol as a package: pkg/symbol/__init__.py
            symbol_pkg = os.path.join(module_path, symbol.replace(".", os.sep))
            if os.path.isdir(symbol_pkg):
                init_file = os.path.join(symbol_pkg, "__init__.py")
                if os.path.exists(init_file):
                    init_rel = os.path.relpath(init_file, self.root)
                    print(f"[DEBUG]       ✔ Symbol '{symbol}' resolved to package: {init_rel}")
                    self._add_graph_edge(src, init_rel)
                    return
            
            # Symbol is not a file, so it must be defined in module's __init__.py
            print(f"[DEBUG]       → Symbol '{symbol}' is not a file, assuming it's from __init__.py")

        # Try module as a direct .py file
        module_file = module_path + ".py"
        if os.path.exists(module_file):
            module_rel = os.path.relpath(module_file, self.root)
            self._add_graph_edge(src, module_rel)
            return

        # Try module as a package
        if os.path.isdir(module_path):
            init_file = os.path.join(module_path, "__init__.py")
            if os.path.exists(init_file):
                init_rel = os.path.relpath(init_file, self.root)
                self._add_graph_edge(src, init_rel)
                print(f"[DEBUG]       → Package import resolved to __init__.py")
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



@dataclass
class FileDependencies:
    source_file: Path
    file_dependencies: Optional[List[Path]]


@dataclass
class FileUsages:
    source_file: Path
    file_usages: Optional[List[Path]]


class Repository:

    def __init__(self, repository_path: Path):
        self.repository_path = Path(repository_path).resolve()

        # Cria e constrói o grafo
        self._graph = RepoGraph(str(self.repository_path))
        self._graph.build()

    # ------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------
    def _to_rel(self, file_path: Path) -> str:
        """
        Converte Path absoluto → caminho relativo usado no grafo (str).
        """
        return str(file_path.resolve().relative_to(self.repository_path))

    def _to_abs(self, rel_path: str) -> Path:
        """
        Converte caminho relativo usado no grafo (str) → Path absoluto.
        """
        return (self.repository_path / rel_path).resolve()


    def list_files(self, base_dir: Optional[Path] = ".") -> List[Path]:
        target_dir = (repo_root / base_dir).resolve()
        if not target_dir.exists():
            raise ValueError(f"❌ Path not found: {target_dir}")

        # Coletar arquivos a analisar
        found_files = []
        if target_dir.is_file() and target_dir.suffix == ".py":
            found_files.append(target_dir)
        elif target_dir.is_dir():
            IGNORED_DIRS = {".venv", "venv", "env", "libs", "__pycache__"}
            for p in target_dir.rglob("*.py"):
                if any(ignored in p.parts for ignored in IGNORED_DIRS):
                    continue
                found_files.append(p)
        else:
            raise ValueError("❌ base_dir must be a .py file or directory within the repository")
        
        return found_files


    # ------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------
    def find_dependencies(self, file_path: Path) -> FileDependencies:
        """
        Retorna todos os arquivos dos quais `file_path` depende.
        """
        rel = self._to_rel(file_path)

        if rel not in self._graph.graph.nodes:
            return FileDependencies(source_file=file_path, file_dependencies=[])

        deps_rel = self._graph.dependencies_of(rel)
        deps_abs = [self._to_abs(r) for r in deps_rel]

        return FileDependencies(
            source_file=file_path.resolve(),
            file_dependencies=deps_abs,
        )

    def find_usages(self, file_path: Path) -> FileUsages:
        """
        Retorna todos os arquivos que dependem de `file_path`.
        """
        rel = self._to_rel(file_path)

        if rel not in self._graph.graph.nodes:
            return FileUsages(source_file=file_path, file_usages=[])

        usages_rel = self._graph.usages_of(rel)
        usages_abs = [self._to_abs(r) for r in usages_rel]

        return FileUsages(
            source_file=file_path.resolve(),
            file_usages=usages_abs,
        )
        
        
# -------------------------
# Example usage
# -------------------------
if __name__ == "__main__":
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(
        prog="repo-deps",
        description="Build python file dependency graph from a repository"
    )

    parser.add_argument(
        "repo",
        help="Path to repository root",
    )

    parser.add_argument(
        "--show-files",
        help="File or directory (relative to repo) to show dependencies/usages for",
        required=True,
    )

    args = parser.parse_args()

    repo_root = Path(args.repo).resolve()
    repo = Repository(repo_root)

    # ------------------------------------------------------------
    # Resolve alvo (arquivo ou diretório)
    # ------------------------------------------------------------
    target = (repo_root / args.show_files).resolve()
    if not target.exists():
        raise ValueError(f"❌ Path not found: {target}")

    # Coletar arquivos a analisar
    filtered_files = repo.list_files(base_dir=args.show_files)

    # ------------------------------------------------------------
    # Execução
    # ------------------------------------------------------------
    print(f"🗂️ Repository: {repo_root}")
    print(f"📂 Target file or directory: {args.show_files}")
    print(f"📄 Total of found files: {len(filtered_files)}")
    print("-" * 60)

    for file in sorted(filtered_files):
        print(f"\n📝 {file.relative_to(repo_root)}")
        print("... | ℹ️ Dependencies:")
        deps = repo.find_dependencies(file)

        if not deps.file_dependencies:
            print("        ⚠️  No dependencies found")
        else:
            for p in deps.file_dependencies:
                print("        ✔", p.relative_to(repo_root))

        print("... | ℹ️ Usages (files that import it):")
        uses = repo.find_usages(file)

        if not uses.file_usages:
            print("        ⚠️  No usages found")
        else:
            for p in uses.file_usages:
                print("        ✔", p.relative_to(repo_root))

    print("\n✔ Finished.")
