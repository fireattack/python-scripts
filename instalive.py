import concurrent.futures
import re
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from shutil import copy2, copyfileobj
from subprocess import run
from urllib.parse import unquote, urljoin

import requests
from tqdm import tqdm


def parse_iso8601_duration(duration):
    '''Parse ISO8601 duration to seconds.
    it sometimes uses float for seconds part, so we need to handle that.'''
    pattern = r'P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>[.\d]+)S)?)?'
    match = re.match(pattern, duration)
    if not match:
        return None

    days = int(match.group('days') or 0)
    hours = int(match.group('hours') or 0)
    minutes = int(match.group('minutes') or 0)
    seconds = int(float(match.group('seconds') or 0))

    # Convert everything to seconds
    total_seconds = (days * 86400) + (hours * 3600) + (minutes * 60) + seconds
    return total_seconds

def concat(files, output, verbose=False):
    '''Concatenate files into one file.'''
    output = Path(output)
    if not output.parent.exists():
        output.parent.mkdir(parents=True)
    out = output.open('wb')
    for f in tqdm(files, ncols=100):
        f = Path(f)
        if verbose:
            print(f'Merging {f.name}...')
        fi = f.open('rb')
        copyfileobj(fi, out)
        fi.close()
    out.close()

def get_webname(url):
    return unquote(url.split('?')[0].split('/')[-1])

def td_format(td):
    seconds = int(td.total_seconds())
    in_future = seconds > 0
    seconds = abs(seconds)
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
            has_s = 's' if period_value > 1 else ''
            strings.append(f"{period_value} {period_name}{has_s}")
    if in_future:
        return 'in ' + ', '.join(strings)
    else:
        return ', '.join(strings) + ' ago'


