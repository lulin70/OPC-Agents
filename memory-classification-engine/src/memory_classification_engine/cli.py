#!/usr/bin/env python3
"""Command-line interface for Memory Classification Engine"""

import argparse
from memory_classification_engine import MemoryClassificationEngine

def main():
    """Main CLI function"""
    parser = argparse.ArgumentParser(description="Memory Classification Engine CLI")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Process command
    process_parser = subparsers.add_parser("process", help="Process a message")
    process_parser.add_argument("message", help="Message to process")
    
    # Retrieve command
    retrieve_parser = subparsers.add_parser("retrieve", help="Retrieve memories")
    retrieve_parser.add_argument("query", nargs="?", help="Query to search for")
    retrieve_parser.add_argument("--limit", type=int, default=5, help="Maximum number of results")
    
    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Get statistics")
    
    # Clear command
    clear_parser = subparsers.add_parser("clear", help="Clear working memory")
    
    args = parser.parse_args()
    
    # Initialize engine
    engine = MemoryClassificationEngine()
    
    if args.command == "process":
        result = engine.process_message(args.message)
        print(f"Message: {args.message}")
        print(f"Matches: {len(result['matches'])}")
        for match in result['matches']:
            print(f"  - {match['memory_type']}: {match['content']} (confidence: {match['confidence']:.2f})")
    
    elif args.command == "retrieve":
        memories = engine.retrieve_memories(args.query, args.limit)
        print(f"Memories matching '{args.query or 'all'}': {len(memories)}")
        for memory in memories:
            print(f"  - {memory['memory_type']}: {memory['content']}")
    
    elif args.command == "stats":
        stats = engine.get_stats()
        print(f"Working memory size: {stats['working_memory_size']}")
        print(f"Tier 2 memories: {stats['tier2']['total_memories']}")
        print(f"Tier 3 memories: {stats['tier3']['total_memories']}")
        print(f"Tier 4 memories: {stats['tier4']['total_relationships']}")
        print(f"Total memories: {stats['total_memories']}")
    
    elif args.command == "clear":
        engine.clear_working_memory()
        print("Working memory cleared")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
