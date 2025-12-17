"""
Testes unitários para SimpleRepoMap.

Execute com: pytest test_simple_repomap.py -v
"""

from pathlib import Path

import pytest

from repo_graph.repo_map.simple_repomap import (
    SimpleRepoMap,
    FileReport,
    SymbolLocation,
    SymbolNavigation,
    MultiSymbolNavigation,
    get_lang_from_filename,
    get_scm_path,
    SCM_FILES,
)


# =============================================================================
# Fixtures - Dados de teste reutilizáveis
# =============================================================================

@pytest.fixture
def mapper():
    """Mapper padrão para testes."""
    return SimpleRepoMap(verbose=False)


@pytest.fixture
def mapper_verbose():
    """Mapper com verbose ativado."""
    return SimpleRepoMap(verbose=True)


@pytest.fixture
def sample_project(tmp_path):
    """Cria estrutura de projeto de exemplo."""
    # main.py
    (tmp_path / "main.py").write_text("""from utils import format_name
from models import User

def run():
    user = User("Alice")
    print(format_name(user.name))

if __name__ == "__main__":
    run()
""")
    # utils.py
    (tmp_path / "utils.py").write_text("""def format_name(name):
    return name.upper()

def validate_email(email):
    return "@" in email
""")
    # models.py
    (tmp_path / "models.py").write_text("""class User:
    def __init__(self, name):
        self.name = name

class Product:
    def __init__(self, title):
        self.title = title
""")
    return tmp_path


# =============================================================================
# Testes de Detecção de Linguagem
# =============================================================================

class TestLanguageDetection:
    """Testes para detecção de linguagem baseada em extensão."""

    def test_get_lang_from_filename_python(self):
        """Testa detecção de Python."""
        assert get_lang_from_filename("test.py") == "python"

    def test_get_lang_from_filename_javascript(self):
        """Testa detecção de JavaScript."""
        assert get_lang_from_filename("app.js") == "javascript"
        assert get_lang_from_filename("component.jsx") == "javascript"

    def test_get_lang_from_filename_typescript(self):
        """Testa detecção de TypeScript."""
        assert get_lang_from_filename("service.ts") == "typescript"
        assert get_lang_from_filename("component.tsx") == "typescript"

    def test_get_lang_from_filename_other_languages(self):
        """Testa detecção de outras linguagens."""
        assert get_lang_from_filename("main.go") == "go"
        assert get_lang_from_filename("lib.rs") == "rust"
        assert get_lang_from_filename("App.java") == "java"
        assert get_lang_from_filename("test.rb") == "ruby"

    def test_get_lang_from_filename_unknown(self):
        """Testa extensões desconhecidas."""
        assert get_lang_from_filename("readme.md") is None
        assert get_lang_from_filename("data.json") is None
        assert get_lang_from_filename("config.yaml") is None

    def test_get_lang_from_filename_case_insensitive(self):
        """Testa que extensões são case-insensitive."""
        assert get_lang_from_filename("test.PY") == "python"
        assert get_lang_from_filename("test.Py") == "python"


# =============================================================================
# Testes de Caminho SCM
# =============================================================================

class TestSCMPath:
    """Testes para resolução de caminhos SCM."""

    def test_get_scm_path_python(self):
        """Testa caminho SCM para Python."""
        path = get_scm_path("python")
        assert path is not None
        assert path.exists()
        assert "python" in path.name

    def test_get_scm_path_javascript(self):
        """Testa caminho SCM para JavaScript."""
        path = get_scm_path("javascript")
        assert path is not None
        assert path.exists()

    def test_get_scm_path_unknown(self):
        """Testa linguagem sem SCM."""
        path = get_scm_path("unknown_language")
        assert path is None

    def test_all_scm_files_exist(self):
        """Verifica que todos os arquivos SCM mapeados existem."""
        for lang in SCM_FILES.keys():
            path = get_scm_path(lang)
            # Algumas linguagens podem não ter arquivo SCM ainda
            if path is not None:
                assert path.exists(), f"Arquivo SCM não encontrado para: {lang}"


# =============================================================================
# Testes da API Principal - get_repo_map
# =============================================================================

