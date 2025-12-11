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

    def test_find_class_and_attributes_references(self):
        # scenario
        file_usages = FileUsages(
            source_file=self.USE_CASES_DIR / "find_class_and_attributes_usages_1/model.py",
            file_usages=[
                self.USE_CASES_DIR / "find_class_and_attributes_usages_1/handler.py",
                self.USE_CASES_DIR / "find_class_and_attributes_usages_1/service.py",
            ]
        )

        # action
        symbol_usages = file_usages.find_symbol_references(qualified_name="class:User.email")
        symbol_usages.pretty_print()

        # validation
        self.assertEqual("class:User.email", symbol_usages.symbol_name)
        self.assertEqual(file_usages.source_file, symbol_usages.definition_location.file_path)
        self.assertEqual(6, len(symbol_usages.references))
        self.assertEqual(4, len(symbol_usages.find_references_of("handler.py")))
        self.assertEqual(2, len(symbol_usages.find_references_of("service.py")))

    def test_find_class_references(self):
        # scenario: User definida em model.py, usada em service.py e handler.py
        file_usages = FileUsages(
            source_file=self.USE_CASES_DIR / "find_class_and_attributes_usages_1/model.py",
            file_usages=[
                self.USE_CASES_DIR / "find_class_and_attributes_usages_1/handler.py",
                self.USE_CASES_DIR / "find_class_and_attributes_usages_1/service.py",
            ]
        )

        # action
        symbol_usages = file_usages.find_symbol_references(qualified_name="class:User")
        symbol_usages.pretty_print()

        # validation
        self.assertEqual("class:User", symbol_usages.symbol_name)
        self.assertEqual(file_usages.source_file, symbol_usages.definition_location.file_path)
        self.assertEqual(10, len(symbol_usages.references))
        self.assertEqual(4, len(symbol_usages.find_references_of("handler.py")))
        self.assertEqual(6, len(symbol_usages.find_references_of("service.py")))

    def test_find_function_calls(self):
        # scenario: validate_cnpj() definida em validator.py, chamada em service.py e handler.py
        file_usages = FileUsages(
            source_file=self.USE_CASES_DIR / "find_function_calls_1/validator.py",
            file_usages=[
                self.USE_CASES_DIR / "find_function_calls_1/service.py",
                self.USE_CASES_DIR / "find_function_calls_1/handler.py",
            ]
        )

        # action
        symbol_usages = file_usages.find_symbol_references(qualified_name="function:validate_cnpj")
        symbol_usages.pretty_print()

        # validation
        self.assertEqual("function:validate_cnpj", symbol_usages.symbol_name)
        self.assertEqual(file_usages.source_file, symbol_usages.definition_location.file_path)
        self.assertEqual(3, len(symbol_usages.references))  # 1 em service.py, 2 em handler.py
        self.assertEqual(1, len(symbol_usages.find_references_of("service.py")))
        self.assertEqual(2, len(symbol_usages.find_references_of("handler.py")))

