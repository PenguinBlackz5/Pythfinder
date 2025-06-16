import discord
from discord.ext import commands
from discord import app_commands
from typing import List, Optional
from database_manager import execute_query
from main import is_admin_or_developer, DEVELOPER_IDS
import io
import os


async def fetch_all_data(table_name: str) -> str:
    """특정 테이블의 모든 컬럼 데이터를 가져와 출력"""
    try:
        result = await execute_query(f"SELECT * FROM {table_name};")
        if not result:
            return "데이터가 없습니다."

        # 컬럼명 가져오기
        col_names = list(result[0].keys())
        
        # 데이터 출력
        output = [" | ".join(col_names), "-" * 50]
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
        self.db_initialized = False

    @commands.Cog.listener()
    async def on_ready(self):
        """봇이 준비되면 데이터베이스 초기화를 시작합니다."""
        if not self.db_initialized:
            print("Bot is ready, starting database initialization...")
            await initialize_database()
            self.db_initialized = True

    @app_commands.command(name="db실행", description="SQL 파일을 실행하여 데이터베이스를 설정합니다. (개발자 전용)")
    @app_commands.describe(filename="실행할 SQL 파일 이름을 입력하세요 (예: create_game_tables.sql)")
    async def execute_sql_file(self, interaction: discord.Interaction, filename: str):
        if interaction.user.id not in DEVELOPER_IDS:
            await interaction.response.send_message("❌ 이 명령어는 개발자만 사용할 수 있습니다!", ephemeral=True)
            return

        sql_file_path = os.path.join('sql', filename)

        if not os.path.exists(sql_file_path):
            await interaction.response.send_message(f"❌ '{sql_file_path}' 파일을 찾을 수 없습니다.", ephemeral=True)
            return

        try:
            with open(sql_file_path, 'r', encoding='utf-8') as f:
                sql_script = f.read()

            # 여러 SQL 문이 있을 수 있으므로 세미콜론으로 분리하여 각각 실행
            # (주석을 제거하고 비어있지 않은 문장만 실행)
            commands = [
                cmd.strip() for cmd in sql_script.split(';')
                if cmd.strip() and not cmd.strip().startswith('--')
            ]

            for command in commands:
                await execute_query(command)

            await interaction.response.send_message(
                f"✅ '{filename}' 파일의 SQL 스크립트를 성공적으로 실행했습니다.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ SQL 스크립트 실행 중 오류가 발생했습니다.\n`{e}`",
                ephemeral=True
            )

    @app_commands.command(
        name="디비테스트",
        description="데이터베이스 연결을 테스트합니다."
    )
    @app_commands.default_permissions(administrator=True)
    async def test_db(self, interaction: discord.Interaction):
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

    @app_commands.command(name="디비구조", description="데이터베이스의 테이블 구조와 현황을 확인합니다. (개발자 전용)")
    async def check_db_structure(self, interaction: discord.Interaction):
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

    @app_commands.command(name="디비조회", description="데이터베이스의 테이블 내용을 조회합니다. (개발자 전용)")
    @app_commands.describe(table_name="조회할 테이블을 선택하세요.")
    async def show_table(self, interaction: discord.Interaction,
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


async def initialize_database():
    """데이터베이스를 초기화하고 모든 테이블 생성 및 데이터 업데이트를 수행합니다."""
    try:
        print("데이터베이스 초기화 시작...")
        # 1. 모든 게임 테이블 생성 (스크립트 전체를 단일 명령으로 실행)
        sql_file_path = 'sql/create_game_tables.sql'
        with open(sql_file_path, 'r', encoding='utf-8') as f:
            sql_script = f.read()
            if sql_script:  # 파일이 비어있지 않은지 확인
                await execute_query(sql_script)
        print("✅ 기본 테이블 구조 생성 완료.")

        # 2. 데이터 버전 확인 및 업데이트 적용
        await check_and_apply_updates()

    except Exception as e:
        import traceback
        print(f"❌ 데이터베이스 초기화 중 심각한 오류 발생: {e}")
        traceback.print_exc()


async def check_and_apply_updates():
    """sql/updates 폴더를 확인하여 데이터베이스 업데이트를 자동으로 적용합니다."""
    print("데이터 업데이트 확인 시작...")
    updates_path = 'sql/updates'
    if not os.path.exists(updates_path):
        print("`sql/updates` 폴더가 존재하지 않아 업데이트를 건너뜁니다.")
        return

    try:
        # 데이터 타입별 현재 DB 버전 가져오기
        db_versions_records = await execute_query("SELECT data_type, version FROM game_data_versions")
        db_versions = {rec['data_type']: rec['version'] for rec in db_versions_records}

        # 업데이트 파일 목록 가져오기 및 파싱
        update_files = sorted(os.listdir(updates_path))
        
        # 데이터 타입별로 업데이트할 파일들을 정리
        updates_to_apply = {}
        for filename in update_files:
            if filename.endswith(".sql"):
                parts = filename[:-4].split('_v')
                if len(parts) == 2:
                    data_type, version_str = parts
                    try:
                        version = int(version_str)
                        if data_type not in updates_to_apply:
                            updates_to_apply[data_type] = []
                        updates_to_apply[data_type].append({'version': version, 'filename': filename})
                    except ValueError:
                        continue # 버전이 숫자가 아닌 파일은 무시

        # 각 데이터 타입에 대해 버전 비교 및 스크립트 실행
        for data_type, files in updates_to_apply.items():
            current_db_version = db_versions.get(data_type, 0)
            
            # 버전 순으로 정렬
            sorted_files = sorted(files, key=lambda x: x['version'])

            for file_info in sorted_files:
                if file_info['version'] > current_db_version:
                    print(f"'{data_type}' 데이터 업데이트 적용: 버전 {file_info['version']} (파일: {file_info['filename']})")
                    file_path = os.path.join(updates_path, file_info['filename'])
                    
                    with open(file_path, 'r', encoding='utf-8') as f:
                        sql_script = f.read()
                    
                    await execute_query(sql_script)
                    await execute_query(
                        "UPDATE game_data_versions SET version = $1 WHERE data_type = $2",
                        (file_info['version'], data_type)
                    )
        
        print("✅ 모든 데이터 업데이트 확인 및 적용 완료.")

    except Exception as e:
        import traceback
        print(f"❌ 데이터 업데이트 확인 중 오류 발생: {e}")
        traceback.print_exc()


async def setup(bot: commands.Bot):
    await bot.add_cog(Database(bot))
