# -*- coding: utf-8 -*-
"""
2048核基地 py源 重写版
按网站导航结构重写分类体系，图片区+小说区加上
- 视频区 9 个一级分类（子分类少的用筛选面板，多的也用筛选因为不超过 8 个）
- 图片区 2 个一级分类（folder 标签二级目录）
- 小说区 2 个一级分类（folder 标签二级目录）
- m3u8 广告清洗代理保留
- 多域名自动更新保留
"""
import sys
import re
import json
import html as html_mod
import requests
import urllib3
import time
import random
from urllib.parse import quote, urljoin, unquote, urlparse

urllib3.disable_warnings()
sys.path.append('..')
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    # ========== 多域名配置 ==========
    hosts = ['https://s7t8u9v0.luanlunba15.cc']
    host = hosts[0]

    PUBLISH_PAGES = [
        'https://www.luanlunba.cc',
        'https://s7t8u9v0.luanlunba13.cc',
        'https://s7t8u9v0.luanlunba14.cc',
    ]

    session = requests.Session()

    def _log(self, msg):
        pass  # 静默

    def getName(self):
        return '2048核基地'

    def isVideoFormat(self, url):
        return url and ('.m3u8' in url or '.mp4' in url or '.ts' in url)

    def manualVideoCheck(self):
        return False

    def destroy(self):
        try:
            self.session.close()
        except:
            pass

    # ===================== 网络 =====================
    def _headers(self, referer=None):
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': referer or self.host + '/',
        }

    def _fetch(self, url, referer=None, retries=2):
        for i in range(retries):
            try:
                if i > 0:
                    time.sleep(random.uniform(0.3, 1))
                r = self.session.get(url, headers=self._headers(referer),
                                     timeout=(10, 20), verify=False)
                if not r.encoding or r.encoding.lower() in ('iso-8859-1', 'latin-1'):
                    r.encoding = r.apparent_encoding
                if r.status_code == 200:
                    return r.text
            except:
                continue
        return ''

    # ===================== 域名自动更新 =====================
    def _update_host(self):
        for pub in self.PUBLISH_PAGES:
            try:
                r1 = self.session.get(pub + '/', headers=self._headers(), timeout=10, verify=False)
                cookie_match = re.search(r'document\.cookie\s*=\s*"([^"]+)"', r1.text)
                if cookie_match:
                    for part in cookie_match.group(1).split(';'):
                        part = part.strip()
                        if '=' in part and 'path' not in part and 'max-age' not in part:
                            k, v = part.split('=', 1)
                            self.session.cookies.set(k.strip(), v.strip())

                ajax_url = pub + '/xuexi/data.php'
                h = self._headers(pub + '/')
                h['X-Requested-With'] = 'XMLHttpRequest'
                r2 = self.session.get(ajax_url, headers=h, timeout=10, verify=False)
                if not r2.encoding or r2.encoding.lower() in ('iso-8859-1', 'latin-1'):
                    r2.encoding = r2.apparent_encoding
                try:
                    urls = r2.json().get('urls', [])
                except:
                    urls = re.findall(r'(https?://[a-z0-9]+\.luanlunba\d*\.\w+)', r2.text)

                for url in urls:
                    url = url.strip('/')
                    if not url.startswith('http'):
                        continue
                    try:
                        test = self.session.get(url + '/', headers=self._headers(), timeout=8, verify=False)
                        if test.status_code == 200 and len(test.text) > 1000:
                            if 'vodtype' in test.text or 'voddetail' in test.text:
                                self.host = url
                                self.hosts = [url] + [h for h in self.hosts if h != url]
                                return True
                    except:
                        continue
            except:
                continue

        for h in self.hosts:
            try:
                test = self.session.get(h + '/', headers=self._headers(), timeout=8, verify=False)
                if test.status_code == 200 and len(test.text) > 1000:
                    self.host = h
                    return True
            except:
                continue
        return False

    # ===================== 分类体系（精简：视频+图片+小说 共8个一级） =====================
    # 一级分类尽量少：视频区按网站导航6组 + 图片区1 + 小说区1 = 8个
    # 每个分类的子分类用筛选面板实现（不占用一级分类名额）
    CATEGORIES = [
        # ---- 视频区（6个一级，按网站导航分组，未选滤默认显示父分类）----
        {'type_id': 'v_gc', 'type_name': '国产传媒', 'filters': [
            ('6', '麻豆视频'), ('7', '91制片厂'), ('8', '天美传媒'), ('9', '蜜桃传媒'),
            ('10', '皇家华人'), ('11', '星空传媒'), ('12', '精东影业'), ('20', '乐播传媒'),
        ]},
        {'type_id': 'v_gq', 'type_name': '国产剧情', 'filters': [
            ('57', '兔子先生'), ('21', '杏吧原创'), ('22', '糖心Vlog'), ('24', '玩偶姐姐'),
            ('25', 'mini传媒'), ('26', '大象传媒'), ('30', '成人头条'), ('31', '乌鸦传媒'),
        ]},
        {'type_id': 'v_wb', 'type_name': '网曝黑料', 'filters': [
            ('60', '国产精品'), ('61', '华语AV'), ('62', '黑料吃瓜'), ('63', '学生合集'),
            ('64', '乱伦精品'), ('65', '探花约炮'), ('66', '日本无码'), ('67', '主播网红'),
        ]},
        {'type_id': 'v_ts', 'type_name': '特色仓库', 'filters': [
            ('37', '国产自拍'), ('32', '强奸乱伦'), ('33', '女优明星'), ('34', '欧美激情'),
            ('28', '重口激情'), ('29', '三级伦理'), ('35', '剧情动漫'), ('15', 'SM调教'),
        ]},
        {'type_id': 'v_zp', 'type_name': '精品资源', 'filters': [
            ('70', '女同性恋'), ('71', '日韩无码'), ('72', '网曝吃瓜'), ('73', '探花约炮'),
            ('74', '偷拍偷窥'), ('75', '日韩主播'), ('76', '中文字幕'), ('77', '主播诱惑'),
        ]},
        {'type_id': 'v_rb', 'type_name': '热播片库', 'filters': [
            ('79', '传媒剧情'), ('80', '抖阴短片'), ('81', 'AV解说'), ('82', '换脸明星'),
            ('83', 'VR视角'),
        ]},
        # ---- 图片区（1个一级，子分类用筛选面板）----
        {'type_id': 'image', 'type_name': '图片区', 'filters': [
            ('39', '美腿丝袜'), ('40', '网友自拍'), ('41', '清纯唯美'), ('42', '另类图片'),
            ('43', '卡通贴图'), ('44', '熟女乱伦'), ('17', '亚州图片'), ('18', '欧美图片'),
        ]},
        # ---- 小说区（1个一级，子分类用筛选面板）----
        {'type_id': 'novel', 'type_name': '小说区', 'filters': [
            ('45', '现代激情'), ('46', '古典武侠'), ('47', '暴力强奸'), ('48', '校园春色'),
            ('49', '家庭乱伦'), ('50', '长篇连载'), ('51', '情色幽默'), ('52', '淫妻交换'),
        ]},
    ]

    def _clean(self, text):
        if not text:
            return ''
        text = re.sub(r'<[^>]+>', '', text)
        text = html_mod.unescape(text)
        return text.strip()

    def init(self, extend=''):
        if hasattr(self, 'session') and self.session:
            try:
                self.session.close()
            except:
                pass
        self.session = requests.Session()
        if not self._update_host():
            pass  # 用默认域名

    # ===================== homeContent =====================
    def homeContent(self, filter_):
        classes = [{'type_id': c['type_id'], 'type_name': c['type_name']} for c in self.CATEGORIES]
        filters = {}
        for c in self.CATEGORIES:
            if 'filters' in c:
                filters[c['type_id']] = [{
                    'key': 'tid', 'name': '子分类',
                    'value': [{'n': '全部', 'v': ''}] + [{'n': name, 'v': tid} for tid, name in c['filters']]
                }]
        # 首页取推荐视频列表
        list_items = self._fetch_video_list()
        return {'class': classes, 'list': list_items[:20], 'filters': filters}

    def homeVideoContent(self):
        return {'list': self._fetch_video_list()[:20]}

    # ===================== categoryContent =====================
    def categoryContent(self, tid, pg, filter_=None, extend=''):
        page = int(pg) if pg else 1

        # 解析筛选值
        ext = extend
        if isinstance(filter_, dict) and filter_.get('tid'):
            ext = filter_['tid']
        if isinstance(ext, dict):
            ext = ext.get('tid', '')

        # --- 视频区：直接分类 or 筛选子分类 ---
        if tid.startswith('vod:') or tid.startswith('v_'):
            # 视频分组未选筛选时的默认父分类 id
            VOD_DEFAULTS = {
                'v_gc': '1', 'v_gq': '2', 'v_wb': '58', 'v_ts': '3',
                'v_zp': '69', 'v_rb': '78',
            }
            real_tid = tid.replace('vod:', '')
            if not real_tid.isdigit():
                real_tid = VOD_DEFAULTS.get(tid, '1')
            if ext and str(ext).isdigit():
                real_tid = str(ext)
            url = f'{self.host}/vodtype/{real_tid}-{page}.html' if page > 1 else f'{self.host}/vodtype/{real_tid}.html'
            html_content = self._fetch(url)
            items = self._parse_video_list(html_content) if html_content else []
            pagecount = self._extract_pagecount(html_content, real_tid) if html_content else page
            return {'list': items, 'page': page, 'pagecount': max(pagecount, page)}

        # --- 图片区 / 小说区：arttype，子分类用筛选 ---
        if tid == 'image':
            art_id = str(ext) if ext and str(ext).isdigit() else '5'  # 默认激情图区
        elif tid == 'novel':
            art_id = str(ext) if ext and str(ext).isdigit() else '38'  # 默认情色小说
        else:
            return {'list': [], 'page': page, 'pagecount': 1}

        url = f'{self.host}/arttype/{art_id}-{page}.html' if page > 1 else f'{self.host}/arttype/{art_id}.html'
        html_content = self._fetch(url)
        # 根据 tid 决定 vod_id 前缀：img_ 或 nov_
        prefix = 'img_' if tid == 'image' else 'nov_'
        is_image = (tid == 'image')
        items = self._parse_art_list(html_content, prefix, is_image) if html_content else []
        pagecount = self._extract_art_pagecount(html_content, art_id) if html_content else page
        return {'list': items, 'page': page, 'pagecount': max(pagecount, page), 'limit': 15}

    # ===================== detailContent =====================
    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, list) else ids)
        # 视频
        if vid.startswith('v_'):
            real_id = vid.replace('v_', '')
            html_content = self._fetch(f'{self.host}/voddetail/{real_id}.html')
            if html_content:
                return self._video_detail(real_id, html_content)
        # 图片（img_ 前缀来自图片区）
        if vid.startswith('img_'):
            real_id = vid.replace('img_', '')
            html_content = self._fetch(f'{self.host}/artdetail-{real_id}.html')
            if html_content:
                return self._img_detail(real_id, html_content)
        # 小说（nov_ 前缀来自小说区）
        if vid.startswith('nov_'):
            real_id = vid.replace('nov_', '')
            html_content = self._fetch(f'{self.host}/artdetail-{real_id}.html')
            if html_content:
                return self._novel_detail(real_id, html_content)
        return {'list': [{'vod_id': vid, 'vod_name': '加载失败', 'vod_play_from': '错误', 'vod_play_url': ''}]}

    # ===================== 视频列表解析 =====================
    def _fetch_video_list(self):
        html_content = self._fetch(self.host + '/')
        return self._parse_video_list(html_content) if html_content else []

    def _parse_video_list(self, html_content):
        items = []
        if not html_content:
            return items
        pattern = (r'<dl>\s*<dt[^>]*>.*?<a[^>]*href="/voddetail/(\d+)\.html"[^>]*>'
                   r'.*?<img[^>]*data-original="([^"]*)"[^>]*>.*?</a>.*?</dt>\s*<dd>\s*'
                   r'<a[^>]*href="/voddetail/\d+\.html"[^>]*>(.*?)</a>\s*</dd>\s*</dl>')
        for m in re.finditer(pattern, html_content, re.S):
            vid, img, title_block = m.groups()
            if not img.startswith('http'):
                img = urljoin(self.host, img)
            items.append({
                'vod_id': f'v_{vid}',
                'vod_name': self._clean(title_block) or '未知标题',
                'vod_pic': img,
            })
        return items

    # ===================== 图片列表解析（arttype 页） =====================
    def _parse_art_list(self, html_content, prefix='art_', is_image=False):
        items = []
        if not html_content:
            return items
        # arttype 页面 artdetail-ID.html（横杠格式）
        for m in re.finditer(r'<a[^>]*href="/artdetail-(\d+)\.html"[^>]*>(.*?)</a>', html_content, re.S):
            aid, block = m.groups()
            raw = html_mod.unescape(self._clean(block))
            if is_image:
                # 图片区：直接删掉日期
                date_m = re.match(r'\[\d{4}-\d{2}-\d{2}\]\s*(.*)', raw)
                title = date_m.group(1).strip() if date_m else raw
                short = title
                # 过滤空壳条目
                if short and len(short) < 4 and '【' not in short:
                    continue
            else:
                # 小说区：删掉日期和【作者：xxx】标记
                title = raw
                title = re.sub(r'\[\d{4}-\d{2}-\d{2}\]\s*', '', title)
                title = re.sub(r'【作者：[^】]*】', '', title)
                title = re.sub(r'【完】', '', title).strip()
                if title and len(title) < 20 and '【' not in title:
                    continue
            items.append({
                'vod_id': f'{prefix}{aid}',
                'vod_name': title or f'图集{aid}',
                'vod_pic': '',
            })
        return items

    # ===================== 视频详情 =====================
    def _video_detail(self, vid, html_content):
        title, cover = '', ''
        m = re.search(r'<h1[^>]*>(.*?)</h1>', html_content, re.S)
        if m:
            title = self._clean(m.group(1))
        if not title:
            m = re.search(r'<title>(.*?)</title>', html_content)
            if m:
                title = self._clean(m.group(1))
        m = re.search(r'<img[^>]*data-original="([^"]*)"[^>]*>', html_content)
        if m:
            cover = m.group(1)
        if not cover:
            m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html_content)
            if m:
                cover = m.group(1)
        if cover and not cover.startswith('http'):
            cover = urljoin(self.host, cover)

        buttons = re.findall(
            r'<div[^>]+class="item"[^>]*>\s*<a[^>]+href="(/vodplay/' + vid + r'[-_]\d+[-_]\d+\.html)"[^>]*>(.*?)</a>',
            html_content, re.S)
        if not buttons:
            buttons = re.findall(
                r'href="(/vodplay/' + vid + r'[^"]*)"[^>]*>(.*?)</a>', html_content, re.S)
        if not buttons:
            buttons = [(f'/vodplay/{vid}-1-1.html', '高清')]

        line_map = {}
        cache = {}
        for href, btn_name in buttons:
            # 播放源名统一为"高清"，不从HTML抓
            btn_name = '高清'

            play_url = urljoin(self.host, href)
            if href not in cache:
                play_html = self._fetch(play_url)
                m3u8_list = self._extract_m3u8(play_html) if play_html else []
                cache[href] = m3u8_list
            else:
                m3u8_list = cache[href]

            if m3u8_list:
                for i, m3u8 in enumerate(m3u8_list):
                    name = btn_name if i == 0 else f'{btn_name}_{i+1}'
                    if btn_name not in line_map:
                        line_map[btn_name] = []
                    line_map[btn_name].append((name, m3u8))
            else:
                if btn_name not in line_map:
                    line_map[btn_name] = []
                line_map[btn_name].append((btn_name, play_url))

        if not line_map:
            return {'list': [{'vod_id': f'v_{vid}', 'vod_name': title, 'vod_pic': cover,
                              'vod_play_from': '错误', 'vod_play_url': '未找到播放地址'}]}

        from_lines, url_lines = [], []
        for line_name, episodes in line_map.items():
            from_lines.append(line_name)
            url_lines.append('#'.join([f'{ep_name}${ep_url}' for ep_name, ep_url in episodes]))

        return {'list': [{'vod_id': f'v_{vid}', 'vod_name': title, 'vod_pic': cover,
                          'vod_play_from': '#'.join(from_lines),
                          'vod_play_url': '$$$'.join(url_lines)}]}

    # ===================== 图片/小说详情 =====================
    def _img_detail(self, vid, html_content):
        """图片集详情：提取正文图片"""
        title = ''
        m = re.search(r'<h1[^>]*>(.*?)</h1>', html_content, re.S)
        if m:
            title = html_mod.unescape(self._clean(m.group(1)))
        if not title:
            m = re.search(r'<title>(.*?)</title>', html_content)
            if m:
                title = self._clean(m.group(1))

        # 优先从正文容器 m1938ing 提取（隔离广告）
        content_area = re.search(r'<div[^>]+class="m1938ing"[^>]*>(.*?)</div>', html_content, re.S)
        if content_area:
            imgs = []
            for attr in ['src', 'data-original', 'data-src', 'original', 'data-url']:
                imgs.extend(re.findall(rf"""<img[^>]*{attr}=['"]([^'"]+)['"]""", content_area.group(1), re.I))
            real_imgs = []
            seen = set()
            for img in imgs:
                if img.startswith('//'): img = 'https:' + img
                if not img.startswith('http'): img = urljoin(self.host, img)
                if img not in seen:
                    seen.add(img)
                    real_imgs.append(img)
        else:
            real_imgs = []

        if real_imgs:
            pics = '&&'.join(real_imgs)
            play_url = f'查看$pics://{pics}'
            return {'list': [{'vod_id': f'img_{vid}', 'vod_name': title,
                              'vod_pic': real_imgs[0], 'vod_play_from': '图片', 'vod_play_url': play_url}]}
        return {'list': [{'vod_id': f'img_{vid}', 'vod_name': title, 'vod_play_from': '错误', 'vod_play_url': '无图片'}]}

    def _novel_detail(self, vid, html_content):
        """小说详情 - 完全照搬三三言情格式"""
        title = ''
        m = re.search(r'<h1[^>]*>(.*?)</h1>', html_content, re.S)
        if m:
            title = html_mod.unescape(self._clean(m.group(1)))
        if not title:
            m = re.search(r'<title>(.*?)</title>', html_content)
            if m:
                title = self._clean(m.group(1))

        # 从 m1938ing 提取正文
        content = ''
        m1938 = re.search(r'class="m1938ing"[^>]*>(.*?)</div>', html_content, re.S)
        if m1938:
            content = re.sub(r'<br\s*/?>', '\n', m1938.group(1))
            content = re.sub(r'<[^>]+>', '', content)
            content = html_mod.unescape(content).strip()
        if not content or len(content) < 20:
            for pat in [r'<div[^>]+id="content"[^>]*>(.*?)</div>',
                        r'<div[^>]+class="[^"]*content[^"]*"[^>]*>(.*?)</div>']:
                m = re.search(pat, html_content, re.S)
                if m:
                    content = re.sub(r'<[^>]+>', '', m.group(1)).strip()
                    if len(content) > 50:
                        break

        if not content or len(content) < 20:
            return {'list': []}

        # 构造章节 URL 列表（和三三言情完全一样的格式：章节名$完整URL）
        play_list = []
        chapters = re.split(r'\n\s*(第[一二三四五六七八九十百千\d]+[章集回节卷]：?[^\n]*)\n', content)
        if len(chapters) > 3:
            intro = chapters[0].strip()
            if intro and len(intro) > 20:
                play_list.append(f"内容简介${self.host}/artdetail-{vid}.html?ch=0")
            for i in range(1, len(chapters), 2):
                ch_name = chapters[i].strip()
                ch_idx = (i + 1) // 2
                if ch_name:
                    play_list.append(f"{ch_name}${self.host}/artdetail-{vid}.html?ch={ch_idx}")
        else:
            play_list.append(f"第1章${self.host}/artdetail-{vid}.html?ch=0")

        # vod_play_from 和 vod_play_url 完全对齐三三言情格式
        play_url = '#'.join(play_list)
        return {
            "list": [{
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": "",
                "vod_play_from": "小说",
                "vod_play_url": play_url
            }]
        }

    # ===================== 搜索 =====================
    def searchContent(self, key, quick, pg='1'):
        try:
            page = int(pg) if pg else 1
            url = f'{self.host}/vodsearch/-------------.html?wd={quote(key)}&page={page}'
            html_content = self._fetch(url)
            items = self._parse_video_list(html_content) if html_content else []
            return {'list': items, 'page': page, 'pagecount': page + 1}
        except:
            return {'list': [], 'page': int(pg) if pg else 1, 'pagecount': 1}

    # ===================== 播放地址提取 =====================
    def _extract_m3u8(self, html_content):
        urls = []
        if not html_content:
            return urls
        player_match = re.search(r'var\s+player_aaaa\s*=\s*({.*?});', html_content, re.S)
        if player_match:
            try:
                data = json.loads(player_match.group(1))
                raw = data.get('url', '')
                if raw:
                    decoded = unquote(raw)
                    if decoded.startswith('http'):
                        urls.append(decoded)
            except:
                pass
        urls.extend(re.findall(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html_content))
        if not urls:
            for scr in re.findall(r'<script[^>]*>(.*?)</script>', html_content, re.S):
                urls.extend(re.findall(r'''['"]url['"]\s*:\s*['"]([^'"]+\.m3u8[^'"]*)['"]''', scr))
        seen = set()
        return [u for u in urls if u.startswith('http') and u not in seen and not seen.add(u)]

    def playerContent(self, flag, id, vipFlags=None):
        # 小说：URL?ch=章节索引 → 请求 artdetail 提取指定章节
        # 兼容 shell 端 URL 编码（?→%3F, =→%3D）
        ch_match = re.search(r'artdetail-(\d+)\.html(?:\?|%3F)ch(?:=|%3D)(\d+)', id)
        if ch_match:
            try:
                art_id = ch_match.group(1)
                ch_idx = int(ch_match.group(2))
                html_content = self._fetch(f'{self.host}/artdetail-{art_id}.html')
                if not html_content:
                    return {"parse": 0, "playUrl": "", "url": "novel://" + json.dumps({"title": "加载失败", "content": "无法获取内容"}, ensure_ascii=False), "header": ""}
                # 提取全文
                content = ''
                m1938 = re.search(r'class="m1938ing"[^>]*>(.*?)</div>', html_content, re.S)
                if m1938:
                    content = re.sub(r'<br\s*/?>', '\n', m1938.group(1))
                    content = re.sub(r'<[^>]+>', '', content)
                    content = html_mod.unescape(content).strip()
                if not content:
                    for pat in [r'<div[^>]+id="content"[^>]*>(.*?)</div>',
                                r'<div[^>]+class="[^"]*content[^"]*"[^>]*>(.*?)</div>']:
                        m = re.search(pat, html_content, re.S)
                        if m:
                            content = re.sub(r'<[^>]+>', '', m.group(1)).strip()
                            if len(content) > 50:
                                break
                # 标题
                title_m = re.search(r'<h1[^>]*>(.*?)</h1>', html_content, re.S)
                title = html_mod.unescape(self._clean(title_m.group(1))) if title_m else '小说'
                # 章节分割
                chapters = re.split(r'\n\s*(第[一二三四五六七八九十百千\d]+[章集回节卷]：?[^\n]*)\n', content)
                if len(chapters) > 3 and ch_idx > 0:
                    ch_real_idx = ch_idx * 2 - 1
                    if ch_real_idx + 1 < len(chapters):
                        ch_name = chapters[ch_real_idx].strip()
                        ch_content = chapters[ch_real_idx + 1].strip()
                        data = {"title": ch_name, "content": ch_content[:15000]}
                    elif ch_real_idx < len(chapters):
                        data = {"title": chapters[ch_real_idx].strip(), "content": chapters[ch_real_idx].strip()[:15000]}
                    else:
                        data = {"title": "简介", "content": chapters[0].strip()[:15000]}
                else:
                    data = {"title": title, "content": content[:15000]}
                return {"parse": 0, "playUrl": "", "url": "novel://" + json.dumps(data, ensure_ascii=False), "header": ""}
            except Exception as e:
                return {"parse": 0, "playUrl": "", "url": "novel://" + json.dumps({"title": "错误", "content": str(e)[:500]}, ensure_ascii=False), "header": ""}
        # 小说直通
        if id.startswith('novel://'):
            return {'parse': 0, 'playUrl': '', 'url': id, 'header': ''}
        # 视频：m3u8/mp4
        if id.startswith('http') and ('.m3u8' in id or '.mp4' in id or '.ts' in id):
            if '.m3u8' in id:
                return {'parse': 0, 'url': self._proxy_m3u8_url(id, self.host),
                        'header': {'Referer': self.host, 'User-Agent': 'Mozilla/5.0'}}
            return {'parse': 0, 'url': id, 'header': {'Referer': self.host, 'User-Agent': 'Mozilla/5.0'}}
        return {'parse': 1, 'url': id, 'header': {'Referer': self.host, 'User-Agent': 'Mozilla/5.0'}}

    # ===================== localProxy =====================
    def localProxy(self, param):
        EMPTY_GIF = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
        if 'do=m3u8' in param:
            try:
                params = dict(p.split('=', 1) for p in param.split('&') if '=' in p)
                url = unquote(params.get('url', ''))
                referer = unquote(params.get('referer', self.host))
                if not url:
                    return [404, "text/plain", "missing url"]
                raw = self._get_m3u8_content(url, referer)
                if not raw:
                    return [404, "text/plain", "m3u8 download failed"]
                cleaned = self._clean_m3u8(raw, url, referer)
                return [200, "application/vnd.apple.mpegurl", cleaned]
            except:
                return [404, "text/plain", "proxy error"]
        if not param or not param.startswith('http'):
            return [200, 'image/gif', EMPTY_GIF]
        try:
            r = self.session.get(param, headers={'User-Agent': 'Mozilla/5.0', 'Referer': self.host + '/'},
                                 timeout=(10, 15))
            r.raise_for_status()
            return [200, r.headers.get('Content-Type', 'application/octet-stream'), r.content]
        except:
            return [200, 'image/gif', EMPTY_GIF]

    # ===================== 分页 =====================
    def _extract_pagecount(self, html_content, tid):
        if not html_content:
            return 1
        page_links = re.findall(rf'/vodtype/{tid}[-_](\d+)\.html', html_content)
        if page_links:
            return max(int(p) for p in page_links)
        return 1

    def _extract_art_pagecount(self, html_content, art_id):
        if not html_content:
            return 1
        page_links = re.findall(rf'/arttype/{art_id}-(\d+)\.html', html_content)
        if page_links:
            return max(int(p) for p in page_links)
        return 1

    # ===================== m3u8 广告清洗 =====================
    def _proxy_m3u8_url(self, url, referer=''):
        try:
            base = self.getProxyUrl()
            if '?' not in base:
                base += '?do=py'
            return base + '&do=m3u8&url=' + quote(url, safe='') + '&referer=' + quote(referer or self.host, safe='')
        except:
            return url

    def _get_m3u8_content(self, url, referer):
        try:
            resp = requests.get(url, headers={'Referer': referer, 'User-Agent': 'Mozilla/5.0'}, timeout=15)
            if resp.status_code == 200:
                if not resp.encoding or resp.encoding.lower() in ('iso-8859-1', 'latin-1'):
                    resp.encoding = resp.apparent_encoding
                return resp.text
        except:
            pass
        return None

    def _clean_m3u8(self, m3u8_text, m3u8_url='', referer='', skip_seconds=25):
        text = (m3u8_text or '').replace('\r', '')
        if '#EXT-X-STREAM-INF' in text:
            out = []
            for raw in text.splitlines():
                line = raw.strip()
                if not line:
                    continue
                if line.startswith('#'):
                    out.append(line)
                else:
                    abs_url = urljoin(m3u8_url, line)
                    if '.m3u8' in line.lower():
                        out.append(self._proxy_m3u8_url(abs_url, referer))
                    else:
                        out.append(abs_url)
            return '\n'.join(out) + '\n'

        header, segments, tail, media_sequence, target_duration = self._parse_m3u8_segments(text)
        if not segments:
            return text

        marker = self._main_path_marker(m3u8_url)
        stat = {}
        for seg in segments:
            key = self._segment_host_key(seg['uri'], m3u8_url)
            stat[key] = stat.get(key, 0.0) + float(seg.get('dur') or 0)
        main_key = max(stat.items(), key=lambda x: x[1])[0] if stat else ('', '')
        total_dur = sum(stat.values()) or 0
        main_dur = stat.get(main_key, 0)

        cleaned, removed = [], 0
        for idx, seg in enumerate(segments):
            key = self._segment_host_key(seg['uri'], m3u8_url)
            is_front = idx < 12
            abs_uri = urljoin(m3u8_url, seg.get('uri', ''))
            is_ad = self._is_ad_segment(seg['uri'], seg.get('dur'), seg.get('tags'))
            if marker and marker not in urlparse(abs_uri).path.lower():
                is_ad = True
            tags_text = '\n'.join(seg.get('tags') or []).upper()
            if is_front and 'METHOD=NONE' in tags_text and marker and marker not in urlparse(abs_uri).path.lower():
                is_ad = True
            if (not is_ad) and is_front and total_dur > 0 and main_dur >= total_dur * 0.6:
                if key != main_key and stat.get(key, 0) <= 90:
                    is_ad = True
            if is_ad:
                removed += 1
                continue
            seg['_idx'] = idx
            cleaned.append(seg)

        if removed == 0 and len(segments) > 4:
            acc, cut = 0.0, 0
            for idx, seg in enumerate(segments[:12]):
                key = self._segment_host_key(seg['uri'], m3u8_url)
                if key == main_key and acc >= 3:
                    break
                acc += float(seg.get('dur') or target_duration or 3)
                cut = idx + 1
                if acc >= skip_seconds:
                    break
            if cut > 0 and cut < len(segments):
                first_key = self._segment_host_key(segments[0]['uri'], m3u8_url)
                if first_key != main_key:
                    cleaned = segments[cut:]
                    removed = cut

        if not cleaned:
            cleaned = segments
            removed = 0

        new_lines = []
        has_m3u = False
        for line in header:
            if line.startswith('#EXTM3U'): has_m3u = True
            if line.startswith('#EXT-X-MEDIA-SEQUENCE') or line.startswith('#EXT-X-START'):
                continue
            if line.startswith('#EXT-X-KEY') and 'METHOD=NONE' in line.upper() and removed > 0:
                continue
            new_lines.append(line)
        if not has_m3u:
            new_lines.insert(0, '#EXTM3U')
        first_idx = cleaned[0].get('_idx', removed) if cleaned else removed
        new_lines.append(f'#EXT-X-MEDIA-SEQUENCE:{media_sequence + first_idx}')
        for seg in cleaned:
            for tag in seg.get('tags') or []:
                if tag.startswith('#EXT-X-KEY') or tag.startswith('#EXT-X-MAP'):
                    def _fix_uri(m):
                        return 'URI="' + urljoin(m3u8_url, m.group(1)) + '"'
                    tag = re.sub(r'URI="([^"]+)"', _fix_uri, tag)
                new_lines.append(tag)
            new_lines.append(urljoin(m3u8_url, seg.get('uri', '')))
        if tail:
            for line in tail:
                if line.startswith('#EXT-X-ENDLIST'):
                    new_lines.append(line)
        elif '#EXT-X-ENDLIST' in text:
            new_lines.append('#EXT-X-ENDLIST')
        return '\n'.join(new_lines) + '\n'

    def _parse_m3u8_segments(self, text):
        lines = [x.strip() for x in (text or '').replace('\r', '').split('\n') if x.strip()]
        header, segments, tail = [], [], []
        pending_tags = []
        media_sequence = 0
        target_duration = 0
        started = False
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith('#EXT-X-MEDIA-SEQUENCE'):
                try: media_sequence = int(line.split(':', 1)[1])
                except: pass
                if not started: header.append(line)
                else: pending_tags.append(line)
            elif line.startswith('#EXT-X-TARGETDURATION'):
                try: target_duration = float(line.split(':', 1)[1])
                except: pass
                if not started: header.append(line)
                else: pending_tags.append(line)
            elif line.startswith('#EXTINF'):
                started = True
                dur = target_duration or 3.0
                m = re.search(r'#EXTINF:\s*([\d.]+)', line)
                if m:
                    try: dur = float(m.group(1))
                    except: pass
                tags = pending_tags + [line]
                pending_tags = []
                uri = ''
                j = i + 1
                while j < len(lines):
                    if lines[j].startswith('#'):
                        tags.append(lines[j]); j += 1; continue
                    uri = lines[j]; break
                if uri:
                    segments.append({'tags': tags, 'uri': uri, 'dur': dur}); i = j
                else:
                    tail.extend(tags)
            elif line.startswith('#EXT-X-ENDLIST'):
                tail.append(line)
            elif line.startswith('#'):
                if started: pending_tags.append(line)
                else: header.append(line)
            else:
                started = True
                segments.append({'tags': pending_tags, 'uri': line, 'dur': target_duration or 3.0})
                pending_tags = []
            i += 1
        return header, segments, tail, media_sequence, target_duration

    def _is_ad_segment(self, uri, dur=0, prev_tags=None):
        u = (uri or '').strip().lower()
        if not u: return False
        if any(w in u for w in ['ad', 'ads', 'advert', 'sponsor', 'pre', 'preroll', '/gg/', '_gg', 'gg_', '/adv/', '/ad/', 'banner', 'promo']):
            return True
        try:
            if 0 < float(dur) <= 1.2: return True
        except: pass
        return False

    def _segment_host_key(self, uri, base_url):
        try:
            full = urljoin(base_url, uri)
            p = urlparse(full)
            return (p.netloc.lower(), re.sub(r'/[^/]*$', '/', (p.path or '/').lower()))
        except:
            return ('', '')

    def _main_path_marker(self, m3u8_url):
        try:
            p = urlparse(m3u8_url).path
            m = re.search(r'(/\d{8}/[^/]+/\d+kb/hls/)', p)
            if m: return m.group(1).lower()
            m = re.search(r'(/\d{8}/[^/]+/)', p)
            if m: return m.group(1).lower()
        except: pass
        return ''
