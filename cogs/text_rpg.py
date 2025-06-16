import discord
from discord.ext import commands
from discord import app_commands
import logging
from database_manager import execute_query
import json
import sentry_sdk

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

    def _get_display_content(self) -> str:
        """현재 선택 사항을 바탕으로 메시지 내용을 생성합니다."""
        content_parts = []
        if self.selected_race_id:
            race = self.races[self.selected_race_id]
            content_parts.append(f"**✅ 종족: {race['name']}**\n> {race['description']}")
        
        if self.selected_class_id:
            d_class = self.classes[self.selected_class_id]
            content_parts.append(f"**✅ 직업: {d_class['name']}**\n> {d_class['description']}")

        if not content_parts:
            return "새로운 모험을 시작합니다. 당신의 정체성을 선택해주세요."
            
        return "\n\n".join(content_parts)

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
        self.selected_race_id = interaction.data['values'][0]
        
        for child in self.children:
            if isinstance(child, discord.ui.Select) and child.custom_id == "race_select":
                child.disabled = True
        
        if not any(c.custom_id == "class_select" for c in self.children):
            self.add_item(self.create_class_select())
        
        content = self._get_display_content()
        await interaction.response.edit_message(content=content, view=self)

    async def on_class_select(self, interaction: discord.Interaction):
        self.selected_class_id = interaction.data['values'][0]

        for child in self.children:
            if isinstance(child, discord.ui.Select) and child.custom_id == "class_select":
                child.disabled = True
        
        create_btn = next((c for c in self.children if isinstance(c, discord.ui.Button)), None)
        if create_btn:
            create_btn.disabled = False
        
        content = self._get_display_content()
        await interaction.response.edit_message(content=content, view=self)

# Phase 0 imports
from game.game_manager import GameManager
from game.renderer import Renderer

# 게임 세션을 관리하기 위한 임시 저장소
# TODO: 프로덕션 환경에서는 Redis 같은 외부 저장소로 교체 필요
active_game_sessions = {}

