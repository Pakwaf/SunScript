# SunScript

**English** | [Français](#français)

## English

**SunScript** is a modern desktop application built with Python and CustomTkinter that converts VOD transcripts (`timecode - description`) into **FCP7 XML** (`xmeml` version 4/5) sequences compatible with FilmCraft, Adobe Premiere Pro, DaVinci Resolve, and Final Cut Pro.

### Features
- **Transcript to Timeline**: Parses line-by-line timecodes (`HH:MM:SS`, `MM:SS`, or `HH:MM:SS:FF`) and descriptions.
- **Configurable Handles (Margins)**: Automatically adds padding (before and after) in seconds around each event.
- **Smart Collision Merging**: Mathematically merges overlapping subclips to guarantee a clean, conflict-free timeline while preserving individual markers.
- **Keyword-Based Color Markers**: Uses word-boundary regular expressions (`\b`) to match keywords in descriptions and assign FCP7 marker colors (Red, Green, Blue, Yellow, Cyan, Magenta, Orange, Purple, White).
- **Bilingual Interface**: Instant toggle between English (`EN`) and French (`FR`).
- **Auto-Saved Configuration**: Automatically persists language and color-keyword mappings to `config.json`.

### Installation & Usage
```bash
pip install -r requirements.txt
python src/main.py
```

---

## Français

**SunScript** est une application de bureau moderne développée en Python avec CustomTkinter permettant de convertir des transcriptions de VOD (`timecode - description`) en séquences **FCP7 XML** (`xmeml`), compatibles avec FilmCraft, Adobe Premiere Pro, DaVinci Resolve et Final Cut Pro.

### Fonctionnalités
- **Transcription vers Timeline** : Analyse ligne par ligne les timecodes (`HH:MM:SS`, `MM:SS` ou `HH:MM:SS:FF`) et leurs descriptions.
- **Marges Configurables (Handles)** : Ajoute automatiquement des marges (avant et après, en secondes) autour de chaque moment clé.
- **Fusion Intelligente des Collisions** : Fusionne mathématiquement les clips qui se chevauchent pour éviter tout conflit sur la timeline tout en conservant les marqueurs individuels.
- **Marqueurs de Couleur par Mots-Clés** : Utilise des expressions régulières avec limites de mots (`\b`) pour associer les descriptions aux couleurs de marqueurs FCP7 (Rouge, Vert, Bleu, Jaune, Cyan, Magenta, Orange, Violet, Blanc).
- **Interface Bilingue** : Bascule instantanée entre le Français (`FR`) et l'Anglais (`EN`).
- **Sauvegarde Automatique** : Enregistre automatiquement la langue et les familles de mots-clés par couleur dans `config.json`.

### Installation et Utilisation
```bash
pip install -r requirements.txt
python src/main.py
```
