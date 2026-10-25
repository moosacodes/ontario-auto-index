from __future__ import annotations

import hashlib


def shard_for(dealer_id: str, shard_count: int) -> int:
    if shard_count < 1:
        raise ValueError("shard_count must be positive")
    digest = hashlib.sha256(dealer_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % shard_count
