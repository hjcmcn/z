# -*- coding: utf-8 -*-
# TG交流群 https://t.me/hshsjk9

import re, json, base64, datetime
try:
    from Crypto.Cipher import AES as _AES
except Exception:
    _AES = None
try:
    import requests as _requests
except Exception:
    _requests = None


class Spider:
    def __init__(self):
        self.site = "https://swarm.epothg.com"
        self.name = "吃瓜718"
        self.header = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-S9080) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.site + "/",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        self.s = self.session = self.sess = _requests.Session() if _requests else None
        self._img_host = "https://feer.hclaow.cn"
        self._img_key = b"K65xztwG4B3FKcJyHOz/QAWiUE+Nh6k2"
        self._img_iv = b"rT/+upBDYhpGn05Q"
        self._cats = [
            ("daily-gossip", "每日吃瓜"),
            ("top-stories", "热门吃瓜"),
            ("contrast-reveal", "反差婊曝光"),
            ("week-top", "吃瓜TOP榜"),
            ("sexbook", "网黄合集"),
            ("AINSFW", "AI成人短剧"),
            ("internet-celebrities", "抖音网红瓜"),
            ("trending-news", "社会热瓜"),
            ("model-photos", "微密圈"),
            ("fuli", "福利姬"),
            ("celebrity-scandals", "娱乐吃瓜"),
            ("entertainment-news", "娱乐圈爆料"),
        ]

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
        pass

    def action(self, action):
        return {}

    def init(self, extend=""):
        return None

    def _get(self, url, referer=None):
        h = dict(self.header)
        if referer:
            h["Referer"] = referer
        if self.s is not None:
            try:
                r = self.s.get(url, headers=h, timeout=15, allow_redirects=True)
                if r.status_code < 400:
                    if not r.encoding or r.encoding.lower() in ("iso-8859-1", "ascii"):
                        r.encoding = "utf-8"
                    return r.text
            except Exception:
                pass
        try:
            import urllib.request
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read().decode("utf-8", "ignore")
        except Exception:
            return ""

    def _bytes(self, url):
        h = dict(self.header)
        if self.s is not None:
            try:
                r = self.s.get(url, headers=h, timeout=15)
                if r.status_code < 400:
                    return r.content
            except Exception:
                pass
        try:
            import urllib.request
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read()
        except Exception:
            return b""

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

    def _img_u(self, p):
        if not p:
            return p
        p = p.strip()
        if p.startswith("http"):
            return p
        if p.startswith("//"):
            return "https:" + p
        return self._img_host + "/" + p.lstrip("/")

    def _img(self, url):
        if not url or _AES is None:
            return b"", ""
        raw = self._bytes(url)
        if not raw or len(raw) <= 276:
            return b"", ""
        try:
            cipher = _AES.new(self._img_key, _AES.MODE_CTR, nonce=b"", initial_value=int.from_bytes(self._img_iv, "big"))
            dec = cipher.decrypt(raw[276:])
        except Exception:
            return b"", ""
        if dec[:4] == b"RIFF" and dec[8:12] == b"WEBP":
            return dec, "image/webp"
        if dec[:3] == b"\xff\xd8\xff":
            return dec, "image/jpeg"
        if dec[:4] == b"\x89PNG":
            return dec, "image/png"
        return b"", ""

    def _wrap_img(self, u):
        if not u:
            return ""
        try:
            return self.getProxyUrl() + "&url=" + __import__("urllib.parse", fromlist=["quote"]).quote("img:" + u)
        except Exception:
            return "http://127.0.0.1:9978/proxy?do=py&url=" + __import__("urllib.parse", fromlist=["quote"]).quote("img:" + u)

    def _items(self, html):
        out = []
        seen = set()
        try:
            today = datetime.date.today()
        except Exception:
            today = None
        for bm in re.finditer(r"<article[\s\S]*?</article>", html):
            block = bm.group(0)
            if 'rel="sponsored' in block:
                continue
            pm = re.search(r'id="post-card-(\d+)"', block)
            tm = re.search(r'post-card-title[^>]*>([\s\S]{0,400}?)</h2>', block)
            if not (pm and tm):
                continue
            if today is not None and "<span" in tm.group(1) and "热搜" in tm.group(1):
                dm = re.search(r'itemprop="datePublished" content="(\d{4}-\d{2}-\d{2})', block)
                if dm:
                    try:
                        d = datetime.date.fromisoformat(dm.group(1))
                    except Exception:
                        d = None
                    if d is not None and (today - d).days > 90:
                        continue
            pid = pm.group(1)
            if pid in seen:
                continue
            title = re.sub(r"<[^>]+>", "", tm.group(1))
            title = _html_unescape(title).strip()
            title = re.sub(r"\s*热搜\s*HOT\s*$", "", title).strip()
            if not title:
                continue
            seen.add(pid)
            pic = ""
            im = re.search(r'itemprop="image" content="([^"]+)"', block)
            if im:
                pic = self._img_u(im.group(1))
            if not pic:
                dm = re.search(r'data-pic="([^"]+)"', block)
                if dm and "${" not in dm.group(1):
                    pic = self._img_u(dm.group(1))
            out.append({
                "vod_id": pid,
                "vod_name": title,
                "vod_pic": self._wrap_img(pic) if pic else "",
                "vod_remarks": "",
            })
        return out

    def _pagecount(self, html, pg):
        m = re.search(r'page-info">\d+/(\d+)<', html)
        if m:
            return int(m.group(1))
        nav = re.search(r'<ul class="page-navigator">([\s\S]{0,4000}?)</ul>', html)
        if nav:
            nums = [int(n) for n in re.findall(r'/(\d+)/"', nav.group(1))]
            if nums:
                return max(nums)
        if 'class="next"' in html:
            return pg + 1
        return pg

    def homeContent(self, filter=None):
        cats = [{"type_id": t, "type_name": n} for t, n in self._cats]
        html = self._get(self.site + "/")
        vod_list = self._items(html) if html else []
        return {"class": cats, "filters": {}, "list": vod_list}

    def homeVideoContent(self):
        html = self._get(self.site + "/")
        return {"list": self._items(html) if html else []}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        t = str(tid)
        if t.startswith("http"):
            url = t
        elif "/" in t:
            url = self.site + t
        else:
            url = self.site + "/category/" + t + ("/" if pg <= 1 else "/%d/" % pg)
        html = self._get(url)
        if not html:
            return {"list": [], "page": pg, "pagecount": pg, "limit": 30, "total": 0}
        vod_list = self._items(html)
        pc = self._pagecount(html, pg)
        total = pc * 30 if pc > 1 else len(vod_list)
        return {"list": vod_list, "page": pg, "pagecount": pc, "limit": 30, "total": total}

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, (list, tuple)) else ids
        vid = str(vid).strip()
        url = self.site + "/archives/" + vid + "/"
        html = self._get(url)
        if not html:
            return {"list": []}
        title = ""
        tm = re.search(r"<h1[^>]*>([\s\S]{0,300}?)</h1>", html, re.S)
        if tm:
            title = _html_unescape(re.sub(r"<[^>]+>", "", tm.group(1))).strip()
        pic = ""
        im = re.search(r'itemprop="image" content="([^"]+)"', html)
        if im:
            pic = self._img_u(im.group(1))
        desc = ""
        dm = re.search(r'property="og:description" content="([^"]+)"', html)
        if dm:
            desc = _html_unescape(dm.group(1)).strip()
        eps = []
        for cm in re.finditer(r"data-config='([^']+)'", html):
            try:
                cfg = json.loads(cm.group(1))
            except Exception:
                continue
            v = cfg.get("video", {}) if isinstance(cfg, dict) else {}
            u2 = v.get("url2") or v.get("url") or ""
            if u2:
                eps.append(u2)
        play_from = ""
        play_url = ""
        if eps:
            play_from = self.name
            play_url = "#".join("%s$%s" % ("第%d集" % (i + 1), u) for i, u in enumerate(eps))
        return {"list": [{"vod_id": vid, "vod_name": title, "vod_pic": self._wrap_img(pic) if pic else "",
                          "vod_content": desc, "vod_play_from": play_from, "vod_play_url": play_url}]}

    def searchContent(self, key, quick=False, pg="1"):
        key = str(key or "").strip()
        if not key:
            return {"list": []}
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        try:
            from urllib.parse import quote
            q = quote(key, safe="")
        except Exception:
            return {"list": []}
        url = self.site + "/search/" + q + ("/" if pg <= 1 else "/%d/" % pg)
        html = self._get(url)
        if not html:
            return {"list": []}
        vod_list = self._items(html)
        pc = self._pagecount(html, pg)
        total = pc * 30 if pc > 1 else len(vod_list)
        return {"list": vod_list, "page": pg, "pagecount": pc, "limit": 30, "total": total}

    def playerContent(self, flag, ids, vipFlags=None):
        url = ids[0] if isinstance(ids, (list, tuple)) else ids
        url = str(url or "").strip()
        if not url:
            return {"parse": 0, "url": "", "header": dict(self.header)}
        if not url.startswith("http"):
            url = self._u(url)
        u = url.lower()
        if u.endswith((".m3u8", ".mp4", ".flv", ".mkv", ".ts", ".avi")) or "m3u8" in u or "mp4" in u:
            return {"parse": 0, "url": url, "header": dict(self.header)}
        html = self._get(url, referer=self.site)
        if html:
            m = re.search(r'"url2"\s*:\s*"([^"]+)"', html)
            if m:
                return {"parse": 0, "url": m.group(1).replace("\\/", "/"), "header": dict(self.header)}
        return {"parse": 0, "url": "", "header": dict(self.header)}

    def localProxy(self, param):
        try:
            p = json.loads(param) if isinstance(param, str) else param
            u = p.get("url", "") if isinstance(p, dict) else ""
            if u.startswith("img:"):
                data, ct = self._img(u[4:])
                if data:
                    return [200, ct, data, {"Content-Length": str(len(data))}]
            return [404, "text/plain", b"", {}]
        except Exception:
            return [502, "text/plain", b"", {}]


def _html_unescape(s):
    import html as _h
    return _h.unescape(s) if s else s
