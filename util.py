import lxml
import requests
from bs4 import BeautifulSoup
import time
import sys

from pathlib import Path
import json
import re
from urllib.parse import unquote

def dump_json(mydict, filename):
    filename = Path(filename)
    if filename.suffix.lower() !='.json':
        filename = filename.with_suffix('.json')
    with filename.open('w', encoding='utf-8') as f:
        json.dump(mydict, f, ensure_ascii=False, indent=2)

def load_json(filename):
    filename = Path(filename)
    with filename.open('r', encoding='utf-8') as f:
        data = json.load(f)
    return data

def safeify(name):
    template = {u'\\': u'＼', u'/': u'／', u':': u'：', u'*': u'＊',
                u'?': u'？', u'"': u'＂', u'<': u'＜', u'>': u'＞', u'|': u'｜','\n':'','\r':''}
    for illegal in template:
        name = name.replace(illegal, template[illegal])
    return name


def get(url, headers=None, cookies=None, encoding='utf-8'):
    r = requests.get(url, cookies=cookies, headers=headers)
    r.encoding = encoding
    return BeautifulSoup(r.text, 'lxml')


def download(url, filename=None, save_path='.', cookies=None, dry_run=False, dupe='skip',referer=None):
    
    def check_dupe(filename):
        if not filename.exists():
            return filename        
        if dupe == 'overwrite':
            print(f'[Warning] File {filename.name} already exists! Overwriting...')
            return filename
        if dupe == 'skip':
            print(f'[Warning] File {filename.name} already exists! Skip.')
            return None
        if dupe == 'rename':            
            i = 2
            stem = filename.stem
            while filename.exists():
                filename = filename.with_name(f'{stem}_{i}{filename.suffix}')
                i = i + 1
            print(f'[Warning] File already exists! Rename to {filename.name}.')
            return filename

    if dry_run:
        return
    if filename: # If filename is supplied
        f = Path(filename)
    else: # If not, create a f using save_path + web_name for now.
        p = Path(save_path)
        web_name = unquote(url.split('?')[0].split('/')[-1])
        f = p / safeify(web_name)
    
    if f.suffix.lower() not in ['.php', '']:
        if not (f := check_dupe(f)):
            return

    f.parent.mkdir(parents=True, exist_ok=True)

    with requests.get(url, headers={"referer": referer}, cookies=cookies, stream=True) as r:
        if r.status_code == 200:
            # Find filename from header
            if not filename and "Content-Disposition" in r.headers:
                if m := re.search(r"filename=(.+)", r.headers["Content-Disposition"]):                    
                    header_name = m[1]
                    if header_name[-1] == '"' and header_name[0] == '"' or header_name[-1] == "'" and header_name[0] == "'":
                        header_name = header_name[1:-1]
                    new_f = p / header_name
                    if not (f := check_dupe(new_f)):
                        return
                        
            print(f'Downloading {f.name} from {url}...')
            with f.open('wb') as fio:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:       
                        fio.write(chunk)
        else:
            print(f'Error! Get HTTP {r.status_code} from {url}.')
            # An empty file will still be created. This is by design.
            f.with_suffix(f.suffix + '.broken').open('wb').close()
                
                

def hello(a, b):
    print(f'hello: {a} and {b}')

def get_files(directory, recursive=False):
    dirpath = Path(directory)
    assert(dirpath.is_dir())
    file_list = []
    for x in dirpath.iterdir():
        if x.is_file():
            file_list.append(x)
        elif x.is_dir() and recursive:
            file_list.extend(get_files(x, recursive=True))
    return file_list

def remove_empty_folders(directory, remove_root=True): #Including root.
    directory = Path(directory)
    assert(directory.is_dir())
    for x in directory.iterdir():
        if x.is_dir():
            remove_empty_folders(x, remove_root=True)
    if remove_root and not list(directory.iterdir()):
        directory.rmdir()