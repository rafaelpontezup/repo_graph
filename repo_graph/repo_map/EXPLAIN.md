# Como a Classe SimpleRepoMap Funciona

Este documento explica o funcionamento interno da classe `SimpleRepoMap` em `simple_repomap.py`.

## Visao Geral

> **Motivacao:** LLMs precisam entender codebases para ajudar desenvolvedores, mas tem limite de tokens. Nao da para enviar todo o codigo. Precisamos de um "resumo inteligente" que mostre as partes mais relevantes.

A `SimpleRepoMap` gera "mapas" de repositorios que identificam e ranqueiam definicoes de simbolos (funcoes, classes) usando PageRank. O objetivo e ajudar LLMs a entenderem codebases complexos de forma eficiente.

**Caracteristicas:**
- **Tree-sitter** para parsing robusto (28+ linguagens)
- **PageRank** para ranking de arquivos por importancia
- **TreeContext** para renderizacao com contexto sintatico
- **Busca binaria** para otimizacao de tokens

**Diferenca da versao original:** API simplificada com apenas 1 metodo publico.

---

## API Publica

> **Motivacao:** APIs complexas com muitos metodos publicos sao dificeis de usar e manter. Poucos pontos de entrada com parametros opcionais sao mais intuitivos e menos propensos a erros.

```python
from pathlib import Path
from simple_repomap import SimpleRepoMap

mapper = SimpleRepoMap(root="/path/to/project", max_map_tokens=8192)

# Metodo 1: Gerar mapa do repositorio
repo_map, report = mapper.get_repo_map(
    paths=[Path("src"), Path("main.py")],  # List[Path] - arquivos e/ou diretorios
    chat_fnames={"src/app.py"},            # Arquivos de alta prioridade (boost 20x)
    mentioned_idents={"UserService"},      # Identificadores mencionados (boost 10x)
    excludes={"tests"},                    # Exclusoes adicionais
    max_tokens=4096,                       # Limite de tokens
)

# Metodo 2: Encontrar simbolo (similar ao GitHub Code Navigation)
nav = mapper.find_symbol(
    symbol="User",                         # Nome do simbolo a buscar
    paths=[Path("src")],                   # Onde buscar
    source_file=Path("src/app.py"),        # Arquivo de origem (boost 20x)
)
if nav.found:
    print(nav.render())                    # Renderiza com contexto sintatico
    print(nav.render(include_references=True))  # Inclui referencias
```

**Por que `List[Path]` em vez de strings?**
- Tipagem forte previne erros
- Aceita arquivos E diretorios na mesma chamada
- Path e mais robusto para manipulacao de caminhos

---

## Exemplo Completo: Entrada e Saida

> **Motivacao:** Exemplos concretos sao mais faceis de entender que descricoes abstratas. Ver input/output reais ajuda a formar um modelo mental correto.

### Cenario

Projeto com 3 arquivos Python:

```
myproject/
├── main.py
├── utils.py
└── models.py
```

**main.py:**
```python
from utils import format_name
from models import User

def run():
    user = User("Alice")
    print(format_name(user.name))
```

**utils.py:**
```python
def format_name(name):
    return name.upper()

def validate_email(email):
    return "@" in email
```

**models.py:**
```python
class User:
    def __init__(self, name):
        self.name = name

class Product:
    def __init__(self, title):
        self.title = title
```

### Uso

```python
from pathlib import Path
from simple_repomap import SimpleRepoMap

mapper = SimpleRepoMap(root="myproject", max_map_tokens=2048)
repo_map, report = mapper.get_repo_map(
    paths=[Path("myproject")],
    chat_fnames={"main.py"},
)
print(repo_map)
```

### Saida

```
main.py:
(Rank value: 10.8220)

│from utils import format_name
│from models import User
│
│def run():
│    user = User("Alice")
│    print(format_name(user.name))

utils.py:
(Rank value: 0.2297)

│def format_name(name):
│    return name.upper()
│
│def validate_email(email):
⋮

models.py:
(Rank value: 0.2292)

│class User:
│    def __init__(self, name):
│        self.name = name
⋮
```

**Simbolos no output:**
- `│` linhas de codigo (contexto e definicoes)
- `⋮` codigo omitido

