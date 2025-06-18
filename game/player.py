from dataclasses import dataclass

@dataclass
class Player:
    """플레이어의 상태를 저장하는 클래스"""
    x: int
    y: int 