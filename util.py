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
    if not filename.endswith('.json'):
        filename = filename + '.json'
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(mydict, f, ensure_ascii=False, indent=2)

def load_json(filename):
    with open(filename, 'r', encoding='utf-8') as f:
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
    if dry_run:
        return
    if filename: # If filename is supplied
        f = Path(filename)
    else: # If not, create a f using save_path + web_name for now.
        p = Path(save_path)
        web_name = unquote(url.split('?')[0].split('/')[-1])
        f = p / safeify(web_name)
    
    if f.exists() and f.suffix.lower() not in ['.php', '']:
        if dupe == 'skip':
            print(f'File {f.name} already exists!')
            return
        if dupe == 'rename':
            #TODO
            pass
        if dupe == 'overwrite':
            pass

    f.parent.mkdir(parents=True, exist_ok=True)

    with requests.get(url, headers={"referer": referer}, cookies=cookies) as r:
        if r.status_code == 200:
            # Find filename from header
            if not filename and "Content-Disposition" in r.headers:
                if m := re.search(r"filename=(.+)", r.headers["Content-Disposition"]):                    
                    header_name = m[1]
                    if header_name[-1] == '"' or header_name[-1] == "'":
                        header_name = header_name[1:-1]
                    new_f = p / header_name
                    if not new_f.exists():
                        print(f'Find filename {header_name} in header. Using it instead..')
                        f = new_f
                    else:
                        print(f'File {new_f.name} already exists!')
                        return
                        
            print(f'Downloading {f.name} from {url}...')
            with f.open('wb') as fio:                
                fio.write(r.content)
        else:
            print(f'Error! Get HTTP {r.status_code} from {url}.')
            # An empty file will still be craeted. This is by design.
            f.open('wb').close()
                
                

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