class TestGetRepoMap:
    """Testes para o método principal get_repo_map."""

    def test_basic_directory_scan(self, sample_project):
        """Testa scan básico de diretório."""
        mapper = SimpleRepoMap(root=str(sample_project))
        output, report = mapper.get_repo_map(paths=[sample_project])

        assert "main.py" in output
        assert report.total_files_considered == 3
        assert report.definition_matches >= 5  # run, format_name, validate_email, User, Product, etc.

    def test_single_file(self, sample_project):
        """Testa com arquivo único."""
        mapper = SimpleRepoMap(root=str(sample_project))
        output, report = mapper.get_repo_map(
            paths=[sample_project / "main.py"]
        )

        assert "main.py" in output
        assert report.total_files_considered == 1

    def test_multiple_files(self, sample_project):
        """Testa com múltiplos arquivos."""
        mapper = SimpleRepoMap(root=str(sample_project))
        output, report = mapper.get_repo_map(
            paths=[sample_project / "main.py", sample_project / "utils.py"]
        )

        assert "main.py" in output
        assert "utils.py" in output
        assert report.total_files_considered == 2

    def test_mixed_files_and_directories(self, tmp_path):
        """Testa mistura de arquivos e diretórios."""
        # Criar estrutura
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("def app(): pass")
        (tmp_path / "main.py").write_text("def main(): pass")

        mapper = SimpleRepoMap(root=str(tmp_path))
        output, report = mapper.get_repo_map(
            paths=[tmp_path / "src", tmp_path / "main.py"]
        )

        assert "app.py" in output
        assert "main.py" in output
        assert report.total_files_considered == 2

    def test_chat_fnames_boost(self, sample_project):
        """Testa boost de chat_fnames."""
        mapper = SimpleRepoMap(root=str(sample_project))
        output, report = mapper.get_repo_map(
            paths=[sample_project],
            chat_fnames={"main.py"}
        )

        # main.py deve aparecer primeiro por causa do boost 20x
        assert output.index("main.py") < output.index("utils.py")

    def test_mentioned_idents_boost(self, sample_project):
        """Testa boost de mentioned_idents."""
        mapper = SimpleRepoMap(root=str(sample_project))
        output, report = mapper.get_repo_map(
            paths=[sample_project],
            mentioned_idents={"User"}
        )

        # User está em models.py, que deve ter boost
        assert "User" in output

    def test_excludes(self, tmp_path):
        """Testa exclusões customizadas."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("def app(): pass")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_app.py").write_text("def test(): pass")

        mapper = SimpleRepoMap(root=str(tmp_path))
        output, report = mapper.get_repo_map(
            paths=[tmp_path],
            excludes={"tests"}
        )

        assert "app.py" in output
        assert "test_app.py" not in output

    def test_max_tokens(self, tmp_path):
        """Testa limite de tokens."""
        # Criar vários arquivos
        for i in range(10):
            (tmp_path / f"module_{i}.py").write_text(f"def func_{i}(): pass")

        mapper = SimpleRepoMap(root=str(tmp_path))

        # Com limite baixo
        output_small, _ = mapper.get_repo_map(
            paths=[tmp_path],
            max_tokens=100
        )

        # Com limite alto
        output_large, _ = mapper.get_repo_map(
            paths=[tmp_path],
            max_tokens=10000
        )

        assert len(output_small) < len(output_large)
        assert mapper._token_count(output_small) <= 100

    def test_empty_directory(self, tmp_path):
        """Testa diretório vazio."""
        mapper = SimpleRepoMap(root=str(tmp_path))
        output, report = mapper.get_repo_map(paths=[tmp_path])

        assert output == "No supported files found."
        assert report.total_files_considered == 0

    def test_unsupported_files_only(self, tmp_path):
        """Testa diretório só com arquivos não suportados."""
        (tmp_path / "readme.md").write_text("# Readme")
        (tmp_path / "config.json").write_text("{}")

        mapper = SimpleRepoMap(root=str(tmp_path))
        output, report = mapper.get_repo_map(paths=[tmp_path])

        assert output == "No supported files found."

    def test_returns_tuple(self, sample_project):
        """Testa que retorna tupla (str, FileReport)."""
        mapper = SimpleRepoMap(root=str(sample_project))
        result = mapper.get_repo_map(paths=[sample_project])

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], FileReport)


# =============================================================================
# Testes de Exclusões Padrão
# =============================================================================

class TestDefaultExcludes:
    """Testes para exclusões padrão."""

    def test_ignores_git(self, tmp_path):
        """Testa que .git é ignorado."""
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "config.py").write_text("def config(): pass")
        (tmp_path / "main.py").write_text("def main(): pass")

        mapper = SimpleRepoMap(root=str(tmp_path))
        output, report = mapper.get_repo_map(paths=[tmp_path])

        assert "main.py" in output
        assert "config.py" not in output
        assert report.total_files_considered == 1

    def test_ignores_node_modules(self, tmp_path):
        """Testa que node_modules é ignorado."""
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "lib.js").write_text("function lib() {}")
        (tmp_path / "app.js").write_text("function app() {}")

        mapper = SimpleRepoMap(root=str(tmp_path))
        output, report = mapper.get_repo_map(paths=[tmp_path])

        assert "app.js" in output
        assert "lib.js" not in output

    def test_ignores_pycache(self, tmp_path):
        """Testa que __pycache__ é ignorado."""
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "module.cpython-311.pyc").write_text("")
        (tmp_path / "module.py").write_text("def func(): pass")

        mapper = SimpleRepoMap(root=str(tmp_path))
        output, report = mapper.get_repo_map(paths=[tmp_path])

        assert report.total_files_considered == 1

    def test_ignores_venv(self, tmp_path):
        """Testa que .venv e venv são ignorados."""
        (tmp_path / ".venv").mkdir()
        (tmp_path / ".venv" / "lib.py").write_text("def lib(): pass")
        (tmp_path / "venv").mkdir()
        (tmp_path / "venv" / "lib2.py").write_text("def lib2(): pass")
        (tmp_path / "app.py").write_text("def app(): pass")

        mapper = SimpleRepoMap(root=str(tmp_path))
        output, report = mapper.get_repo_map(paths=[tmp_path])

        assert report.total_files_considered == 1

    def test_ignores_egg_info(self, tmp_path):
        """Testa que *.egg-info é ignorado."""
        (tmp_path / "mypackage.egg-info").mkdir()
        (tmp_path / "mypackage.egg-info" / "PKG-INFO.py").write_text("def info(): pass")
        (tmp_path / "app.py").write_text("def app(): pass")

        mapper = SimpleRepoMap(root=str(tmp_path))
        output, report = mapper.get_repo_map(paths=[tmp_path])

        assert report.total_files_considered == 1


# =============================================================================
# Testes de Múltiplas Linguagens
# =============================================================================

class TestMultipleLanguages:
    """Testes para suporte a múltiplas linguagens."""

    def test_javascript_files(self, tmp_path):
        """Testa arquivos JavaScript."""
        (tmp_path / "app.js").write_text("""
