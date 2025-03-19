import discord
from discord.ext import commands
import random
import asyncio
from typing import Dict, Tuple
from Pythfinder import get_db_connection


def generate_number() -> str:
    """중복되지 않는 3자리 숫자를 생성합니다."""
    numbers = list(range(10))
    random.shuffle(numbers)
    return ''.join(map(str, numbers[:3]))


def check_number(target: str, guess: str) -> Tuple[int, int]:
    """숫자야구 결과를 계산합니다."""
    strikes = sum(1 for i in range(3) if target[i] == guess[i])
    balls = sum(1 for i in range(3) if guess[i] in target) - strikes
    return strikes, balls

class Baseball(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_games: Dict[int, Tuple[str, int, int, int]] = {}  # user_id: (target_number, bet_amount, attempts_left, multiplier)

        @bot.tree.command(name="숫자야구", description="숫자야구 게임을 시작합니다.")
        async def baseball(interaction: discord.Interaction, bet_amount: int):
            if bet_amount < 1:
                await interaction.response.send_message("베팅 금액은 최소 1원 이상이어야 합니다.", ephemeral=True)
                return

            # 베팅금 차감
            conn = get_db_connection()
            if not conn:
                await interaction.response.send_message("데이터베이스 연결 오류가 발생했습니다.", ephemeral=True)
                return

            try:
                cur = conn.cursor()
                user_id = interaction.user.id

                # 현재 보유 금액 확인
                cur.execute('SELECT money FROM attendance WHERE user_id = %s', (user_id,))
                result = cur.fetchone()
                if result:
                    current_money = result[0]

                if current_money < bet_amount:
                    await interaction.response.send_message("보유 금액이 부족합니다!", ephemeral=True)
                    return
                print(type(user_id))
                print(type(bet_amount))
                # 베팅금 차감
                cur.execute('''
                    UPDATE attendance 
                    SET money = %s 
                    WHERE user_id = %s
                ''', (current_money - bet_amount, user_id))

                conn.commit()

            except Exception as e:
                print(f"베팅금 차감 중 오류 발생: {e}")
                await interaction.response.send_message("베팅금 차감 중 오류가 발생했습니다.", ephemeral=True)
                return
            finally:
                conn.close()

            # DM으로 게임 진행
            try:
                await interaction.user.send("게임이 시작되었습니다! DM을 확인해주세요.")
                await interaction.response.send_message("게임이 시작되었습니다! DM을 확인해주세요.", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message("DM을 보낼 수 없습니다. DM 설정을 확인해주세요.", ephemeral=True)
                return

            target_number = generate_number()
            attempts_left = 5
            multiplier = 10

            self.active_games[interaction.user.id] = (target_number, bet_amount, attempts_left, multiplier)

            try:
                await interaction.user.send(
                    f"숫자야구 게임이 시작되었습니다!\n"
                    f"0~9 사이의 중복되지 않는 3자리 숫자를 맞춰보세요.\n"
                    f"기회는 총 {attempts_left}번 있습니다.\n"
                    f"맞추면 베팅금의 {multiplier}배를 받을 수 있습니다!\n"
                    f"숫자를 입력해주세요 (예: 123)"
                )
            except discord.Forbidden:
                await interaction.response.send_message("DM을 보낼 수 없습니다. DM 설정을 확인해주세요.", ephemeral=True)
                return

            def check(m):
                return (
                        m.author == interaction.user
                        and isinstance(m.channel, discord.DMChannel)  # DM 채널에서만 입력받기
                        and m.content.isdigit()
                        and len(m.content) == 3
                )

            while attempts_left > 0:
                try:
                    guess = await self.bot.wait_for('message', timeout=300.0, check=check)
                    guess_number = guess.content

                    if len(set(guess_number)) != 3:
                        await interaction.user.send("중복되지 않는 3자리 숫자를 입력해주세요!")
                        continue

                    strikes, balls = check_number(target_number, guess_number)

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
                                ''', (winnings, interaction.user.id))
                                conn.commit()
                            except Exception as e:
                                print(f"승리 금액 지급 중 오류 발생: {e}")
                            finally:
                                conn.close()

                        await interaction.user.send(f"정답입니다! {target_number}\n"
                                            f"축하합니다! {winnings}원을 획득했습니다!")
                        del self.active_games[interaction.user.id]
                        return

                    await interaction.user.send(f"결과: {strikes}스트라이크 {balls}볼\n"
                                        f"남은 기회: {attempts_left - 1}번")

                    attempts_left -= 1
                    multiplier -= 2
                    self.active_games[interaction.user.id] = (target_number, bet_amount, attempts_left, multiplier)

                except asyncio.TimeoutError:
                    await interaction.user.send("시간이 초과되었습니다. 게임이 종료됩니다.")
                    del self.active_games[interaction.user.id]
                    return

            await interaction.user.send(f"게임이 종료되었습니다. 정답은 {target_number}였습니다.")
            del self.active_games[interaction.user.id]

async def setup(bot: commands.Bot):
    await bot.add_cog(Baseball(bot))