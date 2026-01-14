from .rag_engine import RAGEngine


def main():
    rag = RAGEngine(top_k=5)

    print("📚 AI Library RAG Chatbot")
    print("Gõ 'exit' để thoát\n")

    while True:
        question = input("👤 Bạn: ")
        if question.lower() in ["exit", "quit"]:
            break

        answer = rag.generate_answer(question)

        print("\n🤖 Bot:")
        print(answer)
        print("-" * 60)


if __name__ == "__main__":
    main()
