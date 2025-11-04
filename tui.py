#!/usr/bin/env python3
"""
TUI (Terminal User Interface) for browsing media duplicates.
Built with Textual framework for an interactive ncdu-style tree view.
"""

import re
from collections import defaultdict
from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.widgets import Tree, Header, Footer, OptionList, Label, Button, Input
from textual.widgets.tree import TreeNode
from textual.widgets.option_list import Option
from textual.screen import ModalScreen
from textual.containers import Container, Vertical, Horizontal

from scanner import MediaKey, MediaMetadata, find_duplicates


def sort_resolutions(resolutions: set[str]) -> list[str]:
    """
    Sort resolutions by numeric value (e.g., 720p before 1080p before 2160p).
    """

    def extract_number(res: str) -> int:
        # Extract numeric part from resolution string (e.g., "1080p" -> 1080)
        match = re.search(r"(\d+)", res)
        return int(match.group(1)) if match else 0

    return sorted(resolutions, key=extract_number)


def format_metadata_summary(
    total_files: int,
    num_duplicates: int,
    metadata_list: list[MediaMetadata],
) -> str:
    """
    Format a complete metadata summary including files, total size, resolutions, and codecs.
    Returns formatted string like "(50 files, 12GB) [1080p, 2160p] [H.264, H.265] 7 duplicates"
    """
    # Calculate total size
    total_size_mb = sum(metadata.file_size_mb for metadata in metadata_list)
    if total_size_mb >= 1024 * 1024:  # >= 1TB
        size_str = f"{total_size_mb / (1024 * 1024):.1f}TB"
    elif total_size_mb >= 1024:  # >= 1GB
        size_str = f"{total_size_mb / 1024:.1f}GB"
    else:
        size_str = f"{total_size_mb:.0f}MB"

    # Proper pluralization
    file_text = "file" if total_files == 1 else "files"
    duplicate_text = "duplicate" if num_duplicates == 1 else "duplicates"

    # Collect unique resolutions and codecs
    resolutions = set()
    codecs = set()

    for metadata in metadata_list:
        if metadata.screen_size:
            resolutions.add(metadata.screen_size)
        if metadata.video_codec:
            codecs.add(metadata.video_codec)

    # Build quality info parts
    quality_parts = []
    if resolutions:
        sorted_resolutions = sort_resolutions(resolutions)
        quality_parts.append(f"[yellow][{', '.join(sorted_resolutions)}][/yellow]")
    if codecs:
        quality_parts.append(f"[{', '.join(sorted(codecs))}]")

    quality_str = f" [dim]{' '.join(quality_parts)}[/dim]" if quality_parts else ""

    # Build duplicates suffix
    duplicates_suffix = (
        f" [red]{num_duplicates} {duplicate_text}[/red]" if num_duplicates > 0 else ""
    )

    return f"[dim]({total_files} {file_text}, {size_str})[/dim]{quality_str}{duplicates_suffix}"


