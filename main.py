from __future__ import annotations

import ctypes
import json
import os
import random
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    import psutil
except ImportError:
    psutil = None

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget


APP_NAME = "Pixel Pet"
WINDOW_SIZE = QSize(280, 230)
PET_X = 105
PET_Y = 112
PIXEL = 5
CONFIG_DIR = Path(os.getenv("APPDATA", Path.home())) / "PixelPet"
CONFIG_FILE = CONFIG_DIR / "settings.json"
MEMORY_FILE = CONFIG_DIR / "memory.json"
STARTUP_DIR = Path(os.getenv("APPDATA", Path.home())) / r"Microsoft\Windows\Start Menu\Programs\Startup"

PALETTE = {
    "outline": QColor("#19152b"),
    "body": QColor("#8c5cff"),
    "body_light": QColor("#b799ff"),
    "body_dark": QColor("#5934bc"),
    "belly": QColor("#f4d6ff"),
    "eye": QColor("#ffffff"),
    "blush": QColor("#ff8fb3"),
    "accent": QColor("#55e6c1"),
    "bubble": QColor(24, 19, 43, 235),
    "bubble_text": QColor("#ffffff"),
}


@dataclass
class Settings:
    x: int = -1
    y: int = -1
    always_on_top: bool = True
    paused: bool = False
    sound: bool = False
    show_stats: bool = True
    startup: bool = False
    pet_name: str = "Pixel"
    color_theme: str = "violet"


@dataclass
class LifeMemory:
    """Long-term memory. Feelings and traits are intentionally not shown as meters."""

    created_at: str = ""
    last_seen: str = ""
    total_interactions: int = 0
    total_play_count: int = 0
    total_feed_count: int = 0
    total_drag_count: int = 0
    total_active_seconds: float = 0.0
    total_sleep_seconds: float = 0.0
    last_sleep_started: str = ""
    first_play_at: str = ""
    last_play_at: str = ""
    last_feed_at: str = ""
    last_interaction_at: str = ""
    last_morning_greeting: str = ""
    last_mystery_at: str = ""
    mystery_count: int = 0
    screen_visits: int = 0
    last_screen_signature: str = ""
    favorite_theme: str = "violet"
    theme_counts: dict = field(default_factory=dict)
    action_counts: dict = field(default_factory=dict)
    hour_counts: list = field(default_factory=lambda: [0] * 24)
    recent_phrases: list = field(default_factory=list)
    milestones: list = field(default_factory=list)
    # Slow personality drift. These are private state, not a visible game system.
    playfulness: float = 0.50
    energy: float = 0.55
    curiosity: float = 0.50
    calmness: float = 0.50
    night_owl: float = 0.25
    adventurousness: float = 0.35


class JsonStore:
    def __init__(self, path: Path, factory):
        self.path = path
        self.factory = factory
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self):
        try:
            if self.path.exists():
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                allowed = {key: value for key, value in raw.items() if key in self.factory.__dataclass_fields__}
                return self.factory(**allowed)
        except Exception:
            pass
        return self.factory()

    def save(self, value) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(asdict(value), indent=2), encoding="utf-8")


