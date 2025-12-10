from repo_graph.repo import Repository

# -------------------------
# Example usage
# -------------------------
if __name__ == "__main__":
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(
        prog="repo-deps",
        description="Build python file dependency graph from a repository"
    )

    parser.add_argument(
        "repo",
        help="Path to repository root",
    )

    parser.add_argument(
        "--show-files",
        help="File or directory (relative to repo) to show dependencies/usages for",
        required=True,
    )

    args = parser.parse_args()

    repo_root = Path(args.repo).resolve()
    repo = Repository(repo_root)

    # ------------------------------------------------------------
    # Resolve alvo (arquivo ou diretório)
    # ------------------------------------------------------------
    target = (repo_root / args.show_files).resolve()
    if not target.exists():
        raise ValueError(f"❌ Path not found: {target}")

    # Coletar arquivos a analisar
    filtered_files = repo.list_files(base_dir=args.show_files)

    # ------------------------------------------------------------
    # Execução
    # ------------------------------------------------------------
    print(f"🗂️ Repository: {repo_root}")
    print(f"📂 Target file or directory: {args.show_files}")
    print(f"📄 Total of found files: {len(filtered_files)}")
    print("-" * 60)

    for file in sorted(filtered_files):
        print(f"\n📝 {file.relative_to(repo_root)}")
        print("... | ℹ️ Dependencies:")
        deps = repo.find_dependencies(file)

        if not deps.file_dependencies:
            print("        ⚠️  No dependencies found")
        else:
            for p in deps.file_dependencies:
                print("        ✔", p.relative_to(repo_root))

        print("... | ℹ️ Usages (files that import it):")
        uses = repo.find_usages(file)

        if not uses.file_usages:
            print("        ⚠️  No usages found")
        else:
            for p in uses.file_usages:
                print("        ✔", p.relative_to(repo_root))

    print("\n✔ Finished.")