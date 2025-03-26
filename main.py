import discord
from discord.ext import commands
from psycopg2 import Error
from datetime import datetime, timedelta
import pytz
from discord.ui import Button, View
import os
# 웹 서버를 위한 추가 import
from flask import Flask
import threading
from dotenv import load_dotenv
import requests  # 새로 추가
import time  # 새로 추가
import sys
from typing import Optional, List, Dict, Any

from database_manager import get_db_connection, execute_query

# 환경변수 로드
load_dotenv()

# Flask 앱 생성
app = Flask(__name__)


@app.route('/')
def home():
    return "Bot is running!"


def run_flask():
    # Render에서 제공하는 PORT 환경변수 사용
    port = int(os.getenv("PORT", 8080))
    app.run(host='0.0.0.0', port=port)


# 한국 시간대 설정
KST = pytz.timezone('Asia/Seoul')

# 상단에 개발자 ID 리스트 추가
DEVELOPER_IDS = [667375690710122526, 927476644002803742]  # 여기에 개발자의 디스코드 ID를 넣으세요


# 권한 체크 함수 추가
def is_admin_or_developer(interaction: discord.Interaction) -> bool:
    return (
            interaction.user.guild_permissions.administrator or
            interaction.user.id in DEVELOPER_IDS
    )


async def check_user_interaction(interaction: discord.Interaction, user_id: int) -> bool:
    """버튼을 클릭한 사용자가 권한이 있는지 확인합니다.
    이후 확인 결과 bool을 반환합니다."""
    if interaction.user.id != user_id:
        interaction.response.send_message("❌ 본인만 선택할 수 있습니다!", ephemeral=True)
        return False
    return True


async def update_balance(user_id: int, amount: int) -> bool:
    """user_id의 잔고를 amount만큼 업데이트합니다."""
    try:
        result = await execute_query(
            'SELECT money FROM user_money WHERE user_id = $1',
            (user_id,)
        )
        if not result or result[0]['money'] < -amount:
            return False
            
        await execute_query(
            'UPDATE user_money SET money = user_money.money + $1 WHERE user_id = $2',
            (amount, user_id)
        )
        print(f"{user_id}님의 통장에 {amount}만큼 변동이 생겼습니다.")
        return True
    except Exception as e:
        print(f"잔액 업데이트 오류: {e}")
        return False


async def check_balance(user_id: int, required_amount: int) -> bool:
    """사용자의 잔액이 요구되는 금액 이상인지 확인합니다."""
    try:
        result = await execute_query(
            'SELECT money FROM user_money WHERE user_id = $1',
            (user_id,)
        )
        return bool(result and result[0]['money'] >= required_amount)
    except Exception as e:
        print(f"잔액 확인 오류: {e}")
        return False


async def reset_attendance(user_id: int) -> bool:
    """사용자의 출석 기록을 초기화합니다."""
    try:
        await execute_query(
            'UPDATE user_attendance SET attendance_count = 0, last_attendance = NULL WHERE user_id = $1',
            (user_id,)
        )
        return True
    except Exception as e:
        print(f"출석 초기화 오류: {e}")
        return False


async def reset_money(user_id: int) -> bool:
    """사용자의 잔액을 초기화합니다."""
    try:
        await execute_query(
            'UPDATE user_money SET money = 0 WHERE user_id = $1',
            (user_id,)
        )
        return True
    except Exception as e:
        print(f"잔액 초기화 오류: {e}")
        return False


