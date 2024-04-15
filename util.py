import builtins
import json
import os
import re
import sys
import time
import hashlib
import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

# all the external dependencies are imported inside the functions,
# so we can use this file in other projects without installing them.
# or to copy and paste the functions to other public projects directly.
# to install them all, you can do:
# pip install requests lxml beautifulsoup4 python-dateutil pytz pyperclip wcwidth rich browser_cookie3

# ==================== CONSTANTS ====================

'''Twitter media name handle
The filename format I use, inherited from good old twMediaDownloader (RIP: here is a mirror: https://github.com/fireattack/twMediaDownloader).
The first version must start with screen_name and ended with type[index][ dupe].suffix
The second one allows optional arbitrary prefix or suffix.
NOTE: to make it simpler, the returned m['extra'] and m['dupe'] will have leading space or hyphen with it.
'''
TWITTER_FILENAME_RE = re.compile(r'^(?P<screen_name>\w+)-(?P<id>\d+)-(?P<date>\d{8})_(?P<time>\d{6})-(?P<type>[^-.]+?)(?P<index>\d*)(?P<dupe> *\(\d+\))?(?P<suffix>\.(?:mp4|zip|jpg|png))$')
TWITTER_FILENAME_RELEXED_RE = re.compile(r'^(?:(?P<prefix>.+?)(?: +?|[-]??))??(?P<screen_name>\w+)-(?P<id>\d+)-(?P<date>\d{8})_(?P<time>\d{6})-(?P<type>[^-.]+?)(?P<index>\d*)(?P<extra>[ _-].+?)??(?P<dupe> *\(\d+\))?(?P<suffix>\.(?:mp4|zip|jpg|png))$')


# ==================== data structure manipulation & misc. ====================
def to_list(a):
    return a if not a or isinstance(a, list) else [a]

def flatten(x):
    from collections.abc import Iterable
    if isinstance(x, Iterable) and not isinstance(x, str):
        return [a for i in x for a in flatten(i)]
    else:
        return [x]

def print_cmd(cmd, prefix=''):
    commands_text_form = [f'"{c}"' if re.search(r'[ ?]', str(c)) else str(c) for c in cmd]
    print(prefix + ' '.join(commands_text_form))

def copy(data):
    # pip install pyperclip
    import pyperclip
    pyperclip.copy(data)

def get_clipboard_data():
    # pip install pyperclip
    import pyperclip
    return pyperclip.paste()

def safeify(name, ignore_backslash=False):
    """
    Replaces illegal characters in a given name with safe alternatives.

    Args:
        name (str): The name to be made safe.
        ignore_backslash (bool, optional): Whether to ignore backslashes. Defaults to False.

    Returns:
        str: The safe version of the name.

    Raises:
        AssertionError: If the name is not a string.
    """

    assert isinstance(name, str), f'Name must be a string, not {type(name)}'

    template = {'\\': '＼', '/': '／', ':': '：', '*': '＊', '?': '？', '"': '＂', '<': '＜', '>': '＞', '|': '｜','\n':'','\r':'','\t':''}
    if ignore_backslash:
        template.pop('\\', None)

    for illegal in template:
        name = name.replace(illegal, template[illegal])
    return name

def format_str(s, width=None, align='left', padding=' '):
    """
    Format a string `s` with a specified width, alignment, and padding.

    Args:
        s (str): The string to be formatted.
        width (int, optional): The desired width of the formatted string. If not provided, the original string will be returned as is. Defaults to None.
        align (str, optional): The alignment of the formatted string. Possible values are 'left', 'right', and 'center'. Defaults to 'left'.
        padding (str, optional): The padding character used to fill the remaining space in the formatted string. Defaults to ' '.

    Returns:
        str: The formatted string.

    """
    # pip install wcwidth
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
        return output + padding*(width-length)
    if align == 'right':
        return padding*(width-length) + output
    if align == 'center':
        left_space = (width-length)//2
        right_space = width-length-left_space
        return padding*left_space + output + padding*right_space

