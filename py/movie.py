# -*- coding: utf-8 -*-
# 测试即可，禁止用于商业贩卖用途。测试完毕24内删除
# TVBox / 影视仓 / OK影视 Python 标准爬虫（单文件自包含版）
# 站点: app.movie (MacCMS v10)
# 特性: 动态域名探测、多线路播放、筛选器、搜索、4K源优先
# 使用说明: TVBox 配置里 api 指向本文件即可，无需额外 json 配置
import sys
import re
import json
import html
import gzip
from urllib.parse import quote, unquote, urljoin, urlparse

sys.path.append('..')
try:
    from base.spider import Spider
except Exception:
    class Spider(object):
        pass


class Spider(Spider):
    def getName(self):
        return 'APP影院'

    def init(self, extend=''):
        self.last_error = ''
        self.load_extend(extend)

    # ============================================================
    # 域名配置（动态探测核心）
    # ============================================================
    # host 只是启动默认值；真正使用前会通过 ensure_host 实时探测当前内容域名。
    host = 'https://app.movie'
    content_hosts = [
        'https://www.appmovie.art',
        'https://app.movie',
    ]
    entry_hosts = [
        'https://app.movie',
        'https://www.appmovie.art',
        'https://appmovie.art',
    ]

    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 12; Mobile) AppleWebKit/537.36 Chrome/120.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Connection': 'close',
    }

    # ============================================================
    # 分类与筛选器（全部内置，不依赖外部 json）
    # ============================================================
    # 主分类
    classes = [
        {'type_name': '电影', 'type_id': '1'},
        {'type_name': '连续剧', 'type_id': '2'},
        {'type_name': '综艺', 'type_id': '3'},
        {'type_name': '动漫', 'type_id': '4'},
        {'type_name': '电影-动作片', 'type_id': '6'},
        {'type_name': '电影-喜剧片', 'type_id': '7'},
        {'type_name': '电影-爱情片', 'type_id': '8'},
        {'type_name': '电影-科幻片', 'type_id': '9'},
        {'type_name': '电影-恐怖片', 'type_id': '10'},
        {'type_name': '电影-剧情片', 'type_id': '11'},
        {'type_name': '电影-战争片', 'type_id': '12'},
        {'type_name': '电影-纪录片', 'type_id': '20'},
        {'type_name': '连续剧-国产剧', 'type_id': '13'},
        {'type_name': '连续剧-港台剧', 'type_id': '14'},
        {'type_name': '连续剧-日韩剧', 'type_id': '15'},
        {'type_name': '连续剧-欧美剧', 'type_id': '16'},
    ]

    # 筛选器配置
    filters = {
        '1': [
            {'key': 'class', 'name': '类型', 'value': [
                {'n': '全部', 'v': ''},
                {'n': '动作片', 'v': '6'},
                {'n': '喜剧片', 'v': '7'},
                {'n': '爱情片', 'v': '8'},
                {'n': '科幻片', 'v': '9'},
                {'n': '恐怖片', 'v': '10'},
                {'n': '剧情片', 'v': '11'},
                {'n': '战争片', 'v': '12'},
                {'n': '纪录片', 'v': '20'},
            ]},
            {'key': 'area', 'name': '地区', 'value': [
                {'n': '全部', 'v': ''},
                {'n': '中国大陆', 'v': '%E4%B8%AD%E5%9B%BD%E5%A4%A7%E9%99%86'},
                {'n': '中国香港', 'v': '%E4%B8%AD%E5%9B%BD%E9%A6%99%E6%B8%AF'},
                {'n': '中国台湾', 'v': '%E4%B8%AD%E5%9B%BD%E5%8F%B0%E6%B9%BE'},
                {'n': '美国', 'v': '%E7%BE%8E%E5%9B%BD'},
                {'n': '韩国', 'v': '%E9%9F%A9%E5%9B%BD'},
                {'n': '日本', 'v': '%E6%97%A5%E6%9C%AC'},
                {'n': '泰国', 'v': '%E6%B3%B0%E5%9B%BD'},
                {'n': '英国', 'v': '%E8%8B%B1%E5%9B%BD'},
            ]},
            {'key': 'year', 'name': '年份', 'value': [
                {'n': '全部', 'v': ''},
                {'n': '2026', 'v': '2026'},
                {'n': '2025', 'v': '2025'},
                {'n': '2024', 'v': '2024'},
                {'n': '2023', 'v': '2023'},
                {'n': '2022', 'v': '2022'},
                {'n': '2021', 'v': '2021'},
                {'n': '2020', 'v': '2020'},
                {'n': '2019', 'v': '2019'},
                {'n': '2018', 'v': '2018'},
                {'n': '2017', 'v': '2017'},
            ]},
        ],
        '2': [
            {'key': 'class', 'name': '类型', 'value': [
                {'n': '全部', 'v': ''},
                {'n': '国产剧', 'v': '13'},
                {'n': '港台剧', 'v': '14'},
                {'n': '日韩剧', 'v': '15'},
                {'n': '欧美剧', 'v': '16'},
            ]},
            {'key': 'area', 'name': '地区', 'value': [
                {'n': '全部', 'v': ''},
                {'n': '中国大陆', 'v': '%E4%B8%AD%E5%9B%BD%E5%A4%A7%E9%99%86'},
                {'n': '中国香港', 'v': '%E4%B8%AD%E5%9B%BD%E9%A6%99%E6%B8%AF'},
                {'n': '中国台湾', 'v': '%E4%B8%AD%E5%9B%BD%E5%8F%B0%E6%B9%BE'},
                {'n': '韩国', 'v': '%E9%9F%A9%E5%9B%BD'},
                {'n': '日本', 'v': '%E6%97%A5%E6%9C%AC'},
                {'n': '美国', 'v': '%E7%BE%8E%E5%9B%BD'},
                {'n': '泰国', 'v': '%E6%B3%B0%E5%9B%BD'},
                {'n': '英国', 'v': '%E8%8B%B1%E5%9B%BD'},
            ]},
            {'key': 'year', 'name': '年份', 'value': [
                {'n': '全部', 'v': ''},
                {'n': '2026', 'v': '2026'},
                {'n': '2025', 'v': '2025'},
                {'n': '2024', 'v': '2024'},
                {'n': '2023', 'v': '2023'},
                {'n': '2022', 'v': '2022'},
                {'n': '2021', 'v': '2021'},
                {'n': '2020', 'v': '2020'},
                {'n': '2019', 'v': '2019'},
            ]},
        ],
        '3': [
            {'key': 'area', 'name': '地区', 'value': [
                {'n': '全部', 'v': ''},
                {'n': '中国大陆', 'v': '%E4%B8%AD%E5%9B%BD%E5%A4%A7%E9%99%86'},
                {'n': '中国香港', 'v': '%E4%B8%AD%E5%9B%BD%E9%A6%99%E6%B8%AF'},
                {'n': '中国台湾', 'v': '%E4%B8%AD%E5%9B%BD%E5%8F%B0%E6%B9%BE'},
                {'n': '韩国', 'v': '%E9%9F%A9%E5%9B%BD'},
                {'n': '日本', 'v': '%E6%97%A5%E6%9C%AC'},
                {'n': '美国', 'v': '%E7%BE%8E%E5%9B%BD'},
            ]},
            {'key': 'year', 'name': '年份', 'value': [
                {'n': '全部', 'v': ''},
                {'n': '2026', 'v': '2026'},
                {'n': '2025', 'v': '2025'},
                {'n': '2024', 'v': '2024'},
                {'n': '2023', 'v': '2023'},
                {'n': '2022', 'v': '2022'},
                {'n': '2021', 'v': '2021'},
            ]},
        ],
        '4': [
            {'key': 'area', 'name': '地区', 'value': [
                {'n': '全部', 'v': ''},
                {'n': '中国大陆', 'v': '%E4%B8%AD%E5%9B%BD%E5%A4%A7%E9%99%86'},
                {'n': '日本', 'v': '%E6%97%A5%E6%9C%AC'},
                {'n': '美国', 'v': '%E7%BE%8E%E5%9B%BD'},
                {'n': '韩国', 'v': '%E9%9F%A9%E5%9B%BD'},
            ]},
            {'key': 'year', 'name': '年份', 'value': [
                {'n': '全部', 'v': ''},
                {'n': '2026', 'v': '2026'},
                {'n': '2025', 'v': '2025'},
                {'n': '2024', 'v': '2024'},
                {'n': '2023', 'v': '2023'},
                {'n': '2022', 'v': '2022'},
            ]},
        ],
    }

    # ============================================================
    # TVBox 标准接口
    # ============================================================
    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    def homeContent(self, filter):
        result = {'class': self.classes}
        if filter:
            result['filters'] = self.filters
        return result

    def homeVideoContent(self):
        html_text = self.fetch(self.host + '/')
        vods = self.parse_vod_list(html_text)
        if not vods:
            vods = [self.debug_vod('首页无数据', self.host + '/', html_text)]
        return {'list': vods[:30]}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = int(pg or 1)
            url = self.build_category_url(tid, pg, extend)
            html_text = self.fetch(url)
            vods = self.parse_vod_list(html_text)
            total = self.parse_total_page(html_text)
            if (not vods) and pg == 1:
                vods = [self.debug_vod('分类无数据', url, html_text)]
            return {
                'page': pg,
                'pagecount': total if total > 0 else (pg + 1 if vods else pg),
                'limit': 24,
                'total': (total if total > 0 else pg + 1) * 24,
                'list': vods,
            }
        except Exception as e:
            return {'page': 1, 'pagecount': 1, 'limit': 24, 'total': 1, 'list': [self.debug_vod('分类异常', str(e), '')]}

    def detailContent(self, ids):
        vod_id = ids[0]
        if str(vod_id).startswith('debug$'):
            msg = str(vod_id).split('$', 1)[1]
            return {'list': [{
                'vod_id': vod_id, 'vod_name': '诊断信息', 'vod_pic': '', 'type_name': '诊断',
                'vod_year': '', 'vod_area': '', 'vod_remarks': '请把这条内容发给我',
                'vod_actor': '', 'vod_director': '', 'vod_content': msg,
                'vod_play_from': '诊断', 'vod_play_url': '诊断$' + vod_id,
            }]}
        url = self.abs_url('/index.php/vod/detail/id/' + str(vod_id) + '.html')
        html_text = self.fetch(url)
        if not html_text:
            return {'list': [self.debug_vod('详情页无内容', url, '')]}
        return self.parse_detail(html_text, vod_id)

    def searchContent(self, key, quick, pg='1'):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg):
        pg = int(pg or 1)
        self.ensure_host()
        url = self.host + '/index.php/vod/search.html?wd=' + quote(key) + ('&page=' + str(pg) if pg > 1 else '')
        html_text = self.fetch(url)
        vods = self.parse_vod_list(html_text)
        if not vods and pg == 1:
            vods = [self.debug_vod('搜索无数据', url, html_text)]
        return {'page': pg, 'pagecount': pg + 1 if vods else pg, 'limit': 24, 'total': len(vods), 'list': vods}

    def playerContent(self, flag, id, vipFlags):
        if str(id).startswith('debug$'):
            return {'parse': 0, 'playUrl': '', 'url': '', 'header': {}}
        try:
            parts = id.split('@')
            video_id = parts[0]
            sid = parts[1] if len(parts) > 1 else '1'
            nid = parts[2] if len(parts) > 2 else '1'
        except Exception:
            video_id = id
            sid = '1'
            nid = '1'
        url = self.abs_url('/index.php/vod/play/id/' + str(video_id) + '/sid/' + str(sid) + '/nid/' + str(nid) + '.html')
        html_text = self.fetch(url)
        if not html_text:
            return {'parse': 0, 'playUrl': '', 'url': '', 'header': {}}
        # 提取 player_data 中的 url
        m = re.search(r'var\s+player_data\s*=\s*({.+?})(?:;|<)', html_text)
        if m:
            try:
                player_data = json.loads(m.group(1))
                play_url = player_data.get('url', '')
                if play_url:
                    return {
                        'parse': 0,
                        'playUrl': '',
                        'url': play_url,
                        'header': {
                            'User-Agent': self.headers['User-Agent'],
                            'Referer': url,
                        },
                    }
            except Exception:
                pass
        # 备用：直接提取 m3u8 链接
        m3u8 = self.search_first(r'(https?://[^\s"\'<>]+\.m3u8)', html_text)
        if m3u8:
            return {
                'parse': 0,
                'playUrl': '',
                'url': m3u8,
                'header': {
                    'User-Agent': self.headers['User-Agent'],
                    'Referer': url,
                },
            }
        return {'parse': 0, 'playUrl': '', 'url': '', 'header': {}}

    def localProxy(self, params):
        return [404, 'text/plain', '']

    # ============================================================
    # 辅助方法
    # ============================================================
    def load_extend(self, extend):
        try:
            hosts = []
            if isinstance(extend, dict):
                hosts = extend.get('hosts') or extend.get('host') or []
            elif isinstance(extend, str) and extend.strip():
                ext = extend.strip()
                if ext.startswith('{'):
                    data = json.loads(ext)
                    hosts = data.get('hosts') or data.get('host') or []
                else:
                    hosts = re.split(r'[,，\s]+', ext)
            if isinstance(hosts, str):
                hosts = [hosts]
            for h in hosts:
                h = self.normalize_host(h)
                if h:
                    self.content_hosts.insert(0, h)
            self.content_hosts = self.unique_hosts(self.content_hosts)
        except Exception:
            pass

    def ensure_host(self):
        # 先测试已有内容域名，成功就直接用。
        for h in self.unique_hosts([self.host] + self.content_hosts):
            text, final_url = self.fetch_once(h + '/')
            if self.looks_like_video_page(text):
                self.host = self.normalize_host(final_url) or h
                return self.host
        # 已有内容域名失效时，从入口域名、跳转结果实时发现新域名。
        for h in self.discover_hosts():
            text, final_url = self.fetch_once(h + '/')
            if self.looks_like_video_page(text):
                self.host = self.normalize_host(final_url) or h
                if self.host not in self.content_hosts:
                    self.content_hosts.insert(0, self.host)
                return self.host
        return self.host

    def discover_hosts(self):
        found = []
        seeds = self.unique_hosts([self.host] + self.content_hosts + self.entry_hosts)
        for h in seeds:
            for path in ['/', '/index.php']:
                text, final_url = self.fetch_once(h + path)
                final_host = self.normalize_host(final_url)
                if final_host and (text or final_url != h + path):
                    found.append(final_host)
                # 页面里如果出现完整域名，也加入候选。
                for u in re.findall(r'https?://[A-Za-z0-9.-]+', text or ''):
                    uh = self.normalize_host(u)
                    if uh:
                        found.append(uh)
        hosts = self.unique_hosts(found)
        if hosts:
            self.content_hosts = self.unique_hosts(hosts + self.content_hosts)
        return hosts

    def fetch(self, url):
        self.last_error = ''
        self.ensure_host()
        best = ''
        for u in self.candidate_urls(url):
            text, final_url = self.fetch_once(u)
            if not text:
                continue
            if not best:
                best = text
            final_host = self.normalize_host(final_url)
            if final_host and self.looks_like_video_page(text):
                self.host = final_host
            if self.looks_like_video_page(text):
                return text
        return best

    def fetch_once(self, url):
        errors = []
        headers = self.get_headers(url)
        try:
            from urllib.request import Request, urlopen
            headers['Accept-Encoding'] = 'gzip, deflate'
            req = Request(url, headers=headers)
            with urlopen(req, timeout=10) as r:
                data = r.read()
                # 处理 gzip 压缩
                if r.headers.get('Content-Encoding') == 'gzip':
                    data = gzip.decompress(data)
                return self.to_text(data), getattr(r, 'url', url)
        except Exception as e:
            errors.append('urllib=' + repr(e))
        try:
            import requests
            r = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
            return self.to_text(r.text), getattr(r, 'url', url)
        except Exception as e:
            errors.append('requests=' + repr(e))
        try:
            rsp = super().fetch(url, headers=headers)
            text, final_url = self.response_to_text(rsp, url)
            if text:
                return text, final_url
        except Exception as e:
            errors.append('super=' + repr(e))
        self.last_error = ' ; '.join(errors)[-500:]
        return '', url

    def get_headers(self, url):
        headers = dict(self.headers)
        headers['Referer'] = url
        return headers

    def candidate_urls(self, url):
        url = self.abs_url(url)
        out = []
        for h in self.unique_hosts([self.host] + self.content_hosts):
            parsed = urlparse(url)
            new_url = h + parsed.path + ('?' + parsed.query if parsed.query else '') + ('#' + parsed.fragment if parsed.fragment else '')
            out.append(new_url)
        return out

    def abs_url(self, path):
        if path.startswith('http'):
            return path
        if not path.startswith('/'):
            path = '/' + path
        return self.host + path

    def normalize_host(self, url):
        if not url:
            return ''
        url = url.strip()
        if not url.startswith('http'):
            url = 'https://' + url
        p = urlparse(url)
        if not p.scheme or not p.netloc:
            return ''
        return p.scheme + '://' + p.netloc

    def unique_hosts(self, hosts):
        seen = set()
        out = []
        for h in hosts:
            h = self.normalize_host(h)
            if h and h not in seen:
                seen.add(h)
                out.append(h)
        return out

    def looks_like_video_page(self, text):
        if not text:
            return False
        # MacCMS 站点的特征
        markers = ['stui-vodlist', 'player_data', 'maccms', 'vod/detail', 'vod/play', 'stui-content__playlist']
        for m in markers:
            if m in text:
                return True
        return False

    def to_text(self, data):
        if isinstance(data, bytes):
            try:
                return data.decode('utf-8')
            except Exception:
                return data.decode('utf-8', 'ignore')
        return str(data)

    def response_to_text(self, rsp, url):
        try:
            if hasattr(rsp, 'text'):
                return rsp.text, getattr(rsp, 'url', url)
            if hasattr(rsp, 'content'):
                return self.to_text(rsp.content), getattr(rsp, 'url', url)
            if hasattr(rsp, 'read'):
                return self.to_text(rsp.read()), getattr(rsp, 'url', url)
        except Exception:
            pass
        return '', url

    # ============================================================
    # URL 构建
    # ============================================================
    def build_category_url(self, tid, pg, extend):
        base = '/index.php/vod/show/id/' + str(tid)
        params = []
        if isinstance(extend, dict):
            if extend.get('class'):
                base = '/index.php/vod/show/id/' + str(extend.get('class'))
            if extend.get('area'):
                params.append('area=' + extend.get('area'))
            if extend.get('year'):
                params.append('year=' + extend.get('year'))
        if pg > 1:
            base += '/page/' + str(pg)
        if params:
            return self.host + base + '.html?' + '&'.join(params)
        return self.host + base + '.html'

    # ============================================================
    # 页面解析
    # ============================================================
    def parse_vod_list(self, html_text):
        vods = []
        if not html_text:
            return vods
        # 匹配每个视频项
        items = re.findall(
            r'<li class="stui-vodlist__item"[^>]*>.*?<a class="stui-vodlist__thumb lazyload"[^>]*href="(/index\.php/vod/detail/id/(\d+)\.html)"[^>]*title="([^"]*)"[^>]*data-original="([^"]*)".*?</li>',
            html_text, re.DOTALL
        )
        for item in items:
            href, vid, title, pic = item
            # 提取状态
            status = ''
            status_match = re.search(r'<span class="pic-text[^"]*">([^<]*)</span>', html_text[html_text.find(href):html_text.find(href)+500])
            if status_match:
                status = status_match.group(1).strip()
            vods.append({
                'vod_id': str(vid),
                'vod_name': html.unescape(title).strip(),
                'vod_pic': pic.strip(),
                'vod_remarks': status,
            })
        return vods

    def parse_total_page(self, html_text):
        if not html_text:
            return 0
        # 从分页中提取最大页码
        pages = re.findall(r'/page/(\d+)\.html', html_text)
        if pages:
            return max(int(p) for p in pages)
        return 0

    def parse_detail(self, html_text, vod_id):
        # 标题
        title = self.search_first(r'<h3 class="title">([^<]+)</h3>', html_text) or '未知标题'
        title = html.unescape(title).strip()
        # 图片
        pic = self.search_first(r'<img class="img-responsive lazyload"[^>]*data-original="([^"]+)"', html_text) or ''
        # 类型
        type_name = ''
        type_match = re.search(r'<span class="text-muted[^"]*">类型：</span><a[^>]*>([^<]+)</a>', html_text)
        if type_match:
            type_name = type_match.group(1).strip()
        # 地区
        area = ''
        area_match = re.search(r'<span class="text-muted[^"]*">地区：</span><a[^>]*>([^<]+)</a>', html_text)
        if area_match:
            area = area_match.group(1).strip()
        # 年份
        year = ''
        year_match = re.search(r'<span class="text-muted[^"]*">年份：</span><a[^>]*>([^<]+)</a>', html_text)
        if year_match:
            year = year_match.group(1).strip()
        # 状态
        status = self.search_first(r'<p class="data"><span>状态：</span>([^<]+)</p>', html_text) or ''
        # 主演
        actor = self.search_first(r'<p class="data"><span>主演：</span>([^<]+)</p>', html_text) or ''
        # 导演
        director = self.search_first(r'<p class="data"><span>导演：</span>([^<]+)</p>', html_text) or ''
        # 简介
        content = ''
        content_match = re.search(r'<div class="stui-content__desc[^"]*">(.*?)</div>', html_text, re.DOTALL)
        if content_match:
            content = re.sub(r'<[^>]+>', '', content_match.group(1))
            content = html.unescape(content).strip()

        # 解析播放源
        play_from = []
        play_url = []
        # 找到所有 playlist，然后向前查找对应的播放源名称
        playlists = list(re.finditer(r'<ul class="stui-content__playlist clearfix">(.*?)</ul>', html_text, re.DOTALL))
        for pl in playlists:
            source_html = pl.group(1)
            # 从 playlist 位置向前查找最近的 h3.title
            before = html_text[:pl.start()]
            h3_match = None
            for m in re.finditer(r'<h3 class="title">\s*([^<]+)\s*</h3>', before):
                h3_match = m
            if not h3_match:
                continue
            source_name = h3_match.group(1).strip()
            if not source_name or '剧情介绍' in source_name or '猜你喜欢' in source_name:
                continue
            # 提取剧集链接
            episodes = re.findall(
                r'<a href="/index\.php/vod/play/id/(\d+)/sid/(\d+)/nid/(\d+)\.html">([^<]+)</a>',
                source_html
            )
            if not episodes:
                continue
            ep_list = []
            for ep_vid, ep_sid, ep_nid, ep_name in episodes:
                ep_name = html.unescape(ep_name).strip()
                play_id = '%s@%s@%s' % (ep_vid, ep_sid, ep_nid)
                ep_list.append('%s$%s' % (ep_name, play_id))
            if ep_list:
                play_from.append(source_name)
                play_url.append('#'.join(ep_list))

        if not play_from:
            # 备用：如果没有解析到播放源，使用详情页链接作为单个播放项
            play_from = ['默认线路']
            play_url = ['播放$%s@1@1' % vod_id]

        vod = {
            'vod_id': vod_id,
            'vod_name': title,
            'vod_pic': pic,
            'type_name': type_name,
            'vod_year': year,
            'vod_area': area,
            'vod_remarks': status,
            'vod_actor': actor,
            'vod_director': director,
            'vod_content': content,
            'vod_play_from': '$$$'.join(play_from),
            'vod_play_url': '$$$'.join(play_url),
        }
        return {'list': [vod]}

    def search_first(self, pattern, text):
        if not text:
            return ''
        m = re.search(pattern, text)
        return m.group(1).strip() if m else ''

    def debug_vod(self, title, url, html_text):
        return {
            'vod_id': 'debug$' + title + '|' + url[:200],
            'vod_name': title,
            'vod_pic': '',
            'type_name': '诊断',
            'vod_year': '',
            'vod_area': '',
            'vod_remarks': self.last_error[-100:] or '诊断',
            'vod_actor': '',
            'vod_director': '',
            'vod_content': 'URL: ' + url[:500] + '\nHTML前500: ' + (html_text[:500] if html_text else '空'),
            'vod_play_from': '诊断',
            'vod_play_url': '诊断$debug$' + title,
        }
