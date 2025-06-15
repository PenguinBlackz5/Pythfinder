import discord
from discord.ext import commands
from discord import app_commands

class TextRPG(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="게임시작", description="텍스트 RPG 게임을 시작하고 캐릭터를 생성합니다.")
    async def start_game(self, interaction: discord.Interaction):
        # 여기에 캐릭터 생성 로직을 추가합니다.
        # 예: 데이터베이스에 사용자 정보가 이미 있는지 확인하고, 없으면 새로 생성
        await interaction.response.send_message(f"환영합니다, {interaction.user.mention}님! 모험이 곧 시작됩니다.", ephemeral=True)

    @app_commands.command(name="내정보", description="당신의 캐릭터 상태를 확인합니다.")
    async def character_info(self, interaction: discord.Interaction):
        # 여기에 데이터베이스에서 캐릭터 정보를 불러오는 로직을 추가합니다.
        embed = discord.Embed(
            title=f"{interaction.user.name}의 정보",
            description="모험가의 현재 상태입니다.",
            color=discord.Color.blue()
        )
        embed.add_field(name="레벨", value="1", inline=True)
        embed.add_field(name="체력", value="100/100", inline=True)
        embed.add_field(name="공격력", value="10", inline=True)
        embed.add_field(name="방어력", value="5", inline=True)
        embed.add_field(name="경험치", value="0/100", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(TextRPG(bot)) 