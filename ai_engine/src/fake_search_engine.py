"""
A lightweight in-memory fake SearchEngine to exercise API endpoints during local testing.
This is intentionally simple: documents are stored in a list with small token sets and
search is performed by token overlap. Suitable only for tests/Postman runs.
"""
from typing import List, Dict, Optional
import random

class FakeSearchEngine:
    def __init__(self):
        # simple in-memory store of documents
        # each doc: {id, title, authors, category, published_year, text, tokens, score}
        self.docs: List[Dict] = []
        self._seed_sample_data()

    def _seed_sample_data(self):
        # Add a few sample books to exercise endpoints
        samples = [
            {
                "id": "book_001",
                "title": "Python Programming: An Introduction",
                "authors": ["John Doe"],
                "category": "Programming",
                "published_year": 2021,
                "text": "An introductory book on Python programming covering basics to intermediate topics.",
            },
            {
                "id": "book_002",
                "title": "Artificial Intelligence: Foundations",
                "authors": ["Jane Smith"],
                "category": "Artificial Intelligence",
                "published_year": 2020,
                "text": "Covers core AI concepts including search, knowledge representation and learning.",
            },
            {
                "id": "book_003",
                "title": "Machine Learning for Practitioners",
                "authors": ["Alice Nguyen"],
                "category": "Machine Learning",
                "published_year": 2022,
                "text": "Practical guide to machine learning workflows and common algorithms.",
            },
            {
                "id": "book_004",
                "title": "Machine Learning for Long",
                "authors": ["Alice Long"],
                "category": "Machine Learning",
                "published_year": 2022,
                "text": "Practical guide to Hieu learning Duong and common Long.",
            },
        ]
        for s in samples:
            s["tokens"] = set((s["title"] + " " + s["text"]).lower().split())
            s["score"] = 1.0
            s["snippet"] = s["text"][:240]
            self.docs.append(s)

    def search(self, query: str, filters: Optional[Dict] = None, top_k: int = 10) -> List[Dict]:
        q_tokens = set(query.lower().split())
        ranked = []
        for d in self.docs:
            if filters:
                # simple filter handling: category or published_year
                if isinstance(filters, dict):
                    if "category" in filters and filters["category"] and filters["category"] != d.get("category"):
                        continue
                    if "published_year" in filters and filters["published_year"] and int(filters["published_year"]) != int(d.get("published_year", 0)):
                        continue
            overlap = len(q_tokens & d.get("tokens", set()))
            score = overlap + random.random() * 0.1
            if overlap > 0:
                ranked.append((score, d))
        # fallback: if nothing overlaps, return top docs by base score
        if not ranked:
            ranked = [(d.get("score", 0.1), d) for d in self.docs]
        ranked.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, d in ranked[:top_k]:
            results.append({
                "id": d["id"],
                "title": d["title"],
                "authors": d["authors"],
                "category": d.get("category"),
                "published_year": d.get("published_year"),
                "score": float(score),
                "snippet": d.get("snippet", "")
            })
        return results

    def recommend(self, book_id: str, top_k: int = 5) -> List[Dict]:
        # simple recommend: other docs in same category
        base = None
        for d in self.docs:
            if d["id"] == book_id:
                base = d
                break
        if not base:
            return []
        others = [d for d in self.docs if d["id"] != book_id and d.get("category") == base.get("category")]
        results = []
        for d in others[:top_k]:
            results.append({
                "id": d["id"],
                "title": d["title"],
                "authors": d["authors"],
                "category": d.get("category"),
                "published_year": d.get("published_year"),
                "score": 0.9,
                "snippet": d.get("snippet", "")
            })
        return results

    def get_filters(self) -> Dict:
        categories = sorted({d.get("category") for d in self.docs if d.get("category")})
        years = sorted({d.get("published_year") for d in self.docs if d.get("published_year")}, reverse=True)
        return {"categories": categories, "years": years}

    def invalidate_cache(self):
        # no-op for fake
        return


# Simple helper to create a fake search engine instance
def create_fake_search_engine():
    return FakeSearchEngine()

