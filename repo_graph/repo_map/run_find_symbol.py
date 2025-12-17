#!/usr/bin/env python3
"""
Script para testar find_symbol com a estrutura de samples/crud_app.

Gera arquivo de saída em output/find_symbol_yyyyMMdd-HHmmss.out
"""

from datetime import datetime
from pathlib import Path
from simple_repomap import SimpleRepoMap

def main():
    root_dir = Path("samples/crud_app")
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_file = output_dir / f"find_symbol_{timestamp}.out"

    mapper = SimpleRepoMap(root=str(root_dir), verbose=False)
    result = mapper.find_symbol(
        symbol="total_amount",
        paths=[root_dir],
        source_file=Path("service/order_service.py")  # arquivo de origem
    )

    output_file.write_text(result.render(include_references=True, show_header=True))


if __name__ == "__main__":
    main()
