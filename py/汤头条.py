#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#https://t.me/yuans899
import re
import os
import json
import time
import ssl
import html as htmllib
import concurrent.futures
import urllib.parse
import urllib.request

try:
    from base.spider import Spider as BaseSpider
except Exception:
    BaseSpider = object

try:
    import requests as rq

    rq.packages.urllib3.disable_warnings()
except Exception:
    rq = None

# 进程级内存缓存: {cache_key: cfg}，同进程多次调用不重复拉配置
_MEM_CACHE = {}


class Spider(BaseSpider):
    _CACHE_FILE = "spider_cache.json"
    # 分类缓存有效期(秒): 1 小时内直接用上次缓存，不请求
    _CACHE_TTL = 3600
    # 站点入口候选（可用 extend 传入覆盖，优先探测可用域名）
    _HOST_CANDIDATES = ["https://m.tangttiao.cc"]
    UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
          "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1")
    TIMEOUT = 15

    def __init__(self):
        try:
            super().__init__()
        except Exception:
            pass
        self.name = "汤头条"
        self._host_candidates = list(self._HOST_CANDIDATES)
        self.host = self._host_candidates[0].rstrip("/")
        self.headers = {
            "User-Agent": self.UA,
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/",
        }
        self.s = None
        if rq:
            try:
                self.s = rq.Session()
                self.s.verify = False
                self.s.headers.update(self.headers)
            except Exception:
                self.s = None
        try:
            self.ctx = ssl.create_default_context()
            self.ctx.check_hostname = False
            self.ctx.verify_mode = ssl.CERT_NONE
        except Exception:
            self.ctx = None
        self._cfg = None
        # 父分类聚合结果缓存: {key: (timestamp, videos)}，TTL 5 分钟
        self._agg_cache = {}

    # ---------- 协议基础 ----------
    def getName(self):
        return self.name

    def init(self, extend=""):
        ext = str(extend or "").strip()
        if ext:
            if not ext.startswith("http"):
                ext = "https://" + ext
            ext = ext.rstrip("/")
            self._host_candidates = [ext] + [c.rstrip("/") for c in self._host_candidates
                                             if c.rstrip("/") != ext]
        self.ensure_config()

    def isVideoFormat(self, url):
        return bool(url and (".m3u8" in url or ".mp4" in url))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    # ---------- 配置加载（规则 1/2/3） ----------
    def ensure_config(self):
        if self._cfg:
            return self._cfg
        key = self._cache_key()
        if key in _MEM_CACHE:
            self._cfg = _MEM_CACHE[key]
        else:
            self._cfg = self._refresh_config()
            _MEM_CACHE[key] = self._cfg
        if self._cfg:
            self.host = self._cfg["host"]
            self.headers["Referer"] = self.host + "/"
        return self._cfg

    def _cache_key(self):
        return self._host_candidates[0].split("//")[-1].split("/")[0]

    def _refresh_config(self):
        # 分类缓存优先: 上次缓存 1 小时内直接用(不请求)；
        # 过期才尝试拉取，拉取成功替换缓存，拉取失败跳过(继续沿用旧缓存)
        now = time.time()
        cached = self._load_cache_file()
        if cached and now - self._cache_time(cached) < self._CACHE_TTL:
            return cached
        cfg = self._fetch_config()
        if cfg:
            self._save_cache_file(cfg)
            return cfg
        if cached:
            return cached
        return {"host": self._host_candidates[0].rstrip("/"),
                "classes": [], "parents": {}, "fetched_at": now}

    def _cache_time(self, cfg):
        try:
            return float((cfg or {}).get("fetched_at") or 0)
        except Exception:
            return 0

    def _fetch_config(self):
        host = self._resolve_host()
        if not host:
            return None
        html = self.fetch(host + "/", timeout=12)
        if not html:
            return None
        cats = self._parse_categories(html)
        if not cats:
            return None
        classes, parents = self._build_classes(cats)
        if not classes:
            return None
        # 站点若出现下拉筛选控件则自动补全 type_extend（汤头条当前无，样本检测后跳过）
        first = (parents.get(classes[0]["type_id"]) or [""])[0]
        if first:
            sample = self.fetch("%s/category/%s/" % (host, first), timeout=8)
            if self._parse_selects(sample):
                for c in classes:
                    subs = parents.get(c["type_id"]) or []
                    if not subs:
                        continue
                    ext = self._parse_selects(
                        self.fetch("%s/category/%s/" % (host, subs[0]), timeout=8) or "")
                    if ext:
                        c["type_extend"].update(ext)
        return {"host": host, "classes": classes, "parents": parents, "fetched_at": time.time()}

    def _parse_categories(self, html):
        # 顶级分类: <button class="...pcg-category-parent-btn..." data-parent-id="cate1">
        #              <span class="van-tab__text">推荐</span></button>
        # 外链广告（同城约炮/最新春药等）是没有 data-parent-id 的 <a>，天然被排除
        names = {}
        for m in re.finditer(
                r'<button[^>]*pcg-category-parent-btn[^>]*data-parent-id="([^"]+)"[^>]*>(.*?)</button>',
                html, re.S):
            names[m.group(1)] = self._clean(m.group(2))
        # 子分类: <div class="...pcg-category-dropdown-menu..." data-parent-id="cate1"> ... </div>
        # 页面会重复渲染两份，按 parent-id 去重
        panes = [(m.group(1), m.start(), m.end()) for m in re.finditer(
            r'<div[^>]*pcg-category-dropdown-menu[^>]*data-parent-id="([^"]+)"[^>]*>', html)]
        result, seen_parent = [], set()
        for i, (pid, _start, end) in enumerate(panes):
            if pid in seen_parent:
                continue
            stop = panes[i + 1][1] if i + 1 < len(panes) else len(html)
            body = html[end:stop]
            subs, seen = [], set()
            for a in re.finditer(
                    r'href="/category/([a-z0-9_]+)/"[^>]*class="[^"]*dropdown-link[^"]*"[^>]*>(.*?)</a>',
                    body, re.S):
                cid, cname = a.group(1), self._clean(a.group(2))
                if not cid or not cname or cid in seen:
                    continue
                seen.add(cid)
                subs.append((cid, cname))
            if not subs:          # 没有子分类的都是广告/无效项，不加入
                continue
            result.append((pid, names.get(pid) or pid, subs))
            seen_parent.add(pid)
        return result

    def _build_classes(self, cats):
        classes, parents = [], {}
        for pid, pname, subs in cats:
            if not subs:
                continue
            parents[pid] = [cid for cid, _ in subs]
            classes.append({
                "type_id": pid,
                "type_name": pname,
                "type_extend": {"class": [{"n": n, "v": v} for v, n in subs]},
            })
        return classes, parents

    def _parse_selects(self, html):
        # 通用下拉筛选解析: <select name=...><option value=...>文本</option></select>
        ext = {}
        key_map = {"type": "class", "class": "class", "area": "area",
                   "year": "year", "order": "order", "sort": "order"}
        for sm in re.finditer(r'<select[^>]*name=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</select>', html or ""):
            key = key_map.get(sm.group(1).lower())
            if not key:
                continue
            values = []
            for om in re.finditer(
                    r'<option[^>]*value=["\']?([^"\'>]*)["\']?[^>]*>([\s\S]*?)</option>', sm.group(2)):
                name = self._clean(om.group(2))
                if name:
                    values.append({"n": name, "v": om.group(1).strip()})
            if values:
                ext[key] = values
        return ext

    # ---------- 筛选构建（规则 2/4） ----------
    def _build_filters(self, ext):
        groups = []
        cls = ext.get("class") or []
        if cls:
            # 超过 8 个拆成多行，各行共用同一个 key（class），仅首行带"全部"
            for g in range((len(cls) + 7) // 8):
                seg = cls[g * 8:(g + 1) * 8]
                if g == 0:
                    seg = [{"n": "全部", "v": ""}] + seg
                groups.append({"key": "class", "name": "类型", "value": seg})
        for key, name in (("area", "地区"), ("year", "年份")):
            if ext.get(key):
                groups.append({"key": key, "name": name,
                               "value": [{"n": "全部", "v": ""}] + ext[key]})
        if ext.get("order"):
            groups.append({"key": "order", "name": "排序", "value": ext["order"]})
        return groups

    # ---------- 首页 ----------
    def homeContent(self, filter=False):
        cfg = self.ensure_config()
        classes = cfg.get("classes") or []
        filters = {c["type_id"]: self._build_filters(c.get("type_extend") or {})
                   for c in classes}
        html = self.fetch(self.host + "/", timeout=12)
        return {"class": classes, "filters": filters, "list": self._parse_list(html)}

    def homeVideoContent(self):
        self.ensure_config()
        return {"list": self._parse_list(self.fetch(self.host + "/", timeout=12))}

    # ---------- 分类页（规则 5） ----------
    def categoryContent(self, tid, pg=1, filter=False, extend=""):
        self.ensure_config()
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1
        tid = str(tid or "").strip()
        f = self._normalize_filter(filter, extend)
        parents = (self._cfg or {}).get("parents") or {}
        subs = parents.get(tid)
        if subs:
            sub = self._class_filter_value(f)
            if sub and sub in subs:
                return self._one_category(sub, pg, f)
            return self._aggregate(subs, pg)
        return self._one_category(tid, pg, f)

    def _one_category(self, slug, pg, f):
        if pg <= 1:
            url = "%s/category/%s/" % (self.host, slug)
        else:
            url = "%s/category/%s/%d/" % (self.host, slug, pg)
        qs = self._merge_filter(f)
        if qs:
            url += "?" + qs
        html = self.fetch(url, timeout=12)
        videos = self._parse_list(html)
        pages = [int(x) for x in re.findall(r'/category/' + re.escape(slug) + r'/(\d+)/', html)]
        pagecount = max(pages) if pages else pg
        if pagecount < pg:
            pagecount = pg
        return {"list": videos, "page": pg, "pagecount": pagecount,
                "limit": max(1, len(videos)), "total": 0}

    def _aggregate(self, subs, pg):
        if pg > 1:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 0, "total": 0}
        key = "|".join(subs)
        now = time.time()
        hit = self._agg_cache.get(key)
        if not hit or now - hit[0] > 300:
            def grab(slug):
                return self._parse_list(self.fetch("%s/category/%s/" % (self.host, slug), timeout=10))

            videos, seen = [], set()
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(subs))) as ex:
                for vs in ex.map(grab, subs):
                    for v in vs:
                        if v["vod_id"] not in seen:
                            seen.add(v["vod_id"])
                            videos.append(v)
            self._agg_cache[key] = (now, videos)
        else:
            videos = hit[1]
        videos = videos[:100]
        return {"list": videos, "page": 1, "pagecount": 1,
                "limit": len(videos), "total": len(videos)}

    def _normalize_filter(self, filter, extend=""):
        # 兼容客户端传参: filter 为 dict/JSON 字符串/True/False，筛选也可能只放 extend
        f = filter
        if isinstance(f, str):
            try:
                f = json.loads(f)
            except Exception:
                f = {}
        if not isinstance(f, dict):
            f = {}
        e = extend
        if isinstance(e, str):
            try:
                e = json.loads(e)
            except Exception:
                e = {}
        if isinstance(e, dict) and e:
            f = {**e, **f}
        return f

    def _class_filter_value(self, f):
        # 规则 4: 各行共用同一个 key，直接取该 key 的值
        return str(f.get("class") or "").strip()

    def _merge_filter(self, f):
        # class 通过选择子分类页实现，不作为查询参数；其余筛选项拼到 query
        parts = [(k, f[k]) for k in ("area", "year", "order") if f.get(k)]
        return urllib.parse.urlencode(parts)

    # ---------- 搜索 ----------
    def searchContent(self, key, quick=False, pg="1"):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, page):
        self.ensure_config()
        try:
            pg = int(page or 1)
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1
        kw = urllib.parse.quote(str(key or "").strip())
        if pg <= 1:
            url = "%s/search/%s/" % (self.host, kw)
        else:
            url = "%s/search/%s/%d/" % (self.host, kw, pg)
        html = self.fetch(url, timeout=12)
        videos = self._parse_list(html)
        pages = [int(x) for x in re.findall(r'/search/[^/]+/(\d+)/', html)]
        pagecount = max(pages) if pages else pg
        if pagecount < pg:
            pagecount = pg
        return {"list": videos, "page": pg, "pagecount": pagecount,
                "limit": 20, "total": 0}

    # ---------- 详情页（规则 6） ----------
    def detailContent(self, ids):
        self.ensure_config()
        try:
            did = str(ids[0] if isinstance(ids, (list, tuple)) else ids).strip()
        except Exception:
            return {"list": []}
        if not did:
            return {"list": []}
        if not did.startswith("http"):
            did = self.host + (did if did.startswith("/") else "/" + did)
        html = self.fetch(did, timeout=15)
        if not html:
            return {"list": []}

        title = ""
        m = re.search(r'<h1[^>]*>([^<]+)</h1>', html) or re.search(r'<title>(.*?)</title>', html)
        if m:
            title = self._clean(m.group(1).split("|")[0].split("_")[0])
        pic = ""
        pm = re.search(r'data-cover="(https?://[^"]+)"', html)
        if pm:
            pic = pm.group(1)

        play_url = self._extract_play(html) or ("正片$" + did)
        return {"list": [{
            "vod_id": did,
            "vod_name": title or "未知",
            "vod_pic": pic,
            "type_name": self.name,
            "vod_remarks": "在线",
            "vod_content": title,
            "vod_play_from": "线路1",
            "vod_play_url": play_url,
            "vod_year": "", "vod_area": "", "vod_actor": "", "vod_director": "",
        }]}

    def playerContent(self, flag, id, vipFlags=None, vipIds=None):
        self.ensure_config()
        key = str(id or "").strip()
        header = {"User-Agent": self.UA, "Referer": self.host + "/"}
        if key.startswith("http") and self.isVideoFormat(key):
            return {"parse": 0, "url": key, "header": header}
        html = self.fetch(key, timeout=15)
        play = self._extract_play(html)
        if play and "$" in play:
            url = play.split("$")[-1]
            if url.startswith("http"):
                return {"parse": 0, "url": url, "header": header}
        return {"parse": 1,
                "url": key if key.startswith("http") else self.host + key,
                "header": header}

    def _extract_play(self, html):
        if not html:
            return ""
        m_url = re.search(r'data-url="([^"]+)"', html)
        m_cdn = re.search(r'data-cdnline="([^"]+)"', html)
        if m_url and m_cdn:
            path = m_url.group(1).strip()
            cdn = m_cdn.group(1).rstrip("/")
            if path.startswith("http"):
                return "正片$" + path
            return "正片$" + cdn + path
        for u in re.findall(r'["\']([^"\']+\.m3u8[^"\']*)["\']', html):
            u = htmllib.unescape(u)
            if u.startswith("http"):
                return "正片$" + u
            if u.startswith("/") and m_cdn:
                return "正片$" + m_cdn.group(1).rstrip("/") + u
        return ""

    # ---------- 列表解析 ----------
    def _parse_list(self, html):
        if not html or len(html) < 200:
            return []
        # 封面: <img ... data-cover="..." ... class="...img{视频id}N...">
        covers = {}
        for m in re.finditer(r'<img([^>]+)>', html):
            tag = m.group(1)
            cm = re.search(r'data-cover="(https?://[^"]+)"', tag)
            vm = re.search(r'img(\d{15,})', tag)
            if not (cm and vm):
                continue
            vid = vm.group(1)
            covers.setdefault(vid, cm.group(1))
            if len(vid) > 15:
                covers.setdefault(vid[:-1], cm.group(1))

        videos, seen = [], set()
        for m in re.finditer(r'href="(/video/(\d+)/)"[^>]*title="([^"]+)"', html):
            href, vid, title = m.group(1), m.group(2), self._clean(m.group(3))
            if vid in seen or not title or title in ("HD", "畅看"):
                continue
            seen.add(vid)
            pic = covers.get(vid) or covers.get(vid + "0") or ""
            if not pic:
                chunk = html[max(0, m.start() - 500):m.end() + 200]
                cm = re.search(r'data-cover="(https?://[^"]+)"', chunk)
                if cm:
                    pic = cm.group(1)
            videos.append({"vod_id": self.host + href, "vod_name": title,
                           "vod_pic": pic, "vod_remarks": "在线"})
        if videos:
            return videos

        # 兜底: 无 title 属性的列表项，用锚文本作标题
        for m in re.finditer(r'href="(/video/(\d+)/)"[^>]*>([^<]{4,})', html):
            href, vid, title = m.group(1), m.group(2), self._clean(m.group(3))
            if vid in seen or not title or title in ("HD", "畅看"):
                continue
            seen.add(vid)
            videos.append({"vod_id": self.host + href, "vod_name": title,
                           "vod_pic": covers.get(vid) or "", "vod_remarks": "在线"})
        return videos

    # ---------- 域名探测 ----------
    def _resolve_host(self):
        for u in self._host_candidates:
            if self._check_host(u):
                return u.rstrip("/")
        return None

    def _check_host(self, u):
        h = self.fetch(u + "/", timeout=8)
        return "pcg-category-parent-btn" in h or "汤头条" in h

    # ---------- 缓存文件（规则 3） ----------
    def _cache_paths(self):
        paths = []
        for d in (os.path.dirname(os.path.abspath(__file__)), os.getcwd(), "/tmp"):
            try:
                paths.append(os.path.join(d, self._CACHE_FILE))
            except Exception:
                continue
        return paths

    def _load_cache_file(self):
        for p in self._cache_paths():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    d = json.load(f)
                if d.get("host") and d.get("classes"):
                    return d
            except Exception:
                continue
        return None

    def _save_cache_file(self, cfg):
        for p in self._cache_paths():
            try:
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, ensure_ascii=False)
                return
            except Exception:
                continue

    # ---------- 内部工具 ----------
    def fetch(self, url, hdr=None, timeout=None):
        timeout = timeout or self.TIMEOUT
        headers = dict(self.headers)
        if hdr:
            headers.update(hdr)
        if self.s:
            try:
                r = self.s.get(url, timeout=timeout, verify=False, headers=headers)
                if r.status_code == 200 and r.text:
                    r.encoding = "utf-8"
                    return r.text
            except Exception:
                pass
        try:
            req = urllib.request.Request(url, headers=headers)
            try:
                resp = urllib.request.urlopen(req, context=self.ctx, timeout=timeout)
            except TypeError:
                resp = urllib.request.urlopen(req, timeout=timeout)
            return resp.read().decode("utf-8", errors="ignore")
        except Exception:
            return ""

    def _clean(self, s):
        s = htmllib.unescape(str(s or ""))
        return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s)).strip()
