import pygame as pg
from src.scenes.scene import Scene
from src.utils import GameSettings
from src.core.services import scene_manager
from src.interface.components import Button

class ColorButton:
    def __init__(self, x, y, w, h, callback):
        self.rect = pg.Rect(x, y, w, h)
        self.callback = callback

    def update(self, dt):
        if pg.mouse.get_pressed()[0]:  # 左鍵按下
            mx, my = pg.mouse.get_pos()
            if self.rect.collidepoint(mx, my):
                self.callback()

    def draw(self, screen, color=(255,255,255)):
        pg.draw.rect(screen, color, self.rect)  # 實心白色按鈕
        pg.draw.rect(screen, (0,0,0), self.rect, 2)  # 黑框

class ShopScene(Scene):
    def __init__(self, game_manager):
        super().__init__()
        self.game_manager = game_manager

        self.captured = False

        # 截取背景（GameScene 畫面）
        screen = pg.display.get_surface()
        self.background_capture = screen.copy()

        # Buy / Sell tab
        self.mode = "buy"   # or "sell"

        # 商品列表
        self.items_for_sale = [
            {"name": "Heal Potion", "price": 5,  "icon": "assets/images/ingame_ui/heal_potion.png"},
            {"name": "Strength Potion", "price": 10,  "icon": "assets/images/ingame_ui/strength_potion.png"},
            {"name": "Defense Potion", "price": 15,  "icon": "assets/images/ingame_ui/defense_potion.png"},
            {"name": "Pokeball", "price": 10, "icon": "assets/images/ingame_ui/ball.png"}
        ]

        self.selected = 0

        # 字體
        self.font = pg.font.SysFont("Arial", 22)

        self.cart_buttons = []   # ← 購物車按鈕列表

        # 半透明背景
        self.overlay = pg.Surface(
            (1280, 720), pg.SRCALPHA
        )  # 根據遊戲的實際 resolution 調整
        self.overlay.fill((0, 0, 0, 160))

        # 視窗圖片 or 顏色替代
        WINDOW_W = 600
        WINDOW_H = 400
        self.window_w = WINDOW_W
        self.window_h = WINDOW_H

        # 自動置中
        center_x = (GameSettings.SCREEN_WIDTH - WINDOW_W) // 2
        center_y = (GameSettings.SCREEN_HEIGHT - WINDOW_H) // 2

        self.window_rect = pg.Rect(center_x, center_y, WINDOW_W, WINDOW_H)
        self.window_img = pg.Surface((WINDOW_W, WINDOW_H))
        self.window_img.fill((255, 165, 50))

        # === SELL list paging (no slider) ===
        self.sell_start_index = 0
        self.VISIBLE_ROWS = 4


        

    def get_sell_list(self):
        """Sell 模式 → 顯示可以賣的怪獸"""
        sell_list = []
        for mon in self.game_manager.bag.monsters:
            sell_list.append({
                "type": "monster",
                "name": mon["name"],
                "sprite_path": mon["sprite_path"],
                "level": mon.get("level", 1),
                "hp": mon.get("hp", 10),
                "max_hp": mon.get("max_hp", 10),
                "price": mon.get("level", 1) * 20   # 怪獸賣價公式
            })

        return sell_list
    
    def enter(self):
        # 只有第一次 enter() 時截圖背景
        if not getattr(self, "captured", False):
            screen = pg.display.get_surface()
            self.background_capture = screen.copy()
            self.captured = True
        self.cart_buttons.clear()

        # 上下按鈕（SELL 模式用）
        arrow_x = self.window_rect.right - 120
        self.btn_up = Button(
            "UI/button_up.png", "UI/button_up_hover.png",
            arrow_x, self.window_rect.top + 110,
            30, 30,
            self.scroll_up
        )
        self.btn_down = Button(
            "UI/button_down.png", "UI/button_down_hover.png",
            arrow_x, self.window_rect.top + 350,
            30, 30,
            self.scroll_down
        )

        # 購物車按鈕起始位置
        X = self.window_rect.x
        Y = self.window_rect.y
        W = self.window_rect.width

        self.btn_buy = ColorButton(
            X + 40, Y + 15,
            60, 30,
            lambda: self._switch_mode("buy")
        )

        self.btn_sell = ColorButton(
            X + 120, Y + 15,
            60, 30,
            lambda: self._switch_mode("sell")
        )

        start_y = Y + 110
        box_h = 60

        # 依模式決定「畫面要顯示的清單」(visible_list)
        if self.mode == "buy":
            visible_list = self.items_for_sale
        else:
            sell_list = self.get_sell_list()

            # 確保 start_index 不會超出範圍（例如賣掉怪物後總數變少）
            max_start = max(0, len(sell_list) - self.VISIBLE_ROWS)
            self.sell_start_index = min(self.sell_start_index, max_start)

            start = self.sell_start_index
            end = min(start + self.VISIBLE_ROWS, len(sell_list))
            visible_list = sell_list[start:end]

        # 只對 visible_list 生「最多 4 個」購物車按鈕
        for row, item in enumerate(visible_list):
            box_y = start_y + row * (box_h + 12)

            cart_x = X + W - 80
            cart_y = box_y + box_h//2 - 20

            btn = Button(
                "UI/button_shop.png", "UI/button_shop_hover.png",
                cart_x, cart_y,
                50, 40,
                lambda item=item: self._on_click_item(item)
            )
            self.cart_buttons.append(btn)   

        self.x_button = Button(
            "UI/button_x.png", "UI/button_x_hover.png",
            X + W - 45, Y + 15,       # panel 右上角
            32, 32,
            lambda: scene_manager.change_scene("game")
        )

    def _switch_mode(self, mode):
        if self.mode != mode:
            self.mode = mode
            self.enter()  # 重新產生購物車按鈕


    def _on_click_item(self, item):
        if self.mode == "buy":
            self.buy_item(item)
        else:
            if item["type"] == "monster":
                self.sell_monster(item)


    # 買
    def buy_item(self, item):
        name = item["name"]
        price = item["price"]
        sprite_path = item["icon"]

        # 先找 Coins 看錢夠不夠
        coins = None
        for it in self.game_manager.bag.items:
            if it["name"] == "Coins":
                coins = it
                break

        # 沒有 coins 或錢不夠就直接不買
        if coins is None or coins["count"] < price:
            return

        # 扣錢
        coins["count"] -= price

        # 找背包裡有沒有這個道具，有的話 +1
        for it in self.game_manager.bag.items:
            if it["name"] == name:
                it["count"] += 1
                return

        # 背包裡沒有，新增一個（sprite_path 要跟 BackpackScene 用的一致）
        #    從 items_for_sale 找對應的圖片路徑
        #sprite_path = f"ingame_ui/{name.lower()}.png"
        self.game_manager.bag.items.append({
            "name": name,
            "count": 1,
            "sprite_path": sprite_path
        })


    # SELL MONSTER
    def sell_monster(self, mon_item):
        # 加錢
        for it in self.game_manager.bag.items:
            if it["name"] == "Coins":
                it["count"] += mon_item["price"]

        # 移除怪獸
        for mon in self.game_manager.bag.monsters:
            if mon["name"] == mon_item["name"]:
                self.game_manager.bag.monsters.remove(mon)
                break

        # 重建 UI
        self.enter()

    def update(self, dt):
        keys = pg.key.get_pressed()

        # 離開
        if keys[pg.K_ESCAPE]:
            scene_manager.change_scene("game")
            return
        
        for btn in self.cart_buttons:
            btn.update(dt)

        self.x_button.update(dt)
        self.btn_buy.update(dt)
        self.btn_sell.update(dt)
        # SELL 模式才需要上下按鈕
        if self.mode == "sell":
            self.btn_up.update(dt)
            self.btn_down.update(dt)

    

    # 畫圖
    def draw(self, screen):
        # 畫背景截圖
        screen.blit(self.background_capture, (0, 0))

        # 半透明蓋上
        screen.blit(self.overlay, (0, 0))

        # 視窗框
        screen.blit(self.window_img, self.window_rect)

        # Buy / Sell tab
        X = self.window_rect.x
        Y = self.window_rect.y
        if self.mode == "buy":
            buy_color = (255,255,255)
            sell_color = (200,200,200)
        else:
            buy_color = (200,200,200)
            sell_color = (255,255,255)

        # 畫按鈕
        self.btn_buy.draw(screen, buy_color)
        self.btn_sell.draw(screen, sell_color)

        # 按鈕文字
        buy_txt = self.font.render("Buy", True, (0,0,0))
        sell_txt = self.font.render("Sell", True, (0,0,0))

        screen.blit(buy_txt, (X + 55, Y + 20))
        screen.blit(sell_txt, (X + 135, Y + 20))


        # 商品列表
        if self.mode == "buy":
            display_list = self.items_for_sale
        else:
            sell_list = self.get_sell_list()
            start = self.sell_start_index
            end = min(start + self.VISIBLE_ROWS, len(sell_list))
            display_list = sell_list[start:end]
        start_y = Y + 110
        box_h = 60
        gap = 12


        for row, item in enumerate(display_list):
            box_y = start_y + row * (box_h + gap)

            # 白框
            pg.draw.rect(screen, (255,255,255), (X+25, box_y, 450, box_h))
            pg.draw.rect(screen, (0,0,0), (X+25, box_y, 450, box_h), 3)

            # icon
            if self.mode == "buy":
                # BUY 模式：道具 icon 來自 item["icon"]
                icon_path = item["icon"]
            else:
                # SELL 模式：怪獸 icon 在 sprite_path
                icon_path = item["sprite_path"]

            icon = pg.image.load(icon_path).convert_alpha()
            icon = pg.transform.scale(icon, (32, 32))
            screen.blit(icon, (X+35, box_y + 14))


            # 名稱（放左中間）
            name_txt = self.font.render(item["name"], True, (0,0,0))
            screen.blit(name_txt, (X + 90, box_y + 18))

            # 數量
            count_txt = self.font.render("x1", True, (0,0,0))
            screen.blit(count_txt, (X + 240, box_y + 18))

            # 價錢（右側）
            price_txt = self.font.render(f"${item['price']}", True, (0,0,0))
            screen.blit(price_txt, (X + 330, box_y + 18))
        # 畫購物車按鈕
        for btn in self.cart_buttons:
            btn.draw(screen)

        self.x_button.draw(screen)
        if self.mode == "sell":
            self.btn_up.draw(screen)
            self.btn_down.draw(screen)

    def scroll_up(self):
        self.sell_start_index = max(0, self.sell_start_index - 1)
        self.enter()  # 重建購物車按鈕

    def scroll_down(self):
        sell_list = self.get_sell_list()
        max_start = max(0, len(sell_list) - self.VISIBLE_ROWS)
        self.sell_start_index = min(max_start, self.sell_start_index + 1)
        self.enter()
