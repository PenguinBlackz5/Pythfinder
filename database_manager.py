import os
import asyncio
from typing import Optional, List, Dict, Any
import aiopg
from dotenv import load_dotenv

# .env 파일에서 환경 변수 로드
load_dotenv()

# 전역 연결 풀 변수
db_pool = None

async def get_db_pool():
    """데이터베이스 연결 풀을 생성합니다."""
    global db_pool
    if db_pool is None:
        dsn = os.getenv('DATABASE_URL')
        db_pool = await aiopg.create_pool(dsn, minsize=1, maxsize=10)
    return db_pool

async def get_db_connection():
    """데이터베이스 연결을 가져옵니다."""
    pool = await get_db_pool()
    return await pool.acquire()

async def execute_query(query: str, params: tuple = None) -> List[Dict[str, Any]]:
    """SQL 쿼리를 실행하고 결과를 반환합니다."""
    conn = await get_db_connection()
    try:
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            if query.strip().upper().startswith('SELECT'):
                result = await cur.fetchall()
                columns = [desc[0] for desc in cur.description]
                return [dict(zip(columns, row)) for row in result]
            return []
    finally:
        conn.close()

async def init_database():
    """데이터베이스를 초기화합니다."""
    # 테이블 생성 쿼리들
    queries = [
        """
        CREATE TABLE IF NOT EXISTS user_money (
            user_id BIGINT PRIMARY KEY,
            balance BIGINT DEFAULT 0,
            last_attendance TIMESTAMP,
            attendance_streak INTEGER DEFAULT 0
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS attendance_channels (
            channel_id BIGINT PRIMARY KEY
        )
        """
    ]
    
    for query in queries:
        await execute_query(query)
