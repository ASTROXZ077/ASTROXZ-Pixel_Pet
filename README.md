# Pixel Pet for Windows

A self-contained animated desktop companion built with Python and PySide6. It procedurally draws its own pixel art, so the project does not require external image assets.

## Included

- Idle, walking, sleeping, happy, and surprised states
- Random movement along the bottom of the screen
- Crisp procedural pixel-art character
- Drag the pet with the left mouse button
- Double-click to play
- Right-click for controls
- System tray menu
- Pause/resume movement
- Always-on-top toggle
- Four color themes: violet, ocean, sunset, and mint
- Optional CPU/RAM display
- Saved position and settings
- Multi-monitor-aware placement
- Optional start-with-Windows launcher
- Windows DPI awareness
- Persistent hidden life memory in `%APPDATA%\\PixelPet\\memory.json`
- Time-of-day behavior: morning, afternoon, evening, and night
- Gradual personality drift based on play, quiet time, screens, themes, and night activity
- Gentle return recognition after time away
- Sleep progression: sleepy, sitting, sleeping, and dreaming
- Rare mystery moments with tiny visual effects
- Subtle long-term visual evolution without game-like unlocks
- Non-repeating, mood-aware speech with quiet periods
- No hunger, health, death, punishment, or maintenance pressure

## Install

Open PowerShell in this folder and run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Run

```powershell
python main.py
```

The pet will appear near the bottom-right of the current screen. Right-click the pet or its tray icon for controls. Double-click the pet to play.

## Build a Windows executable

```powershell
pip install pyinstaller
pyinstaller --noconsole --onefile --name PixelPet main.py
```

The executable will be in `dist\PixelPet.exe`.

## Notes

- Settings are stored in `%APPDATA%\PixelPet\settings.json`.
- The Start with Windows option creates `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\PixelPet.cmd`.
- If you want the pet below normal application windows, disable Always on top in the tray menu.
- To add custom art later, replace `PixelPainter.draw_pet()` with a sprite-sheet loader while keeping the behavior system unchanged.
