from .rag_engine import RAGEngine


def main():
    rag = RAGEngine(top_k=5)

    print("📚 AI Library RAG Chatbot")
    print("Gõ 'exit' để thoát\n")

    # ===============================
    # 👉 HIỂN THỊ CÂU HỎI GỢI Ý
    # ===============================
    suggestions = rag.get_suggested_questions()

    print("💡 Gợi ý câu hỏi:")
    for i, q in enumerate(suggestions, start=1):
        print(f"  {i}. {q}")
    print("\n👉 Bạn có thể nhập số (1–{}) hoặc gõ câu hỏi riêng.\n".format(len(suggestions)))

    while True:
        user_input = input("👤 Bạn: ").strip()

        if user_input.lower() in ["exit", "quit"]:
            break

        # ===============================
        # 👉 CHỌN THEO SỐ
        # ===============================
        if user_input.isdigit():
            idx = int(user_input) - 1
            if 0 <= idx < len(suggestions):
                question = suggestions[idx]
                print(f"👉 Bạn chọn: {question}")
            else:
                print("❌ Số không hợp lệ.")
                continue
        else:
            question = user_input

        answer = rag.generate_answer(question)

        print("\n🤖 Bot:")
        print(answer)
        print("-" * 60)


if __name__ == "__main__":
    main()
