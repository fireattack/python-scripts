import concurrent.futures
import json
import re
from datetime import datetime
from subprocess import run
from urllib.parse import urljoin, urlparse
from urllib.request import getproxies
from pathlib import Path

import browser_cookie3
import websocket
from rich.console import Console
from rich.table import Table
from util import download, dump_json, get, MyTime, requests_retry_session, safeify, to_jp_time, load_cookie

console = Console()
print = console.print

class NicoDownloader():
    HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36'}

    def __init__(self, url_or_video_id, cookies, proxy=None):
        if m := re.search(r'/watch/([^?&]+)', url_or_video_id):
            self.video_id = m[1]
        else:
            self.video_id = url_or_video_id
        if self.video_id.startswith('lv'):
            self.url = f'https://live.nicovideo.jp/watch/{self.video_id}'
            self.video_type = 'live'
        else:
            self.url = f'https://www.nicovideo.jp/watch/{self.video_id}'
            self.video_type = 'video'

        def validate_cookie(cookies):
            for cookie in cookies:
                if cookie.name == 'user_session':
                    print('Find user_session in cookie:', cookie.value)
                    break
            else:
                print(f'WARN: Cannot find user_session in cookie. You\'re probably not logged in.')
                # exit(1) # make it non-fatal

        if cookies.lower() in ['chrome', 'firefox', 'edge']:
            print(f'Fetching cookies from browser {cookies}...')
            cookies = cookies.lower()
            if cookies == 'chrome':
                cookies = browser_cookie3.chrome(domain_name='.nicovideo.jp')
            elif cookies == 'firefox':
                cookies = browser_cookie3.firefox(domain_name='.nicovideo.jp')
            elif cookies == 'edge':
                cookies = browser_cookie3.edge(domain_name='.nicovideo.jp')
            validate_cookie(cookies)
        elif Path(cookies).exists():
            print(f'Loading cookies from file {cookies}...')
            cookies = load_cookie(cookies)
            validate_cookie(cookies)
        elif cookies.startswith('user_session_'):
            cookies = {'user_session': cookies}
        else:
            print('ERROR: Invalid cookie source. Please provide a browser name, a cookie value, or a Netscape-style cookie file.')
            exit(1)

        self.session = requests_retry_session()
        self.session.cookies.update(cookies)
        self.session.headers.update(self.HEADERS)

        # proxy settings
        if proxy is None or proxy.lower() == 'none':
            proxy = None
        elif proxy == 'auto':
            proxies = getproxies()
            if proxy := proxies.get('http'):
                print(f'INFO: automatically use system proxy {proxy}.')

        # I don't think system proxy would be missing scheme, but just in case
        if proxy and '://' not in proxy:
            proxy = f'http://{proxy}'

        self.session.proxies = {'http': proxy, 'https': proxy}
        self.proxy = proxy

    def create_ws(self, url):
        host, port, type_ = None, None, None
        if self.proxy:
            parsed = urlparse(self.proxy)
            host, port, type_ = parsed.hostname, parsed.port, parsed.scheme
        return websocket.create_connection(url, header=self.HEADERS, http_proxy_host=host, http_proxy_port=port, proxy_type=type_)

    def fetch_page(self, url):
        soup = get(url, session=self.session)
        live_data = json.loads(soup.select_one('#embedded-data')['data-props'])
        return live_data

    def download_comments(self, room_info, when):
        chats_all = []
        url = room_info["data"]["messageServer"]["uri"]
        thread_id = room_info["data"]["threadId"]

        ws = self.create_ws(url)
        print(f'Start download comments from thread {thread_id}')
        sending = True
        while sending:
            message = [
                {"ping": {"content": "rs:0"}},
                {"ping": {"content": "ps:0"}},
                {
                    "thread": {
                        "thread": thread_id,
                        "version": "20090904",
                        "res_from": -1000,
                        "when": when + 10
                    }
                },
                {"ping": {"content": "pf:0"}},
                {"ping": {"content": "rf:0"}}
            ]
            ws.send(json.dumps(message))

            first_chat = True
            chats = []
            while True:
                result = ws.recv()
                data = json.loads(result)
                if "chat" in data:
                    if first_chat:
                        first_chat = False
                        # if the date of chat does not change from last batch,
                        # we assume we have fetched all the comments.
                        if data["chat"]["date"] == when:
                            sending = False
                            break
                        when = data["chat"]["date"]
                    chats.append(data)
                else:
                    # reach the end of this batch
                    if "ping" in data and 'rf' in data["ping"]["content"]:
                        break
            chats_all.extend(chats)
        ws.close()

        # remove duplicate from chats_all
        _ = []
        for d in chats_all:
            if d not in _:
                _.append(d)
        chats_all = _
        chats_all.sort(key=lambda x: (x['chat']['date'], x['chat'].get('vpos', 0)))

        print(f'Total unique comments: {len(chats_all)}. Save to {self.filename}.json.')
        dump_json(chats_all, f'{self.filename}.json')

    def download_timeshift(self, info_only=False, comments='yes', verbose=False, dump=False):
        # download video type is not implemented yet
        if self.video_type != 'live':
            print('ERROR: Download video type is not implemented yet.')
            return

        live_data = self.fetch_page(self.url)
        title = live_data['program']['title']
        end_time_epoch = live_data["program"]["endTime"]
        begin_time_dt = to_jp_time(datetime.fromtimestamp(live_data['program']['beginTime']))
        date = begin_time_dt.strftime('%y%m%d')
        max_quality = live_data['program']['stream']['maxQuality']
        self.filename = safeify(f"{date} {title}_{self.video_id}")
        t = Table(show_header=False, show_lines=True)
        t.add_column('Desc.', style='bold green')
        t.add_column('Value')
        t.add_row('Video ID', self.video_id)
        t.add_row('Title', title)
        t.add_row('Start time', MyTime(begin_time_dt).jst("pretty") + " (JST)")
        t.add_row('Max quality', max_quality)
        t.add_row('Filename', self.filename)
        print(t)

        if dump:
            dump_json(live_data, f'{self.filename}.info.json')
        if info_only:
            return

        # check video availability
        if not live_data['site']['relive'].get('webSocketUrl', None):
            assert live_data['userProgramWatch']['canWatch'] == False
            # 'notHaveTimeshiftTicket': not reserved yet
            # 'notUseTimeshiftTicket': reserved but not activated
            if 'notHaveTimeshiftTicket' in live_data['userProgramWatch']['rejectedReasons'] or \
                'notUseTimeshiftTicket' in live_data['userProgramWatch']['rejectedReasons']:
                if input('WARN: You do not have timeshift ticket. Do you want to reserve/activate it now? Y/[N] ').lower() == 'y':
                    print('Reserving...')
                    # POST = reserve, PATCH = activate/use
                    r = self.session.post(f'https://live2.nicovideo.jp/api/v2/programs/{self.video_id}/timeshift/reservation')
                    print('Tried POST, response:', r.status_code)
                    r = self.session.patch(f'https://live2.nicovideo.jp/api/v2/programs/{self.video_id}/timeshift/reservation')
                    print('Tried PATCH, response:', r.status_code)
                    if not r.status_code == 200:
                        print('Reserving or activating failed. Please try reserving it manually in the webpage.')
                        return
                    # refetch live_data
                    live_data = self.fetch_page(self.url)
                else:
                    print("Aborted.")
                    return
            else:
                reasons = ', '.join(live_data['userProgramWatch']['rejectedReasons'])
                print(f'ERROR: You cannot watch this video because of: {reasons}.')
                return

        # Add warning if it's trial only
        if live_data['programWatch']['condition'].get('payment') == 'Ticket' and not live_data['userProgramWatch']['payment']['hasTicket']:
            # you can always download full comments, so no need to check if comments == 'only'
            if comments == 'only':
                pass
            if input('WARN: This timeshift requires a ticket but you don\'t have one. '
                     'The video will only have the trial part, and be black afterwards. '
                     'Do you want to continue? Y/[N] ').lower() != 'y':
                return

        ws_url = live_data['site']['relive']['webSocketUrl']
        audience_token = re.search(r'audience_token=(.+)', ws_url)[1]
        print(f'WS url is {ws_url}')
        print('Creating websocket connection...')
        # websocket.enableTrace(True)
        ws = self.create_ws(ws_url)
        verbose and print("Sent startWatching")
        ws.send('{"type":"startWatching","data":{"stream":{"quality":"' + max_quality + '","protocol":"hls","latency":"low","chasePlay":false},"room":{"protocol":"webSocket","commentable":true},"reconnect":false}}')
        room_info = None
        stream_info = None

        ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)

        while True:
            verbose and print("Receiving...")
            result =  ws.recv()
            verbose and print("Received '%s'" % result)
            data = json.loads(result)
            if data['type'] == 'room':
                room_info = data
                if comments in ['yes', 'only']:
                    ex.submit(self.download_comments, room_info, end_time_epoch)
            elif data['type'] == 'stream':
                stream_info = data
            # just grab all the info even if we don't need it, it doesn't save any time anyway.
            if room_info and stream_info:
                print('Got all the info we needed. Close WS.')
                break
        ws.close()

        if dump:
            dump_json(room_info, f'{self.filename}.roominfo.json')
            dump_json(stream_info, f'{self.filename}.streaminfo.json')

        if comments == 'only':
            ex.shutdown(wait=True)
            return

        m3u8_url = stream_info['data']['uri']
        text = self.session.get(m3u8_url).text
        playlist_url = re.search(r'^.+playlist\.m3u8.*$', text, re.MULTILINE)[0]
        playlist_url = urljoin(m3u8_url, playlist_url) #+ '&start=682.251'
        if verbose:
            print('master m3u8 URL:', m3u8_url)
            print('================== content ==================')
            print(text)
            print('==================== end ====================')
            print('playlist m3u8 URL:', playlist_url)
            print('================== content ==================')
            print(self.session.get(playlist_url).text)
            print('==================== end ====================')

        # do not use arrays. the way python quotes & is not compatible with cmd/bat which minyami uses.
        # See: https://stackoverflow.com/questions/74700723/
        # Make sure to also use shell=True for *nix systems
        cmd = f'minyami -d "{playlist_url}" --key {audience_token},{max_quality} -o "{self.filename}.ts"'
        if self.proxy:
             cmd += f' --proxy "{self.proxy}"'
        if verbose:
            cmd += ' --verbose'
        print('CMD is:')
        print(cmd)
        run(cmd, shell=True)

    def download_thumbnail(self):
        if self.video_type == 'live':
            print('Cannot download thumbnail for live.')
            return

        soup = get(self.url, session=self.session)
        data = json.loads(soup.find(id="js-initial-watch-data")["data-api-data"])
        thumbnails = data["video"]["thumbnail"]
        # get the last value, which is the highest resolution
        name, thumbnail_url = list(thumbnails.items())[-1]
        print(f"Best thumbnail variant: {name}, {thumbnail_url}")
        download(thumbnail_url, filename=self.video_id)

