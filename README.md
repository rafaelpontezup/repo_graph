# Repo Graph

A Python tool that scans repositories using Tree-sitter to build file dependency graphs with NetworkX.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

### CLI

Analyze dependencies for a file or directory:

```bash
python -m repo_graph.main_cli /path/to/repo --show-files path/to/file.py
python -m repo_graph.main_cli /path/to/repo --show-files path/to/directory
```

#### Testing CLI with sample files

To test it locally during development, you can run:

```bash
python -m repo_graph.main_cli samples/happy-path --show-files . > output/repo-$(date +%Y%m%d%H%M%S).out
```

### Programmatic API

```python
from pathlib import Path
from repo_graph.repo import Repository

repo = Repository(Path("/path/to/repo"))

# Find what a file depends on
deps = repo.find_dependencies(Path("/path/to/repo/module.py"))
print(deps.file_dependencies)

# Find what files import a given file
usages = repo.find_usages(Path("/path/to/repo/module.py"))
print(usages.file_usages)
```

## Notes

- Currently supports Python files only (Java parser is placeholder)
- Resolves relative imports, package imports, and wildcard imports
- Does NOT yet resolve fully-qualified symbols across modules
