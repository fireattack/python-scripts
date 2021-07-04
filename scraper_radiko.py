from urllib.parse import urlparse, parse_qs
import requests
import re
from pathlib import Path
import concurrent.futures
import requests
from subprocess import run, DEVNULL
from util import download

class RadikoExtractor():
    def __init__(self, url, save_dir='.', *args, **kwargs):
        self.url = url
        try:
            self.host = urlparse(url).hostname
        except:
            self.host = ''
        self.save_dir = save_dir
        for key in kwargs:
            setattr(self, key, kwargs[key])

    def parse(self, *args, **kwargs):
        import base64
        import xml.etree.ElementTree as ET
        from datetime import datetime, timedelta
        from http.cookiejar import MozillaCookieJar
        import time
        import pytz

        tz = pytz.timezone('Asia/Tokyo')

        s = requests.Session()

        cookie_file = Path('cookies.txt') # for premium account
        if cookie_file.exists():
            print(f"Found cookie file at {cookie_file}. Load...")
            cj = MozillaCookieJar(cookie_file)
            cj.load(ignore_expires=True,ignore_discard=True)
            for cookie in cj:
                if cookie.expires == 0:
                    cookie.expires = int(time.time()+ 86400)
            s.cookies = cj

        #http://www.joqr.co.jp/timefree/mss.php
        #http://radiko.jp/share/?sid=QRR&t=20200822260000
        #http://radiko.jp/#!/ts/QRR/20200823020000
        is_joqr_timefree = False
        if re.search(r'joqr\.co\.jp/timefree/', self.url):
            is_joqr_timefree = True
            r = requests.get(self.url)
            self.url = re.search(r'<META.+URL=(.+)">', r.text)[1]

        if m := re.search(r'/ts/(.+)/(\d{8})(\d+)$', self.url):
            station = m[1]
            date = m[2]
            time = m[3]
        elif re.search(r'/share/', self.url):
            qs = parse_qs(urlparse(self.url).query)
            station = qs['sid'][0]
            t = qs['t'][0]
            date = t[0:8]
            time = t[8:]
        else:
            print('URL format invalid.')
            return

        # 节目单XML的日期是30小时制（实质上是29小时：深夜节目计算为前一天，早晨5点起为新的一天），但是里面的metadata是正常24小时制。
        # 然后上述两种URL又分别用两种时间制度（share是29小时，/ts/是24小时）所以这里转换下。
        # “natural_date”指的是29小时制时的日期（找不到更好的名字了），date和time都是24小时制。
        hr = int(time[0:2])
        natural_date = date
        if hr < 5:
            natural_date = (datetime.strptime(date, '%Y%m%d') - timedelta(days=1)).strftime('%Y%m%d')
        if hr >= 24:
            date = (datetime.strptime(date, '%Y%m%d') + timedelta(days=1)).strftime('%Y%m%d')
            time = '{:02d}'.format(hr-24) + time[2:]

        date_time_obj = tz.localize(datetime.strptime(date + time, '%Y%m%d%H%M%S'))
        now_obj = datetime.now().astimezone(tz)
        if (now_obj - date_time_obj) > timedelta(days=7) and is_joqr_timefree:
            print('[Warning] the link is more than 1 week old. Likely it\'s already expired. Automatically change to next week...')
            date_time_obj = date_time_obj + timedelta(days=7)
            natural_date = (datetime.strptime(natural_date, '%Y%m%d') + timedelta(days=7)).strftime('%Y%m%d')

        prog_list = s.get(f'http://radiko.jp/v3/program/station/date/{natural_date}/{station}.xml')
        prog_list.encoding = 'utf-8'
        root = ET.fromstring(prog_list.text)

        title = ''
        for prog in root[2][0][1]:
            if prog.tag == 'prog':
                if int(prog.attrib['ft']) <= int(date_time_obj.strftime('%Y%m%d%H%M%S')) < int(prog.attrib['to']):
                    print('Find the program!', prog[0].text)
                    title = prog[0].text
                    ft = prog.attrib['ft']
                    to = prog.attrib['to']
                    break

        if not title:
            print('Failed to find the program from the list.')
            return

        headers = {
            'x-radiko-device': 'pc',
            'x-radiko-app-version': '0.0.1',
            'x-radiko-user': 'dummy_user',
            'x-radiko-app': 'pc_html5'
        }
        auth1 = s.get('https://radiko.jp/v2/api/auth1', headers=headers)

        auth_token = auth1.headers['X-Radiko-AuthToken']
        key_length = int(auth1.headers['X-Radiko-KeyLength'])
        key_offset = int(auth1.headers['X-Radiko-KeyOffset'])

        key = 'bcd151073c03b352e1ef2fd66c32209da9ca0afa' #hard-coded key
        partial_key = key[key_offset: key_offset + key_length]
        partial_key_b64 = base64.b64encode(bytes(partial_key, 'ascii')).decode('ascii')
        print('[Auth info] token: ', auth_token, 'partial key: ', partial_key_b64)

        headers2 = {
            'x-radiko-authtoken': auth_token,
            'x-radiko-partialkey': partial_key_b64
        }

        auth2 = s.get('https://radiko.jp/v2/api/auth2', headers=headers2)
        if auth2.status_code == 200:
            if auth2.text == 'OUT':
                print('Geo-restricted. Please use a Japan IP.')
                return
            print('[Auth info] Auth2 succeed.')

            playlist_url = f'https://radiko.jp/v2/api/ts/playlist.m3u8?station_id={station}&&ft={ft}&to={to}'
            playlist = s.get(playlist_url, headers=headers2)
            if m2 := re.search(r'http.+\.m3u8', playlist.text):
                m3u8_url = m2[0]
                with s.get(m3u8_url) as r:
                    urls = re.findall(r'https://media\.radiko\.jp/sound/b/.+?/.+?/.+\.aac', r.text)
                    print(f'Find {len(urls)} segments!')
            else:
                print(f'Cannot get playlist from {playlist_url}! Response: {playlist.text}')
                return

            save_folder = Path(self.save_dir)
            filename = f'{ft[2:8]} {ft[8:]} {title} [{station}].m4a'
            save_folder.mkdir(parents=True, exist_ok=True)
            fullpath = save_folder / filename

            #Temp folder
            temp_folder = save_folder / 'temp'
            i = 1
            while temp_folder.exists(): #Make sure to not use existing folder(s)
                temp_folder = save_folder / f'temp{i}'
                i = i + 1
            print(f'Create temp dir {temp_folder.name} to save temp files.')
            temp_folder.mkdir(parents=True)

            print(f'Download video {filename} segs from\n{m3u8_url}')
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as e:
                for url in urls:
                    e.submit(download, url, save_path=temp_folder)

            files = [f for f in temp_folder.iterdir() if f.suffix.lower() == '.aac']
            # Since FFMPEG 4.4, "the file names / paths given in the concat file are relative to the position of the concat file"
            # See: https://trac.ffmpeg.org/ticket/9277
            # So lets just use abs. path.
            my_str = '\n'.join(f"file '{f.resolve()}'" for f in files) 
            filelist = temp_folder / 'files.txt'
            filelist.write_text(my_str, encoding='utf-8')

            temp_aac = temp_folder / 'temp.aac'
            # Concat in raw aac first, then remuxed in m4a container. Otherwise the duration in SOME software would be wrong. Don't ask me why..
            run(['ffmpeg', '-f', 'concat', '-safe', '0', '-i', filelist, '-c', 'copy', temp_aac], stdout=DEVNULL)
            if not temp_aac.exists():
                print('[Error] acc concat failed. Please check manually!')
                return
            run(['ffmpeg', '-i', temp_aac, '-c', 'copy', fullpath], stdout=DEVNULL)
            # Remove temp files
            for f in files:
                f.unlink()
            filelist.unlink()
            temp_aac.unlink()
            temp_folder.rmdir() 
        else:
            print(f'[Auth info] Auth2 failed (HTTP {auth2.status_code}).')
            return

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = 'http://www.joqr.co.jp/timefree/mss.php'    
    e = RadikoExtractor(url)
    e.parse()