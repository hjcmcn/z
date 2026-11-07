# coding=utf-8

#  注意:player_aaaa 实测 encrypt=0,url 即 m3u8 直链 parse=0;本站更新极快,最新分类 p1/p2 之间插新视频致序号移位属正常
import sys
import re
import json
import requests
import urllib.parse
from requests.adapters import HTTPAdapter
try:
    from requests.packages.urllib3.util.retry import Retry
except Exception:
    Retry = None
from base.spider import Spider

class Spider(Spider):

    # 壳子开关全开
    searchable = 1
    quickSearch = 1
    filterable = 1
    changeable = 1

    def __init__(self):
        # 预置 None,避 __getattr__ 吞属性陷阱(懒取用 is None 判断)
        self.site_url = None
        self.headers = None
        self.sess = None

    def _ensure(self):
        if self.site_url is None:
            self.init()

    def __getattr__(self, name):
        # _ 开头名字直接抛,避免吞掉未定义属性导致懒建误判
        if name.startswith('_'):
            raise AttributeError(name)
        def _noop(*args, **kwargs):
            return None
        return _noop

    def getName(self):
        return "TOPTV"

    def init(self, extend=""):
        try:
            super().init(extend)
        except Exception:
            pass
        self.site_url = "https://toptv15.cyou"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.site_url,
            "Accept-Encoding": "gzip, deflate"
        }
        self.sess = requests.Session()
        if Retry is not None:
            try:
                self.sess.mount("https://", HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1)))
            except Exception:
                pass

    def isVideoFormat(self, url):
        return True

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def close(self):
        self.destroy()

    def getDependence(self):
        return []

    def proxy(self, param):
        return [404, "text/plain", ""]

    def localProxy(self, param):
        return [404, "text/plain", ""]

    def fetch(self, url, timeout=10):
        self._ensure()
        try:
            res = self.sess.get(url, headers=self.headers, timeout=timeout, verify=False)
            res.encoding = "utf-8"
            return res
        except Exception:
            return None

    def _abs(self, url):
        if not url:
            return ""
        if url.startswith("http"):
            return url
        if url.startswith("/"):
            return self.site_url.rstrip("/") + url
        return self.site_url + "/" + url

    def _parse_list(self, html):
        # 卡片 pattern(实测 20/20):href -> data-original -> vod-name 顺序
        video_list = []
        pattern = r'href="(/index.php/vod/detail/id/(\d+).html)".*?data-original="(.*?)".*?vod-name.*?>(.*?)<'
        matches = re.findall(pattern, html or '', re.S)
        for href, v_id, pic, name in matches:
            video_list.append({
                "vod_id": v_id,
                "vod_name": name.strip() or "视频",
                "vod_pic": pic if pic.startswith("http") else self._abs(pic),
                "vod_remarks": ""
            })
        return video_list

    def _pagecount(self, html, kind, key=""):
        # pager 真值:分类 /page/N.html、搜索 /search/page/N/wd/;另认"共N页";取不到回 999
        try:
            if kind == "search":
                nums = [int(x) for x in re.findall(r'/search/page/(\d+)/wd/', html or '')]
            else:
                nums = [int(x) for x in re.findall(r'/page/(\d+)\.html', html or '')]
            if nums:
                return max(nums)
            m = re.search(r'共\s*(\d+)\s*页', html or '')
            if m:
                return int(m.group(1))
        except Exception:
            pass
        return 999

    def homeContent(self, filter=False):
        cate_list = [
            {"type_name": "国产自拍", "type_id": "1"},
            {"type_name": "国产传媒", "type_id": "2"},
            {"type_name": "探花系列", "type_id": "3"},
            {"type_name": "人妻熟女", "type_id": "4"},
            {"type_name": "日本无码", "type_id": "5"},
            {"type_name": "美乳巨乳", "type_id": "6"},
            {"type_name": "强制侵犯", "type_id": "7"},
            {"type_name": "制服诱惑", "type_id": "8"},
            {"type_name": "绝色佳人", "type_id": "9"},
            {"type_name": "家庭乱伦", "type_id": "10"},
            {"type_name": "绝顶潮吹", "type_id": "11"},
            {"type_name": "网红主播", "type_id": "12"}
        ]
        return {"class": cate_list}

    def homeVideoContent(self):
        self._ensure()
        try:
            return {'list': self.categoryContent('1', '1', False, None)['list']}
        except Exception:
            return {'list': []}

    def categoryContent(self, tid='1', pg='1', filter=False, extend=None):
        self._ensure()
        pg = int(pg) if str(pg).isdigit() else 1
        if pg < 1:
            pg = 1
        list_url = f"{self.site_url}/index.php/vod/type/id/{tid}/page/{pg}.html"
        res = self.fetch(list_url)
        video_list = []
        pagecount = 999
        if res:
            video_list = self._parse_list(res.text)
            pagecount = self._pagecount(res.text, "category")
        return {'list': video_list, 'page': pg, 'pagecount': pagecount, 'limit': 20, 'total': 9999}

    def detailContent(self, ids):
        self._ensure()
        if not ids:
            return {'list': []}
        vod_id = ids[0]
        res = self.fetch(f"{self.site_url}/index.php/vod/detail/id/{vod_id}.html")
        if not res:
            return {'list': []}
        html = res.text
        # 标题:h1"资源名称: X"为准(原 vod-name pattern 抓的是相关视频)
        name = ""
        hm = re.search(r'<h1[^>]*>\s*资源名称[:：]\s*(.*?)</h1>', html, re.S)
        if hm:
            name = hm.group(1).strip()
        if not name:
            tm = re.search(r'<title>([^<]*)</title>', html)
            if tm:
                name = tm.group(1).replace("播放地址：", "").replace("-TOPTV", "").strip()
        if not name:
            name = "视频详情"
        # 封面:播放区 poster(/play/N.html 内 img);相关视频的 data-original 绝不能当封面
        pic = ""
        pm = re.search(r'<a[^>]*href="/play/\d+\.html"[^>]*>\s*<img[^>]+src="([^"]+)"', html)
        if pm:
            pic = pm.group(1)
        if pic and not pic.startswith("http"):
            pic = self._abs(pic)
        # 播放列表:允许 <a> 带其他属性;同 v-s-n 重复按钮去重(站模板会把同一地址印两遍)
        play_urls = []
        seen = set()
        play_matches = re.findall(r'href="(/index.php/vod/play/id/(\d+)/sid/(\d+)/nid/(\d+)\.html)"[^>]*>([^<]*)<', html)
        for href, v_id, s_id, n_id, label in play_matches:
            key = (v_id, s_id, n_id)
            if key in seen:
                continue
            seen.add(key)
            play_urls.append(f"{label.strip() or '播放'}${v_id}-{s_id}-{n_id}")
        if not play_urls:
            play_urls.append(f"立即播放${vod_id}-1-1")
        vod = {
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_play_from": "TOP-TV",
            "vod_play_url": "#".join(play_urls)
        }
        return {"list": [vod]}

    def playerContent(self, flag='', id='', vipFlags=None):
        self._ensure()
        v_id = s_id = n_id = None
        if id:
            parts = id.strip().split('-')
            if len(parts) == 3 and all(p.isdigit() for p in parts):
                v_id, s_id, n_id = parts
            else:
                m = re.search(r'(\d+)-(\d+)-(\d+)\s*$', id.strip())
                if m:
                    v_id, s_id, n_id = m.groups()
        if v_id and s_id and n_id:
            play_url = f"{self.site_url}/index.php/vod/play/id/{v_id}/sid/{s_id}/nid/{n_id}.html"
        else:
            # id 解析失败:回详情页嗅探(原版拼的 /vod/play/id/{id}.html 多半 404)
            vid = id.strip().split('-')[0] if id else ''
            play_url = f"{self.site_url}/index.php/vod/detail/id/{vid}.html" if vid.isdigit() else ""
            if not play_url:
                return {"parse": 1, "url": "", "header": self.headers}
            return {"parse": 1, "url": play_url, "header": self.headers}
        res = self.fetch(play_url)
        if res:
            data_json = re.search(r'var player_aaaa=(.*?)</script>', res.text, re.S)
            if data_json:
                try:
                    data = json.loads(data_json.group(1).strip().rstrip(';'))
                    if data.get("encrypt", 0) == 0:
                        url = data.get("url", "")
                        if url:
                            return {"parse": 0, "url": url, "header": self.headers}
                except Exception:
                    pass
        return {"parse": 1, "url": play_url, "header": self.headers}

    def searchContent(self, key='', quick=False, pg='1'):
        self._ensure()
        pg = int(pg) if str(pg).isdigit() else 1
        if pg < 1:
            pg = 1
        q = urllib.parse.quote(key or '')
        res = self.fetch(f"{self.site_url}/index.php/vod/search/page/{pg}/wd/{q}.html")
        video_list = []
        pagecount = 999
        if res:
            video_list = self._parse_list(res.text)
            pagecount = self._pagecount(res.text, "search")
        return {'list': video_list, 'page': pg, 'pagecount': pagecount, 'limit': 20, 'total': 9999}


# 模块级转发(壳子直接调模块函数时用)
_spider = None

def _get_spider():
    global _spider
    if _spider is None:
        _spider = Spider()
    return _spider

def init(extend=""):
    return _get_spider().init(extend)

def getName():
    return _get_spider().getName()

def homeContent(filter=False):
    return _get_spider().homeContent(filter)

def homeVideoContent():
    return _get_spider().homeVideoContent()

def categoryContent(tid='1', pg='1', filter=False, extend=None):
    return _get_spider().categoryContent(tid, pg, filter, extend)

def detailContent(ids):
    return _get_spider().detailContent(ids)

def searchContent(key='', quick=False, pg='1'):
    return _get_spider().searchContent(key, quick, pg)

def playerContent(flag='', id='', vipFlags=None):
    return _get_spider().playerContent(flag, id, vipFlags)

def localProxy(param):
    return _get_spider().localProxy(param)

def destroy():
    return _get_spider().destroy()

def close():
    return _get_spider().close()
