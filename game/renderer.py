import math
from typing import List
from game.dungeon import Dungeon, Tile
from game.player import Player
# from game.monster import Monster # TODO: 몬스터 클래스 구현 후 주석 해제
# from game.item import Item # TODO: 아이템 클래스 구현 후 주석 해제

# ============================================================
# 렌더링 설정값 및 이모지 정의 (중앙 관리)
# ============================================================
VIEWPORT_WIDTH = 15
VIEWPORT_HEIGHT = 9
FOV_RADIUS = 5

# 지형별 이모지 매핑 (단일 정보 출처)
TERRAIN_EMOJIS = {
    # 시야 안에 있을 때 (컬러)
    'visible': {
        'wall': "🟫",
        'floor': "🟩",
        'door': "🚪",
        'stairs_down': "🔽",
    },
    # 시야 밖에 있지만 탐험했을 때 (단색)
    'memorized': {
        'wall': "⬜",
        'floor': "▫️",
        'door': "🚪", # 기억 속의 문도 컬러로 강조
        'stairs_down': "🔽", # 계단은 기억 속에서도 잘 보이도록
    },
    # 기타
    'player': "🙂",
    'fog': "⚫",
    'monsters': {
        'default': '👹',
        'goblin': '👺',
        'snake': '🐍',
        'rat': '🐀',
    },
    'items': {
        'default': '✨',
        'magic_stone': '💎',
        'gold': '💰',
        'potion': '🧪',
        'scroll': '📜',
    }
}
# ============================================================

class Renderer:
    """게임 상태를 Discord에 표시하기 위한 형태로 렌더링하는 클래스"""

    def _get_tile_char(self, x: int, y: int, dungeon: Dungeon, player: Player, monsters: List, items: List) -> str:
        """(x, y) 좌표에 표시될 가장 우선순위 높은 이모지를 반환합니다."""
        
        # 1. 플레이어
        if player.x == x and player.y == y:
            return TERRAIN_EMOJIS['player']

        tile = dungeon.tiles[y][x]
        
        # 시야 밖이면 안개 처리
        if not tile.visible and not tile.explored:
            return TERRAIN_EMOJIS['fog']
            
        # 시야 안일 경우에만 동적 객체 표시
        if tile.visible:
            # 2. 몬스터
            for monster in monsters:
                if monster.x == x and monster.y == y:
                    return TERRAIN_EMOJIS['monsters'].get(monster.name, TERRAIN_EMOJIS['monsters']['default'])
            # 3. 아이템
            for item in items:
                if item.x == x and item.y == y:
                    return TERRAIN_EMOJIS['items'].get(item.type, TERRAIN_EMOJIS['items']['default'])
        
        # 4. 지형
        if tile.visible:
            return TERRAIN_EMOJIS['visible'].get(tile.terrain, '?')
        elif tile.explored:
            return TERRAIN_EMOJIS['memorized'].get(tile.terrain, '?')
            
        return TERRAIN_EMOJIS['fog']

    def render_game_screen(self, dungeon: Dungeon, player: Player, current_floor: int, monsters: List, items: List) -> str:
        """게임의 현재 상태를 나타내는 문자열을 생성"""
        viewport = self._render_viewport(dungeon, player, monsters, items)
        status_bar = self._render_status_bar(player, current_floor)
        
        return f"{viewport}\n{status_bar}"

    def _render_status_bar(self, player: Player, current_floor: int) -> str:
        """플레이어의 상태와 현재 층 정보를 표시하는 바를 렌더링"""
        # TODO: HP, MP 등 더 많은 정보 추가
        floor_info = f"B{current_floor}F"
        
        # 간단한 상태바 형식
        return f"`{floor_info}`"

    def _render_viewport(self, dungeon: Dungeon, player: Player, monsters: List, items: List) -> str:
        """플레이어 중심의 뷰포트를 렌더링"""
        # 뷰포트의 시작점 계산 (플레이어가 중앙에 오도록)
        start_x = player.x - VIEWPORT_WIDTH // 2
        start_y = player.y - VIEWPORT_HEIGHT // 2

        # 화면을 구성할 2D 리스트 생성
        display_grid = []
        for y_vp in range(VIEWPORT_HEIGHT):
            row = []
            for x_vp in range(VIEWPORT_WIDTH):
                map_x = start_x + x_vp
                map_y = start_y + y_vp

                char = TERRAIN_EMOJIS['fog']
                if 0 <= map_x < dungeon.width and 0 <= map_y < dungeon.height:
                    char = self._get_tile_char(map_x, map_y, dungeon, player, monsters, items)
                row.append(char)
            display_grid.append(row)

        # 2D 리스트를 하나의 문자열로 결합
        viewport_str = "\n".join("".join(row) for row in display_grid)
        
        return f"```\n{viewport_str}\n```"

    def render_full_map(self, dungeon: Dungeon, player: Player, monsters: List, items: List) -> str:
        """디버그용 전체 맵을 렌더링. 모든 타일과 오브젝트를 밝혀서 보여줍니다."""
        map_str = ""
        for y in range(dungeon.height):
            row_str = ""
            for x in range(dungeon.width):
                tile = dungeon.tiles[y][x]

                # 렌더링을 위해 모든 타일의 원래 시야 상태를 저장하고, 일시적으로 '보이는' 상태로 만듦
                original_visibility = tile.visible
                tile.visible = True
                
                # _get_tile_char를 호출하여 해당 타일의 문자를 가져옴
                row_str += self._get_tile_char(x, y, dungeon, player, monsters, items)
                
                # 타일의 시야 상태를 원래대로 복구
                tile.visible = original_visibility
            map_str += row_str + "\n"
        return map_str 