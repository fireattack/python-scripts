from pathlib import Path
import re
import sys
from shutil import which
from urllib.parse import urljoin, unquote


import requests
from bs4 import BeautifulSoup


def get_webname(url):
    return unquote(url.split('?')[0].split('/')[-1])

def get(url):
    r = requests.get(url)
    r.encodings = 'shift-jis'
    return BeautifulSoup(r.content, 'html.parser')

def get_orig(url, save_dir='.', test_mode=False, bad_file='delete'):

    def bytes_to_kb(bytes):
        bytes = int(bytes)
        return f'{bytes/1000:.3f} KB'

    def get_jpeg_quality(f):
        from subprocess import check_output
        output = check_output(['magick', 'identify', '-format', '%Q;%[jpeg:sampling-factor]', f])
        quality, sampling_factor = output.decode('utf8').split(';')
        return int(quality), sampling_factor

    def download(url_or_res, f):
        if isinstance(url_or_res, str):
            r = requests.get(url_or_res, stream=True)
        else:
            r = url_or_res

        with f.open('wb') as fio:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    fio.write(chunk)

    def check_quality(f):
        size = f.stat().st_size
        q, sampling_factor = get_jpeg_quality(f)
        print(f'{bytes_to_kb(size)}, q{q}, {sampling_factor}')
        if q == 85 and sampling_factor == '2x2,1x1,1x1':
            return 'bad'
        if q > 85:
            return 'good'
        return 'not sure'

    save_dir = Path(save_dir)
    print(f'Getting {url}')

    web_name = get_webname(url)
    f = save_dir / web_name
    download(url, f)

    print('    First try: ', end='')
    old_quality = check_quality(f)
    if old_quality == 'good':
        f.rename(f.with_name(f'{f.stem}_orig.jpg'))
        print(f'    Find original. Stop.')
        return True
    if old_quality == 'bad':
        print(f'    Likely re-compressed.')

    else:
        print(f'    First try: not sure. Try to get a different one anyway.')

    filesize = f.stat().st_size # cache filesize
    tries = 0
    while True:
        tries += 1
        r = requests.get(url, stream=True)
        if r.headers['Content-length'] == str(filesize):
            print(f'    Remote is still the same size.')
        else:
            print(f'    Got a different file: ', end='')
            savef = f.with_name(f'{f.stem}_orig.jpg')
            download(r, savef)
            new_quality = check_quality(savef)
            new_filesize = savef.stat().st_size
            if test_mode:
                print(f'    Test mode. So keep both files.')
                f.rename(f.with_name(f'{f.stem}_{filesize}.jpg'))
                savef.rename(f.with_name(f'{f.stem}_{new_filesize}.jpg'))
                return True
            # potential results:
            # bad -> good, not sure -> good: keep new
            if old_quality == 'bad' and new_quality == 'good' \
                or old_quality == 'not sure' and new_quality == 'good':
                print(f'    New file is original. Stop and cleanup.')
                if bad_file == 'delete':
                    f.unlink()
                elif bad_file == 'keep':
                    f.rename(f.with_name(f'{f.stem}_bad.jpg'))
                elif bad_file == 'move_to_subfolder':
                    (save_dir / 'tobedel').mkdir(exist_ok=True)
                    f.rename(save_dir / 'tobedel' / f.name)
                savef.rename(f.with_name(f'{f.stem}_orig.jpg'))
                return True
            # bad -> not sure, bad -> bad, not sure -> not sure, not sure -> bad: keep both
            print('    Not sure which one is better. Save both. Please check yourself.')
            f.rename(f.with_name(f'{f.stem}_{filesize}.jpg'))
            savef.rename(f.with_name(f'{f.stem}_{new_filesize}.jpg'))
            return True

        if tries > 100:
            print(f'    Failed to get a different version of {url} after 100 tries.')
            return True

def main(url):
    img_url_candidates = []
    def get_image_from_photo_page(soup):
        if (ele := soup.find('meta', {'property': 'og:image'})) and ele.has_attr('content'):
            url = ele['content']
            url = re.sub(r'cdn-cgi/image/[^/]+/upimg', 'upimg', url)
            img_url_candidates.append(url)
        else:
            img_url_candidates.append(soup.select_one('div#main_photo img')['src'])

    url = re.sub(r'/news/(\d+)/*.+$', r'/news/\1/photo/1/', url)
    print(f'Getting image from {url}')
    soup = get(url)

    get_image_from_photo_page(soup)

    for a in soup.select(('div.photo_slider li > a')):
        new_url = urljoin(url, a['href'])
        if new_url == url:
            continue
        print(f'Getting image from {new_url}')
        soup2 = get(new_url)
        get_image_from_photo_page(soup2)
    img_url_candidates = list(dict.fromkeys(img_url_candidates))

    for photo_url in img_url_candidates:
        get_orig(photo_url)


if __name__ == '__main__':
    # detect magick
    if not which('magick'):
        print('magick is not installed. Please install it.')
        sys.exit(1)

    if len(sys.argv) < 2:
        print('Usage: oricon.py <url>')
        sys.exit(1)
    else:
        url = sys.argv[1]
        main(url)