class InstaliveDownloader:
    def __init__(self, url, save_path, debug=False, quality=None):
        self.session = requests.Session()
        self.url = url
        self.save_path = Path(save_path)
        if not self.save_path.exists():
            self.save_path.mkdir(parents=True)
        self.debug = debug
        if debug:
            print('Debug mode enabled. Only download 30 segments.')
        self.fetch_mpd()
        self.parse_mpd(quality)

    def _download(self, url, save_path=None, filename=None, skip_existing=True):
        if save_path:
            f = Path(save_path) / get_webname(url)
        elif filename:
            f = Path(filename)
        if skip_existing and f.exists() and f.stat().st_size > 0:
            return 'Exists'
        f.parent.mkdir(parents=True, exist_ok=True)
        with self.session.get(url) as r:
            if r.status_code == 200:
                with f.open('wb') as f:
                    f.write(r.content)
            return r.status_code

    def save_mpd(self):
        print('Save mpd to local file...')
        (self.save_path/'mpd.mpd').write_text(self.mpd_text, encoding='utf-8')

    def fetch_mpd(self):
        print('Fetch mpd...')
        self.mpd_text = self.session.get(self.url).text
        self.mpd = ET.fromstring(self.mpd_text)
        return self.mpd

    def parse_mpd(self, quality=None):
        print('Parse mpd...')
        mpd = self.mpd
        #   availabilityStartTime="2024-05-06T01:21:00-07:00"
        #   availabilityEndTime="2024-05-06T01:29:00-07:00"
        current_time = datetime.now().astimezone()
        availability_start_time = datetime.strptime(mpd.attrib['availabilityStartTime'], '%Y-%m-%dT%H:%M:%S%z')
        availability_end_time = datetime.strptime(mpd.attrib['availabilityEndTime'], '%Y-%m-%dT%H:%M:%S%z')
        print(f'Availability start time: {availability_start_time} ({td_format(availability_start_time - current_time)})')
        print(f'Availability end time: {availability_end_time} ({td_format(availability_end_time - current_time)})')

        period = mpd[0]
        video_adaptation_set = period[0]
        # make a simple list of video representations because we can't directly sort xml elements
        videos = [
            (int(x.attrib['width']),
             int(x.attrib['height']),
             float(x.attrib['frameRate']),
             float(x.attrib['bandwidth']),
             idx,
             x.attrib['id']
             ) for idx, x in enumerate(video_adaptation_set)
        ]
        # bvr = best video representation
        print('Video representations:')
        for v in videos:
            print(f'[{v[4]}] {v[5]} {v[0]}x{v[1]}, {v[2]}fps, {v[3]/1024:.1f} kbps')

        if not quality:
            videos.sort(reverse=True)
            self.video_index = videos[0][-2]
            self.video_id = videos[0][-1]
            print(f'Use the best one ([{self.video_index}] {self.video_id}).')
        else:
            for v in videos:
                if v[5] == quality:
                    self.video_index = v[-2]
                    self.video_id = v[-1]
                    print(f'Use the specified one ([{self.video_index}] {self.video_id}).')
                    break
            else:
                raise Exception(f'Quality {quality} not found.')

        video_representation = video_adaptation_set[self.video_index]
        video_segment_template = video_representation[0]
        self.timescale = video_segment_template.attrib['timescale'] # not used for now
        self.video_init = urljoin(self.url, video_segment_template.attrib['initialization'])
        self.video_url_template = urljoin(self.url, video_segment_template.attrib['media']).replace('$Time$', '{}')
        timeline = video_segment_template[0]
        # find the last segment's t
        self.last_t = int(timeline[-1].attrib['t'])
        print(f'Last video segment t={self.last_t}')
        # find the best interval for iterating heuristically
        d_list = [int(x.attrib['d']) for x in timeline]
        print('Intervals between segments:', ', '.join(str(d) for d in d_list))
        # get most common interval
        interval = max(set(d_list), key=d_list.count)
        print(f'Heuristically set interval to {interval}')
        self.interval = interval

        # so far, instagram live only has one audio representation, so just use it.
        # if there are more than one, we need to change the code.
        assert len(period[1][0]) == 1, "Only one audio representation is supported. Please report if you see this message."
        audio_segment_template = period[1][0][0]
        self.audio_init = urljoin(self.url, audio_segment_template.attrib['initialization'])
        self.audio_url_template = urljoin(self.url, audio_segment_template.attrib['media']).replace('$Time$', '{}')

    def download_init(self):
        print('Download init segments...')
        r = self._download(self.video_init, save_path=self.save_path/'video')
        assert r in [200, 'Exists']
        r = self._download(self.audio_init, save_path=self.save_path/'audio')
        assert r in [200, 'Exists']

    def _get_segments(self):
        mpd = self.fetch_mpd() # fetch a new mpd to get the latest segments
        video_representation = mpd[0][0][self.video_index]
        assert video_representation.attrib['id'] == self.video_id
        timeline = video_representation[0][0]
        segments = [int(timeline[i].attrib['t']) for i in range(len(timeline))]
        return segments

    def manually_set(self, last_t=None):
        if last_t is not None:
            self.last_t = int(last_t)
            print(f'Last time set to {self.last_t}')

    def fetch_video_by_id(self, id):
        url = self.video_url_template.format(id)
        status = self._download(url, save_path=self.save_path/'video')
        return status

    def fetch_audio_by_id(self, id):
        url = self.audio_url_template.format(id)
        status = self._download(url, save_path=self.save_path/'audio')
        return status

    def quick_iterate(self, ids):
        # make sure ids are larger than 0
        ids = [id for id in ids if id > 0]
        print(f'\nUse multi-threading to check {len(ids)} IDs starting from {ids[0]}...')
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
            futures = {ex.submit(self.fetch_video_by_id, id): id for id in ids}
            try:
                for future in concurrent.futures.as_completed(futures):
                    if future.cancelled():
                        continue
                    id = futures[future]
                    status = future.result()
                    if status in ['Exists', 200]:
                        # cancel all other futures
                        for f in futures:
                            f.cancel()
                        return id, status
            except KeyboardInterrupt:
                print('\nInterrupted. Cancel all futures...')
                for f in futures:
                    f.cancel()
                raise KeyboardInterrupt
        return None, None

    def download_live(self):
        downloaded = set()

        mpd = self.mpd
        # check if mpd is dynamic
        if mpd.attrib.get('type') != 'dynamic':
            print('This mpd is not dynamic. Stop monitoring live.')
            return
        # use minimumUpdatePeriod if available. otherwise, use timeShiftBufferDepth/2-1 as the interval.
        # make sure it is at least 2s.
        fetch_interval = parse_iso8601_duration(mpd.attrib.get('minimumUpdatePeriod', 'PT0S')) \
            or parse_iso8601_duration(mpd.attrib.get('timeShiftBufferDepth', 'PT0S')) // 2 - 1
        fetch_interval = max(fetch_interval, 2)

        unchange_count = 0
        while True:
            new_segments = self._get_segments()
            if all(id in downloaded for id in new_segments):
                unchange_count += 1
            if unchange_count >= 5:
                print('All segments are downloaded. Stop.')
                break
            for id in new_segments:
                if id in downloaded:
                    continue
                # singe-thread should be enough for live stream
                self.fetch_video_by_id(id)
                self.fetch_audio_by_id(id)
                downloaded.add(id)
            time.sleep(fetch_interval)

    def download_video(self, forward=False):
        count = 0
        known_intervals = {
            self.interval: 0,
            self.interval - 1: 0,
            self.interval + 1: 0,
        }
        id_guesses = [self.last_t]
        prev_id = None
        sign = 1 if forward else -1

        def surrounding(x):
            # surrounding is defined as 60% interval behind of x and 110% interval ahead of x
            # ahead is 100% to make sure the download can continue if there is one missing segment.
            start_id = x - int(self.interval * 0.6) * sign
            end_id = x + int(self.interval * 1.1 + 1) * sign
            ids = list(range(start_id, end_id, -1 if start_id > end_id else 1))
            ids.sort(key=lambda x: abs(x - x))
            return ids

        while True:
            valid_id = None
            # firstly, we try to find if existing local file that is close to the guesses[0].
            # which is defined as +/- 10% of the interval.
            # notice that we don't need to try all the guesses, they will be checked in the
            # next step.
            for candidate in range(id_guesses[0] - int(self.interval*0.1), id_guesses[0] + int(self.interval*0.1) + 1):
                url = self.video_url_template.format(candidate)
                f = self.save_path/'video'/ get_webname(url)
                if f.exists() and f.stat().st_size > 0:
                    valid_id = candidate
                    print(f'\rSegment {valid_id}: {f} already exists. Skip.   ', end='')
                    break
            # if not found locally, we try to fetch the segment by id from the all
            # (last_valid_id - potential_interval) pools.
            # The order matters: we try the most common interval first.
            # this is single-threaded, because it is more costly to close all the threads
            # if we initiate them altogether..
            if not valid_id:
                for candidate in id_guesses:
                    status = self.fetch_video_by_id(candidate)
                    print(f'\rSegment {candidate}: HTTP {status}                                 ', end='')
                    if status in [200, 'Exists']:
                        valid_id = candidate
                        break
            # If still not found, we iterate around the guesses[0] to find the next segment.
            # the range is defined as 60% behind of x and 110% ahead of x,
            # e.g. for 2000 interval, it would be last_id - 800 to last_id - 4200, sorted by
            # distance to last_id - 2000.
            # notice that it covers up to the range of next next id, this way we ensure we still
            # continue the downloading instead of stopping too early (despite missing a segment).
            if not valid_id:
                ids = [id for id in surrounding(id_guesses[0]) if id not in id_guesses]
                valid_id, status = self.quick_iterate(ids)
                # if still not, we assume we downloaded them all and stop.
                if not valid_id:
                    print("\nFailed to find next segment. Assume we downloaded all. Stop.")
                    break
                print(f'\rSegment {valid_id}: HTTP {status}                                 ', end='')
            # at this point, we should have a valid_id.
            assert valid_id
            # add new interval to known_intervals
            if prev_id:
                new_interval = abs(valid_id - prev_id)
                # do not add new interval if it is too different from the current interval.
                # for example, if the nominal interval is 2000, we should only add ones that are
                # less than 3000. Otherwise we enables the possibility of skipping segments.
                # But it is still allowed to have such large interval so we don't stop downloading
                # in the middle just because of one missing segment.
                if new_interval >= self.interval * 1.6:
                    pass
                # add interval to known_intervals (if not already), and increase the count.
                else:
                    known_intervals.setdefault(new_interval, 0)
                    known_intervals[new_interval] += 1

            # print(f'[Debug] known_intervals: {known_intervals}')
            count += 1
            if self.debug and count == 30:
                break
            prev_id = valid_id
            # sort known_intervals by appearance, so we try the most common interval first.
            known_intervals = dict(sorted(known_intervals.items(), key=lambda x: x[1], reverse=True))
            id_guesses = [valid_id + interval * sign for interval in known_intervals]

    def check(self):
        print('Check if there is any missing segment...')
        p = self.save_path / 'video'
        files = list(p.iterdir())
        # filename format: 17981336783244063_0-1297029.m4v
        ids = [int(m[1]) for f in files if (m := re.search(r'\d+_0-(\d+)', f.name))]
        ids.sort()
        # calculate difference between each id
        diffs = [ids[i+1] - ids[i] for i in range(len(ids)-1)]

        diff_count = {}
        for diff in diffs:
            diff_count[diff] = diff_count.get(diff, 0) + 1
        print(f'Count of diff values between each segment:', diff_count)

        if max(diffs) > self.interval * 1.1:
            idx = diffs.index(max(diffs))
            worst = (ids[idx], ids[idx+1])
            print(f'Largest ID diff between each segment: {max(diffs)}, at {ids[idx]} -> {ids[idx+1]}')
            idx = diffs.index(min(diffs))
            print(f'Smallest ID diff between each segment: {min(diffs)}, at {ids[idx]} -> {ids[idx+1]}')
            print(f'It is likely that the video is not fully downloaded!!')
            return worst
        else:
            print('No missing segment found.')

    def download_audio(self):
        print('Downloading audio segments...')
        audio_save_path = self.save_path / 'audio'
        files = list((self.save_path / 'video').iterdir())
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
            futures = []
            count = 0
            for f in files:
                if not f.is_file():
                    continue
                if f.suffix != '.m4v':
                    continue
                id = re.search(r'_0-(init|\d+)\.m4v', f.name)[1]
                url = self.audio_url_template.format(id)
                futures.append(ex.submit(self._download, url, save_path=audio_save_path))
            for _ in concurrent.futures.as_completed(futures):
                count += 1
                print(f'Finished {count}/{len(futures)}         ', end='\r')

    def merge(self):
        def get_key(f):
            '''Make sure init segment is always at the beginning.'''
            if '-init' in f.name:
                return 0
            return int(re.search(r'\d+_0-(\d+)', f.name)[1])

        video_file = self.save_path / 'video.m4v'
        files = list((self.save_path / 'video').iterdir())
        print(f'Find {len(files)} video segments. Merging...')
        files.sort(key=get_key)
        concat(files, video_file)

        audio_file = self.save_path / 'audio.m4a'
        files2 = list((self.save_path / 'audio').iterdir())
        print(f'Find {len(files2)} audio segments. Merging...')
        files2.sort(key=get_key)
        concat(files2, audio_file)
        print(f'Merging video and audio using FFMPEG...')
        run(['ffmpeg', '-loglevel', 'error', '-stats', '-i', video_file, '-i', audio_file, '-c', 'copy', self.save_path/'merged.mp4'])

    def import_segments(self, path):
        '''Import segments downloaded via N_m3u8DL-RE.'''
        path = Path(path)
        for p in path.iterdir():
            if p.is_dir() and (p / '_init.mp4').exists():
                if 'avc' in p.name:
                    template = self.video_url_template
                    type_ = 'video'
                else:
                    template = self.audio_url_template
                    type_ = 'audio'
                for f in p.iterdir():
                    if f.stem.isdigit():
                        id = int(f.stem)
                        new_filename = get_webname(template.format(id))
                        newf = self.save_path / type_ / new_filename
                        if newf.exists():
                            if newf.stat().st_size == f.stat().st_size:
                                print(f'{id}: {newf} already exists. Skip.')
                            else:
                                raise Exception(f'{id}: {newf} already exists but size is different.')
                        else:
                            print(f'{id}: Copy {f} to {newf}')
                            copy2(f, newf)


