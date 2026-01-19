from src.search_engine import SearchEngine
import json

se = SearchEngine()

filters = se.get_filters()

print("\nCATEGORIES:")
print(filters["categories"][:10])

print("\nYEARS:")
print(filters["years"][:10])

print("\nAUTHORS:")
print(filters["authors"][:10])
