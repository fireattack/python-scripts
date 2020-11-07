from util import download
import requests
import re
from pathlib import Path
from urllib.parse import unquote, urljoin
import concurrent.futures

API_POSTS = "https://fantia.jp/api/v1/posts/{}"
API_FANCLUB = "https://fantia.jp/api/v1/fanclubs/{}" # Not used for now
HTML_POSTLIST = "https://fantia.jp/fanclubs/{}/posts?page={}"

class FantiaDownloader:

    def __init__(self, fanclub, output, key, skip_existing=True):
        super().__init__()
        self.key = key
        self.fanclub = fanclub
        self.output = Path(output)
        self.skip_existing = skip_existing

    def fetch(self, url):
        return requests.get(url, cookies={"_session_id": self.key})

    def downloadAll(self):
        if not self.output.exists():
            self.output.exists.mkdir(parents=True, exist_ok=True)
        existing_ids = [m[1] for f in self.output.iterdir() if (m := re.match(r'(\d+) *', f.name))]
        existing_ids = list(dict.fromkeys(existing_ids))
        print(f'{len(existing_ids)} IDs have already been downloaded.')

        page = 1
        results = []

        while True:
            print(f"Attempting to fetch page {page}...")
            out = self.fetchGalleryPage(page)
            if out:
                results.extend(out)
                page += 1
            else:
                break
        results = list(dict.fromkeys(results))
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
            for id in results:
                if self.skip_existing and id in existing_ids:
                    print(f'{id} is already downloaded. Skip.')
                    continue
                ex.submit(self.getPostPhotos, id)

    def fetchGalleryPage(self, page):
        url = HTML_POSTLIST.format(self.fanclub, page)
        r = self.fetch(url)
        r.encoding = 'utf-8'
        html = r.text
        return re.findall(r'\/posts\/(?P<id>[0-9]{1,8})', html)

    def getPostPhotos(self, id):
        def getWebName(url):
            name = unquote(url.split('?')[0].split('/')[-1])
            return name.rsplit('.', 1)

        print(f'Fetching post {id}...')
        d = self.fetch(API_POSTS.format(id)).json()
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
            if thumb := d['post'].get('thumb', None):
                img_url = thumb['original']
                stem, ext = getWebName(img_url)                
                ex.submit(download, img_url, filename= self.output / f'{id} !cover.{ext}', verbose=1)
            if post_contents := d['post'].get('post_contents', None):
                for c in post_contents:
                    cid = c['id']
                    if photos := c.get('post_content_photos', None):
                        for idx, p in enumerate(photos, 1):
                            img_url = p['url']['original']
                            stem, ext = getWebName(img_url)
                            # Clean up the filename; remove all the UUID-ish garbage
                            stem = re.sub(r'^[0-9a-fA-F]{8}_(.+)$', r'\1', stem)
                            stem = re.sub(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', '', stem)
                            idx_string = '_' + str(idx).zfill(len(str(len(photos)))) if len(photos) > 1 else ''
                            stem = f'{id} {cid}{idx_string} {stem}'.strip()
                            ex.submit(download, img_url, filename=self.output / f'{stem}.{ext}', verbose=1)
                    if 'download_uri' in c:
                        dl_url = urljoin('https://fantia.jp', c['download_uri'])
                        ex.submit(download, dl_url, filename=self.output / f'{id} {cid} {c["filename"]}', cookies={"_session_id": self.key}, verbose=1)

if __name__ == "__main__":
    pass