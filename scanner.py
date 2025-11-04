#!/usr/bin/env python3
"""
Media file scanner and metadata extraction.
Handles video file discovery, parsing with GuessIt, and grouping.
"""

import os
import json
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, asdict
from typing import Literal
from multiprocessing import Pool, cpu_count
import click
from guessit import guessit  # type: ignore[import-untyped]

# Type alias for unified media key
MediaKey = tuple[Literal["episode", "movie"], str, int | None, int | None, int | None]


def normalize_title(title: str) -> str:
    """
    Normalize a title for consistent comparison.
    - Convert to lowercase
    - Remove apostrophes
    - Remove periods
    - Remove extra whitespace
    """
    normalized = title.lower()
    # Remove apostrophes (both straight and curly)
    normalized = normalized.replace("'", "").replace("’", "")
    # Remove periods
    normalized = normalized.replace(".", "")
    # Normalize whitespace
    normalized = " ".join(normalized.split())
    return normalized


@dataclass
class MediaMetadata:
    """Container for media file metadata extracted by guessit."""

    filepath: Path
    type: Literal["episode", "movie"]
    title: str
    year: int | None = None
    season: int | None = None
    episode: int | None = None
    episode_title: str | None = None

    # Additional metadata fields
    screen_size: str | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    release_group: str | None = None
    container: str | None = None
    file_size_mb: float = 0.0

    @property
    def is_episode(self) -> bool:
        """Check if this is a TV episode."""
        return self.type == "episode"

    @property
    def is_movie(self) -> bool:
        """Check if this is a movie."""
        return self.type == "movie"

    @property
    def media_key(self) -> MediaKey | None:
        """
        Get the unified key for this media (works for both series and movies).
        Format: (type, title, season, episode, year)
        - Series: ("episode", title, season, episode, None)
        - Movies: ("movie", title, None, None, year)
        """
        if (
            self.is_episode
            and self.title
            and self.season is not None
            and self.episode is not None
        ):
            return (
                "episode",
                normalize_title(self.title),
                self.season,
                self.episode,
                None,
            )
        elif self.is_movie and self.title:
            return ("movie", normalize_title(self.title), None, None, self.year)
        return None


# Common video file extensions
VIDEO_EXTENSIONS = {
    ".mkv",
    ".mp4",
    ".avi",
    ".mov",
    ".wmv",
    ".flv",
    ".webm",
    ".m4v",
    ".mpg",
    ".mpeg",
    ".m2ts",
    ".ts",
    ".vob",
    ".ogv",
}


def is_video_file(filepath: Path) -> bool:
    """Check if a file is a video file based on extension."""
    return filepath.suffix.lower() in VIDEO_EXTENSIONS


def get_video_files(directory: Path) -> list[Path]:
    """Recursively find all video files in a directory."""
    video_files = []

    if not directory.exists():
        return video_files

    if not directory.is_dir():
        return video_files

    for root, _dirs, files in os.walk(directory):
        for file in files:
            filepath = Path(root) / file
            if is_video_file(filepath):
                video_files.append(filepath)

    return video_files


