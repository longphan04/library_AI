"""
Manual script to test SearchEngine.search and filter handling.
Run with: python tests/manual_test_search.py
"""
import traceback
from src.search_engine import SearchEngine


def run_test():
    try:
        se = SearchEngine()
    except Exception as e:
        print('Failed to initialize SearchEngine:', e)
        traceback.print_exc()
        return

    queries = [
        ('Python programming', None),
        ('Python programming', {'authors': 'Liam Foster'}),
        ('Python programming', {'author': 'Liam Foster'}),
        ('Python programming', {'year': '2016'}),
        ('Python programming', {'published_year': '2016'}),
    ]

    for q, f in queries:
        print('\n---')
        print('Query:', q)
        print('Filters (raw):', f)
        try:
            res = se.search(query=q, filters=f, top_k=5)
            print('Result count:', len(res))
            if res:
                print('First result metadata:', res[0])
        except Exception as e:
            print('Search raised exception:', e)
            traceback.print_exc()


if __name__ == '__main__':
    run_test()