class Table():
    # pip install wcwidth

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
            line = '  '.join(parts)
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

        # return some useful info
        total_width = sum(col_format['width'] for col_format in col_formats.values()) + 2 * (len(col_formats) - 1)
        return {'total_width': total_width, 'col_formats': col_formats}

    def save(self, f):
        s = ''
        f = Path(f)
        s += '\t'.join(self.headers) + '\n'
        for row in self.data:
            s += '\t'.join([str(cell) for cell in row]) + '\n'
        f.write_text(s, encoding='utf8')

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

def compare_obj(value_old, value, print_prefix='ROOT', mute=False):
    # pip install rich
    from rich import print as rprint

    def print(*args, **kwargs):
        if not mute:
            rprint(*args, **kwargs)

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
                equal &= compare_obj(v_old, v, print_prefix=f'{print_prefix}.{key}', mute=mute)
        for key, v in value_old.items():
            if key not in value:
                print(f'{print_prefix}.{key}: [red]Removed:[/red]', v)
        return equal
    elif isinstance(value, list):
        for i in range(min(len(value), len(value_old))):
            equal &= compare_obj(value_old[i], value[i], print_prefix=f'{print_prefix}[{i}]', mute=mute)
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

# ==================== datetime related ====================
def parse_to_shortdate(date_str, fmt=None):
    # pip install python-dateutil
    from dateutil import parser

    if fmt is None: fmt = '%y%m%d'
    if isinstance(date_str, datetime):
        return date_str.strftime(fmt)

    date_str = re.sub(r'[\s　]+', ' ', date_str).strip()
    patterns = [r'(\d+)年 *(\d+)月 *(\d+)日', r'(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})']
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
        return parser.parse(date_str, yearfirst=True).strftime(fmt)
    except:
        return ""


class MyTime:
    def __init__(self, t=None):
        import pytz

        self.tz = pytz.timezone('Asia/Tokyo')

        if t is None:
            t = datetime.now()

        # Convert now to local timezone and then to JST
        self.naive_time = t.replace(tzinfo=None)
        self.local_time = t.astimezone()
        self.jst_time = self.local_time.astimezone(self.tz)

    def _format_time(self, dt, format_type):
        if format_type == 'obj':
            return dt
        elif format_type == "short":
            return dt.strftime('%y%m%d_%H%M%S')
        elif format_type == "pretty":
            return dt.strftime('%Y-%m-%d (%a) %H:%M:%S')
        else:
            raise ValueError("Invalid format_type. Choose from 'obj', 'short', 'pretty'.")

    def local(self, format_type="obj"):
        return self._format_time(self.local_time, format_type)

    def jst(self, format_type="obj"):
        return self._format_time(self.jst_time, format_type)

    def naive(self, format_type="obj"):
        return self._format_time(self.naive_time, format_type)

# deprecated, will be removed in the future
def get_current_time(now=None):
    # pip install pytz
    import pytz

    tz = pytz.timezone('Asia/Tokyo')

    if now is None:
        now = datetime.now()
    # convert now to local timezone and then to JST
    now = now.astimezone()
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

# deprecated, just use MyTime(dt).jst()
def to_jp_time(dt, input_timezone=None):
    # pip install python-dateutil pytz
    from dateutil import parser
    from pytz import timezone

    if isinstance(dt, str):
        dt = parser.parse(dt)
    if input_timezone:
        dt = timezone(input_timezone).localize(dt)
    return dt.astimezone(timezone('asia/tokyo'))

# ==================== performance related ====================
def tic():
    global _start_time
    _start_time = time.time()

def tac(print=True):
    global _start_time
    t = time.time() - _start_time
    if print:
        builtins.print(f'Time passed: {t:.2f} s')
    return t

