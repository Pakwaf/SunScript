"""Configuration and localization manager for SunScript.

Handles loading and saving user preferences (language, default margins, FPS,
and color-to-keyword mappings) to `config.json`, as well as loading localized
UI strings from `src/locales/<lang>.json`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

# Project root directory (parent of src/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOCALES_DIR = Path(__file__).resolve().parent / "locales"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.json"

DEFAULT_COLOR_KEYWORDS: Dict[str, str] = {
    "Red": "fail, death, bug, error, mort, erreur, crash",
    "Green": "win, success, clutch, gg, victoire, réussi, boss",
    "Blue": "info, lore, note, question, histoire, astuce, tip",
    "Yellow": "funny, lol, laugh, highlight, drôle, rire, best",
    "Cyan": "intro, outro, start, end, début, fin, pause",
    "Magenta": "epic, insane, clip, wow, incroyable, fou",
    "Orange": "warning, careful, cut, edit, attention, couper",
    "Purple": "music, audio, sound, song, musique, son",
}

DEFAULT_CONFIG: Dict[str, Any] = {
    "language": "en",
    "margin_before": 3.0,
    "margin_after": 3.0,
    "fps": 30,
    "color_keywords": DEFAULT_COLOR_KEYWORDS.copy(),
}


class ConfigManager:
    """Manages persistent application settings and localization bundles."""

    def __init__(self, config_path: Path | str = DEFAULT_CONFIG_PATH) -> None:
        """Initialize the ConfigManager and load existing or default settings.

        Args:
            config_path: Path to the JSON configuration file.
        """
        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = self._load_or_create()
        self.locales: Dict[str, Dict[str, str]] = self._load_locales()

    def _load_or_create(self) -> Dict[str, Any]:
        """Load configuration from disk, merging with defaults if keys are missing."""
        merged: Dict[str, Any] = {
            "language": DEFAULT_CONFIG["language"],
            "margin_before": DEFAULT_CONFIG["margin_before"],
            "margin_after": DEFAULT_CONFIG["margin_after"],
            "fps": DEFAULT_CONFIG["fps"],
            "color_keywords": DEFAULT_COLOR_KEYWORDS.copy(),
        }

        if self.config_path.exists():
            try:
                with self.config_path.open("r", encoding="utf-8") as file:
                    loaded = json.load(file)
                if isinstance(loaded, dict):
                    if loaded.get("language") in ("en", "fr"):
                        merged["language"] = loaded["language"]
                    for num_key in ("margin_before", "margin_after", "fps"):
                        if num_key in loaded:
                            try:
                                merged[num_key] = float(loaded[num_key]) if num_key != "fps" else int(float(loaded[num_key]))
                            except (ValueError, TypeError):
                                pass
                    if isinstance(loaded.get("color_keywords"), dict):
                        for color, kw_str in loaded["color_keywords"].items():
                            if isinstance(kw_str, str):
                                merged["color_keywords"][color] = kw_str
                            elif isinstance(kw_str, list):
                                merged["color_keywords"][color] = ", ".join(str(x) for x in kw_str)
            except (OSError, json.JSONDecodeError):
                pass

        self._write_config(merged)
        return merged

    def _write_config(self, data: Dict[str, Any]) -> None:
        """Write configuration dictionary to `config.json`."""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with self.config_path.open("w", encoding="utf-8") as file:
                json.dump(data, file, indent=2, ensure_ascii=False)
        except OSError:
            pass

    def _load_locales(self) -> Dict[str, Dict[str, str]]:
        """Load English and French locale JSON files from `src/locales/`."""
        bundles: Dict[str, Dict[str, str]] = {"en": {}, "fr": {}}
        for lang in ("en", "fr"):
            locale_file = LOCALES_DIR / f"{lang}.json"
            if locale_file.exists():
                try:
                    with locale_file.open("r", encoding="utf-8") as file:
                        bundles[lang] = json.load(file)
                except (OSError, json.JSONDecodeError):
                    bundles[lang] = {}
        return bundles

    def save(self) -> None:
        """Persist current configuration state to `config.json`."""
        self._write_config(self.config)

    @property
    def language(self) -> str:
        """Return the active language code ('en' or 'fr')."""
        return str(self.config.get("language", "en"))

    @language.setter
    def language(self, lang: str) -> None:
        """Set and persist the active language code."""
        normalized = lang.lower().strip()
        if normalized in ("en", "fr"):
            self.config["language"] = normalized
            self.save()

    @property
    def color_keywords(self) -> Dict[str, str]:
        """Return the dictionary mapping color names to comma-separated keywords."""
        return dict(self.config.get("color_keywords", DEFAULT_COLOR_KEYWORDS))

    def update_color_keywords(self, mapping: Dict[str, str]) -> None:
        """Update the color-to-keyword mapping and auto-save to `config.json`."""
        if "color_keywords" not in self.config or not isinstance(self.config["color_keywords"], dict):
            self.config["color_keywords"] = {}
        for color, keywords in mapping.items():
            self.config["color_keywords"][color] = keywords.strip()
        self.save()

    def update_margins(self, before: float, after: float, fps: int = 30) -> None:
        """Update and persist margin and FPS preferences."""
        self.config["margin_before"] = float(before)
        self.config["margin_after"] = float(after)
        self.config["fps"] = int(fps)
        self.save()

    def translate(self, key: str, **kwargs: Any) -> str:
        """Retrieve a localized UI string for the current language.

        Args:
            key: Translation key in the locale JSON file.
            **kwargs: Optional format placeholders.

        Returns:
            Localized and formatted string.
        """
        lang_bundle = self.locales.get(self.language, {})
        fallback_bundle = self.locales.get("en", {})
        template = lang_bundle.get(key, fallback_bundle.get(key, key))
        if kwargs:
            try:
                return template.format(**kwargs)
            except (KeyError, ValueError):
                return template
        return template
