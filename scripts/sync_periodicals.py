#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import posixpath
import re
import sys
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


def get_r2_client() -> Any:
    import boto3

    endpoint = os.environ.get("R2_ENDPOINT_URL")
    account_id = os.environ.get("R2_ACCOUNT_ID")
    if not endpoint:
        if not account_id:
            raise RuntimeError("Set R2_ACCOUNT_ID or R2_ENDPOINT_URL")
        endpoint = f"https://{account_id}.r2.cloudflarestorage.com"

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


def object_exists(client: Any, bucket: str, key: str) -> bool:
    import botocore

    try:
        client.head_object(Bucket=bucket, Key=key)
        return True
    except botocore.exceptions.ClientError as exc:
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if status == 404:
            return False
        raise


def upload_bytes(client: Any, bucket: str, key: str, data: bytes, content_type: str, dry_run: bool) -> str:
    if dry_run:
        return "dry-run"
    if object_exists(client, bucket, key):
        return "exists"
    client.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)
    return "uploaded"


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
---

# {publication_name} - {title_date}

## Files

{file_links}

## Reading Notes

## Vocabulary

## Highlights
"""


def key_for(config: dict[str, Any], publication_name: str, issue_date: dt.date, filename: str) -> str:
    return posixpath.join(config["output_prefix"], publication_name, issue_date.isoformat(), filename)


def sync_issue(config: dict[str, Any], issue: Issue, client: Any, bucket: str, dry_run: bool) -> None:
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
        if file_format not in allowed_formats:
            continue
        files.append(entry)

    if not files:
        print(f"No matching files found for {publication['name']} {issue.issue_date}", file=sys.stderr)
        return

    uploaded_names: list[str] = []
    for file_entry in files:
        key = key_for(config, publication["name"], issue.issue_date, file_entry["name"])
        data = b"" if dry_run else download_file(file_entry["download_url"])
        content_type = "application/pdf" if file_entry["name"].endswith(".pdf") else "application/epub+zip"
        result = upload_bytes(client, bucket, key, data, content_type, dry_run)
        uploaded_names.append(file_entry["name"])
        print(f"{result}: s3://{bucket}/{key}")

    index_name = f"{publication['name']} {issue.issue_date.isoformat()}.md"
    index_key = key_for(config, publication["name"], issue.issue_date, index_name)
    source_url = issue.source_dir.get("html_url", "")
    index = build_index(publication["name"], issue.issue_date, uploaded_names, source_url).encode("utf-8")
    result = upload_bytes(client, bucket, index_key, index, "text/markdown; charset=utf-8", dry_run)
    print(f"{result}: s3://{bucket}/{index_key}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync selected periodicals from GitHub to Cloudflare R2.")
    parser.add_argument("--config", default="periodicals.json")
    parser.add_argument("--recent", type=int, default=2, help="Recent issues per publication to inspect.")
    parser.add_argument("--dry-run", action="store_true", help="Discover and download metadata without uploading.")
    args = parser.parse_args()

    config = load_config(args.config)
    issues = discover_issues(config, args.recent)
    if not issues:
        print("No issues discovered.", file=sys.stderr)
        return 1

    bucket = os.environ.get("R2_BUCKET", "dry-run-bucket")
    client = None if args.dry_run else get_r2_client()
    for issue in issues:
        sync_issue(config, issue, client, bucket, args.dry_run)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
