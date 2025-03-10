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

class AttendanceBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)
        
        print("봇 초기화 시작...")
        self.init_database()
        self.attendance_channels = set()
        self.load_attendance_channels()

    async def setup_hook(self):
        # 슬래시 명령어 동기화
        try:
            print("슬래시 명령어 동기화 시작...")
            synced = await self.tree.sync()
            print(f"동기화된 슬래시 명령어: {len(synced)}개")
            # 동기화된 명령어 목록 출력
            for cmd in synced:
                print(f"- {cmd.name}")
        except Exception as e:
            print(f"슬래시 명령어 동기화 중 오류 발생: {e}")

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
    print(f'{bot.user}로 로그인했습니다!')
    
    # 봇이 시작될 때 명령어 동기화 상태 확인
    try:
        print("봇 시작 시 명령어 동기화 시도...")
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
    # 관리자 권한 확인
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("이 명령어는 서버 관리자만 사용할 수 있습니다!", ephemeral=True)
        return
        
    channel_id = interaction.channel_id
    
    conn = get_db_connection()
    if not conn:
        return

    try:
        cur = conn.cursor()
        cur.execute('INSERT INTO channels (channel_id) VALUES (%s)', (channel_id,))
        conn.commit()
        bot.attendance_channels.add(channel_id)
        await interaction.response.send_message(f"이 채널이 출석 채널로 지정되었습니다!", ephemeral=True)
    except Error as e:
        print(f"데이터베이스 오류: {e}")
        await interaction.response.send_message("오류가 발생했습니다.", ephemeral=True)
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
    if message.author.bot or message.channel.id not in bot.attendance_channels:
        return
        
    user_id = message.author.id
    today = datetime.now(KST).strftime('%Y-%m-%d')
    
    conn = get_db_connection()
    if not conn:
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
            if last_attendance == today:
                tomorrow = datetime.now(KST) + timedelta(days=1)
                tomorrow = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
                current_time = datetime.now(KST)
                time_until_next = tomorrow - current_time
                
                hours = int(time_until_next.total_seconds() // 3600)
                minutes = int((time_until_next.total_seconds() % 3600) // 60)
                
                await message.channel.send(
                    f"{message.author.mention} 이미 오늘은 출석하셨습니다!\n"
                    f"다음 출석까지 {hours}시간 {minutes}분 남았습니다.",
                    delete_after=10
                )
                return
                
            # 연속 출석 확인
            yesterday = (datetime.now(KST) - timedelta(days=1)).strftime('%Y-%m-%d')
            if last_attendance == yesterday:
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
            SET last_attendance = %s, streak = %s, money = attendance.money + 10
        ''', (user_id, today, streak, current_money + 10, today, streak))
        
        conn.commit()
        
        await message.channel.send(
            f"🎉 {message.author.mention}님 출석하셨습니다!\n"
            f"오늘 {attendance_order}번째 출석이에요.\n"
            f"현재 {streak}일 연속 출석 중입니다!\n"
            f"💰 출석 보상 10원이 지급되었습니다."
        )
        
    except Error as e:
        print(f"출석 처리 중 오류 발생: {e}")
        await message.channel.send("출석 처리 중 오류가 발생했습니다. 다시 시도해주세요.", ephemeral=True)
    finally:
        conn.close()

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
async def test_db(interaction: discord.Interaction):
    # 관리자 권한 체크 수정
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("이 명령어는 관리자만 사용할 수 있습니다!", ephemeral=True)
        return

    print(f"디비테스트 명령어 실행 - 요청자: {interaction.user.name}")  # 디버깅 로그 추가
    
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

# 봇 실행 부분 수정
if __name__ == "__main__":
    # Flask 서버를 별도 스레드에서 실행
    server_thread = threading.Thread(target=run_flask)
    server_thread.start()

    # 봇 토큰 설정 및 실행
    TOKEN = os.getenv('DISCORD_TOKEN')
    if not TOKEN:
        raise ValueError("DISCORD_TOKEN 환경 변수가 설정되지 않았습니다!")
    
    bot.run(TOKEN)
