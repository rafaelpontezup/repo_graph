"""
Versão simplificada da classe RepoMap com Tree-sitter.

Características:
- Tree-sitter para parsing robusto (28+ linguagens)
- TreeContext para renderização com contexto sintático
- Leitura de arquivos reais do disco
- Busca binária para otimização de tokens

Para entender o algoritmo completo, consulte EXPLAIN.md
"""

from collections import defaultdict, namedtuple
from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional
import os

import networkx as nx

# Tree-sitter imports
from grep_ast import filename_to_lang, TreeContext
from grep_ast.tsl import get_language, get_parser
from tree_sitter import Query, QueryCursor

# Token counting
import tiktoken

# Estruturas de dados fundamentais
Tag = namedtuple("Tag", "rel_fname fname line name kind subkind")


@dataclass
class FileReport:
    """Relatório de arquivos processados."""
    excluded: Dict[str, str]
    definition_matches: int
    reference_matches: int
    total_files_considered: int


@dataclass
class SymbolLocation:
    """Localização de um símbolo no código."""
    file: str
    line: int
    snippet: str = ""


@dataclass
class SymbolNavigation:
    """
    Resultado de navegação para um símbolo.

    Similar ao GitHub Code Navigation - contém as definições
    e todas as referências de um símbolo.
    """
    symbol: str
    kind: str  # "class", "function", "method", "unknown"
    definitions: List['SymbolLocation']
    references: List['SymbolLocation']
    source_file: Optional[str] = None
    _files: Dict[str, str] = field(default_factory=dict, repr=False)

    @property
    def found(self) -> bool:
        """Retorna True se o símbolo foi encontrado (definição ou referência)."""
        return len(self.definitions) > 0 or len(self.references) > 0

    def render(
        self,
        include_references: bool = False,
        show_header: bool = True,
    ) -> str:
        """
        Renderiza o símbolo com contexto sintático usando TreeContext.

        Args:
            include_references: Se True, inclui também as referências
            show_header: Se True (default), exibe cabeçalho com metadados

        Returns:
            String formatada com contexto sintático

        Example:
            >>> nav = mapper.find_symbol("User", [Path("src")])
            >>> if nav.found:
            ...     print(nav.render())
            ...     print(nav.render(include_references=True))
            ...     print(nav.render(show_header=False))
        """
        if not self.found:
            return f"Symbol '{self.symbol}' not found."

        output_parts = []

        # Header com informação do símbolo
        if show_header:
            output_parts.append("ℹ️ Summary")
            output_parts.append("=" * 40)
            output_parts.append("")
            output_parts.append(f"Symbol      : {self.symbol} ({self.kind})")
            if self.source_file:
                output_parts.append(f"Source file : {self.source_file}")
            output_parts.append(f"Definitions : {len(self.definitions)}")
            if include_references:
                output_parts.append(f"References  : {len(self.references)}")
            output_parts.append("")

        # Agrupar definições por arquivo
        defs_by_file: Dict[str, List[int]] = defaultdict(list)
        for defn in self.definitions:
            defs_by_file[defn.file].append(defn.line)

        # Header de definições com contagem de arquivos
        file_word = "file" if len(defs_by_file) == 1 else "files"
        output_parts.append(f"ℹ️ Definitions ({len(self.definitions)} total, {len(defs_by_file)} {file_word})")
        output_parts.append("-" * 40)

        # Renderizar definições
        for def_file, lines in defs_by_file.items():
            if def_file in self._files:
                code = self._files[def_file]
                tc = TreeContext(
                    def_file,
                    code,
                    color=False,
                    loi_pad=8,
                    margin=0,
                    parent_context=True,
                    child_context=False,
                    last_line=False,
                    show_top_of_file_parent_scope=False,
                )
                tc.add_lines_of_interest([line - 1 for line in lines])
                tc.add_context()
                rendered = tc.format()
                if rendered:
                    output_parts.append(f"{def_file}:")
                    output_parts.append(rendered)

        # Renderizar referências (se solicitado)
        if include_references and self.references:
            # Agrupar referências por arquivo
            refs_by_file: Dict[str, List[int]] = defaultdict(list)
            for ref in self.references:
                refs_by_file[ref.file].append(ref.line)

            # Header de referências com contagem de arquivos
            ref_file_word = "file" if len(refs_by_file) == 1 else "files"
            output_parts.append(f"ℹ️ References ({len(self.references)} total, {len(refs_by_file)} {ref_file_word})")
            output_parts.append("-" * 40)

            for ref_file, lines in refs_by_file.items():
                if ref_file in self._files:
                    code = self._files[ref_file]
                    tc = TreeContext(
                        ref_file,
                        code,
                        color=False,
                        loi_pad=4,
                        margin=0,
                        parent_context=False,
                        child_context=False,
                        last_line=False,
                        show_top_of_file_parent_scope=False,
                    )
                    tc.add_lines_of_interest([line - 1 for line in lines])
                    tc.add_context()
                    rendered = tc.format()
                    if rendered:
                        output_parts.append(f"\n{ref_file}:")
                        output_parts.append(rendered)

        return "\n".join(output_parts)


