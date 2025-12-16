# Como as Classes Repository e RepoGraph Funcionam

Este documento explica o funcionamento interno das classes `Repository` e `RepoGraph` em `repo.py` e `repo_graph.py`.

## Visao Geral

> **Motivacao:** Entender dependencias entre arquivos e crucial para refatoracoes, analise de impacto e navegacao em codebases grandes. Se voce muda `models.py`, quais arquivos serao afetados? Se voce quer entender `service.py`, de quais arquivos ele depende?

O sistema constroi um **grafo de dependencias** entre arquivos Python baseado em imports. Usa Tree-sitter para parsing robusto e NetworkX para representacao do grafo.

**Caracteristicas:**
- **Tree-sitter** para parsing de imports (nao usa regex)
- **NetworkX DiGraph** para grafo direcionado de dependencias
- **Resolucao inteligente** de imports relativos e absolutos
- **API simples** com apenas 2 metodos principais

---

## API Publica

> **Motivacao:** Uma API minimalista e mais facil de aprender e menos propensa a erros. Dois metodos cobrem os casos de uso principais: "de quem eu dependo?" e "quem depende de mim?".

```python
from pathlib import Path
from repo_graph.repo import Repository

repo = Repository(Path("/path/to/project"))

# Metodo 1: Encontrar dependencias de um arquivo
deps = repo.find_dependencies(Path("src/service.py"))
print(deps.file_dependencies)  # [Path("src/models.py"), Path("src/utils.py")]

# Metodo 2: Encontrar quem usa um arquivo
usages = repo.find_usages(Path("src/models.py"))
print(usages.file_usages)  # [Path("src/service.py"), Path("src/api.py")]

# Metodo 3: Encontrar referencias a um simbolo especifico
symbol_refs = usages.find_symbol_references("User.email")
for ref in symbol_refs.references:
    print(f"{ref.location.file_path}:{ref.location.line}")
```

**Terminologia:**
- **Dependencias** = arquivos que EU importo (successors no grafo)
- **Usages** = arquivos que ME importam (predecessors no grafo)

---

## Exemplo Completo: Entrada e Saida

> **Motivacao:** Exemplos concretos ajudam a formar um modelo mental correto do sistema.

### Cenario

Projeto com 3 arquivos Python:

```
myproject/
├── main.py
├── utils.py
└── models/
    ├── __init__.py
    └── user.py
```

**main.py:**
```python
from models.user import User
from utils import format_name

def run():
    user = User("Alice")
    print(format_name(user.name))
```

**utils.py:**
```python
def format_name(name):
    return name.upper()
```

**models/user.py:**
```python
class User:
    def __init__(self, name):
        self.name = name
```

**models/__init__.py:**
```python
from .user import User
```

### Uso

```python
from pathlib import Path
from repo_graph.repo import Repository

repo = Repository(Path("myproject"))

# Quais arquivos main.py importa?
deps = repo.find_dependencies(Path("myproject/main.py"))
print(deps.file_dependencies)
# [Path("myproject/models/__init__.py"),
#  Path("myproject/models/user.py"),
#  Path("myproject/utils.py")]

# Quem importa models/user.py?
usages = repo.find_usages(Path("myproject/models/user.py"))
print(usages.file_usages)
# [Path("myproject/main.py"), Path("myproject/models/__init__.py")]
```

### Grafo Gerado

```
main.py ──────────────────> utils.py
    │
    ├──────────────────────> models/__init__.py
    │                              │
    └──────────────────────> models/user.py <───┘
```

---

## Estruturas de Dados

> **Motivacao:** Dataclasses simples facilitam o uso da API e tornam os resultados auto-documentados.

### FileDependencies

```python
@dataclass
class FileDependencies:
    source_file: Path           # Arquivo analisado
    file_dependencies: List[Path]  # Arquivos dos quais ele depende
```

**Exemplo:**
```python
FileDependencies(
    source_file=Path("src/main.py"),
    file_dependencies=[Path("src/models.py"), Path("src/utils.py")]
)
```

### FileUsages

```python
@dataclass
class FileUsages:
    source_file: Path         # Arquivo analisado
    file_usages: List[Path]   # Arquivos que dependem dele

    def find_symbol_references(self, qualified_name: str) -> SymbolUsages:
        """Encontra referencias a um simbolo nos arquivos dependentes."""
```

**Exemplo:**
```python
usages = FileUsages(
    source_file=Path("src/models.py"),
    file_usages=[Path("src/main.py"), Path("src/api.py")]
)

# Buscar referencias ao atributo User.email
refs = usages.find_symbol_references("User.email")
```

---

## Fluxo de Execucao