if __name__ == "__main__":
    import argparse

    # https://stackoverflow.com/questions/3853722/how-to-insert-newlines-on-argparse-help-text
    class SmartFormatter(argparse.HelpFormatter):
        def _split_lines(self, text, width):
            if text.startswith('R|'):
                return text[2:].splitlines()
            return argparse.HelpFormatter._split_lines(self, text, width)

    parser = argparse.ArgumentParser(formatter_class=SmartFormatter)
    parser.add_argument("url", help="URL or ID of nicovideo webpage")
    parser.add_argument('--verbose', '-v', action='store_true', help='Print verbose info for debugging.')
    parser.add_argument('--info', '-i', action='store_true', help='Print info only.')
    parser.add_argument('--dump', action='store_true', help='Dump all the metadata to json files.')
    parser.add_argument('--thumb', action='store_true', help='Download thumbnail only. Only works for video type (not live type).')
    parser.add_argument('--cookies', '-c', default='chrome', help='R|Cookie source. [Default: chrome]\nProvide either:\n  - A browser name to fetch from;\n  - The value of "user_session";\n  - A Netscape-style cookie file.')
    parser.add_argument('--comments', '-d', default='yes', choices=['yes', 'no', 'only'], help='Control if comments (danmaku) are downloaded. [Default: yes]')
    parser.add_argument('--proxy', default='auto', help='Specify a proxy, "none", or "auto" (automatically detects system proxy settings). [Default: auto]')
    args = parser.parse_args()

    nico_downloader = NicoDownloader(args.url, args.cookies, args.proxy)

    if args.thumb:
        nico_downloader.download_thumbnail()
    else:
        nico_downloader.download_timeshift(info_only=args.info, verbose=args.verbose, comments=args.comments, dump=args.dump)


