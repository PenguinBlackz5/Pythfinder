import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
from datetime import datetime, timedelta
import pytz
from discord.ui import Button, View
import os

# 한국 시간대 설정
KST = pytz.timezone('Asia/Seoul')

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
        
        # 데이터베이스에서 사용자의 출석 정보만 초기화
        db_path = '/tmp/attendance.db'
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # 현재 보유 금액 확인
        c.execute('SELECT money FROM attendance WHERE user_id = ?', (self.user_id,))
        result = c.fetchone()
        current_money = result[0] if result else 0
        
        # 출석 정보 초기화하되 보유 금액은 유지
        c.execute('''INSERT OR REPLACE INTO attendance 
                     (user_id, last_attendance, streak, money)
                     VALUES (?, NULL, 0, ?)''', (self.user_id, current_money))
        
        conn.commit()
        conn.close()
        
        await interaction.response.edit_message(
            content="출석 정보가 초기화되었습니다.\n💰 보유 금액은 유지됩니다.", 
            view=None
        )

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
        
        db_path = '/tmp/attendance.db'
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # 현재 출석 정보 확인
        c.execute('SELECT last_attendance, streak FROM attendance WHERE user_id = ?', (self.user_id,))
        result = c.fetchone()
        
        # 기존 출석 정보는 유지하고 돈만 0으로 설정
        if result:
            last_attendance = result[0]
            streak = result[1]
        else:
            last_attendance = None
            streak = 0
            
        # INSERT OR REPLACE로 변경
        c.execute('''INSERT OR REPLACE INTO attendance 
                     (user_id, last_attendance, streak, money)
                     VALUES (?, ?, ?, 0)''', 
                  (self.user_id, last_attendance, streak))
        
        conn.commit()
        conn.close()
        
        await interaction.response.edit_message(
            content="💰 보유 금액이 0원으로 초기화되었습니다.", 
            view=None
        )

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
        
        # 데이터베이스 초기화
        self.init_database()
        
        # 출석 채널 ID 저장 변수
        self.attendance_channels = set()
        self.load_attendance_channels()

    async def setup_hook(self):
        # 슬래시 명령어 동기화
        try:
            synced = await self.tree.sync()
            print(f'동기화된 슬래시 명령어: {len(synced)}개')
        except Exception as e:
            print(f'슬래시 명령어 동기화 중 오류 발생: {e}')
        
    def init_database(self):
        # 데이터베이스 파일 경로를 /tmp 디렉토리로 변경
        db_path = '/tmp/attendance.db'
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # 기존 테이블 삭제
        c.execute('DROP TABLE IF EXISTS attendance')
        
        # 출석 정보를 저장할 테이블 생성 (user_id를 PRIMARY KEY로 설정)
        c.execute('''CREATE TABLE IF NOT EXISTS attendance
                    (user_id INTEGER PRIMARY KEY, 
                     last_attendance TEXT,
                     streak INTEGER DEFAULT 0,
                     money INTEGER DEFAULT 0)''')
                     
        # 출석 채널 정보를 저장할 테이블 생성
        c.execute('''CREATE TABLE IF NOT EXISTS channels
                    (channel_id INTEGER PRIMARY KEY)''')
        
        conn.commit()
        conn.close()
    
    def load_attendance_channels(self):
        # 데이터베이스 파일 경로를 /tmp 디렉토리로 변경
        db_path = '/tmp/attendance.db'
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute('SELECT channel_id FROM channels')
        channels = c.fetchall()
        self.attendance_channels = set(channel[0] for channel in channels)
        conn.close()

bot = AttendanceBot()

