"""Performance test for FTS5 full-text search."""

import time
import tempfile
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from memory_classification_engine.storage.tier3 import Tier3Storage
from memory_classification_engine.storage.tier3_fts import Tier3StorageFTS
from memory_classification_engine.utils.helpers import generate_memory_id

def generate_test_memories(count: int, offset: int = 0) -> list:
    """Generate test memories."""
    memories = []
    templates = [
        "用户喜欢在{time}使用{language}编写{project}项目",
        "用户不喜欢在{project}中使用{tool}",
        "用户偏好使用{style}代码风格",
        "用户要求{requirement}必须满足{standard}",
        "用户习惯在{environment}中进行{action}"
    ]

    words = {
        'time': ['早上', '下午', '晚上', '深夜'],
        'language': ['Python', 'JavaScript', 'Java', 'Go', 'Rust'],
        'project': ['Web应用', '移动应用', '数据分析', '机器学习', '自动化脚本'],
        'tool': ['jQuery', 'Bootstrap', 'Lodash', 'Moment.js'],
        'style': ['PEP 8', 'Google Style', 'Airbnb', 'StandardJS'],
        'requirement': ['性能', '安全性', '可维护性', '可扩展性'],
        'standard': ['行业标准', '公司规范', '最佳实践', '团队约定'],
        'environment': ['VS Code', 'IntelliJ', 'PyCharm', '命令行'],
        'action': ['代码审查', '单元测试', '调试', '重构']
    }

    for i in range(count):
        idx = i + offset
        template = templates[idx % len(templates)]
        content = template.format(
            time=words['time'][idx % len(words['time'])],
            language=words['language'][idx % len(words['language'])],
            project=words['project'][idx % len(words['project'])],
            tool=words['tool'][idx % len(words['tool'])],
            style=words['style'][idx % len(words['style'])],
            requirement=words['requirement'][idx % len(words['requirement'])],
            standard=words['standard'][idx % len(words['standard'])],
            environment=words['environment'][idx % len(words['environment'])],
            action=words['action'][idx % len(words['action'])]
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

def test_performance():
    """Test performance comparison between Tier3Storage and Tier3StorageFTS."""

    # Create temporary directories
    temp_dir = tempfile.mkdtemp()
    storage_path = temp_dir

    print("=" * 80)
    print("FTS5 Performance Test")
    print("=" * 80)

    # Test with different data sizes
    test_sizes = [100, 1000, 5000]

    for size in test_sizes:
        print(f"\n{'='*80}")
        print(f"Testing with {size} memories")
        print(f"{'='*80}")

        # Initialize storages
        storage_regular = Tier3Storage(os.path.join(storage_path, f"regular_{size}"))
        storage_fts = Tier3StorageFTS(os.path.join(storage_path, f"fts_{size}"))
        
        # Generate test data
        print(f"\nGenerating {size} test memories...")
        memories_regular = generate_test_memories(size, offset=0)
        memories_fts = generate_test_memories(size, offset=size)  # Different offset to avoid ID conflicts

        # Test insertion performance
        print(f"\nInsertion Performance:")

        # Regular storage
        start_time = time.time()
        for memory in memories_regular:
            storage_regular.store_memory(memory)
        regular_insert_time = time.time() - start_time
        print(f"  Regular Storage: {regular_insert_time:.3f}s ({size/regular_insert_time:.0f} ops/s)")

        # FTS storage
        start_time = time.time()
        for memory in memories_fts:
            storage_fts.store_memory(memory)
        fts_insert_time = time.time() - start_time
        print(f"  FTS Storage:     {fts_insert_time:.3f}s ({size/fts_insert_time:.0f} ops/s)")
        print(f"  Insertion Overhead: {((fts_insert_time/regular_insert_time - 1) * 100):+.1f}%")
        
        # Test search performance
        print(f"\nSearch Performance (100 queries):")
        
        test_queries = ['Python', 'JavaScript', '代码风格', '性能', 'VS Code', '测试', '重构', 'Web应用']
        
        # Regular storage
        start_time = time.time()
        for _ in range(100):
            for query in test_queries:
                storage_regular.retrieve_memories(query, limit=10)
        regular_search_time = time.time() - start_time
        print(f"  Regular Storage: {regular_search_time:.3f}s ({800/regular_search_time:.0f} queries/s)")
        
        # FTS storage
        start_time = time.time()
        for _ in range(100):
            for query in test_queries:
                storage_fts.retrieve_memories(query, limit=10)
        fts_search_time = time.time() - start_time
        print(f"  FTS Storage:     {fts_search_time:.3f}s ({800/fts_search_time:.0f} queries/s)")
        
        # Calculate speedup
        speedup = regular_search_time / fts_search_time
        print(f"  Speedup: {speedup:.2f}x")
        
        # Test accuracy
        print(f"\nSearch Accuracy Test:")
        query = 'Python'
        regular_results = storage_regular.retrieve_memories(query, limit=10)
        fts_results = storage_fts.retrieve_memories(query, limit=10)
        print(f"  Query: '{query}'")
        print(f"  Regular Storage: {len(regular_results)} results")
        print(f"  FTS Storage:     {len(fts_results)} results")

        # Check if results are similar
        if len(regular_results) > 0 and len(fts_results) > 0:
            regular_content = set(r['content'] for r in regular_results)
            fts_content = set(r['content'] for r in fts_results)
            overlap = len(regular_content.intersection(fts_content))
            print(f"  Result Overlap: {overlap} memories ({overlap/max(len(regular_content), len(fts_content))*100:.1f}%)")
        elif len(fts_results) == 0:
            # Debug: check what memories exist
            all_memories = storage_fts.retrieve_memories(limit=5)
            print(f"  Debug: FTS has {len(all_memories)} total memories")
            if all_memories:
                print(f"    Sample content: {all_memories[0]['content'][:50]}...")
    
    print(f"\n{'='*80}")
    print("Performance Test Completed")
    print(f"{'='*80}")

    # Cleanup
    import shutil
    shutil.rmtree(temp_dir)

if __name__ == '__main__':
    test_performance()
