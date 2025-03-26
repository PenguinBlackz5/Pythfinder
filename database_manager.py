import os
import asyncio
from typing import Optional, List, Dict, Any
import aiopg
from dotenv import load_dotenv

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
            else:
                await conn.commit()
                return []
    finally:
        conn.close()