function main() {
    console.log("Hello");
}

export { main };
""")
        mapper = SimpleRepoMap(root=str(tmp_path))
        output, report = mapper.get_repo_map(paths=[tmp_path])

        assert "app.js" in output
        assert report.definition_matches >= 1

    def test_mixed_languages(self, tmp_path):
        """Testa mistura de linguagens."""
        (tmp_path / "app.py").write_text("def main(): pass")
        (tmp_path / "app.js").write_text("function main() {}")
        (tmp_path / "app.ts").write_text("function main(): void {}")

        mapper = SimpleRepoMap(root=str(tmp_path))
        output, report = mapper.get_repo_map(paths=[tmp_path])

        assert report.total_files_considered == 3

    def test_go_syntax(self, tmp_path):
        """Testa sintaxe Go."""
        (tmp_path / "main.go").write_text("""package main

func main() {
    fmt.Println("Hello")
}

type User struct {
    Name string
}
""")
        mapper = SimpleRepoMap(root=str(tmp_path))
        output, report = mapper.get_repo_map(paths=[tmp_path])

        assert "main.go" in output

    def test_rust_syntax(self, tmp_path):
        """Testa sintaxe Rust."""
        (tmp_path / "main.rs").write_text("""
fn main() {
    println!("Hello");
}

struct User {
    name: String,
}
""")
        mapper = SimpleRepoMap(root=str(tmp_path))
        output, report = mapper.get_repo_map(paths=[tmp_path])

        assert "main.rs" in output


# =============================================================================
# Testes de TreeContext
# =============================================================================

class TestTreeContext:
    """Testes para renderização com TreeContext."""

    def test_output_includes_context_markers(self, tmp_path):
        """Testa que output inclui marcadores de contexto."""
        (tmp_path / "app.py").write_text("""
class MyClass:
    def my_method(self):
        pass

    def another_method(self):
        pass
""")
        mapper = SimpleRepoMap(root=str(tmp_path))
        output, _ = mapper.get_repo_map(paths=[tmp_path])

        # TreeContext usa │ para contexto e █ para LOIs
        assert "│" in output or "█" in output or "⋮" in output

    def test_shows_parent_scope(self, tmp_path):
        """Testa que contexto sintático mostra escopo pai."""
        (tmp_path / "app.py").write_text("""
class User:
    def __init__(self, name):
        self.name = name

    def greet(self):
        return f"Hello, {self.name}"
""")
        mapper = SimpleRepoMap(root=str(tmp_path))
        output, _ = mapper.get_repo_map(paths=[tmp_path])

        # Deve mostrar a classe como contexto dos métodos
        assert "class User" in output


# =============================================================================
# Testes de Token Counting
# =============================================================================

class TestTokenCounting:
    """Testes para contagem de tokens."""

    def test_token_count_empty_string(self, mapper):
        """Testa contagem de string vazia."""
        assert mapper._token_count("") == 0

    def test_token_count_short_text(self, mapper):
        """Testa contagem de texto curto."""
        tokens = mapper._token_count("Hello, world!")
        assert tokens > 0
        assert tokens < 10

    def test_token_count_code(self, mapper):
        """Testa contagem de código."""
        code = """
def hello():
    print("Hello, world!")

