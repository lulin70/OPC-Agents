"""Test cache warmup functionality."""
import sys
import os
import tempfile
import time
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from memory_classification_engine.storage.tier3_fts import Tier3StorageFTS
from memory_classification_engine.utils.helpers import generate_memory_id


def test_cache_warmup():
    """Test cache warmup functionality."""
    temp_dir = tempfile.mkdtemp()
    print(f"Temp directory: {temp_dir}")

    # Create storage with cache enabled
    storage = Tier3StorageFTS(
        os.path.join(temp_dir, "test"),
        enable_cache=True,
        cache_size=100
    )

    print("\n" + "=" * 80)
    print("Cache Warmup Test")
    print("=" * 80)

    # Insert test memories
    print("\nInserting 50 test memories...")
    for i in range(50):
        memory = {
            'id': generate_memory_id(),
            'type': 'user_preference',
            'content': f'Test memory content {i}',
            'confidence': 0.9,
            'source': 'test'
        }
        storage.store_memory(memory)

    # Check cache stats before warmup
    print("\nCache stats before warmup:")
    stats = storage.get_cache_stats()
    print(f"  Enabled: {stats['enabled']}")
    print(f"  Size: {stats.get('size', 0)}")
    print(f"  Warmup completed: {stats.get('warmup_completed', False)}")

    # Perform warmup
    print("\nPerforming cache warmup (limit=20)...")
    cached_count = storage.warmup_cache(limit=20)
    print(f"  Cached {cached_count} memories")

    # Check cache stats after warmup
    print("\nCache stats after warmup:")
    stats = storage.get_cache_stats()
    print(f"  Size: {stats.get('size', 0)}")
    print(f"  Warmup completed: {stats.get('warmup_completed', False)}")

    # Test cache invalidation
    print("\nTesting cache invalidation...")
    result = storage.invalidate_cache()
    print(f"  Cache cleared: {result}")

    stats = storage.get_cache_stats()
    print(f"  Size after clear: {stats.get('size', 0)}")

    # Test storage without cache
    print("\n" + "=" * 80)
    print("Testing storage without cache")
    print("=" * 80)

    storage_no_cache = Tier3StorageFTS(
        os.path.join(temp_dir, "test_nocache"),
        enable_cache=False
    )

    stats = storage_no_cache.get_cache_stats()
    print(f"\nCache stats: {stats}")

    warmup_result = storage_no_cache.warmup_cache(limit=10)
    print(f"Warmup result (should be 0): {warmup_result}")

    print("\n" + "=" * 80)
    print("Cache Warmup Test Completed")
    print("=" * 80)

    shutil.rmtree(temp_dir)


if __name__ == '__main__':
    test_cache_warmup()
