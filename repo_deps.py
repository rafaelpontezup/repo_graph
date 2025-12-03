# repo_deps.py
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Tuple, Set
import os
import sys
import re
from tree_sitter import Language, Parser  # type: ignore
import tree_sitter_python as tspython

TREE_SITTER_AVAILABLE = True
# try:
#     # optional: tree-sitter bindings
#     from tree_sitter import Language, Parser  # type: ignore
#     TREE_SITTER_AVAILABLE = True
# except Exception:
#     TREE_SITTER_AVAILABLE = False

import ast
import networkx as nx


@dataclass
class FileDependencies:
    source_file: Path
    file_dependencies: Optional[List[Path]]


@dataclass
class FileUsages:
    source_file: Path
    file_usages: Optional[List[Path]]


class Repository:
    """
    Repository representation able to find python file dependencies and usages (imports-based).
    """

    def __init__(self, repository_path: Path, python_lang_so: Optional[Path] = None):
        """
        :param repository_path: root path for the repository
        :param python_lang_so: optional path to a compiled tree-sitter python language shared library
                               (for example built via Language.build_library). If not passed or not
                               available, parser falls back to Python's ast module.
        """
        self.repository_path = Path(repository_path).resolve()
        self._files: List[Path] = []
        self._module_to_path: Dict[str, Path] = {}
        self._path_to_module: Dict[Path, str] = {}
        self._index_repository()
        self._parser = None
        # if TREE_SITTER_AVAILABLE and python_lang_so:
        try:
            LANGUAGE = Language(tspython.language()) #Language(str(python_lang_so), "python")
            p = Parser(LANGUAGE)
            self._parser = p
        except Exception:
            # fallback silently to ast
            self._parser = None
            raise

    # -------------------------
    # Indexing helpers
    # -------------------------
    def _index_repository(self) -> None:
        """Scans repository for .py files and builds module ↔ path mappings.

        Rules:
        - repo/foo.py -> module 'foo'
        - repo/pkg/__init__.py -> module 'pkg'
        - repo/pkg/mod.py -> module 'pkg.mod'
        - nested appropriately
        """
        files = list(self.repository_path.rglob("*.py"))
        # normalize and filter out files outside repo (shouldn't happen)
        files = [p.resolve() for p in files if str(p.resolve()).startswith(str(self.repository_path))]
        # build mapping
        module_map: Dict[str, Path] = {}
        path_map: Dict[Path, str] = {}
        for f in files:
            rel = f.relative_to(self.repository_path)
            parts = rel.parts  # tuple of path components
            # find module dotted name
            if parts[-1] == "__init__.py":
                mod_parts = parts[:-1]  # directory is the module
                if not mod_parts:
                    module = "__root__"  # repo-level __init__? unlikely
                else:
                    module = ".".join(mod_parts)
            else:
                name = parts[-1][:-3]  # remove .py
                mod_parts = list(parts[:-1]) + [name]
                module = ".".join(mod_parts)
            module_map[module] = f
            path_map[f] = module

        # Additionally, allow top-level single-name modules to be referenced without package prefix:
        # e.g., file 'script.py' -> module 'script'
        self._files = files
        self._module_to_path = module_map
        self._path_to_module = path_map

    # -------------------------
    # Module <-> Path resolution
    # -------------------------
    def _module_candidates_to_path(self, module_name: str) -> Optional[Path]:
        """Given a module dotted name, return the corresponding Path in the repo if present.

        Heuristics:
        - try exact module (pkg.mod -> pkg/mod.py)
        - if module refers to a package (pkg -> pkg/__init__.py) return that
        """
        # direct match
        if module_name in self._module_to_path:
            return self._module_to_path[module_name]
        # maybe module refers to package path without __init__ registered (rare)
        # try mapping last part to __init__.py
        last_try = module_name + ".__init__"
        if last_try in self._module_to_path:
            return self._module_to_path[last_try]
        # also try mapping module -> module/__init__.py by path existence
        candidate = self.repository_path.joinpath(*module_name.split("."))
        if (candidate.with_suffix(".py")).exists():
            return candidate.with_suffix(".py")
        if (candidate / "__init__.py").exists():
            return (candidate / "__init__.py")
        return None

    def _path_to_module_name(self, file_path: Path) -> Optional[str]:
        return self._path_to_module.get(file_path.resolve())

    # -------------------------
    # Parsing imports
    # -------------------------
    def _extract_imports_with_ast(self, source: str) -> List[Tuple[Optional[int], Optional[str]]]:
        """
        Returns list of imports in the form:
           (level, module_name)
        where level is None for 'import x' style (absolute) and integer for 'from ... import ...' relative levels.
        For 'import x.y' we return module_name='x.y' with level None.
        For 'from a.b import c' -> (0, 'a.b') (level 0 means explicit absolute from)
        For 'from .a import b' -> (1, 'a')
        For 'from .. import x' -> (2, None)  # module None but level indicates parent
        """
        tree = ast.parse(source)
        imports: List[Tuple[Optional[int], Optional[str]]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for n in node.names:
                    imports.append((None, n.name))  # absolute import
            elif isinstance(node, ast.ImportFrom):
                module = node.module  # may be None for 'from . import x'
                level = node.level  # 0 for absolute, >=1 for relative
                # treat level==0 as explicit absolute
                if level == 0:
                    # module may be None (rare)
                    imports.append((0, module))
                else:
                    # relative
                    imports.append((level, module))
        return imports

    if TREE_SITTER_AVAILABLE:
        # optional tree-sitter based import extractor (works if language provided)
        def _extract_imports_with_treesitter(self, source_bytes: bytes) -> List[Tuple[Optional[int], Optional[str]]]:
            """
            Extract imports using Tree-sitter nodes. Returns same shape as ast extractor.
            Note: this requires self._parser to be configured with python language.
            """
            if not self._parser:
                return []
            tree = self._parser.parse(source_bytes)
            root = tree.root_node
            imports: List[Tuple[Optional[int], Optional[str]]] = []

            # simple traversal for import and from_import nodes
            # tree-sitter python grammar nodes: "import_statement", "from_statement" or "import_from_statement"
            # we look for 'import_from_statement' and 'import_statement' nodes
            def walk(node):
                for child in node.children:
                    if child.type == "import_statement":
                        # import_statement -> 'import' dotted_name (',' dotted_name)*
                        # collect dotted_name nodes
                        for n in child.named_children:
                            if n.type == "dotted_name":
                                imports.append((None, self._get_node_text(source_bytes, n)))
                    elif child.type in ("import_from_statement", "from_statement", "from_import_statement", "again"):
                        # Many grammars use "import_from_statement" or "from_statement"
                        # structure: 'from' ('.' | '..')* module 'import' names
                        # we'll try to inspect children to find dots and module name
                        # compute level (# of leading dots)
                        level = 0
                        module_name = None
                        saw_from = False
                        for gc in child.children:
                            if gc.type == "from":
                                saw_from = True
                                continue
                            if saw_from:
                                # expect dots or module name
                                if gc.type == ".":
                                    level += 1
                                elif gc.type == "dotted_name":
                                    module_name = self._get_node_text(source_bytes, gc)
                                elif gc.type == "identifier" and module_name is None:
                                    module_name = self._get_node_text(source_bytes, gc)
                        if level == 0:
                            imports.append((0, module_name))
                        else:
                            imports.append((level, module_name))
                    else:
                        walk(child)

            walk(root)
            return imports

        def _get_node_text(self, source: bytes, node) -> str:
            return source[node.start_byte:node.end_byte].decode("utf-8")

    # -------------------------
    # Resolve imported module names
    # -------------------------
    def _resolve_module_name(self, imported: Tuple[Optional[int], Optional[str]], current_module: Optional[str]) -> Optional[str]:
        """
        Turn (level, module) into an absolute module dotted name (or None if cannot resolve).
        - imported: (level, module) where:
            * level is None for 'import x' style (absolute import)
            * level == 0 for 'from a.b import c' absolute from
            * level >=1 for relative 'from ..x import y'
        - current_module: dotted module name of the file doing the import, e.g. 'pkg.sub.file'
        Return absolute module dotted name (may be partial if 'from ... import name' where module was None)
        """
        level, module = imported
        if level is None:
            # import x.y -> module is 'x.y'
            return module
        if level == 0:
            return module
        # relative import: level >= 1
        if current_module is None:
            return None
        # remove last N parts from current_module (if current_module is a module file like pkg.sub.file,
        # then its package is all but the last component)
        cur_parts = current_module.split(".")
        # when importing from a module, the relative import counts from that module's package level
        # E.g. in 'pkg.sub.mod', level=1 from .a -> parent = ['pkg','sub']
        # so remove one part per level
        parent_parts = cur_parts[:-1]  # starting parent
        if level - 1 > len(parent_parts):
            # can't go above repo root
            base_parts: List[str] = []
        else:
            base_parts = parent_parts[: len(parent_parts) - (level - 1)]
        if module:
            return ".".join([*base_parts, module]) if base_parts else module
        else:
            return ".".join(base_parts) if base_parts else None

    # -------------------------
    # Public API
    # -------------------------
    def find_dependencies(self, file_path: Path) -> FileDependencies:
        """
        Finds all file dependencies of the specified `file_path` in the repository.
        Returns FileDependencies with file_dependencies = list[Path] or [] if none found.
        """
        f = Path(file_path).resolve()
        if not f.exists():
            raise FileNotFoundError(f"File {f} not found")
        if f.suffix != ".py":
            raise ValueError("Only .py files supported")

        source = f.read_text(encoding="utf-8", errors="ignore")
        current_module = self._path_to_module_name(f)
        # Extract imports (prefer tree-sitter if available and initialized)
        extracted: List[Tuple[Optional[int], Optional[str]]]
        if TREE_SITTER_AVAILABLE and self._parser:
            try:
                extracted = self._extract_imports_with_treesitter(source.encode("utf-8"))
            except Exception:
                extracted = self._extract_imports_with_ast(source)
        else:
            extracted = self._extract_imports_with_ast(source)

        resolved_modules: Set[str] = set()
        for imp in extracted:
            mod = self._resolve_module_name(imp, current_module)
            if mod:
                resolved_modules.add(mod)

        # Map resolved modules to files in repo
        deps: List[Path] = []
        for mod in resolved_modules:
            path = self._module_candidates_to_path(mod)
            if path:
                deps.append(path)
        return FileDependencies(source_file=f, file_dependencies=sorted(set(deps)))

    def find_usages(self, file_path: Path) -> FileUsages:
        """
        Finds all files in the repository that import the given file (by module mapping).
        """
        f = Path(file_path).resolve()
        if not f.exists():
            raise FileNotFoundError(f"File {f} not found")
        target_module = self._path_to_module_name(f)
        if not target_module:
            # not indexed module (maybe outside repo)
            return FileUsages(source_file=f, file_usages=[])

        usages: List[Path] = []
        # scan each file and see if it imports the target module (including imports of parent packages
        # - e.g., if target module is pkg.mod, an importing 'import pkg' is not necessarily a usage;
        #   so we require either exact module import or import of module prefix that resolves to the module file)
        for other in self._files:
            if other == f:
                continue
            source = other.read_text(encoding="utf-8", errors="ignore")
            if TREE_SITTER_AVAILABLE and self._parser:
                try:
                    extracted = self._extract_imports_with_treesitter(source.encode("utf-8"))
                except Exception:
                    extracted = self._extract_imports_with_ast(source)
            else:
                extracted = self._extract_imports_with_ast(source)
            # resolve each import relative to other module
            other_module = self._path_to_module_name(other)
            resolved = set()
            for imp in extracted:
                mod = self._resolve_module_name(imp, other_module)
                if mod:
                    resolved.add(mod)
            # If any resolved module refers exactly to target_module OR maps to the same file path, it's a usage
            # Also accept imports of package that resolve to the same file (e.g., target was pkg/__init__.py)
            used = False
            for mod in resolved:
                mapped = self._module_candidates_to_path(mod)
                if mapped and mapped.resolve() == f:
                    used = True
                    break
            if used:
                usages.append(other)
        return FileUsages(source_file=f, file_usages=sorted(usages))

    # -------------------------
    # Graph builder helper
    # -------------------------
    def build_graph(self) -> nx.DiGraph:
        """
        Builds a directed graph (NetworkX DiGraph) where nodes are file paths and edges
        are from file -> dependency (file imports dependency).
        """
        g = nx.DiGraph()
        for f in self._files:
            g.add_node(str(f))
        for f in self._files:
            try:
                deps = self.find_dependencies(f)
                if deps.file_dependencies:
                    for d in deps.file_dependencies:
                        g.add_edge(str(f), str(d))
            except Exception:
                # ignore parsing errors for now
                continue
        return g


# -------------------------
# Example usage
# -------------------------
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(prog="repo-deps", description="Build python file dependency graph from repository")
    parser.add_argument("repo", help="path to repository root")
    parser.add_argument("--python-lang-so", help="optional path to compiled tree-sitter python language .so/.dylib", default=None)
    parser.add_argument("--show", help="show dependencies for a given file (relative to repo)", default=None)
    args = parser.parse_args()

    repo = Repository(Path(args.repo), python_lang_so=Path(args.python_lang_so) if args.python_lang_so else None)
    if args.show:
        target = (Path(args.repo) / args.show).resolve()
        deps = repo.find_dependencies(target)
        uses = repo.find_usages(target)
        print("Dependencies for:", target)
        for p in deps.file_dependencies or []:
            print("  ->", p)
        print("Usages (files that import it):")
        for p in uses.file_usages or []:
            print("  <-", p)
    else:
        g = repo.build_graph()
        print("Built graph with", g.number_of_nodes(), "nodes and", g.number_of_edges(), "edges")
