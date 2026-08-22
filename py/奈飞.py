# -*- coding: utf-8 -*-
"""
奈飞影视 - naifei.im
"""
import re
import json
import sys
import time
from urllib.parse import quote, urljoin
from base.spider import Spider


class Spider(Spider):
    def __init__(self):
        super(Spider, self).__init__()
        self.host = "https://naifei.im"
        self.name = "奈飞影视"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'Referer': self.host
        }
        self.categories = {
            '1': '电影',
            '2': '剧集',
            '3': '综艺',
            '4': '动漫',
            '5': '短剧'
        }
        self._detail_cache = {}

    def getName(self):
        return "奈飞影视"

    def init(self, extend=""):
        pass

    def homeContent(self, filter):
        classes = [
            {"type_id": "1", "type_name": "电影"},
            {"type_id": "2", "type_name": "剧集"},
            {"type_id": "3", "type_name": "综艺"},
            {"type_id": "4", "type_name": "动漫"},
            {"type_id": "5", "type_name": "短剧"},
        ]
        return {'class': classes, 'filters': {}, 'list': []}

    def homeVideoContent(self):
        try:
            videos = self._fetch_home()
            return {'list': videos}
        except Exception as e:
            print(f'[{self.name}] 首页爬取失败: {e}')
            return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg) if pg and str(pg).isdigit() else 1
            videos = self._fetch_category(tid, page)
            return {
                'page': page,
                'pagecount': 9999,
                'limit': 20,
                'total': 99999,
                'list': videos
            }
        except Exception as e:
            print(f'[{self.name}] 分类爬取失败: {e}')
            return {'page': int(pg), 'pagecount': 0, 'limit': 20, 'total': 0, 'list': []}

    def detailContent(self, ids):
        try:
            vod_id = ids[0] if isinstance(ids, list) else ids
            detail = self._fetch_detail(vod_id)
            if detail:
                return {'list': [detail]}
            return {'list': []}
        except Exception as e:
            print(f'[{self.name}] 详情爬取失败: {e}')
            return {'list': []}

    def playerContent(self, flag, id, vipFlags):
        try:
            play_url = ''
            if id and id.startswith('http'):
                play_url = id
            elif '$' in str(id):
                parts = str(id).split('$', 1)
                if len(parts) == 2:
                    play_url = parts[1]
            else:
                play_url = id

            # 如果是网页链接，需要解析获取真实播放地址
            if play_url and 'naifei.im' in play_url:
                real_url = self._parse_play_url(play_url)
                if real_url:
                    play_url = real_url

            return {
                'parse': 0,
                'playUrl': '',
                'url': play_url,
            }
        except Exception as e:
            print(f'[{self.name}] 播放失败: {e}')
            return {
                'parse': 1,
                'playUrl': '',
                'url': str(id),
            }

    def _parse_play_url(self, url):
        """解析播放页面获取真实播放地址"""
        import re
        
        html = self._fetch_page(url)
        if not html:
            return None
        
        # 直接提取url字段
        url_match = re.search(r'"url"\s*:\s*"(https?:[^"]+)"', html)
        if url_match:
            video_url = url_match.group(1).replace('\\/', '/')
            if video_url and video_url.startswith('http'):
                return video_url
        
        # 备用：直接匹配m3u8地址
        m3u8_match = re.search(r'(https?://[^\s"\'\\]+\.m3u8[^\s"\'\\]*)', html)
        if m3u8_match:
            return m3u8_match.group(1).replace('\\/', '/')
        
        return None

    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg) if pg and str(pg).isdigit() else 1
            videos = self._fetch_search(key, page)
            return {'list': videos}
        except Exception as e:
            print(f'[{self.name}] 搜索失败: {e}')
            return {'list': []}

    def _fetch_page(self, url, retries=2):
        """获取页面内容"""
        import requests
        session = requests.Session()
        session.headers.update(self.headers)
        
        for attempt in range(retries + 1):
            try:
                resp = session.get(url, timeout=15)
                
                if resp.status_code == 403:
                    redirect_match = re.search(r'window\.location\.href\s*=\s*"([^"]+)"', resp.text)
                    if redirect_match:
                        redirect_path = redirect_match.group(1)
                        if redirect_path.startswith('/'):
                            new_url = self.host + redirect_path
                        else:
                            new_url = redirect_path
                        resp = session.get(new_url, timeout=15)
                    elif attempt < retries:
                        time.sleep(1)
                        session.get(self.host, timeout=10)
                        continue
                
                resp.raise_for_status()
                resp.encoding = 'utf-8'
                return resp.text
            except Exception as e:
                if attempt < retries:
                    time.sleep(1)
                    continue
                print(f'[{self.name}] 请求失败: {url}, 错误: {e}')
                return ''
        return ''

    def _fetch_home(self):
        """获取首页视频"""
        from bs4 import BeautifulSoup
        
        html = self._fetch_page(self.host)
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'html.parser')
        videos = []
        
        items_containers = soup.find_all('div', class_='module-items')
        for container in items_containers:
            items = container.find_all('a', class_='module-poster-item')
            for item in items[:20]:
                vod = self._parse_video_item(item)
                if vod:
                    videos.append(vod)
        
        return videos[:50]

    def _fetch_category(self, tid, page=1):
        """获取分类视频"""
        from bs4 import BeautifulSoup
        
        if page <= 1:
            url = f"{self.host}/vodtype/{tid}.html"
        else:
            url = f"{self.host}/vodtype/{tid}-{page}.html"
        
        html = self._fetch_page(url)
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'html.parser')
        videos = []
        
        items = soup.find_all('a', class_='module-poster-item')
        for item in items:
            vod = self._parse_video_item(item)
            if vod:
                videos.append(vod)
        
        return videos

    def _fetch_detail(self, vid):
        """获取视频详情"""
        from bs4 import BeautifulSoup
        
        if vid in self._detail_cache:
            return self._detail_cache[vid]
        
        url = f"{self.host}/voddetail/{vid}.html"
        html = self._fetch_page(url)
        if not html:
            return None
        
        soup = BeautifulSoup(html, 'html.parser')
        
        result = {"vod_id": vid}
        
        title = soup.find('h1', class_='video-info-heading')
        result['vod_name'] = title.text.strip() if title else ''
        
        cover = soup.find('img', class_='lazy lazyload')
        if cover:
            pic = cover.get('data-original', '') or cover.get('src', '')
            if pic and pic.startswith('//'):
                pic = 'https:' + pic
            result['vod_pic'] = pic
        else:
            result['vod_pic'] = ''
        
        info_items = soup.find_all('li', class_='list-item')
        for item in info_items:
            text = item.text.strip()
            if '主演' in text:
                result['vod_actor'] = text.split('：', 1)[-1] if '：' in text else ''
            elif '导演' in text:
                result['vod_director'] = text.split('：', 1)[-1] if '：' in text else ''
            elif '地区' in text or '语言' in text:
                result['vod_area'] = text.split('：', 1)[-1] if '：' in text else ''
            elif '年份' in text:
                result['vod_year'] = text.split('：', 1)[-1] if '：' in text else ''
            elif '更新' in text or '集数' in text:
                result['vod_remarks'] = text.split('：', 1)[-1] if '：' in text else ''
        
        desc = soup.find('div', class_='video-info-content')
        result['vod_content'] = desc.text.strip() if desc else ''
        
        episodes = []
        episode_list = soup.find('div', class_='module-play-list')
        if episode_list:
            ep_items = episode_list.find_all('a')
            for ep in ep_items:
                ep_link = ep.get('href', '')
                ep_title = ep.text.strip()
                if ep_title and ep_link:
                    full_url = urljoin(self.host, ep_link) if ep_link.startswith('/') else ep_link
                    episodes.append(f'{ep_title}${full_url}')
        
        if episodes:
            result['vod_play_from'] = '奈飞影视'
            result['vod_play_url'] = '#'.join(episodes)
        else:
            result['vod_play_from'] = ''
            result['vod_play_url'] = ''
        
        self._detail_cache[vid] = result
        return result

    def _fetch_search(self, keyword, page=1):
        """搜索视频"""
        import json
        
        url = f"{self.host}/index.php/ajax/suggest?mid=1&limit=20&wd={quote(keyword)}"
        html = self._fetch_page(url)
        if not html:
            return []
        
        videos = []
        try:
            data = json.loads(html)
            if data.get('code') == 1 and data.get('list'):
                for item in data['list']:
                    vod = self._parse_search_item(item)
                    if vod:
                        videos.append(vod)
        except Exception as e:
            print(f'[{self.name}] 解析搜索结果失败: {e}')
        
        return videos

    def _parse_search_item(self, item):
        """解析搜索结果项"""
        try:
            vid = str(item.get('id', ''))
            name = item.get('name', '')
            if not vid or not name:
                return None
            
            pic = item.get('pic', '')
            if pic and pic.startswith('//'):
                pic = 'https:' + pic
            
            return {
                'vod_id': vid,
                'vod_name': name,
                'vod_pic': pic,
                'vod_remarks': '',
            }
        except Exception as e:
            return None

    def _parse_video_item(self, item):
        """解析视频项"""
        try:
            link = item.get('href', '')
            title = item.get('title', '')
            
            img = item.find('img')
            cover = ''
            if img:
                cover = img.get('data-original', '') or img.get('src', '')
                if cover and cover.startswith('//'):
                    cover = 'https:' + cover
            
            note = item.find('div', class_='module-item-note')
            quality = note.text.strip() if note else ''
            
            vid = ''
            match = re.search(r'/voddetail/(\d+)\.html', link)
            if match:
                vid = match.group(1)
            
            if not vid or not title:
                return None
            
            return {
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': cover,
                'vod_remarks': quality,
            }
        except Exception as e:
            return None
