import pygame as pg
from src.scenes.scene import Scene
from src.core.services import scene_manager
import random
import copy

class CatchScene(Scene):
    

    def __init__(self):
        super().__init__()
        self.font = pg.font.Font("assets/fonts/Minecraft.ttf", 36)

        # 隨機生成一隻野生怪物
        self.wild_pool = [
            {
                "name": "Leafy",
                "hp": 30,
                "max_hp": 30,
                "level": 5,
                "sprite_path": "assets/images/menu_sprites/menusprite3.png",
                "evolve_level": 6,
                "evolve_to_sprite_path": "assets/images/menu_sprites/sprite3.png"
            },
            {
                "name": "Sparky",
                "hp": 25,
                "max_hp": 25,
                "level": 4,
                "sprite_path": "assets/images/menu_sprites/menusprite1.png",
                "evolve_level": 5,
                "evolve_to_sprite_path": "assets/images/menu_sprites/menusprite2.png"
            },
            {
                "name": "Rocko",
                "hp": 40,
                "max_hp": 40,
                "level": 6,
                "sprite_path": "assets/images/menu_sprites/menusprite2.png",
                "evolve_level": 7,
                "evolve_to_sprite_path": "assets/images/menu_sprites/menusprite3.png"
            }
        ]
        self.mon = None
        self.sprite = None

    def enter(self):
        print("Entering catch scene")
        # 每次進入時重新生成怪物
        base = random.choice(self.wild_pool).copy()
        base["hp"] = base["max_hp"]
        base["level"] = random.randint(2, 10)

        self.mon = base

        self.sprite = pg.transform.scale(
            pg.image.load(self.mon["sprite_path"]).convert_alpha(),
            (180, 180)
        )

    def update(self, dt):
        keys = pg.key.get_pressed()

        # 按 C 抓怪物
        if keys[pg.K_c]:

            # 加到背包
            game_scene = scene_manager._scenes["game"]
            game_scene.game_manager.bag._monsters_data.append(copy.deepcopy(self.mon))
            print("Caught:", self.mon)

            # 回到地圖
            scene_manager.change_scene("game")

    def draw(self, screen):
        screen.fill((0, 0, 0))

        # 顯示怪物
        screen.blit(self.sprite, (550, 180))

        # 顯示文字
        msg = self.font.render("Press C to catch!", True, (255, 255, 255))
        screen.blit(msg, (480, 500))

