import lxml
import requests
from bs4 import BeautifulSoup
import time
import sys

from pathlib import Path
import json
import re
from urllib.parse import unquote


def safeify(name):
    template = {u'\\': u'＼', u'/': u'／', u':': u'：', u'*': u'＊',
                u'?': u'？', u'"': u'＂', u'<': u'＜', u'>': u'＞', u'|': u'｜','\n':''}
    for illegal in template:
        name = name.replace(illegal, template[illegal])
    return name


def get(url, headers=None, cookies=None, encoding='utf-8'):
    r = requests.get(url, cookies=cookies, headers=headers)
    r.encoding = encoding
    return BeautifulSoup(r.text, 'lxml')


def download(url, filename=None, save_path='.', cookies=None, dry_run=False):
    if dry_run:
        return
    if not filename:
        p = Path(save_path)
        web_name = unquote(url.split('?')[0].split('/')[-1])
        filename = p / safeify(web_name)       
    
    filename = Path(filename)    
    filename.parent.mkdir(parents=True, exist_ok=True)
    if filename.exists():
        print(f'File {filename.name} already exists!')
        return

    print(f'Downloading {filename.name}...')

    with filename.open('wb') as f:        
        f.write(requests.get(url, cookies=cookies).content)

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