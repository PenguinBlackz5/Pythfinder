import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    """데이터베이스 연결을 생성합니다."""
    try:
        connection = psycopg2.connect(
            os.getenv('DATABASE_URL'),
            cursor_factory=RealDictCursor
        )
        return connection
    except Exception as e:
        print(f"데이터베이스 연결 오류: {e}")
        raise

def execute_query(query, params=None):
    """쿼리를 실행하고 결과를 반환합니다."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            if query.strip().upper().startswith('SELECT'):
                return cur.fetchall()
            conn.commit()
            return None
    except Exception as e:
        conn.rollback()
        print(f"쿼리 실행 오류: {e}")
        raise
    finally:
        conn.close() 