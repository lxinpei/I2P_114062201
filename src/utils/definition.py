from pygame import Rect
from .settings import GameSettings
from dataclasses import dataclass
from enum import Enum
from typing import overload, TypedDict, Protocol

MouseBtn = int
Key = int

Direction = Enum('Direction', ['UP', 'DOWN', 'LEFT', 'RIGHT', 'NONE'])

@dataclass
class Position:
    x: float
    y: float
    
    def copy(self):
        return Position(self.x, self.y)
        
    def distance_to(self, other: "Position") -> float:
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5
        
@dataclass
class PositionCamera:
    x: int
    y: int
    
    def copy(self):
        return PositionCamera(self.x, self.y)
        
    def to_tuple(self) -> tuple[int, int]:
        return (self.x, self.y)
        
    def transform_position(self, position: Position) -> tuple[int, int]:
        return (int(position.x) - self.x, int(position.y) - self.y)
        
    def transform_position_as_position(self, position: Position) -> Position:
        return Position(int(position.x) - self.x, int(position.y) - self.y)
        
    def transform_rect(self, rect: Rect) -> Rect:
        return Rect(rect.x - self.x, rect.y - self.y, rect.width, rect.height)

@dataclass
class Teleport:
    pos: Position
    destination: str
    dest_pos: Position | None = None

    
    @overload
    def __init__(self, x: int, y: int, destination: str) -> None: ...
    @overload
    def __init__(self, pos: Position, destination: str) -> None: ...

    def __init__(self, *args, **kwargs):
        kw_dest_x = kwargs.get("dest_x", None)
        kw_dest_y = kwargs.get("dest_y", None)

        if len(args) >= 2 and isinstance(args[0], Position):
            self.pos = args[0]
            self.destination = args[1]
            self.dest_pos = args[2] if len(args) >= 3 else None
        else:
            x, y, dest = args[0], args[1], args[2]
            self.pos = Position(x, y)
            self.destination = dest

            if len(args) >= 5:
                dx, dy = args[3], args[4]
                self.dest_pos = Position(dx, dy)
            elif kw_dest_x is not None and kw_dest_y is not None:
                self.dest_pos = Position(kw_dest_x, kw_dest_y)
            else:
                self.dest_pos = None
    
    def to_dict(self):
        d = {
            "x": self.pos.x // GameSettings.TILE_SIZE,
            "y": self.pos.y // GameSettings.TILE_SIZE,
            "destination": self.destination
        }
        if self.dest_pos is not None:
            d["dest_x"] = self.dest_pos.x // GameSettings.TILE_SIZE
            d["dest_y"] = self.dest_pos.y // GameSettings.TILE_SIZE
        return d

    
    @classmethod
    def from_dict(cls, data: dict):
        x = data["x"] * GameSettings.TILE_SIZE
        y = data["y"] * GameSettings.TILE_SIZE
        dest = data["destination"]

        if "dest_x" in data and "dest_y" in data:
            dx = data["dest_x"] * GameSettings.TILE_SIZE
            dy = data["dest_y"] * GameSettings.TILE_SIZE
            return cls(x, y, dest, dx, dy)

        return cls(x, y, dest)
    
class Monster(TypedDict):
    name: str
    hp: int
    max_hp: int
    level: int
    sprite_path: str

    element: str
    atk: int
    def_: int  # type hint only; JSON key can still be "def"
    evolve_level: int
    evolve_to_sprite_path: str

class Item(TypedDict):
    name: str
    count: int
    sprite_path: str