# python

Some small Python utilities.

To use them, make sure you also downloaded `util.py` file from the same directory (or better, just clone the whole repo).


## `instalive.py`

Instagram live downloader. Feed in MPD URL (including all the query parameters!) within ~~24~~ (a few) hours and it can download the full live stream from the beginning.

Usage:

```
usage: instalive.py [-h] [--action ACTION] [--dir DIR] [--debug] [--quality QUALITY] [--time TIME] [--range RANGE] url

Available actions:
  all      - Download both video and audio (including live and backtracking), and then merge them (default)
  live     - Download the live stream only (no backtracking)
  video    - Download video only
  audio    - Download audio only
  merge    - Merge downloaded video and audio
  check    - Check the downloaded segments to make sure there are no missing segments
  manual   - Manually check missing segments at the largest gap (or use --range to assign a range) (for debugging only)
  info     - Display downloader object info
  import:<path> - Import segments downloaded via N_m3u8DL-RE from a given path

positional arguments:
  url                   url of mpd

options:
  -h, --help            show this help message and exit
  --action ACTION, -a ACTION
                        action to perform (default: all)
  --dir DIR, -d DIR     save path (default: instalive_{mpd_id})
  --debug               debug mode
  --quality QUALITY, -q QUALITY
                        manually assign video quality by quality name.
                        (default: "pst": which is the "original" (?) and has the best bitrate,
                        but not necessarily the highest resolution.
                        Pass empty string or "highest" to use the highest resolution one.)
  --time TIME, -t TIME  for debugging only; manually assign last t (default: auto)
  --range RANGE         for debugging only; manually assign iteration range (start,end) for manual action
```

## `oricon.py`

**Deprecated: You can no longer get original size of images from Oricon website AFAIK. The random quality toggling because of CDN is also gone (?). This can still be used to download the images in the size shown on the webpage, though.**

Quickly download all the highest quality pictures from any Oricon news, special or photo article.

Usage:

```
oricon.py https://www.oricon.co.jp/news/2236438/
```

## `scraper_ameblo_api.py`

[Ameblo](https://ameblo.jp/) (アメーバブログ or アメブロ, Japanese blog service) downloader. Supports images and text.

Usage:

CLI:

```
usage: scraper_ameblo_api.py [-h] [--theme THEME] [--output OUTPUT] [--until UNTIL] [--type TYPE] blog_id

Download ameblo images and texts.

positional arguments:
  blog_id               ameblo blog id

optional arguments:
  -h, --help            show this help message and exit
  --theme THEME         ameblo theme name
  --output OUTPUT, -o OUTPUT
                        folder to save images and texts (default: CWD/{blog_id})
  --until UNTIL         download until this entry id (non-inclusive)
  --type TYPE           download type (image, text, all)
```
As Python module:

```python
from scraper_ameblo_api import download_all

download_all('user_id', save_folder='.', limit=100, download_type='all')
```

## `scraper_fantia.py`

Fantia downloader. Inspired by [dumpia](https://github.com/itskenny0/dumpia).

Usage:

```python
from scraper_fantia import FantiaDownloader

key = 'your {_session_id}' # copy it from cookie `_session_id` on fantia.jp
id = 11111 # FC id copied from URL
downloader = FantiaDownloader(fanclub=id, output=".", key=key)
downloader.downloadAll()
```

Or just download certain post (you can omit fanclub id in this case):

```python
downloader = FantiaDownloader(output=".", key='your _session_id')
downloader.getPostPhotos(12345)
```

## `scraper_radiko.py`

**Deprecated: just use yt-dlp or even better, with [yt-dlp-rajiko](https://github.com/garret1317/yt-dlp-rajiko) plugin.**

Note: you need to prepare the JP proxy yourself.

Usage:

```python
from scraper_radiko import RadikoExtractor

# It supports the following formats:
# http://www.joqr.co.jp/timefree/mss.php
# http://radiko.jp/share/?sid=QRR&t=20200822260000
# http://radiko.jp/#!/ts/QRR/20200823020000

url = 'http://www.joqr.co.jp/timefree/mss.php'

e = RadikoExtractor(url, save_dir='/output')
e.parse()
```

## `nico.py`

Nico Timeshift downloader. Download both video and comments.
Also can download thumbnail from normal video. Downloading for normal video isn't supported (yet).


```
pip install browser-cookie3 websocket-client rich python-dateutil pytz requests beautifulsoup4 lxml
```

The actual downloading is delegated to [minyami](https://github.com/Last-Order/Minyami) and/or [N_m3u8DL-RE](https://github.com/nilaoda/N_m3u8DL-RE), so make sure you have them installed first and available in your PATH.

It also can reads the arguments from a `nico.txt` file in the CWD or the same directory as the script. Syntax: just put all the arguments in one line.

CLI:

```
usage: nico.py [-h] [--verbose] [--info] [--dump] [--thumb] [--cookies COOKIES] [--comments {yes,no,only}] [--proxy PROXY] [--save-dir SAVE_DIR] [--reserve]
               [--simulate]
               url

positional arguments:
  url                   URL or ID of nicovideo webpage

options:
  -h, --help            show this help message and exit
  --verbose, -v         Print verbose info for debugging.
  --info, -i            Print info only.
  --dump                Dump all the metadata to json files.
  --thumb               Download thumbnail only. Only works for video type (not live type).
  --cookies COOKIES, -c COOKIES
                        Cookie source.
                        Provide either:
                          - A browser name to fetch from;
                          - The value of "user_session";
                          - A Netscape-style cookie file.
  --comments {yes,no,only}, -d {yes,no,only}
                        Control if comments (danmaku) are downloaded. [Default: no]
  --proxy PROXY         Specify a proxy, "none", or "auto" (automatically detects system proxy settings). [Default: auto]
  --save-dir SAVE_DIR, -o SAVE_DIR
                        Specify the directory to save the downloaded files. [Default: current directory]
  --reserve             Automatically reserve timeshift ticket if not reserved yet. [Default: no]
  --simulate            Simulate the download process without actually downloading.
```

## `util.py`

Some utility functions mainly for myself. Read the code to get the idea.

Some highlights:

**Network & Web Scraping:**
* **download** - a comprehensive file downloader with retry logic, duplicate handling (skip/overwrite/rename), referer support, and automatic filename detection from URLs or response headers
* **get** - a convenience wrapper around requests that returns a BeautifulSoup object with retry logic built-in
* **requests_retry_session** - create a requests session with automatic retry on network failures
* **load_cookie** - load cookies from browser (Chrome/Firefox/Edge), cookie files (Netscape format), or cookie strings

**File Operations:**
* **safeify** - sanitize filenames by replacing illegal characters with full-width equivalents (yes I know safeify isn't a real word. It was blindly copied from another project and It was too much effort to change it)
* **move_or_delete_duplicate** - move files with smart duplicate detection via hash comparison
* **dump_json/load_json** - convenient JSON file I/O with proper encoding and formatting

**Data Structures & Formatting:**
* **Table** - a simple table class with sorting, searching, filtering, and pretty printing capabilities
* **format_str** - format a string to certain width and alignment. Supports wide characters like Chinese and Japanese
* **compare_obj** - recursively compare two objects (dicts, lists, etc.) and print differences with rich formatting
* **rprint** - print function using the rich library for colored and styled terminal output

**Date & Time:**
* **MyTime** - a datetime wrapper that makes timezone conversions easy (local, JST, naive)
* **parse_to_shortdate** - parse a date string to a short date string ('%y%m%d'). Supports more East Asian language formats than `dateutil.parser`