### Por que `main.py` tem o maior rank?

1. **Personalization:** Como `chat_file`, recebe peso inicial 100x no PageRank
2. **Boost final:** Tags de `chat_files` recebem multiplicador 20x
3. **Resultado:** 0.5411 (PageRank) × 20 (boost) = 10.822

---

## Como Funciona a Deteccao de Referencias

> **Motivacao:** Para rankear arquivos por importancia, precisamos saber quem depende de quem. Se `main.py` usa `User`, entao `models.py` e importante para entender `main.py`. Mas como descobrir essas dependencias sem um compilador completo?

### A Pergunta

> Se tenho `from models import User` em main.py, como o sistema sabe que `User` esta definido em models.py?

### A Resposta

**O sistema NAO analisa imports.** Ele usa **matching por nome de simbolo**.

### Por que nao analisar imports?

- Imports sao especificos de cada linguagem (Python, JS, Go tem sintaxes diferentes)
- Resolver imports corretamente requer entender o sistema de modulos inteiro
- Seria necessario um compilador completo para cada linguagem

### A solucao: matching por nome

Se um simbolo `User` e DEFINIDO em algum arquivo e REFERENCIADO em outro, eles estao conectados. Simples e funciona para qualquer linguagem.

### Fluxo de Deteccao

```
┌─────────────────────────────────────────────────────────────────┐
│ ETAPA 1: Tree-sitter extrai TODAS as tags de TODOS os arquivos │
└─────────────────────────────────────────────────────────────────┘

  models.py:
    Tag(name="User", kind="def", line=1)       ← DEFINICAO

  main.py:
    Tag(name="User", kind="ref", line=5)       ← REFERENCIA (chamada)
    Tag(name="format_name", kind="ref", line=6)


┌─────────────────────────────────────────────────────────────────┐
│ ETAPA 2: Agrupa por nome do simbolo                             │
└─────────────────────────────────────────────────────────────────┘

  defines = {
      "User": {"models.py"},
      "format_name": {"utils.py"},
  }

  references = {
      "User": {"main.py"},
      "format_name": {"main.py"},
  }


┌─────────────────────────────────────────────────────────────────┐
│ ETAPA 3: Conecta no grafo por matching de nomes                 │
└─────────────────────────────────────────────────────────────────┘

  Para cada nome referenciado:
    - Quem DEFINE "User"? → models.py
    - Quem REFERENCIA "User"? → main.py
    - RESULTADO: main.py → models.py (aresta de dependencia)
```

### Codigo Relevante

```python
# Em _get_ranked_tags():

# 1. Coleta tags
for rel_fname, code in files.items():
    tags = self.get_tags(abs_fname, rel_fname, code)
    for tag in tags:
        if tag.kind == "def":
            defines[tag.name].add(rel_fname)
        elif tag.kind == "ref":
            references[tag.name].add(rel_fname)

# 2. Conecta no grafo
for name, ref_fnames in references.items():
    def_fnames = defines.get(name, set())  # ← Busca por NOME
    for ref_fname in ref_fnames:
        for def_fname in def_fnames:
            if ref_fname != def_fname:
                G.add_edge(ref_fname, def_fname)  # ← Conecta
```

### Visualizacao do Grafo

```
         "format_name"          "User"
main.py ──────────────> utils.py
    │
    └───────────────────────────────> models.py

NetworkX MultiDiGraph:
  Nodes: ["main.py", "utils.py", "models.py"]
  Edges:
    - (main.py → utils.py, name="format_name")
    - (main.py → models.py, name="User")
```

### Limitacoes

O sistema **NAO** faz:
- Analise de imports (`from X import Y`)
- Resolucao de namespaces (`models.User` vs `auth.User`)
- Type inference
- Tracking de reatribuicoes/shadows

O sistema **FAZ**:
- Matching por nome de simbolo (string matching)
- Encontrar definicoes/referencias via Tree-sitter AST
- Construir grafo de dependencias implicito
- PageRank para ranking automatico

### Por que Funciona na Pratica?

Em projetos reais, nomes de classes/funcoes tendem a ser unicos o suficiente. Se dois arquivos definem `User`, ambos serao conectados - mas o PageRank suaviza esses falsos positivos distribuindo o peso.