@dataclass
class MultiSymbolNavigation:
    """
    Navegação agregada para múltiplos símbolos.

    Otimiza a renderização agrupando por arquivo para evitar redundância.
    Cada arquivo é renderizado uma única vez com todas as linhas de interesse.
    """
    symbols: Dict[str, SymbolNavigation]
    _files: Dict[str, str] = field(default_factory=dict, repr=False)
    source_file: Optional[str] = None

    @property
    def found_symbols(self) -> List[str]:
        """Retorna lista de símbolos que foram encontrados."""
        return [s for s, nav in self.symbols.items() if nav.found]

    @property
    def not_found_symbols(self) -> List[str]:
        """Retorna lista de símbolos que NÃO foram encontrados."""
        return [s for s, nav in self.symbols.items() if not nav.found]

    def get(self, symbol: str) -> Optional[SymbolNavigation]:
        """Acesso individual a um símbolo."""
        return self.symbols.get(symbol)

    def __getitem__(self, symbol: str) -> SymbolNavigation:
        """Permite acesso via nav['Symbol']."""
        return self.symbols[symbol]

    def __contains__(self, symbol: str) -> bool:
        """Permite 'Symbol' in nav."""
        return symbol in self.symbols

    def __len__(self) -> int:
        """Retorna número de símbolos."""
        return len(self.symbols)

    def render(
        self,
        include_references: bool = False,
        show_header: bool = True,
    ) -> str:
        """
        Renderiza TODOS os símbolos de forma agregada.

        Agrupa por arquivo para evitar redundância:
        - Cada arquivo aparece uma única vez
        - TreeContext compartilha contexto entre símbolos
        - Output ~50% menor que renders separados

        Args:
            include_references: Se True, inclui também as referências
            show_header: Se True (default), exibe cabeçalho com metadados

        Returns:
            String formatada com contexto sintático agregado
        """
        found = self.found_symbols
        not_found = self.not_found_symbols

        if not found:
            symbols_str = ", ".join(self.symbols.keys())
            return f"No symbols found: {symbols_str}"

        output_parts = []

        # Header com todos os símbolos
        if show_header:
            total = len(self.symbols)
            output_parts.append("ℹ️ Summary")
            output_parts.append("=" * 40)
            output_parts.append("")
            if self.source_file:
                output_parts.append(f"Source file : {self.source_file}")

            # Lista de símbolos encontrados
            output_parts.append(f"Symbols found ({len(found)}/{total}):")
            for s in found:
                nav = self.symbols[s]
                output_parts.append(f"  • {s} ({nav.kind})")

            # Lista de símbolos não encontrados
            if not_found:
                output_parts.append(f"Symbols not found ({len(not_found)}/{total}):")
                for s in not_found:
                    output_parts.append(f"  • {s}")

            output_parts.append("")

        # Contar totais
        total_defs = sum(len(self.symbols[s].definitions) for s in found)
        total_refs = sum(len(self.symbols[s].references) for s in found)

        # Agregar definições por arquivo
        defs_by_file: Dict[str, List[int]] = defaultdict(list)
        for symbol in found:
            nav = self.symbols[symbol]
            for defn in nav.definitions:
                defs_by_file[defn.file].append(defn.line)

        # Renderizar definições (agrupadas por arquivo)
        if defs_by_file:
            output_parts.append(f"ℹ️ Definitions ({total_defs} total, {len(defs_by_file)} files)")
            output_parts.append("-" * 40)

            for file, lines in sorted(defs_by_file.items()):
                if file in self._files:
                    code = self._files[file]
                    tc = TreeContext(
                        file,
                        code,
                        color=False,
                        loi_pad=8,
                        margin=0,
                        parent_context=True,
                        child_context=False,
                        last_line=False,
                        show_top_of_file_parent_scope=False,
                    )
                    # Adiciona TODAS as linhas de TODOS os símbolos deste arquivo
                    unique_lines = sorted(set(lines))
                    tc.add_lines_of_interest([line - 1 for line in unique_lines])
                    tc.add_context()
                    rendered = tc.format()
                    if rendered:
                        output_parts.append(f"\n{file}:")
                        output_parts.append(rendered)

        # Agregar referências por arquivo (se solicitado)
        if include_references:
            refs_by_file: Dict[str, List[int]] = defaultdict(list)
            for symbol in found:
                nav = self.symbols[symbol]
                for ref in nav.references:
                    refs_by_file[ref.file].append(ref.line)

            if refs_by_file:
                output_parts.append("")
                output_parts.append(f"ℹ️ References ({total_refs} total, {len(refs_by_file)} files)")
                output_parts.append("-" * 40)

                for file, lines in sorted(refs_by_file.items()):
                    if file in self._files:
                        code = self._files[file]
                        tc = TreeContext(
                            file,
                            code,
                            color=False,
                            loi_pad=4,
                            margin=0,
                            parent_context=False,
                            child_context=False,
                            last_line=False,
                            show_top_of_file_parent_scope=False,
                        )
                        unique_lines = sorted(set(lines))
                        tc.add_lines_of_interest([line - 1 for line in unique_lines])
                        tc.add_context()
                        rendered = tc.format()
                        if rendered:
                            output_parts.append(f"\n{file}:")
                            output_parts.append(rendered)

        return "\n".join(output_parts)


# =============================================================================
# Mapeamento de linguagens para arquivos SCM
# =============================================================================

# Padrões de exclusão padrão (diretórios e arquivos a ignorar)
DEFAULT_EXCLUDES = {
    # Controle de versão
    '.git',
    '.svn',
    '.hg',
    # Dependências
    'node_modules',
    'vendor',
    'bower_components',
    '.bundle',
    # Python
    '__pycache__',
    '.pytest_cache',
    '.mypy_cache',
    '.tox',
    '.nox',
    '.eggs',
    '*.egg-info',
    '.venv',
    '.venv*',
    'venv',
    'venv*',
    'env',
    '.env',
    # Build outputs
    'build',
    'dist',
    'target',
    'out',
    '_build',
    # IDE e editores
    '.idea',
    '.vscode',
    '.eclipse',
    '.settings',
    # Cache e temp
    '.cache',
    '.tmp',
    'tmp',
    '.temp',
    # Outros
    'coverage',
    '.coverage',
    'htmlcov',
    '.nyc_output',
    '.gradle',
    '.cargo',
}

