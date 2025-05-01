from dotenv import load_dotenv
load_dotenv(override=True)
import os
import psycopg2

# 1) load your .env
load_dotenv()

DB_NAME = os.getenv("DATABASE_NAME")
DB_HOST = os.getenv("HOST")
DB_PORT = os.getenv("PORT")
DB_USER = os.getenv("USERNAME")
DB_PASS = os.getenv("PASSWORD")

# 2) connect directly to your database
conn = psycopg2.connect(
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASS,
    host=DB_HOST,
    port=DB_PORT,
    sslmode="require"
)

conn.autocommit = True
cur = conn.cursor()

try:
    # 3) drop the entire public schema (all tables, views, etc.)
    cur.execute('DROP SCHEMA public CASCADE;')

    # 4) recreate it empty
    cur.execute('CREATE SCHEMA public;')

    print(f"✅ Database “{DB_NAME}” has been completely reset.")
finally:
    cur.close()
    conn.close()
