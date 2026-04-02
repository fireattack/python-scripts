import concurrent.futures
import re
import webbrowser
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

# from natsort import natsorted
from bs4 import BeautifulSoup

from util import download, get_webname, requests_retry_session, safeify

API_POSTS = "https://fantia.jp/api/v1/posts/{}"
API_FANCLUB = "https://fantia.jp/api/v1/fanclubs/{}"
HTML_POSTLIST = "https://fantia.jp/fanclubs/{}/posts?page={}"
DEFAULT_UA = 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.99 Safari/537.36'

# Default templates for directory and filename formatting
# Directory template variables:
#   {fanclub_id}, {fanclub_name}, {fanclub_full_name}, {creator_name}
#   {post_id}, {post_title}, {post_date}, {rating}
# Filename template variables (in addition to directory ones):
#   {content_id}, {idx}, {stem_cleaned}
# Note: extension (.ext) is always appended automatically and not part of the template
DEFAULT_DIR_TEMPLATE = '{fanclub_full_name} ({fanclub_id})/{post_id} {post_title}'
DEFAULT_FILENAME_TEMPLATE = '{content_id}{idx} {stem_cleaned}'


class FantiaDownloader:
    def __init__(self, key, fanclub=None, output='.', dir_template=None, filename_template=None, skip_existing=True, quick_stop=True):
        super().__init__()
        self.key = key
        self.fanclub = fanclub
        if not self.fanclub:
            print('[W] no fanclub id is given. "downloadAll()" won\'t work.')
        self.output = Path(output)
        self.dir_template = dir_template or DEFAULT_DIR_TEMPLATE
        self.filename_template = filename_template or DEFAULT_FILENAME_TEMPLATE
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

        # Get base output dir (fanclub level) for checking existing downloads
        # Extract only the fanclub-level part of the template (before any post-level placeholders)
        fanclub_subs = self._get_fanclub_substitutes()
        # Split dir_template and only format the parts that don't require post info
        template_parts = self.dir_template.split('/')
        base_parts = []
        for part in template_parts:
            if any(p in part for p in ['{post_id}', '{post_title}', '{post_date}', '{rating}']):
                break
            base_parts.append(part.format(**fanclub_subs))
        base_dir = self.output / '/'.join(base_parts) if base_parts else self.output

        print(f'Fanclub {self.fanclub}: download all to {base_dir}.')
        existing_ids = []
        if base_dir.exists():
            # Check for subdirectories starting with post_id (new structure)
            for f in base_dir.iterdir():
                if f.is_dir() and (m := re.match(r'^(\d+)\b', f.name)):
                    existing_ids.append(m.group(1))
            # Also check for files starting with post_id (old flat structure)
            for f in base_dir.iterdir():
                if f.is_file() and (m := re.match(r'^(\d+)\b', f.name)):
                    existing_ids.append(m.group(1))
            existing_ids = list(dict.fromkeys(existing_ids))
            existing_ids = set(map(int, existing_ids))

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
        return sorted(map(int, re.findall(r'\/posts\/(?P<id>[0-9]{1,8})"', html)), reverse=True)

    def update_fanclub_info(self, d):
        self.fanclub_info = d

    def _get_fanclub_substitutes(self):
        """Get template substitutes from fanclub info."""
        if not self.fanclub_info:
            return {}
        return dict(
            fanclub_full_name=safeify(str(self.fanclub_info['fanclub_name_with_creator_name'])),
            fanclub_name=safeify(str(self.fanclub_info['fanclub_name'])),
            creator_name=safeify(str(self.fanclub_info['creator_name'])),
            fanclub_id=self.fanclub_info['id']
        )

    def _get_post_substitutes(self, post_data):
        """Get template substitutes from post data."""
        # Parse posted_at date (format: "Fri, 16 Aug 2024 07:15:36 +0900")
        post_date = ''
        if posted_at := post_data.get('posted_at'):
            try:
                dt = datetime.strptime(posted_at, "%a, %d %b %Y %H:%M:%S %z")
                post_date = dt.strftime('%Y%m%d')
            except ValueError:
                post_date = ''

        return dict(
            post_id=post_data.get('id', ''),
            post_title=safeify(str(post_data.get('title', ''))),
            post_date=post_date,
            rating=post_data.get('rating', '')
        )

    def _format_dir(self, post_substitutes):
        """Format directory path using template and substitutes."""
        subs = {**self._get_fanclub_substitutes(), **post_substitutes}
        return self.dir_template.format(**subs)

    def _format_filename(self, post_substitutes, content_id, idx_string, stem_cleaned, ext):
        """Format filename using template and substitutes."""
        subs = {
            **self._get_fanclub_substitutes(),
            **post_substitutes,
            'content_id': content_id,
            'idx': idx_string,
            'stem_cleaned': stem_cleaned
        }
        # Format the template, strip to remove trailing spaces, then append extension
        filename_without_ext = self.filename_template.format(**subs).strip()
        return f'{filename_without_ext}.{ext}'

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

        post_data = d['post']
        post_subs = self._get_post_substitutes(post_data)
        output_dir = self.output / self._format_dir(post_subs)
        # Ensure multi-level directory exists
        output_dir.mkdir(parents=True, exist_ok=True)

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
            if thumb := post_data.get('thumb', None):
                img_url = thumb['original']
                stem, ext = get_webname(img_url).rsplit('.', 1)
                cover_filename = f'!cover.{ext}'
                ex.submit(download, img_url, filename=output_dir / cover_filename, verbose=1)
            if post_contents := post_data.get('post_contents', None):
                for c in post_contents:
                    cid = c['id']
                    if photos := c.get('post_content_photos', None):
                        for idx, p in enumerate(photos, 1):
                            img_url = p['url']['original']
                            stem, ext = get_webname(img_url).rsplit('.', 1)
                            # Clean up the filename; remove all the UUID-ish garbage
                            stem_cleaned = re.sub(r'^[0-9a-fA-F]{8}_(.+)$', r'\1', stem)
                            stem_cleaned = re.sub(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', '', stem_cleaned)
                            stem_cleaned = stem_cleaned.strip()
                            idx_string = '_' + str(idx).zfill(len(str(len(photos)))) if len(photos) > 1 else ''
                            filename = self._format_filename(post_subs, cid, idx_string, stem_cleaned, ext)
                            ex.submit(download, img_url, filename=output_dir / filename, verbose=1)
                    if 'download_uri' in c:
                        dl_url = urljoin('https://fantia.jp', c['download_uri'])
                        # For download files, use original filename with content_id prefix
                        dl_filename = f'{cid} {c["filename"]}'
                        ex.submit(download, dl_url, filename=output_dir / dl_filename, session=self.session, verbose=1)

if __name__ == "__main__":
    pass
