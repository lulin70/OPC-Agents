"""Test FTS5 with English-only content."""
import sys
import os
import tempfile
import time
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from memory_classification_engine.storage.tier3 import Tier3Storage
from memory_classification_engine.storage.tier3_fts import Tier3StorageFTS
from memory_classification_engine.utils.helpers import generate_memory_id

def generate_english_memories(count: int, offset: int = 0) -> list:
    """Generate English test memories."""
    memories = []
    templates = [
        "User likes to use {language} for {project} projects",
        "User prefers {style} coding style in {language}",
        "User requires {requirement} for all {project} work",
        "User works with {language} in {environment}",
        "User focuses on {requirement} when using {language}"
    ]

    words = {
        'language': ['Python', 'JavaScript', 'Java', 'Go', 'Rust', 'TypeScript', 'C++'],
        'project': ['web', 'mobile', 'data analysis', 'machine learning', 'automation'],
        'style': ['PEP 8', 'Google Style', 'Airbnb', 'StandardJS', 'clean code'],
        'requirement': ['performance', 'security', 'maintainability', 'scalability'],
        'environment': ['VS Code', 'IntelliJ', 'PyCharm', 'command line', 'vim']
    }

    for i in range(count):
        idx = i + offset
        template = templates[idx % len(templates)]
        content = template.format(
            language=words['language'][idx % len(words['language'])],
            project=words['project'][idx % len(words['project'])],
            style=words['style'][idx % len(words['style'])],
            requirement=words['requirement'][idx % len(words['requirement'])],
            environment=words['environment'][idx % len(words['environment'])]
        )

        memory = {
            'id': generate_memory_id(),
            'type': 'user_preference' if idx % 2 == 0 else 'fact_declaration',
            'content': content,
            'confidence': 0.8 + (idx % 20) / 100,
            'source': 'test'
        }
        memories.append(memory)

    return memories

def test_english_performance():
    """Test performance with English content."""
    temp_dir = tempfile.mkdtemp()

    print("=" * 80)
    print("FTS5 Performance Test (English Content)")
    print("=" * 80)

    test_sizes = [100, 1000, 5000]

    for size in test_sizes:
        print(f"\n{'='*80}")
        print(f"Testing with {size} memories")
        print(f"{'='*80}")

        storage_regular = Tier3Storage(os.path.join(temp_dir, f"regular_{size}"))
        storage_fts = Tier3StorageFTS(os.path.join(temp_dir, f"fts_{size}"))

        print(f"\nGenerating {size} English test memories...")
        memories_regular = generate_english_memories(size, offset=0)
        memories_fts = generate_english_memories(size, offset=size)

        # Insertion performance
        print(f"\nInsertion Performance:")

        start_time = time.time()
        for memory in memories_regular:
            storage_regular.store_memory(memory)
        regular_insert_time = time.time() - start_time
        print(f"  Regular Storage: {regular_insert_time:.3f}s ({size/regular_insert_time:.0f} ops/s)")

        start_time = time.time()
        for memory in memories_fts:
            storage_fts.store_memory(memory)
        fts_insert_time = time.time() - start_time
        print(f"  FTS Storage:     {fts_insert_time:.3f}s ({size/fts_insert_time:.0f} ops/s)")
        print(f"  Insertion Overhead: {((fts_insert_time/regular_insert_time - 1) * 100):+.1f}%")

        # Check stats
        stats = storage_fts.get_stats()
        print(f"\nFTS Storage Stats:")
        print(f"  Total memories: {stats['total_memories']}")
        print(f"  FTS indexed: {stats['fts_indexed']}")

        # Search performance
        print(f"\nSearch Performance (100 queries):")
        test_queries = ['Python', 'JavaScript', 'performance', 'VS Code', 'web', 'security']

        start_time = time.time()
        for _ in range(100):
            for query in test_queries:
                storage_regular.retrieve_memories(query, limit=10)
        regular_search_time = time.time() - start_time
        print(f"  Regular Storage: {regular_search_time:.3f}s ({600/regular_search_time:.0f} queries/s)")

        start_time = time.time()
        for _ in range(100):
            for query in test_queries:
                storage_fts.retrieve_memories(query, limit=10)
        fts_search_time = time.time() - start_time
        print(f"  FTS Storage:     {fts_search_time:.3f}s ({600/fts_search_time:.0f} queries/s)")

        speedup = regular_search_time / fts_search_time
        print(f"  Speedup: {speedup:.2f}x")

        # Search accuracy
        print(f"\nSearch Accuracy Test:")
        query = 'Python'
        regular_results = storage_regular.retrieve_memories(query, limit=10)
        fts_results = storage_fts.retrieve_memories(query, limit=10)
        print(f"  Query: '{query}'")
        print(f"  Regular Storage: {len(regular_results)} results")
        print(f"  FTS Storage:     {len(fts_results)} results")

        if fts_results:
            print(f"  Sample FTS result: {fts_results[0]['content'][:60]}...")

    print(f"\n{'='*80}")
    print("Performance Test Completed")
    print(f"{'='*80}")

    shutil.rmtree(temp_dir)

if __name__ == '__main__':
    test_english_performance()