---

## Fluxo de Execucao

> **Motivacao:** Entender o pipeline ajuda a debugar problemas e estender funcionalidades. Cada etapa transforma dados para a proxima, permitindo isolamento e testes.

### get_repo_map (mapa do repositorio)

```
get_repo_map(paths)
    │
    ├──> _resolve_paths()      # Descobre arquivos em dirs
    │
    ├──> _read_files()         # Le conteudo dos arquivos
    │
    ├──> _get_ranked_tags()    # Extrai tags + PageRank
    │       │
    │       ├──> get_tags()    # Tree-sitter parsing (extrai subkind)
    │       │
    │       ├──> Construir grafo NetworkX
    │       │
    │       └──> Executar PageRank
    │
    └──> _to_tree_truncated_by_tokens()  # Formata output
            │
            ├──> Busca binaria para otimizar tokens
            │
            └──> _to_tree() + render_tree()
```

### find_symbol (navegacao de simbolo)

```
find_symbol(symbol, paths, source_file)
    │
    ├──> _resolve_paths()      # Descobre arquivos
    │
    ├──> _read_files()         # Le conteudo
    │
    ├──> _get_ranked_tags(kinds={"def", "ref"})  # Ambos os tipos
    │
    ├──> Filtrar por nome do simbolo
    │
    └──> Retornar SymbolNavigation
            └──> render() usa TreeContext sob demanda
```

---

## Estruturas de Dados

> **Motivacao:** Estruturas simples e imutaveis facilitam debugging e evitam efeitos colaterais. Uma Tag e a unidade atomica: "este simbolo existe neste arquivo, nesta linha".

### Tag (namedtuple)

```python
Tag = namedtuple("Tag", "rel_fname fname line name kind subkind")
```

| Campo | Descricao | Exemplo |
|-------|-----------|---------|
| `rel_fname` | Caminho relativo | `"src/models.py"` |
| `fname` | Caminho absoluto | `"/project/src/models.py"` |
| `line` | Numero da linha | `42` |
| `name` | Nome do simbolo | `"User"` |
| `kind` | Tipo | `"def"` ou `"ref"` |
| `subkind` | Subtipo especifico | `"class"`, `"function"`, `"call"` |

**Subkind** e extraido do nome da captura Tree-sitter. Por exemplo:
- `name.definition.class` → subkind = `"class"`
- `name.definition.function` → subkind = `"function"`
- `name.reference.call` → subkind = `"call"`

### FileReport (dataclass)

```python
@dataclass
class FileReport:
    excluded: Dict[str, str]        # Arquivo -> motivo da exclusao
    definition_matches: int         # Total de definicoes
    reference_matches: int          # Total de referencias
    total_files_considered: int     # Total de arquivos
```

**Por que retornar um report?** Transparencia. O usuario sabe quantos arquivos foram processados e quantas definicoes/referencias foram encontradas.

### SymbolLocation (dataclass)

```python
@dataclass
class SymbolLocation:
    file: str       # Caminho relativo do arquivo
    line: int       # Numero da linha
    snippet: str    # Trecho de codigo (opcional)
```

### SymbolNavigation (dataclass)

```python
@dataclass
class SymbolNavigation:
    symbol: str                         # Nome do simbolo buscado
    kind: str                           # Tipo: "class", "function", "method", "unknown"
    definitions: List[SymbolLocation]   # Onde o simbolo e definido
    references: List[SymbolLocation]    # Onde o simbolo e referenciado
    source_file: Optional[str]          # Arquivo de origem da busca
    _files: Dict[str, str]              # Cache interno dos arquivos (para render)
```

**Metodos:**
- `found` (property): Retorna `True` se encontrou definicao ou referencia
- `render(include_references=False)`: Renderiza com contexto sintatico usando TreeContext

---

## Tree-sitter e Queries SCM

> **Motivacao:** Regex nao consegue entender codigo de forma confiavel (aninhamentos, strings, comentarios). Tree-sitter faz parsing real da AST, garantindo que so capturamos definicoes e referencias verdadeiras.

### Como Tags sao Extraidas

