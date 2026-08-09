# -*- coding: utf-8 -*-
import re
from urllib.parse import quote
from base.spider import Spider


class Spider(Spider):

    host = 'https://www.stonelodgeacademy.com'

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    }

    def init(self, extend=""):
        pass

    def getName(self):
        return '达达兔影院'

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return True

    def destroy(self):
        pass

    def homeContent(self, filter):
        result = {'class': [], 'list': []}
        try:
            html = self._fetch(self.host + '/')
            if not html:
                return result
            for m in re.finditer(r'<nav[^>]*class="[^"]*nav-menu[^"]*"[^>]*>(.*?)</nav>', html, re.DOTALL):
                for a in re.finditer(r'<a[^>]*href="/(\w+)/?"[^>]*class="[^"]*nav-item[^"]*"[^>]*>([^<]*)</a>', m.group(1)):
                    result['class'].append({'type_id': a.group(1), 'type_name': a.group(2).strip()})
            result['list'] = self._parse_list(html)
        except Exception as e:
            print(f'homeContent error: {e}')
        return result

    def homeVideoContent(self):
        try:
            html = self._fetch(self.host + '/')
            if html:
                return {'list': self._parse_list(html)}
        except Exception as e:
            print(f'homeVideoContent error: {e}')
        return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        result = {'list': [], 'page': pg, 'pagecount': 1, 'limit': 90, 'total': 0}
        try:
            pg = int(pg)
            url = f'{self.host}/{tid}/'
            if pg > 1:
                url += f'?page={pg}'
            html = self._fetch(url)
            if html:
                result['list'] = self._parse_list(html)
                result['page'] = str(pg)
                result['pagecount'] = 9999
                result['total'] = 999999
        except Exception as e:
            print(f'categoryContent error: {e}')
        return result

    def detailContent(self, ids):
        result = {'list': []}
        try:
            url = ids[0]
            if not url.startswith('http'):
                url = self.host + url
            html = self._fetch(url)
            if not html:
                return result
            vod = {
                'vod_id': ids[0],
                'vod_name': '',
                'vod_pic': '',
                'vod_content': '',
                'vod_year': '',
                'vod_area': '',
                'vod_director': '',
                'vod_actor': '',
                'vod_play_from': '默认',
                'vod_play_url': '',
            }
            m = re.search(r'<h1[^>]*>([^<]*)</h1>', html)
            if m:
                vod['vod_name'] = m.group(1).strip()
            m = re.search(r'<div[^>]*class="[^"]*detail-poster[^"]*"[^>]*>.*?<img[^>]*src="([^"]*)"', html, re.DOTALL)
            if m:
                vod['vod_pic'] = m.group(1)
            else:
                m = re.search(r'<meta\s+property="og:image"\s+content="([^"]*)"', html)
                if m:
                    vod['vod_pic'] = m.group(1)
            m = re.search(r'<p[^>]*class="[^"]*detail-desc[^"]*"[^>]*>([^<]*)</p>', html)
            if m:
                vod['vod_content'] = m.group(1).strip()
            m = re.search(r'导演[：:]\s*([^<\n]*)', html)
            if m:
                vod['vod_director'] = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            m = re.search(r'主演[：:]\s*([^<\n]*)', html)
            if m:
                vod['vod_actor'] = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            m = re.search(r'年份[：:]\s*<a[^>]*>([^<]*)</a>', html)
            if m:
                vod['vod_year'] = m.group(1).strip()
            m = re.search(r'地区[：:]\s*<a[^>]*>([^<]*)</a>', html)
            if m:
                vod['vod_area'] = m.group(1).strip()
            play_from = []
            play_url = []
            for src_m in re.finditer(r'<div[^>]*class="[^"]*play-source[^"]*"[^>]*>(.*?)</div>\s*</div>', html, re.DOTALL):
                block = src_m.group(1)
                name_m = re.search(r'<div[^>]*class="[^"]*play-source-name[^"]*"[^>]*>([^<]*)</div>', block)
                src_name = name_m.group(1).strip() if name_m else '默认'
                eps = []
                for ep_m in re.finditer(r'<a[^>]*href="(/[^"]*)"[^>]*class="[^"]*play-item[^"]*"[^>]*>([^<]*)</a>', block):
                    eps.append(f'{ep_m.group(2).strip()}${ep_m.group(1)}')
                if eps:
                    play_from.append(src_name)
                    play_url.append('#'.join(eps))
            if play_from:
                vod['vod_play_from'] = '$$$'.join(play_from)
                vod['vod_play_url'] = '$$$'.join(play_url)
                ep_map = {}
                for src_idx, url_str in enumerate(play_url):
                    for ep in url_str.split('#'):
                        if '$' in ep:
                            ep_name, ep_url = ep.split('$', 1)
                            if ep_url:
                                ep_map[ep_url] = ep_name
                self._vod_episode_map = ep_map
            self._vod_name = vod['vod_name']
            result['list'] = [vod]
        except Exception as e:
            print(f'detailContent error: {e}')
        return result

    def searchContent(self, key, quick, pg="1"):
        result = {'list': [], 'page': pg, 'pagecount': 1, 'limit': 90, 'total': 0}
        try:
            html = self._fetch(f'{self.host}/search/?keyword={quote(key)}')
            if html:
                result['list'] = self._parse_list(html)
                result['pagecount'] = 9999
                result['total'] = 999999
        except Exception as e:
            print(f'searchContent error: {e}')
        return result

    def playerContent(self, flag, id, vipFlags):
        try:
            url = id
            if not url.startswith('http'):
                url = self.host + url
            html = self._fetch(url)
            if html:
                m = re.search(r'<meta\s+property="og:video"\s+content="([^"]*)"', html)
                if m:
                    vod_name = getattr(self, '_vod_name', '')
                    ep_map = getattr(self, '_vod_episode_map', {})
                    ep_name = ep_map.get(id, '')
                    danmaku = self._build_danmaku_url(vod_name, ep_name)
                    return {'parse': 0, 'url': m.group(1), 'header': self.headers, 'danmaku': danmaku}
                m = re.search(r'<source\s+src="([^"]*)"', html)
                if m:
                    vod_name = getattr(self, '_vod_name', '')
                    ep_map = getattr(self, '_vod_episode_map', {})
                    ep_name = ep_map.get(id, '')
                    danmaku = self._build_danmaku_url(vod_name, ep_name)
                    return {'parse': 0, 'url': m.group(1), 'header': self.headers, 'danmaku': danmaku}
        except Exception as e:
            print(f'playerContent error: {e}')
        return {'parse': 1, 'url': id, 'header': self.headers}

    def localProxy(self, param):
        return [200, {}, ""]

    def _parse_list(self, html):
        videos = []
        if not html:
            return videos
        for m in re.finditer(
            r'<div[^>]*class="[^"]*\bvideo-card\b[^"]*"[^>]*>'
            r'.*?<a[^>]*href="(/[^"]*)"[^>]*class="[^"]*\bvideo-thumb\b[^"]*"[^>]*>',
            html, re.DOTALL
        ):
            block = html[m.start():m.start() + 600]
            href = m.group(1)
            pic = ''
            pic_m = re.search(r'data-src="([^"]*)"', block)
            if pic_m:
                pic = pic_m.group(1)
            else:
                pic_m = re.search(r'src="([^"]*)"', block)
                if pic_m:
                    pic = pic_m.group(1)
            name = ''
            alt_m = re.search(r'alt="([^"]*)"', block)
            if alt_m:
                name = alt_m.group(1)
            if not name:
                title_m = re.search(r'<h[23][^>]*class="[^"]*\bvideo-title\b[^"]*"[^>]*>([^<]*)</h[23]>', block)
                if title_m:
                    name = title_m.group(1).strip()
            remark = ''
            ep = re.search(r'<span[^>]*class="[^"]*\bvideo-episode\b[^"]*"[^>]*>([^<]*)</span>', block)
            if ep:
                remark = ep.group(1).strip()
            else:
                tag = re.search(r'<span[^>]*class="[^"]*\bvideo-tag\b[^"]*"[^>]*>([^<]*)</span>', block)
                if tag:
                    remark = tag.group(1).strip()
            year = ''
            meta_m = re.search(r'<p[^>]*class="[^"]*\bvideo-meta\b[^"]*"[^>]*>([^<]*)</p>', block)
            if meta_m:
                ym = re.search(r'(\d{4})', meta_m.group(1))
                if ym:
                    year = ym.group(1)
            videos.append({
                'vod_id': href,
                'vod_name': name,
                'vod_pic': pic if pic.startswith('http') else '',
                'vod_remarks': remark,
                'vod_year': year,
            })
        return videos

    def _fetch(self, url):
        import time
        self._rate_limit()
        for i in range(3):
            try:
                r = self.fetch(url, headers=self.headers, timeout=15)
                if r.status_code == 200 and len(r.text) > 100:
                    return r.text
                time.sleep(2)
            except:
                time.sleep(2)
        return None

    def _rate_limit(self):
        import time
        now = time.time()
        gap = now - getattr(self, '_last_request_time', 0)
        if gap < 1.5:
            time.sleep(1.5 - gap)
        self._last_request_time = time.time()

    def _build_danmaku_url(self, vod_name='', ep_name=''):
        idx = self._parse_episode_index(ep_name)
        params = []
        if vod_name:
            params.append(f'vodName={quote(vod_name)}')
        params.append(f'vodIndex={idx}')
        q = '&'.join(params)
        return f'http://127.0.0.1:9978/proxy?do=appdanmu&{q}'

    @staticmethod
    def _parse_episode_index(name):
        if not name:
            return 0
        s = str(name).strip()
        m = re.search(r'第\s*((?:\d+)|(?:[一二三四五六七八九十百零]+))\s*[集話话章部期]', s)
        if m:
            ns = m.group(1)
            if ns.isdigit():
                return int(ns)
            return Spider._cn_num(ns)
        m = re.search(r'(?:EP|ep|第)\s*(\d+)', s)
        if m:
            n = int(m.group(1))
            return n if n > 0 else 0
        m = re.search(r'(\d+)', s)
        if m:
            n = int(m.group(1))
            return n if n > 0 else 0
        return 0

    @staticmethod
    def _cn_num(s):
        cm = {'零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
              '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
        t, tmp = 0, 0
        for ch in s:
            if ch == '零':
                continue
            if ch == '十':
                t += (tmp or 1) * 10
                tmp = 0
            elif ch == '百':
                t += (tmp or 1) * 100
                tmp = 0
            elif ch == '千':
                t += (tmp or 1) * 1000
                tmp = 0
            else:
                tmp = cm.get(ch, 0)
        t += tmp
        return t if t else 0
