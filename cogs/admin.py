import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime

from Pythfinder import DEVELOPER_IDS, KST, RankingView, ClearAllView, is_admin_or_developer
from database_manager import get_db_connection


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        @bot.tree.command(name="출석채널", description="출석을 인식할 채널을 지정합니다.")
        @app_commands.default_permissions(administrator=True)
        @app_commands.guild_only()  # 서버에서만 사용 가능하도록 설정
        async def set_attendance_channel(interaction: discord.Interaction):
            # 관리자 또는 개발자 권한 확인
            if not is_admin_or_developer(interaction):
                error_embed = discord.Embed(
                    title="❌ 권한 오류",
                    description="이 명령어는 서버 관리자와 개발자만 사용할 수 있습니다!",
                    color=0xff0000
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
                return

            # DM 채널에서 실행 방지
            if isinstance(interaction.channel, discord.DMChannel):
                error_embed = discord.Embed(
                    title="❌ 채널 오류",
                    description="이 명령어는 서버에서만 사용할 수 있습니다!",
                    color=0xff0000
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
                return

            channel_id = interaction.channel_id
            print(f"\n=== 출석 채널 설정 시도 ===", flush=True)
            print(f"채널 ID: {channel_id}", flush=True)
            print(f"현재 등록된 출석 채널: {bot.attendance_channels}", flush=True)

            try:
                # 먼저 응답 대기 상태로 전환
                await interaction.response.defer(ephemeral=True)
            except discord.NotFound:
                print("상호작용이 만료되었습니다.", flush=True)
                return

            conn = get_db_connection()
            if not conn:
                print("데이터베이스 연결 실패", flush=True)
                try:
                    error_embed = discord.Embed(
                        title="❌ 데이터베이스 오류",
                        description="데이터베이스 연결 실패!",
                        color=0xff0000
                    )
                    await interaction.followup.send(embed=error_embed, ephemeral=True)
                except discord.NotFound:
                    print("상호작용이 만료되었습니다.", flush=True)
                return

            try:
                c = conn.cursor()

                # 현재 서버의 모든 채널 ID 가져오기
                guild_channels = [channel.id for channel in interaction.guild.channels]

                # 현재 서버의 기존 출석 채널 삭제
                c.execute('DELETE FROM channels WHERE channel_id = ANY(%s)', (guild_channels,))
                deleted_count = c.rowcount
                print(f"삭제된 기존 출석 채널 수: {deleted_count}", flush=True)

                # 새로운 채널 등록
                c.execute('INSERT INTO channels (channel_id) VALUES (%s)', (channel_id,))
                conn.commit()

                # 메모리 캐시 업데이트
                c.execute('SELECT channel_id FROM channels')
                channels = c.fetchall()
                if channels:
                    bot.attendance_channels = set(channel[0] for channel in channels)
                    print(f"업데이트된 출석 채널 목록: {bot.attendance_channels}", flush=True)
                else:
                    print("등록된 채널이 없습니다.", flush=True)
                    bot.attendance_channels = set()  # 빈 집합으로 초기화

                try:
                    success_embed = discord.Embed(
                        title="✅ 출석 채널 설정 완료",
                        description=f"이 채널이 출석 채널로 지정되었습니다!\n"
                                  f"📝 기존에 등록되어 있던 {deleted_count}개의 출석 채널이 초기화되었습니다.",
                        color=0x00ff00
                    )
                    await interaction.followup.send(embed=success_embed, ephemeral=True)
                except discord.NotFound:
                    print("상호작용이 만료되었습니다.", flush=True)

            except Exception as e:
                print(f"채널 등록 중 오류 발생: {e}", flush=True)
                try:
                    error_embed = discord.Embed(
                        title="❌ 오류",
                        description="채널 등록 중 오류가 발생했습니다.",
                        color=0xff0000
                    )
                    await interaction.followup.send(embed=error_embed, ephemeral=True)
                except discord.NotFound:
                    print("상호작용이 만료되었습니다.", flush=True)
            finally:
                conn.close()
            print("=== 출석 채널 설정 완료 ===\n", flush=True)

        @bot.tree.command(name="출석현황", description="서버 멤버들의 출석 현황을 확인합니다. (개발자 전용)")
        async def check_server_attendance(interaction: discord.Interaction):
            # 개발자 권한 확인
            if interaction.user.id not in DEVELOPER_IDS:
                try:
                    error_embed = discord.Embed(
                        title="⚠️ 권한 오류",
                        description="이 명령어는 개발자만 사용할 수 있습니다!",
                        color=0xff0000
                    )
                    await interaction.response.send_message(embed=error_embed, ephemeral=True)
                except discord.NotFound:
                    print("상호작용이 만료되었습니다.", flush=True)
                return

            # DM에서 실행 방지
            if not interaction.guild:
                try:
                    error_embed = discord.Embed(
                        title="❌ 채널 오류",
                        description="이 명령어는 서버에서만 사용할 수 있습니다!",
                        color=0xff0000
                    )
                    await interaction.response.send_message(embed=error_embed, ephemeral=True)
                except discord.NotFound:
                    print("상호작용이 만료되었습니다.", flush=True)
                return

            try:
                await interaction.response.defer(ephemeral=True)
            except discord.NotFound:
                print("상호작용이 만료되었습니다.", flush=True)
                return

            try:
                guild = interaction.guild
                await guild.chunk()  # 멤버 목록 다시 로드

                conn = get_db_connection()
                if not conn:
                    try:
                        error_embed = discord.Embed(
                            title="❌ 데이터베이스 오류",
                            description="데이터베이스 연결 실패!",
                            color=0xff0000
                        )
                        await interaction.followup.send(embed=error_embed, ephemeral=True)
                    except discord.NotFound:
                        print("상호작용이 만료되었습니다.", flush=True)
                    return

                cur = conn.cursor()

                # 현재 날짜 (KST)
                today = datetime.now(KST).strftime('%Y-%m-%d')

                # 서버 멤버들의 출석 정보 조회
                member_ids = [member.id for member in guild.members if not member.bot]
                member_id_str = ','.join(str(id) for id in member_ids)

                if not member_ids:
                    try:
                        error_embed = discord.Embed(
                            title="❌ 오류",
                            description="서버에 멤버가 없습니다.",
                            color=0xff0000
                        )
                        await interaction.followup.send(embed=error_embed, ephemeral=True)
                    except discord.NotFound:
                        print("상호작용이 만료되었습니다.", flush=True)
                    return

                cur.execute(f'''
                    SELECT 
                        user_id,
                        last_attendance,
                        streak
                    FROM attendance 
                    WHERE user_id IN ({member_id_str})
                    ORDER BY streak DESC
                ''')

                attendance_results = cur.fetchall()

                cur.execute(f'''
                    SELECT
                        user_id,
                        money
                    FROM user_money
                    where user_id IN ({member_id_str})
                    ORDER BY money DESC
                ''')

                user_money_results = cur.fetchall()

                print(user_money_results)

                # 통계 계산
                registered_members = len(attendance_results)
                today_attendance = sum(1 for r in attendance_results if r[1] and r[1].strftime('%Y-%m-%d') == today)
                total_money = sum(r[1] for r in user_money_results if r[1])

                # 메시지 구성
                embed = discord.Embed(
                    title=f"📊 {guild.name} 서버 출석 현황",
                    color=0x00ff00
                )

                # 통계 정보
                stats_text = f"등록 멤버: {registered_members}명\n"
                stats_text += f"오늘 출석: {today_attendance}명\n"
                stats_text += f"전체 보유 금액: {total_money:,}원"
                embed.add_field(name="📈 통계", value=stats_text, inline=False)

                # 멤버별 상세 정보
                member_text = "```\n"
                member_text += "닉네임         연속출석  마지막출석    보유금액\n"
                member_text += "------------------------------------------------\n"

                user_money_dict = {user_id: money for user_id, money in user_money_results}

                for user_id, last_attendance, streak in attendance_results:
                    member = guild.get_member(user_id)
                    if member:
                        name = member.display_name[:10] + "..." if len(
                            member.display_name) > 10 else member.display_name.ljust(10)
                        last_date = last_attendance.strftime('%Y-%m-%d') if last_attendance else "없음"
                        streak = streak or 0
                        money = user_money_dict.get(user_id, 0)

                        member_text += f"{name:<13} {streak:<8} {last_date:<12} {money:>6}원\n"

                member_text += "```"
                embed.add_field(name="👥 멤버별 현황", value=member_text, inline=False)

                try:
                    await interaction.followup.send(embed=embed, ephemeral=True)
                except discord.NotFound:
                    print("상호작용이 만료되었습니다.", flush=True)

            except Exception as e:
                print(f"출석 현황 조회 중 오류 발생: {e}", flush=True)
                try:
                    error_embed = discord.Embed(
                        title="❌ 오류",
                        description=f"출석 현황 조회 중 오류가 발생했습니다.\n```{str(e)}```",
                        color=0xff0000
                    )
                    await interaction.followup.send(embed=error_embed, ephemeral=True)
                except discord.NotFound:
                    print("상호작용이 만료되었습니다.", flush=True)
            finally:
                if conn:
                    conn.close()

        @bot.tree.command(name="랭킹", description="서버의 출석/보유금액 랭킹을 확인합니다.")
        async def check_ranking(interaction: discord.Interaction):
            view = RankingView(interaction.user.id)
            embed = discord.Embed(
                title="📊 랭킹 확인",
                description="확인하고 싶은 랭킹을 선택해주세요!\n\n"
                          "1️⃣ 출석 랭킹: 연속 출석 일수 기준 TOP 10\n"
                          "2️⃣ 보유 금액 랭킹: 보유 금액 기준 TOP 10",
                color=0x00ff00
            )
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        @bot.tree.command(name="클리어올캐시", description="⚠️ 이 서버의 모든 출석 데이터를 초기화합니다. (개발자 전용)")
        async def clear_all_cache(interaction: discord.Interaction):
            # 개발자 권한 확인
            if interaction.user.id not in DEVELOPER_IDS:
                await interaction.response.send_message("⚠️ 이 명령어는 개발자만 사용할 수 있습니다!", ephemeral=True)
                return

            # DM에서 실행 방지
            if not interaction.guild:
                await interaction.response.send_message("이 명령어는 서버에서만 사용할 수 있습니다!", ephemeral=True)
                return

            guild = interaction.guild

            try:
                # 서버 멤버 목록 다시 가져오기
                await guild.chunk()  # 모든 멤버 정보 다시 로드

                # 실제 멤버 수 계산 (봇 제외)
                member_count = sum(1 for member in guild.members if not member.bot)
                print(f"서버 '{guild.name}'의 멤버 수: {member_count}", flush=True)  # 디버깅용

                if member_count == 0:
                    await interaction.response.send_message(
                        "❌ 멤버 목록을 가져올 수 없습니다. 봇의 권한을 확인해주세요.",
                        ephemeral=True
                    )
                    return

                view = ClearAllView(interaction.user.id, guild.id)
                await interaction.response.send_message(
                    f"⚠️ **정말로 이 서버의 출석 데이터를 초기화하시겠습니까?**\n\n"
                    f"**서버: {guild.name}**\n"
                    f"**영향 받는 멤버: {member_count}명**\n\n"
                    "다음 데이터가 초기화됩니다:\n"
                    "- 서버 멤버들의 출석 정보\n"
                    "- 서버 멤버들의 연속 출석 일수\n"
                    "- 서버 멤버들의 보유 금액\n\n"
                    "❗ **이 작업은 되돌릴 수 없습니다!**\n"
                    "❗ **출석 채널 설정은 유지됩니다.**\n"
                    "❗ **다른 서버의 데이터는 영향받지 않습니다.**",
                    view=view,
                    ephemeral=True
                )
            except Exception as e:
                print(f"멤버 목록 가져오기 실패: {e}", flush=True)
                await interaction.response.send_message(
                    "멤버 목록을 가져오는 중 오류가 발생했습니다.",
                    ephemeral=True
                )


async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
