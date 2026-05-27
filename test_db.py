import psycopg2
try:
    conn = psycopg2.connect(
        dbname='schoollibrary_db',
        user='schoollibrary_user',
        password='postgres',
        host='localhost',
        port='5432'
    )
    print('✅ PostgreSQL connection successful!')
    conn.close()
except Exception as e:
    print(f'❌ PostgreSQL connection failed: {e}')