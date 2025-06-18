"""
던전 생성 및 관리를 담당하는 모듈입니다.
"""
import random
import math
import heapq

# ============================================================
# 던전 생성 설정값 (Tuning Parameters)
# 이 값들을 수정하여 생성되는 던전의 특성을 바꿀 수 있습니다.
# ============================================================
DUNGEON_WIDTH = 80
DUNGEON_HEIGHT = 24

# 방 생성 관련
MAX_ROOMS = 15              # 던전의 최대 방 개수
ROOM_MIN_SIZE = 5           # 방의 최소 크기 (가로/세로)
ROOM_MAX_SIZE = 9           # 방의 최대 크기 (가로/세로)

# 복도 및 연결 관련
ADDITIONAL_CONNECTION_CHANCE = 0.4 # 0.0 ~ 1.0: 순환로(loop)를 만들 추가 연결 생성 확률

# 특징(Feature) 생성 관련
DOOR_CHANCE_PER_ROOM = 0.9    # 0.0 ~ 1.0: 복도 입구에 문이 생성될 확률
# ============================================================

class Tile:
    """던전 맵의 한 타일을 나타내는 클래스"""
    def __init__(self, blocked: bool, block_sight: bool = None, terrain: str = 'wall'):
        self.blocked = blocked
        if block_sight is None:
            block_sight = blocked
        self.block_sight = block_sight
        self.explored = False
        self.visible = False # 플레이어의 현재 시야에 보이는지 여부
        self.terrain = terrain
        if not blocked and terrain == 'wall':
            self.terrain = 'floor'


class Room:
    """던전의 한 구역을 나타내는 클래스"""
    def __init__(self, x, y, w, h, room_id):
        self.x1 = x
        self.y1 = y
        self.x2 = x + w
        self.y2 = y + h
        self.id = room_id
        self.connected_rooms = set()
        self.connected_corridors = set()

    def center(self):
        """방의 중심 좌표를 반환합니다."""
        center_x = (self.x1 + self.x2) // 2
        center_y = (self.y1 + self.y2) // 2
        return center_x, center_y

    def contains_floor(self, x, y):
        """주어진 좌표가 방의 바닥 영역 내에 있는지 확인합니다."""
        return self.x1 < x < self.x2 and self.y1 < y < self.y2

    def intersects(self, other):
        """다른 방과 겹치는지 확인합니다. (1칸 여유공간 포함)"""
        return (self.x1 <= other.x2 + 1 and self.x2 >= other.x1 - 1 and
                self.y1 <= other.y2 + 1 and self.y2 >= other.y1 - 1)


class Corridor:
    """던전의 복도를 나타내는 클래스"""
    def __init__(self, corridor_id, room1_id, room2_id, path):
        self.id = corridor_id
        self.room1_id = room1_id
        self.room2_id = room2_id
        self.path = path
        self.length = len(path)


