#!/usr/bin/env python3
"""
mdupes - Media Duplicates Finder
Identifies duplicate media files in Jellyfin/Plex directory structures.
"""

from pathlib import Path
import click

from scanner import (
    MediaMetadata,
    parse_directory,
    save_scan_results,
    load_scan_results,
)
from tui import MediaDupesApp


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.pass_context
@click.argument(
    "directories",
    nargs=-1,
    required=False,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
)
@click.option(
    "--save",
    "-s",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Save scan results to a JSON file for faster loading later",
)
@click.option(
    "--load",
    "-l",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Load previously saved scan results from a JSON file (skips scanning)",
)
def main(
    ctx: click.Context,
    directories: tuple[Path, ...],
    save: Path | None,
    load: Path | None,
) -> None:
    """
    mdupes - Media Duplicates Finder

    Identifies duplicate media files in Jellyfin/Plex directory structures
    using GuessIt to parse file names and extract metadata.

    Scans the specified directories for video files, parses metadata, and displays
    them in an interactive TUI (Terminal User Interface) tree view.

    You can save scan results to a file for faster loading on subsequent runs,
    or load previously saved results to skip the scanning phase entirely.

    \b
    Examples:
        python mdupes.py /path/to/media
        python mdupes.py /path/to/series /path/to/movies
        python mdupes.py -s results.json /path/to/media
        python mdupes.py -l results.json
    """
    # Validate arguments
    if load and directories:
        click.echo("Error: Cannot specify directories when using --load", err=True)
        click.echo(
            "Use either --load to load saved results, or provide directories to scan"
        )
        click.echo()
        click.echo(ctx.get_help())
        ctx.exit(1)

    if not load and not directories:
        click.echo(
            "Error: Must specify either directories to scan or --load to load saved results",
            err=True,
        )
        click.echo()
        click.echo(ctx.get_help())
        ctx.exit(1)

    if save and not directories:
        click.echo("Error: --save requires directories to scan", err=True)
        click.echo()
        click.echo(ctx.get_help())
        ctx.exit(1)

    click.echo("🔍 mdupes - Media Duplicates Finder")
    click.echo("=" * 50)

    # Load or scan
    if load:
        click.echo(f"\n📂 Loading scan results from: {load}")
        try:
            all_media = load_scan_results(load)
            click.echo(f"✅ Loaded {len(all_media)} files")
        except Exception as e:
            click.echo(f"Error loading file: {e}", err=True)
            return
    else:
        # Collect all media from all directories
        all_media: list[MediaMetadata] = []

        for directory in directories:
            click.echo(f"\n📁 Scanning directory: {directory}")

            # Parse directory (handles both series and movies)
            media_data = parse_directory(directory)

            click.echo(f"Found {len(media_data)} video files")

            # Merge all media
            all_media.extend(media_data)

        # Save results if requested
        if save:
            click.echo(f"\n💾 Saving scan results to: {save}")
            try:
                save_scan_results(all_media, save)
                click.echo("✅ Results saved successfully")
            except Exception as e:
                click.echo(f"Error saving file: {e}", err=True)

    click.echo("\n" + "=" * 50)
    click.echo("📊 Launching TUI...\n")

    # Launch TUI
    if all_media:
        app = MediaDupesApp(all_media)
        app.run()
    else:
        click.echo("✅ No media files found!")


if __name__ == "__main__":
    main()