# a decorator to time a function
def timeme(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        print(f"{func.__name__} executed in {end_time - start_time:.02f} seconds")
        return result
    return wrapper

# ==================== file related ====================
def dump_json(mydict, filename, **kwargs):
    filename = Path(filename)
    if filename.suffix.lower() !='.json':
        filename = filename.with_suffix('.json')
    filename.parent.mkdir(parents=True, exist_ok=True)
    default_kwargs = dict(ensure_ascii=False, indent=2)
    default_kwargs.update(kwargs)
    with filename.open('w', encoding='utf-8') as f:
        json.dump(mydict, f, **default_kwargs)

def load_json(filename, encoding='utf-8'):
    filename = Path(filename)
    with filename.open('r', encoding=encoding) as f:
        data = json.load(f)
    return data

def dump_html(soup, filename='temp.html', encoding='utf-8'):
    """
    Dump the contents of a BeautifulSoup object to an HTML file.

    Args:
        soup (BeautifulSoup): The BeautifulSoup object containing the HTML content.
        filename (str, optional): The name of the output file. Defaults to 'temp.html'.
        encoding (str, optional): The encoding to use when writing the file. Defaults to 'utf-8'.
    """
    filename = Path(filename)
    filename.parent.mkdir(parents=True, exist_ok=True)
    with filename.open('w', encoding=encoding) as f:
        f.write(str(soup))

def dump_tsv(data, filename='temp.tsv', verbose=True, print_header=False):
    """
    Dump data into a TSV (Tab-Separated Values) file.

    Args:
        data (list): The data to be dumped. It can be a list of lists or a list of dictionaries.
        filename (str, optional): The name of the output file. Defaults to 'temp.tsv'.
        verbose (bool, optional): Whether to print the content of the TSV file. Defaults to True.
        print_header (bool, optional): Whether to print the header in the TSV file. Defaults to False.
    """
    s = ''
    if isinstance(data[0], dict):
        headers = data[0].keys()
        if print_header:
            s += '\t'.join(headers) + '\n'
        for row in data:
            s += '\t'.join([str(row[h]) for h in headers]) + '\n'
    else:
        if print_header:
            print('[W] No header provided. Use default header [0, 1, 2, ...]')
            s += '\t'.join([str(i) for i in range(len(data[0]))]) + '\n'
        for row in data:
            s += '\t'.join([str(i) for i in row]) + '\n'
    if verbose:
        print(s)
    filename = Path(filename)
    filename.parent.mkdir(parents=True, exist_ok=True)
    filename.write_text(s, encoding='utf8')


def get_files(directory, recursive=False, file_filter=None, path_filter=None):
    '''filter(s): true means include, false means exclude'''
    directory = Path(directory)
    assert(directory.is_dir())
    # if there is no filter, use os.scandir generator, since it is so much faster.
    if file_filter is None and path_filter is None:
        def quick_scan(directory):
            for entry in os.scandir(directory):
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
        assert directory.is_dir()
        for x in directory.iterdir():
            if x.is_dir():
                remove_empty_folders(x, remove_root=True)
        if remove_root and not list(directory.iterdir()):
            directory.rmdir()
    except PermissionError as e:
        print('Error:', e)

def ensure_nonexist(f):
    '''
    Ensure the file does not exist. If it does, rename it to filename_2, filename_3, etc.
    '''

    i = 2
    stem = f.stem
    if m:= re.search(r'^(.+?)_(\d)$', stem):
        # only do so if for i < 10 and has no padding.
        # so things like file_01, file_1986 etc. won't be renamed to confusing file_2, file_1987 etc.
        if int(m[2]) < 10 and len(m[2]) == 1:
            stem = m[1]
            i = int(m[2]) + 1
    while f.exists():
        f = f.with_name(f'{stem}_{i}{f.suffix}')
        i = i + 1
    return f

def ensure_path_exists(path):
    '''
    ensure the path exists.
    '''
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f'Path {path} does not exist!')
    return path

def quickmd5(f):
    hasher = hashlib.md5()
    file_size = f.stat().st_size
    buffer_size = 1024 * 1024  # 1MB

    with f.open('rb') as f:
        if file_size <= buffer_size:
            # If the file is less than or equal to 1MB, read the entire file
            data = f.read()
            hasher.update(data)
        else:
            # Read the first 1MB
            data = f.read(buffer_size)
            hasher.update(data)

            # Go to the end of the file to read the last 1MB
            f.seek(-buffer_size, os.SEEK_END)
            data = f.read(buffer_size)
            hasher.update(data)

    return f"{file_size}_{hasher.hexdigest()}" # this way is more readable than just return the hexdigest.

