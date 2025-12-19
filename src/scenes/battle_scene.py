import pygame as pg
from src.scenes.scene import Scene
from typing import override
from src.core.services import scene_manager, input_manager
import random
import copy

class BattleScene(Scene):
    # Element multiplier table
    ELEM_MULT = {
        ("Water", "Fire"): 2.0,
        ("Fire", "Grass"): 2.0,
        ("Grass", "Water"): 2.0,
        ("Fire", "Water"): 0.5,
        ("Grass", "Fire"): 0.5,
        ("Water", "Grass"): 0.5,
    }
    DEFAULT_ELEMENTS = ["Water", "Fire", "Grass"]

    def __init__(self):
        super().__init__()
        self.anim_timer = 0.0

        # battle states:
        # idle -> player_turn -> player_attack_anim -> enemy_attack_anim -> player_turn ...
        # plus: item_menu, win, lose
        self.state = "idle"   # wait start_battle()

        # message system (optional but helps UX)
        self.message = ""
        self.message_timer = 0.0

        # end timer (avoid pg.time.delay)
        self.end_timer = 0.0

        # UI fonts
        self.font_big = pg.font.Font("assets/fonts/Minecraft.ttf", 32)
        self.font_mid = pg.font.Font("assets/fonts/Minecraft.ttf", 24)
        self.font_small = pg.font.Font("assets/fonts/Minecraft.ttf", 18)

        # background
        self.bg = pg.image.load("assets/images/backgrounds/background1.png").convert()

        # element icon (top-left)
        self.element_icon = pg.image.load(
            "assets/images/sprites/element.png"
        ).convert_alpha()

        self.element_icon = pg.transform.scale(self.element_icon, (90, 90))


        # fallback sprites (before start_battle)
        self.player_sprite = pg.transform.scale(
            pg.transform.flip(
                pg.image.load("assets/images/menu_sprites/menusprite2.png").convert_alpha(),
                True, False
            ),
            (160, 160)
        )
        enemy_img = pg.image.load("assets/images/menu_sprites/menusprite3.png").convert_alpha()
        self.enemy_sprite = pg.transform.scale(enemy_img, (160, 160))

        # main buttons (bottom)
        self.buttons = {
            "fight": pg.Rect(180, 550, 140, 40),
            "item":  pg.Rect(330, 550, 140, 40),
            "switch": pg.Rect(480, 550, 140, 40),
            "run":   pg.Rect(630, 550, 140, 40),
        }

        # item menu buttons (reuse bottom area when in item_menu)
        self.item_buttons = {
            "heal": pg.Rect(180, 550, 200, 40),
            "strength": pg.Rect(400, 550, 260, 40),
            "defense": pg.Rect(690, 550, 240, 40),
            "back": pg.Rect(180, 610, 140, 40),
        }

        self.pending_enemy_action = False

        # placeholders (set in start_battle)
        self.player_mon = None
        self.enemy_mon = None


    def handle_events(self, event: pg.event.Event):
        pass

    # helpers: stats / element / damage
    def _ensure_stats(self, mon: dict, *, is_enemy: bool):
        # basic keys
        mon.setdefault("level", 1)
        mon.setdefault("max_hp", 50)
        mon.setdefault("hp", mon["max_hp"])

        # attack/defense for item buffs & damage calc
        mon.setdefault("atk", 10)
        mon.setdefault("def", 5)

        # buffs (from potions)
        mon.setdefault("atk_buff", 0)   # Strength Potion
        mon.setdefault("def_buff", 0)   # Defense Potion

        # element: if missing, assign something deterministic-ish
        if "element" not in mon:
            # try infer by name keyword (optional)
            name = str(mon.get("name", "")).lower()
            if "water" in name:
                mon["element"] = "Water"
            elif "fire" in name:
                mon["element"] = "Fire"
            elif "grass" in name or "leaf" in name:
                mon["element"] = "Grass"
            else:
                # at least make elements exist in battle:
                # player -> random but stable-ish; enemy -> random
                mon["element"] = random.choice(self.DEFAULT_ELEMENTS) if is_enemy else random.choice(self.DEFAULT_ELEMENTS)

        # evolution fields are optional:
        # evolve_level: int
        # evolve_to_sprite_path: str
        mon.setdefault("evolved", False)

    def element_multiplier(self, atk_elem: str, def_elem: str) -> float:
        return float(self.ELEM_MULT.get((atk_elem, def_elem), 1.0))

    def calc_damage(self, attacker: dict, defender: dict, base: int = 5) -> int:
        atk = int(attacker.get("atk", 10)) + int(attacker.get("atk_buff", 0))
        df = int(defender.get("def", 5)) + int(defender.get("def_buff", 0))
        mult = self.element_multiplier(attacker.get("element", "Normal"), defender.get("element", "Normal"))
        dmg = int(max(1, (base + atk) * mult - df))
        return dmg

    def _set_message(self, text: str, seconds: float = 0.9):
        self.message = text
        self.message_timer = seconds

    # items (backpack)
    def _get_bag(self):
        game_scene = scene_manager._scenes.get("game")
        if not game_scene:
            return None
        return game_scene.game_manager.bag

    def _find_item(self, bag, name: str):
        # exact match (case-insensitive)
        for it in bag.items:
            if str(it.get("name", "")).lower() == name.lower():
                return it

        # compatibility: some projects use "potion" for heal
        if name.lower() == "heal potion":
            for it in bag.items:
                if str(it.get("name", "")).lower() == "potion":
                    return it
        return None

    def _use_heal_potion(self) -> bool:
        bag = self._get_bag()
        if not bag:
            return False
        it = self._find_item(bag, "Heal Potion")
        if not it or it.get("count", 0) <= 0:
            self._set_message("No Heal Potion!")
            return False

        if self.player_mon["hp"] >= self.player_mon["max_hp"]:
            self._set_message("HP already full!")
            return False

        heal_amount = 25
        self.player_mon["hp"] = min(self.player_mon["max_hp"], self.player_mon["hp"] + heal_amount)
        it["count"] -= 1
        self._set_message(f"Used Heal Potion (+{heal_amount} HP)")
        return True

    def _use_strength_potion(self) -> bool:
        bag = self._get_bag()
        if not bag:
            return False
        it = self._find_item(bag, "Strength Potion")
        if not it or it.get("count", 0) <= 0:
            self._set_message("No Strength Potion!")
            return False

        inc = 3
        self.player_mon["atk_buff"] += inc
        it["count"] -= 1
        self._set_message(f"Used Strength Potion (+{inc} ATK)")
        return True

    def _use_defense_potion(self) -> bool:
        bag = self._get_bag()
        if not bag:
            return False
        it = self._find_item(bag, "Defense Potion")
        if not it or it.get("count", 0) <= 0:
            self._set_message("No Defense Potion!")
            return False

        inc = 2
        self.player_mon["def_buff"] += inc
        it["count"] -= 1
        self._set_message(f"Used Defense Potion (+{inc} DEF)")
        return True

    # evolution
    def try_evolve(self, mon: dict):
        """
        Evolution rule:
        - if mon["level"] >= mon["evolve_level"] and mon has "evolve_to_sprite_path"
        - change sprite_path + boost stats + heal to full
        """
        if mon.get("evolved"):
            return

        evo_lv = mon.get("evolve_level")
        evo_sprite = mon.get("evolve_to_sprite_path")
        if evo_lv is None or evo_sprite is None:
            return

        if int(mon.get("level", 1)) < int(evo_lv):
            return

        # evolve
        mon["evolved"] = True
        mon["sprite_path"] = evo_sprite

        # stat boost (tunable)
        mon["max_hp"] = max(mon["max_hp"] + 10, int(mon["max_hp"] * 1.3))
        mon["atk"] = max(mon["atk"] + 3, int(mon["atk"] * 1.3))
        mon["def"] = max(mon["def"] + 2, int(mon["def"] * 1.2))
        mon["hp"] = mon["max_hp"]

        self._set_message(f"{mon.get('name','Pokemon')} evolved!")

        # reload player sprite immediately
        try:
            self.player_sprite = pg.transform.scale(
                pg.transform.flip(pg.image.load(mon["sprite_path"]).convert_alpha(), True, False),
                (160, 160)
            )
        except Exception:
            # if asset missing, at least don't crash
            pass

    # entry
    def start_battle(self, enemy_mon):
        game_scene = scene_manager._scenes.get("game")

        # player monster (first one)
        self.player_mon = game_scene.game_manager.bag._monsters_data[0]

        # enemy monster (copy)
        self.enemy_mon = copy.deepcopy(enemy_mon)
        if "level" not in self.enemy_mon:
            self.enemy_mon["level"] = random.randint(5, 15)

        # ensure stats / element / buffs
        self._ensure_stats(self.player_mon, is_enemy=False)
        self._ensure_stats(self.enemy_mon, is_enemy=True)

        # sprites
        self.player_sprite = pg.transform.scale(
            pg.transform.flip(pg.image.load(self.player_mon["sprite_path"]).convert_alpha(), True, False),
            (160, 160)
        )
        enemy_img = pg.image.load(self.enemy_mon["sprite_path"]).convert_alpha()
        self.enemy_sprite = pg.transform.scale(enemy_img, (160, 160))

        self.pending_enemy_action = False
        self.state = "player_turn"
        self._set_message("A wild enemy appeared!", 1.0)

    # update
    @override
    def update(self, dt: float):
        if self.state == "idle":
            return

        # message timer
        if self.message_timer > 0:
            self.message_timer -= dt
            if self.message_timer <= 0:
                self.message = ""

        # win/lose: timer then back to game
        if self.state in ("win", "lose"):
            self.end_timer -= dt
            if self.end_timer <= 0:
                scene_manager.change_scene("game")
            return

        # animations
        if self.state == "player_attack_anim":
            self.anim_timer -= dt
            if self.anim_timer <= 0:
                dmg = self.calc_damage(self.player_mon, self.enemy_mon, base=5)
                mult = self.element_multiplier(self.player_mon["element"], self.enemy_mon["element"])
                self.enemy_mon["hp"] -= dmg

                if mult > 1.0:
                    self._set_message(f"It's super effective! (-{dmg})")
                elif mult < 1.0:
                    self._set_message(f"It's not very effective... (-{dmg})")
                else:
                    self._set_message(f"Hit! (-{dmg})")

                if self.enemy_mon["hp"] <= 0:
                    self.enemy_mon["hp"] = 0

                    # level up + evolution attempt (player)
                    self.player_mon["level"] = int(self.player_mon.get("level", 1)) + 1
                    self.try_evolve(self.player_mon)

                    self.state = "win"
                    self.end_timer = 0.8
                else:
                    self.anim_timer = 0.5
                    self.state = "enemy_attack_anim"
            return

        if self.state == "enemy_attack_anim":
            self.anim_timer -= dt
            if self.anim_timer <= 0:
                dmg = self.calc_damage(self.enemy_mon, self.player_mon, base=5)
                mult = self.element_multiplier(self.enemy_mon["element"], self.player_mon["element"])
                self.player_mon["hp"] -= dmg

                if mult > 1.0:
                    self._set_message(f"Enemy: super effective! (-{dmg})")
                elif mult < 1.0:
                    self._set_message(f"Enemy: not very effective... (-{dmg})")
                else:
                    self._set_message(f"Enemy hit! (-{dmg})")

                if self.player_mon["hp"] <= 0:
                    self.player_mon["hp"] = 0
                    self.state = "lose"
                    self.end_timer = 0.8
                else:
                    self.state = "player_turn"
            return

        # input states
        if self.state == "player_turn":
            if input_manager.mouse_pressed(1):
                mx, my = input_manager.mouse_pos

                # Fight: one basic attack (element + buffs handled in calc_damage)
                if self.buttons["fight"].collidepoint(mx, my):
                    if self.enemy_mon["hp"] <= 0:
                        self.enemy_mon["hp"] = 0
                        self.state = "win"
                        self.end_timer = 0.8
                        return
                    self.anim_timer = 0.5
                    self._set_message(f"{self.player_mon['name']} attacks!")
                    self.state = "player_attack_anim"
                    return

                # Item: open item menu
                if self.buttons["item"].collidepoint(mx, my):
                    self.state = "item_menu"
                    return

                # Switch: for now just skip turn (still counts as an action)
                if self.buttons["switch"].collidepoint(mx, my):
                    self._set_message("You hesitated...")
                    self.anim_timer = 0.5
                    self.state = "enemy_attack_anim"
                    return

                # Run: leave battle
                if self.buttons["run"].collidepoint(mx, my):
                    scene_manager.change_scene("game")
                    return

        elif self.state == "item_menu":
            if input_manager.mouse_pressed(1):
                mx, my = input_manager.mouse_pos

                used = False
                if self.item_buttons["heal"].collidepoint(mx, my):
                    used = self._use_heal_potion()
                elif self.item_buttons["strength"].collidepoint(mx, my):
                    used = self._use_strength_potion()
                elif self.item_buttons["defense"].collidepoint(mx, my):
                    used = self._use_defense_potion()
                elif self.item_buttons["back"].collidepoint(mx, my):
                    self.state = "player_turn"
                    return

                # if used item : end player action, enemy attacks
                if used:
                    self.anim_timer = 0.5
                    self.state = "enemy_attack_anim"
                else:
                    # stay in item_menu if not used (no item / hp full etc.)
                    pass

    # drawing
    def draw_hp_bar(self, screen, x, y, current, max_hp):
        bar_w = 200
        bar_h = 12
        ratio = 0 if max_hp <= 0 else max(0.0, min(1.0, current / max_hp))

        pg.draw.rect(screen, (40, 40, 40), (x, y, bar_w, bar_h))
        pg.draw.rect(screen, (0, 200, 0), (x, y, int(bar_w * ratio), bar_h))

    @override
    def draw(self, screen: pg.Surface):
        # background
        bg_scaled = pg.transform.scale(self.bg, (1280, 720))
        screen.blit(bg_scaled, (0, 0))

        # element icon (top-left)
        screen.blit(self.element_icon, (20, 20))


        # debug state
        debug = self.font_small.render(f"STATE = {self.state}", True, (255, 0, 0))
        screen.blit(debug, (20, 150))

        # enemy sprite (top-right)
        enemy_x, enemy_y = 760, 160
        screen.blit(self.enemy_sprite, (enemy_x, enemy_y))

        # enemy UI
        ui_w, ui_h = 320, 92
        ui_x, ui_y = 770, 90
        pg.draw.rect(screen, (255, 255, 255), (ui_x, ui_y, ui_w, ui_h))
        pg.draw.rect(screen, (0, 0, 0), (ui_x, ui_y, ui_w, ui_h), 3)

        name = self.font_mid.render(self.enemy_mon["name"], True, (0, 0, 0))
        level = self.font_mid.render(f"Lv.{self.enemy_mon['level']}", True, (0, 0, 0))
        elem = self.font_small.render(f"{self.enemy_mon.get('element','Normal')}", True, (0, 0, 0))

        screen.blit(name, (ui_x + 15, ui_y + 8))
        screen.blit(level, (ui_x + 240, ui_y + 8))
        screen.blit(elem, (ui_x + 15, ui_y + 36))

        self.draw_hp_bar(screen, ui_x + 15, ui_y + 62, self.enemy_mon["hp"], self.enemy_mon["max_hp"])

        # player sprite (bottom-left)
        player_x, player_y = 400, 320
        screen.blit(self.player_sprite, (player_x, player_y))

        # player UI
        ui2_x, ui2_y = 80, 420
        ui2_w, ui2_h = 320, 105
        pg.draw.rect(screen, (255, 255, 255), (ui2_x, ui2_y, ui2_w, ui2_h))
        pg.draw.rect(screen, (0, 0, 0), (ui2_x, ui2_y, ui2_w, ui2_h), 3)

        name2 = self.font_mid.render(self.player_mon["name"], True, (0, 0, 0))
        level2 = self.font_mid.render(f"Lv.{self.player_mon['level']}", True, (0, 0, 0))
        elem2 = self.font_small.render(f"{self.player_mon.get('element','Normal')}", True, (0, 0, 0))

        # show buffs
        atk_b = int(self.player_mon.get("atk_buff", 0))
        def_b = int(self.player_mon.get("def_buff", 0))
        buffs = self.font_small.render(f"ATK+{atk_b} DEF+{def_b}", True, (0, 0, 0))

        screen.blit(name2, (ui2_x + 15, ui2_y + 8))
        screen.blit(level2, (ui2_x + 240, ui2_y + 8))
        screen.blit(elem2, (ui2_x + 15, ui2_y + 36))
        screen.blit(buffs, (ui2_x + 15, ui2_y + 58))

        self.draw_hp_bar(screen, ui2_x + 15, ui2_y + 86, self.player_mon["hp"], self.player_mon["max_hp"])

        # command box
        pg.draw.rect(screen, (20, 20, 20), (0, 520, 1280, 200))

        # prompt / message
        if self.message:
            prompt_text = self.message
        else:
            prompt_text = "What will You do?"  # keep your original text
        prompt = self.font_big.render(prompt_text, True, (255, 255, 255))
        screen.blit(prompt, (50, 550))

        # draw buttons
        base_y = 620
        button_gap = 200
        start_x = 180

        if self.state != "item_menu":
            # main 4 buttons
            for i, (name, rect) in enumerate(self.buttons.items()):
                rect.x = start_x + i * button_gap
                rect.y = base_y
                pg.draw.rect(screen, (240, 240, 240), rect)
                pg.draw.rect(screen, (0, 0, 0), rect, 2)
                text = self.font_mid.render(name.capitalize(), True, (0, 0, 0))
                screen.blit(text, (rect.x + 18, rect.y + 5))
        else:
            # item menu buttons
            # place them nicely
            self.item_buttons["heal"].x, self.item_buttons["heal"].y = 120, 610
            self.item_buttons["strength"].x, self.item_buttons["strength"].y = 390, 610
            self.item_buttons["defense"].x, self.item_buttons["defense"].y = 720, 610
            self.item_buttons["back"].x, self.item_buttons["back"].y = 120, 660

            labels = {
                "heal": "Heal Potion",
                "strength": "Strength Potion",
                "defense": "Defense Potion",
                "back": "Back",
            }

            for key, rect in self.item_buttons.items():
                pg.draw.rect(screen, (240, 240, 240), rect)
                pg.draw.rect(screen, (0, 0, 0), rect, 2)
                text = self.font_small.render(labels[key], True, (0, 0, 0))
                screen.blit(text, (rect.x + 10, rect.y + 10))

