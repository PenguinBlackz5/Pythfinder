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
import time    # 새로 추가

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
DEVELOPER_IDS = [667375690710122526]  # 여기에 개발자의 디스코드 ID를 넣으세요

# 권한 체크 함수 추가
def is_admin_or_developer(interaction: discord.Interaction) -> bool:
    return (
        interaction.user.guild_permissions.administrator or 
        interaction.user.id in DEVELOPER_IDS
    )

# 데이터베이스 연결 함수
def get_db_connection():
    try:
        print("데이터베이스 연결 시도 중...")  # 연결 시도 로그
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        print("데이터베이스 연결 성공!")  # 성공 로그
        return conn
    except Error as e:
        print(f"데이터베이스 연결 오류: {e}")  # 상세한 에러 메시지
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
            cur.execute('SELECT money FROM attendance WHERE user_id = %s', (self.user_id,))
            result = cur.fetchone()
            current_money = result[0] if result else 0
            
            # 출석 정보 초기화하되 보유 금액은 유지
            cur.execute('''
                INSERT INTO attendance (user_id, last_attendance, streak, money)
                VALUES (%s, NULL, 0, %s)
                ON CONFLICT (user_id) DO UPDATE 
                SET last_attendance = NULL, streak = 0, money = %s
            ''', (self.user_id, current_money, current_money))
            
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
            
            # 현재 출석 정보 확인
            cur.execute('SELECT last_attendance, streak FROM attendance WHERE user_id = %s', (self.user_id,))
            result = cur.fetchone()
            
            # 기존 출석 정보는 유지하고 돈만 0으로 설정
            if result:
                last_attendance = result[0]
                streak = result[1]
            else:
                last_attendance = None
                streak = 0
            
            # INSERT OR REPLACE로 변경
            cur.execute('''
                INSERT INTO attendance (user_id, last_attendance, streak, money)
                VALUES (%s, %s, %s, 0)
                ON CONFLICT (user_id) DO UPDATE 
                SET last_attendance = %s, streak = %s
            ''', (self.user_id, last_attendance, streak, last_attendance, streak))
            
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
                    name = member.display_name[:10] + "..." if len(member.display_name) > 10 else member.display_name.ljust(10)
                    message += f"{str(rank)+'위':4} {name:<13} {streak:>3}일\n"
            
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
                FROM attendance
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
                    name = member.display_name[:10] + "..." if len(member.display_name) > 10 else member.display_name.ljust(10)
                    message += f"{str(rank)+'위':4} {name:<13} {money:>6}원\n"
            
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
        print("\n=== 봇 초기화 시작 ===")
        # members 인텐트 추가
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True  # 멤버 목록 접근 권한 추가
        super().__init__(command_prefix='!', intents=intents)
        
        print("봇 인스턴스 생성 완료")
        self.init_database()
        self.attendance_channels = set()
        self.load_attendance_channels()
        self.processing_messages = set()  # 처리 중인 메시지 ID를 저장하는 집합 추가
        self.attendance_cache = {}  # 출석 캐시 추가
        self.message_history = {}  # 메시지 히스토리 추가
        self.last_processed_message = None  # 마지막으로 처리한 메시지 ID 추가
        self.message_sent = set()  # 이미 전송한 메시지 ID를 저장하는 집합 추가
        print("=== 봇 초기화 완료 ===\n")

    async def setup_hook(self):
        print("\n=== 이벤트 핸들러 등록 시작 ===")
        # 이벤트 핸들러 등록
        self.add_listener(self.on_ready)
        self.add_listener(self.on_message)
        print("이벤트 핸들러 등록 완료")
        print("=== 이벤트 핸들러 등록 완료 ===\n")

    def init_database(self):
        conn = get_db_connection()
        if not conn:
            print("데이터베이스 초기화 실패")
            return

        try:
            cur = conn.cursor()
            
            # 테이블 존재 여부 확인
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'attendance'
                )
            """)
            table_exists = cur.fetchone()[0]
            print(f"attendance 테이블 존재 여부: {table_exists}")  # 테이블 존재 여부 로그
            
            # 테이블 생성
            cur.execute('''
                CREATE TABLE IF NOT EXISTS attendance (
                    user_id BIGINT PRIMARY KEY,
                    last_attendance DATE,
                    streak INTEGER DEFAULT 0,
                    money INTEGER DEFAULT 0
                )
            ''')
            
            cur.execute('''
                CREATE TABLE IF NOT EXISTS channels (
                    channel_id BIGINT PRIMARY KEY
                )
            ''')
            
            conn.commit()
            print("테이블 생성/확인 완료!")  # 테이블 생성 완료 로그
        except Error as e:
            print(f"테이블 생성 오류: {e}")
        finally:
            conn.close()
    
    def load_attendance_channels(self):
        conn = get_db_connection()
        if not conn:
            return

        try:
            cur = conn.cursor()
            cur.execute('SELECT channel_id FROM channels')
            channels = cur.fetchall()
            self.attendance_channels = set(channel[0] for channel in channels)
        except Error as e:
            print(f"채널 로드 오류: {e}")
        finally:
            conn.close()

bot = AttendanceBot()

@bot.event
async def on_ready():
    print("\n" + "="*50)
    print("봇이 준비되었습니다!")
    print(f"봇 이름: {bot.user}")
    print(f"봇 ID: {bot.user.id}")
    print(f"서버 수: {len(bot.guilds)}")
    print(f"캐시된 메시지 수: {len(bot.message_sent)}")
    print(f"처리 중인 메시지 수: {len(bot.processing_messages)}")
    print("="*50 + "\n")
    
    # 봇이 시작될 때 명령어 동기화 상태 확인
    try:
        print("슬래시 명령어 동기화 시작...")
        synced = await bot.tree.sync()
        print(f'명령어 동기화 완료! {len(synced)}개의 명령어가 동기화되었습니다.')
        # 동기화된 명령어 목록 출력
        for cmd in synced:
            print(f"- {cmd.name}")
    except Exception as e:
        print(f'명령어 동기화 중 오류 발생: {e}')

@bot.tree.command(name="출석채널", description="출석을 인식할 채널을 지정합니다.")
@app_commands.default_permissions(administrator=True)
async def set_attendance_channel(interaction: discord.Interaction):
    # 관리자 또는 개발자 권한 확인
    if not is_admin_or_developer(interaction):
        await interaction.response.send_message("이 명령어는 서버 관리자와 개발자만 사용할 수 있습니다!", ephemeral=True)
        return
        
    channel_id = interaction.channel_id
    
    conn = get_db_connection()
    if not conn:
        await interaction.response.send_message("데이터베이스 연결 실패!", ephemeral=True)
        return

    try:
        c = conn.cursor()
        c.execute('INSERT INTO channels (channel_id) VALUES (%s)', (channel_id,))
        conn.commit()
        bot.attendance_channels.add(channel_id)
        await interaction.response.send_message(f"이 채널이 출석 채널로 지정되었습니다!", ephemeral=True)
    except psycopg2.IntegrityError:
        await interaction.response.send_message(f"이미 출석 채널로 지정되어 있습니다!", ephemeral=True)
    finally:
        conn.close()

@bot.tree.command(name="출석정보", description="자신의 출석 현황을 확인합니다.")
async def check_attendance(interaction: discord.Interaction):
    # 먼저 응답 대기 상태를 알림
    await interaction.response.defer(ephemeral=True)
    
    user_id = interaction.user.id
    today = datetime.now(KST).strftime('%Y-%m-%d')
    
    try:
        conn = get_db_connection()
        if not conn:
            await interaction.followup.send("데이터베이스 연결 실패!", ephemeral=True)
            return
        
        c = conn.cursor()
        
        c.execute('SELECT last_attendance, streak FROM attendance WHERE user_id = %s', (user_id,))
        result = c.fetchone()
        
        if result and result[0] is not None:
            last_attendance = result[0]
            streak = result[1]
            
            status = "완료" if last_attendance.strftime('%Y-%m-%d') == today else "미완료"
            
            await interaction.followup.send(
                f"📊 출석 현황\n"
                f"오늘 출석: {status}\n"
                f"연속 출석: {streak}일",
                ephemeral=True
            )
        else:
            # 출석 기록이 없거나 초기화된 경우
            await interaction.followup.send(
                f"📊 출석 현황\n"
                f"오늘 출석: 미완료\n"
                f"연속 출석: 0일",
                ephemeral=True
            )
    
    except Exception as e:
        print(f"출석정보 확인 중 오류 발생: {e}")
        await interaction.followup.send("오류가 발생했습니다. 다시 시도해주세요.", ephemeral=True)
    
    finally:
        if conn:
            conn.close()

@bot.tree.command(name="통장", description="보유한 금액을 확인합니다.")
async def check_balance(interaction: discord.Interaction):
    user_id = interaction.user.id
    
    conn = get_db_connection()
    if not conn:
        return

    try:
        cur = conn.cursor()
        
        cur.execute('SELECT money FROM attendance WHERE user_id = %s', (user_id,))
        result = cur.fetchone()
        
        if result:
            money = result[0]
            await interaction.response.send_message(
                f"💰 현재 잔액: {money}원",
                ephemeral=True
            )
        else:
            await interaction.response.send_message("통장 기록이 없습니다!", ephemeral=True)
        
    except Error as e:
        print(f"잔액 확인 중 오류 발생: {e}")
        await interaction.response.send_message("잔액 확인 중 오류가 발생했습니다. 다시 시도해주세요.", ephemeral=True)
    finally:
        conn.close()

@bot.event
async def on_message(message):
    print("\n" + "="*50)
    print("메시지 이벤트 발생!")
    print(f"메시지 ID: {message.id}")
    print(f"작성자: {message.author.name}")
    print(f"채널: {message.channel.name}")
    print("="*50 + "\n")
    
    # 봇 메시지 무시
    if message.author.bot:
        print("봇 메시지 무시")
        return
        
    # 출석 채널이 아니면 무시
    if message.channel.id not in bot.attendance_channels:
        print("출석 채널이 아님. 무시")
        return
        
    print(f"\n=== 메시지 처리 시작 ===")
    print(f"메시지 ID: {message.id}")
    print(f"작성자: {message.author.name}")
    print(f"채널: {message.channel.name}")
    print(f"처리 중인 메시지 수: {len(bot.processing_messages)}")
    print(f"전송된 메시지 수: {len(bot.message_sent)}")
    
    # 이미 처리 중인 메시지인 경우 무시
    if message.id in bot.processing_messages:
        print("이미 처리 중인 메시지입니다. 무시합니다.")
        return
        
    # 이미 메시지를 전송한 경우 무시
    if message.id in bot.message_sent:
        print("이미 전송된 메시지입니다. 무시합니다.")
        return
        
    # 메시지 ID를 처리 중인 메시지 집합에 추가
    bot.processing_messages.add(message.id)
    print("메시지 처리 시작")
    
    user_id = message.author.id
    today = datetime.now(KST).strftime('%Y-%m-%d')
    
    # 메시지 히스토리 확인
    cache_key = f"{user_id}_{today}"
    if cache_key in bot.message_history:
        last_message_time = bot.message_history[cache_key]
        current_time = datetime.now(KST)
        time_diff = (current_time - last_message_time).total_seconds()
        
        print(f"마지막 메시지로부터 {time_diff}초 경과")
        
        # 5초 이내에 같은 사용자의 메시지가 있다면 무시
        if time_diff < 5:
            print("5초 이내의 중복 메시지입니다. 무시합니다.")
            bot.processing_messages.remove(message.id)
            return
    
    # 캐시에서 오늘 출석 여부 확인
    if cache_key in bot.attendance_cache:
        print("캐시에서 출석 정보 확인됨")
        tomorrow = datetime.now(KST) + timedelta(days=1)
        tomorrow = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
        current_time = datetime.now(KST)
        time_until_next = tomorrow - current_time
        
        hours = int(time_until_next.total_seconds() // 3600)
        minutes = int((time_until_next.total_seconds() % 3600) // 60)
        
        # 메시지 전송 전에 ID를 저장
        bot.message_sent.add(message.id)
        print("중복 출석 메시지 전송")
        
        await message.channel.send(
            f"{message.author.mention} 이미 오늘은 출석하셨습니다!\n"
            f"다음 출석까지 {hours}시간 {minutes}분 남았습니다.",
            delete_after=3
        )
        bot.processing_messages.remove(message.id)
        print("=== 메시지 처리 완료 ===\n")
        return
    
    conn = get_db_connection()
    if not conn:
        print("데이터베이스 연결 실패")
        bot.processing_messages.remove(message.id)
        return

    try:
        cur = conn.cursor()
        
        # 현재 사용자 정보 확인
        cur.execute('SELECT last_attendance, streak, money FROM attendance WHERE user_id = %s', (user_id,))
        result = cur.fetchone()
        
        if result:
            last_attendance = result[0]
            current_streak = result[1]
            current_money = result[2]
            
            # 이미 오늘 출석했는지 확인
            if last_attendance and last_attendance.strftime('%Y-%m-%d') == today:
                print("데이터베이스에서 중복 출석 확인됨")
                # 캐시에 출석 정보 저장
                bot.attendance_cache[cache_key] = True
                bot.message_history[cache_key] = datetime.now(KST)
                
                tomorrow = datetime.now(KST) + timedelta(days=1)
                tomorrow = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
                current_time = datetime.now(KST)
                time_until_next = tomorrow - current_time
                
                hours = int(time_until_next.total_seconds() // 3600)
                minutes = int((time_until_next.total_seconds() % 3600) // 60)
                
                # 메시지 전송 전에 ID를 저장
                bot.message_sent.add(message.id)
                print("중복 출석 메시지 전송")
                
                await message.channel.send(
                    f"{message.author.mention} 이미 오늘은 출석하셨습니다!\n"
                    f"다음 출석까지 {hours}시간 {minutes}분 남았습니다.",
                    delete_after=3
                )
                return
                
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
            WHERE DATE(last_attendance) = %s AND user_id != %s
        ''', (today, user_id))
        attendance_order = cur.fetchone()[0] + 1
        
        # 출석 정보 업데이트
        cur.execute('''
            INSERT INTO attendance (user_id, last_attendance, streak, money)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE 
            SET last_attendance = %s, 
                streak = %s, 
                money = attendance.money + 10
        ''', (user_id, today, streak, current_money + 10, today, streak))
        
        conn.commit()
        
        # 캐시에 출석 정보 저장
        bot.attendance_cache[cache_key] = True
        bot.message_history[cache_key] = datetime.now(KST)
        
        # 메시지 전송 전에 ID를 저장
        bot.message_sent.add(message.id)
        print("출석 성공 메시지 전송")
        
        # 출석 메시지 전송 (한 번만)
        sent_message = await message.channel.send(
            f"🎉 {message.author.mention}님 출석하셨습니다!\n"
            f"오늘 {attendance_order}번째 출석이에요.\n"
            f"현재 {streak}일 연속 출석 중입니다!\n"
            f"💰 출석 보상 10원이 지급되었습니다."
        )
        
    except Exception as e:
        print(f"출석 처리 중 오류 발생: {e}")
        await message.channel.send("출석 처리 중 오류가 발생했습니다. 다시 시도해주세요.")
        
    finally:
        if conn:
            conn.close()
        # 처리 중인 메시지 집합에서 제거
        bot.processing_messages.remove(message.id)
        print("=== 메시지 처리 완료 ===\n")

    # 기존 명령어 처리를 위한 이벤트 추가
    await bot.process_commands(message)

@bot.tree.command(name="출석초기화", description="연속 출석 일수를 초기화합니다. (보유 금액은 유지)")
async def reset_attendance(interaction: discord.Interaction):
    view = ConfirmView(interaction.user.id)
    await interaction.response.send_message(
        "⚠️ 정말로 출석 정보를 초기화하시겠습니까?\n"
        "연속 출석 일수가 초기화됩니다.\n"
        "💰 보유 금액은 유지됩니다.",
        view=view,
        ephemeral=True
    )

@bot.tree.command(name="통장초기화", description="보유한 금액을 0원으로 초기화합니다.")
async def reset_money(interaction: discord.Interaction):
    view = MoneyResetView(interaction.user.id)
    await interaction.response.send_message(
        "⚠️ 정말로 통장을 초기화하시겠습니까?\n"
        "보유한 금액이 0원으로 초기화됩니다.\n"
        "❗ 이 작업은 되돌릴 수 없습니다!",
        view=view,
        ephemeral=True
    )

@bot.tree.command(
    name="디비테스트",
    description="데이터베이스 연결을 테스트합니다."
)
@app_commands.default_permissions(administrator=True)
async def test_db(interaction: discord.Interaction):
    if not is_admin_or_developer(interaction):
        await interaction.response.send_message("이 명령어는 서버 관리자와 개발자만 사용할 수 있습니다!", ephemeral=True)
        return
    
    print(f"디비테스트 명령어 실행 - 요청자: {interaction.user.name}")
    
    conn = get_db_connection()
    if not conn:
        await interaction.response.send_message("❌ 데이터베이스 연결 실패!", ephemeral=True)
        return

    try:
        cur = conn.cursor()
        
        # 테이블 존재 여부 확인
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'attendance'
            )
        """)
        attendance_exists = cur.fetchone()[0]
        
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'channels'
            )
        """)
        channels_exists = cur.fetchone()[0]
        
        # 각 테이블의 레코드 수 확인
        cur.execute("SELECT COUNT(*) FROM attendance")
        attendance_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM channels")
        channels_count = cur.fetchone()[0]
        
        status_message = (
            "✅ 데이터베이스 연결 테스트 결과\n\n"
            f"attendance 테이블: {'존재함' if attendance_exists else '없음'}\n"
            f"channels 테이블: {'존재함' if channels_exists else '없음'}\n"
            f"attendance 레코드 수: {attendance_count}\n"
            f"channels 레코드 수: {channels_count}"
        )
        
        await interaction.response.send_message(status_message, ephemeral=True)
        
    except Exception as e:
        print(f"디비테스트 실행 중 오류: {e}")  # 디버깅 로그 추가
        await interaction.response.send_message(
            f"❌ 데이터베이스 쿼리 실행 중 오류 발생:\n{str(e)}", 
            ephemeral=True
        )
    finally:
        conn.close()

@bot.tree.command(name="클리어올캐시", description="⚠️ 이 서버의 모든 출석 데이터를 초기화합니다. (개발자 전용)")
async def clear_all_cache(interaction: discord.Interaction):
    # 개발자 권한 확인
    if interaction.user.id not in DEVELOPER_IDS:
        await interaction.response.send_message("⚠️ 이 명령어는 개발자만 사용할 수 있습니다!", ephemeral=True)
        return

    # DM에서 실행 방지
    if not interaction.guild:
        await interaction.response.send_message("이 명령어는 서버에서만 사용할 수 있습니다!", ephemeral=True)
        return

    guild = interaction.guild
    
    try:
        # 서버 멤버 목록 다시 가져오기
        await guild.chunk()  # 모든 멤버 정보 다시 로드
        
        # 실제 멤버 수 계산 (봇 제외)
        member_count = sum(1 for member in guild.members if not member.bot)
        print(f"서버 '{guild.name}'의 멤버 수: {member_count}")  # 디버깅용
        
        if member_count == 0:
            await interaction.response.send_message(
                "❌ 멤버 목록을 가져올 수 없습니다. 봇의 권한을 확인해주세요.", 
                ephemeral=True
            )
            return
            
        view = ClearAllView(interaction.user.id, guild.id)
        await interaction.response.send_message(
            f"⚠️ **정말로 이 서버의 출석 데이터를 초기화하시겠습니까?**\n\n"
            f"**서버: {guild.name}**\n"
            f"**영향 받는 멤버: {member_count}명**\n\n"
            "다음 데이터가 초기화됩니다:\n"
            "- 서버 멤버들의 출석 정보\n"
            "- 서버 멤버들의 연속 출석 일수\n"
            "- 서버 멤버들의 보유 금액\n\n"
            "❗ **이 작업은 되돌릴 수 없습니다!**\n"
            "❗ **출석 채널 설정은 유지됩니다.**\n"
            "❗ **다른 서버의 데이터는 영향받지 않습니다.**",
            view=view,
            ephemeral=True
        )
    except Exception as e:
        print(f"멤버 목록 가져오기 실패: {e}")
        await interaction.response.send_message(
            "멤버 목록을 가져오는 중 오류가 발생했습니다.",
            ephemeral=True
        )

@bot.tree.command(name="디비구조", description="데이터베이스의 테이블 구조와 현황을 확인합니다. (개발자 전용)")
async def check_db_structure(interaction: discord.Interaction):
    # 개발자 권한 확인
    if interaction.user.id not in DEVELOPER_IDS:
        await interaction.response.send_message("⚠️ 이 명령어는 개발자만 사용할 수 있습니다!", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    
    conn = get_db_connection()
    if not conn:
        await interaction.followup.send("데이터베이스 연결 실패!", ephemeral=True)
        return

    try:
        cur = conn.cursor()
        
        # attendance 테이블 정보 조회
        cur.execute("""
            SELECT 
                column_name, 
                data_type, 
                column_default,
                is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'attendance'
            ORDER BY ordinal_position;
        """)
        attendance_columns = cur.fetchall()
        
        # channels 테이블 정보 조회
        cur.execute("""
            SELECT 
                column_name, 
                data_type, 
                column_default,
                is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'channels'
            ORDER BY ordinal_position;
        """)
        channels_columns = cur.fetchall()
        
        # 각 테이블의 레코드 수 조회
        cur.execute("SELECT COUNT(*) FROM attendance")
        attendance_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM channels")
        channels_count = cur.fetchone()[0]
        
        # 서버별 통계 (현재 서버 강조)
        current_guild = interaction.guild
        if current_guild:
            member_ids = [member.id for member in current_guild.members]
            cur.execute("""
                SELECT COUNT(*) FROM attendance 
                WHERE user_id = ANY(%s)
            """, (member_ids,))
            current_guild_count = cur.fetchone()[0]
        else:
            current_guild_count = 0

        # 메시지 구성
        message = "📊 **데이터베이스 구조 및 현황**\n\n"
        
        # attendance 테이블 정보
        message += "**📝 attendance 테이블**\n"
        message += "```\n"
        message += "컬럼명         타입      기본값    Null허용\n"
        message += "----------------------------------------\n"
        for col in attendance_columns:
            message += f"{col[0]:<12} {col[1]:<8} {str(col[2]):<8} {col[3]:<6}\n"
        message += "```\n"
        message += f"총 레코드 수: {attendance_count}개\n"
        if current_guild:
            message += f"현재 서버 레코드 수: {current_guild_count}개\n"
        message += "\n"
        
        # channels 테이블 정보
        message += "**🔧 channels 테이블**\n"
        message += "```\n"
        message += "컬럼명         타입      기본값    Null허용\n"
        message += "----------------------------------------\n"
        for col in channels_columns:
            message += f"{col[0]:<12} {col[1]:<8} {str(col[2]):<8} {col[3]:<6}\n"
        message += "```\n"
        message += f"총 레코드 수: {channels_count}개\n\n"
        
        # 출석 채널 목록
        if channels_count > 0:
            cur.execute("SELECT channel_id FROM channels")
            channel_ids = cur.fetchall()
            message += "**📍 등록된 출석 채널**\n"
            for (channel_id,) in channel_ids:
                channel = bot.get_channel(channel_id)
                if channel:
                    message += f"- {channel.guild.name} / #{channel.name}\n"
                else:
                    message += f"- 알 수 없는 채널 (ID: {channel_id})\n"
        
        await interaction.followup.send(message, ephemeral=True)
        
    except Exception as e:
        print(f"데이터베이스 구조 조회 중 오류 발생: {e}")
        await interaction.followup.send(
            f"❌ 데이터베이스 조회 중 오류가 발생했습니다.\n```{str(e)}```", 
            ephemeral=True
        )
    finally:
        conn.close()

@bot.tree.command(name="출석현황", description="서버 멤버들의 출석 현황을 확인합니다. (개발자 전용)")
async def check_server_attendance(interaction: discord.Interaction):
    # 개발자 권한 확인
    if interaction.user.id not in DEVELOPER_IDS:
        await interaction.response.send_message("⚠️ 이 명령어는 개발자만 사용할 수 있습니다!", ephemeral=True)
        return

    # DM에서 실행 방지
    if not interaction.guild:
        await interaction.response.send_message("이 명령어는 서버에서만 사용할 수 있습니다!", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    
    try:
        guild = interaction.guild
        await guild.chunk()  # 멤버 목록 다시 로드
        
        conn = get_db_connection()
        if not conn:
            await interaction.followup.send("데이터베이스 연결 실패!", ephemeral=True)
            return

        cur = conn.cursor()
        
        # 현재 날짜 (KST)
        today = datetime.now(KST).strftime('%Y-%m-%d')
        
        # 서버 멤버들의 출석 정보 조회
        member_ids = [member.id for member in guild.members if not member.bot]
        member_id_str = ','.join(str(id) for id in member_ids)
        
        if not member_ids:
            await interaction.followup.send("서버에 멤버가 없습니다.", ephemeral=True)
            return
            
        cur.execute(f'''
            SELECT 
                user_id,
                last_attendance,
                streak,
                money
            FROM attendance 
            WHERE user_id IN ({member_id_str})
            ORDER BY streak DESC, money DESC
        ''')
        
        results = cur.fetchall()
        
        # 통계 계산
        registered_members = len(results)
        today_attendance = sum(1 for r in results if r[1] and r[1].strftime('%Y-%m-%d') == today)
        total_money = sum(r[3] for r in results if r[3])
        
        # 메시지 구성
        message = f"📊 **{guild.name} 서버 출석 현황**\n\n"
        
        # 통계 정보
        message += "**📈 통계**\n"
        message += f"등록 멤버: {registered_members}명\n"
        message += f"오늘 출석: {today_attendance}명\n"
        message += f"전체 보유 금액: {total_money}원\n\n"
        
        # 멤버별 상세 정보
        message += "**👥 멤버별 현황**\n"
        message += "```\n"
        message += "닉네임         연속출석  마지막출석    보유금액\n"
        message += "------------------------------------------------\n"
        
        for user_id, last_attendance, streak, money in results:
            member = guild.get_member(user_id)
            if member:
                name = member.display_name[:10] + "..." if len(member.display_name) > 10 else member.display_name.ljust(10)
                last_date = last_attendance.strftime('%Y-%m-%d') if last_attendance else "없음"
                streak = streak or 0
                money = money or 0
                
                message += f"{name:<13} {streak:<8} {last_date:<12} {money:>6}원\n"
        
        message += "```\n"
        
        # 메시지가 너무 길 경우 분할 전송
        if len(message) > 2000:
            parts = [message[i:i+1990] for i in range(0, len(message), 1990)]
            for i, part in enumerate(parts):
                if i == 0:
                    await interaction.followup.send(part, ephemeral=True)
                else:
                    await interaction.followup.send(part, ephemeral=True)
        else:
            await interaction.followup.send(message, ephemeral=True)
            
    except Exception as e:
        print(f"출석 현황 조회 중 오류 발생: {e}")
        await interaction.followup.send(
            f"❌ 출석 현황 조회 중 오류가 발생했습니다.\n```{str(e)}```", 
            ephemeral=True
        )
    finally:
        if conn:
            conn.close()

@bot.tree.command(name="랭킹", description="서버의 출석/보유금액 랭킹을 확인합니다.")
async def check_ranking(interaction: discord.Interaction):
    view = RankingView(interaction.user.id)
    await interaction.response.send_message(
        "📊 **확인하고 싶은 랭킹을 선택해주세요!**\n\n"
        "1️⃣ 출석 랭킹: 연속 출석 일수 기준 TOP 10\n"
        "2️⃣ 보유 금액 랭킹: 보유 금액 기준 TOP 10",
        view=view,
        ephemeral=True
    )

def keep_alive():
    """15분마다 자체 서버에 핑을 보내 슬립모드 방지"""
    while True:
        try:
            # Render에서 제공하는 URL 환경변수 사용
            url = os.getenv('RENDER_EXTERNAL_URL', 'http://localhost:8080')
            response = requests.get(url)
            print(f"서버 핑 전송 완료: {response.status_code}")
        except Exception as e:
            print(f"서버 핑 전송 실패: {e}")
        time.sleep(840)  # 14분(840초)마다 실행 (15분보다 약간 짧게 설정)

# 봇 실행 부분 수정
if __name__ == "__main__":
    # Flask 서버를 별도 스레드에서 실행
    server_thread = threading.Thread(target=run_flask)
    server_thread.start()
    
    # 핑 전송을 위한 새로운 스레드 시작
    ping_thread = threading.Thread(target=keep_alive, daemon=True)
    ping_thread.start()

    # 봇 토큰 설정 및 실행
    TOKEN = os.getenv('DISCORD_TOKEN')
    if not TOKEN:
        raise ValueError("DISCORD_TOKEN 환경 변수가 설정되지 않았습니다!")
    
    bot.run(TOKEN)
