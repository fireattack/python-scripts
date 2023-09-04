import builtins
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote
import time

import requests
from bs4 import BeautifulSoup


def timeme(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        print(f"{func.__name__} executed in {end_time - start_time:.02f} seconds")
        return result
    return wrapper


# Modiifed from https://www.peterbe.com/plog/best-practice-with-retries-with-requests
def requests_retry_session(
    retries=5,
    backoff_factor=0.2,
    status_forcelist=(502, 503, 504),
    session=None,
):
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    session = session or requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

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


# https://stackoverflow.com/a/13756038/3939155
def td_format(td_object_or_sec, long_form=True):
    if isinstance(td_object_or_sec, int) or isinstance(td_object_or_sec, float):
        seconds = int(td_object_or_sec)
    else:
        seconds = int(td_object_or_sec.total_seconds())

    periods = [
        ('year',        60*60*24*365),
        ('month',       60*60*24*30),
        ('day',         60*60*24),
        ('hour',        60*60),
        ('minute',      60),
        ('second',      1)
    ]

    strings=[]
    for period_name, period_seconds in periods:
        if seconds > period_seconds:
            period_value , seconds = divmod(seconds, period_seconds)
            if long_form:
                has_s = 's' if period_value > 1 else ''
                strings.append(f"{period_value} {period_name}{has_s}")
            else:
                strings.append(f"{period_value}{period_name[0:1]}")
    if long_form:
        return ", ".join(strings)
    else:
        return "".join(strings)


def to_jp_time(dt, input_timezone=None):
    from dateutil import parser
    from pytz import timezone

    if isinstance(dt, str):
        dt = parser.parse(dt)
    if input_timezone:
        dt = timezone(input_timezone).localize(dt)
    return dt.astimezone(timezone('asia/tokyo'))


def load_cookie(filename):
    import time
    from http.cookiejar import MozillaCookieJar

    cj = MozillaCookieJar(filename)
    cj.load(ignore_expires=True, ignore_discard=True)
    for cookie in cj:
        if cookie.expires == 0:
            cookie.expires = int(time.time()+ 86400)

    return cj

def print_cmd(cmd, prefix=''):
    import re

    commands_text_form = [f'"{c}"' if re.search(r'[ ?]', str(c)) else str(c) for c in cmd]
    print(prefix + ' '.join(commands_text_form))


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

def load_json(filename, encoding='utf-8'):
    filename = Path(filename)
    with filename.open('r', encoding=encoding) as f:
        data = json.load(f)
    return data

def safeify(name, ignore_backslash=False):
    assert isinstance(name, str), f'Name must be a string, not {type(name)}'

    template = {'\\': '＼', '/': '／', ':': '：', '*': '＊', '?': '？', '"': '＂', '<': '＜', '>': '＞', '|': '｜','\n':'','\r':'','\t':''}
    if ignore_backslash:
        template.pop('\\', None)

    for illegal in template:
        name = name.replace(illegal, template[illegal])
    return name

def tic():
    import time

    global _start_time
    _start_time = time.time()

def tac(print=True):
    import builtins
    import time
    global _start_time

    t = time.time() - _start_time
    if print:
        builtins.print(f'Time passed: {t:.2f} s')
    return t

def get(url, headers=None, cookies=None, encoding=None, session=None, parser='lxml'):
    if not session:
        session = requests_retry_session()
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

def get_current_time(now=None):
    from datetime import datetime

    import pytz

    tz = pytz.timezone('Asia/Tokyo')

    if now is None:
        now = datetime.now()
    jst_now = now.astimezone(tz)

    return {
        'local': {
            'obj': now,
            'str_pretty': now.strftime('%Y-%m-%d (%a) %H:%M:%S'),
            'str_short': now.strftime('%y%m%d_%H%M%S'),
        },
        'jst': {
            'obj': jst_now,
            'str_pretty': jst_now.strftime('%Y-%m-%d (%a) %H:%M:%S'),
            'str_short': jst_now.strftime('%y%m%d_%H%M%S'),
        }
    }


def batch_rename(renamings):
    '''
    Non-conflict batch rename.
    renamings: list of (Path object, newname)'''

    files = [f for f, _ in renamings]
    dst_files = [f.with_name(name) for f, name in renamings]
    # if new filename is conflicting and not in our current files, abort
    for new_f in dst_files:
        if new_f.exists() and new_f not in files:
            print(f'[E] file {new_f.name} already exists. Please rename it first.')
            return
    # rename current file(s) to temp filename to make renaming possible
    real_renamings = []
    for f, name in renamings:
        if f in dst_files:
            temp_f = ensure_nonexist(f.with_name(f.stem + '_temp' + f.suffix))
            print(f'[I] temporarily rename {f.name} to {temp_f.name}')
            f = f.rename(temp_f)
        real_renamings.append((f, name))

    for f, name in real_renamings:
        f.rename(f.with_name(name))


def download(url, filename=None, save_path='.', cookies=None, session=None, dry_run=False,
             dupe='skip_same_size', referer=None, headers=None, placeholder=True, prefix='',
             get_suffix=True, verbose=2, retry_failed=True):

    if dupe not in ['skip', 'overwrite', 'rename', 'skip_same_size']:
        raise ValueError('[Error] Invalid dupe method: {dupe} (must be either skip, overwrite, rename or skip_same_size).')

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

    def replace_suffix(f, content_type):
        from mimetypes import guess_extension

        header_suffix = ''
        mime = content_type.split(';')[0]
        guess = guess_extension(mime, strict=False)
        suffix_from_mime = mime.split('/')[-1].lower()

        # manually set suffix for some common types that isn't covered by guess_extension
        maps = {
            'audio/mp4': '.m4a',
            'audio/x-m4a': '.m4a',
            'image/webp': '.webp',
        }

        if mime in maps:
            header_suffix = maps[mime]
        # if 'application/octet-stream', just use the original suffix (guess_extension gives .bin)
        elif mime == 'application/octet-stream':
            header_suffix = ''
        # only use guessed extension if it's valid (and not bin)
        elif guess is not None:
            header_suffix = guess
        # last resort. NOTE: this does not work half the time, maybe just abandon it...
        elif re.search(r'^[a-zA-Z0-9]+$', suffix_from_mime):
            header_suffix = '.' + suffix_from_mime

        # replace logic
        # if they're the same, we don't need to do anything
        if f.suffix.lower() == header_suffix:
            return f
        # if header_suffix is a bad one, don't do anything
        if header_suffix == '' or '-' in header_suffix or '+' in header_suffix:
            return f
        # don't replace equivalent extensions
        ext_alias_groups = [
            ['.mp4', '.m4a', '.m4v', '.m4s'],
            ['.jpg', '.jpeg']
        ]
        for aliases in ext_alias_groups:
            if f.suffix.lower() in aliases and header_suffix in aliases:
                return f
        # likely dynamic content, use header suffix instead (silently)
        if f.suffix.lower() in ['.php', '']:
            return f.with_suffix(header_suffix)

        # this is to prevent that when filename has dot in it, it would cause Path obj to consider part of stem is the suffix.
        # so we only replace the suffix that is "valid" (<= 3 chars etc.) but wrong.
        # Not ideal, but should be good enough.
        if has_valid_suffix(f):
            print(f'[Warning] File suffix is different from the one in Content-Type header! {f.suffix.lower()} -> {header_suffix}', 1)
            return f.with_suffix(header_suffix)
        # f has a weird suffix. We assume it's part of the name stem, so we just append the header suffix (silently).
        return f.with_name(f.name + header_suffix)


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
        # Check if file exists for dupe=skip and rename. Other dupe methods will check later.
        if dupe in ['skip', 'rename']:
            if not (f := check_dupe(f)):
                return 'Exists'
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
        # Skip this check if filename is likely change by response header (by not having valid suffix)
        # #TODO: check if this is a good practice later.
        if has_valid_suffix(f) and dupe in ['skip', 'rename']:
            if not (f := check_dupe(f)):
                return 'Exists'

    session = requests_retry_session(session=session)
    if headers:
        session.headers.update(headers)

    f.parent.mkdir(parents=True, exist_ok=True)

    r = session.get(url, headers={"referer": referer}, cookies=cookies, stream=True)
    if not r.status_code == 200:
        r.close()
        print(f'[Error] Get HTTP {r.status_code} from {url}.', 0)
        if placeholder:
            broken_file = f.with_name(f.name + '.broken')
            broken_file = ensure_nonexist(broken_file)
            broken_file.touch()
        return r.status_code

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
        f = replace_suffix(f, r.headers['Content-Type'])

    expected_size = int(r.headers.get('Content-length', 0))
    if expected_size == 0:
        print('[Warning] Cannot get Content-Length. Omit size check', 2)
    elif r.headers.get('content-encoding', None): # Ignore content-length if it's compressed.
        print('[Warning] Content is compressed. Omit size check.', 2)
        expected_size = 0

    # Check it again before download starts.
    # Note: if dupe=overwrite, it will check (and print) twice, before and after downloading. This is by design.
    if not (f := check_dupe(f, size=expected_size)):
        return 'Exists'
    print(f'Downloading {f.name} from {url}...', 2)
    print(f'Downloading {f.name}...', 1, only=True)
    temp_file = f.with_name(f.name + '.dl')
    temp_file = ensure_nonexist(temp_file)
    broken_file = f.with_name(f.name + '.broken')
    broken_file = ensure_nonexist(broken_file)

    def actually_download(file, response):
        with file.open('wb') as fio:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    fio.write(chunk)

    actually_download(temp_file, r)
    r.close()

    downloaded_size = temp_file.stat().st_size
    #TODO: maybe we should just retry the whole thing. And capture any exceptions too.
    if expected_size and downloaded_size != expected_size and retry_failed:
        retries = 1
        while retries < 5:
            print(f'[Warning] file size does not match (expected: {expected_size}, actual: {downloaded_size}). Retry {retries}', 1)
            with session.get(url, headers={"referer": referer}, cookies=cookies) as r2:
                actually_download(temp_file, r2)
            downloaded_size = temp_file.stat().st_size
            if downloaded_size == expected_size:
                break
            retries += 1

    if expected_size and downloaded_size != expected_size:
        print(f'[Error] file size does not match (expected: {expected_size}, actual: {downloaded_size}). Please check!', 0)
        temp_file.rename(broken_file)
        return r.status_code

    # post-processing
    f = check_dupe(f, size=downloaded_size) # Check again. Because some other programs may create the file during downloading
    if not f: # this means skip. Remove what we just downloaded.
        temp_file.unlink()
        return 'Exists'
    if f.exists(): # this means overwrite. So remove before rename.
        f.unlink()
    # In other case, either f has been renamed or no conflict. So just rename.
    temp_file.rename(f)
    return r.status_code



def hello(a, b):
    print(f'hello: {a} and {b}')

def get_files(directory, recursive=False, file_filter=None, path_filter=None):
    '''filter(s): true means include, false means exclude'''
    directory = Path(directory)
    assert(directory.is_dir())
    # if there is no filter, use scandir generator, since it is so much faster.
    if file_filter is None and path_filter is None:
        from os import scandir
        def quick_scan(directory):
            for entry in scandir(directory):
                if entry.is_file():
                    yield entry
                elif recursive and entry.is_dir(follow_symlinks=False):
                    yield from quick_scan(entry.path)
        return [Path(f) for f in quick_scan(directory)]
    # else, use pathlib.iterdir and just dynamically change the list. The speed is basically the same (slow).
    file_list = []
    for x in directory.iterdir():
        if x.is_file():
            if not file_filter or file_filter(x):
                file_list.append(x)
        elif recursive and x.is_dir() and (not path_filter or path_filter(x)):
            file_list.extend(get_files(x, recursive=recursive, file_filter=file_filter, path_filter=path_filter))
    return file_list

def remove_empty_folders(directory, remove_root=True): #Including root.
    directory = Path(directory)
    try:
        assert(directory.is_dir())
        for x in directory.iterdir():
            if x.is_dir():
                remove_empty_folders(x, remove_root=True)
        if remove_root and not list(directory.iterdir()):
            directory.rmdir()
    except PermissionError as e:
        print('Error:', e)

def sheet_api():
    """Shows basic usage of the Sheets API.
    Prints values from a sample spreadsheet.
    """

    import pickle

    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

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
            assert credentials_file.exists(), "please put credentials.json file in ./auth/ !"
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
    type_changed = False

    if type(value_old) != type(value):
        type_changed = True
        equal = False
    elif isinstance(value, dict):
        for key, v in value.items():
            if key not in value_old:
                print(f'{print_prefix}.{key}: [green]Added:[/green]', v)
            else:
                v_old = value_old[key]
                equal &= compare_obj(v_old, v, print_prefix=f'{print_prefix}.{key}')
        for key, v in value_old.items():
            if key not in value:
                print(f'{print_prefix}.{key}: [red]Removed:[/red]', v)
        return equal
    elif isinstance(value, list):
        for i in range(min(len(value), len(value_old))):
            equal &= compare_obj(value_old[i], value[i], print_prefix=f'{print_prefix}[{i}]')
        if len(value_old) < len(value):
            for i in range(len(value_old), len(value)):
                print(f'{print_prefix}[{i}]: [green]Added:[/green]', value[i])
        elif len(value_old) > len(value):
            for i in range(len(value), len(value_old)):
                print(f'{print_prefix}[{i}]: [red]Removed:[/red]',value_old[i])
        return equal

    elif isinstance(value, str):
        equal = re.sub(r'\s+',' ', value_old) == re.sub(r'\s+',' ', value)
    else:
        equal = value_old == value
    if not equal:
        print(f'{print_prefix}:', end='')
        s = str(value_old) + str(value)
        if len(s) < 60 and not '\n' in s:
            print(f' {value_old} [yellow]->[/yellow] {value}')
            # print(f'[red]Old:[/red] {value_old} [yellow]->[/yellow] [green]New:[/green] {value}')
        else:
            print()
            print('[red]Old:', value_old)
            print('[green]New:', value)
    return equal


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        download(*sys.argv[1:])
    else:
        print('Yay!')

class Table():
    def __init__(self, rows=None, headers=None, max_width=100) -> None:
        if rows and not headers:
            self.headers = rows[0]
            self.data = rows[1:]
        elif headers:
            self.headers = headers
            if rows:
                self.data = rows
            else:
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
        d = [''] * len(self.headers)
        for key, value in new_data.items():
            if not key in self.headers: # silently ignore keys that are not in headers
                continue
            col_idx = self.headers.index(key)
            d[col_idx] = value
        self.data.append(d)
    def print(self, formats=None, custom_print=None):
        import wcwidth

        def fmt(value, str_format):
            try:
                return str_format.format(value)
            except Exception:
                return value

        def calc_width(col_format, idx):
            maxw = sum(wcwidth.wcwidth(c) for c in str(self.headers[idx]))
            for row in self.data:
                if idx > len(row) - 1:
                    continue
                w =sum(wcwidth.wcwidth(c) for c in fmt(row[idx], col_format['str_format']))
                if w > maxw:
                    maxw = w
            maxw = min(maxw, col_format['max_width'])
            col_format['width'] = maxw

        def print_row(row, header_mode=False, custom_print=custom_print):
            parts = []
            for idx in range(len(row)):
                col_format = col_formats[idx]
                # override str format back to nothing for headers
                str_format = "{}" if header_mode else col_format['str_format']
                s = format_str(fmt(row[idx], str_format), width=col_format['width'], align=col_format['align'])
                parts.append(s)
            line = s = '  '.join(parts)
            if custom_print:
                custom_print(line)
            else:
                print(line)

        col_formats = dict()
        for idx in range(len(self.headers)):
            col_format = {
                "align": "left",
                "str_format": "{}",
                "max_width": self.max_width
            }
            if formats:
                if idx in formats:
                    col_format.update(formats[idx])
                elif self.headers[idx] in formats:
                    col_format.update(formats[self.headers[idx]])
            if not 'width' in col_format:
                calc_width(col_format, idx)
            col_formats[idx] = col_format

        print_row(self.headers, header_mode=True)
        for row in self.data:
            print_row(row)

    def save(self, f):
        s = ''
        f = Path(f)
        s += '\t'.join(self.headers) + '\n'
        for row in self.data:
            s += '\t'.join([str(cell) for cell in row]) + '\n'
        f.write_text(s, encoding='utf8')
