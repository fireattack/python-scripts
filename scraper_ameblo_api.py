import re
from pathlib import Path
import requests
from urllib.parse import urljoin
import concurrent.futures
import json
from dateutil import parser

from util import safeify, download, get, dump_json


def download_image(blog_id, id, save_folder='.'):
    # print(f'Processing {id}...')
    data = requests.get(f'https://blogimgapi.ameba.jp/blog/{blog_id}/entries/{id}/images').json()

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        for idx, img in enumerate(data['data']):
            img_url = urljoin('https://stat.ameba.jp/', img['imgUrl'])
            img_url = re.sub(r'^(.+)\?(.+)$', r'\1', img_url)  # Remove parameters
            img_url = re.sub(r'\/t[0-9]*_([^/]*)$', r'/o\1', img_url)
            date = re.search(r'user_images/(\d+)/', img_url)[1]
            file_name = img_url.split('/')[-1]
            desc = img['title']
            img_name = safeify(f'{date} {id}_{desc}_{idx+1} {file_name}') if len(
                data['data']) > 1 else safeify(f'{date} {id}_{desc} {file_name}')
            ex.submit(download, img_url, Path(save_folder) / img_name)

def download_text(blog_id, id, save_folder='.'):
    # print(f'Processing {id}...')
    url = f'https://ameblo.jp/{blog_id}/entry-{id}.html'
    soup = get(url)    
    data = None
    for s in soup('script'):
        if 'window.INIT_DATA' in s.text:
            data = s.text
            break
    if data:
        print('.', end="", flush=True)
        data = json.loads(re.search(r'window\.INIT_DATA *= *(.+);window\.RESOURCE_BASE_URL', data)[1])
        b = data['entryState']['entryMap'][str(id)]
        title = b['entry_title']
        text = b['entry_text']
        time = b['entry_created_datetime']
        date = parser.parse(time).strftime('%Y%m%d_%H%M%S')        
        #Dump
        text_folder = Path(save_folder) / 'text'
        text_folder.mkdir(exist_ok=True)
        html = text_folder / safeify(f'{date} {id}_{title}.html')
        html.write_text(text, encoding='utf8')
        metadata_folder = Path(save_folder) / 'metadata'
        metadata_folder.mkdir(exist_ok=True)
        metadata = metadata_folder / safeify(f'{date} {id}_{title}.json')
        dump_json(b, metadata)
    else:
        print(f'[E] cannot fetch data from {url}!')


def parse_list(blog_id, start_entry, until=None):
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


def download_all(blog_id, save_folder='.', executor=None, until=None, last_entry='auto', download_type='image'):
    if last_entry == 'auto':
        soup = get(f'https://ameblo.jp/{blog_id}/')
        if anchor := soup.select_one(f'a[href*="{blog_id}/entry-"]'):
            last_entry = re.search(r'entry-(\d+).html', anchor['href'])[1]
        else:
            for s in soup('script'):
                if s.text.startswith('window.INIT_DATA'):
                    if m := re.search(r'entryMap.+?"(\d+)"', s.text):
                        last_entry = m[1]
                        break
        if last_entry == 'auto':
            raise Exception(f'[Error] cannot detect last entry for blog {blog_id}!')
        print(f'Info: {blog_id}\'s newest entry is {last_entry}.')
    if last_entry == until:
        print('No new update.')
        return
    results = parse_list(blog_id, last_entry, until=until)
    if not results:
        print('Get 0 entry. Exit.')
        return
    print(f'Get {len(results)} entries. Start downloading..')
    shutdown_executor_inside = False
    if not executor:
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)
        shutdown_executor_inside = True
    for id in results:
        if download_type in ['all', 'image']:
            executor.submit(download_image, blog_id, id, save_folder)
        if download_type in ['all', 'text']:
            executor.submit(download_text, blog_id, id, save_folder)
    if shutdown_executor_inside:
        executor.shutdown()