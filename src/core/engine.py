import pygame as pg

from src.utils import GameSettings, Logger
from .services import scene_manager, input_manager

from src.scenes.menu_scene import MenuScene
from src.scenes.game_scene import GameScene
from src.scenes.setting_scene import SettingsScene
from src.scenes.battle_scene import BattleScene
from src.scenes.backpack_scene import BackpackScene
from src.scenes.catch_scene import CatchScene
from src.scenes.shop_scene import ShopScene
from src.scenes.navigation_scene import NavigationScene


class Engine:

    screen: pg.Surface              # Screen Display of the Game
    clock: pg.time.Clock            # Clock for FPS control
    running: bool                   # Running state of the game

    def __init__(self):
        Logger.info("Initializing Engine")

        pg.init()

        self.screen = pg.display.set_mode((GameSettings.SCREEN_WIDTH, GameSettings.SCREEN_HEIGHT))
        self.clock = pg.time.Clock()
        self.running = True

        pg.display.set_caption(GameSettings.TITLE)

        scene_manager.register_scene("menu", MenuScene())
        scene_manager.register_scene("game", GameScene())
        scene_manager.register_scene("backpack", BackpackScene())

        scene_manager.register_scene("battle", BattleScene())
        scene_manager.register_scene("catch", CatchScene())
        scene_manager.register_scene("shop", ShopScene(None))
        scene_manager.register_scene("navigation", NavigationScene("game"))




        '''
        [TODO HACKATHON 5]
        Register the setting scene here
        '''
        scene_manager.register_scene("setting_from_menu", SettingsScene("menu"))
        scene_manager.register_scene("setting_from_game", SettingsScene("game"))
        scene_manager.change_scene("menu")

    def run(self):
        Logger.info("Running the Game Loop ...")

        while self.running:
            dt = self.clock.tick(GameSettings.FPS) / 1000.0
            self.handle_events()
            self.update(dt)
            self.render()

    def handle_events(self):
        input_manager.reset()
        for event in pg.event.get():
            if event.type == pg.QUIT:
                self.running = False
            # 1) 更新輸入狀態（輪詢用）
            input_manager.handle_events(event)

            # 2) 把事件交給目前 scene（UI/按鈕通常需要這個）
            scene_manager.handle_events(event)   # ✅ 你需要在 scene_manager 實作
            for event in pg.event.get():
                if event.type == pg.QUIT:
                    self.running = False
                input_manager.handle_events(event)
        
        
            

    def update(self, dt: float):
        scene_manager.update(dt)

    def render(self):
        self.screen.fill((0, 0, 0))     # Make sure the display is cleared
        scene_manager.draw(self.screen) # Draw the current scene
        pg.display.flip()               # Render the display
