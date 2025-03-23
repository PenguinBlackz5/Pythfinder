import discord
from discord.ext import commands
from discord import app_commands

from Pythfinder import is_admin_or_developer, DEVELOPER_IDS
from database_manager import get_db_connection


def fetch_all_data(table_name):
    """특정 테이블의 모든 컬럼 데이터를 가져와 출력"""
    conn = get_db_connection()
    if not conn:
        return "데이터베이스 연결 실패!"
    try:
        with conn.cursor() as cur:
            # table_name 테이블의 모든 데이터 조회
            cur.execute(f"SELECT * FROM {table_name};")
            rows = cur.fetchall()  # 모든 행 가져오기

            # 컬럼명 가져오기
            col_names = [desc[0] for desc in cur.description]

            # 데이터 출력
            result = []
            result.append(" | ".join(col_names))  # 컬럼명 추가
            result.append("-" * 50)  # 구분선 추가
            for row in rows:
                result.append(" | ".join(map(str, row)))  # 데이터 추가

            return "\n".join(result)

    except Exception as e:
        return f"데이터 조회 오류: {e}"
    finally:
        conn.close()  # 연결 종료


class TableNameTransformer(app_commands.Transformer):
    async def transform(self, interaction: discord.Interaction, table_name: str) -> str:
        """사용자가 선택한 테이블 이름을 반환"""
        return table_name

    async def autocomplete(self, interaction: discord.Interaction, current: str):
        """데이터베이스에서 테이블 목록을 가져와 자동 완성"""
        tables = get_table_list()  # 데이터베이스에서 테이블 목록 가져오기
        return [
            app_commands.Choice(name=table, value=table)
            for table in tables if current.lower() in table.lower()
        ]


