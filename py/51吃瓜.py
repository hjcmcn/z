# -*- coding: utf-8 -*-
# 51吃瓜网 TVBox 蜘蛛
# 站点: 51吃瓜网 (Typecho + Mirages 主题), 帖子页 /archives/{id}/
# 域名(用户给的 5 个同站镜像, 全部内置):
#   https://at.aygsjxzi.cc / https://chigua.com / https://51cg1.com
#   https://b79kj.avsedgssg.cc / https://amazing.mmxpvspw.cc
# 动态跟踪域名: 请求按当前域名优先, 失败自动切下一个镜像;
#   遇到 301 跳到新镜像时自动收编该域名并置顶(本站会不定期 301 轮换镜像,
#   实测 at.aygsjxzi.cc 曾 301 到 at.sckddzyb.cc); extend 可传 {"domain": "..."} 强制指定。
# 分类: 首页导航实测 26 个
# 结构: 列表 /category/{slug}/, 翻页 /category/{slug}/{pg}/ (注意不是 /page/);
#   搜索 /search/{词}/, 翻页 /search/{词}/{pg}/;
#   卡片 div.post-card + z-bg-loader-url 封面 + h2.post-card-title;
#   播放: 详情页 div.dplayer 的 data-config JSON 里 video.url 即 m3u8 直链(parse=0, auth_key 时效须现取现播)。
#   无 dplayer 的帖子为图文, 详情只给提示不给假链。

import json
import re
import time
import urllib.parse

try:
    from base.spider import Spider as _BaseSpider
except Exception:
    class _BaseSpider:
        pass

try:
    import requests as _requests
except Exception:
    _requests = None

try:
    import urllib.request as _urlreq
    import ssl as _ssl
    _CTX = _ssl._create_unverified_context()
except Exception:
    _urlreq = None
    _CTX = None

DOMAINS = [
    'https://at.aygsjxzi.cc',
    'https://chigua.com',
    'https://51cg1.com',
    'https://b79kj.avsedgssg.cc',
    'https://amazing.mmxpvspw.cc',
]

# 分类表: (slug, 名称)
CATEGORIES = [
    ('mrds', '每日大赛'), ('whhj', '网黄合集'), ('mrdg', '吃瓜榜单'),('xsxy', '学生校园'),
    ('qghj', '瓜友点播'), ('rdsj', '热门大瓜'), ('bkdg', '必看大瓜'),('jpll', '软萌甜妹'),
    ('ysyl', '成人视频'), ('lldd', '伦理道德'), ('gcjq', '国产视频'),
    ('thjx', '探花精选'), ('whhl', '网红黑料'), ('snsn', '骚男骚女'),
    ('whmx', '明星爆料'), ('hwcg', '海外吃瓜'), ('rrcg', '人人吃瓜'),
    ('ldcg', '领导干部'), ('sjb', '竞技吃瓜'), ('qubk', '吃瓜看戏'),
    ('dcbq', '擦边撩骚'), ('zzs', '性爱技巧'), ('cgxw', '吃瓜新闻'),
    ('yczq', '原创博主'), ('51djc', '51剧场'), ('51hd', '往期活动'),
]

