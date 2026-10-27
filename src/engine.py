"""Core FCP7 XML generation, regex keyword matching, and clip collision engine.

This module implements:
1. Transcript line parsing (`timecode - description`).
2. Pre-compiled Regex matching with word boundaries (`\\b`) for marker colors.
3. Margin (handle) application and mathematical merging of overlapping clips.
4. FCP7 XML (`<xmeml version="4">`) generation with `<sequence>`, `<media>`,
   `<clipitem>`, and `<marker>` elements compatible with FilmCraft and NLEs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Dict, List, Pattern, Tuple
from urllib.parse import quote
import xml.etree.ElementTree as ET
from xml.dom import minidom

# RGBA 8-bit values (0-255) for FCP7 XML <color> tags inside <marker>
FCP7_MARKER_COLORS: Dict[str, Tuple[int, int, int, int]] = {
    "Red": (214, 48, 49, 255),
    "Green": (46, 204, 113, 255),
    "Blue": (52, 152, 219, 255),
    "Yellow": (241, 196, 15, 255),
    "Cyan": (26, 188, 156, 255),
    "Magenta": (232, 67, 147, 255),
    "Orange": (230, 126, 34, 255),
    "Purple": (155, 89, 182, 255),
    "White": (255, 255, 255, 255),
}

DEFAULT_NEUTRAL_COLOR = "White"

# Matches lines like:
# "01:23:45 - Boss fight" or "12:34 - Funny moment" or "00:01:05:12 - Frame accurate"
# Also supports en-dash, em-dash, or colon/whitespace separators.
LINE_PATTERN = re.compile(
    r"^\s*\[?(?P<tc>\d{1,2}:\d{2}(?::\d{2}(?:[:.]\d{1,3})?)?)\]?\s*(?:[-–—:|]\s*|\s+)(?P<desc>.+?)\s*$"
)


@dataclass
class TranscriptEvent:
    """Represents a single timestamped event extracted from the VOD transcript."""

    timestamp_seconds: float
    description: str
    color_name: str = DEFAULT_NEUTRAL_COLOR
    start_seconds: float = 0.0
    end_seconds: float = 0.0


@dataclass
class MergedClip:
    """Represents a mathematically merged subclip on the timeline."""

    in_seconds: float
    out_seconds: float
    events: List[TranscriptEvent] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        """Return the clip duration in seconds."""
        return max(0.0, self.out_seconds - self.in_seconds)


@dataclass
class GenerationResult:
    """Summary returned after generating an FCP7 XML sequence."""

    output_path: Path
    merged_clips_count: int
    markers_count: int


class SunScriptEngine:
    """Engine for parsing VOD transcripts and generating FCP7 XML sequences."""

    @staticmethod
    def compile_color_regexes(color_keywords: Dict[str, str]) -> Dict[str, Pattern[str]]:
        """Pre-compile one word-boundary regex (`\\b`) per marker color.

        Compiled once per XML generation run to ensure optimal performance.

        Args:
            color_keywords: Mapping of color name to comma-separated keyword strings.

        Returns:
            Dictionary mapping color names to compiled case-insensitive `re.Pattern` objects.
        """
        compiled: Dict[str, Pattern[str]] = {}
        for color, raw_keywords in color_keywords.items():
            if not raw_keywords or not raw_keywords.strip():
                continue
            tokens = [
                re.escape(token.strip())
                for token in raw_keywords.split(",")
                if token.strip()
            ]
            if not tokens:
                continue
            pattern_str = r"\b(?:" + "|".join(tokens) + r")\b"
            compiled[color] = re.compile(pattern_str, re.IGNORECASE)
        return compiled

    @staticmethod
    def match_marker_color(
        description: str,
        compiled_regexes: Dict[str, Pattern[str]],
        default_color: str = DEFAULT_NEUTRAL_COLOR,
    ) -> str:
        """Determine the marker color for a transcript description.

        Args:
            description: Event text description.
            compiled_regexes: Pre-compiled word-boundary regexes keyed by color.
            default_color: Neutral fallback color when no keyword matches (White).

        Returns:
            Matched color name or `default_color`.
        """
        for color, regex in compiled_regexes.items():
            if regex.search(description):
                return color
        return default_color

    @staticmethod
    def parse_timecode_to_seconds(timecode_str: str, fps: int = 30) -> float:
        """Convert a timecode string (`MM:SS`, `HH:MM:SS`, or `HH:MM:SS:FF`) to seconds.

        Args:
            timecode_str: Raw timecode string.
            fps: Sequence frame rate used if frame digits are present.

        Returns:
            Time in seconds as a float.

        Raises:
            ValueError: If the timecode format or numeric values are invalid.
        """
        clean = timecode_str.strip()
        if not clean:
            raise ValueError("Empty timecode string.")

        # Support millisecond dot notation e.g. 00:01:23.500
        ms_fraction = 0.0
        if "." in clean:
            clean, ms_part = clean.split(".", 1)
            ms_fraction = float(f"0.{ms_part}")

        parts = [int(p) for p in clean.split(":")]
        if len(parts) == 2:
            minutes, seconds = parts
            hours, frames = 0, 0
        elif len(parts) == 3:
            hours, minutes, seconds = parts
            frames = 0
        elif len(parts) == 4:
            hours, minutes, seconds, frames = parts
        else:
            raise ValueError(f"Unsupported timecode format: {timecode_str}")

        if minutes < 0 or seconds < 0 or hours < 0 or frames < 0:
            raise ValueError(f"Negative values in timecode: {timecode_str}")

        total_seconds = (
            hours * 3600.0
            + minutes * 60.0
            + seconds
            + (frames / float(max(1, fps)))
            + ms_fraction
        )
        return total_seconds

    @classmethod
    def parse_transcript(
        cls,
        transcript_text: str,
        color_keywords: Dict[str, str],
        margin_before: float,
        margin_after: float,
        fps: int = 30,
    ) -> List[TranscriptEvent]:
        """Parse raw transcript lines, apply handles, and assign marker colors.

        Args:
            transcript_text: Multiline transcript string (`timecode - description`).
            color_keywords: Mapping of color names to comma-separated keywords.
            margin_before: Handle in seconds to subtract before the timestamp.
            margin_after: Handle in seconds to add after the timestamp.
            fps: Frame rate for parsing frame-level timecodes.

        Returns:
            Chronologically sorted list of `TranscriptEvent` objects.
        """
        compiled_regexes = cls.compile_color_regexes(color_keywords)
        events: List[TranscriptEvent] = []

        # Minimum clip duration if both margins are 0
        effective_after = margin_after if (margin_before + margin_after) > 0 else 1.0

        for raw_line in transcript_text.splitlines():
            stripped = raw_line.strip()
            if not stripped:
                continue
            match = LINE_PATTERN.match(stripped)
            if not match:
                continue

            tc_raw = match.group("tc")
            desc = match.group("desc").strip()
            if not desc:
                continue

            ts_sec = cls.parse_timecode_to_seconds(tc_raw, fps=fps)
            start_sec = max(0.0, ts_sec - max(0.0, margin_before))
            end_sec = max(start_sec + 0.1, ts_sec + max(0.0, effective_after))
            color = cls.match_marker_color(desc, compiled_regexes)

            events.append(
                TranscriptEvent(
                    timestamp_seconds=ts_sec,
                    description=desc,
                    color_name=color,
                    start_seconds=start_sec,
                    end_seconds=end_sec,
                )
            )

        events.sort(key=lambda ev: (ev.start_seconds, ev.timestamp_seconds))
        return events

    @staticmethod
    def merge_overlapping_events(events: List[TranscriptEvent]) -> List[MergedClip]:
        """Mathematically merge overlapping or adjacent clips to prevent collisions.

        If clip B starts before or at the exact moment clip A ends
        (`B.start_seconds <= A.out_seconds`), they are merged into a single
        contiguous `MergedClip` spanning `[min(in), max(out)]` and preserving
        all constituent markers.

        Args:
            events: List of `TranscriptEvent` items.

        Returns:
            List of non-overlapping `MergedClip` instances sorted chronologically.
        """
        if not events:
            return []

        sorted_events = sorted(events, key=lambda e: (e.start_seconds, e.end_seconds))
        merged: List[MergedClip] = [
            MergedClip(
                in_seconds=sorted_events[0].start_seconds,
                out_seconds=sorted_events[0].end_seconds,
                events=[sorted_events[0]],
            )
        ]

        for event in sorted_events[1:]:
            current = merged[-1]
            if event.start_seconds <= current.out_seconds:
                current.out_seconds = max(current.out_seconds, event.end_seconds)
                current.events.append(event)
            else:
                merged.append(
                    MergedClip(
                        in_seconds=event.start_seconds,
                        out_seconds=event.end_seconds,
                        events=[event],
                    )
                )

        return merged

    @staticmethod
    def path_to_fcp7_pathurl(file_path: Path) -> str:
        """Convert a local filesystem path into an FCP7-compatible `file://localhost/...` URI."""
        resolved = file_path.resolve().as_posix()
        if not resolved.startswith("/"):
            # Windows drive path e.g. C:/Users/...
            encoded = quote(resolved, safe="/:")
            return f"file://localhost/{encoded}"
        encoded = quote(resolved, safe="/")
        return f"file://localhost{encoded}"

    @classmethod
    def build_fcp7_xml_ElementTree(
        cls,
        video_path: Path,
        merged_clips: List[MergedClip],
        fps: int = 30,
    ) -> ET.Element:
        """Construct the FCP7 XML (`<xmeml version="4">`) ElementTree hierarchy.

        Includes `<sequence>`, `<rate>`, `<media>`, `<video>`, `<audio>`,
        `<track>`, `<clipitem>`, `<file>`, and colored `<marker>` tags.

        Args:
            video_path: Path to the source video file.
            merged_clips: Non-overlapping merged clips containing marker events.
            fps: Sequence timebase in frames per second.

        Returns:
            Root `<xmeml>` `xml.etree.ElementTree.Element`.
        """
        fps = max(1, int(fps))
        xmeml = ET.Element("xmeml", version="4")
        sequence = ET.SubElement(xmeml, "sequence", id="sequence-1")
        ET.SubElement(sequence, "name").text = f"{video_path.stem}_SunScript"

        # Calculate total timeline frames
        total_timeline_frames = sum(
            max(1, int(round(clip.out_seconds * fps)) - int(round(clip.in_seconds * fps)))
            for clip in merged_clips
        )
        ET.SubElement(sequence, "duration").text = str(total_timeline_frames)

        seq_rate = ET.SubElement(sequence, "rate")
        ET.SubElement(seq_rate, "timebase").text = str(fps)
        ET.SubElement(seq_rate, "ntsc").text = "FALSE"

        timecode_el = ET.SubElement(sequence, "timecode")
        tc_rate = ET.SubElement(timecode_el, "rate")
        ET.SubElement(tc_rate, "timebase").text = str(fps)
        ET.SubElement(tc_rate, "ntsc").text = "FALSE"
        ET.SubElement(timecode_el, "string").text = "00:00:00:00"
        ET.SubElement(timecode_el, "frame").text = "0"
        ET.SubElement(timecode_el, "displayformat").text = "NDF"

        media = ET.SubElement(sequence, "media")
        video_el = ET.SubElement(media, "video")

        # Video format characteristics
        v_format = ET.SubElement(video_el, "format")
        v_sc = ET.SubElement(v_format, "samplecharacteristics")
        v_sc_rate = ET.SubElement(v_sc, "rate")
        ET.SubElement(v_sc_rate, "timebase").text = str(fps)
        ET.SubElement(v_sc_rate, "ntsc").text = "FALSE"
        ET.SubElement(v_sc, "width").text = "1920"
        ET.SubElement(v_sc, "height").text = "1080"
        ET.SubElement(v_sc, "anamorphic").text = "FALSE"
        ET.SubElement(v_sc, "pixelaspectratio").text = "square"
        ET.SubElement(v_sc, "fielddominance").text = "none"

        video_track = ET.SubElement(video_el, "track")

        # Estimate source file duration so it covers the highest out point
        max_out_frames = max(
            (int(round(c.out_seconds * fps)) for c in merged_clips),
            default=total_timeline_frames,
        )
        source_duration_frames = max(max_out_frames + fps * 60, total_timeline_frames)
        file_id = "file-1"
        pathurl = cls.path_to_fcp7_pathurl(video_path)

        timeline_cursor = 0
        for idx, clip in enumerate(merged_clips, start=1):
            in_frame = int(round(clip.in_seconds * fps))
            out_frame = max(in_frame + 1, int(round(clip.out_seconds * fps)))
            clip_duration = out_frame - in_frame

            start_frame = timeline_cursor
            end_frame = timeline_cursor + clip_duration
            timeline_cursor = end_frame

            clipitem = ET.SubElement(video_track, "clipitem", id=f"clipitem-{idx}")
            ET.SubElement(clipitem, "masterclipid").text = "masterclip-1"
            ET.SubElement(clipitem, "name").text = video_path.name
            ET.SubElement(clipitem, "enabled").text = "TRUE"
            ET.SubElement(clipitem, "duration").text = str(source_duration_frames)

            clip_rate = ET.SubElement(clipitem, "rate")
            ET.SubElement(clip_rate, "timebase").text = str(fps)
            ET.SubElement(clip_rate, "ntsc").text = "FALSE"

            ET.SubElement(clipitem, "start").text = str(start_frame)
            ET.SubElement(clipitem, "end").text = str(end_frame)
            ET.SubElement(clipitem, "in").text = str(in_frame)
            ET.SubElement(clipitem, "out").text = str(out_frame)

            if idx == 1:
                file_el = ET.SubElement(clipitem, "file", id=file_id)
                ET.SubElement(file_el, "name").text = video_path.name
                ET.SubElement(file_el, "pathurl").text = pathurl
                file_rate = ET.SubElement(file_el, "rate")
                ET.SubElement(file_rate, "timebase").text = str(fps)
                ET.SubElement(file_rate, "ntsc").text = "FALSE"
                ET.SubElement(file_el, "duration").text = str(source_duration_frames)
                file_media = ET.SubElement(file_el, "media")
                file_video = ET.SubElement(file_media, "video")
                file_v_sc = ET.SubElement(file_video, "samplecharacteristics")
                file_v_rate = ET.SubElement(file_v_sc, "rate")
                ET.SubElement(file_v_rate, "timebase").text = str(fps)
                ET.SubElement(file_v_rate, "ntsc").text = "FALSE"
                ET.SubElement(file_v_sc, "width").text = "1920"
                ET.SubElement(file_v_sc, "height").text = "1080"
                file_audio = ET.SubElement(file_media, "audio")
                file_a_sc = ET.SubElement(file_audio, "samplecharacteristics")
                ET.SubElement(file_a_sc, "depth").text = "16"
                ET.SubElement(file_a_sc, "samplerate").text = "48000"
                ET.SubElement(file_audio, "channelcount").text = "2"
            else:
                ET.SubElement(clipitem, "file", id=file_id)

            # Attach markers for each event merged into this clip
            for event in clip.events:
                marker_frame = int(round(event.timestamp_seconds * fps))
                marker_frame = max(in_frame, min(out_frame - 1, marker_frame))

                marker_el = ET.SubElement(clipitem, "marker")
                ET.SubElement(marker_el, "name").text = event.description
                ET.SubElement(marker_el, "comment").text = f"[{event.color_name}] {event.description}"
                ET.SubElement(marker_el, "in").text = str(marker_frame)
                ET.SubElement(marker_el, "out").text = "-1"

                r, g, b, a = FCP7_MARKER_COLORS.get(
                    event.color_name, FCP7_MARKER_COLORS[DEFAULT_NEUTRAL_COLOR]
                )
                color_el = ET.SubElement(marker_el, "color")
                ET.SubElement(color_el, "alpha").text = str(a)
                ET.SubElement(color_el, "red").text = str(r)
                ET.SubElement(color_el, "green").text = str(g)
                ET.SubElement(color_el, "blue").text = str(b)

                # Also attach a sequence-level marker for timeline visibility in all NLEs/FilmCraft
                timeline_marker_frame = start_frame + (marker_frame - in_frame)
                seq_marker = ET.SubElement(sequence, "marker")
                ET.SubElement(seq_marker, "name").text = event.description
                ET.SubElement(seq_marker, "comment").text = f"[{event.color_name}] {event.description}"
                ET.SubElement(seq_marker, "in").text = str(timeline_marker_frame)
                ET.SubElement(seq_marker, "out").text = "-1"
                seq_color = ET.SubElement(seq_marker, "color")
                ET.SubElement(seq_color, "alpha").text = str(a)
                ET.SubElement(seq_color, "red").text = str(r)
                ET.SubElement(seq_color, "green").text = str(g)
                ET.SubElement(seq_color, "blue").text = str(b)

        return xmeml

    @classmethod
    def generate_fcp7_xml(
        cls,
        video_path: str | Path,
        transcript_text: str,
        margin_before: float,
        margin_after: float,
        color_keywords: Dict[str, str],
        fps: int = 30,
    ) -> GenerationResult:
        """Full pipeline: parse transcript, merge collisions, and write FCP7 `.xml` file.

        The generated XML file is saved in the exact same directory as `video_path`.

        Args:
            video_path: Path to the source video file.
            transcript_text: Multiline VOD transcript (`timecode - description`).
            margin_before: Seconds of padding before each event.
            margin_after: Seconds of padding after each event.
            color_keywords: Mapping of marker colors to comma-separated keywords.
            fps: Sequence frame rate (default 30).

        Returns:
            `GenerationResult` containing the output `.xml` path and statistics.

        Raises:
            FileNotFoundError: If `video_path` does not exist.
            ValueError: If margins are negative or no valid transcript lines exist.
        """
        resolved_video = Path(video_path).expanduser().resolve()
        if not resolved_video.exists() or not resolved_video.is_file():
            raise FileNotFoundError(f"Video file not found: {resolved_video}")

        if margin_before < 0 or margin_after < 0 or fps <= 0:
            raise ValueError("Margins must be non-negative and FPS must be positive.")

        events = cls.parse_transcript(
            transcript_text=transcript_text,
            color_keywords=color_keywords,
            margin_before=margin_before,
            margin_after=margin_after,
            fps=fps,
        )
        if not events:
            raise ValueError("No valid timecode lines found in transcript.")

        merged_clips = cls.merge_overlapping_events(events)
        root_element = cls.build_fcp7_xml_ElementTree(
            video_path=resolved_video,
            merged_clips=merged_clips,
            fps=fps,
        )

        raw_xml_bytes = ET.tostring(root_element, encoding="utf-8")
        pretty_xml = minidom.parseString(raw_xml_bytes).toprettyxml(indent="  ")
        # Remove extra blank lines introduced by minidom and add DOCTYPE xmeml
        lines = [line for line in pretty_xml.splitlines() if line.strip()]
        if lines and lines[0].startswith("<?xml"):
            lines[0] = '<?xml version="1.0" encoding="UTF-8"?>'
            lines.insert(1, "<!DOCTYPE xmeml>")
        formatted_xml = "\n".join(lines) + "\n"

        output_xml_path = resolved_video.with_name(f"{resolved_video.stem}_SunScript.xml")
        output_xml_path.write_text(formatted_xml, encoding="utf-8")

        return GenerationResult(
            output_path=output_xml_path,
            merged_clips_count=len(merged_clips),
            markers_count=len(events),
        )
