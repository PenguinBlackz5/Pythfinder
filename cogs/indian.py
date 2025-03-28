import discord
from discord.ext import commands
import random
import math
from typing import Dict, Tuple, List
from main import update_balance

class IndianPoker(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_games: Dict[int, Tuple[List[int], List[int], List[int], List[int], int, float]] = {}  
        # user_id: (user_open_pool, user_hidden_pool, bot_open_pool, bot_hidden_pool, bet_amount, multiplier)

    def generate_card_pools(self) -> Tuple[List[int], List[int], List[int], List[int]]:
        """카드 풀을 생성하고 초기 카드를 뽑습니다."""
        user_open_pool = list(range(1, 11))
        user_hidden_pool = list(range(1, 11))
        bot_open_pool = list(range(1, 11))
        bot_hidden_pool = list(range(1, 11))
        return user_open_pool, user_hidden_pool, bot_open_pool, bot_hidden_pool

    def draw_cards(self, open_pool: List[int], hidden_pool: List[int]) -> Tuple[int, int]:
        """카드 풀에서 오픈 카드와 히든 카드를 무작위로 뽑습니다."""
        open_card = random.choice(open_pool)
        open_pool.remove(open_card)
        hidden_card = random.choice(hidden_pool)
        hidden_pool.remove(hidden_card)
        return open_card, hidden_card

    def reveal_random_cards(self, user_open_pool: List[int], bot_hidden_pool: List[int]) -> Tuple[int, int]:
        """베팅 시 추가로 공개할 카드를 무작위로 선택합니다."""
        user_reveal = random.choice(user_open_pool)
        user_open_pool.remove(user_reveal)
        bot_reveal = random.choice(bot_hidden_pool)
        bot_hidden_pool.remove(bot_reveal)
        return user_reveal, bot_reveal

    @commands.Cog.listener()
    async def on_ready(self):
        await self.bot.tree.sync()

    @commands.hybrid_command(name="인디언포커", description="인디언 포커 게임을 시작합니다.")
    async def indian_poker(self, ctx: commands.Context, bet_amount: int):
        if bet_amount < 1:
            error_embed = discord.Embed(
                title="❌ 오류",
                description="베팅 금액은 최소 1원 이상이어야 합니다.",
                color=0xff0000
            )
            if isinstance(ctx, discord.Interaction):
                return await ctx.response.send_message(embed=error_embed, ephemeral=True)
            return await ctx.send(embed=error_embed)

        # 베팅금 차감
        try:
            if not await update_balance(ctx.author.id, -bet_amount):
                error_embed = discord.Embed(
                    title="❌ 오류",
                    description="보유 금액이 부족합니다!",
                    color=0xff0000
                )
                if isinstance(ctx, discord.Interaction):
                    return await ctx.response.send_message(embed=error_embed, ephemeral=True)
                return await ctx.send(embed=error_embed)
        except Exception as e:
            print(f"베팅금 차감 중 오류 발생: {e}")
            error_embed = discord.Embed(
                title="❌ 오류",
                description="베팅금 차감 중 오류가 발생했습니다.",
                color=0xff0000
            )
            if isinstance(ctx, discord.Interaction):
                return await ctx.response.send_message(embed=error_embed, ephemeral=True)
            return await ctx.send(embed=error_embed)

        # 게임 초기화
        user_open_pool, user_hidden_pool, bot_open_pool, bot_hidden_pool = self.generate_card_pools()
        user_open, user_hidden = self.draw_cards(user_open_pool, user_hidden_pool)
        bot_open, bot_hidden = self.draw_cards(bot_open_pool, bot_hidden_pool)
        multiplier = 1.0

        self.active_games[ctx.author.id] = (user_open_pool, user_hidden_pool, bot_open_pool, bot_hidden_pool, bet_amount, multiplier)

        # 게임 시작 메시지
        game_embed = discord.Embed(
            title="🎮 인디언 포커",
            description=f"게임이 시작되었습니다!\n\n"
                      f"당신의 히든 카드: **{user_hidden}**\n"
                      f"봇의 오픈 카드: **{bot_open}**\n\n"
                      f"현재 배당률: **{multiplier:.1f}배** (베팅 시 {math.ceil(bet_amount * multiplier)}원)",
            color=0x00ff00
        )

        # 버튼 생성
        view = IndianPokerView(self, ctx.author.id, user_hidden, bot_open, user_open, bot_hidden, bet_amount)
        if isinstance(ctx, discord.Interaction):
            await ctx.response.send_message(embed=game_embed, view=view, ephemeral=True)
        else:
            await ctx.send(embed=game_embed, view=view)

    def generate_card_pools(self) -> Tuple[List[int], List[int], List[int], List[int]]:
        """카드 풀을 생성하고 초기 카드를 뽑습니다."""
        user_open_pool = list(range(1, 11))
        user_hidden_pool = list(range(1, 11))
        bot_open_pool = list(range(1, 11))
        bot_hidden_pool = list(range(1, 11))
        return user_open_pool, user_hidden_pool, bot_open_pool, bot_hidden_pool

    def draw_cards(self, open_pool: List[int], hidden_pool: List[int]) -> Tuple[int, int]:
        """카드 풀에서 오픈 카드와 히든 카드를 무작위로 뽑습니다."""
        open_card = random.choice(open_pool)
        open_pool.remove(open_card)
        hidden_card = random.choice(hidden_pool)
        hidden_pool.remove(hidden_card)
        return open_card, hidden_card

    def reveal_random_cards(self, user_open_pool: List[int], bot_hidden_pool: List[int]) -> Tuple[int, int]:
        """베팅 시 추가로 공개할 카드를 무작위로 선택합니다."""
        user_reveal = random.choice(user_open_pool)
        user_open_pool.remove(user_reveal)
        bot_reveal = random.choice(bot_hidden_pool)
        bot_hidden_pool.remove(bot_reveal)
        return user_reveal, bot_reveal

class IndianPokerView(discord.ui.View):
    def __init__(self, cog: IndianPoker, user_id: int, user_hidden: int, bot_open: int, 
                 user_open: int, bot_hidden: int, bet_amount: int):
        super().__init__(timeout=180)
        self.cog = cog
        self.user_id = user_id
        self.user_hidden = user_hidden
        self.bot_open = bot_open
        self.user_open = user_open
        self.bot_hidden = bot_hidden
        self.bet_amount = bet_amount
        self.bet_count = 0

    @discord.ui.button(label="베팅", style=discord.ButtonStyle.primary)
    async def bet(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("다른 사람의 게임에 참여할 수 없습니다.", ephemeral=True)

        if self.bet_count >= 4:
            return await interaction.response.send_message("더 이상 베팅할 수 없습니다.", ephemeral=True)

        game_data = self.cog.active_games.get(self.user_id)
        if not game_data:
            return await interaction.response.send_message("게임 데이터를 찾을 수 없습니다.", ephemeral=True)

        user_open_pool, user_hidden_pool, bot_open_pool, bot_hidden_pool, bet_amount, multiplier = game_data
        
        # 배당률 증가 및 카드 추가 공개
        multiplier += 0.125
        user_reveal, bot_reveal = self.cog.reveal_random_cards(user_open_pool, bot_hidden_pool)
        
        self.cog.active_games[self.user_id] = (user_open_pool, user_hidden_pool, bot_open_pool, bot_hidden_pool, bet_amount, multiplier)
        self.bet_count += 1

        game_embed = discord.Embed(
            title="🎮 인디언 포커 - 추가 정보",
            description=f"당신의 히든 카드: **{self.user_hidden}**\n"
                      f"봇의 오픈 카드: **{self.bot_open}**\n\n"
                      f"추가로 공개된 카드:\n"
                      f"당신의 가능한 오픈 카드 중 하나: **{user_reveal}**\n"
                      f"봇의 가능한 히든 카드 중 하나: **{bot_reveal}**\n\n"
                      f"현재 배당률: **{multiplier:.1f}배** (베팅 시 {math.ceil(bet_amount * multiplier)}원)",
            color=0x00ff00
        )

        if self.bet_count >= 4:
            self.remove_item(button)

        await interaction.response.edit_message(embed=game_embed, view=self)

    @discord.ui.button(label="진행", style=discord.ButtonStyle.success)
    async def proceed(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("다른 사람의 게임에 참여할 수 없습니다.", ephemeral=True)

        game_data = self.cog.active_games.get(self.user_id)
        if not game_data:
            return await interaction.response.send_message("게임 데이터를 찾을 수 없습니다.", ephemeral=True)

        _, _, _, _, bet_amount, multiplier = game_data
        user_sum = self.user_hidden + self.user_open
        bot_sum = self.bot_hidden + self.bot_open

        result_embed = discord.Embed(
            title="🎮 인디언 포커 - 결과",
            description=f"당신의 카드 합: **{user_sum}** (히든: {self.user_hidden}, 오픈: {self.user_open})\n"
                      f"봇의 카드 합: **{bot_sum}** (히든: {self.bot_hidden}, 오픈: {self.bot_open})\n\n",
            color=0x00ff00
        )

        try:
            if user_sum > bot_sum:
                winnings = math.ceil(bet_amount * multiplier)
                if await update_balance(self.cog.bot.user.id, -winnings) and await update_balance(interaction.user.id, winnings):
                    result_embed.description += f"🎉 승리! {winnings}원을 획득했습니다!"
                    result_embed.color = 0x00ff00
            elif user_sum < bot_sum:
                loss = math.ceil(bet_amount * multiplier)
                await update_balance(self.cog.bot.user.id, loss)
                result_embed.description += f"😢 패배... {loss}원을 잃었습니다."
                result_embed.color = 0xff0000
            else:
                await update_balance(interaction.user.id, bet_amount)
                result_embed.description += "🤝 무승부! 베팅금이 반환됩니다."
                result_embed.color = 0xffff00
        except Exception as e:
            print(f"결과 처리 중 오류 발생: {e}")
            result_embed.description += "오류가 발생했습니다."
            result_embed.color = 0xff0000

        del self.cog.active_games[self.user_id]
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=result_embed, view=self)

    @discord.ui.button(label="포기", style=discord.ButtonStyle.danger)
    async def fold(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("다른 사람의 게임에 참여할 수 없습니다.", ephemeral=True)

        game_data = self.cog.active_games.get(self.user_id)
        if not game_data:
            return await interaction.response.send_message("게임 데이터를 찾을 수 없습니다.", ephemeral=True)

        _, _, _, _, bet_amount, multiplier = game_data
        loss = math.ceil(bet_amount * multiplier)

        try:
            await update_balance(self.cog.bot.user.id, loss)
            fold_embed = discord.Embed(
                title="🎮 인디언 포커 - 포기",
                description=f"게임을 포기했습니다.\n"
                          f"베팅금 {loss}원을 잃었습니다.",
                color=0xff0000
            )
        except Exception as e:
            print(f"포기 처리 중 오류 발생: {e}")
            fold_embed = discord.Embed(
                title="🎮 인디언 포커 - 오류",
                description="포기 처리 중 오류가 발생했습니다.",
                color=0xff0000
            )

        del self.cog.active_games[self.user_id]
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=fold_embed, view=self)

async def setup(bot: commands.Bot):
    await bot.add_cog(IndianPoker(bot)) 