def move_or_delete_duplicate(src, dst, verbose=True, conflict='error'):
    """
    Move or delete a file if it is a duplicate.

    Args:
        src (str): The path to the source file.
        dst (str): The path to the destination file.
        verbose (bool, optional): Whether to print verbose output. Defaults to True.
        conflict (str, optional): The conflict resolution strategy. Can be one of 'error', 'skip', or 'rename'.
                                 Defaults to 'error'.

    Raises:
        FileNotFoundError: If the source file does not exist.
        ValueError: If the source and destination paths are the same.
        FileExistsError: If the destination file already exists and the conflict resolution strategy is 'error'.

    Returns:
        None
    """

    if not src.exists():
        raise FileNotFoundError(f"The source file {src} does not exist.")
    if src == dst:
        raise ValueError(f"Source and destination are the same: {src}")
    if dst.exists():
        if quickmd5(dst) == quickmd5(src):
            print(f'[W] {src.name} is a duplicate. Remove.')
            src.unlink()
            return
        else:
            if conflict == 'skip':
                print(f'[W] Destination file {dst} already exists and hash does not match. Skip.')
                return
            elif conflict == 'error':
                raise FileExistsError(f"Destination file {dst} already exists.")
            elif conflict == 'rename':
                dst = ensure_nonexist(dst)
                print(f'[W] Destination file {src.name} already exists. Use filename {dst.name} instead.')
    if verbose:
        if src.parent == dst.parent:
            print(f"Rename {src.name} to {dst.name}")
        elif src.name == dst.name:
            print(f'Move {src.name} into {dst.parent}')
        else:
            print(f'Move {src.name} to {dst}')
    shutil.move(src, dst)

def batch_rename(renamings):
    """
    Batch rename files without conflicts.

    Args:
        renamings (list): A list of tuples containing the original file paths and the new names.

    Returns:
        None

    Raises:
        None

    This function renames multiple files simultaneously without causing conflicts. It checks for duplicate files
    in the list, duplicate new filenames, and conflicts with existing files. If any conflicts are detected, the
    function prints an error message and aborts the renaming process.

    Example usage:
        renamings = [(Path('file1.txt'), 'new_file1.txt'), (Path('file2.txt'), 'new_file2.txt')]
        batch_rename(renamings)
    """
    files = [f for f, _ in renamings]
    dst_files = [f.with_name(name) for f, name in renamings]

    if len(set(files)) != len(files):
        print('[E] There are duplicate files in the list! Please check.')
        return

    if len(set(dst_files)) != len(dst_files):
        print('[E] There are duplicate new filenames in the list! Please check.')
        return

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

# ==================== network related ====================
def requests_retry_session(
    retries=5,
    backoff_factor=0.2,
    status_forcelist=(502, 503, 504),
    session=None,
):
    """
    Create a session object with retry functionality for making HTTP requests.
    Modified from https://www.peterbe.com/plog/best-practice-with-retries-with-requests

    Args:
        retries (int): The maximum number of retries for each request. Default is 5.
        backoff_factor (float): The backoff factor between retries. Default is 0.2.
        status_forcelist (tuple): A tuple of HTTP status codes that should trigger a retry. Default is (502, 503, 504).
        session (requests.Session): An existing session object to use. If not provided, a new session will be created.

    Returns:
        requests.Session: The session object with retry functionality.

    """
    # pip install requests urllib3
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

