# python

Some small Python utilities.

## `oricon.py`

Quickly download all the highest quality pictures from any Oricon news, special or photo article.

Usage:

```
oricon.py https://www.oricon.co.jp/news/2236438/
```

## `scraper_lineblog.py`

[LINE BLOG](https://www.lineblog.me/) downloader. Download both images and text.

Usage:

CLI:

```
usage: scraper_lineblog.py [-h] [--output OUTPUT] [--start START] [--until UNTIL] [--threads THREADS] user_id

Download LINE BLOG articles (text and images).

positional arguments:
  user_id               LINE BLOG user id

options:
  -h, --help            show this help message and exit
  --output OUTPUT, -o OUTPUT
                        folder to save files (default: {CWD}/{user_id})
  --start START         download starting from this page (inclusive) (default: 1)
  --until UNTIL         download until this page (inclusive) (default: None (download to the last page)
  --threads THREADS, --thread THREADS
                        download threads (default: 20)
```
As Python module:

```python
from scraper_lineblog import main

main('user_id', save_folder='.')
```

## `scraper_ameblo_api.py`

[Ameblo](https://ameblo.jp/) (アメーバブログ or アメブロ, Japanese blog service) downloader. Supports images and text.

Usage:

Note: make sure you also downloaded `util.py` file from the same directory.

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

Install these first:

```
pip install browser-cookie3 websocket-client rich python-dateutil pytz requests beautifulsoup4 lxml
npm i minyami -g
```

CLI:

```
usage: nico.py [-h] [--info] [--verbose] [--thumb] [--cookies COOKIES] [--comments {yes,no,only}] url

positional arguments:
  url                   URL or ID of nicovideo webpage

options:
  -h, --help            show this help message and exit
  --info, -i            Print info only.
  --verbose             Print more info.
  --thumb               Download thumbnail only. Only works for video type (not live).
  --cookies COOKIES, -c COOKIES
                        Cookie source. [Default: chrome]
                        Provide either:
                          - A browser name to fetch from;
                          - The value of "user_session";
                          - A Netscape-style cookie file.
  --comments {yes,no,only}, -d {yes,no,only}
                        Control if comments (danmaku) are downloaded. [Default: yes]
```

## `util.py`

Some utility functions mainly for myself. Read the code to get the idea.

Some highlights:

* download - a generic downloader
* format_str - format a string to certain width and alignment. Supports wide characters like Chinese and Japanese.
* compare_obj - recursively compare two objects.
* Table - a simple table class.
* parse_to_shortdate - parse a date string to a short date string ('%y%m%d'). Supports more East Asian language formats than `dateutil.parser`.