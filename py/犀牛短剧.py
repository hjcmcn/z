# -*- coding: utf-8 -*-
# by @PyramidStore AutoGen
import re
import sys
sys.path.append('..')
import json
from base.spider import Spider


class Spider(Spider):

    def init(self, extend=""):
        self.host = 'https://by24h.com'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': 'https://by24h.com/',
        }


    def getName(self):
        return '犀牛短剧'

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return True

    def homeContent(self, filter):
        classes = [
            {'type_id': '1', 'type_name': '重生'},
            {'type_id': '2', 'type_name': '穿越'},
            {'type_id': '3', 'type_name': '爽剧'},
            {'type_id': '4', 'type_name': '言情'},
            {'type_id': '5', 'type_name': '都市'},
            {'type_id': '6', 'type_name': '古装'},
            {'type_id': '7', 'type_name': '悬疑'},
            {'type_id': '8', 'type_name': '剧情'},
        ]
        videos = self._fetch_home_recommend()
        return {"class": classes, "list": videos}

    def _fetch_home_recommend(self):
        videos = []
        try:
            r = self.fetch(self.host, headers=self.headers, timeout=15, verify=False)
            if r.status_code != 200:
                return videos
            items = re.findall(r'<li class="stui-vodlist__item">(.*?)</li>', r.text, re.DOTALL)
            for item in items:
                v = self._parse_list_item(item)
                if v:
                    videos.append(v)
        except Exception:
            pass
        return videos

    def _parse_list_item(self, item):
        href_m = re.search(r'href="(/duanju/\d+\.html)"', item)
        if not href_m:
            return None
        vod_id = href_m.group(1)

        title_m = re.search(r'title="([^"]+)"', item)
        vod_name = title_m.group(1) if title_m else ''

        pic = ''
        pic_m = re.search(r'src="(https?://[^"]+\.(?:jpg|jpeg|png|webp))"', item)
        if pic_m:
            pic = pic_m.group(1)

        remark = ''
        remark_m = re.search(r'pic-text[^>]*>([^<]+)</span>', item)
        if remark_m:
            remark = remark_m.group(1).strip()

        return {
            'vod_id': vod_id,
            'vod_name': vod_name,
            'vod_pic': pic,
            'vod_remarks': remark,
        }

    def homeVideoContent(self):
        return ''

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg)
        videos = []
        try:
            if pg <= 1:
                url = f'{self.host}/dj/{tid}.html'
            else:
                url = f'{self.host}/dj/{tid}-{pg}.html'
            r = self.fetch(url, headers=self.headers, timeout=15, verify=False)
            if r.status_code != 200:
                return {"list": [], "page": pg, "pagecount": 9999, "limit": 90, "total": 0}
            items = re.findall(r'<li class="stui-vodlist__item">(.*?)</li>', r.text, re.DOTALL)
            for item in items:
                v = self._parse_list_item(item)
                if v:
                    videos.append(v)
        except Exception:
            pass
        return {"list": videos, "page": pg, "pagecount": 9999, "limit": 90, "total": 0}

    def detailContent(self, ids):
        vod = {
            'vod_id': '',
            'vod_name': '',
            'vod_pic': '',
            'type_name': '',
            'vod_year': '',
            'vod_area': '',
            'vod_remarks': '',
            'vod_actor': '',
            'vod_director': '',
            'vod_content': '',
            'vod_play_from': '',
            'vod_play_url': '',
        }
        try:
            url = f'{self.host}{ids[0]}'
            r = self.fetch(url, headers=self.headers, timeout=15, verify=False)
            if r.status_code != 200:
                return {"list": [vod]}
            html = r.text

            # OG meta tags
            og = {}
            for m in re.finditer(r'<meta property="og:([^"]+)" content="([^"]*)"', html):
                og[m.group(1)] = m.group(2)

            vod['vod_id'] = ids[0]
            vod['vod_name'] = og.get('title', '')
            vod['vod_pic'] = og.get('image', '')
            vod['vod_area'] = og.get('video:area', '')
            vod['type_name'] = og.get('video:class', '')
            vod['vod_director'] = og.get('video:director', '')
            vod['vod_actor'] = og.get('video:actor', '')

            # Year from data section
            year_m = re.search(r'年份：</span>\s*(\d{4})', html)
            if year_m:
                vod['vod_year'] = year_m.group(1)

            # Parse sources and episodes from mip-vd-tabs
            sources, play_urls = self._parse_sources(html)
            vod['vod_play_from'] = sources
            vod['vod_play_url'] = play_urls

        except Exception:
            pass
        return {"list": [vod]}

    def _parse_sources(self, html):
        tabs_m = re.search(r'<mip-vd-tabs[^>]*>(.*?)</mip-vd-tabs>', html, re.DOTALL)
        if not tabs_m:
            return '', ''
        tabs_html = tabs_m.group(1)

        # Extract source names
        source_names = re.findall(r'<li>([^<]+)</li>', tabs_html)
        # Extract episode lists
        playlist_blocks = re.findall(r'<ul class="stui-content__playlist[^"]*"[^>]*>(.*?)</ul>', tabs_html, re.DOTALL)

        sources = []
        urls_list = []
        for i, name in enumerate(source_names):
            name = name.strip()
            if not name:
                continue
            episodes = []
            if i < len(playlist_blocks):
                eps = re.findall(r'href="(/play/[^"]+\.html)"[^>]*>([^<]*)', playlist_blocks[i])
                for href, ep_name in eps:
                    ep_name = ep_name.strip()
                    if not ep_name:
                        continue
                    episodes.append(f'{ep_name}${self.host}{href}')
            if episodes:
                sources.append(name)
                urls_list.append('#'.join(episodes))

        return '$$$'.join(sources), '$$$'.join(urls_list)

    def searchContent(self, key, quick, pg="1"):
        return {"list": [], "page": pg, "pagecount": 1, "limit": 90, "total": 0}

    def playerContent(self, flag, id, vipFlags):
        result = {"parse": 1, "url": id, "header": self.headers, "danmaku": ""}
        try:
            r = self.fetch(id, headers=self.headers, timeout=15, verify=False)
            if r.status_code != 200:
                return result
            html = r.text

            # Extract m3u8 from mip-iframe src
            iframe_m = re.search(r'mip-iframe[^>]*src="([^"]*)"', html)
            if iframe_m:
                src = iframe_m.group(1)
                url_m = re.search(r'url=(https?://[^"&\s]+)', src)
                if url_m:
                    video_url = url_m.group(1)
                    result['parse'] = 0
                    result['url'] = video_url
                    # Set Referer to CDN origin for CORS
                    cdn_m = re.search(r'(https?://[^/]+)', video_url)
                    if cdn_m:
                        result['header'] = {
                            'User-Agent': self.headers['User-Agent'],
                            'Referer': cdn_m.group(1) + '/',
                            'Accept': '*/*',
                        }

        except Exception:
            pass
        return result

    def localProxy(self, param):
        return [200, {}, ""]

    def destroy(self):
        pass
