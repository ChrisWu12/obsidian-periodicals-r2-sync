#!/usr/bin/env python3
import argparse
import datetime as dt
import os
import posixpath
import sys
from typing import Any

from periodicals_common import Issue, build_index, discover_issues, download_file, load_config, matching_issue_files

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


def key_for(config: dict[str, Any], publication_name: str, issue_date: dt.date, filename: str) -> str:
    return posixpath.join(config["output_prefix"], publication_name, issue_date.isoformat(), filename)


def sync_issue(config: dict[str, Any], issue: Issue, client: Any, bucket: str, dry_run: bool) -> None:
    publication = issue.publication
    files = matching_issue_files(config, issue)

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
