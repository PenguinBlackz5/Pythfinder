import discord
from discord.ext import commands
import random
import asyncio
from typing import Dict, Tuple
from Pythfinder import get_db_connection

class Baseball(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_games: Dict[int, Tuple[str, int, int, int]] = {}  # user_id: (target_number, bet_amount, attempts_left, multiplier)
        
    def generate_number(self) -> str:
        """중복되지 않는 3자리 숫자를 생성합니다."""
        numbers = list(range(10))
        random.shuffle(numbers)
        return ''.join(map(str, numbers[:3]))
    
    def check_number(self, target: str, guess: str) -> Tuple[int, int]:
        """숫자야구 결과를 계산합니다."""
        strikes = sum(1 for i in range(3) if target[i] == guess[i])
        balls = sum(1 for i in range(3) if guess[i] in target) - strikes
        return strikes, balls
    
    @commands.slash_command(name="숫자야구", description="숫자야구 게임을 시작합니다.")
    async def baseball(self, ctx: discord.ApplicationContext, bet_amount: int):
        if bet_amount < 1:
            await ctx.respond("베팅 금액은 최소 1원 이상이어야 합니다.", ephemeral=True)
            return
            
        # 베팅금 차감
        conn = get_db_connection()
        if not conn:
            await ctx.respond("데이터베이스 연결 오류가 발생했습니다.", ephemeral=True)
            return
            
        try:
            cur = conn.cursor()
            
            # 현재 보유 금액 확인
            cur.execute('SELECT money FROM attendance WHERE user_id = %s', (ctx.author.id,))
            result = cur.fetchone()
            current_money = result[0] if result else 0
            
            if current_money < bet_amount:
                await ctx.respond("보유 금액이 부족합니다!", ephemeral=True)
                return
                
            # 베팅금 차감
            cur.execute('''
                UPDATE attendance 
                SET money = money - %s 
                WHERE user_id = %s
            ''', (bet_amount, ctx.author.id))
            
            conn.commit()
            
        except Exception as e:
            print(f"베팅금 차감 중 오류 발생: {e}")
            await ctx.respond("베팅금 차감 중 오류가 발생했습니다.", ephemeral=True)
            return
        finally:
            conn.close()
            
        # DM으로 게임 진행
        try:
            dm_channel = await ctx.author.create_dm()
        except discord.Forbidden:
            await ctx.respond("DM을 보낼 수 없습니다. DM 설정을 확인해주세요.", ephemeral=True)
            return
            
        await ctx.respond("게임이 시작되었습니다! DM을 확인해주세요.", ephemeral=True)
        
        target_number = self.generate_number()
        attempts_left = 5
        multiplier = 10
        
        self.active_games[ctx.author.id] = (target_number, bet_amount, attempts_left, multiplier)
        
        await dm_channel.send(f"숫자야구 게임이 시작되었습니다!\n"
                            f"0~9 사이의 중복되지 않는 3자리 숫자를 맞춰보세요.\n"
                            f"기회는 총 {attempts_left}번 있습니다.\n"
                            f"맞추면 베팅금의 {multiplier}배를 받을 수 있습니다!\n"
                            f"숫자를 입력해주세요 (예: 123)")
        
        def check(m):
            return m.author == ctx.author and m.channel == dm_channel and m.content.isdigit() and len(m.content) == 3
        
        while attempts_left > 0:
            try:
                guess = await self.bot.wait_for('message', timeout=300.0, check=check)
                guess_number = guess.content
                
                if len(set(guess_number)) != 3:
                    await dm_channel.send("중복되지 않는 3자리 숫자를 입력해주세요!")
                    continue
                
                strikes, balls = self.check_number(target_number, guess_number)
                
                if strikes == 3:
                    winnings = bet_amount * multiplier
                    # 승리 금액 지급
                    conn = get_db_connection()
                    if conn:
                        try:
                            cur = conn.cursor()
                            cur.execute('''
                                UPDATE attendance 
                                SET money = money + %s 
                                WHERE user_id = %s
                            ''', (winnings, ctx.author.id))
                            conn.commit()
                        except Exception as e:
                            print(f"승리 금액 지급 중 오류 발생: {e}")
                        finally:
                            conn.close()
                            
                    await dm_channel.send(f"정답입니다! {target_number}\n"
                                        f"축하합니다! {winnings}원을 획득했습니다!")
                    del self.active_games[ctx.author.id]
                    return
                
                await dm_channel.send(f"결과: {strikes}스트라이크 {balls}볼\n"
                                    f"남은 기회: {attempts_left - 1}번")
                
                attempts_left -= 1
                multiplier -= 2
                self.active_games[ctx.author.id] = (target_number, bet_amount, attempts_left, multiplier)
                
            except asyncio.TimeoutError:
                await dm_channel.send("시간이 초과되었습니다. 게임이 종료됩니다.")
                del self.active_games[ctx.author.id]
                return
        
        await dm_channel.send(f"게임이 종료되었습니다. 정답은 {target_number}였습니다.")
        del self.active_games[ctx.author.id]

def setup(bot):
    bot.add_cog(Baseball(bot)) 