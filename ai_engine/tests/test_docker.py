import mysql.connector

print("Testing direct MySQL connection...")

try:
    conn = mysql.connector.connect(
        host="localhost",
        port=3307,
        user="root",
        password="root",
        database="library_db"
    )

    print("[SUCCESS] Connected to MySQL!")

    cursor = conn.cursor()

    # Test 1: Count roles
    cursor.execute("SELECT COUNT(*) FROM roles")
    count = cursor.fetchone()[0]
    print(f"Roles count: {count}")

    # Test 2: List roles
    cursor.execute("SELECT name FROM roles")
    roles = cursor.fetchall()
    print("Roles:")
    for role in roles:
        print(f"  - {role[0]}")

    cursor.close()
    conn.close()

    print("\n[ALL TESTS PASSED]")

except mysql.connector.Error as e:
    print(f"[ERROR] MySQL Error: {e}")
except Exception as e:
    print(f"[ERROR] {e}")