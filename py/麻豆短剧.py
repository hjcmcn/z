# -*- coding: utf-8 -*-
import requests
import re
import sys
import json
import urllib.parse
from base.spider import Spider
from urllib.parse import urljoin

sys.path.append('..')


class Spider(Spider):
    CANDIDATE_DOMAINS = [
        "https://mdcmai4.xyz",
        "https://mdcmai5.xyz",
    ]
    decode_mode = 0

    def __init__(self):
        super().__init__()
        self._xurl = None
        self._headers = None

    def getName(self):
        return "麻豆传媒AI"

    def init(self, extend):
        self._detect_domain()

    def _detect_domain(self):
        for domain in self.CANDIDATE_DOMAINS:
            try:
                h = {
                    'User-Agent': 'Mozilla/5.0 (Linux; Android 13; M2102J2SC Build/TKQ1.221114.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/144.0.7559.31 Mobile Safari/537.36',
                    'Referer': domain,
                }
                r = requests.get(f"{domain}/api/v1/categories", headers=h, timeout=3)
                if r.status_code == 200:
                    data = r.json()
                    if data.get('code') == 200:
                        self._xurl = domain
                        self._headers = h
                        return
            except Exception:
                continue
        self._xurl = self.CANDIDATE_DOMAINS[0]
        self._headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 13; M2102J2SC Build/TKQ1.221114.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/144.0.7559.31 Mobile Safari/537.36',
            'Referer': self._xurl,
        }

    def _domain(self):
        if self._xurl is None:
            self._detect_domain()
        return self._xurl

    def _req_headers(self):
        if self._headers is None:
            self._detect_domain()
        return self._headers

    def _fetch_api(self, path, params=None):
        url = f"{self._domain()}/api/v1{path}"
        resp = requests.get(url, headers=self._req_headers(), params=params, timeout=15)
        resp.encoding = resp.apparent_encoding or 'utf-8'
        data = json.loads(resp.text)
        return data

    def _build_image_url(self, cover_url):
        if not cover_url:
            return ''
        if cover_url.startswith('http'):
            return cover_url
        if '/api/v1/image/proxy' in cover_url:
            return urljoin(self._domain(), cover_url)
        if cover_url.startswith('/uploads/'):
            return urljoin(self._domain(), cover_url)
        encoded = urllib.parse.quote(cover_url, safe='')
        return f"{self._domain()}/api/v1/image/proxy?path={encoded}"

    def _build_m3u8_proxy_url(self, video_url):
        if not video_url:
            return ''
        if video_url.startswith('http'):
            parsed = urllib.parse.urlparse(video_url)
            path = parsed.path.lstrip('/')
        else:
            path = video_url.lstrip('/')
        encoded = urllib.parse.quote(path, safe='')
        return f"{self._domain()}/api/v1/m3u8/proxy?path={encoded}"

    def _parse_video_items(self, items):
        videos = []
        for item in items:
            vid = str(item.get('id', ''))
            if not vid:
                continue

            title = item.get('title', '').strip()
            if not title:
                continue

            pic = self._build_image_url(item.get('coverUrl', ''))

            remark = ''
            dur = item.get('durationSec', 0)
            if dur and dur > 0:
                mins = dur // 60
                secs = dur % 60
                remark = f'{mins:02d}:{secs:02d}'

            videos.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark
            })
        return videos

    def _parse_short_drama_items(self, items):
        videos = []
        for item in items:
            vid = str(item.get('id', ''))
            if not vid:
                continue

            title = item.get('title', '').strip()
            if not title:
                continue

            pic = self._build_image_url(item.get('coverUrl', ''))

            ep_count = item.get('episodeCount', 0)
            if ep_count:
                remark = f'{ep_count}集'
            else:
                remark = ''

            videos.append({
                "vod_id": f'sd_{vid}',
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark
            })
        return videos

    def homeContent(self, filter):
        filters = {}
        sort_filter = {
            "key": "sortBy",
            "name": "排序",
            "value": [
                {"n": "最新", "v": "newest"},
                {"n": "最早", "v": "oldest"},
                {"n": "播放最多", "v": "views"},
                {"n": "点赞最多", "v": "likes"},
                {"n": "收藏最多", "v": "favorites"},
            ]
        }
        time_filter = {
            "key": "timeRange",
            "name": "更新时间",
            "value": [
                {"n": "全部", "v": ""},
                {"n": "近7天", "v": "7d"},
                {"n": "近1月", "v": "1m"},
                {"n": "近3月", "v": "3m"},
            ]
        }
        duration_filter = {
            "key": "minDuration",
            "name": "视频时长",
            "value": [
                {"n": "全部", "v": ""},
                {"n": "10分钟以上", "v": "10"},
                {"n": "20分钟以上", "v": "20"},
            ]
        }

        class_items = [{"type_id": "short-dramas", "type_name": "AI短剧"}]
        try:
            data = self._fetch_api('/categories')
            cats_raw = data.get('data', [])
            video_cats = [c for c in cats_raw if c.get('type') == 'video' and c.get('enabled')]
            for c in video_cats:
                cid = str(c['id'])
                class_items.append({
                    "type_id": cid,
                    "type_name": c['name']
                })
                filters[cid] = [sort_filter, time_filter, duration_filter]
        except:
            pass

        return {"class": class_items, "filters": filters}

    def homeVideoContent(self):
        try:
            data = self._fetch_api('/videos', params={'page': 1, 'size': 20})
            items = data.get('data', {}).get('items', [])
            return {'list': self._parse_video_items(items)}
        except:
            return {'list': []}

    def categoryContent(self, cid, pg, filter, ext):
        page = int(pg) if pg else 1
        cid = str(cid)

        if cid == 'short-dramas':
            size = 12
            params = {'productId': 1, 'sortBy': 'heat', 'page': page, 'size': size}
            try:
                data = self._fetch_api('/short-dramas', params=params)
                d = data.get('data', {})
                items = d.get('items', [])
                total = d.get('total', 0)
                pagecount = d.get('totalPages', (total + size - 1) // size if total > 0 else 1)
                return {
                    'list': self._parse_short_drama_items(items),
                    'page': page,
                    'pagecount': pagecount,
                    'limit': size,
                    'total': total
                }
            except:
                return {'list': [], 'page': page, 'pagecount': 1, 'limit': size, 'total': 0}

        size = 20
        params = {'page': page, 'size': size, 'categoryId': cid}

        if isinstance(ext, dict):
            sort_by = ext.get('sortBy', '')
            time_range = ext.get('timeRange', '')
            min_duration = ext.get('minDuration', '')
            if sort_by:
                params['sortBy'] = sort_by
            if time_range:
                params['timeRange'] = time_range
            if min_duration:
                params['minDuration'] = min_duration

        try:
            data = self._fetch_api('/videos', params=params)
            d = data.get('data', {})
            items = d.get('items', [])
            total = d.get('total', 0)
            pagecount = (total + size - 1) // size if total > 0 else 1

            return {
                'list': self._parse_video_items(items),
                'page': page,
                'pagecount': pagecount,
                'limit': size,
                'total': total
            }
        except:
            return {
                'list': [],
                'page': page,
                'pagecount': 1,
                'limit': size,
                'total': 0
            }

    def detailContent(self, ids):
        vid = ids[0]

        if vid.startswith('sd_'):
            return self._detail_short_drama(vid)

        try:
            data = self._fetch_api(f'/videos/{vid}')
            item = data.get('data', {})
        except:
            return {'list': []}

        vod = {}
        vod["vod_id"] = vid
        vod["vod_name"] = item.get('title', '')
        vod["vod_pic"] = self._build_image_url(item.get('coverUrl', ''))

        published = item.get('publishedAt', '')
        if published:
            year_m = re.match(r'(\d{4})', published)
            if year_m:
                vod["vod_year"] = year_m.group(1)

        vod["type_name"] = item.get('categoryName', '')

        author = item.get('authorName', '')
        if author:
            vod["vod_actor"] = author

        desc = item.get('description', '')
        if desc:
            vod["vod_content"] = desc

        dur = item.get('durationSec', 0)
        if dur and dur > 0:
            mins = dur // 60
            secs = dur % 60
            vod["vod_remarks"] = f'{mins:02d}:{secs:02d}'

        video_url = item.get('videoUrl', '')
        if video_url:
            m3u8_url = self._build_m3u8_proxy_url(video_url)
            if m3u8_url:
                vod["vod_play_from"] = '正片'
                vod["vod_play_url"] = f'正片${m3u8_url}'

        return {'list': [vod]}

    def _detail_short_drama(self, vid):
        sd_id = vid[3:]
        try:
            data = self._fetch_api(f'/short-dramas/{sd_id}', params={'productId': 1})
            item = data.get('data', {})
        except:
            return {'list': []}

        vod = {}
        vod["vod_id"] = vid
        vod["vod_name"] = item.get('title', '')
        vod["vod_pic"] = self._build_image_url(item.get('coverUrl', ''))

        published = item.get('publishedAt', '')
        if published:
            year_m = re.match(r'(\d{4})', published)
            if year_m:
                vod["vod_year"] = year_m.group(1)

        vod["type_name"] = 'AI短剧'

        desc = item.get('description', '')
        if desc:
            vod["vod_content"] = desc

        ep_count = item.get('episodeCount', 0)
        if ep_count:
            vod["vod_remarks"] = f'{ep_count}集'

        episodes = item.get('episodes', [])
        play_list = []
        for ep in episodes:
            ep_no = ep.get('episodeNo', '')
            ep_title = f"第{ep_no}集"
            ep_url = self._build_m3u8_proxy_url(ep.get('videoUrl', ''))
            if ep_url:
                play_list.append(f'{ep_title}${ep_url}')

        if play_list:
            vod["vod_play_from"] = '正片'
            vod["vod_play_url"] = '#'.join(play_list)

        return {'list': [vod]}

    def playerContent(self, flag, id, vipFlags):
        try:
            if id.startswith('http') and '/m3u8/proxy' in id:
                return {"parse": 0, "playUrl": "", "url": id, "header": json.dumps(self._req_headers())}

            if not id.startswith('http'):
                proxy_url = self._build_m3u8_proxy_url(id)
                if proxy_url:
                    return {"parse": 0, "playUrl": "", "url": proxy_url, "header": json.dumps(self._req_headers())}

            play_url = id if id.startswith(('http://', 'https://')) else urljoin(self._domain(), id)
            return {"parse": 1, "playUrl": "", "url": play_url, "header": json.dumps(self._req_headers())}
        except Exception as e:
            print(f"player error: {e}")
            return {"parse": 1, "playUrl": "", "url": id, "header": json.dumps(self._req_headers())}

    def searchContent(self, key, quick, page='1'):
        page = int(page) if page else 1
        size = 20

        params = {'page': page, 'size': size, 'keyword': key}

        try:
            data = self._fetch_api('/videos', params=params)
            d = data.get('data', {})
            items = d.get('items', [])
            total = d.get('total', 0)
            pagecount = (total + size - 1) // size if total > 0 else 1

            return {
                'list': self._parse_video_items(items),
                'page': page,
                'pagecount': pagecount,
                'limit': size,
                'total': total
            }
        except:
            return {
                'list': [],
                'page': page,
                'pagecount': 1,
                'limit': size,
                'total': 0
            }