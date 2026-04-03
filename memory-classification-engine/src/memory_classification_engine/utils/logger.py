import logging
import os
from datetime import datetime

class Logger:
    """Logger class for memory classification engine."""
    
    def __init__(self, name: str = "memory-classification-engine"):
        """Initialize the logger.
        
        Args:
            name: Logger name.
        """
        # Create logs directory if it doesn't exist
        logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
        os.makedirs(logs_dir, exist_ok=True)
        
        # Create logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # Create file handler
        log_file = os.path.join(logs_dir, f"{datetime.now().strftime('%Y-%m-%d')}.log")
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        
        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        
        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Add handlers to logger
        if not self.logger.handlers:
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)
    
    def debug(self, message: str):
        """Log debug message.
        
        Args:
            message: Debug message.
        """
        self.logger.debug(message)
    
    def info(self, message: str):
        """Log info message.
        
        Args:
            message: Info message.
        """
        self.logger.info(message)
    
    def warning(self, message: str):
        """Log warning message.
        
        Args:
            message: Warning message.
        """
        self.logger.warning(message)
    
    def error(self, message: str, exc_info: bool = False):
        """Log error message.
        
        Args:
            message: Error message.
            exc_info: Whether to include exception information.
        """
        self.logger.error(message, exc_info=exc_info)
    
    def critical(self, message: str, exc_info: bool = False):
        """Log critical message.
        
        Args:
            message: Critical message.
            exc_info: Whether to include exception information.
        """
        self.logger.critical(message, exc_info=exc_info)

# Create global logger instance
logger = Logger()
