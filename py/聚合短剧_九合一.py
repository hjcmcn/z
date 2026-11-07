# -*- coding: utf-8 -*-
# =====================================================================
#  聚合短剧 · 九合一
#     (红果 + 黄豆 + 黄果 + 野果 + 禁果 + 红果黄剧 + 聚合短剧[短] + 2048短剧 + 狂飙短剧)
#  由 __.py(红果) / ____.py(黄豆) / 黄果短剧修复DNS.py(黄果) / 野果.py(野果)
#     / 禁果.py(禁果) / 红果黄剧.js(红果黄剧,已转 Python) / _______.js(聚合，已转 Python)
#     / 2048成人短剧[18].py(麻豆成人,mdcmai4.xyz) / 狂飙短剧.py(狂飙短剧,ai.dramarush.tv) 融合而成
#  单文件 TVBox / CatVod Python 爬虫，class Spider 统一入口，按引擎前缀分发
#      HG:: -> 红果   HD:: -> 黄豆   HGUO:: -> 黄果   YG:: -> 野果
#      JG:: -> 禁果   HGJ:: -> 红果黄剧   AG:: -> 聚合(15平台)   MD:: -> 2048短剧
#      KB:: -> 狂飙短剧
# =====================================================================
from __future__ import annotations
import base64
import binascii
import bisect
import datetime
import gzip
import hashlib
import hmac
import json
import os
try:
    import lzma  # Chaquopy/部分设备 Python 可能未内置 _lzma，缺失时降级
except Exception:
    lzma = None
import random
import re
import socket
import struct
import tempfile
import time
import uuid
try:
    import concurrent.futures
except Exception:
    concurrent = None
try:
    import threading
except Exception:
    threading = None
from collections.abc import Mapping
try:
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
except Exception:
    BaseHTTPRequestHandler = object
    ThreadingHTTPServer = None
try:
    from html.parser import HTMLParser
except Exception:
    class HTMLParser:
        pass
from typing import Any
from urllib.parse import parse_qs, quote, quote_plus, unquote, urlencode, urlparse, urlsplit

# requests 在部分 TVBox/Chaquopy Python 环境未内置；缺失时用标准库 urllib 实现
# 一个等价 shim（覆盖本文件用到的全部 API：Session/get/post/head、resp.text/
# content/status_code/headers.get/encoding/json/raise_for_status/url、
# headers=/data=/timeout=/verify=/allow_redirects=、RequestException），
# 保证在没有第三方 requests 的设备上也能正常 import 与运行。
try:
    import requests  # noqa
    try:
        import urllib3
        urllib3.disable_warnings()
    except Exception:
        pass
except Exception:
    import ssl as _ssl
    import gzip as _gzip
    import zlib as _zlib
    import io as _io
    from urllib import request as _urlreq
    from urllib.error import URLError as _URLError, HTTPError as _HTTPError

    class _ReqException(Exception):
        pass

    class _Resp(object):
        def __init__(self, url, status, headers, body):
            self.url = url
            self.status_code = int(status or 0)
            self.headers = headers or {}
            self.content = body or b""
            self.encoding = None
            try:
                ctype = ""
                for k, v in (headers.items() if hasattr(headers, "items") else []):
                    if str(k).lower() == "content-type":
                        ctype = str(v)
                        break
                if "charset=" in ctype.lower():
                    self.encoding = ctype.lower().split("charset=", 1)[1].split(";")[0].strip()
            except Exception:
                self.encoding = None

        @property
        def text(self):
            for enc in (self.encoding, "utf-8", "gbk"):
                if not enc:
                    continue
                try:
                    return self.content.decode(enc)
                except Exception:
                    continue
            return self.content.decode("utf-8", "replace")

        def json(self):
            import json as _j
            return _j.loads(self.text)

        def raise_for_status(self):
            if self.status_code >= 400:
                raise _ReqException("HTTP %s for %s" % (self.status_code, self.url))

        @property
        def ok(self):
            return self.status_code < 400

    def _decompress(body, headers):
        try:
            enc = ""
            for k, v in (headers.items() if hasattr(headers, "items") else []):
                if str(k).lower() == "content-encoding":
                    enc = str(v).lower()
                    break
            if not body:
                return body
            if "gzip" in enc:
                return _gzip.GzipFile(fileobj=_io.BytesIO(body)).read()
            if "deflate" in enc:
                try:
                    return _zlib.decompress(body)
                except Exception:
                    return _zlib.decompress(body, -_zlib.MAX_WBITS)
        except Exception:
            return body
        return body

    def _request(method, url, headers=None, data=None, timeout=15,
                 verify=True, allow_redirects=True, params=None, **_kw):
        m = (method or "GET").upper()
        if params:
            try:
                sep = "&" if ("?" in url) else "?"
                url = url + sep + urlencode(params)
            except Exception:
                pass
        payload = data
        if isinstance(payload, dict):
            payload = urlencode(payload).encode("utf-8")
        elif isinstance(payload, str):
            payload = payload.encode("utf-8")
        req = _urlreq.Request(url, data=payload, method=m)
        for k, v in (headers or {}).items():
            try:
                req.add_header(str(k), str(v))
            except Exception:
                pass
        ctx = None
        if not verify:
            try:
                ctx = _ssl._create_unverified_context()
            except Exception:
                ctx = None
        opener_kw = {"timeout": timeout}
        if ctx is not None:
            opener_kw["context"] = ctx
        try:
            if not allow_redirects:
                class _NoRedirect(_urlreq.HTTPRedirectHandler):
                    def redirect_request(self, *a, **k):
                        return None
                opener = _urlreq.build_opener(_NoRedirect)
                resp = opener.open(req, timeout=timeout)
            else:
                resp = _urlreq.urlopen(req, **opener_kw)
            body = resp.read()
            hdrs = resp.headers
            body = _decompress(body, hdrs)
            status = getattr(resp, "status", None) or resp.getcode()
            return _Resp(resp.geturl(), status, hdrs, body)
        except _HTTPError as he:
            # 4xx/5xx：requests 不在此抛错，构造响应交由 raise_for_status 处理
            try:
                body = he.read()
            except Exception:
                body = b""
            hdrs = getattr(he, "headers", {}) or {}
            body = _decompress(body, hdrs)
            return _Resp(url, getattr(he, "code", 0), hdrs, body)
        except (_URLError, Exception) as e:
            raise _ReqException(str(e))

    class _Session(object):
        def __init__(self):
            self.headers = {}

        def _merge(self, headers):
            h = dict(self.headers or {})
            if headers:
                h.update(headers)
            return h

        def request(self, method, url, headers=None, **kw):
            return _request(method, url, headers=self._merge(headers), **kw)

        def get(self, url, headers=None, **kw):
            return _request("GET", url, headers=self._merge(headers), **kw)

        def post(self, url, headers=None, **kw):
            return _request("POST", url, headers=self._merge(headers), **kw)

        def head(self, url, headers=None, **kw):
            return _request("HEAD", url, headers=self._merge(headers), **kw)

    class _RequestsShim(object):
        RequestException = _ReqException

        class exceptions(object):
            RequestException = _ReqException

        Session = _Session

        @staticmethod
        def get(url, **kw):
            return _request("GET", url, **kw)

        @staticmethod
        def post(url, **kw):
            return _request("POST", url, **kw)

        @staticmethod
        def head(url, **kw):
            return _request("HEAD", url, **kw)

        @staticmethod
        def request(method, url, **kw):
            return _request(method, url, **kw)

    requests = _RequestsShim()

try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
except Exception:
    hashes = None
    Cipher = algorithms = modes = None
try:
    from Crypto.Cipher import AES as CryptoAES
except Exception:
    CryptoAES = None

try:
    from base.spider import Spider as _BaseSpider
except Exception:
    try:
        import sys as _sys
        _sys.path.append("..")
        from base.spider import Spider as _BaseSpider
    except Exception:
        class _BaseSpider:
            pass

# 关键修复：部分 TVBox / PG 二改的 base.spider.Spider 是 ABC 抽象基类，
# 子类若未实现其全部 @abstractmethod，会在实例化时抛
# "Can't instantiate abstract class ... without an implementation for
# abstract methods ..."，导致整个爬虫加载失败、首页全空。
# 主动清空基类的抽象方法集合，使各引擎子类无需逐一实现即可实例化。
try:
    if getattr(_BaseSpider, "__abstractmethods__", None):
        _BaseSpider.__abstractmethods__ = frozenset()
except Exception:
    pass

# FongMi/TVBox 的 Chaquopy 环境未必带 cryptography，多数壳只带 pycryptodome。
# 统一入口，避免调用点直接依赖某一个库。
if Cipher is not None:
    AES_BACKEND = "cryptography"
elif CryptoAES is not None:
    AES_BACKEND = "pycryptodome"
else:
    AES_BACKEND = "none"


# ############################################################
# ENGINE HD · 黄豆短剧 (原 ____.py)
# ############################################################
class _AESCBC:
    @staticmethod
    def encrypt(data, key, iv):
        try:
            from Crypto.Cipher import AES
            return AES.new(key, AES.MODE_CBC, iv).encrypt(_AESCBC.pad(data))
        except Exception:
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            enc = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend()).encryptor()
            return enc.update(_AESCBC.pad(data)) + enc.finalize()

    @staticmethod
    def decrypt(data, key, iv):
        try:
            from Crypto.Cipher import AES
            plain = AES.new(key, AES.MODE_CBC, iv).decrypt(data)
        except Exception:
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            dec = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend()).decryptor()
            plain = dec.update(data) + dec.finalize()
        return _AESCBC.unpad(plain)

    @staticmethod
    def pad(data):
        n = 16 - len(data) % 16
        return data + bytes([n]) * n

    @staticmethod
    def unpad(data):
        n = data[-1] if data else 0
        return data[:-n] if 1 <= n <= 16 else data

class _HuangdouSpider(_BaseSpider):
    def __init__(self):
        self.host = "https://lzlukvca.cc" 
        self.api = self.host + "/api"
        self.name = "黄豆短剧"
        self.platform_key = "7961beb44246e3012ce228d6b5ced05a"
        self.version = "2.0.0"
        self.device_type = "web"
        self.session_id = uuid.uuid4().hex
        self.device_id = self.session_id
        self.token = ""
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36", "Accept": "*/*", "Origin": self.host, "Referer": self.host + "/home", "Content-Type": "application/octet-stream"}
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.class_cache = None
        self.filter_cache = {}

    def init(self, extend=""):
        if extend:
            try:
                cfg = json.loads(extend)
                self.host = (cfg.get("site") or cfg.get("url") or self.host).rstrip("/")
                self.api = self.host + "/api"
                self.token = cfg.get("token", self.token)
                self.headers["Origin"] = self.host
                self.headers["Referer"] = self.host + "/home"
                self.session.headers.update(self.headers)
            except Exception:
                None

    def getName(self):
        return self.name

    def homeContent(self, filter):
        data = self._api("/drama/list", {"page": "1", "page_size": "18"})
        classes = self._classes()
        return {"class": classes, "filters": self._filters(classes), "list": [self._vod(x) for x in self._list(data)], "parse": 0, "jx": 0}

    def categoryContent(self, tid, pg, filter, extend):
        extend = extend or {}
        if tid == "yuandou":
            data = self._api("/drama/navBlock", {"code": "yuandou", "tab": "recommend", "page": str(pg)})
            items = self._nav_items(data)
        else:
            req = {"page": str(pg), "page_size": "18"}
            if tid and tid not in ("all", "recommend"):
                tabs = self._nav_filter(tid)
                idx = self._int(extend.get("sub"), 0)
                sub = tabs[idx] if tabs and 0 <= idx < len(tabs) else {}
                flt = sub.get("filter", {}) if isinstance(sub, dict) else {}
                req["cat_id"] = flt.get("cat_id", "")
                if flt.get("tag_id"):
                    req["tag_id"] = flt.get("tag_id", "")
                req["order"] = flt.get("order", "") or extend.get("order", "")
            elif extend.get("order"):
                req["order"] = extend.get("order")
            if extend.get("update_status"):
                req["update_status"] = extend.get("update_status")
            data = self._api("/drama/list", req)
            items = self._list(data)
        return {"page": int(pg), "pagecount": int(pg) if len(items) < 18 else int(pg) + 1, "limit": 18, "total": 99999, "list": [self._vod(x) for x in items], "parse": 0, "jx": 0}

    def detailContent(self, ids):
        vid = str(ids[0]).replace("rp_", "")
        obj = self._api("/drama/detail", {"id": vid})
        data = obj.get("data", obj) if isinstance(obj, dict) else {}
        if not isinstance(data, dict):
            return {"list": []}
        data = self._unlock(data)
        vod_id = self._sid(data.get("id") or data.get("drama_id") or vid)
        name = data.get("name") or data.get("title") or data.get("t") or vod_id
        eps = data.get("episodes") if isinstance(data.get("episodes"), list) else []
        count = self._int(data.get("episode_count") or data.get("free_episodes"), len(eps) or 1)
        play = []
        if eps:
            for i, ep in enumerate(eps, 1):
                seq = ep.get("seq") or ep.get("episode") or ep.get("ep") or i
                play.append("%s$%s|%s" % (ep.get("name") or ep.get("title") or "第%s集" % seq, vod_id, seq))
        else:
            play = ["第%s集$%s|%s" % (i, vod_id, i) for i in range(1, count + 1)]
        vod = {"vod_id": vod_id, "vod_name": name, "vod_pic": self._pic(data), "type_name": data.get("category") or data.get("type") or "", "vod_year": "", "vod_area": "", "vod_remarks": data.get("update_label") or "全%s集" % count, "vod_actor": "", "vod_director": "", "vod_content": data.get("description") or data.get("summary") or name, "vod_play_from": self.name, "vod_play_url": "#".join(play)}
        return {"list": [vod], "parse": 0, "jx": 0}

    def searchContent(self, key, quick, pg="1"):
        data = self._api("/drama/list", {"page": str(pg), "page_size": "18", "keywords": str(key)})
        items = self._list(data)
        return {"page": int(pg), "pagecount": int(pg) if len(items) < 18 else int(pg) + 1, "limit": 18, "total": 99999, "list": [self._vod(x) for x in items], "parse": 0, "jx": 0}

    def playerContent(self, flag, id, vipFlags):
        vid, seq = self._split(id)
        obj = self._api("/drama/play", {"id": vid, "seq": str(seq)}, True)
        data = obj.get("data", {}) if isinstance(obj, dict) else {}
        url = data.get("m3u8") or data.get("url") or self._hls(vid, seq)
        return {"parse": 0, "playUrl": "", "url": url, "jx": 0, "header": {"User-Agent": self.headers["User-Agent"], "Referer": self.host + "/home", "Origin": self.host}}

    def _api(self, path, data=None, silent=False):
        path = "/" + path.lstrip("/")
        rid = str(uuid.uuid4())
        key = self._key(rid)
        iv = os.urandom(16)
        raw = json.dumps({"token": self.token or "", "deviceId": self.device_id, "data": data or {}}, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        body = iv + _AESCBC.encrypt(gzip.compress(raw), key, iv)
        ts = int(time.time())
        sign = hashlib.sha256(("Dart|%s|%s|%s|%s" % (self.session_id, rid, ts, path)).encode("utf-8")).hexdigest() + "-" + str(ts)
        h = dict(self.headers)
        h.update({"version": self.version, "deviceType": self.device_type, "time": str(ts), "sign": sign, "requestId": rid, "sessionId": self.session_id, "deviceBrand": "", "deviceModel": "", "systemName": "", "systemVersion": ""})
        try:
            r = self.session.post(self.api + path, data=body, headers=h, timeout=20, verify=False)
            r.raise_for_status()
            return self._decode(r.content, rid)
        except Exception:
            return {}

    def _key(self, rid):
        return hmac.new(self.platform_key.encode("utf-8"), bytes.fromhex(str(rid).replace("-", "")), hashlib.sha256).digest()

    def _decode(self, blob, rid):
        if not blob or len(blob) < 32 or (len(blob) - 16) % 16 != 0:
            try:
                return json.loads(blob.decode("utf-8"))
            except Exception:
                return {}
        plain = _AESCBC.decrypt(blob[16:], self._key(rid), blob[:16])
        if plain[:2] == b"\x1f\x8b":
            plain = gzip.decompress(plain)
        return json.loads(plain.decode("utf-8"))

    def _classes(self):
        if self.class_cache:
            return self.class_cache
        arr = [{"type_id": "all", "type_name": "全部短剧"}]
        data = self._api("/drama/navList", {})
        for item in self._list(data.get("data", data) if isinstance(data, dict) else data):
            tid = str(item.get("code") or item.get("id") or item.get("cat_id") or "")
            name = item.get("name") or item.get("title") or tid
            if tid and name:
                arr.append({"type_id": tid, "type_name": name})
        self.class_cache = arr
        return arr

    def _filters(self, classes):
        common = [{"key": "order", "name": "排序", "value": [{"n": "默认", "v": ""}, {"n": "最新", "v": "new"}, {"n": "最热", "v": "hot"}]}, {"key": "update_status", "name": "状态", "value": [{"n": "全部", "v": ""}, {"n": "连载", "v": "0"}, {"n": "完结", "v": "1"}]}]
        fs = {}
        for c in classes:
            tid = c["type_id"]
            tabs = self._nav_filter(tid) if tid not in ("all", "yuandou") else []
            fs[tid] = ([{"key": "sub", "name": "子分类", "value": [{"n": t.get("name", "默认"), "v": str(i)} for i, t in enumerate(tabs)]}] if tabs else []) + common
        return fs

    def _nav_filter(self, code):
        if code not in self.filter_cache:
            data = self._api("/drama/navFilter", {"code": str(code)})
            self.filter_cache[code] = self._list(data.get("data", data) if isinstance(data, dict) else data)
        return self.filter_cache.get(code, [])

    def _list(self, data):
        if isinstance(data, list):
            return data
        if not isinstance(data, dict):
            return []
        if isinstance(data.get("list"), list):
            return data["list"]
        if isinstance(data.get("items"), list):
            return data["items"]
        if isinstance(data.get("data"), list):
            return data["data"]
        if isinstance(data.get("data"), dict):
            return self._list(data["data"])
        return []

    def _nav_items(self, data):
        blocks = self._list(data.get("data", data) if isinstance(data, dict) else data)
        items = []
        for b in blocks:
            if isinstance(b, dict) and isinstance(b.get("items"), list):
                items += b.get("items")
            elif isinstance(b, dict) and (b.get("id") or b.get("drama_id")):
                items.append(b)
        return items

    def _vod(self, item):
        item = item or {}
        vid = self._sid(item.get("id") or item.get("drama_id") or "")
        remarks = item.get("update_label") or item.get("corner") or ("全%s集" % item.get("episode_count") if item.get("episode_count") else "")
        return {"vod_id": vid, "vod_name": item.get("name") or item.get("title") or item.get("t") or vid, "vod_pic": self._pic(item), "vod_remarks": remarks}

    def _pic(self, item):
        return item.get("img_y") or item.get("img_x") or item.get("img") or item.get("cover") or item.get("pic") or ""

    def _unlock(self, d):
        eps = d.get("episodes")
        if isinstance(eps, list):
            for ep in eps:
                if isinstance(ep, dict):
                    ep["is_buy"] = True
                    ep["type"] = "free"
                    ep["price"] = 0
                    ep["methods"] = []
        d.update({"pay_type": "free", "money": 0, "episode_price": 0, "points_price": 0, "can_vip_watch": True, "is_buy_whole": True, "vip_episodes": [], "coin_episodes": [], "points_episodes": []})
        return d

    def _sid(self, x):
        return str(x or "").replace("rp_", "")

    def _split(self, x):
        p = str(x).split("|", 1)
        return self._sid(p[0]), p[1] if len(p) > 1 and p[1] else "1"

    def _hls(self, vid, seq):
        return "%s/api/drama/hls/%s/%s/play.m3u8?line=free" % (self.host, self._sid(vid), seq)

    def _int(self, x, d=0):
        try:
            return int(x)
        except Exception:
            return d


# ############################################################
# ENGINE HG · 红果短剧 (原 __.py)
# ############################################################
class _PureAES128:
    """纯 Python AES-128，供无 pycryptodome/cryptography 的壳使用。"""

    _S = (
        99,124,119,123,242,107,111,197,48,1,103,43,254,215,171,118,202,130,201,125,250,89,71,240,
        173,212,162,175,156,164,114,192,183,253,147,38,54,63,247,204,52,165,229,241,113,216,49,21,
        4,199,35,195,24,150,5,154,7,18,128,226,235,39,178,117,9,131,44,26,27,110,90,160,82,59,214,
        179,41,227,47,132,83,209,0,237,32,252,177,91,106,203,190,57,74,76,88,207,208,239,170,251,67,
        77,51,133,69,249,2,127,80,60,159,168,81,163,64,143,146,157,56,245,188,182,218,33,16,255,243,
        210,205,12,19,236,95,151,68,23,196,167,126,61,100,93,25,115,96,129,79,220,34,42,144,136,70,
        238,184,20,222,94,11,219,224,50,58,10,73,6,36,92,194,211,172,98,145,149,228,121,231,200,55,
        109,141,213,78,169,108,86,244,234,101,122,174,8,186,120,37,46,28,166,180,198,232,221,116,31,
        75,189,139,138,112,62,181,102,72,3,246,14,97,53,87,185,134,193,29,158,225,248,152,17,105,
        217,142,148,155,30,135,233,206,85,40,223,140,161,137,13,191,230,66,104,65,153,45,15,176,84,
        187,22
    )
    _RCON = (0x00,0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x80,0x1B,0x36)

    def __init__(self, key: bytes):
        if len(key) != 16:
            raise ValueError("AES-128 only")
        self._rk = self._expand(key)

    def _expand(self, key: bytes):
        s = self._S
        w = list(key)
        for i in range(4, 44):
            t0, t1, t2, t3 = w[-4], w[-3], w[-2], w[-1]
            if i % 4 == 0:
                t0, t1, t2, t3 = s[t1], s[t2], s[t3], s[t0]
                t0 ^= self._RCON[i // 4]
            base = (i - 4) * 4
            w.extend((w[base] ^ t0, w[base + 1] ^ t1, w[base + 2] ^ t2, w[base + 3] ^ t3))
        return w

    @staticmethod
    def _xtime(a: int) -> int:
        return ((a << 1) ^ 0x1B) & 0xFF if (a & 0x80) else ((a << 1) & 0xFF)

    def encrypt_block(self, block: bytes) -> bytes:
        s = list(block)
        rk = self._rk
        for i in range(16):
            s[i] ^= rk[i]
        for rnd in range(1, 10):
            s = [self._S[b] for b in s]
            s = [s[0], s[5], s[10], s[15], s[4], s[9], s[14], s[3],
                 s[8], s[13], s[2], s[7], s[12], s[1], s[6], s[11]]
            for c in range(4):
                i = c * 4
                a, b, c0, d = s[i], s[i + 1], s[i + 2], s[i + 3]
                t = a ^ b ^ c0 ^ d
                u = a
                a ^= t ^ self._xtime(a ^ b)
                b ^= t ^ self._xtime(b ^ c0)
                c0 ^= t ^ self._xtime(c0 ^ d)
                d ^= t ^ self._xtime(d ^ u)
                s[i], s[i + 1], s[i + 2], s[i + 3] = a, b, c0, d
            off = rnd * 16
            for i in range(16):
                s[i] ^= rk[off + i]
        s = [self._S[b] for b in s]
        s = [s[0], s[5], s[10], s[15], s[4], s[9], s[14], s[3],
             s[8], s[13], s[2], s[7], s[12], s[1], s[6], s[11]]
        for i in range(16):
            s[i] ^= rk[160 + i]
        return bytes(s)

    def decrypt_block(self, block: bytes) -> bytes:
        def mul(a, b):
            p = 0
            for _ in range(8):
                if b & 1:
                    p ^= a
                hi = a & 0x80
                a = (a << 1) & 0xFF
                if hi:
                    a ^= 0x1B
                b >>= 1
            return p

        s = list(block)
        rk = self._rk
        for i in range(16):
            s[i] ^= rk[160 + i]
        for rnd in range(9, 0, -1):
            s = [s[0], s[13], s[10], s[7], s[4], s[1], s[14], s[11],
                 s[8], s[5], s[2], s[15], s[12], s[9], s[6], s[3]]
            s = [self._SI[b] for b in s]
            off = rnd * 16
            for i in range(16):
                s[i] ^= rk[off + i]
            for c in range(4):
                i = c * 4
                a, b, c0, d = s[i], s[i + 1], s[i + 2], s[i + 3]
                s[i] = mul(a, 0x0E) ^ mul(b, 0x0B) ^ mul(c0, 0x0D) ^ mul(d, 0x09)
                s[i + 1] = mul(a, 0x09) ^ mul(b, 0x0E) ^ mul(c0, 0x0B) ^ mul(d, 0x0D)
                s[i + 2] = mul(a, 0x0D) ^ mul(b, 0x09) ^ mul(c0, 0x0E) ^ mul(d, 0x0B)
                s[i + 3] = mul(a, 0x0B) ^ mul(b, 0x0D) ^ mul(c0, 0x09) ^ mul(d, 0x0E)
        s = [s[0], s[13], s[10], s[7], s[4], s[1], s[14], s[11],
             s[8], s[5], s[2], s[15], s[12], s[9], s[6], s[3]]
        s = [self._SI[b] for b in s]
        for i in range(16):
            s[i] ^= rk[i]
        return bytes(s)



_PureAES128._SI = tuple({v: i for i, v in enumerate(_PureAES128._S)}[i] for i in range(256))


def _pure_ctr_decrypt(key: bytes, counter: bytes, data: bytes) -> bytes:
    if not data:
        return b""
    if len(counter) < 16:
        counter = counter.ljust(16, b"\0")
    else:
        counter = counter[:16]
    aes = _PureAES128(key)
    ctr = int.from_bytes(counter, "big")
    out = bytearray()
    for offset in range(0, len(data), 16):
        ks = aes.encrypt_block(ctr.to_bytes(16, "big"))
        ctr = (ctr + 1) & ((1 << 128) - 1)
        chunk = data[offset:offset + 16]
        out.extend(c ^ k for c, k in zip(chunk, ks))
    return bytes(out)


def _pure_cbc_decrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
    if not data:
        return b""
    if len(data) % 16:
        data = data[: len(data) - (len(data) % 16)]
    aes = _PureAES128(key)
    prev = (iv[:16] if len(iv) >= 16 else iv).ljust(16, b"\0")
    out = bytearray()
    for i in range(0, len(data), 16):
        block = data[i:i + 16]
        dec = aes.decrypt_block(block)
        out.extend(d ^ p for d, p in zip(dec, prev))
        prev = block
    return bytes(out)


def _aes_ctr_decrypt(key: bytes, counter: bytes, data: bytes) -> bytes:
    if not data:
        return b""
    if AES_BACKEND == "cryptography":
        decryptor = Cipher(algorithms.AES(key), modes.CTR(counter)).decryptor()
        return decryptor.update(data) + decryptor.finalize()
    if AES_BACKEND == "pycryptodome":
        cipher = CryptoAES.new(
            key, CryptoAES.MODE_CTR, nonce=b"", initial_value=counter
        )
        return cipher.decrypt(data)
    return _pure_ctr_decrypt(key, counter, data)


def _aes_cbc_decrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
    if not data:
        return b""
    if AES_BACKEND == "cryptography":
        decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
        return decryptor.update(data) + decryptor.finalize()
    if AES_BACKEND == "pycryptodome":
        return CryptoAES.new(key, CryptoAES.MODE_CBC, iv).decrypt(data)
    return _pure_cbc_decrypt(key, iv, data)


SITE = "https://hongguoduanju.com"
EPISODE_PREFIX = "hg-episode-v1:"
# 红果每集视频模型按清晰度返回多条独立线路（360/480/540/720/1080），
# 每条带 main_url + backup_url 双 CDN 与独立加密材料。这里把清晰度作为
# TVBox 多线路暴露；内封音/视轨在解密 _rewrite_moov 时天然全部保留。
_HG_QUALITY_LINES = (
    ("1080", "红果超清"),
    ("720",  "红果高清"),
    ("540",  "红果标准"),
    ("480",  "红果流畅"),
    ("360",  "红果极速"),
)
_QUALITY_LINE_NAME_TO_Q = {
    "超清": "1080", "高清": "720", "标准": "540",
    "流畅": "480", "极速": "360", "1080": "1080", "720": "720",
    "540": "540", "480": "480", "360": "360",
}


def _split_episode_token(token: str) -> tuple[str, str]:
    """把 'hg-episode-v1:<q>:<vid>' 解析为 (清晰度, vid)；兼容旧格式 'hg-episode-v1:<vid>'。"""
    body = str(token or "")
    if body.startswith(EPISODE_PREFIX):
        body = body[len(EPISODE_PREFIX):]
    if ":" in body:
        head, tail = body.split(":", 1)
        if head.isdigit():
            return head, tail
    return "1080", body

# 官网搜索 SSR 固定约 10 条且几乎不认 page；用多关键词轮换实现“翻页”
_AI_MANJU_KEYWORDS = [
    "AI漫剧", "AI动画", "AI短剧", "AI动漫", "漫剧AI", "二次元AI", "AI漫画", "动画短剧",
]


# ---- 本机解密缓存 + 自动清理 ----
_HG_CACHE_DIR = None
_HG_CACHE_MAX_FILES = 8          # 最多保留集数
_HG_CACHE_MAX_BYTES = 400 * 1024 * 1024  # 总容量约 400MB
_HG_CACHE_MAX_AGE = 6 * 3600     # 超过 6 小时自动删


def _hg_cache_dir() -> str:
    global _HG_CACHE_DIR
    if _HG_CACHE_DIR and os.path.isdir(_HG_CACHE_DIR):
        return _HG_CACHE_DIR
    candidates = []
    # 优先 App 可写缓存目录（OK影视 / FongMi 常见路径）
    for root in (
        "/data/user/0/com.fongmi.android.oktv/cache",
        "/data/data/com.fongmi.android.oktv/cache",
        "/data/user/0/com.fongmi.android.tv/cache",
        "/data/data/com.fongmi.android.tv/cache",
        "/sdcard/Android/data/com.fongmi.android.oktv/cache",
        "/sdcard/Android/data/com.fongmi.android.tv/cache",
        "/sdcard/Download",
    ):
        candidates.append(os.path.join(root, "hg_cenc_cache"))
    try:
        candidates.append(os.path.join(tempfile.gettempdir(), "hg_cenc_cache"))
    except Exception:
        pass
    try:
        candidates.append(os.path.join(os.getcwd(), "hg_cenc_cache"))
    except Exception:
        pass
    for path in candidates:
        try:
            os.makedirs(path, exist_ok=True)
            test = os.path.join(path, ".w")
            with open(test, "wb") as fh:
                fh.write(b"1")
            os.remove(test)
            _HG_CACHE_DIR = path
            return path
        except Exception:
            continue
    _HG_CACHE_DIR = tempfile.mkdtemp(prefix="hg_cenc_")
    return _HG_CACHE_DIR


def _hg_cache_path(vid: str, quality: str) -> str:
    safe = re.sub(r"[^0-9A-Za-z_-]", "", str(vid))[:40]
    q = re.sub(r"[^0-9A-Za-z]", "", str(quality or "q"))[:8]
    return os.path.join(_hg_cache_dir(), "%s_%s.mp4" % (safe, q))


def _hg_cache_list() -> list:
    root = _hg_cache_dir()
    files = []
    try:
        now = time.time()
        for name in os.listdir(root):
            if not name.endswith(".mp4"):
                continue
            fp = os.path.join(root, name)
            if not os.path.isfile(fp):
                continue
            try:
                st = os.stat(fp)
            except Exception:
                continue
            files.append({"path": fp, "size": st.st_size, "mtime": st.st_mtime, "age": now - st.st_mtime})
    except Exception:
        return []
    files.sort(key=lambda x: x["mtime"])  # 旧 -> 新
    return files


def _hg_cache_cleanup(force: bool = False) -> None:
    """按时间 + 数量 + 体积自动清理本机缓存。"""
    try:
        files = _hg_cache_list()
        if not files and not force:
            return
        # 1) 过期删除
        remain = []
        for item in files:
            if item["age"] > _HG_CACHE_MAX_AGE or item["size"] <= 0:
                try:
                    os.remove(item["path"])
                except Exception:
                    pass
            else:
                remain.append(item)
        # 2) 超量删除最旧
        total = sum(x["size"] for x in remain)
        while remain and (len(remain) > _HG_CACHE_MAX_FILES or total > _HG_CACHE_MAX_BYTES):
            old = remain.pop(0)
            try:
                os.remove(old["path"])
            except Exception:
                pass
            total -= old["size"]
        # 3) 清理残留 tmp
        root = _hg_cache_dir()
        for name in os.listdir(root):
            if name.endswith(".tmp") or name == ".w":
                try:
                    os.remove(os.path.join(root, name))
                except Exception:
                    pass
    except Exception:
        pass


def _hg_cache_clear_all() -> None:
    try:
        root = _hg_cache_dir()
        for name in os.listdir(root):
            fp = os.path.join(root, name)
            try:
                if os.path.isfile(fp):
                    os.remove(fp)
            except Exception:
                pass
    except Exception:
        pass


def _hg_cache_get(vid: str, quality: str) -> bytes | None:
    _hg_cache_cleanup(False)
    path = _hg_cache_path(vid, quality)
    try:
        if os.path.isfile(path) and os.path.getsize(path) > 64:
            # 读时刷新 mtime，避免刚播又被当过期删
            try:
                os.utime(path, None)
            except Exception:
                pass
            with open(path, "rb") as fh:
                return fh.read()
    except Exception:
        return None
    return None


def _hg_cache_put(vid: str, quality: str, data: bytes) -> None:
    if not data or len(data) < 64:
        return
    path = _hg_cache_path(vid, quality)
    try:
        _hg_cache_cleanup(False)
        tmp = path + ".tmp"
        with open(tmp, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
        _hg_cache_cleanup(False)
    except Exception:
        try:
            if os.path.exists(path + ".tmp"):
                os.remove(path + ".tmp")
        except Exception:
            pass


def _aes_is_fast() -> bool:
    return AES_BACKEND in ("cryptography", "pycryptodome")


def _aes_is_fast() -> bool:
    return AES_BACKEND in ("cryptography", "pycryptodome")


def _http_get_bytes(url: str, headers: dict | None = None, timeout: int = 60) -> bytes:
    h = dict(headers or {})
    r = requests.get(url, headers=h, timeout=timeout)
    r.raise_for_status()
    return r.content


def _probe_content_length(url: str, headers: dict | None = None, timeout: int = 30) -> int:
    h = dict(headers or {})
    try:
        r = requests.head(url, headers=h, timeout=timeout, allow_redirects=True)
        if r.status_code < 400:
            cl = r.headers.get("Content-Length") or r.headers.get("content-length")
            if cl and str(cl).isdigit():
                return int(cl)
    except Exception:
        pass
    try:
        hh = dict(h)
        hh["Range"] = "bytes=0-0"
        r = requests.get(url, headers=hh, timeout=timeout)
        cr = r.headers.get("Content-Range") or r.headers.get("content-range") or ""
        # bytes 0-0/12345
        if "/" in cr:
            total = cr.split("/")[-1].strip()
            if total.isdigit():
                return int(total)
        cl = r.headers.get("Content-Length") or "0"
        if str(cl).isdigit() and int(cl) > 1:
            return int(cl)
    except Exception:
        pass
    return 0


def _download_range(url: str, start: int, end: int, headers: dict | None, timeout: int) -> tuple[int, bytes]:
    h = dict(headers or {})
    h["Range"] = "bytes=%d-%d" % (start, end)
    last_err = None
    for attempt in range(3):
        try:
            r = requests.get(url, headers=h, timeout=timeout)
            if r.status_code not in (200, 206):
                raise RuntimeError("range http %s" % r.status_code)
            data = r.content
            if not data:
                raise RuntimeError("empty range body")
            return start, data
        except Exception as err:
            last_err = err
            try:
                time.sleep(0.25 * (attempt + 1))
            except Exception:
                pass
    raise RuntimeError("range %s-%s failed: %s" % (start, end, last_err))


def _multi_download(url: str, headers: dict | None = None, timeout: int = 90, workers: int = 4) -> bytes:
    """多分片并行下载，失败则回退整文件单线程。"""
    headers = dict(headers or {})
    total = _probe_content_length(url, headers, timeout=min(30, timeout))
    # 太小或未知长度：直接整下
    if total <= 0 or total < 2 * 1024 * 1024:
        return _http_get_bytes(url, headers, timeout=timeout)

    # 分片大小 1~2MB，线程数限制
    workers = max(2, min(int(workers or 4), 6))
    chunk = max(1 * 1024 * 1024, min(2 * 1024 * 1024, total // workers))
    ranges = []
    start = 0
    while start < total:
        end = min(total - 1, start + chunk - 1)
        ranges.append((start, end))
        start = end + 1

    parts: dict[int, bytes] = {}
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            futs = [
                pool.submit(_download_range, url, s, e, headers, timeout)
                for s, e in ranges
            ]
            for fut in concurrent.futures.as_completed(futs):
                s, data = fut.result()
                parts[s] = data
    except Exception:
        # 并行失败回退
        return _http_get_bytes(url, headers, timeout=timeout)

    buf = bytearray()
    for s, e in ranges:
        piece = parts.get(s)
        if piece is None:
            return _http_get_bytes(url, headers, timeout=timeout)
        buf.extend(piece)
    if len(buf) < total * 0.95:
        # 明显不完整
        return _http_get_bytes(url, headers, timeout=timeout)
    return bytes(buf)



_MANJU_KEYWORDS = [
    "漫剧", "动漫短剧", "二次元", "漫画短剧", "国漫短剧", "日漫", "动态漫", "动画剧",
]

VIDEO_URL = "https://api5-normal-sinfonlineb.fqnovel.com/novel/player/multi_video_model/v1/"
UA = "Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
APP_UA = "com.phoenix.read/71332 (Linux; U; Android 16; zh_CN; 25053RT47C; Build/BP2A.250605.031.A3; Cronet/TTNetVersion:04657795 2026-01-23 QuicVersion:c67e9834 2025-09-08)"
MEDIA_UA = "com.phoenix.read/71332"




_HTML_FETCH_ATTEMPTS = 3

_HTML_FETCH_BACKOFF_SECONDS = 1.5

_RANGE_FETCH_ATTEMPTS = 3

_RANGE_FETCH_BACKOFF_SECONDS = 0.8

class HongguoPluginError(RuntimeError):
    pass

def _text(value: Any) -> str:
    return str(value or "").strip()

def _first(*values: Any) -> str:
    for value in values:
        if isinstance(value, (list, tuple)):
            result = _first(*value)
        elif isinstance(value, Mapping):
            result = _first(
                value.get("url"),
                value.get("uri"),
                value.get("src"),
                value.get("download_url"),
                value.get("main_url"),
                value.get("backup_url"),
                value.get("backup_url_1"),
                value.get("play_addr"),
                value.get("url_list"),
            )
        else:
            result = _text(value)
        if result:
            return result
    return ""

def _json_response(response: requests.Response) -> Any:
    response.raise_for_status()
    try:
        return response.json()
    except ValueError as exc:
        raise HongguoPluginError("上游响应不是 JSON") from exc

def _get_html(url: str, *, attempts: int = _HTML_FETCH_ATTEMPTS) -> str:
    last_error: Exception | None = None
    for attempt in range(max(1, attempts)):
        try:
            response = requests.get(
                url,
                headers={
                    "User-Agent": UA,
                    "Accept-Language": "zh-CN,zh;q=0.9",
                },
                timeout=30,
            )
            response.raise_for_status()
            response.encoding = response.encoding or "utf-8"
            return response.text
        except Exception as error:  # transient proxy/DNS/read failures
            last_error = error
            if attempt + 1 < max(1, attempts):
                time.sleep(_HTML_FETCH_BACKOFF_SECONDS * (attempt + 1))
    raise HongguoPluginError(f"fetch failed: {url}") from last_error

def _router_data(html: str) -> dict[str, Any]:
    match = re.search(r"(?:window\.)?_ROUTER_DATA\s*=\s*", html)
    if not match:
        raise HongguoPluginError("页面没有路由数据")
    try:
        value, _ = json.JSONDecoder().raw_decode(html[match.end() :])
    except json.JSONDecodeError as exc:
        raise HongguoPluginError("页面路由数据解析失败") from exc
    if not isinstance(value, dict):
        raise HongguoPluginError("页面路由数据格式错误")
    return value

def _media_url(item: Mapping[str, Any]) -> str:
    return _first(
        item.get("main_url"),
        item.get("backup_url"),
        item.get("backup_url_1"),
        item.get("play_addr"),
        item.get("url"),
    )

def _spade_value(item: Mapping[str, Any]) -> str:
    encrypt_info = item.get("encrypt_info")
    if not isinstance(encrypt_info, Mapping):
        encrypt_info = {}
    return _first(item.get("spade_a"), encrypt_info.get("spade_a"))

def derive_content_key(spade_b64: str) -> bytes:
    raw = _b64(spade_b64)
    if len(raw) < 3:
        raise HongguoPluginError("spade_a 太短")
    v8 = len(raw) - (raw[0] ^ raw[1] ^ raw[2]) + 47
    if v8 <= 0 or 1 + v8 > len(raw):
        v8 = len(raw) - 1
    if v8 < 33:
        raise HongguoPluginError("spade_a 长度异常")
    value = bytearray(raw[1 : 1 + v8])
    va, vb = 85, 246
    for index in range(v8):
        previous = va if index & 1 else vb
        if index & 1:
            va = value[index]
        else:
            vb = value[index]
        value[index] = (-21 - bin(index).count("1") + (previous ^ value[index])) & 0xFF
    try:
        return binascii.unhexlify(bytes(value[1:33]).decode("ascii"))
    except (ValueError, binascii.Error) as exc:
        raise HongguoPluginError("spade_a 密钥材料无效") from exc

def _find_box(data: memoryview, fourcc: bytes, start: int) -> tuple[int, int]:
    for index in range(max(4, start), len(data) - 4):
        if data[index : index + 4] != fourcc:
            continue
        size = struct.unpack(">I", data[index - 4 : index])[0]
        if size == 1 and index + 12 <= len(data):
            size = struct.unpack(">Q", data[index + 4 : index + 12])[0]
        if 8 <= size <= 5_000_000 and index - 4 + size <= len(data):
            return index - 4, size
    return -1, 0

def _box_body(data: memoryview, fourcc: bytes, start: int) -> memoryview | None:
    offset, size = _find_box(data, fourcc, start)
    return data[offset + 8 : offset + size] if offset >= 0 else None

def _parse_track(
    moov: memoryview,
    track_offset: int,
) -> tuple[list[int], list[int], list[int], list[int], int, int] | None:
    if track_offset < 0:
        return None
    stbl_offset, _ = _find_box(moov, b"stbl", track_offset + 8)
    if stbl_offset < 0:
        return None
    stsz = _box_body(moov, b"stsz", stbl_offset)
    stco = _box_body(moov, b"stco", stbl_offset)
    co64 = _box_body(moov, b"co64", stbl_offset)
    stsc = _box_body(moov, b"stsc", stbl_offset)
    saiz = _box_body(moov, b"saiz", stbl_offset)
    saio = _box_body(moov, b"saio", stbl_offset)
    if any(value is None for value in (stsz, stsc, saiz, saio)) or (
        stco is None and co64 is None
    ):
        return None
    assert stsz is not None and stsc is not None
    assert saiz is not None and saio is not None
    default_size = struct.unpack(">I", stsz[4:8])[0]
    sample_count = struct.unpack(">I", stsz[8:12])[0]
    sizes = (
        [default_size] * sample_count
        if default_size
        else [
            struct.unpack(">I", stsz[12 + index * 4 : 16 + index * 4])[0]
            for index in range(sample_count)
        ]
    )
    chunk_table = stco if stco is not None else co64
    assert chunk_table is not None
    chunk_count = struct.unpack(">I", chunk_table[4:8])[0]
    chunk_width = 4 if stco is not None else 8
    offsets = [
        int.from_bytes(
            chunk_table[
                8 + index * chunk_width : 8 + (index + 1) * chunk_width
            ],
            "big",
        )
        for index in range(chunk_count)
    ]
    entry_count = struct.unpack(">I", stsc[4:8])[0]
    entries = [
        (
            struct.unpack(">I", stsc[8 + index * 12 : 12 + index * 12])[0],
            struct.unpack(">I", stsc[12 + index * 12 : 16 + index * 12])[0],
        )
        for index in range(entry_count)
    ]
    chunk_samples = [0] * chunk_count
    for index, (first_chunk, samples_per_chunk) in enumerate(entries):
        end = entries[index + 1][0] - 1 if index + 1 < len(entries) else chunk_count
        for chunk in range(first_chunk - 1, min(end, chunk_count)):
            chunk_samples[chunk] = samples_per_chunk
    saiz_flags = int.from_bytes(saiz[1:4], "big")
    saiz_cursor = 12 if saiz_flags & 1 else 4
    if len(saiz) < saiz_cursor + 5:
        return None
    default_aux_size = saiz[saiz_cursor]
    aux_count = struct.unpack(">I", saiz[saiz_cursor + 1 : saiz_cursor + 5])[0]
    aux_sizes = (
        [default_aux_size] * aux_count
        if default_aux_size
        else [
            int(saiz[saiz_cursor + 5 + index])
            for index in range(aux_count)
            if saiz_cursor + 5 + index < len(saiz)
        ]
    )
    if len(aux_sizes) != aux_count:
        return None
    saio_flags = int.from_bytes(saio[1:4], "big")
    saio_cursor = 12 if saio_flags & 1 else 4
    offset_width = 8 if saio[0] == 1 else 4
    if len(saio) < saio_cursor + 4 + offset_width:
        return None
    entry_count = int.from_bytes(saio[saio_cursor : saio_cursor + 4], "big")
    if entry_count < 1:
        return None
    aux_offset = int.from_bytes(
        saio[saio_cursor + 4 : saio_cursor + 4 + offset_width],
        "big",
    )
    return sizes, offsets, chunk_samples, aux_sizes, aux_offset, sample_count

def _replace_fourcc(data: bytearray, old: bytes, new: bytes) -> None:
    position = 0
    while True:
        position = data.find(old, position)
        if position < 0:
            return
        data[position : position + len(old)] = new
        position += len(new)

def _replace_sinf(data: bytearray) -> None:
    position = 0
    while True:
        position = data.find(b"sinf", position)
        if position < 0:
            return
        if position >= 4:
            size = struct.unpack(">I", data[position - 4 : position])[0]
            end = position - 4 + size
            if 8 <= size < 50_000 and end <= len(data):
                data[position : position + 4] = b"free"
                data[position + 4 : end] = b"\x00" * max(0, end - position - 4)
                position = end
                continue
        position += 4

def decrypt_mp4_cenc(data: bytes, content_key: bytes) -> bytes:
    if len(content_key) != 16:
        raise HongguoPluginError("CENC 密钥长度错误")
    result = bytearray(data)
    if len(result) < 16:
        raise HongguoPluginError("MP4 数据过短")
    moov_start, moov_size = _find_box(memoryview(result), b"moov", 0)
    if moov_start < 0 or moov_size < 8:
        raise HongguoPluginError("MP4 moov 越界")
    moov = memoryview(result)[moov_start : moov_start + moov_size]
    tracks: list[int] = []
    track_search = 0
    while True:
        track, track_size = _find_box(moov, b"trak", track_search)
        if track < 0:
            break
        tracks.append(track)
        track_search = track + max(track_size, 8)
    decrypted_samples = 0
    for track in tracks:
        parsed = _parse_track(moov, track)
        if parsed is None:
            continue
        sizes, offsets, chunk_counts, aux_sizes, aux_offset, sample_count = parsed
        aux_size = sum(max(size, 8) for size in aux_sizes)
        if not sample_count or aux_offset < 0 or aux_offset + aux_size > len(result):
            continue
        aux = result[aux_offset : aux_offset + aux_size]
        sample_index = 0
        aux_index = 0
        for chunk_index, chunk_offset in enumerate(offsets):
            current = chunk_offset
            for _ in range(chunk_counts[chunk_index]):
                if sample_index >= sample_count or sample_index >= len(sizes):
                    break
                size = sizes[sample_index]
                if current + size > len(result):
                    raise HongguoPluginError("MP4 样本越界")
                if sample_index >= len(aux_sizes):
                    raise HongguoPluginError("MP4 辅助信息数量不足")
                entry_size = max(aux_sizes[sample_index], 8)
                iv = bytes(aux[aux_index : aux_index + min(entry_size, 8)]).ljust(
                    8, b"\0"
                ) + b"\0" * 8
                result[current : current + size] = _aes_ctr_decrypt(
                    content_key, iv, bytes(result[current : current + size])
                )
                current += size
                sample_index += 1
                aux_index += entry_size
                decrypted_samples += 1
    if not decrypted_samples:
        raise HongguoPluginError("MP4 没有可解密的 CENC 样本")
    moov_buffer = bytearray(result[moov_start : moov_start + moov_size])
    _restore_cenc_codecs(moov_buffer)
    _replace_sinf(moov_buffer)
    result[moov_start : moov_start + moov_size] = moov_buffer
    return bytes(result)

MEDIA_HEADERS = {"User-Agent": MEDIA_UA, "Referer": "https://novel.snssdk.com/"}

_STREAM_PORT_RANGE = (9990, 10000)
_STREAM_CHUNK = 1 << 20
_STREAM_HEAD_PROBE = 1 << 16
_STREAM_TTL_SECONDS = 900
_STREAM_MAX_SESSIONS = 4
_STREAM_STATE: dict[str, Any] = {"port": 0, "server": None, "sessions": {}}
_STREAM_LOCK = threading.RLock()


def _toplevel_boxes(buf: bytes) -> list[tuple[int, int, bytes]]:
    boxes: list[tuple[int, int, bytes]] = []
    cursor = 0
    while cursor + 8 <= len(buf):
        size = struct.unpack(">I", buf[cursor : cursor + 4])[0]
        fourcc = bytes(buf[cursor + 4 : cursor + 8])
        if size == 1:
            if cursor + 16 > len(buf):
                break
            size = struct.unpack(">Q", buf[cursor + 8 : cursor + 16])[0]
        if size < 8:
            break
        boxes.append((cursor, size, fourcc))
        cursor += size
    return boxes


def _range_get(url: str, start: int, end: int) -> tuple[bytes, int]:
    headers = dict(MEDIA_HEADERS)
    headers["Range"] = "bytes=%d-%d" % (start, end)
    expected = end - start + 1
    last_error: Exception | None = None
    for attempt in range(_RANGE_FETCH_ATTEMPTS):
        if attempt:
            time.sleep(_RANGE_FETCH_BACKOFF_SECONDS * attempt)
        try:
            response = requests.get(url, headers=headers, timeout=60)
        except requests.RequestException as error:
            last_error = error
            continue
        if response.status_code not in (200, 206):
            last_error = HongguoPluginError(
                "媒体分片请求失败 %s" % response.status_code
            )
            continue
        body = response.content
        # 上游偶发返回短包；短于请求长度时重试，避免播放器收到截断数据。
        if not body or (response.status_code == 206 and len(body) < expected):
            last_error = HongguoPluginError(
                "媒体分片长度不足 %d/%d" % (len(body), expected)
            )
            continue
        total = 0
        content_range = response.headers.get("Content-Range") or ""
        if "/" in content_range:
            tail = content_range.rsplit("/", 1)[1].strip()
            if tail.isdigit():
                total = int(tail)
        if not total:
            length = response.headers.get("Content-Length") or ""
            total = int(length) if length.isdigit() else 0
        return body, total
    raise last_error or HongguoPluginError("媒体分片请求失败")


def _fetch_moov(url: str) -> tuple[int, int, bytes]:
    probe, total = _range_get(url, 0, _STREAM_HEAD_PROBE - 1)
    if not total:
        raise HongguoPluginError("媒体总长度未知")
    moov_start = 0
    moov_size = 0
    for offset, size, fourcc in _toplevel_boxes(probe):
        if fourcc == b"moov":
            moov_start = offset
            moov_size = size
            break
    if not moov_size:
        raise HongguoPluginError("未找到 moov 顶层盒")
    if moov_start + moov_size > total:
        raise HongguoPluginError("moov 越界")
    if moov_start + moov_size <= len(probe):
        return total, moov_start, bytes(probe[moov_start : moov_start + moov_size])
    moov, _ = _range_get(url, moov_start, moov_start + moov_size - 1)
    if len(moov) != moov_size:
        raise HongguoPluginError("moov 分片长度不符")
    return total, moov_start, moov


def _original_format_near(data: bytearray, entry_pos: int, default: bytes) -> bytes:
    """从 sample entry 后的 sinf/frma 读取原始四字符码（avc1/hvc1/mp4a 等）。"""
    blob = bytes(data[entry_pos : min(len(data), entry_pos + 800)])
    idx = 0
    while True:
        pos = blob.find(b"frma", idx)
        if pos < 0:
            return default
        if pos + 8 <= len(blob):
            fmt = bytes(blob[pos + 4 : pos + 8])
            if fmt not in (b"", b"\x00\x00\x00\x00", b"encv", b"enca") and all(32 <= c < 127 for c in fmt):
                return fmt
        idx = pos + 4


def _restore_cenc_codecs(data: bytearray) -> None:
    """把 encv/enca 还原为 frma 中的真实编码，避免一律改成 hvc1 导致只有声音。"""
    pos = 0
    while True:
        pos = data.find(b"encv", pos)
        if pos < 0:
            break
        data[pos : pos + 4] = _original_format_near(data, pos, b"avc1")
        pos += 4
    pos = 0
    while True:
        pos = data.find(b"enca", pos)
        if pos < 0:
            break
        data[pos : pos + 4] = _original_format_near(data, pos, b"mp4a")
        pos += 4


def _rewrite_moov(moov: bytes) -> bytes:
    result = bytearray(moov)
    _restore_cenc_codecs(result)
    _replace_sinf(result)
    return bytes(result)


def _sample_table(moov: bytes, moov_start: int) -> list[tuple[int, int, bytes]]:
    view = memoryview(moov)
    samples: list[tuple[int, int, bytes]] = []
    track_search = 0
    while True:
        track, track_size = _find_box(view, b"trak", track_search)
        if track < 0:
            break
        track_search = track + max(track_size, 8)
        parsed = _parse_track(view, track)
        if parsed is None:
            continue
        sizes, offsets, chunk_counts, aux_sizes, aux_offset, sample_count = parsed
        aux_length = sum(max(size, 8) for size in aux_sizes)
        aux_local = aux_offset - moov_start
        if aux_local < 0 or aux_local + aux_length > len(moov):
            raise HongguoPluginError("CENC 辅助信息不在 moov 内，无法流式解密")
        aux = moov[aux_local : aux_local + aux_length]
        sample_index = 0
        aux_index = 0
        for chunk_index, chunk_offset in enumerate(offsets):
            current = chunk_offset
            for _ in range(chunk_counts[chunk_index]):
                if sample_index >= sample_count or sample_index >= len(sizes):
                    break
                if sample_index >= len(aux_sizes):
                    raise HongguoPluginError("CENC 辅助信息数量不足")
                entry_size = max(aux_sizes[sample_index], 8)
                initial_vector = bytes(
                    aux[aux_index : aux_index + min(entry_size, 8)]
                ).ljust(8, b"\0") + b"\0" * 8
                samples.append((current, sizes[sample_index], initial_vector))
                current += sizes[sample_index]
                aux_index += entry_size
                sample_index += 1
    if not samples:
        raise HongguoPluginError("moov 中没有可解密的 CENC 样本")
    samples.sort()
    return samples


class _StreamSession:
    """按 Range 逐块拉取加密 MP4，边下边解 CENC，供本地播放器直连。"""

    def __init__(
        self,
        url: str,
        content_key: bytes,
        total: int,
        moov_start: int,
        moov: bytes,
    ) -> None:
        if len(content_key) != 16:
            raise HongguoPluginError("CENC 密钥长度错误")
        self.url = url
        self.content_key = content_key
        self.total = total
        self.moov_start = moov_start
        self.moov_plain = _rewrite_moov(moov)
        self.moov_end = moov_start + len(moov)
        self.samples = _sample_table(moov, moov_start)
        self.offsets = [item[0] for item in self.samples]
        self.created = time.time()

    def expired(self) -> bool:
        return time.time() - self.created > _STREAM_TTL_SECONDS

    def _patch(self, buffer: bytearray, base: int) -> None:
        end = base + len(buffer) - 1
        index = max(bisect.bisect_right(self.offsets, base) - 1, 0)
        while index < len(self.samples):
            offset, size, initial_vector = self.samples[index]
            index += 1
            if offset > end:
                break
            if offset + size <= base:
                continue
            first = max(offset, base)
            last = min(offset + size - 1, end)
            skip = first - offset
            counter = (
                (int.from_bytes(initial_vector, "big") + skip // 16)
                & ((1 << 128) - 1)
            ).to_bytes(16, "big")
            padding = skip % 16
            plain = _aes_ctr_decrypt(
                self.content_key,
                counter,
                b"\0" * padding + bytes(buffer[first - base : last - base + 1]),
            )
            buffer[first - base : last - base + 1] = plain[padding:]
        if base < self.moov_end and end >= self.moov_start:
            first = max(base, self.moov_start)
            last = min(end, self.moov_end - 1)
            buffer[first - base : last - base + 1] = self.moov_plain[
                first - self.moov_start : last - self.moov_start + 1
            ]

    def read_range(self, start: int, end: int) -> bytes:
        raw, _ = _range_get(self.url, start, end)
        if not raw:
            raise HongguoPluginError("媒体分片为空")
        buffer = bytearray(raw)
        self._patch(buffer, start)
        return bytes(buffer)

    def iter_range(self, start: int, end: int):
        cursor = start
        while cursor <= end:
            stop = min(cursor + _STREAM_CHUNK - 1, end)
            block = self.read_range(cursor, stop)
            yield block
            cursor += len(block)


def _stream_session(video_id: str, config: Mapping[str, Any], quality: str = "1080") -> "_StreamSession":
    quality = quality if quality in _QUALITY_LINE_NAME_TO_Q else "1080"
    cache_key = "%s|%s" % (video_id, quality)
    with _STREAM_LOCK:
        sessions = _STREAM_STATE["sessions"]
        for key in [key for key, item in sessions.items() if item.expired()]:
            sessions.pop(key, None)
        session = sessions.get(cache_key)
    if session is not None:
        return session
    model = _video_model(video_id, config)
    _, item = _select_quality(_video_list_from_model(model), quality)
    url = _media_url(item)
    spade = _spade_value(item)
    if not url or not spade:
        raise HongguoPluginError("播放模型缺少地址或密钥材料")
    key_seed = _key_seed_from_model(model)
    if key_seed:
        try:
            url = _decrypt_spade_url(url, key_seed)
        except HongguoPluginError:
            pass
    total, moov_start, moov = _fetch_moov(url)
    session = _StreamSession(url, derive_content_key(spade), total, moov_start, moov)
    with _STREAM_LOCK:
        sessions = _STREAM_STATE["sessions"]
        while len(sessions) >= _STREAM_MAX_SESSIONS:
            sessions.pop(next(iter(sessions)), None)
        sessions[cache_key] = session
    return session


_RANGE_UNSATISFIABLE = "unsatisfiable"

def _parse_range(value: str, total: int) -> Any:
    """解析 Range 头。返回 (start, end)、None（忽略）或 _RANGE_UNSATISFIABLE。"""
    text = (value or "").strip().lower()
    if not text.startswith("bytes="):
        return None
    spec = text[6:].split(",")[0].strip()
    if "-" not in spec:
        return None
    left, right = spec.split("-", 1)
    if not left:
        if not right.isdigit():
            return None
        length = min(int(right), total)
        if not length:
            return _RANGE_UNSATISFIABLE
        return total - length, total - 1
    if not left.isdigit():
        return None
    start = int(left)
    end = int(right) if right.isdigit() else total - 1
    end = min(end, total - 1)
    if start >= total or start > end:
        return _RANGE_UNSATISFIABLE
    return start, end


class _StreamHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "hg-stream"

    def log_message(self, *args: Any) -> None:
        return None

    def _params(self) -> dict[str, str]:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        video_id = (query.get("vid") or query.get("id") or [""])[0]
        if not video_id:
            video_id = parsed.path.rsplit("/", 1)[-1].split(".")[0]
        return {
            "vid": video_id if video_id.isdigit() else "",
            "quality": (query.get("q") or ["1080"])[0],
            "device_id": (query.get("did") or [""])[0],
            "install_id": (query.get("iid") or [""])[0],
        }

    def _fail(self, code: int, message: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(message)))
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            self.wfile.write(message)
        except OSError:
            pass

    def do_HEAD(self) -> None:  # noqa: N802 - 标准库回调命名
        self._serve(body=False)

    def do_GET(self) -> None:  # noqa: N802 - 标准库回调命名
        self._serve(body=True)

    def _serve(self, body: bool) -> None:
        route = urlparse(self.path).path
        if not route.endswith(".mp4"):
            self._fail(404, b"not found")
            return
        params = self._params()
        if not params["vid"]:
            self._fail(400, b"missing vid")
            return
        try:
            session = _stream_session(
                params["vid"],
                {
                    "device_id": params["device_id"],
                    "install_id": params["install_id"],
                },
                params["quality"],
            )
        except Exception:
            self._fail(502, b"media session failed")
            return
        raw_range = self.headers.get("Range") or ""
        requested = _parse_range(raw_range, session.total)
        if requested is _RANGE_UNSATISFIABLE:
            self.send_response(416)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Range", "bytes */%d" % session.total)
            self.send_header("Content-Length", "0")
            self.send_header("Connection", "close")
            self.end_headers()
            return
        start, end = requested if requested else (0, session.total - 1)
        self.send_response(206 if requested else 200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if requested:
            self.send_header(
                "Content-Range",
                "bytes %d-%d/%d" % (start, end, session.total),
            )
        self.end_headers()
        if not body:
            return
        try:
            for block in session.iter_range(start, end):
                self.wfile.write(block)
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        except Exception:
            self.close_connection = True


def _start_stream_server() -> int:
    with _STREAM_LOCK:
        if _STREAM_STATE["port"]:
            return int(_STREAM_STATE["port"])
        for port in range(_STREAM_PORT_RANGE[0], _STREAM_PORT_RANGE[1]):
            try:
                server = ThreadingHTTPServer(("127.0.0.1", port), _StreamHandler)
            except OSError:
                continue
            server.daemon_threads = True
            threading.Thread(target=server.serve_forever, daemon=True).start()
            _STREAM_STATE["port"] = port
            _STREAM_STATE["server"] = server
            return port
    return 0

def _b64(value: str) -> bytes:
    text = _text(value)
    text += "=" * (-len(text) % 4)
    try:
        return base64.b64decode(text)
    except (ValueError, binascii.Error):
        return base64.urlsafe_b64decode(text)

def _branch_one_bytes() -> bytes:
    if not hasattr(_branch_one_bytes, "value"):
        _branch_one_bytes.value = lzma.decompress(base64.b85decode(_BRANCH_ONE_B85))
    return _branch_one_bytes.value

_BRANCH_ONE_B85 = (
    '{Wp48S^xk9=GL@E0stWa761SMbT8$j;R-wN{#^houf7QIIVU7<Ew*6C3?&vQR7`VixMIZH9HyzSRN)dgt5HsOFl)*@6hSxGmq5aA'
    'QqcTJ>uEXt3ca?@+^++8<`vdWaS1a!^(@3piHN^UDea^utz&m68PwK)la*43U*mNYT~Az3vWRR9M@u9%`>|`oTuVAm{6Xbi7<B{L'
    '+9%}E{{R4tW;N$iTuuPgJ`u;tZ?qE#6f{J&gM{zloCXZoG-hquoMj#I1srY?B&~p9xgbUzb@!5*4S7ma&y#>iUoW)6rJ_BOyLIpL'
    'xODyDEOHDUy)Hr^$hEEodD$hbGrZQIEu8`Tb_H;~Z>VMWKW5~p-hONtZJoi*u&tO=m69!Z>V7E`+W`F%rB6Z`>9J*SJ%Azqgna;j'
    'pyLxZi;ycJaM~j<o%H|7!w`?YyEm7i6pMnWxuw4z`~B6UKR|wY@2gl<iXrJDd{_1*$qp;ibMN}xIL<*Gi$aI_ToO8niDZ|W6uz1!'
    '%)Ofu3qfRq1h1p__0g|vqG(?;aP76#`-*@WsTbSc98!AL83wt_4q^NHqSkY?D&ko53i_{F9n~l_{x^5C{H|fMAIX4f`wb7ERjZ3y'
    '+#;VMHu5P=Jv3&yp^-ASDTXYC%$TxN7n?j-=xsY0676yMQ)eWeYkG3JD<>_>t{HhAIxC^4(?8&VcUx=ux(qrgcIAXU5Yosc?z1$('
    'FqfP|)2$ve(&}uw;(uxdO>E6dMMn^`79eTmC_B=qkOB^y=1A8sQi<MgW~fDdW0t4{^<IjM^J?x<&Z1M)pYO&uEA!yRw?Np_Eoi{o'
    'V9dD%VA6x*g>j#h5;4}+#ILn~##Qh5V8-%l`Cgcy0u7DR!N$07Q0#BWZ9icP<a5UiL*HS#iW;QiR{)ut8&c9ibCtR^s-hvxT<B5I'
    'pZF*<3Mz685I{5Bn03e7@&D%xea0+oBiI=#Ay^38D377%<QuMZ-O*%Tv;8|=X7k@BR9~m7iE|@?x%zlQ3NE968S;+Y@OKTIO1nRQ'
    '%$PlmG26EWG&hsL(A8Kvzr*S5Ay&gwR^Qs5EP|lmJc;6eX{5+3>-W3P^XQYY)|Xa<5v$^`p|naVLW^*4x>oTf$}?2%{6bD};l{wp'
    'UXx&>{O<J~x}|>(!V18p93xBW_5+H#yeu03vRjESLXD$A9{yVQwj)I(NohO>ORrTjPEA{?DAU0dxSX!K7471{McHXwNi-H;o*fS{'
    'A^u%?y|GH!Rj#yLuLt`!o<Kf)Y(ZpN4Tz3<fO`#$DE7bF-%oqDst*3_DWg8nZiEfL0Og$<i9XRgsx?2^G>t{jYLYX|a)tAG>|ahQ'
    '(CvT4r8nG+e1c=US5#<;4qieQKmF}v#Lir5E|do?DhNZDSa32d|8J@+jja&PG#}{s>QAtW@PV$U?q=(1XE9c#V$_wg+bp&V&B)eE'
    'w|E7%&@=fW46%KQT|hx-6(^7@;GSAuQiVAKWj{$=N<Dko+Tu^~&_g4k&tWyT+RiABes%c{2GlZizn~-ml%l&HeCQ7Y89{*{FhFJ$'
    '%A0T5Ok9YTqU!Y`FOD0Vll<93GAUvEw{f##S5Na@_<&-g^C8;XNP;Jns4P4`9G&OuVy9F{ye}9pZXFBGaV{9GqWseFXXDkv-Jtr#'
    'X`v5*<V}u7WzA@LlIItpV&L%Dnu!B`Tlz^fO$|&4Ecr^f5@l|Pk*?l`Q0k`=`(J9}mTP!oxXK|5+g>iFaV|-^t;>U+e*p}pUxsGg'
    'R<;C@A<@#B?1bIdg$yI+yA6AxY23cPa12A79#Fv)!=h0N+GRs0Kg078`}Jx76kkmF2?7`fU$Lt8m3@5>LUp7)McaOF3%leJQMA(V'
    'z#j;PC$N!2YwiDp$FdZE3B6)aNBYUa(TNaoy8X~=byBHab^*nv9%*}Rf54ca_b0AXoR_G3a@6Q#ZFpU^6?~3S9&n|oyDT=y+-aSh'
    'n_@mxq0;KkI{N4=aOj0w-G;T1{5|jUk~rpYu}~n&xeXONR{x@w=wxoIjOh3^cwp6#*_zNzKwGmt%gS9r?F8cMjKT$lB|br+51yB2'
    '=wZV7fy7D{`(29#`6Q#QIa%hm)is>KD_ry#_H*-F*|Z?%Qv8Wrj@X=do{p=*x3Fz@7wS7@0b~~-n@Ufde^yLqtQCm?0O`Da6nn-j'
    'r9Pog2fjAFwY<gel`&!+$DANDLZf`IKhg4BZGPdEYX1n!8rS+gQ7lP{?{KO45vsUu2dS7*+lGbck?L*-g91mpEav%V%JY1;m@7bb'
    '!~8*@(PmIx$hM4)kQD#-N9l_sU8UpQyq;#!2cR64Gr9}3BImqV(P!p6uw?K%E^%~`2F*P-WIQ3uw-kIk4m<8@RYF5W+XhoQx`p6k'
    '+9I#{E}8>IJkyQ%q6436nF9t#Lsz;}b$hp5{_)$_DwZec8D&xJpU4!-(s}b112NIK72XtvrrGX22}y~3_iro{&MnhETA+DaK?Xi('
    'Q0J_&dFeJ5#7fK#kt7e^e@c1D7iOsd7Y$~wsRTJ#qi|^(h#yWd2}FIU8B9IG^z<X74^tO-6ur(^CZ13AW`UFbC{Pe%@)oIN45MqI'
    'PHdq9D!Kbze*P?h!OC)3qiB!l?49WS?)rHvoGtFxap`)w1=tf8AMQ5IfrG3!9*(uQp>&-907)*(j!(qXjiLbP^#}@|w33k4F~`7m'
    'K~fLbR%d?z%hl(M*M#B6)+ez&D3$JDYg5AF2vDMPEE2G;dt-P!gtE!qaJ41%TjxghS@IBUwUEIbBB|AJ4?hq}BLavJ+^|F^sE80o'
    'uLA?B96n!Yic+9jWQ6baLx|+P0BjCKJP6CmKDt5GssWs1oekHG4ifxLAKG`*ebaE=-5kobMB}Pz;R0REqN-x}q3%W$B*jB?E{A%B'
    '2MhzK1%uoumz1tpa`{9cjKqgYo(@1|z(N)PeGvIibln>rkSAlt;@TjZ46mVE-PxOR1;;0DloppysYZl<liKBRKRt?9$YPa;+3T}O'
    'tk(2rC{(dZQ`ym+rqP^|wr0OI>e6G|A!P|?bB1T7wCbzf01t(nEUGrFWjeMlraZ}~O%Xn~3S`Ij?3XhZJj44r^n=^V1+N&4lbxGo'
    '0!x)@u1Oh2G558Kzoz_xRv^@R+Sg`Cz7G*Hrru<u)3M&MHearUo8*q=Tm|q>F#dZW2&@Gr5H7wXs&LAz?4wE7`UwBTRkeMY-w&~x'
    'xYPt=bzf(89ffpeR@daZBH>+i&9AQXz8Ag>QY~)CA!cmHgH<ADaviZ)5dYJuj+}hxlHaonh`lzE$v|TZ2F?t}1iK6w3;xx3i`k5E'
    '3fT8$h)$9gl59pjn9!Wyy(CiSm)fITqjj_HC6bB*xqNUV@F%^;AJG{&N#upHz)q{2eGtJ{3Vt*~?n6mbI5?3tt&&kjlS^Jk`5AKk'
    'stC&F!}ev&(y?w&Bj#pL<xuFqZlgCPdA=?Pv0St5C9@`p^%+}>PV`CM4&WXiAA=p%;HSE^I8hyHb@HbJlKm9(B<&rvxIdWJ!Ra`W'
    'hBT1d#{e#>cz9y9sU9Z>FD5Whu?djyd$z^Ls@m~rs_#3A*V$?hFlmO6p0uz~8wP--L+&#T9-XiXKJ4AQ%8r0jK1b6h*9Wi$-*5_l'
    'O#gg!K%y%um(KnRmO)=2JlcF+X}hP7Gn{v@AW+9!+?D4&s3dzwJ?<}0CzFsHw)I`q@f#x}7%g)SCviR=d%M!Rmu0E64)p8)od~J;'
    '`uAVx3hx(ZmT&ZB5FN_#N-S9Eo!g%GuzQb%boa1Ar5RHkT*|?FDT530rxbxdzA|UYb0wSBm%7Qn@nee@gz=>xU=<{_-qSfw5uiL;'
    'Mw2t@X*I@v5gyeO;Azw^vnq!jZL<eeC#YGoyR%FFGgKx7>CTY%Y{$jEnTUhmlE>vWa&xR^daeIgtPS9t@UxM+5D(jQtQ_K#m>{iU'
    'O?L(Lsk3<&K&Ums!V4(!0{&6z@!u^0I%2ikvMuCv?M%o^RU4iL9Ul=Tq`Qq@Y|gl{oFV~Pg{3!t#0?>Pb^@f|3o+DkcL3`=U&&99'
    'n1ipU;k(6$Nz26d3+X9kD2Xa;);f=qm`iT8!@&Qu*cJ5i_@Hd;W4ON2#^@~rt|oiREpd1zc0fLvL#d((Kta6BI3vAn-V@xZV6?gw'
    'BF+>*#3Zvm$iZ0&*L4xFf>P65Fs@w&+C#wM^s41lRJlT>3OUK+H|^M(l{gmrAm#*VIo*I{)6)`Nzr6!nmw#7l;a=;Tn6ly2vS7=!'
    '4~fE_r9)9&$7RnSmaUHleEM)gsGR)UePI2Z;ewO0?U{4Hj^NSpP?ZKTS1ny~#up6i*JvMIBxfjm6!LI8GWXS)_4~GP0Tc`k@RHlb'
    '?H*yz0Ro+%R`J|{HtsE%xxbx|k*{5o_xZfD-4bteruCah1ep@1vlv6^uCy1}`{fpW42@`+Mu;V?l$yPujd?<|dg(yXnEsC)#1?($'
    'zKI!)WJ{_o-+z`%>g@GCWa}v981h|wyGx=%oNo$4GCZGs6t-$my{R~~VT)-|t0xOmFH*mG*~zgs#tB&P;ZmopQC~^2%k>{0d<p}3'
    'yiuQU#kl%qM@J@o1s$0?AI$+a`tuRJtV4h2xCDaOMA266*nM}E2{;$JcVMOTdlEtNJv@?I-2L%@2q=VCUrysWM}fF%iaD0e+pt)O'
    '8cDVSi$j093_3X&BFLbb<ehj->IwfZ|8hkc56tni&2PBSpf)>hw3C=z-?+kQb#d26(o17askq>W4Pr};0!JE#@sxOF9my2)h<;cb'
    'qT6pG$%k6+f=FhWam9}cQRXZN5wlU$%U1vcZ{jIriu^h(0M*xQrm~b4xv+A)2*h{|*OUZHRs|f|)GEKa&*g~)W2TtT@sp!Yi~Jp6'
    'wj$ze7Qh-nn-d7f*<Tva>4;;Fh?D`p1icS86F*iA9ztj-WD$>79%gsB#1FbG{_>5LsYa?X69@8s3xd{bEr<N~$Y>`6YU0#ux0)++'
    '_%@p1W~Su8mIu&SDyjn!G5Qr|8K|Nb9}JFJojQ+6p^;w+uT6lnyKtZS=3elR)`hl>nFV_s<6^h;+(3*4)YFb;uPh2sE(;xkw=o({'
    'rYtN4S@zdyB7&z_aWQZ;0%0E*48M`@aATEdR@V13+j;5YhV?niH+U<3IVS)kl|v>n;TU6E(jG84m^*Zt2HF%yZ60921r25wAoevU'
    'fmk@6FhGsIlMK1CsV8Jm4?>-}sW4nU_xov}%a{Q;0GBl>+%-!r4`9mrOw6!D_zy3Kwa6^~rCkp^A1C1|-Jv*l9M=p(toY6>j|X}F'
    '&J*W-E$Lo`K*Nd<EoHO-T}2;3saoc$h$~Cga?D2<*&5Hg46wV3^&u}eJhkX|agkeS8;CBK7iTXMl!@!z3#Xf2x*z*nF)B7N^U=Vx'
    'B1}XSW_z$tJhrx*(Dmrr(Zpe6?bMoEU}Hd$5nq02d;8BUsG-9!=<GO0R|^ib3p+0%`}yu_v~J#U1ypv5yk<wJ>O**eB~TiY`XMSO'
    'jw!2tgE@FcbNS9HRi#}gs*>CRWVgjZ+WHLslM%L{zLlX8<O*U*kHTO10bKQ!rz((U%!zunm{*;U4v`f=tki_GYSn_(WA2Q8P=Uk7'
    'YSNM`v$C{T^NR!Hx9ak32Of6EQM^virk&Mt_!gSCwpt|c<Bx7L(PQoVzQ$tp*1$Qn_;wc}g~yzw-duDWuhv`_SQ;@;W)swM@m4Vb'
    'W8AezVn#N9$eYHZ>k>UAErfG>z6II2{1c-NL1G~)I^m>#6?6%=NdcxVnD#ni3uWui)jx9C4=W~kLY|Oe*bewS|N8*!A|#x($!+mR'
    '&gaDU{A&eA&TJ~XwQ`Fl%NrdX4IS10ui2`WfEQ~bHe>|0ky9r;QeKb->WHB`kP<Z+-rb-v6%0~3m7?si`($DP(UgVNbXscA-z7T&'
    'BXqY|qYp+5s?p-tV9KAT`%Lp&5FG+vd$KsO$q>(B+bZ<Ei~zr+3)btP8>-ZV!rzOtPOZt8Tzpn97eQ+wLh9Tl!))xz{-b2}kkE)X'
    'EJG1G<A2Xjg)~Ie>3IPJPD;I6su@*;N(}z!o7+h>cAl{jEcZ2<pFrdhcbK-&I%8!iASA~9B`vDzLN3vW`c883<BT$M^gS3-#&^WI'
    'LaPGGG|E;t&g46)d;@BlL&Y*3TS~FomoxyY%V}Pk=!S-=MV^{`_4HbM-h9Yp8TC*Z1}*{l<!U)PYL@jc@=-i0{QK6{pE8y3AC#bp'
    'l9ydw1bx^a*@@o{E{{lozQxm*zb2_;&9t(7?XIcrpX$(_zxvcvGE?2(4pMG#-_Z%)u7M(X#=t?VqDUmnx$qkPx5p43&eK|G@e;E*'
    'bjQLK!U%%6Tou#CZjwn|W-T|PT}A8LCPa(L@7n%1m>lfCJ3Ne0NKDBGgit}LYoOSmsl1ef0PEllmj*@Js#r6w08Lh9+bSeom$_*!'
    '5|r6Y4Dx}JPapC_RA{VAT|+ZpKEEoA@4)`4S6pmCKGSZTTrRNRB@V7-ucDbG4nM^oJlA)h97s`h>~c&iC{2ig!d1#Ms|2EpI4<pg'
    '5{k+uapUbX&0|$96o+LU(VI+VYjGtVqIV$Uh3`7JiA?nYTAi`>VS+bD+GS(^tdl5+xK6nJ(&b5xU~owi2wxtJwuQfZM9MOwx0S&Y'
    '0M|tBN1P+_SY#BSCCwPqU4kW7U(8c0F&W4nF1xcA91f)B#zz{gL3*#w7izhnq>*o-vc{mLA5QT^YFI*ri12A+GoT(*4sD|;Di3L;'
    'ddvAmG-l-X;ZAVo5xfgM2m#Lip2TfW%kJ?d*tAJDuo;B0EcW}mr$d+~fQI<{!iGQe0|xatE}eU4w=svBpHR<fP(6WoFy&FT8NGV8'
    '(&Q+7Y;%mbwDXyAtMj{#^RRn?x;8cRw3_SKOUhQYa!+q1OWqIlj)JZrOT^1u$Bu;$Y{3nEyc7#(9Oelrup)4yx6w}}2nJRD4O|)s'
    '%rB{_+nfdK5eNdcBW`Z9BIod+IMwsclUxn(!bp2P0C7SD8_EA1q+IBikyuTHEyw!3xuIJaTvfb8c7EPcg_1Q!C~I+Tu`$dQ^{tD8'
    'gUR^F@;|pVI(>9nV9L4ct5-EG*Q2vOh7|QvY@fsu-mx4=)2$W&H%Bv*6Pkqo!X)sGUjZ*w?($clu1BKNR!cvm&l_A4!QaMjH<)|8'
    'n~62K-9(7nUGvuX);0QFvfsj__uhI8O;kdf<L3V*IPRzzDHf|ly5R+Y${!EQG?PpmLmZcy7n{u5$Ua0QuI(2yZsq;qPVdC}peq^0'
    'z<@pjzs`{sAq=EiGu9Zu+w$ZG0ss(;51f8bw)di87Zb5v+Ng67DfaSH=IO^;AYi6tkt^qUHR;7g(k?Vefu`^xoQN4#U)%-JB;8EM'
    'fQT`aG&H`LFoR8qO}2be^6`gmM;n?H_TU9O4M)BE6(zNvxy&tDQKK}R@Gy?a8rvU7vhZ$)+ei#!QQJ+GjyN1|T=)K-%FGHQA}M(+'
    '{CK+xt4R$YYgYPkZ+(JWiO4IwTumqD+v@f?=)w_CvftQMa>TFkgOHe@qOnFRSEJtXUJpu+LXnR*N4v`Q83l2{m1<!7cv4+eKzRpV'
    '2($w<QJ-5OPeQ6Sbs3`oUsgo-SIo}`aMI5R709Et|3kbwyohKtqkky8-SiNU-g&<Xqi5x&!-HhOoNw8lf3gR}HgICxVvi_#kSC9)'
    'wB!Ay+V?oB77Gr3qCQPEpF`s{=+%{~77M(Qz%mS?J$rj8RIJhq*k~4KsnvBFZi)F2=<j9bv;N`cK71xsd^U=)`imfOGvOI6yCL9t'
    'u&`eXa1#S>pvspU*&UREpagCvg(lKkm+jlKin}pFVycXE6L%w(vH&1}baI9hBwpzi>I<c3v>O466<?IPbZQ=$JR~w7xp*k*VFacd'
    'Ev$B@D+QyksU7=6>7L%@%{_50Sj9%@XzeAAOqip=#fq?ykn4q)2(|F|?HnUV5;G%>lG*m}Au;xPFQ4(+j;)-1SD^9BtFjE^O?z}w'
    'uU|!m6Hy#z2M>UblgTLeaF%`8f16wkT><Ui+TSp}e70Y3l6@Zywj0Dv=uQd*K9?KRag-yLHji0#P!`p}>fnKbEb?e@em~s>XttyK'
    ')TceKHQ-~Tnz{k+grpi-x2T;K=yM_^%S`iDEe!1{lj%g!G~tdPIc}F1V7n8}8Nk*~w27SR70RK(##!BZ^@G6-XQEb<XjCmyJeW|2'
    'XX0>9t|3(uBG74aC&5gMh<}|_L8@RrOvt1qn^KyK5@*eAErDMMa|H4mlpeX~;P@EIw^#%8$Fs3W*5yK!O*hzqcb-^@pHmxbYO?i7'
    '&%4x!c>e_}-F<nWRhBR%3=2)xzCHs^{<K7x*m|<326#w9!z`yerW1}xe5UXui?A2ej9YGoX%gTbL03dT!(E(sf>%GGS6Z3v%bqA9'
    '4&dC6(7GuQAaO7{=>r%0nX@Q*tc%Q^bME5x!^o=9e2DXGmRdV?tK*Ze`U*vd^Cc)i6G=%2lu6SA329j44pM323>Q}aW6O}TIN}PJ'
    '(Y^EKmiAHwt}ZeXj;B$)P;W3qGjf*z6K>R6{s4ufaa%$47e&d32a{7%7`^=alj<NPhZ@hrzhw;a#18X!#z3;X>ldOIo_7_`9PMfV'
    '<86~9RK11O2Dr2@VfeqJ)icEr(oVh{jrh*<GEoJ|tt|5^L>o6W7ZNCf8jo-ka?*2<v*ArvW?28ls)^>>c9zWz4|pJ^$coH__5~}='
    'Mj)2(s#paw69f{;*cw2J!qurM{7Qwa!$noN5)<Y#1iWs;q8UC~2obh<a3<t9LyEgExq<yEfT4Mm(C+LE$m6s3$VS9bKkfQ)EW0|@'
    '!lyspCdGd}*}LySa=mo}lm^U7;%hc6_b*`k*A>PTcp)EoZhP@)Myju?zy}cv6x0d0J+gd~7-ByisLI|O>X~<X^2b7+uyX?^w|Qy#'
    'cod8xtTucA9uQ#BEVOLX@^ZZJDym^TA&G^UOd-BN3&jFO%zpa1qAQBQ$2$KwYFL7gnc?1|NCtBU)c5g*+y+O?9GPn%0BPvtEY&Zk'
    'Y906LZ{vwED1*AK5pGUF)e!*f0FPgD(Ecs+F0R<)qqRk)^WcrAhga_e#QaKU7;tDMj0Qi0)yCV!K&A&}V+zYx9w#aTHoOz6Ws^NO'
    'e}@L5x^ldz@k_mQM9=dhSxYFr*K1pdF&=LR3FTQz=m0rD>HCtJRO%=b97P3M=iYoR9501E+f|zhkdjB-ml5ulYLJmy$;X})JU$+3'
    'zyNT=s|&ZPb^&RRoPE7Wytzt^5i^-iyOFQO{2n1MjAr68i#lYjQNZ>4=eooL+zpM&E4Jkv6N6AKqDj9<zDA8vb>hEF2H3f)Ehqph'
    'I$`&19~xp|KthQK>8t|DOAF0Fq&AUnTMuf6Q`n`VsVE(_4L~E!cl}FQDg=W+@HIkucI9Q2%PY>X`q)7P!lf>fPm4&yX5&a%bZKEy'
    'm}FRrxHg!l1$y9y<eVyWWULXlDoC2j#@XxmXGO+0F>Ss$ukj&~twB;p_?hAab<M?AcX8KE2>Q`}9Mgt9Y23OF3A&X_>oGi<n#;$j'
    'BEXenz0@hx%7?+1$S)@(_&&O+g8x<~E>GXT>tUe>LAG~6d7{>2=VA?$j2svmjI9LncaGVXPfjK{J9fDKJ}7Z+(7%Sy;<ZL>Z?g;K'
    '7rYq|cO>Ma^A(!fsLpc`Ov($85(=_aJTcHz>vfvj)8LIb_vkeqBjdiddaQl$Cgs@;xAk@-%pjZ7;VnIFoD7wecc47Pj<RPokEU=w'
    'k{h%I+G>S4z<AO|;h%k8`JLh<>81ELs8~#u1ku8y@4?1EzR}~D^1Xc-^Z2{`=hMlANbzs{o6#@S2T!_-b^~V`zxQ4kKB^mHF*;r*'
    '6Y@H<<CsJa#Oq9;Y*T66-+(OWBOb*~$-hGY(K7#g?h&LUPT{hU3VT6*2i0(+uiRoUs&{rWb7?y8c*ao7<8qnl%F@!3zh{8F`$Gg&'
    'b6*)k5j6>d&y(Wf(Y&q8zyyKBlvy}_Y&I{%!f#$Dgrs}F>QGh*hn2}#WNst6!Q?wz%p0W6njR>>cz6a+No<0vS!G=N!4Y^o+q-*U'
    'yD$@p!i|$I@`{X;v1fX|k5z*J{TaL8RKb)T!vpi_gd$?mOSdG)%3qc4ix46SfP;eZM#Ii((=+We!%sKq3UCXmEEi`{eY;(`rmdqV'
    '9;(y1{6niqWj$+zPeg4?MY__EReO|KGj2}I%NObBmiEKx{CB!o=SIv4ZU2KJOMhs^ZQqbs7obl9^|8){XqaNp+(039&^000Sa^h&'
    '24%u1SGd{X;_&jh|1^|z3t%L-=xP*V!u%w_`$IegUxv>39@ku+aJiCq1DyW6ayl{SLUVR268{cZ7$oh(Yh~pAabC9C3`>B^8i3jw'
    'cgyaT1*d%;V&x2?QGZSpJyN+@7O?W_)zWXN34Eoez%c<|^4mu<_KPoCRvjokm69iJ4ACJ``8J)wK6{|9dL=2{C6~&fSHc!~4x&mH'
    '_m^imaD|EzFcow!V^y|CI~T6}1`sCH{ZqL`LG|rvl7UeLtOOY@id@bc${0dnFCBGw(}}p5kA*qB*?g^Av553SNeW~CO`9#pr~P~q'
    '%2(z1>q&+-X%*JJebW#_MD4<r^+IaE>N8WZk!u)-rsr(5H2#)1>;iC;@*8I^B<*_|q=T2tOtpm+K=Fe3%P2`ymsz;GR59Gb&>srW'
    'k#lwi!x3Q1M?^Q_<cIisHUzTJY$N3z)A9V)KS%uUyAm9`?zuUXoQ8vEg0n7WrlI?l*AF8zz>enuOH=X*9c}(leKhA-qQ;462_!#*'
    'Pe?r;M_4Nwfd6-`X_Fb!6PT-;zt-+O=^Jz`-JR1V@B4I>eR+ho00s6eD;9FgSLqH1wV%@F^$gs>b_zxfvulv|;zIweZ5Vbbca$B6'
    's@#B6JERzQvsUQ5FOrX6>Ta#RVTbm@km0(utG&Ke1hcv4<CvH{mGy&ILfBTA0o8ZZ1yM{x%H^Or5jf6J?=L-8d`Ya2m=(uTGO(Da'
    '+OM)bRzW@xBd(3xkWyM7Sk5&>&zdr8=7AX+Cb8!iUv`?$Cq*}DTOxb>yY`v7Cd1^lBF*GQTHc<l`m>8cuX*^|dmbpr#7tt6J$t`2'
    'h)c&z03gs}>eWqo9~BsDzYw8VZ6t&9<r_cb_PL<iu1K~&p<x4ObUO@n)&_pV((HP8j(!4Ww}-b-@l3#jzoJ^zW)Jo46N+raSUzhe'
    'o4wrTSZg;LJ1h4I{|#Q%(7-J<6D|@$s3p&ODUo<=7_k%O=0@CARS{8;_fY&6rPJsyQsdN=7DTusc*zmfTSW#9-e%EgiE9KQAk5kw'
    'P#)s%h|B`?%7FRrlADbY5i^sEZ?Mf2zcdq{@_fYD`^h=Lb+Tf><b*ta)$~*?$wYK3e83b!e%;JNFx@0zqOzKQZvWwq$BWy6$9API'
    'VZFw%dKnNS5G{^7$afAKLlLTtPwQCM61v<iaU7i84HGLfXsmQlak5RJ43|%i0sgQ!s?GS>oB-kd;m}c>Izd7vAu#xnYZ<?hz~f&_'
    'MO+7}p@|VlWy(`;rl}eCv@HpK9@mUp=M^5uaE0Z4`=_CWa2@hJV<v*B=N%VWl=bFii>TO{a)*YzAsX^Qw(@XZj})i?G07nV$&I;u'
    '%-}gIAIQPL7P;M2&tpL#^K}aqG%oNFJ061=`7vO4x-ZAbJcX|RkE@67);I>}p(7-Ot61m>5`pjRH#8yI+EnmtUM@g1|3oI-8o7kQ'
    'XFxJ3X{~ep;*5O>;?GCGNf3Ik+hbD|lDo}<_L0>GCo1cOkABa4L!<<fmJ!BQ?Hf-8V!dr8IOEP$F}zZBcRVol^D#-;-~Eq0?l>eU'
    'DiRZy@DdfK8_H;A2RBmyBu5ZmFRm|Kh^9CX2Dc?c6B)~b(4p0LX-x-@DseT}jD`^fcOOR9jVk-wZE`NTC<l2ZQJWS7TvShg%Z(*E'
    'r{T;Db4-Z)Wjw`1c%U1gbN9^OAQQkl>?z!~Skzxz2-410{ur4^P<f)v|DZ}t_132kScw^ni-t%9k9XMrWAC*RoMY0gP2|l7wl?CI'
    'fX=R%qA=dXXCFt;2%Z3h9<+nW(5GWU%O+DyU5xND_xM+(3p4ggSuW|atHu^~y)H0&E|IuYsXqh3h}*P;fn&8WyoXi?V)la^6zOKu'
    '0vPp6HamL%z_>17CZsM5cApJR_U{*36Rh0h1qlg3`kuxmj1&4b_-W|F?OQDMg~ISMnec^>kZuYed)n)eYCT;B;t?v6o&>CS{dIJm'
    'h+srIc=rKUx*PB&ReQB1P*m=|g>X^-8n@c_m4^3iHpF~BR2j1EI74nv+CT=J`mNSK0i?*esv~zHAWK1x+Z%Yz5%)Oas!b@;O^G+P'
    'Scz$&p&^ff`xXeMo?%gXzQkm3#=HuMGK?FzmL!C?%B#M|2k{G&_vC)4OZVM28#w-UaR0hi;XXd01qr7u-w6jPmXxv^G669<bmU^g'
    'k+MH?ay-OD9|W;<mF$7y>9cdq_xA7mS@3B-o8AmW1LfQ1--jU<l8po8B(RMIo!<!Fb{Lh&1{Sgq+Uh1dOGN;4W@+k{BojfHpr&UA'
    'oO%t3YNigNl<aCMd9FH7xz7`w_R8vdsng;ID{aN*OoF$jqkTB3IEb2X4@4`kt`e3B+FVzcN>}%nDEQnRap1LS{?U~c4DpUHhY0S6'
    'A25$sj&A}-vlo!^Aj7uuHfJo4AF9&@aQcBJGxwBs1gSWVx_uERU~L*5S%AWc0x{~y*^HAe`tvS8B{lhL!;4_w)`h|Gd}2C3lNnXv'
    'D%j)-sc+g0Yqn=4?L9(NP}4E9ad&rw1)lI%AV*+j7sEtnt4A5pN*{C(Jf&<7xN1};$2>_POQ;>Il&(22NkLQ`Bou-_`OI(4!JWTL'
    'RXZircVC}Jyq>2M4z=*F(Jj?T{Zv>@X{h!2aAq<jyp7FRb2c9oI^0V46t%WfhFk;cd#qtsl+541VDLDia;TeZg(OgpD#k_6MMBC9'
    'VKMoyj--blBNw>I`O+zniuZIe{-amNawhrOslk5blTTIXyeg)+>r|=?Qr<-t!EHSMqlhJI4%Nkm3hZ_Y-<|;Im_2<>Q?cf3YCTp}'
    'xD9UFPR6GR*P6ZhzS25DiP4&TSD<oQpT!6Gs>7Ce$--6qbV_n?RF?+>$8I2x5+}Wy!@D3%z@X%J!!nS-qms$q)YOrjaNG@3F2JeI'
    'B11G89c#!QRdEil3SS2Dcnx1iDNx4pwR7xdP$NK)7b!FPocY>_k@q|ua8R;6)J3Qk0h+YL_iRENH_!Lu9RP3h3_ksx^LPNmXlY!{'
    '7y`-skrRe=0^nqUEM%ZKm{T+YFg+{ama`H$UfOu|Wo}{~Q`BSA6bB`&x3baJSvimiBd(B5ZRC?ntIf;FDi^~|FS~vN;b7}SAjEQE'
    'NTqu30xy1@Wo%8r|4vgb{Yrd0;iN5E6jIh5Rqv4W^h#gT-7@MKFZ93v`_3A;JN=uCYZaY$MbH~=2QSWKOa(W-8el4Rrqrw}0UqvW'
    'P{g<?Bt(*K@H)3PwgsJ2FAd%whMYD`#D{0sxpx!Y>0e+C5|+DNKFUJcasKKjYAptG%7uRTSR<4>lHQWJAhTvl%mRf9J|F2jA1VCT'
    'gN{3cA?R97Pqm#W3xbIEg_2nC;2x1T=Vnp5tTwP{Ju9N9BufCnfhrWLxnbVa>Nbg9{u4TMXk;+<XO)1>SDrjnN^zdI7K@#L(GW}r'
    '1$=l=ni>jyarNmc<82Z4`)X3yy%w^5i0Y*JfayxJ_Qa-04?vh6Fk8s&`+ej56KkW=49@=^@F07CsUMw7*jhgv%4+P~bl*CSz{!U>'
    '0tv<kS^Y)vpjZ06U*eTPN8;lIA4NNo?DdCQvS8?5w3-@;=+Ev%Ll7Ej!x$LO$sz?n@I4~$|0`L`SQ_;kZ5CSY<Kxa0^i9u|s|~Nw'
    '1~5HbpuddQ^Ls>0M2!hDjcBkR`HCnm|M4_Zd35d!3Jl}iy}c@|KWWRIr=Ay^i6q}#uB|s`G+6{D7!;GO>PnRIcm8C2<lYzvT>lJ%'
    'g-Qxx`=^<B{^573Eqcl#pWtT(pe$O5MQlBxkJGtydEiQN5yXoyI~4#ukHZgC6_hqaouEeiEDV^SV}&gd_|Kg2iBR}rqVapm%xvks'
    '+_d?6R;8{Ne?lt&9&8h|bep_%wskas-S03-<Dd#?cRAcX=fQi)-~%&vdi_wzuc=b0-Cn15PCxDt`9i|kR}P(Ix=cz`W-phCNH*|C'
    '$~;?wMTXi1Wr%iOGm&&`tjV30f-9zi!?Rg$!A5>w8HU%ynm-43nYiihePYn9HOx^R;5HPrpPdt^;t*iC0Of7gK}Chl1FPoEOA`_^'
    'm17c>k;23<nRV#)K<e9zZ=+#20%d|kP6k?-Sme<)C;_s546EzYujIh88D_MVwUz6H?>UIcHHbN9-H*(*c5_<;4{9T#v6(WzF3$t;'
    'EYj9-3GTeJBGZiFNKfZ5l*&M>sm0<WfGpwL!Q2|l$&f=h<<)TL9cRRh%(r#<`*CAPYAhKG_Du3T9W0QY!RxRsj@S+GJ=_sC>VdpN'
    'ME!|1EI0i7DC!}j!F=O0{r#|e;TmN9x9#V+$?D?@8kBrC7+}JyX^5r$l(6F_olq+fQsDS`-zif_4dt3f)<beuhGeLPfZo&KLAPMw'
    'M=(g;79BJhMQwx#5*JRT^S8QQv+p)GzL&Q~$>C5IDd)a9lO|(VGa#SQD6ufB>rh;QXVk#)HCD>Bs=K#9oL`T(odYss>huj7K4c1I'
    'y*S~@u!&`zXR-(oQ+u7y{IB+?57IlVH^Qpk*l7x1?*jwq2@A{)T~eLshb|zTAx>`{)%2h~vcMAj&+PCLt~!4zq7UDMO3ZwxhfGB@'
    'uWYsiL7L8yuzEOYXQt?ICri|!tliMAM+#h@$cAQ#foiQnkY?e-cVsf$aJ>5{r4R(9-Fko?JK&q6ghJ{5f+M(2<vkq0iL(e8$KZw('
    '+d%060x0%>f<piGCLK^r?LNFFyU{k&0k7}RgHx^U4*(d^kWnD*SbySY0(izxtv95wcJ)ipKUj<$3$nTvw%y7=hV%U*$>QefYLGM^'
    'T~Umh53Lk870J46*~Ox!KPnxp`iD#S33?+Kd|fdDS8d4&TD4gepnv>~(u@UL>;eZG!iMVaUqBy@YFr+BNO<I7ZmokXvvew4`hH5G'
    '`oZzpURSOpTv_ICs1AbgE`Wf1DO@q?h+k-gy5v-O_BP%pQCb^qb^$_b+afLiAy%tz@i9@W&!~hx(-SSF%@*d|Gvgc~y>a3HhMq)E'
    '-18&ss>uppRbGFzP^<W{&wIK_2*T;BI?3o7odv~EUP_#eg{Kc>Mpiu=4+^?@;m+KYjDRFo{za}^k{a<U9fkam3lZo%1v(+(w_NXp'
    '?{(sHuPZH_hRsv+fNFL*FW9~I9}$tucVNTGvgamlc2R7|Y{ol52_NKx2%v*FVMH;5OYhA?6*bUhj~*-gkG^4-A@b~K8aja1j&rg`'
    'm#+0wCifK|as_}Wj@L>Q>YyGPAK9M43FD((nusW0IT*+ly}1$@8pI+c%49aac^b+PHy0vf4s;zYuri`)+HO7=O($SHgGK3dRS!R_'
    '%tVlLnUq<~?=(hz;QUB1uYz-PLxKWg2M7b(%hVJ7$NV8KhCqc;KFuEdcZcHS^%5v6TF~?Mu6IMhHgd9(KjXk=NecW=DOiM3<tQ5o'
    'w@B<(`RDmcQ(~Lc&twS%Wznhn@XT#+xB|?X{cSx0QGj>LX6^#%xSC?oJM;`w-lm-8DNY)2jd*QOv;_C3oxj2VQYx$4u9HyCMt*02'
    '>TbVw^KT>+txMSW?gE38;peu{7aJ_#Q%Yp$rngee1j#KQm|po#ODOzV7`HwTx>NJ;z5hg_zSvdevUyE20npPlTB&@&hk^WNw;Qe5'
    '9?rlvL%>R=UeauPL_M2r!3r`F6|@5&=Gu>tPE$PPeJ=-ClQm6vYTe<!0exa-Ou%Xn?eCH==^DbO!7Cy!Ph0f^iQF&cYdj8!hEPe;'
    'lY*1z!QTsLiCu4Z@GGL+`=d>RpRm)aX`JLg+H#}d@`Dq(U|J-fo5Lme&^`s)t=@V`o_maG&Zq|AJW@T;h~R>*pEQJ&!{#3HRzo#v'
    'Q85b|&tv;Rj`J#XLXktDIwu`Fvu(>LYz|eSD(*r9X>q{0Qmny<`$-B&K!owrcmk&`P`DTd()hw;9KPkXSn}lU@+72T*+c9X!p!D='
    '$K*OP!Tq}sEX&>);@WJW3uLVyn^jj0GUq(q>++wMq7wGo1gSc5Nk6TpVG<9)^HcKJ@j)q`BCx3XqFFHGj>TThkZd0*!EYiPI?K+n'
    '^rE;EHs}@#vcp7^SOvg(YD93MwOC3jSB;(x*NRlv{hZ{5&_bsiBgNkFK8i=E-gf+Z(K$POGN<eHgH=$yFkJ|zaN5k_MRt%46gO4S'
    '<F<N#^;cT~IKdf@zcFK;G~a~25u#lX81ig1ux>5XS;%%&fAZA4J}r6bGEb6JF8OBL<11D=ql-*c0LTwkH(ZLaU%+KkthH!!Lp`96'
    '#in#0g;9i?%;TtAR9#r0I{8rj)(5EMizbJN)7~u~uMZ^-L2i?IVB3E|jp1F;)aS#nvGCry<vf3Rch`0)faSg+lp^$s4mD!59s<0#'
    '@|e)#yWSAG#hJm;EX4u*aP>svlwdad9&#wZoPW;99cjSie{SuwaOJ_XgZw`6ze^wDH(y^9itJ)CtrOIjX9L{yN2H2kV%ip^uyh22'
    'vu;BwHd$IZ-rBx^yj=t{?jXCwe-??jLwBgB*b%db9Y@}*SBj7EkRQDLR@!#mD-6sY@7^iVIW;@dl8?vS3FM@%O??6{27M%m@@L{q'
    'bJ|-yyxxY5>y{ETUoKIG34YGX_w7}E=tAk&XI<`T(DJ=vEX8SbX@r<6q4+Dw+%H)v9w+lj-{MzzKZ4fu|J%>^wo;3@KKBlmYN=!n'
    'R^G$2EPlIA2wlQU!5)NYp&hm;-pM}VJ$pj^nzg5fYnWxSxD*%zgZ~iHfX*{}-7U&o46emBoDj$b@*7`qi9q%WV3*+6qalokfCVdX'
    '#+;==oWs6^e)Nv2atQuTi#@>N%pL%GJL<PtLx$5_vX+;X#+5Kz;dCVHX4=;*71k^mLXZ6@MuH~Axo2K@u+98{e@h}w6PA1Z{A>Qc'
    '`JevS0ax!p1P9{~B|h?cLL`=GZ@)OUaL<(V^|Xfnx_>uUv<%F0#rBCV`93{2r-o&h>3i8GUjqH;I+>(+U3_5R{^}+60Na*X`#OfQ'
    '?<l<FAZ0uS9XPEt>=|&|Q}~MxI3z@Y228_}eSbC>I{fnsfzaK@q<sk}EO%#7q)l&+O+_rG0cFqN*eroM4D?lU(e9jJc&T^a1OWyT'
    '$~vt^{@-J!e3g<f(3#ZRhO3yj%*>nZHBa|<G$-e*5AtIQ`#+#w$mxl96E<3p@{e<TmNb1sw_HZenAoH%T0{RtOM0t>xD-3Ms26qF'
    ')qD=~o2rYW7^%FwH(Aw`GMUFqMAIQ78>4ITjp=^q?Y7-DZ!vd<lHt1-7}S7yE3EnT(NlWg0;<Qw)r`|ejP{bFpL`+gl?;{`Q`<is'
    '73)<5iwYB806>2UHeW4twMP2!x7EP{`i*Gb=VtdncHYhU(S%x4vA)gWO9cJ>ev_@q^s$@HuelOqzx^%2oc|<7ftbi&#?l#L`H3*1'
    'AmSV3(ov@c+bG@TE8J$gKTUdKMIyL7A!Z{&w;xBRH9YsAdm7<{z_--GVD+Hh7+GvUj!U<KVqhhEImTMKX8F8DpwD<*-_>Y3A!<%b'
    'pW?3UV(64!EP%Yls1FjvudIFch8XVZgLtr0%q~rTvP4kPv)fdAz(dq3OHLuYPmip({U$-D4y|(d{UbKzbc(jT+2Q&jO%3(}l`u|f'
    'f_-c-`b&Fnnwxo~`jTetvI)s6Onu|bxIp?N>o~S^5`aL3%Mf`Y<r^RZ15xwuRk2j&FDkt+sU7YO`H99o6H7Exc-f}-)Y-aefpr|{'
    '8g22E+sOnDBx(vL^x6EqS0lnd@oFEU-*S6HvL1~yaRaL3_V?Mh8JYev0cy3j-6a2rRBBFLEA8jAzDwrYDz!x9gH@nx5aB9o@)D}s'
    'RX^!ov~^^bi)f?21<h4Dkwth)9OvVs=jH&UupwJ59L&VYjM<66)!!>Af%KTD9;V1{EO0)x!;D-Q1kT>!s1W)P=n@Nz?`iU@pYozO'
    'VpN_br9K_$!Pp?$9&_+l_B;n@rJ(S-%-obrSw{1Fwz_!ujwm(4Rpi9rDwUlz{~cy0-v`_X0il0rImnuoBj0lCNeTFXt%s^&#i|HB'
    '!@6v7N+G|~#1riQr0u<b28$fFD+Lv%dke<?R&I+eds`3<H>!@_W%#i7J1IjkRb03f5w%O*!G%0yD9lR$>Y+7;Y7Us~<NL@TZ9;Bd'
    'Y9*16x?#^=Lr@UAO3dE;{(pJK+AT<JbZe=QVio?1)uS6Y_v%FKD@lq0#lik1hBVrkjr#Vk|7%d@8m3yeY0~M6rj|{e<DPY!kVJ`E'
    'IycP3Etdxbm+u-?f2(yOF@->8p;i#>=rQMMb;z_+*MT8HU{V_A)Qi~18YC1+>}OW6c3x+>6+7_YpazZ-K$NxsJjxeLZ~`&$zxE{!'
    'A^Ie=5~$Rt<s7tV(J!Pjuh8K>O6G;P6l5Yc<n3HnCIZoeTT@TcfVV(iWi0OsTdMPZyk}BPR~DtEl&mL_Rg=9OiF*14c5+xZuv`n-'
    'cdwgFEYPX$xM?e`yJaEpflryM_&R38Imep~7lt9@_T0#Uue42e*QXAK@@GY#?(o{pED@(G&w<lXonJ?7xR;)=1d_catqe^_1V7u7'
    'ob8zzlT0#^@FlhDHC&du84=FEp9WOI+_)*S>3%Unf7~3%0%yU<fBj9PZm}O@%<e>xJ2xEL_^JX!pN|<0|C!gh{HMijCoCr-$W@kc'
    'B+Tt<XX^vmPCnK#A9B#!MOv!CBLh}u=1NM@;*wmTHfBjg&py@arKmVd-jKxI6)gk;n7b44qwwGwMB8ZkwaHlnQ>bV5PST0NmdLIS'
    '2JmUE?0V{l1k{**-iJG2gsj~g@+y2+0PvLpYAlHD);P94gSDuV(hIYC8IxhGI)%1Qe{mjP)4mHGC7U)F$nxy>)39taxgoD&DXz$q'
    'Pb;76%2-ufniA5KYZX2rR&U|X_aRC&SR#fF-+k}c(rH0e;5W0}cPIref*yb}$9yP81_jHWq4A7&tOg@A4}66o>2B?BcyD44JgQNY'
    '+#<@RF=sHtBm!&&8y0b}Qj4LNY?k*`-?Pp$8g39{S$-{i{mp~h6A0lRYq1HkvZ-gaDA;M^GVuHGuu<($c*&}I3hok&01*7;tq6mp'
    'EOVB<fC<(kNj-2i*QtnpJPy#dtSC2{a9TqTNk}L1Ijd0I!ys341)T<e;Cx(~XO9z#f+VbYL=5MNCmtHG=fgM8?pU{YfsBAc04QF1'
    'paQNJvA<12N*iknmAAVOrd7|isR@p`vv)c$Grq7%?BLkHPM@xq-I~zd4ZHjy0_dB$q_>#Crf*BK^DQj^AV7bQHHLYNN+vc_f)w!d'
    'CioL*WE~eU+5%7LAH0a2;*sz|Y1DshF{sqDneAZI9CX?=nEwXQe>yHBD2Qp0Ghb*<dHPXF+=8TQMXK*VMJM7N%}4jzGYF-y@~{WQ'
    'z|wEQgEZLr;g`Ta`)h;UG&9mIa`r*wI$-V4&zq5`TZpV5lnAoAMn(JMTiyO6${`%o3leyFVmpu1EAJd$4tG(a<OQ>@0?#B0%&tCE'
    'UErk2-Jt|*$f}k8l-W(kD4eyQnV|-0s(oDmBz2UIi?%V6Au)ROf!?F4Pu7?6qfyDvslVqiDUF}(Q>u|;Z6h6{7e<LIalS<H1xjH0'
    'l)<%Sx8C%<kOc1WJ&qMGty68S6O!>jTh#$-XLg}5!IIiDP>)6pD6fruQPWy?R2>lvnK<3!;d)o_z?;`A3defn5W0?QT!^Eg#3o*?'
    'h*7bB2!FXn#e^51^xzfCr}EbgIo*+qT`#AWEmm<h_d1idl0n>1VvQ(^8{?qyLaZL53e)-wl_#fGC0e=>L3aot4lP7u@C>Z<ZR^p{'
    'F-!YS9+LWQIvt=K3EZiLn5F^0XWpLf54M0rP^dU;#DnwZaaM7v+z_M_sf8#y10Q9Kze!|yoNv*NNVWti-^eOml#L|=r1n=WFlPN}'
    'c;rwi^RSpkx+_!Ohd;<*Yhu_-P#bVU77h+<jeWUF4n;`LI3&YlSut?>Q2dPT#Bb=B*!*{29i!*_hm=(i>UILY)3m(Y=n*lw8-LJW'
    '@EP8kQKnNMBXo`OJkan>WAzT?kQf}r2N6H%CxiwA5khi$S)r(Uq7m@#WtEYf9^dFj78!-=nw6uw!Yl619#A@CPUb#q00d(*FkhXb'
    'N3dAvhvhl6%^QdFe>M*cpi_h9Jr>BGI&R&06Py?HUbm@X4(SHRN6At!XK@m0+k_8;(Uifw$uZ|Ew%k_i`_Q~07o3D+C4v={T)W(I'
    '-TFS++nEkJ!dzrI%_<ynq1Q!^nOdJuVb~6Nm5u2xE)gLHdtm||EaGfJbkPm*t@*lG4`a%rN+RPyk4oe9<5Kky2}ka~E;!KxC>$K='
    'j!48gUC6<5#6NCF4gM`3;Zl#(BuL)dUb6{@SnpXEqYXwJI0qs_lcP$2=%hfln%P4SU=no%QTpM`EivFGgHiYAD?70xS#(q%Jv%!0'
    'xVg;%7Ot_bq5P4IDq-12K@rql$TJ7Y{jctn5+N$^<@%vs^!rn9U<fmh+=8BhXI?`YmalNkId&f<Yy`=dPBUW|asE*Bz5LH`sN3kJ'
    'cX7E5?x$NfHxufSw>kb$^v}I8w>n<(Y+X#khf$dx<`D+(=yeAg|Jg_EOkf4nXuC{#3{+aVY4m#UY0rH*aXkE)Bxpo?jPCni=p@3?'
    'Y=Z1g%Gh5#FLMe`f9a*b`9dG&2MTf6lwdXS(P4`1sT+Gf^v2k4tGFL2Fwsu;+N<fAR=ku05>wy~Z~ugtt^Q<Bz9I)MLGl!buRJqh'
    ';Fg#9d4$4gKv<8Bw#!H;S-q`JqTV}>8Hv)4^nSpLa02aqKmx7FQh`Ilkl2aQ9QD~t`!oQGL7B4RCM)7)FCwiu-F(~3Wk5>K?v#?i'
    'PhG3`5Pq>9lz-Q!R$|2UA-8Osr@y(^0gld*bGa1e)-#GTO=sC_FxYWrb!CrdgTxAfId36?$wkqB*nNChJRIc_$P8*!edLw?NB#m_'
    'IOj9vccR(-q4#lD@gFhW*N_e44jL1z>4U>}#_0epu=tbIme!p><0%H{W3zh=3_JO-NYLtM|Kg^hL+kZ5A(O!9!&3)s{z}mWCj0w*'
    'X*6EJB1##K_3BZ(qJMV*t_?ies?qcaVQCN4grm!KxpP0Mz~9Ja=RnHwWp83l%^&>epGNRVKl&EGhQ5T%;W9#h@Td@Irmx4xYg4cb'
    'o3<)AgQVV-NerpM1ITi4BkcP13}xrm)vHFXmfh!!0*qto`#oH7kmrjI(48{SeW9@&9NUYf+rRf{@8+BvKvjXYl)7m9E}1qz^DB`%'
    '<$awn^^-bvNx$kieD3hj1b$FJUnhUK0iLk}I0?T2FMhFDB5nsH3g98?Q{`u|Rw=1Hlgqz`f6<|Hg<Caj=VkI|ccbunAPjQzj4s~J'
    'TK_Ff$BsiUD>o@#8KUw>+cJv_YsM;tz1nPIZ)`M}`F=)G+i*p7#5L&0Mne$APjX9$2!dTdJMCxN7c?@^Ry;3Pv9r~Ag1*gV8*Y4j'
    'x!(qmMI-N`y%WS)G8G@xGpy-Z;7{r{iQ`fqy}sm1z2gMy^4j+GI>IN}clTxp?BNc)N77w#@z2lK+U(O}_A*75Zpq80tV`id2wW{}'
    ';nT{5_HMwb=|3sNQ_-ZvW0^kh`lM6Mv%I8zm=M3oJ)(*NxN+9tSb9xnGh!kbSf5TybGnlsQ$VCrm+$KjSE{+OBM9@EmjqrMUx}>+'
    '-8c=@sZ{F%0eSJHn_lX-0w)wWnIOkYYo5(~+?dWQ$Xa<XC*s?WtS;g%9<&z!c2y&Li&dV9T=FnuM#6u*&;7Z~pHT_YRe#G=l3BWJ'
    'QZYFAHODnG1cud&BE}tij6O|dB?HGUYs}>MFe15G4CSPj4}nDKlN1^672=LN@o@;5HM?gD05x|XM*f7`CzG)-E>Ap|&MzLZ8-fli'
    'K`y-TgLip(HQlv7meBuimanXZlcp{K+hUsTOqJA_w;<;SRGZ}*TTR3N=rGV9TR2^ds<+61jUk#A%GJ8dg5KVR3J><2f1x2>%hM8J'
    'K2z$a^u8<D5CVCAlCfq-kIergmml>I0M(nQU-$MzFzMymW=c8pPB|2EaDbE87Xh>R5Ry@toauWkT9d`49kxd-mR<&gkO^Gtj}R!Q'
    'FEK|U3xFlqoSEjcGO8>^;;YqZqr-#PVo9*%gC3a?C51Rm-aCVe;shaTv8`=%RHysx2B%2>c_}FubRjAA+4HuNIzw<N<#n~=rD|Tt'
    '&p1X;iUji#jBUr%Dmq`J<X%~VwDYxhV_m3PX75=nl8NuYjWX5QH>N;+36@+DxQ&7y^ID|tP|ECKnIb)(**9cac`EpQvpm}wvg5?~'
    'G^O_Da@}gO8Iz2C?{Q}02C3COVAmlm+6cdN8I2sw_*xc}K{ZBc)DYlCi6Bm??QPvsOT(=@VX0|r1cF}>Up-eboNAe#G0%%<tWzwW'
    'W6dU-2(`PO)1rC;0~N~j?N&HG{Wmx1qZ_)-?iuD7ST!Lm!X0#GVw-eK{GA0%8x(K|adzWMWhLlWKq&oWQw|<?hgAa(flcdKT>UNN'
    '{j=FI9~I+j7;EBBXCN}KKOSqH(V$ZjG-c=n4g&5I9GS3~?!3d_$qd<`<?_Nw#OOgE6UXHx?7j|Rt-l;Czd|DAP+pu<0kPvfKltQ?'
    'YwK-Z$iA4a86@P5{h~4X@#G)l=cf#8`_oo<S=C|kg$*Eu^>W`T>RpC>0M$zsDDo$ajL9KV;$e)%>1Fqn1LCRKqPtS>`n{sn`3PhX'
    'mQCme6?r{%<}O?y%+v?Fmg$=aQr&iNZQ^IV^rdr{nYEAxJBJlh&=syagaFqR$ws<6<f<I(9JVFA2v+e=x$(LXCyqPMZY^S0SDMlN'
    ')xf6n$=yYpus=i)X~h~<{1C5%wp{}2?|SO51~=nD-K^Njlakp#bJrirmz2#Idb-9gNq&`Xx}jd(z5?6LrG(6*>!@D$bD@-0F?f%<'
    '!+~4!ZvIeAH%!b{@;~>!%KOF=z2~T4{AL)iQ|@z%;G+buZ=+Va^kZ?-s?~8PxxaS!?Rah{dvpI<gvNjif%;;&4j`QlTvgK>2T8UM'
    'Mxnlxx(xdoo{+kF{MiSl9ltA|JOJ_N-ocb?lsI-MuM$@+vGN-jP01CY?!dUaTL8B007-GbYvbG@v8?w7e1YSlD5DUw#V+g_Yt|5{'
    '(hTyL)S$|)N^W{=pu*lVI=$OgQFs0|EGWqpaHP&LhdgM#1n$Q_vR)4GPog05BIh?^Cl9HcQu6PyX^EGvd0|USKQGugpaW7f@r3Uc'
    '?$%(6x9G+8F*8$8E5vaR1<>#f3G^n|0W?nfq<ea1X|9(vSl_wsSFBfQe_)cV5pJG_(V;7RUS?Eqc2L#9Faa!blrV7(Q_}}QE3cN+'
    'gdHw|2)RB>UxK9sq%z~0bG>*EJ5jNB!yz}_c3_&6a6FD{D4P(c;50agU;tT7S`z9^oM)Fps(3-oL;6mu8?kTkyQH!;8|ZG?d}1Cy'
    '*&_rjdHQ6&aF2v=S<6@SZ8+;MJq~C>AHD1n)opmIyR`040!+!g^HVx;s&GV(O86#EI^u&5=j7dZ>+2aET@E!vDiCv;LXM)EuKq2#'
    'Ilf`1!FD{%uYv$QRE)Z&M`?K8_4vCeL2$8~DEgm8!Gkl~-d@BXn<0cg`Y*Jw!E&+Mg^1Q3fTUNV;43~s_|2d*y{9B!{sK$Ic7t8b'
    'ErEKcWG{%fFmmH;6OJlxe8^VhMwt|kwD3)H)O-G`PLI=b4firw*@|fy2@x8;1A&Bdx9aa8C|~FS-s)IGou*x+izxC>LRZwsR6M1='
    '^RqN5+j}|T6Any!0P{>~lTFiH(r1Y9AM<C(*(D2PXP~(usR*=^+qM*}*H%qu48FZN1Seri(nVDC8ZIwHf$uYmT*KP%WZFN(2SoDP'
    ';;``l0bA2-EY^kzd7kR<^4yt~&x)-y9(&Zr3-vEW+}h%c5ZYgJ<Es*eR_<n7WQi-9TL((jlOx!6NtBVQ#k_F6ZZ;1f>AaJaIEoMo'
    'Br{?Ht&8m3DxEwk_t2Kq;ADR;tvqEn8{*aG`qm#wwp{&=$|o%e?PSlP8>yz~J2GoU>-uUAfJbUKk%zIfgHFR^J9ld*aER6poV<j!'
    '81gH=<cdVRz_@n#<F5uEssnNV@z5@85N@r?AX64JouwW}pvs|4%*ppou?*k{OW9dAo}M%c(r|q9e4XEt<d8@6=?EnV+)?%AP|Z7u'
    '0l>O9XSjmJc3Hk2ZZUH$)ujeo@O~L5KA+|lv>7Ioa`EHzWEQd}?PkBpcqJ;}2ikhvxDfHzS>uT^6UFxuPaEFh)vMGhl_C&LngPoy'
    'S&J~2e<HmHpa)jdpBaO#efxfj7$8O&5a;EQH1UHRguZ2o{AH#N1IhBaEf&^g7N;EFth(g~NE%y};D5XnX)-IF;F`tw6n*tN_&&?L'
    'SOFsSVi{>FT$>j}A-g5g#z|mJ?sv(z_(KXMH>9SX?|YQMNjAGa3?7s<cX1XD%!m<0B)nRmcX7&F;sZa-_YaSTFhMMt*i%v#M|_Ae'
    'Av@+CWxTA8h{U-+a@YfPo1hO+`SS`MMlAxLPC3>tnPIj1+GoAf^H<VsWb*56slz53VVmp`&Wg?Fg{>5$h|3R2ZJ4v`mcy0~<IY(&'
    '?U>mzC|3$*z9OLqU@${V@*_c0o(j8Qb#AV`fShD^rc1CjyBTiKM#nIlS2ERo1~Xv7HJ6%+=B#<&Md{X&sjJ=5lAXUd@_juCQW_OB'
    'a4nZNS<vtPqQVbzf2|!DON<IQ7F+>bO*AL?R8YCVUI<%ZNQ*g)Lt6vH?DM_+M+u;qN3<K<gkEq>$Og*ftsicv4Z_AI#qI?!Mc=gd'
    '_=s8)7`jE)&`(9yeN6dOuw~nmD1Z2NcrXlFAn6nFT(5ED)Ym!)1}yg5kR;~ZOC8k4feN1CxbkK$2ROd}=_ag`O0Q4--c37|3g8VX'
    'n32v$?z9RxYtz`pqa@ar4GdFz!HUnD>vw+Fwi)&+a;C?2R#Ox}ozdO@GQ+G^L|r>MsAjNozsGbAu0w)#nUa;i%&1q7WV5sihap58'
    '=lHwZt2p^gVacaFos1w?7O<@HP_-F?6B*@eOz2~{q*X&vRUn;-ss?4w1%lMQ?!bqRin7^U6v=Mpv`fFYm1;68a*Q4G6oqn+`LC~C'
    'ETaJazDD1OwjNE0NfM&Qf2c;Q(^<nL=^!0p$HNiUgn~lucf9rsif?<DS;kc<B9Iq>1}wBwx()L&4lS?YvZav5cQ&?GyRZh7N+lEL'
    '`;-qr-m3Na=AbpNRwBKE_y_E(UhnqP-t>H!ql6cz?kGpXo^f_1l*@rG7wK>l-N6FfY1v237Qv5-Iu{#|Ew1VaGi+YIn&N+yqPb=3'
    '86}=3#P2lxdJ9lJ3HPNDm!AVwOB-gzjPT{mA)82d--w*9m^wxyVGxq70tF8cX2bhe9`_Qzh9g~pOcgUh>4|8TdpAg=Tr7x8PbD0F'
    'hF61<WId4oi7Ii2NFbq#LIlifO9<)*TN<8pRg{j2*=S!i=jET%RrhTqFx8sXp;TGee~CZy&#-NB9ptoIIkY_f`ciXBob{fu-2fas'
    'o`a)#48&}l0!z9vIe(*O#RDT68(@iTWD6%EzAQR8t^`5otmt*-V<~$%3r2kD+h@u+t(C<1+1Bqo)!kh~rRQP8R<1>ZdYK@F>5(R1'
    'QB1Q0ssk-ZMh%bK*GJ}QhFTY3C;!JEMR6*P-W0=D!5?XGROPSWk*DZGti*dfFCj%%MVVBTD}E^$1Z9s@q&FUJJ(|75?P@t6-5hda'
    '2a4Vbbj4o+WCHbnaiD)D^fj%UHjh9YwEZPrp|W$?4$X|w(ew)iD~HwhNFqSv$L6W^nM`KUL>YRvIJVpHPfoSey$a5uh0RNqktmkQ'
    'QvTV+?fGU?dG0Z}S>$bH@VIpanZ?@ojRc~-7f~*5g3!#P*G`I$yu8-Rdh=E8TZ+4`IpNrJ@1xc1ktX8_t7bj5e4U=SjL@{&Zm^_W'
    '#6-R#=#eWqAPuDMS;1u>Ed{nI+66w|R3dh()~Pbv$Ux;Z)GRIN=_>kaRf5c;(m-z-V;5F{l1Jdio>qsLC#;B}t~guxIW3DbtuhU?'
    'T+jR3S(UdT!rM!VLgBH~9$vKdX^3lz@&OC>m<wQniQ9fG{LJnM;m7{~vTfcpdu`F*k?HmKIS8^U|4Xv?5D(ft^}nOd7^P0~xQ0SW'
    '>uxa`KS`heFrEBe+&Cch!B(wSi`bcA08q0-RjC6p`TuM)eiU=2%dTDo{s?lXFK?hjl1sF|sp}hiK`A)f^aBl+?il>sJ8`KwyxHJE'
    'Vx!T>V)Y!em{NWlB)nfQ4C^&dbjGD&FEBJa*XYH$WQXH(1u<%*vDO&Wr{6{Pv0wbk8Bwzbn)JP~nk7Nyir@z~lMX%cX<(Wc*v9i('
    'k(=K>SZZ>QbEK7Oj^;}vD3RG$MKiQ8qV2^=3o?RBvGVw^g+^6P1^HZtWGVR)=LTGbu?UU#v;3y_hV|M6pH?%ZUn5tXpb^UXxz4Fs'
    '5vE`_?xX#ln^B5l;)KS>Q%Z{Sh-VzRBPLyj%rtCbu<;F=->IzMwx)!DW5eG4$+ckhNsTD&0|e1*1-*awdyMwIt1J32j<@Xq@h~)P'
    ';P2MqabP3pw^R(hOL3@-*EI=3*VUo}w((}b3a*=g@u!P*i<F}knzWIaKqBue9!6)yy(;%-*g@yfmxCW22Mtq22on2_)_)q|7}s^m'
    '1L;h9mpJ&LXGdL@%!6p#3{3nC$cx)Ffk34o5IhO*3_$^3*Ku4dB5v0@SzQO~ArvFYU1V@Wm#?(_Lk5t5()?>WI_P!6hc5=x2O@VQ'
    'zG}m^S})!w*|%O7Bd;KNYyTow9US?L!M>7rq3O{D&uE|PD01XtQ{r}0yYc>7P;{UC4_ychk$Y_OD>=Xr)iuZ#AyBqH`}Yu|3|Z3r'
    'j$xJiR-RNV^xXKXHz&X5ED1k|K>aZEqPrl<070gqyr@6V(ll9cIfsSI-|uRqeNAL;dPc{fg&1lT=B>|FJvW=|`bJfitY)_80D`BH'
    '3ghX@fAXXtV{x<QZshq&NYDNTKB5PVD9wQK-Km~IVzH@RF9%h7E~m+JrPyJw9fLlOMB?7oCnIkq94?IA=I63<yFIM#glui*`Gvx2'
    'Hy^#vFAkYM)Y3_A3={JgI&CCWE?J&X_{lu?B20eXm*lkbHjV5jRf|O(;iJF>4hUW&N(uPq%oazy=7Ays{f#&@zq5%=f>K5Jhj_|!'
    ';+&ay!%z}d*A~u`JnMi8&&}$bf`BG)5r(<7#d}j|uF8pFqgA$p%1m@uVG|y#^I2k`${3{(Wj%;Ou<rpOcvxn6Bm18JEa60_w7Z?6'
    '7U`a3zv9eg;$WAbT_r&&n&6}+?R;x)nb6G>3WCO;Vo-435GXi;J}O?;7BMNI>XdSoLCp=5_`;iayadJ@<4EE8HDGq0j4&cbe1UXo'
    'ft&a^1iuClwDeg_n;3`W`Q@BWWS)y@%O`Bixdb6{IUo&UK)hv41-M>sqv7k5=x@4BJc^)KHTDXj0BX8ok2W`mh8ut4`Jc7)H%QjV'
    'pF?1qBW3tP#bYI=J^vzqB@)Svf#-clnw#K_2TQ>(C1uXBYZ#T3BXUy-lDL~^&-n_WaKY+QghVsS$Wg+GlfS(h236bpZR{CtwPijw'
    'abx?UN?T%Ysnj{*bUsdri;q?{jX*Dgx5QPOA$4ow|Dt}7ig;bqjIGSvJL1Sje7BLK$$4n`(~H+UL*-ih#3um+uWem21|I#a3XdJ2'
    '8CM;SD>YRn2RZYtzDW<WdYwZ($U-l;zC_9V({DHcn`r2|s1CR0k@&m<D1NO)GHX0b_yP_7KGoB>+`yP;{i;(64xQ2{3K32DB}l=A'
    'm6>iRj;)rAt~ptjtB;K0%w!Ynq%MFP6YJVPeL|z#1e8ayRhVs$ACE)I)@6qa*?u?B=KD+j7wl!v`Ww-r9Eq%4@4d=Jf5y!*-jYWS'
    '(;rH7>DZXoQf6EH7=8j<9Tb=1JpxKrI7nqPlpN2lDnvasHZ@YIYVn!`<H+H-32qdrYq83USbY6NQP&OD<O$2aW-xLU^r?A~&Sssh'
    'hkYbDZ;np15nRg2R_At?3DS%m)b6H=wt|;|C8zsy^ZuhBP9o{IcmsM<NCD=;yXphr;M9*nMR`X~l2-DwSOT_{wutnurbEve(m;8_'
    '=H9%SbH2#nwLhq;N5zrc(gMeJn&`P@ZD8>YCW{A2HC!Sci01+kJ$M$6=XAPW+nZqaha<3>^%>lT$kekUHrmrxd#O`cD?JgNBKtrl'
    'of!0SvlPOAfMUEsCEx5d4sMx-oQDOfKIP2!A#sL?C?11iB)3R^9d47M`_P*p5<2tw)qB%0co(Ny_ZwatA!9W~23uVsM~qIIY&6~A'
    'QtMR1-GYs)&hmb=@_#~YY}~Lk$%MHLU3b_MLoIpAEI$*WEh4TIacq;e=6J>Cm`HiEd;fz~&-{>O?lg!)u#SuTobm{7U_Lu86Hcc1'
    'Nfs17ZJPeWzSp4h5R$z*<%3p%IaYpV5$=lL0FX_fXdm6lUzPl`8f}9dz`JaCEC~*Q%wF_0U8=u|8R6)F!vk|YRE3buzXxXqI{5YF'
    'h)K@gSWL=bR=-{p3*Q1o=*wv@FggYo1_}B-e(yB;GfnpwWKFEN5H65t2CiKyrL5ViNd((~rn0Be+9*LtYhq5eyEADG3mItMPVN;^'
    'kCfja9ub6};jVo_2DRw@06jd|2jT73m(OU^R%Xut+FYObec`vUZaxP8{nv>&l#o^vI@)Wog&P*xPo_D#cD{hU|5kLbnbCH}O-<Wu'
    'Xi^M*I<@`o+l-N5INbbjfYIN>=NdEKQMBcX%ULmyL~gTgPP3`D9FbA_;>8&xhYj-XFcQ8iZ6%OP>!vHMa0z-$`70cmU<^6o92+M9'
    '+!HzUZ%`O^Pp&nG>qn0pKL1eW>XdN#4vlktqSc|+a0VAn;FpJn?0kqt`<((4w4-|92ArB==_Mf_$`%ubD>o@|0<Rx|Fld@*tO&HJ'
    '3r5+NEL+7sjodcWL=ptlF8b#hVl_rcAAEb6k@JIaJL0z@HBAn2E;Ai{OvJ+@Dov_CrPr7{pg@xt-kP{62omewlCRao_?Eu5nGuuk'
    '3zd6K8tE%(>?~pesO50|Mk2s`h*<G5bf?l(=knk+Vmb|5EnwO<V47|A;4<sW6h-Pdh(NR0srFO4tSVM$=yOlXHaJoQe%8jNW#}iX'
    '^-opejxae<<ICh9q3Nhj){qiY=uXbg*KzM2A!#JC^s!-z5s6%(RuW;;?Erz@7SoKtZ`aQ$JG-Ca%mGsCxM;mlU;$RFjkBho$fP2C'
    '_N6T_z`kAesA2t@X+fxHw%_bW*d^vw;7TX-U;ao3C)Ie8#U_4mKrKMMAOAsz5(C&mfjn@U_(!~%-l&ZN{oa7J^0%Xjne2R7omLmf'
    'x^{=Yv1W0E7R0L&aS8U%XpLOn;c@DCqt1pdZlhQe`Vhl=x+dxqB{C<PU?43_gt%6{1{}BYc;jBTtg*j}c0yW8Dbo1jB#q%y&N(wU'
    'zklzIE72Q-&c@*OMTpD3_*H^eJu(#P4VvtR8sKe9<*p(8kA2%DuMF!g;^Qtr&oxN5TrVa5QV<0KBUGCu1@FcVrogFQiv3a~%Tj(Q'
    'S^XQbwp=Kgn0{b+VULnvt5DW0wvuHjhe!+SNqLF9YW3z)G{X|{oy(ANvP&ubNz7#CanDp@w4bzN7H)_SaHU83K@~gI1Y|bIiGzU{'
    '6(ZbHJe}SFU~WEN65YLiDpF3OqO@(XzE2TO1>ivWoxD^JE33&4^~YSuIF&(%HqeDC=(>Y^HhnI<?Oe*x!G1F5W&k<4<;Twt+gx`2'
    '0&A$r>w^Gh>D{r^6^mA|e(?)!30Gc<l?xT<%+_Oq>Il2Q|Dk^v2SGGr>GH<CKQX(IX>O!I!4Me)fa(@2*>+^zitS$ec6$?`>@`+B'
    's+q*v*h`(MblCnuHB9Eo6$r~WSs=0WWyEu4RJVu7U)s)-2b3cQ@v4;R9$=qIktvF59A~3Zt^cWtgPJJ?Eg(%>dlTfZLka(rhej$;'
    'i>fu&giuj^BbMVGBLJ!fHkmm{N9M>sM(JBw*!`F#Lv$K+A{Jam)9t1D5_E_d4B~1?ZwrE=e@}FtT7M<-vmRh4eyv5)ypXY!dyTSs'
    'HQ611@xcT9H5#bX6>vIep=BrEiSRcqVsrW86raE(bLPu?P{-xRl11U?XjmoKQJM|@aNs8G{5K`MhD6V(BeoHA)b`K78n@p9#xjR8'
    'LuEM`tnn>SEjCK^$xwG+-0Vx#8e)KZ@OHEZVe=m`4~Y4~m3t{~r@n)2%ofUi`dm5lF=w(Ws8MnmX-pDcmuUXl4l)8PX@AXb50QK>'
    '7h?8fEzEd{;cUMgjI9jA`H|i4j&#kk{9DRzf&iMAZvs(r5$}D!vN#$>XLIJw(y4t8{92bm28N6fa$R=u3xZq;P4pf;;Ibqgik%6e'
    'HC-QaLrCO@aL8XoUqMmGjQI#GUUwwe?;_!vh6N|05Oci8U9g(pp?<mZdo~dQtaUjzz{ylCp>IS#o_x{h^#ZdA%!aap&jTSbG`XkY'
    'vy+6i$;PgDl2kvSWBeyzsw6jBKME&A)oF@QoitSwHHeH+EJd$?JgxxNU~r}Fdcqe&uKAJhHdl2``;bz<vX@iMF5S`fkPk10XDj+l'
    'dM*PvN1xSVGyTp<-19JT%|2gq*>$;6HGMR$LyEvd+Vy#xU}7zD+te;Pe@ro-cWvoHER0Fl;njlH+bCWGs4g4Pe|omtz3CUhd^UzL'
    'K=HKrsf$`55nc-i%%Kf1w0ww{HhVPWi#<!2_X$1S48EJK7=N5Y4Jz*(A1&iA1~VXR(|-4sx;G4ZP;vb&=>CG*!0LSX(Dq$uB?D_~'
    'B#M4i0ftxcNJDv4ZWJVo@z^Q>T|Oof*ZT%6!Dm~#lDm^i8iU1tAhK0h^~A9u^DI+gXBv_-#Z;M0qMx0hO4=d{9c#rPJvO%#jM4gM'
    'mHsN*d8$bK`S6T%OqZT_!Rzu~{RTm_iNaSzZ*Vx3K@xk$X}o+4zZc_zR`b7A(`=$_EhVG5@;@)%aH@dGpzmM(5K+MMN>U{Hn^50a'
    '>Y_7?Za<HvMWPK_a(Qa%J?v%(o<~H@!+rnAIzj3QoLG4VhkJ13jxt>=s%N{n0|CuFEZz45#LK_>=dj%<S6J9V+Q<f`@Fe(cW0u>0'
    '#(8lEh?i+AVfPIVu20p;#>q)Gc(sj=$TwX5zUQIGl<BactZ@g5Br->Jci6~uewzgx3je0xXvSCw5~1#mctoUZ`3N>&m9?8Ty0&+$'
    'UL&ei4F>zI%ceT+7eO|wl|uqYaF6PCo1E*xswYpCsH(k2=CCMOGQ4~<4dFV6W!{XDirnh$n(M1P-X)p{@i^Rw;OFQ_yHJkUQkGH-'
    'yGjhD&HojK^ZW@WlnrfZt-pp;6<nzBZs(p;p!Lg7*y->w+JF)#R}rHu<TqpBP20lBe?b;;ylygGC~-ts*!r78Lg~htuP^8W?NuSu'
    'C=R;0i2sY^tO&NK#Y8=4em5)co2eWw*r9*p`H1eRR;mfG`n7cbuN(ey30DcN)?H>W^tZ@yZX@1`;C$JJyfkQ9T>2?>g_#aJzxj4T'
    'H8UhjK2`W~SIh=rrQJ#1iBmzB07@O)^H=hCx}<Z3;&_TT9nsJl!tt1<67O4UGxWu_r7g7iVVPj}e28<1-BAkA4n#^ddOcxe(G#+E'
    'L9+K4XXYb5H}}1j$O0HjiY6Za(ddE)s41r_?d|iPW>+O`yMvi0fEULpuxye?Yuf=ZM&9Sd0epP)qKQ(IF&oiq{RE0I;xaYprAuJa'
    'wp=a;zWE$I(CEjHmiyZcL&`K)CWeQfQ>%ZTsAR(cflBe$1qf=>Q^pVdBo@BOKRG-TlQznN9Jh8#yR|H%I`=mj{_{-gn9$os^bNwC'
    'Q->5_^XzwW8p>i|jbV)_352F6{S2ADY$MZ@myhs_*L@t6Y11@S;B2kAPs<W}7welq9~1)Ok8KeeL2~8;t0&y_JT?G?X$3C#w*qhs'
    'D48t|QM*-kte{^9la;23ED2uqT1z`kWMn)~hBHF)tFq!oSi%ZkgDw4Z^}EkXyIc)=wXUB_>0k`zy?PTqu|X2!61zc?z~%kd-yb;g'
    'e5~hUmB1VF&+wO4Zef?PMWSA5F#({`CSLY*?ZsoHDpf91-Y$~c4?wWemU*GLg$|qfrsw?U7sXU!3GZ2V8&BgH+OcR^F(ec-`#aD5'
    'p%&Uft4}I=_D3R)g<p@u{dtB|KDeRp44Dtei$>V<QSC%K9vt>Im?W!^{*FS_J{Xw~jF$c1&2B;v7PQ<#5JJ4hr(iJ})ww&tUI|P6'
    '7v)^v6^ipk53T_wcX6pdhyfpk?ROmxuX>$f<uA9b2enB9dG(TDU-H%zqV)Bfq4+b)b}wn#SV2qypgh#fNsoqXr?sQR`l|1<pB|mN'
    'kGwMLN;c9Jfy>ceX47E?Mff9D)5x^s&N7w-1UOOBDH}DiZ-^$+R;ra%FLa-n_x&Tl$Rne&aRge`L8t}l2f6XCy1{a!YYcS`ad-KQ'
    'ZL$$Yv32a&2^^lUufA3Jw02heA<iN*EVOMiI|L2y3?=31$YPME$&qzRi)JT?*s>i}U-9f8U{B+nb`Bx{{P@{$G6I-(P9I54njWf*'
    '5NCDW)B7AAu=W?_&UTW6Hq;LwSI;v))PYSqTD7$cC1q*vlse((i6j9S-DUJe(gD9PW&($0em*uj0;Y#l|D`gyoVlStFv*Bugw||C'
    '9K)6<zWt!NlcfcuqJdbXx5_{|@<fzwO@#MDC28=}c&E)>Y#sEPwy@;OOFz<FaVJl<Na^+$e$eW5CnEz_1wRZ$5O$}Fj{qFX{%nNz'
    'Jv}kIuo8QHm=%L-Bo7@BwH_|p_ddwbtTc?B)&8|j2l$f6!?Q^D&?dXO4%qsyes$TF%Cb?#<j0o}!0pdqZ_Wtj*W^PmOFt)&U#R%R'
    'X}A)`&xC3IneG6|dJX=Fg~e4R6E;T*V&(G4(gOl~DH5;K%($zr|5cQin4Ml(pGewSjcc4Pbfm#Ww&10~oxchlBkaGqP$if9JVBsb'
    't&1ZC5Y(LJzcnjn&LG{4I}`F%s|l-V5``WOy#-)%4(VM9Vyc>yUDTSzC8p9^9=f_o9ncgO$kV>?M`E&#rtA_tfMVO+HhW*&$Syig'
    'yn6GU-pQKFF0YH%l!m1*FAc6ypqu+`iGX$4a936uw6#GgHd);=-XkP`W`{$oFQ9>}2pYQWdH-I-N9i~W_WV{%4vEFl-UvdH94mBO'
    'KYGVk2}8pFxmWE6T7E+l04E?Bf2lsb<NCXdPZYuZ7@J$`hhQP=!g7zP<P}87EJ^Dq<Y9K{C;F`nS2$D`-P`r3&v*lWCg@rx?MMtc'
    '<Tq#))3T+63T=k{>lxCf$Z*-5(F9VnNh+T{b<+E<rt1v`weCuli@;H=7{5%alLGmE;>VnY)X8P+-6nkmT=^g-15?3k{2R;?q}yv3'
    'MwOr0G{vHV_dG6E{*NY@%_@oPB~s}0cYv#WZLWPGz#JT6*r;tWtv5kwh-*tWB;x6EA~uM{AOTbsZ2oCqm!N&}8(D@j?2w)nQQ)BP'
    'rX7$nEk}SL<b_&ioPqKUotKMhn8V4;_0V@pC9;!QRj@kGVFzLQpvCkH9H+wf3Wvkyw-nM1+kX<4f!>wWd;W4cok=DRb{BM@lqbr`'
    'EXq}%Cv#S$3b?p2H$u6<4D4wg5RWHNQ50?rl5e`y`91w=cZ7BU48+mZ;@M&K*A*{rZnb~`{N9sWs0D;|tf#6@`~|d7Y=?{I-d0ln'
    '0a&%o7j>MbNj)I4G8P$(i7F4mA95OS+T3<(!Dr5{yv8Y0=W(`$eo}J!RVHaAzpIBhzSpZ8zEcBJsZP(@_zX895S2(UH6AK)MtI7j'
    'uFLqthkTz|B&eA{txq@qP)~_tH6b(a$t2_y@WWn#MsCD$3iTBc>fVYQj<PeHNDlPc!pfq-x3st=8)-{3Z<rFsZ+o4Ew}yqb$6PTH'
    'D$#X$KLI|j)=b<(fIZank3q;YjWn_FyUtl5x*3oDjO+3B8UW*4x%Ce_8}_40OW8%Kx#pUtVofMPB>b=jwJ<-qR|woz9LUYjV<Q60'
    'BLb^b+z%E6g5ur~L=#Y$L|U&Cb!*fszvm8avUi5$wVZGW?yAELRS=k`N`tvxlZ@&r_tP>xfusP07rZPKXZdg2KWFzft)Dp#vZpW2'
    'j*3aM{Hyz3kN~uDO$MG+QJL*`COyRr7E(}`2!9-JOceu&tg-FrniY2{9C~{P|6Nn%Z}DW^ylBN#8zsGo-8x^-3aMTL5l)l)**HL('
    'FLS$Yll_eH(?I?w6y(h7sqo&@dRln2yz-Ci6D{7cFVNESd-<8^-PY=b;Ve@2P<Kyml7SKZ)JnWVuFCu|A@dWUc8&Wh0@@viEN%oI'
    '1nE1+?KSot0=;0?^vzp?`8HAFgf#F5l6ZGgzje@#UX{6wcI!t^z{o)`H|~&Z%3^frDJzp{QNVz&>j%DPn*(PjKx_IsD!x^9Yz*?J'
    'goAs;w?3petUc^yTb_!oO~{5)ND(1iIm#UJTOJwQZBJBy+aEZ(dwT?$PKZ-*0C8cT>W9F@M-V%j{|u}kU|%!-+IXkUI#xzJuElZ7'
    '`hEE@KQNU+yh|b61@k9my>4JgtG;Kv)CdKHcig{Co`j}wV&1>mt<MY;c#4PiboBOuFOF(_xxx!Rgsp6Pk`q+cRNq=@0?og|J)>3J'
    'M?}Ka2cruN8%@oJwKZocb{r)*JFO0i4+$_Fq-&)Ty#vfG36Yk#2bCg9n*y6CJbu_<)g3-0Ild11ZK^+1O*(uOKjTmDg=J_@l`Ah6'
    '9x@1>(`&D&@S100&f~zig01{miL}bfDCeu_!x5mQQHY7hhV<xH{ty#p6Z64CP1{XC`Z5r&RbgX!U+D*Xs8O*f+Jxaf@!?+RxmQ1i'
    'mc)EL2E{_{Poc~lh1>f(VhW?$Fus6>vtpX;cx1mKTx}H@hDP{RVar06SF-+;UC+@%Z-tafHU&o5=1=2*jB2{446UMqAQsr_^)-Qx'
    ')y|9mFu<7xiQgB(*Mm6B0*>yVFFAry7}Yy|LN4+)=qiiVSt;BVJ@Hm1g}7+a`d=h?<_@fQo~{dXfjGqy7~@#JYE?fWgmvs+1UAu6'
    'u=B($WsPctS2Spw<i>uc*S{LL#T7ZIMk)1KS}>^_%I?j4OpK!ihBmVxFOLGKi}j;|XkrHY$c!wO1$BpZMvRnj4+6C3^shUyk?N*8'
    '=z}ur!sKCQE22r@risB^?9h!c7duwKIpo$kmuc}NO)J8hne7aV3RGaqUAJJKjvMLJpaQm@rGsw@McI^7s@Pw+9gD`9C>N?e`_s+e'
    'kM4+dE)gDABx?vssHLSXj2O-5$iGG1NDmsVe-c6EA_POwm3!gKe<G?zENnn&z?&aEPmGYVJD5dymo)lp{Bs%6g^%?~`8+xbc&Px>'
    '+xa<{E8SlR-f299*8?(nMun2oIjzOC<rFE*Eaw6QSV+yYB}pI%uM3aOT_M6VH4Q)EwsTF4!&!LY9Z@St+1fwu$%b1e|Le}Fj%$U%'
    'tkOY-vTR*;h?b>F0d-#i2xo812Oy)5-`YZq>#QutTTbUF>jwEcw59Ab=rpm*-DL_H`Xrshi3ARY7r_>=X@tL3mJB{Mub`_6)Lw6l'
    'jp~gu2^9rlE!y=Z0aK3f3{Ha_`SmXT2|eEwd72Rz<`Hr9^fBd~_JJp}CobTZYxbajESga-#!E$J7#N5cNqgt~D#V~iR5VqR6Purx'
    'GKBrOO=%{$8$?LZ#1H7RMoU&Vq)_pv9M+0;V<<R@Sr&b+M_)xjLr7Zst{VT1lrB5uZLTwl%cg1-J-uOqnyjH`sVwT{;Dfv!%txj%'
    'ez%7QrK>elbC_}hrhxEzUO&ivz4Wr?f+5uVH;r<unC`ul`-Y2keF!|UIaOU}R63d;niCQx@wFq8#c>&DdePhp06i!qn1A6%R5KrI'
    'eJf{C6geGsY+kQPrVG;4?>o)fH!N${Pw|}v09KmATQO_wD;Vpv3WDSa#A1~p0}~!dU;*jBVg$feDv;;UH@42#7=7FTY$b!Exs!i+'
    'PdOt;k%EU|TrE_kizVj=fZ-G)KJ3BWg=T5$EtWkIY~QBJJ;0xDwDEx5I6>poyxVg@Hk6$Tx(5Rh%x+sTnyO`fFT?89+((M!9xjWm'
    '1o(MLAYm{d!W<wm%+@_PgQ_Z4CU(fpC&uW`5<!F5|3SW^pjYZZ%s$1KZ7#*4%)wg_f2bKd;opW<(<_XZIL_o)+@7QayTaH=z|X6b'
    '!1wx$XA-_R+(vi>%p{p+t3g?gFg;0o>+a(XjQ3;Dz}1edl!o9hu)2436tmPzzf2*%^3a7ujr8=bHBX_@-DcpZS_BYDaWG_YAGWXP'
    'HDTE{8FMCz1p}MHj$b+wkUvztnyM7Mwsx7(H9Cy5_vZ)}m|E?>S%#t(S*~ZW#nIV<TSZicn_el4ojso&{61h=C`*#f1!q9P)z~7?'
    'j^ybL+rO>C!F>ONMZHFw?)+C?h>_DMX`hPsOi2!{Qr0?Gl8d^_j$Xs(L9~&nN(zD>^NZz`>d0*ChU|l5JHHGxRtu=PNgt^pO>-%I'
    '^(+_0^LXaS!cnJ=(M3>~yiIFa=Y8Ci2x{dljWG|^sdNsn&qH*A?p}0CAFahmC2>nDj~$`cys~a8H0O0EIcqII@>QLjw40C4CU(6g'
    'ieILwM(9RyANj?&X8w!nW(FRNus89N_|r!@)W@D=6CW~K3usE8*+t^fVUHgId2{%UuEM_?1=-WS9!iEPXan)2Qp35{V(J;^#SfbK'
    '7iJFc&ponTpggf7fj!3Yj2OxCT=4rq5)<4rn1x+-1fZ^&gu4B1pzWjUvEF4+xH6MO_$o@EJ?DVlPJ-;uOw_Z=RQBjjwg`ey;%71u'
    'YX+hII(c7T?ADu(qz!T>5ED%HUu4GhJ_Wl>`C&3vg75^YEZaS}5rYu=MSAIFiw*9`lc_%&1~ut1El$P+gnprc0~llsmGbAF6rF^m'
    'e{H+Kp~R!XAxGwxc`BWFg+ew77SN&~U=!`im3Dv&M^371)GAv5v*r{IX=JezaS!*mEL&WL2u2LxYA?dG6*}z(qQh@XNaPnep0j%#'
    'ItF_{he{Qp1oED*zID}X&l&10X*;mLP%5H4J~P3ay484Q54!~z7V8sFy(m|f_p$%jO^!Hh32Wt2*~fNzKTyNw5yII^j7{O63w4nJ'
    'm$LT6kL5)VvjCaM<;e`x<OyK}Os7m(!GhZ4sIjHt;`vyR`fVwsF)%p@quUu{-v(xt0<xK(K{OoNfPa-!gAIdLfogOMn#|6!W410A'
    'Nn|t-hr<I(VS+OOUF|@Bouu2CSEDLK%K=`%s}4JL(Bi<c)KlfRWZJiX%?ZTsHpsyYaOtm2qdtm6V#b_~H)!9h3C#pam}gMFHaA2G'
    'TxF%b`#^<2dUd?O_o!DuB|hB*j$V8c0upBWmE`*f9gKGLe~y*@2=+tXJ-&|=U4jov>@7J3;*c5t1kIoYuB_dBBRg8%#pF}~&M<bZ'
    'j>6hxEHs?Bo4h~xs>pBnhYP)GZmrE~(CHdCAjx@YD2ZLYy3R?6V`nyrPGwxZ@S|$tOm-zuMFs55MJWYwFuENwV(%^v*){)3r$1TC'
    'w^w4q5VEp>OnaM}d{sw1>rer8EVGk@$Ke!@GgL{G-ao1yrKpu^Z<z#e1^0FZPGZ^l$Rr1U=IAeS5md{_B;DHScyJ!?frD;Bwlw@i'
    'wd;yfUQ{r(wnQwe0w3k<4mQs<z+Ia8irJSR&#fD!lGOQzV-~p7B6zRhR+#mvIcmYf^@}%Z&XU5txhuM@@FM^Z+s_r6==*KYq)1m2'
    'j&@&ObNeRW(teN&r^kAR)6mBWvqmOMIH!ePr(SBPU!yiPgYtyiy!7!Vr4E6_5ksbjB>@QL&n-!ae&??YQbk>5>W4Q|k{XDlDoU3u'
    'Y~VP~zoZv4>Km{@FPqr}AsqgL$cg}PtXe$oy8@K2S>{K}k^aTIW&<U15W=6_F?xsOSa@FYtQbJBBBfN(Sld6io0@^A2Z3rCkxk&e'
    'E_vxrd8#G(-{ZaNDyPY?Hvzb35B%EwwP_I8UGj_)ptS0knbY^#Hvgs=<GV7S1>Gyze@Jn=%3QQmpsp~CGKAf#;x4!`NT<~eRkpke'
    'c>;qOw5L{#qD{fOcj*x*&$KRSw;2dIjR?T(l2Pk^s2x&YR2QQ_LR#wMPai!kOio=aeY3I^Y$LB(NqHB`<NnjuZ!&EJj!Gl_m~V1<'
    '*qbu&*Zk{kyomXXNWWr!-}-zjIpjW_h8ewV4HVOn=Q{~+sZ(iewRpIYbnM0Z_IJKLSE}^ro{^MxmgK(r=t5$DgNeoanQ6aqXvn$@'
    'qmsuVGoLJZQ*1655P&hA7wjEsqQ-Xl72Wj)GnWH2!BnbI#3smYag0S6!PU<N1bi*sLA12&YrMt&2`z(BTt%UB=@!lUKk6mfJ-`Qo'
    '6wE(6JMZU;enUK^1_V308UIfoB|8&^CO&gpBJT4K2Cw+>BVvq?f04a^g->+e^1YOk2nm_II6JQ7Z9q@+<4+^w*ee_iuvC2iS2hQO'
    'ahAw_!RenH;#fRTI35Z({y7#ofa$j=J`Awnx&xD$+j3DXR^lja<9f<9zJ!TOyXim%2!ChiyhDp6ALzIrig8d%bXP6~@K+0n5*EpT'
    'mL*F?ZlM(O$}d#M#g$K|6Q`n+mUuPfPDg4*=`t#)tnuI+O(m3NB@SQjhWUl1af|y^Gsp+0q|Qt9dFtyb41T%(u?_%afWqD2vY%ea'
    't;IFlJ5in3C5$=*OFMMjz{9RZ4>lQ=<U|8I9Lu7+E};kNoEiv;J^xOsR?KxAZEHzfNV{P($!P+#TsmL}oT82Ehj(_*SjK)kp-ej?'
    'obZsa*GTG}Jm;ZOh&=}bItBM{GZ*fD?PCNjKnFIEJ~c7#BTN~Ms9Ds9pe@_W$X0=iPXp*C(fl5Pwl0Y&591darbgO#3`tVfGk-8d'
    '+ZPx0G7x)A7sZ>H1CgIX3DTC$c8gGRHqvy+dZnrqNfE#2;ut978$!}uatmU68YEG(+MdEN3-?LF2&=iV-!##jZITzt4GQ_MvLh~f'
    'h&`Vf_U=A|r{O%gA{^3SzP&DpA3y4URBq_9@c8|z004A?z_^snHnG1Yp@dHp#^gNiC-aKa)i*uGe#cML?D)p$<NSZr$?fj~zG<Qq'
    '=cvyqb31lGQi;>I;%O=UP!@P(uUvr@n#WMvZCJDbFw77bq_<&bU1+>sEpz!Jk?!Giq9;2Jsr1vi_pgDSbg%kKOOYy51OiJNpJ1&I'
    'qpO>8r}ZfWhnKZwEsXW@c`#={^du9eCh0stM~I?v0eOKtD@q7ITUE=SeRtM3yAK}}!p?Zb>Wdsl$Nht_8n9SqhGtn=B(ev=Jc$9W'
    'S-6&OgVGlEaSHuF?!Qv^deT&HlH-UScqFC;^1`V%424I_znjcT$nDijrCX2NoMNiN9!#nYzg%#aCl}43<+74-`ilow@au&JuWZGF'
    '0h<`=7>1QH({_@CbojC&=>rd1@NO4WKrEXO>zxCzj1J9I>Fxl?L-k(wE%rk*=PZY5oac%_OX}XWu9C!U>14wFHy}})ka0L8w?`>7'
    'Qn-({As;$yWK1hlgL9t&o3cr7s+EHA-C_Xi<Lp6*@rp02j)rPexYIQ@mrcw(BrkxMDcbPP3s0V3rVGK2GqbI_`mMyRqi1ZcKz_oY'
    '+zcH(^-)?XQOGz@`V>Z+={PO33xQ|Npw1g18aQNXlN43*9EI^Eq5Bx{&o%ebQ?t!8WndF~S3D@>en=5tp2C5ffB2VZcTuZc==4Ss'
    'dvLs!8W-)WJgZaG^YoI#aootxsHQb5lj4Q~gaVy#j2*E|IYz6Nee~kkt?I?Gk(7=3`QXz&QH^6KnAb6A7A<5HH17*p$lqM2jjrHP'
    '5)Af#<ExXbNH#zS=z}d>>`XpWfj4uY<;H-^b9h($#}Re3N@Xb6?}*P5&10V!inykP*`q=CW{GO@E>Bj@B)cn1`M@lPOb3Vu<Kqbn'
    'vmOepyEt=<r6hZ9S3>s*Xi9!1Th5eVj4b5ham7(rk|?cL4WB?49)s+6?}m2Sb?PIp3tNBc6W)t7xlAu2jO;a(BvFC(QB^jLgMB)s'
    '@1L3A(-6df34C9RiC5~%nDf&X{dVd{-ix#CPuED!u4CRX(P$~?DaY_H9sG{WMiBTwY2XrS*NO%$Y68EaEk}_?4=1GCS7pR%P(JZ~'
    '@^>KiZI$gOZovC}wjeNRB@)U_F(%C7&W7yxYH*br20aIwYe)K%KeidLCTXoW<+%9AX`lD|$kVItp~J*BMtrW#sBra*DKw9<=2!Jk'
    '?cN+D*v2p}+F;a-SmU&;DIBZ9`6A7WH9#wlH3%y8jG%I*CCw1U5c)(x(BrN?)*pjX*~h_Jgd>+1t%rI7aF5K$8Um`NeSw@X-<;D%'
    '6$18E0jPTK(kChh6lilRfb(v&2vkw(=+EY*BcC7rr(zIL=nQ0n*tw<217>ZohUu@i??a^sE$_*`!plg_<6_v$HwFxnxdK$DAz0{m'
    '6A&oKq0a_4{6HoUlG*F2?HR^U2M|<OMID%20WGWRr?%(_I<yLWpfLDm1t-rY&S_~GC-4S&xvqegWax~i9x5WzJs5s6%#K??9MH$C'
    'zIc9Y=dbBmksekqVfDRW#UP{#_~5CriY2Um{S@K2Z&fmOugN77j}y+EFqVH^cU;9UXs5#|RKp5N?`-C;^I^=XO#7<5f{(sdFQw6j'
    '*X6M^-sUYeK-?QT9*3U*Keribaf`dJFTq+YPp4nXLn(I)j;>V0ZIPElpxQj5Sa|7v4?)l_#k4srj^6u8_yS#~<`GWi!rPaB(dzYh'
    '9pVV4Ls7C46Ety6=b<)f%;20?pNwqX7Xee5#m^-W(RZW<uE_O2MevO?Pl1kE;Es%knV7&p_{%LTax_R|6~vjQ%d8uUk@)WRn%o_S'
    '(@Q4-rLAuso25RX+20Rj9$R5&{8mWx7KWnZuF;zwejdt<%dgo6_Xo#k4#54V{e+V~b%Wmhxw+|ElpSI5-8g-zv7`Gpf~ST@=0E(!'
    'Vt?HhNJ6`^z=U*qzQPvn(geFxe$Y*YRXLot0RU75lQQFbLp^=4U$~iT7$({VPGvOfQwH!&V#Je(Qeu>}$#WM+a8u&<!2J4+1zw#?'
    'KUZs?&Or33?8&Eu9>ZF>)aS#5SDlQ7dcs}<6hTlffv+6<HC2>Pd3VUAAsP!bsh9T@ka`Ti*P~vg4<u9SHsZ5YmYqSTkAJomRyaky'
    'dplYd1uw4@m#Ak4apIuBepa7-yqBwA8HB8Ib0@5Z<a-2VU1L`5@|N3c6eH#%^c7Ontt1dLeJVm@blH!sqx{f9rLVHxEi4NpIX`1B'
    'LN1GK6*Cco%K`hcfu=QT274`O(Kmk|Vnu{rGw=nEFH&`FD+1T7LX6r^dO_uA_O^qR6*&S)d@4zb24*r-Ad(|G1OzO?)?s+W+e&@e'
    '6xTFwTU`u7Kqp?S8DGKAm{1}W>j!*C+1?u1-OQany&?`|5{?g%R$fUJ(Cm#7aZ8j6hH2Ed@Eq%M^AwF5l0>y9W5&Z|@H_)3+#Mju'
    '@j<E{oZoc(ae4N9jq%yW40UIQX%ljeEdj^=wq>?!cMo)Bv|zD!3j&Ya_)5hl8c>kO+~?quFyq%2?wg3&AStiuR~&%<J`3DfFwW}?'
    '-zyUSeMi1w5m!AoI>^6<<IJoM@`wG#bbKpi+ngHqghEo#WW?wMsoJSqVn4NcdQfb0u>?ybM0iSp0wYWf;f8+cNy^oq+Byfj1!Wo6'
    '_;lpdruG#XD9}PICcTLtU=4^ZmmS|V<8i}Rki<yO65f%N<b}>di-BJmIfxqCl505D!`up6eRas1LQojgrb6^ZP6<&o(hq~O7q-}$'
    'VVp={Iyf)uAk?b&@Uz3_nxYV}maC_F8hwR`Pb?DH=0am^KBeH%R<AZj0GLU)`pkah`JRCx$v~RAz7NxKWkOTYFVmXYdB4o@K(p{='
    'L><?_sP#bje~=m54;BNz8V1QB*FLgjvq$Eb)p4J;*}4}z2LoIEGy(LW+FKSc^nToU`C(PmY#R&>6Rg=FNC|p$2hc$+&{`m&5U__s'
    'ioIovC5m!NBc0mTFH-zMc57`RJ?5wFwk=myhMi&jS*QP<;%~!_R{O?3`3DP1I9UO&pBlwdKBFv8x*-qncoz3?3g@tU;%MdyMZgO8'
    'q|loP>m(`)Vzj=FHuKA%c1s0w-;GcaR)E|p=C`Zu=+(v|VEbS$98~}2rrKOrub&+uHwF3-O1m6yDF@or5MO*xe(^pVI!rhHV=vN9'
    'C0HMM5hKNE4gS(G(+`GT8Rfg~v+)t|KM0)pYy-C>^@t_?POjHxf*Fw-=9{-OpsHm!rg#kat}8Om%Z{FAyJcV7{z|Ah_B#@!Vj7tF'
    'GiWq}e8r9K{sg-NZ;Rn`<-O3PcP4)_-$@R+$T!Sqge=4jypT(=O&yFTusgNij+w)3QrJZmVlbitH1;V_8p299e0w!4z~?6*i}IHU'
    'iS{s|uAJ0~Ek_6sJpqU=vZ@<r?}hwk)~VKj2Qgv}L{cNj5G7m}WAyt^-wYG<p@}5&F-S>vvL<+|g`PNaaPYFnv}B>Yj!5B>x{PJ~'
    'l{9w&*M9S1gVHxHuZu)Nej#STfCt1jUN>x0-_IY{fFR}RG}wPMz7%1(rJp6nD?#XIuN$fy@su`MW#2GsVE%Ju+Q_%(9mRDi?lpb}'
    '<#hD1o=x|r3lnnqIxiK*WDf>uZE+AkhphtHktKZq%jj)<u6gWqR`8Rzx2G*R!#f=5d$-xY1y6xU@BKd$b{YaIKRZFosudmsoczu('
    'VZSO&;z);l@9*jddhj!aysP&=&U@gi4UF3In&bLF^}R>DAzMp64=Lq^?UKU(<eL4e#NY#iB3}M2W&{M8>F}O=9C!|FPp1v3yUt98'
    '2J0hS)P1_vqAu=E9`pw;AG4J>1TI+&;f%sK9Ft_|Lx`<mqdR4WBn(wrM|`X#LfuWr>L!x7d7503GQYt-cWgan=)89tMRISnWQhJ7'
    'zQvhA?NMBib(+>1H>ZSWd_vLY?^NplJnefHxLfLd3J6}%E}%GhAR>D1FGujsEx`Zx6<BfP=1cE3pw5A<L&BV7kZx%AL0gtN3<WU5'
    'U{!E$15AOEtU{vW;;KRlySHil?=(fDNt=(%by#uEQ=r)IQSGB}?vv7=I1^}j+>bX9%Lq_>fxgF5Y}iErW<Vz@+`wmyVKFc7^oRZZ'
    'i>pY&QVhMxcKFvVlY`!damiV-I+@(KYq*h7Tc#=~VXP`J3ctvL>g6RR0J{l(Zt{p^jq7XCq%&>(8RofIWCDX&H4B0Kj);yP>^##1'
    '*h8(M0dXkTGH8gn`K|U@Fh3$Bxa2&aiu5XOU-G1_;Ng>XQdte!ZVh^9UtvWc>7#aG1W9X1_QiYCdRurSY$Rj)^9E~_#Q!D;amg&y'
    ';$gmk)^9twmr%DNTXI7}7sbvzCtt8zAyBdi!^?KEEB;Ri>5(R%8)<LQTF9g@7HIVHCWzlSw*-5W`*h9cK`M}nY5Ra?G%zIT_omf%'
    '2D@}v<gT<;A=M(}!U5pReuX!tALVI~8-@IsGZt1us`M=wg93Vk&q^kPrVQE(>(^@?;WbU3>Y3E+Z&7|^s7E1a$P8Dv*HA*Q?$h*D'
    'a?a<Bv%Uk=Gn2*3@wkDgF-X#D(?_A9BC4mJV#_yx!-tu#N)94-O`yNj@eP_vlFwcIAUc^+hxFegXNbO?ykSamZb|5~rz<i7>qh>G'
    '_K^jtIj%&I>V3T2nhV`jp?fdd4E$J!yM2aVP_D#8$=+IdSpmIjO!0m#f`p=O0-h{AQ+=?~-ahFMk`6m*GECn4`?*rJwj3BhjM++r'
    '_R{zugKqtB?M-;UDp8l(q}M+qR)Xy?Dc-rN8L~!g?C?sB<957uNfUf>I~->R>R0NR&AR;xilk#%Vk=StIaCNGt6YTULKA2o=nJiO'
    '(dn8%wc@S(EDWPMk5Zj<q{jy+js`dgMcEMab%2Jx%b+CPI_vcvksDWZ=?EMzpKmr)P9U$mtKBW$%$954x+2z3eJ4M`-izHBVbaez'
    '#XEQ$(a|PFw)R+CG<b{~kbl00!-8H<hG%CnjZc&2_dGEuH&2s+4Zl1!#8Vstf)+<5RdfP%jH8Id|Hv8%K#!D8Pr0&@VfuN~N0;ik'
    'H2j$E5#Z+NWL|D>@(~9$mv&~M<T`EXHVAF)q5Q5drw3@NDmxBT6Woa9*p(xE>6=AF&Be@i#2!|^0u>XUyy**@laEUNc0%BKxKbx<'
    'r2Ss1Kt`HWn&jQV?Renut`{1_Lq|f&Y9Zhy4*D@B&M@SBNo+tH{C`xV>00{%&{N9kFf);Ev7I4>uK(<$JOn7$5flZmQq&2Pt?X<q'
    'u6d(Wi1uuC$T&dTL;Df%SgF&-8fF?wwWR$*&y>7}+frf>F0Wu=lmyXqkJ-oB6=NgS-aw?Pg?4$)h36-)=APT9(|+MeaD_j-I17^$'
    'X~u$g)7uv$Zw|{`zq9@vY;1Xgdc@=Lq~4xVZzbFk@YlsLL5Y9>vfoO-4ULXbJHJ4OwnNi_+(pX2=ATLET+JL@XEv92Wc){5_2-wC'
    '498E#0t!sarZ`v<HAR{L+MUW`K~AI4hfzUrM#GPHE%Np+U0Uag?{tV^K&OK5I*XU7u;j=DDmK~~Dm$c*F;DIgk?L#@%Gc(}v%933'
    'cPRU`>-J@(OUKf#JGdo|{8$^Y7TTUIDFbofiwly+y+O1VUAEWn>IObe-(0_ZR3pKb?Iny`g4cLZ`}O6<!im&~q$sE!F6cmE*BRYl'
    'mvVfMc&zy8^ew3YzV=z|*~B=PX;iJ3aEdhwQU0@=7@3c1r};ji1OxZoST2nw!^!+~{0?+&n*hG+<qpV*Q`~z${i3eEbN{EJb20|u'
    'm_Z;6oN5tr-1xC;i%6TNUEI=<#}TE!J~K|u{87iJa?>j#you!c1fvB@5Q@jkTr8dxf#E5;vh)ssuW7AO>sOsOo@BPyrB!W0EAs!C'
    'c}&?h*L3;29bf{`w2GnUy-6`+@ItU#ml=6_&uK8H{^F7=Rg<$i)npFT^)#4-aOhUmdL?rXO!>a%OR*MqED~5-t4^Qvy5MIE0u*Ko'
    'd!0V(kniN5W3n14^NlM6_Smt>XD`LB1Nd+dZ_}JpR(y%&>ssrs+VT$C{(hyx3>o_4Mf@hpf#v~)k;0jQM9w38wHxdap!-J`-P4N9'
    '{(G1{;c;pLT00DbK^mX}^HnT^)^IZdy(q$sM?^~BlbFHmwJY<tFTPNw7$?k-vA-14F}&8+nRqq$4fxnGjc9C!VhS(Is`O=Kqdn~('
    '%`8D7j?;)vA@(ToTycsllQoO6PFIJ+#A5*$^GLKsp9jCQrI{K&qF>3P2g%q|0+~4DfKDmZDu9yS;}Ggy4cpDX{g|Y(Bg$NEt&`O`'
    'C~1Fx3Z;3<Iox1w&&6GryH7#hyliC+f9;&g4F-^J3X5HCN&|^``f(c;2k}IsUL)T`;C6OGo=g90@}`ulrmk%`bY`*gIa_$g7s5}X'
    'OC@kfp->besZv-HL`CFNze^OJvxcm<2}sS?#yGA<wcfwdIad8vijn4h*xg2Be#v!|o?yo0dPg(w)=C=SB};)!Cof3=<>XOlQiw~-'
    '*R(nynCmP#Q&1=?Sm|9J^PrSENvT9Qb~J}*em?0%=W`F(@*oSy76!$5S=7tK_oVG?^Upy`lT!*af3Lm_N!1?MFDn%<QJz{s!V|!7'
    'aG`v-NKy+n;j*Vbffs^}f3aN>M+f)KM~fmI$1*rVWhK1?b6c-;kK!VTo!sUuM-T$(+wvsBJ4`iBK@#Ye_L5m0qkwH)7U{9r*jf<k'
    'iAs~T+-pjsE?FF!mz-PkV24?LcRO=Syrd--`p_{YE~w6;mmv~|#PCmz3H9(fCwJs@{lRwB*LigW55&FIeOR-67T*Nu=00R4jpOw<'
    'Zt$-#`3(`qqO~}Wqs~G!Qs6z*U#80KG*bb=N@wvW_tfiz5W2T8D-dLjzDjsr9(bA#bx(R<|80O;!eHX%ECVv*NPq#@OVN3O*J`P9'
    '>ewj{C_4&{zlw?g+2)RtO5zX~GBI7&JjSfcJRyGG-H3^I$-(1iZ#IG9M{F7<MdMB>8B3XDAskKqL>+93qhCAU!p>9Gnb5qXP~?~n'
    'l_Z4nR%u}0(1LYTGbH$>6ts?is^15dR%8Q+N=l0gl85PN5Lwp;G!WkVt9g8o<uKN&AzBC(nIc(;=;bqKNRC#|kKQhlW-8d4!!668'
    'ZJ|dsA&je@OGq&c(!*LfTZ7ok-(nsp0)X~;he9A#$Dhb$*KOL64Q~&T@OR?V6V`<9iB|(t^1)ER?j`vTSa<~Z^4)vj+^Tlk|J)>R'
    ';#SCj{nwu9TetmJ<e&8i5ONy?zi7P@zvlR8zXe}yW;vU)ZWM&1^nR(x9GZ5;?|f1RD#2$`%qd?2XC_)7>7vXl5|J&qFn$F1g8#kx'
    '?P?e1!otbn&Xg&mJT{Vj>_dM(@i@x>uKGN|y2f%3kPWe?sW7z@2#0xRtaJ<CsU{0ekRm8Htalu{Sd)FlOEd0a;N3{f?MPA-4o8ZL'
    '*{LeAF-{#7|8}5|(7ow#&}j0EWc;b&EZ4Z>jYXy8#Vt~@w<g}vMs5-82HfDftmcvSkYkf|`4$E1S^6FnOF@GH%G_t93$$#gzakTa'
    'KU#4X(`w08uPyi3*QP?B-{J(k8(q);l1Wd&c4}98=1asvH|H+gV~2b@^bV!%rnJ?xk=ZjTG&g^v?&q8oTwuQJ0(hx(m~LTZX(yJ@'
    'WEzBW^Q*(><KO+KxeNsHlltE=NnXs+(RcYH#b%78%muhMPpYdVl3Qte;D;7C_}?YVgXEoV)UGt{02~fv$=|Zq&tBy^ZkIbNZV#l9'
    '3tuEHvn`{>L-?U+SGn={jooxT3odQ*^rf>}OSeK@t%?V|FJ{4&HdvyWW&Ft!gH(>~m%=+EA_RPIyfe)-48mG`=!YX>I_++t7QG~?'
    'e7Ad))?=%~KSpp5Q>YwSHkoWGDN)I-uB*DWiw6p1HMs*CUw*D!3?sS@rRWzGzYp;0mUHL+9~6syI4+q@M@HM}5t~wqSE)cBHE{he'
    '$4>$#`R}LzpOj&<+V&AQJBXk$T@8+{YifM!jDCD7X2lEVz@DY<xcLwbc?Dx2^vF~;-R84Q$4a5~zW-2YagcV4zS7PHTht&Qs4QL+'
    '>&<n0WR?IpZ#_SP9mJi#x8W?*QdN-S%53#UtcCj!V#k3}b-ULI5OHOHBfOmDuHm-kxK~~v;WQ0-QQX*&B-9<ZnAdv4v6kIu-Sp%`'
    '&}i86ef7a;ezb{<B{xi?-H=R<Fr$xWxtTeZ90GJXLAH(%jN-2Z^^)U@*W}frL&_RvPB5)KaT$jutmPW)x*Xop*PD*`Tm{R>mqNIl'
    '8l_p~H4T&H6(?5IcAKTstD&O(?W64h`8h<;j~vc$lEX`-q`2?=wpa)WIX{iSE3v48DXRp`q!tpXzT%CRDYr-5!t<N0b7^qShXn?n'
    '`Q|bdF=hZ@e#ZXgTpgHr^gEl^W%aRYyA{JJU?J4C{+bgvLx78y(KiCnL_%TY9Pfb5TtbSzbjsVnaln}Bl<hj`1=g{s-zAb2p#fy)'
    '?gIY%o}|sTbGJb+{EaOKG}KFmNJgOFZH1-~rE!ucP1;`B@kf!|l~tM7etM4B{Gt}mmv)xc59+tS+`=%@qy@<HxpdRd@!H`4_7jbx'
    'N9Cpc>+!M8)fDfsTj-zje5lK<5z#d_j<&&FXG(wJ-fM@ZiTquoyD5`AL3a4#XWZ3tB6Gbi+EfkulW%g;KQGo3x7h~iE3T1x<k>0H'
    'Ht=HSq139tHpvP(mGTzMLf-Bn%63~tyw0+2@3|X;Y^u9(T^Y1>?^}V+?dI@G8AhtZ<qL+BxGVfQKF=B>6?z6i0p_UTFMKuPo`Thn'
    'f?f>K)@d+`_bbwy`YMlT#4iaqURDMNmqxn^kUAB{51-)B#{}&wseZ|_YAB5JTwZAcl&w486(H&CArd_Rkmc8|!9k_}WuwOa6QA`$'
    'sfr_fG2)3EF9udB>N+b|-j^!eN{4&?mKd05dTva<a1}<M;atf8)iRFSipEZ*2k+#u(b>Inhc?`X8Zut?cb{PPi9+y<#l?qI`=5JY'
    'V<p2j3nF#5ZR7U0byYDRR3<)ICq3XN(Q$2yh==jebO7aw+T%ZJ_}I6~uu3d%9+X$ah~q5?>3H+PB<2KYXsOBm?;B_0x;>@g2Z{Vo'
    '^1J4$3a5W*ZUy-tJ&#Ck5#sZLKM>sh4HqdFD*n@&6yw~xAgQTN=qLz7wOYpM0Dyi}$k-vxXZ~hKFZ1PevZ}-zAIvW=<YqIQv~7p9'
    '^?+k*c~6?VL6}NhUdtzed*d0=I@lkn5?-6x9a_sq^KLJ1nRnIan$JAiH0qCbA-f+y4j&m2ntNax|HZ2?Zc4|yn%7#@eZ)i9%{G#9'
    'uTFtgA~wVxK<359p`&J^5^OO37O--MTIe$1%5U-HW3NY7L1WZ<Q5s-VCh053!buANOinQS3;$C6DxDI1>R8Th+(LLBaxh}djk$=x'
    'M{4PLi;}tH_F4<~BaA#fkR(4cHvGKRhGlAToKga&S4ZX36Rr8f5F4VCZrS*=5DI*ftxW5nWAU%>0iU!_Lcw-&V#Kjs`EmTplKL$>'
    'tO}Jeu==wk=dvhi6>0Np2MwG*=_k%p2S$)w2%W~wzCR3Tttp-%@Z?0pZFKYNAv(&)x5I~Ho^tZ+@5HRNvB<rv-g3fZP3Iz@XLZ~m'
    '!vc-Kz#&IDYcX(Hq5tN^?{5fBIQvPCrsDV3#-t-Mz4LILXaV&y8e=Wa>^tDr7?v2ehFc>_J^YU^8qO*26C-@P4$Tz8#c!8v+A*;s'
    '*VGI;{E`X9i9L_7rE*$e=cg@c)UQ)a6MN~`C&8%wzh4fts8XWgKK{xJw*wpuXivcsMXiH2$O>%ve>xj%qEfd!YoEOx@)T;qXhPuS'
    'm*SYjU|;XtGI_t0MgLC>r*e$?L*Kw`C}~-8t|NRrYFsW-jt_CCJKKs+A`n1X4!W&+YukWK?4%*e{`2(goAX%@GELDo`5TOpoH$<c'
    'wVwaiVxE_JR5uiC%0^e0Ej8^iT)^hN0B2i>+8K5!8@Qtp6E`MjTrAz7?v4Z|&rBa^GiJ=+fU2G!m!|z&DfP!u0x$N{;sO(jrKbZo'
    'dFAfPZ)65i?hVhw>gv!7|H{4zmX!&4c{LSK4U>(}#2aVMx;+Mw#bWj4zi6EQFFrF14f4u1KV4X+f;ns|)L@}sP`ZMr6V47CJW>Y5'
    '2Z{iLbu?S0l35hkUu6VTrG5xfTWRB1EM9|)e!Sn~I1Sv*+igmJ8?OV&5>y7fIX~NEs%nWrqJkMV=$QuAZp8oTWvb(-^C#L<;THLa'
    '8*K9qTyd=|Bm&gK4z6oQ-(=LlP*!fuQ6g$=+6jXM(ePulm8DV#9O<<k^F<$}Ftj=vOjZ4jM*=l~=$U<2g}w}whp!DNLU9jItLE{o'
    'y-Hw5+_VT#uYO-Tpn+=zXo-z6nIAYM8A$Fvta#5ye9l!hoJ5Q@2Z*4#f6wB1(f9g4M2y;NHa$ZDkh~|uzeuOS>qg<_KTPmZKue*f'
    'hAbj~wSz)szh>xkydILXnHl3u_ICk|N2T7N8KJ@uHtQcGCFpmtu`MO(3{#)@l8*3XG^@qmz7h<wG9E!t3Hl5~a#lohhAvUP1_=5e'
    'z*kc1hrGitVeFqn8kV0trKcsmGSJFd?G6DT%Ai^4Qc8jlAY&w$!fH(*k;-dZHXXqg^P3f{)j4(qy@WFGxbp-hF!kc)bh+rcNK)Zv'
    'ddo2xaO1?EIta3ZF29i?Ix=~3ReZ1lHrWHUvKL|WDO+!BuC3tLxV==jvng|o9&Y*BNKhd;F~yZq`+4-DBN5@8hvtqU<N8PNf6)t%'
    '<PL*h-k&j%p2JslPOT=boSF;US@W@vUr(OY4pb+)+P5PU?C_zYBozvhd%d*j+vALUfY@&o(miM!V^;hfiP6|mspBMJ8qa1*RHvX?'
    'xXbTeFt_l#u10Mr+yZ8kUIR9UGVC#C#wx57@oN|5^RzIdc*cs@8w|>;X%VI`U|LmnyG-Of`A-<)?U0{%K%6Bx0$eSJQ~~Zs4WOl;'
    '20K3Ol5cPiq5UqC9_q(VyqTa1H9#Dw)!a?t71?%6?hMkZu(c7;N6=oQ$NH<s(rg>2_~Z2jW+cQ(HOyX(Y2`sZS`x~Qi2nb{c+*v2'
    'zJuFOuPPO7Ib<~-yqr#1ZQfMC?!PyzL3YnA2ca~<xyj2C?q?t5*rwPR6aCl=)y=8@4`Q)bd%3nMQv(5oKl-{}NJJEMM?3#n>=m?a'
    '7!rw4qwk+SU@$WG>M{BR-O<%_`g}J@s?6na1c(6zL1Ywd<`DaJ!EBuT2}@1L;-f`JP`z@z@GO4in#=!zvPk?ZrTbidPj-2bAT`Mq'
    'FoFjjUIj&po%;q;<Kl!`*Y{_@6fW%_ufau5{}5&+dCZZkOEH-PrDJZhGA3$jmk4Bzmb{j6FLOOFjcB0epxTX6(PX?hi>A}PjV)5~'
    '_l|$B=d;PAJVFfGB#7`f{-%`_K2&N7%7&u+QizqoCMlPDkonIvg}rB>smccZbdv{Iqdt6rrV;}MljJM<pEhfw*Aq~)y|A1z;T&(J'
    '+B(CNL1Zrfg^GoE-1s3D`anJjETGa4Ae%p0+_9zYTsOS|y)Z}^Tl)uEOV!GL(nTX6_85C5VDy9Iz#hEzbM`2+$(rfFW?(j5<&O0Z'
    '4>~7OEko2xPkl&?*|%%4<%p=x`9)YeiN}<B4dKY&We_QB%dG~SM%jK^uvu$QEX^>VtW8VlZajMm^AO=06^aLsI%8d4!}$YFV#Eq5'
    '#NgA}3B?j_va;C?|D{zcCwdt~7JuTI2+OfX#M-B?Igv7Y^r*()1Qwm;Xw~Dn?9F4-4~Fu^_t8tNY{tRx&UKCROa7T1Bv?83F%o`Z'
    'A7wfGCHSmSJQkwjRs?2cC)J38U&|&BsECL|AWc>9hwt*gFXlA{w8qEv+&tPyqNhIWc@~kc4r<eQ&$a?3Ye0qWt$&7N17zTMhk|Ox'
    '^4kjHfmS#Om?Fna;U#9`Q(Wp79QOBC`96lacvo#4JRcGBG7{(QuQE(AF%rF?oOT5%J-s}*MdbQ5wj21GChHVr{NnpV+EWEa&V3>z'
    'C7F+jZbT%h^37M-ht&>yJFecFpj@(>sseTGjo~O_A&wz`aV=I8?Q!JN8|4I4h+r(C$!1rB$@y0koTiNcDOA2PRn-%@`NHNGO2&)t'
    'Mg{Ei!87_v+r$so>#gPsuHW<%ANTL@OH_{Aa(?+@LSXbq6hg6mb2&VX;A11~{z)vZtu#A~jY7}T-9WtHEO=kHrM4MSmGz@F$YEq*'
    'o_WRFOgOe}WBuM0D4{QLvFvD*171w7ibWz(%cc~KS^A9+P0lGMV2klaz7nuU$v~v0D12gaa~CNFV~2r5>>gJ(*RFfz(p=6C#BgzJ'
    '9$iu7RP#Ly>$c&mK2zh-J<EQ=NF3w%jGz+*A=h2sFCS6@d$K=LX-ejsgGCf`<tgH7iG9M!`X6vPZf*$53)zRaVjVyS7raTE0le#1'
    'UOxLv&r%%ED(^$N{YY0imu6$RIX_`(^{dy_KYOviTP7!JDjXQ=KiBBlasE^D2~I!;EYEskqi)7~DrYlE^^V57FVrUjp5p(ot#)`?'
    'e<CGz{Mv7JjYz<dRM)3=jlOL?X1;iueA6*~a72L@&|dt^YxXS-36+>#D{iYv4cPgB93<h2UN_-zaJH+|-owH*yYo3ZXv~!%uX_oA'
    'f^^tB-W~jIj6RLWs8mJi5%Xe-DFbM5*t+re@Wy@KxK;;!9%3l+p@DOBy?Oavh`Ux5igL|r{lzfcG*q_pnj~TPpDEPG%2#}f=Tfa)'
    'I*PeY6yvNwUyP7@+#y7JPty2vqtXuMS4R_+QzD~U%xivO2e8O;lt$fCl4Z$WdC*@UN^0vnTzI=Ox>Uoz+gZG9l_qbNW7fJhU*lN='
    'F#QJqtdt{w<^P@f>2Rr82FO}=H*eiTt7`=V!yqQexJGXHbuOfi%)HZyaJ?heCh{Rke2Bp!5HU(P(K%>&$dw@NMc_n)wvzQ@0M5zt'
    '9&+zZMkvdqpE$`O-dLkX%cOvQn+Le<zExi`<8@`Ui$9ZPX~A09y9qBvRF=!XM(0fN9BmliQ+?LfXQ#^FN|pVCO7bep{N^o1iWeuO'
    '-w=ZIHR9*da+3~*oSm?rJcTE-)8A5jm=D^7;4rSWmYrb|UZ<gZV5MieSQ9+GTC+N<(vqKo$ARB0bjeL57~Z%4r&oH#Ldel1a_Rjm'
    '&T4GF-UXXFm$C$r8Z0qoGo4*SHRbN_IjYa<EiGQ3i=cD7Q|Bl6{pLs&d#f_MQz^#W)(cJHWVC9g8sfXEw{W2Vse@*ARm11d#^CI6'
    '>-&{9rkBpL-h2~!I$NzzN6lLOmwK!>QHzzNl=9o@_}rhsbs@tRc_g$%Ar&YLy@s8*$H@Ytamz_#K(ES2Tow3nklFEb5P1<La|b%A'
    '3~zG-i0|B+xzAR~3&YXN7Fj!$s2)c+hWu=`rVy;<_67w*mK#~iNM`CA(x7@iU!w*vQHw_i_L>;$+AYxf;-*Tsr#A`;OP2(zMWhP^'
    'Iy?UE8dY*NvE$`y25pR!F|B|3!DT5e76thELu3r-BideiczfZJ>;o*e-Wj=iXSz#8#*A7?y~1g=N<|4JC{5-TE*1y(iThlQHw62h'
    'AR}RIZ&#AmCD_5M&}>C0mJ|*9Ws{et5{`~&rMjP|gg$47;QR}%Y;W<A<LpmRwfc+0%8AFzs_YC7rb0a}JMIXAsAB}S*(HME#D}qD'
    '5d5W6Kd6j~PgEUaF=`$4<ufFp>Bn<57H~D-IkQwyf5shZaJyj{bk&^r6VP6gtKRgYr0m|{YtTz&eT(R~r}Qv{C<a5OROlri26&J|'
    'Zm1phiHyR@eAYjd<A<QF=6#*e_#n)Hq7+lnKtRDMui>H+J;M)wt(UmrK(GgZIM8&&jSmI49poK$_>*MZp`TEk6MC$^QJuQI1OjLr'
    'tmMXNN-T-W5o1BkTRPM*OAUx2I>|Q+MN#O45;CDYF+;nr@#tEPyH;F(4%7(U`tgkrmpwama>^O**gGm0!~e=BIcpMZ5}bnU?F4`8'
    'n?$!dX)=GMo=C^EJ&;Lyhd!hRl}cJj00h%y{-HWM&A|>vyHu*|*eE0dt685d&g>7BpxUj(=kT#|1y!l9gi=}tRrGZyG?)xzQK<T!'
    'O>gMMhB$Q2Z%4S3s6}nP4)be7JONAKjf3m%Bnpg&9b7@tAk)r;@-D=ISTdrJ!MOoK*B0EEA7<=p$Wxz(d6)CT<l?rG+)4c6&S9Tf'
    'ZW~n+bmrYKhr^m8nyar!?z0OKBT-;%V>ANh0Z6?GY1vPzH@Od|By#o3=cDiL<df>dSi&Titmrd|36BR7L2rWPT`F$@$1=+TJBe?s'
    '$0*5O>DXu9fQsWQULca~4g8r!&_xswRT(8%{Rs8!$2mo)t<tf+8uAbj83sPaRlD|&t|DNq#{)PRr>9Q5OI5?a%3)9?DMbJ`=sgh3'
    '+tqP(0-YaHSxecDpXIsLNLtPB=bBAV0r^DhU}mH;Mj&hK<yBSYbxuWxbM89?7W&Yol7{nDa-VlWf##FNu(TZNZzcFh!bA4k)5>JT'
    'axAHazD-0J3;WDWQ&ibO;#7XWW-%{rVGf*y652d53tK=sgKfSMdZ&%48rDQ#H8M3wBm4{O`Ki{oY+;qh7gH_cq@St0bz5k4KicRT'
    'd}f(q0SA7bmQ@rLIp)%_`&L1I5KYGgzcztLC0$+__0v#tCm>J%E6FFO|G=V7g?@t*{HnAN?&>s=shIbLqg_lqUk47ZNa#ChH7r&k'
    's{*5m)v$+HT?e(8UBla@UvNugS65PT>!4eNHlGJOrThurCMRJCZ(^fWa|fx7R6Fv8!iXhJ3oNX$dKe2*mdw+tq-OyN5DZj-Bfop~'
    ')<D%buGHVsuK(VkNxAvj=Sr(DF8JS?wEhlh!;zw%P-riDkhXvD536mWzP!=X^r3uUwvR5++@8YjBMtOHiF*7uc1j%_-T7xGC*S)s'
    'Zl@p({N}2vTS{%sx}__qV3gq5CnqER14rS;<JOD$NXb+tDMU?49vv$SY5|)NA)-TFI1lR$iI+e@%L3KQ6R8^}w6B(7s0E01yAh4w'
    '^C2<)rh-dCj|K8G)h1?dZF|T7WXLpT9Qj2Q7Z?Y}qM%0^WN5Octy2XDeAzpWoG_bZ7uY_rrcVIi3XZED+n)OO)mq=QOSAKxoLpTk'
    'aTDS`Wu5L!(BUUv)4wH7K1#-Z1q4v>2rP^7&pjqX`XjKQuvNIxdz}}L8QdN8rvG}e9Xei>8k*kr6E$Lst3K0)qHaMyh*uk29b9RE'
    '0MO-H07S^tC$cskj|}8H+}=gEMHn<N>VZDt)l<pG!Wb=^PsmqIpw@>Z*2#*x8A`(XJymeKqCqjjTkfdU=OiYGcvvwYqxNIHG`h<T'
    'IC>}0T;7L!oM%=`bC-6~xz-vN+4lk?SfLl?cT!ZuN_-qOlkFuQqKjU~_623qx1w{ywy}(+^Yp0UAc60}53ygxySN&jGbb3c&A|$1'
    '4aGjFp?UKP0cqQu;$<^fJ^7+SYSTp0;C2sLGG$n8bnWul-#8-yMWv}w!Xamw!Vn&A)jL*}eeMB8wI#gIe#`BXiD@ZLZ;kn?w|=s+'
    'YVA=`gnW3U*H1-+0NVoGn=~G$#I)SmLt&{0>)wPw%dY~z&kQk98}o&M%TeD^fNG6x5?i0q+15rQreNw#>`i1+LoL6Y+J9+cs1<et'
    'y~<LzHs0KarLg-Lj@>kK{06S`*F#-ZZ*q56NE9^i-p+%_=2q6FdEgs9YcNXOd-WItHE0}|4mLRzgX0QyJ1@$F)R=nF?gAKr=4=*|'
    'FR+BrbO^gP!hK<&&wyd#Cem|5Bw}4*Se!Evmv%Oq43qSQlD;l{^$Rn7Ls3+ujG3=KFhB2pK|nndlU6O5)a;z*nf#+?Jc|))ivsnE'
    'Q==xe89L`ovs~&+N;7N=dxV?mUboc`Udt*=z-3X>2#gPv^(p6V0F>agElp3d3y2eKrnzWcDH*DSQ-umS@*wolwZ<tLKs$JK!O)CH'
    'EQlhZ-_(U5h!Arr_L#{I7II`$CFki&y*aQkn8Ua!SjDSEn!P$}{_-Q4t*f_=+1s1I3>B|amIzxCowrQhq8;Bvq`V1-kLA3cr|1<Z'
    '9JmV%dX!3$G)ewVwxXDAjoXPYG8zd=@ROE$=?+BXGTA&DO0|pXjH!_jz(QKUa)zsbO0{R|ZpTr>@>G23l{O9Mo3>P9hA=nIGpb7@'
    '!maG&osw-*3^!(l=iq4|Mj=sIf?s)_F|R2GUIgLLFrmVPdShb*i}Udbr4|RjI#3se%%93)wcz>-#d;6zZ+-pc*m0wvnd=mNaFsC}'
    'k*XXqSYcEm>V$Ey+O{_bwO5kP@ZrN^A{M7EdW0!W|8C`AiK&URQKBtMX8zZv)<Ca}>J*0$c`Ym~14ZXml9TJUa^+OU&<Q+B-t5qa'
    '%ns&;bLEOxgxz9$_ODNRkkE{*CjQg+)1d+}UIi!(Yp3>*H!lJKaBu3f1SV`xS%G%y14e^Nxlg96(qRhjY*;I>%n0hhc41Ebs?`IU'
    'U>g`o8MeG@Fl?;wS*m_$`Bua|V=$5%%bl=qh(nl03Fet3lQu}pC@J+;=9>DT1^4moum&N2%kQ9amDD+fW{!scKzhi+X9j$f89`ec'
    'kyFX?AS`-YoDC)+3tZ}?GoAm7F%R$x%I}<_YZNnjXpa%O5Z8l-xS6oi?+3cQRV9sE<D>uMlAp$0)aE;(4(2k#DQjd6Cn_6mQrs<i'
    'szxsA6JmC}(XYNct7_`~CeFsdYY_DQlb`HL3Qj#0h3H5)dH-*;r@AP3JsLE;6i2d|n(m@&)PEzGqdz+#8Pj@${I_huBP9DPAC~x>'
    'XFsQ`LMufBmNW1JmUY(kWQS6qf&En%++fJE5@3)+w=&Ik6<n0$WHdzvmrDsrNE+I1et&e0s3lM4G^NAIzmJ~?@wh^n#M10aw~feE'
    'BsF$^kKEY!viRe1V?)YZMpQ4q9b<I?#rk?}>fbidlo^IdWab-N|1;ZjdYNFs@(Bk2mZgMJm=DJTG<-CLDo5x#{9%0j&c$0*;`0c2'
    'eXt{nnt}c{U_}5T4u&1BlpnsXW9J+zlu^^jVVn5iDL-%ykFDWiLo=1jGk4*iqk!jT6NX*C)vCfX<!$y^r+l5@CNa~Yhng~PDCg{g'
    'zk`iB5Hn<a{3D%<&N)j-M77YH{=JQ@pIjN$vl)&J<qN?FuxD22Yj8}*Y5(aMkY(k%`ig6E^%(!Cj(}OzK$s5O9!d!&jX4qe0B%31'
    '=+VR67l9vynmG_6sd9(+8T*sN?C%{*WdfIPmreV@lf$Qa?|Ag(WvYs~%y=>=e7oQH0)4geb&uX<uf%NG7tJM^Tf{-+jWDwElLzO5'
    'rh@9DD6NWFW$Rvw!vgem??G6U!RWPnKr2`*skS=?W1ElHujO=Zm9duYsO<xT-<J<@it(Bk%**ChyOsh>l~^TQECz3k%gd00z_O<Y'
    'b$nasu64JG49`=TYDAVnVlQLViDtm(P+=`A3h?o~m=@%`|CKQpK5FnRD#?(1Ua{gidco}9?}z5N=@pO=kbQWK^5<$0L_E5rJ&YjA'
    '!vE(0rCL*Ktwqx`s2<BuiXmkX4*(3prPR`w8&HaOCP-{p`NL9w_uaD*nNzQ<7!7bEi@-D<E<dzz7a#96j1FA+ULPYNM80t-R(ba-'
    '#e5Pq)krvg*s|33uw1dUO4SV%6FRZ!f*ryT*DMFq8AvJzEyrEzQeE975=W708s<eWoJbz5HqcZtB+OvT{&(HmCy4>)3T>*p8^DzB'
    'buIk;4Vzl1B<mg_9Vut5@9`rQdoDfx{<DpW{oILNvwFwpZeKwA-t)D%25LYk)je>U8j>$HmP>~w;`)3%xfgwScC_M>a+WtFf(PO#'
    'VJB!~T4-Jf6l~OncLq+X@z(7yy_wVi1N&%n-GRRJOfLCeVI4_Af1+X^?Va0Hndxq)b+4U+u9US3KVo(8AhB$(c6me`?_$w1gI&NL'
    'yP1qn<w~YY4NWC35Yi1;RnpTOalv}+hVQ-iHvkye_w&u<$f!I_yv1dMyamW_;nl~Dn!!mj{gFnp8#z_p#n!ud^9lu3h|*F_M>}^V'
    'F@XgUX5%UH#+rM$fufz{`(xkCE@ySBl73CrtuUXwsWL5C1{1WEX101I5OA6qH0IE3JK`eppH&+LHK;aEhx7smk0X7t@vlb=`;V(T'
    '(J}Z~ngTP^r|LrSF#tU=tgRY_nB4oo<|x9@oxs==5DPKNz|S_2H*L92m-K&qnG=RFnJEg}QF+1a@?7pc{vE=9xwxne{?0fc_0sW7'
    ';my^6-rnW-oO5Y(QY-kdH3mDipDK~|bso5bJLniskNLYjP2W9|$)Q*JrB-Dr_x~TzTMRKc4@e7*kjgzhuQr<VQXUG@hR!{Mn(jf7'
    '<n<9U0?-6Nrm)oqQDw(@(%fdfenF?9+$Y9_pp&*QR@H{4V#(l<nQ7XxN2=(u_i+7iGEUG#r$4=7!l#6n5%a2zqtHU`!U7W$c<^m$'
    'U~U^<M!#dOY3H%r4U8hm(grT)H)B{54TBvjlnEi4RSpMHqOLgkmCbVW6?424P~S99K4+Sj#Joy%V2%QmH(|mK{;<wx^lBdMo}6Ql'
    '9wzN6l4nfDKnpBws7FUN{2^ibw<rsJB80y=B0USi%A?=I9~F<K`|mbTb0H|NaLF-+3ncUyF$YiNC_u$#V*MUu(UE}54z{MLPPR~>'
    'Cm5{(8rdhZN6hIb(Mr{c!u%-)4n=wrYaaIl3l6=#0o^5l%t7ds)S~9ENNoM`iX+@iw$i&Sd4K9Jm0-zq90Gf|!ywZL>BzK~<*s(>'
    'fl*2PGmbB*$C&+ncoWF4ZUlrJbgj>clOeym$S)(*ne}-j<s4n3Y1N7nRss)FS5bK5O^8x$teTwMnO$7iJ@TLDz-}6nX5k(pH!VCE'
    'tItdWI*_}(NV^$}@GVAI_}nU+HAH{@mb7-$=!PSM8m$;L^V?pm!f!X(DV(L1U?r?uT5GWQp7rzKoWhMx(!i}wtD;=c^?hT2{VZ_a'
    'lOp(jnE7X&Ovk_whV?U%$v_Y3CmMAqWP^^&wK3jgRwVZ2u2-aU+bqc67cn-?SGHQ%-(y!me2{Zj1%*8Owd$d8(xl={e5hxMRc1i='
    'BUaOUZgMd7#DW0F!KY1!L18t09yew}M$*xs4wRsihwZAqsp@15;R?MJLReZ_#|8FDS)^*)oGJSw81LpK%P;g28#6r{(iCT7)lghp'
    'acF=2ymTq5u});r&*uyt*7;^tyM!Jg@^u`?_qssob7of;Vi1j}*Q7=`qJCpOmWFZV&elrUYN~KD$(}BUyWjqd&I~nZ1@D)>UmN6a'
    'rR%g!2Wiu&K8*#-@TFtL+k}v$f})K!mi+-#1oS7`VKPsQuhxS%12rC!l-$sSWkWq#K@F@NLL&aAwM#y`t5LBU@FQ`tIs&5zAoZi<'
    'Jycd^03bF)a5A!a`~?YE@Lz)7wsj+JOGuA#>|J+6L3H6N0O4@pMUG~Fl|tnH?^+<%V&Q00!0B$S9>ded9c-iE-wXIzI*#~OZy1C~'
    'jBjHjC>be_MA)<D1s@TH!LkvT6oYZGIdZ#!!n5dwz|ftNv^N2*Mr~*mkJ(&X1OH@%cb!>A4^*>S6N|Mg%4(eXc#3*f<&>Qn{2=m<'
    'xiG-fa~MZp556^Uyj+m>M1Iots+g3#U1Fh^x!WPZ0}E)kv_-KNMM=4ZBLQ1%K53JCJgF*XK9@9_)fmLndzkt7p^$kTr@sL+4XjD<'
    'TgVg~So-e_jaJgZ^}_sd&YQ^z3iBAi%AtV9s4-VM2`UP_m^?nGHKQ}VF}_Eyu$_swiwQ4a&YnoL1cY^nr<!8jAHlQwxUiy}IQLHh'
    'ZFree@Yc}GU~qsXcy$$v93Bw>G@!06zTuvQ5GtXZ$35n60Zq!ZJ=%m~+%N@uMQ%;RV!r(qFL+kt7vnadMA-u#Pwqx@^=5Sq{h6*I'
    'K669J0kZpvQfG@mPE=YS-%@mlL&__X*y&lk2Fsw?b{A9w-kSf+2MMv0yOU-H+c%vDQ(O~$46j&rpMNx$(7199OdAcK4_q<k002vl'
    '*rc|u?<JuCc2P6He3;vRap3o7efNKY75$P@0|VoU9ezWo3c1b)9{(we@P!Tdir{EA0Zyzx={+Id6IVcSKzgq$LyP!o(G>3Kdb1Ji'
    'O07ex-at)iq#_4oVL$6+5FNvTQ?{TDW{}yFfSD}D`1H|o_j6?(F0n6cE6krXh3uRqs~gw**k+WTZ=UHI@m+edH)0XF{|2WK>U(W3'
    'HYdMo?i;o=z1A$M<K`FJ<l^4k+7qcVJdlw%55dT1{AtNh`D(E+3$b~HGaOTBWGMJ%jpx9MJ!d(I6T(KL{;rW|xJF#o^T`Ey+$sv?'
    'Fclhstd$;rl=!T~Gp!DHOQXGSZieK^qynH83X5~6Ym)EaSk1WZH%c2^=oFbLJi-tJY#8J&be^K+C&I(7?)$)m$L|ff=^ix?@L+F$'
    'QWrcpyr77$(oRs_C{%Jr%cb+)KGrOJQq9>AI|e}<BIcJ6%+kU+N!qozcU6=TbZEu}j~G5WjIQNMGYGgS7l%QIxX72Tx2+BHulX;g'
    'UG2=kA>1_Qf!}Iu_-gS@TBIR?sTLtTo=>8t%WY)|+@+4@p3H>DA)wH>8uWlme|vm#y050?#z%1vVH6xXRl*{|A+a^pvH2mSny==8'
    ';{8@z;kn}o={`}7wPfyAWOP$u3z~fq5!VCd_JDE=3V9yzh6s}TG{ztdUK*Z$eBC*x97ufac2!s@SNQSHVnG27D91a&!c7Z_MUwA;'
    'Pjs5DGLO4>-GTIB$LD#c9*J?T_ne7Uu&HD8Pq`syO^5v4m?N_wgMy&t;Y7k>7<OxR@DXf1E7m`fSO?#mWQ96W%oD6WA05>Fy5fG1'
    '^a&cOQgUK)_js@~0bJ4leS>CM_q-df&nvmIy)qgy)jga8H6dq3!DuDu^;W%_u$LPhv0x%teww&jXv9!Xhx~<N-T*f_Jt)Bn23lJA'
    'p}cR774eYekDA|OjfA1B{KBYX6u~Unlf6sg=yu*aNuFYhe<%B<+tJ3ht?BX6bg^=V@{4&#%IgOl)GKM<UP3j7_ONtQ1nJ&l`~P4m'
    'x44lmO1}Hvkk=66tt4c4Jy?KQde`~WlwirI-&q^21#%sakVQpj(81=?m{;`_0s-j8T81HaZV4+#oH!dd!6-dlDt6TA&EZO2^Vcv5'
    'ki5$BC^f=9C1vd0o$_VHmAJs|)oP5T*qF_a;|D7!R2lcn`1Sq&3fSA&VxU>dG<!|A2x8!2gS?Dya=>g~B^!06u&RFHDtSskRd=rH'
    '6exw)cLv(!a&hmbbD67sQ;&R0?hX(l2%ZUvi$sLZaN2w9Os|<5i<!DXHLdAS7A+9W${P=0V3`2AHmzRhI&NH-j}-85Um-aGDs+%T'
    'kxtsCv5B}Ba^*>o_eJb*AUffoF79^^`qDynhiJTv<9JdOg}BP2w^|mL&hPG_{>UhDaq1EQEV2OP8~uQ$v_h(whCZz_h!H+ws>;PG'
    '!@de=q-w_$t2Z<>%BuoL=u2`kZ5|B-h{_JNbu5V@f5jDe0Q%aAQ1o}X2qe6Ttz#lB)TYF*bX2d;$v$PE%k%;V+FL(8QROi5<XNbo'
    'ZSC}jGT%L_7Q3PYup$+~T9&T<99GO48It@YZN*1Hpc>SWKurNU#y&uEXrzzay~3gjbTiZMZc1=U<os0T@#cZk&LCWwgQ^3dFb3))'
    '^m1#ZYGZJxAtQV!PePcLmmpC7+(SNbG-2l5nc$x>-Nn#O`2;~mL~j2lYq(KlctABS%X*#??AAKZeKHfL5FNhz^v2o|wW`YDpAz55'
    'w$t1Z@VC2RoXxR|IVxSLBjMA=`b2pXXB&cEynbkaZ`a+tR4^ivQlCD)2V3Vy55=dk#ZsA>T}={QG^jJ%#SRMK<fR0R2mZ)eXK~8T'
    'C^2vph)%Xz7ux{0CM?0>ZZ6-KET__Mj|h=liLe&OWg6T;I#tz3$TsR<B9liT<Y*{i&_uKwWNd$5VF@7%=gv0A?f?#CM~zFVa~2Uy'
    '<t~#YcOY7ek0+bf#bR3ZZQjvC)M)*I!>7=^iyxzZc+}}x6L^2GFq&H>%xnmRZ~qK)PEj{L**6zBcsbGanWpiACA-`K7aU`qY|QuV'
    '&pT!45Jd*TC_A~sBLy^`&gnIg_+QDs?H&~OFeU~VV4Xyodb?elq*zHosqs3ZA-Gs77H{^3gf(;Bx&U~C4%z_N0s?J-H8FZ=GI@G6'
    's4N6>xh9x2?nCsNNYM(PHG%t*ajhagjk{<+1*2#U^!jQ~Ue@;>FgAk>-bW)aQE`4a9fO9$V0I^^_)-4X$|8IBEYk@icvZriJ0P_d'
    'B<*c;n0DlG=o*6Qo-#Fog~PSN^(fM!j0}781+)iD;hMUAtA;gE1N1WZY8V9i4CN%{$9=dfFq&qL2jjv2b>HH94MFIjXuk^IOWCfE'
    '=ww@Qmblmej^=2l2P@=q0cAgj`Y4s={st9)YGhY@7i_o$>YiVZ$=%gs?@REn)9t+}aO#XzEP<<>OJtmEG!5+{AvIg?=2E8C+SE7a'
    '-#>gg9ZZrLhC`H_J>U8OoU>1CSlIfSH3!(7IifpL>=d?&b}!gb#?Ry0D7j+J`D8n)F4v9r%RQ5RE)%jgCOnb!13*#xm~R0JCmV>#'
    'YUa#NJAy*bnkQMKx!aV6z@^KnTZ0q@k>A5E^)m7nu>A#R%)0p^^8go=65?Hwr?ctV@UAIiX@N%PdHbk#Tj`3AL9@<lMN7PV<WtR3'
    'J!=mg_(H;x;u1*+-bNNCz5Uf*^D4i~@rNd({@e@`Y0zE6EiS9W$&v|aX_#DRSrC5xS??`1S^PZClBH73NET%2_;PR)3=6=?qIyc<'
    '%LMLK*1gqPdA})>@}6QTZh1H%K|#pV<UZ>xikUj@v|yt&lS)ckyc4-p%`7{wu*6qjNSlgVV=)0QZPwn@W-@#P=p(=@eTEV+6ySxL'
    ';Z55vt8ot#@LW}qKd1zLj)kv-iyk=-*HkM!n@Gh4ene77=vgVKjY#<_g<e{b9*1HL&otM+;Nv&MRMhTsWHDy7J&+HeXAkC&mEF{4'
    'LKU;T3P6J#jX1-q^cO$8DTa{6d%RHmPjg%ynk*TUn^CYc_gls#DdiesZ+22F8O2dk?L>+7>OF<4XqqJW@l^*&Bs@^~#|7!ZYWjjF'
    'E1S6dtyq%EG{V0_IYT9m!dwaRe2O+>+(-_w<|{w5pV+NB<916^jZU{UqVJs`)q)F)q}po!4h^?))2mXs-{ATrS$ayy$>5_>5t|5x'
    '6e~%jY_9p93GLG8ahQ}fjj1!Y`4W5%aPiPobz115w{Ph9WbZO5WDlB|A}_HVdIkaSJeNvMMt5}~ZJoE(J%*y#H<H{iU|i`$C<yYL'
    ';0Y4Ab=k8aKKP(Nst#C7Sf^JGuK<mr<Abubp7DNV6O0=}BJ4qD`^E<Jqp=Jdn*&pEztGp2`wqledj5_l-cBOl3NJ;&46~A;K<4KN'
    '>t_#XE1G)6MA7;UH|aViEHSddDDtD+&ZH`>MTF}`3Y1Nn-AK3IzSL|wKIwUAm)AN4gqfpBA2=X7RtIg37znQUvJSH6*Rj3-#?1qR'
    '7MwFMtbQh~h3L*=cIUNlUnfajY^sjvA+l6!W0dC*oktN(p%OqMY~i5*FGvtHxo<K{2CdZAM=UVS&Qx0diGH;7$VaLVZeqtlKzv&G'
    'F+!KcCBo^9_qk8tX$wUx>OGM6oPUmLlI0;e)e4Nz={b`lzjb-_GnT>b&-CYn%(^89>E;r4bNo6x+c=G$o-JU-eYD6bo{mU~P53V~'
    'Zd4EDKWwCx=uV`dvOGYx27p2GHZQx(H!4I<uc7=RPr5uflcIY!8EN2%8dKn}Jtt?ivfI~g)Mo;EHr?-8A-2N5lyP?!`TS^dFx$<T'
    '!J;UMh616JXAJAFWHef!fUR|O*wdqu5ueoPPbo4|=ywD7G$k@0!2u}4K<!#$;vM$OCl*F-Qt<G#Xcs<mBW1pi!$rf&;PoI$sR(xH'
    'POB3N*6w_9#%MlTyK{(GlW(4F*aN3kPRUAWSuk$sNo%rhD=={0bfv($HXdGro`ZXlHuBHYhv&>~$lN>$ZxlIM2Z=CXV8W+Q-7RfX'
    '$t2y0d?!)LmIT+C#uLa9-g$C}s+rkMUK9!SXSQZ8LQ5&bRQ=RWMzo-qX@)gxFUksii8v$>C`6X77N@V<f@Hn>d#Eif%}~0pnQ}AS'
    '<8arMNR_4i8LE$!8NVsPRykF8;BvWmM@zSyX{;E&NtGCoq7wI?f2hb2>2|(K5o80*SdZoZ<jwG+VQZ<}G)tdl9k5^E?&o*EZe-Cp'
    '(H>w#p_Xb0eP4MWxI;&rH8BC>Aq%10KKHFMBu{#*xS`o&=Ixu*c69K2manElI5+yLaXgA0@tLNS)2dhAq4jQ<#^}NX_u2n1q}%H)'
    'ux*JyMRwdW5R!bv1?G}GXl2~pzK)juV`thdUUwcuf?RxAMm}_FZNg$xQ4J>}1rUd4d1hkY<O55o9sI8hA2Zl!towip+-y;7Wqnv8'
    'T&?FiqbEtk1Ujq0<^a<?FvY}=(upO}@)4i&qqOWd*xfnqpH-wK@jWGnctieD3W4@QA8dhYh3^}@_(dQ6(It_V5lJ>`>vWK)6P6g~'
    '>odgR^w?^JG}Wi>N2A)z*kU*rO)OdT2LufStDL-{=lwg@nY@8y3Y*j0oi8@PV5eg0W>eOIMz@lf=otSdYbbcDcez2p_qzVbmgui_'
    '%4b#E`lm{b(sJ_I)u=8uW`SraQak<U_GQxb+Udmg>S!J<!$Q<Df1W+HvIlOr`H3KZTru4s5nu_v7gqH{-Jz*C{EqN~gV=I=EQ1RN'
    '8rqOq$Jd*rS~H>$o(hSFcWuB4yYb#%ps^>s6Zl#BT{=r1{k*z`t`wb~+0l@Uvb=IG@(J~)IHzT$CAUN5DiM|pv{H&Fe$XME9TYPk'
    'E0QnYhyg$K=;4S*!%jL(NHQ9I4^j?9QiIla(WGUOL2s<y_D>E6`XX95vLF1tz$B7cHTd_duK-3;ig1dmr?l%03`mHic(b9AC8jIf'
    'dusWl46$5IeWa%n*A>bc5lQDT`~3pzZAgQE=O1se7uP*X?iQr39`^b}QcgXUiXJvTD_5!XJR|Fm|C;)D6SYrADwp(?!J)z=5Zd^H'
    'zzsL5R<i5P&=76#S?f&w*-U02Wco%x>bWb$Qg6PA`+n!?%t+jKPrDn_PLz8ZyR*r4hl9fJO4XpqXOiw1;iEPN?N}wYx?Ve7fmUnk'
    'HuxA;=&a$+6tU}L)|zd`4Y{3M)E2pQ2v?5Lj`bMoRBN}B|D<lHeSzAdj94G9&VG>%$QD&o-_(EUeClxX@w(+)mawC&s_z<5$GVR{'
    '9LGNFFh+DF>UgW-Fn<h!{31*KkkF?pS2AbqLd(XA!V8cuz()gO{!b`7C!}>url=`x;u5Ty9hiB*^@y5t`JS?mSq@TDa~O;qyh^C`'
    'kcxj-iJHzro{bBN+jm0nTAl#u({NBOar(6M8oOh1gKJxJGzxA8h-yIv8S^2~nchX;2g_&K>c&BusTI7OfhRg+A;X?*iQ8U`>uM%i'
    '+jO4h>thN#N02g$)n!c=j*|(~`Jm^?&C;eK$7RVyakBK+Abx15P($*9O(Tu+hB8P7ak`7K!2uz<k`d#{r0v?;TYr6x;X_@)b8LrF'
    ')2aFBPpDtrQS`<@l;EjlsbqoACiqR=C@8whmrqqs!KKx_*Nj{VD7QvT?37(Z-0DUv!5P>m91FMb@<$cb&Gd-M6z3RYr}G2Umg`I<'
    'GmnGT%ZSiKRd=lmzv){P>s=3poVlu_AxU%f7kn($J-PoC6Vw=9;QQRm@&*`MbUk(`$~bN3oWzWvLkTrroJ(|9K~YLq`71`~@JqA6'
    '1NqR)HMurdt(Dps`xQ+-Ob1xfBA#PWWR#dSW(rs`Eb*pIv0@eph^OlR=AXd4jBgrF%x1aP%PB5hOgSAGQwv!ICQ(vkKS7FQHz6K&'
    '#k6)wkx?3Z-A~IRmnn5GViS-ilX~~prxfXq!<8ijGy&jF{+~NiqS0AuldE5S7|w{WPJdk%W;T*7=l-{i2{?dIv9_XFb%u_P#~~z}'
    '2qn>=Mkd52M$a$FP3)2*q^2kY*L?RvxeY&r&&Xw7^7}f$Vv=?KoIo53V)VpHWC93j>UuyyUQVzd8Qq7B#uXexLO@*1{f9o7&6xWG'
    'SZ&2^ECp)GjQI*-FRS%7M+>f8m<u5p5e;p5D>-7$gpL8K@eURj_5|FW2mk5+mOUir2(1hFWbW+$!c)5`*__LN^pv;lk>|;m{-RO4'
    'g(d+2ZO?M6Nyq-Jp-dQQ24CbKEb?}udPf?pR(<mp&qGtwglZceB-QOX+Of_iS{EXL#TP>P1xn47F6}Njzr!ndz?9xuEgi4{$FmDR'
    'G{V%59izC1kF>U6&}HPdjIBE{sH6n|R--HGzA&KUhU~A^hXpg?1t`78%q&qo{D3K^sk?cG+qMNL8hqS>?5-P(>FRTtG~zk}G3OLP'
    '{YbcTb|grc0S1e`w}m~tP4*1*KvvD)s%GlFpk_Kl%MWz=sAG(ZOJ_MPLOLgN7+Ax=J2Rq+2f$=b{z+<kkV)53@ZA&NndGW2qKmdJ'
    'S$Cm;VY~NHbY4FQz<8%2DM4g9ZzwG@=SJ)2s_#V?vv&-=PHSm(8Hu*KsQqcFEw5qSM-8lM0%(v6vRbac>*m|SMV7^8XJ>YN2bU%('
    'Z^WQUAUsGE6TfIW&Eo~oLP%S8Z*m`ts?)|PF6?jD^ohyCe-XdpsmSWB<bqW6Hj+I$g30Db&<H5P)ZJ|c%*3&NL1v7%MvxpTS~h#F'
    'lKVIaDI{iAM;+}L?Aj1$hBv{K(xZwUY}=Y@>58PayM|-}4&8fsJT;siTBv;RH!otwz5{Vs%CA62e;a=fE~1dt3m_V#$J$*&m@%L3'
    '_}C=81bCehH8hu3QDj$S=>)jQC{er?f=SxU=}ML(x=yPz*4_~^j1Oic@PXhGuJr?UW)2fe+~?+z0K^-VzYZbE%^?daC-d{_$?8N_'
    'vqGknH61UXEYjeR-|i%f^IL2Tm%B=e0fS?#y0{r$FxApN>KN*uiBZnLE%XIRin)@eDaR=(8HPI31y;y^W;7J$F&)>OOrz_0wx<gF'
    '8XUzJgmH@6x@=&T;>tsV#>3TRg!J*E;O+%1JNpv+HdMh`6mY%oo;U4FKQ0yRJGZaY63{H!34Yr(-@9niS)IdZAUTR_NG7W?h)I3&'
    'J5bdU*b_(gO%WJ1KPqYnmz9;gj_Agjjgm@?Sh$oo{v1~XW+54SDY?V63j2`2M4&a!C+s8cJ`d#MrE*L7c5(YXXVzbe1b^k6>jyNC'
    'HqktEK->Vc0_VZ|f$MR7)Kue`Z8)prgur<Y%xcIAEh)9OX9H<fE;KBe*`#qaZ`{h+(u2PuLCYs~=}5o-#A+)t#_~KXnue(5h3ElW'
    'k$vE1E27hJ;HTzmZq46=PeB2C9X63IRuOs{16|Z<_2CA)dDTye^k%qq%>9<Z_^<Fr-Qc+!lWv74gY*Qw4U|wZ)ZYT0$LBJyc#GW<'
    '`HccbaENJINeYG%+_m91-1+D;BjOUkXcq{0AVi8q`6u6#Yo0Y=se$+uuZW{;<K+lDi`X<4w4l!Qz$WfWZRzI61oEnjxkhW2k2}#{'
    '+N`m?4SruiB-Ab{1wwk^;Byk^rCjxX8%PJN_<hW}i;i*x4As;#g;%%Jh9D@_Y-xr3DAF)7XK6VVRLxz=U#HkRQB6X1-$mm_|BsnU'
    'PX7bE{+eBk`p#;2*3E-MH0vIiTHQ~nVj)aUlb6b5x_2g4;ZFR%0Mzp#6iJGsWO{Uu>6*jOL+W+~mP`ThS?k6#>|8QH!mix4u*H66'
    'B4f#_Ja6qdl}>i-PPB$ip$&cvq{(S~P1zEJZ+Mp$PDkp5O>*+>!Ox$-y<hFCpb%wr`2%82`x?KALSpk_6Uh}TG!t6IaoZb_Sx}7#'
    '+zuoOUhB_*OiqW0eQMg~`HcUUWTR5ekpXR1`cn}(W5E+Ltpp=4WJlafIxjM$Xiz9ywz!f=cYyX^6)Q74<udAXHARiF;@@m!k;i0$'
    'gj#iL)DnjX%Nzb+?q0J|`w`Y}YL9^tb5=)fHEa%7J(qiIVOi=Mv{o(Ivg{qOZ%W1a=Uy`4ZJXi>KkNZpL3HblCz?02Zb;5p?34L7'
    'pXINHOwA5JTEJ=F;97PUt2eX;!S8>8bple;)$OQ;^>+yo61nC??!3y&j7R$?<sC#LGm&?aRqNS(pKP3xr{$S{v-0a{N7O#lBn^%e'
    's>d!F&ciK!ny+5=Tin;~eVf-7P|-S&l2+3^mTzrxzk^jHa_(@=G@BfnJdUZF_%enchK#?qLdaWVxa6#CG88=<Siqq+a-f%tGK*|t'
    '-<AYx2q+GbvmMSD9vp?*tEid|`@@%oxEswySVdLQ^I|d~jXP8T6k%E%glO+dq1CXxVsus{XFMDJy`CkagaXvmJ}@h#XkpEIID;@!'
    'ccFZ1{N>9ly($psgO<h8Ih?HmvzT~0E*#bGQaOXuA&k#eCk^&!kGfn;9=sD}Ac4CoFh}NU?7=Snq5~`PNwpNVftVSyR9A1_vY$br'
    '+iDzw2tn`3`iCMFKb#@?C&deTi}S6hud+dLlP1%-bV*Na5;#8BT}kO&`=`AzFvLBj46VHGB&@GA>TZ<-Cc{y4_hYPE)KW#s9~VoF'
    '4TA~6Rp@niVCP{GU5%)}!(2(lP_tBt@}buLwKetaVy1Zzx9raT5bg-rSpbE4z`lb`R?nT*bvvJS9J$P<z@D`y(=d*`*x<||T~Ct&'
    '`AmPpcPpPFA|V;ZcsK16NUEg%Cj2zQrsQVHteQ-<5y-*v>mSD)egN?L>XaiUY<nrJwJcW2q;kbQpxpjRPXxIB**u-U?C=7w?(@iA'
    't{IOE|5}iMNh7xi!b39m7T$8P*Nf`26fc38P{9*}$CB*@1}vtbtuf{PrIK-&`;6Mo@(<tE)V*f@lI<)%ti%_yO!<o}Co;Ku3GcRa'
    'A;VPcvd(B)_6s*xbR|d%0P@l=P#Aj*<0)|*_G1uDnGH*QSKPSX9EGYTpy7KO7(M6Vj(-<S-F7x=olvrq638e7n?FVvGA|u>QFAQ~'
    'X)&eEg-Wz<&P_}<O{i5@hm=vDms`R;HEc%1IWNi)&zr!zZfA>L_6Sk0MUYGZ0x~9%lJC4(vCW9-0JH9-mfRK3M(dt8i|3q=ZbS?7'
    'r_$KdD??39LW?*dTQ>gTn$ZSJ03cD=PolV$Ha<`!Ygq+e9r)TdThniC*Zvz!aN61v=Q5v&0OraO7^T-TGP}a1AStn$SY&fcfSC{&'
    'pQ<!ngg@BF1hTgssftTToX+H3f?l;~q<e*!Xf=5@)arHdYI*MusKq>NkT8QlCgVc5sbivxEh&hExNI@EsYOCCRGf%a>8|x}0#liR'
    'LTQ|#X!PD7i8^d9XE2%S;nsZ9ujqO!w5(`PFSs<h>E{i@yk$bu?pG1w&FvNNnt|}Zq{QF0V{5U6L>#E-zbiRV$w9^jK1k$;HIG8C'
    '%BU%ofy@*@YA%K(4DPS`MAyEe43Qw;Z!wa1n+wAVuhM{EL~Ky;{>ZX2p{S4`TK7x!3rpkT7ne``z0?>jOB68VuCj6W`v`As(Je?|'
    'Ja@F3Om*&RFN{RjKW98?yl<(|XSa~$+DH(=1rTO>+Rb#%o=wW8gUQ&GT(f#cdO0oF-`7%Fzd$P}|Hyq+NvF4y{JH2$F*(p<rzKKf'
    'Z_Rsc)%&I6KqO*Kt}T8SV-At~n&jeObFVW*XzI7|2w-Skzwp1Yt!Ya<1r{FIEU0>21lGP+zx*N<S%^#}Jh>kezY0bnsKu|mO9M;1'
    'W^Kmn4L-2@r0TDw<hFz`JwXlsbb00hhJZSq&u3oZx9w$3T|A%<J$9zAl$L^7$TtQ$uUn8FkiI#me?ZHv`1RPRERuK76(tNF7@AQZ'
    '3R@t94_^H_CTi%dqc9GwFDr)IG)tzn=3Mrq(G%h!{1dbGxO-oQt5rcW=@hYp>^OmGsrZrxF?RFpuK;|lWm{;%xT7_Rc&b&&%!I2S'
    'zJLoNxf&`}N|9B)jPk7kaI?qLd#XXUB``R&G)R#QNr(TVMlsg({B0M74Lb+$+<TZMN+y{kMy%>OslA}gLCz^3&4Uk64hJyo6^y}G'
    '26edpM4Q3hR9d8So~zY-T%kD8L@hDm2_Bv^x0gI3LE;@!{nlLIMy=*FjBI{Tbq}qaT85YU<Hxz^8a1Qv2a~&d2y|c1<C}tHf)Gaf'
    'Y7CzYk@B$XCQ9eyh-JT1L3w}@jlf<C&fg7ADZBy4Uu(G{dsLCubGufZlnN5_M~y=Rv#CH2Zf;Rg$nT&jZI#vCa#&GK$%yzga$ZR|'
    'NQe{rM1Ec}JK>rw6u`UkG>ExX)IFvP`JN1ZT%IHhKt)wdEL3bG7VM<3Na{0pg(DOW@e4(`$*d^uvKKM`%ZAcjLr6o+BNw&Sd)x<w'
    'A+hEjB|iurU;r20kY8XpWLcfywK=3oBxCSYhTpNVz7WLXiNVG0Vhq1p#dA$5+cZz4N+S_$u{6lzln;I9)wV;O^~2M#Twi*wiTj_9'
    'n;7Lc6B$2&l8XS>X|CAUd9Z@GK8f}4-dGP8$L~#`f+pyu+OJEDiA5NkYB)}IQ~)Cca?GE*@R-4O#~}bd@sv9Q$$O!QQ(T#hOc5+D'
    'l+?J?5hq@?u@e6bSfZ5@Tz|NV&Zd9gyk;5``};>H5y8sCiL3aXOkzId^RyH$@_Q{6m)7MOy0ec=HgY=vUf=X8tYONTM1AbZKRsMV'
    'j<-zYue>1*ZeF2P<bFO58_Enn&58$Hdg9NgI~K4AiI*0xp)(w4Um$KfU$rV)Bb^)ixuFPOmiQeS{hx6M=HL9=@)=uBJt+@f4&9-*'
    'C`_HyB%As^7mEfEDH%EhvlyBNrjNbnqyKYtyj82XwZ-EeISjghmPvO+uwbdJY2e#x?S&3|kqb+JQn$Jlq8_bmF7~#=DNig7KC$wa'
    'c;MFKAQ!?DJmx@vzya~K+_rsl7K{8{Mw%ZIpg3W<3}$awJ4qZ6n+6^nm40Rqmkk~zj!|_ChBt%C*&TWnI=UFoCPPw5CE|eQ7s$U0'
    'y6`fS6VJq1hprC~SzFi7|K21xWegWdURFWdW0;e0h;t0ZbWVa}UgF(gp}70%mrb&B$D8M$c(jND8zWf8ddexh?5d#3<BlWwS|M7N'
    'l|-R`1Oe6Qqcd@V$r!Wn5ptqW<szy<xrtHWw?wT&Yzb&cz<j^U3Zba;HH(+uIQowSC{Fp=gv?gL*9x!FHVHc-C2nhuElHceb9HA`'
    'u=%fcEfuoZJRE2oI!>A}ce$qNK@--%Q-Qtdh$5=49ASI;jRCO*A9yjHu<nB7ht7s8wQ)a;>!xGV>&$zt0;MbCY&OUxnljzLwmJ&x'
    '5f&$)_Qq`EL>Y(LPT3(<$6NOe!B43#N=$zb#wf_X`f6mCuuD&ln^-PZ7_mTFVkRb6_E0-b%qWj~-uC-|h5bR-TD%lezJDjFES(&W'
    '4R1aVe)s29UZ1%Tr%%##i9BA0Y=J!|d!{fsuad!T&QK!OEM0yZLAe-buNmS+l$w>u`i2oX0Ne>qTYlENw3rNUI|%xmV}harPhCPb'
    '?-OE3N6ypK@+Lde=?ky2&Dj5mtpj$_8^$rbf?<|#cSM`Xqi-UPsDu44KdFL+ORM?1u#fWUFsQ`2Snci2<Ku?MYIR~LGfrA>HkZ!1'
    '+cDna+8m&|<NZsbrUMRS<S#yfg>0Gb<K)}#oe=dszOpx4cWy16izQR1p||OKdQgr>P-)$c4|0*l<Ve46BjoDGPnu+;y@@qvj99lR'
    'WPWa#{kXxt`NaBg5Cw(^@BLRW!~p}w>XCEyiy|P-v6OG+W;(9(gxpTy>Xx|J4N{<Ztow2O?r}Et(r5(BPPS-^Eh=v_03Kv@y4@-I'
    'EpEpQJEsB(b?ODh5fP9#iHSz^7f_##2ucDPV`Xes@#r7i=(l>S{-erHkhM7&<4TH~tkMd&gR?xkoc^~rwurjjvlqTp85@0VTo0;C'
    'S*OKHqsV!;u{Wn*LfYsdPI!iQEFCrN`&0ud=Zp{P{+`8Y)!Ih#i8)GZBXAqjV3pH^Q)9K86i9RSAsXuyZ{il5r3Y9n^^HWGhVO0F'
    'yw$M%pWk<;MH_o4LOx5sJdMWa=m}|D)lwI|f(kaU6B(=kx(L}N65MYQNA---eNZVl1w~y<cW%TN!m!U2*vu2xE-S310ST7qgASUe'
    'mrnT_O9N$I%T<`cN+ZlQRfhL>$+8=2sG$!9+xUdK_qh7c6_pThh`(Yz$V_NgAA^)VB$Xa5YIp;lG*W&zfz79=zzd*5lWdP<R*m9k'
    'XjD*VXS-6RLs2m~F5Gm`SieNPlW7gZMxH`XZay|S`}i8G8dSSc;ee(?$Bga$lr5bVM<crFw^-5^(|RZ<6Exr8Upl>nZ?<PUz)exg'
    'P%sH7_M^P5x0yez3=SCv2YyR?sL-r;%xB2kTMYab_jKP|dZ=D5l`P~J$|h33*>KwNCk*nZpw>zK#Z>?ptnhRU6GWfvASD#g9PyDv'
    '+rcH9*CEg~=<u>6cAuUmF3p$Vpb}6?xQ!dlhG&`|t2?HPeDS*PffVVqy($1=XN-=xtjZ>f>bQ>t4^!?nJzcVO0lw~a3t~<bz^G91'
    'TF%XT0qs3NywIxa;)iJnmMX9n9EHpGuXO4?+G;5Sn5ybC!|vu{<vj_20r(8BLmxGjH*Rwo#t#BlgJe!{T^Z>oL;Oayd{b|0XE|-W'
    '1;lOWMv-hn7_{m9%rv}<>dg_x+QAo6!44+4jR7)X45YwqXpCqAx>=#M9sz(Jqe%S)ffBi8n+5y`_VX%R$Iv}aH*iZ!vS24#qgQVF'
    '<X^6+F-Nj~qRW$cZ_+j{1C=7tm`^`fP56VNPZuTVDT~al+r%M7^GDeWU~O!s=Xl=V5MK8qSU|^MDfzMSK~cFYU>UA3vpaYP5r!6-'
    'UKkdYri<<2KaWtP4!orl%ZXXcNbNppr>MPsX)Y_KBZB(;vA{8|Air&rZD||I4N7S#j}2vSklaAIU#fcpCdzg+RJ7({tcqba$l{-}'
    '>o7qBYXC}2!hB~Sh_53Y_ST(WJ8GR*<~k?}U$^<dI@P+8>@2P2yhWKvC9L=ag*KWt=^dkteMAwFVpJy-?k0={D6+z+JDZr$BbepR'
    'DXs6Df}o{0mxnFXupctdE<4<OFQ|_S@a~r@Gp{FbsXoVpm8EcbjlJbG3m$#fWG1;WBjofVRq+`glWV>#=l&45H{zqxGa2^h?|ziF'
    'bY1@_cK-g6{)9MmFPJEC&N(c?H)*Y^G6U(8MvI{pA=(h}e#{??c!Lot?Y8~amk^KlEVD>1lOw|TMe6J=6|eWAWJQ4*5ye}Hc$<VU'
    'A40kRh@v##-QhyikGH{1SE3CVtZgC3XHq|Eb*U;oB0(>IzSR7If`Qf*l9e<s&1GF3npKXPbbf(={wdhMfZ^ci{`fxDnT`@cgW^)#'
    'cqp@8HALKNc($<G1<k^nB>aaT6{8^jC4^lsS(+ujL8@uI=;-Qfse^GOvJr(K0At3gXbQ!iL96ZR>1)usf;+QwhucnLwd8!#Y!fhm'
    '$qErR@r=Oq`RjU}P<di)pmKNu1WKE^;v^FPOFcTPYv%d5k+C28$$y@D84vPnjIL-@g?y*D-w&Nv{Gcl*6hr|5=vQNz6N4v~X%gmh'
    'skgDX47&rmLx^JLR=|giBS@&X7#^DSUV`Qk&gA~AFJMAISK893C790}t+cvRW$8cNp+%g=1PkJHxOIOQK`}<v--C}<=@0Wl;Yt)N'
    '!fEp}UfVg0hDs`(-as)kh@r0o<nXXHNujsKQ$v6E?-5-93ZEJf4Nsc6G(-D|$?e3`tlMnFYZpWB$0=i3yE*dWLZc|-|Ev;ZSZ^mz'
    'bsrycv4e$2frcDWItKbEL`s02{C*|m?dKs}77uxs!?1umsn5*pk0Z}61SGlCTUP%wKhq`5WkPp;&Ez0zD_md}s<Vom-QnMGCGw7s'
    'phYNhok(UWf7tAP6Xa^bw~NWTo6A+KBvUnYc*Aa^LTMLodAK<Qva65@vH#jy>#yAYxi;ddC*%l7NRAAf(TFPN8G*~9vDY6o1LVJi'
    '<bp(giu8w3N9Nv4i5vxI5=@*~b`pfh%Ey6B>Ywpy(##8UV-fb9b7{Ymp8(gkGBzp1&uG1K>2hBzx5*`izudETI5_^PM1~V|9+RtE'
    '2nA=F(BY(_WHZ%Z%Vx=Q!kM}iIk&wDGCq>tQ$24%-*><t6#Eku-7p)9Wz0ZAI$)h<rmK*SPnBHJ6^lwCSr1Dk=W;--VupV>8wNNe'
    '8=@7j<%(1bX0{Ez?=Ov0TYnCpv5pOhh+ar}tokE^x`v3c-9c@b{B;r0MG<$#UjD+wiBYBcrz_P5Rv8(G6y1Yp#F!!gaJ{lp@?&D1'
    'ZePlBvZKqaSJ8-&tFg9R-l{#Wfex9Dmzqk?p_vTa!?3lhC;lp^x;5iL_01!!$UoOXj-(YBzM9&;OoI6p)TQDDT!%NBBG(z(J@-3P'
    '3i2H7s|F|Y(WScb(@KrWp1Bv{r!D@lET#P(NDOKau!pS=12FE!B{Vkb>?v3Cr&bYH^T&bS%>Wz6cu12R2kP@x7;_3II`~Z+=VPh6'
    'PvB81GBAOkZ)XnTiuu}jmij%6u2`QV>hAXC-5vC%#cq{n=q|q{{(L$?C3e4JUZ*J2Bnm$WZ#F)ob;^0OE1toRv<OVL;HC#d&>Y%s'
    'QX#ev%wT%&V+7%?j*$-DUBRXJZk?>(0WU?x4)dU#n1Q#?RoiDekq`4ssU~2J+B}_f;s(IgnLy(i%nL(yWh^P<!k+&QmeHCsh?J#y'
    '^tLd`tjY8J7QqB0g8><iV=V7dI|Bc<dVLw&*z70>gC*Ey&W}ru&f77gjm`U+*am~7pFAlBxftkw{&`KDMLc)YgMXDjJ9k5SoLOs@'
    'mJQY!HEK<w!`q_2*TXh^-)5Zq?=FS#+Z<TUjZvT5WH%fLO!^fs<{R2<!djt3joSk87Ar1;68i+E*EmASny19xgfX5S0!Z(7_+LlE'
    'pL^xELCz9;U~C=UvyoZ1kf9!&F6A93{MX~X8Rz}six1-_kt(fNIQkRxg?#I3ts5yJrvImSAe6xO7GhJjTqw-hS=m<tkH2K$cGI0`'
    'n(%0hEHDL}m`Ec67MnvoBO=Bqi(EpSHNY6mXMF9a!YONMNw{BcF}?=K?PENuyh3CIdrsl%dDv8^%!`F0>@kghkc|aFiEsSguj&<L'
    'E{^-Mj?w-rLNwPvTTnPiePpaH$SrvLLc}Ml>g`#+FMx4Ft7b&Qk+EDfh3B|LTSNab?Q|TvW`4UU5%+x(hw~rLRAsa378hz{{uNw@'
    ')w@*>;ax`dHEau@F!$)J;EP9TYx%8ADCKS`MB(iw4=85u>vz%t4e~9Y0cw>dNXX-obBnfB^DKEM8!1;N*({3o(c~6{77}L$1bO_y'
    'fAcgoXDlW{O~@t1h!jS{Z)g|%?Gl@6Ox(|_a4S;c{02;;cP4YgYs|IQed4l_G#xYGv#-i1j1lX>l^epmpK`~oBV`Cnc^c1fh_l>L'
    'r+#5QSWSK}ua;;E7gKg;@ZV;yk0;UUUl6{@VX3t%{ca3%Q*f$$0v~1EV!YDY<R=j<9FT?bWKA*tY;@acaQTK14p`jEjwll=8dB>2'
    '$?qAhM1F?39aUsBgbb;{><2}OD%i;_uOIep+c|W{OQMH$)h(8J^(5`b3KN+(vFy?`r7LPQedhZ?|6>3-TIhm$RvZSI%7M#Gua#1S'
    '4#An&HsOoebyaC>i}LpTUSYAp2M#*a$5L1tZLRUjo@rRFpC$g_>#0EYTK|qQwXg!tAgcdzJ;s32WGQoI^s#&Mu1zkPGu{KQ04P%V'
    'nq#{|K8uRwNa_tY{mi{2<kVW}0+n~vSxXX?wJ2WSgcKr}_c}++dT;|T=6$=irMTZ7N6k*f;Z{k>8hB!x|Bf(|p>av>(<`=L5E3IQ'
    '66S8^(wP7s`|UiSX&;Lz=0M*GGLQzkg4UBdMIOKUSVp~0clhGN*l8Vll+ifW(IU~lzR><VyRi{hv}~3yb1mNnXdUNu0pPqMj;(*`'
    'TG?ZJ26`(ytNRBQ<fc;L6RGfGHMlMyBAFvKcTzU8%hedL^Kr~wyt<}%!b9eE-{xQ1rYsz9VRfhyHav6G(m=p-hcUw$;{mxY2tYu#'
    'IS1a|Kj)w)b3H(0<m$uXlt&ELZ|vdt=1>Z$xc)G?xYz*EOY+-rU!G{FqYb_Dq~=Fub-o3ag`|jh+&kuU>gLU-nFTybAqcs5y{^Ab'
    'J%yRsq5`Unn~cz+`Rpp|;O2(hOLQ3ACj<Wki%MYbz#b^tI0yVir-DWOY2QGUYKFB#U{(eJ!MCA<M6DKy#i{<KNW?0pz)&kCP)NJj'
    '$81n*8!?*7gJ&4HrgW)GPoghk>N6K2wOUvr_+Hlef+Yy)K{Z-vxei3Y$t-$Fq5v5Iw1H`!1=qZ29ci^Gn!eV{K?!m-yPc$iB{xoN'
    'kZY#Udv9Fpw%4XRAJl#xeQnE04*BX!@UNXCIJhd^;(?^~3UeU|rs>$O$vzGTTO=exCeJGN?F^?C1ltBJC5g+;70WeTvvN2Z@FLpW'
    '69w<E{zXQZk(2=xCc!&fuWWC>NmYr7sr-~^Oit!vWF-rj@8LFLK9B^{UxjBRsAFi+Y08y-5={24MU!kzem6T?qvl*xy=`VvL@_=?'
    '$rsQQb~32y-;f5;qmqv}64vIs2nFgDUeuF+h}V%L)1o+vAc>dBN5eQXMyVb7&1l)a0B8rDq5e6Dx)hN#hW0XVQ9I-7Lf)eSncESg'
    'WP5YS28TXtO%$LF_b)!~g*3M`<rHe}&LKf(rCr(c`M^$6=9Fn|S^3^0bQN^jK8TMUZ>(pKSj7#)RZ?OxF8uQx8UE-#=wt35C}ppl'
    'cnj!Pc5=@+!50%=_AHMnZF!fD46YY2E!j_u8Wy=-G&(Y9N`%SsY$qK%;b_N%&U8GNJY6c+L%@@y^&R|yPXuVy(3Rjf2xh3=(|=~2'
    'iv@%yxuY5{n>98iie7=0@U1T^w(CEz_oC0lKMN7OQaX)t(k|e1!9<#OsZ&VF48dx90B0^Tex^$cpOl_|P{iCybMQR4^eCeM!TKx8'
    'K<_yHv6GiYnf};1Z6S_I<QmL!gLY@IwU1Nexp&06dyWzc-R*yLr}#)CM2f<b-7&)UHVYTov#3gYFySyS`aba=u`In&mmL&zDhJ<)'
    'Xyd5Lfe<oDuUw4GQB;G;JTawwZ13XKUWC+PMMInnos^uZ18hL2$1Enae+WX3TLr{~Dgl;n&P5t1Xvgei=pl=#Y@dAUb_9Jwi9GIe'
    ';MkE1Q&ttewenmR%bW7t4_uP1Qh@tdk|?_(SQXQgQ&zC1x%4bejNO`|6pNJQ2cVNcFQ0@Dox&)~YwXs2rHQLE+Q#xBtEocaXj07*'
    'q+(wjz%Pi4Ni3&}=q~P!oopkTejTR^ZwLh)GU)J~!xVlYs?M*Vjs{;zxh6#&c4C!;`bO9@xw%|#--LNqwy;HxMpnIru$4H4kX+gg'
    'jEGQ#|BT4;bT^_K6^BDHk@p-`yBs=W(dT_qI2x9$!t5ASVo=ksUZl#iM6g#Mk`|^tiUgzN2+B%s=gUqx$*aVhb_Vj6A6VHkybZ4n'
    '#6#QJx?hoVoYi={$m~HwYc|mD4Hy;)_GF(^PZR3B9$>pNAbeFor$g|e9~q+)Qd?gRdV#VbnSFQxdla#yK9Gb>#yb9p7H2kw<&^_?'
    'PZlk>)}EFnJ1JZo+VerzgnDN5txm|zKWyXI<?73wJZPVmo8dxYbF-DsD}&x_<TxWtNzn+q%4-K|I{^+bW}0j*)Wxngd|Z!MBc_#3'
    '7}+F*u)Xe;Q|fic&y89kRG>s>8iN+M#n-L*T#!xzqeX$aE}KZED#`se@o5}HpxjUo&Wm3*5JxAr&&~|oy_NKM!f088eaM#Jx_~eV'
    ')=2X89<KDQEg6hQr1KhM&=U9X3~11%UY?2f;6f)9iQXqzL-aO3cok)OgO(u1t^U4swhP~`Veo2|K=l917mS7ez<*;;_K+tawT`uN'
    '%by}W=2z#m&C?VOr6cBi83)d+ihhZwv&e!~|4rB*TBmy0AoWrm0Z4DQz(b0)EzevHdmqnq2L;XnM2wla8Il~ouw1V?C`=*Ms(N1G'
    'FNE@EiR^=SOyQKH(@xiUGBZbz-fip~nSGQDU-~mCvB+7JZhm>XR1?!w(WbOT0ki$fZ`zD*F>Ma}LGhPh@GCh=-yhx*K<x4?WUoza'
    'sbg$_icI*akqfu-&n`$vvDpI0cY}Itt~)9r{xTL#1Sv@<?QU?4i9;<+LHQe!61_0Y?H-LF`(d(dXKIZexUd2xJlGQ~cnI-jZh4fE'
    'Wz+ve)bWN>GeAG01lmu;!_V|UY~9FZ<-wGXnKr{ZoGq{|*Lb)4N^>n3&8K8U?IkR-8Eg^;xu}bfKJ~kKJT_EKscT{B|6<J?gpo8I'
    'Nn?T#p{^l}(a5w86UMZn;10up$UXxZS^l6hnA(^f6OdfS(nZ07nzSxwR6wAm!^S>;^{Fpa0T82Lje1Q;=jsk9$DH7JlAt%YNh7+#'
    'YQY#@g$U=K5*aYl@>P5!DmRT)d~!0v-4#;JP+H=Mq*4kYhmELAdL<~KOMG-hIhZ=8Zj7p)0uX&b>uCuUR3_OyW{EF?P&YKezuyIW'
    '6U+uY)47Ns&zzuaQ$Y?a^^}`6XF@?tt6#VIM1k^TWsZxG=oaQ*<~;s}CCGc2$(zDij~XP1ZFZ^_-(M9jHyFv#{SJmhc1$yW1+>v}'
    'cz;EWK0$diV<fn3^OqN~j<8OXCC#z_`iIg&AuwvwDzltZL+)rUfVQEgegy5e{D>OcQtw7EFMlOSrJKG;vlD#8Ha1VRf&<S#BJ+#7'
    '@7SPxwHQ8x)WMA{nUiWg%d@zGm2Crz(wc8}I}LrpPz6Ub;Ly<snhyKN74_aSq{PYvZMDa<(8-}jyzIRkuPLkT$D9=T>{x;ad!eDm'
    'wts1jQ<%d^<TEZCYOAT(c9H%C&ln{7g+W5t3!>D(@0QYs@t76A>$K;)o9yd97vF@(E9%;nBrM1{y)<NLo4|FY1+>u&S)co<@)^E8'
    '5Y|Oub@})JLK0;jeDFRP=L6Rs1k^a4OVDfrCYAwilk^rHwmHOgM!uiIpqkjruwEjh9EM6s5e{EvMTrQ!d~^9F7AAH2+m{K`z>Y}T'
    ';l5~f-3o+MbI<Trey}6X@q4mzs$uVzLUJ7IYdSd!Swb{~5~d&Q&~|WUXAI3RzZaJ5a0X40oS0|4MmKr8(rMGQwqB^){!Nz~LP`tB'
    'ZS7DK9mx%yD$%xCEE3O-2oXL;G8+icJ9A&$66V9CJhdA5%my5SCuBlj@5yHRY^e^ig4KY9eSbkl;VC^3bm~;9i-E@{fc!DZqednL'
    '^Jj6MMa~rj55Fy8bGg3M$1+3~t=lrR*F`g!8RQ+&2s#aVzD;0Wq;Gf~Cnl^-b(p@atV)p<{vvedcI#7Ac!BN=#}9A@TT;#2@k81J'
    '@#`pBs!u7M4<^Ej>NJn4Y&f;by6zCO^4D@>zeRDRltBOZ90Ft1*mXv6eo1s2M^u}$v6hWXh-PC^8Xh=Fqv%LJB_vyWQx4ek`XGMk'
    'Smx-eZTkg9kPn@Rj=e0T@;%$GY?3ZOC1L)2NXn_Zl9;*mf?0QoJzcFUhheax;E0HPE5E|d$(!zg)hYbrK?%Pk`<bQ--{P6+Z8jAf'
    'l0)b~rn9~2F*LC4PlJQNT$TsNHTec0@64mWxV@j?6p38#*Gm8bMSy~!agh9h@v<Zxbd!OE2t<LpVIo%J!E~c#TigalO&ffT<+M)f'
    '++gj$VTVIh2aA_JY@Wi;b6!a52t{bL6r1@8<lE=J*d{mUt*a3Z&z5_v)02R#%rv&SE=1$b`I<}9*-|xClnXkA9PIQKzO`a!K=*yY'
    'gNT8=Td1WY%Wc=C6qL8n(l{Av<oRTZg)oW?%-Hd!ONUj1gOB#WW6gg82S?j+?}US!v}p1mS~(iQ-_Nki^FfwkB-P77w$f-~dpzUF'
    'qdL5OC?29ze~7A^9}foi-<VU$b6!DQiY)qwMbkes!7GoRcrggS!7c1ZgAb7}gFCE67(oqW7h!u!mrtl##_%4sGf+wXhCw#kCLzSM'
    'H3K%i8nFCWXhY%?)gA}I-}aTp`><`cX3fLz8FL?)(HlV@thIrmwc<o(I26pI-0k4^KG00p0Wbq^o@E7wYAhyd)l0=1nOvq!0>tS*'
    'aZI8WfUbv=tQzn@w2-zcK)|K5FdS1GA&>pn4i|ysF7-)vV-V6Qu-}~Vd0=Yv4!yTx$yxAoGp9E;ojZcRO^mzi!<lHiUZ^f`6OUWw'
    'q_I5~r!_9Xy)nW0QJn+V29nLU;f-`UM#JRZd2DOqZy^h<Y1C)y`?Y0$q2Bq!2(OBq@oZ%O=qgJTG6cS|IEH#j+!qKy31~ia<NHTc'
    '8G0`*K1~`jy9x#p(u}OUp4de2;5=$^`?u~PzW6u_Vlly9PcA{svGfwOMO=a<G)Fc|4YG)6hl2XehBt|};u|GQu7mCEk&uu`bT42l'
    'EUAW)|6S$Uo=YjI>cx6}meAzW?J@`^V0jBnB7im15eoqR`;88`pGO^)<nNIu+FB1sBcLn`NjZcDyvUljf~s8zsaRZegy6qep~d(6'
    'YR<!+$gKKrtaxXfW&e?y%rI%Mez@ObdpQig0J(brZYpQ?HpG>2-lTsc+$gjU8S8>GIuEg-Nn{oAHuNHY@!vBf`kM<3*ER<u`KFX5'
    'Ee^fwyWO*2yn%?G`<3Ll$rn?D{1#EECe9km1d+6q$39wU_*P~*o0G2Fd1c^T{B54pdUX#T0%n6}g0uq?;{-6H7S(+O$xSXaP*(B)'
    '8>M%-^||>p%GDRJD+LT-L6@anXqg16?7559UH|IXk!JfE*eWR#W3N1h=;+7X*QRcA0a#iVkPp0=&PDF$!Q$#10|oRdQyI38s)PwU'
    '48p0f5ufgx-r6bL_a_xUD{Peor-CZ`-iT|g4m2lW-9-DZwXl5%rZ`XPBjNzoGnjLNhWYB&r}eh#Q6d8Xj@WaEeDY(+h4pJlnO*iF'
    'qdPQFNf$WZuKwetSQ3+jlYOHOt^d^aF+Wh$4J1*Xo3@JPe>f{X*e7iK-DHh^zM(QU)ijA!Dg+!XVJesS0>i^k4@T16r(5k>Wj#vh'
    'i?7;9Z&}vzsAvc_#w1Q>3Vj_k4+F^hFKO8C-Gxw&@q0Ncb%K=?aKdv~bXGZH?|R6^IZHP2dIo*rcT9FT4~A0boVqKNC$Llcjjo4O'
    '+W`%K+j^f_6gvB3_$kh&)|%v84w(b1(8et%p0M+o8@qTDX97%5jF;4Ap+m0sc@?Itq}0`saQP!QL81o&cyX<?yi{MMZqL$|&lcK7'
    'n75af2o@)GZwI%ijJJ0joubz==A3RttL_8R><>j{Y9X674=Le(14n?2ui)<jcC2C^M@;F|F|dIlZ|=2_el{38Bw6cp-{wAq0+EEZ'
    '8Nvx!>J|pcDdhR>^7vmv4Di6Jem_9^%F+?yznIXf5YRA*T$W*;X4WHbS~Do8Zn{eySGsm>9HIfvOdACPB@B!36I}ci(s8IX9=0#_'
    ')Ek8RgsRv#!M|Lqp+6W+<=EeD`kuD^@>XD^bJP4yFDRt!#=`^sZ`B}pV^?Sg0>*|^k593;n1!^)QZ%%>s3twTY?Np8q64*8qA?Wq'
    'q7-TZ0s4TO%d53NGoXAIhS`qXsbXvY3FSzB?B$1I#BFZj!`hNz1ch-@%dx|xtJcwCFnNx=P20!!1V-E|VFy$Sjtw;K?mejyKQ=WB'
    '^j`HDm+Y~rp`N;hSW^qdt1lI5F~+56pN4w~^o4CILAATrf}R^dg4na?|FpmhGt0gQD!_Sv-hTmYc*s+BFTYUYxBu#O1DF38borD*'
    'xLD;NgRDq<zG};|l`PU%D}1}Om-%eS$oHNm##bm<OI`zd!)Xshu?8L{-;MzUAG|<WnzYWOT>Cw%;C0)t80YHA;OA!mF<c1N%1F53'
    'R#g_+eXtZ(4IcS>DhH*e^S6-QPu@7S*7%c+gsgjur_igqa1qo_b?3B)&?qc9cnEcy*BGtD-a+XE_tvVbZh7WaJyfsJ!KEY4=lJ?-'
    'F)R?wV9uo3zh3)Gcn={X-Vn_GzckfQ;W`Wrf!8$gz6i}8?evrdy^+{#IW6+;Hxt07>jyfCDV@t|pripErY?8+bNxW>qbU#GFUD17'
    'oo!3CgV5;@0He~5caEgHj%7$yJGcCSDy$lqHE=^+h$Oqu)oLcM(!kA0Sr6idxIGhs2MKj3kU&CKyx*;B5pK#d=WW8yWYl{e@9b~S'
    'FA{vzWaZspM<aot?NMop+M9{f#cDhf0>0_Ye3jIN0%2yzw4gQeTnr0>;CGV$L209mOo;kFLd<8tS>vv(XX3p9^+~l_(D?@$r_U2s'
    'CN8pZ%RxCMP_|xw$xdhH-bt^D$6nxM%UE5R4mN0@O57217;p|q0=u615biAytKiJDcLAp;;}*fUuXeO3eTDVFe4H{$N#NaN$p(lL'
    'G;K^HfuGa|nfDcG*gHC|X&-sr*d~GNh^N%Ru7)<2pn=Kt-&=qAl1*KbXBrgr&zn)+_~mE^f)yAebk+<ovI50_WGy8PRzf|{|EyNH'
    'Uqi|4?;+2!<1{aQlw>btRk8)@#h*HsdLmOu0?ar{Jj?oNIIK}KrQ$SrF88OYKh@!A_+Bx*L8W4aw&Z;l*B0a%0oX^xCqrcL@FoP('
    'y>@6>oLjQ#B4NbfhFNNhNzlFc7Y8MRks#^+SQ>NU`2OW%o&b~<&d;K$<Xj8gc~f56LUFv$(~PO*7%bsKn`MN&lwEW>gb8WtO^Ae%'
    'aV`({3~P^m?q|?Tt>&OO{u?CHFI~e$)2Dq=9YO<cD&RPVi0;h~p1Q?>>g2<=0?_>mn_mGqfguS3Ww1RD+`kF6C9Ayz`|W0c-7!Tf'
    'a3$!RU4ev=U^r66Ujop{27CZ63sP0q+<CFDBSrtWeYa?UzwahoTjP#|PgJcUiEO8Or&LyH0#gtVMI=j$)tDufH3ik^_2})?s>_(U'
    'pSf}Ja(9@9_2yxCyBZ@bI`IOBR=Dir^fPHSO_{JX8jThkSDyxz`{38~M^$O^P>`BYS4E%K@wl!{;r^>%#P|>6cyy6}=K2Sm0PFFe'
    'm9L+|2cdipP(?f^sw+!ESQ)4XCkw%*bC=b;)o-r~!GoB`;W0`;tHJakds0TJeP4=gYp0#E8qmfBu(dc(IlNRCGl=}z)qRQLrjMCn'
    '(+(1w%m56XXnv9E=W~|<$q@WupBy^w7ZHg=Kq*$DbowA3mCF8tb?rN#>GDA((4x-C(JWeXixnT1Zn3?H_uTP2%9EJprJ5(m)W<bH'
    'pHg;$PH6{9sEkKYc0VclNU@=Z*xj&X6`I)JyX29xUr_#cP1O&u3mbCv#A!FPhta3Xryz9L74JMAZ3Fpaf*aevxZOZR8<_YcHgg#z'
    'JWX06oubjk##{7MRFKl0R9&j&uV-#+3|A^&bW9w(V5QSl8u2Idxj4X8H}G)ww{hUaiZ8|;J00S;Vs2=(v+^0@GJ#=G6cr%Zo!17O'
    'qLPknK@pxmX0e;@Fuz{Hlhl2!iPhENqY+w^){d=_1E+7M1!z=b<61}Wvdr&xk07uwDfe5OiLlhYSxKl;>??l>7gtz7w%41h^q}ze'
    'X{q@g^VKaaO^QYoR$<1#cXtOqRF54QpDisVS{$J=<DV(+o1=Pd(1N_BZsBNacL66f%x=6huj*N;?wpBF|IOKl<&_SJWRs9AP7!lm'
    ')xKD|7&R^)enhecPb8yXz5Q|`RX!k|N?8M+$m;)@TM4f4I?;F~L?01;Sedhf5GZp15Dx(Z$*3oU#wR-mHEbE&&KSG$*wx6a^$Ig?'
    'LFCFB+6l}Sc+?tU`a6&q99v9P44iF<g-*&drJI*;>(Z>ztL1aZzV6=u&Yrh@LL@)W3LA|EYl2sht&CQl?Txp@*5JJhjui&O&@sv+'
    '?nj+K0JC~Q%IXP|H{#yDjEdD_OTQy%PW`SW>1Qb(^-=#NzqEM#u)~0?+Ct1l*5V2FdPum!p1`@lAG+7#{~kX;zupd8`6SUmQJGIu'
    'TvGglaZc>E<vop;c@ae~1ep<PU_b1v0xRUTjNof3q9=A6k=gnx__b+ek)eA+3XaBNaR?s;&u<gOicmYAl&AFfn8CfxzIs306hs%)'
    '>EV>MOwqBC=PaE#4y~KGF0l6-xyZY2qyl|4H3$X$#L0?8hIKSo0XM+&H^NvAHCH|61jPert6L`bScpN-7mR<YsY!2iFEEZQ8oO%@'
    'AmgSNI3l?eY>&W2a&GDV*<QFXM#q(QocGKV{PV~=;lw1UX@aT;MKgG6GD$3?syFaIf`7TrNL{(9F%Wt`tQQo@?4*6L1r7^kYbO$f'
    'PmHCf1kE!Bls5@sL#Mn*(oF7SvXNBgL92j`f~qC(asnBbbTn{qMA}?%{+^{q@i5RCBW4==95|}!0rGTGZrSUGixOoMF(2&DqX#Pi'
    'xhlwHw#~&k=j^-25j5J`P{jYX)XSu<C$Qu=lVnB!)y0wf?^|^Fa<59kbhllQ#c0ZMX>>CPQyOH+6??L@58nb>k)i9YJy5wKI|#lS'
    'zxNZ<JqMmo2YPq#kA2|#!5zq4_}^go#?Q&3-Ir*5ILMxyBTQ8Xz8<wm0Z5m!W5ylM(Z%zGMQ^_5O<x$VWME2xZSKq|?BMc+K&w1u'
    '_VFYt$oWOdYau!%ifqN_Hkf9`9|Z~RjSjZJ1GA!D9Z)eDSy|Y58ddswujnPwil-7udW&7cJpR&2efTh8;)|esHIF&myHfr9{j<Fh'
    '8>avmxdOqTpF|p2nSkmtc|}0Nk46Uh52l+smE7chTSUvKcM4!O^?W_*y$SkGKrSiT9kjVrooHgS9o=dnZ7?YdMC}~Qo~%IrqUs9>'
    'r9BL2qF!+McN*WLKrM#o1YDjUc;+FPLhPFHpe|D`SLF{M(w4L7M5chrY=pY5AvOBxdG2qxwRqHjy5bu<o63dEyyXLyZIm?MKg4GW'
    '%<CMSN;9vJ*Py-86CH4@Y-ca;qvh?F5n3JF@yxwUv+wLUOTM%60vt~UIS^CeE6v<k?Gf9e=OM)OzT0-Vl!^kPOh$xv&n~i4a}rY{'
    'Wm<6;5VmmN^P49w+E*2VZclJIRH!=I#25&>@Hgh5xYrxBUmLfKA;6$F#5ivS<DNIk(KqW7#q_D@#w@NBELN94qfGdd;H`JbGol%Q'
    'JHS2CqIcqN%sb=a$<nQ0nARB$-39t=Rx?(MZvxL8k^tgi;hP>v0DX9`5L~m7(W6fPN!Xc@<sA3{94@nm!FV0}W~Bp)3Q2tf8goJ<'
    'VV>@-sj<3q#-9yH6Ai3xB6LY|SJ&PEj8D%f<imE*)xS)1>iT~g9t+0&tQKz3Kkc3ip({!+;n}cDRORSRP=^Wv6fg++%Sh4Im5J?@'
    '(wjA<4ww&Qvlyo^x;@~S4ac~JpGw>kCwZ$f%Tw8<#=IGB#3g-Cjn8J)eb}THlI?H-7z2KIM9k}Q7@_h~&)$r*bgYBUQLu)C?_o@s'
    '?@hLOg??iWcUG+Enkwaks4{FmS85-=(}FivKOTqt_ZUTOE}P~7*84uI-)rY4W}^=#`$eaaK8|G=pqf%gJ8Wd*u*vdo4hXn^f6Ww_'
    'l2oM&OO!(iChuI!fKH+br*Je>aO^t^O_FQwz^A5<jiR-1W?f=Yu-Knjh7%mvZghQMX5Y(#+Jgrj8d%U-CbTae#>lKXAv#SE9HRnB'
    'M^ckrWl8*Z-hO)tP4tA&jP%`81PDws$WXkaoUnj%Lw;CL{l?`=%5cz2gLXJsF{nZq4U7efkFc|doQ7NY<X+2)9l9J2C^j?Xq}Goi'
    '{gaB~<`Y(=Y%LSN#YFtd12ikPTUynJLZ~d!{k{CWOwBFLyqz{$5{nXP{>ZHYy85!{;dwayE|3p~cRb0xEtubuNsukY_b%P6|Nd#Q'
    '06IwEki9HP@B?(AzT4z&UDjs&o{12$+AfB$6bQtzhC<F-Dg2~L$W8<f4(CM6$IG^NL1H%fiFTPXRml9BHQh3e>Utt<HCnJ8P);})'
    '-62iJZDxHJkx<Jd1f_TpGP0y?r|C>BGb&PuBz3t5Fov*%$HxdZ!pu`+>%KM+B!s;`2GRB8Odd`+12JNKPT1wsnHJAB%>uD>QkHQ5'
    'm%wk;abUhChCRa|>?*Jih_y7nbAHXu`bYSwbudSWd_(prR7Of}AX)h<!RBEey_f8yb?U=z)pogKZD=J~nPeDblT+tNWawVMk^lez'
    '_lN0;xhM^(00FCl1dxCQVU;jKvBYQl0ssI200dcD'
)

class SM3:
    def __init__(self, data=b""):
        if isinstance(data, str):
            data = data.encode("utf-8")
        self._data = bytearray(data)

    def update(self, data):
        self._data.extend(data)

    def digest(self):
        # Chaquopy/FongMi 环境未必带 cryptography；保留纯 Python SM3 回退。
        if hashes is not None and hasattr(hashes, "SM3"):
            digest = hashes.Hash(hashes.SM3())
            digest.update(bytes(self._data))
            return digest.finalize()
        data = bytes(self._data)
        bit_len = len(data) * 8
        data += b"\x80"
        data += b"\x00" * ((56 - len(data) % 64) % 64)
        data += bit_len.to_bytes(8, "big")
        iv = [0x7380166F, 0x4914B2B9, 0x172442D7, 0xDA8A0600,
              0xA96F30BC, 0x163138AA, 0xE38DEE4D, 0xB0FB0E4E]
        def rol32(v, n):
            return ((v << n) | (v >> (32 - n))) & 0xFFFFFFFF
        for off in range(0, len(data), 64):
            block = data[off:off + 64]
            w = [int.from_bytes(block[i:i + 4], "big") for i in range(0, 64, 4)]
            for j in range(16, 68):
                x = w[j - 16] ^ w[j - 9] ^ rol32(w[j - 3], 15)
                w.append((x ^ rol32(x, 15) ^ rol32(x, 23) ^ rol32(w[j - 13], 7) ^ w[j - 6]) & 0xFFFFFFFF)
            w1 = [w[j] ^ w[j + 4] for j in range(64)]
            a, b, c, d, e, f, g, h = iv
            for j in range(64):
                tj = 0x79CC4519 if j < 16 else 0x7A879D8A
                ss1 = rol32((rol32(a, 12) + e + rol32(tj, j % 32)) & 0xFFFFFFFF, 7)
                ss2 = ss1 ^ rol32(a, 12)
                ff = a ^ b ^ c if j < 16 else (a & b) | (a & c) | (b & c)
                gg = e ^ f ^ g if j < 16 else (e & f) | ((~e) & g)
                tt1 = (ff + d + ss2 + w1[j]) & 0xFFFFFFFF
                tt2 = (gg + h + ss1 + w[j]) & 0xFFFFFFFF
                d, c, b, a = c, rol32(b, 9), a, tt1
                h, g, f, e = g, rol32(f, 19), e, (tt2 ^ rol32(tt2, 9) ^ rol32(tt2, 17)) & 0xFFFFFFFF
            iv = [(x ^ y) & 0xFFFFFFFF for x, y in zip(iv, (a, b, c, d, e, f, g, h))]
        return b"".join(x.to_bytes(4, "big") for x in iv)

xtime = lambda a: (((a << 1) ^ 0x1B) & 0xFF) if (a & 0x80) else (a << 1)

def rol(num, shift):
    shift %= 32
    # Perform the left rotation
    return ((num << shift) | (num >> (32 - shift))) & 0xFFFFFFFF

def rl8(x: int, k: int) -> int:
    n = 8
    s = k & (n - 1)
    return ((x << s) | (x >> (n - s))) & 0xff

def ror32(value, count):
    count %= 32
    low = value << (32 - count)
    value >>= count
    value |= low
    value &= 0xFFFFFFFF
    return value

def ror(value, count):
    count %= 64
    low = value << (64 - count)
    value >>= count
    value |= low
    value &= 0xFFFFFFFFFFFFFFFF
    return value

def get_key_hash(key, rand):
    to_hash = bytearray(68)
    to_hash[:32] = key
    to_hash[32:36] = rand.to_bytes(4, byteorder='little')
    to_hash[36:] = key

    d1 = (rand >> 16) & 0x000000ff
    d2 = (d1 << 11) | (rand >> 24)
    d2 ^= (d1 >> 5) ^ d1
    d2 = ~d2 & 0xffffffff

    return SM3(to_hash).digest(), d2.to_bytes(4, "little")

def split_blocks(message, block_size=16, require_padding=True):
    assert len(message) % block_size == 0 or not require_padding
    return [message[i:i + 16] for i in range(0, len(message), block_size)]

def add_round_key(s, k):
    for i in range(4):
        for j in range(4):
            s[i][j] ^= k[i][j]

def add_round_key_con(s, k, con):
    for i in range(4):
        for j in range(4):
            s[i][j] ^= k[i][con[j]]

def bytes2matrix(text):
    """ Converts a 16-byte array into a 4x4 matrix.  """
    return [list(text[i:i + 4]) for i in range(0, len(text), 4)]

def xor_bytes(a, b):
    """ Returns a new byte array with the elements xor'ed. """
    return bytearray(i ^ j for i, j in zip(a, b))

def matrix2bytes(matrix):
    """ Converts a 4x4 matrix into a 16-byte array.  """
    return bytearray(sum(matrix, []))

def mix_single_column(a, i):
    t = a[0][i] ^ a[1][i] ^ a[2][i] ^ a[3][i]
    u = a[0][i]
    a[0][i] ^= t ^ xtime(a[0][i] ^ a[1][i])
    a[1][i] ^= t ^ xtime(a[1][i] ^ a[2][i])
    a[2][i] ^= t ^ xtime(a[2][i] ^ a[3][i])
    a[3][i] ^= t ^ xtime(a[3][i] ^ u)

def mix_columns(s):
    for i in range(4):
        mix_single_column(s, i)

def inv_mix_columns(s):
    for i in range(0, 4):
        inv_mix_single_column(s, i)

def inv_mix_single_column(a, i):
    u = xtime(xtime(a[0][i] ^ a[2][i]))
    v = xtime(xtime(a[1][i] ^ a[3][i]))
    a[0][i] ^= u
    a[1][i] ^= v
    a[2][i] ^= u
    a[3][i] ^= v

    mix_single_column(a, i)

s_box = b''.join([
    b'\xFA\x7D\x08\x6B\x9C\x59\xB3\x4B\x04\x5F\x39\xD0\x38\x4A\x91\x99',
    b'\x00\x67\xA6\x20\x9F\xF5\x4D\x82\x73\x26\xEE\xDF\x18\x66\x83\x33',
    b'\x80\x03\x19\xFB\xD9\xFE\xAE\xAA\xA9\xB0\x52\xC6\x0B\xF3\x79\x25',
    b'\x4E\x78\xB4\x36\xAC\x5D\x1A\x27\x9E\x88\xDB\xBD\x3C\x63\xEC\x49',
    b'\x15\xC1\x30\x1F\xDC\xB8\x56\xD4\x6C\xCD\xCA\x09\x43\xC8\x35\xA3',
    b'\xEF\x1E\xF4\x96\xD2\xFC\x0E\x72\x7B\x94\x84\xD1\xEA\x45\x5A\x62',
    b'\x02\x3F\xD3\x12\x81\x34\x2B\xDD\x7E\xE6\x28\xF2\xA5\x46\x13\x01',
    b'\x3B\x21\xF6\x61\x37\x29\x2A\x0D\xED\x8C\xAF\xBF\x9D\x5C\xBB\x24',
    b'\x76\x0F\x75\xE4\x53\x89\xE1\x98\x8D\xB1\x9A\x65\x70\x4F\x54\x4C',
    b'\x58\xAB\x6E\x6F\x8B\x23\xC4\x07\x11\x0C\xBA\xCF\xA0\xA4\x8E\xD8',
    b'\x05\x3D\x14\xB2\xDA\x74\xC3\xD7\xE7\xBE\xD6\x7F\xDE\x48\x16\x3E',
    b'\x85\x90\xA1\x55\xB7\x77\x42\x22\xC9\x86\x50\x2E\x17\xF9\x64\x31',
    b'\x2C\x9B\xF1\x6D\x1C\x44\x68\xE3\xE9\xA8\x93\x97\xCB\x32\x57\xEB',
    b'\xE5\x71\x6A\xAD\xC0\xCC\xC7\xC5\xFD\x60\x1D\xA2\x2D\x47\xA7\xE2',
    b'\x51\x69\x5E\x7A\xCE\x0A\x41\xB6\x95\x8F\xF7\xB9\x87\xE0\x3A\x06',
    b'\x10\x8A\xB5\xF8\x5B\xD5\xF0\xBC\x92\xFF\x7C\x2F\xC2\xE8\x1B\x40',
    b'\xEC\x1B\xDA\xBD\xBA\x98\x91\x0C\xB2\x2B\x83\x41\x34\x67\xFB\x0A',
    b'\xD8\x76\xB5\x46\x05\x59\x61\x23\x75\x90\x87\x2A\xE3\x50\x15\x4C',
    b'\xAC\xB1\x79\xEB\xAE\xE5\x95\x47\x04\x68\xF0\x86\x3D\x51\x8B\x0F',
    b'\xCA\x8E\xE4\xB9\x4E\xF2\x12\x82\xBC\x0E\xD5\xF7\xEF\x28\x25\xCF',
    b'\x5B\x5D\xE9\x6A\x55\x02\xE1\x33\xBE\x93\xE7\xF5\xAD\x9D\x3E\x39',
    b'\x24\xA8\xE2\xFA\x17\x57\xD0\x7A\x0D\x08\x30\xD6\xB8\xA3\x8D\xFD',
    b'\x07\x9A\xC4\x1E\x6E\x22\x64\x97\xD2\x1D\xB0\xBF\x45\x66\x3F\x6C',
    b'\xDD\xDB\x27\x80\xA7\x11\xDC\xA6\xC5\x52\xF8\xC0\xB6\xC8\x5C\x00',
    b'\x73\x60\x7B\xA0\x19\x13\xAA\xC9\x35\x48\x4B\xD3\xA4\xCD\x9F\x99',
    b'\xF3\x10\x44\x40\x54\x7E\x29\xF4\x06\x1F\xA2\xAB\xA1\x2F\x3C\xF6',
    b'\xAF\x85\x62\x36\x21\x7F\x5E\xDF\x20\x1A\xB3\xB4\xE6\xFF\x72\x84',
    b'\x8F\x65\x26\x94\x5A\x77\xEA\x43\x78\xC7\x4A\xCC\x2C\x14\x6B\xC6',
    b'\xE8\x74\x53\xFC\xD4\x1C\xCE\x31\x70\x03\x18\x8C\x96\x38\x32\x89',
    b'\xF1\x3A\x5F\xD7\xF9\xA9\x69\xB7\x63\x37\x58\xC2\x3B\xC3\x71\xCB',
    b'\x9E\x92\x01\x8A\x0B\x4D\x88\x9B\xBB\x4F\x6D\x6F\xE0\xFE\xA5\x49',
    b'\xDE\x56\x16\x09\xED\x9C\xC1\x2D\xEE\x81\x7D\xD9\x7C\xD1\x2E\x42',
    b'\x5B\x4D\xC1\xA6\x5D\xEA\x44\xFD\x45\x4E\x1B\xA1\x3F\xD1\x89\xE1',
    b'\x7D\x2F\xAA\xDB\xAB\xAD\x59\xCB\xB1\xCE\x9A\x28\xC9\xE0\xF6\x70',
    b'\x39\x4A\xD7\xFF\x30\xF5\xDD\xBC\x57\x3B\x11\x8D\xB2\xEE\x00\xB6',
    b'\xE6\x1A\x5A\x7C\xF9\xDE\xC4\xCD\x2E\x80\xBB\xB9\x4C\xA5\x9F\x84',
    b'\x08\xC6\x6F\x42\x6C\xF0\x27\xE7\x8B\x3A\x9C\x51\xFB\x67\x21\x75',
    b'\x41\x31\xA7\xCA\x20\x43\x2A\xB7\xBF\xD9\x7A\xF2\xB5\xF8\x8C\x2C',
    b'\x23\x83\x4F\x8F\x60\xA0\x04\x13\x37\x14\xE3\x01\xC5\x63\x66\x5C',
    b'\x74\x81\xDF\x58\xBD\x68\x90\x3D\xD2\xB3\x34\xF4\x19\x93\x32\x29',
    b'\xD6\x49\xAE\x0D\x4B\xD8\x07\x9E\xAC\x1E\x2D\x0B\x40\xB8\x72\xBA',
    b'\x76\x10\x71\xA8\xE4\x56\x1D\x48\xFE\xE5\xC2\x47\x91\xDA\x87\x26',
    b'\x9D\x1F\x88\x6B\xC0\x98\xBE\x25\x09\x97\x33\xA3\x85\x16\x5E\x7F',
    b'\xDC\x6E\x54\xE9\xF7\xA9\xC8\xE8\xC3\x77\xD0\x82\x2B\xEC\x02\x62',
    b'\x8A\x92\x0E\x3E\xB0\x0F\x05\xF3\xF1\x96\x78\x38\x86\x36\x18\x3C',
    b'\x24\xCF\x0A\xB4\x53\xCC\x61\x65\xA4\xC7\x94\xD5\x15\x7E\x6D\xEF',
    b'\x79\x22\x35\x12\x6A\x8E\x52\x06\x55\x7B\x46\x64\x50\x95\xE2\x0C',
    b'\xED\xD3\x17\x03\xA2\x9B\x99\xEB\x1C\xFC\xAF\xD4\x73\x69\xFA\x5F',
    b'\xF7\x2C\x1E\xBF\xC8\xE1\xF3\x9F\x76\x80\x71\x48\xAA\x94\xAD\x64',
    b'\xFB\x89\xC6\x60\xC3\x32\xB3\x4D\xD2\xE0\x44\xDD\x5F\xA8\xB1\xC7',
    b'\x68\x23\x34\xC9\x6D\x12\x7F\xB7\xEB\x15\xBE\xA9\xD1\x78\x93\xA0',
    b'\x0C\x92\xA4\xD7\x47\xE3\x8A\xC2\x70\xAB\x26\x41\x9A\x79\xA7\xD8',
    b'\x14\x85\x8F\xC0\x6F\x56\xD0\x8C\x11\xB9\x2E\x3C\xE2\x9D\xCF\x0E',
    b'\xDE\x03\x5D\x46\x3E\xCD\x38\x43\x0F\x33\x5A\xD9\x1A\x65\x6C\x22',
    b'\x3B\xFC\x30\xA6\x88\xEA\x37\xA2\xB4\x8D\x8E\x51\x9C\xD6\x40\xEE',
    b'\xF9\xF8\x84\xF4\xAE\x97\xE9\xCA\x0A\x45\x67\x57\x04\x2F\x83\x5C',
    b'\xD5\xC5\xC4\x82\xB6\xA3\x91\x98\x1F\x4A\xAC\x96\x81\x6E\xCB\x1B',
    b'\x09\x08\xAF\x18\x95\x49\x7D\x54\xED\xFA\x16\x31\x3A\xDA\xB8\x66',
    b'\xF5\xA5\xF1\xFE\x10\x01\x06\x74\xCC\x63\xDF\x7C\x28\x25\xF6\xCE',
    b'\xB2\x4F\x8B\xE5\xBC\x87\x69\xBB\x86\x21\x07\x00\x36\xE7\x0B\x50',
    b'\x59\x9B\x1C\xE8\x62\x58\x19\x61\xF2\xBD\x27\x5E\xBA\x1D\xE6\x99',
    b'\x42\x3D\x0D\x2A\xB5\xDC\x5B\x29\xF0\x2D\x4C\x53\x7B\x6A\x73\x4E',
    b'\x3F\x75\xFF\x4B\xA1\x35\x17\x55\x72\x39\x20\xD3\xB0\xFD\xEF\x02',
    b'\xEC\x77\x7E\xE4\x2B\xDB\x90\xC1\x05\x9E\x7A\xD4\x52\x6B\x24\x13'])

inv_s_box = bytearray(1024)

class AES_V3():
    r_con = [[1, 0, 2, 3], [1, 3, 0, 2], [0, 1, 3, 2], [1, 0, 2, 3]]
    r_con2 = [[1, 0, 2, 3], [2, 0, 3, 1], [0, 1, 3, 2], [1, 0, 2, 3]]
    r_orders = [[0, 9, 14, 11, 4, 13, 2, 7, 8, 1, 6, 15, 12, 5, 10, 3],
                [0, 9, 14, 15, 4, 13, 2, 7, 8, 1, 6, 3, 12, 5, 10, 11],
                [0, 9, 14, 7, 4, 13, 2, 11, 8, 1, 6, 3, 12, 5, 10, 15],
                [0, 9, 14, 11, 4, 13, 2, 7, 8, 1, 6, 15, 12, 5, 10, 3]]

    def __init__(self, aes_key, khronos):
        self.word_size = khronos & 3  # khronos - (khronos & -4)
        self.aes_key = aes_key

        self.s_box = s_box[self.word_size << 8:]
        self.inv_s_box = inv_s_box[self.word_size << 8:]

        self.master_key = self._expand_key()
        self._key_matrices = bytes2matrix(self.master_key)
        self.con = self.r_con[self.word_size]
        self.con2 = self.r_con2[self.word_size]

        self.order = self.r_orders[self.word_size]

    def _expand_key(self):
        init_values = [0xca025ddc, 0x823dc546, 0xc9420583, 0xc298225f]
        init_value = init_values[self.word_size]
        mk = bytearray(init_value.to_bytes(4, "little"))
        mk = mk * 4

        mk = xor_bytes(mk, self.aes_key)
        mk += bytearray(32)

        rounds = 8

        for i in range(4, 12):
            idx = 4 * (i - 1)
            k0, k1, k2, k3 = mk[idx], mk[idx + 1], mk[idx + 2], mk[idx + 3]

            if i & 3 == 0:
                k00 = (init_value >> (rounds & 24)) ^ self.s_box[k1]
                k1 = self.s_box[k2]
                k2 = self.s_box[k3]
                k3 = self.s_box[k0]
                k0 = k00 & 0xff
            rounds += 2

            mk[idx + 4] = k0 ^ mk[idx - 12]
            mk[idx + 5] = k1 ^ mk[idx - 11]
            mk[idx + 6] = k2 ^ mk[idx - 10]
            mk[idx + 7] = k3 ^ mk[idx - 9]
        return mk

    @staticmethod
    def sum_data(data):
        key = bytearray(32)
        for i in range(31):
            idx = i * 8
            n0 = (data[idx] >> 4) & 2
            n1 = n0 | data[idx + 1] & 64
            n2 = n1 | (data[idx + 2] >> 2) & 1
            n3 = n2 | (data[idx + 3] << 3) & -128
            n4 = n3 | (data[idx + 4] >> 1) & 4
            n5 = n4 | (data[idx + 5] << 3) & 16
            n6 = n5 | (data[idx + 6] << 5) & 32
            n7 = n6 | (data[idx + 7] >> 4) & 8
            key[i] = (n7 & 0xff)

        key[31] = 1
        return key

    @staticmethod
    def mix_columns(data, key):
        data = bytearray(data)

        for i in range(31):
            kk = key[i]
            idx = i * 8
            # print(k, data[idx + 1], (data[idx + 1] & -65) | (k & 64))
            data[idx + 0] = (data[idx + 0] & -33) | ((kk << 4) & 0xff & 32)
            data[idx + 1] = (data[idx + 1] & -65) | (kk & 64)
            data[idx + 2] = (data[idx + 2] & -5) | ((kk * 4) & 4)
            data[idx + 3] = (data[idx + 3] & -17) | ((kk >> 3) & 16)
            data[idx + 4] = (data[idx + 4] & -9) | ((kk + kk) & 8)
            data[idx + 5] = (data[idx + 5] & -3) | ((kk >> 3) & 2)
            data[idx + 6] = (data[idx + 6] & -2) | ((kk >> 5) & 1)
            data[idx + 7] = (data[idx + 7] & 127) | ((kk << 4) & 0xff & -128)

        return data

    def encrypt(self, data, iv):
        plaintext = self.sum_data(data)
        blocks = []
        previous = iv
        for plaintext_block in split_blocks(plaintext):
            x = xor_bytes(plaintext_block, previous)
            block = self.encrypt_block(x)
            blocks.append(block)
            previous = block

        key = b''.join(blocks)
        # key = bytes.fromhex('a22c23b05bb4a831d31bbdbd1327c5f84991bca3e7d8df24e52f58b7ac61f2e0')
        # print("sign_key", key.hex())
        data = self.mix_columns(data, key)
        return key[-1:] + data

    def encrypt_block(self, plaintext):
        # print("b000", plaintext.hex())
        plain_state = bytes2matrix(plaintext)

        add_round_key_con(plain_state, self._key_matrices[0:4], self.con2)
        # print("b001", matrix2bytes(plain_state).hex())

        for i in range(1, 3):
            self.sub_bytes(plain_state)
            # print("b003", matrix2bytes(plain_state).hex())
            self.shift_rows(plain_state)
            # print("b004", matrix2bytes(plain_state).hex())
            if i == 1:
                self.shift_rows_con(plain_state, self.con2)
                mix_columns(plain_state)

            add_round_key_con(plain_state, self._key_matrices[i * 4:], self.con2)

        add_round_key(plain_state, self._key_matrices[4:])

        return matrix2bytes(plain_state)

    def decrypt(self, ciphertext, iv, data):
        assert len(iv) == 16

        blocks = []
        previous = iv

        for ciphertext_block in split_blocks(ciphertext):
            dc = xor_bytes(previous, self.decrypt_block(ciphertext_block))
            # dc = matrix2bytes(dcm)
            blocks.append(dc)
            previous = ciphertext_block

        key = b''.join(blocks)
        # print("sign_key", key.hex())
        data = self.mix_columns(data, key)
        return data

    def decrypt_block(self, ciphertext):
        assert len(ciphertext) == 16
        cipher_state = bytes2matrix(ciphertext)

        # print("b000", matrix2bytes(cipher_state).hex())
        add_round_key(cipher_state, self._key_matrices[4:])
        #         print("b001", matrix2bytes(cipher_state).hex())

        for i in range(2, 0, -1):
            add_round_key_con(cipher_state, self._key_matrices[i * 4:], self.con2)
            #             print("b002", i, matrix2bytes(cipher_state).hex())

            if i == 1:
                inv_mix_columns(cipher_state)
                self.shift_rows_con(cipher_state, self.con)

            self.inv_shift_rows(cipher_state)
            #             print("b004", i, matrix2bytes(cipher_state).hex())
            self.inv_sub_bytes(cipher_state)
        #             print("b005", i, matrix2bytes(cipher_state).hex())

        add_round_key_con(cipher_state, self._key_matrices[0:4], self.con2)

        return matrix2bytes(cipher_state)

    def shift_rows_con(self, s, c):
        for i in range(4):
            # c = self.con
            s[i][0], s[i][1], s[i][2], s[i][3] = s[i][c[0]], s[i][c[1]], s[i][c[2]], s[i][c[3]]

    def shift_rows(self, s):
        bs = matrix2bytes(s)
        for i in range(4):
            for j in range(4):
                s[i][j] = bs[self.order[i * 4 + j]]

    def inv_shift_rows(self, s):
        order = bytearray(16)
        for i in range(16):
            order[self.order[i]] = i

        bs = matrix2bytes(s)
        for i in range(4):
            for j in range(4):
                s[i][j] = bs[order[i * 4 + j]]

    def sub_bytes(self, s):
        for i in range(4):
            for j in range(4):
                s[i][j] = self.s_box[s[i][j]]

        s[0], s[1], s[2], s[3] = s[self.con2[0]], s[self.con2[1]], s[self.con2[2]], s[self.con2[3]]

    def inv_sub_bytes(self, s):
        for i in range(4):
            for j in range(4):
                s[i][j] = self.inv_s_box[s[i][j]]
        s[0], s[1], s[2], s[3] = s[self.con[0]], s[self.con[1]], s[self.con[2]], s[self.con[3]]

def leftCircularShift(k, bits):
    bits = bits % 32
    k = k % (2 ** 32)
    upper = (k << bits) % (2 ** 32)
    result = upper | (k >> (32 - (bits)))
    return (result)

def blockDivide(block, chunks):
    result = []
    size = len(block) // chunks
    for i in range(0, chunks):
        result.append(int.from_bytes(block[i * size:(i + 1) * size], byteorder="little"))
    return (result)

def F(X, Y, Z):
    return ((X & Y) | ((~X) & Z))

def G(X, Y, Z):
    return ((X & Z) | (Y & (~Z)))

def H(X, Y, Z):
    return (X ^ Y ^ Z)

def I(X, Y, Z):
    return (Y ^ (X | (~Z))) & 0xffffffff

def FF(a, b, c, d, M, s, t):
    result = b + leftCircularShift((a + F(b, c, d) + M + t), s)

    return (result)

def GG(a, b, c, d, M, s, t):
    result = b + leftCircularShift((a + G(b, c, d) + M + t), s)
    return (result)

def HH(a, b, c, d, M, s, t):
    result = b + leftCircularShift((a + H(b, c, d) + M + t), s)
    return (result)

def II(a, b, c, d, M, s, t):
    result = b + leftCircularShift((a + I(b, c, d) + M + t), s)
    return (result)

def sum_md5(data):
    check_sum = 0x20220420
    for i in range(12):
        if i % 2 == 0:
            temp = (check_sum >> 3) ^ check_sum
            check_sum = data[i] ^ (check_sum << 7)
        else:
            temp = (check_sum >> 5) ^ check_sum
            check_sum = data[i] | (check_sum << 11)
            check_sum ^= 0xffffffff

        check_sum ^= temp
        check_sum &= 0xffffffff

    check_sum |= 4
    check_sum ^= 0x1000000
    return check_sum

SV2 = [0xa7aefe20, 0x7149f1d6, 0x47e4ca07, 0xe9b58f67, 0x93b924de, 0xc614d0f5, 0x38afe0ef, 0xb2bbad73,
       0xe24444c3, 0x9d3aec9b, 0xdf7b37e4, 0xd8b16d40, 0xf8ac31b8, 0x76b9a90b, 0x31d833ee, 0x953fce64,
       0x353595a4, 0x4609c13b, 0x36925008, 0x8c6d0925, 0x5df5c177, 0x1cfbf52b, 0x8a4fa7f0, 0x114ca35e,
       0x8193f984, 0x7a7a8733, 0x316ab4d5, 0x3c20cfc9, 0xa6d84453, 0x3a18500c, 0x798ec47a, 0x97a76b28,
       0x66c4ff96, 0x51716443, 0xdd2fc3b, 0xb5696da7, 0xbbeb3ac5, 0x5c53d204, 0xd32608ce, 0x7279b9ec,
       0xf4188ecf, 0xf7d793db, 0x332cc491, 0xab76ae15, 0x9bebe727, 0x18a01384, 0x5be9f8a7, 0x5f90a754,
       0x39b663c0, 0x36673c83, 0x7c92f514, 0x9d7d94d7, 0xe2e8d9aa, 0x5f7e9ea9, 0x7abd4551, 0x569e05da,
       0x40a25632, 0x3df5a9a5, 0xbab37d80, 0x454286dc, 0x3f5d4e78, 0x3d7b75d, 0xb1fe4af7, 0xa5ab26a3]

def md5sum_v3(msg, count_v2, orders, count_v1, n=0):
    count = count_v2 & 0xff

    sv = [0] * 64
    for i in range(64):
        sv[i] = ror32(SV2[i], count_v1)

    start = [
        ror32(0x79e0f2fb, count),
        ror32(0xc8b52570, count),
        ror32(0xebc2f8cd, count),
        ror32(0x7c104d93, count)
    ]

    count = (count_v2 + 6) & 0xff
    end = [
        ror32(0x19be4866, count),
        ror32(0xe85986b4, count),
        ror32(0xe19b326e, count),
        ror32(0x71d1d7d4, count)
    ]
    A = start[0]  # 0x79e0f2fb
    B = start[1]  # 0xc8b52570
    C = start[2]  # 0xebc2f8cd
    D = start[3]  # 0x7c104d93

    a = A
    b = B
    c = C
    d = D
    block = msg[:64]
    M = blockDivide(block, 16)

    order1 = orders[:16]
    order2 = orders[16:32]
    order3 = orders[32:48]
    order4 = orders[48:]
    # Rounds
    a = FF(a, b, c, d, M[order1[0]], 7, sv[0])
    d = FF(d, a, b, c, M[order1[1]], 12, sv[1])  # 0xb6bc6ddb
    c = FF(c, d, a, b, M[order1[2]], 17, sv[2])  # 0xf80b15d4
    b = FF(b, c, d, a, M[order1[3]], 22, sv[3])
    a = FF(a, b, c, d, M[order1[4]], 7, sv[4])
    d = FF(d, a, b, c, M[order1[5]], 12, sv[5])
    c = FF(c, d, a, b, M[order1[6]], 17, sv[6])
    b = FF(b, c, d, a, M[order1[7]], 22, sv[7])
    a = FF(a, b, c, d, M[order1[8]], 7, sv[8])
    d = FF(d, a, b, c, M[order1[9]], 12, sv[9])
    c = FF(c, d, a, b, M[order1[10]], 17, sv[10])
    b = FF(b, c, d, a, M[order1[11]], 22, sv[11])
    a = FF(a, b, c, d, M[order1[12]], 7, sv[12])
    d = FF(d, a, b, c, M[order1[13]], 12, sv[13])
    c = FF(c, d, a, b, M[order1[14]], 17, sv[14])
    b = FF(b, c, d, a, M[order1[15]], 22, sv[15])

    a = GG(a, b, c, d, M[order2[0]], 5, sv[16])
    d = GG(d, a, b, c, M[order2[1]], 9, sv[17])
    c = GG(c, d, a, b, M[order2[2]], 14, sv[18])
    b = GG(b, c, d, a, M[order2[3]], 20, sv[19])
    a = GG(a, b, c, d, M[order2[4]], 5, sv[20])
    d = GG(d, a, b, c, M[order2[5]], 9, sv[21])
    c = GG(c, d, a, b, M[order2[6]], 14, sv[22])
    b = GG(b, c, d, a, M[order2[7]], 20, sv[23])
    a = GG(a, b, c, d, M[order2[8]], 5, sv[24])
    d = GG(d, a, b, c, M[order2[9]], 9, sv[25])
    c = GG(c, d, a, b, M[order2[10]], 14, sv[26])
    b = GG(b, c, d, a, M[order2[11]], 20, sv[27])
    a = GG(a, b, c, d, M[order2[12]], 5, sv[28])
    d = GG(d, a, b, c, M[order2[13]], 9, sv[29])
    c = GG(c, d, a, b, M[order2[14]], 14, sv[30])
    b = GG(b, c, d, a, M[order2[15]], 20, sv[31])

    a = HH(a, b, c, d, M[order3[0]], 4, sv[32])
    d = HH(d, a, b, c, M[order3[1]], 11, sv[33])
    c = HH(c, d, a, b, M[order3[2]], 16, sv[34])
    b = HH(b, c, d, a, M[order3[3]], 23, sv[35])
    a = HH(a, b, c, d, M[order3[4]], 4, sv[36])
    d = HH(d, a, b, c, M[order3[5]], 11, sv[37])
    c = HH(c, d, a, b, M[order3[6]], 16, sv[38])
    b = HH(b, c, d, a, M[order3[7]], 23, sv[39])
    a = HH(a, b, c, d, M[order3[8]], 4, sv[40])
    d = HH(d, a, b, c, M[order3[9]], 11, sv[41])
    c = HH(c, d, a, b, M[order3[10]], 16, sv[42])
    b = HH(b, c, d, a, M[order3[11]], 23, sv[43])
    a = HH(a, b, c, d, M[order3[12]], 4, sv[44])
    d = HH(d, a, b, c, M[order3[13]], 11, sv[45])
    c = HH(c, d, a, b, M[order3[14]], 16, sv[46])
    b = HH(b, c, d, a, M[order3[15]], 23, sv[47])

    a = II(a, b, c, d, M[order4[0]], 6, sv[48])
    d = II(d, a, b, c, M[order4[1]], 10, sv[49])
    c = II(c, d, a, b, M[order4[2]], 15, sv[50])
    b = II(b, c, d, a, M[order4[3]], 21, sv[51])
    a = II(a, b, c, d, M[order4[4]], 6, sv[52])
    d = II(d, a, b, c, M[order4[5]], 10, sv[53])
    c = II(c, d, a, b, M[order4[6]], 15, sv[54])
    b = II(b, c, d, a, M[order4[7]], 21, sv[55])
    a = II(a, b, c, d, M[order4[8]], 6, sv[56])
    d = II(d, a, b, c, M[order4[9]], 10, sv[57])
    c = II(c, d, a, b, M[order4[10]], 15, sv[58])
    b = II(b, c, d, a, M[order4[11]], 21, sv[59])
    a = II(a, b, c, d, M[order4[12]], 6, sv[60])
    d = II(d, a, b, c, M[order4[13]], 10, sv[61])
    c = II(c, d, a, b, M[order4[14]], 15, sv[62])
    b = II(b, c, d, a, M[order4[15]], 21, sv[63])

    A = (A + a) % (2 ** 32) ^ end[0]
    B = (B + b) % (2 ** 32) ^ end[1]
    C = (C + c) % (2 ** 32) ^ end[2]
    D = (D + d) % (2 ** 32) ^ end[3]

    result = bytearray(
        A.to_bytes(4, "little") + B.to_bytes(4, "little") + C.to_bytes(4, "little") + D.to_bytes(4, "little"))

    result += sum_md5(result).to_bytes(4, "little")
    return result

def bxor(b1, b2):
    b3 = bytearray(len(b1))
    for i in range(len(b1)):
        b3[i] = b1[i] ^ b2[i]
    return b3

def get_iv(iv, data):
    for i in range(len(data)):
        if i & 1 == 0:
            iv = (iv >> 4) ^ iv ^ (iv << 6) ^ data[i]
        else:
            iv = ~((iv >> 7) ^ iv ^ (data[i] | iv << 12))
        iv = iv & 0xffffffff
    return iv

def hash_f13(query_sm3, body_md5_bytes, ts_bytes, khronos):
    iv = get_iv(0x20230928, query_sm3)
    iv = get_iv(iv, body_md5_bytes)
    iv = get_iv(iv, ts_bytes)

    iv_v0 = ((iv & 15) * 171) >> 9
    branch = (iv & 15) - ((iv_v0 * 3) & 0xff)
    if branch == 0:
        return branch_0(iv_v0, khronos, query_sm3, body_md5_bytes, ts_bytes)
    elif branch == 1:
        return branch_1(iv_v0, khronos, query_sm3, body_md5_bytes, ts_bytes)
    elif branch == 2:
        return branch_2(iv, khronos, query_sm3, body_md5_bytes, ts_bytes)
    else:
        raise Exception("no branch: " + str(branch))

def branch_0(iv_v0, khronos, query_sm3, body_md5_bytes, ts_bytes):
    tt01 = [0xc4a78580, 0xb3c0fd39, 0xc58c5686, 0xc9aa3ba7, 0xf5a7adf2, 0x963c2ed1]
    iv_v1 = tt01[iv_v0]

    count_v1 = (iv_v1 + khronos + 1) & 0xff
    count_v2 = (iv_v1 + khronos) & 0xffffffff

    tt02 = [0xebb64faf, 0x7aadcc2, 0xcf3187bf, 0xe01138ff, 0x6d0bfcff, 0x5a30a3be, 0xb41ad638, 0x34180eb8, 0xf233eb6f,
            0xb1a584cc, 0xccc30dc7, 0x47d1db51, 0xd55653de, 0x70a84fa1, 0x57473c12, 0xf76f0288, 0x2c077f0a, 0xda0dcad0,
            0xfbb86f6c, 0xfdc4cf00, 0x688a020d, 0xe676c6a6, 0x8cd6338b, 0x1a3c8d0e, 0xcce8b06b, 0x6ad0ed0b, 0xa0522717,
            0xdc71ac83, 0x2285db71, 0xd5b4dda6, 0x736f8650, 0x6560306c, 0x617ce2a6, 0xe423417e, 0xa40e143, 0x544e4032,
            0x88dffb2a, 0x716c1ae0, 0x4c467a88, 0x5b23bb3, 0xe1d0b866, 0xbaa3dcb8, 0xae3374d3, 0xc3381a50, 0x1702f75b,
            0xfe6da368, 0xf0b4cf48, 0x4e0ffbb8, 0x72aad10d, 0x26c53a3d, 0xf2bce0f6, 0xb4557581, 0x4a257fdd, 0x8c3182a2,
            0xab0b3b86, 0x3d5dfb14, 0x4f103634, 0xd37b52d7, 0x444eff16, 0xeb0a33d1, 0x6ca86f6e, 0x284ba7, 0x8387cfa,
            0x5fb37586]

    tt03 = [0] * 64
    for i in range(0, 64):
        tt03[i] = ror32(tt02[i], count_v1) & 0xffffffff

    n0 = (count_v2 + 2) & 7

    pad = bytearray(4)
    seed = bytes([0xfa, 0x45, 0x61, 0xd7])
    for i in range(4):
        v = int.from_bytes(bytes([seed[i], seed[i]]), 'little')
        v = v >> n0
        pad[i] = v & 0xff

    count_v2 = count_v2 & 0xff
    init_value = [
        ror32(0x7aba4fc8, count_v2), ror32(0x67166507, count_v2),
        ror32(0x6403fa00, count_v2), ror32(0x340f512f, count_v2),
        ror32(984304912, count_v2), ror32(3005047866, count_v2),
        ror32(2874125293, count_v2), ror32(2152413264, count_v2)
    ]

    data = query_sm3 + body_md5_bytes + ts_bytes + pad + bytes.fromhex(' 00 00 00 00 00 00 01 a0')
    di = [0] * (len(data) // 4)
    for i in range(len(data) // 4):
        di[i] = int.from_bytes(data[i * 4:i * 4 + 4], "big")

    di0 = di[0]
    for i in range(112):
        di1, di14 = di[i + 1], di[i + 14]
        r_di1 = rol(di1, 14) ^ rol(di1, 25) ^ (di1 >> 3)
        r_di2 = rol(di14, 13) ^ rol(di14, 15) ^ (di14 >> 10)
        di0 = di0 + di[i + 9] + r_di1 + r_di2
        di.append(di0 & 0xffffffff)
        di0 = di1

    if iv_v0 == 5:
        v_j = branch0_xor(init_value, iv_v1, di, tt03, 100, 2, 0, 3, 5, 4, 6, 7, 2, 1, 5)
    elif iv_v0 == 4:
        v_j = branch0_xor(init_value, iv_v1, di, tt03, 96, 0, 5, 6, 7, 3, 1, 2, 5, 4, 4)
    elif iv_v0 == 3:
        v_j = branch0_xor(init_value, iv_v1, di, tt03, 99, 3, 6, 2, 4, 5, 1, 0, 0, 7, 6)
    elif iv_v0 == 2:
        v_j = branch0_xor(init_value, iv_v1, di, tt03, 96, 7, 6, 2, 1, 4, 0, 5, 4, 3, 5)
    elif iv_v0 == 1:
        v_j = branch0_xor(init_value, iv_v1, di, tt03, 96, 0, 6, 7, 5, 3, 2, 1, 5, 4, 4)
    elif iv_v0 == 0:
        v_j = branch0_xor(init_value, iv_v1, di, tt03, 101, 5, 7, 6, 3, 2, 1, 0, 5, 4, 3)

    ret = bytearray(32)
    for i in range(8):
        ret[i * 4:i * 4 + 4] = ((v_j[i] + init_value[i]) & 0xffffffff).to_bytes(4, 'big')

    ret = bxor(ret[:16], ret[16:])
    sum = sum_md5(ret)
    ret += sum.to_bytes(4, "little")
    return ret

def swap_v0(src, src_xor, tt2, table_f, order1, typ=None):
    da0 = [0] * 8
    ha0 = src_xor[:]
    for i in range(8):
        da0[i] = src[order1[i]] ^ src_xor[i]

    for round in range(10):
        rr_0 = r00(ha0[0], ha0[1], ha0[2], ha0[3], ha0[4], ha0[5], ha0[6], ha0[7], 0, table_f)
        rr_1 = r00(ha0[1], ha0[2], ha0[3], ha0[4], ha0[5], ha0[6], ha0[7], ha0[0], 0, table_f)
        rr_2 = r00(ha0[2], ha0[3], ha0[4], ha0[5], ha0[6], ha0[7], ha0[0], ha0[1], 0, table_f)
        rr_3 = r00(ha0[3], ha0[4], ha0[5], ha0[6], ha0[7], ha0[0], ha0[1], ha0[2], 0, table_f)
        rr_4 = r00(ha0[4], ha0[5], ha0[6], ha0[7], ha0[0], ha0[1], ha0[2], ha0[3], 0, table_f)
        rr_5 = r00(ha0[5], ha0[6], ha0[7], ha0[0], ha0[1], ha0[2], ha0[3], ha0[4], 0, table_f)
        rr_6 = r00(ha0[6], ha0[7], ha0[0], ha0[1], ha0[2], ha0[3], ha0[4], ha0[5], 0, table_f)
        rr_7 = r00(ha0[7], ha0[0], ha0[1], ha0[2], ha0[3], ha0[4], ha0[5], ha0[6], 0, table_f)
        rr_7 = rr_7 ^ tt2[round + 1]

        d0, d1, d2, d3, d4, d5, d6, d7 = da0[0], da0[1], da0[2], da0[3], da0[4], da0[5], da0[6], da0[7]

        da0[0] = r00(d0, d1, d2, d3, d4, d5, d6, d7, rr_0, table_f)
        da0[1] = r00(d1, d2, d3, d4, d5, d6, d7, d0, rr_1, table_f)  # 0xd0a489b35ba678e8
        da0[2] = r00(d2, d3, d4, d5, d6, d7, d0, d1, rr_2, table_f)  # 0x3be5b7f9cfd44654
        da0[3] = r00(d3, d4, d5, d6, d7, d0, d1, d2, rr_3, table_f)
        da0[4] = r00(d4, d5, d6, d7, d0, d1, d2, d3, rr_4, table_f)
        da0[5] = r00(d5, d6, d7, d0, d1, d2, d3, d4, rr_5, table_f)
        da0[6] = r00(d6, d7, d0, d1, d2, d3, d4, d5, rr_6, table_f)
        da0[7] = r00(d7, d0, d1, d2, d3, d4, d5, d6, rr_7, table_f)

        ha0[0], ha0[1], ha0[2], ha0[3], ha0[4], ha0[5], ha0[6], ha0[7] = rr_0, rr_1, rr_2, rr_3, rr_4, rr_5, rr_6, rr_7

    if typ is None:
        src[0] = da0[0] ^ src_xor[0] ^ src[0]
        src[1] = da0[7] ^ src_xor[1] ^ src[1]
        src[2] = da0[6] ^ src_xor[2] ^ src[2]
        src[3] = da0[5] ^ src_xor[3] ^ src[3]
        src[4] = da0[4] ^ src_xor[4] ^ src[4]
        src[5] = da0[3] ^ src_xor[5] ^ src[5]
        src[6] = da0[2] ^ src_xor[6] ^ src[6]
        src[7] = da0[1] ^ src_xor[7] ^ src[7]
    else:
        src[0] = da0[7] ^ typ[1]
        src[1] = da0[6] ^ typ[2]
        src[2] = da0[5] ^ typ[3]
        src[3] = da0[4] ^ typ[4]
        src[4] = da0[3] ^ typ[5]
        src[5] = da0[2] ^ typ[6]
        src[6] = da0[1] ^ typ[7] ^ src[7]
        src[7] = da0[0] ^ typ[0]
    return src

def branch_1(iv_v0, khronos, query_sm3, body_md5_bytes, ts_bytes):
    tt1 = [0x808a9c79, 0xf079807e, 0xbadf79c5, 0xa785d3ff, 0x82d8438c]
    iv_v1 = tt1[iv_v0]

    c_v1 = (iv_v1 + khronos) & 0xff
    c_v1 = ror(khronos, c_v1)

    orders = bytes.fromhex('''05 07 01 02 04 00 06 03 00 05 02 04 01 03 07 06
    05 07 02 04 01 06 03 00 03 00 02 04 06 07 01 05
    04 05 00 03 06 02 01 07 00 00 00 00 00 00 00 00''')

    order1 = orders[iv_v0 * 8:iv_v0 * 8 + 8]

    iv_v1 = (iv_v1 + khronos + 1) & 63
    tt1 = [0x87aeea5dab37cd6b, 0x7ff48becb4f54087, 0xb0724c06706bbd5d, 0x1fe5dfb1143e328d,
           0x1a2331d00af4f1f2, 0xcaff7131bb1e71ba, 0x33385e1042752218, 0xff01ed65d4a441fb,
           0xadb1ec8828c80e8, 0x62475d12f4e06fe7, 0xbd0b238da4fe72]

    tt2 = [0] * 11
    for i in range(0, 11):
        tt2[i] = ror(tt1[i], iv_v1)

    to_sign = bytearray(query_sm3 + body_md5_bytes + ts_bytes + bytes([0x80, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]))

    src = [0] * (len(to_sign) // 8)
    for i in range(len(to_sign) // 8):
        src[i] = int.from_bytes(to_sign[i * 8:i * 8 + 8], 'big')

    src_xor = [c_v1, c_v1, c_v1, c_v1, c_v1, c_v1, c_v1, c_v1]

    table_f = get_branch_1_table_f(iv_v0)
    swap = swap_v0(src, src_xor, tt2, table_f, order1)
    data = [0] * 8
    data[7] = 416

    src_xor = [swap[4], swap[3], swap[2], swap[1], swap[0], swap[7], swap[6], swap[5]]
    swap = swap_v0(data, src_xor, tt2, table_f, order1, swap)

    ret = bytearray(32)
    n = 0
    for i in range(7, -1, -1):
        pp = swap[i].to_bytes(8, "little")
        ret[n + 0], ret[n + 1], ret[n + 2], ret[n + 3] = pp[1], pp[3], pp[5], pp[6]
        n += 4

    for i in range(16):
        ret[i] ^= ret[i + 16]
    ret = ret[:16]
    sum = sum_md5(ret)
    ret += sum.to_bytes(4, "little")
    return ret

def r00(r0, r1, r2, r3, r4, r5, r6, r7, tt, table_f, v=0):
    x = table_f(8 * (r0 >> 56))
    r1 = (r1 >> 45) & 2040

    if tt > 0:
        x = x ^ tt
    x = x ^ table_f(r1 + 2048)

    r2 = (r2 >> 37) & 2040
    x = x ^ table_f(r2 + 4096)

    r3 = (r3 >> 29) & 2040
    x = x ^ table_f(r3 + 6144)

    r4 = (r4 >> 21) & 2040
    x = x ^ table_f(r4 + 8192)

    r5 = (r5 >> 13) & 2040
    x = x ^ table_f(r5 + 10240)

    r6 = (r6 >> 8) & 255
    x = x ^ table_f(8 * r6 + 12288)

    r7 = r7 & 255
    x = x ^ table_f(8 * r7 + 14336)

    return x

branch_2_orders = bytes.fromhex('''
    0f 07 04 00 09 08 03 0a 06 0b 05 0d 0e 01 0c 02 0f 05 08 0c 00 09 02 01 03 07 0e 06 0b 0a 0d 04 06 05 00 07 0c 00 0a 04 08 0f 01 0b 0d 09 02 0e 06 0b 02 05 04 03 08 01 01 07 0a 00 0d 0c 09 0e
    0d 07 0e 0f 0b 02 08 03 0c 05 09 01 00 04 06 0a 0d 09 02 06 0f 0b 0a 04 08 07 00 0c 05 03 01 0e 0c 09 0f 07 06 0f 03 0e 02 0d 04 05 01 0b 0a 00 0c 05 0a 09 0e 08 02 04 04 07 03 0f 01 06 0b 00
    0b 0f 04 08 02 0a 07 00 09 0d 06 01 0e 03 05 0c 0b 06 0a 05 08 02 0c 03 07 0f 0e 09 0d 00 01 04 09 06 08 0f 05 08 00 04 0a 0b 03 0d 01 02 0c 0e 09 0d 0c 06 04 07 0a 03 03 0f 00 08 01 05 02 0e
    01 00 0d 0f 09 0a 0b 0e 04 02 08 07 03 06 0c 05 01 08 0a 0c 0f 09 05 06 0b 00 03 04 02 0e 07 0d 04 08 0f 00 0c 0f 0e 0d 0a 01 06 02 07 09 05 03 04 02 05 08 0d 0b 0a 06 06 00 0e 0f 07 0c 09 03
    0a 08 04 0f 00 0b 01 06 0d 0c 07 09 03 0e 05 02 0a 07 0b 05 0f 00 02 0e 01 08 03 0d 0c 06 09 04 0d 07 0f 08 05 0f 06 04 0b 0a 0e 0c 09 00 02 03 0d 0c 02 07 04 01 0b 0e 0e 08 06 0f 09 05 00 03
    ''')

def branch_2(iv, khronos, query_sm3, body_md5_bytes, ts_bytes):
    n0 = (iv & 15 - 2) * 86
    iv_v0 = (n0 >> 15 & 0xff) + (n0 >> 8 & 0xff)

    t001 = [0x8980f29b, 0xeb549c7f, 0xb08726db, 0xd40cb5e6, 0xe8f559e4]

    n1 = t001[iv_v0]
    count_v1 = (n1 + khronos + 1) & 0xff
    count_v2 = (n1 + khronos) & 0xffffffff

    n0 = (count_v2 + 5) & 7

    pad = bytearray(8)
    seed = bytes([0x84, 0x96, 0x77, 0x9d, 0xd4, 0x15, 0x0b, 0xf8])
    for i in range(8):
        v = int.from_bytes(bytes([seed[i], seed[i]]), 'little')
        v = v >> n0
        pad[i] = v & 0xff

    data = query_sm3 + body_md5_bytes + ts_bytes + pad + bytes.fromhex('a0 01 00 00')

    idx = iv_v0 << 6
    ret = md5sum_v3(data, count_v2, branch_2_orders[idx:idx + 64], count_v1)

    return ret

def branch0_xor(data, base, di, tt03, round, x1, x2, x3, x4, x5, x6, x7, x8, x9, x10):
    d = data[:]

    for i in range(round):
        offset = base + i
        n0 = di[offset & 127]

        n1 = ((d[x3] ^ d[x4]) & d[x1]) ^ d[x3]

        n2 = rol(d[x1], 26) ^ rol(d[x1], 21) ^ rol(d[x1], 7)
        offset = offset & 63
        n3 = tt03[offset]

        n4 = (n0 + n1 + n2 + n3 + d[x5]) & 0xffffffff

        n5 = rol(d[x2], 30) ^ rol(d[x2], 19) ^ rol(d[x2], 10)
        n6 = (d[x2] & d[x6]) | ((d[x2] | d[x6]) & d[x7])
        n7 = n5 + n6

        o = d[x9]
        d[0], d[1], d[2], d[3], d[4], d[5], d[6], d[7] = d[7], d[0], d[1], d[2], d[3], d[4], d[5], d[6]
        d[x10] = (n7 + n4) & 0xffffffff
        d[x8] = (o + n4) & 0xffffffff
    return d

branch_1_table = None

def get_branch_1_table_f(iv_v0):
    global branch_1_table
    if branch_1_table is None:
        branch_1_table = _branch_one_bytes()

    table = branch_1_table[iv_v0 << 14:]
    def table_f(x):
        return int.from_bytes(table[x:x + 8], 'little')
    return table_f

def _varint(value: int) -> bytes:
    value = int(value)
    if value < 0:
        value &= (1 << 64) - 1
    result = bytearray()
    while value > 0x7F:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    result.append(value)
    return bytes(result)

def _sint(value: int, bits: int) -> int:
    # 正式 protobuf 编码规则：正数不先截断到有符号范围；
    # 这对 Medusa.rand 等可能大于 2**31 的 sint32 字段很重要。
    value = int(value)
    return (value << 1) if value >= 0 else (value << 1) ^ (~0)

def _proto_field(field: int, value: Any, kind: str) -> bytes:
    if value in (None, "", b"", 0, 0.0, False):
        return b""
    if kind == "sint32":
        return _varint((field << 3) | 0) + _varint(_sint(int(value), 32))
    if kind == "sint64":
        return _varint((field << 3) | 0) + _varint(_sint(int(value), 64))
    if kind == "float":
        return _varint((field << 3) | 5) + struct.pack("<f", float(value))
    if kind == "bytes":
        raw = bytes(value)
    elif kind == "string":
        raw = str(value).encode("utf-8")
    elif kind == "message":
        raw = bytes(value)
    else:
        raise ValueError(f"unknown protobuf field kind: {kind}")
    return _varint((field << 3) | 2) + _varint(len(raw)) + raw

def _proto(fields: list[tuple[int, Any, str]]) -> bytes:
    return b"".join(_proto_field(field, value, kind) for field, value, kind in fields)

def _encode_request() -> bytes:
    return _proto([
        (1, 111, "sint32"),
        (2, 10, "sint32"),
        (3, 694367, "sint32"),
        (5, 586952199, "sint32"),
    ])

def _encode_device(device: Mapping[str, Any]) -> bytes:
    fields = [
        (1, device.get("d1"), "sint32"), (2, device.get("collect_stat"), "sint32"),
        (3, device.get("aid"), "string"), (4, device.get("device_id"), "string"),
        (5, device.get("sec_device_token"), "string"), (6, device.get("app_version"), "string"),
        (7, device.get("battery"), "sint32"), (8, device.get("battery2"), "sint32"),
        (9, device.get("battery_health"), "sint32"), (10, device.get("battery_changed"), "sint32"),
        (11, device.get("network"), "string"), (12, device.get("tz"), "string"),
        (13, device.get("lan"), "string"), (14, device.get("cpu"), "sint32"),
        (15, device.get("resolution"), "string"), (16, device.get("sdcard"), "float"),
        (17, device.get("sdcard_used"), "float"), (18, device.get("memory"), "float"),
        (19, device.get("memory2"), "float"), (20, device.get("data"), "float"),
        (21, device.get("data_used"), "float"), (22, device.get("os_version"), "string"),
        (23, device.get("brightness"), "sint32"), (24, device.get("volume"), "sint32"),
        (25, device.get("ts"), "sint64"), (26, device.get("ts2"), "sint64"),
        (27, device.get("ts3"), "sint64"), (28, device.get("ts4"), "sint64"),
        (29, device.get("usb"), "sint32"), (30, device.get("hw_version"), "string"),
        (31, device.get("brand"), "string"), (32, device.get("board"), "string"),
        (33, device.get("product_name"), "string"), (34, device.get("product_device"), "string"),
        (35, device.get("product_manufacturer"), "string"), (36, device.get("hardware"), "string"),
        (38, device.get("unknown38"), "sint32"), (40, device.get("unknown40"), "sint32"),
    ]
    return _proto(fields)

def _encode_env(env: Mapping[str, Any]) -> bytes:
    fields = [
        (1, env.get("launch_time"), "sint32"), (2, env.get("unknown2"), "sint32"),
        (3, env.get("unknown3"), "sint32"), (5, env.get("unknown5"), "sint32"),
        (6, env.get("version"), "string"), (7, env.get("pid"), "sint32"),
        (12, _encode_device(env.get("device") or {}), "message"),
        (13, _proto([
            (1, (env.get("report") or {}).get("time"), "sint64"),
            (2, (env.get("report") or {}).get("state"), "sint32"),
            (4, (env.get("report") or {}).get("code"), "sint32"),
            (5, (env.get("report") or {}).get("times"), "sint32"),
            (6, (env.get("report") or {}).get("unknown6"), "sint32"),
        ]), "message"),
        (14, env.get("app_version"), "string"),
        (15, env.get("unknown15"), "sint32"), (16, env.get("unknown16"), "sint32"),
        (18, env.get("unknown18"), "sint32"), (19, env.get("unknown19"), "sint32"),
        (20, env.get("unknown20"), "sint32"), (21, env.get("unknown21"), "sint32"),
    ]
    return _proto(fields)

def _encode_medusa(values: Mapping[str, Any]) -> bytes:
    return _proto([
        (1, values.get("magic"), "bytes"), (2, values.get("version"), "sint32"),
        (3, values.get("rand"), "sint32"), (4, values.get("ms_app_id"), "string"),
        (5, values.get("device_id"), "string"), (6, values.get("license_id"), "string"),
        (7, values.get("app_version"), "string"), (8, values.get("sdk_version_str"), "string"),
        (9, values.get("sdk_version"), "sint32"), (10, values.get("xg_seed_bytes"), "bytes"),
        (12, values.get("time"), "sint32"), (13, values.get("query_body_ts_hash"), "bytes"),
        (14, values.get("query_sm3"), "bytes"), (15, _encode_request(), "message"),
        (16, values.get("sec_device_token"), "string"), (17, values.get("time2"), "sint32"),
        (18, values.get("lanusk_hash"), "bytes"), (19, values.get("query_body_hash_sm3"), "bytes"),
        (20, values.get("psk_version"), "string"), (21, values.get("call_type"), "sint32"),
        (23, _encode_env(values.get("env") or {}), "message"),
        (24, values.get("unknown24"), "string"), (26, values.get("original"), "string"),
    ])

def _json_body_md5(data: Any, data_type: str | None = None) -> str:
    if not data:
        return ""
    if isinstance(data, str):
        raw = data.encode("utf-8")
    elif isinstance(data, bytes):
        raw = data
    elif data_type == "application/json; charset=UTF-8":
        raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    else:
        raw = urlencode(data).encode("utf-8")
    return hashlib.md5(raw).hexdigest().upper()

def _url_encode(value: Mapping[str, Any]) -> str:
    return urlencode(value).replace("+", "%20").replace("%2A", "*")

def _get_params_encrypturl(url: str, params: Mapping[str, Any], devices: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    result = dict(params)
    for key, value in devices.items():
        if key in result:
            result[key] = value
        elif key == "device_id" and "did" in result:
            result["did"] = value
    result["ts"] = int(time.time())
    result["_rticket"] = int(time.time() * 1000)
    return url.split("?", 1)[0] + "?" + _url_encode(result), result

def _xg_rc4(data: bytes, key: bytes) -> bytearray:
    table = list(range(256))
    j = 0
    for i in range(256):
        j = (j + table[i] + key[i % len(key)]) % 256
        table[i] = table[j]
    i = j = 0
    result = bytearray(len(data))
    for index, value in enumerate(data):
        i = (i + 1) & 0xFF
        x = table[i]
        j = (j + x) & 0xFF
        y = table[j]
        # 保持正式基线的 RC4 变体：这里只覆盖 S[i]，不交换 S[j]。
        table[i] = y
        result[index] = value ^ table[(y + y) & 0xFF]
    return result

def _reverse_bits(value: int) -> int:
    return int(f"{value:08b}"[::-1], 2)

def _encrypt_gorgon(body: Any, query: str, khronos: int, xg_rand: int, data_type: str) -> str:
    body_md5 = _json_body_md5(body, data_type).lower() if body else ""
    data = bytearray(hashlib.md5(query.encode()).digest()[:4])
    data += bytes.fromhex(body_md5)[:4] if body_md5 else b"\0\0\0\0"
    data += b"\0\0\0\0" + (67503104).to_bytes(4, "little") + khronos.to_bytes(4, "big")
    key = bytes((0x4A, 320 & 0xFF, 0x16, (xg_rand >> 8) & 0xFF, 0x47, 0x6C, 1, xg_rand & 0xFF))
    result = _xg_rc4(data, key)
    for index, value in enumerate(result):
        value = ((value >> 4) | (value << 4)) & 0xFF
        following = result[index + 1] if index + 1 < len(result) else result[0]
        result[index] = (~(_reverse_bits(following ^ value) ^ 20)) & 0xFF
    return (b"\x84\x04" + xg_rand.to_bytes(2, "little") + (320).to_bytes(2, "little") + result).hex()

def _ror64(value: int, count: int) -> int:
    count %= 64
    return ((value >> count) | (value << (64 - count))) & 0xFFFFFFFFFFFFFFFF

def _encrypt_helios(khronos: int, rand_value: int = 0) -> str:
    value = rand_value or random.randint(0, 0xFFFFFFFF)
    seed = value.to_bytes(4, "little") + b"8662"
    digest = hashlib.md5(seed).digest()
    keys = b"".join(f"{item:02x}".encode() for item in digest)
    table = [int.from_bytes(keys[:8], "little")]
    words = [int.from_bytes(keys[i:i + 8], "little") for i in range(0, 32, 8)]
    first, second = words[0], words[1]
    words = words[2:]
    for index in range(0x22):
        value2 = _ror64(second, 8)
        value2 = (value2 + first) & 0xFFFFFFFFFFFFFFFF
        value2 = (value2 ^ index) & 0xFFFFFFFFFFFFFFFF
        words.append(value2)
        value2 ^= _ror64(first, 61)
        value2 &= 0xFFFFFFFFFFFFFFFF
        table.append(value2)
        first, second = value2, words.pop(0)
    raw = (f"{khronos}-1588093228-8662").encode()
    pad = 16 - len(raw) % 16
    raw += bytes([pad]) * pad
    output = bytearray()
    for offset in range(0, len(raw), 16):
        left = int.from_bytes(raw[offset:offset + 8], "little")
        right = int.from_bytes(raw[offset + 8:offset + 16], "little")
        for index in range(0x22):
            right = (table[index] ^ (left + _ror64(right, 8))) & 0xFFFFFFFFFFFFFFFF
            left = (right ^ _ror64(left, 61)) & 0xFFFFFFFFFFFFFFFF
        output += left.to_bytes(8, "little") + right.to_bytes(8, "little")
    return base64.b64encode(value.to_bytes(4, "little") + output).decode()

def _gen_medusa_proto(url: str, url_params: Mapping[str, Any], devices: Mapping[str, Any], data: Any, khronos: int, data_type: str) -> tuple[bytes, bytes, bytes]:
    body_md5 = _json_body_md5(data, data_type).lower() if data else ""
    body_md5_bytes = bytes.fromhex(body_md5) if body_md5 else bytes(16)
    ts_bytes = khronos.to_bytes(4, "little")
    query = url.split("?", 1)[1] if "?" in url else ""
    query_sm3 = SM3(query).digest()
    query_body_hash = SM3(query.encode() + body_md5_bytes + b"none").digest()
    device_id = str(devices.get("device_id", url_params.get("device_id", url_params.get("did", ""))))
    version_name = str(devices.get("version_name", url_params.get("version_name", "7.1.3.32")))
    device_model = str(devices.get("device_model", url_params.get("device_type", "")))
    brand = str(devices.get("device_brand", url_params.get("device_brand", "")))
    sec_device_token = str(devices.get("sec_device_token") or "")
    device_sec_device_token = str(devices.get("device_sec_device_token") or "")
    proto_rand = random.randint(0, 0xFFFFFFFF)
    launch_time = random.randint(100, 120)
    process_id = random.randint(10001, 12000)
    # 这些字段是正式签名实现中的固定环境采样值，不是用户设备标识。
    report_ts = 1728388016635
    report_time = int(time.time())
    device = {
        "d1": 1, "collect_stat": 2, "aid": "8662", "device_id": device_id,
        "sec_device_token": device_sec_device_token,
        "app_version": "!noperm!", "battery": -888888, "battery2": -888888,
        "battery_health": 3, "battery_changed": -888888, "network": "!notset!",
        "tz": "Asia/Shanghai,8", "lan": "zh_CN", "cpu": 4,
        "sdcard": 255.24993896484375, "sdcard_used": 35.58599090576172,
        "memory": 3.467449188232422, "memory2": 3.467449188232422,
        "data": 255.1754913330078, "data_used": 42.17544174194336,
        "os_version": str(devices.get("os_version", url_params.get("os_version", ""))),
        "brightness": 41, "volume": 36, "ts": report_ts, "ts2": report_ts,
        "ts3": report_ts, "ts4": report_ts + 2, "usb": -1, "hw_version": device_model,
        "brand": brand, "board": device_model, "product_name": device_model,
        "product_device": str(devices.get("device_manufacturer", brand)),
        "product_manufacturer": brand, "hardware": brand, "unknown38": 31,
    }
    env = {
        "launch_time": launch_time, "unknown2": 146331399,
        "unknown3": 146331396, "unknown5": 7, "version": "v04.06.04.03-bugfix",
        "pid": process_id, "device": device,
        "report": {"time": report_time, "state": -2, "code": 200, "times": 0, "unknown6": 0},
        "app_version": version_name,
    }
    values = {
        "magic": b"\xf7\xe8_\xfa\xd7\xd7\xdc;\xd6*\xc8pW\xcfa\x18",
        "version": 3, "rand": proto_rand, "ms_app_id": "8662",
        "device_id": device_id, "license_id": "1588093228", "app_version": version_name,
        "sdk_version_str": "v04.06.04-ml-android", "sdk_version": 67503104,
        "xg_seed_bytes": (320).to_bytes(8, "little"), "time": khronos,
        "query_body_ts_hash": hash_f13(query_sm3, body_md5_bytes, ts_bytes, khronos),
        "query_sm3": query_sm3[:6], "sec_device_token": sec_device_token, "time2": khronos,
        "lanusk_hash": b"", "query_body_hash_sm3": query_body_hash, "psk_version": "none",
        "call_type": 312, "env": env,
        "unknown24": '{"cmr":16777216,"cmr2":16777216,"un_h":1879194040,"vpn":0,"kd":0,"fkd":3672518972,"pd":-1872573247,"dyn":"","do":0,"tk":true}',
    }
    return _encode_medusa(values), query_sm3, hash_f13(query_sm3, body_md5_bytes, ts_bytes, khronos)

def _xmxor_two(data: bytes, key: bytes) -> bytearray:
    encoded = bytearray(len(data))
    for index, value in enumerate(data):
        position = (index * 4) & 28
        d0, d1 = key[position], key[position + 1]
        d2 = (rl8(value, 4) + d0) ^ d1
        d2 = rl8((~d2) & 0xFF, 3)
        d2 = ((d2 + d1) & 0xFF) ^ d0
        encoded[-index - 1] = (~d2) & 0xFF
    return encoded

def _xmxor(data: bytes, key: bytes) -> bytearray:
    value = _xmxor_two(data, key)
    last_flag = value[-1] ^ value[-2]
    data0 = value[0]
    value[0] = (~last_flag + value[0]) & 0xFF
    value[1] = ((value[0] ^ value[-1] ^ 254) + value[1]) & 0xFF
    value[2] = (value[2] + ((last_flag - data0) ^ rl8(value[1], 3) ^ 2)) & 0xFF
    for index in range(len(value) - 4):
        temp = rl8(value[index + 2], 3) ^ value[index + 1] ^ (index + 3)
        value[index + 3] = (~temp + value[index + 3]) & 0xFF
    value[-1] ^= value[-2]
    value[0] = ((value[0] ^ value[1]) + sum(value[1:])) & 0xFF
    return value

def _gen_medusa(url: str, url_params: Mapping[str, Any], devices: Mapping[str, Any], data: Any, khronos: int, data_type: str) -> str:
    config_key = b"\xf1Y3vvn\xa9\x8d4\xf3\x1b\x05z\x9d[\xe4"
    config_iv = b"\x1f\xe1\t\xa4\x12R\x83\xf4\x18\xde\x9e\x05\x1a\x96\x9e\x12"
    sign_key = b"\x8e\xbd\xfa8\x06\xec\xc5\xce\xe7\x94#\xe6\x02\x9e\xd8%@\xbc\"\x18\xbb~\xae\xf7\x1c\xb6\x91\xf7\xaa\x8a\xa2\xf5"
    proto, query_sm3, body_sm3 = _gen_medusa_proto(url, url_params, devices, data, khronos, data_type)
    hash_rand = random.randint(0, 0xFFFFFFFF)
    xm_rand = random.randint(0, 0xFFFFFFFF)
    key, seed = get_key_hash(sign_key, hash_rand)
    mixed = _xmxor(proto, key)
    mixed = (320).to_bytes(8, "little") + mixed
    mixed = bytearray(mixed[::-1])
    for index in range(len(mixed)):
        mixed[index] ^= seed[~index & 3]
    hash_bytes = hash_rand.to_bytes(4, "little")
    check_bit = ((query_sm3[0] & 63) << 14) | 0x18000001 | ((body_sm3[0] & 63) << 8)
    mixed = b"\x35" + xm_rand.to_bytes(4, "little") + check_bit.to_bytes(4, "little") + mixed + hash_bytes[2:]
    mixed = AES_V3(config_key, khronos).encrypt(mixed, config_iv)
    version = bytes.fromhex("03 00 00 00 f7 e8 5f fa d7 d7 dc 3b d6 2a c8 70 57 cf 61 18")
    version_or = b"".join((int.from_bytes(version[i:i + 4], "little") ^ khronos).to_bytes(4, "little") for i in range(0, 20, 4))
    return base64.b64encode(version_or + hash_bytes[:2] + (256).to_bytes(2, "little") + mixed).decode()

def _core_sixgod(url: str, params: Mapping[str, Any], devices: Mapping[str, Any], data: Any, header: Mapping[str, Any]) -> tuple[dict[str, str], str]:
    data_type = str(header.get("content-type", header.get("Content-Type", "")))
    xg_rand = random.randint(0, 0xFFFF)
    encrypted_url, url_params = _get_params_encrypturl(url, params, devices)
    khronos = int(time.time())
    encoded_query = _url_encode(url_params)
    values = {
        "khronos": str(khronos),
        "ladon": base64.b64encode(khronos.to_bytes(4, "big")).decode(),
        "argus": base64.b64encode(khronos.to_bytes(4, "little")).decode(),
        "gorgon": _encrypt_gorgon(data, encoded_query, khronos, xg_rand, data_type),
        "helios": _encrypt_helios(khronos, 0),
        "medusa": _gen_medusa(encrypted_url, url_params, devices, data, khronos, data_type),
    }
    signs = {
        "x-ladon": values["ladon"], "x-khronos": values["khronos"],
        "x-argus": values["argus"], "x-gorgon": values["gorgon"],
        "x-helios": values["helios"], "x-medusa": values["medusa"],
    }
    if data:
        signs["x-ss-stub"] = _json_body_md5(data, data_type)
    result_headers = {str(key).lower(): str(value) for key, value in header.items()}
    result_headers.update(signs)
    if devices.get("ua"):
        result_headers["user-agent"] = str(devices["ua"])
    result_headers["x-tt-dt"] = str(devices.get("x_tt_dt", ""))
    return result_headers, encrypted_url

def _device_config(config: Mapping[str, Any]) -> dict[str, str]:
    device_id = _text(config.get("device_id"))
    install_id = _text(config.get("install_id"))
    if not device_id or not install_id:
        raise HongguoPluginError("缺少红果 device_id/install_id 配置")
    return {
        "device_id": device_id, "iid": install_id, "install_id": install_id,
        "device_brand": "Redmi", "device_model": "25053RT47C", "device_type": "25053RT47C",
        "device_manufacturer": "Xiaomi", "os_version": "16", "version_name": "7.1.3.32",
        "x_tt_dt": _text(config.get("x_tt_dt")),
        "sec_device_token": _text(config.get("sec_device_token")),
        "device_sec_device_token": _text(config.get("device_sec_device_token")),
        "ua": APP_UA,
    }

def _video_model(video_id: str, config: Mapping[str, Any]) -> dict[str, Any]:
    devices = _device_config(config)
    params = {
        "iid": devices["install_id"],
        "device_id": devices["device_id"],
        "ac": "wifi",
        "channel": "update_64",
        "aid": "8662",
        "app_name": "novelread",
        "version_code": "71332",
        "version_name": "7.1.3.32",
        "device_platform": "android",
        "os": "android",
        "ssmix": "a",
        "device_type": "25053RT47C",
        "device_brand": "Redmi",
        "language": "zh",
        "os_api": "36",
        "os_version": "16",
        "manifest_version_code": "71332",
        "resolution": "1280*2772",
        "dpi": "520",
        "update_version_code": "71332",
        "host_abi": "arm64-v8a",
        "dragon_device_type": "phone",
        "pv_player": "71332",
        "compliance_status": "0",
        "need_personal_recommend": "1",
        "player_so_load": "1",
        "is_android_pad_screen": "0",
    }
    payload = {
        "biz_param": {
            "detail_page_version": 0,
            "device_level": 3,
            "disable_digg_stat": False,
            "need_all_video_definition": True,
            "need_mp4_align": False,
            "use_os_player": False,
            "use_server_dns": False,
            "video_platform": 1024,
        },
        "mixed_video_id_map": {"1004": [video_id]},
    }
    request_headers = {
        "User-Agent": APP_UA,
        "Accept": "application/json; charset=utf-8,application/x-protobuf",
        "Content-Type": "application/json; charset=UTF-8",
        "x-xs-from-web": "0",
        "x-ss-req-ticket": str(int(time.time() * 1000)),
        "x-tt-request-tag": "t=0;n=0",
        "sdk-version": "2",
        "passport-sdk-version": "50561",
        "x-vc-bdturing-sdk-version": "3.7.2.cn",
    }
    if devices.get("cookie"):
        request_headers["Cookie"] = devices["cookie"]
    signed_headers, signed_url = _core_sixgod(
        VIDEO_URL,
        params,
        devices,
        payload,
        request_headers,
    )
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    response = requests.post(
        signed_url,
        headers=signed_headers,
        data=body,
        timeout=30,
    )
    response_data = _json_response(response)
    data = response_data.get("data") or {}
    if not isinstance(data, Mapping):
        raise HongguoPluginError("video_model 数据为空")
    entry: Any = data.get(video_id)
    if entry is None:
        for value in data.values():
            if isinstance(value, Mapping):
                entry = value
                break
            if isinstance(value, list) and value and isinstance(value[0], Mapping):
                entry = value[0]
                break
    if not isinstance(entry, Mapping):
        entry = data
    raw_model = entry.get("video_model") if isinstance(entry, Mapping) else None
    if raw_model is None:
        raw_model = data.get("video_model")
    if isinstance(raw_model, str):
        try:
            raw_model = json.loads(raw_model)
        except ValueError as exc:
            raise HongguoPluginError("video_model JSON 无效") from exc
    if not isinstance(raw_model, Mapping):
        raise HongguoPluginError("video_model 为空")
    return dict(raw_model)

def _video_list_from_model(model: Mapping[str, Any]) -> Any:
    for key in ("video_list", "dynamic_video_list"):
        if model.get(key) is not None:
            return model[key]
    dynamic = model.get("dynamic_video")
    if isinstance(dynamic, Mapping):
        for key in ("dynamic_video_list", "video_list", "list"):
            if dynamic.get(key) is not None:
                return dynamic[key]
    video_info = model.get("video_info")
    if isinstance(video_info, Mapping):
        data = video_info.get("data")
        if isinstance(data, Mapping):
            return _video_list_from_model(data)
    data = model.get("data")
    if isinstance(data, Mapping):
        return _video_list_from_model(data)
    return None


_QUALITY_ORDER = ("2160", "1440", "1080", "720", "576", "540", "480", "360")

def _int(value: Any) -> int:
    match = re.search(r"\d+", _text(value))
    return int(match.group()) if match else 0

def _quality(value: Any) -> str:
    text = _text(value).lower()
    match = re.search(r"(2160|1440|1080|720|576|540|480|360)", text)
    return match.group(1) if match else "1080"

def _select_quality(video_list: Any, wanted: str = "1080") -> tuple[str, dict[str, Any]]:
    def rows_from(value: Any, hinted_quality: str = "") -> list[tuple[str, dict[str, Any]]]:
        if isinstance(value, list):
            result: list[tuple[str, dict[str, Any]]] = []
            for item in value:
                result.extend(rows_from(item, hinted_quality))
            return result
        if not isinstance(value, Mapping):
            return []
        if any(
            key in value
            for key in (
                "main_url",
                "backup_url",
                "backup_url_1",
                "play_addr",
                "spade_a",
                "encrypt_info",
            )
        ):
            return [(hinted_quality, dict(value))]
        result = []
        for key, item in value.items():
            if key in {"dynamic_video", "video_info", "data"} and isinstance(item, Mapping):
                result.extend(rows_from(item, hinted_quality))
                continue
            if key in {"video_list", "dynamic_video_list", "list"}:
                result.extend(rows_from(item, _quality(key)))
                continue
            if isinstance(item, (Mapping, list)):
                result.extend(rows_from(item, _quality(key)))
        return result

    candidates = rows_from(video_list)
    rows: dict[str, dict[str, Any]] = {}
    for hinted_quality, item in candidates:
        definition = _quality(
            item.get("definition")
            or item.get("vheight")
            or (item.get("video_meta") or {}).get("definition")
            or hinted_quality
        )
        rows[definition] = item
    if not rows:
        raise HongguoPluginError("播放模型没有清晰度")
    requested = _quality(wanted)
    order = [requested] + [item for item in _QUALITY_ORDER if item != requested]
    for definition in order:
        if definition in rows:
            return definition, rows[definition]
    definition = max(rows, key=lambda item: _int(item))
    return definition, rows[definition]

def _fallback_api_value(value: Any) -> str:
    if isinstance(value, Mapping):
        return _first(
            value.get("fallback_api"),
            value.get("url"),
            value.get("api"),
            value.get("data"),
        )
    if isinstance(value, (list, tuple)):
        for item in value:
            result = _fallback_api_value(item)
            if result:
                return result
        return ""
    text = _text(value)
    if text.startswith("{"):
        try:
            decoded = json.loads(text)
        except ValueError:
            decoded = {}
        if decoded:
            return _fallback_api_value(decoded)
    return text if len(text) > 10 else ""

def _decrypt_spade_url(value: str, key_seed: bytes) -> str:
    raw = _b64(value)
    if len(raw) < 20 or raw[0] != 0xA8 or raw[2:4] != b"\x01\x00":
        raise HongguoPluginError("spade URL 头无效")
    cipher_data = raw[4 : len(raw) - (len(raw) - 4) % 16]
    if not cipher_data:
        raise HongguoPluginError("spade URL 密文为空")
    constants = bytes.fromhex(
        "4dd4c2e6b83162090e52b3c7a6733ba4"
        "1cb2462b829ab58a196b39db57177524"
        "f49baf7f08e8d68d26a72e37c1a95a2f"
        "1f05a51892aef2949732b62a38aadd58"
    )
    first = hashlib.sha512(key_seed).digest()
    second = hashlib.sha512(first + constants).digest()
    plaintext = _aes_cbc_decrypt(second[:16], second[16:32], cipher_data)
    if plaintext:
        padding = plaintext[-1]
        if 1 <= padding <= 16 and padding <= len(plaintext):
            plaintext = plaintext[:-padding]
    return plaintext.rstrip(b"\0").decode("utf-8", errors="replace")

def _parse_ref(value: str, prefix: str) -> str:
    if not value.startswith(prefix):
        raise HongguoPluginError("播放引用无效")
    raw = value[len(prefix) :]
    if not raw or not _VIDEO_ID.fullmatch(raw):
        raise HongguoPluginError("播放引用格式无效")
    return raw

def _key_seed_from_model(model: Mapping[str, Any]) -> bytes:
    value = _text(model.get("key_seed"))
    if value:
        return _b64(value)
    for key in ("dynamic_video", "video_info", "data"):
        nested = model.get(key)
        if isinstance(nested, Mapping):
            result = _key_seed_from_model(nested)
            if result:
                return result
    return b""
def _page(url):
    last_err = None
    for attempt in range(3):
        try:
            r = requests.get(
                url,
                headers={
                    "User-Agent": UA,
                    "Accept-Language": "zh-CN,zh;q=0.9",
                    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
                    "Cache-Control": "no-cache",
                },
                timeout=30,
            )
            r.raise_for_status()
            r.encoding = r.encoding or "utf-8"
            if not r.text or "_ROUTER_DATA" not in r.text:
                raise RuntimeError("empty or invalid page")
            return r.text
        except Exception as err:
            last_err = err
            try:
                time.sleep(0.6 * (attempt + 1))
            except Exception:
                pass
    raise RuntimeError("page fetch failed: %s" % last_err)

def _data(url):
    html = _page(url)
    m = re.search(r"(?:window\.)?_ROUTER_DATA\s*=\s*", html)
    if not m:
        return {}
    try:
        return json.JSONDecoder().raw_decode(html[m.end():])[0]
    except (ValueError, TypeError):
        return {}

def _item(x):
    x = x or {}
    vd = x.get("video_data") if isinstance(x.get("video_data"), dict) else x
    sid = str(
        vd.get("series_id")
        or x.get("series_id")
        or x.get("keyword")
        or vd.get("keyword")
        or ""
    )
    name = str(
        vd.get("series_title")
        or vd.get("series_name")
        or x.get("series_name")
        or x.get("name")
        or "未命名"
    )
    count = vd.get("episode_cnt") or x.get("episode_cnt") or 0
    pic = str(vd.get("series_cover") or x.get("series_cover") or "")
    intro = str(vd.get("series_intro") or x.get("series_intro") or "")
    return {
        "vod_id": sid,
        "vod_name": name,
        "vod_pic": pic,
        "vod_remarks": ("全%s集" % count) if count else "",
        "vod_content": intro,
    }

def _cat_item(x):
    return _item(x)

def _filter_group(key, name, values):
    return {"key": key, "name": name, "value": [{"n": n, "v": v} for n, v in values]}


def _search_loader(key: str) -> dict:
    """拉取搜索页 loaderData，失败重试。"""
    last = {}
    for attempt in range(3):
        try:
            data = _data(SITE + "/search/" + quote(str(key), safe=""))
            page = (data.get("loaderData") or {}).get("search_(keyword)/page") or {}
            if page.get("searchList"):
                return page
            last = page or last
        except Exception:
            pass
        try:
            time.sleep(0.5 * (attempt + 1))
        except Exception:
            pass
    return last


def _search_by_keywords(keywords, page: int) -> dict:
    """多关键词轮换：第 N 页用第 N 个关键词（循环），避免搜索无法翻页。"""
    page = max(1, int(page or 1))
    kws = [k for k in (keywords or []) if k]
    if not kws:
        kws = ["短剧"]
    key = kws[(page - 1) % len(kws)]
    p = _search_loader(key)
    rows = p.get("searchList") or []
    # 去重空 id
    out = []
    seen = set()
    for x in rows:
        it = _item(x)
        vid = str(it.get("vod_id") or "")
        if not vid or vid in seen:
            continue
        seen.add(vid)
        out.append(it)
    # 虚拟页数：关键词数；若站点有 totalCount 也参考
    total = int(p.get("totalCount") or 0)
    pagecount = max(len(kws), (total + 9) // 10 if total else len(kws))
    return {
        "page": page,
        "pagecount": max(1, pagecount),
        "limit": len(out),
        "total": total or len(out) * pagecount,
        "list": out,
    }


def _category_loader(page: int, q: dict) -> dict:
    """分类页带重试；page=1 偶发空列表时多试几次。"""
    page = max(1, int(page or 1))
    q = dict(q or {})
    if page > 1:
        q["page"] = str(page)
    last = {}
    for attempt in range(3):
        try:
            data = _data(SITE + "/category?" + urlencode(q))
            p = (data.get("loaderData") or {}).get("category_$") or (data.get("loaderData") or {}).get("category_page") or {}
            rows = p.get("recommendList") or []
            if rows or page > 1:
                return p
            last = p or last
        except Exception:
            pass
        try:
            time.sleep(0.5 * (attempt + 1))
        except Exception:
            pass
    return last

class _HongguoSpider(_BaseSpider):
    def __init__(self):
        self.device_id = str(random.randint(10**17, 10**18 - 1))
        self.install_id = str(random.randint(10**17, 10**18 - 1))

    def getName(self):
        return "红果短剧"

    def isVideoFormat(self, url):
        u = str(url or "").lower()
        return (".mp4" in u) or ("video_mp4" in u) or ("m3u8" in u) or ("mime_type=video" in u) or ("qznovelvod" in u)

    def manualVideoCheck(self):
        return False

    def getDependence(self):
        return []

    def download(self, path, url):
        return ""

    def liveContent(self):
        return {}

    def isVPAYard(self, flag):
        return False

    def action(self, action):
        return ""

    def init(self, extend=""):
        # 每次源实例使用随机合法设备标识；不依赖用户私有配置。
        try:
            _hg_cache_cleanup(False)
        except Exception:
            pass
        return None

    def destroy(self):
        try:
            _hg_cache_cleanup(False)
        except Exception:
            pass

    def homeContent(self, filter):
        meta = self.home_meta()
        class_list = meta["class"]
        filter_dict = meta["filters"]
        home_list = []
        try:
            data = _data(SITE + "/")
            page = (data.get("loaderData") or {}).get("page") or {}
            seen = set()
            for sec in (page.get("homeSections") or []):
                for v in (sec.get("video_list") or []):
                    it = _item(v)
                    vid = str(it.get("vod_id") or "")
                    if vid and vid not in seen:
                        seen.add(vid)
                        home_list.append(it)
        except Exception:
            home_list = []
        return {"class": class_list, "filters": filter_dict, "list": home_list[:40]}

    def home_meta(self):
        """仅返回分类与筛选（无网络请求），供聚合入口快速构建标签。"""
        class_list = [
            {"type_id": "all", "type_name": "短剧"},
            {"type_id": "ai_comic", "type_name": "AI漫剧"},
            {"type_id": "latest", "type_name": "最新"},
            {"type_id": "hot", "type_name": "最热"},
            {"type_id": "male", "type_name": "男频"},
            {"type_id": "female", "type_name": "女频"},
        ]
        groups = [
            {"key": "topic", "name": "主题", "value": [
                {"n": "全部", "v": ""}, {"n": "现言", "v": "cate_1021"}, {"n": "女性成长", "v": "cate_1048"},
                {"n": "脑洞", "v": "cate_262"}, {"n": "奇幻", "v": "cate_1020"}, {"n": "玄幻", "v": "cate_1019"},
                {"n": "古言", "v": "cate_439"}, {"n": "战神", "v": "cate_1038"}, {"n": "宫斗", "v": "cate_246"},
                {"n": "仙侠", "v": "cate_1013"}, {"n": "权谋", "v": "cate_1047"}, {"n": "种田", "v": "cate_1180"},
                {"n": "年代爱情", "v": "cate_1022"}, {"n": "悬疑", "v": "cate_165"}, {"n": "喜剧", "v": "cate_303"},
                {"n": "青春", "v": "cate_297"}, {"n": "志怪", "v": "cate_1027"}, {"n": "民国爱情", "v": "cate_1025"},
                {"n": "灵异", "v": "cate_751"}, {"n": "家国情怀", "v": "cate_1235"}, {"n": "法律", "v": "cate_1136"},
                {"n": "刑侦", "v": "cate_1148"}, {"n": "抗战", "v": "cate_504"}, {"n": "武侠", "v": "cate_1172"},
                {"n": "民国传奇", "v": "cate_1240"}, {"n": "求生", "v": "cate_1168"}, {"n": "动作", "v": "cate_302"},
                {"n": "科幻", "v": "cate_1092"}, {"n": "恐怖", "v": "cate_1219"}, {"n": "商战", "v": "cate_1225"},
            ]},
            {"key": "background", "name": "背景", "value": [
                {"n": "全部", "v": ""}, {"n": "现代", "v": "cate_757"}, {"n": "都市", "v": "cate_1"},
                {"n": "古代", "v": "cate_758"}, {"n": "乡村", "v": "cate_11"}, {"n": "年代", "v": "cate_79"},
                {"n": "架空", "v": "cate_452"}, {"n": "职场", "v": "cate_127"}, {"n": "民国", "v": "cate_390"},
                {"n": "校园", "v": "cate_4"}, {"n": "宫廷", "v": "cate_1153"}, {"n": "荒岛", "v": "cate_1162"},
            ]},
            {"key": "setting", "name": "设定", "value": [
                {"n": "全部", "v": ""}, {"n": "打脸虐渣", "v": "cate_1051"}, {"n": "大男主", "v": "cate_1207"},
                {"n": "大女主", "v": "cate_760"}, {"n": "马甲", "v": "cate_266"}, {"n": "重生", "v": "cate_36"},
                {"n": "穿越", "v": "cate_37"}, {"n": "系统", "v": "cate_19"}, {"n": "先婚后爱", "v": "cate_265"},
                {"n": "家长里短", "v": "cate_862"}, {"n": "小人物", "v": "cate_1010"}, {"n": "破镜重圆", "v": "cate_475"},
                {"n": "神豪", "v": "cate_20"}, {"n": "豪门", "v": "cate_936"}, {"n": "强者回归", "v": "cate_1045"},
                {"n": "异能", "v": "cate_598"}, {"n": "虐恋", "v": "cate_1008"}, {"n": "传承觉醒", "v": "cate_1007"},
                {"n": "医生", "v": "cate_487"}, {"n": "强强联合", "v": "cate_1049"}, {"n": "赘婿逆袭", "v": "cate_1044"},
                {"n": "甜宠", "v": "cate_96"}, {"n": "娱乐圈", "v": "cate_43"}, {"n": "神医", "v": "cate_26"},
                {"n": "青梅竹马", "v": "cate_387"}, {"n": "姐弟恋", "v": "cate_762"}, {"n": "玄学", "v": "cate_929"},
                {"n": "追妻火葬场", "v": "cate_616"}, {"n": "业界精英", "v": "cate_1293"}, {"n": "一见钟情", "v": "cate_477"},
                {"n": "福宝", "v": "cate_1291"}, {"n": "捞偏门", "v": "cate_1287"}, {"n": "反派主角", "v": "cate_1042"},
                {"n": "萌宠", "v": "cate_428"}, {"n": "双向救赎", "v": "cate_1200"}, {"n": "方言", "v": "cate_1255"},
                {"n": "白月光", "v": "cate_615"}, {"n": "灵魂互换", "v": "cate_831"}, {"n": "病娇", "v": "cate_380"},
                {"n": "暴富", "v": "cate_1191"}, {"n": "黑道", "v": "cate_826"}, {"n": "丧尸", "v": "cate_582"},
                {"n": "特种兵", "v": "cate_375"},
            ]},
            {"key": "time", "name": "时间", "value": [
                {"n": "全部", "v": ""}, {"n": "7天内上新", "v": "1"}, {"n": "14天内上新", "v": "2"},
                {"n": "30天内上新", "v": "3"}, {"n": "90天内上新", "v": "4"},
            ]},
        ]
        filter_dict = {c["type_id"]: groups for c in class_list}
        return {"class": class_list, "filters": filter_dict}
    def homeVideoContent(self):
        try:
            data = _data(SITE + "/")
            page = (data.get("loaderData") or {}).get("page") or {}
            out = []
            seen = set()
            for sec in (page.get("homeSections") or []):
                for v in (sec.get("video_list") or []):
                    it = _item(v)
                    vid = str(it.get("vod_id") or "")
                    if vid and vid not in seen:
                        seen.add(vid)
                        out.append(it)
            return {"list": out[:60]}
        except Exception:
            return {"list": []}

    def _query(self, pg, q=None):
        try:
            pg = max(1, int(pg))
        except (TypeError, ValueError):
            pg = 1
        if q is None:
            q = {"tab": "1", "sort_type": "1"}
        return _category_loader(pg, q)
    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = max(1, int(pg))
        except (TypeError, ValueError):
            page = 1
        # 漫剧 / AI漫剧：官网搜索不支持真翻页，多关键词轮换
        if tid in ("comic", "manju", "漫剧"):
            try:
                p = _category_loader(page, {"tab": "2", "sort_type": "1"})
                rows = p.get("recommendList") or []
                if rows:
                    page_data = p.get("pagination") or {}
                    return {
                        "page": page,
                        "pagecount": int(page_data.get("totalPages") or 1),
                        "limit": len(rows),
                        "total": int(page_data.get("total") or len(rows)),
                        "list": [_cat_item(x) for x in rows],
                    }
            except Exception:
                pass
            return _search_by_keywords(_MANJU_KEYWORDS, page)
        if tid in ("ai_comic", "ai_manju", "AI漫剧", "ai漫剧"):
            return _search_by_keywords(_AI_MANJU_KEYWORDS, page)
        q = {"tab": "1", "sort_type": "1"}
        if tid == "latest":
            q["sort_type"] = "2"
        elif tid == "hot":
            q["sort_type"] = "1"
        elif tid == "male":
            q["gender"] = "1"
        elif tid == "female":
            q["gender"] = "2"
        if isinstance(extend, str) and extend:
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if isinstance(extend, dict):
            for k, v in extend.items():
                if v and str(v) not in ("", "all", "0"):
                    q[k] = str(v)
        p = _category_loader(page, q)
        rows = p.get("recommendList") or []
        page_data = p.get("pagination") or {}
        return {
            "page": page,
            "pagecount": int(page_data.get("totalPages") or 1),
            "limit": len(rows),
            "total": int(page_data.get("total") or len(rows)),
            "list": [_cat_item(x) for x in rows],
        }
    def searchContent(self, key, quick=False, pg="1"):
        try:
            page = max(1, int(pg))
        except (TypeError, ValueError):
            page = 1
        key = str(key or "").strip() or "短剧"
        # AI/漫剧相关搜索也走关键词轮换，提升翻页体验
        low = key.lower()
        if key in ("AI漫剧", "ai漫剧") or "ai漫" in low:
            return _search_by_keywords(_AI_MANJU_KEYWORDS, page)
        if key in ("漫剧", "动漫短剧"):
            return _search_by_keywords(_MANJU_KEYWORDS, page)

        p = _search_loader(key)
        rows = p.get("searchList") or []
        total = int(p.get("totalCount") or len(rows) or 0)
        # 官网搜索基本只有一页有效结果
        return {
            "page": page,
            "pagecount": 1 if not total else max(1, min(10, (total + 9) // 10)),
            "limit": len(rows),
            "total": total or len(rows),
            "list": [_item(x) for x in rows],
        }


    def detailContent(self, ids):
        sid = str(ids[0] if isinstance(ids, (list, tuple)) else ids)
        sid = sid.replace("hg-series-v1:", "")
        p = ((_data(SITE + "/detail?series_id=" + quote(sid, safe="")).get("loaderData") or {}).get("detail_page") or {})
        s = p.get("seriesDetail") or {}
        vids = s.get("vid_list") or []
        actors = [str(x.get("nickname")) for x in (s.get("celebrities") or []) if isinstance(x, dict) and x.get("nickname")]
        play_from = []
        play_url = []
        for q, line_name in _HG_QUALITY_LINES:
            eps = "#".join(
                "第%d集%s%s%s%s" % (i + 1, "$", EPISODE_PREFIX, q + ":", str(v))
                for i, v in enumerate(vids)
            )
            play_from.append(line_name)
            play_url.append(eps)
        return {"list": [{"vod_id": sid, "vod_name": str(s.get("series_name") or ""), "vod_pic": str(s.get("series_cover") or ""), "vod_year": "", "vod_area": "", "vod_director": "", "vod_actor": ",".join(actors), "vod_content": str(s.get("series_intro") or ""), "vod_remarks": str(s.get("episode_right_text") or ""), "vod_play_from": "$$$".join(play_from), "vod_play_url": "$$$".join(play_url)}]}
    def playerContent(self, flag, id, vipFlags=None):
        # 从线路名（flag，如“红果超清/红果高清”）与集 token 双路解析清晰度。
        # token 已是 'hg-episode-v1:<q>:<vid>'，flag 用于旧壳只传线路名时兜底。
        token_q, vid = _split_episode_token(id)
        line_q = "1080"
        for name_key, candidate_q in _QUALITY_LINE_NAME_TO_Q.items():
            if name_key in str(flag or ""):
                line_q = candidate_q
                break
        q = line_q if token_q == "1080" and str(flag) else token_q
        q = q if q in _QUALITY_LINE_NAME_TO_Q else "1080"
        if not str(vid).isdigit():
            return {
                "parse": 1,
                "jx": 0,
                "playUrl": "",
                "url": SITE + "/",
                "header": {"User-Agent": UA},
            }
        # OK影视 / 多数壳：必须走 getProxyUrl（通常已带 do=py），不要覆盖 do
        proxy = ""
        try:
            if hasattr(self, "getProxyUrl"):
                proxy = (self.getProxyUrl() or "").strip()
        except Exception:
            proxy = ""
        if proxy:
            sep = "&" if "?" in proxy else "?"
            # 保留壳自带的 do=py，只追加业务参数与清晰度线路
            url = proxy + sep + urlencode(
                {
                    "vid": vid,
                    "q": q,
                    "hg": "cenc",
                    "did": self.device_id or "",
                    "iid": self.install_id or "",
                }
            )
            return {
                "parse": 0,
                "jx": 0,
                "playUrl": "",
                "url": url,
                "header": {
                    "User-Agent": MEDIA_UA,
                    "Referer": "https://novel.snssdk.com/",
                },
            }
        # 备用：本机 Range 流（FongMi 更友好）
        try:
            port = _start_stream_server()
        except Exception:
            port = 0
        if port:
            query = urlencode(
                {
                    "vid": vid,
                    "q": q,
                    "did": self.device_id or "",
                    "iid": self.install_id or "",
                }
            )
            return {
                "parse": 0,
                "jx": 0,
                "playUrl": "",
                "url": "http://127.0.0.1:%d/hg.mp4?%s" % (port, query),
                "header": {"User-Agent": UA},
            }
        return {
            "parse": 1,
            "jx": 0,
            "playUrl": "",
            "url": SITE + "/",
            "header": {"User-Agent": UA},
        }


    def proxy(self, param):
        """部分壳调用 proxy 而不是 localProxy。"""
        return self.localProxy(param)

    def localProxy(self, param):
        """壳本地代理：优先读缓存；无原生 AES 时避免一上来就解 1080 整集导致超时失败。"""
        import traceback
        param = param or {}
        vid = str(
            param.get("vid")
            or param.get("id")
            or param.get("mediaId")
            or ""
        ).strip()
        if not vid or not str(vid).isdigit():
            for _key, value in param.items():
                text = str(value or "").strip()
                if text.isdigit() and len(text) >= 10:
                    vid = text
                    break
        if not vid:
            return [400, "text/plain; charset=utf-8", b"missing vid"]

        try:
            cfg = {
                "device_id": str(param.get("did") or self.device_id or ""),
                "install_id": str(param.get("iid") or self.install_id or ""),
            }
            user_q = str(param.get("q") or param.get("quality") or "").strip()
            # 有原生 AES：优先 1080；纯 Python AES 很慢：先 720 保证能播，再尝试更高
            if user_q:
                order = [user_q, "1080", "720", "480", "360"]
            elif _aes_is_fast():
                order = ["1080", "720", "480", "360"]
            else:
                order = ["720", "480", "1080", "360"]
            # dedupe
            seen_q = set()
            quals = []
            for q in order:
                if q and q not in seen_q:
                    seen_q.add(q)
                    quals.append(q)

            # 缓存命中直接返回。用户指定线路清晰度(user_q)时，只认该清晰度缓存，
            # 不能回退命中其它清晰度缓存（否则请求480会拿到360内容）。
            if user_q:
                primary = [user_q]
            else:
                primary = quals
            for q in primary:
                cached = _hg_cache_get(vid, q)
                if cached:
                    return [200, "video/mp4", cached]

            model = _video_model(vid, cfg)
            rows = _video_list_from_model(model)
            if not rows:
                return [500, "text/plain; charset=utf-8", b"empty video list"]

            last_err = None
            for wanted in quals:
                try:
                    # 再查一次该清晰度缓存（model 解析后）
                    cached = _hg_cache_get(vid, wanted)
                    if cached:
                        return [200, "video/mp4", cached]

                    _, item = _select_quality(rows, wanted)
                    url = _media_url(item)
                    spade = _spade_value(item)
                    if not url or not spade:
                        last_err = "missing url/spade q=%s" % wanted
                        continue
                    try:
                        key_seed = _key_seed_from_model(model)
                        if key_seed:
                            url = _decrypt_spade_url(url, key_seed)
                    except Exception:
                        pass

                    # 下载超时：纯 AES 环境更短，避免壳端空等后失败
                    dl_timeout = 150 if _aes_is_fast() else 90
                    media_headers = {
                        "User-Agent": MEDIA_UA,
                        "Referer": "https://novel.snssdk.com/",
                    }
                    try:
                        body = _multi_download(
                            url,
                            headers=media_headers,
                            timeout=dl_timeout,
                            workers=4 if _aes_is_fast() else 3,
                        )
                    except Exception as dl_err:
                        last_err = "download failed q=%s err=%s" % (wanted, dl_err)
                        continue
                    if not body:
                        last_err = "empty body q=%s" % wanted
                        continue

                    # 纯 AES 且体积过大时跳过超大 1080，减少必超时
                    if (not _aes_is_fast()) and wanted in ("1080", "4k") and len(body) > 45 * 1024 * 1024:
                        last_err = "skip large %s without native AES size=%s" % (wanted, len(body))
                        continue

                    plain = decrypt_mp4_cenc(body, derive_content_key(spade))
                    if len(plain) < 64 or (b"ftyp" not in plain[:64] and b"moov" not in plain[:4096]):
                        last_err = "bad mp4 after decrypt q=%s" % wanted
                        continue
                    try:
                        _hg_cache_put(vid, wanted, plain)
                    except Exception:
                        pass
                    return [200, "video/mp4", plain]
                except Exception as one_err:
                    last_err = "%s q=%s" % (one_err, wanted)
                    continue

            msg = "hg localProxy failed: %s" % last_err
            return [500, "text/plain; charset=utf-8", msg.encode("utf-8")]
        except Exception as exc:
            msg = "hg localProxy failed: %s\n%s" % (exc, traceback.format_exc())
            return [500, "text/plain; charset=utf-8", msg.encode("utf-8")]

# ############################################################
# ENGINE AG · 聚合短剧[短] (原 _______.js → Python 移植)
#   15 平台: 河马/七猫/星芽/围观/百度/薏米/牛牛/山海/好看/西饭/星星/五一/爽爽/喜福/五五
# ############################################################

# ---- 由 extract.py 从原 JS 自动抽取的大字面量 ----
AGG_KEYS = 'd3dGiJc651gSQ8w1'

AGG_CHAR_MAP = {'+': 'P', '/': 'X', '0': 'M', '1': 'U', '2': 'l', '3': 'E', '4': 'r', '5': 'Y', '6': 'W', '7': 'b', '8': 'd', '9': 'J', 'A': '9', 'B': 's', 'C': 'a', 'D': 'I', 'E': '0', 'F': 'o', 'G': 'y', 'H': '_', 'I': 'H', 'J': 'G', 'K': 'i', 'L': 't', 'M': 'g', 'N': 'N', 'O': 'A', 'P': '8', 'Q': 'F', 'R': 'k', 'S': '3', 'T': 'h', 'U': 'f', 'V': 'R', 'W': 'q', 'X': 'C', 'Y': '4', 'Z': 'p', 'a': 'm', 'b': 'B', 'c': 'O', 'd': 'u', 'e': 'c', 'f': '6', 'g': 'K', 'h': 'x', 'i': '5', 'j': 'T', 'k': '-', 'l': '2', 'm': 'z', 'n': 'S', 'o': 'Z', 'p': '1', 'q': 'V', 'r': 'v', 's': 'j', 't': 'Q', 'u': '7', 'v': 'D', 'w': 'w', 'x': 'n', 'y': 'L', 'z': 'e'}

HM_STATIC_DATAS = 'e5f22c6e2c82fe001738cb9ce4696eab0556d064a55aef402e0fbe6b29a083f6538e4567de38e67de2071a49d9751526bfba45314e1fd4702b11c76ab9a3b5f873262854ba66e6715ed51364dbc6ee62c7180e047fcbcdbfd49874fc8f28674b16d90ca71a02de76c70598e0b75e647c37c2c19287e49be5f2a259d727dfc4df3d28802388bf3c356576b342e17e30a2ab74859263dba4d1c8eba79990d22d60d60927fdacb2addf2f0eaadd8887585ca2eb87f603faf0c207dda18cf67dc25b2199d303baff9e6605b3314a7d2631f62864f48619daceb9452f2b7b0667773553741856df030cca68af3c57810f983d452bb428ef5fc32206aef4865ae06c629bee7f5135547304acc7ef4e7c6df887308f2e79c493fd2ee03488722861b5bb51b09cb8911dfc92c288d94e601c066d2f9d612ad2c8d4eeb4920b1d44aff3e13fd75229b857f64925df1cf12f75a00d438c422ec1726462b915903f1dd1f4bb7cdf82cc15a6d507f80c789903e710f39a62aef073f3f93a6c681e75d295428aa290d7e98f82e7e9ad6e2b23d9086dfe8c63c5d8550b13fd61a77291473a8bdd43c7c2639f264be69d9d07f0585de4342a399275a64e7d1d4400b8ed4421a2f289f622e40cdd1cfc916a0b9ce747c924ac33e32d24b91ed5d64772d6ad6896412f52724006eabf12aaecfd6e81dad432c7b3800bbf793a1c375e3e7b4fb3b097724b5fc88a8c9bcf3dbc10cbdb252965'

YIMI_PRIVATE_KEY = '-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDwCPsMptVn80Im4VVfJ2uAkjs7NpJzzsyGxleK1uN9ux/KTiY2o8kiXcRIcAYVChfdX4ywUs0jrjh8iTcC91r6qgeBaDS8wWsL5bZrn7O/8sqq2hbizV4AvvsqhxVJzRUJZjbNOcMZOPJoeL5K4U4YsiOyV8a9lt5C6zEC4Qy0xjscvOTGyVTqtWeJedEedXtiKLQxAiy6OKJxyHQqdwMHUfAgAbLzAHcVpg1RSXwud+5vtTJNXOXT98FHoFDcRIEcHiiqfU9dskzAhG2nPbFujO+YFq9tZBrWmrhPaXcHfXZqtEYePM4vuvMYjhmANdG4Ehl6pN9nuEaLZ+L35/3nAgMBAAECggEBAOe+M+s2E2ll8WMqQEs6+s5J4Ee9201Vxh8E1TYlW8Ni60FdjAVKwgCc+Mla5nRfp0TCYElH1+hv5vdNXsBNYhgKGm701Z27O4dkA2gK6vcSCFtFbb0Qu4YK3OFlQ8dZ6cqGVbhz4Qmz8k2s7UPMHKM5Mb+YgTc/tlxzR4FZF/RaY8MDpv6iMcXPY27xJzZAV1jROCXjZTZNYbgjsKDAbthRDkjMyuKCIdq7rAHrEyFSx3n7/uxnZYh42bXzWyyWudbkAJoq1ZYx+NyYj5TsN/WNoYbCPcX0Ko+CNnpkC/6qtQbHrBiMprnld67qdLCVhWpmOBYukXVPwFMJjOFlYKkCgYEA+WDh3LpitYSO6hn7mhnbqEQba13cutbJW9RQa0BjGf1OGXdqXpimcWK7viZYAKhLlyGWQmoWduDq4bjSRx7ZxY8pMtpIUWoVkKItD7D2yvmYN1guHNRpHlUIAsSH3HGwQIeXy36hJcB5gC+3XgRVPz/juTMWJDC0usECNFz17bsCgYEA9miWi6JPnZ1ffQzAyE+P6vGC/Vrl7Uyr9gqxI/OkZa8bUqfZtGo5UDGSaGRUsoTsYiEJ8m5blPY0X4xr5x1kO6rfk0gHxn1OXlCP42yT2+CqQvjNO2DHOnWNryKjmAqaAITbmC2lgj0PiiPO32ZT3aXTOgwxTKbFP3LBDmwA18UCgYAQuEgsbmqz1OFoHLnbySQLEhXsiuyDsmbpu0BxEG4UjgEwf+sn0IBIVeBUjWmVEbOPvHbAmTBMZCQbYjLnBdCACGswt6Xln4E2o0j2Jl1Fmpp0C3t7/1nU6MqStO6O/yhcCztIL4NKbq82wvw+V3gHt5bjEePIJWPYqZwmOp1ahQKBgCqfHKs6gBr7RbETq6T6XiJ9c/Lu7iaFxJjicJGPazhLeaZqcjXKye8dI/36nMvkQh8XJ+lPPXgeviBo4aEwbE4F2HZZVz72HcAin0DvXwQBcHH1J0rGCrAJ9V/91d5OtySv1mwUOTS16yIx3260/HyyWj8ILN7dWfEHoG0mMV8hAoGBAI0KBzR9WfzxNKI4ZqRD9/sN+SH4oxymo2oJ+FnOW7hk1E0EyrsGzIDCrS/f7MPzLJI7F4DULsrU5RIQyouIybZra29Vqe4L8kdIae5O0R4Y2r7gt/yWo4cWnW53Q0f5o7mzV10Dc8ewuT1DyJrt25dMWsGsP8rQ/0pVUBLEf93b\n-----END PRIVATE KEY-----'

AGG_FILTER = {
 "51": [
  {
   "key": "area",
   "name": "分类",
   "value": [
    {
     "n": "全部短剧",
     "v": "0-0-0-0-0-0"
    },
    {
     "n": "男频",
     "v": "0-0-0-1-0-0"
    },
    {
     "n": "女频",
     "v": "0-0-0-2-0-0"
    }
   ]
  }
 ],
 "星星": [
  {
   "key": "area",
   "name": "分类",
   "value": [
    {
     "n": "精选",
     "v": "1287"
    },
    {
     "n": "热门",
     "v": "1288"
    },
    {
     "n": "新剧",
     "v": "1289"
    }
   ]
  }
 ],
 "河马": [
  {
   "key": "area",
   "name": "分类",
   "value": [
    {
     "n": "精选",
     "v": "53@精选"
    },
    {
     "n": "古装",
     "v": "54@古装"
    },
    {
     "n": "重生",
     "v": "55@重生"
    },
    {
     "n": "家庭",
     "v": "56@家庭"
    },
    {
     "n": "恋爱",
     "v": "57@恋爱"
    }
   ]
  }
 ],
 "百度": [
  {
   "key": "class",
   "name": "综合",
   "value": [
    {
     "n": "新剧",
     "v": "新剧"
    },
    {
     "n": "限时免费",
     "v": "限时免费"
    },
    {
     "n": "精选",
     "v": "精选"
    },
    {
     "n": "独播",
     "v": "独播"
    }
   ]
  },
  {
   "key": "area",
   "name": "题材",
   "value": [
    {
     "n": "全部",
     "v": "全部"
    },
    {
     "n": "神医",
     "v": "神医"
    },
    {
     "n": "都市",
     "v": "都市"
    },
    {
     "n": "现代言情",
     "v": "现代言情"
    },
    {
     "n": "异能",
     "v": "异能"
    },
    {
     "n": "逆袭",
     "v": "逆袭"
    },
    {
     "n": "甜宠",
     "v": "甜宠"
    },
    {
     "n": "总裁",
     "v": "总裁"
    },
    {
     "n": "萌宝",
     "v": "萌宝"
    },
    {
     "n": "战神",
     "v": "战神"
    },
    {
     "n": "宫斗宅斗",
     "v": "宫斗宅斗"
    },
    {
     "n": "神豪",
     "v": "神豪"
    },
    {
     "n": "虐恋",
     "v": "虐恋"
    },
    {
     "n": "闪婚",
     "v": "闪婚"
    },
    {
     "n": "玄幻",
     "v": "玄幻"
    },
    {
     "n": "穿越重生",
     "v": "穿越重生"
    },
    {
     "n": "年代",
     "v": "年代"
    },
    {
     "n": "家庭伦理",
     "v": "家庭伦理"
    },
    {
     "n": "古代言情",
     "v": "古代言情"
    },
    {
     "n": "武侠武打",
     "v": "武侠武打"
    },
    {
     "n": "赘婿",
     "v": "赘婿"
    },
    {
     "n": "青春校园",
     "v": "青春校园"
    }
   ]
  }
 ],
 "星芽": [
  {
   "key": "area",
   "name": "分类",
   "value": [
    {
     "n": "剧场",
     "v": "1"
    },
    {
     "n": "热播剧",
     "v": "2"
    },
    {
     "n": "会员专享",
     "v": "8"
    },
    {
     "n": "星选好剧",
     "v": "7"
    },
    {
     "n": "新剧",
     "v": "3"
    },
    {
     "n": "阳光剧场",
     "v": "5"
    }
   ]
  }
 ],
 "西饭": [
  {
   "key": "area",
   "name": "分类",
   "value": [
    {
     "n": "全部",
     "v": ""
    },
    {
     "n": "都市",
     "v": "68@都市"
    },
    {
     "n": "青春",
     "v": "68@青春"
    },
    {
     "n": "现代言情",
     "v": "81@现代言情"
    },
    {
     "n": "豪门",
     "v": "81@豪门"
    },
    {
     "n": "大女主",
     "v": "80@大女主"
    },
    {
     "n": "逆袭",
     "v": "79@逆袭"
    },
    {
     "n": "打脸虐渣",
     "v": "79@打脸虐渣"
    },
    {
     "n": "穿越",
     "v": "81@穿越"
    }
   ]
  }
 ],
 "七猫": [
  {
   "key": "area",
   "name": "分类",
   "value": [
    {
     "n": "全部",
     "v": ""
    },
    {
     "n": "推荐",
     "v": "0"
    },
    {
     "n": "新剧",
     "v": "-1"
    },
    {
     "n": "都市情感",
     "v": "1273"
    },
    {
     "n": "古装",
     "v": "1272"
    },
    {
     "n": "都市",
     "v": "571"
    },
    {
     "n": "玄幻仙侠",
     "v": "1286"
    },
    {
     "n": "奇幻",
     "v": "570"
    },
    {
     "n": "乡村",
     "v": "590"
    },
    {
     "n": "民国",
     "v": "573"
    },
    {
     "n": "年代",
     "v": "572"
    },
    {
     "n": "青春校园",
     "v": "1288"
    },
    {
     "n": "武侠",
     "v": "371"
    },
    {
     "n": "科幻",
     "v": "594"
    },
    {
     "n": "末世",
     "v": "556"
    },
    {
     "n": "二次元",
     "v": "1289"
    },
    {
     "n": "逆袭",
     "v": "400"
    },
    {
     "n": "穿越",
     "v": "373"
    },
    {
     "n": "复仇",
     "v": "795"
    },
    {
     "n": "系统",
     "v": "787"
    },
    {
     "n": "权谋",
     "v": "790"
    },
    {
     "n": "重生",
     "v": "784"
    },
    {
     "n": "女性成长",
     "v": "1294"
    },
    {
     "n": "打脸虐渣",
     "v": "716"
    },
    {
     "n": "闪婚",
     "v": "480"
    },
    {
     "n": "强者回归",
     "v": "402"
    },
    {
     "n": "追妻火葬场",
     "v": "715"
    },
    {
     "n": "家庭",
     "v": "670"
    },
    {
     "n": "马甲",
     "v": "558"
    },
    {
     "n": "职场",
     "v": "724"
    },
    {
     "n": "宫斗",
     "v": "343"
    },
    {
     "n": "高手下山",
     "v": "1299"
    },
    {
     "n": "娱乐明星",
     "v": "1295"
    },
    {
     "n": "异能",
     "v": "727"
    },
    {
     "n": "宅斗",
     "v": "342"
    },
    {
     "n": "替身",
     "v": "712"
    },
    {
     "n": "穿书",
     "v": "338"
    },
    {
     "n": "商战",
     "v": "723"
    },
    {
     "n": "种田经商",
     "v": "1291"
    },
    {
     "n": "伦理",
     "v": "1293"
    },
    {
     "n": "社会话题",
     "v": "1290"
    },
    {
     "n": "致富",
     "v": "492"
    },
    {
     "n": "偷听心声",
     "v": "1258"
    },
    {
     "n": "脑洞",
     "v": "526"
    },
    {
     "n": "豪门总裁",
     "v": "624"
    },
    {
     "n": "萌宝",
     "v": "356"
    },
    {
     "n": "战神",
     "v": "527"
    },
    {
     "n": "真假千金",
     "v": "812"
    },
    {
     "n": "赘婿",
     "v": "36"
    },
    {
     "n": "神医",
     "v": "1269"
    },
    {
     "n": "神豪",
     "v": "37"
    },
    {
     "n": "小人物",
     "v": "1296"
    },
    {
     "n": "团宠",
     "v": "545"
    },
    {
     "n": "欢喜冤家",
     "v": "464"
    },
    {
     "n": "女帝",
     "v": "617"
    },
    {
     "n": "银发",
     "v": "1297"
    },
    {
     "n": "兵王",
     "v": "28"
    },
    {
     "n": "虐恋",
     "v": "16"
    },
    {
     "n": "甜宠",
     "v": "21"
    },
    {
     "n": "悬疑",
     "v": "27"
    },
    {
     "n": "搞笑",
     "v": "793"
    },
    {
     "n": "灵异",
     "v": "1287"
    }
   ]
  }
 ],
 "牛牛": [
  {
   "key": "area",
   "name": "分类",
   "value": [
    {
     "n": "全部",
     "v": ""
    },
    {
     "n": "现言",
     "v": "现言"
    },
    {
     "n": "古言",
     "v": "古言"
    },
    {
     "n": "历史",
     "v": "历史"
    },
    {
     "n": "都市",
     "v": "都市"
    },
    {
     "n": "亲情",
     "v": "亲情"
    },
    {
     "n": "玄幻",
     "v": "玄幻"
    },
    {
     "n": "热血",
     "v": "热血"
    },
    {
     "n": "喜剧",
     "v": "喜剧"
    },
    {
     "n": "悬疑",
     "v": "悬疑"
    },
    {
     "n": "军事",
     "v": "军事"
    },
    {
     "n": "其他剧情",
     "v": "其他剧情"
    }
   ]
  }
 ],
 "山海": [
  {
   "key": "area",
   "name": "分类",
   "value": [
    {
     "n": "精选",
     "v": "0"
    },
    {
     "n": "人气",
     "v": "1"
    },
    {
     "n": "新剧",
     "v": "51"
    },
    {
     "n": "甜宠",
     "v": "46"
    },
    {
     "n": "逆袭",
     "v": "6"
    },
    {
     "n": "强者回归",
     "v": "50"
    },
    {
     "n": "奇幻",
     "v": "44"
    },
    {
     "n": "复仇",
     "v": "49"
    },
    {
     "n": "中国梦",
     "v": "41"
    },
    {
     "n": "家庭",
     "v": "9"
    }
   ]
  }
 ],
 "好看": [
  {
   "key": "area",
   "name": "分类",
   "value": [
    {
     "n": "热播剧",
     "v": "1"
    },
    {
     "n": "新剧",
     "v": "2"
    },
    {
     "n": "战神",
     "v": "1001"
    },
    {
     "n": "神豪",
     "v": "2001"
    },
    {
     "n": "神医",
     "v": "1002"
    },
    {
     "n": "甜宠",
     "v": "1007"
    },
    {
     "n": "赘婿",
     "v": "1003"
    },
    {
     "n": "穿越重生",
     "v": "2004"
    },
    {
     "n": "异能",
     "v": "2005"
    },
    {
     "n": "虐恋",
     "v": "1006"
    },
    {
     "n": "宫斗宅斗",
     "v": "2006"
    },
    {
     "n": "玄幻",
     "v": "2009"
    }
   ]
  }
 ],
 "围观": [
  {
   "key": "area",
   "name": "分类",
   "value": [
    {
     "n": "全部",
     "v": ""
    }
   ]
  }
 ],
 "薏米": [
  {
   "key": "area",
   "name": "分类",
   "value": [
    {
     "n": "精选",
     "v": "channel_c6f50cd9"
    },
    {
     "n": "逆袭",
     "v": "channel_a8e10abc"
    },
    {
     "n": "复仇",
     "v": "channel_d26dd434"
    },
    {
     "n": "恋爱",
     "v": "channel_75afe84a"
    },
    {
     "n": "重生",
     "v": "channel_2272aac5"
    },
    {
     "n": "古风",
     "v": "channel_73190d4f"
    },
    {
     "n": "神医",
     "v": "channel_2d7eae6b"
    },
    {
     "n": "言情",
     "v": "channel_614820bd"
    },
    {
     "n": "都市",
     "v": "channel_13dfce8b"
    },
    {
     "n": "悬疑",
     "v": "channel_861b9642"
    },
    {
     "n": "历史",
     "v": "channel_18157927"
    }
   ]
  }
 ],
 "爽爽": [
  {
   "key": "area",
   "name": "分类",
   "value": [
    {
     "n": "全部",
     "v": ""
    },
    {
     "n": "女频恋爱",
     "v": "女频恋爱"
    },
    {
     "n": "脑洞悬疑",
     "v": "脑洞悬疑"
    },
    {
     "n": "年代穿越",
     "v": "年代穿越"
    },
    {
     "n": "古装仙侠",
     "v": "古装仙侠"
    },
    {
     "n": "现代都市",
     "v": "现代都市"
    },
    {
     "n": "反转",
     "v": "反转"
    },
    {
     "n": "爽文",
     "v": "爽文"
    },
    {
     "n": "短剧",
     "v": "短剧"
    }
   ]
  }
 ],
 "喜福": [
  {
   "key": "area",
   "name": "分类",
   "value": [
    {
     "n": "全部",
     "v": ""
    },
    {
     "n": "爽剧",
     "v": "3"
    },
    {
     "n": "甜宠",
     "v": "6"
    },
    {
     "n": "逆袭",
     "v": "5"
    },
    {
     "n": "现代言情",
     "v": "1"
    },
    {
     "n": "都市",
     "v": "4"
    },
    {
     "n": "玄幻",
     "v": "23"
    },
    {
     "n": "古代言情",
     "v": "16"
    }
   ]
  }
 ],
 "五五": [
  {
   "key": "area",
   "name": "分类",
   "value": [
    {
     "n": "全部",
     "v": "全部"
    },
    {
     "n": "男频",
     "v": "男频"
    },
    {
     "n": "女频",
     "v": "女频"
    },
    {
     "n": "都市",
     "v": "都市"
    },
    {
     "n": "虐渣",
     "v": "虐渣"
    },
    {
     "n": "励志",
     "v": "励志"
    },
    {
     "n": "逆袭",
     "v": "逆袭"
    },
    {
     "n": "古风",
     "v": "古风"
    },
    {
     "n": "复仇",
     "v": "复仇"
    },
    {
     "n": "家庭",
     "v": "家庭"
    },
    {
     "n": "悬疑",
     "v": "悬疑"
    },
    {
     "n": "奇幻",
     "v": "奇幻"
    }
   ]
  }
 ]
}


# ---- 平台配置 (aggConfig.platform) ----
AGG_PLATFORM = {
    "51": {"host": "https://51hub.com", "list": "/new-theater-category", "detail": "/video/videolist", "search": "/search"},
    "星星": {"host": "http://read.api.duodutek.com", "list": "/novel-api/app/pageModel/getResourceById", "detail": "/novel-api/basedata/book/getChapterList"},
    "河马": {"host": "https://freevideo.zqqds.cn", "url1": "/free-video-portal/portal"},
    "七猫": {"host": "https://api-store.qmplaylet.com", "url1": "/api/v1/playlet/index", "url2": "https://api-read.qmplaylet.com/player/api/v1/playlet/info", "search": "/api/v1/playlet/search"},
    "星芽": {"host": "https://app.whjzjx.cn", "url1": "/cloud/v2/theater/home_page?theater_class_id", "url2": "/v2/theater_parent/detail", "search": "/v3/search", "loginUrl": "https://u.shytkjgs.com/user/v1/account/login"},
    "围观": {"host": "https://api.drama.9ddm.com", "url1": "/drama/home/shortVideoTags?version_code=1500&os_type=1", "url2": "/drama/home/shortVideoDetail?version_code=1000&os_type=1", "search": "/drama/home/search?version_code=1500&os_type=1"},
    "百度": {"host": "https://mbd.baidu.com"},
    "牛牛": {"host": "https://new.tianjinzhitongdaohe.com", "url1": "https://csj-sp.csjdeveloper.com"},
    "山海": {"host": "https://api.app.gxshxy.com", "url1": "https://u.app.gxshxy.com/user/v3/account/login"},
    "好看": {"host": "https://sv.baidu.com"},
    "西饭": {"host": "https://xifan-api-cn.youlishipin.com", "url1": "/xifan/drama/portalPage", "url2": "/xifan/drama/getDuanjuInfo", "search": "/xifan/search/getSearchList"},
    "薏米": {"host": "https://yimi-api.zhangyue.com", "list": "/bookstore/local/visual/channel/list", "detail": "/video/client/short_play/episode_list", "search": "/bookstore/search/recommend_data"},
    "爽爽": {"host": "https://djw123.com", "class": "duanju", "show": "/show/duanju---%s-----%s---.html", "searchUrl": "/search/-------------.html"},
    "喜福": {"host": "https://minidrama-api.contentchina.com", "list": "/web/v1/home/categoryList?isLeft=1", "dramaList": "/web/v1/drama/list", "playAuth": "/web/v1/drama/play_auth"},
    "五五": {"host": "https://www.duanju55.com", "list": "/index.php/vod/show/class/", "type": "/index.php/vod/type/id/1.html", "detail": "/index.php/vod/detail/id/", "search": "/index.php/vod/search/wd/"},
}

# aggConfig.platformList (顺序与名称)
AGG_PLATFORM_LIST = [
    {"name": "河马短剧", "id": "河马"}, {"name": "七猫短剧", "id": "七猫"}, {"name": "星芽短剧", "id": "星芽"},
    {"name": "围观短剧", "id": "围观"}, {"name": "百度短剧", "id": "百度"}, {"name": "薏米短剧", "id": "薏米"},
    {"name": "牛牛短剧", "id": "牛牛"}, {"name": "山海短剧", "id": "山海"}, {"name": "好看短剧", "id": "好看"},
    {"name": "西饭短剧", "id": "西饭"}, {"name": "星星短剧", "id": "星星"}, {"name": "五一短剧", "id": "51"},
    {"name": "爽爽短剧", "id": "爽爽"}, {"name": "喜福短剧", "id": "喜福"}, {"name": "五五短剧", "id": "五五"},
]

# aggConfig.headers
AGG_HEADERS = {
    "default": {"User-Agent": "okhttp/4.10.0", "Content-Type": "application/json"},
    "form": {"User-Agent": "okhttp/3.12.11", "Content-Type": "application/x-www-form-urlencoded"},
    "browser": {"User-Agent": "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.91 Mobile Safari/537.36", "Content-Type": "application/x-www-form-urlencoded"},
    "qimao": {"User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.87 Safari/537.36"},
    "baidu_app": {"User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; 22081212C Build/PQ3B.190801.002) Talos/1.8.13 SP-engine/3.47.0 bd_dvt/1 baiduboxapp/15.21.0.10 (Baidu; P1 9)", "Content-Type": "application/x-www-form-urlencoded", "Cookie": "BAIDUCUID=0Ovgu0uAvu0_828wj8Hma_8i28joaSuIlOvOigiAH88ikS8f0k35aD6mA"},
    "xingxing": {"User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.87 Safari/537.36"},
}

# filter_def 默认分类
AGG_FILTER_DEF = {
    "51": {"area": "0-0-0-0-0-0"}, "星星": {"area": "1287"}, "河马": {"area": "53@精选"},
    "星芽": {"area": "1"}, "西饭": {"area": "68@都市"}, "七猫": {"area": "0"},
    "围观": {"area": ""}, "牛牛": {"area": "全部"}, "山海": {"area": "1"}, "好看": {"area": "1"},
    "百度": {"class": "新剧", "area": "全部"}, "薏米": {"area": "channel_c6f50cd9"},
    "爽爽": {"area": ""}, "喜福": {"area": ""}, "五五": {"area": "全部"},
}

# AES 配置 (51)
AGG_AES_CONFIG_51 = {
    "video": {"key": "2acf7e91e9864673", "iv": "1c29882d3ddfcfd6"},
    "img": {"key": "f5d965df75336270", "iv": "97b60394abc2fbe1"},
}


# =====================================================================
#  加密 / 编码 工具 (等价替换 CryptoJS / forge / btoa / atob)
# =====================================================================
def _ag_pkcs7_pad(data: bytes, block: int = 16) -> bytes:
    n = block - (len(data) % block)
    return data + bytes([n]) * n


def _ag_pkcs7_unpad(data: bytes) -> bytes:
    if not data:
        return data
    n = data[-1]
    return data[:-n] if 1 <= n <= 16 else data


def _ag_aes_cbc_encrypt(data: bytes, key: bytes, iv: bytes) -> bytes:
    if CryptoAES is not None:
        return CryptoAES.new(key, CryptoAES.MODE_CBC, iv).encrypt(_ag_pkcs7_pad(data))
    if Cipher is not None:
        enc = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
        return enc.update(_ag_pkcs7_pad(data)) + enc.finalize()
    raise RuntimeError("no AES backend")


def _ag_aes_cbc_decrypt(data: bytes, key: bytes, iv: bytes) -> bytes:
    if CryptoAES is not None:
        return _ag_pkcs7_unpad(CryptoAES.new(key, CryptoAES.MODE_CBC, iv).decrypt(data))
    if Cipher is not None:
        dec = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
        return _ag_pkcs7_unpad(dec.update(data) + dec.finalize())
    raise RuntimeError("no AES backend")


def _ag_aes_ecb_encrypt(data: bytes, key: bytes) -> bytes:
    if CryptoAES is not None:
        return CryptoAES.new(key, CryptoAES.MODE_ECB).encrypt(_ag_pkcs7_pad(data))
    if Cipher is not None:
        enc = Cipher(algorithms.AES(key), modes.ECB()).encryptor()
        return enc.update(_ag_pkcs7_pad(data)) + enc.finalize()
    raise RuntimeError("no AES backend")


def _ag_aes_ecb_decrypt(data: bytes, key: bytes) -> bytes:
    if CryptoAES is not None:
        return _ag_pkcs7_unpad(CryptoAES.new(key, CryptoAES.MODE_ECB).decrypt(data))
    if Cipher is not None:
        dec = Cipher(algorithms.AES(key), modes.ECB()).decryptor()
        return _ag_pkcs7_unpad(dec.update(data) + dec.finalize())
    raise RuntimeError("no AES backend")


def _ag_aes_gcm_decrypt(cipher_hex: str, iv_hex: str, key: bytes) -> str:
    """AES-GCM，密文尾部 16 字节为 tag (对应 forge 实现)。"""
    try:
        raw = bytes.fromhex(cipher_hex)
        iv = bytes.fromhex(iv_hex)
        tag = raw[-16:]
        ct = raw[:-16]
        if CryptoAES is not None:
            cipher = CryptoAES.new(key, CryptoAES.MODE_GCM, nonce=iv)
            return cipher.decrypt_and_verify(ct, tag).decode("utf-8", "ignore")
        if Cipher is not None:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            return AESGCM(key).decrypt(iv, ct + tag, None).decode("utf-8", "ignore")
    except Exception:
        return "{}"
    return "{}"


def _ag_hmac_sha256_hex(msg: str, key: str) -> str:
    return hmac.new(key.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()


def _ag_md5(text) -> str:
    return hashlib.md5(str(text).encode("utf-8")).hexdigest()


def _ag_rsa_sha256_sign_b64(pem: str, data: str) -> str:
    """RSA-SHA256 (PKCS#1 v1.5) 签名，base64 输出 (对应 forge)。"""
    if CryptoAES is not None:
        try:
            from Crypto.PublicKey import RSA
            from Crypto.Signature import pkcs1_15
            from Crypto.Hash import SHA256
            key = RSA.import_key(pem)
            h = SHA256.new(data.encode("utf-8"))
            return base64.b64encode(pkcs1_15.new(key).sign(h)).decode("ascii")
        except Exception:
            pass
    if Cipher is not None:
        try:
            from cryptography.hazmat.primitives import hashes as _h
            from cryptography.hazmat.primitives.asymmetric import padding
            from cryptography.hazmat.primitives.serialization import load_pem_private_key
            key = load_pem_private_key(pem.encode("utf-8"), password=None)
            sig = key.sign(data.encode("utf-8"), padding.PKCS1v15(), _h.SHA256())
            return base64.b64encode(sig).decode("ascii")
        except Exception:
            pass
    return ""


def _ag_json(text):
    try:
        if isinstance(text, (dict, list)):
            return text
        return json.loads(text or "{}")
    except Exception:
        return {}


def _ag_enc_uri(s) -> str:
    # 等价 encodeURIComponent
    return quote(str(s), safe="!~*'()")


def _ag_build_query(params: dict) -> str:
    return "&".join("%s=%s" % (_ag_enc_uri(k), _ag_enc_uri(v)) for k, v in params.items())


def _ag_form_encode(obj: dict) -> str:
    out = []
    for k, v in obj.items():
        if v is None:
            continue
        out.append("%s=%s" % (_ag_enc_uri(k), _ag_enc_uri(v)))
    return "&".join(out)


# =====================================================================
#  底层 request (等价框架 request/post)
# =====================================================================
_AG_SESSION = requests.Session()


def _ag_request(url, method="GET", headers=None, body=None, data=None, timeout=15):
    """返回响应文本；等价 JS 框架的 request()。"""
    h = dict(headers or {})
    try:
        m = (method or "GET").upper()
        if m == "POST":
            if data is not None:
                payload = _ag_form_encode(data) if isinstance(data, dict) else data
            else:
                payload = body
            if isinstance(payload, (dict, list)):
                payload = json.dumps(payload, ensure_ascii=False)
            if isinstance(payload, str):
                payload = payload.encode("utf-8")
            r = _AG_SESSION.post(url, data=payload if payload is not None else b"",
                                 headers=h, timeout=timeout, verify=False)
        else:
            r = _AG_SESSION.get(url, headers=h, timeout=timeout, verify=False)
        r.encoding = r.encoding or "utf-8"
        return r.text
    except Exception:
        return ""


def _ag_post(url, data, headers=None):
    """等价 JS 的 post()：dict→JSON 体，否则原样；返回解析后的 JSON。"""
    body = json.dumps(data, ensure_ascii=False) if isinstance(data, (dict, list)) else data
    return _ag_json(_ag_request(url, method="POST",
                                headers=headers or AGG_HEADERS["default"], body=body))


def _ag_fetch(url, headers=None, method="GET", body=None):
    """等价内部 fetch：默认 headers，GET，解析 JSON。"""
    return _ag_json(_ag_request(url, method=method,
                                headers=headers or AGG_HEADERS["default"], body=body))


# =====================================================================
#  聚合引擎 · 各平台服务 (对应 JS 中 HM_Service/NN_Service/SH_Service 等)
# =====================================================================

# ------ 河马服务 ------
class _AG_HM_Service:
    KEY = bytes.fromhex("647a6b6a67667978677368796c677a6d")
    IV = bytes.fromhex("6170697570646f776e65646372797074")

    @classmethod
    def encrypt(cls, plaintext: str) -> str:
        ct = _ag_aes_cbc_encrypt(plaintext.encode("utf-8"), cls.KEY, cls.IV)
        return ct.hex().upper()

    @classmethod
    def decrypt(cls, word: str) -> str:
        raw = bytes.fromhex(word)
        return _ag_aes_cbc_decrypt(raw, cls.KEY, cls.IV).decode("utf-8", "ignore")

    @classmethod
    def api(cls, code, body_data):
        plat = AGG_PLATFORM["河马"]
        url = "%s%s/%s" % (plat["host"], plat["url1"], code)
        enc_body = cls.encrypt(json.dumps(body_data, ensure_ascii=False))
        try:
            raw = _ag_request(url, method="POST", headers={
                "datas": HM_STATIC_DATAS, "content-type": "text/plain",
                "user-agent": "okhttp/4.10.0", "Referer": "https://freevideo.zqqds.cn",
            }, body=enc_body)
            res = _ag_json(raw)
            if res and res.get("data"):
                return _ag_json(cls.decrypt(res["data"]))
        except Exception:
            pass
        return {}


# ------ 牛牛服务 ------
class _AG_NN_Service:
    @staticmethod
    def aes_dec_ecb(enc_b64: str, key: str) -> str:
        raw = base64.b64decode(enc_b64)
        return _ag_aes_ecb_decrypt(raw, key.encode("utf-8")).decode("utf-8", "ignore")

    @staticmethod
    def aes_enc_ecb(data: str, key: str) -> str:
        ct = _ag_aes_ecb_encrypt(data.encode("utf-8"), key.encode("utf-8"))
        return base64.b64encode(ct).decode("ascii")

    @staticmethod
    def hmac_sha256(msg, key):
        return _ag_hmac_sha256_hex(msg, key)

    @classmethod
    def ensure_auth(cls, cfg):
        if cfg.get("nn_token"):
            return
        try:
            html = _ag_request("https://new.tianjinzhitongdaohe.com/api/v1/app/user/visitorInfo",
                               headers={"deviceid": "aa11fc54-ba9c-3980-add5-447d3fa5b939",
                                        "User-Agent": "okhttp/4.12.0"})
            cfg["nn_token"] = _ag_json(html)["data"]["token"]
        except Exception:
            pass

    @classmethod
    def ensure_csj_auth(cls, cfg):
        if cfg.get("nn_csj_token"):
            return
        try:
            t = str(int(time.time()))
            body = ("ac=wifi&os=Android&vod_version=1.10.21.6-tob&os_version=9&type=1"
                    "&clientVersion=v5.2.5&uuid=Y4WNZ3SAWK7MAJMH7CXCDHJ4VMPVFRZQTBSIA4XTYO4AWEUHIK6Q01"
                    "&resolution=1280*2618&openudid=889edced38f1069b&dt=Pixel%204"
                    "&sha1=46121F77CE2FCAD3DBC3B9EC8A24908C1A8AD6D9&os_api=28"
                    "&install_id=1549688030634536&device_brand=google&sdk_version=1.1.3.0"
                    "&package_name=com.niuniu.ztdh.app&siteid=5627189&dev_log_aid=667431"
                    "&oaid=&timestamp=" + t)
            nonce = "VX1KKGtoBDCi1fB1"
            signature = cls.hmac_sha256(t + nonce + body, "aceaa47f96b4875d446b2e1d97e03bbb")
            enc_body = cls.aes_enc_ecb(body, "dafdb3d2a5c343d6")
            res = _ag_request("%s/csj_sp/api/v1/user/login?siteid=5627189" % AGG_PLATFORM["牛牛"]["url1"],
                              method="POST", headers={
                                  "X-Salt": "786774955F", "X-Nonce": nonce, "X-Timestamp": t,
                                  "X-Signature": signature,
                                  "Content-Type": "application/x-www-form-urlencoded"},
                              body=enc_body)
            dec = cls.aes_dec_ecb(res, "dafdb3d2a5c343d6")
            cfg["nn_csj_token"] = _ag_json(dec)["data"]["access_token"]
        except Exception:
            pass

    @classmethod
    def api(cls, cfg, url, body):
        cls.ensure_auth(cfg)
        return _ag_json(_ag_request(url, method="POST", headers={
            "token": cfg.get("nn_token", ""),
            "deviceid": "aa11fc54-ba9c-3980-add5-447d3fa5b939",
            "content-type": "application/json;charset=UTF-8",
            "User-Agent": "okhttp/4.12.0"},
            body=json.dumps(body, ensure_ascii=False)))

    @classmethod
    def post1(cls, cfg, url1, data1, index=None):
        cls.ensure_csj_auth(cfg)
        t10 = str(int(time.time()))
        x_nonce = "X9UknYKtLa3DmtjC"
        idx = str(index or "1")
        body1 = data1
        body1 = re.sub(r"&lock_free=\d+", "&lock_free=1", body1)
        body1 = re.sub(r"&timestamp=\d+", "&timestamp=" + t10, body1)
        body1 = re.sub(r"&count=\d+", "&count=1", body1)
        body1 = re.sub(r"&index=\d+", "&index=" + idx, body1)
        body1 = re.sub(r"&lock_ad=\d+", "&lock_ad=1", body1)
        body1 = re.sub(r"&lock_index=\d+", "&lock_index=" + idx, body1)
        body2 = cls.aes_enc_ecb(body1, "ce49b18dd4e0a4d8")
        signature = cls.hmac_sha256(t10 + x_nonce + body1, "aceaa47f96b4875d446b2e1d97e03bbb")
        try:
            html1 = _ag_request(url1, method="POST", headers={
                "X-Salt": "FD8188A8D5", "X-Nonce": x_nonce, "X-Timestamp": t10,
                "X-Access-Token": cfg.get("nn_csj_token", ""), "X-Signature": signature,
                "User-Agent": "okhttp/3.12.11",
                "Content-Type": "application/x-www-form-urlencoded"}, body=body2)
            return _ag_json(cls.aes_dec_ecb(html1, "ce49b18dd4e0a4d8"))
        except Exception:
            return {}


# ------ 山海服务 ------
class _AG_SH_Service:
    KEY = b"xxxxxxwhwqedqder"

    @classmethod
    def gcm_decrypt(cls, cipher_hex, iv_hex):
        return _ag_aes_gcm_decrypt(cipher_hex, iv_hex, cls.KEY)

    @staticmethod
    def encrypt_ecb(plain_text):
        ct = _ag_aes_ecb_encrypt(plain_text.encode("utf-8"), b"B@ecf920Od8A4df7")
        return base64.b64encode(ct).decode("ascii")

    @classmethod
    def ensure_auth(cls, cfg):
        if cfg.get("sh_token"):
            return
        try:
            body = json.dumps({
                "device": "22ebfeec0a5ad3c0397bae448b8658cc3", "install_first_open": True,
                "first_install_time": 1751687627754, "last_update_time": 1751687627754,
                "report_link_url": "", "android_id": "8f7db6f23d745890",
                "package_name": "com.shanhai.duanju", "authorization": "",
                "timestamp": int(time.time() * 1000)}, ensure_ascii=False)
            res = _ag_json(_ag_request(AGG_PLATFORM["山海"]["url1"], method="POST",
                                       headers={"content-type": "application/json; charset=utf-8"},
                                       body=cls.encrypt_ecb(body)))
            cfg["sh_token"] = res["data"]["token"]
        except Exception:
            pass

    @classmethod
    def request(cls, cfg, url, method="GET", headers=None, body=None):
        cls.ensure_auth(cfg)
        h = {"authorization": cfg.get("sh_token", "")}
        if headers:
            h.update(headers)
        raw = _ag_json(_ag_request(url, method=method, headers=h, body=body))
        try:
            return _ag_json(cls.gcm_decrypt(raw["data"]["data"], raw["data"]["nonce"]))
        except Exception:
            return {}


# ------ 七猫核心 ------
def _ag_qm_params_and_sign():
    session_id = str(int(time.time() * 1000))
    data = {
        "static_score": "0.8", "uuid": "00000000-7fc7-08dc-0000-000000000000",
        "device-id": "20250220125449b9b8cac84c2dd3d035c9052a2572f7dd0122edde3cc42a70",
        "mac": "", "sourceuid": "aa7de295aad621a6", "refresh-type": "0", "model": "22021211RC",
        "wlb-imei": "", "client-id": "aa7de295aad621a6", "brand": "Redmi", "oaid": "",
        "oaid-no-cache": "", "sys-ver": "12", "trusted-id": "", "phone-level": "H",
        "imei": "", "wlb-uid": "aa7de295aad621a6", "session-id": session_id,
    }
    json_str = json.dumps(data, separators=(",", ":"))
    # btoa(unescape(encodeURIComponent(jsonStr)))  ==  base64(utf-8 bytes)
    b64 = base64.b64encode(json_str.encode("utf-8")).decode("ascii")
    qm_params = "".join(AGG_CHAR_MAP.get(c, c) for c in b64)
    params_str = ("AUTHORIZATION=app-version=10001application-id=com.duoduo.readchannel="
                  "unknownis-white=net-env=5platform=androidqm-params=%sreg=%s" % (qm_params, AGG_KEYS))
    sign = _ag_md5(params_str)
    return qm_params, sign


def _ag_get_header_x():
    qm_params, sign = _ag_qm_params_and_sign()
    return {
        "net-env": "5", "reg": "", "channel": "unknown", "is-white": "", "platform": "android",
        "application-id": "com.duoduo.read", "authorization": "", "app-version": "10001",
        "user-agent": "webviewversion/0", "qm-params": qm_params, "sign": sign,
    }


# ------ 薏米 (RSA 签名头) ------
def _ag_yimi_headers(path, params, sec):
    ts = str(int(time.time() * 1000))
    str3 = "&" + params + "&" + path + "&" + ts + "&" + sec
    sign = _ag_rsa_sha256_sign_b64(YIMI_PRIVATE_KEY, str3)
    return {
        "x-appid": "zy9351ae", "x-sig-timestamp": ts, "x-sig-alg": "RSA-SHA256",
        "x-sig-sign": sign, "x-sig-ver": "v1.1", "x-sig-sec": sec,
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 15; 22081212C Build/AQ3A.241006.001)",
    }


# ------ 51 短剧 ------
def _ag_51_aes_decrypt(encrypted_data, typ="video"):
    try:
        if not encrypted_data:
            return None
        conf = AGG_AES_CONFIG_51[typ]
        key = conf["key"].encode("utf-8")
        iv = conf["iv"].encode("utf-8")
        if isinstance(encrypted_data, str):
            raw = base64.b64decode(encrypted_data)
        elif isinstance(encrypted_data, (bytes, bytearray)):
            raw = bytes(encrypted_data)
        else:
            return None
        plain = _ag_aes_cbc_decrypt(raw, key, iv)
        if typ == "video":
            text = plain.decode("utf-8", "ignore")
            first = text.find("{")
            last = text.rfind("}")
            if first != -1 and last != -1:
                return _ag_json(text[first:last + 1])
            return _ag_json(text)
        return plain
    except Exception:
        return None


class _AG_HTMLVideoParser:
    """辅助 51 首页/搜索 HTML 解析 (正则等价原 JS)。"""


def _ag_51_unescape(s):
    return (s or "").replace("\\u002F", "/").replace("\\/", "/")


def _ag_51_span_end(doc, start):
    """从 doc[start]('[' 或 '{') 起做括号配平(字符串感知)，返回配平结束下标。"""
    depth = 0
    instr = False
    esc = False
    for i in range(start, len(doc)):
        c = doc[i]
        if instr:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                instr = False
            continue
        if c == '"':
            instr = True
        elif c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
            if depth == 0:
                return i
    return -1


def _ag_51_nuxt_series(html):
    """解析 51 play 页内嵌的 Nuxt devalue 扁平数组，返回该短剧的结构化 dict。

    devalue 格式：一个扁平数组 flat，元素间用下标(整数)互相引用；剧集 schema
    是含 'episodeAll' 且 'video_url' 的字典，字段值多为指向 flat 的整数下标。
    """
    if not html:
        return None
    key = html.find('"episodeAll"')
    if key < 0:
        return None
    flat = None
    for s in reversed([mo.start() for mo in re.finditer(r"\[", html) if mo.start() < key][-120:]):
        e = _ag_51_span_end(html, s)
        if e > key:
            try:
                flat = json.loads(_ag_51_unescape(html[s:e + 1]))
            except Exception:
                flat = None
            if flat:
                break
    if not flat:
        return None
    schema = None
    for el in flat:
        if isinstance(el, dict) and "episodeAll" in el and "video_url" in el:
            schema = el
            break
    if not schema:
        return None

    def R(v):
        return flat[v] if isinstance(v, int) and 0 <= v < len(flat) else v

    rec = {k: R(i) for k, i in schema.items()}
    eps = []
    ea = R(schema.get("episodeAll"))
    if isinstance(ea, list):
        for ref in ea:
            ep = R(ref)
            if isinstance(ep, dict):
                eps.append({k: R(i) for k, i in ep.items()})
    rec["_episodes"] = eps
    return rec


def _ag_51_warm_m3u8(html):
    """提取 play 页 warmup 脚本注入的当前集 m3u8 直链。"""
    if not html:
        return ""
    mo = re.search(
        r'play-warmup"[\s\S]{0,4000}?\}\)\((?:JSON\.parse\()?["\']([^"\']+\.m3u8[^"\']*)',
        html)
    if mo:
        return _ag_51_unescape(mo.group(1))
    mo = re.search(r'"((?:https?:)?(?:\\u002F|/){2}[^"\\]+?\.m3u8[^"\\]*)"', html)
    return _ag_51_unescape(mo.group(1)) if mo else ""


def _ag_51_card_list(html, proxy_fn):
    """解析 51 分类/搜索页卡片：aria-label 标题 + 顺序对应的封面。新版 SSR 结构。"""
    videos = []
    if not html:
        return videos
    doc = _ag_51_unescape(html)
    # 卡片：/play/{id}/{ep}/ + aria-label（同一卡片可能出现两次，按 id 去重保序）
    order = []
    seen = set()
    for mo in re.finditer(r'href="/play/(\d+)/\d+/"[^>]*aria-label="([^"]*)"', doc):
        vid = mo.group(1)
        if vid in seen:
            continue
        seen.add(vid)
        name = re.sub(r"\s+", " ", mo.group(2)).strip()
        order.append((vid, name))
    # 封面：Nuxt 负载里的 upload 图，按出现顺序与卡片对齐
    covers = re.findall(r'https?://[^"\s]+?/upload[^"\s]*?\.(?:jpe?g|png|webp)', doc)
    for i, (vid, name) in enumerate(order):
        pic = covers[i] if i < len(covers) else ""
        if name:
            videos.append({"vod_id": "51@" + vid, "vod_name": name,
                           "vod_pic": proxy_fn(pic), "vod_remarks": "五一"})
    return videos


def _ag_51_parse_home(html, proxy_fn):
    return _ag_51_card_list(html, proxy_fn)


def _ag_51_parse_search(html, proxy_fn):
    return _ag_51_card_list(html, proxy_fn)



# =====================================================================
#  ENGINE HGUO · 黄果短剧 (原 黄果短剧修复DNS.py 单文件 Spider 融合)
#    type_id / vod_id 前缀: HGUO::      播放线路名: 黄果短剧
#    本机代理: 封面图 / m3u8 / ts / key 一律带 &eng=hguo，与红果代理互不干扰
#    DNS: 内置 DoH(腾讯/阿里/Google/Cloudflare 轮询)，绕开 DNS 污染与劫持
# =====================================================================
_HGUO_TAG = "HGUO"
_HGUO_PROXY_MARK = "&eng=hguo"
_HGUO_DOH_SERVERS = (
    "https://doh.pub/dns-query",
    "https://dns.alidns.com/resolve",
    "https://dns.google/resolve",
    "https://cloudflare-dns.com/dns-query",
)
_HGUO_DOH_TTL = 300
# 失败冷却：DoH 全挂时不要每次解析都重打一遍（原版会把失败结果缓存 300 秒，
# 这里改成「失败只冷却一小会儿」——期间直接交给系统 DNS，照样能连，不黑洞）
_HGUO_DOH_FAIL_TTL = 60
_HGUO_DOH_FAIL_AT = {}
# 单个 DoH 服务连续失败后的冷却，避免每次都白等它超时
_HGUO_DOH_SRV_COOLDOWN = 300
_HGUO_DOH_SRV_DEAD_AT = {}
_HGUO_DOH_CACHE = {}
_HGUO_DOH_LAST = {}
# DoH 全部失败时的兜底 IP，可手工填 {"huangguoai.com": "1.2.3.4"}
_HGUO_FALLBACK_IPS = {}
_HGUO_ORIG_GETADDRINFO = socket.getaddrinfo
_HGUO_DOH_APPLIED = False
_HGUO_DOH_LOCAL = threading.local() if threading is not None else None
_HGUO_DOH_LOCK = threading.Lock() if threading is not None else None
_HGUO_DOH_INFLIGHT = set()


def _hguo_is_hostname(host):
    """只有真域名才值得走 DoH。IP 字面量 / localhost 直接交给系统解析
    （原实现把 127.0.0.1 这类也丢给 DoH，白白多一轮网络往返）。"""
    if not host or not isinstance(host, str):
        return False
    if host == "localhost" or host.endswith(".localhost"):
        return False
    if ":" in host:                                   # IPv6 字面量
        return False
    if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", host):    # IPv4 字面量
        return False
    return "." in host


def _hguo_doh_query(host):
    now = time.time()
    for srv in _HGUO_DOH_SERVERS:
        dead = _HGUO_DOH_SRV_DEAD_AT.get(srv)
        if dead and now - dead < _HGUO_DOH_SRV_COOLDOWN:
            continue                                   # 这家刚挂过，先跳过，省一次超时
        try:
            qs = urlencode({"name": host, "type": "A"})
            url = srv + ("&" if "?" in srv else "?") + qs
            r = requests.get(url, headers={"Accept": "application/dns-json"},
                             timeout=2, verify=False)
            if getattr(r, "status_code", 0) != 200:
                _HGUO_DOH_SRV_DEAD_AT[srv] = now
                continue
            body = json.loads(r.text or "{}")
            for ans in (body.get("Answer") or []):
                d = str(ans.get("data") or "")
                if str(ans.get("type")) == "1" and re.match(r"^\d+\.\d+\.\d+\.\d+$", d):
                    _HGUO_DOH_SRV_DEAD_AT.pop(srv, None)
                    return d
            _HGUO_DOH_SRV_DEAD_AT[srv] = now
        except Exception:
            _HGUO_DOH_SRV_DEAD_AT[srv] = now
            continue
    return ""


def _hguo_doh_lookup(host):
    """DoH 解析。相对原版修四处：
       1. 失败不再写空缓存（原版会把失败结果缓存 300 秒，期间该域名一直解析不出来）
       2. 并发按域名各自解析（原版全局标志一置位，后面几路直接被跳过）
       3. IP 字面量 / localhost 不进 DoH
       4. 失败只冷却 60 秒 + 单个 DoH 服务挂了就冷 5 分钟，不再每次解析都白等超时
    """
    if not _hguo_is_hostname(host):
        return ""
    now = time.time()
    cached = _HGUO_DOH_CACHE.get(host)
    if cached and now - _HGUO_DOH_LAST.get(host, 0.0) < _HGUO_DOH_TTL:
        return cached
    fail_at = _HGUO_DOH_FAIL_AT.get(host)
    if fail_at and now - fail_at < _HGUO_DOH_FAIL_TTL:
        return ""            # 刚失败过：这一分钟内别再打了，系统 DNS 先顶着
    # 递归保护：本线程正在发 DoH 请求时，其内部 DNS 查询直接走系统解析
    if _HGUO_DOH_LOCAL is not None and getattr(_HGUO_DOH_LOCAL, "busy", False):
        return ""
    # 同一域名已有并发解析在跑，本线程不重复打，让系统解析兜着走
    if _HGUO_DOH_LOCK is not None:
        with _HGUO_DOH_LOCK:
            if host in _HGUO_DOH_INFLIGHT:
                return ""
            _HGUO_DOH_INFLIGHT.add(host)
    try:
        if _HGUO_DOH_LOCAL is not None:
            _HGUO_DOH_LOCAL.busy = True
        try:
            ip = _hguo_doh_query(host)
        finally:
            if _HGUO_DOH_LOCAL is not None:
                _HGUO_DOH_LOCAL.busy = False
    finally:
        if _HGUO_DOH_LOCK is not None:
            with _HGUO_DOH_LOCK:
                _HGUO_DOH_INFLIGHT.discard(host)
    if not ip:
        ip = _HGUO_FALLBACK_IPS.get(host, "")
    if ip:
        _HGUO_DOH_CACHE[host] = ip
        _HGUO_DOH_LAST[host] = now
        _HGUO_DOH_FAIL_AT.pop(host, None)
    else:
        # 不缓存空结果（缓存了就是黑洞），只记个冷却时间，避免每次解析都白等一轮
        _HGUO_DOH_CACHE.pop(host, None)
        _HGUO_DOH_LAST.pop(host, None)
        _HGUO_DOH_FAIL_AT[host] = now
    return ip


def _hguo_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    name = host.decode("utf-8", "ignore") if isinstance(host, (bytes, bytearray)) else host
    if isinstance(name, str):
        ip = _hguo_doh_lookup(name)
        if ip:
            try:
                return _HGUO_ORIG_GETADDRINFO(ip, port, family, type, proto, flags)
            except Exception:
                pass
    return _HGUO_ORIG_GETADDRINFO(host, port, family, type, proto, flags)


def _hguo_install_doh():
    """把 DoH 解析挂到 socket 上。幂等，多实例共享同一次补丁。"""
    global _HGUO_DOH_APPLIED
    if _HGUO_DOH_APPLIED:
        return
    try:
        socket.getaddrinfo = _hguo_getaddrinfo
        _HGUO_DOH_APPLIED = True
    except Exception:
        pass


def _hguo_pv(param, key):
    """取本机代理参数；兼容壳把 query 解析成 {k: [v]} 的情况。"""
    v = (param or {}).get(key)
    if isinstance(v, (list, tuple)):
        v = v[0] if v else ""
    return str(v or "")


class _HuangguoSpider(_BaseSpider):
    """黄果短剧 (huangguoai.com)：卡片流解析 + 专辑/榜单/吃瓜 + m3u8 本机代理。"""

    def __init__(self):
        self.name = "黄果短剧"
        self.host = "https://huangguoai.com"
        self.header = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Referer": self.host,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9"
        }
        self.cat_map = [
            {"type_id": "ai-duanju", "type_name": "AI成人短剧", "path": "/ai-duanju/", "api": "ai-duanju",
             "tabs": [{"v": "latest", "n": "最新更新", "q": "sort=latest"},
                      {"v": "hot", "n": "当前热播", "q": ""},
                      {"v": "original", "n": "独家原创", "q": "is_original=1"},
                      {"v": "random", "n": "随机推荐", "q": "sort=random&size=20"}]},
            {"type_id": "ai-manju", "type_name": "AI成人漫剧", "path": "/ai-manju/", "api": "ai-manju",
             "tabs": [{"v": "latest", "n": "最新更新", "q": "sort=latest"},
                      {"v": "hot", "n": "当前热播", "q": ""},
                      {"v": "original", "n": "独家原创", "q": "is_original=1"},
                      {"v": "random", "n": "随机推荐", "q": "sort=random&size=20"}]},
            {"type_id": "ai-huanlian", "type_name": "AI换脸", "path": "/ai-huanlian/", "api": "ai-huanlian",
             "tabs": [{"v": "latest", "n": "最新更新", "q": "sort=latest"},
                      {"v": "hot", "n": "当前热播", "q": ""},
                      {"v": "original", "n": "独家原创", "q": "is_original=1"},
                      {"v": "random", "n": "随机推荐", "q": "sort=random&size=20"}]},
            {"type_id": "ai-mogai", "type_name": "AI魔改", "path": "/ai-mogai/", "api": "ai-mogai",
             "tabs": [{"v": "latest", "n": "最新更新", "q": "sort=latest"},
                      {"v": "hot", "n": "当前热播", "q": ""},
                      {"v": "original", "n": "独家原创", "q": "is_original=1"},
                      {"v": "random", "n": "随机推荐", "q": "sort=random&size=20"}]},
            {"type_id": "topic", "type_name": "专题", "path": "/topics/", "kind": "topic"},
            {"type_id": "rank", "type_name": "排行榜", "path": "/ranks/hot/", "kind": "rank",
             "tabs": [{"v": "hot", "n": "热播榜", "path": "/ranks/hot/"},
                      {"v": "potential", "n": "潜力榜", "path": "/ranks/potential/"},
                      {"v": "recommend", "n": "推荐榜", "path": "/ranks/recommend/"}]},
            {"type_id": "chigua", "type_name": "黄果吃瓜", "path": "/chigua/", "kind": "chigua",
             "tabs": [{"v": "latest", "n": "最新吃瓜", "path": "/chigua/"},
                      {"v": "remen", "n": "热门吃瓜", "path": "/chigua/remen/"},
                      {"v": "yuanchuang", "n": "AI原创", "path": "/chigua/yuanchuang/"}]}
        ]
        self.key = bytes(int(c) for c in "102_53_100_57_54_53_100_102_55_53_51_51_54_50_55_48".split("_"))
        self.iv = bytes(int(c) for c in "57_55_98_54_48_51_57_52_97_98_99_50_102_98_101_49".split("_"))
        self.filter_map = {"": {}}
        self._host_pinned = False
        _hguo_install_doh()

    def getName(self):
        return self.name

    # 壳不选分类时（只点标签、没动筛选）默认走「首页推荐」，保证一进去就有内容
    _HGUO_HOME_KEYS = ("", "home", "root", "首页推荐", "推荐", "首页")

    def filter_meta(self):
        """给统一入口用的筛选：分类 + 子分类（跨分类按显示名去重）。
        第一项固定「首页推荐」= 站点首页卡片流，也是壳不传筛选时的默认。"""
        cate_vals = [{"n": "首页推荐", "v": "home"}]
        cate_vals += [{"n": c["type_name"], "v": c["type_id"]} for c in self.cat_map]
        seen = set()
        sub_vals = []
        for c in self.cat_map:
            for t in (c.get("tabs") or []):
                nm = t.get("n")
                if nm and nm not in seen:
                    seen.add(nm)
                    sub_vals.append({"n": nm, "v": t.get("v")})
        groups = [{"key": "cate", "name": "分类", "value": cate_vals}]
        if sub_vals:
            groups.append({"key": "sub", "name": "子分类", "value": sub_vals})
        return groups

    def init(self, extend=""):
        pass

    def getHtml(self, url):
        # 首次真正抓取时后台预热目标域名（不阻塞），避免 __init__ 里同步等网络
        if not self._host_pinned:
            self._host_pinned = True
            self._pin_host(self.host)
        for attempt in range(3):
            for kw in ({"verify": False}, {}):
                try:
                    r = requests.get(url, headers=self.header, timeout=15, **kw)
                    if r.status_code == 200:
                        return r.text
                except (TypeError, ValueError):
                    continue
                except Exception:
                    pass
        return ""

    def fix_url(self, url):
        if not url:
            return ""
        url = url.replace("\\u0026", "&").replace("&amp;", "&")
        if url.startswith("/proxy?") or url.startswith("/local/") or url.startswith("http://127.0.0.1"):
            return url
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.host + url
        return url

    def _pin_host(self, url):
        """后台预解析目标域名（DoH 治 DNS 污染）。最多等 0.8 秒，等不到就让系统 DNS
        先顶着，绝不把首次请求卡在预热上（壳的首屏超时可不等人）。"""
        try:
            m = re.search(r'https?://([^/?#]+)', url)
            if not m:
                return
            host = m.group(1)
            if threading is not None:
                t = threading.Thread(target=_hguo_doh_lookup, args=(host,), daemon=True)
                t.start()
                t.join(0.8)
                return
            _hguo_doh_lookup(host)
        except Exception:
            pass

    def _proxy_url(self):
        """取壳注入的本机代理地址；没注入时退回 9978 默认口。"""
        try:
            fn = getattr(self, "getProxyUrl", None)
            if callable(fn):
                b = str(fn() or "").strip()
                if b:
                    return b
        except Exception:
            pass
        return "http://127.0.0.1:9978/proxy?do=py"

    def proc_pic(self, pic):
        if not pic:
            return ""
        pic = self.fix_url(pic)
        if "127.0.0.1" in pic or "local://" in pic or pic.startswith("data:"):
            return pic
        try:
            b = self._proxy_url()
            if "?" not in b:
                b += "?do=py"
            return b + _HGUO_PROXY_MARK + "&url=" + quote(pic)
        except Exception:
            return "http://127.0.0.1:9978/proxy?do=py" + _HGUO_PROXY_MARK + "&url=" + quote(pic)

    def extract_cards(self, html, link_prefix="detail|video"):
        # 站点 2026-09 改版：详情链接从 /detail/{id}/ 换成 /video/{id}/，
        # 默认两个前缀都认，避免再因改版整站空数据
        result = []
        seen = set()
        matches = list(re.finditer(r'data-track-id="(\d+)"', html))
        for i, m in enumerate(matches):
            try:
                start = m.start()
                end = matches[i + 1].start() if i + 1 < len(matches) else min(start + 3000, len(html))
                chunk = html[start:end]
                vod_id = m.group(1)
                if vod_id in seen:
                    continue
                link = re.search(r'href="(/(?:%s)/%s/?)"' % (link_prefix, re.escape(vod_id)), chunk)
                if not link:
                    # 站点再改版时的兜底：链接里带 id 就算数，不锁死前缀
                    link = re.search(r'href="([^"]*%s[^"]*)"' % re.escape(vod_id), chunk)
                if not link:
                    continue
                seen.add(vod_id)
                title = re.search(r'data-track-title="([^"]*)"', chunk)
                vod_name = title.group(1) if title else ""
                if not vod_name:
                    t = re.search(r'alt="([^"]*)"', chunk)
                    vod_name = t.group(1) if t else ""
                if not vod_name:
                    h = re.search(r'<h2[^>]*>.*?<a[^>]*>([^<]+)</a>', chunk, re.S)
                    vod_name = h.group(1).strip() if h else ""
                pic = re.search(r'data-src="(https?://[^"]*)"', chunk)
                if not pic:
                    pic = re.search(r'<img[^>]*data-src="([^"]+)"', chunk)
                vod_pic = self.proc_pic(pic.group(1) if pic else "")
                # 集数现在挂在 data-ep-base 属性上（"更新至6集"），旧的文本取法抓不到
                ep = re.search(r'hg-drama-card__episode"[^>]*data-ep-base="([^"]*)"', chunk)
                if not ep:
                    ep = re.search(r'data-ep-base="([^"]*)"', chunk)
                if not ep:
                    ep = re.search(r'hg-drama-card__episode[^>]*>([^<]*)', chunk)
                vod_remarks = ep.group(1).strip() if ep else ""
                if not vod_remarks:
                    score = re.search(r'hg-drama-card__score[^>]*>([^<]*)', chunk)
                    vod_remarks = score.group(1).strip() if score else ""
                if vod_name and vod_id:
                    result.append({
                        "vod_id": vod_id,
                        "vod_name": vod_name,
                        "vod_pic": vod_pic,
                        "vod_remarks": vod_remarks
                    })
            except Exception:
                continue
        return result

    def extract_rank(self, html):
        result = []
        seen = set()
        for m in re.finditer(r'<div class="hg-rank-item"[^>]*data-track-id="(\d+)"', html):
            try:
                start = m.start()
                vod_id = m.group(1)
                if vod_id in seen:
                    continue
                chunk = html[start:start + 2500]
                seen.add(vod_id)
                link = re.search(r'href="(/(?:detail|video)/%s/?)"' % re.escape(vod_id), chunk)
                if not link:
                    link = re.search(r'href="([^"]*%s[^"]*)"' % re.escape(vod_id), chunk)
                if not link:
                    continue
                title = re.search(r'data-track-title="([^"]*)"', chunk)
                vod_name = title.group(1) if title else ""
                pic = re.search(r'data-src="(https?://[^"]*)"', chunk)
                vod_pic = self.proc_pic(pic.group(1) if pic else "")
                heat = re.search(r'hg-rank-item__heat-value[^>]*>([^<]*)', chunk)
                vod_remarks = heat.group(1).strip() if heat else ""
                if vod_name:
                    result.append({
                        "vod_id": vod_id,
                        "vod_name": vod_name,
                        "vod_pic": vod_pic,
                        "vod_remarks": vod_remarks
                    })
            except Exception:
                continue
        return result

    def extract_topics(self, html):
        result = []
        for m in re.finditer(r'<a class="hg-topic-card" href="(/topics/[^"]*/)"', html):
            try:
                start = m.start()
                chunk = html[start:start + 900]
                title = re.search(r'hg-topic-card__title[^>]*>([^<]*)', chunk)
                vod_name = title.group(1).strip() if title else ""
                meta = re.search(r'hg-topic-card__meta[^>]*>\s*<span>([^<]*)</span>', chunk)
                vod_remarks = meta.group(1).strip() if meta else ""
                pic = re.search(r'data-src="(https?://[^"]*)"', chunk)
                vod_pic = self.proc_pic(pic.group(1) if pic else "")
                if vod_name:
                    result.append({
                        "vod_id": m.group(1),
                        "vod_name": vod_name,
                        "vod_pic": vod_pic,
                        "vod_remarks": vod_remarks
                    })
            except Exception:
                continue
        return result

    def extract_posts(self, html):
        result = []
        seen = set()
        for m in re.finditer(r'<a class="hg-post-card" href="(/archives/(\d+)/)"', html):
            try:
                start = m.start()
                pid = m.group(2)
                if pid in seen:
                    continue
                seen.add(pid)
                chunk = html[start:start + 1500]
                title = re.search(r'<h3>([^<]*)</h3>', chunk)
                vod_name = title.group(1).strip() if title else ""
                pic = re.search(r'data-src="(https?://[^"]*)"', chunk)
                vod_pic = self.proc_pic(pic.group(1) if pic else "")
                meta = re.search(r'hg-post-card__cat[^>]*>([^<]*)', chunk)
                vod_remarks = meta.group(1).strip() if meta else ""
                if vod_name:
                    result.append({
                        "vod_id": m.group(1),
                        "vod_name": vod_name,
                        "vod_pic": vod_pic,
                        "vod_remarks": vod_remarks
                    })
            except Exception:
                continue
        return result

    def parse_api_list(self, items):
        result = []
        for it in items:
            try:
                vid = str(it.get("id") or "")
                if not vid:
                    continue
                name = (it.get("title") or "").strip()
                if not name:
                    continue
                score = it.get("score") or 0
                remark = ""
                if it.get("is_finished"):
                    remark = "全%d集" % (it.get("total_episodes") or 0)
                else:
                    ec = it.get("episode_count") or 0
                    if ec:
                        remark = "更新至%d集" % ec
                if score:
                    remark = ("%s %.1f分" % (remark, score)).strip()
                if it.get("is_original"):
                    remark = ("黄果原创 " + remark).strip()
                result.append({
                    "vod_id": vid,
                    "vod_name": name,
                    "vod_pic": self.proc_pic(it.get("cover") or ""),
                    "vod_remarks": remark
                })
            except Exception:
                continue
        return result

    def homeContent(self, filter):
        result = {"class": [], "filters": {}}
        for cat in self.cat_map:
            result["class"].append({"type_id": cat["type_id"], "type_name": cat["type_name"]})
            tabs = cat.get("tabs")
            if tabs:
                result["filters"][cat["type_id"]] = [{"key": "sub", "name": "子分类", "value": [{"n": t["n"], "v": t["v"]} for t in tabs]}]
        result["list"] = self.homeVideoContent().get("list", [])
        return result

    def homeVideoContent(self):
        result = {"list": []}
        html = self.getHtml(self.host)
        if not html:
            return result
        cards = self.extract_cards(html)
        seen = set()
        unique = []
        for c in cards:
            if c["vod_id"] not in seen:
                seen.add(c["vod_id"])
                unique.append(c)
        result["list"] = unique[:20]
        return result

    def get_tab(self, filter, extend):
        for d in (filter, extend):
            if isinstance(d, dict):
                if d.get("sub"):
                    return d.get("sub")
                inner = d.get("filter")
                if isinstance(inner, dict) and inner.get("sub"):
                    return inner.get("sub")
        return ""

    def _pick_cat(self, tid):
        """解析壳传来的分类：空值 / 未知值一律当「首页推荐」(返回 None)。"""
        t = str(tid or "").strip()
        if t in self._HGUO_HOME_KEYS:
            return None
        return next((c for c in self.cat_map if c["type_id"] == t or c["type_name"] == t), None)

    def page_cards(self, path, limit=None):
        """抓某个页面并抽出卡片流（去重）。"""
        p = str(path or "/")
        url = self.host + p if p.startswith("/") else self.host + "/" + p
        html = self.getHtml(url)
        if not html:
            return []
        seen = set()
        out = []
        for c in self.extract_cards(html):
            vid = c.get("vod_id")
            if not vid or vid in seen:
                continue
            seen.add(vid)
            out.append(c)
        return out[:limit] if limit else out

    def home_feed(self, limit=36):
        """首页推荐：站点首页卡片流，黄果默认入口靠它撑住。"""
        result = {"list": [], "page": 1, "pagecount": 1, "limit": limit, "total": 0}
        cards = self.page_cards("/", limit)
        result["list"] = cards
        result["total"] = len(cards)
        result["limit"] = len(cards) or limit
        return result

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if tid and str(tid).startswith("folder_topic_"):
            return self.topicFolderList(tid, page)
        cat = self._pick_cat(tid)
        if not cat:
            # 壳没带分类（初始进标签就是这种情况）或传了个对不上的值 → 给首页推荐
            return self.home_feed()
        result = {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}
        kind = cat.get("kind", "")
        tab = self.get_tab(filter, extend)
        if kind == "topic":
            html = self.getHtml(self.host + cat["path"].rstrip("/") + "/")
            if not html:
                return result
            topics = self.extract_topics(re.sub(r'<template[\s\S]*?</template>', '', html))
            for t in topics:
                fid = "folder_topic_" + base64.urlsafe_b64encode(t["vod_id"].encode("utf-8")).decode("utf-8")
                result["list"].append({
                    "vod_id": fid,
                    "vod_name": t["vod_name"],
                    "vod_pic": t["vod_pic"],
                    "vod_remarks": t["vod_remarks"] or "进入专辑",
                    "vod_tag": "folder"
                })
            result["page"] = page
            result["limit"] = len(result["list"]) if result["list"] else 20
            return result
        if kind == "rank":
            tabs = cat.get("tabs") or []
            tc = next((t for t in tabs if t["v"] == tab), tabs[0] if tabs else None)
            if not tc:
                return result
            html = self.getHtml(self.host + tc["path"])
            if not html:
                return result
            result["list"] = self.extract_rank(html)
            result["page"] = page
            return result
        if kind == "chigua":
            tabs = cat.get("tabs") or []
            tc = next((t for t in tabs if t["v"] == tab), tabs[0] if tabs else None)
            if not tc:
                return result
            base = tc["path"].rstrip("/")
            if page <= 1:
                url = self.host + base + "/"
            else:
                url = self.host + base + "/%d/" % page
            html = self.getHtml(url)
            if not html:
                return result
            result["list"] = self.extract_posts(re.sub(r'<template[\s\S]*?</template>', '', html))
            total_m = re.search(r'共 (\d+) 条', html)
            if total_m:
                result["total"] = int(total_m.group(1))
            page_m = re.search(r'第 (\d+)/(\d+) 页', html)
            if page_m:
                result["page"] = int(page_m.group(1))
                result["pagecount"] = int(page_m.group(2))
            result["limit"] = len(result["list"]) if result["list"] else 20
            return result
        tabs = cat.get("tabs") or []
        tc = next((t for t in tabs if t["v"] == tab), tabs[0] if tabs else None)
        if not tc:
            return result
        url = "%s/api/videos/category/%s?page=%d" % (self.host, cat.get("api", cat["type_id"]), page)
        if tc.get("q"):
            url += "&" + tc["q"]
        html = self.getHtml(url)
        if html:
            try:
                data = json.loads(html)
            except Exception:
                data = None
            if data and isinstance(data.get("data"), dict):
                d = data["data"]
                result["list"] = self.parse_api_list(d.get("items") or [])
                pgd = d.get("pagination") or {}
                result["page"] = pgd.get("page") or page
                result["pagecount"] = pgd.get("pages") or 1
                result["total"] = pgd.get("total") or 0
                result["limit"] = pgd.get("size") or 20
        if not result["list"] and page <= 1:
            # 接口改版/被挡时的兜底：直接吃分类页本身的卡片流，别给个空标签
            fb = self.page_cards(cat.get("path") or "/")
            if fb:
                result["list"] = fb
                result["page"] = 1
                result["pagecount"] = 1
                result["total"] = len(fb)
                result["limit"] = len(fb)
        return result

    def detailContent(self, ids):
        result = {"list": []}
        vid = ids[0] if isinstance(ids, list) else ids
        if isinstance(vid, str) and vid.startswith("folder_topic_"):
            return self.topicFolderDetail(vid)
        if isinstance(vid, str) and (vid.startswith("/topics/") or vid.startswith("/archives/")):
            if vid.startswith("/topics/"):
                return self.topicDetail(vid)
            return self.postDetail(vid)
        m = re.search(r'(\d+)', vid)
        if not m:
            return result
        vid = m.group(1)
        # 站点改版后详情页在 /video/{id}/；老路径留着兜底
        html = self.getHtml("%s/video/%s/" % (self.host, vid))
        if not html:
            html = self.getHtml("%s/detail/%s/" % (self.host, vid))
        if not html:
            return result
        vod = {"vod_id": vid}
        title = re.search(r'<title>([^|<]*)', html)
        if title:
            vod["vod_name"] = re.sub(r'\s*-\s*(短剧视频在线观看|黄果短剧|短剧).*$', '', title.group(1).strip()).strip() or vid
        else:
            vod["vod_name"] = vid
        pic = re.search(r'(?:data-src|src)="(https?://pic[^"]*)"', html)
        if pic:
            vod["vod_pic"] = self.proc_pic(pic.group(1))
        else:
            vod["vod_pic"] = ""
        eps = re.findall(r'<a[^>]*href="(/video/%s(?:/ep-\d+)?/)"[^>]*data-ep-id="(\d+)"[^>]*>(.*?)</a>' % re.escape(vid), html, re.S)
        if eps:
            ep_map = {}
            for href, eid, name in eps:
                ep_map[int(eid)] = (href, re.sub(r'<[^>]+>', '', name).strip())
            play_urls = []
            for eid in sorted(ep_map.keys()):
                href, name = ep_map[eid]
                label = name if name else "第%02d集" % eid
                play_urls.append("%s$%s" % (label, self.fix_url(href)))
            vod["vod_play_from"] = "黄果短剧"
            vod["vod_play_url"] = "#".join(play_urls)
        else:
            data = None
            dm = re.search(r'<script id="videoInitialData" type="application/json">(.*?)</script>', html, re.S)
            if dm:
                try:
                    data = json.loads(dm.group(1).replace("\\u0026", "&"))
                except Exception:
                    data = None
            if data and data.get("epPlaySrcs"):
                vod["vod_pic"] = self.proc_pic(data.get("coverSrc")) or vod["vod_pic"]
                eps = data.get("epPlaySrcs") or {}
                play_urls = []
                for ep_id in sorted(eps.keys(), key=lambda x: int(x)):
                    play_urls.append("第%02d集$%s" % (int(ep_id), self.proxy_play(eps[ep_id])))
                vod["vod_play_from"] = "黄果短剧"
                vod["vod_play_url"] = "#".join(play_urls)
            else:
                vod["vod_play_from"] = "黄果短剧"
                vod["vod_play_url"] = "第01集$/video/%s/" % vid
        result["list"] = [vod]
        return result

    def topicFolderList(self, tid, page):
        result = {"list": [], "page": page, "pagecount": 1, "limit": 20, "total": 0}
        try:
            path = base64.urlsafe_b64decode(tid[len("folder_topic_"):].encode("utf-8")).decode("utf-8")
        except Exception:
            return result
        html = self.getHtml(self.fix_url(path))
        if not html:
            return result
        cards = self.extract_cards(re.sub(r'<template[\s\S]*?</template>', '', html))
        seen = set()
        unique = []
        for c in cards:
            if c["vod_id"] not in seen:
                seen.add(c["vod_id"])
                unique.append(c)
        result["list"] = unique
        result["limit"] = len(unique) if unique else 20
        return result

    def topicFolderDetail(self, tid):
        result = {"list": []}
        try:
            path = base64.urlsafe_b64decode(tid[len("folder_topic_"):].encode("utf-8")).decode("utf-8")
        except Exception:
            return result
        html = self.getHtml(self.fix_url(path))
        if not html:
            return result
        cards = self.extract_cards(re.sub(r'<template[\s\S]*?</template>', '', html))
        seen = set()
        unique = []
        for c in cards:
            if c["vod_id"] not in seen:
                seen.add(c["vod_id"])
                unique.append(c)
        if not unique:
            return result
        title = re.search(r'<title>([^<]*)', html)
        name = title.group(1).strip() if title else "专辑"
        name = re.sub(r'\s*[·\-]\s*黄果短剧.*$', '', name).strip() or "专辑"
        vod = {
            "vod_id": tid,
            "vod_name": name,
            "vod_pic": unique[0]["vod_pic"],
            "vod_remarks": "专辑目录",
            "vod_content": "目录入口，点击播放进入视频列表",
            "vod_play_from": "目录",
            "vod_play_url": "打开$" + tid
        }
        result["list"] = [vod]
        return result

    def topicDetail(self, vid):
        result = {"list": []}
        html = self.getHtml(self.fix_url(vid))
        if not html:
            return result
        cards = self.extract_cards(re.sub(r'<template[\s\S]*?</template>', '', html))
        seen = set()
        unique = []
        for c in cards:
            if c["vod_id"] not in seen:
                seen.add(c["vod_id"])
                unique.append(c)
        result["list"] = unique
        return result

    def postDetail(self, vid):
        result = {"list": []}
        html = self.getHtml(self.fix_url(vid))
        if not html:
            return result
        vod = {"vod_id": vid}
        title = re.search(r'<h1[^>]*>([^<]*)', html)
        if title:
            vod["vod_name"] = title.group(1).strip()
        else:
            t = re.search(r'<title>([^<]*)', html)
            vod["vod_name"] = t.group(1).strip() if t else vid
        pic = re.search(r'data-src="(https?://pic[^\"]*)"', html)
        if pic:
            vod["vod_pic"] = self.proc_pic(pic.group(1))
        else:
            vod["vod_pic"] = ""
        players = re.findall(r'class="post-video-player"[^>]*data-src="([^"]*)"', html)
        if players:
            play_urls = []
            for idx, src in enumerate(players, 1):
                play_urls.append("第%02d集$%s" % (idx, self.proxy_play(src.replace("\\u0026", "&"))))
            vod["vod_play_from"] = "黄果短剧"
            vod["vod_play_url"] = "#".join(play_urls)
        else:
            m3u8s = re.findall(r'(https?://[^\s"<>\\]*\.m3u8[^\s"<>\\]*)', html)
            if m3u8s:
                seen = []
                for u in m3u8s:
                    u = u.replace("\\u0026", "&")
                    if u not in seen:
                        seen.append(u)
                vod["vod_play_from"] = "黄果短剧"
                vod["vod_play_url"] = "#".join("第%02d集$%s" % (i + 1, self.proxy_play(u)) for i, u in enumerate(seen))
            else:
                vod["vod_play_from"] = "黄果短剧"
                vod["vod_play_url"] = "第01集$" + vid
        result["list"] = [vod]
        return result

    def searchContent(self, key, quick, pg):
        result = {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}
        page = int(pg) if pg else 1
        url = "%s/search/?keyword=%s" % (self.host, quote(key))
        if page > 1:
            url += "&page=%d" % page
        html = self.getHtml(url)
        if not html:
            return result
        result["list"] = self.extract_cards(re.sub(r'<template[\s\S]*?</template>', '', html))
        total = re.search(r'data-track-search-total="(\d+)"', html)
        if total:
            result["total"] = int(total.group(1))
        result["page"] = page
        return result

    def playerContent(self, flag, id, vipFlags):
        result = {"parse": 0, "playUrl": "", "url": "", "header": ""}
        if isinstance(id, str) and id.startswith("folder_topic_"):
            return {"parse": 1, "url": id, "header": {}}
        play_url = self.fix_url(id) if id else ""
        if play_url.startswith("/proxy?") or play_url.startswith("/local/") or play_url.startswith("http://127.0.0.1"):
            result["url"] = play_url
            result["header"] = json.dumps({"User-Agent": self.header["User-Agent"], "Referer": self.host})
            return result
        if 'm3u8' in play_url or '.mp4' in play_url:
            result["url"] = self.proxy_play(play_url)
            result["header"] = json.dumps({"User-Agent": self.header["User-Agent"], "Referer": self.host})
            return result
        if re.fullmatch(r'\d+', play_url):
            d = self.detailContent([play_url])
            if d["list"]:
                first = d["list"][0].get("vod_play_url", "").split("#")[0]
                if "$" in first:
                    play_url = self.fix_url(first.split("$", 1)[1])
        if play_url.startswith("/proxy?") or play_url.startswith("/local/") or play_url.startswith("http://127.0.0.1"):
            result["url"] = play_url
            result["header"] = json.dumps({"User-Agent": self.header["User-Agent"], "Referer": self.host})
            return result
        html = self.getHtml(play_url)
        if not html:
            return result
        m3u8 = ""
        m = re.search(r'"videoSrc"\s*:\s*"([^"]*)"', html)
        if m:
            m3u8 = m.group(1).replace("\\u0026", "&")
        if not m3u8:
            m = re.search(r'<video[^>]*>\s*<source[^>]*src="([^"]*)"', html)
            if m:
                m3u8 = m.group(1)
        if not m3u8:
            m = re.search(r'(https?://[^\s"<>\\]*\.m3u8[^\s"<>\\]*)', html)
            if m:
                m3u8 = m.group(1).replace("\\u0026", "&")
        result["url"] = self.proxy_m3u8_url(m3u8) if m3u8 else ""
        result["header"] = json.dumps({"User-Agent": self.header["User-Agent"], "Referer": self.host})
        return result

    def proxy_m3u8_url(self, url):
        return self._proxy_base("m3u8", url)

    def proxy_ts_url(self, url):
        return self._proxy_base("ts", url)

    def proxy_key_url(self, url):
        return self._proxy_base("key", url)

    def _proxy_base(self, typ, url):
        b = self._proxy_url()
        if "?" not in b:
            b += "?do=py"
        return b + _HGUO_PROXY_MARK + "&type=" + typ + "&url=" + quote(url)

    def proxy_play(self, url):
        url = self.fix_url(url)
        if url.startswith("/proxy?") or url.startswith("/local/") or url.startswith("http://127.0.0.1"):
            return url
        if "m3u8" in url.lower():
            return self.proxy_m3u8_url(url)
        return url

    def _proxy_m3u8(self, url):
        try:
            r = requests.get(url, headers=self.header, timeout=20, verify=False)
            if r.status_code != 200:
                return [502, "text/plain", "err:%d" % r.status_code]
            text = r.text
            host_base = re.match(r'https?://[^/]+', url)
            host_base = host_base.group(0) if host_base else ""
            path_dir = url[:url.rfind("/") + 1] if "/" in url else ""
            lines = []
            for line in text.split("\n"):
                s = line.strip()
                if not s:
                    continue
                if s.startswith("#"):
                    if 'URI="' in s:
                        mm = re.search(r'URI="([^"]*)"', s)
                        if mm:
                            u = mm.group(1)
                            if u.startswith("//"):
                                u = "https:" + u
                            elif u.startswith("/"):
                                u = host_base + u
                            elif not re.match(r'https?://', u):
                                u = path_dir + u
                            s = s[:mm.start(1)] + self.proxy_key_url(u) + s[mm.end(1):]
                    lines.append(s)
                    continue
                if re.match(r'https?://', s):
                    turl = s
                elif s.startswith("//"):
                    turl = "https:" + s
                elif s.startswith("/"):
                    turl = host_base + s
                else:
                    turl = path_dir + s
                lines.append(self.proxy_ts_url(turl))
            return [200, "application/vnd.apple.mpegurl", "\n".join(lines).encode("utf-8")]
        except Exception:
            return [502, "text/plain", "err"]

    def _proxy_ts(self, url):
        try:
            r = requests.get(url, headers=self.header, timeout=20, verify=False)
            if r.status_code != 200:
                return [502, "text/plain", "err:%d" % r.status_code]
            return [200, "video/mp2t", r.content]
        except Exception:
            return [502, "text/plain", "err"]

    def _proxy_key(self, url):
        try:
            r = requests.get(url, headers=self.header, timeout=20, verify=False)
            if r.status_code != 200:
                return [502, "text/plain", "err:%d" % r.status_code]
            return [200, "application/octet-stream", r.content]
        except Exception:
            return [502, "text/plain", "err"]

    def _proxy_pic(self, url):
        try:
            r = requests.get(url, headers=self.header, timeout=15, verify=False)
            ct = r.content
            if ct[:3] == b"\xff\xd8\xff":
                return [200, "image/jpeg", ct]
            if ct[:8] == b"\x89PNG\r\n\x1a\n":
                return [200, "image/png", ct]
            if ct[:4] == b"RIFF" and ct[8:12] == b"WEBP":
                return [200, "image/webp", ct]
            if ct[:3] == b"GIF":
                return [200, "image/gif", ct]
            if ct and len(ct) % 16 == 0:
                try:
                    dec = _aes_cbc_decrypt(self.key, self.iv, ct)
                except Exception:
                    dec = b""
                if dec[:3] == b"\xff\xd8\xff":
                    return [200, "image/jpeg", dec]
                if dec[:8] == b"\x89PNG\r\n\x1a\n":
                    return [200, "image/png", dec]
                if dec[:4] == b"RIFF" and dec[8:12] == b"WEBP":
                    return [200, "image/webp", dec]
                if dec[:3] == b"GIF":
                    return [200, "image/gif", dec]
                return [200, "image/jpeg", dec or ct]
            return [200, "image/jpeg", ct]
        except Exception:
            return [404, "text/plain", "err"]

    def localProxy(self, param):
        if not param:
            return [404, "text/plain", "nf"]
        typ = _hguo_pv(param, "type")
        url = _hguo_pv(param, "url") or _hguo_pv(param, "pic")
        if not url:
            return [404, "text/plain", "nf"]
        url = unquote(url)
        if typ == "m3u8":
            return self._proxy_m3u8(url)
        if typ == "ts":
            return self._proxy_ts(url)
        if typ == "key":
            return self._proxy_key(url)
        return self._proxy_pic(url)

# =====================================================================
#  聚合引擎 · Spider (对应 JS rule 的 class_parse/一级/二级/搜索/lazy)
#  d.push({title,img,desc,url})  ->  {vod_id:url, vod_name, vod_pic, vod_remarks}
# =====================================================================
class _AggSpider(_BaseSpider):
    def __init__(self):
        self.cfg = {}
        self.oauth_id_51 = ""
        self.proxy_img_51 = ""

    def getName(self):
        return "聚合短剧"

    def _proxy51(self, url):
        if self.proxy_img_51 and url:
            return self.proxy_img_51 + _ag_enc_uri(url)
        return url

    # ---------- 预处理 / 鉴权 ----------
    def prepare(self):
        cfg = self.cfg
        try:
            _AG_NN_Service.ensure_auth(cfg)
        except Exception:
            pass
        try:
            _AG_SH_Service.ensure_auth(cfg)
        except Exception:
            pass
        if not self.oauth_id_51:
            def repl(c):
                r = random.randint(0, 15)
                v = r if c == "x" else (r & 0x3 | 0x8)
                return format(v, "x")
            self.oauth_id_51 = re.sub(r"[xy]", lambda m: repl(m.group(0)),
                                      "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx")
        if not cfg.get("xingya_headers"):
            try:
                headers = {
                    "User-Agent": "okhttp/4.10.0", "Accept-Encoding": "gzip",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "x-app-id": "7", "platform": "1", "manufacturer": "realme",
                    "version_name": "3.3.1",
                    "user_agent": "Mozilla/5.0 (Linux; Android 9; RMX1931 Build/PQ3A.190605.05081124; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/91.0.4472.114 Mobile Safari/537.36",
                    "app_version": "3.3.1", "device_platform": "android",
                    "personalized_recommend_status": "1", "device_type": "RMX1931",
                    "device_brand": "realme", "os_version": "9", "channel": "default",
                    "raw_channel": "default", "oaid": "", "msa_oaid": "",
                    "uuid": "randomUUID_914e7a9b-deac-4f80-9247-db56669187df",
                    "device_id": "24250683a3bdb3f118dff25ba4b1cba1a", "ab_id": "",
                    "support_h265": "1",
                }
                body = ("device=24250683a3bdb3f118dff25ba4b1cba1a&install_first_open=false"
                        "&first_install_time=1723214205125&last_update_time=1723214205125"
                        "&report_link_url=")
                res = _ag_json(_ag_request(AGG_PLATFORM["星芽"]["loginUrl"], method="POST",
                                           headers=headers, body=body))
                token = (res.get("data") or {}).get("token")
                if token:
                    cfg["xingya_headers"] = dict(AGG_HEADERS["default"])
                    cfg["xingya_headers"].update({
                        "authorization": token,
                        "dev_token": "Bnf9uRPIcKTIOZasAUgUJAUDXhIOlB4lpDKsyLD4yvKm708G4J8PN1Z-gMaFgPwkRvqJrEje81VRxh41IaSj0lNWuoRLUg1r08Z1f0IqSv2q1lvfxrYckKavmnAPYLdkT9P1fPFNRt0RuN3DLLFZqApRDdPD3mM2jB6d79CF2LtM*",
                        "User-Agent": "okhttp/4.10.0",
                        "user_agent": "Mozilla/5.0 (Linux; Android 9; RMX1931 Build/PQ3A.190605.05081124; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/91.0.4472.114 Mobile Safari/537.36",
                        "app_version": "3.0.0.1", "version_name": "3.0.0.1", "support_h265": "1",
                    })
            except Exception:
                pass

    # ---------- class_parse ----------
    def classes(self):
        return [{"type_id": it["id"], "type_name": it["name"]} for it in AGG_PLATFORM_LIST]

    def filters(self):
        return AGG_FILTER

    # ---------- 一级 (分类) ----------
    def category(self, cate, area, page):
        cfg = self.cfg
        d = []
        plat = AGG_PLATFORM.get(cate, {})
        try:
            if cate == "河马":
                cid, cname = (area or "53@精选").split("@")
                body = {"recSwitch": True, "storePageId": 10002, "channelGroupId": "10",
                        "channelId": int(cid), "channelName": cname, "lastColumnStyle": 3,
                        "fromColumnId": "1", "pageFlag": str(page), "theaterSubscriptSwitch": True}
                res = _AG_HM_Service.api("1125", body)
                cols = res.get("columnData") if isinstance(res, dict) else None
                if cols and cols[0]:
                    for vod in cols[0].get("videoData", []):
                        d.append({"title": vod.get("bookName"), "img": vod.get("coverWap"),
                                  "desc": "河马 | 更新%s集" % vod.get("updateNum"),
                                  "url": "河马@%s" % vod.get("bookId")})
                return d
            if cate == "百度":
                t = int(time.time())
                version = _ag_md5(str(t) + "v2")
                fl_class = "新剧"
                body = json.dumps({"data": {
                    "refreshIndex": int(page), "timestamp": t, "version": version,
                    "themes": [{"kind": "综合", "names": [fl_class]},
                               {"kind": "题材", "names": ["" if area == "全部" else area]}],
                    "extRequest": {"flow_tabid": "13"}, "from": "feed",
                    "page": "channel_video_landing", "pd": "feed", "theme": ""}}, ensure_ascii=False)
                res = _ag_post("https://mbd.baidu.com/feedapi/v1/videoserver/playlets/list?service=bdbox",
                               "data=" + body, AGG_HEADERS["baidu_app"])
                for it in ((res.get("data") or {}).get("items") or []):
                    d.append({"title": it.get("title"), "img": it.get("img"),
                              "desc": "百度 | %s" % (it.get("updateStatus") or "全集"),
                              "url": "百度@%s" % it.get("collId")})
                return d
            if cate == "牛牛":
                res = _AG_NN_Service.api(cfg, "%s/api/v1/app/screen/screenMovie" % plat["host"],
                                         {"condition": {"classify": "" if area == "全部" else area,
                                                        "typeId": "S1"}, "pageNum": page, "pageSize": 40})
                for item in ((res.get("data") or {}).get("records") or []):
                    d.append({"title": item.get("name"), "url": "牛牛@%s" % item.get("id"),
                              "desc": "牛牛 | 共%s集" % item.get("totalEpisode"), "img": item.get("cover")})
                return d
            if cate == "山海":
                url = ("%s/shanhai-theater/v2/theater_parent/cloud/v2/theater/home_page"
                       "?theater_class_id=1&type=1&class2_ids=%s&page_num=%s&page_size=24"
                       % (plat["host"], area, page))
                res = _AG_SH_Service.request(cfg, url)
                for item in (res.get("items") or []):
                    th = item.get("theater", {})
                    d.append({"title": th.get("title"), "desc": "山海 | 共%s集" % th.get("total"),
                              "img": th.get("cover_url"), "url": "山海@%s" % th.get("id")})
                return d
            if cate == "好看":
                body = "tag_id=%s&pn=%s&rn=12" % (area, page)
                res = _ag_post("%s/haokan/ui-feed/playletTagsFeed?log=vhk&tn=1020970b&ctn=1008350n&blur=1"
                               % plat["host"], body, AGG_HEADERS["browser"])
                for item in ((res.get("data") or {}).get("list") or []):
                    d.append({"title": item.get("playlet_title"),
                              "desc": "好看 | 更新%s集" % item.get("episodes_num"),
                              "img": item.get("playlet_poster"),
                              "url": "好看@%s@%s" % (item.get("playlet_id"), item.get("progress_vid"))})
                return d
            if cate == "星芽":
                if not cfg.get("xingya_headers"):
                    self.prepare()
                headers = cfg.get("xingya_headers") or AGG_HEADERS["default"]
                url = ("%s%s&type=1&class2_ids=0&page_num=%s&page_size=24"
                       % (plat["host"], plat["url1"].replace("theater_class_id",
                                                              "theater_class_id=" + str(area)), page))
                r = _ag_fetch(url, headers=headers)
                for it in (((r.get("data") or {}).get("list")) or []):
                    th = it.get("theater", {})
                    d.append({"title": th.get("title"), "img": th.get("cover_url"),
                              "desc": "星芽 | %s集" % th.get("total"),
                              "url": "星芽@%s%s?theater_parent_id=%s"
                                     % (plat["host"], plat["url2"], th.get("id"))})
                return d
            if cate == "西饭":
                parts = area.split("@") if area else ["68", "都市"]
                type_id = parts[0] or "68"
                type_name = parts[1] if len(parts) > 1 else "都市"
                url = ("%s%s?reqType=aggregationPage&offset=%s&categoryId=%s&categoryNames=%s"
                       "&pageID=page_theater&appId=drama"
                       % (plat["host"], plat["url1"], (int(page) - 1) * 30, type_id,
                          _ag_enc_uri(type_name)))
                res = _ag_fetch(url)
                for soup in ((res.get("result") or {}).get("elements") or []):
                    for vod in soup.get("contents", []):
                        dj = vod.get("duanjuVo", {})
                        d.append({"title": dj.get("title"), "img": dj.get("coverImageUrl"),
                                  "desc": "西饭 | %s集" % dj.get("total"),
                                  "url": "西饭@%s#%s" % (dj.get("duanjuId"), dj.get("source"))})
                return d
            if cate == "七猫":
                sign = _ag_md5("operation=1playlet_privacy=1tag_id=%s%s" % (area, AGG_KEYS))
                url = ("%s%s?tag_id=%s&playlet_privacy=1&operation=1&sign=%s"
                       % (plat["host"], plat["url1"], area, sign))
                headers = dict(_ag_get_header_x())
                headers.update(AGG_HEADERS["qimao"])
                res = _ag_json(_ag_request(url, headers=headers))
                for item in ((res.get("data") or {}).get("list") or []):
                    d.append({"title": item.get("title"), "img": item.get("image_link"),
                              "desc": "七猫 | %s集" % item.get("total_episode_num"),
                              "url": "七猫@%s" % _ag_enc_uri(item.get("playlet_id"))})
                return d
            if cate == "51":
                url = "%s%s/%s" % (plat["host"], plat["list"], area)
                if int(page) > 1:
                    url += "/page/%s" % page
                resp = _ag_request(url, method="GET", headers=_AG_HEADER_51, timeout=15)
                for v in _ag_51_parse_home(resp, self._proxy51):
                    d.append({"title": v["vod_name"], "img": v["vod_pic"],
                              "desc": v["vod_remarks"], "url": v["vod_id"]})
                return d
            if cate == "星星":
                url = "%s%s" % (plat["host"], plat["list"])
                params = {"productId": "2a8c14d1-72e7-498b-af23-381028eb47c0",
                          "vestId": "2be070e0-c824-4d0e-a67a-8f688890cadb", "channel": "oppo19",
                          "osType": "android", "version": "20",
                          "token": "202509271001001446030204698626", "resourceId": area,
                          "pageNum": str(page), "pageSize": "20"}
                resp = _ag_request("%s?%s" % (url, _ag_build_query(params)),
                                   headers=AGG_HEADERS["xingxing"])
                res = _ag_json(resp)
                for vod in ((res.get("data") or {}).get("datalist") or []):
                    d.append({"title": vod.get("name") or "", "img": vod.get("icon") or "",
                              "desc": "星星 | %s万播放" % (vod.get("heat") or 0),
                              "url": "星星@%s@%s@%s" % (vod.get("id"),
                                                       _ag_enc_uri(vod.get("name") or ""),
                                                       _ag_enc_uri(vod.get("introduction") or ""))})
                return d
            if cate == "围观":
                res = _ag_request("%s%s" % (plat["host"], plat["search"]), method="POST",
                                  headers={"content-type": "application/json; charset=utf-8"},
                                  body=json.dumps({"audience": "全部受众", "page": page,
                                                   "pageSize": 30, "searchWord": "",
                                                   "subject": "全部主题"}, ensure_ascii=False))
                j = _ag_json(res)
                for it in (j.get("data") or []):
                    d.append({"title": it.get("title"), "img": it.get("vertPoster"),
                              "desc": "围观 | %s集" % it.get("episodeCount"),
                              "url": "围观@%s" % it.get("oneId")})
                return d
            if cate == "薏米":
                path = "/bookstore/local/visual/channel/list"
                base = ("key=%s&p1=1750574688516674369&p16=22081212C&p2=341201&p21=10&p22=15"
                        "&p24=0&p25=21200&p28=cca83346da195d11&p29=zy9351ae&p3=102120009"
                        "&p31=29d1af74b128f29f&p33=com.zhangyue.app.shortplay&p34=force_fsg_nav_bar"
                        "&p35=BUZGFVakskazFWG2XwZ/LNs4fOnQczc4iivy1qLFvZqmerp2Abe2hv5Tu1jOHQJO5PGANizg3JbzgaTOon0qkmQ=="
                        "&p4=501609&p5=16&p7=cca83346da195d11&p9=3&page=%s&pc=10&usr=tj1290623468"
                        "&zyeid=4fc4c6737a87b603e1b8ce9210032bae" % (area, page))
                headers = _ag_yimi_headers(path, base, "AAF4IWZnITkqeX4hJCB5eio4IWc4IH4=")
                url = plat["host"] + path + "?" + base
                resp = _ag_request(url, headers=headers, method="GET")
                j = _ag_json(resp)
                lst = (((j.get("body") or {}).get("list") or [{}])[0] or {}).get("short_plays") or []
                for item in lst:
                    d.append({"title": item.get("short_play_name"), "img": item.get("cover_url"),
                              "desc": "薏米 | 热度值:%s" % (item.get("favor_count_format") or 0),
                              "url": "薏米@%s" % item.get("id")})
                return d
            if cate == "爽爽":
                fa = area or "女频恋爱"
                html = _ag_request("%s/show/duanju---%s-----%s---.html" % (plat["host"], _ag_enc_uri(fa), page),
                                   headers={"User-Agent": _AG_MOBILE_UA})
                for card in re.findall(r'<div class="a-con-inner">[\s\S]*?</div>(?=\s*<div class="a-con-inner"|$)',
                                       html, re.I):
                    tm = re.search(r'<a[^>]*title="([^"]+)"[^>]*>', card)
                    um = re.search(r'<a[^>]*href="([^"]+)"[^>]*>', card)
                    if not (tm and um):
                        continue
                    pm = re.search(r'<img[^>]*data-original="([^"]+)"', card)
                    rm = re.search(r'<span[^>]*>([^<]+)</span>', card)
                    d.append({"title": tm.group(1), "img": pm.group(1) if pm else "",
                              "desc": "爽爽短剧 | %s" % (rm.group(1) if rm else ""),
                              "url": "爽爽@%s" % _ag_enc_uri(um.group(1))})
                return d
            if cate == "喜福":
                url = "%s%s?pageSize=24&currentPage=%s" % (plat["host"], plat["dramaList"], page)
                if area:
                    url += "&filterCategories[]=%s" % _ag_enc_uri(area)
                res = _ag_fetch(url, headers={"User-Agent": _AG_OLD_UA})
                for v in ((res.get("data") or {}).get("data") or []):
                    d.append({"title": v.get("title"), "img": v.get("coverUrl"),
                              "desc": "喜福短剧 | 共%s集" % (v.get("total") or 0),
                              "url": "喜福@%s@%s@%s@%s" % (v.get("albumId"), v.get("total") or 1,
                                                          _ag_enc_uri(v.get("title") or ""),
                                                          _ag_enc_uri(v.get("coverUrl") or ""))})
                return d
            if cate == "五五":
                if area and area != "全部":
                    url = "%s%s%s/id/1.html" % (plat["host"], plat["list"], _ag_enc_uri(area))
                else:
                    url = "%s%s" % (plat["host"], plat.get("type", "/index.php/vod/type/id/1.html"))
                if int(page) > 1:
                    url += "?page=%s" % page
                html = _ag_request(url, headers=AGG_HEADERS["default"])
                for v in _ag_parse_wuwu_list(html, plat["host"]):
                    d.append({"title": v["name"], "img": v["pic"],
                              "desc": "五五短剧 | %s" % v["rem"], "url": "五五@%s" % v["id"]})
                return d
        except Exception:
            pass
        return d

    # ---------- 二级 (详情) ----------
    def detail(self, or_id):
        cfg = self.cfg
        parts = or_id.split("@")
        platform = parts[0]
        vid = "@".join(parts[1:])
        plat = AGG_PLATFORM.get(platform, {})
        VOD = {}
        try:
            if platform == "河马":
                book_id = vid
                res = _AG_HM_Service.api("1131", {"bookId": book_id})
                if res.get("videoInfo"):
                    v = res["videoInfo"]
                    list_res = _AG_HM_Service.api("1132", {"bookId": book_id,
                                                           "chapterMin": 1, "chapterMax": 10000})
                    chapters = list_res.get("chapterList") or []
                    eps = ["%s$%s++%s++%s" % (c.get("chapterName"), c.get("chapterId"),
                                              c.get("chapterIndex"), book_id) for c in chapters]
                    return {"vod_name": v.get("bookName"), "vod_pic": v.get("coverWap"),
                            "vod_id": or_id, "vod_remarks": v.get("finishStatusCn"),
                            "vod_content": v.get("introduction") or "",
                            "vod_play_from": "河马短剧", "vod_play_url": "#".join(eps)}
            elif platform == "百度":
                res = _ag_post("https://sv.baidu.com/haokan/ui-video/playlet/rec/detail?log=vhk&tn=1020970b&ctn=1008350n&blur=1",
                               "playlet_id=%s&vid=undefined" % vid, AGG_HEADERS["browser"]).get("data", {})
                eps = ["第%s集$%s" % (i + 1, v) for i, v in enumerate(res.get("vid_list") or [])]
                return {"vod_name": res.get("playlet_title"), "vod_pic": res.get("playlet_poster"),
                        "vod_remarks": "热度:%s" % res.get("hot_value"),
                        "vod_content": res.get("description"),
                        "vod_play_from": "百度短剧", "vod_play_url": "#".join(eps)}
            elif platform == "牛牛":
                desc_res = _AG_NN_Service.api(cfg, "%s/api/v1/app/play/movieDesc" % plat["host"],
                                              {"id": vid, "typeId": "S1"}).get("data", {})
                list_res = _AG_NN_Service.api(cfg, "%s/api/v1/app/play/movieDetails" % plat["host"],
                                              {"id": vid, "source": 0, "typeId": "S1",
                                               "userId": "546932"}).get("data", {})
                eps = []
                if list_res.get("episodeList"):
                    eps = ["%s$%s+%s+free" % (item.get("episode"), item.get("id"), vid)
                           for item in list_res["episodeList"]]
                if not eps and list_res.get("thirdPlayId"):
                    t = str(int(time.time()))
                    data1 = ("not_include=0&lock_free=1&type=1&clientVersion=v5.2.5"
                             "&uuid=6IDYUSASPQY5BBVACWQW3LLTPV4V7DE26UOCX5TZTVUGX4VUJNXQ01"
                             "&resolution=1080*2320&openudid=82f4175d577a2939&dt=22021211RC"
                             "&os_api=31&install_id=1496879012031075&sdk_version=1.1.3.0"
                             "&siteid=5627189&dev_log_aid=667431&oaid=&timestamp=%s&direction=0"
                             "&ac=mobile&os=Android&vod_version=1.10.21.6-tob&os_version=12"
                             "&count=1&index=1&shortplay_id=%s"
                             "&sha1=46121F77CE2FCAD3DBC3B9EC8A24908C1A8AD6D9&device_brand=Redmi"
                             "&package_name=com.niuniu.ztdh.app" % (t, list_res["thirdPlayId"]))
                    html1 = _AG_NN_Service.post1(cfg,
                                                 "%s/csj_sp/api/v1/shortplay/detail?siteid=5627189" % plat["url1"],
                                                 data1)
                    erl = ((html1.get("data") or {}).get("episode_right_list")) if html1 else None
                    if erl:
                        eps = ["第%s集$%s+%s+%s" % (it.get("index"), it.get("index"),
                                                   it.get("lock_type"), list_res["thirdPlayId"])
                               for it in erl]
                return {"vod_name": desc_res.get("name"), "vod_pic": desc_res.get("cover"),
                        "vod_remarks": "评分:%s" % desc_res.get("score"),
                        "vod_content": desc_res.get("introduce"),
                        "vod_play_from": "牛牛短剧", "vod_play_url": "#".join(eps)}
            elif platform == "山海":
                detail = _AG_SH_Service.request(cfg,
                                                "%s/shanhai-theater/v2/theater_parent/detail?theater_parent_id=%s"
                                                % (plat["host"], vid))
                eps = ["%s$%s" % (item.get("son_title"), item.get("son_video_url"))
                       for item in detail.get("theaters", [])]
                return {"vod_name": detail.get("title"), "vod_pic": detail.get("cover_url"),
                        "vod_remarks": "标签:%s" % " ".join(detail.get("desc_tags", [])),
                        "vod_content": detail.get("introduction"),
                        "vod_play_from": "山海短剧", "vod_play_url": "#".join(eps)}
            elif platform == "好看":
                pid, hkvid = (vid.split("@") + [""])[:2]
                res = _ag_post("%s/haokan/ui-video/playlet/rec/detail?log=vhk&tn=1020970b&ctn=1008350n&blur=1"
                               % plat["host"], "playlet_id=%s&vid=%s" % (pid, hkvid),
                               AGG_HEADERS["browser"]).get("data", {})
                eps = ["第%s集$%s" % (i + 1, v) for i, v in enumerate(res.get("vid_list") or [])]
                return {"vod_name": res.get("playlet_title"), "vod_pic": res.get("playlet_poster"),
                        "vod_remarks": "更新:%s" % res.get("episodes_num"),
                        "vod_content": res.get("description"),
                        "vod_play_from": "好看短剧", "vod_play_url": "#".join(eps)}
            elif platform == "星芽":
                if not cfg.get("xingya_headers"):
                    self.prepare()
                headers = cfg.get("xingya_headers") or AGG_HEADERS["default"]
                res = _ag_json(_ag_request(vid, headers=headers))
                dd = res.get("data")
                if dd:
                    eps = ["第%s集$%s" % (i.get("num"), i.get("son_video_url"))
                           for i in (dd.get("theaters") or [])]
                    VOD = {"vod_name": dd.get("title"), "vod_pic": dd.get("cover_url"),
                           "vod_content": dd.get("introduction"), "vod_play_from": "星芽短剧",
                           "vod_play_url": "#".join(eps)}
            elif platform == "西饭":
                did, src = (vid.split("#") + [""])[:2]
                r = _ag_fetch("%s%s?duanjuId=%s&source=%s&appId=drama"
                              % (plat["host"], plat["url2"], did, src)).get("result", {})
                eps = ["%s$%s" % (i.get("index"), i.get("playUrl")) for i in r.get("episodeList", [])]
                VOD = {"vod_name": r.get("title"), "vod_pic": r.get("coverImageUrl"),
                       "vod_content": r.get("desc"), "vod_play_from": "西饭短剧",
                       "vod_play_url": "#".join(eps)}
            elif platform == "七猫":
                d = unquote(vid)
                sign = _ag_md5("playlet_id=%s%s" % (d, AGG_KEYS))
                headers = dict(_ag_get_header_x())
                headers.update(AGG_HEADERS["qimao"])
                headers["Content-Type"] = ""
                r = _ag_fetch("%s?playlet_id=%s&sign=%s" % (plat["url2"], d, sign),
                              headers=headers)
                rd = r.get("data", {})
                eps = ["%s$%s" % (i.get("sort"), i.get("video_url")) for i in rd.get("play_list", [])]
                VOD = {"vod_name": rd.get("title"), "vod_pic": rd.get("image_link"),
                       "vod_content": rd.get("intro"), "vod_play_from": "七猫短剧",
                       "vod_play_url": "#".join(eps)}
            elif platform == "围观":
                resp = _ag_request("%s%s&oneId=%s&page=1&pageSize=1000" % (plat["host"], plat["url2"], vid),
                                   headers=AGG_HEADERS["default"])
                r = _ag_json(resp)
                if r.get("data"):
                    data = r.get("data") or []
                    first = data[0] if data else {}
                    play_urls = []
                    for ep in data:
                        url = self._wg_pick_url(ep.get("playSetting")
                                                or ep.get("videoClarityList"))
                        if not url:
                            url = ep.get("playUrl") or ""
                        epid = ep.get("episodeOneId") or ep.get("oneId") or ""
                        title = "第%s集" % (ep.get("playOrder") or ep.get("episode") or (len(play_urls) + 1))
                        # 该站直链带时效签名，附 oneId/分集号，播放侧过期时可实时重签
                        play_urls.append("%s$%s@@%s@@%s" % (title, url, vid, epid))
                    VOD = {"vod_id": or_id, "vod_name": first.get("title") or "",
                           "vod_pic": first.get("vertPoster") or first.get("horizonPoster") or "",
                           "vod_remarks": "共%s集" % (len(data) or 0),
                           "vod_content": "播放量:%s 收藏:%s 评论:%s" % (
                               first.get("viewCount") or 0, first.get("collectionCount") or 0,
                               first.get("commentCount") or 0),
                           "vod_play_from": "围观短剧", "vod_play_url": "#".join(play_urls)}
            elif platform == "51":
                # 51hub 已改版为 Nuxt SSR：直接解析 play 页内嵌 devalue 负载
                html = _ag_request("%s/play/%s/1/" % (plat["host"], vid),
                                   headers=_AG_HEADER_51, timeout=15)
                info = _ag_51_nuxt_series(html)
                if info:
                    play_urls = []
                    for ep in info.get("_episodes", []):
                        idx = ep.get("index") or ep.get("sort")
                        title = ep.get("episode_title") or ("第%s集" % (ep.get("sort") or idx))
                        # 逐集直链需访问对应分集页，播放时经 player 解析：token=51ep|playlet_id|index
                        play_urls.append("%s$51ep|%s|%s" % (title, vid, idx))
                    if not play_urls:
                        play_urls = ["第1集$51ep|%s|1" % vid]
                    pic = info.get("cover_img") or ""
                    remarks = info.get("update_status") or (
                        "全%s集" % info.get("total_serial") if info.get("total_serial") else "")
                    VOD = {"vod_id": or_id,
                           "vod_name": info.get("drama_name") or info.get("video_title") or "未知短剧",
                           "vod_pic": self._proxy51(pic),
                           "vod_remarks": remarks,
                           "vod_content": info.get("description") or "暂无简介",
                           "vod_play_from": "五一短剧",
                           "vod_play_url": "#".join(play_urls) or "暂无播放地址$0"}
            elif platform == "星星":
                pa = vid.split("@")
                book_id = pa[0]
                vod_name = unquote(pa[1]) if len(pa) > 1 else ""
                content_desc = unquote(pa[2]) if len(pa) > 2 else ""
                url = "%s%s" % (plat["host"], plat["detail"])
                params = {"bookId": book_id, "productId": "2a8c14d1-72e7-498b-af23-381028eb47c0",
                          "vestId": "2be070e0-c824-4d0e-a67a-8f688890cadb", "channel": "oppo19",
                          "osType": "android", "version": "20",
                          "token": "202509271001001446030204698626"}
                resp = _ag_request("%s?%s" % (url, _ag_build_query(params)),
                                   headers=AGG_HEADERS["xingxing"])
                res = _ag_json(resp)
                data = res.get("data") or []
                play_urls = []
                for i, vi in enumerate(data):
                    pu = ""
                    spl = vi.get("shortPlayList") or []
                    if spl:
                        cs = spl[0].get("chapterShortPlayVoList") or []
                        if cs:
                            pu = cs[0].get("shortPlayUrl") or ""
                    if pu:
                        play_urls.append("第%s集$%s" % (i + 1, pu))
                VOD = {"vod_id": or_id, "vod_name": vod_name or "未知短剧",
                       "vod_content": content_desc, "vod_play_from": "星星短剧",
                       "vod_play_url": "#".join(play_urls) or "暂无播放地址$0"}
            elif platform == "薏米":
                play_id = vid
                path = "/video/client/short_play/episode_list"
                page_size = 30
                start_id = 1
                total = 999999
                episodes = []
                body = {}
                original = ("end_id=30&p1=1750574688516674369&p16=22081212C&p2=341201&p21=10&p22=15"
                            "&p24=0&p25=21200&p28=cca83346da195d11&p29=zy9351ae&p3=102120009"
                            "&p31=29d1af74b128f29f&p33=com.zhangyue.app.shortplay&p34=force_fsg_nav_bar"
                            "&p35=BUZGFVakskazFWG2XwZ/LNs4fOnQczc4iivy1qLFvZqmerp2Abe2hv5Tu1jOHQJO5PGANizg3JbzgaTOon0qkmQ=="
                            "&p4=501609&p5=16&p7=cca83346da195d11&p9=3&pc=10&play_id=%s"
                            "&start_id=1&usr=tj1290623468&zyeid=4fc4c6737a87b603e1b8ce9210032bae" % play_id)

                def repl_param(s, k, v):
                    return re.sub(r"(" + re.escape(k) + r"=)[^&]*", r"\g<1>" + str(v), s)

                while start_id <= total:
                    end_id = start_id + page_size - 1
                    s1 = repl_param(original, "start_id", start_id)
                    s1 = repl_param(s1, "end_id", end_id)
                    headers = _ag_yimi_headers(path, s1, "AAFzKmZkKjIqenUqJCNycSo7Kmw4I3U=")
                    url = plat["host"] + path + "?" + s1
                    resp = _ag_request(url, headers=headers, method="GET")
                    j = _ag_json(resp)
                    body = j.get("body") or {}
                    lst = body.get("episode_list") or []
                    if not lst:
                        break
                    if start_id == 1:
                        total = body.get("target_count") or total
                    for ep in lst:
                        play_url = ep.get("play_url") or ""
                        if "zhangyuecdn" in play_url:
                            play_url = "https://mother-t.d.ireader.com" + play_url.split("com", 1)[1]
                        episodes.append("第%s集$%s" % (ep.get("order"), play_url))
                    start_id += page_size
                VOD = {"vod_name": body.get("name") or "未知剧名", "vod_pic": "",
                       "vod_content": body.get("introduce") or "", "vod_play_from": "薏米短剧",
                       "vod_play_url": "#".join(episodes)}
            elif platform == "爽爽":
                du = unquote(vid)
                du = du if du.startswith("http") else plat["host"] + du
                html0 = _ag_request(du, headers={"User-Agent": _AG_MOBILE_UA})
                fpu = du
                mv = re.search(
                    r'<div[^>]*class=["\']movbox["\'][^>]*>[\s\S]*?<a[^>]*href=["\']([^"\']+)["\']',
                    html0, re.I)
                if mv:
                    fpu = mv.group(1)
                else:
                    plk = re.search(r'<a[^>]*href=["\']([^"\']*/play/[^"\']+)["\']', html0, re.I)
                    if plk:
                        fpu = plk.group(1)
                if not fpu.startswith("http"):
                    fpu = plat["host"] + fpu
                play_html = _ag_request(fpu, headers={"User-Agent": _AG_MOBILE_UA})
                tabs, tab_urls = [], []
                xl = re.search(r'<div[^>]*class=["\']xianlu["\'][^>]*>([\s\S]*?)</div>', play_html, re.I)
                if xl:
                    for mo in re.finditer(r'<a[^>]*>([\s\S]*?)</a>', xl.group(1), re.I):
                        th = mo.group(0)
                        hr = re.search(r'href=["\']([^"\']+)["\']', th, re.I)
                        if not hr:
                            continue
                        line = re.sub(r'<[^>]+>', '', th).strip()
                        sm = re.search(r'<small[^>]*>([^<]+)</small>', th, re.I)
                        if sm:
                            line = line.replace(sm.group(1), '').strip()
                        tabs.append(line or "爽爽短剧")
                        u = hr.group(1)
                        if 'javascript' in u:
                            u = fpu
                        elif not u.startswith('http'):
                            u = plat["host"] + u
                        tab_urls.append(u)
                if not tab_urls:
                    tabs.append("爽爽短剧")
                    tab_urls.append(fpu)
                vn_m = re.search(r'<h1[^>]*>([^<]+)</h1>', html0)
                vp_m = re.search(r'<img[^>]*data-original="([^"]+)"', html0)
                st = re.search(r'<p[^>]*class=["\'][^"\']*zhuangtai[^"\']*["\'][^>]*>([\s\S]*?)</p>',
                               html0, re.I)
                return {"vod_id": or_id,
                        "vod_name": vn_m.group(1).strip() if vn_m else "爽爽短剧",
                        "vod_pic": vp_m.group(1) if vp_m else "",
                        "vod_remarks": re.sub(r'<[^>]+>', '', st.group(1)).strip() if st else "爽爽短剧",
                        "vod_content": "",
                        "vod_play_from": "$$$".join(tabs),
                        "vod_play_url": "$$$".join(["全集$%s" % u for u in tab_urls])}
            elif platform == "喜福":
                dp = vid.split("@")
                aid = dp[0]
                try:
                    total = max(1, min(1000, int(dp[1]))) if len(dp) > 1 else 1
                except (TypeError, ValueError):
                    total = 1
                eps = ["第%s集$%s@%s" % (i, aid, i) for i in range(1, total + 1)]
                xname = unquote(dp[2]) if len(dp) > 2 and dp[2] else "喜福短剧"
                xpic = unquote(dp[3]) if len(dp) > 3 and dp[3] else ""
                if xpic and not xpic.startswith("http"):
                    xpic = ""
                return {"vod_id": or_id, "vod_name": xname, "vod_pic": xpic,
                        "vod_remarks": "共%s集" % total, "vod_content": "",
                        "vod_play_from": "喜福短剧",
                        "vod_play_url": "#".join(eps) or "暂无播放地址$0"}
            elif platform == "五五":
                html = _ag_request("%s%s%s.html" % (plat["host"], plat["detail"], vid),
                                   headers=AGG_HEADERS["default"])
                tm = re.search(r'<title>(.*?)</title>', html, re.I)
                nm = re.search(r'<h1[^>]*class="[^"]*\bDramaDetail_bookName\b[^"]*"[^>]*>([\s\S]*?)</h1>',
                               html, re.I)
                im = re.search(r'<img[^>]*class="[^"]*\bDramaDetail_bookCover\b[^"]*"[^>]*\bsrc="([^"]+)"',
                               html, re.I) or re.search(r'property="og:image"[^>]+content="([^"]+)"',
                                                        html, re.I)
                cm = re.search(r'class="[^"]*(?:detail-content|vod-content|descr|intro)[^"]*"'
                               r'[^>]*>([\s\S]*?)</div>', html, re.I)
                sources, urls = [], []
                # 线路区块：新版结构是 <div class="pcDrama_contentBox"> → <h3 class="pcDrama_titleText"> → <a class="pcDrama_catalogItem">
                for box in re.split(r'<div class="pcDrama_contentBox', html)[1:]:
                    title_m = re.search(r'pcDrama_titleText">([\s\S]*?)</h3>', box, re.I)
                    if not title_m:
                        continue
                    line = re.sub(r'<[^>]+>', '', title_m.group(1)).strip()
                    eps = []
                    for mo in re.finditer(
                            r'<a[^>]*class="[^"]*\bpcDrama_catalogItem\b[^"]*"[^>]*'
                            r'href="([^"]*vod/play/id/\d+/sid/\d+/nid/(\d+)\.html)"[^>]*>([\s\S]*?)</a>',
                            box, re.I):
                        eps.append({"nid": int(mo.group(2)),
                                    "name": re.sub(r'<[^>]+>', '', mo.group(3)).strip()
                                            or ("第%s集" % mo.group(2)),
                                    "href": mo.group(1)})
                    if eps:
                        eps.sort(key=lambda x: x["nid"])
                        sources.append(line or "五五短剧")
                        urls.append("#".join(
                            ["%s$%s" % (e["name"], e["href"] if e["href"].startswith("http")
                                        else plat["host"] + e["href"]) for e in eps]))
                vn = (re.sub(r'<[^>]+>', '', nm.group(1)).strip() if nm else
                      (re.split(r'[-_|]', tm.group(1))[0].strip() if tm else "五五短剧"))
                return {"vod_id": or_id, "vod_name": vn,
                        "vod_pic": (im.group(1) if im.group(1).startswith("http")
                                    else plat["host"] + im.group(1)) if im else "",
                        "vod_content": re.sub(r'<[^>]+>', '', cm.group(1)).strip() if cm else "",
                        "vod_play_from": "$$$".join(sources) or "五五短剧",
                        "vod_play_url": "$$$".join(urls) or "暂无播放地址$0"}
        except Exception:
            pass
        if VOD and not VOD.get("vod_id"):
            VOD["vod_id"] = or_id
        return VOD

    # ---------- 搜索 ----------
    def search(self, key, page):
        cfg = self.cfg
        results = []
        for p in AGG_PLATFORM_LIST:
            pid = p["id"]
            plat = AGG_PLATFORM[pid]
            try:
                if pid == "七猫":
                    track_id = "ec1280db127955061754851657967"
                    enc_wd = _ag_enc_uri(key)
                    sign = _ag_md5("extend=page=%sread_preference=0track_id=%swd=%s%s"
                                   % (page, track_id, enc_wd, AGG_KEYS))
                    url = ("%s%s?extend=&page=%s&wd=%s&read_preference=0&track_id=%s&sign=%s"
                           % (plat["host"], plat["search"], page, enc_wd, track_id, sign))
                    headers = dict(_ag_get_header_x())
                    headers.update(AGG_HEADERS["qimao"])
                    headers.pop("Content-Type", None)
                    headers.pop("content-type", None)
                    headers.pop("User-Agent", None)
                    res = _ag_json(_ag_request(url, headers=headers))
                    for item in ((res.get("data") or {}).get("list") or []):
                        clean = re.sub(r"<[^>]+>", "", item.get("title") or "").strip()
                        eps = (item.get("total_num") or "0").replace("集", "")
                        results.append({"title": clean, "img": item.get("image_link"),
                                        "desc": "七猫 | %s集" % eps,
                                        "url": "七猫@%s" % _ag_enc_uri(item.get("id"))})
                elif pid == "牛牛":
                    _AG_NN_Service.ensure_auth(cfg)
                    if not cfg.get("nn_token"):
                        continue
                    res = _AG_NN_Service.api(cfg, "%s/api/v1/app/search/searchMovie" % plat["host"],
                                             {"condition": {"typeId": "S1", "value": key},
                                              "pageNum": page, "pageSize": 40})
                    for i in ((res.get("data") or {}).get("records") or []):
                        results.append({"title": i.get("name"), "url": "牛牛@%s" % i.get("id"),
                                        "desc": "牛牛 | %s" % i.get("type"), "img": i.get("cover")})
                elif pid == "河马":
                    body = {"keyword": key, "page": int(page), "size": 15,
                            "searchSource": "搜索按钮", "hotWordType": 2, "tagIds": "",
                            "reservationSwitch": True}
                    res = _AG_HM_Service.api("1803", body)
                    for vod in (res.get("searchVos") or []):
                        results.append({"title": vod.get("bookName"), "img": vod.get("coverWap"),
                                        "desc": "河马 | 更新%s集" % vod.get("updateNum"),
                                        "url": "河马@%s" % vod.get("bookId")})
                elif pid == "百度":
                    body = json.dumps({"query": key, "page": page, "attribute": ["title"],
                                       "fe_page_type": "search",
                                       "extra": {"tab_id": "216", "flow_tabid": "13",
                                                 "shortplay_source": "feed", "from": "feed",
                                                 "tab_type": "搜索",
                                                 "sub_template": "playlet_search_result"}},
                                      ensure_ascii=False)
                    res = _ag_post("https://mbd.baidu.com/feedapi/v1/videoserver/playlets/search?service=bdbox",
                                   "data=" + body, AGG_HEADERS["baidu_app"])
                    for it in ((res.get("data") or {}).get("itemList") or []):
                        nid = (it.get("nid") or "_").split("_")
                        results.append({"title": it.get("title"), "img": it.get("img"),
                                        "url": "百度@%s" % (nid[1] if len(nid) > 1 else ""),
                                        "desc": "百度 | %s集" % (it.get("collNum") or "")})
                elif pid == "山海":
                    res = _ag_post("%s/v3/search" % plat["host"], {"text": key},
                                   {"authorization": cfg.get("sh_token", ""),
                                    "Content-Type": "application/json"})
                    for i in (((res.get("data") or {}).get("theater") or {}).get("search_data") or []):
                        results.append({"title": i.get("title"), "url": "山海@%s" % i.get("id"),
                                        "desc": "山海 | %s集" % i.get("total"), "img": i.get("cover_url")})
                elif pid == "好看":
                    body = "method=get&pn=1&rn=10&v=2&word=%s" % _ag_enc_uri(key)
                    res = _ag_post("%s/haokan/api?cmd=search/sug&log=vhk&tn=1020970b&ctn=1008350n&blur=1&word=%s"
                                   % (plat["host"], _ag_enc_uri(key)), body,
                                   AGG_HEADERS["browser"])
                    lst = (((res.get("search/sug") or {}).get("data") or {}).get("list") or [])
                    for i in lst:
                        if i.get("tplName") == "sug_playlet":
                            results.append({"title": i.get("title"), "img": i.get("cover_url"),
                                            "desc": "好看 | 热度:%s" % i.get("hot_value"),
                                            "url": "好看@%s@" % i.get("id")})
                elif pid == "星芽":
                    if not cfg.get("xingya_headers"):
                        self.prepare()
                    headers = dict(cfg.get("xingya_headers") or AGG_HEADERS["default"])
                    headers["Content-Type"] = "application/json"
                    res = _ag_post(plat["host"] + plat["search"], {"text": key}, headers)
                    sd = (((res.get("data") or {}).get("theater") or {}).get("search_data"))
                    if sd:
                        for it in sd:
                            results.append({"title": it.get("title"),
                                            "desc": "星芽 | %s集" % (it.get("total") or 0),
                                            "img": it.get("cover_url"),
                                            "url": "星芽@%s%s?theater_parent_id=%s"
                                                   % (plat["host"], plat["url2"], it.get("id"))})
                elif pid == "西饭":
                    ts = int(time.time())
                    url = ("%s%s?reqType=search&offset=%s&keyword=%s&requestId=%saa498144140ef297&appId=drama"
                           % (plat["host"], plat["search"], (int(page) - 1) * 30,
                              _ag_enc_uri(key), ts))
                    res = _ag_json(_ag_request(url))
                    for vod in ((res.get("result") or {}).get("elements") or []):
                        dj = vod.get("duanjuVo", {})
                        results.append({"title": dj.get("title"), "img": dj.get("coverImageUrl"),
                                        "desc": "西饭 | %s集" % dj.get("total"),
                                        "url": "西饭@%s#%s" % (dj.get("duanjuId"), dj.get("source"))})
                elif pid == "51":
                    su = "%s%s/%s" % (plat["host"], plat["search"], _ag_enc_uri(key))
                    if int(page) > 1:
                        su += "/page/%s" % page
                    resp = _ag_request(su, method="GET", headers=_AG_HEADER_51)
                    for v in _ag_51_parse_search(resp, self._proxy51):
                        results.append({"title": v["vod_name"], "img": v["vod_pic"],
                                        "desc": v["vod_remarks"], "url": v["vod_id"]})
                elif pid == "围观":
                    res = _ag_request("%s%s" % (plat["host"], plat["search"]), method="POST",
                                      headers={"content-type": "application/json; charset=utf-8"},
                                      body=json.dumps({"audience": "全部受众", "page": page,
                                                       "pageSize": 30, "searchWord": key,
                                                       "subject": "全部主题"}, ensure_ascii=False))
                    j = _ag_json(res)
                    for it in (j.get("data") or []):
                        results.append({"title": it.get("title"), "img": it.get("vertPoster"),
                                        "desc": "围观 | %s集" % it.get("episodeCount"),
                                        "url": "围观@%s" % it.get("oneId")})
                elif pid == "薏米":
                    path = "/bookstore/search/recommend_data"
                    params = ("keyword=%s&p1=1750574688516674369&p16=22081212C&p2=341201&p21=3&p22=15"
                              "&p24=0&p25=21200&p28=cca83346da195d11&p29=zy9351ae&p3=102120009"
                              "&p31=29d1af74b128f29f&p33=com.zhangyue.app.shortplay&p34=force_fsg_nav_bar"
                              "&p35=BUZGFVakskazFWG2XwZ/LNs4fOnQczc4iivy1qLFvZqmerp2Abe2hv5Tu1jOHQJO5PGANizg3JbzgaTOon0qkmQ=="
                              "&p4=501609&p5=16&p7=cca83346da195d11&p9=3&page=%s&pc=10"
                              "&resource_type=short_play&size=10&sort=1&source_type=0,1&type=0"
                              "&usr=tj1290623468&zyeid=4fc4c6737a87b603e1b8ce9210032bae"
                              % (_ag_enc_uri(key), page))
                    headers = _ag_yimi_headers(path, params, "AAF4IWZnITkqeX4hJCB5eio4IWc4IH4=")
                    url = plat["host"] + path + "?" + params
                    resp = _ag_request(url, method="GET", headers=headers)
                    j = _ag_json(resp)
                    sp = (j.get("body") or {}).get("short_play") or {}
                    lst = sp.get("list") or []
                    tmp = [{"title": data.get("name"), "img": data.get("pic"),
                            "desc": "薏米 | 播放量:%s" % data.get("popularity"),
                            "url": "薏米@%s" % data.get("id")} for data in lst]
                    if tmp and key:
                        tmp = [it for it in tmp if it.get("title") and key in it["title"]]
                    results.extend(tmp)
                    continue
                elif pid == "爽爽":
                    html = _ag_request("%s%s?wd=%s" % (plat["host"], plat.get("searchUrl", ""),
                                                       _ag_enc_uri(key)),
                                       headers={"User-Agent": _AG_MOBILE_UA})
                    sc = re.search(r'<div[^>]*class="search-con"[^>]*>[\s\S]*?</div>', html)
                    if sc:
                        for it in re.findall(r'<li[^>]*>[\s\S]*?</li>', sc.group(0), re.I):
                            tm = re.search(r'<a[^>]*title="([^"]+)"[^>]*>', it)
                            um = re.search(r'<a[^>]*href="([^"]+)"[^>]*>', it)
                            if not (tm and um):
                                continue
                            pm = re.search(r'<img[^>]*data-original="([^"]+)"', it)
                            rm = re.search(r'<span[^>]*class="state"[^>]*>([^<]+)</span>', it)
                            results.append({"title": tm.group(1), "img": pm.group(1) if pm else "",
                                            "desc": "爽爽短剧 | %s" % (rm.group(1) if rm else ""),
                                            "url": "爽爽@%s" % _ag_enc_uri(um.group(1))})
                elif pid == "五五":
                    su = "%s%s%s.html" % (plat["host"], plat["search"], _ag_enc_uri(key))
                    if int(page) > 1:
                        su += "?page=%s" % page
                    html = _ag_request(su, headers=AGG_HEADERS["default"])
                    for v in _ag_parse_wuwu_list(html, plat["host"]):
                        results.append({"title": v["name"], "img": v["pic"],
                                        "desc": "五五短剧 | %s" % v["rem"], "url": "五五@%s" % v["id"]})
                elif pid == "星星":
                    continue  # 原 JS 搜索未实现星星
                elif pid == "喜福":
                    continue  # 原 JS 搜索未实现喜福
            except Exception:
                continue
        return results

    # ---------- lazy (播放解析) ----------
    def player(self, flag, play_id):
        cfg = self.cfg
        inp = play_id
        try:
            if "河马" in flag:
                arr = inp.split("++")
                chapter_id, chapter_index, book_id = arr[0], arr[1], arr[2]
                body = {"bookId": book_id, "chapterId": chapter_id, "unClockType": "pay",
                        "confirmPay": 2, "autoPayFlag": True,
                        "omap": {"channelName": "精选",
                                 "logId": "17a6500357709bb2547e1e122b438cfc",
                                 "originName": "书城", "recId": "bigdata_rec",
                                 "scene": "nsc_727", "sceneId": "dzmf_video_sc_reco",
                                 "strategyId": "g6y6b5sq"}}
                res = _AG_HM_Service.api("1133", body)
                if res.get("chaptersPayType") == "免费":
                    ci = res.get("chapterInfo")
                    if ci and ci[0] and ci[0].get("content"):
                        content = ci[0]["content"]
                        play_url = content.get("m3u8720p") or (
                            content.get("mp4SwitchUrl", [""])[0] if content.get("mp4SwitchUrl") else "")
                        return {"parse": 0, "url": play_url, "header": {"User-Agent": "okhttp/4.10.0"}}
                elif res.get("chaptersPayType") == "按章付费":
                    play_url = ("https://api.cenguigui.cn/api/duanju/hema.php?book_id=%s&video_id=%s&type=mp4"
                                % (book_id, chapter_index))
                    return {"parse": 0, "url": play_url}
                return {"parse": 0, "url": "toast://解析失败"}
            if "百度" in flag:
                html = _ag_post("https://sv.baidu.com/appui/api?cmd=video/relate&log=vhk&tn=1020970b&ctn=1008350n&blur=1",
                                "method=post&vid=" + inp, AGG_HEADERS["baidu_app"])
                j = (((html.get("video/relate") or {}).get("data") or {}).get("cur_video"))
                if j and j.get("clarityUrl"):
                    urls = sorted([i for i in j["clarityUrl"] if i.get("url")],
                                  key=lambda a: a.get("video_quality", 0), reverse=True)
                    if urls:
                        return {"parse": 0, "url": urls[0]["url"]}
                return {"parse": 0, "url": inp}
            if "牛牛" in flag:
                p = inp.split("+")
                if len(p) == 3 and p[2] == "free":
                    r = _AG_NN_Service.api(cfg, "https://new.tianjinzhitongdaohe.com/api/v1/app/play/movieDetails",
                                           {"id": p[1], "source": 0, "typeId": "S1",
                                            "userId": "546932", "episodeId": p[0]})
                    return {"parse": 0, "url": (r.get("data") or {}).get("url") or "toast://无法播放"}
                elif len(p) == 3:
                    if p[1] != "free":
                        unlock = ("ac=mobile&os=Android&vod_version=1.10.21.6-tob&os_version=12"
                                  "&lock_ad=3&lock_free=3&type=1&clientVersion=v5.2.5"
                                  "&uuid=6IDYUSASPQY5BBVACWQW3LLTPV4V7DE26UOCX5TZTVUGX4VUJNXQ01"
                                  "&resolution=1080*2320&openudid=82f4175d577a2939&dt=22021211RC"
                                  "&os_api=31&install_id=1496879012031075&device_brand=Redmi"
                                  "&sdk_version=1.1.3.0&package_name=com.niuniu.ztdh.app"
                                  "&siteid=5627189&dev_log_aid=667431&oaid=abec0dfff623201b"
                                  "&timestamp=1752498493")
                        _AG_NN_Service.post1(cfg,
                                             "https://csj-sp.csjdeveloper.com/csj_sp/api/v1/pay/ad_unlock?siteid=5627189",
                                             unlock, p[0])
                    data1 = ("not_include=0&lock_free=1&type=1&clientVersion=v5.2.5"
                             "&uuid=6IDYUSASPQY5BBVACWQW3LLTPV4V7DE26UOCX5TZTVUGX4VUJNXQ01"
                             "&resolution=1080*2320&openudid=82f4175d577a2939&dt=22021211RC"
                             "&os_api=31&install_id=1496879012031075&sdk_version=1.1.3.0"
                             "&siteid=5627189&dev_log_aid=667431&oaid=abec0dfff623201b"
                             "&timestamp=1752498494&direction=0&ac=mobile&os=Android"
                             "&vod_version=1.10.21.6-tob&os_version=12&count=1&index=1"
                             "&shortplay_id=" + p[2] +
                             "&sha1=46121F77CE2FCAD3DBC3B9EC8A24908C1A8AD6D9&device_brand=Redmi"
                             "&package_name=com.niuniu.ztdh.app")
                    r = _AG_NN_Service.post1(cfg,
                                             "https://csj-sp.csjdeveloper.com/csj_sp/api/v1/shortplay/detail?siteid=5627189",
                                             data1, p[0])
                    u = None
                    try:
                        u = r["data"]["list"][0]["video_model"]["video_list"]["video_1"]["main_url"]
                    except Exception:
                        u = None
                    play_url = base64.b64decode(u).decode("utf-8", "ignore") if u else "toast://解析失败"
                    return {"parse": 0, "url": play_url}
            if "好看" in flag:
                res = _ag_post("https://sv.baidu.com/appui/api?cmd=video/relate&log=vhk&tn=1020970b&ctn=1008350n&blur=1",
                               "method=post&vid=%s" % inp, AGG_HEADERS["browser"])
                lst = res["video/relate"]["data"]["cur_video"]["clarityUrl"]
                urls = []
                for i in lst:
                    urls.append(i.get("title"))
                    urls.append(i.get("url"))
                return {"parse": 0, "url": urls}
            if "围观" in flag:
                # 该站详情给的是带时效签名的 mp4 直链（super/high/normal 三档）。
                # 兼容三种入参：url@@oneId@@分集号 / 纯直链 / playSetting JSON。
                return self._wg_play(inp)
            # 爽爽：播放页 player_xxx JSON 里取直链
            if "爽爽" in flag or "djw123.com" in inp:
                pu = inp
                if not pu.startswith("http"):
                    seg = inp.split("@")
                    pu = seg[1] if len(seg) > 1 else inp
                    if not pu.startswith("http"):
                        pu = AGG_PLATFORM["爽爽"]["host"] + pu
                html = _ag_request(pu, headers={"User-Agent": _AG_MOBILE_UA})
                mo = (re.search(r'var player_[a-zA-Z0-9]+=(.*?)<', html)
                      or re.search(r'player_[a-zA-Z0-9]+=(.*?)<', html)
                      or re.search(r'(\{"flag":"play".*?\})', html))
                if mo:
                    pd = {}
                    try:
                        pd = json.loads(mo.group(1))
                    except Exception:
                        pd = {}
                    vu = pd.get("url") or ""
                    enc = str(pd.get("encrypt") or "")
                    if vu and enc == "1":
                        vu = unquote(vu)
                    elif vu and enc == "2":
                        try:
                            vu = base64.b64decode(vu).decode("utf-8", "ignore")
                        except Exception:
                            pass
                        if "%" in vu:
                            vu = unquote(vu)
                    if vu and vu.startswith("http"):
                        return {"parse": 0, "url": vu}
                vt = (re.search(r'<video[^>]*src=["\']([^"\']+)["\']', html, re.I)
                      or re.search(r'<source[^>]*src=["\']([^"\']+)["\']', html, re.I))
                if vt:
                    return {"parse": 0, "url": vt.group(1)}

            # 喜福：play_auth 取阿里云 VOD 凭证 → 本地签名换直链
            if "喜福" in flag:
                seg = inp.split("@")
                if len(seg) >= 2:
                    host_xf = AGG_PLATFORM["喜福"]["host"]
                    ar = _ag_fetch("%s%s?albumId=%s&seq=%s"
                                   % (host_xf, AGG_PLATFORM["喜福"]["playAuth"], seg[0], seg[1]),
                                   headers={"User-Agent": _AG_OLD_UA})
                    ad = ar.get("data") or {}
                    if ad.get("vid") and ad.get("playAuth"):
                        try:
                            cred = json.loads(base64.b64decode(ad["playAuth"]).decode("utf-8"))
                            params = {
                                "Action": "GetPlayInfo", "Version": "2017-03-21", "Format": "JSON",
                                "AccessKeyId": cred["AccessKeyId"],
                                "SecurityToken": cred["SecurityToken"],
                                "VideoId": ad["vid"], "AuthInfo": cred.get("AuthInfo", ""),
                                "Timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                                "SignatureMethod": "HMAC-SHA1", "SignatureVersion": "1.0",
                                "SignatureNonce": str(uuid.uuid4()),
                            }
                            if cred.get("PlayConfig"):
                                params["PlayConfig"] = json.dumps(cred["PlayConfig"])
                            cqs = "&".join(
                                ["%s=%s" % (quote(k, safe="-._~"), quote(str(params[k]), safe="-._~"))
                                 for k in sorted(params.keys())])
                            sts = "GET&%%2F&%s" % quote(cqs, safe="-._~")
                            sig = base64.b64encode(
                                hmac.new(("%s&" % cred["AccessKeySecret"]).encode("utf-8"),
                                         sts.encode("utf-8"), hashlib.sha1).digest()).decode("utf-8")
                            region = cred.get("Region") or "cn-shanghai"
                            vr = _ag_fetch("https://vod.%s.aliyuncs.com/?%s&Signature=%s"
                                           % (region, cqs, quote(sig, safe="-._~")),
                                           headers={"Accept": "*/*",
                                                    "Origin": "https://minidrama.contentchina.com",
                                                    "Referer": "https://minidrama.contentchina.com/",
                                                    "User-Agent": _AG_OLD_UA})
                            pi = ((vr.get("PlayInfoList") or {}).get("PlayInfo") or [])
                            if pi:
                                return {"parse": 0, "url": pi[0].get("PlayURL")}
                        except Exception:
                            pass
                return {"parse": 0, "url": inp}

            # 五五：播放页取 m3u8 / base64 直链 / iframe
            if "五五" in flag or "duanju55.com" in inp:
                html = _ag_request(inp, headers={"User-Agent": AGG_HEADERS["default"]["User-Agent"],
                                                 "Referer": "https://www.duanju55.com/"})
                vu = ""
                pm = (re.search(r'var\s+player_\w+\s*=\s*\{[\s\S]*?["\']url["\']\s*:\s*["\']([^"\']*)["\']',
                                html, re.I)
                      or re.search(r'["\']url["\']\s*:\s*["\']([^"\']*\.m3u8[^"\']*)["\']', html, re.I))
                if pm:
                    vu = pm.group(1).replace('\\/', '/')
                if not vu:
                    bm = re.search(r'["\']url["\']\s*:\s*["\']([^"\']+)["\']', html, re.I)
                    if bm and re.match(r'^[A-Za-z0-9+/=]{16,}$', bm.group(1)):
                        try:
                            vu = base64.b64decode(bm.group(1).strip()).decode("utf-8", "ignore")
                        except Exception:
                            vu = ""
                if not vu:
                    vm = (re.search(r'(?:https?:)?//[^\s"\'<>]+\.(?:m3u8|mp4)', html, re.I)
                          or re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html, re.I))
                    if vm:
                        vu = vm.group(1) if len(vm.groups()) > 0 else vm.group(0)
                if vu:
                    if vu.startswith('//'):
                        vu = 'https:' + vu
                    return {"parse": 0, "url": vu,
                            "header": {"User-Agent": AGG_HEADERS["default"]["User-Agent"],
                                       "Referer": "https://www.duanju55.com/"}}
                return {"parse": 0, "url": inp}

            # 五一：token 形如 '51ep|<playlet_id>|<index>'，取对应分集页的 m3u8 直链
            if inp.startswith("51ep|"):
                try:
                    _, pid, idx = inp.split("|", 2)
                except ValueError:
                    return {"parse": 0, "url": "toast://解析失败"}
                html = _ag_request("%s/play/%s/%s/" % (AGG_PLATFORM["51"]["host"], pid, idx),
                                   headers=_AG_HEADER_51, timeout=15)
                url = _ag_51_warm_m3u8(html)
                if url:
                    return {"parse": 0, "url": url,
                            "header": {"User-Agent": _AG_HEADER_51["User-Agent"],
                                       "Referer": "https://51hub.com/"}}
                return {"parse": 0, "url": "toast://解析失败"}
        except Exception:
            pass
        return {"parse": 0, "url": inp}

    # ---------- 围观短剧：直链取用 + 签名时效刷新 ----------
    _WG_SIGN_TTL = 120  # 签名保守有效期（秒），超过就重新签发，避免壳里缓存久了拿到 403

    @staticmethod
    def _wg_pick_url(ps):
        """从 playSetting（JSON 串 / dict / 清晰度数组）里挑最高清晰度直链。"""
        if isinstance(ps, str):
            ps = _ag_json(ps) if ps.strip().startswith(("{", "[")) else {}
        if isinstance(ps, dict):
            return (ps.get("super") or ps.get("high") or ps.get("normal")
                    or ps.get("url") or ps.get("playUrl") or "")
        if isinstance(ps, list) and ps:
            best = next((it for it in ps if isinstance(it, dict)
                         and str(it.get("clarity") or "") in ("1080P", "1080p", "super", "超清")),
                        ps[0])
            if isinstance(best, dict):
                return best.get("url") or best.get("playUrl") or ""
        return ""

    @classmethod
    def _wg_stale(cls, url):
        """地址是否缺失或签名随时可能过期（无 timestamp 的公开直链不刷新）。"""
        if not url or not url.startswith("http"):
            return True
        try:
            m = re.search(r"[?&]timestamp=(\d+)", url)
            if not m:
                return False
            return (int(time.time()) - int(m.group(1))) > cls._WG_SIGN_TTL
        except Exception:
            return False

    def _wg_refresh(self, one_id, ep_id):
        """重新请求详情，换取同一集的最新签名地址。"""
        plat = AGG_PLATFORM["围观"]
        r = _ag_json(_ag_request(
            "%s%s&oneId=%s&page=1&pageSize=1000" % (plat["host"], plat["url2"], one_id),
            headers=AGG_HEADERS["default"], timeout=12))
        eps = r.get("data") if isinstance(r, dict) else None
        if not isinstance(eps, list) or not eps:
            return ""
        if ep_id:
            for ep in eps:
                if str(ep.get("episodeOneId") or "") == str(ep_id):
                    u = self._wg_pick_url(ep.get("playSetting") or ep.get("videoClarityList"))
                    if u:
                        return u
        u = self._wg_pick_url(eps[0].get("playSetting") or eps[0].get("videoClarityList"))
        return u or ""

    def _wg_play(self, inp):
        raw = str(inp or "").strip()
        url, one_id, ep_id = raw, "", ""
        if "@@" in raw:
            seg = raw.split("@@")
            url = (seg[0] or "").strip()
            one_id = (seg[1] or "").strip() if len(seg) > 1 else ""
            ep_id = (seg[2] or "").strip() if len(seg) > 2 else ""
        # 旧格式：整段 playSetting JSON
        if url.startswith("{"):
            u = self._wg_pick_url(url)
            return {"parse": 0, "url": u or "toast://围观短剧：该集暂无播放地址"}
        if not url.startswith("http"):
            # 兜底：万一壳对 id 做了包装，仍尝试从串里抠出直链
            m = re.search(r"https?://[^\s@]+", raw)
            url = m.group(0) if m else ""
        # 地址缺失或签名过期 → 实时重签
        if (not url or self._wg_stale(url)) and one_id:
            fresh = self._wg_refresh(one_id, ep_id)
            if fresh:
                url = fresh
        if not url:
            return {"parse": 0, "url": "toast://围观短剧：播放地址获取失败，请稍后重试"}
        return {"parse": 0, "url": url,
                "header": {"User-Agent": AGG_HEADERS["default"]["User-Agent"]}}


# =====================================================================
#  新增平台辅助（爽爽 / 喜福 / 五五）
# =====================================================================
_AG_MOBILE_UA = ("Mozilla/5.0 (Linux; Android 10; SM-G970F) AppleWebKit/537.36 "
                 "(KHTML, like Gecko) Chrome/91.0.4472.114 Mobile Safari/537.36")
_AG_OLD_UA = ("Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/50.0.2661.87 Safari/537.36")


def _ag_parse_wuwu_list(html, host):
    """五五(duanju55)列表页解析：三套卡片 class 各抓 名称 / 封面 / 集数。"""
    items = {}
    if not html:
        return []
    patterns = [
        {"name": "SecondList_bookName", "img": "SecondList_bookImage",
         "rem": "SecondList_totalChapterNum"},
        {"name": "TagBookList_bookName", "img": "TagBookList_bookImageBox",
         "rem": "TagBookList_totalChapterNum"},
        {"name": "BrowseList_bookName", "img": "BrowseList_imageBox",
         "rem": "BrowseList_totalChapterNum"},
    ]
    for pat in patterns:
        for mo in re.finditer(
                r'<a[^>]*class="[^"]*\b' + pat["name"] + r'\b[^"]*"[^>]*'
                r'href="[^"]*vod/detail/id/(\d+)\.html"[^>]*>([\s\S]*?)</a>', html, re.I):
            vid, raw = mo.group(1), mo.group(2)
            if vid not in items:
                items[vid] = {"id": vid, "name": "", "pic": "", "rem": ""}
            sm = re.search(r'<span[^>]*>([^<]+)</span>', raw, re.I)
            items[vid]["name"] = sm.group(1).strip() if sm else re.sub(r'<[^>]+>', "", raw).strip()
        for mo in re.finditer(
                r'<a[^>]*class="[^"]*\b' + pat["img"] + r'\b[^"]*"[^>]*'
                r'href="[^"]*vod/detail/id/(\d+)\.html"[^>]*>([\s\S]*?)</a>', html, re.I):
            if mo.group(1) in items:
                im = re.search(r'<img[^>]*\bsrc="([^"]+)"', mo.group(2), re.I)
                if im:
                    items[mo.group(1)]["pic"] = im.group(1) if im.group(1).startswith("http") \
                        else host + im.group(1)
        for mo in re.finditer(
                r'<a[^>]*class="[^"]*\b' + pat["rem"] + r'\b[^"]*"[^>]*'
                r'href="[^"]*vod/detail/id/(\d+)\.html"[^>]*>([\s\S]*?)</a>', html, re.I):
            if mo.group(1) in items:
                items[mo.group(1)]["rem"] = re.sub(r'<[^>]+>', "", mo.group(2)).strip()
    return list(items.values())


# 51 请求头
_AG_HEADER_51 = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Connection": "keep-alive", "X-Requested-With": "XMLHttpRequest",
}


# =====================================================================
#  ENGINE YG · 野果短剧 (原 野果.py 单文件 Spider 融合)
#    site: https://yeguodj.com     api: https://www.yeguodj.com/api.php
#    type_id / vod_id 前缀: YG::        播放线路名: 野果短剧
#    接口响应的 data 字段是 AES-128-CBC(base64) 密文，解密后再 json.loads
#    封面(pic.ndhixj.cn)同为 AES 密文，走本机代理拉取并解密
#    本机代理: 封面图一律带 &eng=yeguo，与红果 / 黄果互不干扰
#    AES 走本文件统一后端(cryptography → pycryptodome → 内置纯 Python)，
#    不再各带一套孤立的表；解密失败只会在「不是图」时退化成原图原样返回
# =====================================================================
_YG_TAG = "YG"
_YG_PROXY_MARK = "&eng=yeguo"
_YG_API_KEY = b"2acf7e91e9864673"
_YG_API_IV = b"1c29882d3ddfcfd6"
_YG_MEDIA_KEY = b"f5d965df75336270"
_YG_MEDIA_IV = b"97b60394abc2fbe1"
_YG_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
_YG_API_BASE = "https://www.yeguodj.com/api.php"
_YG_SITE_REFERER = "https://yeguodj.com/"
_YG_SITE_ORIGIN = "https://yeguodj.com"
_YG_LINE_NAME = "野果短剧"
# 分类: type_id -> 名称（bg_ 走 background 参数，set_ 走 setting 参数）
_YG_CATEGORIES = [
    ("rank", "排行榜"),
    ("explore", "发现"),
    ("bg_40", "都市"),
    ("bg_39", "现代"),
    ("bg_47", "校园"),
    ("bg_41", "古代"),
    ("bg_42", "乡村"),
    ("bg_44", "职场"),
    ("set_26", "重生"),
    ("set_27", "穿越"),
    ("set_28", "系统"),
    ("set_53", "逆袭"),
    ("set_56", "魔改"),
]


class _YeguoSpider(_BaseSpider):
    """野果短剧 (yeguodj.com)：AES 密文接口 + 卡片流 + 本机代理解封面。"""

    def __init__(self):
        self.name = _YG_LINE_NAME
        self.host = _YG_SITE_REFERER
        self.header = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "User-Agent": _YG_UA,
            "Referer": _YG_SITE_REFERER,
            "Origin": _YG_SITE_ORIGIN,
        }
        self._known_tids = [t for t, _ in _YG_CATEGORIES]
        self._api_failed = False
        self.apiBase = _YG_API_BASE
        self.session = None
        self._new_session()

    def _new_session(self):
        try:
            self.session = requests.Session()
        except Exception:
            self.session = requests

    # ---------------------------------------------------------- 生命周期
    def init(self, extend=""):
        if self.session is None:
            self._new_session()
        # 兼容原版：壳里可以传 {"apiBase": "https://..."} 换接口域名（站点换域名时救急）
        try:
            if extend:
                conf = json.loads(extend) if isinstance(extend, str) else extend
                if isinstance(conf, dict) and conf.get("apiBase"):
                    self.apiBase = str(conf["apiBase"]).rstrip("/")
        except Exception:
            pass

    def getName(self):
        return _YG_LINE_NAME

    def getDependence(self):
        return []

    def isVideoFormat(self, url):
        u = str(url or "").lower()
        return any(x in u for x in [".m3u8", ".mp4", ".flv", ".ts", ".mkv", ".avi"])

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return

    def getProxyUrl(self):
        """壳没注入时的保底本机代理地址。"""
        return "http://127.0.0.1:9978/proxy?do=py"

    def _proxy_url(self):
        try:
            fn = getattr(self, "getProxyUrl", None)
            if callable(fn):
                b = str(fn() or "").strip()
                if b:
                    return b
        except Exception:
            pass
        return "http://127.0.0.1:9978/proxy?do=py"

    # ---------------------------------------------------------- 首页/分类
    def filter_meta(self):
        """给统一入口用的筛选：第一项「首页推荐」= 壳不传分类时的默认，防白板。"""
        cate = [{"n": "首页推荐", "v": "home"}]
        cate += [{"n": n, "v": t} for t, n in _YG_CATEGORIES]
        return [{"key": "cate", "name": "分类", "value": cate}]

    def homeContent(self, filter):
        classes = [{"type_id": tid, "type_name": name} for tid, name in _YG_CATEGORIES]
        result = {"class": classes}
        try:
            result["list"] = self.homeVideoContent().get("list", [])
        except Exception:
            pass
        return result

    def homeVideoContent(self):
        try:
            d = self._api("/api/home/homePage", {})
            inner = self._unwrap(d)
            raw = []
            if isinstance(inner, dict):
                raw = list(inner.get("top_list") or [])
                mods = inner.get("modules")
                mlist = mods.get("list") if isinstance(mods, dict) else None
                if isinstance(mlist, list):
                    for m in mlist:
                        if isinstance(m, dict):
                            if isinstance(m.get("list"), list):
                                raw += m["list"]
                            elif m.get("video_id") is not None:
                                raw.append(m)
            videos = self._to_videos(raw)
            seen, uniq = set(), []
            for v in videos:
                if v["vod_id"] in seen:
                    continue
                seen.add(v["vod_id"])
                uniq.append(v)
            return {"list": uniq}
        except Exception:
            return {"list": []}

    def _home_as_page(self, page):
        """首页推荐当一页数据用（分类缺省 / 接口整个挂掉时的兜底，避免白板）。"""
        videos = []
        try:
            videos = self.homeVideoContent().get("list") or []
        except Exception:
            videos = []
        return {"list": videos, "page": page, "pagecount": page,
                "limit": len(videos) or 24, "total": 999999, "parse": 0, "jx": 0}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg)
        except Exception:
            page = 1
        if page < 1:
            page = 1
        tid = str(tid or "")
        # 壳没传分类 / 传了旧名或 0（例如只点了顶级标签）→ 回首页推荐，别甩白板
        if tid in ("", "root", "home", "all", "0") or tid not in self._known_tids:
            return self._home_as_page(page)
        body = {"page": page, "limit": 24}
        path = "/api/theater/exploreList"
        if tid == "rank":
            path = "/api/theater/videoRank"
        elif tid.startswith("bg_"):
            body["background"] = self._num(tid[3:])
        elif tid.startswith("set_"):
            body["setting"] = self._num(tid[4:])
        d = self._api(path, body)
        videos = self._to_videos(self._extract_list(d.get("data")))
        # 接口整个拿不到（被挡 / 改版 / 断网）→ 首次页给首页推荐兜底；
        # 分类本身真没数据（接口正常返回空列表）就照实返回空，不拿别的冒充
        if not videos and page == 1 and self._api_failed:
            return self._home_as_page(page)
        pagecount = page + 1 if len(videos) >= 24 else page
        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 24,
            "total": 999999,
            "parse": 0,
            "jx": 0,
        }

    # ---------------------------------------------------------- 详情/搜索
    def detailContent(self, ids):
        vid = str(ids[0] if ids else "").strip()
        if _ENGINE_SEP in vid:
            vid = vid.split(_ENGINE_SEP, 1)[1]
        if vid.startswith("yeguo:") or vid.startswith("yeguodj:"):
            vid = vid.split(":", 1)[1]
        d = self._api("/api/playlet/detail", {"video_id": self._num(vid)})
        info = self._unwrap(d)
        if isinstance(info, dict) and info.get("video_id") is None and isinstance(info.get("data"), dict):
            info = info["data"]
        if not isinstance(info, dict):
            info = {}
        title = self._san(info.get("title") or vid)
        cover = self._cover(info.get("cover") or info.get("cover_img") or "")
        desc = str(info.get("description") or info.get("intro") or "").strip()
        eps = info.get("episodes")
        eps = eps if isinstance(eps, list) else []
        parts = []
        if eps:
            for i, ep in enumerate(eps):
                if isinstance(ep, dict):
                    n = ep.get("sort") or ep.get("episode") or (i + 1)
                    name = self._san(ep.get("title") or ("第%s集" % n))
                else:
                    n = i + 1
                    name = "第%d集" % n
                parts.append("%s$%s_%s" % (name, vid, n))
        else:
            parts.append("第1集$%s_1" % vid)
        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": cover,
            "vod_content": desc,
            "vod_play_from": _YG_LINE_NAME,
            "vod_play_url": "#".join(parts),
        }
        return {"list": [vod], "parse": 0, "jx": 0}

    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg)
        except Exception:
            page = 1
        if not key:
            return {"list": []}
        d = self._api("/api/search/result", {"keyword": key, "page": page})
        videos = self._to_videos(self._extract_list(d.get("data")))
        return {"list": videos, "page": page, "pagecount": page if len(videos) < 24 else page + 1,
                "limit": 24, "total": 999999, "parse": 0, "jx": 0}

    # ---------------------------------------------------------- 播放
    def playerContent(self, flag, id, vipFlags=None):
        pid = str(id or "")
        if _ENGINE_SEP in pid:
            pid = pid.split(_ENGINE_SEP, 1)[1]
        vid, ep = pid, "1"
        if "_" in pid:
            vid, ep = pid.rsplit("_", 1)
        url = ""
        try:
            # 播放地址是带签名的直链，每次点播都要现签一次，不吃缓存的过期地址
            d = self._api("/api/playlet/play", {"video_id": self._num(vid), "ep": self._num(ep)})
            info = self._unwrap(d)
            if isinstance(info, dict) and info.get("video_url") is None and isinstance(info.get("data"), dict):
                info = info["data"]
            if isinstance(info, dict):
                url = str(info.get("video_url") or "").strip()
                if not url and isinstance(info.get("episodeAll"), list):
                    for e in info["episodeAll"]:
                        if not isinstance(e, dict):
                            continue
                        if str(e.get("sort") or e.get("index")) == str(ep) or str(e.get("id")) == str(ep):
                            url = str(e.get("video_url") or "").strip()
                            break
        except Exception:
            url = ""
        return {
            "parse": 0,
            "playUrl": "",
            "url": url,
            "header": {
                "User-Agent": _YG_UA,
                "Referer": _YG_SITE_REFERER,
                "Origin": _YG_SITE_ORIGIN,
            },
        }

    # ---------------------------------------------------------- 本机代理(封面解密)
    def localProxy(self, param):
        param = param or {}
        url = _hguo_pv(param, "url") or _hguo_pv(param, "pic")
        if not url:
            return [404, "text/plain", b""]
        url = unquote(url)
        if not url:
            return [404, "text/plain", b""]
        try:
            r = self.session.get(url, headers={
                "Accept": "image/*,*/*;q=0.8",
                "User-Agent": _YG_UA,
                "Referer": _YG_SITE_REFERER,
                "Origin": _YG_SITE_ORIGIN,
            }, timeout=20, verify=False)
            raw = r.content or b""
        except Exception:
            return [404, "text/plain", b""]
        data = raw
        if not self._is_image(raw):
            try:
                dec = self._aes_raw(raw, _YG_MEDIA_KEY, _YG_MEDIA_IV)
                if self._is_image(dec):
                    data = dec
            except Exception:
                pass
        mime = "image/jpeg"
        if len(data) >= 4:
            if data[:3] == b"\x89PN":
                mime = "image/png"
            elif data[:3] == b"GIF":
                mime = "image/gif"
            elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
                mime = "image/webp"
        return [200, mime, bytes(data)]

    # ================================================================ 内部工具
    def _headers(self):
        h = dict(self.header)
        h["Referer"] = _YG_SITE_REFERER
        h["Origin"] = _YG_SITE_ORIGIN
        h["User-Agent"] = _YG_UA
        return h

    def _api(self, path, body):
        url = getattr(self, "apiBase", _YG_API_BASE) + path
        body = body or {}
        d = None
        self._api_failed = False
        try:
            r = self.session.post(url, data=json.dumps(body), headers=self._headers(),
                                  timeout=20, verify=False)
            d = r.json()
        except Exception:
            try:
                r = self.session.get(url, params=body, headers=self._headers(),
                                     timeout=20, verify=False)
                d = r.json()
            except Exception:
                self._api_failed = True
                return {}
        if not isinstance(d, dict):
            self._api_failed = True
            return {}
        if isinstance(d.get("data"), str) and len(d["data"]) > 20:
            try:
                plain = self._aes_text(d["data"], _YG_API_KEY, _YG_API_IV)
                d["data"] = json.loads(plain)
            except Exception:
                # 解密/解析失败 = 这批数据拿不到，标记失败好让上层兜底，
                # 但不要把 {} 当成「该分类真没内容」
                self._api_failed = True
        return d

    def _unwrap(self, d):
        if not isinstance(d, dict):
            return {}
        x = d.get("data") if d.get("data") is not None else d
        if isinstance(x, dict) and isinstance(x.get("data"), (dict, list)):
            return x["data"]
        return x if isinstance(x, dict) else {}

    def _extract_list(self, data):
        inner = data
        if isinstance(data, dict) and isinstance(data.get("data"), (dict, list)):
            inner = data["data"]
        if isinstance(inner, dict):
            arr = inner.get("list") or inner.get("top_list") or []
        elif isinstance(inner, list):
            arr = inner
        else:
            arr = []
        return arr if isinstance(arr, list) else []

    def _to_videos(self, arr):
        out = []
        for it in arr or []:
            if not isinstance(it, dict):
                continue
            vid = it.get("video_id")
            if vid is None:
                vid = it.get("id")
            if vid is None or str(vid).strip() == "":
                continue
            vid = str(vid).strip()
            title = it.get("title") or it.get("video_title") or it.get("name") or vid
            cover = self._cover(it.get("cover") or it.get("cover_img") or it.get("pic") or "")
            ep = it.get("episode_count") or it.get("total_serial")
            remark = str(it.get("update_status") or it.get("serialize_status_text") or "").strip()
            if not remark and ep not in (None, ""):
                remark = "更新至%s集" % ep
            out.append({
                "vod_id": vid,
                "vod_name": self._san(title),
                "vod_pic": cover,
                "vod_remarks": remark,
            })
        return out

    def _cover(self, url):
        url = str(url or "").strip()
        if not url:
            return ""
        if url.startswith("data:"):
            return url
        # 已经代理过的地址：先剥回原图地址再重新包一次，避免套娃
        if "url=" in url:
            try:
                m = re.search(r"[?&]url=([^&]+)", url)
                if m:
                    url = unquote(m.group(1))
            except Exception:
                pass
        if url.startswith("//"):
            url = "https:" + url
        elif url.startswith("/"):
            url = self.host.rstrip("/") + url
        try:
            b = self._proxy_url()
            if "?" not in b:
                b += "?do=py"
            return b + _YG_PROXY_MARK + "&url=" + quote(url, safe="")
        except Exception:
            return "http://127.0.0.1:9978/proxy?do=py" + _YG_PROXY_MARK + "&url=" + quote(url, safe="")

    def _san(self, s):
        return str(s if s is not None else "").replace("#", " ").replace("$", " ").strip()

    def _num(self, v):
        try:
            return int(str(v).strip())
        except Exception:
            return v

    def _is_image(self, b):
        if b is None or len(b) < 3:
            return False
        b0, b1, b2 = b[0], b[1], b[2]
        if b0 == 0xff and b1 == 0xd8:
            return True
        if b0 == 0x89 and b1 == 0x50 and b2 == 0x4e:
            return True
        if b0 == 0x47 and b1 == 0x49 and b2 == 0x46:
            return True
        if len(b) >= 12 and b[:4] == b"RIFF" and b[8:12] == b"WEBP":
            return True
        return False

    # ---------------------------------------------------------- AES-128-CBC
    def _aes_raw(self, cipher, key, iv):
        """AES-128-CBC 解密 + PKCS7 去填充；走本文件统一后端(三级回退)。"""
        if isinstance(cipher, (bytes, bytearray)):
            data = bytes(cipher)
        else:
            data = bytes(bytearray(cipher))
        n = len(data) - (len(data) % 16)
        if n <= 0:
            return b""
        k = bytes(key)[:16].ljust(16, b"\x00")
        v = bytes(iv)[:16].ljust(16, b"\x00")
        out = _aes_cbc_decrypt(k, v, data[:n])
        if out:
            pad = out[-1]
            if 1 <= pad <= 16 and pad <= len(out):
                out = out[:-pad]
        return out

    def _aes_text(self, b64, key, iv):
        s = str(b64 or "").strip().replace("\n", "").replace("\r", "").replace(" ", "")
        s = s.replace("-", "+").replace("_", "/")
        s += "=" * ((4 - len(s) % 4) % 4)
        try:
            raw = base64.b64decode(s)
        except Exception:
            return ""
        return self._aes_raw(raw, key, iv).decode("utf-8", "ignore")

# =====================================================================
#  ENGINE JG · 禁果短剧 (原 禁果.py 单文件 Spider 融合)
#    site: https://jinguoduanju.app        api: /api/v1/*
#    type_id / vod_id 前缀: JG::          播放线路名: 禁果短剧
#    鉴权: 先 POST /api/v1/auth/device 用随机 deviceId 换 Bearer token，
#          之后 /api/v1/* 请求一律带 Authorization；令牌失效(401)自动重登一次
#    分类: 官方剧场导航 navigationId + 本地 tags 精确过滤（服务端 tags 参数会 400）
#    列表: /dramas 一次返回全量，本地按 _JG_PAGE_SIZE 分页
#    封面: 站点直链，不套本机代理（与红果/黄果/野果不同，禁果封面无需中转）
# =====================================================================
_JG_TAG = "JG"
_JG_LINE_NAME = "禁果短剧"
_JG_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
_JG_API_BASE = "https://jinguoduanju.app"
_JG_PAGE_SIZE = 24

# type_id -> (中文名, query dict, tag过滤词)
#   query 里 sort / navigationId / length 直接透传服务端；tag 走本地过滤
_JG_CATEGORIES = [
    ("heat",         "热度",     {"sort": "heat"},                       None),
    ("latest",       "最新",     {"sort": "latest"},                     None),
    ("nav_all",      "全部",     {"sort": "latest", "navigationId": 2},  None),
    ("nav_original", "原创精品", {"sort": "latest", "navigationId": 7},  None),
    ("nav_single",   "单体作品", {"sort": "latest", "navigationId": 3},  None),
    ("nav_anime",    "动漫改编", {"sort": "latest", "navigationId": 6},  None),
    ("nav_movie",    "影视改编", {"sort": "latest", "navigationId": 5},  None),
    ("len_multi",    "多集",     {"sort": "latest", "length": "multi"},  None),
    ("len_single",   "单集",     {"sort": "latest", "length": "single"}, None),
    ("tag_mogai",    "魔改",     {"sort": "latest"},                     "魔改"),
    ("tag_dushi",    "都市",     {"sort": "latest"},                     "都市"),
    ("tag_zhichang", "职场",     {"sort": "latest"},                     "职场"),
    ("tag_qihuan",   "奇幻",     {"sort": "latest"},                     "奇幻"),
    ("tag_guzhuang", "古装",     {"sort": "latest"},                     "古装"),
    ("tag_dongman",  "动漫",     {"sort": "latest"},                     "动漫"),
]
_JG_CAT_MAP = {tid: (q, tag) for tid, _n, q, tag in _JG_CATEGORIES}


class _JinguoSpider(_BaseSpider):
    """禁果短剧 (jinguoduanju.app)：设备令牌鉴权 + 全量列表本地分页。"""

    def __init__(self):
        self.name = _JG_LINE_NAME
        self.apiBase = _JG_API_BASE
        self._token = ""
        self._deviceId = ""
        self.session = None
        self._new_session()

    def _new_session(self):
        try:
            self.session = requests.Session()
        except Exception:
            self.session = requests

    # ---------------------------------------------------------- 生命周期
    def init(self, extend=""):
        if self.session is None:
            self._new_session()
        # 站点换域名时可在壳里传 {"apiBase": "https://..."} 救急
        try:
            if extend:
                conf = json.loads(extend) if isinstance(extend, str) else extend
                if isinstance(conf, dict) and conf.get("apiBase"):
                    self.apiBase = str(conf["apiBase"]).rstrip("/")
        except Exception:
            pass

    def getName(self):
        return _JG_LINE_NAME

    def getDependence(self):
        return []

    def isVideoFormat(self, url):
        u = str(url or "").lower()
        return any(x in u for x in [".m3u8", ".mp4", ".flv", ".ts", ".mkv", ".avi"])

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return

    # ---------------------------------------------------------- 首页/分类
    def filter_meta(self):
        """给统一入口用的筛选：第一项「首页推荐」= 壳不传分类时的默认，防白板。"""
        cate = [{"n": "首页推荐", "v": "home"}]
        cate += [{"n": name, "v": tid} for tid, name, _q, _t in _JG_CATEGORIES]
        return [{"key": "cate", "name": "分类", "value": cate}]

    def homeContent(self, filter):
        classes = [{"type_id": tid, "type_name": name} for tid, name, _q, _t in _JG_CATEGORIES]
        result = {"class": classes}
        try:
            result["list"] = self.homeVideoContent().get("list", [])
        except Exception:
            pass
        return result

    def homeVideoContent(self):
        try:
            data = self._api_get("/landing")
            arr = data.get("dramas") if isinstance(data, dict) else None
            if not isinstance(arr, list):
                arr = []
            return {"list": self._to_videos(self._page_slice(arr, 1))}
        except Exception:
            return {"list": []}

    def _home_as_page(self, page):
        """首页推荐当一页数据用（只第一页有效，翻页返回空避免重复堆同一批）。"""
        if page > 1:
            return {"list": [], "page": page, "pagecount": page,
                    "limit": 0, "total": 0, "parse": 0, "jx": 0}
        videos = []
        try:
            videos = self.homeVideoContent().get("list") or []
        except Exception:
            videos = []
        return {"list": videos, "page": page, "pagecount": page,
                "limit": len(videos) or _JG_PAGE_SIZE, "total": len(videos),
                "parse": 0, "jx": 0}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg)
        except Exception:
            page = 1
        if page < 1:
            page = 1
        tid = str(tid or "")
        # 只点了顶级标签 / 传了空或旧名 → 回首页推荐，别甩白板
        if tid in ("", "root", "home", "0"):
            return self._home_as_page(page)
        q, tag = _JG_CAT_MAP.get(tid, ({"sort": "latest"}, None))
        arr = self._fetch_dramas(dict(q), tag)
        videos = self._to_videos(self._page_slice(arr, page))
        total = len(arr)
        pagecount = (total + _JG_PAGE_SIZE - 1) // _JG_PAGE_SIZE if total else page
        if pagecount < 1:
            pagecount = 1
        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": _JG_PAGE_SIZE,
            "total": total,
            "parse": 0,
            "jx": 0,
        }

    # ---------------------------------------------------------- 详情/搜索
    def detailContent(self, ids):
        vid = str(ids[0] if ids else "").strip()
        if _ENGINE_SEP in vid:
            vid = vid.split(_ENGINE_SEP, 1)[1]
        vid = self._strip_prefix(vid).split(":")[0]
        data = self._unwrap(self._api_get("/dramas/" + self._enc(vid)))
        drama = data.get("drama") if isinstance(data.get("drama"), dict) else {}
        eps = data.get("episodes") if isinstance(data.get("episodes"), list) else []
        cover = self._abs(drama.get("coverUrl") or "")
        title = self._san(drama.get("title") or vid)
        tags = drama.get("tags")
        tagstr = " · ".join(str(x) for x in tags) if isinstance(tags, list) else ""
        desc = str(data.get("description") or tagstr or "").strip()

        parts = []
        for i, ep in enumerate(eps):
            if not isinstance(ep, dict):
                continue
            n = ep.get("number") or (i + 1)
            eid = str(ep.get("id") or "")
            name = self._san(ep.get("title") or ("第%s集" % n))
            # 播放标识: dramaId:epNum:episodeId
            parts.append("%s$%s:%s:%s" % (name, vid, n, eid))
        if not parts:
            parts.append("第1集$%s:1:" % vid)

        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": cover,
            "vod_content": desc,
            "vod_play_from": _JG_LINE_NAME,
            "vod_play_url": "#".join(parts),
        }
        return {"list": [vod], "parse": 0, "jx": 0}

    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg)
        except Exception:
            page = 1
        if page < 1:
            page = 1
        if not key:
            return {"list": [], "page": page}
        try:
            arr = self._as_list(self._api_get("/dramas", {"sort": "latest", "q": key}))
        except Exception:
            arr = []
        lst = self._to_videos(self._page_slice(arr, page))
        total = len(arr)
        pagecount = (total + _JG_PAGE_SIZE - 1) // _JG_PAGE_SIZE if total else page
        return {"list": lst, "page": page, "pagecount": max(1, pagecount),
                "limit": _JG_PAGE_SIZE, "total": total, "parse": 0, "jx": 0}

    # ---------------------------------------------------------- 播放
    def playerContent(self, flag, id, vipFlags=None):
        s = str(id or "")
        if _ENGINE_SEP in s:
            s = s.split(_ENGINE_SEP, 1)[1]
        s = self._strip_prefix(s)
        parts = s.split(":")
        drama_id = parts[0] if parts else ""
        ep_num = (parts[1] if len(parts) > 1 and parts[1] else "1") or "1"
        episode_id = parts[2] if len(parts) > 2 else ""
        url = ""
        try:
            if drama_id and not episode_id:
                episode_id = self._resolve_episode_id(drama_id, ep_num)
            if episode_id:
                play = self._api_get("/episodes/" + self._enc(episode_id) + "/play")
                if isinstance(play, dict):
                    url = str(play.get("videoUrl") or "").strip()
        except Exception:
            url = ""
        return {
            "parse": 0,
            "playUrl": "",
            "url": url,
            "header": {
                "User-Agent": _JG_UA,
                "Referer": self.apiBase + "/",
                "Origin": self.apiBase,
            },
        }

    def localProxy(self, param):
        return None

    # ================================================================ 内部

    def _fetch_dramas(self, query, tag_filter):
        arr = self._as_list(self._api_get("/dramas", query))
        if tag_filter:
            filtered = []
            for it in arr:
                tags = it.get("tags") if isinstance(it, dict) else None
                if isinstance(tags, list) and any(str(x) == tag_filter for x in tags):
                    filtered.append(it)
            arr = filtered
        return arr

    def _resolve_episode_id(self, drama_id, ep_num):
        data = self._unwrap(self._api_get("/dramas/" + self._enc(drama_id)))
        eps = data.get("episodes") if isinstance(data.get("episodes"), list) else []
        for e in eps:
            if not isinstance(e, dict):
                continue
            if str(e.get("number")) == str(ep_num) or str(e.get("id")) == str(ep_num):
                return str(e.get("id") or "")
        return str(eps[0].get("id")) if eps and isinstance(eps[0], dict) else ""

    # ---------------------------------------------------------- HTTP
    def _rand_device(self):
        return "".join(random.choice("0123456789abcdef") for _ in range(32))

    def _ensure_token(self):
        if self._token:
            return self._token
        if not self._deviceId:
            self._deviceId = self._rand_device()
        url = self.apiBase + "/api/v1/auth/device"
        body = {"deviceId": "h5:" + self._deviceId, "channelCode": "", "attributionToken": ""}
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": _JG_UA,
            "Referer": self.apiBase + "/",
            "Origin": self.apiBase,
        }
        d = None
        try:
            r = self.session.post(url, data=json.dumps(body), headers=headers,
                                  timeout=20, verify=False)
            d = r.json()
        except Exception:
            d = None
        self._token = str((d or {}).get("token") or "").strip() if isinstance(d, dict) else ""
        if not self._token:
            raise RuntimeError("禁果设备登录失败")
        return self._token

    def _api_get(self, path, query=None, retry=False):
        self._ensure_token()
        url = self.apiBase + "/api/v1" + path + self._qs(query or {})
        headers = {
            "Accept": "application/json",
            "User-Agent": _JG_UA,
            "Referer": self.apiBase + "/",
            "Origin": self.apiBase,
            "Authorization": "Bearer " + self._token,
        }
        try:
            r = self.session.get(url, headers=headers, timeout=20, verify=False)
            d = r.json()
        except Exception:
            return None
        # 令牌过期：丢掉重登一次再打，避免整段分类直接空白
        if isinstance(d, dict) and d.get("status") == 401 and not retry:
            self._token = ""
            return self._api_get(path, query, True)
        return d

    def _qs(self, obj):
        parts = []
        for k, v in (obj or {}).items():
            if v is None or v == "":
                continue
            if isinstance(v, (list, tuple)):
                for x in v:
                    parts.append("%s=%s" % (quote(str(k)), quote(str(x))))
            else:
                parts.append("%s=%s" % (quote(str(k)), quote(str(v))))
        return "?" + "&".join(parts) if parts else ""

    # ---------------------------------------------------------- 映射
    @staticmethod
    def _as_list(d):
        """列表接口兼容取数：直接就是 list，或包在 data/list/dramas/items 里。"""
        if isinstance(d, list):
            return d
        if isinstance(d, dict):
            for k in ("data", "list", "dramas", "items", "results"):
                v = d.get(k)
                if isinstance(v, list):
                    return v
                if isinstance(v, dict):
                    for k2 in ("list", "dramas", "items"):
                        if isinstance(v.get(k2), list):
                            return v[k2]
        return []

    @staticmethod
    def _unwrap(d):
        """详情接口兼容取数：{drama, episodes, description} 直接给，或再包一层 data。"""
        if not isinstance(d, dict):
            return {}
        inner = d.get("data")
        if isinstance(inner, dict) and ("drama" in inner or "episodes" in inner):
            return inner
        return d

    def _to_videos(self, arr):
        out = []
        for it in arr or []:
            if not isinstance(it, dict):
                continue
            vid = str(it.get("id") or "").strip()
            if not vid:
                continue
            cover = self._abs(it.get("coverUrl") or it.get("cover") or "")
            ep = it.get("episodeCount")
            remark = ("全%s集" % ep) if ep not in (None, "", 0) else ""
            tags = it.get("tags")
            tagstr = " · ".join(str(x) for x in tags) if isinstance(tags, list) else ""
            if tagstr:
                remark = (remark + " · " + tagstr) if remark else tagstr
            out.append({
                "vod_id": vid,
                "vod_name": self._san(it.get("title") or vid),
                "vod_pic": cover,
                "vod_remarks": remark,
            })
        return out

    def _page_slice(self, arr, page):
        if not isinstance(arr, list):
            return []
        try:
            page = int(page)
        except Exception:
            page = 1
        if page < 1:
            page = 1
        start = (page - 1) * _JG_PAGE_SIZE
        return arr[start:start + _JG_PAGE_SIZE]

    def _abs(self, u):
        u = str(u or "").strip()
        if not u:
            return ""
        if u.lower().startswith("http://") or u.lower().startswith("https://"):
            return u
        if u.startswith("//"):
            return "https:" + u
        return self.apiBase + ("" if u.startswith("/") else "/") + u

    def _strip_prefix(self, s):
        s = str(s or "").strip()
        if s.startswith("jinguo:"):
            s = s[7:]
        if s.startswith("jgdj:"):
            s = s[5:]
        return s

    def _enc(self, s):
        return quote(str(s), safe="")

    def _san(self, s):
        return str(s if s is not None else "").replace("#", " ").replace("$", " ").strip()


# =====================================================================
#  ENGINE HGJ · 红果黄剧 (原 红果黄剧.js ForwardWidget v1.6.1 → Python 移植)
#    site: https://huangju.net        api: https://api.huangju.net
#    type_id / vod_id 前缀: HGJ::      播放线路名: 红果黄剧
#    鉴权: POST /auth/guest(随机 deviceId) 换 Bearer，401 自动清 token 重登一次
#    列表: /dramas?category=&page=&pageSize=&sort=  (搜索走 &q=)
#          分组分类 = 多个 slug 并发拉取后按 id 去重合并(对应 JS fetchMergedCategories)
#    详情: /dramas/{slug-id} → episodes[{id,epNo}]，剧集标识 play:{episodeId}
#    播放: ① playProxy 拿 CloudFront 签名 → 转 Cookie,配裸链下发(主线路)
#          ② 直连 /play/{episodeId} 读 Set-Cookie 里的 CloudFront 三件套
#          站点 m3u8 内部全是相对路径,用 query 签名在子列表/分片会被丢弃 → 403,
#          所以统一改成 Cookie 下发;个别不吃请求头的播放器可把 playMode 设 signed
#    封面: 站点直链，不套本机代理
# =====================================================================
# 红果黄剧引擎(本段在聚合版里原样复用,勿改缩进/类名)
_HGJ_TAG = "HGJ"
_HGJ_LINE_NAME = "红果黄剧"
_HGJ_API_BASE = "https://api.huangju.net"
_HGJ_SITE = "https://huangju.net"
_HGJ_PLAY_PROXY = "https://play.uou.qzz.io"
_HGJ_PLAY_MODE = "cookie"
_HGJ_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
_HGJ_PAGE_SIZE = 20
_HGJ_SKIP_PROBE = "X-Forward-Skip-Redirect-Probe"

# type_id -> (中文名, 多 slug 合并列表, 单接口 query)
#   slugs 非空 = 并发拉多个 category 后按 id 去重合并(对应 JS 的 fetchMergedCategories)
#   slugs 为空 = 直接打 /dramas 带 query(sort / q 等)
_HGJ_CATEGORIES = [
    ("hot",      "热门",     None, {"sort": "hot"}),
    ("latest",   "最新",     None, {"sort": "latest"}),
    ("adult",    "成人",     ["adult"], None),
    ("mo-gai",   "魔改",     ["mo-gai"], None),
    ("urban",    "都市",     ["urban"], None),
    ("suspense", "悬疑",     ["suspense"], None),
    ("g_romance", "爱情甜宠", ["romance", "modern-romance", "ancient-romance", "sweet-love"], None),
    ("g_fantasy", "玄幻脑洞", ["fantasy", "brain-hole", "xi-ju"], None),
    ("g_rebirth", "穿越重生", ["chuan-yue", "rebirth"], None),
    ("g_xianxia", "仙侠古装", ["xian-xia", "costume", "gong-dou", "wu-xia", "qi-huan"], None),
    ("g_youth",   "青春校园", ["qing-chun", "xiao-yuan"], None),
    ("g_family",  "家庭情感", ["family", "tong-ju", "gui-mi", "lao-shi"], None),
    ("g_counter", "逆袭复仇", ["war-god", "revenge", "counterattack", "son-in-law"], None),
    ("g_horror",  "灵异恐怖", ["ling-yi", "kong-bu", "jing-song"], None),
    ("g_original", "原创精选", ["du-jia-yuan-chuang", "yuan-chuang"], None),
]
_HGJ_CAT_MAP = {tid: (slugs, q) for tid, _n, slugs, q in _HGJ_CATEGORIES}


class _HuangjuSpider(_BaseSpider):
    """红果黄剧 (huangju.net)：guest 令牌 + CloudFront 签名播放。"""

    def __init__(self):
        self.name = _HGJ_LINE_NAME
        self.apiBase = _HGJ_API_BASE
        self.site = _HGJ_SITE
        self.playProxy = _HGJ_PLAY_PROXY
        self.playProxyToken = ""
        # cookie = 裸链 + CloudFront Cookie（默认，HLS 子资源才带得上签名）
        # signed = 老的 query 签名直链（个别播放器不吃请求头时可切回来）
        self.playMode = _HGJ_PLAY_MODE
        self._token = ""
        self._deviceId = ""
        self.session = None
        self._new_session()

    def _new_session(self):
        try:
            self.session = requests.Session() if requests is not None else None
        except Exception:
            self.session = None

    # ---------------------------------------------------------- 生命周期
    def init(self, extend=""):
        if self.session is None:
            self._new_session()
        # 站点/代理换域名时在壳里传 JSON 即可救急，不用改代码
        try:
            if extend:
                conf = json.loads(extend) if isinstance(extend, str) else extend
                if isinstance(conf, dict):
                    if conf.get("apiBase"):
                        self.apiBase = str(conf["apiBase"]).rstrip("/")
                    if conf.get("site"):
                        self.site = str(conf["site"]).rstrip("/")
                    if conf.get("playProxy"):
                        self.playProxy = str(conf["playProxy"]).rstrip("/")
                    if "playProxyToken" in conf:
                        self.playProxyToken = str(conf.get("playProxyToken") or "")
                    if conf.get("playMode"):
                        self.playMode = str(conf.get("playMode") or "cookie").strip().lower()
        except Exception:
            pass

    def getName(self):
        return _HGJ_LINE_NAME

    def getDependence(self):
        return []

    def isVideoFormat(self, url):
        u = str(url or "").lower()
        return any(x in u for x in [".m3u8", ".mp4", ".flv", ".ts", ".mkv", ".avi"])

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return None

    def localProxy(self, param):
        # 黄剧封面/视频均为站点直链，无需本机中转
        return None

    # ---------------------------------------------------------- 首页/分类
    def filter_meta(self):
        """给聚合入口用的筛选：15 个分类全下沉为 cate，默认落在热门。"""
        return [{"key": "cate", "name": "分类",
                 "value": [{"n": name, "v": tid} for tid, name, _s, _q in _HGJ_CATEGORIES]}]

    def homeContent(self, filter):
        classes = [{"type_id": tid, "type_name": name}
                   for tid, name, _s, _q in _HGJ_CATEGORIES]
        result = {"class": classes}
        try:
            result["list"] = self.homeVideoContent().get("list", [])
        except Exception:
            pass
        return result

    def homeVideoContent(self):
        try:
            arr = self._fetch_dramas({"page": 1, "pageSize": _HGJ_PAGE_SIZE, "sort": "hot"})
            return {"list": [self._to_video(x) for x in arr]}
        except Exception:
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg)
        except Exception:
            page = 1
        if page < 1:
            page = 1
        tid = str(tid or "").strip()
        if "::" in tid:
            tid = tid.split("::", 1)[1]
        # 只点顶级标签 / 空分类 → 落热门，别甩白板
        if tid in ("", "root", "home", "0"):
            tid = "hot"
        slugs, query = _HGJ_CAT_MAP.get(tid, (None, {"sort": "hot"}))
        try:
            arr = self._fetch_list(page, slugs, query)
        except Exception:
            arr = []
        videos = [self._to_video(x) for x in arr]
        pagecount = page + 1 if len(videos) >= _HGJ_PAGE_SIZE else page
        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": _HGJ_PAGE_SIZE,
            "total": 999999,
            "parse": 0,
            "jx": 0,
        }

    # ---------------------------------------------------------- 详情
    def detailContent(self, ids):
        raw = ids[0] if isinstance(ids, (list, tuple)) else ids
        vid = self._strip_prefix(raw)
        vod = {
            "vod_id": vid,
            "vod_name": vid,
            "vod_pic": "",
            "vod_content": "",
            "vod_play_from": _HGJ_LINE_NAME,
            "vod_play_url": "",
        }
        try:
            pack = self._http_get(self.apiBase + "/dramas/" + quote(vid, safe=""), False)
            d = self._unwrap(pack.get("body"))
        except Exception:
            d = None
        if not isinstance(d, dict) or not d.get("id"):
            vod["vod_play_url"] = "第1集$play:" + vid
            return {"list": [vod], "parse": 0, "jx": 0}

        cover = str(d.get("coverUrl") or d.get("coverHUrl") or "")
        vod["vod_id"] = vid
        vod["vod_name"] = self._san(d.get("title") or vid)
        vod["vod_pic"] = cover
        vod["vod_content"] = self._san(d.get("description") or "")
        if d.get("score") is not None:
            try:
                vod["vod_douban_score"] = str(d.get("score"))
            except Exception:
                pass
        pub = str(d.get("publishedAt") or "")
        if len(pub) >= 4:
            vod["vod_year"] = pub[:4]
        cat = d.get("category")
        if isinstance(cat, dict) and cat.get("name"):
            vod["vod_class"] = self._san(cat.get("name"))

        eps = d.get("episodes")
        parts = []
        if isinstance(eps, list):
            for i, ep in enumerate(eps):
                if not isinstance(ep, dict):
                    continue
                n = ep.get("epNo")
                if n in (None, ""):
                    n = i + 1
                eid = str(ep.get("id") or "").strip()
                if not eid:
                    continue
                name = self._san(ep.get("title") or ("第%s集" % n))
                parts.append("%s$play:%s" % (name, eid))
        if not parts:
            parts.append("第1集$play:%s" % vod["vod_id"])
        vod["vod_play_url"] = "#".join(parts)
        return {"list": [vod], "parse": 0, "jx": 0}

    # ---------------------------------------------------------- 搜索
    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg)
        except Exception:
            page = 1
        if page < 1:
            page = 1
        if not key:
            return {"list": [], "page": page}
        try:
            arr = self._fetch_dramas({"q": key, "page": page, "pageSize": _HGJ_PAGE_SIZE})
        except Exception:
            arr = []
        lst = [self._to_video(x) for x in arr]
        return {"list": lst, "page": page,
                "pagecount": page + 1 if len(lst) >= _HGJ_PAGE_SIZE else page,
                "limit": _HGJ_PAGE_SIZE, "total": 999999, "parse": 0, "jx": 0}

    # ---------------------------------------------------------- 播放
    def playerContent(self, flag, id, vipFlags=None):
        s = str(id or "").strip()
        if "::" in s:
            s = s.split("::", 1)[1]
        s = self._strip_prefix(s)
        episode_id = s
        if episode_id.startswith("play:"):
            episode_id = episode_id[5:]
        if ":" in episode_id:
            episode_id = episode_id.split(":")[-1]
        episode_id = episode_id.strip()

        url = ""
        jar = None
        raw = ""
        if episode_id:
            try:
                grant = self._fetch_play_grant(episode_id)
            except Exception:
                grant = None
            if isinstance(grant, dict):
                signed = str(grant.get("signedUrl") or "")
                raw = str(grant.get("rawUrl") or "")
                jar = grant.get("jar")
                # 关键：站点用的是 CloudFront 签名。
                # 它的 m3u8 内部全是相对路径（480/playlist.m3u8、seg-000.ts），
                # 播放器解析子列表/分片时会把 URL 上的 ?Policy=&Signature= 丢掉，
                # 结果子资源一律 403（播放器报 Bad HTTP Status）。
                # 所以主线路走「裸链 + CloudFront Cookie」：Cookie 由播放器对
                # video.huangju.net 的每个请求自动携带，master/子列表/ts 全通。
                if self.playMode == "signed":
                    url = signed or raw
                else:
                    url = raw or signed
        header = {
            "User-Agent": _HGJ_UA,
            "Referer": self.site + "/",
            "Origin": self.site,
            _HGJ_SKIP_PROBE: "1",
        }
        # 只要抠到签名就下发 Cookie：走裸链时它是唯一凭据；
        # 走签名直链时带上也无害，还能顺带兜住子资源请求。
        if jar:
            try:
                header["Cookie"] = self._cookie_header(jar)
            except Exception:
                pass
        return {"parse": 0, "playUrl": "", "url": url, "header": header}

    # ================================================================ 内部

    def _to_video(self, d):
        if not isinstance(d, dict):
            return {}
        vid = str(d.get("id") or "").strip()
        title = self._san(d.get("title") or vid)
        cover = str(d.get("coverUrl") or d.get("coverHUrl") or d.get("cover") or "")
        remark = ""
        total = d.get("totalEpisodes")
        if str(d.get("status") or "") == "completed":
            remark = "全%s集" % (total if total not in (None, "") else "?")
        elif total not in (None, ""):
            remark = "更新至%s集" % total
        cat = d.get("category")
        if isinstance(cat, dict) and cat.get("name"):
            cname = self._san(cat.get("name"))
            remark = (remark + " · " + cname) if remark else cname
        return {
            # 与原 JS 的 link 保持一致：slug-id（无 slug 时退回纯 id），详情接口按此 key 取
            "vod_id": ("%s-%s" % (str(d.get("slug")).strip(), vid)) if d.get("slug") else vid,
            "vod_name": title,
            "vod_pic": cover,
            "vod_remarks": remark,
        }

    def _fetch_list(self, page, slugs, query):
        """单分类直取 / 多 slug 并发合并(对应 JS fetchMergedCategories)。"""
        if slugs:
            def one(s):
                try:
                    return self._fetch_dramas({"category": s, "page": page,
                                               "pageSize": _HGJ_PAGE_SIZE})
                except Exception:
                    return []
            groups = self._parallel(one, list(slugs))
            seen = set()
            out = []
            for g in groups:
                for it in (g or []):
                    if not isinstance(it, dict):
                        continue
                    k = str(it.get("id") or "")
                    if not k or k in seen:
                        continue
                    seen.add(k)
                    out.append(it)
            return out
        q = dict(query or {})
        q["page"] = page
        q["pageSize"] = _HGJ_PAGE_SIZE
        return self._fetch_dramas(q)

    def _fetch_dramas(self, query):
        url = self.apiBase + "/dramas" + self._qs(query)
        pack = self._http_get(url, False)
        body = pack.get("body")
        return self._as_list(body)

    def _parallel(self, fn, items):
        items = list(items or [])
        if not items:
            return []
        if concurrent is not None and len(items) > 1:
            try:
                with concurrent.futures.ThreadPoolExecutor(
                        max_workers=min(5, len(items))) as ex:
                    return list(ex.map(fn, items))
            except Exception:
                pass
        return [fn(x) for x in items]

    # ---------------------------------------------------------- 播放取签名
    def _fetch_play_grant(self, episode_id):
        """① playProxy ② 直连 api 抠 CloudFront 签名。返回 dict 或 None。"""
        # 1) 代理（推荐线路：JSON 里直接给签名 URL）
        if self.playProxy:
            try:
                q = {"episodeId": episode_id}
                if self.playProxyToken:
                    q["token"] = self.playProxyToken
                d = self._proxy_json(self.playProxy + "/?" + self._qs_body(q))
                if isinstance(d, dict) and d.get("ok") and d.get("url"):
                    su = str(d.get("url") or "")
                    return {"via": "proxy", "rawUrl": str(d.get("rawUrl") or ""),
                            "signedUrl": su, "jar": self._jar_from_url(su),
                            "expiresAt": d.get("expiresAt")}
            except Exception:
                pass
            try:
                url = self.playProxy + "/play/" + quote(episode_id, safe="")
                if self.playProxyToken:
                    url += "?token=" + quote(self.playProxyToken, safe="")
                d2 = self._proxy_json(url)
                if isinstance(d2, dict) and d2.get("url"):
                    su2 = str(d2.get("url") or "")
                    return {"via": "proxy", "rawUrl": str(d2.get("rawUrl") or ""),
                            "signedUrl": su2, "jar": self._jar_from_url(su2),
                            "expiresAt": d2.get("expiresAt")}
            except Exception:
                pass

        # 2) 直连 api（依赖壳是否透传 Set-Cookie）
        raw = ""
        body = None
        res = None
        try:
            pack = self._http_get(self.apiBase + "/play/" + quote(episode_id, safe=""), True)
            body = pack.get("body")
            res = pack.get("res")
            if isinstance(body, dict):
                raw = str(body.get("url") or "")
        except Exception:
            pass
        if not raw:
            try:
                pack = self._http_get(self.apiBase + "/play/" + quote(episode_id, safe=""), False)
                body = pack.get("body")
                res = pack.get("res")
                if isinstance(body, dict):
                    raw = str(body.get("url") or "")
            except Exception:
                pass
        if not raw:
            raise RuntimeError("play 无 url")

        jar = self._extract_cf_jar(res, body)
        signed = self._sign_url(raw, jar) if jar else ""
        return {"via": "direct-jar" if jar else "direct-naked",
                "rawUrl": raw, "signedUrl": signed,
                "jar": jar,
                "expiresAt": body.get("expiresAt") if isinstance(body, dict) else None}

    def _proxy_json(self, url):
        r = self._raw_get(url, {"Accept": "application/json", "User-Agent": _HGJ_UA})
        if r is None:
            return None
        return self._json(r)

    def _extract_cf_jar(self, res, body):
        """从响应头 / Set-Cookie / 返回体里抠 CloudFront 三件套。"""
        texts = []

        def eat(v):
            if v is None:
                return
            if isinstance(v, (list, tuple)):
                for x in v:
                    eat(x)
                return
            texts.append(str(v))

        try:
            h = getattr(res, "headers", None)
            if h is not None:
                try:
                    for k in h.keys():
                        if "cookie" in str(k).lower():
                            eat(h.get(k))
                except Exception:
                    pass
        except Exception:
            pass
        try:
            raw_h = getattr(res, "raw", None)
            hh = getattr(raw_h, "headers", None)
            if hh is not None:
                try:
                    eat(hh.getlist("Set-Cookie"))
                except Exception:
                    pass
        except Exception:
            pass
        try:
            cookies = getattr(res, "cookies", None)
            if cookies is not None:
                try:
                    for c in cookies:
                        jar_txt = "CloudFront-Policy=%s; CloudFront-Signature=%s; CloudFront-Key-Pair-Id=%s" % (
                            c.value if c.name == "CloudFront-Policy" else "",
                            c.value if c.name == "CloudFront-Signature" else "",
                            c.value if c.name == "CloudFront-Key-Pair-Id" else "")
                        if "CloudFront-" in jar_txt:
                            eat(jar_txt)
                except Exception:
                    pass
        except Exception:
            pass
        if isinstance(body, dict):
            try:
                eat(json.dumps(body))
            except Exception:
                pass

        jar = {}
        pat = re.compile(r"CloudFront-(Policy|Signature|Key-Pair-Id)=([A-Za-z0-9_=~\-/\+%]+)")
        for txt in texts:
            for m in pat.finditer(txt):
                val = m.group(2)
                try:
                    from urllib.parse import unquote as _uq
                    val = _uq(val)
                except Exception:
                    pass
                jar["CloudFront-" + m.group(1)] = val
        if (jar.get("CloudFront-Policy") and jar.get("CloudFront-Signature")
                and jar.get("CloudFront-Key-Pair-Id")):
            return jar
        return None

    def _sign_url(self, raw_url, jar):
        if not raw_url or not jar:
            return ""
        join = "&" if "?" in raw_url else "?"
        return (raw_url + join
                + "Policy=" + quote(jar["CloudFront-Policy"], safe="")
                + "&Signature=" + quote(jar["CloudFront-Signature"], safe="")
                + "&Key-Pair-Id=" + quote(jar["CloudFront-Key-Pair-Id"], safe=""))

    def _cookie_header(self, jar):
        if not jar:
            return ""
        return ("CloudFront-Policy=%s; CloudFront-Signature=%s; CloudFront-Key-Pair-Id=%s"
                % (jar.get("CloudFront-Policy", ""), jar.get("CloudFront-Signature", ""),
                   jar.get("CloudFront-Key-Pair-Id", "")))

    def _jar_from_url(self, url):
        """从带 query 签名的播放地址里抠出 CloudFront 三件套，转成 Cookie 用。

        代理线路给的是 ...m3u8?Policy=..&Signature=..&Key-Pair-Id=..
        站点本来就支持把这同样的三个值当 Cookie 下发（直连接口就是发
        Set-Cookie 的），转成 Cookie 后子列表和分片才带得上签名。
        """
        try:
            q = parse_qs(urlsplit(str(url or "")).query)
        except Exception:
            return None
        try:
            jar = {}
            for k in ("Policy", "Signature", "Key-Pair-Id"):
                v = q.get(k)
                if v:
                    jar["CloudFront-" + k] = unquote(v[0])
            if (jar.get("CloudFront-Policy") and jar.get("CloudFront-Signature")
                    and jar.get("CloudFront-Key-Pair-Id")):
                return jar
        except Exception:
            pass
        return None

    # ---------------------------------------------------------- 鉴权
    def _gen_device(self):
        return "fw-%s-%s" % (uuid.uuid4().hex[:8], uuid.uuid4().hex[:10])

    def _ensure_token(self):
        if self._token:
            return self._token
        if not self._deviceId:
            self._deviceId = self._gen_device()
        url = self.apiBase + "/auth/guest"
        headers = self._headers(json_body=True)
        d = None
        try:
            if self.session is not None:
                r = self.session.post(url, data=json.dumps({"deviceId": self._deviceId}),
                                      headers=headers, timeout=20, verify=False)
                d = self._json(r)
            else:
                # 无第三方 requests 的壳：标准库兜底
                import urllib.request
                req = urllib.request.Request(
                    url, data=json.dumps({"deviceId": self._deviceId}).encode("utf-8"),
                    headers=headers, method="POST")
                r = urllib.request.urlopen(req, timeout=20)
                d = json.loads(r.read().decode("utf-8", "ignore"))
        except Exception:
            d = None
        if isinstance(d, dict):
            tok = d.get("token")
            if not tok and isinstance(d.get("data"), dict):
                tok = d["data"].get("token")
            self._token = str(tok or "").strip()
        if not self._token:
            raise RuntimeError("黄剧 guest 登录失败")
        return self._token

    # ---------------------------------------------------------- HTTP
    def _headers(self, json_body=False, with_auth=False, token=None):
        h = {
            "User-Agent": _HGJ_UA,
            "Accept": "application/json",
            "Origin": self.site,
            "Referer": self.site + "/",
        }
        if json_body:
            h["Content-Type"] = "application/json"
        if with_auth:
            h["Authorization"] = "Bearer " + (token or self._ensure_token())
        return h

    def _http_get(self, url, with_auth=False, retry=False):
        """带登录态 GET；401 清 token 重登一次再打，避免整段分类空白。"""
        headers = self._headers()
        if with_auth:
            try:
                headers = self._headers(with_auth=True)
            except Exception:
                # 登录失败就退匿名请求，别把整段分类直接打空
                headers = self._headers()
                with_auth = False
        r = self._raw_get(url, headers)
        if r is None:
            raise RuntimeError("无响应: %s" % url)
        body = self._json(r)
        if (isinstance(body, dict) and body.get("statusCode") == 401
                and with_auth and not retry):
            self._token = ""
            return self._http_get(url, True, True)
        return {"body": body, "res": r}

    def _raw_get(self, url, headers):
        if self.session is not None:
            try:
                return self.session.get(url, headers=headers, timeout=20, verify=False)
            except Exception:
                return None
        try:
            import urllib.request
            req = urllib.request.Request(url, headers=headers)
            return urllib.request.urlopen(req, timeout=20)
        except Exception:
            return None

    def _json(self, r):
        if r is None:
            return None
        try:
            return r.json()
        except Exception:
            pass
        try:
            txt = r.text if hasattr(r, "text") else r.read().decode("utf-8", "ignore")
        except Exception:
            return None
        try:
            return json.loads(txt)
        except Exception:
            return None

    # ---------------------------------------------------------- 工具
    @staticmethod
    def _qs_body(obj):
        parts = []
        for k, v in (obj or {}).items():
            if v is None or v == "":
                continue
            parts.append("%s=%s" % (quote(str(k)), quote(str(v))))
        return "&".join(parts)

    def _qs(self, obj):
        s = self._qs_body(obj)
        return "?" + s if s else ""

    @staticmethod
    def _as_list(d):
        if isinstance(d, list):
            return d
        if isinstance(d, dict):
            for k in ("items", "list", "dramas", "results", "data"):
                v = d.get(k)
                if isinstance(v, list):
                    return v
                if isinstance(v, dict):
                    for k2 in ("items", "list", "dramas", "results"):
                        if isinstance(v.get(k2), list):
                            return v[k2]
        return []

    @staticmethod
    def _unwrap(d):
        """详情兼容取数：本体直接给，或再包一层 data。"""
        if not isinstance(d, dict):
            return {}
        inner = d.get("data")
        if isinstance(inner, dict) and ("id" in inner or "episodes" in inner or "title" in inner):
            return inner
        return d

    def _strip_prefix(self, s):
        s = str(s or "").strip()
        for p in ("detail:", "play:", "huangju:", "huangju.net:", "hj:"):
            if s.startswith(p):
                s = s[len(p):]
                break
        if "play:" in s:
            s = s.split("play:", 1)[1]
        return s.strip()

    @staticmethod
    def _san(s):
        return str(s if s is not None else "").replace("#", " ").replace("$", " ").strip()

# =====================================================================
#  ENGINE MD · 麻豆成人 (原 2048成人短剧[18].py 融合)
#    site: https://mdcmai4.xyz
#    分类: /api/v1/categories?type=video
#    列表: /api/v1/videos?page&size&categoryId[&sortBy]          长视频(单集)
#          /api/v1/short-dramas?productId=1&sortBy&page&size   AI短剧
#    详情: /api/v1/short-dramas/{id}?productId=1                AI短剧(含全部分集)
#          /api/v1/videos/{id}                                  长视频兜底补地址
#    搜索: /api/v1/videos/search?page&size&q (短剧名走本地过滤)
#    中转: /api/v1/m3u8/proxy?path=     /api/v1/image/proxy?path=
#    type_id / vod_id 前缀: MD::       播放线路名: 麻豆成人 / 麻豆AI短剧
#    播放: 相对路径一律套站点 m3u8 中转(中转回来的清单里分片已是「绝对地址 +
#          auth_key」,不存在黄剧那种相对路径丢签名的坑),绝对地址原样放行
#    封面: /uploads/、/api/ 走直链,其余相对路径走 image 中转
# =====================================================================
_MD_TAG = "MD"
_MD_LINE_NAME = "2048短剧"
_MD_LINE_AI = "麻豆AI短剧"
_MD_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
_MD_API_BASE = "https://mdcmai4.xyz"
_MD_SIZE = 24
_MD_AI_TID = "ai"

# (tid, 中文名, categoryId) —— categoryId 取自站点 /api/v1/categories?type=video
_MD_CATEGORIES = [
    ("c27", "每日更新", 27),
    ("c1", "国产自拍(最新)", 1),
    ("c2", "AV中文字幕", 2),
    ("c8", "AV无码流出", 8),
    ("c9", "麻豆传媒", 9),
    ("c10", "麻豆×性吧联合原创", 10),
    ("c6", "麻豆原创AI", 6),
    ("c4", "探花大神", 4),
    ("c7", "91大神", 7),
    ("c13", "清纯少女", 13),
    ("c22", "白虎嫩妹", 22),
    ("c18", "白虎少女", 18),
    ("c16", "网红主播", 16),
    ("c25", "网黄原创", 25),
    ("c15", "直播大秀", 15),
    ("c21", "反差母狗", 21),
    ("c17", "媚黑母狗", 17),
    ("c24", "熟女偷情", 24),
    ("c23", "家庭乱伦", 23),
    ("c14", "重口调教", 14),
    ("c20", "破解偷拍", 20),
    ("c19", "黑料吃瓜", 19),
    ("c28", "世界杯专栏", 28),
]
_MD_CAT_MAP = {tid: cid for tid, _n, cid in _MD_CATEGORIES}
_MD_SORTS = [("latest", "最新"), ("heat", "最热")]


def _md_int(v, default=0):
    try:
        return int(str(v).strip())
    except Exception:
        return default


def _md_qs(obj):
    parts = []
    for k, v in (obj or {}).items():
        if v is None or v == "":
            continue
        parts.append("%s=%s" % (quote(str(k)), quote(str(v))))
    return ("?" + "&".join(parts)) if parts else ""


def _md_enc(s):
    return quote(str(s if s is not None else ""), safe="")


def _md_san(s):
    """清掉会截断 TVBox 播放串的分隔符。"""
    return (str(s if s is not None else "")
            .replace("#", " ").replace("$", " ")
            .replace("@@", " ").strip())


def _md_http_json(url, headers, timeout=20):
    """有 requests 就用(连接复用),没有就 urllib 兜底,拿不到一律回 {}。"""
    try:
        r = requests.get(url, headers=headers, timeout=timeout, verify=False)
        return r.json()
    except Exception:
        pass
    try:
        import urllib.request as _u
        req = _u.Request(url, headers=headers)
        with _u.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))
    except Exception:
        return {}


class _MadouSpider(_BaseSpider):
    """2048短剧 (mdcmai4.xyz)：AI短剧 + 长视频双形态,单一入口按 cate 分流。"""

    def __init__(self):
        self.name = _MD_LINE_NAME
        self.apiBase = _MD_API_BASE

    # ---------------------------------------------------------- 生命周期
    def init(self, extend=""):
        # 站点换域名时可在壳里传 {"apiBase": "https://..."} 救急,不用改代码
        try:
            if extend:
                conf = json.loads(extend) if isinstance(extend, str) else extend
                if isinstance(conf, dict) and conf.get("apiBase"):
                    self.apiBase = str(conf["apiBase"]).rstrip("/")
        except Exception:
            pass

    def getName(self):
        return _MD_LINE_NAME

    def getDependence(self):
        return []

    def isVideoFormat(self, url):
        u = str(url or "").lower()
        return any(x in u for x in (".m3u8", ".mp4", ".flv", ".ts", ".mkv"))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return

    # ---------------------------------------------------------- 首页 / 筛选
    def filter_meta(self):
        """给统一入口用的筛选：AI短剧 + 23 个分类(首项即默认,防白板)。"""
        cate = [{"n": "🔥AI短剧", "v": _MD_AI_TID}]
        cate += [{"n": n, "v": tid} for tid, n, _c in _MD_CATEGORIES]
        return [{"key": "cate", "name": "分类", "value": cate},
                {"key": "sort", "name": "排序",
                 "value": [{"n": n, "v": v} for v, n in _MD_SORTS]}]

    def homeContent(self, filter):
        classes = [{"type_id": _MD_AI_TID, "type_name": "🔥AI短剧"}]
        classes += [{"type_id": tid, "type_name": n} for tid, n, _c in _MD_CATEGORIES]
        result = {"class": classes}
        try:
            result["list"] = self.homeVideoContent().get("list", [])
        except Exception:
            pass
        return result

    def homeVideoContent(self):
        try:
            return {"list": self._ai_page(1).get("list") or []}
        except Exception:
            return {"list": []}

    # ---------------------------------------------------------- 分类
    def categoryContent(self, tid, pg, filter, extend):
        page = _md_int(pg, 1)
        if page < 1:
            page = 1
        tid = str(tid or "")
        extend = extend if isinstance(extend, dict) else {}
        sort = str(extend.get("sort") or "").strip()
        # 只点了顶级标签 / 传了空 → 默认 AI短剧，别甩白板
        if tid in ("", "root", "0"):
            tid = _MD_AI_TID
        if tid == _MD_AI_TID:
            return self._ai_page(page, sort or "heat")
        cid = _MD_CAT_MAP.get(tid)
        if cid is None:
            cid = _md_int(tid, 0)   # 兼容壳直接传裸 categoryId
        if not cid:
            return self._ai_page(page, sort or "heat")
        return self._video_page(cid, page, sort or "latest")

    def _ai_page(self, page, sort="heat"):
        query = {"productId": 1, "page": page, "size": _MD_SIZE}
        if sort:
            query["sortBy"] = sort
        d = self._page_data("/short-dramas", query)
        if not d.get("items") and sort:
            # 站点哪天不认 sortBy 了,去掉重打一次,别整页空白
            d = self._page_data("/short-dramas",
                                {"productId": 1, "page": page, "size": _MD_SIZE})
        return self._pack(self._ai_to_list(d.get("items")), page, d)

    def _video_page(self, cid, page, sort):
        query = {"page": page, "size": _MD_SIZE, "categoryId": cid}
        if sort:
            query["sortBy"] = sort
        d = self._page_data("/videos", query)
        if not d.get("items") and sort:
            d = self._page_data("/videos",
                                {"page": page, "size": _MD_SIZE, "categoryId": cid})
        return self._pack(self._video_to_list(d.get("items")), page, d)

    # ---------------------------------------------------------- 详情
    def detailContent(self, ids):
        raw = str((ids[0] if isinstance(ids, (list, tuple)) and ids else ids) or "")
        if _ENGINE_SEP in raw:
            raw = raw.split(_ENGINE_SEP, 1)[1]
        parts = raw.split("@@")
        kind = parts[0] if parts else ""
        if kind == "drama":
            return self._drama_detail(parts)
        if kind == "video":
            return self._video_detail(parts)
        if raw.lower().startswith("http") or ".m3u8" in raw.lower():
            return self._video_detail(["video", "", raw, "在线播放", ""])
        return self._video_detail(["video", raw, "", "在线播放", ""])

    def _drama_detail(self, parts):
        did = parts[1] if len(parts) > 1 else ""
        title = _md_san(parts[2]) if len(parts) > 2 else ""
        cover = parts[3] if len(parts) > 3 else ""
        d = self._unwrap(self._api_get("/short-dramas/" + _md_enc(did),
                                       {"productId": 1}))
        title = _md_san(d.get("title") or title or did)
        cover = str(d.get("coverUrl") or cover or "")
        eps = d.get("episodes") if isinstance(d.get("episodes"), list) else []

        parts_out = []
        for i, ep in enumerate(eps):
            if not isinstance(ep, dict):
                continue
            no = ep.get("episodeNo") or (i + 1)
            u = self._play_url(ep.get("videoUrl"))
            if u:
                parts_out.append("第%s集$%s" % (no, u))
        if not parts_out:
            parts_out.append("暂无分集数据$error")

        vod = {
            "vod_id": did,
            "vod_name": title,
            "vod_pic": self._cover(cover),
            "vod_content": _md_san(d.get("description") or ""),
            "vod_play_from": _MD_LINE_AI,
            "vod_play_url": "#".join(parts_out),
        }
        return {"list": [vod], "parse": 0, "jx": 0}

    def _video_detail(self, parts):
        vid = parts[1] if len(parts) > 1 else ""
        vurl = parts[2] if len(parts) > 2 else ""
        title = _md_san(parts[3]) if len(parts) > 3 else ""
        cover = parts[4] if len(parts) > 4 else ""
        # 带 id 没带地址 → 补拉一次详情接口,别让详情页空着
        if not vurl and vid and not vid.lower().startswith("http"):
            d = self._unwrap(self._api_get("/videos/" + _md_enc(vid)))
            vurl = str(d.get("videoUrl") or "")
            title = title or _md_san(d.get("title") or vid)
            cover = cover or str(d.get("coverUrl") or "")
        u = self._play_url(vurl)
        vod = {
            "vod_id": vid,
            "vod_name": title or "在线播放",
            "vod_pic": self._cover(cover),
            "vod_play_from": _MD_LINE_NAME,
            "vod_play_url": ("正片$%s" % u) if u else "暂无播放地址$error",
        }
        return {"list": [vod], "parse": 0, "jx": 0}

    # ---------------------------------------------------------- 搜索
    def searchContent(self, key, quick, pg="1"):
        page = _md_int(pg, 1)
        if page < 1:
            page = 1
        key = str(key or "").strip()
        if not key:
            return {"list": [], "page": page, "pagecount": 1,
                    "limit": 0, "total": 0, "parse": 0, "jx": 0}
        out = []
        d = self._page_data("/videos/search",
                            {"page": page, "size": _MD_SIZE, "q": key})
        out.extend(self._video_to_list(d.get("items")))
        # 站点短剧接口不吃 q → 第一页顺手在热门短剧里本地过滤一遍,别拖慢翻页
        if page == 1:
            try:
                d2 = self._page_data("/short-dramas",
                                     {"productId": 1, "sortBy": "heat",
                                      "page": 1, "size": 60})
                k = key.lower()
                for it in (d2.get("items") or []):
                    if isinstance(it, dict) and k in str(it.get("title") or "").lower():
                        out.extend(self._ai_to_list([it]))
            except Exception:
                pass
        return {"list": out, "page": page, "pagecount": page,
                "limit": len(out), "total": len(out), "parse": 0, "jx": 0}

    # ---------------------------------------------------------- 播放
    def playerContent(self, flag, id, vipFlags=None):
        s = str(id or "")
        if _ENGINE_SEP in s:
            s = s.split(_ENGINE_SEP, 1)[1]
        # 有些壳会把整个 vod_id 丢过来 → 自己剥出真实播放地址
        if "@@" in s:
            parts = s.split("@@")
            if parts[0] == "drama":
                s = self._first_ep_url(parts[1] if len(parts) > 1 else "")
            else:
                s = parts[2] if len(parts) > 2 else ""
        return {"parse": 0, "playUrl": "", "url": self._play_url(s),
                "header": self._headers()}

    def localProxy(self, param):
        return None

    def _first_ep_url(self, did):
        try:
            d = self._unwrap(self._api_get("/short-dramas/" + _md_enc(did),
                                           {"productId": 1}))
            for ep in (d.get("episodes") or []):
                if isinstance(ep, dict):
                    u = self._play_url(ep.get("videoUrl"))
                    if u:
                        return u
        except Exception:
            pass
        return ""

    # ================================================================ 内部

    def _headers(self, extra=None):
        h = {
            "User-Agent": _MD_UA,
            "Referer": self.apiBase + "/",
            "Origin": self.apiBase,
            "Accept": "application/json, text/plain, */*",
        }
        if extra:
            h.update(extra)
        return h

    def _api_get(self, path, query=None):
        url = self.apiBase + "/api/v1" + path + _md_qs(query or {})
        d = _md_http_json(url, self._headers(), 20)
        return d if isinstance(d, dict) else {}

    def _page_data(self, path, query):
        """列表接口取数：{data:{items,total,totalPages}} 或 data 直接是数组都能吃。"""
        d = self._api_get(path, query)
        if not isinstance(d, dict):
            return {}
        inner = d.get("data")
        if isinstance(inner, dict):
            return inner
        if isinstance(inner, list):
            return {"items": inner, "total": len(inner)}
        if isinstance(d.get("items"), list):
            return d
        return {}

    @staticmethod
    def _unwrap(d):
        if not isinstance(d, dict):
            return {}
        inner = d.get("data")
        return inner if isinstance(inner, dict) else {}

    def _pack(self, lst, page, d):
        total = _md_int((d or {}).get("total"), 0)
        pcount = _md_int((d or {}).get("totalPages"), 0)
        if not pcount:
            pcount = ((total + _MD_SIZE - 1) // _MD_SIZE) if total else page
        if pcount < 1:
            pcount = 1
        return {"list": lst, "page": page, "pagecount": pcount,
                "limit": len(lst) or _MD_SIZE, "total": total or len(lst),
                "parse": 0, "jx": 0}

    def _ai_to_list(self, items):
        out = []
        for it in items or []:
            if not isinstance(it, dict):
                continue
            vid = str(it.get("id") or "").strip()
            if not vid:
                continue
            title = _md_san(it.get("title") or vid)
            cover = str(it.get("coverUrl") or "")
            remark = []
            if it.get("rating"):
                remark.append("评分:%s" % it.get("rating"))
            if it.get("episodeCount"):
                remark.append("共%s集" % it.get("episodeCount"))
            out.append({
                "vod_id": "drama@@%s@@%s@@%s" % (vid, title, cover),
                "vod_name": title,
                "vod_pic": self._cover(cover),
                "vod_remarks": " | ".join(remark),
            })
        return out

    def _video_to_list(self, items):
        out = []
        for it in items or []:
            if not isinstance(it, dict):
                continue
            vid = str(it.get("id") or "").strip()
            vurl = str(it.get("videoUrl") or "").strip()
            if not vid and not vurl:
                continue
            title = _md_san(it.get("title") or vid)
            cover = str(it.get("coverUrl") or "")
            out.append({
                "vod_id": "video@@%s@@%s@@%s@@%s" % (vid, vurl, title, cover),
                "vod_name": title,
                "vod_pic": self._cover(cover),
                "vod_remarks": self._dur(it.get("durationSec")) or str(it.get("categoryName") or ""),
            })
        return out

    @staticmethod
    def _dur(sec):
        s = _md_int(sec, 0)
        if s <= 0:
            return ""
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        return ("%d:%02d:%02d" % (h, m, s)) if h else ("%02d:%02d" % (m, s))

    def _play_url(self, path):
        p = str(path or "").strip()
        if not p:
            return ""
        low = p.lower()
        if low.startswith("http://") or low.startswith("https://"):
            return p
        if low.startswith("//"):
            return "https:" + p
        if p.startswith("/api/v1/m3u8/proxy"):
            return self.apiBase + p
        return "%s/api/v1/m3u8/proxy?path=%s" % (self.apiBase, _md_enc(p))

    def _cover(self, path):
        p = str(path or "").strip()
        if not p:
            return ""
        low = p.lower()
        if low.startswith("http://") or low.startswith("https://"):
            return p
        if low.startswith("//"):
            return "https:" + p
        if p.startswith("/uploads/") or p.startswith("/api/"):
            return self.apiBase + p
        return "%s/api/v1/image/proxy?path=%s" % (self.apiBase, _md_enc(p))


# =====================================================================
#  ENGINE KB · 狂飙短剧 (原 狂飙短剧.py 单文件 Spider 融合)
#    site: https://ai.dramarush.tv         api: /api/trpc/*  (tRPC)
#    type_id / vod_id 前缀: KB::           播放线路名: 狂飙短剧
#    接口: /api/trpc/feed.recommend          首页推荐(nextCursor 翻页)
#          /api/trpc/feed.browse             分类列表(categorySlug / tagSlug /
#                                            contentKind + cursor 翻页)
#          /api/trpc/episode.watch           详情分集(dramaId + episodeNumber)
#    入参编码: input=quoted({"json": {...}}) —— tRPC superjson 惯例
#    分类(下沉为 cate 筛选): 首页推荐 / 短剧 / 成人短剧 / 正规短剧
#    成人 / 正规分流按 drama.tags 判定(adult- 前缀 / 含「不伦」「偷情」)
#    播放: 有分集 id 直接拼 raw.shorttv.online 直链 mp4；否则抓 /zh/watch 页面
#          解析地址，再退到 cdn 多条镜像逐个探活，最后用列表里的 trailerUrl 兜底
#    封面: 站点直链 + _minimize.webp 缩略，lsj 目录纠正到 raw 域名
#    换域名救急: 壳里传 {"kbApiBase": "https://..."}（用专属 key，不与其它
#                引擎共用的 apiBase 打架）
# =====================================================================
_KB_TAG = "KB"
_KB_LINE_NAME = "狂飙短剧"
_KB_HOST = "https://ai.dramarush.tv"
_KB_DEFAULT_TID = "recommend"
_KB_UA = ("Mozilla/5.0 (Linux; Android 12; Mobile) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")
_KB_RAW_HOST = "https://raw.shorttv.online"
_KB_CDN_HOST = "https://cdn.shorttv.online"

# (type_id, 中文名) —— 第一项即壳不传分类时的默认，防白板
_KB_CATEGORIES = [
    ("recommend",    "首页推荐"),
    ("t-5jxcit",     "短剧"),
    ("adult_short",  "成人短剧"),
    ("normal_short", "正规短剧"),
]

# 站点临时抽风时的兜底列表(原单文件版自带，保留)
_KB_FALLBACK = [
    {"vod_id": "cms5gkpmm08ic016polf4lbnq", "vod_name": "鸭王争霸【已更新】",
     "vod_pic": "https://raw.shorttv.online/images/2026-08-08/aa93208f-c3db-46f9-8a1b-8ac55fcc6298.jpg",
     "vod_remarks": "8集", "trailerUrl": "https://raw.shorttv.online/uploads/direct/cms5gkpmr08id016p43cfqk20/video.mp4"},
    {"vod_id": "cmsgx8rgr00lj010fi6lttg9c", "vod_name": "斗破苍穹",
     "vod_pic": "https://cdn.shorttv.online/images/2026-08-06/fca26c04-5a77-492c-a505-fa7440886090.jpg",
     "vod_remarks": "7集", "trailerUrl": "/api/media/centaurus/hls/cmsgx8rgu00lk010fjy2kas6p/h264/master.m3u8"},
    {"vod_id": "cmse0xyci0d300130psgoy5c5", "vod_name": "魔毒圣缘",
     "vod_pic": "https://cdn.shorttv.online/images/2026-08-04/2a3f6dc2-7491-4d7e-a2bd-a4d88c092d0f.png",
     "vod_remarks": "4集", "trailerUrl": "https://raw.shorttv.online/uploads/direct/cmse0xycl0d310130rev3nav1/video.mp4"},
    {"vod_id": "cmscmdvbu0ddb0173a71sc57c", "vod_name": "萌新三人行",
     "vod_pic": "https://raw.shorttv.online/images/2026-08-03/7be24fc7-0e0c-4587-b0ae-6b38d93aa5ec.jpg",
     "vod_remarks": "4集", "trailerUrl": "https://raw.shorttv.online/uploads/direct/cmscmdvbx0ddc0173yd1b2t9z/video.mp4"},
    {"vod_id": "cms6za7vq05sh010edvz48iun", "vod_name": "精液救世，丧尸围城",
     "vod_pic": "https://raw.shorttv.online/images/2026-07-30/e1c33bf0-db83-45ce-8213-4a274a9c5b48.jpg",
     "vod_remarks": "4集", "trailerUrl": ""},
    {"vod_id": "cms8rjowz00qo01cu1t7z6d8x", "vod_name": "等不到的她",
     "vod_pic": "https://raw.shorttv.online/images/2026-07-31/e04ce57f-2e01-455c-8357-4f4e2de5fc30.jpg",
     "vod_remarks": "5集", "trailerUrl": ""},
]


def _kb_int(v, default=1):
    try:
        return int(str(v).strip())
    except Exception:
        return default


class _KuangbiaoSpider(_BaseSpider):
    """狂飙短剧 (ai.dramarush.tv)：tRPC 接口 + cursor 翻页 + 本地剧名搜索。"""

    def __init__(self):
        self.name = _KB_LINE_NAME
        self.host = _KB_HOST
        self.headers = {
            "User-Agent": _KB_UA,
            "Referer": _KB_HOST + "/zh/",
            "Accept": "application/json,text/plain,*/*",
        }
        self.session = None
        self.cache = {}
        self.cursor = {}
        self.seen_page = {}
        self.eps = {}
        self.fallback = list(_KB_FALLBACK)

    # ---------------------------------------------------------- 生命周期
    def init(self, extend=""):
        # 站点换域名时可在壳里传 {"kbApiBase": "https://..."} 救急，不用改代码
        try:
            if extend:
                conf = json.loads(extend) if isinstance(extend, str) else extend
                if isinstance(conf, dict) and conf.get("kbApiBase"):
                    self.host = str(conf["kbApiBase"]).rstrip("/")
        except Exception:
            pass
        try:
            self.session = requests.Session()
        except Exception:
            self.session = None
        if not self.headers:
            self.headers = {}
        self.headers["Referer"] = self.host + "/zh/"
        self.cache = {}
        self.cursor = {}
        self.seen_page = {}
        self.eps = {}
        self.fallback = list(_KB_FALLBACK)
        return None

    def getName(self):
        return _KB_LINE_NAME

    def getDependence(self):
        return []

    def isVideoFormat(self, url):
        u = str(url or "").lower()
        return any(x in u for x in (".m3u8", ".mp4", ".flv", ".ts", ".mkv"))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        try:
            if self.session is not None:
                close = getattr(self.session, "close", None)
                if callable(close):
                    close()
        except Exception:
            pass
        return

    # ---------------------------------------------------------- 首页/分类
    def filter_meta(self):
        """给统一入口用的筛选：首项「首页推荐」= 壳不传分类时的默认，防白板。"""
        return [{"key": "cate", "name": "分类",
                 "value": [{"n": n, "v": tid} for tid, n in _KB_CATEGORIES]}]

    def homeContent(self, filter):
        classes = [{"type_id": tid, "type_name": n} for tid, n in _KB_CATEGORIES]
        result = {"class": classes}
        try:
            result["list"] = self.homeVideoContent().get("list") or []
        except Exception:
            pass
        return result

    def homeVideoContent(self):
        try:
            li = self._list("recommend")
        except Exception:
            li = []
        if not li:
            try:
                li = self._fallback_items()
            except Exception:
                li = []
        return {"list": li}

    def categoryContent(self, tid, pg, filter, extend):
        tid = str(tid or "")
        if tid in ("", "root", "0"):
            tid = _KB_DEFAULT_TID
        extend = extend if isinstance(extend, dict) else {}
        cate = str(extend.get("cate") or "").strip()
        if cate:
            tid = cate
        pg = _kb_int(pg, 1)
        li = self._list(tid, pg)
        has_next = bool(self.cursor.get(tid, {}).get(pg + 1))
        return {"page": pg, "pagecount": pg + 1 if has_next else pg,
                "limit": 12, "total": pg * 12 + (12 if has_next else 0),
                "count": len(li), "list": li}

    # ---------------------------------------------------------- 详情
    def detailContent(self, ids):
        out = []
        if not self.cache:
            try:
                self._list("t-5jxcit")
            except Exception:
                pass
        for vid in ids:
            it = self.cache.get(vid) or next(
                (x for x in self.fallback if x.get("vod_id") == vid),
                {"vod_id": vid, "vod_name": vid, "vod_pic": "", "vod_remarks": "12集", "vod_content": ""})
            m = re.search(r"(\d+)", str(it.get("vod_remarks") or ""))
            total = max(1, min(_kb_int(m.group(1), 12) if m else 12, 80))
            eps = self._episodes(vid)
            if eps:
                play = "#".join([
                    "第%d集$%s/%d/%s" % (
                        i, vid, i,
                        (eps[i - 1].get("id") if i - 1 < len(eps) and isinstance(eps[i - 1], dict) else ""))
                    for i in range(1, total + 1)])
            else:
                play = "第1集$%s/1/%s" % (vid, it.get("firstEpisodeId", ""))
            out.append({"vod_id": vid, "vod_name": it.get("vod_name", vid),
                        "vod_pic": it.get("vod_pic", ""), "vod_remarks": it.get("vod_remarks", ""),
                        "vod_content": it.get("vod_content", ""),
                        "vod_play_from": _KB_LINE_NAME, "vod_play_url": play})
        return {"list": out}

    # ---------------------------------------------------------- 搜索
    def searchContent(self, key, quick, pg="1"):
        """站点接口不吃搜索参数，拉一页大列表在本地按剧名过滤(不动翻页游标)。"""
        key = str(key or "").strip()
        page = _kb_int(pg, 1)
        out = []
        seen = set()
        if key:
            key_cmp = re.sub(r"\s+", "", key)
            try:
                d = self._api("feed.browse", {"categorySlug": "t-5jxcit", "limit": 30})
                for x in self._items(d):
                    name = re.sub(r"\s+", "", str(x.get("vod_name") or ""))
                    vid = x.get("vod_id")
                    if key_cmp and key_cmp in name and vid and vid not in seen:
                        seen.add(vid)
                        out.append(x)
            except Exception:
                out = []
        if not out and key:
            try:
                out = [x for x in self._list("t-5jxcit") if key in str(x.get("vod_name") or "")]
            except Exception:
                out = []
        return {"page": page, "list": out}

    # ---------------------------------------------------------- 播放
    def playerContent(self, flag, id, vipFlags=None):
        vid, ep, eid = (str(id).split("/") + ["1", ""])[:3]
        url = ""
        html = ""
        if eid:
            url = _KB_RAW_HOST + "/uploads/direct/" + eid + "/video.mp4"
        if not url:
            try:
                watch = self.host + "/zh/watch/" + vid + "/" + ep
                html = self.session.get(watch, headers={
                    "User-Agent": self.headers["User-Agent"], "Referer": watch}, timeout=12).text
            except Exception:
                pass
            url = self._media(html)
        if not url:
            eid = self._eid(html)
            arr = []
            if eid:
                arr = [_KB_RAW_HOST + "/uploads/direct/" + eid + "/video.mp4",
                       _KB_CDN_HOST + "/uploads/direct/" + eid + "/video.mp4",
                       _KB_CDN_HOST + "/uploads/hls/" + eid + "/master.m3u8",
                       _KB_CDN_HOST + "/lsj/hls/" + eid + "/master.m3u8",
                       _KB_CDN_HOST + "/dc/hls/" + eid + "/master.m3u8"]
            for u in arr:
                if self._alive(u):
                    url = u
                    break
        if not url:
            it = self.cache.get(vid) or next((x for x in self.fallback if x.get("vod_id") == vid), {})
            url = self._fix(it.get("trailerUrl", ""))
        return {"parse": 0 if url else 1, "url": self._unesc(url),
                "header": json.dumps({"User-Agent": self.headers["User-Agent"],
                                      "Referer": self.host + "/zh/", "Origin": self.host})}

    # ---------------------------------------------------------- 内部工具
    def _enc(self, o):
        return quote(json.dumps({"json": o}, ensure_ascii=False, separators=(",", ":")), safe="")

    def _api(self, name, data=None):
        try:
            url = self.host + "/api/trpc/" + name + ("?input=" + self._enc(data) if data is not None else "")
            sess = self.session
            if sess is None:
                sess = requests.Session()
                self.session = sess
            return sess.get(url, headers=self.headers, timeout=12).json().get("result", {}).get("data", {}).get("json", {})
        except Exception:
            return {} if data is not None else []

    def _fix(self, u):
        return self.host + u if u and u.startswith("/") else u or ""

    def _img_min(self, u):
        if not u or "_minimize." in u:
            return u or ""
        q = ""
        p = u
        if "?" in u:
            p, q = u.split("?", 1)
            q = "?" + q
        i = p.rfind(".")
        return (p[:i] + "_minimize.webp" + q) if i > p.rfind("/") else u

    def _pic(self, v, x):
        a = [v.get("cover"), v.get("poster"), x.get("vod_pic")]
        b = []
        for u in a:
            if not u or "dc/img/828ed491f008e85d9caef01a.jpg" in u:
                continue
            if "cdn.shorttv.online/lsj/" in u:
                u = u.replace("https://cdn.shorttv.online/lsj/", "https://raw.shorttv.online/lsj/")
            b.append(self._img_min(u))
        return b[0] if b else ""

    def _it(self, x):
        if not isinstance(x, dict):
            return {}
        v = x.get("drama") or x
        vid = str(v.get("id") or x.get("id") or "")
        if not vid:
            return {}
        d = {"vod_id": vid,
             "vod_name": v.get("title") or x.get("vod_name") or vid,
             "vod_pic": self._pic(v, x),
             "vod_remarks": (str(v.get("totalEpisodes") or "").strip() + "集")
                            if v.get("totalEpisodes") else x.get("vod_remarks", "")}
        d["vod_content"] = v.get("description") or x.get("vod_content", "")
        d["trailerUrl"] = self._fix(x.get("trailerUrl") or "")
        d["firstEpisodeId"] = x.get("firstEpisodeId") or ""
        return d

    def _items(self, d, mode="all", need_pic=False):
        arr = d.get("items", []) if isinstance(d, dict) else (d if isinstance(d, list) else [])
        out = []
        seen_id = set()
        seen_name = set()
        for x in arr:
            v = x.get("drama") if isinstance(x, dict) else {}
            tags = [str(t.get("name") or "") for t in v.get("tags", []) if isinstance(t, dict)] if isinstance(v, dict) else []
            adult = any(t.startswith("adult-") or "不伦" in t or "偷情" in t for t in tags)
            if (mode == "adult" and not adult) or (mode == "normal" and adult):
                continue
            it = self._it(x)
            name = re.sub(r"\s+", "", str(it.get("vod_name") or ""))
            if need_pic and not it.get("vod_pic"):
                continue
            if it.get("vod_id") and name and it["vod_id"] not in seen_id and name not in seen_name:
                seen_id.add(it["vod_id"])
                seen_name.add(name)
                self.cache[it["vod_id"]] = it
                out.append({k: it.get(k, "") for k in ["vod_id", "vod_name", "vod_pic", "vod_remarks"]})
        return out

    def _fallback_items(self):
        out = []
        seen = set()
        for x in self.fallback:
            name = re.sub(r"\s+", "", str(x.get("vod_name") or ""))
            if name not in seen:
                seen.add(name)
                self.cache[x["vod_id"]] = x
                out.append({k: x.get(k, "") for k in ["vod_id", "vod_name", "vod_pic", "vod_remarks"]})
        return out

    def _list(self, tid="t-5jxcit", pg=1):
        pg = _kb_int(pg, 1)
        if pg < 1:
            pg = 1
        tid = str(tid or "") or _KB_DEFAULT_TID
        mp = {"t-5jxcit": {"categorySlug": "t-5jxcit"},
              "adult_short": {"tagSlug": "adult"},
              "normal_short": {"contentKind": "SHORT_DRAMA"}}
        if pg == 1:
            self.cursor[tid] = {}
            self.seen_page[tid] = set()
        cur = self.cursor.get(tid, {}).get(pg)
        if pg > 1 and not cur:
            return []
        mode = "adult" if tid == "adult_short" else "normal" if tid == "normal_short" else "all"
        seen = self.seen_page.setdefault(tid, set())
        out = []
        nxt = ""
        if tid in ["recommend", "all", ""]:
            # 推荐流也吃 cursor(实测第二页与第一页零重叠)，不传就会一直重播第一页
            rdata = {"limit": 12}
            if cur:
                rdata["cursor"] = cur
            d = self._api("feed.recommend", rdata)
            nxt = d.get("nextCursor") if isinstance(d, dict) else ""
            for x in self._items(d):
                k = x.get("vod_id") or re.sub(r"\s+", "", str(x.get("vod_name") or ""))
                if k and k not in seen:
                    seen.add(k)
                    out.append(x)
        else:
            data = dict({"limit": 12}, **mp.get(tid, {"categorySlug": tid}))
            if cur:
                data["cursor"] = cur
            loops = 8 if tid in ["adult_short", "normal_short"] else 1
            for _ in range(loops):
                d = self._api("feed.browse", data)
                nxt = d.get("nextCursor") if isinstance(d, dict) else ""
                for x in self._items(d, mode, tid == "normal_short"):
                    k = x.get("vod_id") or re.sub(r"\s+", "", str(x.get("vod_name") or ""))
                    if k and k not in seen:
                        seen.add(k)
                        out.append(x)
                    if len(out) >= 12:
                        break
                if len(out) >= 12 or not nxt:
                    break
                data["cursor"] = nxt
        if nxt:
            self.cursor.setdefault(tid, {})[pg + 1] = nxt
        return out

    def _episodes(self, vid):
        if vid in self.eps:
            return self.eps[vid]
        d = self._api("episode.watch", {"dramaId": vid, "episodeNumber": 1})
        arr = d.get("episodes", []) if isinstance(d, dict) else []
        if not isinstance(arr, list):
            arr = []
        self.eps[vid] = arr
        return arr

    def _unesc(self, s):
        return (s or "").replace("\\u0026", "&").replace("\\/", "/")

    def _media(self, h):
        h = self._unesc(h)
        m = (re.search(r'<video[^>]+src="([^"]+)', h)
             or re.search(r'"(?:hlsUrl|playUrl|videoUrl|sourceUrl|mediaUrl|trailerUrl)"\s*:\s*"([^"]+?\.(?:m3u8|mp4)[^"]*)"', h)
             or re.search(r'https?://[^"\\\s<>]+?\.(?:mp4|m3u8)[^"\\\s<>]*', h))
        return self._fix(m.group(1) if m and m.lastindex else m.group(0) if m else "")

    def _eid(self, h):
        """从播放页里抠分集 id。站点 id 前缀并不固定(cms / cmu / ...)，
        所以这里不做前缀限制，只认「episode.id」和「episodeId」两个字段，
        免得误抓到 dramaId。"""
        h = self._unesc(h)
        m = (re.search(r'"episode"\s*:\s*\{[^{}]*"id"\s*:\s*"([^"]+)"', h)
             or re.search(r'"episodeId"\s*:\s*"([a-zA-Z0-9]{12,})"', h))
        return m.group(1) if m else ""

    def _alive(self, u):
        try:
            sess = self.session or requests
            r = sess.get(u, headers={"User-Agent": self.headers["User-Agent"],
                                     "Referer": self.host + "/", "Origin": self.host,
                                     "Range": "bytes=0-0"}, timeout=4, stream=True)
            return int(getattr(r, "status_code", 0) or 0) in (200, 206)
        except Exception:
            return False

# =====================================================================
#  统一入口 Spider · 九引擎聚合分发
#    type_id / vod_id 前缀:  HG::(红果)  HD::(黄豆)  HGUO::(黄果)
#                            YG::(野果)  JG::(禁果)  HGJ::(红果黄剧)  AG::(聚合15平台)
#                            MD::(2048短剧)  KB::(狂飙短剧)
#    播放线路(flag)天然可区分:  含"红果"→红果   含"黄果"/"目录"→黄果
#                             含"黄豆"→黄豆    含"野果"→野果
#                             含"禁果"→禁果    含"黄剧"→红果黄剧(判序在红果之前)
#                             含"2048短剧"→2048短剧 含"狂飙"→狂飙短剧   其余→聚合平台名
#    本机代理(param)区分:      eng=hguo → 黄果   eng=yeguo → 野果   其余 → 红果
# =====================================================================
_ENGINE_SEP = "::"


def _dj_prefix_list(result, tag):
    """给 result['list'] 每个条目的 vod_id 打上引擎前缀。"""
    if not isinstance(result, dict):
        return result
    for it in (result.get("list") or []):
        if isinstance(it, dict) and it.get("vod_id") is not None:
            it["vod_id"] = "%s%s%s" % (tag, _ENGINE_SEP, it["vod_id"])
    return result


def _dj_agg_items_to_list(items, tag="AG"):
    out = []
    for it in (items or []):
        url = it.get("url") or ""
        out.append({
            "vod_id": "%s%s%s" % (tag, _ENGINE_SEP, url),
            "vod_name": it.get("title") or "",
            "vod_pic": it.get("img") or "",
            "vod_remarks": it.get("desc") or "",
        })
    return out


class Spider(_BaseSpider):
    """九合一短剧聚合：红果 + 黄豆 + 黄果 + 野果 + 禁果 + 红果黄剧 + 聚合(15平台) + 2048短剧 + 狂飙短剧。"""

    def __init__(self):
        self._hg = _HongguoSpider()
        self._hd = _HuangdouSpider()
        self._hguo = _HuangguoSpider()
        self._yg = _YeguoSpider()
        self._jg = _JinguoSpider()
        self._hgj = _HuangjuSpider()
        self._ag = _AggSpider()
        self._md = _MadouSpider()
        self._kb = _KuangbiaoSpider()
        self._ag_ready = False

    # ---------- 基础信息 ----------
    def getName(self):
        return "聚合短剧九合一"

    def init(self, extend=""):
        try:
            self._hg.init(extend)
        except Exception:
            pass
        try:
            self._hd.init(extend)
        except Exception:
            pass
        try:
            self._hguo.init(extend)
        except Exception:
            pass
        try:
            self._yg.init(extend)
        except Exception:
            pass
        try:
            self._jg.init(extend)
        except Exception:
            pass
        try:
            self._hgj.init(extend)
        except Exception:
            pass
        try:
            self._md.init(extend)
        except Exception:
            pass
        try:
            self._kb.init(extend)
        except Exception:
            pass
        return None

    def isVideoFormat(self, url):
        u = str(url or "").lower()
        return any(x in u for x in
                   (".mp4", ".m3u8", "video_mp4", "mime_type=video", "qznovelvod", ".ts"))

    def manualVideoCheck(self):
        return False

    def getDependence(self):
        return []

    def destroy(self):
        try:
            self._hg.destroy()
        except Exception:
            pass
        try:
            self._hguo.destroy()
        except Exception:
            pass
        try:
            self._yg.destroy()
        except Exception:
            pass
        try:
            self._md.destroy()
        except Exception:
            pass
        try:
            self._kb.destroy()
        except Exception:
            pass
        return None

    def _ensure_ag(self):
        if not self._ag_ready:
            try:
                self._ag.prepare()
            except Exception:
                pass
            self._ag_ready = True

    def _bind_proxy(self):
        """把框架注入到本实例上的 getProxyUrl 转交给需要本机代理的引擎。"""
        fn = getattr(self, "getProxyUrl", None)
        if fn is not None:
            for eng in (self._hg, self._hguo, self._yg):
                try:
                    eng.getProxyUrl = fn
                except Exception:
                    pass

    # ---------- 首页 ----------
    def homeContent(self, filter):
        """只返回分类与筛选（静态、无阻塞网络），保证标签栏一定即时出现。
        规整：红果 / 黄豆 各收敛为单一顶级分类，小分类下沉为筛选（与聚合各平台一致）。"""
        class_list = []
        filters = {}

        # 红果：单一顶级「🔴红果短剧」，短剧/AI漫剧/最新/最热/男频/女频 + 主题/背景/设定/时间 下沉为筛选
        try:
            meta = self._hg.home_meta()
            hg_cats = meta.get("class") or []
            fdict = meta.get("filters") or {}
            base_groups = []
            for c in hg_cats:
                g = fdict.get(c.get("type_id"))
                if g:
                    base_groups = list(g)
                    break
            cate_group = {"key": "cate", "name": "分类",
                          "value": [{"n": c.get("type_name"), "v": str(c.get("type_id"))}
                                    for c in hg_cats]}
            hg_root = "HG%sroot" % _ENGINE_SEP
            class_list.append({"type_id": hg_root, "type_name": "🔴红果短剧"})
            filters[hg_root] = [cate_group] + base_groups
        except Exception:
            pass

        # 聚合 15 平台（静态，本就是单平台顶级 + 筛选）
        try:
            for c in self._ag.classes():
                class_list.append({"type_id": "AG%s%s" % (_ENGINE_SEP, c.get("type_id")),
                                   "type_name": "🟢%s" % c.get("type_name")})
            for k, v in (self._ag.filters() or {}).items():
                filters["AG%s%s" % (_ENGINE_SEP, k)] = v
        except Exception:
            pass

        # 黄豆：单一顶级「🟡黄豆短剧」，全部短剧/原豆推荐 下沉为筛选
        hd_root = "HD%sroot" % _ENGINE_SEP
        class_list.append({"type_id": hd_root, "type_name": "🟡黄豆短剧"})
        filters[hd_root] = [{"key": "cate", "name": "分类", "value": [
            {"n": "全部短剧", "v": "all"}, {"n": "原豆推荐", "v": "yuandou"}]}]

        # 黄果：单一顶级「🟠黄果短剧」，7 个分类下沉为 cate 筛选，子分类为 sub
        hguo_root = "HGUO%sroot" % _ENGINE_SEP
        try:
            class_list.append({"type_id": hguo_root, "type_name": "🟠黄果短剧"})
            filters[hguo_root] = self._hguo.filter_meta()
        except Exception:
            pass

        # 野果：单一顶级「🟣野果短剧」，13 个分类下沉为 cate 筛选（首项首页推荐即默认，防白板）
        yg_root = "YG%sroot" % _ENGINE_SEP
        try:
            class_list.append({"type_id": yg_root, "type_name": "🟣野果短剧"})
            filters[yg_root] = self._yg.filter_meta()
        except Exception:
            pass

        # 禁果：单一顶级「🔵禁果短剧」，15 个分类下沉为 cate 筛选（首项首页推荐即默认，防白板）
        jg_root = "JG%sroot" % _ENGINE_SEP
        try:
            class_list.append({"type_id": jg_root, "type_name": "🔵禁果短剧"})
            filters[jg_root] = self._jg.filter_meta()
        except Exception:
            pass

        # 红果黄剧：单一顶级「🟤红果黄剧」，15 个分类下沉为 cate 筛选（默认落热门，防白板）
        hgj_root = "HGJ%sroot" % _ENGINE_SEP
        try:
            class_list.append({"type_id": hgj_root, "type_name": "🟤红果黄剧"})
            filters[hgj_root] = self._hgj.filter_meta()
        except Exception:
            pass

        # 2048短剧：单一顶级「🔞2048短剧」，AI短剧 + 23 个分类下沉为 cate 筛选（默认 AI短剧，防白板）
        md_root = "MD%sroot" % _ENGINE_SEP
        try:
            class_list.append({"type_id": md_root, "type_name": "🔞2048短剧"})
            filters[md_root] = self._md.filter_meta()
        except Exception:
            pass

        # 狂飙短剧：单一顶级「⚡狂飙短剧」，4 个分类下沉为 cate 筛选（默认首页推荐，防白板）
        kb_root = "KB%sroot" % _ENGINE_SEP
        try:
            class_list.append({"type_id": kb_root, "type_name": "⚡狂飙短剧"})
            filters[kb_root] = self._kb.filter_meta()
        except Exception:
            pass

        return {"class": class_list, "filters": filters, "list": [], "parse": 0, "jx": 0}

    def homeVideoContent(self):
        """首页推荐列表单独拉取（框架会另行调用），失败静默不影响标签。"""
        out = []
        try:
            hg = self._hg.homeVideoContent()
            _dj_prefix_list(hg, "HG")
            out.extend(hg.get("list") or [])
        except Exception:
            pass
        return {"list": out}

    # ---------- 分类 ----------
    def categoryContent(self, tid, pg, filter, extend):
        engine, _, real = str(tid).partition(_ENGINE_SEP)
        extend = extend or {}
        if isinstance(extend, str):
            extend = _ag_json(extend) or {}
        if not isinstance(extend, dict):
            extend = {}
        if engine == "HG":
            if real == "root":
                extend = dict(extend)
                real = str(extend.pop("cate", "") or "all")
            return _dj_prefix_list(self._hg.categoryContent(real, pg, filter, extend), "HG")
        if engine == "HD":
            if real == "root":
                extend = dict(extend)
                real = str(extend.pop("cate", "") or "all")
            return _dj_prefix_list(self._hd.categoryContent(real, pg, filter, extend), "HD")
        if engine == "HGUO":
            if real == "root":
                extend = dict(extend)
                real = str(extend.pop("cate", "") or "")
            return _dj_prefix_list(self._hguo.categoryContent(real, pg, filter, extend), "HGUO")
        if engine == "YG":
            if real == "root":
                extend = dict(extend)
                real = str(extend.pop("cate", "") or "home")
            return _dj_prefix_list(self._yg.categoryContent(real, pg, filter, extend), "YG")
        if engine == "JG":
            if real == "root":
                extend = dict(extend)
                real = str(extend.pop("cate", "") or "home")
            return _dj_prefix_list(self._jg.categoryContent(real, pg, filter, extend), "JG")
        if engine == "HGJ":
            if real == "root":
                extend = dict(extend)
                real = str(extend.pop("cate", "") or "hot")
            return _dj_prefix_list(self._hgj.categoryContent(real, pg, filter, extend), "HGJ")
        if engine == "MD":
            if real == "root":
                extend = dict(extend)
                real = str(extend.pop("cate", "") or _MD_AI_TID)
            return _dj_prefix_list(self._md.categoryContent(real, pg, filter, extend), "MD")
        if engine == "KB":
            if real == "root":
                extend = dict(extend)
                real = str(extend.pop("cate", "") or _KB_DEFAULT_TID)
            return _dj_prefix_list(self._kb.categoryContent(real, pg, filter, extend), "KB")
        if engine == "AG":
            self._ensure_ag()
            area = ""
            if isinstance(extend, dict):
                area = extend.get("area") or extend.get("class") or ""
            if not area:
                area = (AGG_FILTER_DEF.get(real) or {}).get("area", "")
            try:
                page = max(1, int(pg))
            except (TypeError, ValueError):
                page = 1
            items = self._ag.category(real, area, page)
            lst = _dj_agg_items_to_list(items, "AG")
            return {"page": page, "pagecount": page if len(lst) < 18 else page + 1,
                    "limit": len(lst) or 18, "total": 999999, "list": lst, "parse": 0, "jx": 0}
        return {"list": []}

    # ---------- 详情 ----------
    def detailContent(self, ids):
        raw = ids[0] if isinstance(ids, (list, tuple)) else ids
        engine, _, real = str(raw).partition(_ENGINE_SEP)
        if engine == "HG":
            return self._hg.detailContent([real])
        if engine == "HD":
            return self._hd.detailContent([real])
        if engine == "HGUO":
            return self._hguo.detailContent([real])
        if engine == "YG":
            return self._yg.detailContent([real])
        if engine == "JG":
            return self._jg.detailContent([real])
        if engine == "HGJ":
            return self._hgj.detailContent([real])
        if engine == "MD":
            return self._md.detailContent([real])
        if engine == "KB":
            return self._kb.detailContent([real])
        if engine == "AG":
            self._ensure_ag()
            vod = self._ag.detail(real)
            return {"list": [vod] if vod else [], "parse": 0, "jx": 0}
        # 无前缀兜底：按红果处理
        return self._hg.detailContent([raw])

    # ---------- 搜索 ----------
    def searchContent(self, key, quick=False, pg="1"):
        try:
            page = max(1, int(pg))
        except (TypeError, ValueError):
            page = 1
        merged = []

        try:
            r = self._hg.searchContent(key, quick, str(page))
            _dj_prefix_list(r, "HG")
            merged.extend(r.get("list") or [])
        except Exception:
            pass
        try:
            r = self._hd.searchContent(key, quick, str(page))
            _dj_prefix_list(r, "HD")
            merged.extend(r.get("list") or [])
        except Exception:
            pass
        try:
            r = self._hguo.searchContent(key, quick, str(page))
            _dj_prefix_list(r, "HGUO")
            merged.extend(r.get("list") or [])
        except Exception:
            pass
        try:
            r = self._yg.searchContent(key, quick, str(page))
            _dj_prefix_list(r, "YG")
            merged.extend(r.get("list") or [])
        except Exception:
            pass
        try:
            r = self._jg.searchContent(key, quick, str(page))
            _dj_prefix_list(r, "JG")
            merged.extend(r.get("list") or [])
        except Exception:
            pass
        try:
            r = self._hgj.searchContent(key, quick, str(page))
            _dj_prefix_list(r, "HGJ")
            merged.extend(r.get("list") or [])
        except Exception:
            pass
        try:
            r = self._md.searchContent(key, quick, str(page))
            _dj_prefix_list(r, "MD")
            merged.extend(r.get("list") or [])
        except Exception:
            pass
        try:
            r = self._kb.searchContent(key, quick, str(page))
            _dj_prefix_list(r, "KB")
            merged.extend(r.get("list") or [])
        except Exception:
            pass
        try:
            self._ensure_ag()
            items = self._ag.search(key, page)
            merged.extend(_dj_agg_items_to_list(items, "AG"))
        except Exception:
            pass

        return {"page": page, "pagecount": page, "limit": len(merged),
                "total": len(merged), "list": merged, "parse": 0, "jx": 0}

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags=None):
        f = str(flag or "")
        # "红果黄剧" 线路名里含 "红果"，必须先判黄剧，否则会被红果抢走
        if "黄剧" in f:
            return self._hgj.playerContent(flag, id, vipFlags)
        if "红果" in f:
            self._bind_proxy()
            return self._hg.playerContent(flag, id, vipFlags)
        if "黄果" in f or f == "目录":
            self._bind_proxy()
            return self._hguo_player(flag, id, vipFlags)
        if "黄豆" in f:
            return self._hd.playerContent(flag, id, vipFlags)
        if "野果" in f:
            return self._yg.playerContent(flag, id, vipFlags)
        if "禁果" in f:
            return self._jg.playerContent(flag, id, vipFlags)
        if "麻豆" in f:
            return self._md.playerContent(flag, id, vipFlags)
        if "狂飙" in f:
            return self._kb.playerContent(flag, id, vipFlags)
        # 其余线路名均属聚合平台（河马/百度/牛牛/山海/好看/星芽/西饭/七猫/围观/五一/星星/薏米/爽爽/喜福/五五）
        self._ensure_ag()
        return self._ag.player(flag, id)

    # ---------- 黄果播放（专辑目录递进） ----------
    # ---------- 本机代理（红果解密 / 黄果 m3u8 中转） ----------
    def _hguo_player(self, flag, vid, vipFlags=None):
        """黄果播放：先剥掉引擎前缀；专辑目录(folder)递进时再把前缀补回 tid。"""
        raw = str(vid or "")
        real = raw.split(_ENGINE_SEP, 1)[1] if _ENGINE_SEP in raw else raw
        res = self._hguo.playerContent(flag, real, vipFlags)
        if isinstance(res, dict) and res.get("parse") == 1:
            u = str(res.get("url") or "")
            if u and _ENGINE_SEP not in u and not re.match(r"^https?://", u):
                res = dict(res)
                res["url"] = "%s%s%s" % (_HGUO_TAG, _ENGINE_SEP, u)
        return res

    def localProxy(self, param):
        param = param or {}
        # 黄果代理请求带 eng=hguo 标记；红果靠数字 vid 识别，两边互不干扰
        if _hguo_pv(param, "eng") == "hguo":
            return self._hguo.localProxy(param)
        if _hguo_pv(param, "eng") == "yeguo":
            return self._yg.localProxy(param)
        self._bind_proxy()
        return self._hg.localProxy(param)

    def proxy(self, param):
        return self.localProxy(param)

    def liveContent(self):
        return {}

    def isVPAYard(self, flag):
        return False

    def action(self, action):
        return ""
