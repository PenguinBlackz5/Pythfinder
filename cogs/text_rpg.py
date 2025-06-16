import discord
from discord.ext import commands
from discord import app_commands
import logging
from database_manager import execute_query
import json

# 데이터 버전 상수는 cogs/database.py에서 중앙 관리하므로 여기서는 제거합니다.

# ==== 캐릭터 생성 UI ====

class CharacterCreationView(discord.ui.View):
    """캐릭터 생성을 위한 동적 View"""
    def __init__(self, author_id: int, races: list, classes: list):
        super().__init__(timeout=300)
        self.author_id = author_id
        self.races = {str(r['race_id']): r for r in races}
        self.classes = {str(c['class_id']): c for c in classes}
        
        self.selected_race_id = None
        self.selected_class_id = None

        # 초기에는 종족 선택만 추가
        self.add_item(self.create_race_select())

    def create_race_select(self):
        """종족 선택 드롭다운 메뉴를 생성합니다."""
        options = [
            discord.SelectOption(label=r['name'], value=str(r['race_id']), description=r['description'][:100])
            for r in self.races.values()
        ]
        select = discord.ui.Select(placeholder="1. 종족을 선택하세요...", options=options, custom_id="race_select")
        select.callback = self.on_race_select
        return select

    def create_class_select(self):
        """직업 선택 드롭다운 메뉴를 생성합니다."""
        options = [
            discord.SelectOption(label=c['name'], value=str(c['class_id']), description=c['description'][:100])
            for c in self.classes.values()
        ]
        select = discord.ui.Select(placeholder="2. 직업을 선택하세요...", options=options, custom_id="class_select")
        select.callback = self.on_class_select
        return select

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("명령어를 실행한 본인만 선택할 수 있습니다.", ephemeral=True)
            return False
        return True

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        if self.message:
            await self.message.edit(content="캐릭터 생성 시간이 초과되었습니다.", view=self)

    @discord.ui.button(label="캐릭터 생성", style=discord.ButtonStyle.success, row=2, disabled=True)
    async def create_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            race = self.races[self.selected_race_id]
            d_class = self.classes[self.selected_class_id]

            name = interaction.user.display_name
            user_id = interaction.user.id
            hp = race['base_hp']
            mp = race['base_mp']
            attack = race['base_attack']
            defense = race['base_defense']
            next_exp = 100 

            new_char = await execute_query(
                """
                INSERT INTO game_characters 
                (user_id, name, race_id, class_id, hp, max_hp, mp, max_mp, attack, defense, next_exp)
                VALUES ($1, $2, $3, $4, $5, $5, $6, $6, $7, $8, $9)
                RETURNING character_id
                """,
                (user_id, name, int(self.selected_race_id), int(self.selected_class_id), hp, mp, attack, defense, next_exp)
            )
            character_id = new_char[0]['character_id']
            
            if d_class['starting_items']:
                starting_items_str = d_class['starting_items']
                starting_items = json.loads(starting_items_str) if isinstance(starting_items_str, str) else starting_items_str
                
                for item_info in starting_items:
                    item_record = await execute_query("SELECT item_id FROM game_items WHERE name = $1", (item_info['item_name'],))
                    if item_record:
                        item_id = item_record[0]['item_id']
                        await execute_query(
                            "INSERT INTO game_inventory (character_id, item_id, quantity) VALUES ($1, $2, $3)",
                            (character_id, item_id, item_info['quantity'])
                        )

            embed = discord.Embed(title="⚔️ 모험의 시작", description=f"{interaction.user.mention}, 당신의 새로운 이야기가 시작됩니다.", color=discord.Color.green())
            embed.add_field(name="이름", value=name)
            embed.add_field(name="종족", value=race['name'])
            embed.add_field(name="직업", value=d_class['name'])
            
            await interaction.followup.send(embed=embed)
            
            for item in self.children:
                item.disabled = True
            await interaction.edit_original_response(content="캐릭터 생성이 완료되었습니다.", view=self)
            self.stop()

        except Exception as e:
            logging.error(f"캐릭터 생성 중 오류: {e}", exc_info=True)
            await interaction.followup.send("캐릭터 생성 중 오류가 발생했습니다. 다시 시도해주세요.", ephemeral=True)

    async def on_race_select(self, interaction: discord.Interaction):
        select = interaction.data['values'][0]
        self.selected_race_id = select
        
        # 직업 선택 메뉴가 없다면 추가
        if not any(c.custom_id == "class_select" for c in self.children):
            self.add_item(self.create_class_select())
        
        await interaction.response.edit_message(view=self)

    async def on_class_select(self, interaction: discord.Interaction):
        select = interaction.data['values'][0]
        self.selected_class_id = select
        
        create_btn = next((c for c in self.children if isinstance(c, discord.ui.Button)), None)
        if create_btn:
            create_btn.disabled = False
        
        await interaction.response.edit_message(view=self)

