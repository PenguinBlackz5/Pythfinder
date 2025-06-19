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
        self.player = Player(x=0, y=0) # 초기 위치는 어차피 설정됨
        self.current_floor = 0
        self.dungeon = None
        self.monsters = []
        self.items = []
        
        self.go_to_next_floor()

    def _generate_floor(self):
        """새로운 던전 층을 생성하고 플레이어를 배치"""
        self.dungeon = Dungeon(DUNGEON_WIDTH, DUNGEON_HEIGHT)
        self.player.x = self.dungeon.player_start_x
        self.player.y = self.dungeon.player_start_y
        
        # TODO: 몬스터 및 아이템 생성 로직 추가
        self.monsters = []
        self.items = []

        self.update_fov()

    def go_to_next_floor(self):
        """다음 층으로 이동. 새 던전을 생성하고 게임 상태를 재설정."""
        self.current_floor += 1
        self._generate_floor()
        logging.info(f"Player moved to floor {self.current_floor}")

    def update_fov(self):
        """플레이어 주변의 시야를 다시 계산"""
        if self.dungeon:
            compute_fov(
                dungeon=self.dungeon,
                player_x=self.player.x,
                player_y=self.player.y,
                radius=FOV_RADIUS
            )

    def teleport_to_room(self, room_id: int) -> bool:
        """[개발자용] 플레이어를 지정된 방 ID의 중심으로 순간이동시킵니다."""
        target_room = next((r for r in self.dungeon.rooms if r.id == room_id), None)

        if target_room:
            new_x, new_y = target_room.center()
            self.player.x = new_x
            self.player.y = new_y
            self.update_fov()
            logging.info(f"Player teleported to room {room_id} at ({new_x}, {new_y}).")
            return True
        else:
            logging.warning(f"Teleport failed: Room ID {room_id} not found.")
            return False

    def use_stairs(self):
        """플레이어가 현재 위치에서 계단을 사용할 수 있는지 확인하고 사용"""
        current_tile = self.dungeon.tiles[self.player.y][self.player.x]
        if current_tile.terrain == 'stairs_down':
            self.go_to_next_floor()
            return True # 성공
        return False # 계단이 아님

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
            "player": self.player,
            "current_floor": self.current_floor,
            "monsters": self.monsters,
            "items": self.items,
        } 