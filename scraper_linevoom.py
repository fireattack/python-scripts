import concurrent.futures
import datetime
import json
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def dump_json(mydict, filename):
    filename = Path(filename)
    if filename.suffix.lower() != '.json':
        filename = filename.with_suffix('.json')
    filename.parent.mkdir(parents=True, exist_ok=True)
    with filename.open('w', encoding='utf-8') as f:
        json.dump(mydict, f, ensure_ascii=False, indent=2)


def load_json(filename):
    filename = Path(filename)
    with filename.open('r', encoding='utf-8') as f:
        data = json.load(f)
    return data

# Modified from https://www.peterbe.com/plog/best-practice-with-retries-with-requests


def requests_retry_session(retries=5, backoff_factor=0.2):
    session = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=None,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


def to_jp_date(timestamp):
    dt = datetime.datetime.fromtimestamp(timestamp / 1000)
    dt = dt.astimezone(datetime.timezone(datetime.timedelta(hours=9)))
    return dt.strftime('%y%m%d')


def parse_list(user_id):
    results = []
    post_id = None
    updated_time = None

    while True:
        url = "https://linevoom.line.me/api/socialprofile/getPosts"
        params = {
            'homeId': user_id,
            'withSocialHomeInfo': 'false',
            'postLimit': '10',
            'postId': post_id,
            'updatedTime': updated_time,
        }

        headers = {
            'referer': f'https://linevoom.line.me/user/{user_id}',
        }

        r = requests_retry_session().request("GET", url, headers=headers, params=params)
        data = r.json()
        if not 'posts' in data['data']:
            break
        posts = data['data']['posts']
        print(f'Find {len(posts)} posts: from {posts[0]["postInfo"]["postId"]} to {posts[-1]["postInfo"]["postId"]}')
        for post in posts:
            results.append(post)

        post_id = posts[-1]['postInfo']['postId']
        updated_time = posts[-1]['postInfo']['updatedTime']

    return results


def parse_item(post, save_folder, verbose=False):
    post_id = post['postInfo']['postId']
    date = to_jp_date(post['postInfo']['createdTime'])

    medias = post['contents']['media']

    for idx, media in enumerate(medias, 1):
        img_url = f'https://obs.line-scdn.net/{media["resourceId"]}'
        img_name = f'{date} {post_id}_{idx}'
        tries = 0
        while tries < 5:
            try:
                with requests_retry_session().get(img_url, stream=True) as r:
                    suffix = '.' + r.headers['content-type'].split('/')[-1].replace('jpeg', 'jpg')
                    expected_filesize = int(r.headers['content-length'])
                    f = save_folder / (img_name + suffix)
                    f_temp = f.with_name(f.name + '.dl')
                    if f.exists() and expected_filesize == f.stat().st_size:
                        verbose and print(f'[I] {f.name} already exists and is identical. Skip.')
                        if f_temp.exists():
                            # if f already exists and is good, remove any potential temp file from previous download(s).
                            f_temp.unlink()
                        break
                    else:
                        if f.exists() and expected_filesize != f.stat().st_size:
                            print(f'[W] {f.name} already exists but filesize is a mismatch. Re-download and overwrite.')
                        if verbose:
                            print(f'[I] Downloading {f.name} from {img_url}...')
                        else:
                            print(f'[I] Downloading {f.name}...')
                        with f_temp.open('wb') as fio:
                            for chunk in r.iter_content(chunk_size=8192):
                                if chunk:
                                    fio.write(chunk)
                        if f_temp.stat().st_size == expected_filesize:
                            # remove old, broken file.
                            if f.exists():
                                f.unlink()
                            f_temp.rename(f)
                            break
                        else:
                            print(f'[E] {f.name}: file download failed: filesize does not match. Retry...')
                            f_temp.unlink()
            except Exception as e:
                print(f'[E] {img_name}: file download failed: {e}. Retry...')
            tries += 1


def main(user_id, save_folder, threads, verbose):

    save_folder = Path(save_folder)
    save_folder.mkdir(parents=True, exist_ok=True)

    data = parse_list(user_id)
    print(f'Find {len(data)} posts in total.')
    print(f'Save data to {save_folder / "!data.json"}')
    dump_json(data, save_folder / '!data.json')

    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as ex:
        for post in data:
            ex.submit(parse_item, post, save_folder=save_folder, verbose=verbose)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Download LINE VOOM posts and images.')
    parser.add_argument('user_id', help='LINE VOOM user id (the string after "/user/" in the URL)')
    parser.add_argument('--output', '-o', help='folder to save files (default: {CWD}/{user_id})')
    parser.add_argument('--threads', '--thread', type=int, default=10, help='image downloading thread number (default: 10)')
    parser.add_argument('--verbose', '-v', action='store_true', help='verbose mode')

    args = parser.parse_args()
    save_folder = args.output if args.output else args.user_id
    main(args.user_id, save_folder=save_folder, threads=args.threads, verbose=args.verbose)
