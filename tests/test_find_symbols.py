import os
import unittest
from pathlib import Path
from typing import override

from repo_graph.repo import FileUsages


class FindSimbolsTest(unittest.TestCase):

    maxDiff = None

    @override
    def setUp(self):
        tests_dir = Path(__file__).parent
        self.RESOURCES_DIR = tests_dir / "resources"
        self.USE_CASES_DIR = self.RESOURCES_DIR / "use_cases"

    def test_find_symbols_from_file_usages(self):
        # scenario
        file_usages = FileUsages(
            source_file=self.USE_CASES_DIR / "find_symbol_usages_1/model.py",
            file_usages=[
                self.USE_CASES_DIR / "find_symbol_usages_1/handler.py",
                self.USE_CASES_DIR / "find_symbol_usages_1/service.py",
            ]
        )

        # action
        symbol_usages = file_usages.find_symbol_references(qualified_name="User.email")
        symbol_usages.pretty_print()

        # validation
        self.assertEqual("User.email", symbol_usages.symbol_name)
        self.assertEqual(file_usages.source_file, symbol_usages.definition_location.file_path)
        self.assertEqual(6, len(symbol_usages.references))  # add assertion here
        self.assertEqual(
            4,
            len([ref for ref in symbol_usages.references if ref.location.file_path.name == "handler.py"])
        )
        self.assertEqual(
            2,
            len([ref for ref in symbol_usages.references if ref.location.file_path.name == "service.py"])
        )