@bot.event
async def on_ready():
    print(f'{bot.user}로 로그인했습니다!')
    
    # 봇이 시작될 때 명령어 동기화 상태 확인
    try:
        synced = await bot.tree.sync()
        print(f'명령어 동기화 완료! {len(synced)}개의 명령어가 동기화되었습니다.')
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
    
    db_path = '/tmp/attendance.db'
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    try:
        c.execute('INSERT INTO channels (channel_id) VALUES (?)', (channel_id,))
        conn.commit()
        bot.attendance_channels.add(channel_id)
        await interaction.response.send_message(f"이 채널이 출석 채널로 지정되었습니다!", ephemeral=True)
    except sqlite3.IntegrityError:
        await interaction.response.send_message(f"이미 출석 채널로 지정되어 있습니다!", ephemeral=True)
    finally:
        conn.close()

@bot.tree.command(name="출석정보", description="자신의 출석 현황을 확인합니다.")
async def check_attendance(interaction: discord.Interaction):
    user_id = interaction.user.id
    today = datetime.now(KST).strftime('%Y-%m-%d')  # KST 기준 오늘 날짜
    
    db_path = '/tmp/attendance.db'
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    c.execute('SELECT last_attendance, streak FROM attendance WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    
    if result and result[0] is not None:
        last_attendance = result[0]  # 저장된 마지막 출석일
        streak = result[1]
        
        status = "완료" if last_attendance == today else "미완료"
        
        await interaction.response.send_message(
            f"📊 출석 현황\n"
            f"오늘 출석: {status}\n"
            f"연속 출석: {streak}일",
            ephemeral=True
        )
    else:
        # 출석 기록이 없거나 초기화된 경우
        await interaction.response.send_message(
            f"📊 출석 현황\n"
            f"오늘 출석: 미완료\n"
            f"연속 출석: 0일",
            ephemeral=True
        )
    
    conn.close()

@bot.tree.command(name="통장", description="보유한 금액을 확인합니다.")
async def check_balance(interaction: discord.Interaction):
    user_id = interaction.user.id
    
    db_path = '/tmp/attendance.db'
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    c.execute('SELECT money FROM attendance WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    
    if result:
        money = result[0]
        await interaction.response.send_message(
            f"💰 현재 잔액: {money}원",
            ephemeral=True
        )
    else:
        await interaction.response.send_message("통장 기록이 없습니다!", ephemeral=True)
    
    conn.close()

@bot.event
async def on_message(message):
    if message.author.bot:
        return
        
    if message.channel.id not in bot.attendance_channels:
        return
        
    user_id = message.author.id
    today = datetime.now(KST).strftime('%Y-%m-%d')
    
    db_path = '/tmp/attendance.db'
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    try:
        # 현재 사용자 정보 확인
        c.execute('SELECT last_attendance, streak, money FROM attendance WHERE user_id = ?', (user_id,))
        result = c.fetchone()
        
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
        c.execute('''SELECT COUNT(*) FROM attendance 
                     WHERE last_attendance = ? AND user_id != ?''', 
                  (today, user_id))
        attendance_order = c.fetchone()[0] + 1
        
        # 출석 정보 업데이트 (PRIMARY KEY로 인해 자동으로 REPLACE 작동)
        c.execute('''INSERT OR REPLACE INTO attendance 
                     (user_id, last_attendance, streak, money)
                     VALUES (?, ?, ?, ?)''',
                  (user_id, today, streak, current_money + 10))
        
        conn.commit()
        
        await message.channel.send(
            f"🎉 {message.author.mention}님 출석하셨습니다!\n"
            f"오늘 {attendance_order}번째 출석이에요.\n"
            f"현재 {streak}일 연속 출석 중입니다!\n"
            f"💰 출석 보상 10원이 지급되었습니다."
        )
        
    except Exception as e:
        print(f"출석 처리 중 오류 발생: {e}")
        await message.channel.send("출석 처리 중 오류가 발생했습니다. 다시 시도해주세요.")
        
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

# 봇 실행 부분 수정
if __name__ == "__main__":
    # 환경 변수에서 토큰 가져오기
    TOKEN = os.getenv('DISCORD_TOKEN')
    if not TOKEN:
        raise ValueError("DISCORD_TOKEN 환경 변수가 설정되지 않았습니다!")
    
    bot.run(TOKEN)