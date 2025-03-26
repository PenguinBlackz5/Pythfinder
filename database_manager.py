import os
import asyncpg
from typing import Optional, List, Dict, Any
import aiopg
from dotenv import load_dotenv

# .env 파일에서 환경 변수 로드
load_dotenv()

# 전역 연결 풀
_pool: Optional[asyncpg.Pool] = None


async def get_db_pool() -> asyncpg.Pool:
    """데이터베이스 연결 풀을 가져옵니다."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(os.getenv('DATABASE_URL'))
    return _pool


async def get_db_connection() -> Optional[asyncpg.Connection]:
    """데이터베이스 연결을 가져옵니다."""
    try:
        pool = await get_db_pool()
        return await pool.acquire()
    except Exception as e:
        print(f"데이터베이스 연결 오류: {e}")
        return None


async def execute_query(query: str, params: Optional[tuple] = None) -> Optional[List[Dict[str, Any]]]:
    """쿼리를 실행하고 결과를 반환합니다."""
    pool = await get_db_pool()
    conn = await get_db_connection()

    if not conn:
        return None

    try:
        if query.strip().upper().startswith('SELECT'):
            return await conn.fetch(query, *params) if params else await conn.fetch(query)
        else:
            await conn.execute(query, *params) if params else await conn.execute(query)
            return None
    except Exception as e:
        print(f"쿼리 실행 오류: {e}")
        raise
    finally:
        await pool.release(conn)
