import pygame as pg
from src.utils import load_sound, GameSettings

class SoundManager:
    def __init__(self):
        pg.mixer.init()
        pg.mixer.set_num_channels(GameSettings.MAX_CHANNELS)
        self.current_bgm = None

        self.volume = GameSettings.AUDIO_VOLUME
        
    def play_bgm(self, filepath: str):
        if self.current_bgm:
            self.current_bgm.stop()
        audio = load_sound(filepath)
        audio.set_volume(self.volume)      # ← 使用我們的 volume
        audio.play(-1)
        self.current_bgm = audio
        
    def set_bgm_volume(self, vol: float):
        """調整背景音樂音量（0~1）"""
        self.volume = max(0.0, min(1.0, vol))
        if self.current_bgm:
            self.current_bgm.set_volume(self.volume)

    def get_bgm_volume(self):
        """取得目前背景音量"""
        return self.volume

    def pause_all(self):
        pg.mixer.pause()

    def resume_all(self):
        pg.mixer.unpause()
        
    def play_sound(self, filepath, volume=0.7):
        sound = load_sound(filepath)
        sound.set_volume(volume)
        sound.play()

    def stop_all_sounds(self):
        pg.mixer.stop()
        self.current_bgm = None