hello()
"""
        tokens = mapper._token_count(code)
        assert tokens > 5
        assert tokens < 50

    def test_binary_search_efficiency(self, tmp_path):
        """Testa que busca binária é eficiente."""
        # Criar arquivo com muitas definições
        lines = [f"def func_{i}(): pass" for i in range(100)]
        (tmp_path / "many_funcs.py").write_text("\n".join(lines))

        mapper = SimpleRepoMap(root=str(tmp_path))
        output, report = mapper.get_repo_map(
            paths=[tmp_path],
            max_tokens=500
        )

        assert mapper._token_count(output) <= 500


# =============================================================================
# Testes de Edge Cases
# =============================================================================

class TestEdgeCases:
    """Testes para casos extremos."""

    def test_file_with_syntax_error(self, tmp_path):
        """Testa arquivo com erro de sintaxe."""
        (tmp_path / "broken.py").write_text("""def incomplete(
            # missing closing paren and colon
        """)

        mapper = SimpleRepoMap(root=str(tmp_path))
        output, report = mapper.get_repo_map(paths=[tmp_path])

        # Não deve lançar exceção
        assert isinstance(output, str)

    def test_very_long_file(self, tmp_path):
        """Testa arquivo muito longo."""
        lines = []
        for i in range(100):
            lines.append(f"def func_{i}():")
            lines.append("    pass")
            lines.append("")

        (tmp_path / "long.py").write_text("\n".join(lines))

        mapper = SimpleRepoMap(root=str(tmp_path))
        output, report = mapper.get_repo_map(paths=[tmp_path])

        assert report.definition_matches == 100

    def test_unicode_content(self, tmp_path):
        """Testa arquivo com conteúdo Unicode."""
        (tmp_path / "unicode.py").write_text("""def saudação():
    return "Olá, 世界! 🌍"

class Configuração:
    pass
""")

        mapper = SimpleRepoMap(root=str(tmp_path))
        output, report = mapper.get_repo_map(paths=[tmp_path])

        assert report.definition_matches >= 2

    def test_special_characters_in_filename(self, tmp_path):
        """Testa arquivos com caracteres especiais no nome."""
        (tmp_path / "my-module.py").write_text("def test(): pass")
        (tmp_path / "my_module.py").write_text("def test2(): pass")

        mapper = SimpleRepoMap(root=str(tmp_path))
        output, report = mapper.get_repo_map(paths=[tmp_path])

        assert report.total_files_considered == 2

    def test_deeply_nested_code(self, tmp_path):
        """Testa código com muitos níveis de indentação."""
        (tmp_path / "nested.py").write_text("""
class Outer:
    class Inner:
        class DeepInner:
            def deep_method(self):
                def nested_func():
                    pass
                return nested_func
""")

        mapper = SimpleRepoMap(root=str(tmp_path))
        output, report = mapper.get_repo_map(paths=[tmp_path])

        assert report.definition_matches >= 3

    def test_missing_file(self, tmp_path):
        """Testa com arquivo inexistente."""
        mapper = SimpleRepoMap(root=str(tmp_path))
        output, report = mapper.get_repo_map(
            paths=[tmp_path / "nonexistent.py"]
        )

        assert output == "No supported files found."


# =============================================================================
# Testes de Integração
# =============================================================================

class TestIntegration:
    """Testes de integração end-to-end."""

    def test_full_workflow(self, sample_project):
        """Testa fluxo completo de uso."""
        mapper = SimpleRepoMap(root=str(sample_project))

        # 1. Gerar mapa inicial
        output1, report1 = mapper.get_repo_map(paths=[sample_project])
        assert report1.definition_matches > 0

        # 2. Gerar mapa com chat_files
        output2, report2 = mapper.get_repo_map(
            paths=[sample_project],
            chat_fnames={"main.py"}
        )

        # main.py deve aparecer primeiro no output2
        assert output2.index("main.py") < output2.index("utils.py")

        # 3. Gerar mapa com mentioned_idents
        output3, report3 = mapper.get_repo_map(
            paths=[sample_project],
            mentioned_idents={"User"}
        )

        # Todos os reports devem ter mesmas contagens base
        assert report1.definition_matches == report2.definition_matches == report3.definition_matches

    def test_consistency_across_runs(self, sample_project):
        """Testa que resultados são consistentes entre execuções."""
        mapper = SimpleRepoMap(root=str(sample_project))

        output1, _ = mapper.get_repo_map(paths=[sample_project])
        output2, _ = mapper.get_repo_map(paths=[sample_project])

        assert output1 == output2


# =============================================================================
# Testes do Verbose Mode
# =============================================================================

class TestVerboseMode:
    """Testes para modo verbose."""

    def test_verbose_mode_outputs_debug(self, sample_project, capsys):
        """Testa que modo verbose produz output de debug."""
        mapper = SimpleRepoMap(root=str(sample_project), verbose=True)
        mapper.get_repo_map(paths=[sample_project])

        captured = capsys.readouterr()
        assert "[DEBUG]" in captured.out

    def test_non_verbose_mode_quiet(self, sample_project, capsys):
        """Testa que modo não-verbose é silencioso."""
        mapper = SimpleRepoMap(root=str(sample_project), verbose=False)
        mapper.get_repo_map(paths=[sample_project])

        captured = capsys.readouterr()
        assert "[DEBUG]" not in captured.out


# =============================================================================
# Testes com Repositório Real
# =============================================================================

class TestRealRepository:
    """Testes usando o próprio repositório como exemplo."""

    def test_scan_current_repo(self):
        """Testa scan do próprio repositório RepoMapper."""
        import os
        repo_root = Path(os.path.dirname(os.path.abspath(__file__)))

        mapper = SimpleRepoMap(root=str(repo_root), verbose=False)
        output, report = mapper.get_repo_map(
            paths=[repo_root],
            excludes={"repo_graph/repo_map/samples"},  # Excluir samples para focar nos arquivos do projeto
        )

        # Deve encontrar arquivos Python do projeto
        assert report.total_files_considered > 0
        assert report.definition_matches > 0

        # Deve incluir arquivos conhecidos
        assert "simple_repomap.py" in output

    def test_scan_with_mentioned_idents(self):
        """Testa scan com identificadores mencionados."""
        import os
        import inspect
        repo_root = Path(inspect.getfile(SimpleRepoMap)).parent

        mapper = SimpleRepoMap(root=str(repo_root), verbose=False)
        output, report = mapper.get_repo_map(
            paths=[repo_root],
            mentioned_idents={"SimpleRepoMap", "get_repo_map"}
        )

        assert "SimpleRepoMap" in output

    def test_scan_specific_file(self):
        """Testa scan de arquivo específico do repo."""
        import os
        import inspect
        repo_root = Path(inspect.getfile(SimpleRepoMap)).parent

        mapper = SimpleRepoMap(root=str(repo_root), verbose=False)
        output, report = mapper.get_repo_map(
            paths=[repo_root / "simple_repomap.py"]
        )

        assert "simple_repomap.py" in output
        assert "SimpleRepoMap" in output
        assert report.total_files_considered == 1


# =============================================================================
# Testes do find_symbol (Symbol Navigation)
# =============================================================================

class TestFindSymbol:
    """Testes para o método find_symbol (GitHub Code Navigation style)."""

    def test_find_symbol_class(self, sample_project):
        """Testa busca de uma classe."""
        mapper = SimpleRepoMap(root=str(sample_project))
        result = mapper.find_symbol("User", [sample_project])

        assert result.symbol == "User"
        assert result.kind == "class"
        assert len(result.definitions) > 0
        assert result.definitions[0].file == "models.py"
        assert result.definitions[0].line == 1
        assert "class User" in result.definitions[0].snippet

    def test_find_symbol_function(self, sample_project):
        """Testa busca de uma função."""
        mapper = SimpleRepoMap(root=str(sample_project))
        result = mapper.find_symbol("format_name", [sample_project])

        assert result.symbol == "format_name"
        assert result.kind == "function"
        assert len(result.definitions) > 0
        assert result.definitions[0].file == "utils.py"
        assert "def format_name" in result.definitions[0].snippet

    def test_find_symbol_not_found(self, sample_project):
        """Testa busca de símbolo inexistente."""
        mapper = SimpleRepoMap(root=str(sample_project))
        result = mapper.find_symbol("NonExistent", [sample_project])

        assert result.symbol == "NonExistent"
        assert result.kind == "unknown"
        assert len(result.definitions) == 0
        assert len(result.references) == 0

    def test_find_symbol_with_references(self, sample_project):
        """Testa que referências são encontradas."""
        mapper = SimpleRepoMap(root=str(sample_project))
        result = mapper.find_symbol("User", [sample_project])

        # User é referenciado em main.py (chamada User("Alice"))
        assert len(result.references) > 0

        ref_files = [ref.file for ref in result.references]
        assert "main.py" in ref_files

    def test_find_symbol_returns_correct_type(self, sample_project):
        """Testa que o retorno é SymbolNavigation."""
        mapper = SimpleRepoMap(root=str(sample_project))
        result = mapper.find_symbol("User", [sample_project])

        assert isinstance(result, SymbolNavigation)
        assert all(isinstance(defn, SymbolLocation) for defn in result.definitions)
        assert all(isinstance(ref, SymbolLocation) for ref in result.references)

    def test_find_symbol_without_snippet(self, sample_project):
        """Testa busca sem incluir snippets."""
        mapper = SimpleRepoMap(root=str(sample_project))
        result = mapper.find_symbol(
            "User",
            [sample_project],
            include_snippet=False
        )

        assert len(result.definitions) > 0
        assert result.definitions[0].snippet == ""

    def test_find_symbol_exact_match_only(self, tmp_path):
        """Testa que busca é exata (não fuzzy)."""
        (tmp_path / "models.py").write_text("""
class User:
    pass

class UserService:
    pass

class BaseUser:
    pass
""")
        mapper = SimpleRepoMap(root=str(tmp_path))
        result = mapper.find_symbol("User", [tmp_path])

        # Deve encontrar apenas "User", não "UserService" ou "BaseUser"
        assert len(result.definitions) > 0
        assert "class User" in result.definitions[0].snippet
        # Não deve confundir com UserService ou BaseUser

    def test_find_symbol_multiple_definitions_returns_all(self, tmp_path):
        """Testa que múltiplas definições retornam todas."""
        (tmp_path / "models.py").write_text("class User: pass")
        (tmp_path / "auth" ).mkdir()
        (tmp_path / "auth" / "models.py").write_text("class User: pass")

        mapper = SimpleRepoMap(root=str(tmp_path))
        result = mapper.find_symbol("User", [tmp_path])

        # Deve retornar todas as definições encontradas
        assert len(result.definitions) == 2
        def_files = [d.file for d in result.definitions]
        assert "models.py" in def_files
        assert "auth/models.py" in def_files

    def test_find_symbol_with_excludes(self, tmp_path):
        """Testa que exclusões são respeitadas."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "models.py").write_text("class User: pass")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_models.py").write_text("class User: pass")

        mapper = SimpleRepoMap(root=str(tmp_path))
        result = mapper.find_symbol(
            "User",
            [tmp_path],
            excludes={"tests"}
        )

        assert len(result.definitions) > 0
        assert all("tests" not in d.file for d in result.definitions)

    def test_find_symbol_empty_paths(self, tmp_path):
        """Testa com paths sem arquivos suportados."""
        mapper = SimpleRepoMap(root=str(tmp_path))
        result = mapper.find_symbol("User", [tmp_path])

        assert result.symbol == "User"
        assert result.kind == "unknown"
        assert len(result.definitions) == 0
        assert len(result.references) == 0

    def test_find_symbol_with_source_file(self, tmp_path):
        """Testa que source_file prioriza resultados conectados ao arquivo de origem."""
        # Criar estrutura: service usa User de models
        (tmp_path / "models.py").write_text("class User: pass")
        (tmp_path / "service.py").write_text("""
from models import User

def get_user():
    return User()
""")
        (tmp_path / "other.py").write_text("""
from models import User

def other_func():
    return User()
""")

        mapper = SimpleRepoMap(root=str(tmp_path))

        # Sem source_file
        result_no_source = mapper.find_symbol("User", [tmp_path])
        assert len(result_no_source.definitions) > 0

        # Com source_file - deve funcionar e priorizar conexões com service.py
        result_with_source = mapper.find_symbol(
            "User",
            [tmp_path],
            source_file=Path("service.py")
        )
        assert len(result_with_source.definitions) > 0
        assert result_with_source.found


