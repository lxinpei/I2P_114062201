from __future__ import annotations
import pygame as pg
from .entity import Entity
from src.core.services import input_manager
from src.utils import Position, PositionCamera, GameSettings, Logger
from src.core import GameManager
import math
from typing import override
from src.utils import Direction

class Player(Entity):
    speed: float = 4.0 * GameSettings.TILE_SIZE
    game_manager: GameManager

    def __init__(self, x: float, y: float, game_manager: GameManager) -> None:
        super().__init__(x, y, game_manager)
        self.direction = Direction.DOWN

    def _find_nearest_free_tile(self):
        """If dest tile is blocked, find nearest free tile to avoid getting stuck."""
        tile = GameSettings.TILE_SIZE
        w, h = self.animation.rect.width, self.animation.rect.height
        offsets = [(0, 0), (0, tile), (0, -tile), (tile, 0), (-tile, 0),
                   (tile, tile), (-tile, tile), (tile, -tile), (-tile, -tile),
                   (0, 2*tile), (0, -2*tile), (2*tile, 0), (-2*tile, 0)]
        for dx, dy in offsets:
            test_x = self._snap_to_grid(self.position.x + dx)
            test_y = self._snap_to_grid(self.position.y + dy)
            rect = pg.Rect(int(test_x), int(test_y), w, h)
            if (not self.game_manager.check_collision(rect)) and (not rect.colliderect(self.game_manager.npc_collision_rect)):
                self.position.x = test_x
                self.position.y = test_y
                return

    @override
    def update(self, dt: float) -> None:
        dis = Position(0, 0)
        '''
        [TODO HACKATHON 2]
        Calculate the distance change, and then normalize the distance
        
        [TODO HACKATHON 4]
        Check if there is collision, if so try to make the movement smooth
        Hint #1 : use entity.py _snap_to_grid function or create a similar function
        Hint #2 : Beware of glitchy teleportation, you must do
                    1. Update X
                    2. If collide, snap to grid
                    3. Update Y
                    4. If collide, snap to grid
                  instead of update both x, y, then snap to grid
        '''
        
        if input_manager.key_down(pg.K_LEFT) or input_manager.key_down(pg.K_a):
            dis.x -= 1
            self.direction = Direction.LEFT
            self.animation.switch("left")
        if input_manager.key_down(pg.K_RIGHT) or input_manager.key_down(pg.K_d):
            dis.x += 1
            self.direction = Direction.RIGHT
            self.animation.switch("right")
        if input_manager.key_down(pg.K_UP) or input_manager.key_down(pg.K_w):
            dis.y -= 1
            self.direction = Direction.UP
            self.animation.switch("up")
        if input_manager.key_down(pg.K_DOWN) or input_manager.key_down(pg.K_s):
            dis.y += 1
            self.direction = Direction.DOWN
            self.animation.switch("down")
        
        '''self.position = ...'''
        length = math.sqrt(dis.x ** 2 + dis.y ** 2)
        if length != 0:
            dis.x /= length
            dis.y /= length

        dis.x *= self.speed * dt
        dis.y *= self.speed * dt

        npc_rect = getattr(self.game_manager, "npc_collision_rect", None)
        if not isinstance(npc_rect, pg.Rect):
            npc_rect = pg.Rect(0, 0, 0, 0)

        new_x = self.position.x + dis.x
        player_rect = pg.Rect(int(new_x), int(self.position.y), self.animation.rect.width, self.animation.rect.height)
        if not self.game_manager.check_collision(player_rect) and not player_rect.colliderect(self.game_manager.npc_collision_rect):
            self.position.x = new_x 
        else:
            self.position.x = self._snap_to_grid(self.position.x)
            

        new_y = self.position.y + dis.y
        player_rect = pg.Rect(int(self.position.x) , int(new_y) ,self.animation.rect.width, self.animation.rect.height)
        if not self.game_manager.check_collision(player_rect) and not player_rect.colliderect(self.game_manager.npc_collision_rect):
            self.position.y = new_y
        else:
            self.position.y = self._snap_to_grid(self.position.y)
        
        
        # Teleportation (ONLY here)
        # Use game_manager.teleport_cooldown to avoid double-trigger / instant bounce
        if not hasattr(self.game_manager, "teleport_cooldown"):
            self.game_manager.teleport_cooldown = 0.0

        if self.game_manager.teleport_cooldown <= 0:
            tp = self.game_manager.current_map.check_teleport(self.position)
            if tp:
                self.game_manager.teleport_cooldown = 0.6  # 先用大一點，穩定後再調回 0.35

                print("[TP] before switch:", self.game_manager.current_map.path_name, "->", tp.destination)

                # 告訴 game_manager 要切去哪
                self.game_manager.switch_map(tp.destination)

                # 真正執行切圖
                self.game_manager.try_switch_map()

                print("[TP] after switch:", self.game_manager.current_map.path_name)

                # 落點（dest_pos 或 spawn）
                if getattr(tp, "dest_pos", None) is not None:
                    self.position = tp.dest_pos.copy()
                else:
                    self.position = self.game_manager.current_map.spawn.copy()

                # snap
                self.position.x = self._snap_to_grid(self.position.x)
                self.position.y = self._snap_to_grid(self.position.y)

                super().update(dt)
                return

                
        super().update(dt)
        # print(
        #     "Player tile:",
        #     int(self.position.x // GameSettings.TILE_SIZE),
        #     int(self.position.y // GameSettings.TILE_SIZE)
        # )


    @override
    def draw(self, screen: pg.Surface, camera: PositionCamera) -> None:
        super().draw(screen, camera)
        
    @override
    def to_dict(self) -> dict[str, object]:
        return super().to_dict()
    
    @classmethod
    @override
    def from_dict(cls, data: dict[str, object], game_manager: GameManager) -> Player:
        return cls(data["x"] * GameSettings.TILE_SIZE, data["y"] * GameSettings.TILE_SIZE, game_manager)

