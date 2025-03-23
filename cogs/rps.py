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
        await interaction.response.send_message(f"{interaction.user.mention}님이 선택을 완료했습니다!", ephemeral=True)

        if len(self.choices) == 2:
            await self.resolve_game()

    async def resolve_game(self):
        choices = list(self.choices.values())
        result = determine_winner(self.challenger, choices[0], self.opponent, choices[1], self.bet_amount)
        await self.interaction.response.send_message(result)

    def determine_winner(self, player1, choice1, player2, choice2, bet_amount: int):
        outcomes = {"가위": "보", "바위": "가위", "보": "바위"}
        if choice1 == choice2:
            update_balance(self.bot.id, bet_amount)
            update_balance(player1.id, -bet_amount)
            update_balance(player2.id, -bet_amount)
            return f"{player1.mention}({choice1}) vs {player2.mention}({choice2}) - 무승부! 베팅금은 봇의 통장으로 들어갑니다."
        elif outcomes[choice1] == choice2:
            update_balance(player1.id, bet_amount)
            update_balance(player2.id, -bet_amount)
            return f"{player1.mention}({choice1})가 {player2.mention}({choice2})를 이겼습니다!"
        else:
            update_balance(player2.id, bet_amount)
            update_balance(player1.id, -bet_amount)
            return f"{player2.mention}({choice2})가 {player1.mention}({choice1})를 이겼습니다!"


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
        self.view = view  # View에 접근하기 위해 저장

    async def callback(self, interaction: discord.Interaction):
        """참가 버튼 클릭 시 실행되는 함수"""
        if self.opponent is not None:
            await interaction.response.send_message("이미 상대가 정해졌습니다!", ephemeral=True)
            return

        self.opponent = interaction.user
        await interaction.response.send_message(f"{self.challenger.mention} vs {self.opponent.mention}! 게임이 시작됩니다!",
                                                ephemeral=False)
        view = RPSGameView(self.bot, self.challenger, self.opponent, self.interaction, self.bet_amount)
        await self.interaction.response.send_message(
            f"{self.challenger.mention} vs {self.opponent.mention}! 아래 버튼을 눌러 선택하세요!", view=view)

    @view.setter
    def view(self, value):
        self._view = value


class RockPaperScissors(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        @bot.tree.command(name="가위바위보", description="가위바위보 상대를 찾습니다.")
        async def 가위바위보(interaction: discord.Interaction, bet_amount: int):
            view = RockPaperScissorsView(self.bot, interaction.user, interaction, bet_amount)

            await interaction.response.send_message(
                f"{interaction.user.mention}님이 {bet_amount}원을 걸고 가위바위보 상대를 찾고 있습니다! 참가하려면 버튼을 눌러주세요.", view=view)


async def setup(bot):
    await bot.add_cog(RockPaperScissors(bot))
