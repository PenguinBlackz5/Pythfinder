import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from typing import Optional, List, Dict, Any

from main import DEVELOPER_IDS, KST, RankingView, ClearAllView, is_admin_or_developer
from database_manager import execute_query


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

            try:
                # 현재 서버의 모든 채널 ID 가져오기
                guild_channels = [channel.id for channel in interaction.guild.channels]

                # 현재 서버의 기존 출석 채널 삭제
                result = await execute_query(
                    'DELETE FROM attendance_channels WHERE channel_id = ANY(%s) RETURNING channel_id',
                    (guild_channels,)
                )
                deleted_count = len(result) if result else 0
                print(f"삭제된 기존 출석 채널 수: {deleted_count}", flush=True)

                # 새로운 채널 등록
                await execute_query(
                    'INSERT INTO attendance_channels (channel_id, guild_id) VALUES (%s, %s)',
                    (channel_id, interaction.guild_id)
                )

                # 메모리 캐시 업데이트
                result = await execute_query('SELECT channel_id FROM channels')
                if result:
                    bot.attendance_channels = {row['channel_id'] for row in result}
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
                print(f"출석 채널 설정 중 오류 발생: {e}", flush=True)
                try:
                    error_embed = discord.Embed(
                        title="❌ 오류",
                        description=f"출석 채널 설정 중 오류가 발생했습니다.\n오류: {str(e)}",
                        color=0xff0000
                    )
                    await interaction.followup.send(embed=error_embed, ephemeral=True)
                except discord.NotFound:
                    print("상호작용이 만료되었습니다.", flush=True)
            finally:
                print("=== 출석 채널 설정 완료 ===\n", flush=True)

        @bot.tree.command(name="출석현황", description="서버 멤버들의 출석 현황을 확인합니다. (개발자 전용)")
        async def check_server_attendance(interaction: discord.Interaction):
            # 개발자 권한 확인
            if not is_admin_or_developer(interaction):
                error_embed = discord.Embed(
                    title="❌ 권한 오류",
                    description="이 명령어는 개발자만 사용할 수 있습니다!",
                    color=0xff0000
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
                return

            try:
                # 서버 멤버 목록 가져오기
                guild = interaction.guild
                member_ids = [member.id for member in guild.members if not member.bot]

                # 출석 데이터 조회
                attendance_results = await execute_query(
                    '''
                    SELECT 
                        user_id,
                        attendance_count,
                        streak_count,
                        last_attendance
                    FROM user_attendance
                    WHERE user_id = ANY(%s)
                    ORDER BY attendance_count DESC
                    ''',
                    (member_ids,)
                )

                if not attendance_results:
                    await interaction.response.send_message("아직 출석 기록이 없습니다.", ephemeral=True)
                    return

                user_money_results = await execute_query(
                    '''
                    SELECT
                        user_id,
                        money
                    FROM user_money
                    where user_id = Any($1)
                    ORDER BY money DESC 
                    ''',
                    (member_ids,)
                )

                # 결과 처리
                attendance_data = []
                for row in attendance_results:
                    member = guild.get_member(row['user_id'])
                    if member:
                        attendance_data.append({
                            'name': member.display_name,
                            'count': row['attendance_count'],
                            'streak': row['streak_count'],
                            'last': row['last_attendance']
                        })

                user_money_data = []
                for row in user_money_results:
                    member = guild.get_member(row['user_id'])
                    if member:
                        user_money_data.append({
                            'name': member.display_name,
                            'money': row['money']
                        })

                registered_members = len(attendance_results)
                today_attendance = sum(
                    1 for row in (attendance_results or [])
                    if row.get("attendance_date") and row["attendance_date"].strftime('%Y-%m-%d') == today)
                total_money = sum(
                    row.get("money") for row in (user_money_results or [])
                    if row.get("money")
                )

                # 메시지 구성
                embed = discord.Embed(
                    title="📊 서버 출석 현황",
                    description=f"총 {len(attendance_data)}명의 멤버가 출석했습니다.",
                    color=0x00ff00
                )

                # 상위 10명만 표시
                for i, data in enumerate(attendance_data[:10], 1):
                    last_attendance = data['last'].strftime('%Y-%m-%d %H:%M') if data['last'] else '없음'
                    embed.add_field(
                        name=f"{i}위: {data['name']}",
                        value=f"총 출석: {data['count']}회\n"
                              f"연속 출석: {data['streak']}일\n"
                              f"마지막 출석: {last_attendance}",
                        inline=False
                    )

                # 통계 정보
                stats_text = f"등록 멤버: {registered_members}명\n"
                stats_text += f"오늘 출석: {today_attendance}명\n"
                stats_text += f"전체 보유 금액: {total_money:,}원"
                embed.add_field(name="📈 통계", value=stats_text, inline=False)

                await interaction.response.send_message(embed=embed, ephemeral=True)

            except Exception as e:
                error_embed = discord.Embed(
                    title="❌ 오류",
                    description=f"출석 현황 조회 중 오류가 발생했습니다.\n오류: {str(e)}",
                    color=0xff0000
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)

        @bot.tree.command(name="랭킹", description="서버의 출석/보유금액 랭킹을 확인합니다.")
        async def check_ranking(interaction: discord.Interaction):
            """출석/보유금액 랭킹을 확인합니다."""
            try:
                # 뷰 생성
                view = RankingView(interaction.user.id)
                
                # 임베드 생성
                embed = discord.Embed(
                    title="📊 랭킹 확인",
                    description="확인하고 싶은 랭킹을 선택해주세요!\n\n"
                                "1️⃣ 출석 랭킹: 연속 출석 일수 기준 TOP 10\n"
                                "2️⃣ 보유 금액 랭킹: 보유 금액 기준 TOP 10",
                    color=0x00ff00
                )

                # 상호작용 응답
                try:
                    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
                except discord.NotFound:
                    # 상호작용이 만료된 경우 followup 사용
                    await interaction.followup.send(embed=embed, view=view, ephemeral=True)
                except Exception as e:
                    print(f"랭킹 명령어 응답 오류: {e}")
                    try:
                        await interaction.followup.send("랭킹 정보를 표시하는 중 오류가 발생했습니다.", ephemeral=True)
                    except:
                        pass

            except Exception as e:
                print(f"랭킹 명령어 실행 오류: {e}")
                try:
                    await interaction.followup.send("랭킹 정보를 가져오는 중 오류가 발생했습니다.", ephemeral=True)
                except:
                    pass

        @bot.tree.command(name="클리어올캐시", description="⚠️ 이 서버의 모든 출석 데이터를 초기화합니다. (개발자 전용)")
        async def clear_all_cache(interaction: discord.Interaction):
            # 개발자 권한 확인
            if not is_admin_or_developer(interaction):
                error_embed = discord.Embed(
                    title="❌ 권한 오류",
                    description="이 명령어는 개발자만 사용할 수 있습니다!",
                    color=0xff0000
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
                return

            view = ClearAllView(interaction.user.id, interaction.guild_id)
            await interaction.response.send_message(
                "⚠️ 정말로 이 서버의 모든 출석 데이터를 초기화하시겠습니까?\n"
                "이 작업은 되돌릴 수 없습니다!",
                view=view,
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
