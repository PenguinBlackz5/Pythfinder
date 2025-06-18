"""
Ray-casting 기반의 시야(Field of View, FoV) 계산 모듈
"""
from typing import Set, Tuple
from game.dungeon import Dungeon

def compute_fov(dungeon: Dungeon, player_x: int, player_y: int, radius: int):
    """
    주어진 맵에서 플레이어의 시야를 계산하고, 타일의 visible 및 explored 상태를 업데이트합니다.

    :param dungeon: 던전 맵 객체
    :param player_x: 플레이어의 x 좌표
    :param player_y: 플레이어의 y 좌표
    :param radius: 시야 반경
    """
    visible_tiles: Set[Tuple[int, int]] = set()
    
    # 플레이어 위치는 항상 보임
    visible_tiles.add((player_x, player_y))

    # 시야 반경 내의 경계 타일에 대해 광선을 쏨
    for x in range(player_x - radius, player_x + radius + 1):
        cast_ray(dungeon, player_x, player_y, x, player_y - radius, visible_tiles)
        cast_ray(dungeon, player_x, player_y, x, player_y + radius, visible_tiles)

    for y in range(player_y - radius + 1, player_y + radius):
        cast_ray(dungeon, player_x, player_y, player_x - radius, y, visible_tiles)
        cast_ray(dungeon, player_x, player_y, player_x + radius, y, visible_tiles)

    # 모든 타일의 visible 상태를 먼저 False로 초기화
    for y in range(dungeon.height):
        for x in range(dungeon.width):
            dungeon.tiles[y][x].visible = False

    # 계산된 시야 내 타일들의 상태를 업데이트
    for x, y in visible_tiles:
        if 0 <= x < dungeon.width and 0 <= y < dungeon.height:
            dungeon.tiles[y][x].visible = True
            dungeon.tiles[y][x].explored = True


def cast_ray(dungeon: Dungeon, start_x: int, start_y: int, end_x: int, end_y: int, visible_tiles: Set[Tuple[int, int]]):
    """
    Bresenham's Line Algorithm을 사용하여 시작점에서 끝점까지 광선을 쏩니다.
    """
    line = bresenham_line(start_x, start_y, end_x, end_y)
    for x, y in line:
        if not (0 <= x < dungeon.width and 0 <= y < dungeon.height):
            break
        
        visible_tiles.add((x, y))
        if dungeon.tiles[y][x].block_sight:
            # 시야를 막는 타일을 만나면 광선 전파 중지
            break


def bresenham_line(x0: int, y0: int, x1: int, y1: int) -> list[Tuple[int, int]]:
    """
    Bresenham's Line Algorithm. 두 점 사이의 모든 정수 좌표를 반환합니다.
    """
    points = []
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    
    x, y = x0, y0
    
    while True:
        points.append((x, y))
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy
            
    return points 