def main(url, save_path, time, debug, action, quality):
    downloader = InstaliveDownloader(url=url, save_path=save_path, debug=debug, quality=quality)
    if time is not None:
        downloader.manually_set(time)
    if action.startswith('import'):
        import_path = action.partition(':')[2]
        downloader.import_segments(import_path)
        return
    if action == 'info':
        for k, v in downloader.__dict__.items():
            print(f'{k}: {v}')
        return
    try:
        if action == 'all':
            downloader.save_mpd()
            downloader.download_init()
            def task1():
                downloader.download_video()
                downloader.download_audio()
            t1 = threading.Thread(target=task1)
            t2 = threading.Thread(target=downloader.download_live)
            t1.start()
            t2.start()
            t1.join()
            t2.join()
            downloader.check()
            downloader.merge()
        elif action == 'live':
            downloader.save_mpd()
            downloader.download_live()
        elif action == 'video':
            downloader.save_mpd()
            downloader.download_init()
            downloader.download_video()
        elif action == 'audio':
            downloader.download_audio()
        elif action == 'merge':
            downloader.merge()
        elif action == 'check':
            downloader.check()
        elif action == 'manual':
            if args.range:
                start, end = map(int, args.range.split('-'))
                print(f'manually set range to from {start} to {end} (inclusive)')
            else:
                worst = downloader.check()
                if not worst:
                    print('No bad interval found. Stop.')
                    return
                start = worst[0] + 1
                end = worst[1] - 1
                print(f'automatically largest interval, between {start} and {end} (inclusive)')
            ids = list(range(start, end + 1)) if start < end else list(range(start, end - 1, -1))
            downloader.quick_iterate(ids)

    except KeyboardInterrupt:
        print('\nInterrupted by user. Stop.')


