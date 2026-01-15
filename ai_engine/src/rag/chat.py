from .rag_engine import RAGEngine


def main():
    # ===============================
    # 1️⃣ KHỞI TẠO RAG ENGINE
    # ===============================
    # top_k = 5 nghĩa là mỗi lần hỏi sẽ lấy 5 document gần nhất trong vector DB
    rag = RAGEngine(top_k=5)

    # ===============================
    # 2️⃣ HIỂN THỊ TIÊU ĐỀ CHƯƠNG TRÌNH
    # ===============================
    print("📚 AI Library RAG Chatbot")
    print("Gõ 'exit' để thoát\n")

    # ===============================
    # 3️⃣ LẤY DANH SÁCH CÂU HỎI GỢI Ý
    # ===============================
    # Các câu này thường được sinh sẵn từ hệ thống (FAQ / popular questions)
    suggestions = rag.get_suggested_questions()

    # ===============================
    # 4️⃣ HIỂN THỊ DANH SÁCH GỢI Ý
    # ===============================
    print("💡 Gợi ý câu hỏi:")
    for i, q in enumerate(suggestions, start=1):
        print(f"  {i}. {q}")

    print("\n👉 Bạn có thể nhập số (1–{}) hoặc gõ câu hỏi riêng.\n".format(len(suggestions)))

    # ===============================
    # 5️⃣ VÒNG LẶP CHAT CHÍNH
    # ===============================
    while True:
        # Nhận input từ người dùng
        user_input = input("👤 Bạn: ").strip()

        # ===============================
        # 5.1️⃣ THOÁT CHƯƠNG TRÌNH
        # ===============================
        if user_input.lower() in ["exit", "quit"]:
            print("👋 Tạm biệt!")
            break

        # ===============================
        # 5.2️⃣ KIỂM TRA XEM USER CÓ NHẬP SỐ KHÔNG
        # ===============================
        # Nếu user nhập số -> chọn câu hỏi gợi ý
        if user_input.isdigit():
            idx = int(user_input) - 1

            # Kiểm tra chỉ số có hợp lệ không
            if 0 <= idx < len(suggestions):
                question = suggestions[idx]
                print(f"👉 Bạn chọn: {question}")
            else:
                print("❌ Số không hợp lệ.")
                continue

        # ===============================
        # 5.3️⃣ NGƯỜI DÙNG NHẬP CÂU HỎI TỰ DO
        # ===============================
        else:
            question = user_input

        # ===============================
        # 6️⃣ GỌI RAG ENGINE ĐỂ SINH CÂU TRẢ LỜI
        # ===============================
        # Bên trong sẽ:
        #   - Embed câu hỏi
        #   - Search vector DB (Chroma / FAISS / etc)
        #   - Lấy top_k document liên quan
        #   - Gửi context + question cho LLM
        answer = rag.generate_answer(question)

        # ===============================
        # 7️⃣ HIỂN THỊ KẾT QUẢ
        # ===============================
        print("\n🤖 Bot:")
        print(answer)
        print("-" * 60)


# ===============================
# 8️⃣ ĐIỂM ENTRY POINT CỦA CHƯƠNG TRÌNH
# ===============================
if __name__ == "__main__":
    main()