class DeleteConfirmation(ModalScreen[bool]):
    """Modal screen for confirming file deletion."""

    CSS = """
    DeleteConfirmation {
        align: center middle;
    }

    #delete-dialog {
        width: 70;
        height: auto;
        border: thick $error 80%;
        background: $surface;
        padding: 1 2;
    }

    #delete-message {
        width: 100%;
        content-align: center middle;
        padding: 1 0;
    }

    #button-container {
        width: 100%;
        height: auto;
        align: center middle;
    }

    Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("left", "focus_cancel", "Focus Cancel"),
        ("right", "focus_delete", "Focus Delete"),
    ]

    def __init__(self, filepath: Path):
        super().__init__()
        self.filepath = filepath

    def compose(self) -> ComposeResult:
        with Vertical(id="delete-dialog"):
            yield Label(
                f"Delete file?\n\n{self.filepath.name}\n\nThis cannot be undone!",
                id="delete-message",
            )
            with Horizontal(id="button-container"):
                yield Button("Cancel", variant="default", id="cancel-btn")
                yield Button("Delete", variant="error", id="delete-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "delete-btn":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def on_mount(self) -> None:
        """Set initial focus on Cancel button when modal opens."""
        self.query_one("#cancel-btn", Button).focus()

    def action_cancel(self) -> None:
        """Cancel deletion."""
        self.dismiss(False)

    def action_focus_cancel(self) -> None:
        """Focus the Cancel button."""
        self.query_one("#cancel-btn", Button).focus()

    def action_focus_delete(self) -> None:
        """Focus the Delete button."""
        self.query_one("#delete-btn", Button).focus()


class DeleteMultipleConfirmation(ModalScreen[bool]):
    """Modal screen for confirming deletion of multiple files."""

    CSS = """
    DeleteMultipleConfirmation {
        align: center middle;
    }

    #delete-multiple-dialog {
        width: 80;
        height: auto;
        max-height: 30;
        border: thick $error 80%;
        background: $surface;
        padding: 1 2;
    }

    #delete-multiple-message {
        width: 100%;
        padding: 0 0 1 0;
    }

    #file-list {
        width: 100%;
        height: auto;
        max-height: 15;
        overflow-y: auto;
        background: $panel;
        padding: 1;
        margin: 1 0;
    }

    #button-container {
        width: 100%;
        height: auto;
        align: center middle;
        padding: 1 0 0 0;
    }

    Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("left", "focus_cancel", "Focus Cancel"),
        ("right", "focus_delete", "Focus Delete"),
    ]

    def __init__(self, filepaths: list[Path]):
        super().__init__()
        self.filepaths = filepaths

    def compose(self) -> ComposeResult:
        file_list = "\n".join(f"  • {fp.name}" for fp in self.filepaths)
        count = len(self.filepaths)

        with Vertical(id="delete-multiple-dialog"):
            yield Label(
                f"Delete {count} file(s)?\n\nThis cannot be undone!",
                id="delete-multiple-message",
            )
            yield Label(file_list, id="file-list")
            with Horizontal(id="button-container"):
                yield Button("Cancel", variant="default", id="cancel-btn")
                yield Button(f"Delete {count}", variant="error", id="delete-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "delete-btn":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def on_mount(self) -> None:
        """Set initial focus on Cancel button when modal opens."""
        self.query_one("#cancel-btn", Button).focus()

    def action_cancel(self) -> None:
        """Cancel deletion."""
        self.dismiss(False)

    def action_focus_cancel(self) -> None:
        """Focus the Cancel button."""
        self.query_one("#cancel-btn", Button).focus()

    def action_focus_delete(self) -> None:
        """Focus the Delete button."""
        self.query_one("#delete-btn", Button).focus()


class RenameDialog(ModalScreen[str | None]):
    """Modal screen for renaming a file."""

    CSS = """
    RenameDialog {
        align: center middle;
    }

    #rename-dialog {
        width: 70;
        height: auto;
        border: thick $primary 80%;
        background: $surface;
        padding: 1 2;
    }

    #rename-message {
        width: 100%;
        padding: 0 0 1 0;
    }

    #rename-input {
        width: 100%;
        margin: 1 0;
    }

    #button-container {
        width: 100%;
        height: auto;
        align: center middle;
        padding: 1 0 0 0;
    }

    Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, current_name: str):
        super().__init__()
        self.current_name = current_name

    def compose(self) -> ComposeResult:
        with Vertical(id="rename-dialog"):
            yield Label("Rename file:", id="rename-message")
            yield Input(
                value=self.current_name,
                placeholder="Enter new filename",
                id="rename-input",
            )
            with Horizontal(id="button-container"):
                yield Button("Cancel", variant="default", id="cancel-btn")
                yield Button("Rename", variant="primary", id="rename-btn")

    def on_mount(self) -> None:
        """Focus the input when mounted."""
        self.query_one("#rename-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "rename-btn":
            new_name = self.query_one("#rename-input", Input).value
            if new_name and new_name != self.current_name:
                self.dismiss(new_name)
            else:
                self.dismiss(None)
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in input."""
        if event.value and event.value != self.current_name:
            self.dismiss(event.value)
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        """Cancel rename."""
        self.dismiss(None)


class SortPrompt(ModalScreen[str]):
    """Modal screen for selecting sort order."""

    CSS = """
    SortPrompt {
        align: center middle;
    }

    #sort-dialog {
        width: 50;
        height: auto;
        border: thick $background 80%;
        background: $surface;
        padding: 1 2;
    }

    OptionList {
        height: auto;
        max-height: 10;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        with Container(id="sort-dialog"):
            yield OptionList(
                Option("Alphabetic", id="alpha"),
                Option("File count", id="count"),
                Option("Total size", id="size"),
                Option("Duplicate count", id="duplicates"),
            )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle option selection."""
        self.dismiss(event.option.id)

    def action_cancel(self) -> None:
        """Cancel the sort prompt."""
        self.dismiss(None)


class MediaDupesApp(App):
    """A Textual app to display media duplicates in a tree view."""

    TITLE = "mdupes"

    CSS = """
    Tree {
        width: 100%;
        height: 100%;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("c", "collapse_all", "Collapse All"),
        ("e", "expand_all", "Expand All"),
        ("f", "toggle_filter", "Toggle Filter"),
        ("s", "sort", "Sort"),
        ("d", "delete_file", "Delete File"),
        ("r", "rename_file", "Rename File"),
        ("left", "collapse_single", "Collapse"),
        ("right", "expand_single", "Expand"),
        ("m", "toggle_mark", "Mark/Unmark"),
        ("ctrl+d", "delete_marked", "Delete Marked"),
        ("ctrl+u", "unmark_all", "Unmark All"),
    ]

    def __init__(self, media_list: list[MediaMetadata]):
        super().__init__()
        self.media_list = media_list
        self.duplicates = find_duplicates(media_list)
        self.show_duplicates_only = False
        self.sort_order = "alpha"  # Default sort order
        self.expansion_states: dict[str, bool] = {}  # Store expansion states
        self.selected_files: set[Path] = set()  # Store selected files for deletion

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield Tree("", id="duplicates-tree")
        yield Footer()

    def on_mount(self) -> None:
        """Build the tree when the app starts."""
        self._rebuild_tree()

    def _rebuild_tree(self) -> None:
        """Rebuild the entire tree based on current filter state."""
        tree = self.query_one("#duplicates-tree", Tree)

        # Save expansion states before clearing
        self._save_expansion_states(tree.root)

        tree.clear()
        tree.show_root = False

        # Choose data source based on filter state
        data_source = self.duplicates if self.show_duplicates_only else self.media_list

        # Group by media key first
        by_key: dict[MediaKey, list[MediaMetadata]] = defaultdict(list)
        for metadata in data_source:
            if metadata.media_key:
                by_key[metadata.media_key].append(metadata)

        # Separate series and movies
        series_items: dict[MediaKey, list[MediaMetadata]] = {}
        movie_items: dict[MediaKey, list[MediaMetadata]] = {}

        for key, metadata_list in by_key.items():
            if key[0] == "episode":
                series_items[key] = metadata_list
            elif key[0] == "movie":
                movie_items[key] = metadata_list

        # Update header with filter state
        filter_text = "Duplicates Only" if self.show_duplicates_only else "All Media"
        self.sub_title = f"Mode: {filter_text}"

        # Add movies section
        if movie_items:
            total_movie_files = sum(
                len(metadata_list) for metadata_list in movie_items.values()
            )
            total_movie_duplicates = total_movie_files - len(movie_items)
            all_movie_metadata = [
                metadata
                for metadata_list in movie_items.values()
                for metadata in metadata_list
            ]
            summary = format_metadata_summary(
                total_movie_files, total_movie_duplicates, all_movie_metadata
            )
            movies_node = tree.root.add(
                f"🎬 [bold cyan]Movies[/bold cyan] {summary}",
                expand=True,
            )
            self._build_movies_tree(movies_node, movie_items)

        # Add series section
        if series_items:
            total_series_files = sum(
                len(metadata_list) for metadata_list in series_items.values()
            )
            total_series_duplicates = total_series_files - len(series_items)
            all_series_metadata = [
                metadata
                for metadata_list in series_items.values()
                for metadata in metadata_list
            ]
            summary = format_metadata_summary(
                total_series_files, total_series_duplicates, all_series_metadata
            )
            series_node = tree.root.add(
                f"📺 [bold cyan]Series[/bold cyan] {summary}",
                expand=True,
            )
            self._build_series_tree(series_node, series_items)

        if not by_key:
            if self.show_duplicates_only:
                tree.root.add("✅ No duplicates found!")
            else:
                tree.root.add("📂 No media files found!")

        # Restore expansion states after rebuilding
        self._restore_expansion_states(tree.root)

    def _build_movies_tree(
        self, parent: TreeNode, movies: dict[MediaKey, list[MediaMetadata]]
    ) -> None:
        """Build the movies section of the tree."""
        # Group by title
        by_title: dict[str, list[MediaMetadata]] = {}
        for key, metadata_list in movies.items():
            _, title, _, _, _ = key
            if title not in by_title:
                by_title[title] = []
            by_title[title].extend(metadata_list)

        # Sort titles based on current sort order
        sorted_titles = self._sort_items(by_title)

        for title in sorted_titles:
            metadata_list = by_title[title]
            num_duplicates = len(metadata_list) - 1
            summary = format_metadata_summary(
                len(metadata_list), num_duplicates, metadata_list
            )
            title_node = parent.add(
                f"[cyan]{title.title()}[/cyan] {summary}",
                expand=False,
            )

            for metadata in sorted(metadata_list, key=lambda m: m.filepath):
                # Add checkmark if file is selected
                mark = "✓ " if metadata.filepath in self.selected_files else ""
                title_node.add_leaf(
                    f"{mark}[cyan]{metadata.filepath.name}[/cyan] "
                    + format_metadata_summary(1, 0, [metadata])
                )

    def _build_series_tree(
        self, parent: TreeNode, series: dict[MediaKey, list[MediaMetadata]]
    ) -> None:
        """Build the series section of the tree."""
        # Group by series title -> season -> episode
        by_series: dict[str, dict[int, dict[int, list[MediaMetadata]]]] = {}

        for key, metadata_list in series.items():
            _, title, season, episode, _ = key
            if season is None or episode is None:
                continue

            if title not in by_series:
                by_series[title] = {}
            if season not in by_series[title]:
                by_series[title][season] = {}
            by_series[title][season][episode] = metadata_list

        # Prepare data for sorting
        series_metadata_map = {}
        for series_title in by_series.keys():
            seasons = by_series[series_title]
            all_metadata = [
                metadata
                for season_eps in seasons.values()
                for metadata_list in season_eps.values()
                for metadata in metadata_list
            ]
            series_metadata_map[series_title] = all_metadata

        # Sort series based on current sort order
        sorted_series = self._sort_items(series_metadata_map)

        for series_title in sorted_series:
            seasons = by_series[series_title]
            all_series_metadata = series_metadata_map[series_title]
            total_episodes = sum(len(season_eps) for season_eps in seasons.values())
            total_copies = len(all_series_metadata)
            total_duplicates = total_copies - total_episodes
            summary = format_metadata_summary(
                total_copies, total_duplicates, all_series_metadata
            )
            series_node = parent.add(
                f"[cyan]{series_title.title()}[/cyan] {summary}",
                expand=False,
            )

            for season in sorted(seasons.keys()):
                episodes = seasons[season]
                season_copies = sum(
                    len(metadata_list) for metadata_list in episodes.values()
                )
                season_duplicates = season_copies - len(episodes)
                all_season_metadata = [
                    metadata
                    for metadata_list in episodes.values()
                    for metadata in metadata_list
                ]
                summary = format_metadata_summary(
                    season_copies, season_duplicates, all_season_metadata
                )
                season_node = series_node.add(
                    f"[cyan]Season {season}[/cyan] {summary}",
                    expand=False,
                )

                for episode in sorted(episodes.keys()):
                    metadata_list = episodes[episode]
                    episode_duplicates = len(metadata_list) - 1

                    # Get episode title from first metadata item if available
                    episode_title = ""
                    if metadata_list and metadata_list[0].episode_title:
                        episode_title = f" - {metadata_list[0].episode_title}"

                    summary = format_metadata_summary(
                        len(metadata_list), episode_duplicates, metadata_list
                    )
                    episode_node = season_node.add(
                        f"[cyan]S{season:02d}E{episode:02d}{episode_title}[/cyan] {summary}",
                        expand=False,
                    )

                    for metadata in sorted(metadata_list, key=lambda m: m.filepath):
                        # Add checkmark if file is selected
                        mark = "✓ " if metadata.filepath in self.selected_files else ""
                        episode_node.add_leaf(
                            f"{mark}[cyan]{metadata.filepath.name}[/cyan] "
                            + format_metadata_summary(1, 0, [metadata])
                        )

    def _get_cursor_node(self) -> TreeNode | None:
        """Get the current cursor node from the tree, or None if not available."""
        tree = self.query_one("#duplicates-tree", Tree)
        return tree.cursor_node

    def _extract_node_identifier(self, node: TreeNode) -> str:
        """Extract the stable identifier (cyan text) from a node's label."""
        label_text = node.label

        if isinstance(label_text, Text):
            # Extract text from cyan or bold cyan spans
            for span in label_text.spans:
                style_str = str(span.style) if span.style else ""
                if "cyan" in style_str:
                    return label_text.plain[span.start : span.end]
            # Fallback to full plain text if no cyan span found
            return label_text.plain
        return str(label_text)

    def _save_expansion_states(self, node: TreeNode, path: str = "") -> None:
        """Recursively save the expansion state of all nodes."""
        if node == node.tree.root:
            # Clear previous states when starting from root
            self.expansion_states = {}
            # Process root's children
            for child in node.children:
                self._save_expansion_states(child, "")
            return

        # Build the path for this node using its label
        # Extract only the cyan-colored text part for stable identification
        clean_label = self._extract_node_identifier(node)

        # Create hierarchical path
        current_path = f"{path}/{clean_label}" if path else clean_label

        # Save the expansion state
        self.expansion_states[current_path] = node.is_expanded

        # Recursively process children
        for child in node.children:
            self._save_expansion_states(child, current_path)

    def _restore_expansion_states(self, node: TreeNode, path: str = "") -> None:
        """Recursively restore the expansion state of all nodes."""
        if node == node.tree.root:
            # Process root's children
            for child in node.children:
                self._restore_expansion_states(child, "")
            return

        # Build the path for this node using its label
        # Extract only the cyan-colored text part for stable identification
        clean_label = self._extract_node_identifier(node)

        # Create hierarchical path
        current_path = f"{path}/{clean_label}" if path else clean_label

        # Restore the expansion state if we have it saved
        if current_path in self.expansion_states:
            saved_state = self.expansion_states[current_path]
            if saved_state:
                node.expand()
            else:
                node.collapse()

        # Recursively process children
        for child in node.children:
            self._restore_expansion_states(child, current_path)

    def action_collapse_single(self) -> None:
        """Collapse the current node only."""
        cursor_node = self._get_cursor_node()
        if cursor_node:
            cursor_node.collapse()

    def action_expand_single(self) -> None:
        """Expand the current node only."""
        cursor_node = self._get_cursor_node()
        if cursor_node:
            cursor_node.expand()

    def action_collapse_all(self) -> None:
        """Collapse the current node and all its children."""
        cursor_node = self._get_cursor_node()
        if cursor_node:
            cursor_node.collapse_all()

    def action_expand_all(self) -> None:
        """Expand the current node and all its children."""
        cursor_node = self._get_cursor_node()
        if cursor_node:
            cursor_node.expand_all()

    def action_toggle_filter(self) -> None:
        """Toggle between showing duplicates only and showing all media."""
        self.show_duplicates_only = not self.show_duplicates_only
        self._rebuild_tree()

    def action_sort(self) -> None:
        """Show sort order selection prompt."""
        self.push_screen(SortPrompt(), callback=self._handle_sort_result)

    def _handle_sort_result(self, result: str | None) -> None:
        """Handle the sort order selection result."""
        if result:
            self.sort_order = result
            self._rebuild_tree()

    def _sort_items(self, items: dict[str, list[MediaMetadata]]) -> list[str]:
        """Sort items based on current sort order."""
        if self.sort_order == "alpha":
            return sorted(items.keys())
        elif self.sort_order == "count":
            return sorted(items.keys(), key=lambda k: len(items[k]), reverse=True)
        elif self.sort_order == "size":
            return sorted(
                items.keys(),
                key=lambda k: sum(m.file_size_mb for m in items[k]),
                reverse=True,
            )
        elif self.sort_order == "duplicates":
            return sorted(items.keys(), key=lambda k: len(items[k]) - 1, reverse=True)
        return sorted(items.keys())

    def action_delete_file(self) -> None:
        """Delete the currently selected file."""
        cursor_node = self._get_cursor_node()
        if not cursor_node:
            return

        # Check if the current node is a leaf (file node)
        if not cursor_node.allow_expand:
            # Try to find the metadata for this file
            filepath = self._get_filepath_from_node(cursor_node)
            if filepath:
                self.push_screen(
                    DeleteConfirmation(filepath), callback=self._handle_delete_result
                )

    def _get_filepath_from_node(self, node: TreeNode) -> Path | None:
        """Extract the filepath from a file node by matching against metadata."""
        label = str(node.label)
        # Extract just the filename from the label (before the first space/paren)
        # The label format is: "[cyan]filename[/cyan] ..." or "✓ [cyan]filename[/cyan] ..."
        # We need to search through our metadata to find a match
        for metadata in self.media_list:
            if metadata.filepath.name in label:
                return metadata.filepath
        return None

    def action_toggle_mark(self) -> None:
        """Toggle the mark on the currently selected file."""
        cursor_node = self._get_cursor_node()
        if not cursor_node or cursor_node.allow_expand:
            return

        filepath = self._get_filepath_from_node(cursor_node)
        if not filepath:
            return

        # Toggle selection
        if filepath in self.selected_files:
            self.selected_files.remove(filepath)
            self.sub_title = f"Unmarked: {filepath.name}"
        else:
            self.selected_files.add(filepath)
            self.sub_title = (
                f"Marked: {filepath.name} ({len(self.selected_files)} total)"
            )

        # Rebuild tree to show/hide checkmarks
        self._rebuild_tree()

    def action_unmark_all(self) -> None:
        """Unmark all selected files."""
        count = len(self.selected_files)
        self.selected_files.clear()
        self.sub_title = f"Unmarked {count} file(s)"
        self._rebuild_tree()

    def action_delete_marked(self) -> None:
        """Delete all marked files."""
        if not self.selected_files:
            self.sub_title = "No files marked for deletion"
            return

        # Show confirmation dialog with all files
        files_list = sorted(self.selected_files)
        self.push_screen(
            DeleteMultipleConfirmation(files_list),
            callback=lambda confirmed: self._handle_delete_marked_result(
                confirmed, files_list
            ),
        )

    def _handle_delete_marked_result(
        self, confirmed: bool, files_to_delete: list[Path]
    ) -> None:
        """Handle the deletion confirmation result for marked files."""
        if not confirmed:
            return

        deleted = []
        errors = []

        for filepath in files_to_delete:
            try:
                filepath.unlink()
                deleted.append(filepath)
            except Exception as e:
                errors.append((filepath, e))

        # Update data structures
        if deleted:
            self.media_list = [m for m in self.media_list if m.filepath not in deleted]
            self.duplicates = find_duplicates(self.media_list)
            self.selected_files.clear()
            self._rebuild_tree()

        # Show results
        if errors:
            error_names = ", ".join(fp.name for fp, _ in errors[:3])
            self.sub_title = (
                f"Deleted {len(deleted)}, errors: {len(errors)} ({error_names}...)"
            )
        else:
            self.sub_title = f"Successfully deleted {len(deleted)} file(s)"

    def _handle_delete_result(self, confirmed: bool) -> None:
        """Handle the deletion confirmation result."""
        if not confirmed:
            return

        cursor_node = self._get_cursor_node()
        if not cursor_node:
            return

        filepath = self._get_filepath_from_node(cursor_node)
        if not filepath:
            return

        try:
            # Delete the file
            filepath.unlink()

            # Remove from our data
            self.media_list = [m for m in self.media_list if m.filepath != filepath]
            self.duplicates = find_duplicates(self.media_list)

            # Rebuild the tree
            self._rebuild_tree()

            # Show success message in the subtitle
            self.sub_title = f"Deleted: {filepath.name}"
        except Exception as e:
            # Show error message in the subtitle
            self.sub_title = f"Error deleting file: {e}"

    def action_rename_file(self) -> None:
        """Rename the currently selected file."""
        cursor_node = self._get_cursor_node()
        if not cursor_node:
            return

        # Check if the current node is a leaf (file node)
        if not cursor_node.allow_expand:
            # Try to find the metadata for this file
            filepath = self._get_filepath_from_node(cursor_node)
            if filepath:
                self.push_screen(
                    RenameDialog(filepath.name), callback=self._handle_rename_result
                )

    def _handle_rename_result(self, new_name: str | None) -> None:
        """Handle the rename dialog result."""
        if not new_name:
            return

        cursor_node = self._get_cursor_node()
        if not cursor_node:
            return

        filepath = self._get_filepath_from_node(cursor_node)
        if not filepath:
            return

        # Create new path with the new name
        new_filepath = filepath.parent / new_name

        # Check if target already exists
        if new_filepath.exists():
            self.sub_title = f"Error: File already exists: {new_name}"
            return

        try:
            # Rename the file
            filepath.rename(new_filepath)

            # Update in our data
            for metadata in self.media_list:
                if metadata.filepath == filepath:
                    metadata.filepath = new_filepath
                    break

            # Recalculate duplicates
            self.duplicates = find_duplicates(self.media_list)

            # Rebuild the tree
            self._rebuild_tree()

            # Show success message in the subtitle
            self.sub_title = f"Renamed to: {new_name}"
        except Exception as e:
            # Show error message in the subtitle
            self.sub_title = f"Error renaming file: {e}"
