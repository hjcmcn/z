# -*- coding: utf-8 -*-
# TG交流群 https://t.me/hshsjk9

import re, json
try:
    import requests as _requests
except Exception:
    _requests = None


class Spider:
    def __init__(self):
        self.site = "https://vip0012.51xxx.tv"
        self.name = "51X"
        self.header = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-S9080) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.site + "/",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        self.s = self.session = self.sess = _requests.Session() if _requests else None
        self._extend = {}
        self._home = None
        self.cats = [
            ("x视频", "X视频"),
            ("短剧", "短剧"),
            ("x-av", "X-AV"),
            ("x吃瓜", "X吃瓜"),
        ]
        self.subs = {
            "x视频": [("真实自拍", "真实自拍"), ("网红女神", "网红女神"), ("国产精品", "精品国产"), ("爱好男同-1", "爱好男同")],
            "短剧": [("情感剧场", "情感剧场"), ("古装历史", "古装剧场"), ("年代农村", "年代农村"), ("穿越重生", "穿越重生")],
            "x-av": [("日本无码", "日本AV"), ("国产av", "国产AV"), ("欧美av", "欧美AV"), ("动漫av", "动漫AV")],
            "x吃瓜": [("今日吃瓜", "今日吃瓜"), ("海外吃瓜", "海外吃瓜"), ("娱乐吃瓜", "娱乐吃瓜"), ("网红黑料", "网红黑料")],
        }
        self.drama_slugs = {"短剧", "情感剧场", "古装历史", "年代农村", "穿越重生"}
        self.post_slugs = {"x吃瓜", "今日吃瓜", "海外吃瓜", "娱乐吃瓜", "网红黑料"}

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

    def getName(self):
        return self.name

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

    def _f(self, seg, name):
        m = re.search(r'\\"' + name + r'\\":\\"((?:[^"\\]|\\u[0-9a-fA-F]{4}|\\\\|\\/|\\n|\\r|\\t|\\ )*)\\"', seg)
        if not m:
            return ""
        v = m.group(1)
        try:
            return json.loads('"' + v + '"')
        except Exception:
            return v

    def _n(self, seg, name):
        m = re.search(r'\\"' + name + r'\\":(\d+)', seg)
        return int(m.group(1)) if m else 0

    def _record(self, html, pos):
        lb = html.rfind("{", 0, pos)
        if lb < 0:
            return ""
        depth = 0
        end = None
        for i in range(lb, min(lb + 500000, len(html))):
            c = html[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end is None:
            return ""
        return html[lb:end]

    def _records(self, html, kind, start=0):
        out = []
        seen = set()
        seen_slugs = set()
        for m in re.finditer(r'\\"id\\":\\"([a-z0-9]{20,})\\"', html):
            if m.start() < start:
                continue
            rid = m.group(1)
            if rid in seen:
                continue
            seg = self._record(html, m.start())
            if not seg:
                continue
            title = self._f(seg, "titleZh")
            cover = self._f(seg, "coverUrl")
            if not title or not cover:
                continue
            slug = self._f(seg, "slug")
            if slug and slug in seen_slugs:
                continue
            if kind == "video":
                hls = self._f(seg, "hlsUrl")
                if not hls:
                    continue
                seen.add(rid)
                if slug:
                    seen_slugs.add(slug)
                out.append({"id": rid, "slug": slug, "title": title,
                            "duration": self._f(seg, "duration"), "views": self._n(seg, "viewCount"),
                            "cover": cover, "hls": hls})
            elif kind == "post":
                hls = self._f(seg, "hlsUrl")
                ext = self._f(seg, "externalUrl")
                if not hls and not ext:
                    continue
                seen.add(rid)
                if slug:
                    seen_slugs.add(slug)
                out.append({"id": rid, "slug": slug, "title": title,
                            "views": self._n(seg, "viewCount"),
                            "cover": cover, "hls": hls, "ext": ext})
            else:
                if self._f(seg, "kind") != "drama":
                    continue
                seen.add(rid)
                if slug:
                    seen_slugs.add(slug)
                out.append({"id": rid, "slug": slug, "title": title,
                            "ep": self._n(seg, "episodeCount"), "cur": self._n(seg, "currentEpisode"),
                            "views": self._n(seg, "viewCount"), "cover": cover})
        return out

    def _episodes(self, html):
        out = []
        seen = set()
        for m in re.finditer(r'\\"lsjEpisodeId\\":\\"([^"]*)\\"', html):
            seg = self._record(html, m.start())
            if not seg:
                continue
            hls = self._f(seg, "hlsUrl")
            if not hls:
                continue
            key = hls
            if key in seen:
                continue
            seen.add(key)
            out.append({"sort": self._n(seg, "sort"), "name": self._f(seg, "name"), "hls": hls})
        out.sort(key=lambda x: x["sort"])
        return out

    def _dur(self, s):
        try:
            t = int(str(s))
        except Exception:
            return ""
        if t <= 0:
            return ""
        h = t // 3600
        m = (t % 3600) // 60
        sec = t % 60
        if h > 0:
            return "%d:%02d:%02d" % (h, m, sec)
        return "%d:%02d" % (m, sec)

    def _views(self, n):
        try:
            n = int(n)
        except Exception:
            return ""
        if n >= 10000:
            return "%.1f万" % (n / 10000.0)
        if n > 0:
            return str(n)
        return ""

    def _video_card(self, r):
        remarks = self._dur(r["duration"])
        v = self._views(r["views"])
        if v:
            remarks = (remarks + " " + v) if remarks else v
        return {"vod_id": self.site + "/video/" + r["id"] + "/" + r["slug"],
                "vod_name": r["title"], "vod_pic": r["cover"], "vod_remarks": remarks}

    def _drama_card(self, r):
        if r["ep"] > 0 and r["cur"] >= r["ep"]:
            remarks = "全%d集" % r["ep"]
        elif r["cur"] > 0:
            remarks = "更新至%d集" % r["cur"]
        elif r["ep"] > 0:
            remarks = "共%d集" % r["ep"]
        else:
            remarks = ""
        v = self._views(r["views"])
        if v:
            remarks = (remarks + " " + v) if remarks else v
        return {"vod_id": self.site + "/drama/" + r["id"] + "/" + r["slug"],
                "vod_name": r["title"], "vod_pic": r["cover"], "vod_remarks": remarks}

    def _post_card(self, r):
        v = self._views(r["views"])
        if r.get("hls"):
            vid = self.site + "/post/" + r["id"] + "/" + r["slug"]
        else:
            vid = r["ext"]
        return {"vod_id": vid, "vod_name": r["title"], "vod_pic": r["cover"], "vod_remarks": v}

    def _article_video(self, html):
        m3 = re.search(r'<video[^>]*data-stream-src="([^"]+)"', html or "")
        return self._u(m3.group(1)) if m3 else ""

    def _pagecount(self, html):
        pages = re.findall(r'href="/m/[^"]+\?page=(\d+)"', html)
        if pages:
            return max(int(p) for p in pages)
        return 1

    def homeContent(self, filter=None):
        cats = [{"type_id": slug, "type_name": name} for slug, name in self.cats]
        filters = {}
        for slug, name in self.cats:
            filters[slug] = [
                {"key": "sub", "name": "分类", "value": [{"n": "全部", "v": ""}] + [{"n": n2, "v": s2} for s2, n2 in self.subs.get(slug, [])]},
            ]
        if self._home is None:
            self._home = self._get(self.site + "/")
        vod_list = [self._video_card(r) for r in self._records(self._home or "", "video")]
        return {"class": cats, "filters": filters, "list": vod_list}

    def homeVideoContent(self):
        if self._home is None:
            self._home = self._get(self.site + "/")
        vod_list = [self._video_card(r) for r in self._records(self._home or "", "video")]
        return {"list": vod_list}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        slug = str(tid or "").strip()
        if not slug:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 24, "total": 24}
        ext = {}
        if isinstance(extend, dict):
            ext = extend
        elif isinstance(extend, str) and extend.strip():
            try:
                e = json.loads(extend)
                if isinstance(e, dict):
                    ext = e
            except Exception:
                pass
        if not ext and isinstance(self._extend, dict):
            ext = self._extend
        sub = str(ext.get("sub") or "").strip()
        if sub:
            subs = dict(self.subs.get(slug, []))
            if sub in subs:
                slug = sub
        try:
            from urllib.parse import quote
            url = self.site + "/m/" + quote(slug) + "?page=%d" % pg
        except Exception:
            url = self.site + "/m/" + slug + "?page=%d" % pg
        html = self._get(url)
        if not html:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 24, "total": 24}
        is_drama = slug in self.drama_slugs
        is_post = slug in self.post_slugs
        if is_drama:
            vod_list = [self._drama_card(r) for r in self._records(html, "drama")]
        elif is_post:
            vod_list = [self._post_card(r) for r in self._records(html, "post")]
        else:
            vod_list = [self._video_card(r) for r in self._records(html, "video")]
        pagecount = self._pagecount(html)
        if pagecount < pg and vod_list:
            pagecount = pg
        total = pagecount * 24
        return {"list": vod_list, "page": pg, "pagecount": pagecount, "limit": 24, "total": total}

    def detailContent(self, ids):
        vid = ids
        if isinstance(ids, (list, tuple)):
            vid = ids[0] if ids else ""
        vid = str(vid or "").strip()
        if not vid:
            return {"list": []}
        url = vid if vid.startswith("http") else self._u(vid)
        is_drama = "/drama/" in url
        m = re.search(r"/(?:video|drama|post)/([a-z0-9]+)/", url)
        rid = m.group(1) if m else ""
        html = self._get(url, referer=self.site + "/")
        if not html:
            return {"list": []}
        if "818chiguavip.com/article/" in url:
            vids = []
            seen = set()
            for m3 in re.finditer(r'<video[^>]*data-stream-src="([^"]+)"', html):
                u = self._u(m3.group(1))
                if u not in seen:
                    seen.add(u)
                    vids.append(u)
            if not vids:
                return {"list": []}
            title = ""
            tm = re.search(r'<meta property="og:title" content="([^"]*)"', html)
            if tm:
                title = tm.group(1)
            if not title:
                tm = re.search(r'<title>([^<]*)</title>', html)
                title = tm.group(1).strip() if tm else ""
            pic = ""
            pm = re.search(r'<video[^>]*poster="([^"]*)"', html)
            if pm:
                pic = self._u(pm.group(1))
            if len(vids) == 1:
                play_url = "播放$" + vids[0]
            else:
                play_url = "#".join("第%d集$%s" % (i + 1, v) for i, v in enumerate(vids))
            return {"list": [{"vod_id": url, "vod_name": title, "vod_pic": pic,
                              "vod_remarks": "", "vod_content": "", "vod_play_from": "在线播放",
                              "vod_play_url": play_url}]}
        if "/post/" in url:
            recs = self._records(html, "post")
            main = None
            for r in recs:
                if r["id"] == rid:
                    main = r
                    break
            if main is None and recs:
                main = recs[0]
            if main is None:
                return {"list": []}
            hls = main.get("hls") or ""
            if not hls and main.get("ext"):
                ah = self._get(main["ext"], referer=self.site + "/")
                hls = self._article_video(ah)
            if not hls:
                return {"list": []}
            return {"list": [{"vod_id": url, "vod_name": main["title"], "vod_pic": main["cover"],
                              "vod_remarks": "", "vod_content": "", "vod_play_from": "在线播放",
                              "vod_play_url": "播放$" + hls}]}
        if is_drama:
            recs = self._records(html, "drama")
            main = None
            for r in recs:
                if r["id"] == rid:
                    main = r
                    break
            if main is None and recs:
                main = recs[0]
            if main is None:
                return {"list": []}
            eps = self._episodes(html)
            if not eps:
                return {"list": []}
            play_from = "在线播放"
            play_url = "#".join("第%d集$%s" % (e["sort"], e["hls"]) for e in eps)
            if main["ep"] > 0 and main["cur"] >= main["ep"]:
                remarks = "全%d集" % main["ep"]
            elif main["cur"] > 0:
                remarks = "更新至%d集" % main["cur"]
            else:
                remarks = ""
            return {"list": [{"vod_id": url, "vod_name": main["title"], "vod_pic": main["cover"],
                              "vod_remarks": remarks, "vod_content": "", "vod_play_from": play_from,
                              "vod_play_url": play_url}]}
        recs = self._records(html, "video")
        main = None
        for r in recs:
            if r["id"] == rid:
                main = r
                break
        if main is None and recs:
            main = recs[0]
        if main is None:
            return {"list": []}
        seg = ""
        for m2 in re.finditer(r'\\"id\\":\\"' + re.escape(main["id"]) + r'\\"', html):
            seg = self._record(html, m2.start())
            if seg and self._f(seg, "hlsUrl"):
                break
        desc = self._f(seg, "descriptionZh") if seg else ""
        creator = ""
        if seg:
            cm = re.search(r'\\"creator\\":\{', seg)
            if cm:
                cseg = self._record(seg, cm.start())
                creator = self._f(cseg, "name") if cseg else ""
        remarks = self._dur(main["duration"])
        v = self._views(main["views"])
        if v:
            remarks = (remarks + " " + v) if remarks else v
        return {"list": [{"vod_id": url, "vod_name": main["title"], "vod_pic": main["cover"],
                          "vod_remarks": remarks, "vod_actor": creator, "vod_content": desc,
                          "vod_play_from": "在线播放", "vod_play_url": "播放$" + main["hls"]}]}

    def searchContent(self, key, quick=False, pg="1"):
        if not key:
            return {"list": [], "page": 1, "pagecount": 1, "limit": 24, "total": 0}
        try:
            from urllib.parse import quote
            url = self.site + "/search?q=" + quote(str(key))
        except Exception:
            url = self.site + "/search?q=" + str(key)
        html = self._get(url)
        if not html:
            return {"list": [], "page": 1, "pagecount": 1, "limit": 24, "total": 0}
        start = 0
        im = re.search(r'\\"items\\":\[', html)
        if im:
            start = im.start()
        vod_list = [self._video_card(r) for r in self._records(html, "video", start=start)]
        return {"list": vod_list, "page": 1, "pagecount": 1, "limit": 24, "total": len(vod_list)}

    def playerContent(self, flag, ids, vipFlags=None):
        url = ids
        if isinstance(ids, (list, tuple)):
            url = ids[0] if ids else ""
        url = str(url or "").strip()
        if not url:
            return {"parse": 0, "url": "", "header": dict(self.header)}
        if not url.startswith("http"):
            url = self._u(url)
        u = url.lower()
        if u.endswith(".m3u8") or "m3u8" in u:
            return {"parse": 0, "url": url, "header": dict(self.header)}
        html = self._get(url, referer=self.site + "/")
        if not html:
            return {"parse": 0, "url": "", "header": dict(self.header)}
        if "818chiguavip.com/article/" in url:
            hls = self._article_video(html)
            if hls:
                return {"parse": 0, "url": hls, "header": dict(self.header)}
            return {"parse": 0, "url": "", "header": dict(self.header)}
        if "/post/" in url:
            pm = re.search(r"/post/([a-z0-9]+)/", url)
            pid = pm.group(1) if pm else ""
            recs = self._records(html, "post")
            main = None
            for r in recs:
                if r["id"] == pid:
                    main = r
                    break
            if main is None and recs:
                main = recs[0]
            if main is not None:
                hls = main.get("hls") or ""
                if not hls and main.get("ext"):
                    ah = self._get(main["ext"], referer=self.site + "/")
                    hls = self._article_video(ah)
                if hls:
                    return {"parse": 0, "url": hls, "header": dict(self.header)}
            return {"parse": 0, "url": "", "header": dict(self.header)}
        if "/drama/" in url:
            eps = self._episodes(html)
            if eps:
                return {"parse": 0, "url": eps[0]["hls"], "header": dict(self.header)}
            return {"parse": 0, "url": "", "header": dict(self.header)}
        recs = self._records(html, "video")
        if recs:
            return {"parse": 0, "url": recs[0]["hls"], "header": dict(self.header)}
        return {"parse": 0, "url": "", "header": dict(self.header)}

    def localProxy(self, param):
        u = param.get("url", "") if isinstance(param, dict) else ""
        if not u:
            return [403, "text/plain", b"", None]
        h = dict(self.header)
        if self.s is not None:
            try:
                r = self.s.get(u, headers=h, timeout=15)
                return [200, r.headers.get("Content-Type", "application/octet-stream"), r.content, None]
            except Exception:
                pass
        try:
            import urllib.request
            req = urllib.request.Request(u, headers=h)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return [200, resp.headers.get("Content-Type", "application/octet-stream"), resp.read(), None]
        except Exception:
            return [403, "text/plain", b"", None]
