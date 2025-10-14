import concurrent.futures
import json
import re
from datetime import datetime
from subprocess import run
from urllib.parse import urljoin, urlparse
from urllib.request import getproxies
from pathlib import Path
import websocket
from rich.console import Console
from rich.table import Table

from util import download, dump_json, get, MyTime, requests_retry_session, safeify, to_jp_time, load_cookie
from proto.dwango.nicolive.chat.service.edge import payload_pb2 as chat
import google.protobuf.json_format

console = Console()
print = console.print

# based on https://github.com/rinsuki-lab/ndgr-reader/blob/main/src/protobuf-stream-reader.ts
def read_protobuf_message(data):
    offset = 0
    result = 0
    i = 0
    while True:
        if offset >= len(data):
            return None
        current = data[offset]
        result |= (current & 0x7F) << i
        offset += 1
        i += 7
        if not (current & 0x80):
            break
    if offset + result > len(data):
        return None
    return data[offset:offset + result]


class NicoDownloader():
    HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36'}

    def __init__(self, cookies, proxy=None, save_dir=None):
        def validate_cookie(cookies):
            for cookie in cookies:
                if cookie.name == 'user_session' and cookie.value:
                    print('Find user_session in cookie:', cookie.value)
                    break
            else:
                print(f'WARN: Cannot find user_session in cookie. You\'re probably not logged in.')
                # exit(1) # make it non-fatal
        if isinstance(cookies, str) and cookies.lower() in ['chrome', 'firefox', 'edge']:
            cookies = load_cookie(cookies + '/nicovideo.jp')
            validate_cookie(cookies)
        elif isinstance(cookies, str) and cookies.startswith('user_session_'):
            cookies = {'user_session': cookies}
        elif Path(cookies).exists():
            print(f'Loading cookies from file {cookies}...')
            cookies = load_cookie(cookies)
            validate_cookie(cookies)
        else:
            print('ERROR: Invalid cookie source. Please provide a browser name, a cookie value, or a Netscape-style cookie file.')
            exit(1)

        self.session = requests_retry_session()
        self.session.cookies.update(cookies)
        self.session.headers.update(self.HEADERS)

        # proxy settings
        if not proxy or proxy.lower() == 'none':
            # it's recommended to set proxy to '' instead of None, otherwise
            # some redirected requests may not actually use the proxy settings.
            # see https://github.com/psf/requests/issues/6153
            proxy = ''
        elif proxy == 'auto':
            sys_proxies = getproxies()
            if proxy := sys_proxies.get('http', ''): # if failed, proxy would be ''
                print(f'INFO: Automatically use system proxy {proxy}')
        # I don't think system proxy would be missing scheme ever, but just in case
        if proxy and '://' not in proxy:
            print('WARN: Proxy is missing scheme. Assuming http://')
            proxy = f'http://{proxy}'
        # setting self.session.proxies alone isn't enough; because requests will
        # prioritize system proxy over session.proxies.
        # you have to set proxy at request level to override system proxy.
        # see https://github.com/psf/requests/issues/2018
        # so, we have to disable system proxy by setting trust_env to False first.
        self.session.trust_env = False
        self.session.proxies = {'http': proxy, 'https': proxy}
        # this is for websocket connection/minyami download
        self.proxy = proxy
        self.save_dir = Path(save_dir) if save_dir else Path.cwd()

    def _parse_url_or_video_id(self, url_or_video_id):
        if m := re.search(r'/watch/([^?&]+)', url_or_video_id):
            video_id = m[1]
        else:
            video_id = url_or_video_id
        if video_id.startswith('lv'):
            url = f'https://live.nicovideo.jp/watch/{video_id}'
            video_type = 'live'
        else:
            url = f'https://www.nicovideo.jp/watch/{video_id}'
            video_type = 'video'
        return video_id, url, video_type

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

    def download_comments_native(self, message_server_info, output):
        view_uri = message_server_info['data']['viewUri']
        #"vposBaseTime": "2024-09-25T21:50:00+09:00",
        vpos_base_time_dt = datetime.strptime(message_server_info['data']['vposBaseTime'], '%Y-%m-%dT%H:%M:%S%z')
        vpos_base_time_epoch = int(vpos_base_time_dt.timestamp())
        print(f'vpos Base time: {vpos_base_time_dt} ({vpos_base_time_epoch})')

        at = 'now'
        backward_api_uri = None
        while True:
            url = f'{view_uri}?&at={at}'
            print(f'Fetch {url}')
            r = self.session.get(url, timeout=30)
            message = read_protobuf_message(r.content)
            chunked_entry = chat.ChunkedEntry()
            chunked_entry.ParseFromString(message)
            if chunked_entry.HasField('next'):
                at = chunked_entry.next.at
            elif chunked_entry.HasField('backward'):
                backward_api_uri = chunked_entry.backward.segment.uri
                break
        messages = []
        while True:
            print(f'Fetch {backward_api_uri}')
            r2 = self.session.get(backward_api_uri, timeout=30)
            packed_segment = chat.PackedSegment()
            packed_segment.ParseFromString(r2.content)
            # prepend to messages
            messages = [message for message in packed_segment.messages] + messages
            if packed_segment.HasField('next'):
                backward_api_uri = packed_segment.next.uri
            else:
                break
        print(f'Find {len(messages)} messages.')
        dump_json([google.protobuf.json_format.MessageToDict(message) for message in messages], output)
        # TODO: convert the json to a format that is compatible with nicoxml2ass


    def download_timeshift(self, url_or_video_id, info_only=False, comments='no', verbose=False, dump=False, auto_reserve=False, simulate=False):
        video_id, url, video_type = self._parse_url_or_video_id(url_or_video_id)

        return_value = {
            'id': video_id,
            'url': url,
            'type': video_type,
        }

        # download video type is not implemented yet
        if video_type != 'live':
            print('ERROR: Download video type is not implemented yet.')
            return return_value

        live_data = self.fetch_page(url)
        title = live_data['program']['title']
        begin_time_epoch = live_data["program"]["beginTime"]
        end_time_epoch = live_data["program"]["endTime"]
        begin_time_dt = to_jp_time(datetime.fromtimestamp(begin_time_epoch))
        end_time_dt = to_jp_time(datetime.fromtimestamp(end_time_epoch))

        date = begin_time_dt.strftime('%y%m%d')
        max_quality = live_data['program']['stream']['maxQuality']
        filename = safeify(f"{date} {title}_{video_id}")
        t = Table(show_header=False, show_lines=True)
        t.add_column('Desc.', style='bold green')
        t.add_column('Value')
        t.add_row('Video ID', video_id)
        t.add_row('Title', title)
        t.add_row('Start time', MyTime(begin_time_dt).jst("pretty") + " (JST)")
        t.add_row('Max quality', max_quality)
        t.add_row('Filename', filename)
        print(t)

        return_value.update({
            'title': title,
            'begin_time': begin_time_dt,
            'end_time': end_time_dt,
            'short_date': date,
            'max_quality': max_quality,
            'filename': filename,
            'info': live_data
        })

        if dump:
            dump_json(live_data, self.save_dir / f'{filename}.info.json')
        if info_only:
            return return_value

        # check video availability
        # use while, this way when we reserve/activate timeshift ticket, we can refetch live_data and recheck
        # to see if there is any other errors
        while not live_data['site']['relive'].get('webSocketUrl', None):
            assert live_data['userProgramWatch']['canWatch'] == False
            if auto_reserve or input(f'WARN: You don\'t have or have not activated the timeshift ticket:\n{live_data["userProgramWatch"]}\nDo you want to reserve/activate it now? Y/[N] ').lower() == 'y':
                print('Reserving...')
                # POST = reserve, PATCH = activate/use
                reservation_url = f'https://live2.nicovideo.jp/api/v2/programs/{video_id}/timeshift/reservation'
                r = self.session.post(reservation_url)
                print('Tried POST, response:', r.status_code)
                r = self.session.patch(reservation_url)
                print('Tried PATCH, response:', r.status_code)
                if r.status_code != 200:
                    print('Reserving or activating failed. Please try reserving it manually on the webpage.')
                    return return_value
                # refetch live_data
                live_data = self.fetch_page(url)
                # back to the beginning of the loop
            else:
                print("Aborted.")
                return return_value

        # Add warning if it's trial only
        if live_data['programWatch']['condition'].get('payment') == 'Ticket' and not live_data['userProgramWatch']['payment']['hasTicket']:
            # you can always download full comments, so no need to check if comments == 'only'
            if comments == 'only':
                pass
            if input('WARN: This timeshift requires a ticket but you don\'t have one. '
                     'The video will only have the trial part, and be black afterwards. '
                     'Do you want to continue? Y/[N] ').lower() != 'y':
                return return_value

        ws_url = live_data['site']['relive']['webSocketUrl']
        audience_token = re.search(r'audience_token=(.+)', ws_url)[1]
        print(f'WS url is {ws_url}')
        print('Creating websocket connection...')
        # websocket.enableTrace(True)
        ws = self.create_ws(ws_url)
        verbose and print("Sent startWatching")
        start_watching_payload = {
            "type": "startWatching",
            "data": {
            "stream": {
                "quality": max_quality,
                "protocol": "hls",
                "latency": "low",
                "chasePlay": False,
                'accessRightMethod': 'single_cookie'
            },
            "room": {
                "protocol": "webSocket",
                "commentable": True
            },
            "reconnect": False
            }
        }
        verbose and print('Payload:', start_watching_payload)
        ws.send(json.dumps(start_watching_payload))
        stream_info = None
        message_server_info = None

        while True:
            verbose and print("Receiving...")
            result =  ws.recv()
            verbose and print("Received '%s'" % result)
            data = json.loads(result)
            if data['type'] == 'stream':
                stream_info = data
            elif data['type'] == 'messageServer':
                message_server_info = data
            if stream_info and message_server_info:
                print('Got all the info we needed. Close WS connection.')
                break
        ws.close()

        if dump:
            dump_json(stream_info, self.save_dir / f'{filename}.streaminfo.json')
            dump_json(message_server_info, self.save_dir / f'{filename}.msgserverinfo.json')
        return_value.update({
            'stream_info': stream_info,
            'message_server_info': message_server_info
        })

        ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        if not simulate and comments in ['yes', 'only']:
            print('Downloading comments...')
            danmaku_output = self.save_dir / f'{filename}.json'
            return_value['danmaku'] = danmaku_output
            if comments == 'yes':
                ex.submit(self.download_comments_native, message_server_info, danmaku_output)
            elif comments == 'only':
                self.download_comments_native(message_server_info, danmaku_output)
                return return_value
        else:
            return_value['danmaku'] = None

        master_m3u8_url = stream_info['data']['uri']

        if 'assetdelivery.dlive' in master_m3u8_url:
            print('WARN: This is a DLive stream. Will use yt-dlp to download.')
            assert 'cookies' in stream_info['data']
            for c in stream_info['data']['cookies']:
                self.session.cookies.set(c['name'], c['value'])
            playlist_url = None
            if verbose:
                print('master m3u8 URL:', master_m3u8_url)
                print('================== content ==================')
                print(self.session.get(master_m3u8_url).text)
                print('==================== end ====================')
            output = self.save_dir / f'{filename}.mp4'
            dlive_bid = self.session.cookies.get("dlive_bid")
            # cmd = f'yt-dlp "{master_m3u8_url}" --ignore-config -N 10 -o "{output}" --add-headers "Cookie:dlive_bid={dlive_bid}"'
            save_dir_str = str(self.save_dir).rstrip('\\') # remove trailing backslash otherwise it will escape quotes in cmd
            cmd = f'N_m3u8DL-RE "{master_m3u8_url}" --save-name "{filename}" --save-dir "{save_dir_str}" --auto-select -H "Cookie:dlive_bid={dlive_bid}" -mt -M format=mp4 --no-date-info'
        else:
            master_m3u8_text = self.session.get(master_m3u8_url).text
            playlist_url = re.search(r'^.+playlist\.m3u8.*$', master_m3u8_text, re.MULTILINE)[0]
            playlist_url = urljoin(master_m3u8_url, playlist_url) #+ '&start=682.251'
            if verbose:
                print('master m3u8 URL:', master_m3u8_url)
                print('================== content ==================')
                print(master_m3u8_text)
                print('==================== end ====================')
                print('playlist m3u8 URL:', playlist_url)
                print('================== content ==================')
                print(self.session.get(playlist_url).text)
                print('==================== end ====================')
            output = self.save_dir / f'{filename}.ts'
            # do not use arrays. the way python quotes & is not compatible with cmd/bat which minyami uses.
            # See: https://stackoverflow.com/questions/74700723/
            # Make sure to also use shell=True for *nix systems
            cmd = f'minyami -d "{playlist_url}" --key {audience_token},{max_quality} -o "{output}"'
            if self.proxy:
                cmd += f' --proxy "{self.proxy}"'

        if verbose:
            cmd += ' --verbose'
        print('CMD is:')
        print(cmd)
        if simulate:
            output = None
        else:
            run(cmd, shell=True)
            ex.shutdown(wait=True) # ensure download_comments is finished

        return_value.update({
            'master_m3u8_url': master_m3u8_url,
            'playlist_m3u8_url': playlist_url,
            'output': output,
        })

        return return_value


    def download_thumbnail(self, url_or_video_id, info_only=False, dump=False):
        video_id, url, video_type = self._parse_url_or_video_id(url_or_video_id)

        if video_type == 'live':
            print('Cannot download thumbnail for live.')
            return

        soup = get(url, session=self.session)
        data = json.loads(soup.find(id="js-initial-watch-data")["data-api-data"])
        if dump:
            dump_json(data, self.save_dir / f'{video_id}.info.json')
        if info_only:
            return
        thumbnails = data["video"]["thumbnail"]
        # get the last value, which is the highest resolution
        name, thumbnail_url = list(thumbnails.items())[-1]
        print(f"Best thumbnail variant: {name}, {thumbnail_url}")
        download(thumbnail_url, filename=self.save_dir / video_id)

