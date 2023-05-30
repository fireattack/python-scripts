import concurrent.futures
import json
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def safeify(name):
    template = {u'\\': u'＼', u'/': u'／', u':': u'：', u'*': u'＊', u'?': u'？', u'"': u'＂', u'<': u'＜', u'>': u'＞', u'|': u'｜', '\n': '', '\r': '', '\t': ''}
    for illegal in template:
        name = name.replace(illegal, template[illegal])
    return name


def dump_json(mydict, filename):
    filename = Path(filename)
    if filename.suffix.lower() != '.json':
        filename = filename.with_suffix('.json')
    filename.parent.mkdir(parents=True, exist_ok=True)
    with filename.open('w', encoding='utf-8') as f:
        json.dump(mydict, f, ensure_ascii=False, indent=2)


# Modified from https://www.peterbe.com/plog/best-practice-with-retries-with-requests
def requests_retry_session(retries=5, backoff_factor=0.2):
    session = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=None,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


def get(url):
    r = requests_retry_session().get(url)
    return BeautifulSoup(r.content, 'html.parser')


def parse_list(user_id, start, until, threads=20):
    results = []

    def parse_list_single(page):
        print(f'Parsing page {page}...')
        url = f'https://lineblog.me/{user_id}/?p={page}'
        selector = 'article'
        items = get(url).select(selector)
        print(f'Got {len(items)} articles from page {page}.')
        results.extend(items)

    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as ex:
        for i in range(start, until + 1):
            ex.submit(parse_list_single, i)
    return results


def parse_item(soup, save_folder, verbose=False):
    content = soup.text
    content_html = str(soup)
    url = soup.select_one('h1 > a')['href']
    user_id, post_id = re.search(r'lineblog\.me/([^/]+)/archives/(\d+)', url).groups()
    title = soup.select_one('h1.article-title').text
    time = soup.select_one('time')['datetime']
    date = time.split('T')[0].replace('-', '')[2:]  # YYMMDD

    filename_prefix = safeify(f'{date} lineblog_{user_id}_{post_id} {title}')  # path-safe name

    img_eles = soup.select('div.article-body-inner img')
    img_urls = []
    for idx, ele in enumerate(img_eles, 1):
        # for some reason it has a space at the end sometimes
        img_url = ele['src'].strip()
        if 'line.blogimg.jp' in img_url:
            img_url = re.sub(r'(\/[^/.]*)-[sm](\.[^/.]*)', r'\1\2', img_url)
        if 'line-scdn.net' in img_url:
            img_url = re.sub(r'(:\/\/[^/]*\/[-_0-9A-Za-z]*)\/[a-z0-9]*$', r'\1', img_url)
        img_name = ''
        # add original filename if exist
        if 'alt' in ele.attrs:
            img_name = ele['alt'].rsplit('.', 1)[0]  # remove extension, since we will get it from header later.
        img_name = safeify(f'{filename_prefix}_{idx} {img_name}'.strip())

        tries = 0
        while tries < 5:
            try:
                with requests_retry_session().get(img_url, stream=True) as r:
                    suffix = '.' + r.headers['content-type'].split('/')[-1].replace('jpeg', 'jpg')
                    expected_filesize = int(r.headers['content-length'])
                    f = save_folder / (img_name + suffix)
                    f_temp = f.with_name(f.name + '.dl')
                    if f.exists() and expected_filesize == f.stat().st_size:
                        verbose and print(f'[I] {f.name} already exists and is identical. Skip.')
                        if f_temp.exists():
                            # if f already exists and is good, remove any potential temp file from previous download(s).
                            f_temp.unlink()
                        break
                    else:
                        if f.exists() and expected_filesize != f.stat().st_size:
                            print(f'[W] {f.name} already exists but filesize is a mismatch. Re-download and overwrite.')
                        verbose and print(f'[I] Downloading {f.name} from {img_url}...')
                        with f_temp.open('wb') as fio:
                            for chunk in r.iter_content(chunk_size=8192):
                                if chunk:
                                    fio.write(chunk)
                        if f_temp.stat().st_size == expected_filesize:
                            # remove old, broken file.
                            if f.exists():
                                f.unlink()
                            f_temp.rename(f)
                            break
                        else:
                            print(f'[E] {f.name}: file download failed: filesize does not match. Retry...')
                            f_temp.unlink()
            except Exception as e:
                print(f'[E] {img_name}: file download failed: {e}. Retry...')
            tries += 1

        img_urls.append((img_url, f.name))

    (save_folder / 'text').mkdir(exist_ok=True)
    (save_folder / 'text' / f'{filename_prefix}.html').write_text(content_html, encoding='utf-8')

    data = dict(user_id=user_id, post_id=post_id, url=url, title=title, time=time, date=date, content=content, content_html=content_html, img_urls=img_urls)
    (save_folder / 'metadata').mkdir(exist_ok=True)
    dump_json(data, (save_folder / 'metadata' / f'{filename_prefix}.json'))


def main(user_id, save_folder, start=1, until=None, threads=20, verbose=False):
    save_folder = Path(save_folder)

    if until is None:
        # get the last page.
        print('No last page given. Fetch the last page...')
        soup = get(f'https://lineblog.me/{user_id}/')
        until = int(soup.select_one('li.paging-last>a').text)
        print(f'The last page is {until}.')

    items = parse_list(user_id, start, until, threads=threads)
    print(f'Find {len(items)} articles in total.')

    if items:
        save_folder.mkdir(exist_ok=True, parents=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as main_e:
            for item in items:
                main_e.submit(parse_item, item, save_folder, verbose=verbose)
    else:
        print('[W] find no articles. Please check parameters.')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Download LINE BLOG articles (text and images).')
    parser.add_argument('user_id', help='LINE BLOG user id')
    parser.add_argument('--output', '-o', help='folder to save files (default: {CWD}/{user_id})')
    parser.add_argument('--start', default=1, type=int, help='download starting from this page (inclusive) (default: 1)')
    parser.add_argument('--until', type=int, help='download until this page (inclusive) (default: None (download to the last page)')
    parser.add_argument('--threads', '--thread', type=int, help='download threads (default: 20)')
    parser.add_argument('--verbose', '-v', action='store_true', help='verbose mode')

    args = parser.parse_args()
    save_folder = args.output if args.output else args.user_id
    main(args.user_id, save_folder=save_folder, start=args.start, until=args.until, threads=args.threads, verbose=args.verbose)
