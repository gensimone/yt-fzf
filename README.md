# yt-fzf (YouTube Fuzzy Finder)

# Installation
yt-fzf dependes on [fzf](https://github.com/junegunn/fzf) and [yt-dlp](https://github.com/yt-dlp/yt-dlp).
On Arch Linux you can install them using pacman:
```sh
sudo pacman -S yt-dlp fzf
```
yt-dlp is also available on PyPi so you can install it using pip or pipx.
After fzf and yt-dlp are installed you can proceed and install yt-fzf:
```sh
pipx install yt-fzf
```
This will download yt-fzf and [innertube](https://github.com/tombulled/innertube), a library
that allows you to access the Google's private InnerTube API.