class Dungeon:
    """던전 맵의 구조와 타일 데이터를 관리하는 클래스"""
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.tiles = self._initialize_tiles()
        self.rooms = []
        self.corridors = []
        self._corridor_id_counter = 0
        self._generate_rooms()
        self._connect_all_rooms()
        # 플레이어 시작 위치 (첫 번째 방의 중앙)
        if self.rooms:
            self.player_start_x, self.player_start_y = self.rooms[0].center()
        else: # 방이 하나도 생성되지 않은 경우
            self.player_start_x, self.player_start_y = self.width // 2, self.height // 2


    def _initialize_tiles(self):
        """맵을 벽으로 가득 채운 초기 타일 그리드를 생성합니다."""
        return [[Tile(True) for _ in range(self.width)] for _ in range(self.height)]

    def _generate_rooms(self):
        """던전의 방들을 생성하고 배치합니다."""
        self.rooms = []
        for i in range(MAX_ROOMS * 2): # 충분한 시도를 위해 최대 방 개수의 2배만큼 반복
            if len(self.rooms) >= MAX_ROOMS: break
            
            w = random.randint(ROOM_MIN_SIZE, ROOM_MAX_SIZE)
            h = random.randint(ROOM_MIN_SIZE, ROOM_MAX_SIZE)
            x = random.randint(1, self.width - w - 2)
            y = random.randint(1, self.height - h - 2)

            new_room = Room(x, y, w, h, room_id=i)

            if not any(new_room.intersects(other_room) for other_room in self.rooms):
                self.rooms.append(new_room)
        
        for room in self.rooms:
            self._create_room(room)


    def _connect_all_rooms(self):
        """모든 방이 연결되도록 복도를 생성합니다."""
        if len(self.rooms) < 2:
            return

        connected_pairs = set()
        
        # 1. 모든 방이 최소 하나씩 연결되도록 보장 (최소 신장 트리)
        connected = [self.rooms[0]]
        unconnected = self.rooms[1:]
        while unconnected:
            room_to_connect = min(unconnected, key=lambda r: min(math.dist(r.center(), cr.center()) for cr in connected))
            nearest_connected_room = min(connected, key=lambda cr: math.dist(room_to_connect.center(), cr.center()))
            
            if self._connect_rooms(room_to_connect, nearest_connected_room):
                pair = tuple(sorted((room_to_connect.id, nearest_connected_room.id)))
                connected_pairs.add(pair)
            else:
                # 만약 주요 경로 연결에 실패하면, 다른 방과 연결 시도
                sorted_by_dist = sorted(connected, key=lambda cr: math.dist(room_to_connect.center(), cr.center()))
                for alt_room in sorted_by_dist[1:]: # 가장 가까운 방은 실패했으므로 그 다음부터
                    if self._connect_rooms(room_to_connect, alt_room):
                        pair = tuple(sorted((room_to_connect.id, alt_room.id)))
                        connected_pairs.add(pair)
                        break
            
            connected.append(room_to_connect)
            unconnected.remove(room_to_connect)

        # 2. 추가 연결 (순환로) 생성
        for room1 in self.rooms:
            if random.random() < ADDITIONAL_CONNECTION_CHANCE:
                possible_connections = sorted(
                    [r for r in self.rooms if r.id != room1.id],
                    key=lambda r: math.dist(room1.center(), r.center())
                )
                if possible_connections:
                    room2 = random.choice(possible_connections[:3]) 
                    pair = tuple(sorted((room1.id, room2.id)))
                    if pair not in connected_pairs:
                        if self._connect_rooms(room1, room2, with_door=False):
                            connected_pairs.add(pair)

    def _create_room(self, room: Room):
        """주어진 Room 객체의 영역을 바닥 타일로 채웁니다."""
        for y in range(room.y1 + 1, room.y2):
            for x in range(room.x1 + 1, room.x2):
                self.tiles[y][x] = Tile(False, False, terrain='floor')

    def _connect_rooms(self, room1, room2, with_door=True):
        """두 방을 잇는 유효한 경로를 찾아 복도를 생성합니다. 성공 시 True를 반환합니다."""
        start_data = self._find_border_point(room1, room2)
        end_data = self._find_border_point(room2, room1)

        if not start_data or not end_data:
            return False
        
        start_pos, start_wall = start_data
        end_pos, end_wall = end_data

        path = self._find_path_astar(start_pos, end_pos, room1, room2)

        if path:
            # A* 경로는 방 바깥에서 시작하므로, 연결 벽 지점을 경로에 추가합니다.
            final_path = [start_wall] + path + [end_wall]
            self._carve_path(final_path, with_door)
            
            # 복도 정보 생성 및 저장
            corridor_id = self._corridor_id_counter
            new_corridor = Corridor(corridor_id, room1.id, room2.id, path)
            self.corridors.append(new_corridor)
            self._corridor_id_counter += 1
            
            room1.connected_rooms.add(room2.id)
            room2.connected_rooms.add(room1.id)
            room1.connected_corridors.add(corridor_id)
            room2.connected_corridors.add(corridor_id)
            
            return True
        return False

    def _find_border_point(self, start_room, target_room):
        """방의 경계에서 복도를 시작할 지점과, 연결될 벽의 지점을 함께 찾습니다."""
        start_center = start_room.center()
        target_center = target_room.center()
        
        dx = target_center[0] - start_center[0]
        dy = target_center[1] - start_center[1]

        points_to_check = []
        
        # 주된 방향 결정 (x 또는 y)
        if abs(dx) > abs(dy): # 가로로 더 길면
            if dx > 0: # 오른쪽 벽
                points_to_check = [(start_room.x2, y) for y in range(start_room.y1 + 1, start_room.y2)]
            else: # 왼쪽 벽
                points_to_check = [(start_room.x1, y) for y in range(start_room.y1 + 1, start_room.y2)]
        else: # 세로로 더 길면
            if dy > 0: # 아래쪽 벽
                points_to_check = [(x, start_room.y2) for x in range(start_room.x1 + 1, start_room.x2)]
            else: # 위쪽 벽
                points_to_check = [(x, start_room.y1) for x in range(start_room.x1 + 1, start_room.x2)]
        
        random.shuffle(points_to_check)

        # 벽 바로 바깥의 유효한 지점 찾기
        for wall_point in points_to_check:
            if wall_point[0] == start_room.x1: corridor_start_point = (wall_point[0] - 1, wall_point[1])
            elif wall_point[0] == start_room.x2: corridor_start_point = (wall_point[0] + 1, wall_point[1])
            elif wall_point[1] == start_room.y1: corridor_start_point = (wall_point[0], wall_point[1] - 1)
            else: corridor_start_point = (wall_point[0], wall_point[1] + 1)

            if 0 < corridor_start_point[0] < self.width -1 and 0 < corridor_start_point[1] < self.height -1:
                if self.tiles[corridor_start_point[1]][corridor_start_point[0]].terrain == 'wall':
                    # 복도 시작점과 벽 지점을 모두 반환
                    return corridor_start_point, wall_point
        return None # 적합한 지점을 찾지 못함


    def _get_path_cost(self, x, y, start_room, end_room):
        """A* 알고리즘에서 사용할 특정 타일의 이동 비용을 계산합니다."""
        if not (0 <= x < self.width and 0 <= y < self.height):
            return float('inf') # 맵 밖은 무한대 비용

        # 경로가 다른 방의 안전지대(주변 8칸)를 침범하는지 확인
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                check_x, check_y = x + dx, y + dy
                if not (0 <= check_x < self.width and 0 <= check_y < self.height):
                    continue
                for room in self.rooms:
                    if room != start_room and room != end_room:
                        if room.contains_floor(check_x, check_y):
                            return 100.0 # 매우 높은 비용

        if self.tiles[y][x].terrain == 'floor':
            return 0.5 # 기존 복도 재활용 비용
        
        return 1.0 # 일반 벽 통과 비용


    def _find_path_astar(self, start, end, start_room, end_room):
        """A* 알고리즘으로 시작점에서 도착점까지의 최적 경로를 찾습니다."""
        open_set = []
        heapq.heappush(open_set, (0, start))
        
        came_from = {}
        g_score = {start: 0}
        f_score = {start: self._heuristic(start, end)}

        while open_set:
            _, current = heapq.heappop(open_set)

            if current == end:
                return self._reconstruct_path(came_from, current)

            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                neighbor = (current[0] + dx, current[1] + dy)

                if not (0 < neighbor[0] < self.width-1 and 0 < neighbor[1] < self.height-1):
                    continue

                cost = self._get_path_cost(neighbor[0], neighbor[1], start_room, end_room)
                tentative_g_score = g_score.get(current, float('inf')) + cost

                if tentative_g_score < g_score.get(neighbor, float('inf')):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g_score
                    f_score[neighbor] = tentative_g_score + self._heuristic(neighbor, end)
                    if neighbor not in [i[1] for i in open_set]:
                        heapq.heappush(open_set, (f_score[neighbor], neighbor))
        return None # 경로를 찾지 못함

    def _heuristic(self, a, b):
        """A* 알고리즘의 휴리스틱 함수 (맨해튼 거리)."""
        return abs(a[0] - b[0]) + abs(a[1] - b[1])
    
    def _reconstruct_path(self, came_from, current):
        """A* 알고리즘이 찾은 경로를 역추적하여 리스트로 만듭니다."""
        total_path = [current]
        while current in came_from:
            current = came_from[current]
            total_path.append(current)
        total_path.reverse()
        return total_path
        
    def _is_path_valid(self, path, start_room, end_room):
        # A* 알고리즘 도입으로 이 함수는 더 이상 사용되지 않거나 역할이 축소될 수 있습니다.
        # 비용 함수(_get_path_cost)가 유효성 검사를 대신합니다.
        return True

    def _carve_path(self, path, with_door=True):
        """주어진 좌표 리스트를 따라 복도를 생성합니다."""
        door_placed = False
        for i, (x,y) in enumerate(path):
            tile = self.tiles[y][x]
            if tile.terrain == 'wall':
                # 문은 복도의 끝자락(방과 만나는 지점)에만 생성되도록 함
                is_endpoint = (i < 3 or i > len(path) - 4)
                if with_door and not door_placed and is_endpoint and random.random() < DOOR_CHANCE_PER_ROOM and self._is_valid_door_location(x, y):
                    self.tiles[y][x] = Tile(True, True, terrain='door')
                    door_placed = True
                else:
                    self.tiles[y][x] = Tile(False, False, terrain='floor')

    def _is_valid_door_location(self, x, y):
        """해당 좌표가 문을 만들기에 적합한지(1타일 복도의 입구인지) 확인합니다."""
        if not (1 < x < self.width - 2 and 1 < y < self.height - 2):
            return False

        # 수평 복도 입구 조건
        h_neighbors = (self.tiles[y][x-1].terrain, self.tiles[y][x+1].terrain)
        is_h_corridor = ('floor' in h_neighbors and 'wall' in h_neighbors)
        if is_h_corridor and self.tiles[y-1][x].terrain == 'wall' and self.tiles[y+1][x].terrain == 'wall':
            return True
        
        # 수직 복도 입구 조건
        v_neighbors = (self.tiles[y-1][x].terrain, self.tiles[y+1][x].terrain)
        is_v_corridor = ('floor' in v_neighbors and 'wall' in v_neighbors)
        if is_v_corridor and self.tiles[y][x-1].terrain == 'wall' and self.tiles[y][x+1].terrain == 'wall':
            return True

        return False 