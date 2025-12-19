import pygame as pg
from src.scenes.scene import Scene
from src.core.services import scene_manager, input_manager
from src.interface.components import Button
from typing import override

class NavigationScene(Scene):

    def __init__(self, previous_scene: str):
        super().__init__()
        self.previous_scene = previous_scene

        self.font_label = pg.font.Font("assets/fonts/Minecraft.ttf", 14)


        # 半透明背景
        self.overlay = pg.Surface((1280, 720), pg.SRCALPHA)
        self.overlay.fill((0, 0, 0, 160))

        # 背景圖
        self.window_img = pg.image.load(
            "assets/images/backgrounds/setting.png"
        ).convert_alpha()
        self.window_rect = self.window_img.get_rect(center=(640, 360))

        # X 關閉按鈕
        px = self.window_rect.right
        py = self.window_rect.top
        self.x_button = Button(
            "UI/button_x.png",
            "UI/button_x_hover.png",
            px - 60,
            py + 20,
            32,
            32,
            lambda: scene_manager.change_scene(self.previous_scene)
        )
        btn_w, btn_h = 48, 48
        btn_gap = 20

        # 視窗內 padding（控制按鈕位置）
        pad_x = 30
        pad_y = 40
        # 視窗左上角為基準
        base_x = self.window_rect.left + pad_x
        base_y = self.window_rect.top + pad_y

        self.nav_start_button = Button(
            "UI/button_nav_to.png",
            "UI/button_nav_to_hover.png",
            base_x,
            base_y,
            btn_w,
            btn_h,
            lambda: scene_manager._scenes["game"].go_to("Start")
        )

        self.nav_gym_button = Button(
            "UI/button_nav_to.png",
            "UI/button_nav_to_hover.png",
            base_x + btn_w + btn_gap,
            base_y,
            btn_w,
            btn_h,
            lambda: scene_manager._scenes["game"].go_to("Gym")
        )

        self.nav_start_pos = (base_x, base_y)
        self.nav_gym_pos = (base_x + btn_w + btn_gap, base_y)

        self.btn_w = btn_w
        self.btn_h = btn_h


    @override
    def enter(self) -> None:
        # 擷取目前畫面當背景
        screen = pg.display.get_surface()
        self.background_capture = screen.copy()

    @override
    def update(self, dt: float):
        # ESC 關閉
        if input_manager.key_down(pg.K_ESCAPE):
            scene_manager.change_scene(self.previous_scene)
            return

        self.x_button.update(dt)
        self.nav_start_button.update(dt)
        self.nav_gym_button.update(dt)

    @override
    def draw(self, screen: pg.Surface):
        # 原畫面
        screen.blit(self.background_capture, (0, 0))

        # 半透明遮罩
        screen.blit(self.overlay, (0, 0))

        # 中央視窗（背景）
        screen.blit(self.window_img, self.window_rect)

        # 按鈕
        self.x_button.draw(screen)
        self.nav_start_button.draw(screen)
        self.nav_gym_button.draw(screen)

        # 文字標籤
        start_txt = self.font_label.render("Start", True, (255, 255, 255))
        gym_txt   = self.font_label.render("Gym",   True, (255, 255, 255))

        # Start 文字（置中在第一顆下面）
        sx, sy = self.nav_start_pos
        gx, gy = self.nav_gym_pos

        # Start 文字
        screen.blit(
            start_txt,
            (
                sx + self.btn_w // 2 - start_txt.get_width() // 2,
                sy + self.btn_h + 6
            )
        )

        # Gym 文字
        screen.blit(
            gym_txt,
            (
                gx + self.btn_w // 2 - gym_txt.get_width() // 2,
                gy + self.btn_h + 6
            )
        )
