import discord
from discord.ext import commands
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from Pythfinder import ResetAttendanceView, ResetMoneyView, KST
from database_manager import execute_query


class General(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        @bot.tree.command(name="출석정보", description="자신의 출석 현황을 확인합니다.")
        async def check_attendance(interaction: discord.Interaction):
            try:
                # 즉시 응답 대기 상태로 전환
                await interaction.response.defer(ephemeral=True)

                user_id = interaction.user.id
                today = datetime.now(KST).strftime('%Y-%m-%d')

                result = await execute_query(
                    'SELECT last_attendance, streak_count FROM user_attendance WHERE user_id = $1',
                    (user_id,)
                )

                if result and result[0]['last_attendance'] is not None:
                    last_attendance = result[0]['last_attendance']
                    streak = result[0]['streak_count']

                    status = "완료" if last_attendance.strftime('%Y-%m-%d') == today else "미완료"

                    # 다음 출석까지 남은 시간 계산
                    now = datetime.now(KST)
                    next_attendance = last_attendance + timedelta(days=1)
                    next_attendance = datetime(next_attendance.year, next_attendance.month, next_attendance.day,
                                             tzinfo=KST)
                    time_left = next_attendance - now

                    if time_left.total_seconds() <= 0:
                        time_left_str = "지금 출석 가능!"
                    else:
                        hours = int(time_left.total_seconds() // 3600)
                        minutes = int((time_left.total_seconds() % 3600) // 60)
                        time_left_str = f"{hours}시간 {minutes}분"

                    embed = discord.Embed(
                        title="📊 출석 현황",
                        color=0x00ff00 if status == "완료" else 0xffcc00
                    )
                    embed.add_field(name="오늘 출석", value=status, inline=True)
                    embed.add_field(name="연속 출석", value=f"{streak}일", inline=True)
                    embed.add_field(name="다음 출석까지", value=time_left_str, inline=True)
                    embed.set_footer(text=f"확인 시간: {now.strftime('%Y-%m-%d %H:%M:%S')}")

                    await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    # 출석 기록이 없거나 초기화된 경우
                    embed = discord.Embed(
                        title="📊 출석 현황",
                        color=0xffcc00
                    )
                    embed.add_field(name="오늘 출석", value="미완료", inline=True)
                    embed.add_field(name="연속 출석", value="0일", inline=True)
                    embed.add_field(name="다음 출석까지", value="지금 출석 가능!", inline=True)
                    embed.set_footer(text=f"확인 시간: {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')}")

                    await interaction.followup.send(embed=embed, ephemeral=True)

            except discord.NotFound:
                print("상호작용이 만료되었습니다.", flush=True)
            except Exception as e:
                print(f"출석정보 확인 중 오류 발생: {e}", flush=True)
                try:
                    error_embed = discord.Embed(
                        title="❌ 오류",
                        description="오류가 발생했습니다. 다시 시도해주세요.",
                        color=0xff0000
                    )
                    await interaction.followup.send(embed=error_embed, ephemeral=True)
                except discord.NotFound:
                    print("상호작용이 만료되어 응답을 보낼 수 없습니다.", flush=True)

        @bot.tree.command(name="통장", description="보유한 금액을 확인합니다.")
        async def check_balance(interaction: discord.Interaction):
            user_id = interaction.user.id

            try:
                result = await execute_query(
                    'SELECT balance FROM user_balance WHERE user_id = $1',
                    (user_id,)
                )

                if result:
                    money = result[0]['balance']
                    embed = discord.Embed(
                        title="💰 통장 잔액",
                        description=f"현재 잔액: {money:,}원",
                        color=0x00ff00
                    )
                    embed.set_footer(text=f"확인 시간: {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')}")
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                else:
                    error_embed = discord.Embed(
                        title="❌ 오류",
                        description="통장 기록이 없습니다!",
                        color=0xff0000
                    )
                    await interaction.response.send_message(embed=error_embed, ephemeral=True)

            except Exception as e:
                print(f"잔액 확인 중 오류 발생: {e}")
                error_embed = discord.Embed(
                    title="❌ 오류",
                    description="잔액 확인 중 오류가 발생했습니다. 다시 시도해주세요.",
                    color=0xff0000
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)

        @bot.tree.command(name="출석초기화", description="연속 출석 일수를 초기화합니다. (보유 금액은 유지)")
        async def reset_attendance(interaction: discord.Interaction):
            view = ResetAttendanceView(interaction.user.id)
            embed = discord.Embed(
                title="⚠️ 출석 정보 초기화",
                description="정말로 출석 정보를 초기화하시겠습니까?\n"
                          "연속 출석 일수가 초기화됩니다.\n"
                          "💰 보유 금액은 유지됩니다.",
                color=0xffcc00
            )
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        @bot.tree.command(name="통장초기화", description="보유한 금액을 0원으로 초기화합니다.")
        async def reset_money(interaction: discord.Interaction):
            view = ResetMoneyView(interaction.user.id)
            embed = discord.Embed(
                title="⚠️ 통장 초기화",
                description="정말로 통장을 초기화하시겠습니까?\n"
                          "보유한 금액이 0원으로 초기화됩니다.\n"
                          "❗ 이 작업은 되돌릴 수 없습니다!",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(General(bot))