def get(url, headers=None, cookies=None, encoding=None, session=None, parser='lxml', timeout=None):
    """
    Sends a GET request to the specified URL and returns the parsed HTML content.

    Args:
        url (str): The URL to send the GET request to.
        headers (dict, optional): The headers to include in the request. Defaults to None.
        cookies (dict, optional): The cookies to include in the request. Defaults to None.
        encoding (str, optional): The encoding to use when parsing the HTML content. Defaults to None.
        session (requests.Session, optional): The session to use for the request. Defaults to None.
        parser (str, optional): The parser to use for parsing the HTML content. Defaults to 'lxml'.
        timeout (float, optional): The maximum number of seconds to wait for the request to complete. Defaults to None.

    Returns:
        BeautifulSoup: The parsed HTML content.

    Raises:
        Any exceptions raised by the underlying requests library.

    Dependencies:
        - requests
        - lxml
        - beautifulsoup4
    """
    from bs4 import BeautifulSoup

    if not session:
        session = requests_retry_session()
    r = session.get(url, cookies=cookies, headers=headers, timeout=timeout)
    if encoding:
        return BeautifulSoup(r.content, parser, from_encoding=encoding)
    else:
        return BeautifulSoup(r.content, parser)

def get_webname(url):
    return unquote(url.split('?')[0].split('/')[-1])

def load_cookie(s):
    """
    Load cookies from various sources and convert them to a `RequestsCookieJar` object.

    Args:
        s (str): The input string, file path containing the cookies, or "{browser_name}/{domain_name}" to load cookies from a browser.

    Returns:
        requests.cookies.RequestsCookieJar: The converted `RequestsCookieJar` object.

    Raises:
        ValueError: If the input string is invalid.

    Examples:
        >>> load_cookie('cookie1=value1; cookie2=value2')
        <RequestsCookieJar[Cookie(version=0, name='cookie1', value='value1', port=None, port_specified=False, domain='', domain_specified=False, domain_initial_dot=False, path='/', path_specified=False, secure=False, expires=None, discard=True, comment=None, comment_url=None, rest={'HttpOnly': None}, rfc2109=False), Cookie(version=0, name='cookie2', value='value2', port=None, port_specified=False, domain='', domain_specified=False, domain_initial_dot=False, path='/', path_specified=False, secure=False, expires=None, discard=True, comment=None, comment_url=None, rest={'HttpOnly': None}, rfc2109=False)]>

        >>> load_cookie('/path/to/cookies.txt')
        <RequestsCookieJar[Cookie(version=0, name='cookie1', value='value1', port=None, port_specified=False, domain='example.com', domain_specified=False, domain_initial_dot=False, path='/', path_specified=False, secure=False, expires=None, discard=True, comment=None, comment_url=None, rest={'HttpOnly': None}, rfc2109=False), Cookie(version=0, name='cookie2', value='value2', port=None, port_specified=False, domain='example.com', domain_specified=False, domain_initial_dot=False, path='/', path_specified=False, secure=False, expires=None, discard=True, comment=None, comment_url=None, rest={'HttpOnly': None}, rfc2109=False)]>
    """
    from http.cookiejar import MozillaCookieJar
    from requests.cookies import RequestsCookieJar, create_cookie
    import browser_cookie3
    # pip install browser_cookie3

    def convert(cj):
        cookies = RequestsCookieJar()
        for cookie in cj:
            requests_cookie = create_cookie(
            name=cookie.name,
            value=cookie.value,
            domain=cookie.domain,
            path=cookie.path,
            secure=cookie.secure,
            rest={'HttpOnly': cookie.get_nonstandard_attr('HttpOnly')},
            expires=cookie.expires,
            )
            cookies.set_cookie(requests_cookie)
        return cookies

    if m := re.search(r'^(chrome|firefox|edge)(/.+)?', str(s), re.IGNORECASE):
        domain_name = m[2].lstrip('/') if m[2] else ""
        if m[1] == 'chrome':
            cj = browser_cookie3.chrome(domain_name=domain_name)
        elif m[1] == 'firefox':
            cj = browser_cookie3.firefox(domain_name=domain_name)
        elif m[1] == 'edge':
            cj = browser_cookie3.edge(domain_name=domain_name)
        return convert(cj)

    if Path(s).exists():
        cj = MozillaCookieJar(s)
        cj.load(ignore_expires=True, ignore_discard=True)
        for cookie in cj:
            if cookie.expires == 0:
                cookie.expires = int(time.time()+ 86400)
        return convert(cj)

    if re.search(r'^(.+?):\s*(.+?)', str(s)):
        cookies = RequestsCookieJar()
        for k, v in re.findall(r'(.+?):\s*([^;]+?)(?:;|$)', s):
            cookies.set(k, v)
        return cookies

    raise ValueError(f'Invalid cookie string: {s}')