class PixelPainter:
    """Procedurally paints crisp pixel art so Pixel works without external assets."""

    @staticmethod
    def rect(painter: QPainter, x: int, y: int, w: int, h: int, color: QColor) -> None:
        painter.fillRect(x * PIXEL, y * PIXEL, w * PIXEL, h * PIXEL, color)

    @classmethod
    def draw_pet(
        cls,
        painter: QPainter,
        frame: int,
        state: str,
        facing: int,
        theme: str,
        evolution: int = 0,
        mystery: bool = False,
    ) -> None:
        painter.save()
        painter.translate(PET_X, PET_Y)
        if facing < 0:
            painter.scale(-1, 1)
            painter.translate(-24 * PIXEL, 0)

        body = PALETTE["body"]
        light = PALETTE["body_light"]
        dark = PALETTE["body_dark"]
        if theme == "ocean":
            body, light, dark = QColor("#2e9cca"), QColor("#8de7ff"), QColor("#145789")
        elif theme == "sunset":
            body, light, dark = QColor("#ff7657"), QColor("#ffc27d"), QColor("#a83662")
        elif theme == "mint":
            body, light, dark = QColor("#37b889"), QColor("#a9f5c8"), QColor("#1b765f")

        bob = 0
        if state in ("idle", "sitting", "looking"):
            bob = 1 if frame % 10 in (0, 1) else 0
        elif state in ("happy", "playful"):
            bob = -2 if frame % 6 < 3 else 0
        elif state in ("surprised", "curious"):
            bob = -1
        elif state in ("sleeping", "dreaming"):
            bob = 2
        elif state == "sleepy":
            bob = 1 if frame % 18 < 3 else 0

        painter.translate(0, bob * PIXEL)

        painter.setOpacity(0.22)
        cls.rect(painter, 4, 20, 16, 2, QColor("#000000"))
        painter.setOpacity(1.0)

        # Rare visual evolution: a tiny scarf-like band after Pixel has lived with you awhile.
        if evolution >= 2:
            cls.rect(painter, 6, 15, 13, 2, PALETTE["accent"])
            cls.rect(painter, 17, 16, 3, 3, PALETTE["accent"])
        if evolution >= 1:
            cls.rect(painter, 20, 7, 1, 1, QColor("#ffe58a"))

        tail_up = state in ("happy", "playful", "surprised", "curious") or frame % 8 < 3
        cls.rect(painter, 19, 12 if tail_up else 15, 3, 3, dark)
        cls.rect(painter, 21, 10 if tail_up else 14, 2, 3, body)

        cls.rect(painter, 5, 2, 5, 5, PALETTE["outline"])
        cls.rect(painter, 14, 2, 5, 5, PALETTE["outline"])
        cls.rect(painter, 6, 3, 3, 3, body)
        cls.rect(painter, 15, 3, 3, 3, body)
        cls.rect(painter, 7, 3, 2, 2, light)
        cls.rect(painter, 15, 3, 2, 2, light)

        cls.rect(painter, 3, 6, 18, 13, PALETTE["outline"])
        cls.rect(painter, 4, 7, 16, 11, body)
        cls.rect(painter, 5, 8, 14, 5, light)
        cls.rect(painter, 6, 13, 12, 5, body)
        cls.rect(painter, 8, 13, 8, 4, PALETTE["belly"])

        blink = state in ("sleeping", "dreaming") or (state == "sleepy" and frame % 12 < 6)
        if blink:
            cls.rect(painter, 7, 10, 3, 1, PALETTE["outline"])
            cls.rect(painter, 14, 10, 3, 1, PALETTE["outline"])
        elif state == "curious":
            cls.rect(painter, 7, 8, 3, 4, PALETTE["outline"])
            cls.rect(painter, 14, 9, 3, 3, PALETTE["outline"])
            cls.rect(painter, 8, 8, 1, 1, PALETTE["eye"])
            cls.rect(painter, 15, 9, 1, 1, PALETTE["eye"])
        else:
            cls.rect(painter, 7, 9, 3, 3, PALETTE["outline"])
            cls.rect(painter, 14, 9, 3, 3, PALETTE["outline"])
            cls.rect(painter, 8, 9, 1, 1, PALETTE["eye"])
            cls.rect(painter, 15, 9, 1, 1, PALETTE["eye"])

        if state in ("surprised", "curious"):
            cls.rect(painter, 11, 12, 3, 2, PALETTE["outline"])
        elif state in ("happy", "playful"):
            cls.rect(painter, 9, 12, 2, 1, PALETTE["outline"])
            cls.rect(painter, 14, 12, 2, 1, PALETTE["outline"])
        else:
            cls.rect(painter, 11, 12, 3, 1, PALETTE["outline"])

        if state in ("happy", "playful", "idle", "curious"):
            cls.rect(painter, 5, 12, 2, 1, PALETTE["blush"])
            cls.rect(painter, 17, 12, 2, 1, PALETTE["blush"])

        step = 1 if frame % 8 < 4 else 0
        cls.rect(painter, 6, 18 + step, 4, 2, dark)
        cls.rect(painter, 14, 18 + (1 - step), 4, 2, dark)

        if state == "sleepy":
            cls.rect(painter, 20, 5, 1, 2, PALETTE["accent"])
        if state in ("sleeping", "dreaming"):
            cls.rect(painter, 20, 5, 2, 1, PALETTE["accent"])
            cls.rect(painter, 21, 4, 1, 1, PALETTE["accent"])
        if mystery:
            cls.rect(painter, 2, 6 + (frame % 3), 1, 1, PALETTE["accent"])
            cls.rect(painter, 22, 4 + ((frame + 1) % 4), 1, 1, QColor("#ffe58a"))
            cls.rect(painter, 1, 16, 1, 1, QColor("#ffe58a"))

        painter.restore()