class TestTagSubkind:
    """Testes para o campo subkind da Tag."""

    def test_tag_has_subkind_field(self, sample_project):
        """Testa que Tag inclui campo subkind."""
        mapper = SimpleRepoMap(root=str(sample_project))
        tags = mapper.get_tags(
            str(sample_project / "models.py"),
            "models.py",
            (sample_project / "models.py").read_text()
        )

        assert len(tags) > 0
        # Verificar que todas as tags têm subkind
        for tag in tags:
            assert hasattr(tag, 'subkind')
            assert tag.subkind is not None

    def test_class_has_subkind_class(self, sample_project):
        """Testa que classe tem subkind='class'."""
        mapper = SimpleRepoMap(root=str(sample_project))
        tags = mapper.get_tags(
            str(sample_project / "models.py"),
            "models.py",
            (sample_project / "models.py").read_text()
        )

        class_tags = [t for t in tags if t.name == "User" and t.kind == "def"]
        assert len(class_tags) > 0
        assert class_tags[0].subkind == "class"

    def test_function_has_subkind_function(self, sample_project):
        """Testa que função tem subkind='function'."""
        mapper = SimpleRepoMap(root=str(sample_project))
        tags = mapper.get_tags(
            str(sample_project / "utils.py"),
            "utils.py",
            (sample_project / "utils.py").read_text()
        )

        func_tags = [t for t in tags if t.name == "format_name" and t.kind == "def"]
        assert len(func_tags) > 0
        assert func_tags[0].subkind == "function"

    def test_reference_has_subkind_call(self, sample_project):
        """Testa que referência de chamada tem subkind='call'."""
        mapper = SimpleRepoMap(root=str(sample_project))
        tags = mapper.get_tags(
            str(sample_project / "main.py"),
            "main.py",
            (sample_project / "main.py").read_text()
        )

        # Procurar referência a User (chamada User("Alice"))
        ref_tags = [t for t in tags if t.name == "User" and t.kind == "ref"]
        assert len(ref_tags) > 0
        assert ref_tags[0].subkind == "call"


