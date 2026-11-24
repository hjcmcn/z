import re, json, datetime
try:
    import requests as _requests
except Exception:
    _requests = None


class Spider:
    def __init__(self):
        self.site = "https://dandanzan.net"
        self.name = "蛋蛋赞影院"
        self.header = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-S9080) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.site + "/",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        self.s = self.session = self.sess = _requests.Session() if _requests else None
        self._extend = {}
        self._home = None
        self._cats = [
            ("/dianying/", "电影"),
            ("/dianshiju/", "电视剧"),
            ("/zongyi/", "综艺"),
            ("/dongman/", "动漫"),
        ]
        self._genres = {
            "/dianying/": [("ju-qing", "剧情"), ("xi-ju", "喜剧"), ("ai-qing", "爱情"), ("dong-zuo", "动作"), ("jing-song", "惊悚"), ("fan-zui", "犯罪"), ("xuan-yi", "悬疑"), ("kong-bu", "恐怖"), ("ke-huan", "科幻"), ("qi-huan", "奇幻"), ("chuan-ji", "传记"), ("zhan-zheng", "战争"), ("jia-ting", "家庭"), ("mao-xian", "冒险"), ("ren-xing", "人性"), ("qing-chun", "青春"), ("li-shi", "历史"), ("wen-yi", "文艺"), ("wen-qing", "温情"), ("gao-xiao", "搞笑")],
            "/dianshiju/": [("ju-qing", "剧情"), ("ai-qing", "爱情"), ("xi-ju", "喜剧"), ("xuan-yi", "悬疑"), ("fan-zui", "犯罪"), ("gu-zhuang", "古装"), ("qi-huan", "奇幻"), ("jing-song", "惊悚"), ("ke-huan", "科幻"), ("jia-ting", "家庭"), ("dong-zuo", "动作"), ("li-shi", "历史"), ("qing-chun", "青春"), ("gao-xiao", "搞笑"), ("tui-li", "推理"), ("zhan-zheng", "战争"), ("ren-xing", "人性"), ("nv-xing", "女性"), ("tong-xing", "同性"), ("wu-xia", "武侠")],
            "/zongyi/": [("zhen-ren-xiu", "真人秀"), ("tuo-kou-xiu", "脱口秀"), ("yin-le", "音乐"), ("gao-xiao", "搞笑"), ("xi-ju", "喜剧"), ("mei-shi", "美食"), ("wen-qing", "温情"), ("wen-hua", "文化"), ("ge-wu", "歌舞"), ("qing-chun", "青春"), ("ai-qing", "爱情"), ("jia-ting", "家庭"), ("xuan-xiu", "选秀")],
            "/dongman/": [("xi-ju", "喜剧"), ("qi-huan", "奇幻"), ("mao-xian", "冒险"), ("ju-qing", "剧情"), ("ke-huan", "科幻"), ("dong-zuo", "动作"), ("gao-xiao", "搞笑"), ("ai-qing", "爱情"), ("jia-ting", "家庭"), ("er-tong", "儿童"), ("duan-pian", "短片"), ("wen-qing", "温情"), ("xuan-yi", "悬疑"), ("qing-chun", "青春"), ("re-xue", "热血"), ("cheng-zhang", "成长"), ("tong-nian", "童年"), ("zhi-yu", "治愈"), ("jing-dian", "经典"), ("fan-zui", "犯罪")],
        }
        self._countries = {
            "/dianying/": [("cn", "大陆"), ("us", "美国"), ("hk", "香港"), ("tw", "台湾"), ("jp", "日本"), ("kr", "韩国"), ("gb", "英国"), ("fr", "法国"), ("de", "德国"), ("it", "意大利"), ("es", "西班牙"), ("in", "印度"), ("th", "泰国"), ("ru", "俄罗斯")],
            "/dianshiju/": [("cn", "大陆"), ("us", "美国"), ("hk", "香港"), ("tw", "台湾"), ("jp", "日本"), ("kr", "韩国"), ("gb", "英国"), ("fr", "法国"), ("de", "德国"), ("it", "意大利"), ("es", "西班牙"), ("in", "印度"), ("th", "泰国"), ("ru", "俄罗斯")],
            "/zongyi/": [("cn", "大陆"), ("us", "美国"), ("hk", "香港"), ("tw", "台湾"), ("jp", "日本"), ("kr", "韩国"), ("gb", "英国")],
            "/dongman/": [("cn", "大陆"), ("us", "美国"), ("hk", "香港"), ("tw", "台湾"), ("jp", "日本"), ("kr", "韩国"), ("gb", "英国"), ("fr", "法国")],
        }

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

    def _u(self, u):
        if not u:
            return u
        u = u.strip()
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("http"):
            return u
        if u.startswith("/"):
            return self.site + u
        return self.site + "/" + u.lstrip("/")

    def _years(self):
        y = datetime.date.today().year
        out = [(str(v), str(v)) for v in range(y, 2009, -1)]
        out.append(("lt__2010", "2010以前"))
        return out

    def _filters(self, tid):
        def opts(items):
            return [{"n": "全部", "v": ""}] + [{"n": n, "v": v} for v, n in items]
        return [
            {"key": "genre", "name": "分类", "value": opts(self._genres.get(tid, []))},
            {"key": "country", "name": "地区", "value": opts(self._countries.get(tid, []))},
            {"key": "year", "name": "年代", "value": opts(self._years())},
        ]

    def _resolve_extend(self, tid, extend):
        e = {}
        if isinstance(extend, dict):
            e = extend
        elif isinstance(extend, str) and extend.strip():
            try:
                v = json.loads(extend)
                if isinstance(v, dict):
                    e = v
            except Exception:
                e = {}
        if not e and isinstance(self._extend, dict):
            e = self._extend
        genre = str(e.get("genre", "") or "")
        country = str(e.get("country", "") or "")
        year = str(e.get("year", "") or "")
        if genre not in [v for v, _ in self._genres.get(tid, [])]:
            genre = ""
        if country not in [v for v, _ in self._countries.get(tid, [])]:
            country = ""
        if year not in [v for v, _ in self._years()]:
            year = ""
        return genre, country, year

    def _items(self, html):
        out = []
        seen = set()
        for m in re.finditer(r'<a href="((?:/dianying|/dianshiju|/zongyi|/dongman)/\d+\.html)" class="thumbnail"\s*>([\s\S]{0,900}?)</a>', html):
            href = m.group(1)
            block = m.group(2)
            if href in seen:
                continue
            im = re.search(r'<img[^>]+data-src="([^"]+)"', block) or re.search(r'<img[^>]+src="([^"]+)"', block)
            tm = re.search(r'alt="([^"]+)"', block)
            if not (im and tm):
                continue
            seen.add(href)
            tail = html[m.end():m.end() + 400]
            nm = re.search(r'<div class="note"><span>([^<]*)</span></div>', tail)
            cm = re.findall(r'<div class="countrie">([\s\S]{0,200}?)</div>', tail)
            rm = re.search(r'<span class="rate">([^<]*)</span>', tail)
            remarks = ""
            if nm and nm.group(1).strip():
                remarks = nm.group(1).strip()
            elif cm:
                parts = [p.strip() for p in re.findall(r'<span[^>]*>([^<]+)</span>', cm[0]) if p.strip()]
                remarks = " / ".join(parts)
            elif rm and rm.group(1).strip():
                remarks = rm.group(1).strip()
            out.append({
                "vod_id": self._u(href),
                "vod_name": _html_unescape(tm.group(1)).strip(),
                "vod_pic": self._u(im.group(1)),
                "vod_remarks": remarks,
            })
        return out

    def _page(self, items, pg):
        pc = pg + 1 if len(items) >= 24 else pg
        return {"list": items, "page": pg, "pagecount": pc, "limit": 24, "total": pc * 24}

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
            self._home = self._get(self.site + "/")
        cats = [{"type_id": p, "type_name": n} for p, n in self._cats]
        filters = {p: self._filters(p) for p, _ in self._cats}
        return {"class": cats, "filters": filters, "list": self._items(self._home or "")}

    def homeVideoContent(self):
        if self._home is None:
            self._home = self._get(self.site + "/")
        return {"list": self._items(self._home or "")}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        tid = str(tid or "")
        if tid.startswith("http"):
            m = re.match(r"(https?://[^/]+)(/[^?#]*)", tid)
            tid = m.group(2) if m else "/dianying/"
        if tid not in [p for p, _ in self._cats]:
            tid = "/dianying/"
        genre, country, year = self._resolve_extend(tid, extend)
        qs = []
        if genre:
            qs.append("genre=" + genre)
        if country:
            qs.append("country=" + country)
        if year:
            qs.append("year=" + year)
        qs.append("page=" + str(pg))
        url = self.site + tid + "?" + "&".join(qs)
        html = self._get(url)
        if not html:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 24, "total": 0}
        return self._page(self._items(html), pg)

    def detailContent(self, ids):
        vid = ids
        if isinstance(ids, (list, tuple)):
            vid = ids[0] if ids else ""
        vid = str(vid or "").strip()
        url = vid if vid.startswith("http") else self._u(vid)
        if not re.search(r"/\d+\.html", url):
            return {"list": []}
        html = self._get(url)
        if not html:
            return {"list": []}
        tm = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S) or re.search(r"<title[^>]*>([^<]{2,80})</title>", html)
        title = _html_unescape(re.sub(r"<[^>]+>", "", tm.group(1))).strip() if tm else ""
        if not title:
            return {"list": []}
        vid_id = re.search(r"/(\d+)\.html", url).group(1)
        pm = re.search(r'<img[^>]+src="(/image/\d+\.jpg)"', html)
        pic = self._u(pm.group(1)) if pm else self._u("/thumbnail/" + vid_id + ".jpg")
        dm = re.search(r'name="description" content="([^"]+)"', html)
        desc = _html_unescape(dm.group(1)).strip() if dm else ""
        info = []
        for label in ("导演", "主演", "类型", "地区"):
            im = re.search(label + r"：\s*<span>(.*?)</span>", html, re.S)
            if im:
                txt = _html_unescape(re.sub(r"<[^>]+>", " ", im.group(1)))
                txt = re.sub(r"\s+", " ", txt).strip()
                if txt:
                    info.append(label + "：" + txt)
        if info:
            desc = "\n".join(info) + ("\n" + desc if desc else "")
        eps = []
        seen = set()
        for em in re.finditer(r'<li class="play-btn"[^>]*ep_slug="([^"]+)"[^>]*>.*?<a[^>]*>(.*?)</a>', html, re.S):
            slug = em.group(1).strip()
            name = _html_unescape(re.sub(r"<[^>]+>", "", em.group(2))).strip() or slug
            if slug in seen:
                continue
            seen.add(slug)
            eps.append((slug, "%s$%s?ep=%s" % (name, url, slug)))
        numbered = [e for e in eps if re.fullmatch(r"ep\d+", e[0])]
        others = [e for e in eps if not re.fullmatch(r"ep\d+", e[0]) and e[0] != "default"]
        if numbered:
            numbered.sort(key=lambda e: int(e[0][2:]))
            eps = numbered + others
        else:
            eps = [e for e in eps if e[0] != "default"] or eps
        play_from = self.name if eps else ""
        play_url = "#".join(e[1] for e in eps)
        return {"list": [{"vod_id": vid, "vod_name": title, "vod_pic": pic,
                          "vod_content": desc, "vod_play_from": play_from,
                          "vod_play_url": play_url}]}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        if not str(key or "").strip():
            return {"list": []}
        try:
            from urllib.parse import quote
            url = self.site + "/so?q=" + quote(str(key)) + "&page=" + str(pg)
        except Exception:
            return {"list": []}
        html = self._get(url)
        if not html:
            return {"list": []}
        return self._page(self._items(html), pg)

    def playerContent(self, flag, ids, vipFlags=None):
        url = ids
        if isinstance(ids, (list, tuple)):
            url = ids[0] if ids else ""
        url = str(url or "").strip()
        if "$" in url:
            url = url.rsplit("$", 1)[1]
        if not url:
            return {"parse": 0, "url": "", "header": dict(self.header)}
        m = re.search(r"/(\d+)\.html", url)
        if not m:
            return {"parse": 0, "url": "", "header": dict(self.header)}
        vid_id = m.group(1)
        em = re.search(r"[?&#]ep=([^&#]+)", url)
        fm = re.search(r"#([^#]+)$", url)
        slug = (em.group(1) if em else None) or (fm.group(1) if fm else None) or "hd"
        durl = url.split("?")[0].split("#")[0]
        api = self.site + "/fetch_plays/" + vid_id + "/" + slug
        raw = self._get(api, referer=durl)
        plays = []
        if raw:
            try:
                d = json.loads(raw)
                plays = [p.get("play_data", "") for p in d.get("video_plays", []) if p.get("play_data")]
            except Exception:
                plays = []
        if not plays:
            return {"parse": 0, "url": "", "header": dict(self.header)}
        for u in plays:
            u = u.strip()
            if u.endswith(".mp4"):
                return {"parse": 0, "url": u, "header": dict(self.header)}
            if ".m3u8" in u:
                if u.startswith("//"):
                    u = "https:" + u
                elif not u.startswith("http"):
                    u = self._u(u)
                probe = self._get(u, referer=durl)
                if probe and "#EXTM3U" in probe:
                    return {"parse": 0, "url": u, "header": dict(self.header)}
        first = plays[0].strip()
        if first.startswith("//"):
            first = "https:" + first
        elif not first.startswith("http"):
            first = self._u(first)
        return {"parse": 0, "url": first, "header": dict(self.header)}

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


def _html_unescape(s):
    import html as _h
    return _h.unescape(s) if s else s
