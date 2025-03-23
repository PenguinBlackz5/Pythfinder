import discord
from discord.ext import commands
import random
import asyncio
from typing import Dict, Tuple
from Pythfinder import update_balance
from database_manager import get_db_connection


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
        self.active_games: Dict[
            int, Tuple[str, int, int, float]] = {}  # user_id: (target_number, bet_amount, attempts_left, multiplier)

        @bot.tree.command(name="숫자야구", description="숫자야구 게임을 시작합니다.")
        async def baseball(interaction: discord.Interaction, bet_amount: int):
            if bet_amount < 1:
                return await interaction.response.send_message("베팅 금액은 최소 1원 이상이어야 합니다.", ephemeral=True)

            # 베팅금 차감
            try:
                if not update_balance(interaction.user.id, -bet_amount):
                    return await interaction.response.send_message("보유 금액이 부족합니다!")
            except Exception as e:
                print(f"베팅금 차감 중 오류 발생: {e}")
                await interaction.response.send_message("베팅금 차감 중 오류가 발생했습니다.", ephemeral=True)
                return

            # DM으로 게임 진행
            try:
                await interaction.response.send_message("게임이 시작되었습니다! DM을 확인해주세요.", ephemeral=True)
            except discord.Forbidden:
                return await interaction.response.send_message("DM을 보낼 수 없습니다. DM 설정을 확인해주세요.", ephemeral=True)

            # 정답, 시도회수, 초기 배당률
            target_number, attempts_left, multiplier = generate_number(), 5, 2.0

            self.active_games[interaction.user.id] = (target_number, bet_amount, attempts_left, multiplier)

            try:
                await interaction.user.send(
                    f"숫자야구 게임이 시작되었습니다!\n"
                    f"0~9 사이의 중복되지 않는 3자리 숫자를 맞춰보세요.\n"
                    f"기회는 총 {attempts_left}번 있습니다.\n"
                    f"맞추면 베팅금의 {multiplier:.1f}배를 받을 수 있습니다!\n"
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
                        # 승리 금액 계산식
                        winnings = round(bet_amount * multiplier)  # 소수점 일의자리에서 반올림

                        try:
                            # 봇의 잔고에서 차감하고 유저에게 지급
                            if update_balance(bot.user.id, -winnings) and update_balance(interaction.user.id, winnings):
                                await interaction.user.send(f"정답입니다! {target_number}\n"
                                                            f"축하합니다! 베팅금 {bet_amount}원의 {multiplier:.1f}배인 💰 {winnings}원을 획득했습니다!")
                                # 원래 채널에도 결과 전송
                                await interaction.channel.send(
                                    f"{interaction.user.mention}님 축하합니다! 숫자야구 게임에서 승리하여 베팅금 {bet_amount}원의 {multiplier:.1f}배인 💰 ***{winnings}원**을 획득했습니다!*")
                                return
                            else:
                                # 봇의 잔고 부족
                                await interaction.user.send(f"정답입니다! {target_number}\n"
                                                            f"축하합니다! 베팅금 {bet_amount}원의 {multiplier:.1f}배인 💰 {winnings}원을 획득했습니다!\n"
                                                            f"하지만 돈이 부족하여 지급해드리지 못했습니다...")
                                await interaction.channel.send(
                                    f"{interaction.user.mention}님 축하합니다! 숫자야구 게임에서 승리하여 베팅금 {bet_amount}원의 {multiplier:.1f}배인 💰 ***{winnings}원**을 획득했습니다!*\n"
                                    f"하지만 돈이 부족하여 지급해드리지 못했습니다...")
                        except Exception as e:
                            print(f"승리 금액 지급 중 오류 발생: {e}")

                        del self.active_games[interaction.user.id]
                        return

                    attempts_left -= 1
                    multiplier -= 0.2  # 시도마다 0.2씩 감소하도록 변경
                    self.active_games[interaction.user.id] = (target_number, bet_amount, attempts_left, multiplier)

                    await interaction.user.send(f"✅ **{strikes} 스트라이크 / {balls} 볼**\n"
                                                f"남은 기회 🔄️ ***{attempts_left}번***")
                except asyncio.TimeoutError:
                    await interaction.user.send("시간이 초과되었습니다. 게임이 종료됩니다.")
                    del self.active_games[interaction.user.id]
                    return
            # 봇 잔고 추가
            update_balance(bot.user.id, bet_amount)
            # DM으로 결과 전송
            await interaction.user.send(f"아쉽게도 모든 기회를 사용했습니다. 정답은 {target_number}였습니다.")
            # 원래 채널에 결과 전송
            await interaction.channel.send(
                f"{interaction.user.mention}님의 숫자야구 게임이 종료되었습니다. 아쉽게도 정답을 맞추지 못하여 💸 ***{bet_amount}원**을 잃었습니다.*")
            del self.active_games[interaction.user.id]


async def setup(bot: commands.Bot):
    await bot.add_cog(Baseball(bot))
