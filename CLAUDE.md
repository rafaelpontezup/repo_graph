# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Repo Graph is a tool that scans Python repositories using Tree-sitter, builds file dependency graphs with NetworkX, and provides both a CLI and programmatic API for querying dependencies and symbol references.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Common Commands

**Analyze dependencies for a file or directory:**
```bash
python -m repo_graph.main_cli /path/to/repo --show-files path/to/file.py
python -m repo_graph.main_cli /path/to/repo --show-files path/to/directory
```

**Run tests:**
```bash
pytest tests/
```

## Architecture

### Core Package (`repo_graph/`)

- **`repo.py`** - `Repository` class: public API with `find_dependencies()` and `find_usages()` methods
- **`repo_graph.py`** - `RepoGraph` class: internal engine that builds the dependency graph using Tree-sitter
- **`symbol_finder.py`** - `SymbolFinder` class: finds symbol references (classes, attributes, functions) using Tree-sitter queries
- **`main_cli.py`** - CLI entry point

### RepoMap Subpackage (`repo_graph/repo_map/`)

- **`simple_repomap.py`** - `SimpleRepoMap` class: generates repository maps with PageRank ranking and symbol navigation
- **`run_simple_repomap.py`** - Example script for repo map generation
- **`run_find_symbol.py`** - Example script for symbol navigation
- **`queries/`** - Tree-sitter SCM query files for 28+ languages

### Documentation

- **`repo_graph/EXPLAIN.md`** - Detailed explanation of Repository and RepoGraph classes
- **`repo_graph/repo_map/EXPLAIN.md`** - Detailed explanation of SimpleRepoMap and PageRank algorithm

## Key Patterns

### Import Extraction (RepoGraph)

Uses Tree-sitter Query API with SCM patterns to capture:
- Simple imports (`import pkg.sub`)
- From imports (`from pkg import symbol`)
- Relative imports (`from . import x`, `from ..pkg import y`)
- Wildcard imports (`from pkg import *`)

### Dependency Resolution

- Resolves module paths relative to repository root
- Handles both package imports (`pkg/__init__.py`) and module imports (`pkg/module.py`)
- Adds dependencies to parent `__init__.py` files in the import path

### Symbol Finding (SymbolFinder)

Uses Tree-sitter queries to find:
- Class definitions and instantiations
- Attribute accesses (`user.email`)
- Function definitions and calls
- Type hints and imports

Qualified name format: `"class:ClassName"`, `"class:ClassName.attribute"`, `"function:func_name"`

### Repository Mapping (SimpleRepoMap)

- **Tree-sitter** for multi-language parsing (28+ languages)
- **PageRank** for file importance ranking
- **TreeContext** for syntax-aware rendering
- **Binary search** for token optimization

## Data Structures

### Core Module

```python
FileDependencies(source_file: Path, file_dependencies: List[Path])
FileUsages(source_file: Path, file_usages: List[Path])
SymbolLocation(file_path: Path, line: int, column: int, end_column: int, context_line: str)
SymbolReference(location: SymbolLocation, reference_type: str, symbol_name: str)
SymbolUsages(symbol_name: str, definition_location: SymbolLocation, references: List[SymbolReference])
```

### RepoMap Module

```python
Tag = namedtuple("Tag", "rel_fname fname line name kind subkind")
FileReport(excluded: Dict, definition_matches: int, reference_matches: int, total_files_considered: int)
SymbolNavigation(symbol: str, kind: str, definitions: List, references: List)
```

## Graph Structure

NetworkX DiGraph where:
- **Nodes** = relative file paths
- **Edges** = import dependencies (A → B means "A imports B")
- `graph.successors(file)` = files that `file` imports
- `graph.predecessors(file)` = files that import `file`

## Dependencies

- `networkx` - Graph data structure
- `tree_sitter` - Parser library
- `tree-sitter-python` - Python grammar
- `grep-ast` - Tree-sitter language support and TreeContext rendering
- `tiktoken` - Token counting for LLM optimization
