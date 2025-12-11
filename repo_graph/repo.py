from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .repo_graph import RepoGraph
from .symbol_finder import SymbolFinder, SymbolUsages


# ------------------------------------------------------------
# Dataclasses
# ------------------------------------------------------------

@dataclass
class FileDependencies:
    source_file: Path
    file_dependencies: Optional[List[Path]]


@dataclass
class FileUsages:
    source_file: Path
    file_usages: Optional[List[Path]]

    def __post_init__(self):
        assert self.source_file, "source_file must not be empty"
        assert self.source_file.is_file(), "source_file must be a file"
        assert self.file_usages, "file_usages must not be empty"


    def find_symbol_references(self, qualified_name: str) -> SymbolUsages:
        """
        Encontra referências a um símbolo definido em source_file
        nos arquivos que dependem dele (file_usages).

        Args:
            qualified_name: "ClassName" ou "ClassName.attribute"

        Returns:
            SymbolUsages com todas as referências encontradas

        Example:
            >>> usages = repo.find_usages(Path("model.py"))
            >>> symbol_refs = usages.find_symbol_references("User.email")
            >>> for ref in symbol_refs.references:
            ...     print(f"{ref.location.file_path}:{ref.location.line}")
        """
        finder = SymbolFinder()
        return finder.find_references(
            definition_file=self.source_file,
            dependent_files=self.file_usages or [],
            qualified_name=qualified_name
        )


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
        target_dir = (self.repository_path / base_dir).resolve()
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