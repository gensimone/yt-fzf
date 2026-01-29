import sys
import shutil
import subprocess as sp
from argparse import ArgumentParser
from innertube.clients import InnerTube
from dataclasses import dataclass
from enum import Enum


class CollectionType(Enum):
    ALBUM = "Album"
    SINGLE = "Single"
    EP = "EP"


@dataclass
class Entry:
    title: str
    id: str

    def __str__(self) -> str:
        return self.title


@dataclass
class Playlist(Entry):
    type: CollectionType
    year: int

    def __str__(self) -> str:
        out = f"{self.type.value}"
        out += " " * (max(map(len, CollectionType.__members__)) - len(self.type.value))
        out += " "
        out += f"{self.year}"
        out += " - "
        out += self.title
        return out


def get_title_from_str_entry(str_entry: str, entry: Entry) -> str:
    return " ".join(str_entry.split()[3:]) if isinstance(entry, Playlist) else str_entry


def extract_channel_id(data: dict) -> str:
    try:
        return data["contents"]["tabbedSearchResultsRenderer"][
            "tabs"][0]["tabRenderer"]["content"]["sectionListRenderer"][
            "contents"][1]["musicCardShelfRenderer"]["title"]["runs"][0][
            "navigationEndpoint"]["browseEndpoint"]["browseId"]
    except KeyError:
        return ""


def extract_videos(data: dict) -> list[Entry]:
    entries: list[Entry] = []
    for item in data["contents"]["singleColumnMusicWatchNextResultsRenderer"][
            "tabbedRenderer"]["watchNextTabbedResultsRenderer"][
                    "tabs"][0]["tabRenderer"]["content"][
                            "musicQueueRenderer"]["content"][
                                    "playlistPanelRenderer"]["contents"]:
        if "playlistPanelVideoRenderer" not in item:
            break
        item_data = item["playlistPanelVideoRenderer"]
        title = item_data["title"]["runs"][0]["text"]
        id = item_data["navigationEndpoint"]["watchEndpoint"]["videoId"]
        entries.append(Entry(title=title, id=id))
    return entries


def extract_playlists(data: dict) -> list[Playlist]:
    playlists: list[Playlist] = []
    try:
        for item in data["contents"]["singleColumnBrowseResultsRenderer"]["tabs"][0][
            "tabRenderer"]["content"]["sectionListRenderer"]["contents"][
                0]["gridRenderer"]["items"]:
            item_data = item["musicTwoRowItemRenderer"]
            type = CollectionType(item_data["subtitle"]["runs"][0]["text"])
            title = item_data["title"]["runs"][0]["text"]
            year = int(item_data["subtitle"]["runs"][-1]["text"])
            id = item_data["menu"]["menuRenderer"]["items"][
                0]["menuNavigationItemRenderer"]["navigationEndpoint"][
                "watchPlaylistEndpoint"]["playlistId"]
            playlists.append(
                Playlist(
                    title=title,
                    type=type,
                    year=year,
                    id=id
                )
            )
    except KeyError:
        pass
    return playlists


def fzf(stdin: str = "", args: list[str] = []) -> sp.CompletedProcess:
    return sp.run(["fzf"] + args, input=stdin.encode(), stdout=sp.PIPE)


def yt_dlp(stdin: str = "", args: list[str] = []) -> sp.CompletedProcess:
    return sp.run(["yt-dlp"] + args, input=stdin.encode())


def get_playlists_from_channel_id(innertube_client: InnerTube, channel_id: str) -> list[Playlist]:
    response = innertube_client.browse(f"MPAD{channel_id}")
    return extract_playlists(response)


def get_playlists_from_channel_name(innertube_client: InnerTube, channel_name: str) -> list[Playlist]:
    response = innertube_client.search(channel_name)
    channel_id = extract_channel_id(response)
    if not channel_id:
        return []
    return get_playlists_from_channel_id(innertube_client, channel_id)


def get_chosen_ids_from_entries(entries: list[Entry]) -> list[str]:
    map_ids: dict[str, str] = dict()
    str_list: list[str] = []
    for e in entries:
        map_ids[e.title] = e.id
        str_list.append(str(e))
    selected_entries = fzf(args=["-m"], stdin="\n".join(str_list)).stdout.decode()
    return [map_ids[get_title_from_str_entry(e, entries[0])] for e in selected_entries.split("\n") if e]


def check_deps(deps: set[str]) -> None:
    missing_dependencies: set[str] = set()
    for d in deps:
        if not shutil.which(d):
            missing_dependencies.add(d)
    if missing_dependencies:
        print(f"Missing dependencies: {', '.join(missing_dependencies)}", file=sys.stderr)
        sys.exit(1)


def get_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Search and download music from YouTube Music using fzf and yt-dlp.")
    parser.add_argument("channel", help="name of the channel to search for")
    parser.add_argument("-i", "--id", action="store_true", help="intepret the channel name as an ID")
    parser.add_argument("-e", "--entries", action="store_true", help="show available entries for each individual playlist")
    return parser


def main() -> int:
    try:
        return _main()
    except KeyboardInterrupt:
        print()
        print("Interrupted", file=sys.stderr)
        return 130


def _main() -> int:
    check_deps({"fzf", "yt-dlp"})
    args = get_parser().parse_args()

    innertube_client = InnerTube("WEB_REMIX")
    if args.id:
        playlists = get_playlists_from_channel_id(
                innertube_client=innertube_client,
                channel_id=args.channel
        )
    else:
        playlists = get_playlists_from_channel_name(
                innertube_client=innertube_client,
                channel_name=args.channel
        )
    if not playlists:
        print("No results found.", file=sys.stderr)
        return 1

    ids = get_chosen_ids_from_entries(playlists)
    if args.entries:
        print("Loading entries..")
        videos: list[Video] = []
        for id in ids:
            videos.extend(extract_videos(innertube_client.next(playlist_id=id)))
        ids = get_chosen_ids_from_entries(videos)

    if not ids:
        return 0

    cp = yt_dlp(args=ids)
    return cp.returncode


if __name__ == "__main__":
    sys.exit(main())
