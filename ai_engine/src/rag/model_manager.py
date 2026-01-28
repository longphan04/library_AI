import logging
import time
from typing import List, Optional
from google import genai
from google.genai import types
from google.api_core import exceptions as google_exceptions

logger = logging.getLogger("ModelManager")

class ModelManager:
    """
    Manages usage of multiple API Keys and Models to handle rate limits.
    Strategy:
    1. Round-robin through API Keys for 429/ResourceExhausted errors.
    2. If all keys fail, switch to next model in list (lighter model).
    """
    def __init__(self, api_keys: List[str], models: List[str]):
        if not api_keys:
            raise ValueError("No API Keys provided for ModelManager")
        if not models:
            raise ValueError("No Models provided for ModelManager")
            
        self.api_keys = api_keys
        self.models = models
        
        self.current_key_idx = 0
        self.current_model_idx = 0
        
        # Initialize clients for all keys (lazy or upfront)
        # Here we create client on demand or cache them
        self._clients = [genai.Client(api_key=k) for k in self.api_keys]

    def _get_client(self):
        return self._clients[self.current_key_idx]

    def _rotate_key(self) -> bool:
        """
        Switch to next API Key.
        Returns: True if rotated, False if cycled through all keys (round completed).
        """
        prev_idx = self.current_key_idx
        self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)
        logger.warning(f"Switched API Key: {prev_idx} -> {self.current_key_idx}")
        
        # If we wrapped around to 0, we've tried all keys
        return self.current_key_idx != 0

    def _switch_model(self) -> bool:
        """
        Switch to next Model (fallback).
        Returns: True if switched, False if exhaust all models.
        """
        if self.current_model_idx + 1 < len(self.models):
            self.current_model_idx += 1
            logger.warning(f"Fallback to Model: {self.models[self.current_model_idx]}")
            return True
        return False

    def generate_content(self, prompt: str, temperature: float, max_tokens: int) -> Optional[str]:
        """
        Attempt to generate content with retries on Rate Limit.
        """
        # We try (Keys * Models) times roughly
        max_attempts = len(self.api_keys) * len(self.models) * 2 
        
        for attempt in range(max_attempts):
            client = self._get_client()
            model = self.models[self.current_model_idx]
            
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=temperature,
                        max_output_tokens=max_tokens
                    )
                )
                return response.text.strip() if response and response.text else None

            except Exception as e:
                # Check for Rate Limit errors
                # Google GenAI raises custom exceptions, string check is fallback
                err_str = str(e).lower()
                logger.error(f"Generate Error (Key {self.current_key_idx} | Model {model}): {type(e).__name__} - {e}")
                
                is_rate_limit = "429" in err_str or "resource" in err_str or "exhausted" in err_str or "quota" in err_str or "403" in err_str or "permission" in err_str
                is_model_error = "404" in err_str or "not found" in err_str or "support" in err_str or "bad request" in err_str

                if is_model_error:
                    logger.warning(f"Model {model} error. Switching model immediately...")
                    if self._switch_model():
                        self.current_key_idx = 0 # Try new model with first key
                        continue
                    else:
                        raise e # No more models

                if is_rate_limit:
                    logger.warning(f"Rate limit hit on Key {self.current_key_idx} Model {model}. Rotating...")
                    
                    # Try next key
                    rotated_key = self._rotate_key()
                    
                    # If we cycled all keys, try switching model
                    if not rotated_key:
                        switched_model = self._switch_model()
                        if not switched_model:
                            logger.error("Exhausted all Keys and Models!")
                            raise e # Give up
                        else:
                            # Reset key index when switching model to try new model with all keys
                            self.current_key_idx = 0
                    
                    time.sleep(1) # Brief pause
                    continue
                else:
                    # Other error (auth, payload), raise immediately
                    logger.error(f"Critical GenAI Error: {e}")
                    raise e
                    
        return None
