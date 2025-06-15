import discord
from discord.ext import commands
from discord import app_commands
import os
import logging
from database_manager import execute_query

# 데이터 버전 정의
# 나중에 아이템, 몬스터 데이터가 추가될 때마다 이 버전을 올리고,
# sql/updates/ 폴더에 해당 버전의 sql 파일을 추가해야 합니다.
LATEST_ITEM_VERSION = 1
LATEST_MONSTER_VERSION = 1

class TextRPG(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_versions = {}
        bot.loop.create_task(self.initialize_game_data())

    async def initialize_game_data(self):
        """봇 시작 시 게임 데이터 버전을 확인하고, 필요시 업데이트를 수행합니다."""
        await self.bot.wait_until_ready()
        logging.info("TextRPG: 데이터 버전 확인 및 업데이트 시작...")

        try:
            # 코드에 정의된 최신 버전
            code_versions = {
                "items": LATEST_ITEM_VERSION,
                "monsters": LATEST_MONSTER_VERSION,
            }

            for data_type, latest_version in code_versions.items():
                # DB에 저장된 현재 버전 가져오기
                result = await execute_query(
                    "SELECT version FROM game_data_versions WHERE data_type = $1",
                    (data_type,)
                )
                db_version = result[0]['version'] if result else 0

                logging.info(f"'{data_type}' 데이터 버전: DB = v{db_version}, Code = v{latest_version}")

                # 버전 비교 및 업데이트
                if db_version < latest_version:
                    logging.info(f"'{data_type}' 데이터 업데이트 필요. (v{db_version} -> v{latest_version})")
                    await self.run_updates(data_type, db_version, latest_version)
                
                # 메모리에 현재 버전 저장
                self.data_versions[data_type] = latest_version

            logging.info("TextRPG: 데이터 버전 확인 및 업데이트 완료.")

        except Exception as e:
            logging.error(f"게임 데이터 초기화 중 심각한 오류 발생: {e}", exc_info=True)

    async def run_updates(self, data_type: str, current_version: int, target_version: int):
        """특정 데이터 타입의 업데이트 스크립트를 순차적으로 실행합니다."""
        for version in range(current_version + 1, target_version + 1):
            update_file = f"sql/updates/{data_type}_v{version}.sql"
            logging.info(f"'{update_file}' 실행 시도...")
            
            if not os.path.exists(update_file):
                logging.warning(f"업데이트 파일 '{update_file}'을(를) 찾을 수 없어 건너뜁니다.")
                continue

            try:
                with open(update_file, 'r', encoding='utf-8') as f:
                    # 주석을 제외하고 세미콜론으로 구분된 모든 명령 실행
                    commands = [cmd.strip() for cmd in f.read().split(';') if cmd.strip() and not cmd.strip().startswith('--')]
                    for command in commands:
                        await execute_query(command)
                
                # 버전 정보 업데이트
                await execute_query(
                    """
                    INSERT INTO game_data_versions (data_type, version) VALUES ($1, $2)
                    ON CONFLICT (data_type) DO UPDATE SET version = $2
                    """,
                    (data_type, version)
                )
                logging.info(f"✅ '{update_file}' 성공적으로 실행. '{data_type}'이(가) v{version}(으)로 업데이트되었습니다.")

            except Exception as e:
                logging.error(f"'{update_file}' 실행 중 오류 발생: {e}", exc_info=True)
                # 업데이트 실패 시, 더 이상 진행하지 않고 중단
                raise

    @app_commands.command(name="게임시작", description="텍스트 RPG 게임을 시작하고 캐릭터를 생성합니다.")
    async def start_game(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        
        try:
            # 사용자가 이미 캐릭터를 가지고 있는지 확인
            existing_character = await execute_query(
                "SELECT user_id FROM game_characters WHERE user_id = $1",
                (user_id,)
            )

            if existing_character:
                await interaction.response.send_message("이미 당신의 모험은 시작되었습니다. `/내정보`를 확인해보세요!", ephemeral=True)
                return

            # 새 캐릭터 생성
            await execute_query(
                """
                INSERT INTO game_characters (user_id, level, hp, max_hp, attack, defense, exp, next_exp)
                VALUES ($1, 1, 100, 100, 10, 5, 0, 100)
                """,
                (user_id,)
            )
            
            logging.info(f"{interaction.user.name}({user_id}) 님이 게임을 시작했습니다.")
            await interaction.response.send_message(f"🎉 환영합니다, {interaction.user.mention}님! 당신의 모험이 지금 막 시작되었습니다. `/내정보`로 능력치를 확인해보세요.", ephemeral=True)

        except Exception as e:
            logging.error(f"/게임시작 명령어 처리 중 오류 발생: {e}", exc_info=True)
            await interaction.response.send_message("❌ 캐릭터를 만드는 동안 오류가 발생했습니다. 잠시 후 다시 시도해주세요.", ephemeral=True)

    @app_commands.command(name="내정보", description="당신의 캐릭터 상태를 확인합니다.")
    async def character_info(self, interaction: discord.Interaction):
        user_id = interaction.user.id

        try:
            # 데이터베이스에서 캐릭터 정보 불러오기
            character_data = await execute_query(
                "SELECT * FROM game_characters WHERE user_id = $1",
                (user_id,)
            )

            if not character_data:
                await interaction.response.send_message("아직 모험을 시작하지 않으셨군요. `/게임시작`으로 당신의 이야기를 만들어보세요!", ephemeral=True)
                return
            
            char = character_data[0]

            embed = discord.Embed(
                title=f"{interaction.user.name}의 모험가 정보",
                description="당신의 위대한 여정은 이제 시작일 뿐입니다.",
                color=discord.Color.gold()
            )
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            
            embed.add_field(name="`🏅` 레벨", value=f"{char['level']}", inline=True)
            embed.add_field(name="`❤️` 체력", value=f"{char['hp']} / {char['max_hp']}", inline=True)
            embed.add_field(name="`📈` 경험치", value=f"{char['exp']} / {char['next_exp']}", inline=True)
            embed.add_field(name="`⚔️` 공격력", value=f"{char['attack']}", inline=True)
            embed.add_field(name="`🛡️` 방어력", value=f"{char['defense']}", inline=True)

            embed.set_footer(text=f"ID: {char['user_id']}")

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logging.error(f"/내정보 명령어 처리 중 오류 발생: {e}", exc_info=True)
            await interaction.response.send_message("❌ 정보를 불러오는 동안 오류가 발생했습니다. 잠시 후 다시 시도해주세요.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(TextRPG(bot)) 