"""Main entry point and CustomTkinter GUI for SunScript.

Provides a modern dark desktop interface featuring:
- Bilingual UI toggle (English / French)
- Video file selector
- Margin (before/after handles in seconds) and FPS inputs
- VOD Transcript editor with sample loader
- Side panel mapping FCP7 marker colors to comma-separated keyword families
  with automatic persistence to `config.json`
- Graceful error handling and status reporting
"""

from __future__ import annotations

from pathlib import Path
import sys
from tkinter import filedialog, messagebox
from typing import Dict

import customtkinter as ctk

# Ensure local imports work whether executed via `python src/main.py` or `python -m src.main`
SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config_manager import DEFAULT_COLOR_KEYWORDS, ConfigManager  # noqa: E402
from engine import SunScriptEngine  # noqa: E402

COLOR_SWATCH_HEX: Dict[str, str] = {
    "Red": "#D63031",
    "Green": "#2ECC71",
    "Blue": "#3498DB",
    "Yellow": "#F1C40F",
    "Cyan": "#1ABC9C",
    "Magenta": "#E84393",
    "Orange": "#E67E22",
    "Purple": "#9B59B6",
}


class SunScriptApp(ctk.CTk):
    """Main CustomTkinter application window for SunScript."""

    def __init__(self) -> None:
        """Initialize the GUI, load configuration, and build all widgets."""
        super().__init__()

        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.config_mgr = ConfigManager()
        self.color_entries: Dict[str, ctk.CTkEntry] = {}
        self.color_labels: Dict[str, ctk.CTkLabel] = {}

        self.title(self.config_mgr.translate("app_title"))
        self.geometry("1120x740")
        self.minsize(920, 620)

        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_left_workspace()
        self._build_right_settings_panel()
        self._build_status_bar()
        self._refresh_ui_texts()

    def _build_header(self) -> None:
        """Build the top bar containing the application title and EN/FR language switcher."""
        self.header_frame = ctk.CTkFrame(self, corner_radius=10)
        self.header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=16, pady=(14, 8))
        self.header_frame.grid_columnconfigure(0, weight=1)

        title_box = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        title_box.grid(row=0, column=0, sticky="w", padx=14, pady=10)

        self.title_label = ctk.CTkLabel(
            title_box,
            text="SunScript",
            font=ctk.CTkFont(size=22, weight="bold"),
        )
        self.title_label.pack(anchor="w")

        self.subtitle_label = ctk.CTkLabel(
            title_box,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=("gray30", "gray70"),
        )
        self.subtitle_label.pack(anchor="w")

        lang_box = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        lang_box.grid(row=0, column=1, sticky="e", padx=14, pady=10)

        self.lang_label = ctk.CTkLabel(lang_box, text="", font=ctk.CTkFont(size=13, weight="bold"))
        self.lang_label.pack(side="left", padx=(0, 8))

        self.lang_switch = ctk.CTkSegmentedButton(
            lang_box,
            values=["EN", "FR"],
            command=self._on_language_change,
            width=100,
        )
        self.lang_switch.set(self.config_mgr.language.upper())
        self.lang_switch.pack(side="left")

    def _build_left_workspace(self) -> None:
        """Build the main left panel: video picker, margin inputs, transcript box, and generate button."""
        self.left_frame = ctk.CTkFrame(self, corner_radius=10)
        self.left_frame.grid(row=1, column=0, sticky="nsew", padx=(16, 8), pady=8)
        self.left_frame.grid_columnconfigure(0, weight=1)
        self.left_frame.grid_rowconfigure(5, weight=1)

        # 1. Source Video Section
        self.video_section_label = ctk.CTkLabel(
            self.left_frame,
            text="",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.video_section_label.grid(row=0, column=0, sticky="w", padx=14, pady=(12, 4))

        video_row = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        video_row.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))
        video_row.grid_columnconfigure(0, weight=1)

        self.video_entry = ctk.CTkEntry(video_row, height=34)
        self.video_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.browse_btn = ctk.CTkButton(
            video_row,
            text="",
            width=120,
            height=34,
            command=self._on_browse_video,
        )
        self.browse_btn.grid(row=0, column=1, sticky="e")

        # 2. Margins & Sequence Settings
        self.margins_section_label = ctk.CTkLabel(
            self.left_frame,
            text="",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.margins_section_label.grid(row=2, column=0, sticky="w", padx=14, pady=(4, 4))

        margins_row = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        margins_row.grid(row=3, column=0, sticky="ew", padx=14, pady=(0, 10))

        self.margin_before_label = ctk.CTkLabel(margins_row, text="")
        self.margin_before_label.grid(row=0, column=0, sticky="w", padx=(0, 6))

        self.margin_before_entry = ctk.CTkEntry(margins_row, width=75)
        self.margin_before_entry.insert(0, str(self.config_mgr.config.get("margin_before", 3.0)))
        self.margin_before_entry.grid(row=0, column=1, sticky="w", padx=(0, 18))
        self.margin_before_entry.bind("<FocusOut>", self._on_settings_modified)

        self.margin_after_label = ctk.CTkLabel(margins_row, text="")
        self.margin_after_label.grid(row=0, column=2, sticky="w", padx=(0, 6))

        self.margin_after_entry = ctk.CTkEntry(margins_row, width=75)
        self.margin_after_entry.insert(0, str(self.config_mgr.config.get("margin_after", 3.0)))
        self.margin_after_entry.grid(row=0, column=3, sticky="w", padx=(0, 18))
        self.margin_after_entry.bind("<FocusOut>", self._on_settings_modified)

        self.fps_label = ctk.CTkLabel(margins_row, text="")
        self.fps_label.grid(row=0, column=4, sticky="w", padx=(0, 6))

        self.fps_entry = ctk.CTkEntry(margins_row, width=65)
        self.fps_entry.insert(0, str(self.config_mgr.config.get("fps", 30)))
        self.fps_entry.grid(row=0, column=5, sticky="w")
        self.fps_entry.bind("<FocusOut>", self._on_settings_modified)

        # 3. Transcript Header & Helper Buttons
        transcript_header = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        transcript_header.grid(row=4, column=0, sticky="ew", padx=14, pady=(4, 4))
        transcript_header.grid_columnconfigure(0, weight=1)

        self.transcript_section_label = ctk.CTkLabel(
            transcript_header,
            text="",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.transcript_section_label.grid(row=0, column=0, sticky="w")

        self.load_sample_btn = ctk.CTkButton(
            transcript_header,
            text="",
            width=110,
            height=26,
            fg_color=("gray70", "gray28"),
            hover_color=("gray60", "gray35"),
            command=self._on_load_sample,
        )
        self.load_sample_btn.grid(row=0, column=1, padx=(0, 6))

        self.clear_btn = ctk.CTkButton(
            transcript_header,
            text="",
            width=80,
            height=26,
            fg_color=("gray70", "gray28"),
            hover_color=("gray60", "gray35"),
            command=self._on_clear_transcript,
        )
        self.clear_btn.grid(row=0, column=2)

        # Transcript Textbox
        self.transcript_textbox = ctk.CTkTextbox(
            self.left_frame,
            font=ctk.CTkFont(family="Consolas", size=13),
            wrap="word",
        )
        self.transcript_textbox.grid(row=5, column=0, sticky="nsew", padx=14, pady=(4, 12))

        # Generate Button
        self.generate_btn = ctk.CTkButton(
            self.left_frame,
            text="",
            height=44,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            command=self._on_generate_xml,
        )
        self.generate_btn.grid(row=6, column=0, sticky="ew", padx=14, pady=(0, 14))

    def _build_right_settings_panel(self) -> None:
        """Build the side panel for mapping marker colors to comma-separated keyword lists."""
        self.right_frame = ctk.CTkFrame(self, corner_radius=10)
        self.right_frame.grid(row=1, column=1, sticky="nsew", padx=(8, 16), pady=8)
        self.right_frame.grid_columnconfigure(0, weight=1)
        self.right_frame.grid_rowconfigure(2, weight=1)

        self.settings_title_label = ctk.CTkLabel(
            self.right_frame,
            text="",
            font=ctk.CTkFont(size=15, weight="bold"),
        )
        self.settings_title_label.grid(row=0, column=0, sticky="w", padx=14, pady=(12, 2))

        self.settings_subtitle_label = ctk.CTkLabel(
            self.right_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=("gray30", "gray70"),
            wraplength=360,
            justify="left",
        )
        self.settings_subtitle_label.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 8))

        self.colors_scroll = ctk.CTkScrollableFrame(self.right_frame, fg_color="transparent")
        self.colors_scroll.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 12))
        self.colors_scroll.grid_columnconfigure(1, weight=1)

        current_keywords = self.config_mgr.color_keywords
        for row_idx, color_key in enumerate(DEFAULT_COLOR_KEYWORDS.keys()):
            swatch_hex = COLOR_SWATCH_HEX.get(color_key, "#FFFFFF")

            badge_frame = ctk.CTkFrame(self.colors_scroll, fg_color="transparent")
            badge_frame.grid(row=row_idx * 2, column=0, columnspan=2, sticky="ew", padx=6, pady=(6, 2))

            swatch = ctk.CTkFrame(
                badge_frame,
                width=14,
                height=14,
                corner_radius=7,
                fg_color=swatch_hex,
            )
            swatch.pack(side="left", padx=(0, 8))

            lbl = ctk.CTkLabel(
                badge_frame,
                text=color_key,
                font=ctk.CTkFont(size=13, weight="bold"),
            )
            lbl.pack(side="left")
            self.color_labels[color_key] = lbl

            entry = ctk.CTkEntry(self.colors_scroll, height=32)
            entry.insert(0, current_keywords.get(color_key, ""))
            entry.grid(row=row_idx * 2 + 1, column=0, columnspan=2, sticky="ew", padx=6, pady=(0, 6))
            entry.bind("<KeyRelease>", self._on_keyword_entry_changed)
            entry.bind("<FocusOut>", self._on_keyword_entry_changed)
            self.color_entries[color_key] = entry

    def _build_status_bar(self) -> None:
        """Build the bottom status bar displaying application feedback."""
        self.status_frame = ctk.CTkFrame(self, height=32, corner_radius=8)
        self.status_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=16, pady=(4, 12))

        self.status_label = ctk.CTkLabel(
            self.status_frame,
            text="",
            font=ctk.CTkFont(size=12),
            anchor="w",
        )
        self.status_label.pack(fill="x", padx=12, pady=4)

    def _refresh_ui_texts(self) -> None:
        """Update all visible labels, placeholders, and buttons to the active language."""
        t = self.config_mgr.translate
        self.title(t("app_title"))
        self.subtitle_label.configure(text=t("header_subtitle"))
        self.lang_label.configure(text=t("lang_toggle_label"))

        self.video_section_label.configure(text=t("video_section_title"))
        self.video_entry.configure(placeholder_text=t("video_placeholder"))
        self.browse_btn.configure(text=t("browse_btn"))

        self.margins_section_label.configure(text=t("margins_section_title"))
        self.margin_before_label.configure(text=t("margin_before_label"))
        self.margin_after_label.configure(text=t("margin_after_label"))
        self.fps_label.configure(text=t("fps_label"))

        self.transcript_section_label.configure(text=t("transcript_section_title"))
        self.load_sample_btn.configure(text=t("load_sample_btn"))
        self.clear_btn.configure(text=t("clear_btn"))
        self.generate_btn.configure(text=t("generate_btn"))

        self.settings_title_label.configure(text=t("settings_section_title"))
        self.settings_subtitle_label.configure(text=t("settings_subtitle"))

        for color_key, label_widget in self.color_labels.items():
            label_widget.configure(text=t(f"color_{color_key}"))

        self.status_label.configure(text=t("status_ready"))

    def _on_language_change(self, selected_value: str) -> None:
        """Handle language toggle between English and French."""
        self.config_mgr.language = selected_value.lower()
        self._refresh_ui_texts()

    def _on_browse_video(self) -> None:
        """Open file dialog to choose a source video file."""
        file_path = filedialog.askopenfilename(
            title=self.config_mgr.translate("video_section_title"),
            filetypes=[
                ("Video Files", "*.mp4 *.mov *.mkv *.avi *.mxf *.webm *.m4v"),
                ("All Files", "*.*"),
            ],
        )
        if file_path:
            self.video_entry.delete(0, "end")
            self.video_entry.insert(0, file_path)

    def _on_load_sample(self) -> None:
        """Populate the transcript textbox with sample timestamped events."""
        sample_text = self.config_mgr.translate("transcript_placeholder")
        self.transcript_textbox.delete("1.0", "end")
        self.transcript_textbox.insert("1.0", sample_text)

    def _on_clear_transcript(self) -> None:
        """Clear the transcript text area."""
        self.transcript_textbox.delete("1.0", "end")

    def _on_keyword_entry_changed(self, _event: object = None) -> None:
        """Auto-save color-to-keyword mappings whenever an entry changes."""
        updated_mapping = {
            color: entry.get().strip() for color, entry in self.color_entries.items()
        }
        self.config_mgr.update_color_keywords(updated_mapping)
        self.status_label.configure(text=self.config_mgr.translate("status_saved_config"))

    def _on_settings_modified(self, _event: object = None) -> None:
        """Persist margin and FPS changes when focus leaves the input boxes."""
        try:
            before = float(self.margin_before_entry.get().strip())
            after = float(self.margin_after_entry.get().strip())
            fps = int(float(self.fps_entry.get().strip()))
            if before >= 0 and after >= 0 and fps > 0:
                self.config_mgr.update_margins(before, after, fps)
        except ValueError:
            pass

    def _on_generate_xml(self) -> None:
        """Validate user inputs, invoke `SunScriptEngine.generate_fcp7_xml`, and report status."""
        t = self.config_mgr.translate

        # Save latest keyword entries first
        self._on_keyword_entry_changed()

        video_str = self.video_entry.get().strip()
        if not video_str or not Path(video_str).expanduser().is_file():
            messagebox.showerror(t("error_title"), t("err_no_video"))
            return

        try:
            margin_before = float(self.margin_before_entry.get().strip())
            margin_after = float(self.margin_after_entry.get().strip())
            fps = int(float(self.fps_entry.get().strip()))
            if margin_before < 0 or margin_after < 0 or fps <= 0:
                raise ValueError("Negative margin or non-positive FPS")
        except ValueError:
            messagebox.showerror(t("error_title"), t("err_invalid_margins"))
            return

        self.config_mgr.update_margins(margin_before, margin_after, fps)

        transcript_text = self.transcript_textbox.get("1.0", "end").strip()
        if not transcript_text:
            messagebox.showerror(t("error_title"), t("err_empty_transcript"))
            return

        try:
            result = SunScriptEngine.generate_fcp7_xml(
                video_path=video_str,
                transcript_text=transcript_text,
                margin_before=margin_before,
                margin_after=margin_after,
                color_keywords=self.config_mgr.color_keywords,
                fps=fps,
            )
        except ValueError:
            messagebox.showerror(t("error_title"), t("err_no_valid_lines"))
            return
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(t("error_title"), t("err_generation_failed", error=str(exc)))
            return

        success_msg = t(
            "status_success",
            path=str(result.output_path),
            clips=result.merged_clips_count,
            markers=result.markers_count,
        )
        self.status_label.configure(text=success_msg)
        messagebox.showinfo(t("success_title"), success_msg)


def main() -> None:
    """Launch the SunScript desktop application."""
    app = SunScriptApp()
    app.mainloop()


if __name__ == "__main__":
    main()
