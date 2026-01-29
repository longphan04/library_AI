"""Quick script to check actual categories in ChromaDB"""
from src.vector_db import VectorDB

vdb = VectorDB()
metas = vdb.get_all_metadata()

# Count books per category
cat_count = {}
for m in metas:
    cat = m.get('category', 'N/A')
    cat_count[cat] = cat_count.get(cat, 0) + 1

print("=== Categories in ChromaDB ===")
for cat, count in sorted(cat_count.items(), key=lambda x: -x[1]):
    print(f"  '{cat}': {count} books")