class GameUIView(discord.ui.View):
    """게임의 상호작용 버튼을 관리하는 View 클래스"""
    def __init__(self, game_manager: GameManager, renderer: Renderer):
        super().__init__(timeout=None)
        self.game_manager = game_manager
        self.renderer = renderer
        self.message = None

    async def handle_move(self, interaction: discord.Interaction, dx: int, dy: int):
        """플레이어 이동 및 화면 업데이트 처리"""
        try:
            # 1. 입력 잠금: 모든 버튼 비활성화
            for item in self.children:
                item.disabled = True
            await interaction.response.edit_message(view=self)

            # 2. 게임 로직 처리
            self.game_manager.move_player(dx, dy)
            game_state = self.game_manager.get_game_state()
            
            # 3. 화면 렌더링
            rendered_screen = self.renderer.render_game_screen(**game_state)

            # 4. 잠금 해제: 모든 버튼 활성화
            for item in self.children:
                item.disabled = False
            
            await interaction.edit_original_response(content=rendered_screen, view=self)
        
        except IndexError:
            p = self.game_manager.player
            d = self.game_manager.dungeon
            error_message = (
                f"❌ 렌더링 오류가 발생했습니다! (list index out of range)\n\n"
                f"**디버그 정보:**\n"
                f"```"
                f"Player Position: ({p.x}, {p.y})\n"
                f"Attempted Move: ({dx}, {dy})\n"
                f"Dungeon Size: ({d.width}, {d.height})\n"
                f"```\n"
                f"이 정보와 함께 개발자에게 문의해주세요."
            )
            logging.error(f"IndexError during rendering: Player({p.x},{p.y}), Move({dx},{dy}), Dungeon({d.width},{d.height})", exc_info=True)
            await interaction.edit_original_response(content=error_message, view=None) # view=None to remove buttons
        
        except Exception as e:
            logging.error(f"An unexpected error occurred in handle_move: {e}", exc_info=True)
            await interaction.edit_original_response(content=f"알 수 없는 오류 발생: {e}", view=None)

    # 3x3 격자 이동 버튼
    @discord.ui.button(label="↖", style=discord.ButtonStyle.secondary, row=0)
    async def move_nw(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_move(interaction, -1, -1)
        
    @discord.ui.button(label="↑", style=discord.ButtonStyle.primary, row=0)
    async def move_n(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_move(interaction, 0, -1)
        
    @discord.ui.button(label="↗", style=discord.ButtonStyle.secondary, row=0)
    async def move_ne(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_move(interaction, 1, -1)
        
    @discord.ui.button(label="←", style=discord.ButtonStyle.primary, row=1)
    async def move_w(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_move(interaction, -1, 0)
        
    @discord.ui.button(label=".", style=discord.ButtonStyle.secondary, row=1, disabled=True)
    async def placeholder(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass # 중앙 버튼
        
    @discord.ui.button(label="→", style=discord.ButtonStyle.primary, row=1)
    async def move_e(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_move(interaction, 1, 0)
        
    @discord.ui.button(label="↙", style=discord.ButtonStyle.secondary, row=2)
    async def move_sw(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_move(interaction, -1, 1)

    @discord.ui.button(label="↓", style=discord.ButtonStyle.primary, row=2)
    async def move_s(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_move(interaction, 0, 1)
        
    @discord.ui.button(label="↘", style=discord.ButtonStyle.secondary, row=2)
    async def move_se(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_move(interaction, 1, 1)

class TextRPG(commands.Cog):
    dungeon = app_commands.Group(name="던전", description="텍스트 로그라이크 게임 관련 명령어")

    def __init__(self, bot):
        self.bot = bot

    @dungeon.command(name="시작", description="새로운 모험을 시작하고, 당신의 분신을 만듭니다.")
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
            logging.error(f"/던전 시작 명령어 처리 중 오류 발생: {e}", exc_info=True)
            await interaction.response.send_message("❌ 모험을 시작하는 중 오류가 발생했습니다.", ephemeral=True)

    @dungeon.command(name="정보", description="현재 캐릭터의 상태를 확인합니다.")
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
                await interaction.response.send_message("생성된 캐릭터가 없습니다. `/던전 시작`으로 새로운 모험을 시작하세요.", ephemeral=True)
                return
            
            char = char_data[0]
            character_id = char['character_id']

            # 인벤토리 정보 가져오기 (아이템 타입 포함)
            inventory_data = await execute_query("""
                SELECT i.name, i.item_type, inv.quantity, inv.is_equipped
                FROM game_inventory inv
                JOIN game_items i ON inv.item_id = i.item_id
                WHERE inv.character_id = $1
                ORDER BY inv.is_equipped DESC, i.item_type, i.name
            """, (character_id,))

            # Embed 생성
            embed = discord.Embed(
                title=f"<{char['name']}>의 모험 정보",
                description=f"_{char['race_name']} {char['class_name']}_",
                color=discord.Color.dark_gold()
            )
            embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
            
            # 1. 기본 정보 필드
            embed.add_field(
                name="🌟 기본 정보",
                value=f"**레벨**: {char['level']}\n"
                      f"**경험치**: {char['exp']}/{char['next_exp']}\n"
                      f"**위치**: 지하 {char['dungeon_level']}층",
                inline=True
            )

            # 2. 능력치 필드
            embed.add_field(
                name="📊 능력치",
                value=f"**체력**: ❤️ {char['hp']}/{char['max_hp']}\n"
                      f"**마나**: 💙 {char['mp']}/{char['max_mp']}\n"
                      f"**식량**: 🍞 {char['food']}",
                inline=True
            )

            # 3. 전투 능력치 필드
            embed.add_field(
                name="⚔️ 전투력",
                value=f"**공격력**: {char['attack']}\n"
                      f"**방어력**: {char['defense']}\n"
                      f"**골드**: 💰 {char.get('gold', 0)} G",
                inline=True
            )

            # 4. 장착 장비 필드
            equipped_items_str = []
            for item in inventory_data:
                if item['is_equipped']:
                    type_icon = {'WEAPON': '🗡️', 'ARMOR': '🛡️'}.get(item['item_type'], '🔹')
                    equipped_items_str.append(f"{type_icon} {item['name']}")
            
            embed.add_field(
                name="🎽 장착 장비",
                value='\n'.join(equipped_items_str) if equipped_items_str else "장착한 장비가 없습니다.",
                inline=False
            )

            # 5. 가방 필드
            inventory_items_str = [f" • {item['name']} x{item['quantity']}" for item in inventory_data if not item['is_equipped']]
            
            embed.add_field(
                name="🎒 가방",
                value='\n'.join(inventory_items_str) if inventory_items_str else "가방이 비어있습니다.",
                inline=False
            )
            
            embed.set_footer(text=f"캐릭터 ID: {character_id}")

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logging.error(f"/던전 정보 명령어 처리 중 오류 발생: {e}", exc_info=True)
            await interaction.response.send_message("❌ 정보를 불러오는 중 오류가 발생했습니다.", ephemeral=True)

    @dungeon.command(name="테스트", description="[테스트] Phase 0 기능을 테스트합니다.")
    async def test_phase0(self, interaction: discord.Interaction):
        """Phase 0 테스트용 명령어"""
        game_manager = None
        try:
            user_id = interaction.user.id
            
            # 새로운 게임 세션 시작
            game_manager = GameManager()
            renderer = Renderer()
            
            active_game_sessions[user_id] = {
                "manager": game_manager,
                "renderer": renderer
            }

            game_state = game_manager.get_game_state()
            rendered_screen = renderer.render_game_screen(**game_state)
            
            view = GameUIView(game_manager, renderer)

            await interaction.response.send_message(rendered_screen, view=view)
            
            view.message = await interaction.original_response()

        except IndexError:
            p = game_manager.player if game_manager else "N/A"
            d = game_manager.dungeon if game_manager else "N/A"
            player_pos = f"({p.x}, {p.y})" if hasattr(p, 'x') else p
            dungeon_size = f"({d.width}, {d.height})" if hasattr(d, 'width') else d

            error_message = (
                f"❌ 초기 렌더링 오류가 발생했습니다! (list index out of range)\n\n"
                f"**디버그 정보:**\n"
                f"```"
                f"Player Position: {player_pos}\n"
                f"Dungeon Size: {dungeon_size}\n"
                f"```\n"
                f"이 정보와 함께 개발자에게 문의해주세요."
            )
            logging.error(f"IndexError during initial rendering: Player={player_pos}, Dungeon={dungeon_size}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message(error_message, ephemeral=True)
            else:
                await interaction.followup.send(error_message, ephemeral=True)

        except Exception as e:
            logging.error(f"An unexpected error occurred in test_phase0: {e}", exc_info=True)
            sentry_sdk.capture_exception(e)
            if not interaction.response.is_done():
                await interaction.response.send_message(f"오류 발생: {e}", ephemeral=True)
            else:
                await interaction.followup.send(f"오류 발생: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(TextRPG(bot)) 