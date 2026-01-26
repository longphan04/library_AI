"""
RAG Configuration
Settings for RAG Engine, Gemini API, and search parameters.
"""

import os

# Gemini API Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.5-flash"  # Changed from gemini-2.5-pro to avoid quota issues

# Search Configuration
DEFAULT_TOP_K = 5
SCORE_THRESHOLD = 0.80

# RAG Behavior
MIN_QUERY_LENGTH = 3
ENABLE_GARBAGE_FILTER = True
ENABLE_INTENT_CLASSIFICATION = True
QUERY_CACHE_THRESHOLD = 0.95  # Similarity threshold for query cache hits
SEARCH_EXPAND_FACTOR = 2  # Fetch more results than needed, then filter

# Generation Parameters
TEMPERATURE = 0.2
MAX_OUTPUT_TOKENS = 512
