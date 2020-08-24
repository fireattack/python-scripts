import re
from pathlib import Path
import lxml
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from util import safeify, download, get
import concurrent.futures
from pathlib import Path


def parse_entry(blog_id, id, save_folder='.'):
    data = requests.get(
        f'https://blogimgapi.ameba.jp/blog/{blog_id}/entries/{id}/images').json()

    for idx, img in enumerate(data['data']):
        img_url = urljoin('https://stat.ameba.jp/', img['imgUrl'])
        img_url = re.sub(r'^(.+)\?(.+)$', r'\1', img_url)  # Remove parameters
        img_url = re.sub(r'\/t[0-9]*_([^/]*)$', r'/o\1', img_url)
        date = re.search(r'user_images/(\d+)/', img_url)[1]
        file_name = img_url.split('/')[-1]
        desc = img['title']
        img_name = safeify(f'{date} {id}_{desc}_{idx+1} {file_name}') if len(
            data['data']) > 1 else safeify(f'{date} {id}_{desc} {file_name}')
        download(img_url, Path(save_folder) / img_name)


def parse_list(blog_id, start_entry, *, results=None, until=None, auto_iter=True):
    if results is None: # Fuck python https://stackoverflow.com/questions/366422/
        results = []    
    print(f'Parsing {blog_id} starting from {start_entry}...')
    myjson = requests.get(
        f'https://blogimgapi.ameba.jp/blog/{blog_id}/entries/{start_entry}/neighbors?limit=100').json()
    for entry in myjson['data']:
        id = entry["entryId"]
        if until and str(id) == str(until):
            print(f'Reached last record {until}! Stopping..')
            return results
        if not id in results:
            results.append(id)
    if auto_iter and myjson['paging']['nextUrl']:
        next_id = re.search(r'/entries/(\d+)/', myjson['paging']['nextUrl'])[1]
        parse_list(blog_id, next_id, results=results, until=until)
    return results

# Without using iteration for better readability 
def parse_list_new(blog_id, start_entry, until=None):
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


def download_all(blog_id, save_folder='.', executor=None, until=None, last_entry='auto'):

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
    results = parse_list(blog_id, last_entry, results=[], until=until)
    print(f'Get {len(results)} entries. Start downloading..')
    shutdown_executor_inside = False
    if not executor:
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)
        shutdown_executor_inside = True
    for id in results:
        executor.submit(parse_entry, blog_id, id, save_folder)
    if shutdown_executor_inside:
        executor.shutdown()