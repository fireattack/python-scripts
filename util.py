import builtins
import requests
from bs4 import BeautifulSoup
import sys

from pathlib import Path
import json
import re
from urllib.parse import unquote


def get_webname(url):
    return unquote(url.split('?')[0].split('/')[-1])


def to_list(a):
    return a if not a or isinstance(a, list) else [a]


def parse_to_shortdate(date_str):
    from dateutil import parser

    date_str = re.sub(r'[\s　]+', ' ', date_str).strip()
    patterns = [r'(\d+)年 *(\d+)月 *(\d+)日', r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})']
    for pattern in patterns:
        if m := re.search(pattern, date_str):
            date_str = m[1] + m[2].zfill(2) + m[3].zfill(2)
            break
        # Sometimes the string has extra spaces. But this is dangerous since things like `2014/3/7 23:52` will be parsed as `20140372`.
        # But it *should* have been caught by the `m` above already, so 99% of the cases it should be fine.
        if m2 := re.search(pattern, date_str.replace(' ', '')):
            date_str = m2[1] + m2[2].zfill(2) + m2[3].zfill(2)
            break
    try:
        return parser.parse(date_str, yearfirst=True).strftime('%y%m%d')
    except:
        return ""


def load_cookie(filename):
    import time

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
    filename.parent.mkdir(parents=True, exist_ok=True)
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


def get(url, headers=None, cookies=None, encoding=None, session=None, parser='lxml'):
    if not session:
        session = requests.Session()
    r = session.get(url, cookies=cookies, headers=headers)
    if encoding:
        return BeautifulSoup(r.content, parser, from_encoding=encoding)
    else:
        return BeautifulSoup(r.content, parser)


def ensure_nonexist(f):
    i = 2
    stem = f.stem
    if m:= re.search(r'^(.+?)_(\d)$', stem):
        stem = m[1]
        i = int(m[2]) + 1
    while f.exists():
        f = f.with_name(f'{stem}_{i}{f.suffix}')
        i = i + 1
    return f


def download(url, filename=None, save_path='.', cookies=None, session=None, dry_run=False,
             dupe='skip_same_size', referer=None, headers=None, placeholder=True, prefix='', get_suffix=True, verbose=2):
    if dupe not in ['skip', 'overwrite', 'rename', 'skip_same_size']:
        raise ValueError('[Error] Invalid dupe method: {dupe} (must be either skip, overwrite, rename or skip_same_size).')

    if not session:
        session = requests.Session()
    if headers:
        session.headers.update(headers)

    def print(s, verbose_level, only=False):
        if (only and verbose == verbose_level) or (not only and verbose >= verbose_level):
            builtins.print(s)

    def has_valid_suffix(f):
        # common suffixes
        if f.suffix.lower() in ['.jpg', '.png', '.gif', '.webp', '.jpeg', '.bmp', '.svg', '.ico', '.mp4', '.mkv', '.webm', '.heic', '.pdf']:
            return True
        if f.suffix.lower() in ['.php', '']:
            return False
        # if the suffix is too long, has a space, etc., we assume it is not a valid suffix
        if len(f.suffix.lower()) > 5 or ' ' in f.suffix.lower():
            return False
        return True

    def check_dupe(f, dupe=dupe, size=0):
        if not f.exists():
            return f
        if dupe == 'skip_same_size':
            if size:
                # this part is basically `ensure_nonexist()` but the logic is slightly different:
                # (if the filename exists and the filesize is the same, stop; otherwise find the next unoccupied filename.)
                # Therefore, we have to repeat it here.
                i = 2
                stem = f.stem
                if m:= re.search(r'^(.+?)_(\d+)$', stem):
                    stem = m[1]
                    i = int(m[2]) + 1
                while f.exists():
                    existing_size = f.stat().st_size
                    if size == existing_size:
                        print(f'[Warning] File {f.name} already exists and have same size! Skip download.', 1)
                        return None
                    print(f'[Warning] File {f.name} already exists, and the size doesn\'t match (existing: {existing_size}; new: {size}). Rename..', 1)
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
        return 'Dry run'

    if filename: # If filename is supplied
        f = Path(filename)
        f = f.with_name(safeify(f.name))
    else: # If not, create a f using save_path + web_name for now.
        p = Path(save_path)
        web_name = get_webname(url)
        if prefix:
            web_name = f'{prefix} ' + web_name
        # a special case is when web_name is empty, which causes f to be just the save_path. We just don't check in this case.
        if not web_name:
            web_name = 'no_web_name'
        f = p / safeify(web_name)

    # Check if file exists for dupe=skip and rename. Other dupe methods will check later.
    # Also don't check if filename is likely change by response header.
    if dupe in ['skip', 'rename'] and not has_valid_suffix(f):
        if not (f := check_dupe(f)):
            return 'Exists'

    f.parent.mkdir(parents=True, exist_ok=True)

    with session.get(url, headers={"referer": referer}, cookies=cookies, stream=True) as r:
        if r.status_code == 200:
            if not filename: # Try to find filename using the response again, if not specified
                if r.url != url: # Get filename again from URL for potential 302/301
                    web_name = get_webname(r.url)
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
            if (get_suffix or not has_valid_suffix(f)) and 'Content-Type' in r.headers: # Also find the file extension
                def get_ext(mime):
                    from mimetypes import guess_extension
                    # don't return .bin
                    if mime == 'application/octet-stream':
                        return ''
                    # manually replace some weird ones
                    if mime == 'audio/mp4' or mime == 'audio/x-m4a':
                        return '.m4a'
                    guess = guess_extension(mime)
                    if guess is not None:
                        return guess
                    # last resort
                    return mime.split('/')[-1].lower()
                header_suffix = get_ext(r.headers['Content-Type'].split(';')[0])
                # if they're the same, we don't need to do anything
                if f.suffix.lower() == header_suffix:
                    pass
                # if header_suffix is bad, don't do anything
                elif header_suffix == '' or '-' in header_suffix:
                    pass
                # don't replace jpeg to jpg or vice versa
                elif header_suffix in ['.jpg', '.jpeg'] and f.suffix.lower() in ['.jpg', '.jpeg']:
                    pass
                # don't replace m4a to mp4 or vice versa
                elif header_suffix in ['.mp4', '.m4a'] and f.suffix.lower() in ['.m4a', '.mp4']:
                    pass
                # likely dynamic content, use header suffix instead
                elif f.suffix.lower() in ['.php', '']:
                    f = f.with_suffix(header_suffix)
                # this is to prevent the filename has dot in it, which causes Path to think part of stem is suffix.
                # so we only replace the suffix that is <= 3 chars.
                # Not ideal, but should be good enough.
                elif has_valid_suffix(f):
                    print(f'[Warning] File suffix is different from the one in Content-Type header! {f.suffix.lower()} -> {header_suffix}', 1)
                    f = f.with_suffix(header_suffix)
                # f has a weird suffix. We assume it's part of the name stem, so we just append the header suffix.
                else:
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
                return 'Exists'
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
                return 'Exists'
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

def get_files(directory, recursive=False, file_filter=None, path_filter=None):
    dirpath = Path(directory)
    assert(dirpath.is_dir())
    file_list = []
    for x in dirpath.iterdir():
        if x.is_file():
            if not file_filter or file_filter(x):
                file_list.append(x)
        elif x.is_dir() and recursive and (not path_filter or path_filter(x)):
            file_list.extend(get_files(x, recursive=recursive, file_filter=file_filter, path_filter=path_filter))
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
    if align == 'center':
        left_space = (width-length)//2
        right_space = width-length-left_space
        return ' '*left_space + output + ' '*right_space


def array_to_range_text(a, sep=', ', dash='-'):
    s = ''
    prev_seg = None
    for idx, seg in enumerate(a):
        if idx == 0: # first segment
            s += f'{seg}'
            range_start = seg
        else:
            if seg - prev_seg == 1:
                if idx == len(a) - 1: # last segment
                    s += f'{dash}{seg}'
            else:
                if prev_seg > range_start:
                    s += f'{dash}{prev_seg}'
                s += f'{sep}{seg}'
                range_start = seg
        prev_seg = seg
    return s


def compare_obj(value_old, value, print_prefix='ROOT'):
    from rich import print
    equal = True

    if type(value_old) != type(value):
        print(f'{print_prefix}: warning: data changes type from {type(value_old)} to {type(value)}.')
        equal = False
    elif isinstance(value, dict):
        for key, v in value.items():
            if key not in value_old:
                print(f'{print_prefix}: found new key \'{key}\':')
                print(v)
            else:
                v_old = value_old[key]
                equal &= compare_obj(v_old, v, print_prefix=f'{print_prefix}.{key}')
        return equal
    elif isinstance(value, list):
        if len(value) == 1 and len(value_old) == 1:
            value = value[0]
            value_old = value_old[0]
            equal &= compare_obj(value_old, value, print_prefix=f'{print_prefix}[0]')
            return equal
        else:
            try:
                equal = sorted(value_old) == sorted(value)
            except Exception:
                equal = value_old == value
    elif isinstance(value, str):
        equal = re.sub(r'\s','', value_old) == re.sub(r'\s','', value)
    else:
        equal = value_old == value
    if not equal:
        print(f'{print_prefix}: data does not match with new one:')
        if isinstance(value, str) or isinstance(value, int):
            print('[red]Old:', value_old)
            print('[green]New:', value)
        else:
            print('[red]======= Old =======')
            if isinstance(value, list):
                print('Items count: ', len(value_old))
            print(value_old)
            print('[green]======= New =======')
            if isinstance(value, list):
                print('Items count: ', len(value))
            print(value)
    return equal


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        download(*sys.argv[1:])
    else:
        print('Yay!')

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
    def rows(self):
        for row in self.data:
            row_dict = {}
            for i, header in enumerate(self.headers):
                row_dict[header] = row[i]
            yield row_dict

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

    def save(self, f):
        s = ''
        f = Path(f)
        s += '\t'.join(self.headers) + '\n'
        for row in self.data:
            s += '\t'.join([str(cell) for cell in row]) + '\n'
        f.write_text(s, encoding='utf8')
