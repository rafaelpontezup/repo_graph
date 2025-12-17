# Repo Graph

A Python tool that scans repositories using Tree-sitter to build file dependency graphs with NetworkX. Supports dependency analysis, symbol reference finding, and repository mapping for LLMs.

## Features

- **Dependency Graph**: Build file dependency graphs from Python imports
- **Symbol Finder**: Find references to classes, attributes, and functions across files
- **Repository Map**: Generate ranked repository maps optimized for LLM context windows (28+ languages)

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

```bash
python -m repo_graph.main_cli samples/happy-path --show-files . > output/repo-$(date +%Y%m%d%H%M%S).out
```

### Programmatic API

#### File Dependencies

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

#### Symbol References

```python
# Find references to a symbol in dependent files
usages = repo.find_usages(Path("/path/to/repo/models.py"))

# Find class references
refs = usages.find_symbol_references("class:User")

# Find attribute references
refs = usages.find_symbol_references("class:User.email")

# Find function call references
refs = usages.find_symbol_references("function:validate")

for ref in refs.references:
    print(f"{ref.location.file_path}:{ref.location.line} [{ref.reference_type}]")
    print(f"  {ref.location.context_line}")
```

#### Repository Map (for LLMs)

```python
from pathlib import Path
from repo_graph.repo_map import SimpleRepoMap

mapper = SimpleRepoMap(root="/path/to/project", max_map_tokens=8192)

# Generate repository map with PageRank ranking
repo_map, report = mapper.get_repo_map(
    paths=[Path("src")],
    chat_fnames={"src/main.py"},        # Files being edited (20x boost)
    mentioned_idents={"UserService"},   # Mentioned symbols (10x boost)
    max_tokens=4096,
)
print(repo_map)

# Find symbol definitions and references (like GitHub Code Navigation)
nav = mapper.find_symbol(
    symbol="User",
    paths=[Path("src")],
    source_file=Path("src/app.py"),
)
if nav.found:
    print(nav.render(include_references=True))
```

## Architecture

```
repo_graph/
├── repo.py           # Repository class: public API
├── repo_graph.py     # RepoGraph: dependency graph engine
├── symbol_finder.py  # SymbolFinder: symbol reference search
├── main_cli.py       # CLI entry point
├── EXPLAIN.md        # Detailed documentation
└── repo_map/
    ├── simple_repomap.py  # SimpleRepoMap: LLM-optimized maps
    ├── queries/           # Tree-sitter SCM queries (28+ languages)
    └── EXPLAIN.md         # Detailed documentation
```

## Supported Languages

The repository map supports 28+ languages via Tree-sitter:

Python, JavaScript, TypeScript, Java, Go, Rust, Ruby, C, C++, C#, PHP, Swift, Kotlin, Scala, Elixir, Lua, R, Dart, Elm, HCL/Terraform, and more.

## How It Works

### Dependency Graph

1. **Parse**: Tree-sitter extracts imports from Python files
2. **Resolve**: Maps imports to file paths (handles relative, absolute, wildcard)
3. **Graph**: NetworkX DiGraph where edges represent import dependencies
4. **Query**: `successors()` = dependencies, `predecessors()` = usages

### Symbol Finder

1. **Parse**: Tree-sitter queries find class/function definitions
2. **Track**: Identifies typed variables and parameter types
3. **Match**: Finds attribute accesses, instantiations, type hints, calls

### Repository Map

1. **Extract**: Tree-sitter extracts definitions and references as tags
2. **Graph**: Builds dependency graph from symbol name matching
3. **Rank**: PageRank identifies important files
4. **Boost**: Chat files (20x) and mentioned identifiers (10x)
5. **Optimize**: Binary search fits maximum content in token limit

## Running Tests

```bash
pytest tests/ -v
```

## Notes

- Dependency graph currently supports Python files only
- Repository map supports 28+ languages via tree-sitter-language-pack
- Symbol finder uses Tree-sitter queries for robust AST-based matching
- See `EXPLAIN.md` files for detailed algorithm documentation
