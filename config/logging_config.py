import logging
import sys

def setup_logging():
    """Configures the standard application logger."""
    logger = logging.getLogger("chatbot")
    
    # If handler is already configured, return the logger to prevent duplicate handlers
    if logger.handlers:
        return logger
        
    logger.setLevel(logging.INFO)
    
    # Create console handler printing to stdout
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    
    # Custom formatter to match the user's requested style exactly
    # Example: [INFO] User Create API request received
    formatter = logging.Formatter("[%(levelname)s] %(message)s")
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    logger.propagate = False
    return logger

# Exported logger instance
logger = setup_logging()
