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


def download(url_or_res, f):
    if isinstance(url_or_res, str):
        r = requests.get(url_or_res, stream=True)
    else:
        r = url_or_res

    with f.open('wb') as fio:
        for chunk in r.iter_content(chunk_size=8192):
            if chunk:
                fio.write(chunk)

def get_orig(url):
    def bytes_to_kb(bytes):
        bytes = int(bytes)
        return f'{bytes/1000:.2f} KB'

    def get_jpeg_quality(f):
        from subprocess import check_output
        output = check_output(['magick', 'identify', '-format', '%Q;%[jpeg:sampling-factor]', f])
        quality, sampling_factor = output.decode('utf8').split(';')
        return int(quality), sampling_factor

    f = Path.cwd() / get_webname(url)
    download(url, f)
    q, sampling_factor = get_jpeg_quality(f)
    if q == 85 and sampling_factor == '2x2,1x1,1x1':
        print(f'{f.name} is likely re-compressed: q{q} ({sampling_factor}). Trying to get original...')
    else:
        print(f'{f.name} is already original: q{q} ({sampling_factor}). Done!')
        f.rename(f.with_name(f'{f.stem}_orig.jpg'))
        return True
    filesize = f.stat().st_size # cache filesize
    tries = 0
    while True:
        tries += 1
        r = requests.get(url, stream=True)
        if r.headers['Content-length'] == str(filesize):
            print(f'{f.name}: remote is still the same size')
        else:
            print(f'{f.name}: remote now is different ({bytes_to_kb(filesize)} -> {bytes_to_kb(r.headers["Content-length"])})')
            savef = f.with_name(f'{f.stem}_orig.jpg')
            download(r, savef)
            newq, new_sampling_factor = get_jpeg_quality(savef)
            if newq == 85 and new_sampling_factor == '2x2,1x1,1x1':
                continue
            print(f'{f.name}: done! q{q} ({sampling_factor}) -> q{newq} ({new_sampling_factor})')
            f.unlink()
            return True
        if tries > 100:
            print(f'Failed to get uncompressed version of {url} after 100 tries.')
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
    print(f'Getting images from {url}')
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