import pygame as pg
import threading
import time

from src.scenes.scene import Scene
from src.core import GameManager, OnlineManager
from src.utils import Logger, PositionCamera, GameSettings, Position
from src.core.services import sound_manager, scene_manager, input_manager
from src.sprites import Sprite
from typing import override
from src.interface.components import Button
from src.scenes.bush_interaction import BushInteraction
from src.interface.components.chat_overlay import ChatOverlay
from src.sprites import Animation # 用你的動畫系統
from src.scenes.navigation_scene import NavigationScene
from collections import deque


NAV_PLACES = {
    "Start": (16, 30),   # tile 座標
    "Gym":   (24, 25),
}

def bfs(grid, start, goal):
    q = deque([start])
    came_from = {start: None}

    while q:
        x, y = q.popleft()
        if (x, y) == goal:
            break

        for dx, dy in [(1,0), (-1,0), (0,1), (0,-1)]:
            nx, ny = x + dx, y + dy
            if (nx, ny) in came_from:
                continue
            if not grid[ny][nx]:
                continue

            came_from[(nx, ny)] = (x, y)
            q.append((nx, ny))

    path = []
    cur = goal
    while cur:
        path.append(cur)
        cur = came_from.get(cur)
    path.reverse()
    return path
    
def try_get_flower_rects_from_tmx(game_map) -> list[pg.Rect]:
    """
    不靠 layer 名完全匹配。
    -layer 名只要包含 flower / plant / decor 就視為可能花層
    - 或者 tile 本身有 properties（例如 type=flower / collide=true / blocked=true）也會被擋
    """
    TILE = GameSettings.TILE_SIZE
    rects: list[pg.Rect] = []

    tmx = getattr(game_map, "tmxdata", None)
    if tmx is None:
        return rects

    layers = getattr(tmx, "visible_layers", None)
    if not layers:
        return rects

    def is_flower_layer(layer_name: str) -> bool:
        n = (layer_name or "").strip().lower()
        return ("flower" in n) or ("plant" in n) or ("decor" in n)

    def is_blocking_tile(gid: int) -> bool:
        # pytmx：用 gid 取 tile properties
        props = None
        if hasattr(tmx, "get_tile_properties_by_gid"):
            props = tmx.get_tile_properties_by_gid(gid)
        if not props:
            return False

        # 常見命名：type / class / name / collide / collision / blocked / block
        typ = str(props.get("type", props.get("class", props.get("name", "")))).lower()
        if "flower" in typ or "plant" in typ:
            return True

        for k in ["collide", "collision", "blocked", "block", "solid"]:
            v = props.get(k, False)
            if v in (True, 1, "1", "true", "True", "yes", "Yes"):
                return True

        return False

    for layer in layers:
        name = getattr(layer, "name", "")
        layer_hint = is_flower_layer(name)

        if hasattr(layer, "tiles"):
            for x, y, gid in layer.tiles():
                if not gid:
                    continue

                # 兩種命中：花層（名稱包含關鍵字） or tile 自己標記是 blocking/flower
                if layer_hint or is_blocking_tile(gid):
                    rects.append(pg.Rect(x * TILE, y * TILE, TILE, TILE))

    return rects

def iter_obstacle_rects(game_scene):
    game_map = game_scene.game_manager.current_map

    # 牆
    for r in getattr(game_map, "_collision_map", []):
        yield r

    # 草叢（不可走，保留）
    if hasattr(game_map, "get_bush_tiles"):
        for r in game_map.get_bush_tiles():
            yield r

    # 花 若已經有 try_get_flower_rects_from_tmx 直接用
    if "try_get_flower_rects_from_tmx" in globals():
        for r in try_get_flower_rects_from_tmx(game_map):
            yield r

    # 商店 NPC
    npc_rect = getattr(game_scene.game_manager, "npc_collision_rect", None)
    if npc_rect:
        yield npc_rect

    # 其他 trainer/NPC
    for enemy in getattr(game_scene.game_manager, "current_enemy_trainers", []):
        r = getattr(getattr(enemy, "animation", None), "rect", None) or getattr(enemy, "rect", None)
        if r:
            yield r


