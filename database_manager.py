import os
import asyncpg
from typing import Optional, List, Dict, Any
import aiopg
from dotenv import load_dotenv
import sentry_sdk

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

        elif "RETURNING" in query.upper():
            return await conn.fetch(query, *params) if params else await conn.fetch(query)

        else:
            await conn.execute(query, *params) if params else await conn.execute(query)
            return None
    except Exception as e:
        print(f"쿼리 실행 오류: {e}")
        sentry_sdk.capture_exception(e)
        raise
    finally:
        await pool.release(conn)

# --- Dccon 즐겨찾기 기능 함수 ---

async def add_dccon_favorite(user_id: int, title: str, image_url: str, local_path: str) -> bool:
    """사용자의 디시콘 즐겨찾기를 추가합니다."""
    query = """
        INSERT INTO favorited_dccons (user_id, dccon_title, image_url, local_path)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (user_id, image_url) DO NOTHING;
    """
    try:
        await execute_query(query, (user_id, title, image_url, local_path))
        return True
    except Exception as e:
        print(f"즐겨찾기 추가 중 오류 발생: {e}")
        return False

async def remove_dccon_favorite(user_id: int, image_url: str) -> Optional[str]:
    """사용자의 디시콘 즐겨찾기를 삭제하고, 로컬 파일 경로를 반환합니다."""
    query = """
        DELETE FROM favorited_dccons
        WHERE user_id = $1 AND image_url = $2
        RETURNING local_path;
    """
    try:
        result = await execute_query(query, (user_id, image_url))
        if result:
            return result[0]['local_path']
        return None
    except Exception as e:
        print(f"즐겨찾기 삭제 중 오류 발생: {e}")
        return None

async def get_user_favorites(user_id: int) -> List[Dict[str, Any]]:
    """특정 사용자의 모든 디시콘 즐겨찾기 목록을 가져옵니다."""
    query = "SELECT dccon_title, image_url, local_path FROM favorited_dccons WHERE user_id = $1 ORDER BY favorited_at DESC;"
    try:
        favorites = await execute_query(query, (user_id,))
        return favorites if favorites else []
    except Exception as e:
        print(f"즐겨찾기 목록 조회 중 오류 발생: {e}")
        return []

async def is_dccon_favorited(user_id: int, image_url: str) -> bool:
    """사용자가 해당 이미지를 이미 즐겨찾기 했는지 확인합니다."""
    query = "SELECT 1 FROM favorited_dccons WHERE user_id = $1 AND image_url = $2;"
    try:
        result = await execute_query(query, (user_id, image_url))
        return bool(result)
    except Exception as e:
        print(f"즐겨찾기 확인 중 오류 발생: {e}")
        return False