```python
def get_tags(self, fname, rel_fname, code):
    # 1. Detecta linguagem pela extensao
    lang = filename_to_lang(fname)  # .py → "python"

    # 2. Carrega parser e queries SCM
    language = get_language(lang)
    parser = get_parser(lang)
    scm_path = get_scm_path(lang)  # queries/.../python-tags.scm

    # 3. Faz parsing do codigo
    tree = parser.parse(bytes(code, "utf-8"))
    query = Query(language, scm_path.read_text())
    captures = cursor.captures(tree.root_node)

    # 4. Processa capturas
    for capture_name, nodes in captures.items():
        if "name.definition" in capture_name:
            kind = "def"
        elif "name.reference" in capture_name:
            kind = "ref"
        # Cria Tag(...)
```

### Exemplo de Query SCM (Python)

```scheme
; DEFINICOES - capturam onde simbolos sao criados
(class_definition
  name: (identifier) @name.definition.class)

(function_definition
  name: (identifier) @name.definition.function)

; REFERENCIAS - capturam onde simbolos sao usados
(call
  function: [
      (identifier) @name.reference.call
      (attribute
        attribute: (identifier) @name.reference.call)
  ])
```

**O que cada query captura:**

| Codigo | Query Match | Tag Gerada |
|--------|-------------|------------|
| `class User:` | `@name.definition.class` | `Tag(name="User", kind="def", subkind="class")` |
| `def run():` | `@name.definition.function` | `Tag(name="run", kind="def", subkind="function")` |
| `user = User()` | `@name.reference.call` | `Tag(name="User", kind="ref", subkind="call")` |
| `obj.method()` | `@name.reference.call` | `Tag(name="method", kind="ref", subkind="call")` |

**Extracao do subkind:**
```python
# Formato do capture_name: "name.definition.class" ou "name.reference.call"
parts = capture_name.split(".")
subkind = parts[-1] if len(parts) >= 3 else "unknown"
# "name.definition.class" → ["name", "definition", "class"] → subkind = "class"
```

---

## PageRank e Sistema de Boosts

> **Motivacao:** Em um repositorio grande, nem todos os arquivos sao igualmente importantes. PageRank (mesmo algoritmo do Google) identifica arquivos "centrais" - aqueles muito referenciados. Boosts permitem personalizar para o contexto atual.

### PageRank

```python
# Personalizacao: chat_files recebem peso inicial 100x
personalization = {}
for fname in chat_fnames:
    personalization[fname] = 100.0

# Executa PageRank
ranks = nx.pagerank(G, personalization=personalization, alpha=0.85)
```

**Parametros:**
- `alpha=0.85`: 85% do rank vem de seguir links no grafo, 15% de "teleportar" para nos personalizados
- `personalization`: Distribuicao inicial de probabilidade (boost para chat_files)

**Intuicao:** PageRank simula um "navegador aleatorio" que segue links. Arquivos que recebem muitos links (sao muito referenciados) tem maior probabilidade de serem visitados = maior rank.

### Sistema de Boosts

```python
for tag in tags:
    if tag.kind == "def":
        boost = 1.0

        # Identificador mencionado na conversa
        if tag.name in mentioned_idents:
            boost *= 10.0

        # Arquivo sendo editado
        if tag.rel_fname in chat_fnames:
            boost *= 20.0

        final_rank = file_rank * boost
```

| Tipo | Multiplicador | Quando Usar |
|------|---------------|-------------|
| Chat file | 20x | Arquivo que o usuario esta editando |
| Mentioned ident | 10x | Simbolo mencionado na conversa |
| Personalization | 100x | Peso inicial no PageRank |

**Por que boosts multiplicativos?** Permitem combinar: um arquivo sendo editado (20x) que contem um simbolo mencionado (10x) recebe 200x de boost total.

---

## Busca Binaria por Tokens

> **Motivacao:** LLMs tem limite de tokens (ex: 8192). Precisamos maximizar informacao util dentro desse limite. Testar todas as combinacoes seria O(n). Busca binaria encontra o maximo em O(log n).

### Problema

Dado um limite de tokens, qual o numero maximo de tags que podemos incluir no output?

### Solucao

