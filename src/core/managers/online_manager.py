import requests
import threading
import queue
from src.utils import Logger, GameSettings

POLL_INTERVAL = 0.05

class OnlineManager:
    list_players: list[dict]
    player_id: int
    
    _stop_event: threading.Event
    _fetch_thread: threading.Thread | None
    _send_thread: threading.Thread | None
    _lock: threading.Lock
    _update_queue: queue.Queue
    
    def __init__(self):
        self.base: str = GameSettings.ONLINE_SERVER_URL
        self.player_id = -1
        self.list_players = []

        self._fetch_thread = None
        self._send_thread = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._update_queue = queue.Queue(maxsize=10)
        
        Logger.info("OnlineManager initialized")
        
    def enter(self):
        self.register()
        self.start()
            
    def exit(self):
        self.stop()
        
    def get_list_players(self) -> list[dict]:
        with self._lock:
            return list(self.list_players)

    # ------------------------------------------------------------------
    # Threading and API Calling Below
    # ------------------------------------------------------------------
    def register(self):
        try:
            url = f"{self.base}/register"
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            data = resp.json()
            if resp.status_code == 200:
                self.player_id = data["id"]
                Logger.info(f"OnlineManager registered with id={self.player_id}")
            else:
                Logger.error("Registration failed:", data)
        except Exception as e:
            Logger.warning(f"OnlineManager registration error: {e}")
        return

    def update(self, x: float, y: float, map_name: str) -> bool:
        if self.player_id == -1:
            return False
        
        try:
            self._update_queue.put_nowait({"x": x, "y": y, "map": map_name})
            return True
        except queue.Full:
            return False

    def start(self) -> None:
        if (self._fetch_thread and self._fetch_thread.is_alive()) or \
           (self._send_thread and self._send_thread.is_alive()):
            return
        
        self._stop_event.clear()
        
        self._fetch_thread = threading.Thread(
            target=self._fetch_loop,
            name="OnlineManagerFetcher",
            daemon=True
        )
        self._fetch_thread.start()
        
        self._send_thread = threading.Thread(
            target=self._send_loop,
            name="OnlineManagerSender",
            daemon=True
        )
        self._send_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._fetch_thread and self._fetch_thread.is_alive():
            self._fetch_thread.join(timeout=2)
        if self._send_thread and self._send_thread.is_alive():
            self._send_thread.join(timeout=2)

    def _fetch_loop(self) -> None:
        while not self._stop_event.wait(POLL_INTERVAL):
            self._fetch_players()
    
    def _send_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                update_data = self._update_queue.get(timeout=0.1)
                self._send_update(update_data)
            except queue.Empty:
                continue
            
    def _send_update(self, update_data: dict) -> None:
        if self.player_id == -1:
            return
        
        url = f"{self.base}/players"
        body = {
            "id": self.player_id,
            "x": update_data["x"],
            "y": update_data["y"],
            "map": update_data["map"]
        }
        
        try:
            resp = requests.post(url, json=body, timeout=5)
            if resp.status_code != 200:
                Logger.warning(f"Update failed: {resp.status_code} {resp.text}")
        except Exception as e:
            Logger.warning(f"Online update error: {e}")
    
    def _fetch_players(self) -> None:
        try:
            url = f"{self.base}/players"
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            all_players = resp.json().get("players", [])

            pid = self.player_id
            filtered = [p for key, p in all_players.items() if int(key) != pid]
            with self._lock:
                self.list_players = filtered
            
        except Exception as e:
            Logger.warning(f"OnlineManager fetch error: {e}")