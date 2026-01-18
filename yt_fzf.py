import sys
import shutil
import subprocess as sp
from innertube.clients import InnerTube
from dataclasses import dataclass
from enum import Enum


@dataclass
class Playlist:
    title: str
    type: CollectionType
    year: int
    id: str


class CollectionType(Enum):
    ALBUM = "Album"
    SINGLE = "Single"
    EP = "EP"


def extract_channel_id(data: dict) -> str:
    try:
        return data["contents"]["tabbedSearchResultsRenderer"][
            "tabs"][0]["tabRenderer"]["content"]["sectionListRenderer"][
            "contents"][1]["musicCardShelfRenderer"]["title"]["runs"][0][
            "navigationEndpoint"]["browseEndpoint"]["browseId"]
    except KeyError:
        return ""


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


def get_playlists_from_query(innertube_client: InnerTube, query: str) -> list[Playlist]:
    response = innertube_client.search(query)
    channel_id = extract_channel_id(response)
    if not channel_id:
        return []
    response = innertube_client.browse(f"MPAD{channel_id}")
    return extract_playlists(response)


def get_title_from_entry(entry: str) -> str:
    """
    Extract the playlist title from the formatted playlist selected by the user through fzf.
    NOTE: How this works depends strictly on format_playlists.
    """
    return " ".join(entry.split()[3:])


def format_playlists(playlists: list[Playlist]) -> str:
    """
    [ALBUM]  [year] - title..
    [EP]     [year] - title..
    ...
    [SINGLE] [year] - title..
    """
    components: list[str] = []
    max_ctype_length = max(map(len, CollectionType.__members__))
    for p in playlists:
        component = f"{p.type.value}"
        component += " " * (max_ctype_length - len(p.type.value))
        component += " "
        component += f"{p.year}"
        component += " - "
        component += p.title
        components.append(component)
    return '\n'.join(components)


class MissingDependency(Exception):
    pass


def check_deps(deps: set[str]) -> None:
    for d in deps:
        if not shutil.which(d):
            raise MissingDependency(d)


def main() -> int:
    check_deps({"fzf", "yt-dlp"})

    # Search and extract
    innertube_client = InnerTube("WEB_REMIX")
    query = input("Search: ")
    if not query:
        return 1
    playlists = get_playlists_from_query(innertube_client, query=query)
    if not playlists:
        print("No results found.", file=sys.stderr)
        return 2

    # Show results using fzf
    map_title_id = {p.title: p.id for p in playlists}
    formatted_playlists = format_playlists(playlists)
    choice = fzf(stdin=formatted_playlists).stdout.decode()
    if not choice:
        print("Aborting..", file=sys.stderr)
        return 1

    # Downloading
    playlist_title = get_title_from_entry(choice)
    playlist_id = map_title_id[playlist_title]
    cp = yt_dlp(args=[playlist_id])

    return cp.returncode


if __name__ == "__main__":
    exit(main())
