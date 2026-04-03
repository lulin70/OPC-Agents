#!/usr/bin/env python3
"""Basic usage example for Memory Classification Engine"""

from memory_classification_engine import MemoryClassificationEngine

def main():
    # Initialize the engine
    engine = MemoryClassificationEngine()
    
    print("Memory Classification Engine - Basic Usage Example")
    print("=" * 60)
    
    # Test message 1: User preference
    print("\n1. Testing user preference:")
    message1 = "记住，我不喜欢在代码中使用破折号"
    result1 = engine.process_message(message1)
    print(f"Message: {message1}")
    print(f"Matches: {len(result1['matches'])}")
    for match in result1['matches']:
        print(f"  - {match['memory_type']}: {match['content']} (confidence: {match['confidence']:.2f})")
    
    # Test message 2: Fact declaration
    print("\n2. Testing fact declaration:")
    message2 = "我们公司有100名员工"
    result2 = engine.process_message(message2)
    print(f"Message: {message2}")
    print(f"Matches: {len(result2['matches'])}")
    for match in result2['matches']:
        print(f"  - {match['memory_type']}: {match['content']} (confidence: {match['confidence']:.2f})")
    
    # Test message 3: Decision
    print("\n3. Testing decision:")
    message3 = "好的，就用这个方案"
    result3 = engine.process_message(message3)
    print(f"Message: {message3}")
    print(f"Matches: {len(result3['matches'])}")
    for match in result3['matches']:
        print(f"  - {match['memory_type']}: {match['content']} (confidence: {match['confidence']:.2f})")
    
    # Test message 4: Correction
    print("\n4. Testing correction:")
    message4 = "不对，应该是这样做"
    result4 = engine.process_message(message4)
    print(f"Message: {message4}")
    print(f"Matches: {len(result4['matches'])}")
    for match in result4['matches']:
        print(f"  - {match['memory_type']}: {match['content']} (confidence: {match['confidence']:.2f})")
    
    # Test memory retrieval
    print("\n5. Testing memory retrieval:")
    query = "代码"
    memories = engine.retrieve_memories(query)
    print(f"Memories matching '{query}': {len(memories)}")
    for memory in memories:
        print(f"  - {memory['memory_type']}: {memory['content']}")
    
    # Test stats
    print("\n6. Testing stats:")
    stats = engine.get_stats()
    print(f"Working memory size: {stats['working_memory_size']}")
    print(f"Tier 2 memories: {stats['tier2']['total_memories']}")
    print(f"Tier 3 memories: {stats['tier3']['total_memories']}")
    print(f"Tier 4 memories: {stats['tier4']['total_relationships']}")
    print(f"Total memories: {stats['total_memories']}")
    
    print("\n" + "=" * 60)
    print("Example completed successfully!")

if __name__ == "__main__":
    main()
