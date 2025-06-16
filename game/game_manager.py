import math
import logging
from game.models import Dungeon, Player, create_test_dungeon

class GameManager:
    """게임의 상태와 핵심 로직을 관리하는 클래스"""

    def __init__(self):
        self.dungeon: Dungeon = create_test_dungeon()
        self.player: Player = Player(x=1, y=1)
        self.update_fov()

    def update_fov(self):
        """플레이어 주변의 시야를 업데이트"""
        # 1. 모든 타일을 '보이지 않음'으로 초기화
        for y in range(self.dungeon.height):
            for x in range(self.dungeon.width):
                self.dungeon.grid[y][x].visible = False

        # 2. 플레이어 주변의 원형 시야 내 타일을 '보임'으로 설정
        player_x, player_y = self.player.x, self.player.y
        radius = 6  # 시야 반경
        
        for y in range(max(0, player_y - radius), min(self.dungeon.height, player_y + radius + 1)):
            for x in range(max(0, player_x - radius), min(self.dungeon.width, player_x + radius + 1)):
                # 간단한 원형 시야 알고리즘
                if math.sqrt((x - player_x)**2 + (y - player_y)**2) <= radius:
                    # TODO: 더 정교한 Ray-casting 알고리즘으로 교체 필요
                    self.dungeon.grid[y][x].visible = True
                    self.dungeon.grid[y][x].explored = True


    def move_player(self, dx: int, dy: int):
        """플레이어를 이동시키고, 게임 상태를 업데이트"""
        new_x = self.player.x + dx
        new_y = self.player.y + dy

        logging.info(f"Attempting to move player from ({self.player.x}, {self.player.y}) to ({new_x}, {new_y}). Dungeon size: ({self.dungeon.width}, {self.dungeon.height})")

        if not self.dungeon.is_wall(new_x, new_y):
            self.player.x = new_x
            self.player.y = new_y
            self.update_fov()

    def get_game_state(self):
        """현재 게임 상태를 반환 (렌더러에 전달하기 위함)"""
        return {
            "dungeon": self.dungeon,
            "player": self.player
        } 