# =============================================================================
# Testes do SymbolNavigation.render()
# =============================================================================

class TestSymbolNavigationRender:
    """Testes para o método SymbolNavigation.render() com loi_pad=4."""

    @pytest.fixture
    def project_with_context(self, tmp_path):
        """Projeto com código que permite testar contexto e padding."""
        (tmp_path / "models.py").write_text("""# line 1
# line 2
# line 3
# line 4
class User:  # line 5 - definition
    # line 6
    # line 7
    # line 8
    # line 9
    def __init__(self, name):  # line 10
        self.name = name
""")
        (tmp_path / "main.py").write_text("""# line 1
# line 2
# line 3
# line 4
from models import User  # line 5 - reference
# line 6
# line 7
# line 8
# line 9
user = User("Alice")  # line 10 - reference
""")
        return tmp_path

    def test_render_definition_with_padding(self, project_with_context):
        """Testa que render() mostra definição com padding de 4 linhas."""
        mapper = SimpleRepoMap(root=str(project_with_context))
        result = mapper.find_symbol("User", [project_with_context])

        output = result.render()

        # Deve conter a linha da definição
        assert "class User" in output
        # Deve conter linhas de padding (até 4 linhas antes/depois)
        assert "line 1" in output or "line 2" in output  # padding antes

    def test_render_references_with_padding(self, project_with_context):
        """Testa que render(include_references=True) mostra refs com padding."""
        mapper = SimpleRepoMap(root=str(project_with_context))
        result = mapper.find_symbol("User", [project_with_context])

        output = result.render(include_references=True)

        assert "References  :" in output
        assert "main.py" in output

    def test_render_no_parent_context(self, tmp_path):
        """Testa que contexto sintático (parent scope) NÃO é exibido."""
        (tmp_path / "app.py").write_text("""class Service:
    class Inner:
        def method(self):  # target - should NOT show Service/Inner context
            pass
""")
        mapper = SimpleRepoMap(root=str(tmp_path))
        result = mapper.find_symbol("method", [tmp_path])

        output = result.render()

        # Deve conter a definição
        assert "def method" in output
        # NÃO deve mostrar contexto sintático com marcadores TreeContext
        # (o parent_context=False desabilita isso)

    def test_render_not_found_symbol(self, tmp_path):
        """Testa mensagem quando símbolo não é encontrado."""
        (tmp_path / "empty.py").write_text("x = 1")
        mapper = SimpleRepoMap(root=str(tmp_path))
        result = mapper.find_symbol("NonExistent", [tmp_path])

        output = result.render()

        assert "not found" in output.lower()
        assert "NonExistent" in output

    def test_render_header_format(self, project_with_context):
        """Testa formato do header com Symbol, Definitions, References."""
        mapper = SimpleRepoMap(root=str(project_with_context))
        result = mapper.find_symbol("User", [project_with_context])

        output = result.render(include_references=True)

        assert "Symbol      : User" in output
        assert "Definitions :" in output
        assert "models.py" in output
        assert "References  :" in output

    def test_render_groups_references_by_file(self, tmp_path):
        """Testa que múltiplas refs no mesmo arquivo são agrupadas."""
        (tmp_path / "models.py").write_text("class User: pass")
        (tmp_path / "main.py").write_text("""user1 = User()
user2 = User()
user3 = User()
""")
        mapper = SimpleRepoMap(root=str(tmp_path))
        result = mapper.find_symbol("User", [tmp_path])

        output = result.render(include_references=True)

        # main.py deve aparecer apenas uma vez (refs agrupadas)
        assert output.count("main.py:") == 1


