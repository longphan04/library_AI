"""
RAG Configuration
Settings for RAG Engine, Gemini API, and search parameters.
"""

import os
from dotenv import load_dotenv

# Explicitly load .env from project root (library_AI)
# Path: config/../../.env
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # ai_engine
root_dir = os.path.dirname(base_dir) # library_AI
env_path = os.path.join(root_dir, ".env")
load_dotenv(env_path)
# Also try default lookup
load_dotenv()

# Gemini API Configuration
raw_key = os.getenv("GEMINI_API_KEY")
google_key = os.getenv("GOOGLE_API_KEY")

GEMINI_API_KEYS = []
if raw_key: GEMINI_API_KEYS.append(raw_key)
if google_key: GEMINI_API_KEYS.append(google_key)

# Filter out duplicates and None
GEMINI_API_KEYS = list(set([k for k in GEMINI_API_KEYS if k]))

# Models to rotate through (fallback strategy)
GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash-tts",
    "gemini-3-flash",
    "gemma-3-27b"
]


GEMINI_MODEL = GEMINI_MODELS[0] # Default

# Search Configuration
DEFAULT_TOP_K = 5
SCORE_THRESHOLD = 0.80

# RAG Behavior
MIN_QUERY_LENGTH = 3
ENABLE_GARBAGE_FILTER = True
ENABLE_INTENT_CLASSIFICATION = True
QUERY_CACHE_THRESHOLD = 2.0  # DISABLED (Previously 0.95). High value prevents cache hits to ensure Context is always populated.
SEARCH_EXPAND_FACTOR = 2  # Fetch more results than needed, then filter

# Generation Parameters
TEMPERATURE = 0.2
MAX_OUTPUT_TOKENS = 512