def download(url, filename=None, save_path='.', cookies=None, session=None, dry_run=False,
             dupe='skip_same_size', referer=None, headers=None, placeholder=True, prefix='',
             get_suffix=True, verbose=2, retry_failed=True):
    """
    Downloads a file from the given URL and saves it to the specified location.

    Args:
        url (str): The URL of the file to download.
        filename (str, optional): The name of the file to save. If not provided, the filename will be extracted from the URL or the response header. Defaults to None.
        save_path (str, optional): The directory path to save the file. Defaults to '.' (current directory).
        cookies (dict, optional): A dictionary of cookies to include in the request. Defaults to None.
        session (requests.Session, optional): A requests Session object to use for the request. Defaults to None.
        dry_run (bool, optional): If True, only prints the URL and does not perform the actual download. Defaults to False.
        dupe (str, optional): The method to handle duplicate files. Must be one of 'skip', 'overwrite', 'rename', or 'skip_same_size'. Defaults to 'skip_same_size'.
        referer (str, optional): The referer header to include in the request. Defaults to None.
        headers (dict, optional): Additional headers to include in the request. Defaults to None.
        placeholder (bool, optional): If True, creates a placeholder file with a '.broken' extension if the download fails. Defaults to True.
        prefix (str, optional): A prefix to add to the filename. Useful when fetching the filename from the response headers. Defaults to ''.
        get_suffix (bool, optional): If True, attempts to determine the file extension from the response headers. Defaults to True.
        verbose (int, optional): The verbosity level of the download progress. Must be 0, 1, or 2. Defaults to 2.
        retry_failed (bool, optional): If True, retries the download if it fails. Defaults to True.

    Returns:
        str: The status of the download. Can be 'Dry run', 'Exists', or the HTTP status code.
    """
    from cgi import parse_header
    from mimetypes import guess_extension
    # it uses requests_retry_session, so
    # pip install requests

    if dupe not in ['skip', 'overwrite', 'rename', 'skip_same_size']:
        raise ValueError(f'[Error] Invalid dupe method: {dupe} (must be either skip, overwrite, rename or skip_same_size).')

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
        # TODO: check if this is a good practice later.
        if has_valid_suffix(f) and dupe in ['skip', 'rename']:
            if not (f := check_dupe(f)):
                return 'Exists'

    session = requests_retry_session(session=session)
    if headers:
        session.headers.update(headers)
    if referer:
        session.headers.update({'referer': referer})
    if cookies:
        session.cookies.update(cookies)

    f.parent.mkdir(parents=True, exist_ok=True)

    r = session.get(url, stream=True)
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
            # TODO: write a parser myself since cgi.parse_header is deprecated and has its own problems as noted below in "HACK".

            content_disposition = r.headers["Content-Disposition"]
            # HACK: parse_header doesn't work if there is no value of "attachment" etc. exists.
            # Like content_disposition == "filename=xxx". So we add a dummy value.
            # I think it's non-standard, but it's relatively common.
            if content_disposition.startswith('filename'):
                content_disposition = 'attachment; ' + r.headers["Content-Disposition"]
            _, params = parse_header(content_disposition)
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
    # NOTE: if dupe=overwrite, it will check (and print) twice, before and after downloading. This is by design.
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
            with session.get(url) as r2:
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

def sheet_api():
    """Shows basic usage of the Sheets API.
    Prints values from a sample spreadsheet.
    """

    import pickle

    # pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    print('Initialize Google Sheets API..')
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

# =========== for testing ===========
def hello(a, b):
    print(f'hello: {a} and {b}')

if __name__ == "__main__":
    if len(sys.argv) > 1:
        download(*sys.argv[1:])
    else:
        print('util.py installed correctly.')
