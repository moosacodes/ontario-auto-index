import pytest

from ontario_auto_index.sharding import shard_for


def test_sharding_is_deterministic_and_bounded() -> None:
    assert shard_for("dealer-1", 4) == shard_for("dealer-1", 4)
    assert 0 <= shard_for("dealer-1", 4) < 4


def test_sharding_rejects_invalid_count() -> None:
    with pytest.raises(ValueError):
        shard_for("dealer-1", 0)