class TextRPG(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="탐험시작", description="새로운 모험을 시작하고, 당신의 분신을 만듭니다.")
    async def explore_start(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        try:
            existing_character = await execute_query("SELECT 1 FROM game_characters WHERE user_id = $1", (user_id,))
            if existing_character:
                await interaction.response.send_message("⚠️ 이미 살아있는 모험가가 있습니다. 여정을 끝마친 후에 새로운 모험을 시작할 수 있습니다.", ephemeral=True)
                return

            races = await execute_query("SELECT * FROM game_races ORDER BY name")
            classes = await execute_query("SELECT * FROM game_classes ORDER BY name")

            if not races or not classes:
                await interaction.response.send_message("❌ 게임 기본 데이터를 불러올 수 없습니다. 관리자에게 문의하세요.", ephemeral=True)
                return

            view = CharacterCreationView(interaction.user.id, races, classes)
            await interaction.response.send_message("새로운 모험을 시작합니다. 당신의 정체성을 선택해주세요.", view=view, ephemeral=True)
            view.message = await interaction.original_response()

        except Exception as e:
            logging.error(f"/탐험시작 명령어 처리 중 오류 발생: {e}", exc_info=True)
            await interaction.response.send_message("❌ 모험을 시작하는 중 오류가 발생했습니다.", ephemeral=True)

    @app_commands.command(name="내정보", description="현재 캐릭터의 상태를 확인합니다.")
    async def character_info(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        try:
            # 캐릭터 기본 정보, 종족, 직업 정보 가져오기
            char_data = await execute_query("""
                SELECT c.*, r.name as race_name, cl.name as class_name
                FROM game_characters c
                JOIN game_races r ON c.race_id = r.race_id
                JOIN game_classes cl ON c.class_id = cl.class_id
                WHERE c.user_id = $1
            """, (user_id,))

            if not char_data:
                await interaction.response.send_message("생성된 캐릭터가 없습니다. `/탐험시작`으로 새로운 모험을 시작하세요.", ephemeral=True)
                return
            
            char = char_data[0]
            character_id = char['character_id']

            # 인벤토리 정보 가져오기 (장착 장비 포함)
            inventory_data = await execute_query("""
                SELECT i.name, inv.quantity, inv.is_equipped
                FROM game_inventory inv
                JOIN game_items i ON inv.item_id = i.item_id
                WHERE inv.character_id = $1
                ORDER BY inv.is_equipped DESC, i.name
            """, (character_id,))

            # Embed 생성
            embed = discord.Embed(
                title=f"<{char['name']}>의 모험 정보",
                description=f"_{char['race_name']} {char['class_name']}_",
                color=discord.Color.blue()
            )
            embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar.url)
            
            # 주요 스탯
            embed.add_field(name="레벨", value=f"**Lv. {char['level']}** ({char['exp']}/{char['next_exp']} EXP)")
            embed.add_field(name="체력 (HP)", value=f"❤️ {char['hp']}/{char['max_hp']}", inline=True)
            embed.add_field(name="마나 (MP)", value=f"💙 {char['mp']}/{char['max_mp']}", inline=True)
            
            # 전투 능력치
            embed.add_field(name="⚔️ 공격력", value=str(char['attack']), inline=True)
            embed.add_field(name="🛡️ 방어력", value=str(char['defense']), inline=True)
            embed.add_field(name="💰 골드", value="0 G", inline=True) # 골드 필드는 나중에 추가
            
            # 장비 및 인벤토리
            equipped_items = [item['name'] for item in inventory_data if item['is_equipped']]
            inventory_items = [f"{item['name']} ({item['quantity']})" for item in inventory_data if not item['is_equipped']]

            embed.add_field(name="장착 장비", value="\n".join(equipped_items) if equipped_items else "장착한 장비가 없습니다.", inline=False)
            embed.add_field(name="가방", value="\n".join(inventory_items) if inventory_items else "가방이 비어있습니다.", inline=False)

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logging.error(f"/내정보 명령어 처리 중 오류 발생: {e}", exc_info=True)
            await interaction.response.send_message("❌ 정보를 불러오는 중 오류가 발생했습니다.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(TextRPG(bot)) 