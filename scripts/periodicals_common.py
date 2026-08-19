#!/usr/bin/env python3
import datetime as dt
import json
import os
import re
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional


GITHUB_API = "https://api.github.com"


@dataclass(frozen=True)
class Issue:
    publication: dict[str, Any]
    source_dir: dict[str, Any]
    issue_date: dt.date


def load_config(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "periodicals-r2-sync",
    }
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def github_get_json(url: str) -> Any:
    request = urllib.request.Request(url, headers=github_headers())
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def list_github_dir(repo: str, branch: str, path: str) -> list[dict[str, Any]]:
    url = f"{GITHUB_API}/repos/{repo}/contents/{path}?ref={branch}"
    data = github_get_json(url)
    if not isinstance(data, list):
        raise RuntimeError(f"Expected directory listing at {path}")
    return data


def parse_issue_date(name: str, pattern: str) -> Optional[dt.date]:
    match = re.match(pattern, name)
    if not match:
        return None
    year, month, day = match.group(1), match.group(2), match.group(3)
    return dt.date(int(year), int(month), int(day))


def discover_issues(config: dict[str, Any], recent: int) -> list[Issue]:
    repo = config["source_repo"]
    branch = config.get("source_branch", "master")
    issues: list[Issue] = []

    for publication in config["publications"]:
        entries = list_github_dir(repo, branch, publication["source_path"])
        publication_issues: list[Issue] = []
        for entry in entries:
            if entry.get("type") != "dir":
                continue
            issue_date = parse_issue_date(entry["name"], publication["issue_dir_regex"])
            if issue_date:
                publication_issues.append(Issue(publication, entry, issue_date))

        publication_issues.sort(key=lambda item: item.issue_date, reverse=True)
        issues.extend(publication_issues[:recent])

    return issues


def download_file(url: str) -> bytes:
    request = urllib.request.Request(url, headers=github_headers())
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def build_index(publication_name: str, issue_date: dt.date, files: list[str], source_url: str) -> str:
    title_date = issue_date.isoformat()
    file_links = "\n".join(f"- [[{name}]]" for name in files)
    return f"""---
type: periodical
publication: {publication_name}
date: {title_date}
status: unread
source: github-actions
source_url: {source_url}
translation_status: pending
---

# {publication_name} - {title_date}

## Files

{file_links}

## Study Workflow

- [ ] Extract article text
- [ ] Build bilingual English-Chinese note
- [ ] Add vocabulary and useful phrases
- [ ] Review with source PDF/EPUB

## Reading Notes

## Vocabulary

## Highlights
"""


def matching_issue_files(config: dict[str, Any], issue: Issue) -> list[dict[str, Any]]:
    repo = config["source_repo"]
    branch = config.get("source_branch", "master")
    publication = issue.publication
    issue_path = issue.source_dir["path"]
    entries = list_github_dir(repo, branch, issue_path)
    file_pattern = re.compile(publication["file_regex"])
    allowed_formats = set(config.get("formats", ["pdf", "epub"]))

    files = []
    for entry in entries:
        if entry.get("type") != "file":
            continue
        name = entry["name"]
        match = file_pattern.match(name)
        if not match:
            continue
        file_format = match.group(1)
        if file_format in allowed_formats:
            files.append(entry)
    return files