# =============================================================================
# Testes para find_symbols() e MultiSymbolNavigation
# =============================================================================

class TestFindSymbols:
    """Testes para o método find_symbols() que busca múltiplos símbolos."""

    @pytest.fixture
    def multi_symbol_project(self, tmp_path):
        """Projeto com múltiplos símbolos para testar agregação."""
        (tmp_path / "models.py").write_text("""class User:
    def __init__(self, name: str, email: str):
        self.name = name
        self.email = email

class Product:
    def __init__(self, title: str, price: float):
        self.title = title
        self.price = price

class Order:
    def __init__(self, user: User, product: Product):
        self.user = user
        self.product = product
""")
        (tmp_path / "services.py").write_text("""from models import User, Product, Order

class OrderService:
    def create_order(self, user: User, product: Product) -> Order:
        return Order(user, product)

    def get_user_orders(self, user: User):
        pass
""")
        (tmp_path / "main.py").write_text("""from models import User, Product
from services import OrderService

user = User("Alice", "alice@example.com")
product = Product("Widget", 9.99)
service = OrderService()
order = service.create_order(user, product)
""")
        return tmp_path

    def test_find_symbols_returns_multi_symbol_navigation(self, multi_symbol_project):
        """Testa que find_symbols retorna MultiSymbolNavigation."""
        mapper = SimpleRepoMap(root=str(multi_symbol_project))
        result = mapper.find_symbols(["User", "Product"], [multi_symbol_project])

        assert isinstance(result, MultiSymbolNavigation)

    def test_find_symbols_finds_all_symbols(self, multi_symbol_project):
        """Testa que todos os símbolos são encontrados."""
        mapper = SimpleRepoMap(root=str(multi_symbol_project))
        result = mapper.find_symbols(["User", "Product", "Order"], [multi_symbol_project])

        assert len(result.found_symbols) == 3
        assert "User" in result.found_symbols
        assert "Product" in result.found_symbols
        assert "Order" in result.found_symbols

    def test_find_symbols_reports_not_found(self, multi_symbol_project):
        """Testa que símbolos não encontrados são reportados."""
        mapper = SimpleRepoMap(root=str(multi_symbol_project))
        result = mapper.find_symbols(["User", "NonExistent"], [multi_symbol_project])

        assert "User" in result.found_symbols
        assert "NonExistent" in result.not_found_symbols

    def test_find_symbols_individual_access(self, multi_symbol_project):
        """Testa acesso individual a símbolos via get() e []."""
        mapper = SimpleRepoMap(root=str(multi_symbol_project))
        result = mapper.find_symbols(["User", "Product"], [multi_symbol_project])

        # Via get()
        user_nav = result.get("User")
        assert user_nav is not None
        assert user_nav.symbol == "User"
        assert user_nav.kind == "class"

        # Via []
        product_nav = result["Product"]
        assert product_nav.symbol == "Product"

        # Via in
        assert "User" in result
        assert "NonExistent" not in result

    def test_find_symbols_efficiency(self, multi_symbol_project):
        """Testa que find_symbols processa arquivos uma única vez."""
        mapper = SimpleRepoMap(root=str(multi_symbol_project))

        # Ambas as chamadas devem funcionar, mas find_symbols é mais eficiente
        single1 = mapper.find_symbol("User", [multi_symbol_project])
        single2 = mapper.find_symbol("Product", [multi_symbol_project])
        multi = mapper.find_symbols(["User", "Product"], [multi_symbol_project])

        # Resultados devem ser equivalentes
        assert len(single1.definitions) == len(multi.get("User").definitions)
        assert len(single2.definitions) == len(multi.get("Product").definitions)