if __name__ == '__main__':
    import argparse

    class CustomHelpFormatter(argparse.RawTextHelpFormatter):
        pass

    parser = argparse.ArgumentParser(
        description='Available actions:\n'
                    '  all      - Download both video and audio, and merge them (default)\n'
                    '  live     - Download the live stream only\n'
                    '  video    - Download video only\n'
                    '  audio    - Download audio only\n'
                    '  merge    - Merge downloaded video and audio\n'
                    '  check    - Check the downloaded segments to make sure there is no missing segments\n'
                    '  manual   - Manually process a specified range (used together with --range)\n'
                    '  info     - Display downloader object info\n'
                    '  import:<path> - Import segments downloaded via N_m3u8DL-RE from a given path',
        formatter_class=CustomHelpFormatter
    )


    parser.add_argument("url", help="url of mpd")
    parser.add_argument("--action", '-a', default='all', help="action to perform (default: all)")
    parser.add_argument("--dir", "-d", default='.', help="save path (default: CWD)")
    parser.add_argument("--debug", action='store_true', help="debug mode")
    parser.add_argument("--quality", "-q", help="manually assign video quality (default: auto)")
    parser.add_argument("--time", "-t", help="manually assign last t (default: auto)")
    parser.add_argument('--range', help='manually assign range (start,end) for quick iterate test mode')

    args = parser.parse_args()

    main(args.url, args.dir, args.time, args.debug, args.action, args.quality)