```python
def _to_tree_truncated_by_tokens(self, ranked_tags, files, max_tokens):
    left, right = 1, len(ranked_tags)
    best_tree = ""

    while left <= right:
        mid = (left + right) // 2
        tree_output = self._to_tree(ranked_tags[:mid], files)
        tokens = self._token_count(tree_output)

        if tokens <= max_tokens:
            best_tree = tree_output
            left = mid + 1   # Cabe! Tentar mais tags
        else:
            right = mid - 1  # Nao cabe! Reduzir tags

    return best_tree
```

**Exemplo:**
- 100 tags disponiveis, limite 500 tokens
- Iteracao 1: mid=50, tokens=800 → nao cabe, right=49
- Iteracao 2: mid=25, tokens=350 → cabe, left=26
- Iteracao 3: mid=37, tokens=520 → nao cabe, right=36
- ...
- Resultado: 32 tags, 480 tokens (maximo que cabe)

**Complexidade:** O(log n) em vez de O(n) - com 1000 tags, ~10 iteracoes vs 1000.

---

## Navegacao de Simbolos (find_symbol)

> **Motivacao:** Desenvolvedores frequentemente precisam saber "onde este simbolo e definido?" e "onde ele e usado?". Similar ao GitHub Code Navigation, o metodo `find_symbol` responde essas perguntas.

### Uso

```python
mapper = SimpleRepoMap(root="/path/to/project")
nav = mapper.find_symbol(
    symbol="User",
    paths=[Path("src")],
    source_file=Path("src/services/user_service.py"),  # Opcional: boost 20x
)

if nav.found:
    print(f"Simbolo: {nav.symbol} ({nav.kind})")
    print(f"Definicoes: {len(nav.definitions)}")
    print(f"Referencias: {len(nav.references)}")

    # Renderizar com contexto sintatico
    print(nav.render())  # Apenas definicoes
    print(nav.render(include_references=True))  # Definicoes + referencias
```

### Fluxo de Execucao

```
find_symbol("User", [Path("src")], source_file=Path("app.py"))
    │
    ├──> _resolve_paths()      # Descobre arquivos
    │
    ├──> _read_files()         # Le conteudo
    │
    ├──> _get_ranked_tags()    # Extrai tags com boost
    │       │
    │       ├──> kinds={"def", "ref"}  # Busca AMBOS os tipos
    │       │
    │       ├──> chat_fnames={"app.py"}  # Boost 20x para source_file
    │       │
    │       └──> mentioned_idents={"User"}  # Boost 10x para o simbolo
    │
    ├──> Filtrar tags pelo nome do simbolo
    │
    └──> Retornar SymbolNavigation
            │
            ├──> definitions: [SymbolLocation, ...]
            ├──> references: [SymbolLocation, ...]
            └──> kind: subkind da primeira definicao (ex: "class")
```

### Exemplo de Output (render)

```
Symbol     : User (class)
Source file: src/services/user_service.py
Definitions: 1
References : 3

ℹ️ Definitions (1)
----------------------------------------
src/models/user.py:
class User:
    def __init__(self, name):
        self.name = name

ℹ️ References (3)
----------------------------------------
src/services/user_service.py:
from models.user import User

def get_user():
    return User("Alice")

src/main.py:
user = User("Bob")
```

### Diferenca do get_repo_map

| Aspecto | `get_repo_map` | `find_symbol` |
|---------|----------------|---------------|
| Proposito | Visao geral do repositorio | Navegacao especifica de simbolo |
| Retorno | String formatada | `SymbolNavigation` estruturado |
| Foco | Todas as definicoes rankeadas | Um simbolo especifico |
| Tipos de tags | Apenas `def` | `def` E `ref` |
| Renderizacao | TreeContext automatico | Metodo `render()` sob demanda |

---

## Exclusoes Padrao

> **Motivacao:** Diretorios como `node_modules`, `.git`, `__pycache__` contem codigo que nao e do projeto. Incluir gera ruido e desperica tokens. Excluir por padrao evita que o usuario tenha que lembrar toda vez.

