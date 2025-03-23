import discord
from discord.ext import commands
import random
import asyncio
from typing import Dict, Tuple
from Pythfinder import update_balance
from database_manager import get_db_connection


class RPSGameView(discord.ui.View):
    def __init__(self, bot, challenger, opponent, interaction, bet_amount):
        super().__init__(timeout=60)
        self.bot = bot
        self.challenger = challenger
        self.opponent = opponent
        self.interaction = interaction
        self.bet_amount = bet_amount
        self.choices = {}

    @discord.ui.button(label="가위 ✌️", style=discord.ButtonStyle.primary)
    async def choose_scissors(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.record_choice(interaction, "가위")

    @discord.ui.button(label="바위 ✊", style=discord.ButtonStyle.primary)
    async def choose_rock(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.record_choice(interaction, "바위")

    @discord.ui.button(label="보 ✋", style=discord.ButtonStyle.primary)
    async def choose_paper(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.record_choice(interaction, "보")

    async def record_choice(self, interaction, choice):
        if interaction.user not in [self.challenger, self.opponent]:
            await interaction.response.send_message("이 게임에 참여할 수 없습니다!", ephemeral=True)
            return

        self.choices[interaction.user] = choice
        await interaction.response.send_message(f"{choice}를 선택했습니다!", ephemeral=True)

        # 상대방에게 선택을 완료했다고 알리기 위해 메시지 수정
        if interaction.user == self.challenger:
            # challenger가 선택을 완료했을 때
            await self.interaction.edit_original_response(
                content=f"{self.challenger.mention}님이 선택을 완료했습니다! 상대방의 선택을 기다리고 있습니다.")
        else:
            # opponent가 선택을 완료했을 때
            await self.interaction.edit_original_response(
                content=f"{self.opponent.mention}님이 선택을 완료했습니다! 상대방의 선택을 기다리고 있습니다.")

        if len(self.choices) == 2:
            await self.resolve_game()

    async def resolve_game(self):
        # 플레이어들의 선택을 정확히 매칭시켜서 결과를 처리
        challenger_choice = self.choices.get(self.challenger)
        opponent_choice = self.choices.get(self.opponent)

        result = self.determine_winner(self.challenger, challenger_choice, self.opponent, opponent_choice, self.bet_amount)

        await self.interaction.followup.send(result)

    def determine_winner(self, player1, choice1, player2, choice2, bet_amount: int):
        outcomes = {"가위": "보", "바위": "가위", "보": "바위"}
        if choice1 == choice2:
            update_balance(self.bot.user.id, bet_amount * 2)
            update_balance(player1.id, -bet_amount)
            update_balance(player2.id, -bet_amount)
            return f"{player1.mention}({choice1}) vs {player2.mention}({choice2}) - 무승부! 두 분의 베팅금 {bet_amount}원은 봇의 통장으로 들어갑니다."
        elif outcomes[choice1] == choice2:
            update_balance(player1.id, bet_amount)
            update_balance(player2.id, -bet_amount)
            return (f"{player1.mention}({choice1})가 {player2.mention}({choice2})를 이겼습니다!"
                    f"{player1.mention}님이 {player2.mention}님의 {bet_amount}원을 획득하셨습니다.")
        else:
            update_balance(player2.id, bet_amount)
            update_balance(player1.id, -bet_amount)
            return (f"{player2.mention}({choice2})가 {player1.mention}({choice1})를 이겼습니다!"
                    f"{player2.mention}님이 {player1.mention}님의 {bet_amount}원을 획득하셨습니다.")


class RockPaperScissorsView(discord.ui.View):
    def __init__(self, bot, challenger, interaction, bet_amount):
        super().__init__(timeout=60)
        self.bot = bot
        self.challenger = challenger
        self.opponent = None
        self.interaction = interaction
        self.bet_amount = bet_amount

        self.add_item(JoinGameButton(label=f"{bet_amount}원을 내고 참가하기", view=self))


# 커스텀 버튼 아이템
class JoinGameButton(discord.ui.Button):
    """1대1 대전용 참가 버튼입니다."""
    # view 속성 추가
    @property
    def view(self):
        return self._view

    def __init__(self, label, view):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.bot = view.bot
        self.challenger = view.challenger
        self.opponent = view.opponent
        self.interaction = view.interaction
        self.bet_amount = view.bet_amount
        self.view = view

    async def callback(self, interaction: discord.Interaction):
        """참가 버튼 클릭 시 실행되는 함수"""
        if self.opponent is not None:
            await interaction.response.send_message("이미 상대가 정해졌습니다!", ephemeral=True)
            return
        if interaction.user == self.challenger:
            await interaction.response.send_message("자기 자신과 대전할 수 없습니다!", ephemeral=True)
            return

        # 베팅금 차감
        try:
            if not update_balance(interaction.user.id, -self.bet_amount):
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

        self.opponent = interaction.user
        await interaction.response.send_message(f"{self.challenger.mention} vs {self.opponent.mention}! 게임이 시작됩니다!",
                                                ephemeral=False)
        view = RPSGameView(self.bot, self.challenger, self.opponent, self.interaction, self.bet_amount)
        await interaction.followup.send(
            f"{self.challenger.mention} vs {self.opponent.mention}! 아래 버튼을 눌러 선택하세요!", view=view)

    @view.setter
    def view(self, value):
        self._view = value


class RockPaperScissors(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        @bot.tree.command(name="가위바위보", description="가위바위보 상대를 찾습니다.")
        async def 가위바위보(interaction: discord.Interaction, bet_amount: int):
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

            view = RockPaperScissorsView(self.bot, interaction.user, interaction, bet_amount)

            await interaction.response.send_message(
                f"{interaction.user.mention}님이 {bet_amount}원을 걸고 가위바위보 상대를 찾고 있습니다! 참가하려면 버튼을 눌러주세요.", view=view)


async def setup(bot):
    await bot.add_cog(RockPaperScissors(bot))