def parse_video_file(filepath: Path) -> MediaMetadata | None:
    """
    Parse a video file using guessit and return metadata.
    Returns: MediaMetadata object or None if parsing fails
    """
    try:
        # Get file size in MB
        file_size_mb = filepath.stat().st_size / (1024 * 1024)

        guess = guessit(str(filepath))

        # Extract common fields
        type = guess.get("type")
        title = guess.get("title")
        year = guess.get("year")
        season = guess.get("season")
        episode = guess.get("episode")
        episode_title = guess.get("episode_title")

        # Handle title as list (alternative titles)
        if isinstance(title, list):
            title = title[0] if title else None

        # Skip if no title
        if not title:
            return None

        # Handle season as list
        if isinstance(season, list):
            season = season[0] if season else None

        # Handle episode as list (e.g., S01E01-E02)
        if isinstance(episode, list):
            episode = episode[0] if episode else None

        # Handle episode_title as list
        if isinstance(episode_title, list):
            episode_title = episode_title[0] if episode_title else None

        # Handle year as list (rare but possible)
        if isinstance(year, list):
            year = year[0] if year else None

        # Extract additional metadata
        screen_size = guess.get("screen_size")
        video_codec = guess.get("video_codec")
        audio_codec = guess.get("audio_codec")
        release_group = guess.get("release_group")
        container = guess.get("container")

        # Convert to strings where needed
        if isinstance(screen_size, list):
            screen_size = screen_size[0] if screen_size else None
        if isinstance(video_codec, list):
            video_codec = video_codec[0] if video_codec else None
        if isinstance(audio_codec, list):
            audio_codec = audio_codec[0] if audio_codec else None
        if isinstance(release_group, list):
            release_group = release_group[0] if release_group else None
        if isinstance(container, list):
            container = container[0] if container else None

        # Ensure types are correct
        year_int = int(year) if year is not None else None
        season_int = int(season) if season is not None else None
        episode_int = int(episode) if episode is not None else None

        return MediaMetadata(
            filepath=filepath,
            type=type,
            title=str(title),
            year=year_int,
            season=season_int,
            episode=episode_int,
            episode_title=str(episode_title) if episode_title else None,
            screen_size=str(screen_size) if screen_size else None,
            video_codec=str(video_codec) if video_codec else None,
            audio_codec=str(audio_codec) if audio_codec else None,
            release_group=str(release_group) if release_group else None,
            container=str(container) if container else None,
            file_size_mb=file_size_mb,
        )
    except Exception:
        return None


def parse_directory(
    directory: Path, max_workers: int | None = None
) -> list[MediaMetadata]:
    """
    Parse all video files in a directory.

    Args:
        directory: Directory to scan for video files
        max_workers: Maximum number of worker processes (defaults to CPU count)

    Returns: List of MediaMetadata objects
    """
    video_files = get_video_files(directory)

    # Collect all parsed metadata
    media_list: list[MediaMetadata] = []

    # Use all CPUs if not specified
    workers = max_workers or cpu_count()

    with click.progressbar(length=len(video_files), label="Parsing video files") as bar:
        with Pool(processes=workers) as pool:
            # imap_unordered processes items as they complete (faster than ordered)
            for metadata in pool.imap_unordered(
                parse_video_file, video_files, chunksize=10
            ):
                if metadata and metadata.media_key:
                    media_list.append(metadata)
                bar.update(1)

    return media_list


def find_duplicates(media_list: list[MediaMetadata]) -> list[MediaMetadata]:
    """
    Filter a media list to only include duplicates (items with more than one file for the same media key).
    Returns: List with only metadata items that have duplicates
    """
    # Group by media key
    by_key: dict[MediaKey, list[MediaMetadata]] = defaultdict(list)
    for metadata in media_list:
        if metadata.media_key:
            by_key[metadata.media_key].append(metadata)

    # Return only items that have duplicates
    result = []
    for metadata_list in by_key.values():
        if len(metadata_list) > 1:
            result.extend(metadata_list)

    return result


def save_scan_results(media_list: list[MediaMetadata], filepath: Path) -> None:
    """
    Save scan results to a JSON file.

    Args:
        media_list: List of media metadata to save
        filepath: Path to save the JSON file
    """
    # Serialize metadata to list of dicts
    all_metadata = []
    for metadata in media_list:
        # Serialize dataclass to dict
        metadata_dict = asdict(metadata)
        # Convert Path to string
        metadata_dict["filepath"] = str(metadata.filepath)
        all_metadata.append(metadata_dict)

    data = {"version": "1.0", "media": all_metadata}

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)


def load_scan_results(filepath: Path) -> list[MediaMetadata]:
    """
    Load scan results from a JSON file.

    Args:
        filepath: Path to the JSON file

    Returns: List of MediaMetadata objects
    """
    with open(filepath, "r") as f:
        data = json.load(f)

    media_list: list[MediaMetadata] = []

    for meta_data in data["media"]:
        # Reconstruct MediaMetadata from serialized dict
        meta_data["filepath"] = Path(meta_data["filepath"])
        metadata = MediaMetadata(**meta_data)

        if metadata.media_key:
            media_list.append(metadata)

    return media_list