if __name__ == "__main__":
    import shlex
    import sys
    import argparse

    # auto load arguments from nico.txt
    for f in [Path(__file__).parent / 'nico.txt', Path('nico.txt')]:
        if f.exists():
            with open(f, encoding='utf8') as f:
                # insert in front so it can be overridden
                commands = shlex.split(f.read().replace('\\', '\\\\'))
                sys.argv[1:1] = commands
                break

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
    parser.add_argument('--cookies', '-c', help='R|Cookie source.\nProvide either:\n  - A browser name to fetch from;\n  - The value of "user_session";\n  - A Netscape-style cookie file.')
    parser.add_argument('--comments', '-d', default='no', choices=['yes', 'no', 'only'], help='Control if comments (danmaku) are downloaded. [Default: no]')
    parser.add_argument('--proxy', default='auto', help='Specify a proxy, "none", or "auto" (automatically detects system proxy settings). [Default: auto]')
    parser.add_argument('--save-dir', '-o', help='Specify the directory to save the downloaded files. [Default: current directory]')
    parser.add_argument('--reserve', action='store_true', help='Automatically reserve timeshift ticket if not reserved yet. [Default: no]')
    parser.add_argument('--simulate', action='store_true', help='Simulate the download process without actually downloading.')

    args = parser.parse_args()

    nico_downloader = NicoDownloader(args.cookies, args.proxy, save_dir=args.save_dir)

    if args.thumb:
        nico_downloader.download_thumbnail(args.url, info_only=args.info, dump=args.dump)
    else:
        nico_downloader.download_timeshift(args.url, info_only=args.info, verbose=args.verbose, comments=args.comments, dump=args.dump, auto_reserve=args.reserve, simulate=args.simulate)


