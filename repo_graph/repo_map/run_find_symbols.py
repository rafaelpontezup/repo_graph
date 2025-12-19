#!/usr/bin/env python3
"""
Script para testar find_symbols (múltiplos símbolos) com samples/crud_app.

Demonstra a busca agregada de múltiplos símbolos com render unificado,
evitando duplicação de arquivos no output.

Gera arquivo de saída em output/find_symbols_yyyyMMdd-HHmmss.out
"""

from datetime import datetime
from pathlib import Path
from simple_repomap import SimpleRepoMap


def main():
    root_dir = Path("samples/crud_app")
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_file = output_dir / f"find_symbols_{timestamp}.out"

    # Buscar múltiplos símbolos de uma vez
    symbols = [
        "User",
        "Product",
        "Order",
        "total_amount",
        "stackspot_ai"    # this symbol does not exist
    ]

    mapper = SimpleRepoMap(root=str(root_dir), verbose=True)
    result = mapper.find_symbols(
        symbols=symbols,
        paths=[root_dir],
        source_file=Path("service/order_service.py"),
    )

    # Gerar output
    output_file.write_text(result.render(include_references=True, show_header=True))


if __name__ == "__main__":
    main()
