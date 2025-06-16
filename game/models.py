from dataclasses import dataclass, field
from enum import Enum

# 렌더링 시 사용할 이모지 정의
class TileType(Enum):
    WALL = "🟫"
    FLOOR = "🟩"
    FOG = "⚫"
    UNKNOWN = "❓"
    MEMORIZED_FLOOR = "▫️"
    PLAYER = "🙂"


@dataclass
class Tile:
    """맵의 한 타일을 나타내는 클래스"""
    char: str
    visible: bool = False
    explored: bool = False

    def get_display_char(self):
        """시야와 탐험 여부에 따라 표시할 문자를 반환"""
        if not self.visible:
            if self.explored:
                return TileType.MEMORIZED_FLOOR.value
            else:
                return TileType.FOG.value
        return self.char


@dataclass
class Player:
    """플레이어의 상태를 저장하는 클래스"""
    x: int
    y: int


@dataclass
class Dungeon:
    """던전의 상태를 저장하는 클래스"""
    width: int = 0
    height: int = 0
    grid: list[list[Tile]] = field(default_factory=list, init=False)

    def initialize_from_layout(self, layout: list[str]):
        """문자열 리스트 레이아웃으로부터 그리드를 생성하고 초기화합니다."""
        if not layout or not layout[0]:
            self.height = 0
            self.width = 0
            self.grid = []
            return

        self.height = len(layout)
        self.width = len(layout[0])
        
        new_grid = []
        for y, row_str in enumerate(layout):
            if len(row_str) != self.width:
                raise ValueError(f"Inconsistent row length at index {y}. Expected {self.width}, got {len(row_str)}.")
            
            row = [Tile(char=char) for char in row_str]
            new_grid.append(row)
        
        self.grid = new_grid

    def is_wall(self, x, y):
        """해당 좌표가 벽인지 확인"""
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.grid[y][x].char == TileType.WALL.value
        return True # 맵 밖은 벽으로 간주


def create_test_dungeon() -> Dungeon:
    """테스트용으로 고정된 던전을 생성하는 함수"""
    layout = [
        "🟫🟫🟫🟫🟫🟫🟫🟫🟫🟫🟫🟫🟫🟫🟫",
        "🟫🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟫",
        "🟫🟩🟫🟫🟫🟫🟩🟫🟫🟫🟩🟫🟫🟩🟫",
        "🟫🟩🟫🟩🟩🟩🟩🟩🟩🟩🟩🟩🟫🟩🟫",
        "🟫🟩🟫🟩🟫🟫🟫🟩🟫🟫🟫🟫🟩🟫🟫",
        "🟫🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩🟫",
        "🟫🟫🟫🟫🟫🟫🟫🟫🟫🟫🟫🟫🟫🟫🟫",
    ]
    dungeon = Dungeon()
    dungeon.initialize_from_layout(layout)
    return dungeon 