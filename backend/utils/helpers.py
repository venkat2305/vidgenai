import re
import logging
from typing import List, Dict, Any

logger = logging.getLogger("vidgenai.helpers")

def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to be safe for file systems.
    
    Args:
        filename: The filename to sanitize
        
    Returns:
        Sanitized filename
    """
    # Replace spaces with underscores
    filename = filename.replace(" ", "_")
    
    # Remove any non-alphanumeric characters except underscores, hyphens, and periods
    filename = re.sub(r'[^\w\-\.]', '', filename)
    
    # Ensure filename is not too long
    if len(filename) > 100:
        filename = filename[:100]
    
    return filename

def chunk_text(text: str, max_length: int = 1000) -> List[str]:
    """
    Split text into chunks of maximum length.
    
    Args:
        text: The text to split
        max_length: Maximum length of each chunk
        
    Returns:
        List of text chunks
    """
    # If text is shorter than max_length, return it as is
    if len(text) <= max_length:
        return [text]
    
    # Split text into sentences
    sentences = re.split(r'(?<=[.!?]) +', text)
    
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        # If adding this sentence would exceed max_length, start a new chunk
        if len(current_chunk) + len(sentence) + 1 > max_length:
            chunks.append(current_chunk.strip())
            current_chunk = sentence
        else:
            if current_chunk:
                current_chunk += " " + sentence
            else:
                current_chunk = sentence
    
    # Add the last chunk if it's not empty
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks
