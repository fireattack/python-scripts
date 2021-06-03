import builtins
import lxml
import requests
from bs4 import BeautifulSoup
import time
import sys

from pathlib import Path
import json
import re
from urllib.parse import unquote


def load_cookie(filename):
    from http.cookiejar import MozillaCookieJar
    cj = MozillaCookieJar(filename)
    cj.load(ignore_expires=True,ignore_discard=True)
    for cookie in cj:
        if cookie.expires == 0:
            cookie.expires = int(time.time()+ 86400)

    return cj


def flatten(x):
    from collections.abc import Iterable
    if isinstance(x, Iterable) and not isinstance(x, str):
        return [a for i in x for a in flatten(i)]
    else:
        return [x]

def copy(data):
    import win32clipboard
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardText(data, win32clipboard.CF_UNICODETEXT)
    win32clipboard.CloseClipboard()

def get_clipboard_data():
    import win32clipboard
    win32clipboard.OpenClipboard()
    data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
    win32clipboard.CloseClipboard()
    return data

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


def get(url, headers=None, cookies=None, encoding='utf-8', session=None):
    if not session:
        session = requests.Session()    
    r = session.get(url, cookies=cookies, headers=headers)
    r.encoding = encoding
    return BeautifulSoup(r.text, 'lxml')


def ensure_nonexist(f):
    i = 2
    stem = f.stem
    while f.exists():
        f = f.with_name(f'{stem}_{i}{f.suffix}')
        i = i + 1
    return f


def download(url, filename=None, save_path='.', cookies=None, session=None, dry_run=False,
             dupe='skip_same_size', referer=None, placeholder=True, prefix='', get_suffix=False, verbose=2):
    if dupe not in ['skip', 'overwrite', 'rename', 'skip_same_size']:
        raise ValueError('[Error] Invalid dupe method: {dupe} (must be either skip, overwrite or rename).')

    if not session:
        session = requests.Session()

    def print(s, verbose_level, only=False):
        if (only and verbose == verbose_level) or (not only and verbose >= verbose_level):
            builtins.print(s)

    def check_dupe(f, dupe=dupe, size=0):
        if not f.exists():
            return f
        if dupe == 'skip_same_size':
            if size:
                i = 2 
                stem = f.stem
                while f.exists():
                    existing_size = f.stat().st_size
                    if size == existing_size:
                        print(f'[Warning] File {f.name} already exists and have same size! Skip download.', 1)
                        return None
                    print(f'[Warning] File {f.name} already exists, and the size doesn\'t match (exiting: {existing_size}; new: {size}). Rename..', 1)
                    f = f.with_name(f'{stem}_{i}{f.suffix}')
                    i = i + 1                
                return f
            else:
                dupe = 'skip' # if we can't get size, just assume it's the same so we skip.
        if dupe == 'overwrite':
            print(f'[Warning] File {f.name} already exists! Overwriting...', 1)
            return f
        if dupe == 'skip':
            print(f'[Warning] File {f.name} already exists! Skip.', 1)
            return None
        if dupe == 'rename':
            f = ensure_nonexist(f)
            print(f'[Warning] File already exists! Rename to {f.name}.', 1)
            return f

    if dry_run:
        print(f'[Info only] URL: {url}', 1)
        return

    if filename: # If filename is supplied
        f = Path(filename)
        f = f.with_name(safeify(f.name))
    else: # If not, create a f using save_path + web_name for now.
        p = Path(save_path)
        web_name = unquote(url.split('?')[0].split('/')[-1])
        if prefix:
            web_name = f'{prefix} ' + web_name
        f = p / safeify(web_name)

    # Check if file exists for dupe=skip and rename. Other dupe methods will check later.
    # Also don't check if filename is likely change by response header.
    if dupe in ['skip', 'rename'] and f.suffix.lower() not in ['.php', '']:
        if not (f := check_dupe(f)):
            return

    f.parent.mkdir(parents=True, exist_ok=True)

    with session.get(url, headers={"referer": referer}, cookies=cookies, stream=True) as r:
        if r.status_code == 200:
            if not filename: # Try to find filename using the response again, is not specified
                if r.url != url: # Get filename again from URL for potential 302/301
                    web_name = unquote(r.url.split('?')[0].split('/')[-1])
                    if prefix:
                        web_name = f'{prefix} ' + web_name
                    f = p / safeify(web_name)
                if "Content-Disposition" in r.headers: # Get filename from the header
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
            if (get_suffix or f.suffix.lower() in ['.php', '']) and 'Content-Type' in r.headers: # Also find the file extension
                header_suffix = '.' + r.headers['Content-Type'].split('/')[-1].replace('jpeg','jpg')
                if f.suffix.lower() in ['.php', '']:
                    f = f.with_suffix(header_suffix)
                else: # this is to prevent the filename has dot in it, which causes Path to think part of stem is suffix.
                    f = f.with_name(f.name + header_suffix)

            expected_size = int(r.headers.get('Content-length', 0))
            if dupe == 'skip_same_size':
                if expected_size == 0:
                    print('[Warning] Cannot get content-length. Omit size check', 2)
                elif r.headers.get('content-encoding', None): # Ignore content-length if it's compressed.
                    print('[Warning] content is compressed. Omit size check.', 2)
                    expected_size = 0

            # Check it again before download starts.
            # Note: if dupe=overwrite, it will check (and print) twice, before and after downloading. This is by design.
            if not (f := check_dupe(f, size=expected_size)):
                return
            print(f'Downloading {f.name} from {url}...', 2)
            print(f'Downloading {f.name}...', 1, only=True)
            temp_file = f.with_name(f.name + '.dl')
            temp_file = ensure_nonexist(temp_file)
            with temp_file.open('wb') as fio:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        fio.write(chunk)
            downloaded_size = temp_file.stat().st_size
            f = check_dupe(f, size=downloaded_size) # Check again. Because some other programs may create the file during downloading
            if not f: # this means skip. Remove what we just downloaded.
                temp_file.unlink()
                return
            if f.exists(): # this means overwrite. So remove before rename.
                f.unlink()
            # In other case, either f has been renamed or no conflict. So just rename.
            temp_file.rename(f)
            return r.status_code
        else:
            print(f'[Error] Get HTTP {r.status_code} from {url}.', 0)
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

