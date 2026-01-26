from .rag_engine import RAGEngine


def main():
    """Main chat loop for CLI testing"""
    
    # Initialize RAG Engine
    rag = RAGEngine(top_k=5)

    print("="*60)
    print("AI Library RAG Chatbot")
    print("="*60)
    print("Gõ 'exit' để thoát\n")

    # Hardcoded suggestions (don't rely on non-existent method)
    suggestions = [
        "Tìm sách về Python",
        "Sách Machine Learning hay nhất",
        "Thư viện có bao nhiêu cuốn sách?",
        "Giờ mở cửa thư viện?",
        "Quy định mượn sách như thế nào?"
    ]

    # Show suggestions
    print("Gợi ý câu hỏi:")
    for i, q in enumerate(suggestions, start=1):
        print(f"  {i}. {q}")

    print(f"\nBạn có thể nhập số (1-{len(suggestions)}) hoặc gõ câu hỏi riêng.\n")

    # Main chat loop
    while True:
        try:
            question = input("Ban: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nThoát...")
            break
            
        if not question:
            continue
            
        if question.lower() in ["exit", "quit", "q"]:
            print("Tạm biệt!")
            break

        # Check if user input is a number (selecting suggestion)
        if question.isdigit():
            idx = int(question) - 1
            if 0 <= idx < len(suggestions):
                question = suggestions[idx]
                print(f">> Bạn chọn: {question}")
            else:
                print("Số không hợp lệ. Vui lòng chọn từ 1-{}.".format(len(suggestions)))
                continue

        # Generate answer
        try:
            # Use a static session ID for CLI (or generate random one at start)
            if not hasattr(main, "session_id"):
                import uuid
                main.session_id = str(uuid.uuid4())
                
            answer = rag.generate_answer(question, session_id=main.session_id)
            print("\nBot:")
            print(answer)
        except Exception as e:
            print(f"\nLỗi: {e}")
        
        print("-" * 60)


if __name__ == "__main__":
    main()