def get_table_list():
    """PostgreSQL 데이터베이스에서 테이블 목록을 가져오는 함수"""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT tablename FROM pg_catalog.pg_tables
        WHERE schemaname = 'public';
    """)  # 'public' 스키마의 테이블 목록 조회
    tables = [row[0] for row in cur.fetchall()]
    conn.close()
    return tables


class Database(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        @bot.tree.command(
            name="디비테스트",
            description="데이터베이스 연결을 테스트합니다."
        )
        @app_commands.default_permissions(administrator=True)
        async def test_db(interaction: discord.Interaction):
            if not is_admin_or_developer(interaction):
                error_embed = discord.Embed(
                    title="❌ 권한 오류",
                    description="이 명령어는 서버 관리자와 개발자만 사용할 수 있습니다!",
                    color=0xff0000
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
                return

            print(f"디비테스트 명령어 실행 - 요청자: {interaction.user.name}", flush=True)

            conn = get_db_connection()
            if not conn:
                error_embed = discord.Embed(
                    title="❌ 데이터베이스 오류",
                    description="데이터베이스 연결 실패!",
                    color=0xff0000
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
                return

            try:
                cur = conn.cursor()

                # 테이블 존재 여부 확인
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'attendance'
                    )
                """)
                attendance_exists = cur.fetchone()[0]

                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'channels'
                    )
                """)
                channels_exists = cur.fetchone()[0]

                # 각 테이블의 레코드 수 확인
                cur.execute("SELECT COUNT(*) FROM attendance")
                attendance_count = cur.fetchone()[0]

                cur.execute("SELECT COUNT(*) FROM channels")
                channels_count = cur.fetchone()[0]

                embed = discord.Embed(
                    title="✅ 데이터베이스 연결 테스트 결과",
                    color=0x00ff00
                )
                embed.add_field(
                    name="attendance 테이블",
                    value=f"존재함: {'✅' if attendance_exists else '❌'}\n레코드 수: {attendance_count}",
                    inline=True
                )
                embed.add_field(
                    name="channels 테이블",
                    value=f"존재함: {'✅' if channels_exists else '❌'}\n레코드 수: {channels_count}",
                    inline=True
                )

                await interaction.response.send_message(embed=embed, ephemeral=True)

            except Exception as e:
                print(f"디비테스트 실행 중 오류: {e}", flush=True)
                error_embed = discord.Embed(
                    title="❌ 오류",
                    description=f"데이터베이스 쿼리 실행 중 오류 발생:\n```{str(e)}```",
                    color=0xff0000
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
            finally:
                conn.close()

        @bot.tree.command(name="디비구조", description="데이터베이스의 테이블 구조와 현황을 확인합니다. (개발자 전용)")
        async def check_db_structure(interaction: discord.Interaction):
            # 개발자 권한 확인
            if interaction.user.id not in DEVELOPER_IDS:
                error_embed = discord.Embed(
                    title="⚠️ 권한 오류",
                    description="이 명령어는 개발자만 사용할 수 있습니다!",
                    color=0xff0000
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
                return

            await interaction.response.defer(ephemeral=True)

            conn = get_db_connection()
            if not conn:
                error_embed = discord.Embed(
                    title="❌ 데이터베이스 오류",
                    description="데이터베이스 연결 실패!",
                    color=0xff0000
                )
                await interaction.followup.send(embed=error_embed, ephemeral=True)
                return

            try:
                cur = conn.cursor()

                # attendance 테이블 정보 조회
                cur.execute("""
                    SELECT 
                        column_name, 
                        data_type, 
                        column_default,
                        is_nullable
                    FROM information_schema.columns 
                    WHERE table_name = 'attendance'
                    ORDER BY ordinal_position;
                """)
                attendance_columns = cur.fetchall()

                # channels 테이블 정보 조회
                cur.execute("""
                    SELECT 
                        column_name, 
                        data_type, 
                        column_default,
                        is_nullable
                    FROM information_schema.columns 
                    WHERE table_name = 'channels'
                    ORDER BY ordinal_position;
                """)
                channels_columns = cur.fetchall()

                # 각 테이블의 레코드 수 조회
                cur.execute("SELECT COUNT(*) FROM attendance")
                attendance_count = cur.fetchone()[0]

                cur.execute("SELECT COUNT(*) FROM channels")
                channels_count = cur.fetchone()[0]

                # 서버별 통계 (현재 서버 강조)
                current_guild = interaction.guild
                if current_guild:
                    member_ids = [member.id for member in current_guild.members]
                    cur.execute("""
                        SELECT COUNT(*) FROM attendance 
                        WHERE user_id = ANY(%s)
                    """, (member_ids,))
                    current_guild_count = cur.fetchone()[0]
                else:
                    current_guild_count = 0

                embed = discord.Embed(
                    title="📊 데이터베이스 구조 및 현황",
                    color=0x00ff00
                )

                # attendance 테이블 정보
                attendance_text = "```\n"
                attendance_text += "컬럼명         타입      기본값    Null허용\n"
                attendance_text += "----------------------------------------\n"
                for col in attendance_columns:
                    attendance_text += f"{col[0]:<12} {col[1]:<8} {str(col[2]):<8} {col[3]:<6}\n"
                attendance_text += "```"
                embed.add_field(
                    name="📝 attendance 테이블",
                    value=f"{attendance_text}\n총 레코드 수: {attendance_count}개\n"
                          f"{f'현재 서버 레코드 수: {current_guild_count}개' if current_guild else ''}",
                    inline=False
                )

                # channels 테이블 정보
                channels_text = "```\n"
                channels_text += "컬럼명         타입      기본값    Null허용\n"
                channels_text += "----------------------------------------\n"
                for col in channels_columns:
                    channels_text += f"{col[0]:<12} {col[1]:<8} {str(col[2]):<8} {col[3]:<6}\n"
                channels_text += "```"
                embed.add_field(
                    name="🔧 channels 테이블",
                    value=f"{channels_text}\n총 레코드 수: {channels_count}개",
                    inline=False
                )

                # 출석 채널 목록
                if channels_count > 0:
                    cur.execute("SELECT channel_id FROM channels")
                    channel_ids = cur.fetchall()
                    channel_list = []
                    for (channel_id,) in channel_ids:
                        channel = bot.get_channel(channel_id)
                        if channel:
                            channel_list.append(f"- {channel.guild.name} / #{channel.name}")
                        else:
                            channel_list.append(f"- 알 수 없는 채널 (ID: {channel_id})")
                    
                    if channel_list:
                        embed.add_field(
                            name="📍 등록된 출석 채널",
                            value="\n".join(channel_list),
                            inline=False
                        )

                await interaction.followup.send(embed=embed, ephemeral=True)

            except Exception as e:
                print(f"데이터베이스 구조 조회 중 오류 발생: {e}", flush=True)
                error_embed = discord.Embed(
                    title="❌ 오류",
                    description=f"데이터베이스 조회 중 오류가 발생했습니다.\n```{str(e)}```",
                    color=0xff0000
                )
                await interaction.followup.send(embed=error_embed, ephemeral=True)
            finally:
                conn.close()

        @bot.tree.command(name="디비조회", description="데이터베이스의 테이블 내용을 조회합니다. (개발자 전용)")
        @app_commands.describe(table_name="조회할 테이블을 선택하세요.")
        async def show_table(interaction: discord.Interaction,
                             table_name: app_commands.Transform[str, TableNameTransformer]):
            """사용자가 입력한 테이블의 모든 컬럼 내용을 출력"""

            # 개발자 권한 확인
            if interaction.user.id not in DEVELOPER_IDS:
                error_embed = discord.Embed(
                    title="⚠️ 권한 오류",
                    description="이 명령어는 개발자만 사용할 수 있습니다!",
                    color=0xff0000
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
                return

            await interaction.response.defer(ephemeral=True)

            result = fetch_all_data(table_name)

            # 너무 긴 경우 파일로 저장하여 전송
            if len(result) > 2000:  # 디스코드 메시지 제한 (2000자)
                with open("output.txt", "w", encoding="utf-8") as f:
                    f.write(result)
                await interaction.followup.send("데이터가 너무 길어 파일로 전송합니다.", file=discord.File("output.txt"))
            else:
                await interaction.followup.send(f"```\n{result}\n```")


async def setup(bot: commands.Bot):
    await bot.add_cog(Database(bot))
