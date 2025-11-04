# mdupes - Media Duplicates Finder

A Python command-line tool with an interactive TUI to identify and manage duplicate media files in Jellyfin, Plex, or similar media server directory structures.

## Features

- 🔍 **Smart duplicate detection** - Groups files by series/season/episode or movie title/year
- 📺 **TV series support** - Handles complex episode naming with season and episode detection
- 🎬 **Movie support** - Identifies duplicates by title and year
- 🖥️ **Interactive TUI** - ncdu-style tree view with [Textual](https://textual.textualize.io/) framework
- 📊 **Quality comparison** - Shows resolution (720p, 1080p, 4K) and codec (H.264, H.265) for each file
- 📈 **File size tracking** - Displays individual file sizes and total storage per series/movie
- 🎯 **Smart filtering** - Toggle between showing all media or only duplicates
- 🔄 **Multiple sort options** - Sort by name, file count, total size, or duplicate count
- 💾 **Save/load scans** - Cache scan results for instant loading of large libraries
- 🗑️ **File management** - Delete or rename files directly from the TUI
- ⚡ **Parallel processing** - Fast scanning using all CPU cores
- 📁 **Title normalization** - Handles variations like "Marvel's" vs "Marvels", "S.H.I.E.L.D." vs "SHIELD"

## Installation

1. Clone or download this repository
2. Install the required dependencies:

```bash
pip install -r requirements.txt
```

Or install dependencies manually:

```bash
pip install click guessit textual
```

## Usage

### Basic Scanning

Scan a single directory:
```bash
python mdupes.py /path/to/media
```

Scan multiple directories:
```bash
python mdupes.py /path/to/series /path/to/movies
```

Scan with wildcards:
```bash
python mdupes.py /mnt/media/*
```

### Saving and Loading Results

For large media collections, scanning can take time. Save results to reload instantly:

**Save results while scanning:**
```bash
python mdupes.py --save results.json /path/to/media
```

**Load previously saved results:**
```bash
python mdupes.py --load results.json
```

**Short form:**
```bash
# Save
python mdupes.py -s results.json /path/to/media

# Load
python mdupes.py -l results.json
```

## TUI Navigation

### Keyboard Shortcuts

**Navigation:**
- `↑/↓` or `j/k` - Move up/down the tree
- `←` - Collapse current node
- `→` - Expand current node
- `c` - Collapse current node and all children
- `e` - Expand current node and all children

**Actions:**
- `f` - Toggle between "All Media" and "Duplicates Only" view
- `s` - Open sort menu (alphabetic, file count, total size, duplicate count)
- `d` - Delete selected file (with confirmation)
- `r` - Rename selected file
- `m` - Mark/unmark file for deletion
- `Ctrl+D` - Delete all marked files (with confirmation)
- `Ctrl+U` - Unmark all files
- `q` - Quit

**Multi-Select Workflow:**
1. Navigate to a file and press `m` to mark it (shows ✓)
2. Mark additional files as needed
3. Press `Ctrl+D` to delete all marked files at once
4. Use `Ctrl+U` to clear all marks if needed

## Example Display

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Media Duplicates                             Mode: Duplicates Only   ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

▼ 📺 Series (11223 files, 45.2GB) [720p, 1080p, 2160p] [H.264, H.265] 773 duplicates
├── ▼ Breaking Bad (62 files, 52.1GB) [1080p] [H.264, H.265] 5 duplicates
│   ├── ▶ Season 1 (7 files, 5.8GB) [1080p] [H.264]
│   └── ▼ Season 2 (14 files, 11.2GB) [1080p] [H.264, H.265] 1 duplicate
│       ├── ▶ S02E01 - Seven Thirty-Seven (1 file, 800MB) [1080p] [H.264]
│       ├── ▼ S02E02 - Grilled (2 files, 1.6GB) [1080p] [H.264, H.265] 1 duplicate
│       │   ├── Breaking.Bad.S02E02.1080p.BluRay.x264.mkv (1 file, 850MB) [1080p] [H.264]
│       │   └── Breaking.Bad.S02E02.1080p.BluRay.x265.mkv (1 file, 780MB) [1080p] [H.265]
│       └── ▶ S02E03 - Bit by a Dead Bee (1 file, 820MB) [1080p] [H.264]
└── ▼ The Office (201 files, 98.3GB) [720p, 1080p] [H.264] 15 duplicates

▼ 🎬 Movies (150 files, 425.6GB) [720p, 1080p, 2160p] [H.264, H.265] 12 duplicates
└── ▼ Inception (3 files, 12.5GB) [720p, 1080p, 2160p] [H.264, H.265] 2 duplicates
    ├── Inception.2010.720p.BluRay.x264.mkv (1 file, 4.2GB) [720p] [H.264]
    ├── Inception.2010.1080p.BluRay.x264.mkv (1 file, 8.1GB) [1080p] [H.264]
    └── Inception.2010.2160p.UHD.BluRay.x265.mkv (1 file, 18.5GB) [2160p] [H.265]
```

### Color Coding

- **Cyan** - Titles and filenames
- **Yellow** - Resolutions (720p, 1080p, 2160p)
- **Red** - Duplicate counts (when > 0)
- **Dim/Gray** - File counts, sizes, codecs, and metadata

## Use Cases

### Library Cleanup

After upgrading your collection or migrating between servers:
```bash
python mdupes.py --save cleanup.json /var/lib/jellyfin/media
```

Navigate the TUI, press `d` to delete lower-quality duplicates.

### Quality Comparison

See all quality variations at a glance. The TUI shows resolution and codec for easy comparison:
- Delete 720p versions after upgrading to 1080p
- Keep H.265 versions and remove larger H.264 files
- Identify episodes with mixed quality

### Storage Analysis

Sort by total size (`s` → "Total size") to find which series consume the most space:
```bash
python mdupes.py /mnt/media/series
```

### Duplicate Prevention

After downloading new content, check for duplicates before adding to your library:
```bash
python mdupes.py ~/Downloads/Complete /mnt/media/series
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions, issues, and feature requests are welcome!
