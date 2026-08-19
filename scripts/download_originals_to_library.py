#!/usr/bin/env python3
import argparse
import os
from pathlib import Path

from periodicals_common import build_index, discover_issues, download_file, load_config, matching_issue_files


DEFAULT_LIBRARY = "/Users/chris/Documents/Periodicals Library"


def safe_output_dir(library: Path, publication: str, issue_date: str) -> Path:
    library_real = library.resolve()
    target = (library_real / publication / issue_date).resolve()
    if os.path.commonpath([str(library_real), str(target)]) != str(library_real):
        raise RuntimeError(f"Refusing to write outside {library_real}")
    return target


def write_file(path: Path, data: bytes, dry_run: bool) -> str:
    if path.exists():
        return "exists"
    if dry_run:
        return "dry-run"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return "downloaded"


def write_text_file(path: Path, text: str, dry_run: bool) -> str:
    if path.exists():
        return "exists"
    if dry_run:
        return "dry-run"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return "created"


def download_issue(config: dict, issue, library: Path, dry_run: bool) -> None:
    publication = issue.publication["name"]
    issue_date = issue.issue_date.isoformat()
    target_dir = safe_output_dir(library, publication, issue_date)
    files = matching_issue_files(config, issue)

    if not files:
        print(f"No matching files found for {publication} {issue_date}")
        return

    file_names = []
    for entry in files:
        file_names.append(entry["name"])
        target = target_dir / entry["name"]
        data = b"" if dry_run else download_file(entry["download_url"])
        result = write_file(target, data, dry_run)
        print(f"{result}: {target}")

    index_name = f"{publication} {issue_date}.md"
    index = build_index(publication, issue.issue_date, file_names, issue.source_dir.get("html_url", ""))
    result = write_text_file(target_dir / index_name, index, dry_run)
    print(f"{result}: {target_dir / index_name}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Download periodical originals into a local Mac library.")
    parser.add_argument("--config", default="periodicals.json")
    parser.add_argument("--library", default=DEFAULT_LIBRARY)
    parser.add_argument("--recent", type=int, default=1, help="Recent issues per publication to inspect.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned writes without downloading files.")
    args = parser.parse_args()

    library = Path(args.library)
    if not args.dry_run:
        library.mkdir(parents=True, exist_ok=True)

    config = load_config(args.config)
    issues = discover_issues(config, args.recent)
    for issue in issues:
        download_issue(config, issue, library, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

