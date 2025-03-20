import os
import psycopg2
from dotenv import load_dotenv

# Render 데이터베이스 URL (기존 데이터베이스)
RENDER_DATABASE_URL = "postgresql://pythfinder_user:6bVZHqFdCkdUxqabX9nWL7MvUuFPqu0y@dpg-cv7fa7lumphs738hp3ig-a.oregon-postgres.render.com/pythfinder"

# Neon 데이터베이스 URL (새 데이터베이스)
load_dotenv()
NEON_DATABASE_URL = os.getenv('DATABASE_URL')

def migrate_data():
    """Render에서 Neon으로 데이터를 마이그레이션합니다."""
    try:
        # Render 데이터베이스 연결
        render_conn = psycopg2.connect(RENDER_DATABASE_URL)
        render_cur = render_conn.cursor()

        # Neon 데이터베이스 연결
        neon_conn = psycopg2.connect(NEON_DATABASE_URL)
        neon_cur = neon_conn.cursor()

        # attendance 테이블 데이터 마이그레이션
        print("attendance 테이블 데이터 마이그레이션 중...")
        render_cur.execute("SELECT * FROM attendance")
        attendance_data = render_cur.fetchall()
        
        for row in attendance_data:
            neon_cur.execute("""
                INSERT INTO attendance (user_id, last_attendance, streak, money)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    last_attendance = EXCLUDED.last_attendance,
                    streak = EXCLUDED.streak,
                    money = EXCLUDED.money
            """, row)

        # channels 테이블 데이터 마이그레이션
        print("channels 테이블 데이터 마이그레이션 중...")
        render_cur.execute("SELECT * FROM channels")
        channels_data = render_cur.fetchall()
        
        for row in channels_data:
            neon_cur.execute("""
                INSERT INTO channels (channel_id)
                VALUES (%s)
                ON CONFLICT (channel_id) DO NOTHING
            """, row)

        # 변경사항 저장
        neon_conn.commit()
        print("데이터 마이그레이션이 완료되었습니다!")

    except Exception as e:
        print(f"마이그레이션 중 오류 발생: {e}")
        if 'neon_conn' in locals():
            neon_conn.rollback()
    finally:
        if 'render_cur' in locals():
            render_cur.close()
        if 'render_conn' in locals():
            render_conn.close()
        if 'neon_cur' in locals():
            neon_cur.close()
        if 'neon_conn' in locals():
            neon_conn.close()

if __name__ == "__main__":
    migrate_data() 