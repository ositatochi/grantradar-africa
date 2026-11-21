from typing import TypedDict


class SnapshotItem(TypedDict):
    source_id: int
    source_run_id: int
    url: str
    canonical_url: str
    content: bytes
    content_type: str
    status_code: int
    etag: str
    last_modified: str