# Mapeamento: extensão -> linguagem Tree-sitter
EXTENSION_TO_LANG = {
    '.py': 'python',
    '.js': 'javascript',
    '.jsx': 'javascript',
    '.ts': 'typescript',
    '.tsx': 'typescript',
    '.java': 'java',
    '.go': 'go',
    '.rs': 'rust',
    '.rb': 'ruby',
    '.c': 'c',
    '.h': 'c',
    '.cpp': 'cpp',
    '.hpp': 'cpp',
    '.cc': 'cpp',
    '.cs': 'csharp',
    '.php': 'php',
    '.swift': 'swift',
    '.kt': 'kotlin',
    '.scala': 'scala',
    '.ex': 'elixir',
    '.exs': 'elixir',
    '.lua': 'lua',
    '.r': 'r',
    '.R': 'r',
    '.dart': 'dart',
    '.elm': 'elm',
    '.gleam': 'gleam',
    '.sol': 'solidity',
    '.tf': 'hcl',
    '.hcl': 'hcl',
    '.el': 'elisp',
    '.lisp': 'commonlisp',
    '.cl': 'commonlisp',
    '.ml': 'ocaml',
    '.mli': 'ocaml_interface',
    '.d': 'd',
    '.ino': 'arduino',
    '.pony': 'pony',
    '.rkt': 'racket',
    '.ql': 'ql',
}

# Mapeamento: linguagem -> arquivo SCM
SCM_FILES = {
    'arduino': 'arduino-tags.scm',
    'chatito': 'chatito-tags.scm',
    'commonlisp': 'commonlisp-tags.scm',
    'cpp': 'cpp-tags.scm',
    'csharp': 'csharp-tags.scm',
    'c': 'c-tags.scm',
    'dart': 'dart-tags.scm',
    'd': 'd-tags.scm',
    'elisp': 'elisp-tags.scm',
    'elixir': 'elixir-tags.scm',
    'elm': 'elm-tags.scm',
    'gleam': 'gleam-tags.scm',
    'go': 'go-tags.scm',
    'javascript': 'javascript-tags.scm',
    'java': 'java-tags.scm',
    'lua': 'lua-tags.scm',
    'ocaml_interface': 'ocaml_interface-tags.scm',
    'ocaml': 'ocaml-tags.scm',
    'pony': 'pony-tags.scm',
    'properties': 'properties-tags.scm',
    'python': 'python-tags.scm',
    'racket': 'racket-tags.scm',
    'r': 'r-tags.scm',
    'ruby': 'ruby-tags.scm',
    'rust': 'rust-tags.scm',
    'solidity': 'solidity-tags.scm',
    'swift': 'swift-tags.scm',
    'udev': 'udev-tags.scm',
    'c_sharp': 'c_sharp-tags.scm',
    'hcl': 'hcl-tags.scm',
    'kotlin': 'kotlin-tags.scm',
    'php': 'php-tags.scm',
    'ql': 'ql-tags.scm',
    'scala': 'scala-tags.scm',
    'typescript': 'typescript-tags.scm',
}


def get_lang_from_filename(filename: str) -> Optional[str]:
    """Detecta a linguagem baseado na extensão do arquivo."""
    ext = Path(filename).suffix.lower()
    return EXTENSION_TO_LANG.get(ext)


def get_scm_path(lang: str) -> Optional[Path]:
    """Retorna o caminho do arquivo SCM para a linguagem."""
    if lang not in SCM_FILES:
        return None

    scm_filename = SCM_FILES[lang]
    base_dir = Path(__file__).parent / "queries"

    # Tentar tree-sitter-language-pack primeiro
    scm_path = base_dir / "tree-sitter-language-pack" / scm_filename
    if scm_path.exists():
        return scm_path

    # Fallback para tree-sitter-languages
    scm_path = base_dir / "tree-sitter-languages" / scm_filename
    if scm_path.exists():
        return scm_path

    return None


# =============================================================================
# Classe Principal
# =============================================================================

