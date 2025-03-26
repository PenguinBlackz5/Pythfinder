import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
from database_manager import get_db_connection

from Pythfinder import update_balance
from typing import Optional


async def get_user_ids_from_db():
    """데이터베이스에서 모든 user_id 가져오기"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM user_money")
        user_ids = [row[0] for row in cursor.fetchall()]
        conn.close()
        return user_ids
    except sqlite3.Error as e:
        print(f"데이터베이스 오류: {e}")
        return []


async def get_user_id_from_str_id(interaction: discord.Interaction, user_name: str) -> Optional[int]:
    """
    사용자 이름(display_name)을 통해 실제 user_id를 찾는 함수

    Args:
        interaction (discord.Interaction): 현재 상호작용 컨텍스트
        user_name (str): 사용자의 디스플레이 이름

    Returns:
        str: 찾은 사용자의 user_id, 찾지 못하면 None
    """
    # 데이터베이스에서 유효한 user_ids 가져오기
    valid_user_ids = await get_user_ids_from_db()

    # 길드의 모든 멤버 중에서 이름과 일치하고 데이터베이스에 존재하는 멤버 찾기
    for member in interaction.guild.members:
        print(str(member.id), user_name, valid_user_ids)
    for member in interaction.guild.members:
        if (str(member.id) == user_name and
                member.id in valid_user_ids):
            return member.id

    return None


class UserNameTransformer(app_commands.Transformer):
    async def transform(self, interaction: discord.Interaction, value: str) -> str:
        """선택된 사용자의 ID를 반환"""
        return value

    async def autocomplete(self, interaction: discord.Interaction, current: str):
        """데이터베이스에서 유저 목록을 가져와 자동 완성"""
        user_ids = await get_user_ids_from_db()

        matching_members = [
            discord.app_commands.Choice(name=member.display_name, value=str(member.id))
            for member in interaction.guild.members
            if member.id in user_ids and current.lower() in member.display_name.lower()
        ]

        return matching_members[:25]


class TransferAutocomplete(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        @bot.tree.command(name="송금")
        async def transfer_money(
                interaction: discord.Interaction,
                recipient: app_commands.Transform[str, UserNameTransformer],
                amount: int
        ):
            """송금 커맨드"""
            recipient_id = await get_user_id_from_str_id(interaction, recipient)

            if recipient_id is None:
                await interaction.response.send_message(f"{recipient_id} 해당 사용자를 찾을 수 없습니다.")
                return

            try:
                update_balance(recipient_id, amount)
                update_balance(interaction.user.id, -amount)
                await interaction.response.send_message(f"{amount}원을 송금했습니다.")
            except Exception as e:
                await interaction.response.send_message(f"송금 중 오류가 발생했습니다: {e}")


async def setup(bot):
    await bot.add_cog(TransferAutocomplete(bot))
