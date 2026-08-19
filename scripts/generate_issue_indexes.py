#!/usr/bin/env python3
import argparse
import html
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from periodicals_common import load_config


DEFAULT_LIBRARY = "/Users/chris/Documents/Periodicals Library"
DEFAULT_VAULT = "/Users/chris/Desktop/Obsidian Vault"
DEFAULT_STUDY_PREFIX = "外刊学习"

SECTION_HEADINGS = {
    "leaders",
    "letters",
    "by invitation",
    "briefing",
    "asia",
    "china",
    "united states",
    "the americas",
    "middle east & africa",
    "europe",
    "britain",
    "international",
    "business",
    "finance & economics",
    "science & technology",
    "culture",
    "economic & financial indicators",
    "obituary",
}


@dataclass(frozen=True)
class TocEntry:
    number: str
    title: str
    source: str


def safe_stem(title: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]", " ", title)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:140]


def find_epub(issue_dir: Path) -> Optional[Path]:
    epubs = sorted(issue_dir.glob("*.epub"))
    return epubs[0] if epubs else None


def read_toc(epub: Path) -> list[tuple[str, str]]:
    with zipfile.ZipFile(epub) as z:
        toc_name = "EPUB/toc.ncx" if "EPUB/toc.ncx" in z.namelist() else "toc.ncx"
        root = ET.fromstring(z.read(toc_name))

    ns = {"n": "http://www.daisy.org/z3986/2005/ncx/"}
    raw_entries: list[tuple[str, str]] = []
    for nav in root.findall(".//n:navPoint", ns):
        text_node = nav.find(".//n:text", ns)
        content_node = nav.find("n:content", ns)
        if text_node is None or content_node is None:
            continue
        title = html.unescape("".join(text_node.itertext()).strip())
        source = content_node.attrib.get("src", "").split("#", 1)[0]
        if title and source:
            raw_entries.append((title, source))
    return raw_entries


def article_entries(epub: Path) -> list[TocEntry]:
    raw = read_toc(epub)
    articles: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for idx, (title, source) in enumerate(raw):
        normalized = title.lower()
        next_source = raw[idx + 1][1] if idx + 1 < len(raw) else None
        if normalized in SECTION_HEADINGS:
            continue
        if next_source == source:
            continue
        key = (title, source)
        if key in seen:
            continue
        seen.add(key)
        articles.append((title, source))

    return [TocEntry(f"{idx:02d}", title, source) for idx, (title, source) in enumerate(articles, 1)]


def safe_study_dir(vault: Path, study_prefix: str, publication: str, issue_date: str) -> Path:
    vault_real = vault.resolve()
    target = (vault_real / study_prefix / publication / issue_date).resolve()
    allowed_root = (vault_real / study_prefix).resolve()
    if os.path.commonpath([str(allowed_root), str(target)]) != str(allowed_root):
        raise RuntimeError(f"Refusing to write outside {allowed_root}")
    return target


def issue_dirs_for(publication_dir: Path, recent: int) -> list[Path]:
    dirs = [p for p in publication_dir.iterdir() if p.is_dir() and re.match(r"^\d{4}-\d{2}-\d{2}$", p.name)]
    dirs.sort(key=lambda p: p.name, reverse=True)
    return dirs[:recent]


def render_index(publication: str, issue_date: str, source_dir: Path, entries: list[TocEntry]) -> str:
    rows = []
    queue = []
    for entry in entries:
        note_name = f"{entry.number} {safe_stem(entry.title)} bilingual"
        rows.append(f"| {entry.number} | {entry.title} | [[{note_name}]] | `{entry.source}` |")
        queue.append(f"- [ ] {entry.number} {entry.title}")

    return f"""---
type: periodical_study_index
publication: {publication}
issue_date: {issue_date}
source_library: {source_dir}
status: in_progress
---

# {publication} - {issue_date}

## Source

Original PDF/EPUB are kept outside the Obsidian Vault:

```text
{source_dir}
```

## How To Request Processing

Tell Codex:

```text
处理 {publication} {issue_date} 编号 01, 03, 05
```

## Article Directory

| No. | Article | Target note | EPUB source |
|---|---|---|---|
{chr(10).join(rows)}

## Processing Queue

{chr(10).join(queue)}
"""


def write_issue_index(vault: Path, study_prefix: str, publication: str, issue_dir: Path, dry_run: bool) -> None:
    epub = find_epub(issue_dir)
    if not epub:
        print(f"skip: no epub in {issue_dir}")
        return

    entries = article_entries(epub)
    target_dir = safe_study_dir(vault, study_prefix, publication, issue_dir.name)
    target = target_dir / "00 Issue Index.md"
    content = render_index(publication, issue_dir.name, issue_dir, entries)

    if dry_run:
        print(f"dry-run: {target} ({len(entries)} articles)")
        return

    target_dir.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    print(f"updated: {target} ({len(entries)} articles)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate numbered Obsidian issue indexes from local EPUB files.")
    parser.add_argument("--config", default="periodicals.json")
    parser.add_argument("--library", default=DEFAULT_LIBRARY)
    parser.add_argument("--vault", default=DEFAULT_VAULT)
    parser.add_argument("--study-prefix", default=DEFAULT_STUDY_PREFIX)
    parser.add_argument("--recent", type=int, default=2, help="Recent local issues per publication to index.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config = load_config(args.config)
    library = Path(args.library)
    vault = Path(args.vault)

    for publication in config["publications"]:
        publication_name = publication["name"]
        publication_dir = library / publication_name
        if not publication_dir.exists():
            print(f"skip: missing {publication_dir}")
            continue
        for issue_dir in issue_dirs_for(publication_dir, args.recent):
            write_issue_index(vault, args.study_prefix, publication_name, issue_dir, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
