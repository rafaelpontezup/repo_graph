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
                for imp in self._extract_imports(root_node, code):
                    print(f"[DEBUG]     Found import: '{imp}'")
                    self._add_edge(rel, imp)

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
    # def _extract_imports(self, root_node, code: bytes):
    #     """
    #     Generator que retorna strings com caminhos tipo:
    #         - "a.b.c"
    #         - "module.sub"
    #     """
    #     def text(node):
    #         return code[node.start_byte:node.end_byte].decode("utf8")

    #     cursor = root_node.walk()
    #     stack = [root_node]

    #     while stack:
    #         node = stack.pop()

    #         # import X
    #         if node.type == "import_statement":
    #             for child in node.children:
    #                 if child.type == "dotted_name":
    #                     yield text(child)

    #         # from X import Y
    #         elif node.type == "import_from_statement":
    #             module_node = None

    #             for child in node.children:
    #                 if child.type in ("dotted_name", "relative_import"):
    #                     module_node = child
    #                     break

    #             if module_node:
    #                 module_name = text(module_node)
    #                 cleaned = module_name.lstrip(".")
    #                 yield cleaned

    #         if hasattr(node, "children"):
    #             stack.extend(node.children)
    from tree_sitter import Query, QueryCursor

    def _extract_imports(self, root_node, code: bytes):
        """
        Extrai imports usando QueryCursor moderno (API nova):
        cursor = QueryCursor(query)
        matches = cursor.matches(node)
        """

        QUERY = b"""
            ; -----------------------------
            ; import x.y
            ; import x.y as z
            ; -----------------------------
            (import_statement
            [
                (dotted_name)
                (aliased_import
                    name: (dotted_name))
            ] @import.module)

            ; -----------------------------
            ; from x.y import z
            ; from .x.y import z
            ; from .. import z
            ; -----------------------------
            (import_from_statement
            [
                (dotted_name)
                (relative_import) 
            ] @import.module)
            
            ; -----------------------------
            ; import x.y.z as alias
            ; -----------------------------
            (import_statement
                (aliased_import
                    name: (dotted_name) @import.module
                    alias: (identifier) @import.alias
                )+
            )
        """

        query = Query(self.language, QUERY)
        cursor = QueryCursor(query)   # ← assinatura nova

        def text(node):
            return code[node.start_byte:node.end_byte].decode("utf8")

        # matches() retorna:  [(pattern_index, {capture_name: [nodes...]})]
        for pattern_index, captures_dict in cursor.matches(root_node):
            # Cada pattern encontrado pode ter vários nodes capturados
            for capture_name, nodes in captures_dict.items():
                if capture_name != "import.module":
                    continue

                for node in nodes:
                    module = text(node).lstrip(".")
                    if module:
                        yield module



    # ------------------------------------------------------------
    # Graph edge creation
    # ------------------------------------------------------------
    # def _add_edge(self, src: str, module: str):
    #     print(f"[DEBUG]   Resolving import '{module}' from '{src}'")

    #     tgt = module.replace(".", os.sep) + ".py"
    #     print(f"[DEBUG]     Converted module to path: {tgt}")

    #     if tgt in self.graph.nodes:
    #         print(f"[DEBUG]     ✔ Edge created: {src} -> {tgt}")
    #         self.graph.add_edge(src, tgt)
    def _add_edge(self, src: str, module: str):
        print(f"[DEBUG]     Resolving import '{module}' from '{src}'")
        
        tgt_rel = module.replace(".", os.sep) + ".py"

        # Caminho absoluto do arquivo alvo
        abs_tgt = os.path.join(self.root, tgt_rel)

        # Se o arquivo realmente existe no repo, convertemos novamente para o formato de nó
        if os.path.exists(abs_tgt):
            final_rel = os.path.relpath(abs_tgt, self.root)
            print(f"[DEBUG]       ✔ Edge created: {src} -> {final_rel}")
            self.graph.add_edge(src, final_rel)
        else:
            print(f"[DEBUG]       ✖ Target not found in repo: {tgt_rel}")

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