UA = ('Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36')
_HEADERS = {'User-Agent': UA, 'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'zh-CN,zh;q=0.9', 'Accept-Encoding': 'gzip, deflate'}

_DOMAINS = list(DOMAINS)
_CUR = [0]
_SESSION = [None]


def _session():
    if _SESSION[0] is None and _requests is not None:
        try:
            _SESSION[0] = _requests.Session()
        except Exception:
            _SESSION[0] = False
    return _SESSION[0] or None


def _adopt(final_url):
    try:
        p = urllib.parse.urlparse(final_url)
        host = '%s://%s' % (p.scheme, p.netloc)
    except Exception:
        return
    if not host or host == 'https://':
        return
    if host in _DOMAINS:
        _DOMAINS.remove(host)
    _DOMAINS.insert(0, host)
    _CUR[0] = 0


def _get_once(url, timeout=12):
    """单次请求, 返回 (text, final_url), 失败返回 ('', url)。"""
    s = _session()
    try:
        if s is not None:
            try:
                import urllib3 as _u3
                _u3.disable_warnings()
            except Exception:
                pass
            r = s.get(url, headers=_HEADERS, timeout=timeout, verify=False)
            if r.status_code >= 500:
                return '', url
            return r.text or '', r.url or url
    except Exception:
        pass
    if _urlreq is not None:
        try:
            req = _urlreq.Request(url, headers=_HEADERS)
            with _urlreq.urlopen(req, timeout=timeout, context=_CTX) as r:
                raw = r.read()
                try:
                    import gzip as _gz
                    if r.headers.get('Content-Encoding') == 'gzip':
                        raw = _gz.decompress(raw)
                except Exception:
                    pass
                if r.status >= 500:
                    return '', url
                return raw.decode('utf-8', 'replace'), r.geturl() or url
        except Exception:
            return '', url
    return '', url


def _fetch(path):
    """动态域名: 从当前域名起逐个试, 成功即置顶, 跳转的新域名自动收编。"""
    order = list(range(len(_DOMAINS)))
    start = _CUR[0] % len(_DOMAINS)
    order = order[start:] + order[:start]
    for i in order:
        base = _DOMAINS[i]
        txt, final = _get_once(base + path)
        if txt and ('post-card' in txt or 'dplayer' in txt or 'Mirages' in txt):
            _CUR[0] = i
            if final and not final.startswith(base):
                _adopt(final)
            return txt
    return ''


def _parse_cards(html):
    out, seen = [], set()
    for m in re.finditer(r'post-card-(\d+)', html):
        vid = m.group(1)
        if vid in seen:
            continue
        seen.add(vid)
        seg = html[m.start():m.start() + 3000]
        t = re.search(r'class="post-card-title"[^>]*>([^<]+)</h2>', seg)
        if not t:
            continue
        c = re.search(r'z-bg-loader-url="([^"]+)"', seg)
        out.append({'vod_id': vid, 'vod_name': t.group(1).strip(),
                    'vod_pic': (c.group(1) if c else ''),
                    'vod_remarks': ''})
    return out


def _parse_dplayer(html):
    eps = []
    for m in re.finditer(r'<div\s+class="dplayer"[^>]*data-video_title="([^"]*)"[^>]*data-config=\'(.*?)\'\s*>',
                         html, re.S):
        title, cfg = m.group(1), m.group(2)
        url = ''
        try:
            j = json.loads(cfg)
            url = ((j.get('video') or {}).get('url') or '').replace('\\/', '/')
        except Exception:
            pass
        if not url:
            u = re.search(r'"url"\s*:\s*"(https:[^"]+?\.m3u8[^"]*)"', cfg)
            if u:
                url = u.group(1).replace('\\/', '/')
        if url:
            eps.append((title.strip() or '正片', url))
    if not eps:
        # 兜底: 无 data-video_title 的 dplayer 块
        for m in re.finditer(r'<div\s+class="dplayer"[^>]*data-config=\'(.*?)\'\s*>', html, re.S):
            cfg = m.group(1)
            url = ''
            try:
                j = json.loads(cfg)
                url = ((j.get('video') or {}).get('url') or '').replace('\\/', '/')
            except Exception:
                pass
            if not url:
                u = re.search(r'"url"\s*:\s*"(https:[^"]+?\.m3u8[^"]*)"', cfg)
                if u:
                    url = u.group(1).replace('\\/', '/')
            if url:
                eps.append(('正片', url))
    return eps


class Spider(_BaseSpider):
    searchable = 1
    quickSearch = 1
    filterable = 1
    changeable = 1

    def __init__(self):
        self._host = None

    def getName(self):
        return '51吃瓜网'

    def init(self, extend=""):
        try:
            ext = (extend or '').strip()
            if ext.startswith('{'):
                c = json.loads(ext)
                d = str(c.get('domain') or '').strip().rstrip('/')
                if d.startswith('http'):
                    if d in _DOMAINS:
                        _DOMAINS.remove(d)
                    _DOMAINS.insert(0, d)
                    _CUR[0] = 0
        except Exception:
            pass
        return None

    def manualVideoCheck(self):
        return None

    def destroy(self):
        return None

    def close(self):
        return None

    def getDependence(self):
        return []

    def proxy(self, param):
        return None

    def localProxy(self, param):
        return None

    def _classes(self):
        return [{'type_id': s, 'type_name': n} for s, n in CATEGORIES]

    def homeContent(self, filter=False):
        try:
            html = _fetch('/')
            lst = _parse_cards(html) if html else []
            if not lst:
                return {'class': self._classes(), 'filters': {},
                        'list': [{'vod_id': 'diag', 'vod_name': '[诊断] 首页未取到',
                                  'vod_pic': '', 'vod_remarks': '域名: ' + _DOMAINS[_CUR[0] % len(_DOMAINS)],
                                  'vod_content': '5 个镜像均未返回列表, 稍后重进自动换域名重试'}]}
            return {'class': self._classes(), 'filters': {}, 'list': lst}
        except Exception as e:
            return {'class': self._classes(), 'filters': {},
                    'list': [{'vod_id': 'diag', 'vod_name': '[诊断] 首页异常',
                              'vod_pic': '', 'vod_remarks': str(e)[:60]}]}

    def homeVideoContent(self):
        try:
            html = _fetch('/')
            lst = _parse_cards(html) if html else []
            return {'list': lst}
        except Exception:
            return {'list': []}

    def categoryContent(self, tid='mrds', pg='1', filter=False, extend=None):
        try:
            pg = int(pg or 1)
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1
        path = '/category/%s/' % tid if pg == 1 else '/category/%s/%d/' % (tid, pg)
        try:
            html = _fetch(path)
            lst = _parse_cards(html) if html else []
            if not lst:
                return {'list': [], 'page': pg, 'pagecount': max(pg - 1, 0),
                        'limit': 30, 'total': max(pg - 1, 0) * 30}
            pc = pg if len(lst) < 10 else 99999
            return {'list': lst, 'page': pg, 'pagecount': pc,
                    'limit': 30, 'total': pc * 30}
        except Exception:
            return {'list': [], 'page': pg, 'pagecount': max(pg - 1, 0),
                    'limit': 30, 'total': max(pg - 1, 0) * 30}

    def detailContent(self, ids):
        vid = str(ids[0]) if isinstance(ids, (list, tuple)) and ids else str(ids)
        if vid == 'diag' or not vid.isdigit():
            return {'list': [{'vod_id': vid, 'vod_name': '诊断卡',
                              'vod_pic': '', 'vod_content': '这是诊断卡片, 不是影片。',
                              'vod_play_from': '提示', 'vod_play_url': '无线路$diag'}]}
        try:
            html = _fetch('/archives/%s/' % vid)
            if not html:
                return {'list': [{'vod_id': vid, 'vod_name': '详情未取到',
                                  'vod_pic': '', 'vod_content': '详情页 5 个镜像均未返回',
                                  'vod_play_from': '提示', 'vod_play_url': '无线路$diag'}]}
            t = re.search(r'property="og:title" content="([^"]+)"', html)
            if not t:
                t = re.search(r'<title>([^<]*)</title>', html)
            name = (t.group(1).strip() if t else vid)
            name = re.sub(r'\s*\|\s*51吃瓜网\s*$', '', name)
            pic = ''
            og = re.search(r'property="og:image" content="([^"]+)"', html)
            if og and 'social-default' not in og.group(1):
                pic = og.group(1)
            if not pic:
                im = re.search(r'<img[^>]+src="(https?://[^"]+\.(?:jpe?g|png|webp)[^"]*)"', html)
                if im:
                    pic = im.group(1)
            eps = _parse_dplayer(html)
            if not eps:
                return {'list': [{'vod_id': vid, 'vod_name': name, 'vod_pic': pic,
                                  'vod_content': '本帖为图文, 无视频',
                                  'vod_play_from': '提示',
                                  'vod_play_url': '本帖为图文，无视频$none'}]}
            play_url = '#'.join('%s$%s' % (n, u) for n, u in eps)
            return {'list': [{'vod_id': vid, 'vod_name': name, 'vod_pic': pic,
                              'vod_play_from': '视频', 'vod_play_url': play_url}]}
        except Exception as e:
            return {'list': [{'vod_id': vid, 'vod_name': '详情异常',
                              'vod_pic': '', 'vod_content': str(e)[:80],
                              'vod_play_from': '提示', 'vod_play_url': '无线路$diag'}]}

    def searchContent(self, key='', quick=False, pg='1'):
        try:
            pg = int(pg or 1)
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1
        q = urllib.parse.quote(str(key or ''))
        path = '/search/%s/' % q if pg == 1 else '/search/%s/%d/' % (q, pg)
        try:
            html = _fetch(path)
            lst = _parse_cards(html) if html else []
            return {'list': lst, 'page': pg, 'pagecount': pg if len(lst) < 10 else 99999,
                    'limit': 30, 'total': 0}
        except Exception:
            return {'list': []}

    def playerContent(self, flag='', id='', vipFlags=None):
        try:
            url = (id or '').strip()
            if url.startswith('http') and '.m3u8' in url:
                return {'parse': 0, 'url': url, 'header': {'User-Agent': UA}}
            return {'parse': 0, 'url': '', 'header': {}}
        except Exception:
            return {'parse': 0, 'url': '', 'header': {}}

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)

        def _noop(*a, **k):
            return None
        return _noop


def _sp():
    s = Spider()
    return s


def homeContent(filter=False):
    return _sp().homeContent(filter)


def homeVideoContent():
    return _sp().homeVideoContent()


def categoryContent(tid, pg, filter=False, extend=None):
    return _sp().categoryContent(tid, pg, filter, extend)


def detailContent(ids):
    return _sp().detailContent(ids)


def searchContent(key, quick=False, pg='1'):
    return _sp().searchContent(key, quick, pg)


def playerContent(flag, id, vipFlags=None):
    return _sp().playerContent(flag, id, vipFlags)