> **Motivacao:** Entender o pipeline ajuda a debugar problemas e estender funcionalidades.

### Inicializacao do Repository

```
Repository(repository_path)
    │
    ├──> Resolve caminho absoluto
    │
    └──> RepoGraph(root)
            │
            └──> build()
                    │
                    ├──> os.walk() para encontrar .py files
                    │
                    ├──> Para cada arquivo:
                    │       │
                    │       ├──> parser.parse(code)
                    │       │
                    │       ├──> _extract_imports(root_node)
                    │       │
                    │       └──> _add_edge() para cada import
                    │
                    └──> Grafo NetworkX pronto
```

### find_dependencies / find_usages

```
find_dependencies(file_path)          find_usages(file_path)
    │                                     │
    ├──> _to_rel(file_path)               ├──> _to_rel(file_path)
    │                                     │
    ├──> graph.successors(rel)            ├──> graph.predecessors(rel)
    │                                     │
    ├──> _to_abs() para cada              ├──> _to_abs() para cada
    │                                     │
    └──> FileDependencies                 └──> FileUsages
```

---

## Extracao de Imports com Tree-sitter

> **Motivacao:** Regex nao consegue entender codigo de forma confiavel (strings, comentarios, aninhamentos). Tree-sitter faz parsing real da AST.

### Query SCM Usada

```scheme
; Rule 1: Simple import (import pkg.sub)
(import_statement
    name: [
        (dotted_name) @import.module
        (aliased_import
            name: (dotted_name) @import.module)
    ])

; Rule 2: From import (from pkg import symbol)
(import_from_statement
    module_name: [
        (dotted_name) @import.from.module
        (relative_import) @import.from.module
    ]
    name: [
        (dotted_name) @import.from.symbol
        (identifier) @import.from.symbol
        (aliased_import
            name: [
                (dotted_name) @import.from.symbol
                (identifier) @import.from.symbol
            ])
    ])

; Rule 3: Wildcard import (from pkg import *)
(import_from_statement
    module_name: [
        (dotted_name) @import.from.wildcard.module
        (relative_import) @import.from.wildcard.module
    ]
    (wildcard_import))
```

### Tipos de Import Capturados

| Codigo | Captura | Resultado |
|--------|---------|-----------|
| `import pkg` | `@import.module` | `('pkg', None)` |
| `import pkg.sub` | `@import.module` | `('pkg.sub', None)` |
| `from pkg import x` | `@import.from.module`, `@import.from.symbol` | `('pkg', 'x')` |
| `from pkg import x, y` | (idem) | `('pkg', 'x'), ('pkg', 'y')` |
| `from . import x` | `@import.from.module` = `.` | `('.', 'x')` |
| `from ..pkg import x` | `@import.from.module` = `..pkg` | `('..pkg', 'x')` |
| `from pkg import *` | `@import.from.wildcard.module` | `('pkg', None)` |

---

## Resolucao de Dependencias

> **Motivacao:** Python tem regras complexas para resolver imports. O sistema precisa mapear `from pkg import x` para o arquivo correto no filesystem.

### Logica de Resolucao

```python
def _add_edge(self, src, module, symbol):
    # 1. Resolve caminho do modulo
    if module.startswith("."):
        # Import relativo: resolve baseado no diretorio do src
        module_path = resolve_relative(src_dir, module)
    else:
        # Import absoluto: resolve a partir da raiz
        module_path = os.path.join(self.root, *module.split("."))

    # 2. Adiciona dependencias para __init__.py no caminho
    _add_parent_init_deps(src, module_path)

    # 3. Tenta resolver como arquivo .py
    if exists(module_path + ".py"):
        add_edge(src, module_path + ".py")
        return

    # 4. Tenta resolver como pacote (__init__.py)
    if is_dir(module_path) and exists(module_path/__init__.py):
        add_edge(src, module_path/__init__.py)

        # Se tem symbol, tenta resolver como submodulo
        if symbol and exists(module_path/symbol.py):
            add_edge(src, module_path/symbol.py)
```

### Exemplo de Resolucao

```
Codigo: from models.user import User
Arquivo: main.py

1. module = "models.user", symbol = "User"

2. module_path = /project/models/user

3. Adiciona parent inits:
   → /project/models/__init__.py

4. Existe /project/models/user.py?
   → Sim! Adiciona edge: main.py → models/user.py

5. Symbol "User" e uma classe definida em user.py
   → Dependencia ja capturada pelo arquivo
```

### Imports Relativos

```
Codigo: from ..utils import helper
Arquivo: pkg/sub/module.py

1. dots = 2, tail = "utils"

2. base = /project/pkg/sub
   → sobe 1 nivel (dots - 1)
   → base = /project/pkg

3. module_path = /project/pkg/utils

4. Resolve como /project/pkg/utils.py
```

