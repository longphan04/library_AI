import pymysql

conn = pymysql.connect(
    host="shuttle.proxy.rlwy.net",
    port=32138,
    user="root",
    password="VZCXvjsAFkAZbqaZuuZlCzxDoNGrXVen",
    database="railway",
    connect_timeout=10
)

print("✅ CONNECT OK!")

cur = conn.cursor()
cur.execute("SHOW TABLES;")
print("Tables:", cur.fetchall())

conn.close()