def sheet_api():
    """Shows basic usage of the Sheets API.
    Prints values from a sample spreadsheet.
    """

    import pickle
    from googleapiclient.discovery import build
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request

    print('Initilize Google Sheets API..')
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    auth_folder = Path(__file__).parent / 'auth'
    token_file = auth_folder / 'token.pickle'
    if token_file.exists():
        with token_file.open('rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            credentials_file = auth_folder / 'credentials.json'
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_file), ['https://www.googleapis.com/auth/spreadsheets'])
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with token_file.open('wb') as token:
            pickle.dump(creds, token)

    service = build('sheets', 'v4', credentials=creds)

    # Call the Sheets API
    return service.spreadsheets()


def format_str(s, width=None, align='left'):
    import wcwidth
    if s is None:
        s = ''
    else:
        s = str(s)
    if not width:
        return s
    output = ''
    length = 0
    for char in s:
        size = wcwidth.wcswidth(char)
        if length + size > width:
            break
        output += char
        length += size
    if align == 'left':
        return output + ' '*(width-length)
    if align == 'right':
        return ' '*(width-length) + output


if __name__ == "__main__":
    import sys
    download(*sys.argv[1:])

class Table():
    def __init__(self, rows=None, headers=None, max_width=20) -> None:
        if rows and not headers:
            self.headers = rows[0]
            self.data = rows[1:]
        elif headers:
            self.headers = headers
            self.data = []
        else:
            raise Exception('No header or data given!')
        self.max_width = max_width

    def search(self, keywords, single=True):
        matched_rows = []
        for row in self.data:
            matched = True
            for key, value in keywords.items():
                assert key in self.headers
                col_idx = self.headers.index(key)
                if not value: # Ignore empty values
                    continue
                if not ((str(row[col_idx]) == str(value)) or (row[col_idx] == value)):
                    matched = False
                    break
            if matched:
                matched_rows.append(row)
                if single:
                    break
        if matched_rows:
            if single and len(matched_rows) == 1:
                return matched_rows[0]
            else:
                return matched_rows
        else:
            return []
    def append(self, new_data):
        d = [None] * len(self.headers)
        for key, value in new_data.items():
            assert key in self.headers
            col_idx = self.headers.index(key)
            d[col_idx] = value
        self.data.append(d)
    def print(self):
        import wcwidth
        def print_row(row, widths):
            print(''.join(format_str(row[idx], widths[idx]) + ' ' for idx in range(len(row))))
        def max_width(idx):
            maxw = 0
            for c in str(self.headers[idx]):
                maxw += wcwidth.wcwidth(c)
                
            for row in self.data:
                w = 0
                if idx > len(row) - 1:
                    continue
                for c in str(row[idx]):
                    w += wcwidth.wcwidth(c)
                if w > maxw:
                    maxw = w
            maxw = min(maxw, self.max_width)
            return maxw

        widths = dict()
        for idx in range(len(self.headers)):
            widths[idx] = max_width(idx)

        print_row(self.headers, widths)
        for row in self.data:
            print_row(row, widths)