from src.search_engine import SearchEngine
import json

se = SearchEngine()

filters = se.get_filters()

print("\n📚 CATEGORIES:")
print(filters["categories"][:10])

print("\n📅 YEARS:")
print(filters["years"][:10])

print("\n✍ AUTHORS:")
print(filters["authors"][:10])
