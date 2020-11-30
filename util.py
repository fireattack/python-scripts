import lxml
import requests
from bs4 import BeautifulSoup
import time
import sys

from pathlib import Path
import json
import re
from urllib.parse import unquote

def copy(data):
    import win32clipboard
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardText(data, win32clipboard.CF_UNICODETEXT)
    win32clipboard.CloseClipboard()

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
                u'?': u'？', u'"': u'＂', u'<': u'＜', u'>': u'＞', u'|': u'｜','\n':'','\r':'','\t':''}
    for illegal in template:
        name = name.replace(illegal, template[illegal])
    return name


def get(url, headers=None, cookies=None, encoding='utf-8'):
    r = requests.get(url, cookies=cookies, headers=headers)
    r.encoding = encoding
    return BeautifulSoup(r.text, 'lxml')


def ensure_nonexist(f):
    i = 2
    stem = f.stem
    while f.exists():
        f = f.with_name(f'{stem}_{i}{f.suffix}')
        i = i + 1
    return f    

def download(url, filename=None, save_path='.', cookies=None, dry_run=False, dupe='skip',referer=None, placeholder=True, prefix='', verbose=2):
    if dupe not in ['skip', 'overwrite', 'rename']:
        raise ValueError('[Error] Invalid dupe method: {dupe} (must be either skip, overwrite or rename).')        

    def check_dupe(f, dupe=dupe):
        if not f.exists():
            return f        
        if dupe == 'overwrite':
            if verbose > 0:
                print(f'[Warning] File {f.name} already exists! Overwriting...')
            return f
        if dupe == 'skip':
            if verbose > 0:
                print(f'[Warning] File {f.name} already exists! Skip.')
            return None
        if dupe == 'rename':            
            i = 2
            stem = f.stem
            while f.exists():
                f = f.with_name(f'{stem}_{i}{f.suffix}')
                i = i + 1
            if verbose > 0:
                print(f'[Warning] File already exists! Rename to {f.name}.')
            return f
        
    if dry_run:
        if verbose > 0:
            print(f'[Info only] URL: {url}')
        return

    if filename: # If filename is supplied
        f = Path(filename)
    else: # If not, create a f using save_path + web_name for now.
        p = Path(save_path)
        web_name = unquote(url.split('?')[0].split('/')[-1])
        if prefix:
            web_name = f'{prefix} ' + web_name
        f = p / safeify(web_name)
    
    if f.suffix.lower() not in ['.php', '']:
        if not (f := check_dupe(f)):
            return

    f.parent.mkdir(parents=True, exist_ok=True)

    with requests.get(url, headers={"referer": referer}, cookies=cookies, stream=True) as r:
        if r.status_code == 200:
            # Find filename from header
            if not filename:
                if r.url != url: # Deal with 302
                    web_name = unquote(r.url.split('?')[0].split('/')[-1])
                    if prefix:
                        web_name = f'{prefix} ' + web_name
                    f = p / safeify(web_name)
                if "Content-Disposition" in r.headers:
                    from cgi import parse_header
                    _, params = parse_header(r.headers["Content-Disposition"])
                    header_name = ''
                    if 'filename*' in params:
                        header_name = unquote(params['filename*'].lstrip("UTF-8''"))
                    elif 'filename' in params:
                        header_name = params['filename']
                    if header_name:
                        if prefix:
                            header_name = f'{prefix} ' + header_name
                        f = p / safeify(header_name)
                if f.suffix == '' and 'Content-Type' in r.headers:
                    header_suffix = '.' + r.headers['Content-Type'].split('/')[-1].replace('jpeg','jpg')
                    f = f.with_suffix(header_suffix)
                if not (f := check_dupe(f)):
                    return
            if verbose > 1:
                print(f'Downloading {f.name} from {url}...')
            elif verbose > 0:
                print(f'Downloading {f.name}...')
            temp_file = f.with_name(f.name + '.dl')
            while temp_file.exists():
                temp_file = temp_file.with_name(temp_file.name + '.dl')
            with temp_file.open('wb') as fio:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:       
                        fio.write(chunk)
            f = check_dupe(f) # Check again. Because some other programs may create the file during downloading
            if not f: # this means skip. Remove what we just downloaded.
                temp_file.unlink()
                return
            if f.exists(): # this means overwrite. So remove before rename.
                f.unlink()
            # In other case, either f has been renamed or no conflict. So just rename.
            temp_file.rename(f)
            return r.status_code
        else:
            if verbose > -1:
                print(f'[Error] Get HTTP {r.status_code} from {url}.')
            if placeholder:
                f.with_suffix(f.suffix + '.broken').open('wb').close()
            return r.status_code
                

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

if __name__ == "__main__":
    import sys
    download(*sys.argv[1:])