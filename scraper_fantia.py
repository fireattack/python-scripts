import concurrent.futures
import re
import webbrowser
from pathlib import Path
from urllib.parse import urljoin

# from natsort import natsorted
from bs4 import BeautifulSoup

from util import download, get_webname, requests_retry_session, safeify

API_POSTS = "https://fantia.jp/api/v1/posts/{}"
API_FANCLUB = "https://fantia.jp/api/v1/fanclubs/{}"
HTML_POSTLIST = "https://fantia.jp/fanclubs/{}/posts?page={}"
DEFAULT_UA = 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.99 Safari/537.36'

class FantiaDownloader:
    def __init__(self, key, fanclub=None, output='.', subfolder_template=None, skip_existing=True, quick_stop=True):
        super().__init__()
        self.key = key
        self.fanclub = fanclub
        if not self.fanclub:
            print('[W] no fanclub id is given. "downloadAll()" won\'t work.')
        self.output = Path(output)
        self.subfolder_template = subfolder_template or '{fanclub_full_name} ({fanclub_id})'
        self.subfolder_name = None
        #TODO: self.filename_template = '{id} {title}'
        self.skip_existing = skip_existing
        self.quick_stop = skip_existing and quick_stop
        self.fanclub_info = None

        self.session = requests_retry_session()
        self.session.headers['User-Agent'] = DEFAULT_UA
        self.session.cookies.update({"_session_id": self.key})
        self.token = None
        self.__set_token__()

    def __set_token__(self):
        r = self.fetch('https://fantia.jp/')
        soup = BeautifulSoup(r.content, 'html.parser')
        if ele := soup.select_one('meta[name="csrf-token"]'):
            print(f'Set csrf-token = {ele["content"]}')
            self.token = ele['content']
            self.session.headers['x-csrf-token'] = self.token
        else:
            raise Exception('Failed to obtain csrf-token!!')

    def fetch(self, url, headers=None):
        return self.session.get(url, headers=headers)

    def download_all(self):
        if not self.fanclub:
            print('No fanclub id is given. "downloadAll()" won\'t work.')
            return
        if not self.fanclub_info:
            with self.fetch(API_FANCLUB.format(self.fanclub)) as r:
                self.update_fanclub_info(r.json()['fanclub'])

        output_full = self.output / self.subfolder_name
        print(f'Fanclub {self.fanclub}: download all to {output_full}.')
        if output_full.exists():
            existing_ids = [m[1] for f in output_full.iterdir() if (m := re.match(r'(\d+) *', f.name))]
            existing_ids = list(dict.fromkeys(existing_ids))
        else:
            existing_ids = []
        print(f'{len(existing_ids)} ID(s) have already been downloaded.')

        def fetch_all():
            results = []; page = 1
            while True:
                print(f"Attempting to fetch page {page}...")
                out = self.fetch_gallery_page(page)
                if out:
                    # do NOT sort; since the order is not id_desc
                    # out = natsorted(out, reverse=True)
                    for id in out:
                        if self.quick_stop and id in existing_ids:
                            print(f'Encountered existing id {id}. Quick stop.')
                            return results
                        results.append(id)
                    page += 1
                else:
                    return results

        results = fetch_all()
        results = list(dict.fromkeys(results))
        print(f"Get {len(results)} ID(s) from list.")

        skipped = []; to_be_dl = []
        for id in results:
            if self.skip_existing and id in existing_ids:
                skipped.append(id)
            else:
                to_be_dl.append(id)
        if skipped:
            print(f"Skip {len(skipped)} existing ID(s).")
        if to_be_dl:
            # Only create the output directory if we're actually going to download something
            self.output.mkdir(parents=True, exist_ok=True)
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
                for id in to_be_dl:
                    ex.submit(self.get_post_photos, id)

    def fetch_gallery_page(self, page):
        url = HTML_POSTLIST.format(self.fanclub, page)
        r = self.fetch(url)
        r.encoding = 'utf-8'
        html = r.text
        return re.findall(r'\/posts\/(?P<id>[0-9]{1,8})"', html)

    def update_fanclub_info(self, d):
        self.fanclub_info = d
        substitutes = dict(
            fanclub_full_name=self.fanclub_info['fanclub_name_with_creator_name'],
            fanclub_name=self.fanclub_info['fanclub_name'],
            creater_name=self.fanclub_info['creator_name'],
            fanclub_id=self.fanclub_info['id']
        )
        substitutes = {k: safeify(str(v)) for k, v in substitutes.items()}
        if not self.subfolder_name:
            self.subfolder_name = self.subfolder_template.format(**substitutes)

    def get_post_photos(self, id):
        print(f'Fetching post {id}...')
        while True:
            d = self.fetch(API_POSTS.format(id), headers={'x-requested-with': 'XMLHttpRequest'}).json()

            if 'redirect' in d:
                recaptcha_url = urljoin(API_POSTS, d["redirect"])
                # open recaptcha_url in browser
                webbrowser.open(recaptcha_url)
                input(f'Please solve the recaptcha at {recaptcha_url} and then press any key')
            else:
                break
        if 'error_text' in d:
            print(f'Error: {d["error_text"]}')
            raise Exception(f'Error: {d["error_text"]}')

        if not self.fanclub_info:
            self.update_fanclub_info(d['post']['fanclub'])

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
            if thumb := d['post'].get('thumb', None):
                img_url = thumb['original']
                stem, ext = get_webname(img_url).rsplit('.', 1)
                ex.submit(download, img_url, filename= self.output / self.subfolder_name / f'{id} !cover.{ext}', verbose=1)
            if post_contents := d['post'].get('post_contents', None):
                for c in post_contents:
                    cid = c['id']
                    if photos := c.get('post_content_photos', None):
                        for idx, p in enumerate(photos, 1):
                            img_url = p['url']['original']
                            stem, ext = get_webname(img_url).rsplit('.', 1)
                            # Clean up the filename; remove all the UUID-ish garbage
                            stem = re.sub(r'^[0-9a-fA-F]{8}_(.+)$', r'\1', stem)
                            stem = re.sub(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', '', stem)
                            idx_string = '_' + str(idx).zfill(len(str(len(photos)))) if len(photos) > 1 else ''
                            stem = f'{id} {cid}{idx_string} {stem}'.strip()
                            ex.submit(download, img_url, filename=self.output / self.subfolder_name / f'{stem}.{ext}', verbose=1)
                    if 'download_uri' in c:
                        dl_url = urljoin('https://fantia.jp', c['download_uri'])
                        ex.submit(download, dl_url, filename=self.output / self.subfolder_name / f'{id} {cid} {c["filename"]}', session=self.session, verbose=1)

if __name__ == "__main__":
    pass
