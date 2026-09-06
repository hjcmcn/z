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

    # 网站 menu 结构 (menuId -> 菜单名)
    MENU_NAMES = {
        1: "麻豆原创",
        2: "国产AV",
        3: "岛国AV",
        4: "黑料吃瓜",
    }

    def __init__(self):
        super().__init__()
        self._xurl = None
        self._headers = None
        self._cache_cats = None  # 缓存分类列表

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
        return json.loads(resp.text)

    def _get_categories(self):
        """获取并缓存所有分类"""
        if self._cache_cats is None:
            try:
                data = self._fetch_api('/categories')
                self._cache_cats = data.get('data', [])
            except Exception:
                self._cache_cats = []
        return self._cache_cats

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

    def _parse_post_items(self, items):
        """帖子/黑料类内容"""
        videos = []
        for item in items:
            pid = str(item.get('id', ''))
            if not pid:
                continue
            title = (item.get('title') or item.get('name') or '').strip()
            if not title:
                continue
            pic = self._build_image_url(item.get('coverUrl') or item.get('cover') or '')
            published = item.get('publishedAt', '')
            if published:
                m = re.match(r'(\d{4})-(\d{2})-(\d{2})', published)
                if m:
                    title += f' [{m.group(1)}-{m.group(2)}-{m.group(3)}]'
            videos.append({
                "vod_id": f'post_{pid}',
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": item.get('categoryName', '')
            })
        return videos

    # ============ 首页分类：4 个菜单 folder + AI短剧 ============
    def homeContent(self, filter):
        class_items = []
        filters = {}

        # 4 个一级菜单（按 menuId 分组）作为 folder
        for mid in [1, 2, 3, 4]:
            name = self.MENU_NAMES.get(mid, f"菜单{mid}")
            class_items.append({
                "type_id": f"menu_{mid}",
                "type_name": name
            })
            # 排序筛选（菜单 1/2/3 视频用）
            if mid in (1, 2, 3):
                filters[f"menu_{mid}"] = [self._video_sort_filter(), self._time_filter(), self._duration_filter()]
            else:
                # 黑料吃瓜(帖子)只需时间
                filters[f"menu_{mid}"] = [self._time_filter()]

        # AI短剧（独立一级）
        class_items.append({"type_id": "short-dramas", "type_name": "AI短剧"})
        filters["short-dramas"] = [self._time_filter()]

        return {"class": class_items, "filters": filters}

    def _video_sort_filter(self):
        return {
            "key": "sortBy",
            "name": "排序",
            "value": [
                {"n": "最热", "v": "heat"},
                {"n": "最新", "v": "newest"},
                {"n": "最早", "v": "oldest"},
                {"n": "播放最多", "v": "views"},
                {"n": "点赞最多", "v": "likes"},
            ]
        }

    def _time_filter(self):
        return {
            "key": "timeRange",
            "name": "更新时间",
            "value": [
                {"n": "全部", "v": ""},
                {"n": "近7天", "v": "7d"},
                {"n": "近1月", "v": "1m"},
                {"n": "近3月", "v": "3m"},
            ]
        }

    def _duration_filter(self):
        return {
            "key": "minDuration",
            "name": "视频时长",
            "value": [
                {"n": "全部", "v": ""},
                {"n": "10分钟以上", "v": "10"},
                {"n": "20分钟以上", "v": "20"},
            ]
        }

    def homeVideoContent(self):
        """推荐页 = 每日更新 (menuId=1 排序)"""
        try:
            data = self._fetch_api('/videos', params={'page': 1, 'size': 20, 'sortBy': 'heat'})
            items = data.get('data', {}).get('items', [])
            return {'list': self._parse_video_items(items)}
        except:
            return {'list': []}

    # ============ 分类内容 ============
    def categoryContent(self, cid, pg, filter, ext):
        page = int(pg) if pg else 1
        cid = str(cid)

        # 二级目录：进入菜单 → 列子分类
        if cid.startswith('menu_'):
            return self._category_menu(cid, page, filter, ext)

        # AI短剧
        if cid == 'short-dramas':
            return self._category_short_dramas(page, ext)

        # 视频分类
        if cid.isdigit():
            return self._category_videos(int(cid), page, ext)

        # 帖子分类
        if cid.startswith('post_cat_'):
            return self._category_posts(int(cid[9:]), page, ext)

        return {'list': [], 'page': page, 'pagecount': 1, 'limit': 20, 'total': 0}

    def _category_menu(self, cid, page, filter, ext):
        """进入菜单，列出子分类作为 folder 项"""
        menu_id = int(cid.split('_')[1])
        all_cats = self._get_categories()
        sub_cats = [c for c in all_cats
                    if c.get('menuId') == menu_id
                    and c.get('enabled')
                    and c.get('type') in ('video', 'post', 'shortdrama')]
        sub_cats.sort(key=lambda x: x.get('sortOrder', 0))

        videos = []
        for c in sub_cats:
            c_id = c.get('id')
            c_type = c.get('type', 'video')
            # video/post 用分类 ID，短剧用 short-dramas
            if c_type == 'post':
                vod_id = f'post_cat_{c_id}'
            elif c_type == 'video':
                vod_id = str(c_id)
            else:
                continue
            videos.append({
                "vod_id": vod_id,
                "vod_name": c.get('name', ''),
                "vod_pic": '',
                "vod_remarks": '',
                "vod_tag": "folder"
            })
        return {'list': videos, 'page': 1, 'pagecount': 1, 'limit': 100, 'total': len(videos)}

    def _category_short_dramas(self, page, ext):
        size = 12
        params = {'productId': 1, 'sortBy': 'heat', 'page': page, 'size': size}
        if isinstance(ext, dict):
            tr = ext.get('timeRange', '')
            if tr:
                params['timeRange'] = tr
        try:
            data = self._fetch_api('/short-dramas', params=params)
            d = data.get('data', {})
            items = d.get('items', [])
            total = d.get('total', 0)
            pagecount = d.get('totalPages', (total + size - 1) // size if total > 0 else 1)
            return {
                'list': self._parse_short_drama_items(items),
                'page': page, 'pagecount': pagecount, 'limit': size, 'total': total
            }
        except:
            return {'list': [], 'page': page, 'pagecount': 1, 'limit': size, 'total': 0}

    def _category_videos(self, cat_id, page, ext):
        size = 20
        params = {'page': page, 'size': size, 'categoryId': cat_id}
        if isinstance(ext, dict):
            for k, param in [('sortBy', 'sortBy'), ('timeRange', 'timeRange'), ('minDuration', 'minDuration')]:
                v = ext.get(k, '')
                if v:
                    params[param] = v
        try:
            data = self._fetch_api('/videos', params=params)
            d = data.get('data', {})
            items = d.get('items', [])
            total = d.get('total', 0)
            pagecount = (total + size - 1) // size if total > 0 else 1
            return {
                'list': self._parse_video_items(items),
                'page': page, 'pagecount': pagecount, 'limit': size, 'total': total
            }
        except:
            return {'list': [], 'page': page, 'pagecount': 1, 'limit': size, 'total': 0}

    def _category_posts(self, cat_id, page, ext):
        size = 20
        params = {'page': page, 'size': size, 'categoryId': cat_id}
        if isinstance(ext, dict):
            tr = ext.get('timeRange', '')
            if tr:
                params['timeRange'] = tr
        try:
            data = self._fetch_api('/posts', params=params)
            d = data.get('data', {})
            items = d.get('items', [])
            total = d.get('total', 0)
            pagecount = (total + size - 1) // size if total > 0 else 1
            return {
                'list': self._parse_post_items(items),
                'page': page, 'pagecount': pagecount, 'limit': size, 'total': total
            }
        except:
            return {'list': [], 'page': page, 'pagecount': 1, 'limit': size, 'total': 0}

    # ============ 详情 ============
    def detailContent(self, ids):
        vid = ids[0]
        if vid.startswith('sd_'):
            return self._detail_short_drama(vid)
        if vid.startswith('post_'):
            return self._detail_post(vid)
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
            ym = re.match(r'(\d{4})', published)
            if ym:
                vod["vod_year"] = ym.group(1)
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
                vod["vod_play_from"] = '麻豆'
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
            ym = re.match(r'(\d{4})', published)
            if ym:
                vod["vod_year"] = ym.group(1)
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
            ep_title = ep.get('titleOverride') or ep.get('title') or f"第{ep.get('episodeNo', '')}集"
            ep_url = self._build_m3u8_proxy_url(ep.get('videoUrl', ''))
            if ep_url:
                play_list.append(f'{ep_title}${ep_url}')
        if play_list:
            vod["vod_play_from"] = '麻豆'
            vod["vod_play_url"] = '#'.join(play_list)
        return {'list': [vod]}

    def _detail_post(self, vid):
        post_id = vid[5:]
        try:
            data = self._fetch_api(f'/posts/{post_id}')
            item = data.get('data', {})
        except:
            return {'list': []}
        vod = {}
        vod["vod_id"] = vid
        vod["vod_name"] = item.get('title', '')
        vod["vod_pic"] = self._build_image_url(item.get('coverUrl') or item.get('cover') or '')
        published = item.get('publishedAt', '')
        if published:
            ym = re.match(r'(\d{4})', published)
            if ym:
                vod["vod_year"] = ym.group(1)
        vod["type_name"] = item.get('categoryName', '黑料吃瓜')
        # 描述
        desc = item.get('content') or item.get('description') or ''
        if desc:
            vod["vod_content"] = str(desc)[:1000]
        # 视频（顶层 videoUrl 字段）
        video_url = item.get('videoUrl', '')
        if video_url:
            m3u8_url = self._build_m3u8_proxy_url(video_url)
            if m3u8_url:
                vod["vod_play_from"] = '麻豆'
                vod["vod_play_url"] = f'正片${m3u8_url}'
        # 图片列表拼到内容（黑料多图文）
        images = item.get('images') or []
        img_urls = []
        for img in images:
            if isinstance(img, dict):
                url = img.get('url') or img.get('path') or img.get('imageUrl')
            else:
                url = img
            if url:
                img_urls.append(self._build_image_url(url))
        if img_urls:
            vod["vod_content"] = (vod.get("vod_content", "") + '\n\n' + '\n'.join(img_urls))
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
                'page': page, 'pagecount': pagecount, 'limit': size, 'total': total
            }
        except:
            return {'list': [], 'page': page, 'pagecount': 1, 'limit': size, 'total': 0}
