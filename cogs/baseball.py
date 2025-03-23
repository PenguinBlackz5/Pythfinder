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
                error_embed = discord.Embed(
                    title="❌ 오류",
                    description="베팅 금액은 최소 1원 이상이어야 합니다.",
                    color=0xff0000
                )
                return await interaction.response.send_message(embed=error_embed, ephemeral=True)

            # 베팅금 차감
            try:
                if not update_balance(interaction.user.id, -bet_amount):
                    error_embed = discord.Embed(
                        title="❌ 오류",
                        description="보유 금액이 부족합니다!",
                        color=0xff0000
                    )
                    return await interaction.response.send_message(embed=error_embed)
            except Exception as e:
                print(f"베팅금 차감 중 오류 발생: {e}")
                error_embed = discord.Embed(
                    title="❌ 오류",
                    description="베팅금 차감 중 오류가 발생했습니다.",
                    color=0xff0000
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
                return

            # DM으로 게임 진행
            try:
                start_embed = discord.Embed(
                    title="🎮 숫자야구 게임",
                    description="게임이 시작되었습니다! DM을 확인해주세요.",
                    color=0x00ff00
                )
                await interaction.response.send_message(embed=start_embed, ephemeral=True)
            except discord.Forbidden:
                error_embed = discord.Embed(
                    title="❌ 오류",
                    description="DM을 보낼 수 없습니다. DM 설정을 확인해주세요.",
                    color=0xff0000
                )
                return await interaction.response.send_message(embed=error_embed, ephemeral=True)

            # 정답, 시도회수, 초기 배당률
            target_number, attempts_left, multiplier = generate_number(), 5, 2.0

            self.active_games[interaction.user.id] = (target_number, bet_amount, attempts_left, multiplier)

            try:
                game_start_embed = discord.Embed(
                    title="🎮 숫자야구 게임",
                    description=f"0~9 사이의 중복되지 않는 3자리 숫자를 맞춰보세요.\n"
                              f"기회는 총 {attempts_left}번 있습니다.\n"
                              f"맞추면 베팅금의 {multiplier:.1f}배를 받을 수 있습니다!",
                    color=0x00ff00
                )
                game_start_embed.add_field(name="입력 방법", value="숫자를 입력해주세요 (예: 123)", inline=False)
                await interaction.user.send(embed=game_start_embed)
            except discord.Forbidden:
                error_embed = discord.Embed(
                    title="❌ 오류",
                    description="DM을 보낼 수 없습니다. DM 설정을 확인해주세요.",
                    color=0xff0000
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
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
                        error_embed = discord.Embed(
                            title="❌ 잘못된 입력",
                            description="중복되지 않는 3자리 숫자를 입력해주세요!",
                            color=0xff0000
                        )
                        await interaction.user.send(embed=error_embed)
                        continue

                    strikes, balls = check_number(target_number, guess_number)

                    if strikes == 3:
                        # 승리 금액 계산식
                        winnings = round(bet_amount * multiplier)  # 소수점 일의자리에서 반올림

                        try:
                            # 봇의 잔고에서 차감하고 유저에게 지급
                            if update_balance(bot.user.id, -winnings) and update_balance(interaction.user.id, winnings):
                                win_embed = discord.Embed(
                                    title="🎉 승리!",
                                    description=f"정답입니다! {target_number}\n"
                                              f"축하합니다! 베팅금 {bet_amount}원의 {multiplier:.1f}배인 💰 {winnings}원을 획득했습니다!",
                                    color=0x00ff00
                                )
                                await interaction.user.send(embed=win_embed)
                                # 원래 채널에도 결과 전송
                                channel_win_embed = discord.Embed(
                                    title="🎉 숫자야구 게임 승리!",
                                    description=f"{interaction.user.mention}님 축하합니다! 숫자야구 게임에서 승리하여 베팅금 {bet_amount}원의 {multiplier:.1f}배인 💰 ***{winnings}원**을 획득했습니다!*",
                                    color=0x00ff00
                                )
                                await interaction.channel.send(embed=channel_win_embed)
                                return
                            else:
                                # 봇의 잔고 부족
                                win_no_money_embed = discord.Embed(
                                    title="🎉 승리! (지급 실패)",
                                    description=f"정답입니다! {target_number}\n"
                                              f"축하합니다! 베팅금 {bet_amount}원의 {multiplier:.1f}배인 💰 {winnings}원을 획득했습니다!\n"
                                              f"하지만 돈이 부족하여 지급해드리지 못했습니다...",
                                    color=0xffcc00
                                )
                                await interaction.user.send(embed=win_no_money_embed)
                                channel_win_no_money_embed = discord.Embed(
                                    title="🎉 숫자야구 게임 승리! (지급 실패)",
                                    description=f"{interaction.user.mention}님 축하합니다! 숫자야구 게임에서 승리하여 베팅금 {bet_amount}원의 {multiplier:.1f}배인 💰 ***{winnings}원**을 획득했습니다!*\n"
                                              f"하지만 돈이 부족하여 지급해드리지 못했습니다...",
                                    color=0xffcc00
                                )
                                await interaction.channel.send(embed=channel_win_no_money_embed)
                        except Exception as e:
                            print(f"승리 금액 지급 중 오류 발생: {e}")

                        del self.active_games[interaction.user.id]
                        return

                    attempts_left -= 1
                    multiplier -= 0.2  # 시도마다 0.2씩 감소하도록 변경
                    self.active_games[interaction.user.id] = (target_number, bet_amount, attempts_left, multiplier)

                    result_embed = discord.Embed(
                        title="⚾ 숫자야구 결과",
                        description=f"✅ **{strikes} 스트라이크 / {balls} 볼**\n"
                                  f"남은 기회 🔄️ ***{attempts_left}번***",
                        color=0xffcc00
                    )
                    await interaction.user.send(embed=result_embed)
                except asyncio.TimeoutError:
                    timeout_embed = discord.Embed(
                        title="⏰ 시간 초과",
                        description="시간이 초과되었습니다. 게임이 종료됩니다.",
                        color=0xff0000
                    )
                    await interaction.user.send(embed=timeout_embed)
                    del self.active_games[interaction.user.id]
                    return
            # 봇 잔고 추가
            update_balance(bot.user.id, bet_amount)
            # DM으로 결과 전송
            lose_embed = discord.Embed(
                title="😢 게임 종료",
                description=f"아쉽게도 모든 기회를 사용했습니다. 정답은 {target_number}였습니다.",
                color=0xff0000
            )
            await interaction.user.send(embed=lose_embed)
            # 원래 채널에 결과 전송
            channel_lose_embed = discord.Embed(
                title="😢 숫자야구 게임 종료",
                description=f"{interaction.user.mention}님의 숫자야구 게임이 종료되었습니다. 아쉽게도 정답을 맞추지 못하여 💸 ***{bet_amount}원**을 잃었습니다.*",
                color=0xff0000
            )
            await interaction.channel.send(embed=channel_lose_embed)
            del self.active_games[interaction.user.id]


async def setup(bot: commands.Bot):
    await bot.add_cog(Baseball(bot))
