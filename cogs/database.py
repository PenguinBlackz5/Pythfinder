import discord
from discord.ext import commands
from discord import app_commands
from typing import List, Optional
from database_manager import execute_query

from Pythfinder import is_admin_or_developer, DEVELOPER_IDS


async def fetch_all_data(table_name: str) -> str:
    """특정 테이블의 모든 컬럼 데이터를 가져와 출력"""
    try:
        result = await execute_query(f"SELECT * FROM {table_name};")
        if not result:
            return "데이터가 없습니다."

        # 컬럼명 가져오기
        col_names = list(result[0].keys())
        
        # 데이터 출력
        output = []
        output.append(" | ".join(col_names))  # 컬럼명 추가
        output.append("-" * 50)  # 구분선 추가
        for row in result:
            output.append(" | ".join(map(str, row.values())))  # 데이터 추가

        return "\n".join(output)

    except Exception as e:
        return f"데이터 조회 오류: {e}"


class TableNameTransformer(app_commands.Transformer):
    async def transform(self, interaction: discord.Interaction, table_name: str) -> str:
        """사용자가 선택한 테이블 이름을 반환"""
        return table_name

    async def autocomplete(self, interaction: discord.Interaction, current: str):
        """데이터베이스에서 테이블 목록을 가져와 자동 완성"""
        tables = await get_table_list()  # 데이터베이스에서 테이블 목록 가져오기
        return [
            app_commands.Choice(name=table, value=table)
            for table in tables if current.lower() in table.lower()
        ]


async def get_table_list() -> List[str]:
    """PostgreSQL 데이터베이스에서 테이블 목록을 가져오는 함수"""
    try:
        result = await execute_query("""
            SELECT tablename FROM pg_catalog.pg_tables
            WHERE schemaname = 'public';
        """)
        return [row['tablename'] for row in result] if result else []
    except Exception as e:
        print(f"테이블 목록 조회 오류: {e}")
        return []


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

            try:
                # 테이블 존재 여부 확인
                result = await execute_query("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public'
                    );
                """)
                
                if result and result[0]['exists']:
                    success_embed = discord.Embed(
                        title="✅ 데이터베이스 연결 성공",
                        description="데이터베이스 연결이 정상적으로 작동합니다!",
                        color=0x00ff00
                    )
                    await interaction.response.send_message(embed=success_embed, ephemeral=True)
                else:
                    error_embed = discord.Embed(
                        title="❌ 데이터베이스 오류",
                        description="데이터베이스에 테이블이 없습니다!",
                        color=0xff0000
                    )
                    await interaction.response.send_message(embed=error_embed, ephemeral=True)
            except Exception as e:
                error_embed = discord.Embed(
                    title="❌ 데이터베이스 오류",
                    description=f"데이터베이스 연결 실패!\n오류: {str(e)}",
                    color=0xff0000
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)

        @bot.tree.command(name="디비구조", description="데이터베이스의 테이블 구조와 현황을 확인합니다. (개발자 전용)")
        async def check_db_structure(interaction: discord.Interaction):
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
                # 테이블 목록 조회
                tables = await get_table_list()
                if not tables:
                    await interaction.response.send_message("데이터베이스에 테이블이 없습니다.", ephemeral=True)
                    return

                # 각 테이블의 구조와 데이터 수 조회
                structure_info = []
                for table in tables:
                    # 테이블 구조 조회
                    columns = await execute_query(f"""
                        SELECT column_name, data_type, is_nullable
                        FROM information_schema.columns
                        WHERE table_name = '{table}'
                        ORDER BY ordinal_position;
                    """)
                    
                    # 데이터 수 조회
                    count = await execute_query(f"SELECT COUNT(*) FROM {table};")
                    row_count = count[0]['count'] if count else 0

                    # 테이블 정보 구성
                    table_info = [f"**{table}** (총 {row_count}개 행)"]
                    for col in columns:
                        nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                        table_info.append(f"- {col['column_name']}: {col['data_type']} {nullable}")
                    
                    structure_info.append("\n".join(table_info))

                # 결과 메시지 구성
                embed = discord.Embed(
                    title="📊 데이터베이스 구조",
                    description="\n\n".join(structure_info),
                    color=0x00ff00
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

            except Exception as e:
                error_embed = discord.Embed(
                    title="❌ 오류",
                    description=f"데이터베이스 구조 조회 중 오류가 발생했습니다.\n오류: {str(e)}",
                    color=0xff0000
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)

        @bot.tree.command(name="디비조회", description="데이터베이스의 테이블 내용을 조회합니다. (개발자 전용)")
        @app_commands.describe(table_name="조회할 테이블을 선택하세요.")
        async def show_table(interaction: discord.Interaction,
                           table_name: app_commands.Transform[str, TableNameTransformer]):
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
                # 테이블 데이터 조회
                data = await fetch_all_data(table_name)
                
                # 결과가 너무 길 경우 파일로 전송
                if len(data) > 1900:
                    file = discord.File(
                        io.StringIO(data),
                        filename=f"{table_name}_data.txt"
                    )
                    await interaction.response.send_message(
                        f"**{table_name}** 테이블의 데이터가 너무 길어 파일로 전송합니다.",
                        file=file,
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        f"**{table_name}** 테이블의 데이터:\n```\n{data}\n```",
                        ephemeral=True
                    )

            except Exception as e:
                error_embed = discord.Embed(
                    title="❌ 오류",
                    description=f"데이터 조회 중 오류가 발생했습니다.\n오류: {str(e)}",
                    color=0xff0000
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Database(bot))
