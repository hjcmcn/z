# -*- coding: utf-8 -*-
import math
import os
import sys
from urllib.parse import urljoin

import requests


HERE = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(HERE)
if PARENT not in sys.path:
    sys.path.insert(0, PARENT)
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        pass


HOST = 'https://m.xgshort.com'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
      'AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36')
DEFAULT_IDS = '0,0,0,0,0,0,0'


class Spider(BaseSpider):
    def init(self, extend=''):
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers.update({
            'User-Agent': UA,
            'Accept': 'application/json',
            'Referer': HOST + '/',
        })
        self._token = ''
        self._guest_token = ''
        self._login()

    def getName(self):
        return '🍉西瓜｜[短剧]'

    def destroy(self):
        if getattr(self, 'session', None):
            self.session.close()

    def homeContent(self, filter=False):
        payload = self._api('GET', '/api/home/categories', auth=False)
        categories = payload if isinstance(payload, list) else payload.get('data', [])
        return {'class': [
            {'type_name': item.get('name', ''), 'type_id': str(item.get('id'))}
            for item in categories
            if item.get('isEnabled', True) and item.get('id') is not None
        ]}

    def homeVideoContent(self):
        return self.categoryContent('1', 1)

    def categoryContent(self, tid='', pg=1, filter=False, extend=None):
        page = max(self._int(pg, 1), 1)
        params = {
            'channeid': self._int(tid, 1),
            'ids': (extend or {}).get('ids', DEFAULT_IDS)
                    if isinstance(extend, dict) else DEFAULT_IDS,
            'page': page,
            'size': 20,
        }
        data = self._api('GET', '/api/list/getfiltersdata', params=params)
        data = data.get('data', data)
        values = [self._video(item) for item in data.get('list', [])]
        size = self._int(data.get('size'), len(values) or 20)
        total = self._int(data.get('total'), len(values))
        pagecount = max(math.ceil(total / size) if size else page, page)
        if data.get('hasMore'):
            pagecount = max(pagecount, page + 1)
        return {'list': values, 'page': page, 'pagecount': pagecount,
                'limit': len(values), 'total': total}

    def detailContent(self, ids=''):
        value = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
        series_id = str(value or '').strip()
        if not series_id:
            return {'list': []}
        data = self._api('GET', '/api/video/episodes',
                         params={'seriesShortId': series_id, 'size': 500})
        data = data.get('data', data)
        info = data.get('seriesInfo') or {}
        episodes = []
        for item in data.get('list', []):
            short_id = str(item.get('shortId') or '').strip()
            access_key = str(item.get('episodeAccessKey') or '').strip()
            if not access_key and item.get('urls'):
                access_key = str(item['urls'][0].get('accessKey') or '').strip()
            if short_id and access_key:
                token = 'xg1:{}:{}:{}'.format(series_id, short_id, access_key)
                episodes.append('{}${}'.format(
                    item.get('episodeTitle') or item.get('title') or short_id,
                    token))
        item = {
            'vod_id': series_id,
            'vod_name': info.get('title') or series_id,
            'vod_pic': info.get('coverUrl') or '',
            'vod_content': info.get('description') or '',
            'vod_play_from': '西瓜线路' if episodes else '',
            'vod_play_url': '#'.join(episodes),
        }
        return {'list': [item] if episodes else []}

    def playerContent(self, flag='', id='', vipFlags=None):
        token = str(id or '').rsplit('$', 1)[-1].strip()
        parts = token.split(':')
        access_key = parts[3] if len(parts) == 4 and parts[0] == 'xg1' else token
        data = self._api('POST', '/api/video/episode-url/query',
                         body={'type': 'episode', 'accessKey': access_key})
        data = data.get('data', data)
        for item in data.get('urls', []):
            media = str(item.get('cdnUrl') or item.get('ossUrl') or '').strip()
            if media:
                return {'parse': 0, 'playUrl': '', 'url': media,
                        'header': {'User-Agent': UA, 'Referer': HOST + '/'}}
        return {'parse': 0, 'playUrl': '', 'url': ''}

    def searchContent(self, key, quick=False, pg='1'):
        page = max(self._int(pg, 1), 1)
        data = self._api('GET', '/api/list/fuzzysearch', params={
            'keyword': str(key or ''), 'page': page, 'size': 20,
        })
        data = data.get('data', data)
        values = [self._video(item) for item in data.get('list', [])]
        size = self._int(data.get('size'), len(values) or 20)
        total = self._int(data.get('total'), len(values))
        return {'list': values, 'page': page,
                'pagecount': max(math.ceil(total / size) if size else page, page),
                'limit': len(values), 'total': total}

    def localProxy(self, param=None):
        return [404, 'text/plain', b'not found']

    def isVideoFormat(self, url):
        value = str(url or '').lower().split('?', 1)[0]
        return value.endswith(('.m3u8', '.mp4'))

    def _login(self):
        try:
            response = self.session.post(
                self._proxy('/api/auth/guest-login'),
                json={'guestToken': self._guest_token},
                timeout=(5, 15),
            )
            if response.status_code != 200:
                return False
            data = response.json()
            self._token = '{} {}'.format(
                data.get('token_type', 'Bearer'), data.get('access_token', '')).strip()
            self._guest_token = data.get('guestToken', self._guest_token)
            if not data.get('access_token'):
                self._token = ''
                return False
            self.session.headers['Authorization'] = self._token
            return True
        except (requests.RequestException, ValueError, TypeError):
            return False

    def _api(self, method, path, params=None, body=None, auth=True):
        if auth and not self._token and not self._login():
            return {}
        try:
            response = self.session.request(
                method, self._proxy(path), params=params, json=body,
                timeout=(5, 20),
            )
            if response.status_code == 401 and auth and self._login():
                response = self.session.request(
                    method, self._proxy(path), params=params, json=body,
                    timeout=(5, 20),
                )
            if response.status_code != 200 and response.status_code != 201:
                return {}
            value = response.json()
            return value if isinstance(value, (dict, list)) else {}
        except (requests.RequestException, ValueError, TypeError):
            return {}

    @staticmethod
    def _proxy(path):
        return urljoin(HOST + '/', path.lstrip('/'))

    @staticmethod
    def _video(item):
        return {
            'vod_id': str(item.get('shortId') or item.get('url') or item.get('id') or ''),
            'vod_name': item.get('title') or '',
            'vod_pic': item.get('coverUrl') or '',
            'vod_remarks': item.get('upStatus') or '',
            'vod_year': str(item.get('createdAt') or '')[:4],
        }

    @staticmethod
    def _int(value, default):
        try:
            return int(str(value))
        except (TypeError, ValueError):
            return default
