"""Exception classes for memory classification engine."""


class MemoryEngineError(Exception):
    """Base exception class for memory engine errors."""
    pass


class StorageError(MemoryEngineError):
    """Exception raised for storage-related errors."""
    pass


class MemoryNotFoundError(StorageError):
    """Exception raised when a memory is not found."""
    pass


class MemoryAlreadyExistsError(StorageError):
    """Exception raised when trying to create a memory that already exists."""
    pass


class DatabaseError(StorageError):
    """Exception raised for database-related errors."""
    pass


class FTS5Error(StorageError):
    """Exception raised for FTS5-related errors."""
    pass


class CacheError(MemoryEngineError):
    """Exception raised for cache-related errors."""
    pass


class ConfigurationError(MemoryEngineError):
    """Exception raised for configuration-related errors."""
    pass


class ValidationError(MemoryEngineError):
    """Exception raised for validation errors."""
    pass


class EncryptionError(MemoryEngineError):
    """Exception raised for encryption-related errors."""
    pass


class LLMError(MemoryEngineError):
    """Exception raised for LLM-related errors."""
    pass


class AccessControlError(MemoryEngineError):
    """Exception raised for access control errors."""
    pass
