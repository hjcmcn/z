# -*- coding: utf-8 -*-
# TVBox / 影视仓 / OK影视 Python 标准爬虫
import sys
import re
import json
import base64
import html
from urllib.parse import quote, unquote, urljoin, urlparse, urlunparse

sys.path.append('..')
try:
    from base.spider import Spider
except Exception:
    class Spider(object):
        pass


class Spider(Spider):
    def getName(self):
        return 'N2影视'

    def init(self, extend=''):
        self.last_error = ''
        self.load_extend(extend)

    # host 只是启动默认值；真正使用前会通过 ensure_host 实时探测当前内容域名。
    # 旧域名 o4z6i / n2d4z 已变成入口跳转，保留在 entry_hosts 用来发现新域名。
    host = 'https://www.c9z7j.top'
    content_hosts = [
        'https://www.c9z7j.top',
        'https://www.j2r7q.top',
    ]
    entry_hosts = [
        'https://www.o4z6i.top',
        'https://www.n2d4z.top',
        'https://www.c9z7j.top',
        'https://www.j2r7q.top',
    ]

    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 12; Mobile) AppleWebKit/537.36 Chrome/120.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Connection': 'close',
    }

    classes = [
        {'type_name': '最新剧情', 'type_id': 'juqing'},
        {'type_name': '最新电影', 'type_id': 'shipin'},
        {'type_name': '最新精选', 'type_id': 'jingpin'},
        {'type_name': '剧情-麻豆传媒', 'type_id': 'juqing|麻豆传媒'},
        {'type_name': '剧情-天美传媒', 'type_id': 'juqing|天美传媒'},
        {'type_name': '剧情-星空果冻', 'type_id': 'juqing|星空果冻'},
        {'type_name': '剧情-蜜桃精东', 'type_id': 'juqing|蜜桃精东'},
        {'type_name': '剧情-韩国伦理', 'type_id': 'juqing|韩国伦理'},
        {'type_name': '剧情-COSPLAY', 'type_id': 'juqing|COSPLAY'},
        {'type_name': '剧情-经典三级', 'type_id': 'juqing|经典三级'},
        {'type_name': '剧情-中文字幕', 'type_id': 'juqing|中文字幕'},
        {'type_name': '电影-日本av', 'type_id': 'shipin|日本av'},
        {'type_name': '电影-韩国热舞', 'type_id': 'shipin|韩国热舞'},
        {'type_name': '电影-欧美精品', 'type_id': 'shipin|欧美精品'},
        {'type_name': '电影-动漫电影', 'type_id': 'shipin|动漫电影'},
        {'type_name': '电影-国产自拍', 'type_id': 'shipin|国产自拍'},
        {'type_name': '电影-岛国无码', 'type_id': 'shipin|岛国无码'},
        {'type_name': '电影-JVID', 'type_id': 'shipin|JVID'},
        {'type_name': '电影-SM调教', 'type_id': 'shipin|SM调教'},
        {'type_name': '精品-软萌福利姬', 'type_id': 'jingpin|软萌福利姬'},
        {'type_name': '精品-黑料头条', 'type_id': 'jingpin|黑料头条'},
        {'type_name': '精品-明星AI', 'type_id': 'jingpin|明星AI'},
        {'type_name': '精品-人妖伪娘', 'type_id': 'jingpin|人妖伪娘'},
        {'type_name': '精品-onlyfans', 'type_id': 'jingpin|onlyfans'},
        {'type_name': '精品-探花系列', 'type_id': 'jingpin|探花系列'},
        {'type_name': '精品-主播大秀', 'type_id': 'jingpin|主播大秀'},
        {'type_name': '精品-韩国主播', 'type_id': 'jingpin|韩国主播'},
    ]

    filters = {
        'juqing': [{'key': 'tag', 'name': '剧情筛选', 'value': [
            {'n': '全部', 'v': ''}, {'n': '麻豆传媒', 'v': '麻豆传媒'}, {'n': '天美传媒', 'v': '天美传媒'},
            {'n': '星空果冻', 'v': '星空果冻'}, {'n': '蜜桃精东', 'v': '蜜桃精东'}, {'n': '韩国伦理', 'v': '韩国伦理'},
            {'n': 'COSPLAY', 'v': 'COSPLAY'}, {'n': '经典三级', 'v': '经典三级'}, {'n': '中文字幕', 'v': '中文字幕'},
        ]}],
        'shipin': [{'key': 'tag', 'name': '电影筛选', 'value': [
            {'n': '全部', 'v': ''}, {'n': '日本av', 'v': '日本av'}, {'n': '韩国热舞', 'v': '韩国热舞'},
            {'n': '欧美精品', 'v': '欧美精品'}, {'n': '动漫电影', 'v': '动漫电影'}, {'n': '国产自拍', 'v': '国产自拍'},
            {'n': '岛国无码', 'v': '岛国无码'}, {'n': 'JVID', 'v': 'JVID'}, {'n': 'SM调教', 'v': 'SM调教'},
        ]}],
        'jingpin': [{'key': 'tag', 'name': '精品筛选', 'value': [
            {'n': '全部', 'v': ''}, {'n': '软萌福利姬', 'v': '软萌福利姬'}, {'n': '黑料头条', 'v': '黑料头条'},
            {'n': '明星AI', 'v': '明星AI'}, {'n': '人妖伪娘', 'v': '人妖伪娘'}, {'n': 'onlyfans', 'v': 'onlyfans'},
            {'n': '探花系列', 'v': '探花系列'}, {'n': '主播大秀', 'v': '主播大秀'}, {'n': '韩国主播', 'v': '韩国主播'},
        ]}],
    }

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
        html_text = self.fetch(self.host + '/index/home.html', require_video=True)
        vods = self.parse_vod_list(html_text)
        if not vods:
            vods = [self.debug_vod('首页无数据', self.host + '/index/home.html', html_text)]
        return {'list': vods[:30]}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = int(pg or 1)
            channel, tag = self.split_tid(tid)
            if isinstance(extend, dict) and extend.get('tag'):
                tag = extend.get('tag') or ''
            url = self.build_list_url(channel, tag, pg)
            html_text = self.fetch(url, require_video=True)
            vods = self.parse_vod_list(html_text)
            total = self.parse_total_page(html_text)
            if (not vods) and pg == 1:
                vods = [self.debug_vod('分类无数据', url, html_text)]
            return {
                'page': pg,
                'pagecount': total if total > 0 else (pg + 1 if vods else pg),
                'limit': 20,
                'total': (total if total > 0 else pg + 1) * 20,
                'list': vods,
            }
        except Exception as e:
            return {'page': 1, 'pagecount': 1, 'limit': 20, 'total': 1, 'list': [self.debug_vod('分类异常', str(e), '')]}

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
        url = self.abs_url(vod_id)
        html_text = self.fetch(url)
        title = self.parse_detail_title(html_text) or self.title_from_id(vod_id)
        pic = self.parse_detail_pic(html_text)
        date = self.search_first(r'<div class=["\']video-item-date["\']>([^<]+)', html_text)
        vod = {
            'vod_id': vod_id,
            'vod_name': title,
            'vod_pic': pic,
            'type_name': '',
            'vod_year': date or '',
            'vod_area': '',
            'vod_remarks': date or '播放',
            'vod_actor': '',
            'vod_director': '',
            'vod_content': title,
            'vod_play_from': '线路一$$$线路二',
            'vod_play_url': '播放$%s#备用$%s' % (vod_id + '@1', vod_id + '@2'),
        }
        return {'list': [vod]}

    def searchContent(self, key, quick, pg='1'):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg):
        pg = int(pg or 1)
        self.ensure_host()
        vods = []
        urls = []
        for code in ['juqing', 'shipin', 'jingpin']:
            url = self.host + '/' + self.encode_path('/search/%s-%s-%s.html' % (code, key, pg)) + '.html'
            urls.append(url)
            text = self.fetch(url)
            vods.extend(self.parse_search_json(text, code))
        vods = self.dedupe(vods)
        if not vods and pg == 1:
            vods = [self.debug_vod('搜索无数据', ' ; '.join(urls), '')]
        return {'page': pg, 'pagecount': 1, 'limit': 20, 'total': len(vods), 'list': vods}

    def playerContent(self, flag, id, vipFlags):
        if str(id).startswith('debug$'):
            return {'parse': 0, 'playUrl': '', 'url': '', 'header': {}}
        if '@' in id:
            page_id, road = id.rsplit('@', 1)
        else:
            page_id, road = id, '1'
        page_url = self.abs_url(page_id)
        html_text = self.fetch(page_url)
        video = self.b64_from_js(html_text, 'video')
        host1 = self.b64_from_js(html_text, 'm3u8_host')
        host2 = self.b64_from_js(html_text, 'm3u8_host1')
        play_host = host1 if str(road) == '1' else (host2 or host1)
        play_url = urljoin(play_host or self.host, video or '')
        return {
            'parse': 0,
            'playUrl': '',
            'url': play_url,
            'header': {
                'User-Agent': self.headers['User-Agent'],
                'Referer': page_url,
            },
        }

    def localProxy(self, params):
        return [404, 'text/plain', '']

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
            text, final_url = self.fetch_once(h + '/index/home.html')
            if self.looks_like_video_page(text):
                self.host = self.normalize_host(final_url) or h
                return self.host
        # 已有内容域名失效时，从入口域名、跳转结果、页面里的链接实时发现新域名。
        for h in self.discover_hosts():
            text, final_url = self.fetch_once(h + '/index/home.html')
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
            for path in ['/', '/enter/index.html', '/index/home.html']:
                text, final_url = self.fetch_once(h + path)
                final_host = self.normalize_host(final_url)
                if final_host:
                    found.append(final_host)
                # 入口页或脚本里如果出现完整域名，也加入候选。
                for u in re.findall(r'https?://[A-Za-z0-9.-]+', text or ''):
                    uh = self.normalize_host(u)
                    if uh and uh.endswith('.top'):
                        found.append(uh)
                # 有些入口页只写 //www.xxx.top。
                for u in re.findall(r'//[A-Za-z0-9.-]+\.top', text or ''):
                    uh = self.normalize_host('https:' + u)
                    if uh:
                        found.append(uh)
        # 新发现的域名排前面，下一次直接使用；不把失效的启动 host 强行塞进内容域名池。
        hosts = self.unique_hosts(found)
        if hosts:
            self.content_hosts = self.unique_hosts(hosts + self.content_hosts)
        return hosts

    def fetch(self, url, require_video=False):
        self.last_error = ''
        if require_video:
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
            if (not require_video) or self.looks_like_video_page(text):
                return text
        return best

    def fetch_once(self, url):
        errors = []
        headers = self.get_headers(url)
        try:
            from urllib.request import Request, urlopen
            req = Request(url, headers=headers)
            with urlopen(req, timeout=8) as r:
                return self.to_text(r.read()), getattr(r, 'url', url)
        except Exception as e:
            errors.append('urllib=' + repr(e))
        try:
            import requests
            r = requests.get(url, headers=headers, timeout=8, allow_redirects=True)
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

    def build_list_url(self, channel, tag, pg):
        pg = int(pg or 1)
        if tag:
            path = '/%s/list-%s.html' % (channel, tag) if pg <= 1 else '/%s/list-%s-%s.html' % (channel, tag, pg)
        else:
            path = '/%s/list.html' % channel if pg <= 1 else '/%s/list-%s.html' % (channel, pg)
        return self.host + '/' + self.encode_path(path) + '.html'

    def encode_path(self, path):
        return 'cYc' + base64.b64encode(path.encode('utf-8')).decode('utf-8')

    def candidate_urls(self, url):
        url = self.abs_url(url)
        out = []
        for h in self.unique_hosts([self.host] + self.content_hosts):
            for v in self.url_variants(self.replace_host(url, h)):
                out.append(v)
        return self.unique_urls(out)

    def url_variants(self, url):
        out = [url]
        try:
            raw = unquote(url)
            out.append(raw)
            p = urlparse(raw)
            out.append(urlunparse((p.scheme, p.netloc, quote(p.path, safe='/%+='), p.params, p.query, p.fragment)))
            out.append(urlunparse((p.scheme, p.netloc, quote(p.path, safe='/'), p.params, p.query, p.fragment)))
        except Exception:
            pass
        return self.unique_urls(out)

    def parse_vod_list(self, html_text):
        vods = []
        if not html_text:
            return vods
        blocks = re.findall(r'<a\b[^>]*class=["\'][^"\']*\bvideo-item\b[^"\']*["\'][\s\S]*?</a>', html_text)
        for block in blocks:
            href = self.search_first(r'href=["\']([^"\']+)["\']', block)
            if not href:
                continue
            pic = self.search_first(r'<img[^>]+data-base64=["\']([^"\']+)["\']', block)
            title_enc = self.search_first(r'<div[^>]+video-item-title[^>]+title=["\']([^"\']*)["\']', block)
            title = self.decode_title(title_enc)
            if not title:
                title = self.clean_text(self.search_first(r'<div[^>]+video-item-title[^>]*>([\s\S]*?)</div>', block))
            date = self.search_first(r'<div class=["\']video-item-date["\']>([^<]+)', block)
            if not title:
                title = self.title_from_id(href)
            vods.append({
                'vod_id': href,
                'vod_name': title,
                'vod_pic': self.abs_url(pic),
                'vod_remarks': date or '播放',
            })
        return self.dedupe(vods)

    def parse_search_json(self, text, default_channel):
        vods = []
        try:
            data = json.loads(text or '[]')
        except Exception:
            return vods
        if not isinstance(data, list):
            return vods
        for item in data:
            if not isinstance(item, dict):
                continue
            vid = item.get('id')
            channel = item.get('channel') or default_channel
            if not vid or channel not in ['juqing', 'shipin', 'jingpin']:
                continue
            title = self.decode_title(item.get('title') or '') or ('视频' + str(vid))
            pic = item.get('thumb') or ''
            try:
                date = self.format_date(int(item.get('insert_time') or 0))
            except Exception:
                date = ''
            vods.append({
                'vod_id': '/' + self.encode_path('/%s/play-%s.html' % (channel, vid)) + '.html',
                'vod_name': title,
                'vod_pic': self.abs_url(pic),
                'vod_remarks': date or '播放',
            })
        return vods

    def parse_total_page(self, html_text):
        nums = re.findall(r'title=["\']第"?(\d+)"?页["\']', html_text or '')
        nums += re.findall(r'>(\d+)</a>', html_text or '')
        arr = []
        for n in nums:
            try:
                arr.append(int(n))
            except Exception:
                pass
        return max(arr) if arr else 0

    def parse_detail_title(self, html_text):
        play_title = self.search_first(r'<div class=["\']play-title["\'][\s\S]*?title=["\']([^"\']+)["\']', html_text or '')
        txt = self.decode_title(play_title)
        if txt:
            return txt
        candidates = re.findall(r'class=["\'][^"\']*dec-ti[^"\']*["\'][^>]*title=["\']([^"\']+)["\']', html_text or '')
        decoded = []
        for item in candidates:
            txt = self.decode_title(item)
            if txt:
                decoded.append(txt)
        bad = set(['剧情区', '电影区', '精品区', '图片区', '小说区', '撸撸区', '博彩区', '特色区', '线路一', '线路二', '中文字幕'])
        for txt in decoded:
            if txt in bad or '首页' in txt:
                continue
            if len(txt) >= 18 or re.search(r'[A-Z]{2,6}[-_ ]?\d{2,}', txt):
                return txt
        for txt in decoded:
            if txt not in bad and '首页' not in txt and len(txt) > 2:
                return txt
        return ''

    def parse_detail_pic(self, html_text):
        pic = self.search_first(r'<img[^>]+data-base64=["\']([^"\']+)["\']', html_text or '')
        return self.abs_url(pic)

    def b64_from_js(self, html_text, var_name):
        pattern = r'var\s+' + re.escape(var_name) + r'\s*=\s*decodeString\([\'"]([^\'"]+)[\'"]\)'
        enc = self.search_first(pattern, html_text or '')
        return self.decode_base64_utf8(enc) if enc else ''

    def decode_title(self, data):
        data = html.unescape(data or '').strip()
        if not data:
            return ''
        if self.has_cn(data):
            return data
        txt = self.decode_base64_utf8(data)
        if txt and self.has_readable(txt):
            return txt
        try:
            from Crypto.Cipher import AES
            from Crypto.Util.Padding import unpad
            key = base64.b64decode('SWRUSnEwSGtscHVJNm11OGlCJU9PQCF2ZF40SyZ1WFc=')
            iv = base64.b64decode('JDB2QGtySDdWMg==') + b'883346'
            raw = base64.b64decode(data + '===')
            dec = unpad(AES.new(key, AES.MODE_CBC, iv).decrypt(raw), AES.block_size)
            return dec.decode('utf-8', 'ignore').replace('"', '').strip()
        except Exception:
            return ''

    def decode_base64_utf8(self, data):
        try:
            return base64.b64decode((data or '') + '===').decode('utf-8')
        except Exception:
            return ''

    def split_tid(self, tid):
        if '|' in tid:
            return tid.split('|', 1)
        return tid, ''

    def title_from_id(self, href):
        try:
            s = unquote(href or '')
            s = s.rsplit('.html', 1)[0].rsplit('/', 1)[-1]
            if s.startswith('cYc'):
                path = base64.b64decode(s[3:] + '===').decode('utf-8')
                m = re.search(r'play-(\d+)', path)
                if m:
                    return '视频' + m.group(1)
        except Exception:
            pass
        return '视频'

    def abs_url(self, url):
        if not url:
            return ''
        url = html.unescape(url)
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('http://') or url.startswith('https://'):
            return url
        return urljoin(self.host, url)

    def replace_host(self, url, host):
        try:
            p = urlparse(url)
            hp = urlparse(host)
            return urlunparse((hp.scheme, hp.netloc, p.path, p.params, p.query, p.fragment))
        except Exception:
            return url

    def get_headers(self, referer=''):
        h = dict(self.headers)
        h['Referer'] = referer if str(referer).startswith('http') else self.host + '/index/home.html'
        return h

    def normalize_host(self, url):
        try:
            if not url:
                return ''
            if not str(url).startswith('http'):
                url = 'https://' + str(url).strip().strip('/')
            p = urlparse(str(url).strip())
            if not p.scheme or not p.netloc:
                return ''
            return p.scheme + '://' + p.netloc
        except Exception:
            return ''

    def unique_hosts(self, hosts):
        out, seen = [], set()
        for h in hosts:
            h = self.normalize_host(h)
            if h and h not in seen:
                seen.add(h)
                out.append(h)
        return out

    def unique_urls(self, urls):
        out, seen = [], set()
        for u in urls:
            if u and u not in seen:
                seen.add(u)
                out.append(u)
        return out

    def response_to_text(self, rsp, url):
        if rsp is None:
            return '', url
        if isinstance(rsp, dict):
            return self.to_text(rsp.get('content') or rsp.get('body') or rsp.get('text') or ''), rsp.get('url') or url
        if isinstance(rsp, (str, bytes)):
            return self.to_text(rsp), url
        for key in ('text', 'content', 'body'):
            try:
                data = getattr(rsp, key)
                if data:
                    return self.to_text(data), getattr(rsp, 'url', url)
            except Exception:
                pass
        return self.to_text(rsp), getattr(rsp, 'url', url)

    def to_text(self, data):
        if data is None:
            return ''
        if isinstance(data, bytes):
            for enc in ('utf-8', 'gbk', 'gb18030'):
                try:
                    return data.decode(enc)
                except Exception:
                    pass
            return data.decode('utf-8', 'ignore')
        return str(data)

    def clean_text(self, text):
        text = re.sub(r'<[^>]+>', ' ', text or '')
        text = html.unescape(text)
        return re.sub(r'\s+', ' ', text).strip()

    def format_date(self, ts):
        try:
            import time
            return time.strftime('%Y-%m-%d', time.localtime(int(ts)))
        except Exception:
            return ''

    def search_first(self, pattern, text):
        m = re.search(pattern, text or '', re.S)
        return html.unescape(m.group(1).strip()) if m else ''

    def has_cn(self, text):
        return bool(re.search(r'[\u4e00-\u9fff]', text or ''))

    def has_readable(self, text):
        return bool(re.search(r'[\u4e00-\u9fffA-Za-z0-9]', text or ''))

    def looks_like_video_page(self, text):
        return bool(text and ('video-item' in text or 'data-base64' in text or 'm3u8_host' in text))

    def dedupe(self, vods):
        seen, out = set(), []
        for v in vods:
            vid = v.get('vod_id')
            if vid and vid not in seen:
                seen.add(vid)
                out.append(v)
        return out

    def debug_vod(self, title, url, html_text):
        info = [
            title,
            'host=' + str(self.host),
            'url=' + str(url),
            'html_len=' + str(len(html_text or '')),
            'video_item=' + str((html_text or '').count('video-item')),
            'data_base64=' + str((html_text or '').count('data-base64')),
            'm3u8_host=' + str((html_text or '').count('m3u8_host')),
            'error=' + str(getattr(self, 'last_error', '')),
            'snippet=' + self.clean_text((html_text or '')[:180]),
        ]
        msg = ' | '.join(info)
        return {'vod_id': 'debug$' + msg, 'vod_name': '【诊断】' + msg[:180], 'vod_pic': '', 'vod_remarks': '把这条内容发给我'}
