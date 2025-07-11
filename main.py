import asyncio
import discord
from discord.ext import commands
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

import logging
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

from database_manager import get_db_connection, execute_query, get_db_pool
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

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

# 개발자 ID 리스트
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
            'SELECT balance FROM user_balance WHERE user_id = $1',
            (user_id,)
        )
        if not result or result[0]['balance'] < -amount:
            return False

        await execute_query(
            'UPDATE user_balance SET balance = user_balance.balance + $1 WHERE user_id = $2',
            (amount, user_id)
        )
        logger.info(f"{user_id}님의 통장에 {amount}만큼 변동이 생겼습니다.")
        return True
    except Exception as e:
        logger.error(f"잔액 업데이트 오류: {e}")
        return False


async def check_balance(user_id: int, required_amount: int) -> bool:
    """사용자의 잔액이 요구되는 금액 이상인지 확인합니다."""
    try:
        result = await execute_query(
            'SELECT balance FROM user_balance WHERE user_id = $1',
            (user_id,)
        )
        return bool(result and result[0]['money'] >= required_amount)
    except Exception as e:
        logger.error(f"잔액 확인 오류: {e}")
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
        logger.error(f"출석 초기화 오류: {e}")
        return False


async def reset_money(user_id: int) -> bool:
    """사용자의 잔액을 초기화합니다."""
    try:
        await execute_query(
            'UPDATE user_balance SET balance = 0 WHERE user_id = $1',
            (user_id,)
        )
        return True
    except Exception as e:
        logger.error(f"잔액 초기화 오류: {e}")
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
        except Exception as e:
            logger.error(f"출석 정보 초기화 중 오류 발생: {e}")
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
        except Exception as e:
            logger.error(f"데이터베이스 오류: {e}")
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
        print(f"초기화 대상 멤버 ID 목록: {member_ids}")

        if not member_ids:
            await interaction.response.edit_message(
                content="❌ 멤버 목록을 가져올 수 없습니다.",
                view=None
            )
            return

        # 현재 데이터베이스 상태 확인
        total_before = await execute_query('SELECT COUNT(*) FROM user_attendance')

        # 멤버별로 개별 삭제 (더 안정적인 방법)
        deleted_count = 0
        for member_id in member_ids:
            await execute_query('DELETE FROM user_attendance WHERE user_id = $1 RETURNING user_id', (member_id,))

        # 삭제 후 상태 확인
        total_after = await execute_query('SELECT COUNT(*) FROM user_attendance')

        status_message = (
            f"✅ 서버의 출석 데이터가 초기화되었습니다.\n"
            f"- 서버: {guild.name}\n"
            f"- 처리된 멤버 수: {len(member_ids)}명\n"
            f"- 삭제된 데이터 수: {deleted_count}개\n"
            f"- 전체 레코드 변화: {total_before} → {total_after}"
        )

        print(status_message)
        await interaction.response.edit_message(content=status_message, view=None)

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

        # 연속 출석 기준 데이터 조회
        results = await execute_query('''
            SELECT user_id, streak_count
            FROM user_attendance
            WHERE streak_count > 0
            ORDER BY streak_count DESC
        ''')

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

        await interaction.response.edit_message(content=message)

    @discord.ui.button(label="2️⃣ 보유 금액 랭킹", style=discord.ButtonStyle.primary)
    async def money_ranking(self, interaction: discord.Interaction, button: Button):
        await check_user_interaction(interaction, self.user_id)
        conn = get_db_connection()
        if not conn:
            await interaction.response.edit_message(content="데이터베이스 연결 실패!", view=None)
            return

        # 보유 금액 기준 데이터 조회
        results = await execute_query('''
            SELECT user_id, balance
            FROM user_balance
            WHERE balance > 0
            ORDER BY balance DESC
        ''')

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


async def is_duplicate_message_in_day(user_id: int) -> bool:
    """오늘 이미 메시지를 보냈는지 확인합니다."""
    today_kst = datetime.now(KST).strftime('%Y-%m-%d')

    result = await execute_query("SELECT 1 FROM daily_chat_log WHERE user_id = $1 AND chat_date = $2",
                                 (user_id, today_kst))
    if result:  # 이미 기록이 있으면 True 반환
        logger.info(f"사용자 {user_id}는 오늘({today_kst}) 이미 메시지를 보냈습니다.")
        return True
    else:
        # 오늘 첫 메시지이므로 기록 추가 후 false 반환
        await execute_query(
            "INSERT INTO daily_chat_log (user_id, chat_date) VALUES ($1, $2)"
            "ON CONFLICT (user_id, chat_date) DO nothing",
            (user_id, today_kst)
        )
        logger.info(f"사용자 {user_id}의 오늘({today_kst}) 첫 메시지를 기록했습니다.")
        return False


async def clear_daily_log():
    await execute_query("DELETE FROM daily_chat_log;")
    logger.info(f"clear_daily_log_ KST 실행 시간: {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S %Z%z')}")


