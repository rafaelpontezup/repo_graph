#!/usr/bin/env python3
"""
Script para testar get_repo_map com a estrutura de samples/crud_app.

Gera arquivo de saída em output/simple_repomap_yyyyMMdd-HHmmss.out
"""

from datetime import datetime
from pathlib import Path
from simple_repomap import SimpleRepoMap


def main():
    samples_dir = Path(__file__).parent / Path("samples/crud_app")
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_file = output_dir / f"simple_repomap_{timestamp}.out"

    mapper = SimpleRepoMap(root=str(samples_dir), max_map_tokens=4000)
    repo_map, report = mapper.get_repo_map(
        paths=[samples_dir],
        chat_fnames={"service/order_service.py"},
        mentioned_idents={"User", "OrderService"},
    )

    output_file.write_text(repo_map)

    print(f"Output written to: {output_file}")
    print(f"Files processed: {report.total_files_considered}")


if __name__ == "__main__":
    main()
