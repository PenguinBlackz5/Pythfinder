import discord
from psycopg2 import Error
from discord.ext import commands
from datetime import datetime, timedelta

from Pythfinder import ConfirmView, MoneyResetView, get_db_connection, KST


class General(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        @bot.tree.command(name="출석정보", description="자신의 출석 현황을 확인합니다.")
        async def check_attendance(interaction: discord.Interaction):
            conn = None
            try:
                # 즉시 응답 대기 상태로 전환
                await interaction.response.defer(ephemeral=True)

                user_id = interaction.user.id
                today = datetime.now(KST).strftime('%Y-%m-%d')

                conn = get_db_connection()
                if not conn:
                    await interaction.followup.send("데이터베이스 연결 실패!", ephemeral=True)
                    return

                c = conn.cursor()

                c.execute('SELECT last_attendance, streak FROM attendance WHERE user_id = %s', (user_id,))
                result = c.fetchone()

                if result and result[0] is not None:
                    last_attendance = result[0]
                    streak = result[1]

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

                    await interaction.followup.send(
                        f"📊 출석 현황\n"
                        f"오늘 출석: {status}\n"
                        f"연속 출석: {streak}일\n"
                        f"다음 출석까지: {time_left_str}",
                        ephemeral=True
                    )
                else:
                    # 출석 기록이 없거나 초기화된 경우
                    await interaction.followup.send(
                        f"📊 출석 현황\n"
                        f"오늘 출석: 미완료\n"
                        f"연속 출석: 0일\n"
                        f"다음 출석까지: 지금 출석 가능!",
                        ephemeral=True
                    )

            except discord.NotFound:
                print("상호작용이 만료되었습니다.", flush=True)
            except Exception as e:
                print(f"출석정보 확인 중 오류 발생: {e}", flush=True)
                try:
                    await interaction.followup.send("오류가 발생했습니다. 다시 시도해주세요.", ephemeral=True)
                except discord.NotFound:
                    print("상호작용이 만료되어 응답을 보낼 수 없습니다.", flush=True)

            finally:
                if conn:
                    conn.close()

        @bot.tree.command(name="통장", description="보유한 금액을 확인합니다.")
        async def check_balance(interaction: discord.Interaction):
            user_id = interaction.user.id

            conn = get_db_connection()
            if not conn:
                return

            try:
                cur = conn.cursor()

                cur.execute('SELECT money FROM attendance WHERE user_id = %s', (user_id,))
                result = cur.fetchone()

                if result:
                    money = result[0]
                    await interaction.response.send_message(
                        f"💰 현재 잔액: {money}원",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message("통장 기록이 없습니다!", ephemeral=True)

            except Error as e:
                print(f"잔액 확인 중 오류 발생: {e}")
                await interaction.response.send_message("잔액 확인 중 오류가 발생했습니다. 다시 시도해주세요.", ephemeral=True)
            finally:
                conn.close()

        @bot.tree.command(name="출석초기화", description="연속 출석 일수를 초기화합니다. (보유 금액은 유지)")
        async def reset_attendance(interaction: discord.Interaction):
            view = ConfirmView(interaction.user.id)
            await interaction.response.send_message(
                "⚠️ 정말로 출석 정보를 초기화하시겠습니까?\n"
                "연속 출석 일수가 초기화됩니다.\n"
                "💰 보유 금액은 유지됩니다.",
                view=view,
                ephemeral=True
            )

        @bot.tree.command(name="통장초기화", description="보유한 금액을 0원으로 초기화합니다.")
        async def reset_money(interaction: discord.Interaction):
            view = MoneyResetView(interaction.user.id)
            await interaction.response.send_message(
                "⚠️ 정말로 통장을 초기화하시겠습니까?\n"
                "보유한 금액이 0원으로 초기화됩니다.\n"
                "❗ 이 작업은 되돌릴 수 없습니다!",
                view=view,
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(General(bot))
