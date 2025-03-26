import os
import asyncio
from typing import Optional, List, Dict, Any
import aiopg
from dotenv import load_dotenv

# .env 파일에서 환경 변수 로드
load_dotenv()

# 전역 연결 풀 변수
_pool: Optional[aiopg.Pool] = None

async def get_db_pool() -> aiopg.Pool:
    """데이터베이스 연결 풀을 가져옵니다."""
    global _pool
    if _pool is None:
        _pool = await aiopg.create_pool(
            dsn=os.getenv('DATABASE_URL'),
            minsize=1,
            maxsize=10
        )
    return _pool

async def get_db_connection() -> aiopg.Connection:
    """데이터베이스 연결을 가져옵니다."""
    pool = await get_db_pool()
    return await pool.acquire()

async def execute_query(query: str, *args) -> List[Dict[str, Any]]:
    """SQL 쿼리를 실행하고 결과를 반환합니다."""
    conn = await get_db_connection()
    try:
        async with conn.cursor() as cur:
            await cur.execute(query, args)
            if query.strip().upper().startswith('SELECT'):
                result = await cur.fetchall()
                columns = [desc[0] for desc in cur.description]
                return [dict(zip(columns, row)) for row in result]
            else:
                await conn.commit()
                return []
    finally:
        pool = await get_db_pool()
        pool.release(conn)
