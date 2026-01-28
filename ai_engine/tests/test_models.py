
import os
import time
import logging
from config.rag_config import GEMINI_API_KEYS, GEMINI_MODELS
import google.genai as genai
from google.genai import types

# Configure simple logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ModelTester")

def test_models():
    print("\n" + "="*50)
    print("STARTING GEMINI MODELS TEST")
    print("="*50)
    print(f"Found {len(GEMINI_API_KEYS)} API Keys")
    print(f"Found {len(GEMINI_MODELS)} Models to test: {GEMINI_MODELS}")
    print("="*50 + "\n")

    if not GEMINI_API_KEYS:
        logger.error("No API Keys found in config/rag_config.py!")
        return

    # Use the first key for testing
    api_key = GEMINI_API_KEYS[0]
    client = genai.Client(api_key=api_key) # New SDK client
    # For older generic usage, we can also use genai.configure
    try:
        import google.generativeai as old_genai
        old_genai.configure(api_key=api_key)
    except:
        pass

    results = []

    for model_name in GEMINI_MODELS:
        print(f"Testing model: {model_name}...", end=" ", flush=True)
        start_time = time.time()
        status = "FAILED"
        message = ""
        latency = 0

        try:
            # Try generating content
            # Note: Using the new SDK syntax implied by ModelManager usage
            # But let's try the most standard way compatible with google-generativeai package
            
            # Simple prompt
            response = client.models.generate_content(
                model=model_name,
                contents="Hello, simply reply 'OK' if you are working.",
                config=types.GenerateContentConfig(
                    max_output_tokens=10
                )
            )
            
            latency = time.time() - start_time
            if response and response.text:
                status = "SUCCESS"
                message = f"Response: {response.text.strip()}"
            else:
                message = "Empty response"

        except Exception as e:
            latency = time.time() - start_time
            status = "ERROR"
            error_str = str(e)
            if "404" in error_str or "not found" in error_str.lower():
                message = "Model Not Found (404)"
            elif "403" in error_str or "permission" in error_str.lower():
                message = "Permission Denied (403)"
            elif "429" in error_str or "quota" in error_str.lower():
                message = "Rate Limit/Quota Exceeded"
            else:
                message = f"Error: {error_str[:100]}..."

        print(f"[{status}] ({latency:.2f}s)")
        print(f"   -> {message}")
        print("-" * 30)
        
        results.append({
            "model": model_name,
            "status": status,
            "latency": latency,
            "message": message
        })

    print("\n" + "="*50)
    print("TEST SUMMARY")
    print("="*50)
    print(f"{'MODEL':<25} | {'STATUS':<10} | {'LATENCY':<10}")
    print("-" * 50)
    for r in results:
        print(f"{r['model']:<25} | {r['status']:<10} | {r['latency']:.2f}s")
    print("="*50 + "\n")

if __name__ == "__main__":
    test_models()