class ResetAttendanceView(View):
    def __init__(self, user_id):
        super().__init__(timeout=60)  # 60초 후 버튼 비활성화
        self.user_id = user_id
        self.value = None

    @discord.ui.button(label="✓ 확인", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        await check_user_interaction(interaction, self.user_id)

        self.value = True
        self.stop()

        try:
            if not await reset_attendance(self.user_id):
                return
            else:
                await interaction.response.edit_message(
                    content="출석 정보가 초기화되었습니다.\n💰 보유 금액은 유지됩니다.",
                    view=None
                )
        except Error as e:
            print(f"출석 정보 초기화 중 오류 발생: {e}")
            await interaction.response.send_message("❌ 출석 정보 초기화 중에 오류가 발생했습니다.", ephemeral=True)

    @discord.ui.button(label="✗ 취소", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await check_user_interaction(interaction, self.user_id)

        self.value = False
        self.stop()
        await interaction.response.edit_message(content="출석 초기화가 취소되었습니다.", view=None)


class ResetMoneyView(View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.value = None

    @discord.ui.button(label="✓ 확인", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        await check_user_interaction(interaction, self.user_id)

        self.value = True
        self.stop()

        try:
            if not await reset_money(self.user_id):
                return
            else:
                await interaction.response.edit_message(
                    content="💰 보유 금액이 0원으로 초기화되었습니다.",
                    view=None
                )
        except Error as e:
            print(f"데이터베이스 오류: {e}")
            await interaction.response.send_message("❌ 잔고 초기화 중에 오류가 발생했습니다.", ephemeral=True)

    @discord.ui.button(label="✗ 취소", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await check_user_interaction(interaction, self.user_id)

        self.value = False
        self.stop()

        await interaction.response.edit_message(content="통장 초기화가 취소되었습니다.", view=None)


class ClearAllView(View):
    def __init__(self, user_id, guild_id):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.guild_id = guild_id
        self.value = None

    @discord.ui.button(label="✓ 확인", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        await check_user_interaction(interaction, self.user_id)

        self.value = True
        self.stop()

        guild = interaction.guild
        await guild.chunk()  # 멤버 목록 다시 로드

        # 멤버 ID 목록 생성 (봇 제외)
        member_ids = [member.id for member in guild.members if not member.bot]
        print(f"초기화 대상 멤버 ID 목록: {member_ids}")  # 디버깅용

        if not member_ids:
            await interaction.response.edit_message(
                content="❌ 멤버 목록을 가져올 수 없습니다.",
                view=None
            )
            return

        conn = get_db_connection()
        if not conn:
            await interaction.response.edit_message(content="데이터베이스 연결 실패!", view=None)
            return

        try:
            cur = conn.cursor()

            # 현재 데이터베이스 상태 확인
            cur.execute('SELECT COUNT(*) FROM attendance')
            total_before = cur.fetchone()[0]

            # 멤버별로 개별 삭제 (더 안정적인 방법)
            deleted_count = 0
            for member_id in member_ids:
                cur.execute('DELETE FROM attendance WHERE user_id = %s RETURNING user_id', (member_id,))
                if cur.fetchone():
                    deleted_count += 1

            conn.commit()

            # 삭제 후 상태 확인
            cur.execute('SELECT COUNT(*) FROM attendance')
            total_after = cur.fetchone()[0]

            status_message = (
                f"✅ 서버의 출석 데이터가 초기화되었습니다.\n"
                f"- 서버: {guild.name}\n"
                f"- 처리된 멤버 수: {len(member_ids)}명\n"
                f"- 삭제된 데이터 수: {deleted_count}개\n"
                f"- 전체 레코드 변화: {total_before} → {total_after}"
            )

            print(status_message)  # 디버깅용
            await interaction.response.edit_message(content=status_message, view=None)

        except Exception as e:
            print(f"데이터베이스 초기화 중 오류 발생: {e}")
            await interaction.response.edit_message(
                content=f"❌ 데이터 초기화 중 오류가 발생했습니다.\n에러: {str(e)}",
                view=None
            )
        finally:
            conn.close()

    @discord.ui.button(label="✗ 취소", style=discord.ButtonStyle.gray)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await check_user_interaction(interaction, self.user_id)

        self.value = False
        self.stop()
        await interaction.response.edit_message(content="데이터 초기화가 취소되었습니다.", view=None)


class RankingView(View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id

    @discord.ui.button(label="1️⃣ 출석 랭킹", style=discord.ButtonStyle.primary)
    async def attendance_ranking(self, interaction: discord.Interaction, button: Button):
        await check_user_interaction(interaction, self.user_id)

        conn = get_db_connection()
        if not conn:
            await interaction.response.edit_message(content="데이터베이스 연결 실패!", view=None)
            return

        try:
            cur = conn.cursor()

            # 연속 출석 기준 데이터 조회
            cur.execute('''
                SELECT user_id, streak
                FROM attendance
                WHERE streak > 0
                ORDER BY streak DESC
            ''')

            results = cur.fetchall()

            if not results:
                await interaction.response.edit_message(
                    content="아직 출석 기록이 없습니다!",
                    view=None
                )
                return

            # 동점자 순위 처리
            ranked_results = []
            current_rank = 1
            current_streak = None
            rank_count = 0

            for user_id, streak in results:
                if streak != current_streak:
                    current_rank = rank_count + 1
                    current_streak = streak
                rank_count += 1
                ranked_results.append((current_rank, user_id, streak))
                if rank_count >= 10:  # 10등까지만 표시
                    break

            # 메시지 구성
            message = "🏆 **연속 출석 랭킹 TOP 10**\n\n"
            message += "```\n"
            message += "순위  닉네임         연속 출석\n"
            message += "--------------------------------\n"

            for rank, user_id, streak in ranked_results:
                member = interaction.guild.get_member(user_id)
                if member:
                    name = member.display_name[:10] + "..." if len(
                        member.display_name) > 10 else member.display_name.ljust(10)
                    message += f"{str(rank) + '위':4} {name:<13} {streak:>3}일\n"

            message += "```"

            await interaction.response.edit_message(content=message, view=None)

        except Exception as e:
            print(f"랭킹 조회 중 오류 발생: {e}")
            await interaction.response.edit_message(
                content="랭킹 조회 중 오류가 발생했습니다.",
                view=None
            )
        finally:
            conn.close()

    @discord.ui.button(label="2️⃣ 보유 금액 랭킹", style=discord.ButtonStyle.primary)
    async def money_ranking(self, interaction: discord.Interaction, button: Button):
        await check_user_interaction(interaction, self.user_id)

        conn = get_db_connection()
        if not conn:
            await interaction.response.edit_message(content="데이터베이스 연결 실패!", view=None)
            return

        try:
            cur = conn.cursor()

            # 보유 금액 기준 데이터 조회
            cur.execute('''
                SELECT user_id, money
                FROM user_money
                WHERE money > 0
                ORDER BY money DESC
            ''')

            results = cur.fetchall()

            if not results:
                await interaction.response.edit_message(
                    content="아직 보유 금액 기록이 없습니다!",
                    view=None
                )
                return

            # 동점자 순위 처리
            ranked_results = []
            current_rank = 1
            current_money = None
            rank_count = 0

            for user_id, money in results:
                if money != current_money:
                    current_rank = rank_count + 1
                    current_money = money
                rank_count += 1
                ranked_results.append((current_rank, user_id, money))
                if rank_count >= 10:  # 10등까지만 표시
                    break

            # 메시지 구성
            message = "💰 **보유 금액 랭킹 TOP 10**\n\n"
            message += "```\n"
            message += "순위  닉네임         보유 금액\n"
            message += "--------------------------------\n"

            for rank, user_id, money in ranked_results:
                member = interaction.guild.get_member(user_id)
                if member:
                    name = member.display_name[:10] + "..." if len(
                        member.display_name) > 10 else member.display_name.ljust(10)
                    message += f"{str(rank) + '위':4} {name:<13} {money:>6}원\n"

            message += "```"

            await interaction.response.edit_message(content=message, view=None)

        except Exception as e:
            print(f"랭킹 조회 중 오류 발생: {e}")
            await interaction.response.edit_message(
                content="랭킹 조회 중 오류가 발생했습니다.",
                view=None
            )
        finally:
            conn.close()


class AttendanceBot(commands.Bot):
    def __init__(self):
        print("\n=== 봇 초기화 시작 ===", flush=True)
        sys.stdout.flush()
        # 필요한 모든 인텐트 추가
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True  # 서버 정보 접근 권한 추가
        intents.guild_messages = True  # 서버 메시지 접근 권한 추가
        super().__init__(command_prefix='!', intents=intents)

        print("봇 인스턴스 생성 완료", flush=True)
        sys.stdout.flush()
        self._db_initialized = False
        self.attendance_channels = set()

        print("=== 봇 초기화 완료 ===\n", flush=True)
        sys.stdout.flush()

    async def setup_hook(self):
        # 데이터베이스 초기화
        try:
            await execute_query('''
                CREATE TABLE IF NOT EXISTS user_attendance (
                    user_id BIGINT PRIMARY KEY,
                    attendance_count INTEGER DEFAULT 0,
                    last_attendance TIMESTAMP,
                    streak_count INTEGER DEFAULT 0
                )
            ''')
            
            await execute_query('''
                CREATE TABLE IF NOT EXISTS user_money (
                    user_id BIGINT PRIMARY KEY,
                    money INTEGER DEFAULT 0
                )
            ''')
            
            await execute_query('''
                CREATE TABLE IF NOT EXISTS attendance_channels (
                    channel_id BIGINT PRIMARY KEY,
                    guild_id BIGINT NOT NULL
                )
            ''')
        except Exception as e:
            print(f"데이터베이스 초기화 오류: {e}")

        # 출석 채널 로드
        try:
            result = await execute_query('SELECT channel_id FROM attendance_channels')
            self.attendance_channels = {row['channel_id'] for row in result}
        except Exception as e:
            print(f"출석 채널 로드 오류: {e}")
            self.attendance_channels = set()

        # 모든 cog 로드
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await self.load_extension(f'cogs.{filename[:-3]}')
        
        # 명령어 동기화
        await self.tree.sync()

    async def on_ready(self):
        print("\n" + "=" * 50, flush=True)
        print("봇이 준비되었습니다!", flush=True)
        print(f"봇 이름: {self.user}", flush=True)
        print(f"봇 ID: {self.user.id}", flush=True)
        print(f"서버 수: {len(self.guilds)}", flush=True)

        print("=" * 50 + "\n", flush=True)


bot = AttendanceBot()


def keep_alive():
    """15분마다 자체 서버에 핑을 보내 슬립모드 방지"""
    while True:
        try:
            # Render에서 제공하는 URL 환경변수 사용
            url = os.getenv('RENDER_EXTERNAL_URL', 'http://localhost:8080')
            response = requests.get(url)
            print(f"서버 핑 전송 완료: {response.status_code}", flush=True)
        except Exception as e:
            print(f"서버 핑 전송 실패: {e}", flush=True)
        time.sleep(840)  # 14분(840초)마다 실행 (15분보다 약간 짧게 설정)


# 봇 실행 부분 수정
if __name__ == "__main__":
    print("\n=== 봇 시작 ===", flush=True)
    # Flask 서버를 별도 스레드에서 실행
    server_thread = threading.Thread(target=run_flask)
    server_thread.start()
    print("Flask 서버 스레드 시작됨", flush=True)

    # 핑 전송을 위한 새로운 스레드 시작
    ping_thread = threading.Thread(target=keep_alive, daemon=True)
    ping_thread.start()
    print("핑 전송 스레드 시작됨", flush=True)

    # 봇 토큰 설정 및 실행
    TOKEN = os.getenv('DISCORD_TOKEN')
    if not TOKEN:
        raise ValueError("DISCORD_TOKEN 환경 변수가 설정되지 않았습니다!")

    print("봇 실행 시작...", flush=True)
    bot.run(TOKEN)