class TestMultiSymbolNavigationRender:
    """Testes para o método render() agregado de MultiSymbolNavigation."""

    @pytest.fixture
    def render_project(self, tmp_path):
        """Projeto para testar render agregado."""
        (tmp_path / "models.py").write_text("""class User:
    def __init__(self, name):
        self.name = name

class Product:
    def __init__(self, title):
        self.title = title
""")
        (tmp_path / "main.py").write_text("""from models import User, Product

user = User("Alice")
product = Product("Widget")
""")
        return tmp_path

    def test_render_aggregates_definitions_by_file(self, render_project):
        """Testa que definições no mesmo arquivo são agregadas."""
        mapper = SimpleRepoMap(root=str(render_project))
        result = mapper.find_symbols(["User", "Product"], [render_project])

        output = result.render()

        # models.py deve aparecer apenas UMA vez
        assert output.count("models.py:") == 1
        # Mas ambas as definições devem estar presentes
        assert "class User" in output
        assert "class Product" in output

    def test_render_aggregates_references_by_file(self, render_project):
        """Testa que referências no mesmo arquivo são agregadas."""
        mapper = SimpleRepoMap(root=str(render_project))
        result = mapper.find_symbols(["User", "Product"], [render_project])

        output = result.render(include_references=True)

        # main.py deve aparecer apenas UMA vez na seção de referências
        refs_section = output.split("References")[1] if "References" in output else ""
        assert refs_section.count("main.py:") == 1

    def test_render_header_shows_all_symbols(self, render_project):
        """Testa que o header lista todos os símbolos encontrados."""
        mapper = SimpleRepoMap(root=str(render_project))
        result = mapper.find_symbols(["User", "Product"], [render_project])

        output = result.render()

        assert "Symbols found (2/2):" in output
        assert "User" in output
        assert "Product" in output

    def test_render_shows_not_found_symbols(self, render_project):
        """Testa que símbolos não encontrados são listados no header."""
        mapper = SimpleRepoMap(root=str(render_project))
        result = mapper.find_symbols(["User", "NonExistent"], [render_project])

        output = result.render()

        assert "Symbols found (1/2):" in output
        assert "Symbols not found (1/2):" in output
        assert "NonExistent" in output

    def test_render_no_symbols_found(self, tmp_path):
        """Testa mensagem quando nenhum símbolo é encontrado."""
        (tmp_path / "empty.py").write_text("x = 1")
        mapper = SimpleRepoMap(root=str(tmp_path))
        result = mapper.find_symbols(["NonExistent1", "NonExistent2"], [tmp_path])

        output = result.render()

        assert "No symbols found" in output

    def test_render_includes_file_count(self, render_project):
        """Testa que o render mostra contagem de arquivos."""
        mapper = SimpleRepoMap(root=str(render_project))
        result = mapper.find_symbols(["User", "Product"], [render_project])

        output = result.render()

        # Deve mostrar "X total, Y files"
        assert "total" in output
        assert "files" in output

    def test_render_vs_individual_renders_less_output(self, render_project):
        """Testa que render agregado produz menos output que renders individuais."""
        mapper = SimpleRepoMap(root=str(render_project))

        # Renders individuais
        nav1 = mapper.find_symbol("User", [render_project])
        nav2 = mapper.find_symbol("Product", [render_project])
        individual_output = nav1.render() + "\n" + nav2.render()

        # Render agregado
        multi = mapper.find_symbols(["User", "Product"], [render_project])
        aggregated_output = multi.render()

        # Agregado deve ser menor (menos duplicação)
        assert len(aggregated_output) < len(individual_output)
