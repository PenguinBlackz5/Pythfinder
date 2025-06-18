import math
import logging
from game.dungeon import Dungeon, DUNGEON_WIDTH, DUNGEON_HEIGHT
from game.player import Player
from game.fov import compute_fov

# 시야 반경 설정
FOV_RADIUS = 6

class GameManager:
    """게임의 상태와 핵심 로직을 관리하는 클래스"""

    def __init__(self):
        self.dungeon = Dungeon(DUNGEON_WIDTH, DUNGEON_HEIGHT)
        
        start_x = self.dungeon.player_start_x
        start_y = self.dungeon.player_start_y
        self.player = Player(x=start_x, y=start_y)
        
        self.update_fov()

    def update_fov(self):
        """플레이어 주변의 시야를 다시 계산"""
        compute_fov(
            dungeon=self.dungeon,
            player_x=self.player.x,
            player_y=self.player.y,
            radius=FOV_RADIUS
        )

    def move_player(self, dx: int, dy: int):
        """플레이어를 이동시키고, 게임 상태를 업데이트"""
        new_x = self.player.x + dx
        new_y = self.player.y + dy

        logging.info(f"Attempting to move player from ({self.player.x}, {self.player.y}) to ({new_x}, {new_y}). Dungeon size: ({self.dungeon.width}, {self.dungeon.height})")

        if 0 <= new_x < self.dungeon.width and 0 <= new_y < self.dungeon.height:
            target_tile = self.dungeon.tiles[new_y][new_x]

            if target_tile.terrain == 'door':
                # 문을 여는 행동
                target_tile.terrain = 'floor'
                target_tile.blocked = False
                target_tile.block_sight = False
                self.update_fov()
                logging.info(f"Player opened a door at ({new_x}, {new_y})")
            elif not target_tile.blocked:
                # 일반 이동
                self.player.x = new_x
                self.player.y = new_y
                self.update_fov()
            # 그 외 (벽)는 아무것도 하지 않음

    def get_game_state(self):
        """현재 게임 상태를 반환 (렌더러에 전달하기 위함)"""
        return {
            "dungeon": self.dungeon,
            "player": self.player
        } 