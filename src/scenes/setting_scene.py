import pygame as pg
from src.scenes.scene import Scene
from src.core.services import sound_manager, scene_manager, input_manager
from src.core.managers.game_manager import GameManager
from src.sprites import Sprite
from src.interface.components import Button
from typing import override

class SettingsScene(Scene):

    def __init__(self, previous_scene:str):
        super().__init__()

        self.font_title = pg.font.Font("assets/fonts/Minecraft.ttf", 32)
        self.font_label = pg.font.Font("assets/fonts/Minecraft.ttf", 24)
        self.font_small = pg.font.Font("assets/fonts/Minecraft.ttf", 18)
        self.previous_scene = previous_scene

        # 半透明背景
        self.overlay = pg.Surface(
            (1280, 720), pg.SRCALPHA
        )  # 根據遊戲的實際 resolution 調整
        self.overlay.fill((0, 0, 0, 160))

        # UI 主視窗
        self.window_img = pg.image.load("assets/images/backgrounds/setting.png").convert_alpha()
        self.window_rect = self.window_img.get_rect(center=(640, 360))

        # Back 按鈕
        px = self.window_rect.right
        py = self.window_rect.top
        self.x_button = Button(
            "UI/button_x.png", "UI/button_x_hover.png",
            px - 60, py  + 20, 32, 32,
            lambda: scene_manager.change_scene(self.previous_scene)
        )
        self.back_button = Button(
            "UI/button_back.png", "UI/button_back_hover.png",
            px - 380, py  + 200, 40, 40,
            lambda: scene_manager.change_scene("menu")
        )
        # Mute 按鈕
        self.muted = False
        self.mute_off = "UI/mute_off.png"
        self.mute_on = "UI/mute_on.png"
        self.mute_button = Button(
            self.mute_off, self.mute_off,
            px - 325, py  + 160, 48, 24,
            on_click=self.toggle_mute
        )
        self.save_button = Button(
            "UI/button_save.png", "UI/button_save_hover.png",
            px - 480, py + 200, 40, 40,
            on_click=lambda: self.save_game()
        )
        self.load_button = Button(
            "UI/button_load.png", "UI/button_load_hover.png",
            px - 430, py + 200, 40, 40,
            on_click=lambda: self.load_game()
        )
        

        # 音量條
        self.slider_width = 400
        self.slider_height = 24
        self.volume = sound_manager.get_bgm_volume()

        self.slider_bar_rect = pg.Rect(
            self.window_rect.left + 35,
            self.window_rect.top + 120,
            self.slider_width,
            self.slider_height
        )
        self.knob_img = pg.image.load(
            "assets/images/UI/slider_knob.png"
        ).convert_alpha()
        self.knob_img = pg.transform.scale(self.knob_img, (24, 24))
        self.knob_rect = self.knob_img.get_rect(
            center=(
                self.slider_bar_rect.left + int(self.volume * self.slider_width),
                self.slider_bar_rect.centery
            )
        )
        
        # 現在音量
        self.volume = sound_manager.get_bgm_volume()
        self.slider_dragging = False

        self._mouse_prev = False
    
    def toggle_mute(self):
        self.muted = not self.muted

        if self.muted:
            sound_manager.set_bgm_volume(0)
            new_sprite = Sprite(self.mute_on, (48, 24))
        else:
            sound_manager.set_bgm_volume(self.volume)
            new_sprite = Sprite(self.mute_off, (48, 24))

        # mute button 圖片
        self.mute_button.img_button_default = new_sprite
        self.mute_button.img_button_hover = new_sprite
        self.mute_button.img_button = new_sprite

    def save_game(self):
        print("[SETTING] Saving game...")

        # 目前遊戲場景
        game_scene = scene_manager._scenes.get("game")

        if game_scene:
            game_scene.game_manager.save("saves/game0.json")
            print("[SETTING] Save complete")
        else:
            print("[SETTING] ERROR: Cannot find game scene to save!")


    def load_game(self):
        print("[SETTING] Loading game...")

        game_scene = scene_manager._scenes.get("game")
        if not game_scene:
            print("[SETTING] ERROR: Cannot find GameScene")
            return

        new_manager = GameManager.load("saves/game0.json")
        if new_manager is None:
            print("[SETTING] ERROR: Failed to load save file!")
            return

        game_scene.game_manager = new_manager

        # 重新綁 Camera
        player = new_manager.player
        player.camera.target = player

        # 重新初始化 GameScene（NPC、按鈕、敵人 ...)
        game_scene.enter()

        print("[SETTING] Load complete")

    @override
    def enter(self) -> None:
        print("[SettingsScene] Enter")
        screen = pg.display.get_surface()
        self.background_capture = screen.copy()

    @override
    def exit(self) -> None:
        print("[SettingsScene] Exit")

    @override
    def update(self, dt: float):
        if input_manager.key_down(pg.K_ESCAPE):
            scene_manager.change_scene(self.previous_scene)
            return

        mouse_left, _, _ = pg.mouse.get_pressed()
        mx, my = pg.mouse.get_pos()
        # 防止重複觸發
        if not hasattr(self, "prev_mouse"):
            self.prev_mouse = False


        self.x_button.update(dt)
        self.back_button.update(dt)
        self.mute_button.update(dt)
        self.save_button.update(dt)
        self.load_button.update(dt)

        # Slider 拖曳
        knob_rect = self.knob_rect

        if mouse_left and not self._mouse_prev:
            if knob_rect.collidepoint(mx, my):
                self.slider_dragging = True

        if self.slider_dragging and mouse_left:
            new_x = max(self.slider_bar_rect.left,
                        min(mx, self.slider_bar_rect.right))
            self.knob_rect.centerx = new_x

            self.volume = (new_x - self.slider_bar_rect.left) / self.slider_bar_rect.width
            if not self.muted:
                sound_manager.set_bgm_volume(self.volume)

        if not mouse_left:
            self.slider_dragging = False

        self._mouse_prev = mouse_left


    @override
    def draw(self, screen: pg.Surface):
        # 半透明背景
        # 先畫剛剛截到的 GameScene
        screen.blit(self.background_capture, (0, 0))

        # 半透明覆蓋
        screen.blit(self.overlay, (0, 0))
        
        # 視窗
        screen.blit(self.window_img, self.window_rect)

        # SETTINGS 標題
        title = self.font_title.render("SETTINGS", True, (255, 255, 255))
        screen.blit(title, (self.window_rect.left + 35, self.window_rect.top + 32))
        
        # Volume 文字
        txt = self.font_label.render(f"Volume: {int(self.volume * 100)}%", True, (0, 0, 0))
        screen.blit(txt, (self.window_rect.left + 35, self.window_rect.top + 80))
        
        # SLIDER
        pg.draw.rect(screen, (220, 220, 220), self.slider_bar_rect, border_radius=3)
        self.knob_rect.centery = self.slider_bar_rect.centery
        screen.blit(self.knob_img, self.knob_rect)

        # Mute文字
        mute_txt = self.font_label.render("Mute:", True, (0, 0, 0))
        screen.blit(mute_txt, (self.window_rect.left + 35, self.window_rect.top + 160))
        # MUTE 按鈕-
        self.mute_button.draw(screen)
        #MUTE on/off
        mute_state = "On" if self.muted else "Off"
        mute_state_txt = self.font_label.render(f"{mute_state}", True, (0, 0, 0))
        screen.blit(mute_state_txt, (self.window_rect.left + 115, self.window_rect.top + 160))

        # BACK 按鈕
        self.x_button.draw(screen)
        self.back_button.draw(screen)

        # SAVE BUTTON
        self.save_button.draw(screen)

        # LOAD BUTTON
        self.load_button.draw(screen)

        # ESC
        esc_txt = self.font_small.render("Press ESC to close", True, (0, 0, 0))
        screen.blit(esc_txt, (self.window_rect.left + 35, self.window_rect.bottom - 60))