def build_walkable_grid(game_scene):
    """
    game_scene: GameScene（不是 game_map）
    可以同時拿到：
    - game_scene.game_manager.current_map._collision_map
    - game_scene.game_manager.npc_collision_rect
    - game_scene.bush_list
    """
    game_map = game_scene.game_manager.current_map
    TILE = GameSettings.TILE_SIZE

    w = game_map.tmxdata.width
    h = game_map.tmxdata.height
    grid = [[True for _ in range(w)] for _ in range(h)]

    def block_rect(rect: pg.Rect):
        # 把一個 rect 覆蓋到所有 tile（支援 rect 跨多格）
        left = max(0, rect.left // TILE)
        right = min(w - 1, (rect.right - 1) // TILE)
        top = max(0, rect.top // TILE)
        bottom = min(h - 1, (rect.bottom - 1) // TILE)
        for ty in range(top, bottom + 1):
            for tx in range(left, right + 1):
                grid[ty][tx] = False

    # 牆（collision map）
    for r in iter_obstacle_rects(game_scene):
        block_rect(r)
    #for rect in game_map._collision_map:
    #    block_rect(rect)

    # NPC
    npc_rect = getattr(game_scene.game_manager, "npc_collision_rect", None)
    if npc_rect is not None:
        block_rect(npc_rect)

    # 草叢（導航避開草叢）
    #bush_list = getattr(game_scene, "bush_list", None)
    for rect in game_map.get_bush_tiles():
        block_rect(rect)

    # 其他障礙 enemy trainers / NPC
    for enemy in getattr(game_scene.game_manager, "current_enemy_trainers", []):
        r = getattr(getattr(enemy, "animation", None), "rect", None)
        if r:
            block_rect(r)
        else:
            r2 = getattr(enemy, "rect", None)
            if r2:
                block_rect(r2)


    return grid


class OnlinePlayerVisual:
    def __init__(self):
         # 玩家動畫圖
        self.anim = Animation(
            "character/ow1.png",
            ["down", "left", "right", "up"],   # 必須 match 玩家 rows
            4,                                 # 玩家也是 4 keyframes
            (GameSettings.TILE_SIZE, GameSettings.TILE_SIZE)
        )

        self.x = 0
        self.y = 0
        self.direction = "down"
        self.moving = False

        # 預設停在下方向 idle
        self.anim.switch("down")

    def update_state(self, x, y, direction, moving):
        direction = direction.lower()
        self.x = x
        self.y = y
        self.direction = direction
        self.moving = moving

        if direction in ["down", "left", "right", "up"]:
            self.anim.switch(direction)

        if moving:
            self.anim.switch(direction)
        else:
            self.anim.switch(direction)

    def update(self, dt):
        self.anim.update(dt)
        self.anim.update_pos(Position(self.x, self.y))

    def draw(self, screen, camera):
        pos = camera.transform_position_as_position(Position(self.x, self.y))
        self.anim.update_pos(Position(self.x, self.y))
        self.anim.draw(screen, camera)

class GameScene(Scene):
    game_manager: GameManager
    online_manager: OnlineManager | None
    sprite_online: Sprite
    
    def __init__(self):
        super().__init__()

        self.bush_cooldown = 0

        # Game Manager
        manager = GameManager.load("saves/initial_game.json")
        if manager is None:
            Logger.error("Failed to load game manager")
            exit(1)
        self.game_manager = manager
        if not hasattr(self.game_manager, "teleport_cooldown"):
            self.game_manager.teleport_cooldown = 0.0
        
        # Online Manager
        if GameSettings.IS_ONLINE:
            self.online_manager = OnlineManager()
        else:
            self.online_manager = None
        self.sprite_online = Sprite("ingame_ui/options1.png", (GameSettings.TILE_SIZE, GameSettings.TILE_SIZE))
        px, py = GameSettings.SCREEN_WIDTH, GameSettings.SCREEN_HEIGHT // 2
        self.setting_button = Button(
            "UI/button_setting.png", "UI/button_setting_hover.png",
            px - 70, py - 330, 30, 30,
            lambda: scene_manager.change_scene("setting_from_game")
        )
        self.backpack_button = Button(
            "UI/button_backpack.png", "UI/button_backpack_hover.png",
            px - 120, py - 330, 30, 30,
            lambda: scene_manager.change_scene("backpack")
        )
        self.navigation_button = Button(
            "UI/button_navigation.png", "UI/button_navigation_hover.png",
            px - 170, py - 330, 30, 30,
            lambda: scene_manager.change_scene("navigation")  # 你要切的 scene
        )
        # 載入 NPC spritesheet
        self.npc_sheet = pg.image.load("assets/images/character/ow10.png").convert_alpha()

        NPC_FRAME = 32  # 每格大小

        # 最右下角的格子 (row=3, col=3)
        frame_x = 0 * NPC_FRAME  # 96
        frame_y = 3 * NPC_FRAME  # 96
        # 切第一張 (0,0) 當作站立
        self.npc_surface = pg.Surface((NPC_FRAME, NPC_FRAME), pg.SRCALPHA)
        self.npc_surface.blit(self.npc_sheet, (0, 0), (frame_x, frame_y, NPC_FRAME, NPC_FRAME))

        # 放大到和玩家一樣大
        tile = GameSettings.TILE_SIZE
        self.npc_surface = pg.transform.scale(self.npc_surface, (tile, tile))
        # NPC 的世界座標
        self.shop_npc_pos = Position(18.5 * GameSettings.TILE_SIZE, 32 * GameSettings.TILE_SIZE)

        self.shop_npc_rect = pg.Rect(
            self.shop_npc_pos.x,
            self.shop_npc_pos.y,
            GameSettings.TILE_SIZE,
            GameSettings.TILE_SIZE
        )
        


        
    @override
    def enter(self) -> None:
            
        self._chat_overlay = ChatOverlay(
            send_callback=self.online_manager.send_chat if self.online_manager else None,
            get_messages=self.online_manager.get_recent_chat if self.online_manager else None
        )
        self._last_chat_id_seen = 0
        self._chat_bubbles = {}  # pid → (text, expire_time)

        self.online_visuals = {}
        sound_manager.play_bgm("RBY 103 Pallet Town.ogg")

        if self.online_manager:
            self.online_manager.enter()

        # 初始化草叢互動
        self.bush_list = [
            BushInteraction(rect, self.game_manager.player)
            for rect in self.game_manager.current_map.get_bush_tiles()
        ]
        self.game_manager.npc_collision_rect = self.shop_npc_rect
        self._last_map_name = self.game_manager.current_map.path_name


           

    @override
    def exit(self) -> None:
        if self.online_manager:
            self.online_manager.exit()
        

    @override
    def update(self, dt: float):
        # AUTO NAVIGATION
        if hasattr(self, "nav_path") and self.nav_path:
            player = self.game_manager.player
            TILE = GameSettings.TILE_SIZE
            speed = player.speed * dt

            tx, ty = self.nav_path[0]
            target_x = tx * TILE
            target_y = ty * TILE

            dx = target_x - player.position.x
            dy = target_y - player.position.y

            move_x = 0
            move_y = 0

            # 一次只走一個方向
            if abs(dx) > abs(dy):
                if dx > 0:
                    player.direction = player.direction.RIGHT
                    player.animation.switch("right")
                    move_x = min(speed, dx)
                else:
                    player.direction = player.direction.LEFT
                    player.animation.switch("left")
                    move_x = max(-speed, dx)
            else:
                if dy > 0:
                    player.direction = player.direction.DOWN
                    player.animation.switch("down")
                    move_y = min(speed, dy)
                else:
                    player.direction = player.direction.UP
                    player.animation.switch("up")
                    move_y = max(-speed, dy)
            # 碰撞檢查
            next_rect = pg.Rect(
                player.position.x + move_x,
                player.position.y + move_y,
                TILE,
                TILE
            )

            for wall in self.game_manager.current_map._collision_map:
                if next_rect.colliderect(wall):
                    del self.nav_path
                    return

            player.position.x += move_x
            player.position.y += move_y
            player.animation.update_pos(player.position)
            player.animation.update(dt)

            # 到達這個 tile  換下一個
            if abs(dx) < 2 and abs(dy) < 2:
                self.nav_path.pop(0)
                if not self.nav_path:
                    del self.nav_path

            return
        # TELEPORT COOLDOWN UPDATE
        if not hasattr(self.game_manager, "teleport_cooldown"):
            self.game_manager.teleport_cooldown = 0.0
        if self.game_manager.teleport_cooldown > 0:
            self.game_manager.teleport_cooldown -= dt
        # CHAT OPEN / TYPING
        if self._chat_overlay:
            # 按 Enter 打開聊天
            if input_manager.key_pressed(pg.K_RETURN) and not self._chat_overlay.is_open:
                self._chat_overlay.open()

            # 如果聊天視窗是開的，要更新聊天輸入
            if self._chat_overlay.is_open:
                self._chat_overlay.update(dt)
                return  # 避免聊天時角色還能動

        # Shop NPC 互動：站在 (18, 31) 按 E 進入
        if self.game_manager.player:
            px = self.game_manager.player.position.x
            py = self.game_manager.player.position.y

            tile_x = int(px // GameSettings.TILE_SIZE)
            tile_y = int(py // GameSettings.TILE_SIZE)

            # 玩家站在 18,31 這格，就可以按 E 開商店
            if tile_x == 18 and tile_y == 31:
                if input_manager.key_pressed(pg.K_e):
                    shop_scene = scene_manager._scenes["shop"]
                    shop_scene.game_manager = self.game_manager  # 注入 game_manager
                    scene_manager.change_scene("shop")
                    return
        

        if self.bush_cooldown > 0:
            self.bush_cooldown -= dt
            
        # 地圖切換
        # 地圖切換（加草叢重建）
        old_map = self.game_manager.current_map.path_name

        if self.game_manager.player:
            self.game_manager.player.update(dt)

        new_map = self.game_manager.current_map.path_name
        if new_map != old_map:
            # 地圖真的換了，重建草叢判定
            self.bush_list = [
                BushInteraction(rect, self.game_manager.player)
                for rect in self.game_manager.current_map.get_bush_tiles()
            ]
            self.bush_cooldown = 0
            return

        detected_enemy = None   # 目前有看到玩家的敵人（選第一個）
        for enemy in self.game_manager.current_enemy_trainers:
            enemy.update(dt)
            if enemy.detected and detected_enemy is None:
                detected_enemy = enemy

        # NPC 視線 + 戰鬥觸發
        can_enter_battle = detected_enemy is not None

        if can_enter_battle and input_manager.key_down(pg.K_e):
            battle_scene = scene_manager._scenes["battle"]

            # 用 EnemyTrainer 自帶的 monster 資料
            enemy_mon = detected_enemy.monster
            battle_scene.start_battle(enemy_mon)

            scene_manager.change_scene("battle")
            return

        # 草叢互動更新
        for bush in self.bush_list:
            bush.update()
            if bush.near and self.bush_cooldown <= 0:
                self.bush_cooldown = 2  # 2秒冷卻時間
                scene_manager.change_scene("catch")
                return
        
        # 背包更新
        self.game_manager.bag.update(dt)

        
        # TODO: UPDATE CHAT OVERLAY:

        # if self._chat_overlay:
        #     if _____.key_pressed(...):
        #         self._chat_overlay.____
        #     self._chat_overlay.update(____)
        # Update chat bubbles from recent messages

        # This part's for the chatting feature, we've made it for you.
        if self.online_manager:
            try:
                msgs = self.r.get_recent_chat(50)
                max_id = self._last_chat_id_seen
                now = time.monotonic()
                for m in msgs:
                    mid = int(m.get("id", 0))
                    if mid <= self._last_chat_id_seen:
                        continue
                    sender = int(m.get("from", -1))
                    text = str(m.get("text", ""))
                    if sender >= 0 and text:
                        self._chat_bubbles[sender] = (text, now + 5.0)
                    if mid > max_id:
                        max_id = mid
                self._last_chat_id_seen = max_id
            except Exception:
                pass
        

        # 線上更新
        if self.online_manager and self.game_manager.player:
            
            player = self.game_manager.player
            moving = (
                input_manager.key_down(pg.K_LEFT) or
                input_manager.key_down(pg.K_a) or
                input_manager.key_down(pg.K_RIGHT) or
                input_manager.key_down(pg.K_d) or
                input_manager.key_down(pg.K_UP) or
                input_manager.key_down(pg.K_w) or
                input_manager.key_down(pg.K_DOWN) or
                input_manager.key_down(pg.K_s)
            )



            self.online_manager.update(
                player.position.x,
                player.position.y,
                self.game_manager.current_map.path_name,
                player.direction.name.lower(),
                moving
            )

        # UI 更新
        self.setting_button.update(dt)
        self.backpack_button.update(dt)
        self.navigation_button.update(dt)


        


    def draw_minimap(self, screen: pg.Surface):
        # 沒玩家就不用畫
        if not self.game_manager.player:
            return

        current_map = self.game_manager.current_map

        # 這裡用 Map.prebake 好的整張地圖 surface
        full_map_surface: pg.Surface = current_map._surface  # 如果名字不一樣就改這行

        # 小地圖大小 & 位置
        MINIMAP_W, MINIMAP_H = 180, 120
        MINIMAP_X, MINIMAP_Y = 10, 10

        # 把整張地圖縮小成小地圖
        minimap_surf = pg.transform.smoothscale(
            full_map_surface, (MINIMAP_W, MINIMAP_H)
        )

        # 畫一個外框背景（黑框 + 內圖）
        frame_rect = pg.Rect(MINIMAP_X - 3, MINIMAP_Y - 3,
                             MINIMAP_W + 6, MINIMAP_H + 6)
        pg.draw.rect(screen, (0, 0, 0), frame_rect)          # 外面的黑底
        screen.blit(minimap_surf, (MINIMAP_X, MINIMAP_Y))    # 貼上縮小地圖

        # 畫玩家點點
        map_w, map_h = full_map_surface.get_width(), full_map_surface.get_height()
        scale_x = MINIMAP_W / map_w
        scale_y = MINIMAP_H / map_h

        px = self.game_manager.player.position.x
        py = self.game_manager.player.position.y

        mini_px = MINIMAP_X + px * scale_x
        mini_py = MINIMAP_Y + py * scale_y

        # 玩家在 minimap 上的藍色小圓點
        pg.draw.circle(screen, (0, 0, 255), (int(mini_px), int(mini_py)), 3)


    @override
    def draw(self, screen: pg.Surface):
        current_time = pg.time.get_ticks()
        dt = (current_time - getattr(self, "_last_time", current_time)) / 1000.0
        self._last_time = current_time 
     
        if self.game_manager.player:
            '''
            [TODO HACKATHON 3]
            Implement the camera algorithm logic here
            Right now it's hard coded, you need to follow the player's positions
            you may use the below example, but the function still incorrect, you may trace the entity.py
            '''
            camera = self.game_manager.player.camera
            
            self.game_manager.current_map.draw(screen, camera)
            self.game_manager.player.draw(screen, camera)
        else:
            camera = PositionCamera(0, 0)
            self.game_manager.current_map.draw(screen, camera)
        for enemy in self.game_manager.current_enemy_trainers:
            enemy.draw(screen, camera)

        self.game_manager.bag.draw(screen)

        if self._chat_overlay:
            self._chat_overlay.draw(screen)

        # 畫商店 NPC
        cam = self.game_manager.player.camera
        npc_screen_pos = cam.transform_position_as_position(self.shop_npc_pos)
        screen.blit(self.npc_surface, (npc_screen_pos.x, npc_screen_pos.y))

        
        if self.online_manager and self.game_manager.player:
            list_online = self.online_manager.get_list_players()
            for p in list_online:
                pid = p["id"]

                # 如果沒有 visual，建立一個
                if pid not in self.online_visuals:
                    self.online_visuals[pid] = OnlinePlayerVisual()

                vis = self.online_visuals[pid]
                vis.update_state(
                    p["x"],
                    p["y"],
                    p.get("direction", "down"),
                    p.get("moving", False)
                )

                vis.update(dt)

                # 只畫同地圖的人
                if p["map"] == self.game_manager.current_map.path_name:
                    vis.draw(screen, camera)
            try:
                self._draw_chat_bubbles(screen, camera)
            except Exception:
                pass
        
        self.setting_button.draw(screen)
        self.backpack_button.draw(screen)
        self.navigation_button.draw(screen)

        self.draw_minimap(screen)

        if hasattr(self, "nav_path") and self.nav_path:
            TILE = GameSettings.TILE_SIZE

            for i, (tx, ty) in enumerate(self.nav_path):
                wx = tx * TILE + TILE // 2
                wy = ty * TILE + TILE // 2
                pos = camera.transform_position_as_position(Position(wx, wy))

                # 決定三角形方向（看下一個節點）
                if i < len(self.nav_path) - 1:
                    nx, ny = self.nav_path[i + 1]
                    dx = nx - tx
                    dy = ny - ty

                    if abs(dx) > abs(dy):
                        direction = "right" if dx > 0 else "left"
                    else:
                        direction = "down" if dy > 0 else "up"
                else:
                    direction = "up"  # 終點箭頭朝上（你也可以改成 "down"）

                self._draw_nav_triangle(screen, pos, direction)

    def _draw_nav_triangle(self, screen, pos, direction, color=(0, 120, 255), size=6):
        x, y = pos.x, pos.y

        if direction == "right":
            points = [(x + size, y), (x - size, y - size), (x - size, y + size)]
        elif direction == "left":
            points = [(x - size, y), (x + size, y - size), (x + size, y + size)]
        elif direction == "down":
            points = [(x, y + size), (x - size, y - size), (x + size, y - size)]
        else:  # "up"
            points = [(x, y - size), (x - size, y + size), (x + size, y + size)]

        pg.draw.polygon(screen, color, points)


    def _draw_chat_bubbles(self, screen: pg.Surface, camera: PositionCamera) -> None:
        
        if not self.online_manager:
            return
        # REMOVE EXPIRED BUBBLES
        now = time.monotonic()
        expired = [pid for pid, (_, ts) in self._chat_bubbles.items() if ts <= now]
        for pid in expired:
            del self._chat_bubbles[pid]
        if not self._chat_bubbles:
            return
        
        font = pg.font.SysFont("Arial", 16)

        # DRAW LOCAL PLAYER'S BUBBLE
        local_pid = self.online_manager.player_id if self.online_manager else -1
        if self.game_manager.player and local_pid in self._chat_bubbles:
            text, _ = self._chat_bubbles[local_pid]
            self._draw_bubble_for_pos(
                screen,
                camera,
                self.game_manager.player.position,
                text,
                pg.font.SysFont("Arial", 16)
            )

        # DRAW OTHER PLAYERS' BUBBLES
        # for pid, (text, _) in self._chat_bubbles.items():
        #     if pid == local_pid:
        #         continue
        #     pos_xy = self._online_last_pos.____(..., ...)
        #     if not pos_xy:
        #         continue
        #     px, py = pos_xy
        #     self._draw_bubble_for_pos(..., ..., ..., ..., ...)
        list_online = self.online_manager.get_list_players()

        for p in list_online:
            pid = p["id"]
            if pid == local_pid:
                continue
            if pid not in self._chat_bubbles:
                continue

            text, _ = self._chat_bubbles[pid]
            world_pos = Position(p["x"], p["y"])

            self._draw_chat_bubble_for_pos(
                screen,
                camera,
                world_pos,
                text,
                font
            )

        
        """
        DRAWING CHAT BUBBLES:
        - When a player sends a chat message, the message should briefly appear above
        that player's character in the world, similar to speech bubbles in RPGs.
        - Each bubble should last only a few seconds before fading or disappearing.
        - Only players currently visible on the map should show bubbles.

         What you need to think about:
            ------------------------------
            1. **Which players currently have messages?**
            You will have a small structure mapping player IDs to the text they sent
            and the time the bubble should disappear.

            2. **How do you know where to place the bubble?**
            The bubble belongs above the player's *current position in the world*.
            The game already tracks each player’s world-space location.
            Convert that into screen-space and draw the bubble there.

            3. **How should bubbles look?**
            You decide. The visual style is up to you:
            - A rounded rectangle, or a simple box.
            - Optional border.
            - A small triangle pointing toward the character's head.
            - Enough padding around the text so it looks readable.

            4. **How do bubbles disappear?**
            Compare the current time to the stored expiration timestamp.
            Remove any bubbles that have expired.

            5. **In what order should bubbles be drawn?**
            Draw them *after* world objects but *before* UI overlays.

        Reminder:
        - For the local player, you can use the self.game_manager.player.position to get the player's position
        - For other players, maybe you can find some way to store other player's last position?
        - For each player with a message, maybe you can call a helper to actually draw a single bubble?
        """

    def _draw_chat_bubble_for_pos(self, screen: pg.Surface, camera: PositionCamera, world_pos: Position, text: str, font: pg.font.Font):
        
        """
        Steps:
            ------------------
            1. Convert a player’s world position into a location on the screen.
            (Use the camera system provided by the game engine.)

            2. Decide where "above the player" is.
            Typically a little above the sprite’s head.

            3. Measure the rendered text to determine bubble size.
            Add padding around the text.
        """
        # 世界座標轉螢幕座標
        pos = camera.transform_position_as_position(world_pos)
        px, py = pos.x, pos.y - 20   # 往上 20px 放泡泡

        # 渲染文字
        text_surf = font.render(text, True, (0, 0, 0))
        tw, th = text_surf.get_size()

        padding = 6
        box_w = tw + padding * 2
        box_h = th + padding * 2

        # 背景方塊
        bg = pg.Surface((box_w, box_h), pg.SRCALPHA)
        bg.fill((255, 255, 255, 220))  # 白底＋透明度

        screen.blit(bg, (px - box_w // 2, py - box_h))
        screen.blit(text_surf, (px - tw // 2, py - box_h + padding))


    def go_to(self, place_name):
        game_scene = scene_manager._scenes["game"]

        px = int(game_scene.game_manager.player.position.x // GameSettings.TILE_SIZE)
        py = int(game_scene.game_manager.player.position.y // GameSettings.TILE_SIZE)

        start = (px, py)
        goal = NAV_PLACES[place_name]

        grid = build_walkable_grid(game_scene)
        path = bfs(grid, start, goal)

        game_scene.nav_path = path
        scene_manager.change_scene("game")

    