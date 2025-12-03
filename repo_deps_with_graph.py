from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import os
import ast
import networkx as nx

import os
import networkx as nx
from tree_sitter import Parser
from tree_sitter import Language, Parser  # type: ignore
import tree_sitter_python as tspython


class RepoGraph:
    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        self.graph = nx.DiGraph()

        # Tree-sitter parser
        LANGUAGE = Language(tspython.language())
        self.parser = Parser(LANGUAGE)

    # ------------------------------------------------------------
    # Build graph
    # ------------------------------------------------------------
    def build(self):
        for dirpath, _, files in os.walk(self.root):
            for f in files:
                if not f.endswith(".py"):
                    continue

                full = os.path.join(dirpath, f)
                rel = os.path.relpath(full, self.root)

                self.graph.add_node(rel)

                code = self._read_file(full)
                if code is None:
                    continue

                tree = self.parser.parse(code)
                root_node = tree.root_node

                for imp in self._extract_imports(root_node, code):
                    self._add_edge(rel, imp)

    # ------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------
    def _read_file(self, full_path: str) -> bytes | None:
        try:
            return open(full_path, "rb").read()
        except Exception:
            return None

    # ------------------------------------------------------------
    # Import extraction using Tree-Sitter
    # ------------------------------------------------------------
    def _extract_imports(self, root_node, code: bytes):
        """
        Generator que retorna strings com caminhos tipo:
            - "a.b.c"
            - "module.sub"
        """
        def text(node):
            return code[node.start_byte:node.end_byte].decode("utf8")

        cursor = root_node.walk()
        stack = [root_node]

        while stack:
            node = stack.pop()

            # import module
            if node.type == "import_statement":
                # e.g. "import a", "import a.b.c"
                for child in node.children:
                    if child.type == "dotted_name":
                        yield text(child)

            # from a.b import x
            elif node.type == "import_from_statement":
                module_node = None

                # A module pode estar em "dotted_name" ou "relative_import"
                for child in node.children:
                    if child.type in ("dotted_name", "relative_import"):
                        module_node = child
                        break

                if module_node:
                    module_name = text(module_node)
                    # Limpar "from ..module" => "..module"
                    module_name = module_name.lstrip(".")
                    if module_name:
                        yield module_name

            # DFS
            if hasattr(node, "children"):
                stack.extend(node.children)

    # ------------------------------------------------------------
    # Graph edge creation
    # ------------------------------------------------------------
    def _add_edge(self, src: str, module: str):
        """
        Converte o nome de módulo em caminho de arquivo e cria aresta se existir.
        """
        # Transformar a.b.c → a/b/c.py
        tgt = module.replace(".", os.sep) + ".py"

        if tgt in self.graph.nodes:
            self.graph.add_edge(src, tgt)

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
    files_to_show = []

    if target.is_file() and target.suffix == ".py":
        files_to_show.append(target)

    elif target.is_dir():
        for p in target.rglob("*.py"):
            files_to_show.append(p)

    else:
        raise ValueError("❌ --show-files deve ser um arquivo .py ou um diretório contendo .py")

    # ------------------------------------------------------------
    # Execução
    # ------------------------------------------------------------
    print(f"🗂️ Repository: {repo_root}")
    print(f"📂 Target file or directory: {target}")
    print(f"📄 Total of found files: {len(files_to_show)}")
    print("-" * 60)

    for file in sorted(files_to_show):
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
