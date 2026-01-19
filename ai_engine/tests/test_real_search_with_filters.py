#!/usr/bin/env python3
"""
Test thực tế tìm kiếm sách với tên và filter cụ thể từ database.

Chạy các tìm kiếm thực tế với:
- Tìm theo tên sách
- Tìm theo tác giả
- Tìm theo category
- Tìm theo năm xuất bản
- Kết hợp nhiều filters
"""
import sys
import os
import json
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.search_engine import SearchEngine


class RealSearchTester:
    """Class để test tìm kiếm thực tế với database."""

    def __init__(self):
        """Khởi tạo search engine."""
        print("=" * 80)
        print("KHOI TAO SEARCH ENGINE")
        print("=" * 80)
        try:
            self.search_engine = SearchEngine()
            print("SearchEngine da san sang")
        except Exception as e:
            print(f"Loi khoi tao SearchEngine: {e}")
            raise

    def print_results(self, results, title="KET QUA TIM KIEM"):
        """In kết quả tìm kiếm đẹp mắt."""
        print("\n" + "=" * 80)
        print(title)
        print("=" * 80)

        if not results:
            print("Khong tim thay ket qua nao")
            return

        print(f"Tim thay {len(results)} ket qua\n")

        for i, book in enumerate(results, 1):
            print(f"{i}. {book.get('title', 'N/A')}")
            print(f"   Tac gia: {book.get('authors', 'N/A')}")
            print(f"   The loai: {book.get('category', 'N/A')}")
            print(f"   Nam: {book.get('published_year', 'N/A')}")
            print(f"   Diem: {book.get('score', 0):.4f}")
            print(f"   ID: {book.get('id', 'N/A')}")

            snippet = book.get('snippet', '')
            if snippet:
                print(f"   Trich doan: {snippet[:150]}...")
            print()

    def test_search_by_name(self, query="Python", top_k=5):
        """Test 1: Tìm kiếm theo tên sách."""
        print("\n" + "=" * 80)
        print(f"TEST 1: TIM KIEM THEO TEN '{query}'")
        print("=" * 80)

        try:
            results = self.search_engine.search(
                query=query,
                top_k=top_k
            )
            self.print_results(results, f"Ket qua tim kiem: '{query}'")
            return results
        except Exception as e:
            print(f"Loi: {e}")
            import traceback
            traceback.print_exc()
            return []

    def test_search_with_title_filter(self, query="programming", title_filter="Python", top_k=5):
        """Test 2: Tìm kiếm với filter tiêu đề."""
        print("\n" + "=" * 80)
        print(f"TEST 2: TIM '{query}' VOI FILTER TITLE='{title_filter}'")
        print("=" * 80)

        try:
            filters = {"title": title_filter}
            results = self.search_engine.search(
                query=query,
                filters=filters,
                top_k=top_k
            )
            self.print_results(results, f"Ket qua voi title filter='{title_filter}'")
            return results
        except Exception as e:
            print(f"Loi: {e}")
            import traceback
            traceback.print_exc()
            return []

    def test_search_with_author_filter(self, query="books", author="Mark", top_k=5):
        """Test 3: Tìm kiếm với filter tác giả."""
        print("\n" + "=" * 80)
        print(f"TEST 3: TIM '{query}' CUA TAC GIA '{author}'")
        print("=" * 80)

        try:
            filters = {"authors": author}
            results = self.search_engine.search(
                query=query,
                filters=filters,
                top_k=top_k
            )
            self.print_results(results, f"Sach cua tac gia '{author}'")
            return results
        except Exception as e:
            print(f"Loi: {e}")
            import traceback
            traceback.print_exc()
            return []

    def test_search_with_category_filter(self, query="learning", category="Programming", top_k=5):
        """Test 4: Tìm kiếm với filter thể loại."""
        print("\n" + "=" * 80)
        print(f"TEST 4: TIM '{query}' TRONG THE LOAI '{category}'")
        print("=" * 80)

        try:
            filters = {"category": category}
            results = self.search_engine.search(
                query=query,
                filters=filters,
                top_k=top_k
            )
            self.print_results(results, f"Sach the loai '{category}'")
            return results
        except Exception as e:
            print(f"Loi: {e}")
            import traceback
            traceback.print_exc()
            return []

    def test_search_with_year_filter(self, query="new books", year="2023", top_k=5):
        """Test 5: Tìm kiếm với filter năm xuất bản."""
        print("\n" + "=" * 80)
        print(f"TEST 5: TIM '{query}' NAM {year}")
        print("=" * 80)

        try:
            filters = {"published_year": year}
            results = self.search_engine.search(
                query=query,
                filters=filters,
                top_k=top_k
            )
            self.print_results(results, f"Sach xuat ban nam {year}")
            return results
        except Exception as e:
            print(f"Loi: {e}")
            import traceback
            traceback.print_exc()
            return []

    def test_search_with_multiple_filters(self, query="programming", category="Programming",
                                         year="2023", top_k=5):
        """Test 6: Tìm kiếm với nhiều filters kết hợp."""
        print("\n" + "=" * 80)
        print(f"TEST 6: TIM '{query}' VOI NHIEU FILTERS")
        print(f"  - Category: {category}")
        print(f"  - Year: {year}")
        print("=" * 80)

        try:
            filters = {
                "category": category,
                "published_year": year
            }
            results = self.search_engine.search(
                query=query,
                filters=filters,
                top_k=top_k
            )
            self.print_results(results, f"Sach {category} nam {year}")
            return results
        except Exception as e:
            print(f"Loi: {e}")
            import traceback
            traceback.print_exc()
            return []

    def test_get_available_filters(self):
        """Test 7: Lấy danh sách filters có sẵn."""
        print("\n" + "=" * 80)
        print("TEST 7: LAY DANH SACH FILTERS CO SAN")
        print("=" * 80)

        try:
            filters = self.search_engine.get_filters()

            print("\nCAC FILTERS CO SAN:")
            print("=" * 80)

            # Categories
            categories = filters.get('categories', [])
            print(f"\nCATEGORIES ({len(categories)}):")
            for i, cat in enumerate(categories[:20], 1):  # Show first 20
                print(f"  {i}. {cat}")
            if len(categories) > 20:
                print(f"  ... va {len(categories) - 20} categories khac")

            # Years
            years = filters.get('years', [])
            print(f"\nYEARS ({len(years)}):")
            print(f"  {', '.join(map(str, years[:20]))}")
            if len(years) > 20:
                print(f"  ... va {len(years) - 20} nam khac")

            # Authors
            authors = filters.get('authors', [])
            print(f"\nAUTHORS ({len(authors)}):")
            for i, author in enumerate(authors[:20], 1):  # Show first 20
                print(f"  {i}. {author}")
            if len(authors) > 20:
                print(f"  ... va {len(authors) - 20} tac gia khac")

            return filters
        except Exception as e:
            print(f"Loi: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def test_recommend_similar_books(self, book_id=None, top_k=5):
        """Test 8: Gợi ý sách tương tự."""
        if not book_id:
            # Tìm 1 sách trước để lấy ID
            print("\nTim sach de test recommendation...")
            results = self.search_engine.search(query="Python", top_k=1)
            if results:
                book_id = results[0].get('id')
                print(f"Su dung sach: {results[0].get('title')} (ID: {book_id})")
            else:
                print("Khong tim thay sach nao de test")
                return []

        print("\n" + "=" * 80)
        print(f"TEST 8: GOI Y SACH TUONG TU CHO ID={book_id}")
        print("=" * 80)

        try:
            recommendations = self.search_engine.recommend(
                book_id=book_id,
                top_k=top_k
            )
            self.print_results(recommendations, f"Sach tuong tu voi {book_id}")
            return recommendations
        except Exception as e:
            print(f"Loi: {e}")
            import traceback
            traceback.print_exc()
            return []

    def save_results_to_file(self, results, filename):
        """Lưu kết quả vào file JSON."""
        try:
            output_dir = os.path.join(os.path.dirname(__file__), "output")
            os.makedirs(output_dir, exist_ok=True)

            filepath = os.path.join(output_dir, filename)

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

            print(f"\nDa luu ket qua vao: {filepath}")
        except Exception as e:
            print(f"Loi khi luu file: {e}")


    def interactive_search(self):
        """Tìm kiếm tương tác - cho phép người dùng nhập query và filters."""
        print("\n" + "=" * 80)
        print("TIM KIEM TUONG TAC")
        print("=" * 80)
        print("\nNhap thong tin tim kiem (Enter de bo qua):\n")

        # Nhập query
        query = input("Nhap tu khoa tim kiem: ").strip()
        if not query:
            print("Tu khoa tim kiem khong duoc de trong!")
            return []

        # Nhập filters
        filters = {}

        print("\nNhap filters (Enter de bo qua):")

        # Title filter
        title = input("  - Tieu de chua (title): ").strip()
        if title:
            filters["title"] = title

        # Author filter
        author = input("  - Tac gia chua (authors): ").strip()
        if author:
            filters["authors"] = author

        # Category filter
        category = input("  - The loai (category): ").strip()
        if category:
            filters["category"] = category

        # Year filter
        year = input("  - Nam xuat ban (year): ").strip()
        if year:
            filters["published_year"] = year

        # Top K
        try:
            top_k_input = input("\nSo ket qua mong muon (mac dinh 10): ").strip()
            top_k = int(top_k_input) if top_k_input else 10
        except ValueError:
            print("Gia tri khong hop le, su dung mac dinh top_k=10")
            top_k = 10

        # Hiển thị thông tin tìm kiếm
        print("\n" + "=" * 80)
        print("THONG TIN TIM KIEM")
        print("=" * 80)
        print(f"Query: {query}")
        print(f"Top K: {top_k}")
        if filters:
            print(f"Filters:")
            for key, value in filters.items():
                print(f"  - {key}: {value}")
        else:
            print("Filters: Khong co")

        # Thực hiện tìm kiếm
        print("\nDang tim kiem...")
        try:
            results = self.search_engine.search(
                query=query,
                filters=filters if filters else None,
                top_k=top_k
            )
            self.print_results(results, f"Ket qua tim kiem: '{query}'")

            # Tùy chọn lưu kết quả
            save_option = input("\nLuu ket qua vao file? (y/n): ").strip().lower()
            if save_option == 'y':
                filename = f"interactive_search_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                self.save_results_to_file({
                    "query": query,
                    "filters": filters,
                    "top_k": top_k,
                    "results": results
                }, filename)

            return results
        except Exception as e:
            print(f"Loi: {e}")
            import traceback
            traceback.print_exc()
            return []

    def run_interactive_mode(self):
        """Chạy chế độ tương tác với menu."""
        while True:
            print("\n" + "=" * 80)
            print("MENU TIM KIEM")
            print("=" * 80)
            print("1. Tim kiem tu nhap query va filter")
            print("2. Xem danh sach filters co san")
            print("3. Goi y sach tuong tu (nhap ID)")
            print("0. Thoat")
            print("=" * 80)

            choice = input("\nChon chuc nang (0-3): ").strip()

            if choice == "1":
                self.interactive_search()
            elif choice == "2":
                self.test_get_available_filters()
            elif choice == "3":
                book_id = input("Nhap ID sach: ").strip()
                if book_id:
                    try:
                        top_k = int(input("So goi y (mac dinh 5): ").strip() or "5")
                    except ValueError:
                        top_k = 5
                    self.test_recommend_similar_books(book_id=book_id, top_k=top_k)
                else:
                    print("ID khong duoc de trong!")
            elif choice == "0":
                print("\nTam biet!")
                break
            else:
                print("Lua chon khong hop le!")


def main():
    """Main function."""
    try:
        tester = RealSearchTester()

        # Kiểm tra xem có tham số command line không
        if len(sys.argv) > 1:
            if sys.argv[1] == "--help":
                print("Su dung:")
                print("  python test_real_search_with_filters.py              # Che do tuong tac")
                print("  python test_real_search_with_filters.py --help       # Hien thi tro giup")
                return None

        # Mặc định: chạy chế độ tương tác
        tester.run_interactive_mode()

    except KeyboardInterrupt:
        print("\n\nDa dung boi nguoi dung (Ctrl+C)")
    except Exception as e:
        print(f"\nLOI CHINH: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    main()

