
import sys
import os
import shutil

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.embedder import Embedder
from src.vector_db import VectorDB
from config.settings import settings

def test_vector_flow():
    print(">>> 1. Init Embedder")
    embedder = Embedder()
    
    print(">>> 2. Init VectorDB")
    vector_db = VectorDB()
    
    print(">>> 3. Embed Sample Text")
    text = "Python is a powerful programming language."
    vector = embedder.embed_text(text, is_query=False)
    
    if vector and len(vector) == 768:
        print(f"PASS: Vector generated with shape {len(vector)}")
    else:
        print("FAIL: Vector generation failed")
        return

    print(">>> 4. Upsert to DB")
    # Use a dummy ID
    book_id = "test_book_001"
    meta = {"title": "Test Book", "category": "Programming"}
    
    success = vector_db.upsert_texts(
        ids=[book_id],
        vectors=[vector],
        metadatas=[meta],
        documents=[text]
    )
    
    if success:
         print("PASS: Upsert successful")
    else:
         print("FAIL: Upsert failed")
         return

    print(">>> 5. Query DB")
    query_text = "programming language"
    query_vec = embedder.embed_text(query_text, is_query=True)
    
    results = vector_db.query_vectors(query_vec, n_results=1)
    
    if results and results['ids'] and results['ids'][0]:
        found_id = results['ids'][0][0]
        print(f"PASS: Query returned ID: {found_id}")
        if found_id == book_id:
            print("PASS: ID matches expected.")
        else:
             print("FAIL: ID mismatch.")
    else:
        print("FAIL: Query returned no results.")

if __name__ == "__main__":
    test_vector_flow()
