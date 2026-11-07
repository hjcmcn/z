#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
X红颜 (https://xhongyan.com) 蜘蛛源
写法与结构参照 通用.py，但站点没有可用的 JSON 接口，所以走 HTML 解析。

站点是苹果CMS v10 模板：
  * /api.php/provide/vod/ 已关闭（ac=list、ac=detail、at/json 都返回 closed）
  * 页面路由如下（均已实测）

  首页        /
  分类        /index.php/vod/type/id/{id}.html         分页 .../page/{n}.html
  排序        /index.php/vod/show/by/{time|hits}/id/{id}.html
  关键词搜索  /index.php/vod/search/wd/{kw}.html        分页 .../search/page/{n}/wd/{kw}.html
  标签搜索    /index.php/vod/search/tag/{tag}.html      分页 .../search/page/{n}/tag/{tag}.html
  详情/播放   /index.php/vod/play/id/{vid}/sid/{sid}/nid/{nid}.html

公开分类：1=OnlyFans  2=网黄  3=品牌  4=业余
（type id 5 起是“请升级会员组”的权限页，不收录）

播放页结构：
  <script>var player_data={"url":"/upload/vod_file/xxx.mp4?md5=..&expires=..", ...}</script>
  相对路径 + 时效签名，请求时 302 跳转到视频 CDN（1.onlyfans18.vip）。
"""

import sys
import re
import json
import base64
import urllib.request
import urllib.error
import urllib.parse
import http.cookiejar
import gzip
import zlib
import ssl
import time

try:
    from urllib.parse import quote, unquote
except ImportError:  # pragma: no cover
    from urllib import quote, unquote

try:
    from base.spider import Spider as SpiderBase
except ImportError:
    class SpiderBase(object):
        def getCache(self, key):
            return None

        def setCache(self, key, value):
            return "fail"

        def delCache(self, key):
            return "fail"


# ---------------------------------------------------------------- 配置

SITE = "https://xhongyan.com"
# 同一套站的备用域名，主域名不通时自动切
ALT_SITES = ["https://seyudao.net"]
KNOWN_HOSTS = ("xhongyan.com", "www.xhongyan.com", "seyudao.net", "www.seyudao.net")

BRAND = "🍷 X红颜"
STREAM_EXTS = (".m3u8", ".mp4", ".flv", ".mkv", ".avi", ".ts", ".mpd")

# 导航类文字不能当片名
NOISE_TITLES = (
    "上一集", "下一集", "上集", "下集", "上一页", "下一页",
    "影片收藏", "下载视频", "立即播放", "播放", "收藏", "首页",
)


# ---------------------------------------------------------------- 小工具

def _unescape(text):
    """轻量反转义，避免依赖 html 模块（老 runtime 不一定有）"""
    s = str(text or "")
    if "&" not in s:
        return s
    s = s.replace("&nbsp;", " ")
    s = s.replace("&quot;", '"').replace("&#39;", "'").replace("&apos;", "'")
    s = s.replace("&lt;", "<").replace("&gt;", ">")
    s = s.replace("&amp;", "&")
    return s


def format_remarks(brand=BRAND, meta=""):
    clean_meta = re.sub(r"[\r\n\t]+", " ", str(meta or "")).strip()
    return "%s | %s" % (brand, clean_meta) if clean_meta else brand


def clean_label(text):
    """压成单行的片名"""
    t = str(text or "").strip()
    t = re.sub(r"<[^>]+>", " ", t)
    t = _unescape(t)
    t = re.sub(r"[\r\n\t\$#]+", " ", t)
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip()


def clean_pic(url):
    u = str(url or "").strip().replace("\\/", "/")
    if not u or u.startswith("data:"):
        return ""
    low = u.lower()
    for bad in ("lazyload", "loading", "placeholder", "blank.gif", "wechat-tip", "/logo"):
        if bad in low:
            return ""
    return u


def fixed_int(value, default=1):
    try:
        n = int(str(value or default).strip())
    except Exception:
        n = default
    return n if n >= 1 else default


# ---------------------------------------------------------------- 分区

ZONE_MATRIX = [
    {"id": "zone_home", "name": "🏠首页精选", "subs": [
        {"n": "今日推荐", "v": "home"},
    ]},
    {"id": "zone_amateur", "name": "📷业余自拍", "subs": [
        {"n": "最新上架", "v": "t4"},
        {"n": "人气最高", "v": "h4"},
    ]},
    {"id": "zone_onlyfans", "name": "💎OnlyFans", "subs": [
        {"n": "最新上架", "v": "t1"},
        {"n": "人气最高", "v": "h1"},
    ]},
    {"id": "zone_netred", "name": "💃网黄自制", "subs": [
        {"n": "最新上架", "v": "t2"},
        {"n": "人气最高", "v": "h2"},
    ]},
    {"id": "zone_brand", "name": "🏢传媒品牌", "subs": [
        {"n": "最新上架", "v": "t3"},
        {"n": "人气最高", "v": "h3"},
    ]},
    {"id": "zone_tag", "name": "🏷️标签专题", "subs": [
        {"n": "御姐", "v": "tag:御姐"},
        {"n": "人妻", "v": "tag:人妻"},
        {"n": "少妇", "v": "tag:少妇"},
        {"n": "巨乳", "v": "tag:巨乳"},
        {"n": "黑丝", "v": "tag:黑丝"},
        {"n": "高颜值", "v": "tag:高颜值"},
        {"n": "反差", "v": "tag:反差"},
        {"n": "网红", "v": "tag:网红"},
        {"n": "主播", "v": "tag:主播"},
        {"n": "出轨", "v": "tag:出轨"},
        {"n": "绿帽", "v": "tag:绿帽"},
        {"n": "换妻", "v": "tag:换妻"},
        {"n": "3P", "v": "tag:3P"},
        {"n": "群P", "v": "tag:群P"},
        {"n": "调教", "v": "tag:调教"},
        {"n": "探花", "v": "tag:探花"},
        {"n": "车震", "v": "tag:车震"},
        {"n": "户外", "v": "tag:户外"},
        {"n": "自慰", "v": "tag:自慰"},
        {"n": "内射", "v": "tag:内射"},
        {"n": "口交", "v": "tag:口交"},
        {"n": "骑乘", "v": "tag:骑乘"},
        {"n": "足交", "v": "tag:足交"},
        {"n": "制服", "v": "tag:制服"},
        {"n": "旗袍", "v": "tag:旗袍"},
        {"n": "cosplay", "v": "tag:cosplay"},
        {"n": "混血", "v": "tag:混血"},
        {"n": "日本", "v": "tag:日本"},
        {"n": "韩国", "v": "tag:韩国"},
        {"n": "欧美", "v": "tag:欧美"},
    ]},
]


# ---------------------------------------------------------------- 主体

class Spider(SpiderBase):
    def __init__(self):
        super(Spider, self).__init__()
        self.siteUrl = SITE
        self.active_host = SITE
        self.brandActor = "🍷 X红颜"
        self.brandDirector = "🍷 X红颜"
        self._ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/128.0.0.0 Safari/537.36")
        self.options = {}
        self._init_session()

    def _init_session(self):
        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE
        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj),
            urllib.request.HTTPSHandler(context=self.ctx)
        )

    def init(self, extend=""):
        if isinstance(extend, dict):
            self.options = extend
        elif extend:
            try:
                self.options = json.loads(extend)
            except Exception:
                self.options = {}
        site = str(self.options.get("site") or self.options.get("url") or "").strip()
        if site.startswith("http"):
            self.siteUrl = site.rstrip("/")
            self.active_host = self.siteUrl

    def getName(self):
        return "X红颜"

    def isVideoFormat(self, url):
        low = str(url or "").lower()
        if not low:
            return False
        return any(k in low for k in STREAM_EXTS)

    def manualVideoCheck(self):
        return False

    # ---------------- 网络 ----------------

    def _hosts(self):
        hosts = [self.siteUrl.rstrip("/")]
        for h in ALT_SITES:
            h = h.rstrip("/")
            if h and h not in hosts:
                hosts.append(h)
        return hosts

    def _fix_host(self, url):
        u = str(url or "")
        if not u or self.active_host == self.siteUrl:
            return u
        m = re.match(r"^(?:https?:)?//([^/]+)(.*)$", u)
        if m and m.group(1).lower() in KNOWN_HOSTS:
            return self.active_host + m.group(2)
        return u

    def _abs(self, url):
        u = str(url or "").strip().replace("\\/", "/")
        if not u:
            return ""
        if u.startswith("//"):
            u = "https:" + u
        elif not u.startswith("http"):
            u = (self.siteUrl + u) if u.startswith("/") else (self.siteUrl + "/" + u)
        return self._fix_host(u)

    def _request(self, url, referer="", accept_encoding="gzip, deflate"):
        headers = {
            "User-Agent": self._ua,
            "Referer": referer or (self.siteUrl + "/"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": accept_encoding,
            "Connection": "close",
        }
        req = urllib.request.Request(url, headers=headers)
        with self.opener.open(req, timeout=10) as resp:
            code = resp.getcode()
            final = resp.geturl()
            try:
                enc = resp.headers.get("Content-Encoding", "") or ""
            except Exception:
                enc = ""
            raw = resp.read()
        return code, final, enc, raw

    @staticmethod
    def _decompress(raw, enc):
        enc = (enc or "").lower()
        if raw[:2] == b"\x1f\x8b" or "gzip" in enc:
            try:
                return gzip.decompress(raw)
            except Exception:
                return raw
        if "deflate" in enc:
            try:
                return zlib.decompress(raw)
            except Exception:
                try:
                    return zlib.decompress(raw, -zlib.MAX_WBITS)
                except Exception:
                    return raw
        return raw

    @staticmethod
    def _decode(raw):
        for codec in ("utf-8", "gbk"):
            try:
                return raw.decode(codec)
            except Exception:
                pass
        return raw.decode("utf-8", "ignore")

    def _fetch_url(self, url, referer=""):
        last_err = ""
        for attempt in range(3):
            try:
                code, final, enc, raw = self._request(url, referer)
                # Cloudflare 有时无视 Accept-Encoding 直接回 br，换明文再取一次
                if "br" in enc.lower():
                    code, final, enc, raw = self._request(url, referer, "identity")
                raw = self._decompress(raw, enc)
                return {"code": code, "text": self._decode(raw), "err": "", "final_url": final}
            except urllib.error.HTTPError as e:
                last_err = "HTTP %s" % e.code
                if e.code in (403, 429, 451, 502, 503, 520, 521, 522) and attempt < 2:
                    self._init_session()
                    time.sleep(0.15)
                    continue
                body = ""
                try:
                    body = e.read().decode("utf-8", "ignore")
                except Exception:
                    pass
                return {"code": e.code, "text": body, "err": last_err, "final_url": url}
            except Exception as e:
                last_err = str(e)
                if attempt < 2:
                    self._init_session()
                    time.sleep(0.15)
                    continue
                return {"code": -1, "text": "", "err": last_err, "final_url": url}
        return {"code": -1, "text": "", "err": last_err, "final_url": url}

    def _fetch(self, path, referer=""):
        """相对路径会在主力 / 备用域名上依次重试"""
        if not path:
            return {"code": 0, "text": "", "err": "", "final_url": ""}
        if path.startswith("//"):
            path = "https:" + path
        if path.startswith("http"):
            return self._fetch_url(self._fix_host(path), referer)
        if not path.startswith("/"):
            path = "/" + path

        last = {"code": -1, "text": "", "err": "no host", "final_url": path}
        for host in self._hosts():
            res = self._fetch_url(host + path, referer)
            if res["code"] == 200 and len(res["text"]) > 500:
                self.active_host = host
                return res
            last = res
        return last

    # ---------------- 列表解析 ----------------

    def _pic(self, inner):
        for attr in ("data-original", "data-src", "data-lazy-src", "data-echo", "src"):
            m = re.search(r"""%s=["']([^"']+)["']""" % attr, inner, re.I)
            if m:
                cand = clean_pic(_unescape(m.group(1)))
                if cand:
                    return self._abs(cand)

        # 该模板部分位置用 background-image 出封面，且地址被拼坏成
        # .../nid/%22/upload/vod/xxx.png%22
        m = re.search(r"""background-image\s*:\s*url\(\s*['"]?([^'")]+)""", inner, re.I)
        if m:
            cand = m.group(1).strip()
            if "%22" in cand:
                seg = cand.split("%22")
                if len(seg) > 1 and seg[1].strip():
                    cand = seg[1].strip()
            cand = clean_pic(cand)
            if cand:
                return self._abs(cand)
        return ""

    def _title_from_text(self, inner):
        plain = re.sub(r"<[^>]+>", "\n", inner)
        plain = _unescape(plain)
        keep = []
        for line in plain.splitlines():
            ln = line.strip()
            if not ln:
                continue
            if re.match(r"^\d{1,3}:\d{2}(?::\d{2})?$", ln):              # 26:56
                continue
            if re.match(r"^\d{2}-\d{2}(?:-\d{2})?$", ln):                # 10-13
                continue
            if re.match(r"^[\d.,]+\s*[KkMm千万]?\s+[\d.,]+$", ln):        # 297 0
                continue
            if re.match(r"^[\d.,]+\s*[KkMm千万]?$", ln):                  # 1.2K
                continue
            if re.match(r"^[\d.]+\s*(?:秒|分钟|分|小时|天|周|星期|个月|月|年)前?$", ln):
                continue
            keep.append(ln)
        return max(keep, key=len) if keep else ""

    def _title(self, attrs, inner):
        # img alt 在这个模板里就是完整片名
        alts = []
        for item in re.findall(r"""alt=["']([^"']*)["']""", inner, re.I):
            t = clean_label(item)
            if t and len(t) >= 2 and t not in NOISE_TITLES:
                alts.append(t)
        if alts:
            return max(alts, key=len)

        cands = []
        for item in re.findall(r"""title=["']([^"']*)["']""", inner, re.I):
            cands.append(item)
        for item in re.findall(r"""title=["']([^"']*)["']""", attrs, re.I):
            cands.append(item)
        for item in re.findall(r"<h[1-6][^>]*>([\s\S]*?)</h[1-6]>", inner, re.I):
            cands.append(item)
        cands.append(self._title_from_text(inner))

        cleaned = []
        for item in cands:
            t = clean_label(item)
            if t and len(t) >= 2 and t not in NOISE_TITLES:
                cleaned.append(t)
        return max(cleaned, key=len) if cleaned else ""

    def _cards(self, html):
        """抓 /vod/play/id/x/sid/y/nid/z.html 卡片；同一 href 的多段信息合并"""
        if not html:
            return []

        order = []
        records = {}

        for m in re.finditer(r"""<a\b([^>]*)>([\s\S]*?)</a>""", html, re.I):
            attrs = m.group(1) or ""
            inner = m.group(2) or ""
            hm = re.search(r"""href=["']([^"']+)["']""", attrs, re.I)
            if not hm:
                continue
            href = _unescape(hm.group(1)).strip()
            if not re.search(r"/vod/play/id/\d+/sid/\d+/nid/\d+\.html", href, re.I):
                continue

            rec = records.get(href)
            if rec is None:
                rec = {"id": href, "title": "", "pic": "", "dur": "", "date": ""}
                records[href] = rec
                order.append(href)

            if not rec["pic"]:
                rec["pic"] = self._pic(inner)
            if not rec["dur"]:
                dm = re.search(r"(\d{1,3}:\d{2}(?::\d{2})?)", inner)
                if dm:
                    rec["dur"] = dm.group(1)
            if not rec["date"]:
                dm = re.search(r">\s*(\d{2}-\d{2})\s*<", inner)
                if dm:
                    rec["date"] = dm.group(1)

            title = self._title(attrs, inner)
            if title and len(title) > len(rec["title"]):
                rec["title"] = title

        vod_list = []
        for href in order:
            rec = records[href]
            if not rec["pic"] and not rec["dur"] and not rec["date"]:
                continue
            if not rec["title"]:
                continue
            vod_list.append({
                "vod_id": self._abs(href),
                "vod_name": rec["title"],
                "vod_pic": rec["pic"],
                "vod_remarks": format_remarks(BRAND, rec["dur"] or rec["date"]),
                "style": {"type": "rect", "ratio": 1.78},
            })
        return vod_list

    @staticmethod
    def _pagecount(html, page, count):
        nums = [int(x) for x in re.findall(r"/page/(\d+)(?:/|\.html)", html or "")]
        if nums:
            return max(nums)
        return page + 1 if count > 0 else page

    # ---------------- 取流 ----------------

    @staticmethod
    def _slice_json(text, start):
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
        return ""

    @staticmethod
    def _cfg_url(url, encrypt):
        u = str(url or "").strip().replace("\\/", "/")
        if not u:
            return ""
        enc = str(encrypt or "0").strip()
        if enc in ("1", "2"):
            try:
                if enc == "2":
                    u = u[::-1]
                pad = len(u) % 4
                if pad:
                    u += "=" * (4 - pad)
                u = base64.b64decode(u).decode("utf-8", "ignore")
            except Exception:
                pass
        return u.strip()

    def _stream(self, html):
        """player_data 里的相对签名地址 → 绝对地址"""
        if not html:
            return ""
        norm = html.replace("\\/", "/").replace("\\u002F", "/").replace("\\u002f", "/")

        for m in re.finditer(r"(player_[a-zA-Z0-9_]+|mac_player)\s*=\s*\{", html):
            blob = self._slice_json(html, m.end() - 1)
            if not blob:
                continue
            try:
                cfg = json.loads(blob)
            except Exception:
                continue
            if not isinstance(cfg, dict):
                continue
            cand = self._cfg_url(cfg.get("url") or cfg.get("link") or "",
                                 cfg.get("encrypt", "0"))
            if cand and self.isVideoFormat(cand):
                return self._abs(cand)

        # JSON 不合法时的兜底
        m = re.search(r"""["']url["']\s*:\s*["'](\\?/[^"']+\.(?:mp4|m3u8|flv)[^"']*)["']""",
                      norm, re.I)
        if m:
            return self._abs(m.group(1))

        m = re.search(r"""["'](?:url|video|src|file|play_url)["']\s*:\s*["']"""
                      r"""((?:https?:)?//[^"']+?\.(?:m3u8|mp4|flv)[^"']*)["']""", norm, re.I)
        if m:
            return self._abs(m.group(1))

        for ext in ("m3u8", "mp4", "flv"):
            m = re.search(r"""((?:https?:)?//[^\s"'<>\\]+?\.%s[^\s"'<>\\]*)""" % ext, norm, re.I)
            if m:
                return self._abs(m.group(1))

        m = re.search(r"""<iframe[^>]+src=["']([^"']+)["']""", norm, re.I)
        if m:
            src = _unescape(m.group(1)).strip()
            qm = re.search(r"[?&](?:url|v|vid|code)=([^&#]+)", src, re.I)
            if qm:
                inner = unquote(qm.group(1))
                if self.isVideoFormat(inner):
                    return self._abs(inner)
            return self._abs(src)

        m = re.search(r"""<video[^>]+src=["']([^"']+)["']""", norm, re.I)
        if m:
            return self._abs(_unescape(m.group(1)).strip())

        return ""

    # ---------------- 首页 ----------------

    def homeContent(self, filter):
        classes = [{"type_name": z["name"], "type_id": z["id"]} for z in ZONE_MATRIX]
        filters = {}
        for z in ZONE_MATRIX:
            if len(z["subs"]) > 1:
                filters[z["id"]] = [{
                    "key": "sub",
                    "name": "细分",
                    "init": z["subs"][0]["v"],
                    "value": z["subs"],
                }]
        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        res = self._fetch("/")
        return {"list": self._cards(res.get("text", ""))[:24]}

    # ---------------- 分类 ----------------

    def _list_path(self, target, page):
        if target == "home":
            return "/"

        m = re.match(r"^([th])(\d+)$", target or "")
        if m:
            base = ("/index.php/vod/show/by/hits/id/%s" % m.group(2)) if m.group(1) == "h" \
                else ("/index.php/vod/type/id/%s" % m.group(2))
            return (base + ".html") if page <= 1 else ("%s/page/%d.html" % (base, page))

        if target.startswith("tag:"):
            tag = quote(target[4:].strip())
            return ("/index.php/vod/search/tag/%s.html" % tag) if page <= 1 else \
                ("/index.php/vod/search/page/%d/tag/%s.html" % (page, tag))

        return "/index.php/vod/type/id/%s.html" % target

    def categoryContent(self, tid, pg, filter, extend):
        page = fixed_int(pg, 1)

        cate = ""
        if isinstance(extend, str) and extend.strip():
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if isinstance(extend, dict) and extend.get("sub"):
            cate = str(extend["sub"]).strip()
        if not cate:
            for z in ZONE_MATRIX:
                if z["id"] == tid:
                    cate = z["subs"][0]["v"]
                    break
        if not cate:
            cate = str(tid or "")

        res = self._fetch(self._list_path(cate, page))
        html = res.get("text", "")
        vod_list = self._cards(html)

        if cate == "home":
            return {"page": 1, "pagecount": 1, "limit": 20,
                    "total": len(vod_list), "list": vod_list}

        pagecount = self._pagecount(html, page, len(vod_list))
        return {
            "page": page,
            "pagecount": pagecount,
            "limit": 20,
            "total": pagecount * 20,
            "list": vod_list,
        }

    # ---------------- 详情 ----------------

    def detailContent(self, ids):
        raw_id = str(ids[0] if isinstance(ids, (list, tuple)) else ids).strip()
        detail_url = self._abs(raw_id)

        res = self._fetch(detail_url)
        html = res.get("text", "")

        title = ""
        m = re.search(r"<h1[^>]*>([\s\S]*?)</h1>", html, re.I)
        if m:
            title = clean_label(m.group(1))
        if not title:
            m = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
            if m:
                title = clean_label(re.split(r"\s+-\s+", m.group(1))[0])
        if not title:
            title = "X红颜高清视频"

        poster = ""
        m = re.search(r"""<meta[^>]+(?:property|name)=["']og:image["'][^>]+content=["']([^"']+)["']""",
                      html, re.I)
        if m:
            poster = self._abs(m.group(1))
        if not poster:
            for card in self._cards(html):
                if card.get("vod_pic"):
                    poster = card["vod_pic"]
                    break

        tags = []
        for m in re.finditer(r"""<a[^>]+href=["'][^"']*/vod/search/tag/[^"']*["'][^>]*>([^<]+)</a>""",
                             html, re.I):
            t = clean_label(m.group(1))
            if t and t not in tags:
                tags.append(t)

        upload = ""
        m = re.search(r"上传时间[：:]\s*([0-9/\-: ]{6,20})", html)
        if m:
            upload = m.group(1).strip()

        episodes = ["正片$%s@@@%s" % (detail_url, quote(title))]
        seen = set([detail_url])
        idx = 1
        for card in self._cards(html):
            rec_id = card["vod_id"]
            if rec_id in seen:
                continue
            seen.add(rec_id)
            name = card["vod_name"]
            short = (name[:20] + "...") if len(name) > 20 else name
            episodes.append("%02d·猜你喜欢 %s$%s@@@%s" % (idx, short, rec_id, quote(name)))
            idx += 1
            if idx > 24:
                break

        content = "🍷 X红颜 | %s" % title
        if tags:
            content += " | 标签: %s" % " ".join(tags[:8])
        if upload:
            content += " | 上传: %s" % upload

        vod = {
            "vod_id": raw_id,
            "vod_name": title,
            "vod_pic": poster,
            "vod_bg": poster,
            "vod_background": poster,
            "vod_banner": poster,
            "vod_actor": self.brandActor,
            "vod_director": self.brandDirector,
            "vod_remarks": format_remarks(BRAND, "共%d部" % len(episodes)),
            "vod_content": content,
            "vod_play_from": "红颜专线",
            "vod_play_url": "#".join(episodes),
        }
        return {"list": [vod]}

    # ---------------- 播放 ----------------

    def playerContent(self, flag, id, vipFlags):
        raw = str(id or "").strip()
        desc = ""
        if "@@@" in raw:
            target, raw_desc = raw.split("@@@", 1)
            desc = unquote(raw_desc)
        else:
            target = raw

        stream = target
        if not self.isVideoFormat(target):
            res = self._fetch(target, referer=target)
            cand = self._stream(res.get("text", ""))
            if cand:
                stream = cand

        is_stream = self.isVideoFormat(stream)
        result = {
            "parse": 0 if is_stream else 1,
            "playUrl": "",
            "url": stream,
            "header": {
                "User-Agent": self._ua,
                "Referer": self.siteUrl + "/",
                "Accept": "*/*",
                "Connection": "keep-alive",
            },
        }
        if desc:
            result["desc"] = desc
        return result

    def _probe(self, url, referer=""):
        """只取 1 字节，确认直链是否可访问、是否 302 到别的域名"""
        headers = {
            "User-Agent": self._ua,
            "Referer": referer or (self.siteUrl + "/"),
            "Accept": "*/*",
            "Range": "bytes=0-1",
            "Connection": "close",
        }
        try:
            req = urllib.request.Request(url, headers=headers)
            with self.opener.open(req, timeout=10) as resp:
                return resp.getcode(), resp.headers.get("Content-Type", ""), resp.geturl()
        except urllib.error.HTTPError as e:
            ctype = e.headers.get("Content-Type", "") if e.headers else ""
            return e.code, ctype, url
        except Exception as e:
            return -1, str(e), url

    # ---------------- 搜索 ----------------

    def searchContent(self, key, quick, pg="1"):
        page = fixed_int(pg, 1)
        kw = quote(str(key or "").strip())
        path = ("/index.php/vod/search/wd/%s.html" % kw) if page <= 1 else \
            ("/index.php/vod/search/page/%d/wd/%s.html" % (page, kw))

        res = self._fetch(path)
        html = res.get("text", "")
        vod_list = self._cards(html)
        pagecount = self._pagecount(html, page, len(vod_list))

        return {
            "page": page,
            "pagecount": pagecount,
            "limit": 20,
            "total": pagecount * 20,
            "list": vod_list,
        }

    # ---------------- 其他 ----------------

    def action(self, action):
        return {"msg": "ok"}

    def liveContent(self):
        return ""

    def localProxy(self, params):
        return [404, "text/plain; charset=utf-8", "Proxy not configured"]

    def destroy(self):
        self.options = {}


# ---------------------------------------------------------------- 自检

def _selftest():
    sp = Spider()
    sp.init("")
    print("源名称:", sp.getName())

    print("分类:", ", ".join([c["type_name"] for c in sp.homeContent(True)["class"]]))

    r = sp._fetch("/")
    print("[1] 首页   HTTP %s 长度 %s 域名 %s" % (r["code"], len(r["text"]), sp.active_host))
    print("    推荐条数:", len(sp.homeVideoContent()["list"]))

    r = sp._fetch("/index.php/vod/type/id/4.html")
    print("[2] 分类   HTTP %s 长度 %s" % (r["code"], len(r["text"])))
    cat = sp.categoryContent("zone_amateur", "1", False, {"sub": "t4"})
    print("    业余第1页 %s 条, 总页 %s" % (len(cat["list"]), cat["pagecount"]))
    for v in cat["list"][:3]:
        print("    -", v["vod_name"][:24])

    sr = sp.searchContent("御姐", False, "1")
    print("[3] 搜索   %s 条, 总页 %s" % (len(sr["list"]), sr["pagecount"]))

    if not cat["list"]:
        print("列表为空，后面的步骤跳过")
        return

    vod_id = cat["list"][0]["vod_id"]
    r = sp._fetch(vod_id)
    print("[4] 详情页 HTTP %s 长度 %s 含player_data %s" %
          (r["code"], len(r["text"]), "player_data" in r["text"]))

    stream = sp._stream(r["text"])
    print("[5] 取流   %s" % (stream[:160] if stream else "没取到"))

    vod = sp.detailContent([vod_id])["list"][0]
    print("    标题:", vod["vod_name"][:40])
    print("    选集数:", len(vod["vod_play_url"].split("#")))

    if stream:
        code, ctype, final = sp._probe(stream)
        print("[6] 直链   HTTP %s %s" % (code, ctype))
        print("    最终:", final[:160])


if __name__ == "__main__":
    _selftest()
