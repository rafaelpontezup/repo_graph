# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Repo Graph CLI is a tool that scans Python and Java repositories using Tree-sitter, builds dependency graphs with NetworkX, and provides a CLI (Typer) for querying dependencies and exports.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Common Commands

**Build dependency graph:**
```bash
python -m repo_graph.cli.main build repo /path/to/repo
```

**Query dependencies:**
```bash
python -m repo_graph.cli.main query depends mymodule.Class.method
python -m repo_graph.cli.main query used-by mymodule.Class.method
```

**Alternative standalone scripts (more detailed output):**
```bash
python repo_deps.py /path/to/repo --show-files path/to/file.py
python repo_deps_with_graph.py /path/to/repo --show-files path/to/file.py
```

## Architecture

### Core Components

- **`repo_graph/cli/`** - Typer CLI with `build` and `query` subcommands
- **`repo_graph/parsers/`** - Tree-sitter based parsers for Python (`python.py`) and Java (`java.py`)
- **`repo_graph/graph/store.py`** - GraphStore class wrapping NetworkX DiGraph with pickle serialization

### Standalone Scripts (Root Level)

- **`repo_deps.py`** - Full-featured Repository class using Tree-sitter or AST fallback for import extraction
- **`repo_deps_with_graph.py`** - Enhanced version with RepoGraph class using Tree-sitter queries (SCM patterns) for import extraction; includes detailed debug logging

### Key Patterns

**Import extraction:** Uses Tree-sitter Query API with SCM patterns to capture:
- Simple imports (`import pkg.sub`)
- From imports (`from pkg import symbol`)
- Relative imports (`from . import x`, `from ..pkg import y`)
- Wildcard imports (`from pkg import *`)

**Dependency resolution:**
- Resolves module paths relative to repository root
- Handles both package imports (`pkg/__init__.py`) and module imports (`pkg/module.py`)
- Adds dependencies to parent `__init__.py` files in the import path

**Graph storage:** Dependencies stored as NetworkX DiGraph, serialized to `graph.pkl`

## Dependencies

- `typer` - CLI framework
- `networkx` - Graph data structure
- `tree_sitter` - Parser library
- `tree-sitter-python`, `tree-sitter-java` - Language grammars
