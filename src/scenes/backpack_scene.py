import pygame as pg
from src.scenes.scene import Scene
from src.core.services import sound_manager, scene_manager, input_manager
from src.sprites import Sprite
from src.interface.components import Button
from typing import override

class BackpackScene(Scene):

    def __init__(self):
        super().__init__()

        self.font_title = pg.font.Font("assets/fonts/Minecraft.ttf", 32)
        self.font_label = pg.font.Font("assets/fonts/Minecraft.ttf", 18)
        self.font_small = pg.font.Font("assets/fonts/Minecraft.ttf", 16)

        # self.img_potion = pg.transform.scale(
        #     pg.image.load("assets/images/ingame_ui/potion.png").convert_alpha(),
        #     (30, 30)
        # )
        self.img_heal_potion = pg.transform.scale(
            pg.image.load("assets/images/ingame_ui/heal_potion.png").convert_alpha(),
            (30, 30)
        )
        self.img_strength_potion = pg.transform.scale(
            pg.image.load("assets/images/ingame_ui/strength_potion.png").convert_alpha(),
            (30, 30)
        )
        self.img_defense_potion = pg.transform.scale(
            pg.image.load("assets/images/ingame_ui/defense_potion.png").convert_alpha(),
            (30, 30)
        )
        self.img_coin = pg.transform.scale(
            pg.image.load("assets/images/ingame_ui/coin.png").convert_alpha(),
            (30, 30)
        )
        self.img_pokeball = pg.transform.scale(
            pg.image.load("assets/images/ingame_ui/ball.png").convert_alpha(),
            (30, 30)
        )

        self.img_pokemon = pg.transform.scale(
            pg.image.load("assets/images/menu_sprites/menusprite2.png").convert_alpha(),
            (60, 60)
        )

        # 半透明背景
        self.overlay = pg.Surface(
            (1280, 720), pg.SRCALPHA
        )  # 根據遊戲的實際 resolution 調整
        self.overlay.fill((0, 0, 0, 160))

        # UI 主視窗
        self.window_img = pg.image.load("assets/images/backgrounds/backpack.png").convert_alpha()
        self.window_img = pg.transform.scale(self.window_img, (700, 480))
        self.window_rect = self.window_img.get_rect(center=(640, 360))

        # Back 按鈕
        px = self.window_rect.right
        py = self.window_rect.top
        self.btn_x = Button(
            "UI/button_x.png", "UI/button_x_hover.png",
            px - 60, py  + 35, 32, 32,
            lambda: scene_manager.change_scene("game")
        )
        # 箭頭區域設定
        self.arrow_up_rect = None
        self.arrow_down_rect = None

        self.scroll_offset = 0
        self.max_scroll = 0
        # Scrollbar 設定
        self.scroll_offset = 0
        self.max_scroll = 0
        arrow_x = self.window_rect.left + 40 + 360 - 10
        arrow_top = self.window_rect.top + 90
        arrow_bottom = arrow_top + 360

        self.btn_up = Button(
            "UI/button_up.png",
            "UI/button_up_hover.png",
            arrow_x,
            arrow_top,
            30,
            30,
            self.scroll_up
        )

        self.btn_down = Button(
            "UI/button_down.png",
            "UI/button_down_hover.png",
            arrow_x,
            arrow_bottom - 60,
            30,
            30,
            self.scroll_down
        )
        self.VISIBLE_ROWS = 3
        self.scroll_index = 0

        
        

    @override
    def enter(self) -> None:
        print("[SettingsScene] Enter")
        screen = pg.display.get_surface()
        self.background_capture = screen.copy()
        # 預載圖片
        self.cached_mon_images = {}
        self.cached_item_images = {}

        game_scene = scene_manager._scenes["game"]
        bag = game_scene.game_manager.bag

        # 預載怪獸圖片
        for mon in bag.monsters:
            path = mon["sprite_path"]
            if path not in self.cached_mon_images:
                img = pg.image.load(path).convert_alpha()
                img = pg.transform.scale(img, (60, 60))
                self.cached_mon_images[path] = img

        # 預載道具圖片
        for item in bag.items:
            full_path = "assets/images/" + item["sprite_path"]
            if full_path not in self.cached_item_images:
                img = pg.image.load(full_path).convert_alpha()
                img = pg.transform.scale(img, (30, 30))
                self.cached_item_images[full_path] = img


    @override
    def exit(self) -> None:
        print("[SettingsScene] Exit")

    @override
    def update(self, dt: float):
        # 先算 max_scroll一定要在點擊前
        game_scene = scene_manager._scenes["game"]
        bag = game_scene.game_manager.bag
        gap_y = 110
        self.max_scroll = max(0, len(bag.monsters) * gap_y - 350)
        if input_manager.key_pressed(pg.K_ESCAPE):
            scene_manager.change_scene("game")
            return

        self.btn_x.update(dt)
        self.btn_up.update(dt)
        self.btn_down.update(dt)

    


    @override
    def draw(self, screen: pg.Surface):
        VISIBLE_ROWS = 3
        BOX_H = 95
        # 先畫剛剛截到的 GameScene
        screen.blit(self.background_capture, (0, 0))

        # 半透明覆蓋
        screen.blit(self.overlay, (0, 0))
        
        # 視窗
        screen.blit(self.window_img, self.window_rect)

        # BAG 標題
        title = self.font_title.render("BAG", True, (255, 255, 255))
        screen.blit(title, (self.window_rect.left + 35, self.window_rect.top + 30))
        
        self.btn_x.draw(screen)

        # 製作裁切區域（怪物清單可見範圍
        clip_rect = pg.Rect(
            self.window_rect.left + 40,
            self.window_rect.top + 80,
            360,     # 左側怪物清單寬度
            360      # 高度
        )
        screen.set_clip(clip_rect)

        # 頭像
        game_scene = scene_manager._scenes["game"]
        bag = game_scene.game_manager.bag

        list_x = self.window_rect.left + 50
        list_y = self.window_rect.top + 90 + self.scroll_offset
        gap_y  = 110

        start_index = self.scroll_index
        end_index = min(start_index + VISIBLE_ROWS, len(bag.monsters))

        self.max_scroll = max(
            0,
            (len(bag.monsters) - VISIBLE_ROWS) * gap_y
        )

        for row, i in enumerate(range(start_index, end_index)):
            mon = bag.monsters[i]

            box_x = list_x
            box_y = self.window_rect.top + 90 + row * gap_y
            box_w = 330
            box_h = BOX_H

            pg.draw.rect(screen, (255,255,255), (box_x, box_y, box_w, box_h))
            pg.draw.rect(screen, (0,0,0), (box_x, box_y, box_w, box_h), 3)

            sprite = self.cached_mon_images[mon["sprite_path"]]
            screen.blit(sprite, (box_x + 10, box_y + 15))

            name_txt = self.font_label.render(mon["name"], True, (0, 0, 0))
            screen.blit(name_txt, (box_x + 80, box_y + 12))

            level = mon.get("level", 5)
            lvl_txt = self.font_small.render(f"Lv {level}", True, (0, 0, 0))
            screen.blit(lvl_txt, (box_x + box_w - 55, box_y + 12))

            bar_x = box_x + 80
            bar_y = box_y + 45
            bar_w = 200
            bar_h = 10

            current = mon["hp"]
            max_hp = mon["max_hp"]
            hp_ratio = current / max_hp

            pg.draw.rect(screen, (0, 200, 0), (bar_x, bar_y, int(bar_w * hp_ratio), bar_h))

            hp_txt = self.font_small.render(f"{current} / {max_hp}", True, (0, 0, 0))
            screen.blit(hp_txt, (bar_x, bar_y + 12))

        # 取消裁切
        screen.set_clip(None)

        # 右邊：道具列表
        item_x = self.window_rect.left + 420
        item_y = self.window_rect.top + 100

        items = bag.items
        y = item_y

        for item in items:
            # 圖片
            icon = self.cached_item_images["assets/images/" + item["sprite_path"]]

            screen.blit(icon, (item_x, y))

            # 名稱
            name_txt = self.font_label.render(item["name"], True, (0, 0, 0))
            screen.blit(name_txt, (item_x + 50, y + 3))

            # 數量
            num_txt = self.font_small.render(f"x{item['count']}", True, (0, 0, 0))
            num_rect = num_txt.get_rect()
            num_rect.topright = (self.window_rect.right - 60, y + 5)
            screen.blit(num_txt, num_rect)

            y += 70

        self.btn_up.draw(screen)
        self.btn_down.draw(screen)
    
            
    def scroll_up(self):
        self.scroll_index = max(0, self.scroll_index - 1)

    def scroll_down(self):
        game_scene = scene_manager._scenes["game"]
        bag = game_scene.game_manager.bag

        max_start = max(0, len(bag.monsters) - self.VISIBLE_ROWS)
        self.scroll_index = min(max_start, self.scroll_index + 1)