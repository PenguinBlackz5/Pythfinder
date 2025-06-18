import math
from game.dungeon import Dungeon, Tile
from game.player import Player

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
    },
    # 시야 밖에 있지만 탐험했을 때 (단색)
    'memorized': {
        'wall': "⬜",
        'floor': "▫️",
        'door': "🚪", # 기억 속의 문도 컬러로 강조
    },
    # 기타
    'player': "🙂",
    'fog': "⚫",
}
# ============================================================

class Renderer:
    """게임 상태를 Discord에 표시하기 위한 형태로 렌더링하는 클래스"""

    def render_game_screen(self, dungeon: Dungeon, player: Player) -> str:
        """게임의 현재 상태를 나타내는 문자열을 생성"""
        viewport = self._render_viewport(dungeon, player)
        # TODO: 추후 상태 바, 메시지 로그 등을 여기에 추가
        return viewport

    def _render_viewport(self, dungeon: Dungeon, player: Player) -> str:
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
                    tile = dungeon.tiles[map_y][map_x]
                    
                    if tile.visible:
                        char = TERRAIN_EMOJIS['visible'].get(tile.terrain, '?')
                    elif tile.explored:
                        char = TERRAIN_EMOJIS['memorized'].get(tile.terrain, '?')
                row.append(char)
            display_grid.append(row)

        # 플레이어 위치에 플레이어 아이콘 삽입
        viewport_player_x = VIEWPORT_WIDTH // 2
        viewport_player_y = VIEWPORT_HEIGHT // 2
        
        if 0 <= viewport_player_y < VIEWPORT_HEIGHT and 0 <= viewport_player_x < VIEWPORT_WIDTH:
             display_grid[viewport_player_y][viewport_player_x] = TERRAIN_EMOJIS['player']

        # 2D 리스트를 하나의 문자열로 결합
        viewport_str = "\n".join("".join(row) for row in display_grid)
        
        return f"```\n{viewport_str}\n```" 