class SimpleRepoMap:
    """
    Versão simplificada do RepoMap com Tree-sitter.

    Gera "mapas" de repositórios identificando e ranqueando
    definições de símbolos (funções, classes) usando PageRank.

    Fluxo:
    1. Extrai tags (definições e referências) dos arquivos via Tree-sitter
    2. Constrói grafo de dependências entre arquivos
    3. Executa PageRank para ranquear arquivos
    4. Aplica boosts para contexto (chat_files, mentioned_idents)
    5. Formata output como árvore de código
    """

    def __init__(
        self,
        root: str | PathLike[str] = ".",
        max_map_tokens: int = 8192,
        verbose: bool = False,
    ):
        """
        Args:
            root: Diretório raiz do projeto
            max_map_tokens: Limite máximo de tokens no output (default: 8192)
            verbose: Se True, imprime mensagens de debug
        """
        self.root = Path(root).resolve()
        self.max_map_tokens = max_map_tokens
        self.verbose = verbose

        # Inicializar tokenizer (cl100k_base é usado pelo GPT-4)
        self._encoding = tiktoken.get_encoding("cl100k_base")

    def _log(self, msg: str):
        """Imprime mensagem se verbose=True."""
        if self.verbose:
            print(f"[DEBUG] {msg}")

    # =========================================================================
    # Contagem de Tokens
    # =========================================================================

    def _token_count(self, text: str) -> int:
        """
        Conta tokens no texto usando tiktoken.

        Para textos longos (>200 chars), usa amostragem para estimar
        o número de tokens de forma mais eficiente.

        Args:
            text: Texto para contar tokens

        Returns:
            Número de tokens (ou estimativa para textos longos)
        """
        if not text:
            return 0

        len_text = len(text)

        # Para textos curtos, contar diretamente
        if len_text < 200:
            return len(self._encoding.encode(text))

        # Para textos longos, usar amostragem
        lines = text.splitlines(keepends=True)
        num_lines = len(lines)

        if num_lines == 0:
            return len(self._encoding.encode(text))

        # Amostrar ~100 linhas distribuídas pelo texto
        step = max(1, num_lines // 100)
        sampled_lines = lines[::step]
        sample_text = "".join(sampled_lines)

        if not sample_text:
            return len(self._encoding.encode(text))

        # Contar tokens da amostra e extrapolar
        sample_tokens = len(self._encoding.encode(sample_text))
        est_tokens = (sample_tokens / len(sample_text)) * len_text

        return int(est_tokens)

    # =========================================================================
    # Extração de Tags com Tree-sitter
    # =========================================================================

    def get_tags(self, fname: str, rel_fname: str, code: str) -> List[Tag]:
        """
        Extrai tags do código usando Tree-sitter.

        Tree-sitter faz parsing real da AST, garantindo que só capturamos
        definições e referências verdadeiras, não falsos positivos em
        comentários ou strings.

        Args:
            fname: Caminho absoluto do arquivo
            rel_fname: Caminho relativo do arquivo
            code: Conteúdo do arquivo

        Returns:
            Lista de Tags (definições e referências)
        """
        # Detectar linguagem
        lang = filename_to_lang(fname)
        if not lang:
            lang = get_lang_from_filename(fname)

        if not lang:
            self._log(f"Linguagem não detectada para: {fname}")
            return []

        # Obter parser e linguagem
        try:
            language = get_language(lang)
            parser = get_parser(lang)
        except Exception as e:
            self._log(f"Erro ao obter parser para {lang}: {e}")
            return []

        # Obter arquivo SCM de queries
        scm_path = get_scm_path(lang)
        if not scm_path:
            self._log(f"Arquivo SCM não encontrado para: {lang}")
            return []

        # Ler queries SCM
        try:
            query_text = scm_path.read_text()
        except Exception as e:
            self._log(f"Erro ao ler {scm_path}: {e}")
            return []

        # Fazer parsing do código
        try:
            tree = parser.parse(bytes(code, "utf-8"))
            query = Query(language, query_text)
            cursor = QueryCursor(query)
            captures = cursor.captures(tree.root_node)
        except Exception as e:
            self._log(f"Erro ao fazer parsing de {fname}: {e}")
            return []

        # Processar capturas
        tags = []
        for capture_name, nodes in captures.items():
            # Determinar tipo de tag baseado no nome da captura
            # Formato: "name.definition.class" ou "name.reference.call"
            if "name.definition" in capture_name:
                kind = "def"
            elif "name.reference" in capture_name:
                kind = "ref"
            else:
                continue  # Ignorar outras capturas

            # Extrair subkind: "name.definition.class" → "class"
            parts = capture_name.split(".")
            subkind = parts[-1] if len(parts) >= 3 else "unknown"

            for node in nodes:
                line_num = node.start_point[0] + 1  # Tree-sitter usa 0-indexed
                name = node.text.decode('utf-8') if node.text else ""

                if name:  # Só adicionar se tem nome
                    tags.append(Tag(
                        rel_fname=rel_fname,
                        fname=fname,
                        line=line_num,
                        name=name,
                        kind=kind,
                        subkind=subkind,
                    ))

        self._log(f"Tree-sitter extraiu {len(tags)} tags de {rel_fname} ({lang})")
        return tags

    # =========================================================================
    # PageRank e Ranking
    # =========================================================================

    def _get_ranked_tags(
        self,
        files: Dict[str, str],
        chat_fnames: Optional[Set[str]] = None,
        mentioned_idents: Optional[Set[str]] = None,
        kinds: Optional[Set[str]] = None,
    ) -> Tuple[List[Tuple[float, Tag]], FileReport]:
        """
        Ranqueia tags usando PageRank.

        Etapas:
        1. Coleta tags de todos os arquivos
        2. Constrói grafo (arquivo → arquivo via referências)
        3. Executa PageRank com personalização (chat_files boosted)
        4. Aplica boosts (chat_files: 20x, mentioned_idents: 10x)

        Args:
            files: Dicionário {caminho_relativo: conteúdo}
            chat_fnames: Arquivos de alta prioridade (sendo editados)
            mentioned_idents: Identificadores mencionados na conversa
            kinds: Tipos de tags a incluir (default: {"def"} apenas definições)

        Returns:
            Tupla (lista de (rank, tag), FileReport)
        """
        chat_fnames = chat_fnames or set()
        mentioned_idents = mentioned_idents or set()
        if kinds is None:
            kinds = {"def"}

        # 1. Coletar todas as tags
        defines = defaultdict(set)      # nome -> {arquivos que definem}
        references = defaultdict(set)   # nome -> {arquivos que referenciam}
        all_tags = []
        definition_count = 0
        reference_count = 0

        for rel_fname, code in files.items():
            # Construir caminho absoluto
            abs_fname = str(self.root / rel_fname)

            tags = self.get_tags(abs_fname, rel_fname, code)
            all_tags.extend(tags)

            for tag in tags:
                if tag.kind == "def":
                    defines[tag.name].add(rel_fname)
                    definition_count += 1
                elif tag.kind == "ref":
                    references[tag.name].add(rel_fname)
                    reference_count += 1

        # 2. Construir grafo de dependências
        G = nx.MultiDiGraph()

        # Adicionar todos os arquivos como nós
        for rel_fname in files.keys():
            G.add_node(rel_fname)

        # Adicionar arestas: arquivo que referencia -> arquivo que define
        for name, ref_fnames in references.items():
            def_fnames = defines.get(name, set())
            for ref_fname in ref_fnames:
                for def_fname in def_fnames:
                    if ref_fname != def_fname:
                        G.add_edge(ref_fname, def_fname, name=name)

        # 3. Configurar personalização do PageRank
        # chat_files recebem peso inicial 100x maior
        personalization = {}
        if chat_fnames:
            for fname in chat_fnames:
                if fname in G.nodes():
                    personalization[fname] = 100.0

        # 4. Executar PageRank
        if personalization and len(G.nodes()) > 0:
            try:
                ranks = nx.pagerank(G, personalization=personalization, alpha=0.85)
            except Exception:
                # Fallback se PageRank falhar (ex: numpy não instalado)
                ranks = {node: 1.0 for node in G.nodes()}
                # Aplicar personalização manualmente como fallback simples
                for fname, weight in personalization.items():
                    if fname in ranks:
                        ranks[fname] = weight
        else:
            ranks = {node: 1.0 for node in G.nodes()}

        # 5. Aplicar boosts e criar ranking final
        ranked_tags = []

        for tag in all_tags:
            if tag.kind not in kinds:
                continue

            file_rank = ranks.get(tag.rel_fname, 0.0)
            boost = 1.0

            # Boost para identificadores mencionados (10x)
            if tag.name in mentioned_idents:
                boost *= 10.0

            # Boost para chat files (20x)
            if tag.rel_fname in chat_fnames:
                boost *= 20.0

            final_rank = file_rank * boost
            ranked_tags.append((final_rank, tag))

        # Ordenar por rank (maior primeiro), depois por arquivo e linha
        ranked_tags.sort(key=lambda x: (-x[0], x[1].rel_fname, x[1].line))

        # Criar relatório
        report = FileReport(
            excluded={},
            definition_matches=definition_count,
            reference_matches=reference_count,
            total_files_considered=len(files),
        )

        return ranked_tags, report

    # =========================================================================
    # Formatação de Output com TreeContext
    # =========================================================================

    def render_tree(self, rel_fname: str, code: str, lois: List[int]) -> str:
        """
        Renderiza código com contexto sintático usando TreeContext.

        TreeContext entende a estrutura do código e mostra contexto
        sintático (ex: em qual classe/função a linha está), tornando
        snippets isolados compreensíveis.

        Símbolos usados no output:
        - │ marca linhas de contexto
        - █ marca linhas de interesse (LOIs)
        - ⋮ indica código omitido

        Args:
            rel_fname: Caminho relativo do arquivo
            code: Conteúdo do arquivo
            lois: Lista de linhas de interesse (1-indexed)

        Returns:
            String formatada com contexto sintático
        """
        if not code or not lois:
            return ""

        # Criar TreeContext para cada renderização
        # (TreeContext acumula LOIs, então precisamos de instância fresca)
        # Configuração sem contexto - apenas as linhas de definição (estilo Aider)
        tc = TreeContext(
                rel_fname,
                code,
                color=False,
                line_number=False,
                child_context=False,
                last_line=False,
                margin=0,
                mark_lois=False,
                loi_pad=0,
                # header_max=30,
                show_top_of_file_parent_scope=False,
        )

        # Adicionar linhas de interesse (converter de 1-indexed para 0-indexed)
        tc.add_lines_of_interest([line - 1 for line in lois])
        tc.add_context()

        return tc.format()

    def _to_tree(
        self,
        ranked_tags: List[Tuple[float, Tag]],
        files: Dict[str, str],
    ) -> str:
        """
        Formata output como árvore de código com contexto sintático.

        Agrupa tags por arquivo, ordena por rank, e usa TreeContext
        para mostrar as linhas com contexto estrutural.

        Args:
            ranked_tags: Lista de (rank, tag) ordenada
            files: Dicionário {caminho_relativo: conteúdo}

        Returns:
            String formatada com o mapa do repositório
        """
        if not ranked_tags:
            return ""

        # Agrupar tags por arquivo
        tags_by_file = defaultdict(list)
        max_rank_by_file = {}

        for rank, tag in ranked_tags:
            tags_by_file[tag.rel_fname].append((rank, tag))
            if tag.rel_fname not in max_rank_by_file:
                max_rank_by_file[tag.rel_fname] = rank
            else:
                max_rank_by_file[tag.rel_fname] = max(max_rank_by_file[tag.rel_fname], rank)

        # Ordenar arquivos por rank máximo (maior primeiro)
        sorted_files = sorted(
            tags_by_file.keys(),
            key=lambda f: -max_rank_by_file[f]
        )

        # Gerar output
        output_parts = []
        for fname in sorted_files:
            # Coletar linhas de interesse para este arquivo
            lois = [tag.line for _, tag in tags_by_file[fname]]

            # Renderizar com TreeContext
            code = files.get(fname, "")
            rendered = self.render_tree(fname, code, lois)

            if rendered:
                # Adicionar cabeçalho com rank
                header = f"{fname}:\n(Rank value: {max_rank_by_file[fname]:.4f})\n"
                output_parts.append(header + "\n" + rendered)

        return '\n\n'.join(output_parts)

    # =========================================================================
    # Busca Binária por Tokens
    # =========================================================================

    def _to_tree_truncated_by_tokens(
        self,
        ranked_tags: List[Tuple[float, Tag]],
        files: Dict[str, str],
        max_tokens: int,
    ) -> str:
        """
        Gera árvore de código truncada para caber no limite de tokens.

        Usa busca binária para encontrar eficientemente o número
        máximo de tags que cabem no limite. Complexidade: O(log n).

        Args:
            ranked_tags: Lista de (rank, tag) ordenada por rank
            files: Dicionário {caminho_relativo: conteúdo}
            max_tokens: Limite máximo de tokens

        Returns:
            String formatada com o mapa truncado
        """
        if not ranked_tags:
            return "No definitions found."

        def try_tags(num_tags: int) -> Tuple[str, int]:
            """Tenta renderizar num_tags e retorna (output, tokens)."""
            if num_tags <= 0:
                return "", 0

            selected_tags = ranked_tags[:num_tags]
            tree_output = self._to_tree(selected_tags, files)
            tokens = self._token_count(tree_output)
            return tree_output, tokens

        # Busca binária
        left, right = 1, len(ranked_tags)
        best_tree = ""
        best_tokens = 0

        self._log(f"Busca binária: {len(ranked_tags)} tags, limite {max_tokens} tokens")

        iterations = 0
        while left <= right:
            mid = (left + right) // 2
            tree_output, tokens = try_tags(mid)
            iterations += 1

            self._log(f"  Iteração {iterations}: mid={mid}, tokens={tokens}")

            if tokens <= max_tokens:
                # Cabe! Guardar e tentar incluir mais tags
                best_tree = tree_output
                best_tokens = tokens
                left = mid + 1
            else:
                # Não cabe! Reduzir número de tags
                right = mid - 1

        self._log(f"Resultado: {right} tags, {best_tokens} tokens em {iterations} iterações")

        return best_tree if best_tree else "No definitions found."

    # =========================================================================
    # API Principal
    # =========================================================================

    def get_repo_map(
        self,
        paths: List[Path],
        chat_fnames: Optional[Set[str]] = None,
        mentioned_idents: Optional[Set[str]] = None,
        excludes: Optional[Set[str]] = None,
        max_tokens: Optional[int] = None,
    ) -> Tuple[str, FileReport]:
        """
        Gera o mapa do repositório a partir de arquivos e/ou diretórios.

        Esta é a única API pública para geração de mapas. Aceita uma lista
        de Paths que podem ser arquivos ou diretórios (processados recursivamente).

        Args:
            paths: Lista de arquivos e/ou diretórios a processar
            chat_fnames: Arquivos de alta prioridade (boost 20x no ranking)
            mentioned_idents: Identificadores mencionados (boost 10x no ranking)
            excludes: Padrões de exclusão adicionais (combina com DEFAULT_EXCLUDES)
            max_tokens: Limite de tokens (usa self.max_map_tokens se None)

        Returns:
            Tupla (mapa_formatado, FileReport)

        Example:
            >>> mapper = SimpleRepoMap(root="/path/to/project")
            >>> repo_map, report = mapper.get_repo_map(
            ...     paths=[Path("src"), Path("main.py")],
            ...     chat_fnames={"src/app.py"},
            ...     mentioned_idents={"UserService"},
            ... )
        """
        if max_tokens is None:
            max_tokens = self.max_map_tokens

        # 1. Descobrir todos os arquivos a partir dos paths
        file_paths = self._resolve_paths(paths, excludes)

        if not file_paths:
            return "No supported files found.", FileReport(
                excluded={},
                definition_matches=0,
                reference_matches=0,
                total_files_considered=0,
            )

        # 2. Ler conteúdo dos arquivos
        files = self._read_files(file_paths)

        if not files:
            return "No supported files found.", FileReport(
                excluded={},
                definition_matches=0,
                reference_matches=0,
                total_files_considered=0,
            )

        # 3. Ranquear tags
        ranked_tags, report = self._get_ranked_tags(files, chat_fnames, mentioned_idents)

        # 4. Gerar output com busca binária para otimizar tokens
        tree = self._to_tree_truncated_by_tokens(ranked_tags, files, max_tokens)

        return tree, report

    def find_symbol(
        self,
        symbol: str,
        paths: List[Path],
        source_file: Optional[Path] = None,
        excludes: Optional[Set[str]] = None,
        include_snippet: bool = True,
    ) -> SymbolNavigation:
        """
        Encontra definições e referências de um símbolo.

        Similar ao GitHub Code Navigation - dado um símbolo,
        retorna onde é definido e onde é referenciado.

        Args:
            symbol: Nome do símbolo a buscar (ex: "User", "get_repo_map")
            paths: Lista de arquivos/diretórios a buscar
            source_file: Path do arquivo de origem (onde o usuário clicou no símbolo).
                        Recebe boost 20x no ranking, priorizando definições
                        e referências conectadas a este arquivo.
            excludes: Padrões de exclusão adicionais
            include_snippet: Se True, inclui trecho de código

        Returns:
            SymbolNavigation com definições e referências

        Example:
            >>> mapper = SimpleRepoMap(root="/path/to/project")
            >>> result = mapper.find_symbol(
            ...     "User",
            ...     [Path("src")],
            ...     source_file=Path("src/services/user_service.py")
            ... )
            >>> print(f"{result.symbol} ({result.kind})")
            User (class)
            >>> for defn in result.definitions:
            ...     print(f"Defined at: {defn.file}:{defn.line}")
        """
        # 1. Descobrir arquivos
        file_paths = self._resolve_paths(paths, excludes)

        if not file_paths:
            return SymbolNavigation(
                symbol=symbol,
                kind="unknown",
                definitions=[],
                references=[],
                source_file=str(source_file) if source_file else None,
            )

        # 2. Ler conteúdo dos arquivos
        files = self._read_files(file_paths)

        if not files:
            return SymbolNavigation(
                symbol=symbol,
                kind="unknown",
                definitions=[],
                references=[],
                source_file=str(source_file) if source_file else None,
            )

        # 3. Obter tags rankeadas (def + ref) com boost para o símbolo buscado
        source_file_str = str(source_file) if source_file else None
        ranked_tags, _ = self._get_ranked_tags(
            files,
            chat_fnames={source_file_str} if source_file_str else None,
            mentioned_idents={symbol},
            kinds={"def", "ref"},
        )

        # 4. Filtrar pelo símbolo (já vem ordenado por rank)
        matching = [(rank, tag) for rank, tag in ranked_tags if tag.name == symbol]
        definitions = [tag for rank, tag in matching if tag.kind == "def"]
        references = [tag for rank, tag in matching if tag.kind == "ref"]

        # 5. Helper para criar SymbolLocation
        def make_location(tag: Tag) -> SymbolLocation:
            snippet = ""
            if include_snippet and tag.rel_fname in files:
                lines = files[tag.rel_fname].splitlines()
                if 0 < tag.line <= len(lines):
                    snippet = lines[tag.line - 1].strip()
            return SymbolLocation(
                file=tag.rel_fname,
                line=tag.line,
                snippet=snippet,
            )

        # 6. Coletar arquivos relevantes (apenas os que contêm o símbolo)
        relevant_files = {}
        for tag in definitions + references:
            if tag.rel_fname in files and tag.rel_fname not in relevant_files:
                relevant_files[tag.rel_fname] = files[tag.rel_fname]

        # 7. Montar resultado
        kind = definitions[0].subkind if definitions else "unknown"

        return SymbolNavigation(
            symbol=symbol,
            kind=kind,
            definitions=[make_location(t) for t in definitions],
            references=[make_location(t) for t in references],
            source_file=source_file_str,
            _files=relevant_files,
        )

    def find_symbols(
        self,
        symbols: List[str],
        paths: List[Path],
        source_file: Optional[Path] = None,
        excludes: Optional[Set[str]] = None,
        include_snippet: bool = True,
    ) -> MultiSymbolNavigation:
        """
        Encontra definições e referências de múltiplos símbolos.

        Mais eficiente que chamar find_symbol() múltiplas vezes,
        pois faz parsing dos arquivos apenas uma vez.

        Args:
            symbols: Lista de nomes de símbolos a buscar
            paths: Lista de arquivos/diretórios a buscar
            source_file: Path do arquivo de origem (boost 20x no ranking)
            excludes: Padrões de exclusão adicionais
            include_snippet: Se True, inclui trecho de código

        Returns:
            MultiSymbolNavigation com navegação agregada para todos os símbolos

        Example:
            >>> mapper = SimpleRepoMap(root="/path/to/project")
            >>> result = mapper.find_symbols(
            ...     ["User", "Product", "OrderService"],
            ...     [Path("src")],
            ...     source_file=Path("src/api/routes.py")
            ... )
            >>> print(result.found_symbols)  # ['User', 'Product', 'OrderService']
            >>> print(result.render())       # Output agregado, sem duplicação
            >>> print(result.get("User"))    # Acesso individual
        """
        source_file_str = str(source_file) if source_file else None

        # 1. Descobrir arquivos
        file_paths = self._resolve_paths(paths, excludes)

        if not file_paths:
            # Retorna MultiSymbolNavigation com todos os símbolos não encontrados
            empty_navs = {
                symbol: SymbolNavigation(
                    symbol=symbol,
                    kind="unknown",
                    definitions=[],
                    references=[],
                    source_file=source_file_str,
                )
                for symbol in symbols
            }
            return MultiSymbolNavigation(
                symbols=empty_navs,
                source_file=source_file_str,
            )

        # 2. Ler conteúdo dos arquivos
        files = self._read_files(file_paths)

        if not files:
            empty_navs = {
                symbol: SymbolNavigation(
                    symbol=symbol,
                    kind="unknown",
                    definitions=[],
                    references=[],
                    source_file=source_file_str,
                )
                for symbol in symbols
            }
            return MultiSymbolNavigation(
                symbols=empty_navs,
                source_file=source_file_str,
            )

        # 3. Obter tags rankeadas com boost para TODOS os símbolos
        ranked_tags, _ = self._get_ranked_tags(
            files,
            chat_fnames={source_file_str} if source_file_str else None,
            mentioned_idents=set(symbols),  # Todos recebem boost 10x
            kinds={"def", "ref"},
        )

        # 4. Helper para criar SymbolLocation
        def make_location(tag: Tag) -> SymbolLocation:
            snippet = ""
            if include_snippet and tag.rel_fname in files:
                lines_list = files[tag.rel_fname].splitlines()
                if 0 < tag.line <= len(lines_list):
                    snippet = lines_list[tag.line - 1].strip()
            return SymbolLocation(
                file=tag.rel_fname,
                line=tag.line,
                snippet=snippet,
            )

        # 5. Filtrar e agrupar por símbolo
        symbol_set = set(symbols)
        matching = [(rank, tag) for rank, tag in ranked_tags if tag.name in symbol_set]

        # Agrupar por símbolo
        defs_by_symbol: Dict[str, List[Tag]] = defaultdict(list)
        refs_by_symbol: Dict[str, List[Tag]] = defaultdict(list)

        for rank, tag in matching:
            if tag.kind == "def":
                defs_by_symbol[tag.name].append(tag)
            elif tag.kind == "ref":
                refs_by_symbol[tag.name].append(tag)

        # 6. Coletar todos os arquivos relevantes
        relevant_files = {}
        for rank, tag in matching:
            if tag.rel_fname in files and tag.rel_fname not in relevant_files:
                relevant_files[tag.rel_fname] = files[tag.rel_fname]

        # 7. Construir SymbolNavigation para cada símbolo
        symbol_navs = {}
        for symbol in symbols:
            definitions = defs_by_symbol.get(symbol, [])
            references = refs_by_symbol.get(symbol, [])
            kind = definitions[0].subkind if definitions else "unknown"

            symbol_navs[symbol] = SymbolNavigation(
                symbol=symbol,
                kind=kind,
                definitions=[make_location(t) for t in definitions],
                references=[make_location(t) for t in references],
                source_file=source_file_str,
                _files=relevant_files,
            )

        return MultiSymbolNavigation(
            symbols=symbol_navs,
            _files=relevant_files,
            source_file=source_file_str,
        )

    # =========================================================================
    # Métodos Privados - Resolução de Paths
    # =========================================================================

    def _should_exclude(self, path: Path, excludes: Set[str]) -> bool:
        """
        Verifica se um caminho deve ser excluído.

        Args:
            path: Caminho a verificar
            excludes: Conjunto de padrões de exclusão

        Returns:
            True se deve ser excluído
        """
        # Verificar cada parte do caminho
        for part in path.parts:
            if part in excludes:
                return True
            # Verificar padrões com wildcard (ex: *.egg-info)
            for pattern in excludes:
                if '*' in pattern:
                    import fnmatch
                    if fnmatch.fnmatch(part, pattern):
                        return True
        return False

    def _is_supported_file(self, path: Path) -> bool:
        """Verifica se o arquivo tem extensão suportada pelo Tree-sitter."""
        ext = path.suffix.lower()
        return ext in EXTENSION_TO_LANG

    def _resolve_paths(
        self,
        paths: List[Path],
        excludes: Optional[Set[str]] = None,
    ) -> List[Path]:
        """
        Resolve lista de paths em arquivos concretos.

        Aceita tanto arquivos quanto diretórios. Diretórios são
        escaneados recursivamente.

        Args:
            paths: Lista de arquivos e/ou diretórios
            excludes: Padrões de exclusão adicionais

        Returns:
            Lista de arquivos descobertos
        """
        # Combinar exclusões padrão com adicionais
        all_excludes = DEFAULT_EXCLUDES.copy()
        if excludes:
            all_excludes.update(excludes)

        discovered = []

        for path in paths:
            path = path.resolve() if not path.is_absolute() else path

            if path.is_file():
                # Arquivo individual
                if self._is_supported_file(path):
                    # Verificar exclusões no caminho relativo
                    try:
                        rel_path = path.relative_to(self.root)
                    except ValueError:
                        rel_path = Path(path.name)

                    if not self._should_exclude(rel_path, all_excludes):
                        discovered.append(path)
                        self._log(f"Arquivo: {path}")

            elif path.is_dir():
                # Diretório - escanear recursivamente
                self._log(f"Escaneando diretório: {path}")

                for file_path in path.rglob('*'):
                    if file_path.is_dir():
                        continue

                    # Calcular caminho relativo para verificar exclusões
                    try:
                        rel_path = file_path.relative_to(self.root)
                    except ValueError:
                        try:
                            rel_path = file_path.relative_to(path)
                        except ValueError:
                            rel_path = Path(file_path.name)

                    # Verificar exclusões
                    if self._should_exclude(rel_path, all_excludes):
                        continue

                    # Verificar se é arquivo suportado
                    if not self._is_supported_file(file_path):
                        continue

                    discovered.append(file_path)

        self._log(f"Total: {len(discovered)} arquivos descobertos")
        return discovered

    def _read_files(self, file_paths: List[Path]) -> Dict[str, str]:
        """
        Lê conteúdo de uma lista de arquivos.

        Args:
            file_paths: Lista de caminhos de arquivos

        Returns:
            Dicionário {caminho_relativo: conteúdo}
        """
        files = {}
        errors = []

        for fpath in file_paths:
            abs_path = fpath.resolve() if not fpath.is_absolute() else fpath

            # Calcular caminho relativo
            try:
                rel_path = abs_path.relative_to(self.root)
            except ValueError:
                rel_path = Path(abs_path.name)

            # Ler conteúdo
            try:
                content = abs_path.read_text(encoding='utf-8')
                files[str(rel_path)] = content
            except UnicodeDecodeError:
                # Tentar com latin-1 como fallback
                try:
                    content = abs_path.read_text(encoding='latin-1')
                    files[str(rel_path)] = content
                    self._log(f"Arquivo {rel_path} lido com encoding latin-1")
                except Exception as e:
                    errors.append((rel_path, str(e)))
                    self._log(f"Erro ao ler {rel_path}: {e}")
            except Exception as e:
                errors.append((rel_path, str(e)))
                self._log(f"Erro ao ler {rel_path}: {e}")

        if errors:
            self._log(f"{len(errors)} arquivos não puderam ser lidos")

        return files


# =============================================================================
# Exemplo de uso
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Exemplo 1: Escanear diretório atual")
    print("=" * 60)

    # Criar mapper apontando para o diretório atual
    mapper = SimpleRepoMap(root=".", verbose=True, max_map_tokens=2000)

    # A nova API aceita List[Path] com arquivos e/ou diretórios
    repo_map, report = mapper.get_repo_map(
        paths=[Path(".")],  # Diretório atual
        chat_fnames={"simple_repomap.py"},
        mentioned_idents={"SimpleRepoMap", "get_repo_map"},
    )

    print(f"\nArquivos processados: {report.total_files_considered}")
    print(f"Definições: {report.definition_matches}")
    print(f"Referências: {report.reference_matches}")
    print(f"\nMapa:")
    print(repo_map[:2000] if len(repo_map) > 2000 else repo_map)
    print(f"\nTokens usados: {mapper._token_count(repo_map)}")

    print("\n" + "=" * 60)
    print("Exemplo 2: Arquivos específicos")
    print("=" * 60)

    # Também aceita arquivos específicos
    repo_map, report = mapper.get_repo_map(
        paths=[Path("simple_repomap.py"), Path("utils.py")],
        max_tokens=500,
    )

    print(f"\nArquivos processados: {report.total_files_considered}")
    print(repo_map)

    print("\n" + "=" * 60)
    print("Exemplo 3: Mistura de arquivos e diretórios")
    print("=" * 60)

    # Pode misturar arquivos e diretórios na mesma chamada
    repo_map, report = mapper.get_repo_map(
        paths=[Path("queries"), Path("simple_repomap.py")],
        excludes={"tests"},  # Exclusão adicional
        max_tokens=1000,
    )

    print(f"\nArquivos processados: {report.total_files_considered}")
    print(f"Definições: {report.definition_matches}")
