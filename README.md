# python
 
Some small Python utilities 

## `fantia.py`

Fantia downloader. Inspired by [dumpia](https://github.com/itskenny0/dumpia).

Usage:

```python
from fantia import FantiaDownloader

key = 'your _session_id' # copy it from cookie `_session_id` on fantia.jp
id = 1111111111111111111
downloader = FantiaDownloader(fanclub=id, output=".", key=key)
downloader.downloadAll()
```