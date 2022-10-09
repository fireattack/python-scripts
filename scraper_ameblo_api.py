import re
from pathlib import Path
import requests
from urllib.parse import urljoin
import concurrent.futures
import json
from dateutil import parser as dateparser

from util import safeify, download, get, dump_json, parse_to_shortdate

def load_init_data(soup):
    for script in soup('script'):
        if 'window.INIT_DATA' in script.text:
            return json.loads(re.search(r'window\.INIT_DATA *= *(.+);window\.RESOURCE_BASE_URL', script.text)[1])
    return None

def first(my_dict):
    return list(my_dict.values())[0]

def download_image(blog_id, id, save_folder='.'):
    # print(f'Processing {id}...')
    data = requests.get(f'https://blogimgapi.ameba.jp/blog/{blog_id}/entries/{id}/images').json()

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        for idx, img in enumerate(data['data'], 1):
            img_url = urljoin('https://stat.ameba.jp/', img['imgUrl'])
            img_url = re.sub(r'^(.+)\?(.+)$', r'\1', img_url)  # Remove parameters
            img_url = re.sub(r'\/t[0-9]*_([^/]*)$', r'/o\1', img_url)
            date = parse_to_shortdate(img['date'])
            img_date = parse_to_shortdate(re.search(r'user_images/(\d+)/', img_url)[1])
            if date != img_date:
                img_date = f'{date} ({img_date})'
            file_name = img_url.split('/')[-1]
            desc = img['title']
            desc_ = f'{desc}_{idx}' if len(data['data']) > 1 else desc
            img_name = safeify(f'{img_date} ameblo_{blog_id}_{id} {desc_} {file_name}')
            ex.submit(download, img_url, Path(save_folder) / img_name, dupe='skip', verbose=1)

def download_text(blog_id, id, save_folder='.'):
    # print(f'Processing {id}...')
    url = f'https://ameblo.jp/{blog_id}/entry-{id}.html'
    soup = get(url)
    data = load_init_data(soup)
    if data:
        print('.', end="", flush=True)
        b = data['entryState']['entryMap'][str(id)]
        title = b['entry_title']
        text = b['entry_text']
        time = b['entry_created_datetime']
        date = dateparser.parse(time).strftime('%y%m%d_%H%M%S') # keep HMS as well for text

        #Dump
        text_folder = Path(save_folder) / 'text'
        text_folder.mkdir(exist_ok=True, parents=True)
        stem = f'{date} ameblo_{blog_id}_{id} {title}'

        html = text_folder / safeify(f'{stem}.html')
        if html.exists():
            print(f'{html.name} Already exists! Ignore.')
            return
        html.write_text(text, encoding='utf8')
        metadata_folder = Path(save_folder) / 'metadata'
        metadata_folder.mkdir(exist_ok=True, parents=True)
        metadata = metadata_folder / safeify(f'{stem}.json')
        dump_json(b, metadata)
    else:
        print(f'[E] cannot fetch data from {url}!')

# This API only list posts with images. Abandoned.
def parse_image_list(blog_id, start_entry, until=None):
    results = []
    while True:
        print(f'Parsing {blog_id} starting from {start_entry}...')
        myjson = requests.get(
            f'https://blogimgapi.ameba.jp/blog/{blog_id}/entries/{start_entry}/neighbors?limit=100').json()
        for entry in myjson['data']:
            id = entry["entryId"]
            if until and str(id) == str(until):
                print(f'Reached last record {until}! Stopping..')
                return results
            results.append(id)
        if not myjson['paging']['nextUrl']:
            return results
        start_entry = re.search(r'/entries/(\d+)/', myjson['paging']['nextUrl'])[1]


def parse_list(blog_id, theme_name=None, limit=10, until=None):
    try: # Get blog_num_id
        soup = get(f'https://ameblo.jp/{blog_id}/')
        data = load_init_data(soup)
        blog_num_id = first(data['bloggerState']['bloggerMap'])['blog']
        endpoint = f'https://ameblo.jp/_api/blogEntries;blogId={blog_num_id};'

        if theme_name:
            # get themes
            first_theme_id = first(data['bloggerState']['blogMap']).get('moblog_theme_id', None) or first(data['entryState']['entryMap']).get('theme_id', None)
            soup2 = get(f'https://ameblo.jp/{blog_id}/theme-{first_theme_id}.html')
            data2 = load_init_data(soup2)
            themes = data2['themesState']['themeMap']
            theme_id_to_be_used = None
            print('Available theme:')
            for theme_id, info in themes.items():
                name = info['theme_name']
                count = info['entry_cnt']
                print(f'{name} (id: {theme_id}, count: {count})')
                if name == theme_name:
                    theme_id_to_be_used = theme_id
            if not theme_id_to_be_used:
                print(f'[E] target theme \'{theme_name}\' not found in themes! Stop.')
                return []
            endpoint = f'https://ameblo.jp/_api/blogThemeEntries;blogId={blog_num_id};themeId={theme_id_to_be_used};'

    except Exception as ex:
        print(f'[E] failed when parsing frontpage for {blog_id}.')
        print(ex)
        return []

    ids = []
    offset = 0
    while True:
        url = f'{endpoint}limit={limit};offset={offset}'
        print(f'Loading {url}...')
        data = requests.get(url).json()

        if theme_name:
            blogs = data['entryMap']
            paging =  data['paging']
        else:
            blogs = data['entities']['entryMap']
            paging = first(data['entities']['blogPageMap'])['paging']
        for entry_id, entry in blogs.items():
            if entry['publish_flg'] == 'amember':
                print(f'[W] cannot get post {entry_id} since it\'s amember only.')
                continue
            if until and str(entry_id) == str(until):
                print(f'Reached last record {until}! Stop.')
                return ids
            ids.append(entry_id)
        offset = paging['next']
        total_count = paging['total_count']
        if total_count == offset:
            print('Reach end of the list. Stop.')
            return ids


def download_all(blog_id, save_folder='.', theme_name=None, executor=None, until=None, limit=10, download_type='image'):
    results = parse_list(blog_id, until=until, limit=limit, theme_name=theme_name)
    if not results:
        print('No new entry found.')
        return
    print(f'Get {len(results)} entries. Start downloading...')
    shutdown_executor_inside = False
    if not executor:
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)
        shutdown_executor_inside = True
    for id in results:
        if download_type in ['all', 'image']:
            executor.submit(download_image, blog_id, id, save_folder)
        if download_type in ['all', 'text']:
            executor.submit(download_text, blog_id, id, save_folder)
    if shutdown_executor_inside:
        executor.shutdown()
        print('Done!')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Download ameblo images and texts.')
    parser.add_argument('blog_id', help='ameblo blog id')
    parser.add_argument('--theme', help='ameblo theme name')
    parser.add_argument('--output', '-o', help='folder to save images and texts (default: CWD/{blog_id})')
    parser.add_argument('--until', help='download until this entry id (non-inclusive)')
    parser.add_argument('--type', default='image', help='download type (image, text, all)')

    args = parser.parse_args()
    save_folder = args.output if args.output else args.blog_id
    download_all(args.blog_id, save_folder=save_folder, theme_name=args.theme, until=args.until, limit=500, download_type=args.type)