---

## Dependencias de __init__.py

> **Motivacao:** Em Python, `import pkg.sub.module` executa TODOS os `__init__.py` no caminho. O grafo precisa refletir isso.

### Por que adicionar parent inits?

```python
# Quando voce escreve:
from pkg.sub import func

# Python executa:
# 1. pkg/__init__.py
# 2. pkg/sub/__init__.py
# 3. pkg/sub.py (se existir) ou usa o que sub/__init__.py exporta
```

### Codigo Relevante

```python
def _add_parent_init_deps(self, src, tgt_path):
    rel_path = os.path.relpath(tgt_path, self.root)
    path_parts = rel_path.split(os.sep)

    current_path = self.root
    for part in path_parts[:-1]:  # Nao inclui o arquivo final
        current_path = os.path.join(current_path, part)
        init_file = os.path.join(current_path, "__init__.py")

        if os.path.exists(init_file):
            self._add_graph_edge(src, init_rel)
```

### Exemplo

```
Import: from pkg.sub.module import func
Arquivo fonte: main.py

Edges criadas:
  main.py → pkg/__init__.py
  main.py → pkg/sub/__init__.py
  main.py → pkg/sub/module.py
```

---

## Grafo NetworkX

> **Motivacao:** NetworkX e uma biblioteca madura e bem testada para grafos. DiGraph (grafo direcionado) representa naturalmente "A depende de B".

### Estrutura

```python
self.graph = nx.DiGraph()

# Nodes: caminhos relativos dos arquivos
# Edges: dependencias (src → target significa "src importa target")
```

### Direcao das Arestas

```
A importa B  →  Edge: A → B

graph.successors(A) = [B]     # Arquivos que A importa
graph.predecessors(B) = [A]   # Arquivos que importam B
```

### Visualizacao

```
main.py ────────────────────────────> utils.py
    │
    ├─────────────> models/__init__.py
    │                      │
    └─────────────> models/user.py <──┘

Nodes: ["main.py", "utils.py", "models/__init__.py", "models/user.py"]
Edges:
  - main.py → utils.py
  - main.py → models/__init__.py
  - main.py → models/user.py
  - models/__init__.py → models/user.py
```

---

## Arquivos Ignorados

> **Motivacao:** Diretorios como `.venv`, `__pycache__` contem codigo que nao e do projeto. Ignora-los evita ruido e melhora performance.

```python
IGNORED_DIRS = {".venv", "venv", "env", "libs", "__pycache__"}

for dirpath, dirnames, files in os.walk(self.root):
    dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]
```

---

## Conversao de Caminhos

> **Motivacao:** O grafo usa caminhos relativos (para portabilidade), mas a API recebe/retorna Paths absolutos (para conveniencia).

```python
def _to_rel(self, file_path: Path) -> str:
    """Path absoluto → caminho relativo (str)"""
    return str(file_path.resolve().relative_to(self.repository_path))

def _to_abs(self, rel_path: str) -> Path:
    """Caminho relativo (str) → Path absoluto"""
    return (self.repository_path / rel_path).resolve()
```

### Exemplo

```python
repo = Repository(Path("/project"))

# Entrada do usuario
file = Path("/project/src/main.py")

# Internamente
rel = "src/main.py"  # Usado no grafo

# Saida para o usuario
abs_path = Path("/project/src/main.py")  # Retornado na API
```

---

## Resumo do Algoritmo

> **Motivacao:** Um resumo em etapas serve como referencia rapida.

```
1. INIT
   └─ Repository(path)
       └─ RepoGraph(root).build()

2. SCAN
   └─ os.walk() encontra todos os .py (exceto ignorados)

3. PARSE (para cada arquivo)
   └─ Tree-sitter extrai imports da AST
   └─ Query SCM captura module + symbol

4. RESOLVE (para cada import)
   └─ Converte "from pkg.sub import x" → caminho do arquivo
   └─ Adiciona __init__.py parents ao grafo
   └─ Adiciona arquivo do modulo ao grafo

5. QUERY
   └─ find_dependencies(file) → graph.successors()
   └─ find_usages(file) → graph.predecessors()
```

---

## Limitacoes

O sistema **NAO** faz:
- Analise de imports dinamicos (`__import__()`, `importlib`)
- Tracking de re-exports complexos
- Resolucao de `sys.path` customizado
- Analise de codigo em strings (`exec()`)

O sistema **FAZ**:
- Parsing robusto com Tree-sitter
- Resolucao de imports relativos e absolutos
- Tracking de dependencias de `__init__.py`
- API simples para queries de dependencias
