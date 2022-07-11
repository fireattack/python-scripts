# python

Some small Python utilities.

## `oricon.py`

Quickly download all the highest quality pictures from any Oricon news, special or photo article.

## `scraper_ameblo_api.py`

[Ameblo](https://ameblo.jp/) (アメーバブログ or アメブロ, Japanese blog service) downloader. Supports images and text.

Usage:

```python
from scraper_ameblo_api import download_all

download_all('user_id', save_folder='.', until=None, last_entry='auto', download_type='all')
```

## `scraper_fantia.py`

Fantia downloader. Inspired by [dumpia](https://github.com/itskenny0/dumpia).

Usage:

```python
from scraper_fantia import FantiaDownloader

key = 'your _session_id' # copy it from cookie `_session_id` on fantia.jp
id = 1111111111111111111
downloader = FantiaDownloader(fanclub=id, output=".", key=key)
downloader.downloadAll()
```

Or just download certain post (you can omit fanclub id in this case):

```python
downloader = FantiaDownloader(output=".", key='your _session_id')
downloader.getPostPhotos(12345)
```

## `scraper_radiko.py`

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

## `util.py`

Some utility functions mainly for myself. Read the code to get the idea. Some highlights:
* download - a generic downloader