from game.models import Dungeon, Player, TileType

VIEWPORT_WIDTH = 15
VIEWPORT_HEIGHT = 9

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
        for y in range(VIEWPORT_HEIGHT):
            row = []
            for x in range(VIEWPORT_WIDTH):
                map_x = start_x + x
                map_y = start_y + y
                
                if 0 <= map_x < dungeon.width and 0 <= map_y < dungeon.height:
                    tile = dungeon.grid[map_y][map_x]
                    # Tile 클래스의 메서드를 사용하여 표시할 문자 결정
                    row.append(tile.get_display_char())
                else:
                    # 맵 밖은 안개로 표시
                    row.append(TileType.FOG.value)
            display_grid.append(row)
            
        # 플레이어 위치에 플레이어 아이콘 삽입
        viewport_player_x = VIEWPORT_WIDTH // 2
        viewport_player_y = VIEWPORT_HEIGHT // 2
        
        if 0 <= viewport_player_y < VIEWPORT_HEIGHT and 0 <= viewport_player_x < VIEWPORT_WIDTH:
             display_grid[viewport_player_y][viewport_player_x] = TileType.PLAYER.value

        # 2D 리스트를 하나의 문자열로 결합
        viewport_str = "\n".join("".join(row) for row in display_grid)
        
        return f"```\n{viewport_str}\n```" 