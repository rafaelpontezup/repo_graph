# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Repo Graph is a tool that scans Python repositories using Tree-sitter, builds file dependency graphs with NetworkX, and provides both a CLI and programmatic API for querying dependencies.

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

## Architecture

### Core Package (`repo_graph/`)

- **`repo.py`** - `Repository` class: public API with `find_dependencies()` and `find_usages()` methods
- **`repo_graph.py`** - `RepoGraph` class: internal engine that builds the dependency graph using Tree-sitter
- **`main_cli.py`** - CLI entry point

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

**Graph structure:** NetworkX DiGraph where nodes are relative file paths and edges represent import dependencies

## Dependencies

- `networkx` - Graph data structure
- `tree_sitter` - Parser library
- `tree-sitter-python` - Python grammar
