from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import os
import ast
import networkx as nx

class RepoGraph:
    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        self.graph = nx.DiGraph()

    def build(self):
        for dirpath, _, files in os.walk(self.root):
            for f in files:
                if f.endswith('.py'):
                    full = os.path.join(dirpath, f)
                    rel = os.path.relpath(full, self.root)
                    self.graph.add_node(rel)
                    with open(full) as fh:
                        try:
                            tree = ast.parse(fh.read())
                        except Exception:
                            continue
                        for node in ast.walk(tree):
                            if isinstance(node, ast.Import):
                                for n in node.names:
                                    self._add_edge(rel, n.name)
                            elif isinstance(node, ast.ImportFrom):
                                if node.module:
                                    self._add_edge(rel, node.module)

    def _add_edge(self, src, mod):
        tgt = mod.replace('.', os.sep) + '.py'
        if tgt in self.graph.nodes:
            self.graph.add_edge(src, tgt)

    def dependencies_of(self, file: str):
        return list(self.graph.successors(file))

    def usages_of(self, file: str):
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
    parser = argparse.ArgumentParser(prog="repo-deps", description="Build python file dependency graph from repository")
    parser.add_argument("repo", help="path to repository root")
    parser.add_argument("--show", help="show dependencies for a given file (relative to repo)", default=None, required=True)
    args = parser.parse_args()

    repo = Repository(Path(args.repo))
    if not args.show:
        raise ValueError("❌ Argumento --show deve ser informado")
    
    target = (Path(args.repo) / args.show).resolve()
    
    print("ℹ️ Dependencies for:", target)
    deps = repo.find_dependencies(target)
    if not deps.file_dependencies:
        print("  ⚠️ No dependencies")
    else:
        for p in deps.file_dependencies or []:
            print("  ➡️", p)
    
    print("ℹ️ Usages (files that import it):")
    uses = repo.find_usages(target)
    if not uses.file_usages:
        print("  ⚠️ No usages")
    else:        
        for p in uses.file_usages or []:
            print("  ⬅️ ", p)
        