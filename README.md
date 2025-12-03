# Repo Graph CLI

This project scans repositories (Python + Java) using Tree-sitter and builds a dependency graph (NetworkX).
It includes a Typer CLI to query dependencies and export visualizations.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Build Tree-sitter language bundle

This project expects the `build/my-languages.so` file produced by `tree_sitter.Language.build_library`.
A helper script `build_languages.sh` is provided; it will clone the grammars into `vendor/` and build the bundle.

```bash
chmod +x build_languages.sh
./build_languages.sh
```

## Usage

Build graph:
```bash
python -m repo_graph.cli.main build repo /path/to/repo
```

Query:
```bash
python -m repo_graph.cli.main query depends mymodule.Class.method
python -m repo_graph.cli.main query used-by mymodule.Class.method
```

Export:
```bash
python -m repo_graph.cli.main build repo /path/to/repo
python -m repo_graph.cli.main query export-html out.html
```

## Notes

- Parsers provide a strong starting point but do NOT yet resolve fully-qualified symbols across multiple modules. For best results, run on a codebase with conventional imports.
- If you want, I can further implement precise symbol resolution (cross-file) and richer metadata.
