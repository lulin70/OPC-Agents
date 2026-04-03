# Memory Classification Engine - API Documentation

## Overview

The Memory Classification Engine provides a comprehensive API for managing AI agent memories, including classification, storage, retrieval, and management functions.

## Installation

```bash
pip install -e .
```

## Basic Usage

```python
from memory_classification_engine import MemoryClassificationEngine

# Initialize engine
engine = MemoryClassificationEngine()

# Process message
result = engine.process_message("记住，我不喜欢在代码中使用破折号")
print(result)

# Retrieve memories
memories = engine.retrieve_memories("代码")
print(memories)

# Get statistics
stats = engine.get_stats()
print(stats)
```

## API Reference

### MemoryClassificationEngine

#### Initialization

```python
MemoryClassificationEngine(config_path: str = None)
```

- `config_path`: Optional path to the configuration file. If not provided, uses the default path `./config/config.yaml`.

#### process_message

```python
process_message(message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]
```

Processes a message and classifies it into memory types.

- `message`: The message to process.
- `context`: Optional context for the message, such as conversation ID.
- **Returns**: A dictionary containing the classification results, including the original message, matched memories, and working memory size.

#### retrieve_memories

```python
retrieve_memories(query: str = None, limit: int = 5) -> List[Dict[str, Any]]
```

Retrieves memories based on a query.

- `query`: Optional query string to filter memories.
- `limit`: Maximum number of memories to return (default: 5).
- **Returns**: A list of matching memories, sorted by confidence.

#### manage_memory

```python
manage_memory(action: str, memory_id: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]
```

Manages memory (view, edit, delete).

- `action`: The action to perform (`view`, `edit`, `delete`).
- `memory_id`: The ID of the memory to manage.
- `data`: Optional data for editing.
- **Returns**: A dictionary containing the result of the action.

#### get_stats

```python
get_stats() -> Dict[str, Any]
```

Gets statistics about the engine.

- **Returns**: A dictionary with statistics about working memory size and memory counts by tier.

#### export_memories

```python
export_memories(format: str = "json") -> Dict[str, Any]
```

Exports memories.

- `format`: Export format (currently only `json` is supported).
- **Returns**: A dictionary containing the exported memories organized by tier.

#### import_memories

```python
import_memories(data: Dict[str, Any], format: str = "json") -> Dict[str, Any]
```

Imports memories.

- `data`: The data to import.
- `format`: Import format (currently only `json` is supported).
- **Returns**: A dictionary containing the import result, including the number of imported memories.

#### clear_working_memory

```python
clear_working_memory()
```

Clears working memory.

#### reload_config

```python
reload_config()
```

Reloads configuration from the config file.

## Configuration

The engine can be configured using a YAML configuration file. The default path is `./config/config.yaml`.

### Example Configuration

```yaml
# Storage settings
storage:
  data_path: ./data
  tier2_path: ./data/tier2
  tier3_path: ./data/tier3
  tier4_path: ./data/tier4
  max_work_memory_size: 100

# Memory management settings
memory:
  forgetting:
    enabled: true
    decay_factor: 0.9
    min_weight: 0.1
    archive_interval: 86400  # 24 hours
  deduplication:
    enabled: true
    similarity_threshold: 0.8
  conflict_resolution:
    strategy: latest  # Options: latest, highest_confidence, merge

# LLM settings (optional)
llm:
  enabled: false
  api_key: ""
  model: "glm-4-plus"
  temperature: 0.3
  max_tokens: 500
  timeout: 30  # In seconds
```

## Environment Variables

The following environment variables can be used to override configuration settings:

- `MCE_CONFIG_PATH`: Path to the configuration file
- `MCE_LLM_ENABLED`: Whether to enable LLM (true/false)
- `MCE_LLM_API_KEY`: LLM API key
- `MCE_LLM_MODEL`: LLM model to use

## Error Handling

All methods return appropriate error messages in case of failures. For example:

```python
result = engine.manage_memory('view', 'non-existent-id')
print(result)  # {'success': False, 'message': 'Memory not found'}
```

## Logging

The engine logs all errors and important events to the `logs` directory. Each day's logs are stored in a separate file.

## Security

- All memory content is encrypted at rest using Fernet symmetric encryption.
- Access control is provided through role-based permissions.

## Examples

### Example 1: Basic Memory Processing

```python
from memory_classification_engine import MemoryClassificationEngine

# Initialize engine
engine = MemoryClassificationEngine()

# Process a message
result = engine.process_message("我喜欢使用Python进行编程")
print("Processing result:", result)

# Retrieve memories related to programming
memories = engine.retrieve_memories("编程")
print("Retrieved memories:", memories)

# Get statistics
stats = engine.get_stats()
print("Statistics:", stats)
```

### Example 2: Memory Management

```python
from memory_classification_engine import MemoryClassificationEngine

# Initialize engine
engine = MemoryClassificationEngine()

# Process a message to create a memory
result = engine.process_message("我不喜欢在代码中使用分号")
memory_id = result['matches'][0]['id']
print("Created memory with ID:", memory_id)

# View the memory
view_result = engine.manage_memory('view', memory_id)
print("Memory details:", view_result)

# Edit the memory
edit_result = engine.manage_memory('edit', memory_id, {'content': '我不喜欢在Python代码中使用分号'})
print("Edit result:", edit_result)

# Delete the memory
delete_result = engine.manage_memory('delete', memory_id)
print("Delete result:", delete_result)
```

### Example 3: Import/Export

```python
from memory_classification_engine import MemoryClassificationEngine

# Initialize engine
engine = MemoryClassificationEngine()

# Export memories
export_data = engine.export_memories()
print("Exported memories:", export_data)

# Import memories
import_result = engine.import_memories(export_data)
print("Import result:", import_result)
```
