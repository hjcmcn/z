# -*- coding: utf-8 -*-
# by @PyramidStore AutoGen
import re
import sys
sys.path.append('..')
import json
import time
import random
import hashlib
import requests as _req
from base.spider import Spider
from urllib.parse import quote, urlencode, unquote


class Spider(Spider):

    LANDING_URL = 'https://dyrs.net'
    HOSTS_API = 'https://dyrshd.net/api/videox/least'

    UA_LIST = [
        'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1',
        'Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Mobile Safari/537.36',
        'Mozilla/5.0 (iPad; CPU OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0',
    ]

    CATEGORIES = [
        ('dianying', '电影'),
        ('dianshiju', '电视剧'),
        ('zongyi', '综艺'),
        ('dongman', '动漫'),
        ('duanju', '短剧'),
    ]

    CLASS_LIST = ['剧情', '喜剧', '动作', '爱情', '惊悚', '犯罪', '院线', '悬疑', '恐怖', '冒险', '奇幻', '科幻', '家庭', '战争', '古装', '历史', '传记', '武侠', '动画', '音乐']
    AREA_LIST = ['美国', '内地', '中国香港', '日本', '英国', '法国', '韩国', '加拿大', '德国', '中国台湾', '印度', '意大利', '其它地区', '西班牙', '澳大利亚', '泰国', '俄罗斯', '比利时', '丹麦', '墨西哥']
    YEAR_LIST = ['2026', '2025', '2024', '2023', '2022', '2021', '2020', '2019', '2018', '2017', '2016', '2015', '2014', '2013', '2012', '2011', '2010']

    def init(self, extend=""):
        self._host = getattr(self, '_host', None) or self._resolve_host()
        self._vod_name = ''
        self._last_fetch = 0
        self._sion_id = ''
        self._session = _req.Session()
        self._ua = random.choice(self.UA_LIST)
        self._session.headers.update({
            'User-Agent': self._ua,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
        })
        self._session.verify = False
        # Force fresh session to avoid stale sion_id causing 429
        self._ensure_session()

    def getName(self):
        return '电影人生'

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return True

    def destroy(self):
        pass

    def _resolve_host(self):
        try:
            r = _req.get(self.HOSTS_API, headers={'User-Agent': random.choice(self.UA_LIST)}, timeout=10, verify=False)
            data = r.json()
            urls = data.get('urls', [])
            for url in urls[:10]:
                try:
                    host = url.rstrip('/')
                    r2 = _req.get(host + '/dianying.html?page=1', headers={'User-Agent': random.choice(self.UA_LIST)}, timeout=5, verify=False)
                    if r2.status_code == 200 and len(r2.text) > 100000 and re.search(r'data-url="[^"]+"', r2.text):
                        return host
                except:
                    continue
        except:
            pass
        return 'https://dyrs3.vip'

    def _switch_host(self):
        try:
            r = _req.get(self.HOSTS_API, headers={'User-Agent': random.choice(self.UA_LIST)}, timeout=10, verify=False)
            data = r.json()
            urls = data.get('urls', [])
            for url in urls[:10]:
                try:
                    host = url.rstrip('/')
                    if host == self._host:
                        continue
                    r2 = _req.get(host + '/', headers={'User-Agent': random.choice(self.UA_LIST)}, timeout=5, verify=False)
                    if r2.status_code == 200:
                        self._host = host
                        self._sion_id = ''
                        self._session.cookies.clear()
                        self._ensure_session()
                        return True
                except:
                    continue
        except:
            pass
        return False

    def _ensure_session(self):
        if not self._sion_id:
            try:
                r = self._session.get(f'{self._host}/', timeout=10)
                self._sion_id = self._session.cookies.get('sion_id', '')
            except:
                pass

    def _solve_pow(self, html):
        hash_m = re.search(r"var\s+hash\s*=\s*'([^']+)'", html)
        target_m = re.search(r"var\s+target\s*=\s*'([^']+)'", html)
        if not hash_m or not target_m:
            return None
        h, target = hash_m.group(1), target_m.group(1)
        for i in range(10000000):
            if hashlib.sha1((h + str(i)).encode()).hexdigest() == target:
                return i
        return None

    def _is_pow_page(self, text):
        return 'passChallenge' in text and 'var hash' in text and 'var target' in text

    def _try_pow(self, r, url):
        if self._is_pow_page(r.text):
            attack_key = self._solve_pow(r.text)
            if attack_key is not None:
                sep = '&' if '?' in url else '?'
                pow_url = f'{url}{sep}attack_key={attack_key}'
                time.sleep(1)
                r2 = self._session.get(pow_url, timeout=15)
                r2.encoding = 'utf-8'
                if r2.status_code == 200 and len(r2.text) > 1000 and not self._is_pow_page(r2.text):
                    return r2.text
        return None

    def _fetch(self, url, retries=3):
        self._ensure_session()
        if self._sion_id and 'sion_id=' not in url:
            sep = '&' if '?' in url else '?'
            url = f'{url}{sep}sion_id={self._sion_id}'
        for attempt in range(retries):
            try:
                elapsed = time.time() - self._last_fetch
                if elapsed < 2.0:
                    time.sleep(2.0 - elapsed)
                r = self._session.get(url, timeout=15)
                self._last_fetch = time.time()
                r.encoding = 'utf-8'
                if r.status_code == 200 and len(r.text) > 1000:
                    pow_result = self._try_pow(r, url)
                    if pow_result:
                        return pow_result
                    if not self._is_pow_page(r.text):
                        return r.text
                if r.status_code in (429, 200) and self._is_pow_page(r.text):
                    pow_result = self._try_pow(r, url)
                    if pow_result:
                        return pow_result
                if r.status_code == 429:
                    time.sleep(3 * (attempt + 1))
                    self._sion_id = ''
                    self._session.cookies.clear()
                    self._session.headers['User-Agent'] = random.choice(self.UA_LIST)
                    self._ensure_session()
                    if self._sion_id:
                        url = re.sub(r'sion_id=[^&]*', f'sion_id={self._sion_id}', url) if 'sion_id=' in url else f'{url}&sion_id={self._sion_id}'
                    continue
            except (_req.exceptions.ConnectionError, _req.exceptions.Timeout):
                if attempt < retries - 1:
                    time.sleep(2)
                    self._switch_host()
                    if self._sion_id:
                        url = re.sub(r'sion_id=[^&]*', f'sion_id={self._sion_id}', url) if 'sion_id=' in url else f'{url}&sion_id={self._sion_id}'
                    continue
            except:
                pass
            if attempt < retries - 1:
                time.sleep(3)
        return None

    def _parse_list(self, html):
        videos = []
        if not html:
            return videos
        urls = re.findall(r'data-url="([^"]+)"', html)
        titles = re.findall(r'<a\s[^>]*?title="([^"]*)"[^>]*?data-url=', html)
        pics = re.findall(r'data-src="([^"]+)"', html)
        for i, data_url in enumerate(urls):
            title = titles[i] if i < len(titles) else ''
            pic = pics[i] if i < len(pics) else ''
            if pic and not pic.startswith('http'):
                pic = f'{self._host}{pic}'
            remark = ''
            year = ''
            idx = html.find(f'data-url="{data_url}"')
            if idx > 0:
                after = html[idx:idx+1500]
                # rounded shadow-sm = remark (清晰度/集数)
                rem_m = re.search(r'rounded shadow-sm[^>]*>\s*([^<]+)', after)
                if rem_m:
                    remark = rem_m.group(1).strip()
                # <span>年份</span> = year
                year_m = re.search(r'<span>\s*(\d{4})\s*</span>', after)
                if year_m:
                    year = year_m.group(1)
            videos.append({
                'vod_id': data_url if data_url.startswith('/') else f'/{data_url}',
                'vod_name': title,
                'vod_pic': pic,
                'vod_remarks': remark,
                'vod_year': year,
            })
        return videos

    def _parse_episodes(self, html, detail_base):
        sources = {}
        from urllib.parse import unquote, quote

        # Find source selector links: href="...origin=xxx..." (no p= param, not api/m3u8, not download)
        source_map = {}
        for m in re.finditer(r'href="([^"]*origin=[^"]*)"', html):
            href = m.group(1).replace('&amp;', '&')
            if 'p=' in href or 'api/m3u8' in href or 'download' in href or 'dianying.html' in href:
                continue
            origin_m = re.search(r'origin=([^&"]+)', href)
            if origin_m:
                origin_val = unquote(origin_m.group(1))
                if origin_val and origin_val not in source_map:
                    source_map[origin_val] = href

        # Find episode links: href="...origin=xxx&p=N..."
        ep_links = re.findall(r'href="([^"]*\?origin=[^"&]*&(?:amp;)?p=\d+[^"]*)"', html)
        ep_links = list(dict.fromkeys(ep_links))

        # Group episodes by origin from current page
        for link in ep_links:
            link = link.replace('&amp;', '&')
            origin_m = re.search(r'origin=([^&]+)', link)
            if origin_m:
                origin = unquote(origin_m.group(1))
                if origin not in sources:
                    sources[origin] = []
                sources[origin].append(link)

        # For sources not in current page, visit their selector page
        for origin_val in source_map:
            if origin_val not in sources:
                source_url = f'{self._host}{detail_base}?origin={quote(origin_val)}'
                try:
                    src_html = self._fetch(source_url, retries=2)
                    if src_html:
                        src_eps = re.findall(r'href="([^"]*\?origin=[^"&]*&(?:amp;)?p=\d+[^"]*)"', src_html)
                        src_eps = list(dict.fromkeys(src_eps))
                        if src_eps:
                            sources[origin_val] = [e.replace('&amp;', '&') for e in src_eps]
                except Exception:
                    pass
                time.sleep(1)

        return sources

    def homeContent(self, filter):
        result = {'class': [], 'list': []}
        try:
            html = self._fetch(f'{self._host}/')
            if html:
                result['class'] = [{'type_id': cid, 'type_name': cn} for cid, cn in self.CATEGORIES]
                result['list'] = self._parse_list(html)
                if filter:
                    result['filters'] = {
                        cid: [
                            {'key': 'class', 'name': '类型', 'value': [{'n': '全部', 'v': ''}] + [{'n': c, 'v': c} for c in self.CLASS_LIST]},
                            {'key': 'area', 'name': '地区', 'value': [{'n': '全部', 'v': ''}] + [{'n': a, 'v': a} for a in self.AREA_LIST]},
                            {'key': 'year', 'name': '年份', 'value': [{'n': '全部', 'v': ''}] + [{'n': y, 'v': y} for y in self.YEAR_LIST]},
                        ]
                        for cid, cn in self.CATEGORIES
                    }
        except:
            pass
        return result

    def homeVideoContent(self):
        try:
            html = self._fetch(f'{self._host}/')
            if html:
                return {'list': self._parse_list(html)}
        except:
            pass
        return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        result = {'list': [], 'page': int(pg), 'pagecount': 9999, 'limit': 90, 'total': 0}
        try:
            pg = int(pg)
            params = {'page': pg}
            if extend:
                for key in ('area', 'class', 'year'):
                    if extend.get(key):
                        params[key] = extend[key]
            url = f'{self._host}/{tid}.html?{urlencode(params)}'
            html = self._fetch(url)
            if html:
                items = self._parse_list(html)
                result['list'] = items
                result['limit'] = max(len(items), 1)
                result['total'] = len(items)
        except:
            pass
        return result

    def detailContent(self, ids):
        result = {'list': []}
        try:
            url = ids[0]
            if not url.startswith('http'):
                url = f'{self._host}{url}'
            html = self._fetch(url)
            if not html:
                return result

            vod_name = ''
            m = re.search(r'<title>([^<]+)', html)
            if m:
                vod_name = m.group(1).split('-')[0].strip()
                vod_name = re.sub(r'[\u300a\u300b\u3008\u3009\u300c\u300d\u300e\u300f\uff08\uff09\(\)\[\]\{\}]', '', vod_name)
                vod_name = re.sub(r'(在线观看|在线播放|免费播放|免费观看|高清播放|高清在线|完整版|全集|电视剧|电影|免费|高清|播放|观看|全集免费|在线|影院)$', '', vod_name)
                vod_name = re.sub(r'[-\s]+$', '', vod_name).strip()

            vod_pic = ''
            m = re.search(r'imgurl\s*[=:]\s*[\'"]([^\'"]+)[\'"]', html)
            if m:
                vod_pic = m.group(1)
                if not vod_pic.startswith('http'):
                    vod_pic = f'{self._host}{vod_pic}'

            vod_content = ''
            m = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]*)"', html)
            if m:
                vod_content = m.group(1).strip()

            vod_year = ''
            m = re.search(r'year\s*[=:]\s*[\'"](\d{4})[\'"]', html)
            if m:
                vod_year = m.group(1)

            vod_actor = ''
            m = re.search(r'"actor"\s*:\s*\[(.*?)\]', html)
            if m:
                actors = re.findall(r'"name"\s*:\s*"([^"]+)"', m.group(1))
                vod_actor = ','.join(actors[:10])

            vod_director = ''
            m = re.search(r'"director"\s*:\s*\{[^}]*"name"\s*:\s*"([^"]*)"', html)
            if m:
                vod_director = m.group(1)

            vod = {
                'vod_id': ids[0],
                'vod_name': vod_name,
                'vod_pic': vod_pic,
                'vod_content': vod_content,
                'vod_year': vod_year,
                'vod_actor': vod_actor,
                'vod_director': vod_director,
                'vod_play_from': '',
                'vod_play_url': '',
            }

            play_sources = {}

            # Method 1: Parse episode links from detail page
            detail_base = re.search(r'(\/[^?]+\.html)', ids[0])
            if detail_base:
                episodes = self._parse_episodes(html, detail_base.group(1))
                if episodes:
                    play_sources = episodes

            # Method 2: Try xg_video_player_doc.aa (single episode)
            if not play_sources:
                aa_m = re.search(r'xg_video_player_doc\s*=\s*\{[^}]*aa:\s*JSON\.parse\([\'"](\{[^}]+\})[\'"]\)', html, re.DOTALL)
                if aa_m:
                    raw = aa_m.group(1).replace('\\u0022', '"').replace('\\u0026', '&')
                    raw = re.sub(r'\\(.)', r'\1', raw)
                    try:
                        aa = json.loads(raw)
                        origin = aa.get('origin', '默认')
                        play_url = aa.get('url', '')
                        if play_url:
                            if not play_url.startswith('http'):
                                play_url = f'{self._host}{play_url}'
                            play_sources[origin] = [play_url]
                    except:
                        pass

            # Method 3: Try videoid fallback
            if not play_sources:
                m = re.search(r'videoid\s*[=:]\s*[\'"]([a-f0-9]+)[\'"]', html)
                if m:
                    vid = m.group(1)
                    play_sources['超级线路'] = [f'{self._host}/api/m3u8?origin=%E8%B6%85%E7%BA%A7%E7%BA%BF%E8%B7%AF&url={vid}']

            if play_sources:
                play_from = []
                play_urls = []
                for src_name, src_urls in play_sources.items():
                    play_from.append(src_name)
                    eps = []
                    for i, u in enumerate(src_urls, 1):
                        full_url = u if u.startswith('http') else f'{self._host}{u}'
                        eps.append(f'第{i}集${full_url}')
                    play_urls.append('#'.join(eps))
                vod['vod_play_from'] = '$$$'.join(play_from)
                vod['vod_play_url'] = '$$$'.join(play_urls)

            self._vod_name = vod_name
            result['list'] = [vod]
        except:
            pass
        return result

    def searchContent(self, key, quick, pg="1"):
        result = {'list': [], 'page': int(pg), 'pagecount': 1, 'limit': 90, 'total': 0}
        try:
            html = self._fetch(f'{self._host}/search.html?keyword={quote(key)}')
            if html:
                result['list'] = self._parse_list(html)
                if result['list']:
                    result['pagecount'] = 9999
                    result['total'] = 999999
        except:
            pass
        return result

    def playerContent(self, flag, id, vipFlags):
        try:
            url = id
            if not url.startswith('http'):
                url = f'{self._host}{url}'
            # For episode URLs with origin, fetch the page to get m3u8
            if 'origin=' in url and 'api/m3u8' not in url:
                html = self._fetch(url, retries=3)
                if html:
                    m3u8_url = self._extract_m3u8(html)
                    if m3u8_url:
                        danmaku = self._build_danmaku(url)
                        return {'parse': 0, 'url': m3u8_url, 'header': {'Referer': f'{self._host}/'}, 'danmaku': danmaku}
                # Retry with fresh session
                self._sion_id = ''
                self._session.cookies.clear()
                self._ensure_session()
                if self._sion_id:
                    url = re.sub(r'sion_id=[^&]*', f'sion_id={self._sion_id}', url) if 'sion_id=' in url else f'{url}&sion_id={self._sion_id}'
                    html = self._fetch(url, retries=2)
                    if html:
                        m3u8_url = self._extract_m3u8(html)
                        if m3u8_url:
                            danmaku = self._build_danmaku(url)
                            return {'parse': 0, 'url': m3u8_url, 'header': {'Referer': f'{self._host}/'}, 'danmaku': danmaku}
            # Direct m3u8 URL
            html = self._fetch(url, retries=2)
            if html and ('#EXTM3U' in html or 'mpegurl' in html.lower()):
                danmaku = self._build_danmaku(url)
                return {'parse': 0, 'url': url, 'header': {'Referer': f'{self._host}/'}, 'danmaku': danmaku}
        except:
            pass
        return {'parse': 1, 'url': id, 'header': {'Referer': f'{self._host}/'}, 'danmaku': ''}

    def _extract_m3u8(self, html):
        aa_m = re.search(r'xg_video_player_doc\s*=\s*\{[^}]*aa:\s*JSON\.parse\([\'"](\{[^}]+\})[\'"]\)', html, re.DOTALL)
        if aa_m:
            raw = aa_m.group(1).replace('\\u0022', '"').replace('\\u0026', '&')
            raw = re.sub(r'\\(.)', r'\1', raw)
            try:
                aa = json.loads(raw)
                m3u8_url = aa.get('url', '')
                if m3u8_url:
                    if not m3u8_url.startswith('http'):
                        m3u8_url = f'{self._host}{m3u8_url}'
                    return m3u8_url
            except:
                pass
        return None

    def _build_danmaku(self, url):
        if not self._vod_name:
            return ''
        name = self._vod_name
        name = re.sub(r'[\u300a\u300b\u3008\u3009\u300c\u300d\u300e\u300f\uff08\uff09\(\)\[\]\{\}]', '', name)
        name = re.sub(r'(在线观看|在线播放|免费播放|免费观看|高清播放|高清在线|完整版|全集|电视剧|电影|免费|高清|完整版|播放|观看|全集免费|在线|影院)$', '', name)
        name = re.sub(r'[-\s]+$', '', name).strip()
        if not name:
            return ''
        ep_name = ''
        if 'p=' in url:
            p_m = re.search(r'p=(\d+)', url)
            if p_m:
                ep_name = str(int(p_m.group(1)) + 1)
        return f'http://127.0.0.1:9978/proxy?do=appdanmu&vodName={quote(name)}&vodIndex={ep_name}'

    def localProxy(self, param):
        return [200, {}, '']