class PixelPet(QWidget):
    def __init__(self) -> None:
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        super().__init__(None, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setFixedSize(WINDOW_SIZE)
        self.setAcceptDrops(False)

        self.settings = JsonStore(CONFIG_FILE, Settings).load()
        self.memory = JsonStore(MEMORY_FILE, LifeMemory).load()
        self.boot_time = time.time()
        self.last_checkpoint = self.boot_time
        self.session_awake_seconds = 0.0
        self.last_behavior_time = time.monotonic()
        self.last_stats_time = 0.0
        self.last_daily_drift = self.boot_time
        self.last_screen_check = 0.0
        self.last_morning_check = ""
        self.last_interaction_monotonic = time.monotonic()
        self.last_speech_monotonic = 0.0
        self.state = "idle"
        self.state_until = time.monotonic() + 3
        self.frame = 0
        self.facing = 1
        self.speed = 1.6
        self.drag_offset: Optional[QPoint] = None
        self.dragging = False
        self.bubble = "Hi! I'm Pixel."
        self.bubble_until = time.monotonic() + 5
        self.stats_text = ""
        self.dream_until = 0.0
        self.mystery_until = 0.0
        self.mystery_text = ""
        self.theme_names = ["violet", "ocean", "sunset", "mint"]
        self.store_settings = JsonStore(CONFIG_FILE, Settings)
        self.store_memory = JsonStore(MEMORY_FILE, LifeMemory)

        self.prepare_memory()
        self.setWindowTitle(APP_NAME)
        self.apply_window_flags()
        self.create_tray()
        self.restore_position()
        self.show()
        self.raise_()

        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.tick)
        self.animation_timer.start(85)

        self.behavior_timer = QTimer(self)
        self.behavior_timer.timeout.connect(self.behavior_tick)
        self.behavior_timer.start(1000)

        self.save_timer = QTimer(self)
        self.save_timer.timeout.connect(self.save)
        self.save_timer.start(10000)

    # ---------- memory and personality ----------

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def parse_iso(value: str) -> float:
        try:
            return datetime.fromisoformat(value).timestamp()
        except Exception:
            return 0.0

    @staticmethod
    def phase() -> str:
        hour = time.localtime().tm_hour
        if 5 <= hour < 12:
            return "morning"
        if 12 <= hour < 18:
            return "afternoon"
        if 18 <= hour < 23:
            return "evening"
        return "night"

    @staticmethod
    def date_key() -> str:
        return time.strftime("%Y-%m-%d")

    def prepare_memory(self) -> None:
        now = time.time()
        first_run = not bool(self.memory.created_at)
        previous_seen = self.parse_iso(self.memory.last_seen)
        away_seconds = max(0.0, now - previous_seen) if previous_seen else 0.0
        self.away_seconds = away_seconds
        if first_run:
            self.memory.created_at = self.now_iso()
            self.memory.last_seen = self.now_iso()
            self.welcome_text = "Hi! I'm Pixel."
        else:
            self.welcome_text = self.return_message(away_seconds)
            self.memory.last_seen = self.now_iso()
        self.memory.action_counts.setdefault("launch", 0)
        self.memory.action_counts["launch"] += 1
        self.memory.hour_counts = (self.memory.hour_counts + [0] * 24)[:24]
        self.memory.theme_counts.setdefault(self.settings.color_theme, 0)
        self.memory.theme_counts[self.settings.color_theme] += 1
        self.update_favorite_theme()
        self.last_seen_message()
        self.store_memory.save(self.memory)

    def return_message(self, away_seconds: float) -> str:
        if away_seconds > 3 * 86400:
            return random.choice(["Whoa... it's been a while.", "You came back.", "Pixel remembers you."])
        if away_seconds > 20 * 3600:
            return random.choice(["Good to see you.", "You're back.", "A new day."])
        if away_seconds > 4 * 3600:
            return random.choice(["You're back!", "There you are.", "I was here."])
        if away_seconds > 45 * 60:
            return random.choice(["Hi again.", "Welcome back.", "Oh, hello."])
        return "Hi! I'm Pixel."

    def last_seen_message(self) -> None:
        # The return message is deliberately gentle and occasional. It does not create a need to maintain Pixel.
        self.bubble = self.welcome_text
        self.bubble_until = time.monotonic() + (5 if self.away_seconds > 45 * 60 else 3)

    def evolution_level(self) -> int:
        age_days = max(0.0, (time.time() - self.parse_iso(self.memory.created_at)) / 86400) if self.memory.created_at else 0
        if age_days >= 14 or self.memory.total_interactions >= 100:
            return 3
        if age_days >= 3 or self.memory.total_interactions >= 25:
            return 2
        if age_days >= 1 or self.memory.total_interactions >= 8:
            return 1
        return 0

    def feelings(self) -> dict[str, float]:
        hour = time.localtime().tm_hour
        phase = self.phase()
        base_energy = self.memory.energy
        if phase == "morning":
            time_energy = 0.72
        elif phase == "afternoon":
            time_energy = 0.64
        elif phase == "evening":
            time_energy = 0.45
        else:
            time_energy = 0.20 + self.memory.night_owl * 0.40
        if 1 <= hour <= 4 and self.memory.night_owl < 0.45:
            time_energy -= 0.18
        idle_seconds = max(0.0, time.monotonic() - self.last_interaction_monotonic)
        boredom = min(1.0, idle_seconds / 240.0) * (0.55 + self.memory.playfulness * 0.45)
        loneliness = min(1.0, idle_seconds / 900.0) * 0.45
        energy = max(0.0, min(1.0, base_energy * 0.45 + time_energy * 0.55))
        sleepiness = max(0.0, min(1.0, 1.0 - energy + (0.18 if phase == "night" else 0.0)))
        curiosity = max(0.0, min(1.0, self.memory.curiosity + boredom * 0.12))
        happiness = max(0.0, min(1.0, 0.42 + self.memory.playfulness * 0.22 + (1.0 - loneliness) * 0.18))
        return {
            "energy": energy,
            "sleepiness": sleepiness,
            "boredom": boredom,
            "loneliness": loneliness,
            "curiosity": curiosity,
            "happiness": happiness,
            "calmness": self.memory.calmness,
        }

    def record_interaction(self, action: str) -> None:
        now = time.time()
        hour = time.localtime().tm_hour
        self.memory.total_interactions += 1
        self.memory.action_counts[action] = self.memory.action_counts.get(action, 0) + 1
        self.memory.hour_counts[hour] += 1
        self.memory.last_interaction_at = self.now_iso()
        self.last_interaction_monotonic = time.monotonic()
        self.memory.last_seen = self.now_iso()

        if action == "play":
            self.memory.total_play_count += 1
            self.memory.last_play_at = self.now_iso()
            if not self.memory.first_play_at:
                self.memory.first_play_at = self.now_iso()
            self.memory.playfulness = min(1.0, self.memory.playfulness + 0.006)
            self.memory.energy = min(1.0, self.memory.energy + 0.002)
        elif action == "feed":
            self.memory.total_feed_count += 1
            self.memory.last_feed_at = self.now_iso()
            self.memory.calmness = min(1.0, self.memory.calmness + 0.004)
        elif action == "drag":
            self.memory.total_drag_count += 1
            self.memory.adventurousness = min(1.0, self.memory.adventurousness + 0.008)
        elif action == "theme":
            self.memory.theme_counts[self.settings.color_theme] = self.memory.theme_counts.get(self.settings.color_theme, 0) + 1
            self.update_favorite_theme()

        if self.phase() == "night":
            self.memory.night_owl = min(1.0, self.memory.night_owl + 0.004)
        if self.phase() in ("morning", "afternoon"):
            self.memory.night_owl = max(0.0, self.memory.night_owl - 0.001)
        self.maybe_add_milestones()

    def update_favorite_theme(self) -> None:
        if self.memory.theme_counts:
            self.memory.favorite_theme = max(self.memory.theme_counts, key=self.memory.theme_counts.get)

    def maybe_add_milestones(self) -> None:
        candidates = [
            ("first_play", self.memory.total_play_count >= 1),
            ("old_friend", self.memory.total_interactions >= 100),
            ("frequent_playmate", self.memory.total_play_count >= 50),
            ("night_companion", self.memory.night_owl >= 0.55),
            ("explorer", self.memory.total_drag_count >= 12),
            ("long_lived", self.evolution_level() >= 3),
        ]
        for name, condition in candidates:
            if condition and name not in self.memory.milestones:
                self.memory.milestones.append(name)

    def personality_drift(self) -> None:
        now = time.time()
        if now - self.last_daily_drift < 60:
            return
        self.last_daily_drift = now
        # Tiny drift makes Pixel feel different over days, never instantly.
        phase = self.phase()
        if phase == "night":
            self.memory.night_owl = min(1.0, self.memory.night_owl + 0.0008)
        else:
            self.memory.night_owl = max(0.0, self.memory.night_owl - 0.00015)
        idle = max(0.0, time.monotonic() - self.last_interaction_monotonic)
        if idle > 600:
            self.memory.calmness = min(1.0, self.memory.calmness + 0.0007)
            self.memory.playfulness = max(0.0, self.memory.playfulness - 0.00025)
        else:
            self.memory.playfulness = min(1.0, self.memory.playfulness + 0.00025)
        self.memory.energy = max(0.15, min(0.90, self.memory.energy + random.uniform(-0.001, 0.001)))

    # ---------- behavior ----------

    def choose_behavior(self) -> None:
        now = time.monotonic()
        f = self.feelings()
        phase = self.phase()

        if self.maybe_mystery():
            return

        # Sleep is a progression, not a switch: sleepy -> sitting -> sleeping.
        if f["sleepiness"] > 0.77 and (phase == "night" or f["energy"] < 0.28):
            if self.state not in ("sleepy", "sleeping", "dreaming"):
                self.state = "sleepy"
                self.speed = 0.45
                self.state_until = now + random.uniform(7, 14)
                if random.random() < 0.25:
                    self.say_from(["Getting a little sleepy.", "My eyes feel heavy.", "...yawn..."])
                return
            if self.state == "sleepy":
                self.state = "sitting"
                self.state_until = now + random.uniform(3, 8)
                return
            if self.state == "sitting":
                self.enter_sleep()
                return

        # If Pixel is sleeping, remain asleep until an interaction wakes it.
        if self.state in ("sleeping", "dreaming"):
            if random.random() < 0.035:
                self.state = "dreaming"
                self.dream_until = now + random.uniform(2, 5)
                self.state_until = self.dream_until
            else:
                self.state = "sleeping"
                self.state_until = now + random.uniform(8, 18)
            return

        if phase == "morning" and self.memory.last_morning_greeting != self.date_key():
            self.memory.last_morning_greeting = self.date_key()
            if random.random() < 0.65:
                self.say_from(["Good morning.", "Morning!", "A new day."])
            return

        options: list[tuple[str, float]] = [
            ("idle", 2.0 + f["calmness"] * 3),
            ("sitting", 1.5 + f["calmness"] * 3),
            ("looking", 1.0 + f["curiosity"] * 3),
            ("walking", 1.2 + f["energy"] * 2 + self.memory.adventurousness),
            ("stretching", 0.5 + f["energy"]),
        ]
        if f["boredom"] > 0.42:
            options += [("curious", 1.8), ("walking", 1.3)]
        if self.memory.playfulness > 0.62 and f["energy"] > 0.42:
            options += [("playful", 1.8), ("happy", 1.0)]
        if phase == "evening":
            options += [("sitting", 2.0), ("looking", 1.5)]
        if phase == "night":
            options += [("sitting", 2.5), ("looking", 1.0)]

        state = self.weighted_choice(options)
        self.state = state
        self.facing = random.choice([-1, 1]) if state in ("walking", "curious", "playful") else self.facing
        self.speed = random.choice([0.7, 1.0, 1.4, 1.8, 2.2])
        if state in ("sleepy", "sitting", "stretching"):
            self.speed = 0.4
        duration = random.uniform(2.5, 8.0)
        if state in ("sitting", "looking"):
            duration = random.uniform(3.0, 12.0)
        self.state_until = now + duration

        if state == "stretching" and random.random() < 0.20:
            self.say_from(["Hmm.", "One moment.", "That helped."])
        elif state == "curious" and random.random() < 0.24:
            self.say_from(["What's that?", "I wonder...", "Hmm?"])
        elif state == "playful" and random.random() < 0.17:
            self.say_from(["Catch me!", "Hehe.", "Look at this."])
        elif state == "happy" and random.random() < 0.15:
            self.say_from(["Nice.", "I like this.", "Pixel power."])

    @staticmethod
    def weighted_choice(options: list[tuple[str, float]]) -> str:
        total = sum(weight for _, weight in options)
        pick = random.uniform(0, total)
        running = 0.0
        for name, weight in options:
            running += weight
            if pick <= running:
                return name
        return options[-1][0]

    def enter_sleep(self) -> None:
        self.state = "sleeping"
        self.memory.last_sleep_started = self.now_iso()
        self.state_until = time.monotonic() + random.uniform(15, 35)
        if random.random() < 0.18:
            self.say_from(["Goodnight.", "See you in a little while.", "Zzz..."])

    def maybe_mystery(self) -> bool:
        age_seconds = max(0.0, time.time() - self.parse_iso(self.memory.created_at))
        last = self.parse_iso(self.memory.last_mystery_at)
        cooldown_ok = time.time() - last > 3 * 86400
        eligible = age_seconds > 12 * 3600 and self.memory.total_interactions >= 8 and cooldown_ok
        if not eligible or random.random() > 0.000008:
            return False
        self.memory.last_mystery_at = self.now_iso()
        self.memory.mystery_count += 1
        self.mystery_until = time.monotonic() + random.uniform(5, 10)
        self.state = "curious"
        self.state_until = self.mystery_until
        self.mystery_text = random.choice(["Hmm?", "...", "Did you see that?", "Oh."])
        if random.random() < 0.75:
            self.say(self.mystery_text, 2.8)
        return True

    def tick(self) -> None:
        self.frame += 1
        if self.state in ("sleeping", "dreaming"):
            self.memory.total_sleep_seconds += 0.085
        else:
            self.session_awake_seconds += 0.085
        if self.state in ("walking", "playful") and not self.settings.paused and not self.dragging:
            move_speed = self.speed * (0.45 if self.state == "playful" and self.frame % 10 < 4 else 1.0)
            self.move(self.x() + int(self.facing * move_speed), self.y())
            self.keep_on_screen()
        self.update()

    def behavior_tick(self) -> None:
        now = time.monotonic()
        if self.dragging:
            return
        self.personality_drift()
        self.check_screen_discovery()
        if self.settings.paused:
            self.state = "idle"
            return

        if self.state in ("sleeping", "dreaming"):
            if self.state == "dreaming" and now >= self.dream_until:
                self.state = "sleeping"
            if now >= self.state_until:
                self.state_until = now + random.uniform(8, 20)
                if random.random() < 0.045:
                    self.state = "dreaming"
                    self.dream_until = now + random.uniform(2, 5)
                    self.state_until = self.dream_until
            if self.settings.show_stats and time.time() - self.last_stats_time > 3:
                self.stats_text = self.read_stats()
                self.last_stats_time = time.time()
            return

        if now >= self.state_until:
            self.choose_behavior()
        if self.settings.show_stats and time.time() - self.last_stats_time > 3:
            self.stats_text = self.read_stats()
            self.last_stats_time = time.time()

    def check_screen_discovery(self) -> None:
        now = time.time()
        if now - self.last_screen_check < 5:
            return
        self.last_screen_check = now
        screen = self.current_screen()
        if screen is None:
            return
        area = screen.availableGeometry()
        signature = f"{area.x()}:{area.y()}:{area.width()}:{area.height()}"
        if self.memory.last_screen_signature and signature != self.memory.last_screen_signature:
            self.memory.screen_visits += 1
            self.memory.adventurousness = min(1.0, self.memory.adventurousness + 0.01)
            if random.random() < 0.25:
                self.state = "curious"
                self.state_until = time.monotonic() + 4
                self.say_from(["New place.", "I know this screen.", "Let's look around."])
        self.memory.last_screen_signature = signature

    # ---------- speech and reactions ----------

    def say(self, text: str, seconds: float = 3.5) -> None:
        self.bubble = text
        self.bubble_until = time.monotonic() + seconds
        self.last_speech_monotonic = time.monotonic()
        self.update()

    def say_from(self, phrases: list[str], seconds: float = 3.5) -> None:
        available = [phrase for phrase in phrases if phrase not in self.memory.recent_phrases]
        text = random.choice(available or phrases)
        self.memory.recent_phrases.append(text)
        self.memory.recent_phrases = self.memory.recent_phrases[-12:]
        self.say(text, seconds)

    def wake_from_sleep(self) -> None:
        self.state = "waking"
        self.state_until = time.monotonic() + 1.5
        self.record_interaction("wake")
        self.say_from(["Hmm...?", "Oh, hi.", "I was dreaming."])

    def feed(self) -> None:
        if self.state in ("sleeping", "dreaming"):
            self.wake_from_sleep()
        self.record_interaction("feed")
        self.state = "happy"
        self.state_until = time.monotonic() + 4
        self.say_from(["Yum. Thank you.", "That was nice.", "A thoughtful offering."])

    def play(self) -> None:
        if self.state in ("sleeping", "dreaming"):
            self.wake_from_sleep()
        self.record_interaction("play")
        self.state = "playful"
        self.state_until = time.monotonic() + 6
        self.speed = 2.2
        if self.memory.total_play_count in (25, 50, 100, 250):
            self.say_from(["We do this a lot.", "You always know how to cheer me up.", "I remember this."])
        else:
            self.say_from(["Play time!", "Again!", "Let's go!", "Hehe, yes!"])

    # ---------- desktop and controls ----------

    def apply_window_flags(self) -> None:
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if self.settings.always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        if not self.isVisible():
            self.show()

    def create_tray(self) -> None:
        self.tray = QSystemTrayIcon(self.make_tray_icon(), self)
        self.tray.setToolTip(APP_NAME)
        menu = QMenu()

        self.pause_action = QAction("Pause movement", self)
        self.pause_action.setCheckable(True)
        self.pause_action.setChecked(self.settings.paused)
        self.pause_action.triggered.connect(self.toggle_pause)
        menu.addAction(self.pause_action)

        self.top_action = QAction("Always on top", self)
        self.top_action.setCheckable(True)
        self.top_action.setChecked(self.settings.always_on_top)
        self.top_action.triggered.connect(self.toggle_top)
        menu.addAction(self.top_action)

        stats_action = QAction("Show system stats", self)
        stats_action.setCheckable(True)
        stats_action.setChecked(self.settings.show_stats)
        stats_action.triggered.connect(self.toggle_stats)
        menu.addAction(stats_action)

        theme_menu = menu.addMenu("Change color theme")
        for name in self.theme_names:
            action = QAction(name.title(), self)
            action.triggered.connect(lambda checked=False, value=name: self.change_theme(value))
            theme_menu.addAction(action)

        menu.addSeparator()
        startup_action = QAction("Start with Windows", self)
        startup_action.setCheckable(True)
        startup_action.setChecked(self.settings.startup)
        startup_action.triggered.connect(self.toggle_startup)
        menu.addAction(startup_action)
        self.startup_action = startup_action
        menu.addAction("Feed Pixel", self.feed)
        menu.addAction("Play", self.play)
        menu.addAction("Exit", QApplication.instance().quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.tray_activated)
        self.tray.show()

    def make_tray_icon(self) -> QIcon:
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        colors = {
            "violet": (QColor("#8c5cff"), QColor("#b799ff")),
            "ocean": (QColor("#2e9cca"), QColor("#8de7ff")),
            "sunset": (QColor("#ff7657"), QColor("#ffc27d")),
            "mint": (QColor("#37b889"), QColor("#a9f5c8")),
        }
        body, light = colors.get(self.settings.color_theme, colors["violet"])
        painter.fillRect(7, 9, 18, 15, PALETTE["outline"])
        painter.fillRect(9, 11, 14, 11, body)
        painter.fillRect(11, 12, 10, 4, light)
        painter.fillRect(11, 15, 2, 3, PALETTE["outline"])
        painter.fillRect(19, 15, 2, 3, PALETTE["outline"])
        painter.fillRect(12, 14, 1, 1, PALETTE["eye"])
        painter.fillRect(19, 14, 1, 1, PALETTE["eye"])
        painter.fillRect(15, 18, 3, 1, PALETTE["outline"])
        painter.fillRect(8, 6, 5, 5, PALETTE["outline"])
        painter.fillRect(19, 6, 5, 5, PALETTE["outline"])
        painter.fillRect(10, 7, 2, 2, body)
        painter.fillRect(20, 7, 2, 2, body)
        painter.end()
        return QIcon(pixmap)

    def restore_position(self) -> None:
        if self.settings.x >= 0 and self.settings.y >= 0:
            self.move(self.settings.x, self.settings.y)
        else:
            self.move_to_floor()

    def current_screen(self):
        center = self.frameGeometry().center()
        return QApplication.screenAt(center) or QApplication.primaryScreen()

    def move_to_floor(self) -> None:
        screen = self.current_screen()
        if screen is None:
            return
        area = screen.availableGeometry()
        self.move(max(area.left(), area.right() - self.width() // 2), area.bottom() - self.height() + 1)

    def floor_y(self) -> int:
        screen = self.current_screen()
        return screen.availableGeometry().bottom() - self.height() + 1 if screen else self.y()

    def keep_on_screen(self) -> None:
        screen = self.current_screen()
        if screen is None:
            return
        area = screen.availableGeometry()
        min_x = area.left() - self.width() // 2
        max_x = area.right() - self.width() // 2
        if self.x() <= min_x:
            self.move(min_x, self.floor_y())
            self.facing = 1
        elif self.x() >= max_x:
            self.move(max_x, self.floor_y())
            self.facing = -1
        if abs(self.y() - self.floor_y()) < 20:
            self.move(self.x(), self.floor_y())

    def read_stats(self) -> str:
        if psutil is None:
            return ""
        try:
            return f"CPU {psutil.cpu_percent(interval=None):.0f}%  RAM {psutil.virtual_memory().percent:.0f}%"
        except Exception:
            return ""

    def toggle_pause(self, checked: bool) -> None:
        self.settings.paused = checked
        self.pause_action.setChecked(checked)
        self.say("Paused." if checked else "I'm back!")
        self.save()

    def toggle_top(self, checked: bool) -> None:
        self.settings.always_on_top = checked
        self.apply_window_flags()
        self.top_action.setChecked(checked)
        self.save()

    def toggle_stats(self, checked: bool) -> None:
        self.settings.show_stats = checked
        self.save()
        self.update()

    def change_theme(self, theme: str) -> None:
        self.settings.color_theme = theme
        self.record_interaction("theme")
        self.tray.setIcon(self.make_tray_icon())
        self.say_from([f"{theme.title()} feels good.", "I like this one.", "A different mood."])
        self.save()

    def toggle_startup(self, checked: bool) -> None:
        self.settings.startup = checked
        try:
            STARTUP_DIR.mkdir(parents=True, exist_ok=True)
            launcher = STARTUP_DIR / "PixelPet.cmd"
            if checked:
                target = Path(sys.executable).resolve()
                script = Path(__file__).resolve()
                launcher.write_text(f'@echo off\nstart "" "{target}" "{script}"\n', encoding="utf-8")
            elif launcher.exists():
                launcher.unlink()
        except Exception:
            self.settings.startup = False
            self.startup_action.setChecked(False)
            self.say("Startup permission failed.")
        self.save()

    def tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.showNormal()
            self.raise_()
            self.activateWindow()
            self.record_interaction("tray")
            self.say_from(["Here I am!", "There you are.", "Hi again."])

    # ---------- mouse, rendering, persistence ----------

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self.state in ("sleeping", "dreaming"):
                self.wake_from_sleep()
            self.record_interaction("click")
            self.dragging = True
            self.drag_offset = event.position().toPoint()
            self.state = "surprised"
            self.say_from(["Wheee!", "Oh!", "Hello."] , 1.8)
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            self.record_interaction("menu")
            self.open_context_menu(event.globalPosition().toPoint())
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self.dragging and self.drag_offset is not None:
            self.move(event.globalPosition().toPoint() - self.drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            self.drag_offset = None
            self.record_interaction("drag")
            self.state = "happy"
            self.state_until = time.monotonic() + 2.5
            self.save()
            event.accept()

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.play()
            event.accept()

    def open_context_menu(self, point: QPoint) -> None:
        menu = QMenu(self)
        menu.addAction("Feed Pixel", self.feed)
        menu.addAction("Play", self.play)
        menu.addSeparator()
        pause = menu.addAction("Pause movement", lambda: self.toggle_pause(not self.settings.paused))
        pause.setCheckable(True)
        pause.setChecked(self.settings.paused)
        menu.addAction("Move to screen bottom", self.move_to_floor)
        menu.addSeparator()
        theme_menu = menu.addMenu("Color theme")
        for name in self.theme_names:
            theme_menu.addAction(name.title(), lambda value=name: self.change_theme(value))
        menu.exec(point)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        if time.monotonic() < self.bubble_until:
            self.draw_bubble(painter)
        if self.settings.show_stats and self.stats_text:
            painter.setFont(QFont("Consolas", 8))
            painter.setPen(QPen(QColor("#ded7ff")))
            painter.drawText(12, self.height() - 10, self.stats_text)
        if self.state == "dreaming":
            painter.setPen(QPen(QColor("#c7b9ff"), 2))
            painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            painter.drawText(210, 95 - (self.frame % 10), "z")
            painter.drawText(225, 80 - (self.frame % 7), "Z")
        PixelPainter.draw_pet(
            painter,
            self.frame,
            self.state,
            self.facing,
            self.settings.color_theme,
            self.evolution_level(),
            time.monotonic() < self.mystery_until,
        )
        painter.end()

    def draw_bubble(self, painter: QPainter) -> None:
        text = self.bubble
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Medium))
        metrics = painter.fontMetrics()
        width = min(245, max(100, metrics.horizontalAdvance(text) + 24))
        rect = QRect(8, 10, width, 34)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(PALETTE["bubble"])
        painter.drawRoundedRect(rect, 10, 10)
        painter.drawPolygon([QPoint(42, 44), QPoint(54, 44), QPoint(48, 54)])
        painter.setPen(PALETTE["bubble_text"])
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

    def save(self) -> None:
        now = time.time()
        elapsed = max(0.0, now - self.last_checkpoint)
        self.memory.total_active_seconds += elapsed
        self.last_checkpoint = now
        self.memory.last_seen = self.now_iso()
        self.settings.x = self.x()
        self.settings.y = self.y()
        self.store_settings.save(self.settings)
        self.store_memory.save(self.memory)

    def closeEvent(self, event) -> None:
        self.save()
        self.tray.hide()
        event.accept()


def enable_windows_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def main() -> int:
    enable_windows_dpi_awareness()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")
    PixelPet()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
