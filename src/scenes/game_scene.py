import pygame as pg
import threading
import time

from src.scenes.scene import Scene
from src.core import GameManager, OnlineManager
from src.utils import Logger, PositionCamera, GameSettings, Position
from src.core.services import sound_manager
from src.sprites import Sprite

from typing import override, Dict, Tuple
# from src.interface.components.chat_overlay import ChatOverlay

class GameScene(Scene):
    game_manager: GameManager
    online_manager: OnlineManager | None
    sprite_online: Sprite
    
    def __init__(self):
        super().__init__()
        # Game Manager
        manager = GameManager.load("saves/game0.json")
        if manager is None:
            Logger.error("Failed to load game manager")
            exit(1)
        self.game_manager = manager
        
        # Online Manager
        if GameSettings.IS_ONLINE:
            self.online_manager = OnlineManager()
            # self.chat_overlay = ChatOverlay(
            #     send_callback=..., <- send chat method
            #     get_messages=..., <- get chat messages method
            # )
        else:
            self.online_manager = None
        self.sprite_online = Sprite("ingame_ui/options1.png", (GameSettings.TILE_SIZE, GameSettings.TILE_SIZE))
        self._chat_bubbles: Dict[int, Tuple[str, str]] = {}
        self._last_chat_id_seen = 0

    @override
    def enter(self) -> None:
        sound_manager.play_bgm("RBY 103 Pallet Town.ogg")
        if self.online_manager:
            self.online_manager.enter()
        
    @override
    def exit(self) -> None:
        if self.online_manager:
            self.online_manager.exit()
        
    @override
    def update(self, dt: float):
        # Check if there is assigned next scene
        self.game_manager.try_switch_map()
        
        # Update player and other data
        if self.game_manager.player:
            self.game_manager.player.update(dt)
        for enemy in self.game_manager.current_enemy_trainers:
            enemy.update(dt)
            
        # Update others
        self.game_manager.bag.update(dt)

        """
        TODO: UPDATE CHAT OVERLAY:

        # if self._chat_overlay:
        #     if _____.key_pressed(...):
        #         self._chat_overlay.____
        #     self._chat_overlay.update(____)
        # Update chat bubbles from recent messages

        # This part's for the chatting feature, we've made it for you.
        # if self.online_manager:
        #     try:
        #         msgs = self.online_manager.get_recent_chat(50)
        #         max_id = self._last_chat_id_seen
        #         now = time.monotonic()
        #         for m in msgs:
        #             mid = int(m.get("id", 0))
        #             if mid <= self._last_chat_id_seen:
        #                 continue
        #             sender = int(m.get("from", -1))
        #             text = str(m.get("text", ""))
        #             if sender >= 0 and text:
        #                 self._chat_bubbles[sender] = (text, now + 5.0)
        #             if mid > max_id:
        #                 max_id = mid
        #         self._last_chat_id_seen = max_id
        #     except Exception:
        #         pass
        """
        if self.game_manager.player is not None and self.online_manager is not None:
            _ = self.online_manager.update(
                self.game_manager.player.position.x, 
                self.game_manager.player.position.y,
                self.game_manager.current_map.path_name
            )
        
    @override
    def draw(self, screen: pg.Surface):        
        if self.game_manager.player:
            '''
            [TODO HACKATHON 3]
            Implement the camera algorithm logic here
            Right now it's hard coded, you need to follow the player's positions
            you may use the below example, but the function still incorrect, you may trace the entity.py
            
            camera = self.game_manager.player.camera
            '''
            camera = PositionCamera(16 * GameSettings.TILE_SIZE, 30 * GameSettings.TILE_SIZE)
            self.game_manager.current_map.draw(screen, camera)
            self.game_manager.player.draw(screen, camera)
        else:
            camera = PositionCamera(0, 0)
            self.game_manager.current_map.draw(screen, camera)
        for enemy in self.game_manager.current_enemy_trainers:
            enemy.draw(screen, camera)

        self.game_manager.bag.draw(screen)

        # if self._chat_overlay:
        #     self._chat_overlay.draw(screen)
        
        if self.online_manager and self.game_manager.player:
            list_online = self.online_manager.get_list_players()
            for player in list_online:
                if player["map"] == self.game_manager.current_map.path_name:
                    cam = self.game_manager.player.camera
                    pos = cam.transform_position_as_position(Position(player["x"], player["y"]))
                    self.sprite_online.update_pos(pos)
                    self.sprite_online.draw(screen)
            # try:
            #     self._draw_chat_bubbles(...)
            # except Exception:
            #     pass
    def _draw_chat_bubbles(self, screen: pg.Surface, camera: PositionCamera) -> None:
        
        # if not self.online_manager:
        #     return
        # REMOVE EXPIRED BUBBLES
        # now = time.monotonic()
        # expired = [pid for pid, (_, ts) in self._chat_bubbles.items() if ts <= now]
        # for pid in expired:
        #     self._chat_bubbles.____(..., ...)
        # if not self._chat_bubbles:
        #     return

        # DRAW LOCAL PLAYER'S BUBBLE
        # local_pid = self.____
        # if self.game_manager.player and local_pid in self._chat_bubbles:
        #     text, _ = self._chat_bubbles[...]
        #     self._draw_bubble_for_pos(..., ..., ..., ..., ...)

        # DRAW OTHER PLAYERS' BUBBLES
        # for pid, (text, _) in self._chat_bubbles.items():
        #     if pid == local_pid:
        #         continue
        #     pos_xy = self._online_last_pos.____(..., ...)
        #     if not pos_xy:
        #         continue
        #     px, py = pos_xy
        #     self._draw_bubble_for_pos(..., ..., ..., ..., ...)

        pass
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
    pass
    """
    Conceptual steps:
        ------------------
        1. Convert a player’s world position into a location on the screen.
        (Use the camera system provided by the game engine.)

        2. Decide where "above the player" is.
        Typically a little above the sprite’s head.

        3. Measure the rendered text to determine bubble size.
        Add padding around the text.
    """
