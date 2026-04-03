import unittest
import tempfile
import os
from memory_classification_engine import MemoryClassificationEngine

class TestMemoryClassificationEngine(unittest.TestCase):
    """Test cases for Memory Classification Engine."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory for test data
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.temp_dir.name, "config.yaml")
        
        # Create a minimal config file
        with open(self.config_path, 'w') as f:
            f.write("""
storage:
  data_path: {data_path}
  tier2_path: {data_path}/tier2
  tier3_path: {data_path}/tier3
  tier4_path: {data_path}/tier4
  max_work_memory_size: 100

memory:
  forgetting:
    enabled: false
  deduplication:
    enabled: true
  conflict_resolution:
    strategy: latest

llm:
  enabled: false
""".format(data_path=self.temp_dir.name))
        
        # Initialize engine
        self.engine = MemoryClassificationEngine(self.config_path)
    
    def tearDown(self):
        """Clean up test environment."""
        self.temp_dir.cleanup()
    
    def test_process_message(self):
        """Test message processing."""
        result = self.engine.process_message("我喜欢使用Python进行编程")
        self.assertIn('message', result)
        self.assertIn('matches', result)
        self.assertIn('working_memory_size', result)
        self.assertEqual(result['message'], "我喜欢使用Python进行编程")
        self.assertIsInstance(result['matches'], list)
    
    def test_retrieve_memories(self):
        """Test memory retrieval."""
        # Process a message first
        self.engine.process_message("我喜欢使用Python进行编程")
        
        # Retrieve memories
        memories = self.engine.retrieve_memories("编程")
        self.assertIsInstance(memories, list)
        
        # Retrieve with limit
        limited_memories = self.engine.retrieve_memories("编程", limit=2)
        self.assertIsInstance(limited_memories, list)
        self.assertLessEqual(len(limited_memories), 2)
    
    def test_manage_memory(self):
        """Test memory management."""
        # Process a message to create a memory
        result = self.engine.process_message("我不喜欢在代码中使用分号")
        memory_id = result['matches'][0]['id']
        
        # View memory
        view_result = self.engine.manage_memory('view', memory_id)
        self.assertTrue(view_result['success'])
        self.assertIn('memory', view_result)
        
        # Edit memory
        edit_result = self.engine.manage_memory('edit', memory_id, {'content': '我不喜欢在Python代码中使用分号'})
        self.assertTrue(edit_result['success'])
        
        # Delete memory
        delete_result = self.engine.manage_memory('delete', memory_id)
        self.assertTrue(delete_result['success'])
        
        # Try to view deleted memory
        view_result = self.engine.manage_memory('view', memory_id)
        self.assertFalse(view_result['success'])
    
    def test_get_stats(self):
        """Test statistics retrieval."""
        stats = self.engine.get_stats()
        self.assertIn('working_memory_size', stats)
        self.assertIn('tier2', stats)
        self.assertIn('tier3', stats)
        self.assertIn('tier4', stats)
        self.assertIn('total_memories', stats)
    
    def test_export_import(self):
        """Test memory export and import."""
        # Process a message first
        self.engine.process_message("我喜欢使用Python进行编程")
        
        # Export memories
        export_data = self.engine.export_memories()
        self.assertIn('tier2', export_data)
        self.assertIn('tier3', export_data)
        self.assertIn('tier4', export_data)
        
        # Import memories
        import_result = self.engine.import_memories(export_data)
        self.assertTrue(import_result['success'])
        self.assertIn('imported_count', import_result)
    
    def test_clear_working_memory(self):
        """Test clearing working memory."""
        # Add some messages to working memory
        for i in range(5):
            self.engine.process_message(f"Test message {i}")
        
        # Check working memory size
        stats = self.engine.get_stats()
        self.assertEqual(stats['working_memory_size'], 5)
        
        # Clear working memory
        self.engine.clear_working_memory()
        
        # Check working memory size again
        stats = self.engine.get_stats()
        self.assertEqual(stats['working_memory_size'], 0)
    
    def test_reload_config(self):
        """Test reloading configuration."""
        # Reload config
        self.engine.reload_config()
        # This should not raise an exception
        self.assertTrue(True)

if __name__ == '__main__':
    unittest.main()
