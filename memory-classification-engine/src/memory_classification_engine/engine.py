import os
from typing import Dict, List, Optional, Any
from memory_classification_engine.utils.config import ConfigManager
from memory_classification_engine.utils.helpers import generate_memory_id, get_current_time
from memory_classification_engine.utils.logger import logger
from memory_classification_engine.layers.rule_matcher import RuleMatcher
from memory_classification_engine.layers.pattern_analyzer import PatternAnalyzer
from memory_classification_engine.layers.semantic_classifier import SemanticClassifier
from memory_classification_engine.storage.tier2 import Tier2Storage
from memory_classification_engine.storage.tier3 import Tier3Storage
from memory_classification_engine.storage.tier4 import Tier4Storage
from memory_classification_engine.utils.exceptions import (
    MemoryEngineError,
    StorageError,
    MemoryNotFoundError,
    ConfigurationError
)

class MemoryClassificationEngine:
    """Memory Classification Engine."""
    
    def __init__(self, config_path: str = None):
        """Initialize the memory classification engine.
        
        Args:
            config_path: Path to the configuration file.
        """
        # Load configuration
        self.config = ConfigManager(config_path)
        
        # Initialize storage
        storage_path = self.config.get('storage.data_path', './data')
        os.makedirs(storage_path, exist_ok=True)
        
        self.tier2_storage = Tier2Storage(self.config.get('storage.tier2_path', './data/tier2'))
        self.tier3_storage = Tier3Storage(self.config.get('storage.tier3_path', './data/tier3'))
        self.tier4_storage = Tier4Storage(self.config.get('storage.tier4_path', './data/tier4'))
        
        # Initialize working memory
        self.working_memory = []
        self.max_work_memory_size = self.config.get('storage.max_work_memory_size', 100)
        
        # Initialize layers
        rules = self.config.get_rules().get('rules', [])
        self.rule_matcher = RuleMatcher(rules)
        self.pattern_analyzer = PatternAnalyzer()
        
        llm_enabled = self.config.get('llm.enabled', False)
        api_key = self.config.get('llm.api_key', '')
        self.semantic_classifier = SemanticClassifier(llm_enabled, api_key)
        
        # Initialize memory management
        self.forgetting_enabled = self.config.get('memory.forgetting.enabled', True)
        self.decay_factor = self.config.get('memory.forgetting.decay_factor', 0.9)
        self.min_weight = self.config.get('memory.forgetting.min_weight', 0.1)
        self.archive_interval = self.config.get('memory.forgetting.archive_interval', 86400)  # 24 hours
        
        self.deduplication_enabled = self.config.get('memory.deduplication.enabled', True)
        self.similarity_threshold = self.config.get('memory.deduplication.similarity_threshold', 0.8)
        
        self.conflict_resolution_strategy = self.config.get('memory.conflict_resolution.strategy', 'latest')
        
        # Initialize last archive time
        self.last_archive_time = get_current_time()
        
        # Initialize cache
        self.cache = {}
        self.cache_size = 1000  # Maximum cache size
        self.cache_ttl = 3600  # Cache time-to-live in seconds
        
        # Run initial archive
        self._run_archive()
    
    def _run_archive(self):
        """Run memory archive process to remove low-weight memories."""
        if not self.forgetting_enabled:
            return
        
        # Archive tier 2 memories
        self._archive_tier2_memories()
        
        # Archive tier 3 memories
        self._archive_tier3_memories()
        
        # Archive tier 4 memories
        self._archive_tier4_memories()
        
        # Clear cache since memories were archived
        self._clear_cache()
        
        # Update last archive time
        self.last_archive_time = get_current_time()
    
    def _archive_tier2_memories(self):
        """Archive low-weight memories in tier 2."""
        memories = self.tier2_storage.retrieve_memories()
        for memory in memories:
            weight = self._calculate_memory_weight(memory)
            if weight < self.min_weight:
                self.tier2_storage.delete_memory(memory.get('id'))
    
    def _archive_tier3_memories(self):
        """Archive low-weight memories in tier 3."""
        memories = self.tier3_storage.retrieve_memories()
        for memory in memories:
            weight = self._calculate_memory_weight(memory)
            if weight < self.min_weight:
                self.tier3_storage.delete_memory(memory.get('id'))
    
    def _archive_tier4_memories(self):
        """Archive low-weight memories in tier 4."""
        memories = self.tier4_storage.retrieve_memories()
        for memory in memories:
            weight = self._calculate_memory_weight(memory)
            if weight < self.min_weight:
                self.tier4_storage.delete_memory(memory.get('id'))
    
    def _calculate_memory_weight(self, memory: Dict[str, Any]) -> float:
        """Calculate memory weight based on confidence, recency, and frequency.
        
        Args:
            memory: The memory to calculate weight for.
            
        Returns:
            The calculated weight.
        """
        from datetime import datetime, timezone
        
        # Get memory properties
        confidence = memory.get('confidence', 1.0)
        last_accessed = memory.get('last_accessed', memory.get('created_at', get_current_time()))
        access_count = memory.get('access_count', 1)
        
        # Calculate days since last access
        try:
            last_accessed_dt = datetime.fromisoformat(last_accessed.replace('Z', '+00:00'))
            current_dt = datetime.now(timezone.utc)
            days_since_last_access = (current_dt - last_accessed_dt).days
        except:
            days_since_last_access = 30  # Default to 30 days if parsing fails
        
        # Exponential decay for recency
        recency_score = 2 ** (-0.1 * days_since_last_access)
        
        # Logarithmic growth for frequency (边际递减)
        frequency_score = 1 + 0.5 * (access_count ** 0.5)
        
        # Calculate final weight
        weight = confidence * recency_score * frequency_score
        
        return weight
    
    def _check_archive_time(self):
        """Check if it's time to run the archive process."""
        from datetime import datetime, timezone, timedelta
        
        try:
            last_archive_dt = datetime.fromisoformat(self.last_archive_time.replace('Z', '+00:00'))
            current_dt = datetime.now(timezone.utc)
            time_since_last_archive = (current_dt - last_archive_dt).total_seconds()
            
            if time_since_last_archive >= self.archive_interval:
                self._run_archive()
        except Exception as e:
            logger.error(f"Error checking archive time: {e}", exc_info=True)
            # Run archive anyway if there's an error
            self._run_archive()
    
    def _get_from_cache(self, key: str) -> Optional[Any]:
        """Get value from cache.
        
        Args:
            key: Cache key.
            
        Returns:
            Cached value or None if not found or expired.
        """
        from datetime import datetime, timezone
        
        if key not in self.cache:
            return None
        
        cached_item = self.cache[key]
        stored_time = cached_item['timestamp']
        value = cached_item['value']
        
        # Check if cache is expired
        try:
            stored_dt = datetime.fromisoformat(stored_time.replace('Z', '+00:00'))
            current_dt = datetime.now(timezone.utc)
            time_since_stored = (current_dt - stored_dt).total_seconds()
            
            if time_since_stored > self.cache_ttl:
                del self.cache[key]
                return None
            
            return value
        except Exception as e:
            logger.error(f"Error checking cache expiry: {e}", exc_info=True)
            del self.cache[key]
            return None
    
    def _add_to_cache(self, key: str, value: Any):
        """Add value to cache.
        
        Args:
            key: Cache key.
            value: Value to cache.
        """
        # Remove oldest items if cache is full
        if len(self.cache) >= self.cache_size:
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k]['timestamp'])
            del self.cache[oldest_key]
        
        # Add to cache
        self.cache[key] = {
            'value': value,
            'timestamp': get_current_time()
        }
    
    def _clear_cache(self):
        """Clear all cache."""
        self.cache = {}
    
    def process_message(self, message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process a message and classify memory.
        
        Args:
            message: The message to process.
            context: Optional context for the message.
            
        Returns:
            A dictionary containing the classification results.
        """
        try:
            # Check if it's time to run archive
            self._check_archive_time()
            
            # Step 1: Add message to working memory
            self._add_to_working_memory(message)
            
            # Step 2: Apply layers in order
            # Layer 1: Rule matching
            rule_matches = self.rule_matcher.match(message, context)
            
            # Layer 2: Pattern analysis
            pattern_matches = self.pattern_analyzer.analyze(message, context)
            
            # Layer 3: Semantic classification
            semantic_matches = self.semantic_classifier.classify(message, context)
            
            # Step 3: Combine results
            all_matches = rule_matches + pattern_matches + semantic_matches
            
            # Step 4: Deduplicate and resolve conflicts
            unique_matches = self._deduplicate_matches(all_matches)
            
            # Step 5: Store memories
            stored_memories = []
            for match in unique_matches:
                # Generate memory ID
                memory_id = generate_memory_id()
                match['id'] = memory_id
                
                # Add context if provided
                if context:
                    match['context'] = context.get('conversation_id', '')
                
                # Rename memory_type to type for storage compatibility
                if 'memory_type' in match:
                    match['type'] = match['memory_type']
                # Also keep memory_type for compatibility with retrieval
                if 'type' in match and 'memory_type' not in match:
                    match['memory_type'] = match['type']
                
                # Store based on tier
                if match.get('tier') == 2:
                    self.tier2_storage.store_memory(match)
                elif match.get('tier') == 3:
                    self.tier3_storage.store_memory(match)
                elif match.get('tier') == 4:
                    self.tier4_storage.store_memory(match)
                
                stored_memories.append(match)
            
            # Clear cache since new memories were added
            self._clear_cache()
            
            return {
                'message': message,
                'matches': stored_memories,
                'working_memory_size': len(self.working_memory)
            }
        except StorageError as e:
            logger.error(f"Error storing memories: {e}", exc_info=True)
            return {
                'message': message,
                'matches': [],
                'working_memory_size': len(self.working_memory),
                'error': f'Storage error: {e}'
            }
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            return {
                'message': message,
                'matches': [],
                'working_memory_size': len(self.working_memory),
                'error': f'Internal error: {e}'
            }
    
    def retrieve_memories(self, query: str = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Retrieve memories based on query.
        
        Args:
            query: Optional query string to filter memories.
            limit: Maximum number of memories to return.
            
        Returns:
            A list of matching memories.
        """
        # Generate cache key
        cache_key = f"retrieve:{query}:{limit}"
        
        # Check if result is in cache
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            return cached_result
        
        # Retrieve from all tiers
        tier2_memories = self.tier2_storage.retrieve_memories(query, limit)
        tier3_memories = self.tier3_storage.retrieve_memories(query, limit)
        tier4_memories = self.tier4_storage.retrieve_memories(query, limit)
        
        # Combine and sort by confidence
        all_memories = tier2_memories + tier3_memories + tier4_memories
        all_memories.sort(key=lambda x: x.get('confidence', 0), reverse=True)
        
        # Limit the result
        result = all_memories[:limit]
        
        # Store in cache
        self._add_to_cache(cache_key, result)
        
        return result
    
    def manage_memory(self, action: str, memory_id: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Manage memory (view, edit, delete).
        
        Args:
            action: The action to perform (view, edit, delete).
            memory_id: The ID of the memory to manage.
            data: Optional data for editing.
            
        Returns:
            A dictionary containing the result.
        """
        try:
            # Try to find the memory in all tiers
            memory = None
            storage = None
            
            # Check tier 2
            tier2_memories = self.tier2_storage.retrieve_memories()
            for m in tier2_memories:
                if m.get('id') == memory_id:
                    memory = m
                    storage = self.tier2_storage
                    break
            
            # Check tier 3
            if not memory:
                tier3_memories = self.tier3_storage.retrieve_memories()
                for m in tier3_memories:
                    if m.get('id') == memory_id:
                        memory = m
                        storage = self.tier3_storage
                        break
            
            # Check tier 4
            if not memory:
                tier4_memories = self.tier4_storage.retrieve_memories()
                for m in tier4_memories:
                    if m.get('id') == memory_id:
                        memory = m
                        storage = self.tier4_storage
                        break
            
            if not memory:
                return {'success': False, 'message': 'Memory not found'}
            
            if action == 'view':
                return {'success': True, 'memory': memory}
            
            elif action == 'edit':
                if data and storage:
                    success = storage.update_memory(memory_id, data)
                    if success:
                        # Get updated memory
                        updated_memory = None
                        if storage == self.tier2_storage:
                            for m in self.tier2_storage.retrieve_memories():
                                if m.get('id') == memory_id:
                                    updated_memory = m
                                    break
                        elif storage == self.tier3_storage:
                            for m in self.tier3_storage.retrieve_memories():
                                if m.get('id') == memory_id:
                                    updated_memory = m
                                    break
                        elif storage == self.tier4_storage:
                            for m in self.tier4_storage.retrieve_memories():
                                if m.get('id') == memory_id:
                                    updated_memory = m
                                    break
                        # Clear cache since memory was updated
                        self._clear_cache()
                        return {'success': True, 'memory': updated_memory}
                return {'success': False, 'message': 'Failed to update memory'}
            
            elif action == 'delete':
                if storage:
                    success = storage.delete_memory(memory_id)
                    if success:
                        # Clear cache since memory was deleted
                        self._clear_cache()
                    return {'success': success, 'message': 'Memory deleted' if success else 'Failed to delete memory'}
            
            return {'success': False, 'message': 'Invalid action'}
        except MemoryNotFoundError as e:
            return {'success': False, 'message': str(e)}
        except StorageError as e:
            return {'success': False, 'message': f'Storage error: {e}'}
        except Exception as e:
            logger.error(f"Error managing memory: {e}", exc_info=True)
            return {'success': False, 'message': f'Internal error: {e}'}
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the engine.
        
        Returns:
            A dictionary with statistics.
        """
        tier2_stats = self.tier2_storage.get_stats()
        tier3_stats = self.tier3_storage.get_stats()
        tier4_stats = self.tier4_storage.get_stats()
        
        return {
            'working_memory_size': len(self.working_memory),
            'tier2': tier2_stats,
            'tier3': tier3_stats,
            'tier4': tier4_stats,
            'total_memories': (
                tier2_stats.get('total_memories', 0) +
                tier3_stats.get('total_memories', 0) +
                tier4_stats.get('total_relationships', 0)
            )
        }
    
    def export_memories(self, format: str = "json") -> Dict[str, Any]:
        """Export memories.
        
        Args:
            format: Export format (json).
            
        Returns:
            A dictionary containing the exported memories.
        """
        tier2_memories = self.tier2_storage.retrieve_memories(limit=1000)
        tier3_memories = self.tier3_storage.retrieve_memories(limit=1000)
        tier4_memories = self.tier4_storage.retrieve_memories(limit=1000)
        
        if format == "json":
            return {
                'tier2': tier2_memories,
                'tier3': tier3_memories,
                'tier4': tier4_memories
            }
        
        return {'error': 'Unsupported format'}
    
    def import_memories(self, data: Dict[str, Any], format: str = "json") -> Dict[str, Any]:
        """Import memories.
        
        Args:
            data: The data to import.
            format: Import format (json).
            
        Returns:
            A dictionary containing the import result.
        """
        if format != "json":
            return {'error': 'Unsupported format'}
        
        imported_count = 0
        
        # Import tier 2 memories
        for memory in data.get('tier2', []):
            if self.tier2_storage.store_memory(memory):
                imported_count += 1
        
        # Import tier 3 memories
        for memory in data.get('tier3', []):
            if self.tier3_storage.store_memory(memory):
                imported_count += 1
        
        # Import tier 4 memories
        for memory in data.get('tier4', []):
            if self.tier4_storage.store_memory(memory):
                imported_count += 1
        
        # Clear cache since memories were imported
        self._clear_cache()
        
        return {'success': True, 'imported_count': imported_count}
    
    def _add_to_working_memory(self, message: str):
        """Add a message to working memory.
        
        Args:
            message: The message to add.
        """
        self.working_memory.append({
            'message': message,
            'timestamp': get_current_time()
        })
        
        # Limit working memory size
        if len(self.working_memory) > self.max_work_memory_size:
            self.working_memory.pop(0)
    
    def _deduplicate_matches(self, matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate matches.
        
        Args:
            matches: List of matches to deduplicate.
            
        Returns:
            List of unique matches.
        """
        if not self.deduplication_enabled:
            return matches
        
        unique_matches = []
        
        for match in matches:
            content = match.get('content', '').strip()
            is_duplicate = False
            
            for existing_match in unique_matches:
                existing_content = existing_match.get('content', '').strip()
                similarity = self._calculate_semantic_similarity(content, existing_content)
                
                if similarity > self.similarity_threshold:
                    is_duplicate = True
                    # Check for conflict
                    if self._detect_conflict(match, existing_match):
                        # Resolve conflict
                        resolved_match = self._resolve_conflict(match, existing_match)
                        unique_matches.remove(existing_match)
                        unique_matches.append(resolved_match)
                    else:
                        # Keep the match with higher confidence
                        if match.get('confidence', 0) > existing_match.get('confidence', 0):
                            unique_matches.remove(existing_match)
                            unique_matches.append(match)
                    break
            
            if not is_duplicate:
                unique_matches.append(match)
        
        return unique_matches
    
    def _detect_conflict(self, memory1: Dict[str, Any], memory2: Dict[str, Any]) -> bool:
        """Detect if two memories conflict.
        
        Args:
            memory1: First memory.
            memory2: Second memory.
            
        Returns:
            True if memories conflict, False otherwise.
        """
        # Simple conflict detection based on negation patterns
        content1 = memory1.get('content', '').lower()
        content2 = memory2.get('content', '').lower()
        
        # Check for direct negation
        negation_words = ['不', '没', '没有', '不是', '不要', '不喜欢', '不想要']
        
        for word in negation_words:
            if word in content1 and word not in content2:
                # Check if the rest of the content is similar
                content1_without_negation = content1.replace(word, '').strip()
                similarity = self._calculate_semantic_similarity(content1_without_negation, content2)
                if similarity > 0.7:
                    return True
            elif word in content2 and word not in content1:
                # Check if the rest of the content is similar
                content2_without_negation = content2.replace(word, '').strip()
                similarity = self._calculate_semantic_similarity(content1, content2_without_negation)
                if similarity > 0.7:
                    return True
        
        return False
    
    def _resolve_conflict(self, memory1: Dict[str, Any], memory2: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve conflict between two memories.
        
        Args:
            memory1: First memory.
            memory2: Second memory.
            
        Returns:
            Resolved memory.
        """
        strategy = self.conflict_resolution_strategy
        
        if strategy == 'latest':
            # Use the latest memory
            time1 = memory1.get('created_at', '')
            time2 = memory2.get('created_at', '')
            return memory1 if time1 > time2 else memory2
        elif strategy == 'highest_confidence':
            # Use the memory with highest confidence
            conf1 = memory1.get('confidence', 0)
            conf2 = memory2.get('confidence', 0)
            return memory1 if conf1 > conf2 else memory2
        elif strategy == 'merge':
            # Merge both memories with context
            merged_content = f"{memory1.get('content', '')} (conflict resolved: {memory2.get('content', '')})"
            merged_memory = memory1.copy()
            merged_memory['content'] = merged_content
            merged_memory['confidence'] = (memory1.get('confidence', 0) + memory2.get('confidence', 0)) / 2
            merged_memory['updated_at'] = get_current_time()
            return merged_memory
        else:
            # Default to latest
            time1 = memory1.get('created_at', '')
            time2 = memory2.get('created_at', '')
            return memory1 if time1 > time2 else memory2
    
    def _calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        """Calculate semantic similarity between two texts.
        
        Args:
            text1: First text.
            text2: Second text.
            
        Returns:
            Similarity score between 0 and 1.
        """
        # Simple bag-of-words similarity for now
        # In a real implementation, this would use word embeddings or LLM
        
        # Tokenize texts
        def tokenize(text):
            return set(word.lower() for word in text.split() if word.isalnum())
        
        tokens1 = tokenize(text1)
        tokens2 = tokenize(text2)
        
        if not tokens1 and not tokens2:
            return 1.0
        
        # Calculate Jaccard similarity
        intersection = len(tokens1.intersection(tokens2))
        union = len(tokens1.union(tokens2))
        
        return intersection / union if union > 0 else 0.0
    
    def clear_working_memory(self):
        """Clear working memory."""
        self.working_memory = []
    
    def reload_config(self):
        """Reload configuration."""
        self.config.reload()
        
        # Update storage paths if changed
        tier2_path = self.config.get('storage.tier2_path', './data/tier2')
        tier3_path = self.config.get('storage.tier3_path', './data/tier3')
        tier4_path = self.config.get('storage.tier4_path', './data/tier4')
        
        self.tier2_storage = Tier2Storage(tier2_path)
        self.tier3_storage = Tier3Storage(tier3_path)
        self.tier4_storage = Tier4Storage(tier4_path)
        
        # Update rules
        rules = self.config.get_rules().get('rules', [])
        self.rule_matcher = RuleMatcher(rules)
        
        # Update LLM settings
        llm_enabled = self.config.get('llm.enabled', False)
        api_key = self.config.get('llm.api_key', '')
        self.semantic_classifier = SemanticClassifier(llm_enabled, api_key)
