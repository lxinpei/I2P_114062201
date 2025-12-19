import pygame as pg
import math
from src.utils import Position, GameSettings

class BushInteraction:
    def __init__(self, bush_rect: pg.Rect, player):
        self.rect = bush_rect   # 草叢範圍（世界座標）
        self.player = player
        self.near = False

    def update(self):
        # px = self.player.position.x
        # py = self.player.position.y
        # # 這邊用玩家的 position 和 bush_rect 碰撞檢查
        # '''if self.rect.collidepoint(px, py):
        #     self.near = True
        # else:
        #     self.near = False'''
        # player_rect = pg.Rect(px, py, GameSettings.TILE_SIZE, GameSettings.TILE_SIZE)

        # self.near = player_rect.colliderect(self.rect)
        size = GameSettings.TILE_SIZE

        # 玩家世界座標 rect
        player_rect = pg.Rect(
            self.player.position.x,
            self.player.position.y,
            size,
            size
        )

        # 只要站在草叢上（有重疊）就觸發
        self.near = player_rect.colliderect(self.rect)

    def draw(self, screen: pg.Surface, camera):
        pass