```python
DEFAULT_EXCLUDES = {
    # Controle de versao - historico, nao codigo atual
    '.git', '.svn', '.hg',

    # Dependencias - codigo de terceiros
    'node_modules', 'vendor', '.bundle',

    # Python - bytecode e cache
    '__pycache__', '.pytest_cache', '.venv', 'venv',

    # Build - artefatos gerados
    'build', 'dist', 'target', 'out',

    # IDE - configuracoes locais
    '.idea', '.vscode',

    # Cache e cobertura
    '.cache', 'coverage', '.nyc_output',
}
```

**Customizavel:** O parametro `excludes` permite adicionar mais exclusoes:

```python
mapper.get_repo_map(
    paths=[Path(".")],
    excludes={"tests", "docs", "examples"}  # Adiciona aos padroes
)
```

---

## Linguagens Suportadas

> **Motivacao:** Desenvolvedores usam muitas linguagens. Tree-sitter tem parsers para 28+ linguagens, permitindo que o RepoMap funcione em projetos poliglotas sem configuracao adicional.

| Linguagem | Extensoes |
|-----------|-----------|
| Python | `.py` |
| JavaScript | `.js`, `.jsx` |
| TypeScript | `.ts`, `.tsx` |
| Java | `.java` |
| Go | `.go` |
| Rust | `.rs` |
| Ruby | `.rb` |
| C | `.c`, `.h` |
| C++ | `.cpp`, `.hpp`, `.cc` |
| C# | `.cs` |
| PHP | `.php` |
| Swift | `.swift` |
| Kotlin | `.kt` |
| Scala | `.scala` |
| Elixir | `.ex`, `.exs` |
| Lua | `.lua` |
| R | `.r`, `.R` |
| Dart | `.dart` |
| Elm | `.elm` |
| HCL/Terraform | `.tf`, `.hcl` |

**Adicionar linguagem:** Basta ter um arquivo de queries SCM em `queries/tree-sitter-language-pack/` e adicionar o mapeamento em `EXTENSION_TO_LANG` e `SCM_FILES`.

---

## Resumo do Algoritmo

> **Motivacao:** Um resumo em etapas ajuda a formar o modelo mental completo e serve como referencia rapida.

### get_repo_map (mapa do repositorio)

```
1. INPUT
   └─ Lista de paths (arquivos/diretorios)

2. DISCOVER
   └─ Encontra arquivos com extensoes suportadas
   └─ Aplica exclusoes (node_modules, .git, etc)

3. READ
   └─ Le conteudo dos arquivos (UTF-8, fallback latin-1)

4. PARSE
   └─ Tree-sitter extrai tags (def/ref + subkind) de cada arquivo
   └─ Agrupa por nome: defines["User"] = {"models.py"}

5. GRAPH
   └─ Constroi grafo: ref_file → def_file
   └─ main.py → models.py (via "User")

6. RANK
   └─ PageRank com personalizacao (chat_files 100x)
   └─ Calcula importancia de cada arquivo

7. BOOST
   └─ chat_files: 20x
   └─ mentioned_idents: 10x

8. OPTIMIZE
   └─ Busca binaria para caber no limite de tokens
   └─ Maximiza tags incluidas

9. OUTPUT
   └─ TreeContext formata com contexto sintatico
   └─ Retorna (mapa_string, FileReport)
```

**Resultado:** Um "mapa" do repositorio que destaca as partes mais relevantes para o contexto atual, otimizado para caber na janela de contexto de um LLM.

### find_symbol (navegacao de simbolo)

```
1. INPUT
   └─ Nome do simbolo + paths + source_file (opcional)

2. DISCOVER + READ
   └─ Mesmas etapas do get_repo_map

3. PARSE
   └─ Extrai tags com kinds={"def", "ref"}
   └─ Captura subkind para identificar tipo do simbolo

4. RANK
   └─ source_file recebe boost 20x (via chat_fnames)
   └─ Simbolo buscado recebe boost 10x (via mentioned_idents)

5. FILTER
   └─ Filtra apenas tags com nome == simbolo buscado
   └─ Separa definicoes e referencias

6. OUTPUT
   └─ SymbolNavigation com listas de SymbolLocation
   └─ kind = subkind da primeira definicao
   └─ render() disponivel para formatacao com TreeContext
```

**Resultado:** Navegacao similar ao GitHub Code Navigation - mostra onde um simbolo e definido e onde e usado.
