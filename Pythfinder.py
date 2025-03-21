import discord
from discord import app_commands
from discord.ext import commands
import psycopg2
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
import asyncio

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


# 데이터베이스 연결 함수
def get_db_connection():
    try:
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        return conn
    except Error as e:
        print(f"데이터베이스 연결 오류: {e}")
        return None


class ConfirmView(View):
    def __init__(self, user_id):
        super().__init__(timeout=60)  # 60초 후 버튼 비활성화
        self.user_id = user_id
        self.value = None

    @discord.ui.button(label="✓ 확인", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("본인만 선택할 수 있습니다!", ephemeral=True)
            return

        self.value = True
        self.stop()

        conn = get_db_connection()
        if not conn:
            await interaction.response.send_message("데이터베이스 연결 오류가 발생했습니다.", ephemeral=True)
            return

        try:
            cur = conn.cursor()

            # 현재 보유 금액 확인
            cur.execute('SELECT money FROM user_money WHERE user_id = %s', (self.user_id,))
            result = cur.fetchone()
            current_money = result[0] if result else 0

            # 출석 정보 초기화하되 보유 금액은 유지
            cur.execute('''
                INSERT INTO attendance (user_id, last_attendance, streak)
                VALUES (%s, NULL, 0)
                ON CONFLICT (user_id) DO UPDATE 
                SET last_attendance = NULL, streak = 0
            ''', (self.user_id, ))

            conn.commit()
            await interaction.response.edit_message(
                content="출석 정보가 초기화되었습니다.\n💰 보유 금액은 유지됩니다.",
                view=None
            )
        except Error as e:
            print(f"데이터베이스 오류: {e}")
            await interaction.response.send_message("오류가 발생했습니다.", ephemeral=True)
        finally:
            conn.close()

    @discord.ui.button(label="✗ 취소", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("본인만 선택할 수 있습니다!", ephemeral=True)
            return

        self.value = False
        self.stop()
        await interaction.response.edit_message(content="출석 초기화가 취소되었습니다.", view=None)


class MoneyResetView(View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.value = None

    @discord.ui.button(label="✓ 확인", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("본인만 선택할 수 있습니다!", ephemeral=True)
            return

        self.value = True
        self.stop()

        conn = get_db_connection()
        if not conn:
            await interaction.response.send_message("데이터베이스 연결 오류가 발생했습니다.", ephemeral=True)
            return

        try:
            cur = conn.cursor()

            # user_money 테이블에서 금액 초기화
            cur.execute('''
                INSERT INTO user_money (user_id, money)
                VALUES (%s, 0)
                ON CONFLICT (user_id) DO UPDATE 
                SET money = 0
            ''', (self.user_id,))

            conn.commit()
            await interaction.response.edit_message(
                content="💰 보유 금액이 0원으로 초기화되었습니다.",
                view=None
            )
        except Error as e:
            print(f"데이터베이스 오류: {e}")
            await interaction.response.send_message("오류가 발생했습니다.", ephemeral=True)
        finally:
            conn.close()

    @discord.ui.button(label="✗ 취소", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("본인만 선택할 수 있습니다!", ephemeral=True)
            return

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
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("본인만 선택할 수 있습니다!", ephemeral=True)
            return

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
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("본인만 선택할 수 있습니다!", ephemeral=True)
            return

        self.value = False
        self.stop()
        await interaction.response.edit_message(content="데이터 초기화가 취소되었습니다.", view=None)


class RankingView(View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id

    @discord.ui.button(label="1️⃣ 출석 랭킹", style=discord.ButtonStyle.primary)
    async def attendance_ranking(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("본인만 선택할 수 있습니다!", ephemeral=True)
            return

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
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("본인만 선택할 수 있습니다!", ephemeral=True)
            return

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
        self.init_database()
        self.attendance_channels = set()
        self.load_attendance_channels()

        # 메시지 처리 관련 집합들을 클래스 변수로 초기화
        self._processing_messages = set()
        self._message_sent = set()
        self._attendance_cache = {}
        self._message_history = {}
        self._message_lock = {}

        print("=== 봇 초기화 완료 ===\n", flush=True)
        sys.stdout.flush()

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

    def update_attendance_cache(self, user_id: int, today: str):
        """출석 캐시를 업데이트합니다."""
        cache_key = f"{user_id}_{today}"
        self.attendance_cache[cache_key] = True

    async def setup_hook(self):
        print("\n=== 이벤트 핸들러 등록 시작 ===", flush=True)
        print("\n=== cog 파일 로드 시작 ===", flush=True)
        # cogs 폴더에 있는 모든 .py 파일을 불러옴
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py"):
                await self.load_extension(f"cogs.{filename[:-3]}")
                print(f"✅ {filename} 로드 완료")
        # 슬래시 명령어 동기화
        try:
            print("슬래시 명령어 동기화 시작...", flush=True)
            synced = await self.tree.sync()
            print(f"동기화된 슬래시 명령어: {len(synced)}개", flush=True)
            # 동기화된 명령어 목록 출력
            for cmd in synced:
                print(f"- {cmd.name}", flush=True)
        except Exception as e:
            print(f"슬래시 명령어 동기화 중 오류 발생: {e}", flush=True)
        print("=== 이벤트 핸들러 등록 완료 ===\n", flush=True)

    async def on_ready(self):
        print("\n" + "=" * 50, flush=True)
        print("봇이 준비되었습니다!", flush=True)
        print(f"봇 이름: {self.user}", flush=True)
        print(f"봇 ID: {self.user.id}", flush=True)
        print(f"서버 수: {len(self.guilds)}", flush=True)
        print(f"캐시된 메시지 수: {len(self.message_sent)}", flush=True)
        print(f"처리 중인 메시지 수: {len(self.processing_messages)}", flush=True)

        # 봇이 준비되면 출석 채널 다시 로드
        self.load_attendance_channels()

        print("=" * 50 + "\n", flush=True)

    def init_database(self):
        if self._db_initialized:
            print("데이터베이스가 이미 초기화되어 있습니다.", flush=True)
            sys.stdout.flush()
            return

        print("\n=== 데이터베이스 초기화 시작 ===", flush=True)
        sys.stdout.flush()
        print("데이터베이스 연결 시도 중...", flush=True)
        sys.stdout.flush()
        conn = get_db_connection()
        if not conn:
            print("데이터베이스 연결 실패", flush=True)
            sys.stdout.flush()
            return

        try:
            cur = conn.cursor()
            print("데이터베이스 연결 성공", flush=True)
            sys.stdout.flush()

            # 테이블 생성
            cur.execute('''
                CREATE TABLE IF NOT EXISTS attendance (
                    user_id BIGINT PRIMARY KEY,
                    last_attendance TIMESTAMP,
                    streak INTEGER DEFAULT 0,
                    money INTEGER DEFAULT 0
                )
            ''')
            print("attendance 테이블 확인/생성 완료", flush=True)
            sys.stdout.flush()

            cur.execute('''
                CREATE TABLE IF NOT EXISTS channels (
                    channel_id BIGINT PRIMARY KEY
                )
            ''')
            print("channels 테이블 확인/생성 완료", flush=True)
            sys.stdout.flush()

            conn.commit()
            self._db_initialized = True
            print("=== 데이터베이스 초기화 완료 ===\n", flush=True)
            sys.stdout.flush()

        except Error as e:
            print(f"데이터베이스 초기화 중 오류 발생: {e}", flush=True)
            sys.stdout.flush()
        finally:
            if conn:
                conn.close()

    def load_attendance_channels(self):
        print("\n=== 출석 채널 로드 시작 ===", flush=True)
        conn = get_db_connection()
        if not conn:
            print("데이터베이스 연결 실패", flush=True)
            return

        try:
            cur = conn.cursor()
            cur.execute('SELECT channel_id FROM channels')
            channels = cur.fetchall()
            self.attendance_channels = set(channel[0] for channel in channels)
            print(f"로드된 출석 채널: {self.attendance_channels}", flush=True)
        except Error as e:
            print(f"채널 로드 오류: {e}", flush=True)
        finally:
            conn.close()
        print("=== 출석 채널 로드 완료 ===\n", flush=True)

    async def on_message(self, message):
        print(f"\n=== 메시지 이벤트 발생 ===", flush=True)
        print(f"메시지 ID: {message.id}", flush=True)
        print(f"작성자: {message.author.name}", flush=True)
        print(f"메시지 내용: {message.content}", flush=True)  # 메시지 내용 추가

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
            print("채널 정보를 가져올 수 없습니다.", flush=True)

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

        try:
            # 메시지를 처리 중으로 표시
            self.mark_message_as_processing(message.id)

            # 사용자 ID와 오늘 날짜로 캐시 키 생성
            user_id = message.author.id
            today = datetime.now(KST).strftime('%Y-%m-%d')
            cache_key = f"{user_id}_{today}"

            # 데이터베이스에서 먼저 출석 여부 확인
            conn = get_db_connection()
            if not conn:
                print("데이터베이스 연결 실패", flush=True)
                return

            cur = conn.cursor()

            cur.execute('''
                SELECT last_attendance 
                FROM attendance 
                WHERE user_id = %s AND last_attendance::date = %s
            ''', (user_id, today))

            if cur.fetchone():
                print(f"이미 오늘 출석한 사용자: {user_id}", flush=True)
                msg = await message.channel.send(f"{message.author.mention}님, 이미 출석하셨습니다.", delete_after=3)
                self.mark_message_as_processed(message.id)
                return

            # 현재 사용자 정보 확인
            cur.execute('SELECT last_attendance, streak FROM attendance WHERE user_id = %s', (user_id,))
            attendance_result = cur.fetchone()
            cur.execute('SELECT money FROM user_money WHERE user_id = %s', (user_id,))
            money_result = cur.fetchone()

            if attendance_result and money_result:
                last_attendance = attendance_result[0]
                current_streak = attendance_result[1]
                current_money = money_result[0]

                # 연속 출석 확인
                yesterday = (datetime.now(KST) - timedelta(days=1)).strftime('%Y-%m-%d')
                if last_attendance and last_attendance.strftime('%Y-%m-%d') == yesterday:
                    streak = current_streak + 1
                else:
                    streak = 1
            else:
                # 새로운 사용자
                current_money = 0
                streak = 1

            # 출석 순서 확인
            cur.execute('''
                SELECT COUNT(*) FROM attendance 
                WHERE last_attendance::date = %s AND user_id != %s
            ''', (today, user_id))
            attendance_order = cur.fetchone()[0] + 1

            # 출석 정보 업데이트
            cur.execute('''
                INSERT INTO attendance (user_id, last_attendance, streak)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE 
                SET last_attendance = %s, 
                    streak = %s
            ''', (user_id, today, streak, today, streak))

            cur.execute('''
                INSERT INTO user_money (user_id, money)
                Values (%s, %s)
                On CONFLICT (user_id) DO UPDATE
                SET money = user_money.money + 10
            ''', (user_id, current_money))

            conn.commit()

            # 출석 메시지 전송
            await message.channel.send(
                f"🎉 {message.author.mention}님 출석하셨습니다!\n"
                f"오늘 {attendance_order}번째 출석이에요.\n"
                f"현재 {streak}일 연속 출석 중입니다!\n"
                f"💰 출석 보상 10원이 지급되었습니다."
            )

        except Exception as e:
            print(f"출석 처리 중 오류 발생: {e}", flush=True)
            self.clear_processing_message(message.id)

    async def process_attendance(self, message):
        """출석 처리를 수행합니다."""
        conn = None
        try:
            user_id = message.author.id
            today = datetime.now(KST).strftime('%Y-%m-%d')
            cache_key = f"{user_id}_{today}"

            # 데이터베이스 연결
            conn = get_db_connection()
            if not conn:
                print("데이터베이스 연결 실패", flush=True)
                return

            cur = conn.cursor()

            # 먼저 오늘 이미 출석했는지 확인
            cur.execute('''
                SELECT last_attendance 
                FROM attendance 
                WHERE user_id = %s AND last_attendance::date = %s
            ''', (user_id, today))

            if cur.fetchone():
                print(f"이미 오늘 출석한 사용자: {user_id}", flush=True)
                return

            # 현재 사용자 정보 확인
            cur.execute('SELECT last_attendance, streak FROM attendance WHERE user_id = %s', (user_id,))
            attendance_result = cur.fetchone()
            cur.execute('SELECT money FROM user_money WHERE user_id = %s', (user_id,))
            money_result = cur.fetchone()

            if result:
                last_attendance = attendance_result[0]
                current_streak = attendance_result[1]
                current_money = money_result[0]

                # 연속 출석 확인
                yesterday = (datetime.now(KST) - timedelta(days=1)).strftime('%Y-%m-%d')
                if last_attendance and last_attendance.strftime('%Y-%m-%d') == yesterday:
                    streak = current_streak + 1
                else:
                    streak = 1
            else:
                # 새로운 사용자
                current_money = 0
                streak = 1

            # 출석 순서 확인
            cur.execute('''
                SELECT COUNT(*) FROM attendance 
                WHERE last_attendance::date = %s AND user_id != %s
            ''', (today, user_id))
            attendance_order = cur.fetchone()[0] + 1

            # 출석 정보 업데이트
            cur.execute('''
                            INSERT INTO attendance (user_id, last_attendance, streak)
                            VALUES (%s, %s, %s)
                            ON CONFLICT (user_id) DO UPDATE 
                            SET last_attendance = %s, 
                                streak = %s
                        ''', (user_id, today, streak, today, streak))

            cur.execute('''
                            INSERT INTO user_money (user_id, money)
                            Values (%s, %s)
                            On CONFLICT (user_id) DO UPDATE
                            SET money = user_money.money + 10
                        ''', (user_id, current_money))

            conn.commit()

            # 출석 메시지 전송
            await message.channel.send(
                f"🎉 {message.author.mention}님 출석하셨습니다!\n"
                f"오늘 {attendance_order}번째 출석이에요.\n"
                f"현재 {streak}일 연속 출석 중입니다!\n"
                f"💰 출석 보상 10원이 지급되었습니다."
            )

        except Exception as e:
            print(f"출석 처리 중 오류 발생: {e}", flush=True)
            await message.channel.send("출석 처리 중 오류가 발생했습니다. 다시 시도해주세요.", delete_after=3)

        finally:
            if conn:
                conn.close()


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
