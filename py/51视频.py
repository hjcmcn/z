# -*- coding: utf-8 -*-
# TG交流群 https://t.me/hshsjk9

import re, json, base64
try:
    import requests as _requests
except Exception:
    _requests = None


class Spider:
    CATS = [
        {"type_id": "wpcz", "type_name": "今日推荐"},
        {"type_id": "lpjp", "type_name": "撸片精品"},
        {"type_id": "meiridasai", "type_name": "每日大赛"},
        {"type_id": "rdsj", "type_name": "吃瓜爆料"},
        {"type_id": "aisj", "type_name": "AI短剧"},
        {"type_id": "pmv", "type_name": "PMV混剪"},
        {"type_id": "51yc", "type_name": "51原创"},
        {"type_id": "tynd", "type_name": "体育男大"},
        {"type_id": "xsxy", "type_name": "学生校园"},
        {"type_id": "lljx", "type_name": "伦理精选"},
        {"type_id": "smtt", "type_name": "色漫天堂"},
        {"type_id": "whhl", "type_name": "网红黑料"},
        {"type_id": "ysyl", "type_name": "看片娱乐"},
        {"type_id": "cqdb", "type_name": "超前点播"},
        {"type_id": "qubk", "type_name": "奇趣百科"},
        {"type_id": "dyds", "type_name": "短剧影视"},
        {"type_id": "whhj", "type_name": "网黄合集"},
        {"type_id": "mxhl", "type_name": "明星黑料"},
        {"type_id": "jpav", "type_name": "精品AV"},
    ]

    def __init__(self):
        self.site = "https://51sptv.com"
        self.hosts = ["https://51sptv.com", "https://both.iotenjoz.com"]
        self.name = "51视频"
        self.cover_dec = "https://2.h8.ccwu.cc/?url="
        self.header = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-S9080) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.site,
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        self.s = self.session = self.sess = _requests.Session() if _requests else None
        self._extend = {}
        self._home = None
        self._img_cache = {}

    def getName(self):
        return self.name

    def getDependence(self):
        return []

    def manualVideoCheck(self):
        return False

    def isVideoFormat(self, url):
        if not url:
            return False
        u = str(url).lower()
        return u.endswith((".m3u8", ".mp4", ".flv", ".mkv", ".ts", ".avi")) or "m3u8" in u

    def destroy(self):
        try:
            self._img_cache.clear()
        except Exception:
            pass

    def action(self, action):
        return {}

    def _get(self, url, referer=None):
        h = dict(self.header)
        if referer:
            h["Referer"] = referer
        if self.s is not None:
            try:
                r = self.s.get(url, headers=h, timeout=12, allow_redirects=True)
                if r.status_code < 400:
                    if not r.encoding or r.encoding.lower() in ("iso-8859-1", "ascii"):
                        r.encoding = "utf-8"
                    return r.text
            except Exception:
                pass
        try:
            import urllib.request
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=12) as resp:
                return resp.read().decode("utf-8", "ignore")
        except Exception:
            return ""

    def _fetch(self, path):
        if path.startswith("http"):
            return self._get(path)
        for host in self.hosts:
            for _ in range(2):
                t = self._get(host.rstrip("/") + path)
                if t and len(t) > 1000:
                    return t
        return ""

    def _bytes(self, url):
        h = dict(self.header)
        if self.s is not None:
            try:
                r = self.s.get(url, headers=h, timeout=15)
                if r.status_code < 400:
                    return r.content, r.headers.get("Content-Type", "application/octet-stream")
            except Exception:
                pass
        try:
            import urllib.request
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read(), resp.headers.get("Content-Type", "application/octet-stream")
        except Exception:
            return b"", ""

    def _u(self, u):
        if not u:
            return u
        u = u.strip()
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("http"):
            return u
        if u.startswith("/"):
            m = re.match(r"(https?://[^/]+)", self.site)
            return (m.group(1) if m else self.site) + u
        return self.site.rstrip("/") + "/" + u.lstrip("/")

    def _cats(self):
        return [dict(c) for c in self.CATS]

    def _aesimg(self, data):
        if len(data) < 16:
            return data
        try:
            from Crypto.Cipher import AES
            from Crypto.Util.Padding import unpad
        except Exception:
            return data
        for k, v in ((b"f5d965df75336270", b"97b60394abc2fbe1"), (b"75336270f5d965df", b"abc2fbe197b60394")):
            try:
                dec = unpad(AES.new(k, AES.MODE_CBC, v).decrypt(data), 16)
                if dec.startswith(b"\xff\xd8") or dec.startswith(b"\x89PNG"):
                    return dec
            except Exception:
                pass
            try:
                dec = unpad(AES.new(k, AES.MODE_ECB).decrypt(data), 16)
                if dec.startswith(b"\xff\xd8"):
                    return dec
            except Exception:
                pass
        return data

    def _pic(self, u):
        s = (u or "").strip()
        if not s:
            return ""
        if s.startswith("data:"):
            try:
                raw = base64.b64decode(s.split(",", 1)[1])
            except Exception:
                return ""
            if not (raw.startswith(b"\xff\xd8") or raw.startswith(b"\x89PNG") or raw.startswith(b"GIF8")):
                raw = self._aesimg(raw)
            import hashlib
            key = hashlib.md5(raw).hexdigest()
            self._img_cache[key] = raw
            f = getattr(self, "getProxyUrl", None)
            if callable(f):
                try:
                    return f() + "&type=cache&key=" + key
                except Exception:
                    pass
            return ""
        if s.startswith("//"):
            s = "https:" + s
        elif s.startswith("/"):
            s = self.site + s
        elif not s.startswith("http"):
            return s
        f = getattr(self, "getProxyUrl", None)
        if callable(f):
            try:
                return f() + "&url=" + base64.b64encode(s.encode("utf-8")).decode("utf-8") + "&type=img"
            except Exception:
                pass
        from urllib.parse import quote
        return self.cover_dec + quote(s, safe="")

    def _items(self, html):
        out = []
        seen = set()
        if not html:
            return out
        for bm in re.finditer(r"<article\b[^>]*>([\s\S]*?)</article>", html):
            block = bm.group(1)
            if "post-card-ads" in block:
                continue
            hm = re.search(r"/archives/(\d+)/", block)
            if not hm:
                continue
            vid = hm.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            title = ""
            tm = re.search(r"<h2[^>]*post-card-title[^>]*>([\s\S]*?)</h2>", block)
            if tm:
                raw = re.sub(r'<div class="wrap">[\s\S]*?</div>', "", tm.group(1))
                title = _html_unescape(re.sub(r"<[^>]+>", "", raw)).strip()
                title = re.sub(r"\s*热搜\s*HOT\s*$", "", title)
                title = re.sub(r"\s+", " ", title).strip()
            if not title:
                am = re.search(r'<img[^>]+alt="([^"]+)"', block)
                if am:
                    title = _html_unescape(am.group(1)).strip()
            pic = ""
            pm = re.search(r"loadBannerDirect\('([^']+)'", block)
            if not pm:
                pm = re.search(r'data-xkrkllgl="([^"]+)"', block)
            if not pm:
                pm = re.search(r'z-image-loader-url="([^"]+)"', block)
            if not pm:
                pm = re.search(r'data-src="(https?:[^"]+)"', block)
            if pm:
                pic = pm.group(1)
            else:
                for rm in re.finditer(r"(https?://[^\s\"'<>]+\.(?:jpg|jpeg|png|webp))", block, re.I):
                    if "logo.png" not in rm.group(1) and "51cg.png" not in rm.group(1):
                        pic = rm.group(1)
                        break
            remarks = ""
            dm = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", block)
            if dm:
                remarks = "%s-%02d-%02d" % (dm.group(1), int(dm.group(2)), int(dm.group(3)))
            else:
                dm2 = re.search(r'datePublished[^>]*?content="(\d{4}-\d{2}-\d{2})', block)
                if dm2:
                    remarks = dm2.group(1)
            out.append({
                "vod_id": "/archives/" + vid + "/",
                "vod_name": title or ("视频_" + vid),
                "vod_pic": self._pic(pic),
                "vod_remarks": remarks,
            })
        return out

    def _pagecount(self, html, pg, n):
        pc = 0
        if html:
            m = re.search(r'data-total="(\d+)"', html)
            if m:
                pc = int(m.group(1))
            if not pc:
                m = re.search(r'<span class="page-info"[^>]*>\s*(\d+)\s*/\s*(\d+)\s*</span>', html)
                if m:
                    pc = int(m.group(2))
            if not pc:
                nums = [int(x) for x in re.findall(r"(?:/category/[A-Za-z0-9\-]+/|/search/[^/\"]+/|/page/)(\d+)/", html)]
                if nums:
                    pc = max(nums)
        if not pc:
            pc = pg + 1 if n >= 30 else pg
        if pc < pg:
            pc = pg
        return pc

    def _play_urls(self, html):
        out = []
        seen = set()
        if not html:
            return out
        for pat in (r'<div[^>]*class="[^"]*dplayer[^"]*"[^>]*data-config=\'([^\']+)\'',
                    r'<div[^>]*class="[^"]*dplayer[^"]*"[^>]*data-config="([^"]+)"'):
            for m in re.finditer(pat, html):
                try:
                    cfg = json.loads(m.group(1))
                except Exception:
                    try:
                        cfg = json.loads(_html_unescape(m.group(1)))
                    except Exception:
                        continue
                v = (cfg or {}).get("video") or {}
                u = v.get("url") or ""
                if not u:
                    h265 = v.get("video_h265")
                    if isinstance(h265, str):
                        u = h265
                    elif isinstance(h265, dict):
                        u = h265.get("url") or ""
                if u and self.isVideoFormat(u) and u not in seen:
                    seen.add(u)
                    out.append(u)
        if not out:
            for m in re.finditer(r'"url"\s*:\s*"([^"]+\.(?:m3u8|mp4)[^"]*)"', html):
                u = m.group(1).replace("\\/", "/")
                if u not in seen:
                    seen.add(u)
                    out.append(u)
        if not out:
            for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>', html):
                u = m.group(1).replace("\\/", "/")
                if self.isVideoFormat(u) and u not in seen:
                    seen.add(u)
                    out.append(self._u(u))
        return out

    def init(self, extend=""):
        self._extend = {}
        if isinstance(extend, dict):
            self._extend = extend
        elif isinstance(extend, str) and extend.strip():
            try:
                e = json.loads(extend)
                if isinstance(e, dict):
                    self._extend = e
            except Exception:
                pass

    def homeContent(self, filter=None):
        if self._home is None:
            t = self._fetch("/")
            if t:
                self._home = t
        html = self._home or ""
        return {"class": self._cats(), "filters": {}, "list": self._items(html)}

    def homeVideoContent(self):
        if self._home is None:
            t = self._fetch("/")
            if t:
                self._home = t
        return {"list": self._items(self._home or "")}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1
        html = self._fetch(self._cat_url(tid, pg))
        vod_list = self._items(html)
        pagecount = self._pagecount(html, pg, html.count("<article") if html else 0)
        return {"list": vod_list, "page": pg, "pagecount": pagecount, "limit": 30, "total": pagecount * 30}

    def _cat_url(self, tid, pg):
        t = str(tid).strip()
        if t.startswith("http"):
            base = t.rstrip("/")
        elif t.startswith("/"):
            base = t.rstrip("/")
        else:
            base = "/category/" + t.strip("/")
        if pg <= 1:
            return base + "/"
        return base + "/%d/" % pg

    def detailContent(self, ids):
        vid = ids
        if isinstance(ids, (list, tuple)):
            vid = ids[0] if ids else ""
        vid = str(vid).strip()
        if not vid:
            return {"list": []}
        if vid.startswith("http"):
            html = self._get(vid)
        elif vid.startswith("/"):
            html = self._fetch(vid)
        else:
            html = self._fetch("/archives/%s/" % vid.strip("/"))
        if not html:
            return {"list": []}
        title = ""
        tm = re.search(r'<h1[^>]*class="[^"]*post-title[^"]*"[^>]*>([\s\S]*?)</h1>', html)
        if tm:
            title = _html_unescape(re.sub(r"<[^>]+>", "", tm.group(1))).strip()
            title = re.sub(r"\s+", " ", title).strip()
        if not title:
            tm = re.search(r"<title[^>]*>([^<]{2,120})</title>", html)
            if tm:
                title = re.sub(r"\s*-\s*51视频\s*$", "", _html_unescape(tm.group(1))).strip()
        pic = ""
        im = re.search(r'data-xkrkllgl="([^"]+)"', html)
        if im:
            pic = self._pic(im.group(1))
        desc = ""
        dm = re.search(r'<meta property="og:description" content="([^"]*)"', html)
        if dm:
            desc = _html_unescape(dm.group(1)).strip()
        if not desc:
            tg = re.search(r'<div class="tags"[^>]*>([\s\S]*?)</div>', html)
            if tg:
                names = re.findall(r"<a[^>]*>([^<]+)</a>", tg.group(1))
                desc = " ".join([n.strip() for n in names if n.strip()])
        if not desc:
            desc = title
        plays = self._play_urls(html)
        play_url = "#".join(["视频%d$%s" % (i + 1, u) for i, u in enumerate(plays)])
        return {"list": [{"vod_id": vid, "vod_name": title, "vod_pic": pic,
                           "vod_content": desc, "vod_play_from": self.name if plays else "",
                           "vod_play_url": play_url}]}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1
        from urllib.parse import quote
        enc = quote(str(key))
        path = "/search/%s/" % enc
        if pg > 1:
            path += "%d/" % pg
        html = self._fetch(path)
        vod_list = self._items(html)
        if not vod_list:
            self._fetch("/")
            html = self._fetch(path)
            vod_list = self._items(html)
        if not vod_list:
            path2 = "/search/%s/" % str(key)
            if pg > 1:
                path2 += "%d/" % pg
            html = self._fetch(path2)
            vod_list = self._items(html)
        pagecount = self._pagecount(html, pg, html.count("<article") if html else 0)
        return {"list": vod_list, "page": pg, "pagecount": pagecount, "limit": 30, "total": pagecount * 30}

    def playerContent(self, flag, ids, vipFlags=None):
        url = ids
        if isinstance(ids, (list, tuple)):
            url = ids[0] if ids else ""
        url = str(url or "").strip()
        if not url:
            return {"parse": 0, "url": "", "header": dict(self.header)}
        if self.isVideoFormat(url):
            return {"parse": 0, "url": url, "header": dict(self.header)}
        return {"parse": 1, "url": url, "header": dict(self.header)}

    def localProxy(self, param):
        try:
            p = param if isinstance(param, dict) else {}
            t = p.get("type", "")
            u = p.get("url", "")
            if t == "cache":
                content = self._img_cache.get(p.get("key", ""))
                if content:
                    return [200, "image/jpeg", content, None]
                return [404, "text/plain", b"Expired", None]
            if t == "img":
                raw_url = u
                if raw_url and not raw_url.startswith("http"):
                    try:
                        raw_url = base64.b64decode(raw_url.encode("utf-8")).decode("utf-8")
                    except Exception:
                        pass
                data, _ = self._bytes(raw_url)
                if data:
                    dec = self._aesimg(data)
                    ctype = "image/jpeg"
                    if dec.startswith(b"\x89PNG"):
                        ctype = "image/png"
                    elif dec.startswith(b"GIF8"):
                        ctype = "image/gif"
                    return [200, ctype, dec, None]
                return [404, "text/plain", b"", None]
            if u:
                data, ctype = self._bytes(u)
                if data:
                    return [200, ctype or "application/octet-stream", data, None]
            return [403, "text/plain", b"", None]
        except Exception:
            return [404, "text/plain", b"", None]


def _html_unescape(s):
    import html as _h
    return _h.unescape(s) if s else s