class AttendanceBot(commands.Bot):
    def __init__(self):
        # 기본 인텐트 설정
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        intents.guild_messages = True

        # 부모 클래스 초기화
        super().__init__(command_prefix='!', intents=intents)

        # 기본 속성 초기화
        self.attendance_channels = set()
        self._processing_messages = set()
        self._message_sent = set()
        self._attendance_cache = {}
        self._message_history = {}
        self._message_lock = asyncio.Lock()

    @property
    def processing_messages(self):
        return self._processing_messages

    @property
    def message_sent(self):
        return self._message_sent

    @property
    def attendance_cache(self):
        return self._attendance_cache

    @property
    def message_history(self):
        return self._message_history

    @property
    def message_lock(self):
        return self._message_lock

    def is_message_processed(self, message_id: int) -> bool:
        """메시지가 이미 처리되었는지 확인합니다."""
        return message_id in self.processing_messages or message_id in self.message_sent

    def mark_message_as_processed(self, message_id: int):
        """메시지를 처리 완료로 표시합니다."""
        self.message_sent.add(message_id)
        if message_id in self.processing_messages:
            self.processing_messages.remove(message_id)

    def mark_message_as_processing(self, message_id: int):
        """메시지를 처리 중으로 표시합니다."""
        self.processing_messages.add(message_id)

    def clear_processing_message(self, message_id: int):
        """메시지의 처리 중 상태를 제거합니다."""
        if message_id in self.processing_messages:
            self.processing_messages.remove(message_id)

    def update_message_history(self, user_id: int, today: str):
        """메시지 히스토리를 업데이트합니다."""
        cache_key = f"{user_id}_{today}"
        self.message_history[cache_key] = datetime.now(KST)

    def is_duplicate_message(self, user_id: int, today: str) -> bool:
        """5초 이내의 중복 메시지인지 확인합니다."""
        cache_key = f"{user_id}_{today}"
        if cache_key in self.message_history:
            last_message_time = self.message_history[cache_key]
            current_time = datetime.now(KST)
            time_diff = (current_time - last_message_time).total_seconds()
            return time_diff < 5
        return False

    async def setup_hook(self):
        # 데이터베이스 연결 풀 생성
        await get_db_pool()

        # sql/ 디렉토리의 모든 .sql 파일을 읽어 테이블 생성
        sql_dir = 'sql'
        if os.path.isdir(sql_dir):
            for filename in sorted(os.listdir(sql_dir)):
                if filename.endswith('.sql'):
                    filepath = os.path.join(sql_dir, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            sql_script = f.read()
                            # 주석 등을 제외하고 실제 쿼리가 있는지 확인
                            if sql_script.strip():
                                await execute_query(sql_script)
                                print(f"✅ SQL 스크립트 '{filename}' 실행 완료.")
                    except Exception as e:
                        print(f"❌ SQL 스크립트 '{filename}' 실행 중 오류 발생: {e}")

        # Cogs 로드
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    print(f"로드 중: {filename}", flush=True)
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    print(f"로드 완료: {filename}", flush=True)
                except Exception as e:
                    logger.error(f"Cog 로드 오류 ({filename}): {e}")

        # 명령어 동기화
        print("명령어 동기화 중...", flush=True)
        try:
            await self.tree.sync()
            print("명령어 동기화 완료", flush=True)
        except Exception as e:
            logger.error(f"명령어 동기화 오류: {e}")

        print("=== 봇 초기화 완료 ===\n", flush=True)

    async def on_ready(self):
        print("\n" + "=" * 50, flush=True)
        print("봇이 준비되었습니다!", flush=True)
        print(f"봇 이름: {self.user}", flush=True)
        print(f"봇 ID: {self.user.id}", flush=True)
        print(f"서버 수: {len(self.guilds)}", flush=True)
        print(f"캐시된 메시지 수: {len(self.message_sent)}", flush=True)
        print(f"처리 중인 메시지 수: {len(self.processing_messages)}", flush=True)

        # 봇이 준비되면 출석 채널 다시 로드
        await self.load_attendance_channels()

        scheduler = AsyncIOScheduler(timezone='Asia/Seoul')
        # 매일 새벽 0시에 데이터베이스 채팅 기록 지우기
        scheduler.add_job(clear_daily_log, CronTrigger(hour=0, timezone=KST))
        scheduler.start()

        print("=" * 50 + "\n", flush=True)

    async def load_attendance_channels(self):
        """출석 채널 목록을 로드합니다."""
        try:
            result = await execute_query('SELECT channel_id FROM attendance_channels')
            self.attendance_channels = {row['channel_id'] for row in result}
        except Exception as e:
            logger.error(f"출석 채널 로드 오류: {e}")
            self.attendance_channels = set()

    async def on_message(self, message):
        logger.info(f"{message.author.name}의 메시지 이벤트 발생", extra={
            'message_id': message.id,
            'author_name': message.author.name,
            'message_content': message.content,
        })

        # DM 채널인 경우 명령어만 처리하고 종료
        if isinstance(message.channel, discord.DMChannel):
            print("DM 채널 메시지 - 명령어만 처리", flush=True)
            await self.process_commands(message)
            return

        # 채널 정보 출력 (DM이 아닌 경우에만)
        try:
            print(f"채널: {message.channel.name}", flush=True)
            print(f"채널 ID: {message.channel.id}", flush=True)
            print(f"등록된 출석 채널: {self.attendance_channels}", flush=True)
        except AttributeError:
            logger.error("채널 정보를 가져올 수 없습니다.")

        print("=" * 50 + "\n", flush=True)

        # 봇 메시지 무시
        if message.author == self.user or message.author.bot:
            print("봇 메시지 무시", flush=True)
            return

        # 명령어 처리 시도
        await self.process_commands(message)

        # 출석 채널이 아닌 경우 무시
        if message.channel.id not in self.attendance_channels:
            print("출석 채널이 아님. 무시", flush=True)
            return

        # 이미 처리된 메시지인지 확인
        if self.is_message_processed(message.id):
            print("이미 처리된 메시지. 무시", flush=True)
            return

        print("출석 처리 중...")

        try:
            # 메시지를 처리 중으로 표시
            self.mark_message_as_processing(message.id)

            user_id = message.author.id
            today = datetime.now(KST).strftime('%Y-%m-%d')
            today_date = datetime.strptime(today, "%Y-%m-%d").date()

            # 중복 출석 체크
            if await is_duplicate_message_in_day(user_id):
                logger.info(f"중복 출석 감지: {message.author.name}")
                await message.channel.send(f"❌ {message.author.mention}님은 이미 오늘 출석하셨습니다!", delete_after=3)
                self.mark_message_as_processed(message.id)
                return

            # 출석 처리
            result = await execute_query(
                '''
                INSERT INTO user_attendance (user_id, attendance_count, last_attendance, streak_count)
                VALUES ($1, 1, $2, 1)
                ON CONFLICT (user_id) DO UPDATE
                SET 
                    attendance_count = user_attendance.attendance_count + 1,
                    last_attendance = $2,
                    streak_count = CASE 
                        WHEN DATE(user_attendance.last_attendance) = DATE($2 - INTERVAL '1 day')
                        THEN user_attendance.streak_count + 1
                        WHEN DATE(user_attendance.last_attendance) = DATE($2)
                        THEN user_attendance.streak_count
                        ELSE 1
                    END
                RETURNING attendance_count, streak_count
                ''',
                (user_id, today_date)
            )

            if result:
                attendance_count = result[0]['attendance_count']
                streak_count = result[0]['streak_count']

                # 보상 지급
                reward = 100 + (streak_count * 10)
                await update_balance(user_id, reward)

                # 출석 순서 확인
                result = await execute_query('''
                    SELECT COUNT(*) AS count 
                    FROM user_attendance
                    WHERE DATE(last_attendance) = DATE($1) 
                    AND user_id != $2
                ''', (today_date, user_id))

                attendance_order = result[0]["count"] + 1

                await message.channel.send(
                    f"🎉 {message.author.mention}님 출석하셨습니다!\n"
                    f"오늘 {attendance_order}번째 출석이에요.\n"
                    f"현재 총 출석 횟수: {attendance_count}회,\n"
                    f"연속 출석: {streak_count}일\n"
                    f"💰 보상: {reward}원"
                )

                self.mark_message_as_processed(message.id)
            else:
                logger.info("출석 처리 실패")
        except Exception as e:
            logger.error(f"출석 처리 오류: {e}")
            self.clear_processing_message(message.id)


def keep_alive():
    """15분마다 자체 서버에 핑을 보내 슬립모드 방지"""
    while True:
        try:
            # Render에서 제공하는 URL 환경변수 사용
            url = os.getenv('RENDER_EXTERNAL_URL', 'http://localhost:8080')
            response = requests.get(url)
            logger.info(f"서버 핑 전송 완료: {response.status_code}")
        except Exception as e:
            logger.error(f"서버 핑 전송 실패: {e}")
        time.sleep(840)  # 14분(840초)마다 실행 (15분보다 약간 짧게 설정)


bot = AttendanceBot()

# 센트리로 에러 로그 전송
SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN:
    sentry_logging = LoggingIntegration(
        level=logging.INFO,  # INFO 레벨 이상 로그 수집
        event_level=logging.ERROR  # ERROR 레벨 이상은 Sentry 이벤트로 전송
    )
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[sentry_logging],
        traces_sample_rate=1.0  # 성능 트레이싱 필요시
    )
    print("Sentry 초기화 됨")
else:
    print("SENTRY_DSN 환경 변수가 설정되지 않았습니다!")

logger = logging.getLogger(__name__)

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

    logger.info("봇 실행 시작...")
    bot.run(TOKEN)
