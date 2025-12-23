"""
Testes de Snapshot para SimpleRepoMap.

Estes testes comparam a saída gerada com arquivos de referência (snapshots)
para detectar mudanças sutis na implementação do SimpleRepoMap.

Os snapshots foram gerados a partir dos scripts run_*.py em repo_graph/repo_map/
usando samples/crud_app como base.

Execute com: pytest tests/repo_map/test_simple_repomap_snapshots.py -v
"""

from pathlib import Path

import pytest

from repo_graph.repo_map.simple_repomap import SimpleRepoMap


# =============================================================================
# Fixtures compartilhadas
# =============================================================================

@pytest.fixture
def crud_app_path():
    """Caminho para samples/crud_app."""
    return Path(__file__).parent.parent.parent / "repo_graph" / "repo_map" / "samples" / "crud_app"


@pytest.fixture
def snapshots_dir():
    """Caminho para diretório de snapshots."""
    return Path(__file__).parent / "snapshots"


# =============================================================================
# Testes de Snapshot - find_symbol
# =============================================================================

class TestSnapshotFindSymbol:
    """
    Testes de snapshot para find_symbol usando samples/crud_app.

    Para atualizar os snapshots após mudanças intencionais:
        cp tests/repo_map/snapshots/actual_find_symbol.out tests/repo_map/snapshots/expected_find_symbol.out
    """

    def test_find_symbol_total_amount_matches_snapshot(self, crud_app_path, snapshots_dir):
        """
        Testa que find_symbol('total_amount') gera saída idêntica ao snapshot.

        Este teste reproduz o cenário do script run_find_symbol.py:
        - Busca o símbolo 'total_amount'
        - source_file=service/order_service.py
        - include_references=True, show_header=True
        """
        mapper = SimpleRepoMap(root=str(crud_app_path), verbose=False)
        result = mapper.find_symbol(
            symbol="total_amount",
            paths=[crud_app_path],
            source_file=Path("service/order_service.py")
        )

        actual_output = result.render(include_references=True, show_header=True)
        expected_output = (snapshots_dir / "expected_find_symbol.out").read_text()

        # Salvar output atual para debug em caso de falha
        actual_file = snapshots_dir / "actual_find_symbol.out"
        actual_file.write_text(actual_output)

        assert actual_output == expected_output, (
            f"Output diverge do snapshot esperado.\n"
            f"Para ver diferenças: diff {snapshots_dir}/expected_find_symbol.out {snapshots_dir}/actual_find_symbol.out\n"
            f"Para atualizar snapshot: cp {snapshots_dir}/actual_find_symbol.out {snapshots_dir}/expected_find_symbol.out"
        )


# =============================================================================
# Testes de Snapshot - find_symbols
# =============================================================================

class TestSnapshotFindSymbols:
    """
    Testes de snapshot para find_symbols usando samples/crud_app.

    Para atualizar os snapshots após mudanças intencionais:
        cp tests/repo_map/snapshots/actual_find_symbols.out tests/repo_map/snapshots/expected_find_symbols.out
    """

    def test_find_symbols_multiple_matches_snapshot(self, crud_app_path, snapshots_dir):
        """
        Testa que find_symbols() para múltiplos símbolos gera saída idêntica ao snapshot.

        Este teste reproduz o cenário do script run_find_symbols.py:
        - Busca símbolos: User, Product, Order, total_amount, stackspot_ai
        - source_file=service/order_service.py
        - include_references=True, show_header=True
        """
        symbols = [
            "User",
            "Product",
            "Order",
            "total_amount",
            "stackspot_ai"  # símbolo que não existe
        ]

        mapper = SimpleRepoMap(root=str(crud_app_path), verbose=False)
        result = mapper.find_symbols(
            symbols=symbols,
            paths=[crud_app_path],
            source_file=Path("service/order_service.py"),
        )

        actual_output = result.render(include_references=True, show_header=True)
        expected_output = (snapshots_dir / "expected_find_symbols.out").read_text()

        # Salvar output atual para debug em caso de falha
        actual_file = snapshots_dir / "actual_find_symbols.out"
        actual_file.write_text(actual_output)

        assert actual_output == expected_output, (
            f"Output diverge do snapshot esperado.\n"
            f"Para ver diferenças: diff {snapshots_dir}/expected_find_symbols.out {snapshots_dir}/actual_find_symbols.out\n"
            f"Para atualizar snapshot: cp {snapshots_dir}/actual_find_symbols.out {snapshots_dir}/expected_find_symbols.out"
        )


# =============================================================================
# Testes de Snapshot - get_repo_map
# =============================================================================

class TestSnapshotGetRepoMap:
    """
    Testes de snapshot para get_repo_map usando samples/crud_app.

    Para atualizar os snapshots após mudanças intencionais:
        cp tests/repo_map/snapshots/actual_simple_repomap.out tests/repo_map/snapshots/expected_simple_repomap.out
    """

    def test_get_repo_map_matches_snapshot(self, crud_app_path, snapshots_dir):
        """
        Testa que get_repo_map() gera saída idêntica ao snapshot.

        Este teste reproduz o cenário do script run_simple_repomap.py:
        - max_map_tokens=4000
        - chat_fnames={"service/order_service.py"}
        - mentioned_idents={"User", "OrderService"}
        """
        mapper = SimpleRepoMap(root=str(crud_app_path), max_map_tokens=4000, verbose=False)
        repo_map, report = mapper.get_repo_map(
            paths=[crud_app_path],
            chat_fnames={"service/order_service.py"},
            mentioned_idents={"User", "OrderService"},
        )

        actual_output = repo_map
        expected_output = (snapshots_dir / "expected_simple_repomap.out").read_text()

        # Salvar output atual para debug em caso de falha
        actual_file = snapshots_dir / "actual_simple_repomap.out"
        actual_file.write_text(actual_output)

        assert actual_output == expected_output, (
            f"Output diverge do snapshot esperado.\n"
            f"Para ver diferenças: diff {snapshots_dir}/expected_simple_repomap.out {snapshots_dir}/actual_simple_repomap.out\n"
            f"Para atualizar snapshot: cp {snapshots_dir}/actual_simple_repomap.out {snapshots_dir}/expected_simple_repomap.out"
        )
