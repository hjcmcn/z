# -*- coding: utf-8 -*-
"""
TVBox 壳子 py 插件 —— ONE一个 (csp_One)
=====================================
壳内直接加载，纯标准库实现（不需要 pip install 任何东西）：
  AES-128-CBC 自己实现、请求 urllib、JSON json、TLS 用 ssl 免校验。

放置与配置见同目录 README_TVBox.md，最小写法：
  api.json 里
  {"key":"one","name":"一个app","type":3,"api":"one","searchable":1,
   "quickSearch":1,"filterable":0,"ext":""}
  插件文件命名为 one.py，放进壳子的 spider 目录（或与配置同目录）。

ext 可选（& 分隔）：
  token=eyJ...   api=https://xxx/   line=http://ip:9672
  uuid=...       userkey=...        months=12   cooldown=20
  imgtimeout=15  mediaua=...        playref=1   host=a.com,b.com
  imghost=https://img807.hkq57tt.com  强制图片域名（裂图时换域名试）
图片域名说明（2026-11-18 实测）：bootstrap 的 image/flutter_enc_img 域名
返回 AES 加密字节，壳子直连必然裂图；flutter_img/resource 域名对同一
路径返回正常图片，_img 只走这两类明文域名。
"""
import base64
import hashlib
import json
import random
import re
import ssl
import threading
import time
import urllib.parse
import urllib.request
import zlib

try:                                  # 部分壳要求继承 base.spider.Spider
    from base.spider import Spider as _BaseSpider
except Exception:
    _BaseSpider = object


SBOX = (
0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16)
INV_SBOX = [0] * 256
for _i, _v in enumerate(SBOX):
    INV_SBOX[_v] = _i
RCON = (0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x80,0x1b,0x36)


def _xtime(a):
    a <<= 1
    return (a ^ 0x1b) & 0xff if a & 0x100 else a


def _mul(a, b):
    r = 0
    while b:
        if b & 1:
            r ^= a
        a = _xtime(a)
        b >>= 1
    return r


def _expand(key):
    assert len(key) == 16
    w = [list(key[i:i + 4]) for i in range(0, 16, 4)]
    for i in range(4, 44):
        t = list(w[i - 1])
        if i % 4 == 0:
            t = t[1:] + t[:1]
            t = [SBOX[x] for x in t]
            t[0] ^= RCON[i // 4 - 1]
        w.append([w[i - 4][j] ^ t[j] for j in range(4)])
    return [sum(w[4 * r:4 * r + 4], []) for r in range(11)]


def _add_round(s, k):
    return [s[i] ^ k[i] for i in range(16)]


def _shift_rows(s):
    return [s[0],s[5],s[10],s[15], s[4],s[9],s[14],s[3],
            s[8],s[13],s[2],s[7], s[12],s[1],s[6],s[11]]


def _inv_shift_rows(s):
    return [s[0],s[13],s[10],s[7], s[4],s[1],s[14],s[11],
            s[8],s[5],s[2],s[15], s[12],s[9],s[6],s[3]]


def _mix(s):
    o = [0] * 16
    for c in range(4):
        a = s[4 * c:4 * c + 4]
        o[4*c+0] = _mul(a[0],2) ^ _mul(a[1],3) ^ a[2] ^ a[3]
        o[4*c+1] = a[0] ^ _mul(a[1],2) ^ _mul(a[2],3) ^ a[3]
        o[4*c+2] = a[0] ^ a[1] ^ _mul(a[2],2) ^ _mul(a[3],3)
        o[4*c+3] = _mul(a[0],3) ^ a[1] ^ a[2] ^ _mul(a[3],2)
    return o


def _inv_mix(s):
    o = [0] * 16
    for c in range(4):
        a = s[4 * c:4 * c + 4]
        o[4*c+0] = _mul(a[0],14) ^ _mul(a[1],11) ^ _mul(a[2],13) ^ _mul(a[3],9)
        o[4*c+1] = _mul(a[0],9) ^ _mul(a[1],14) ^ _mul(a[2],11) ^ _mul(a[3],13)
        o[4*c+2] = _mul(a[0],13) ^ _mul(a[1],9) ^ _mul(a[2],14) ^ _mul(a[3],11)
        o[4*c+3] = _mul(a[0],11) ^ _mul(a[1],13) ^ _mul(a[2],9) ^ _mul(a[3],14)
    return o


def encrypt_block(block, rk):
    s = _add_round(list(block), rk[0])
    for r in range(1, 10):
        s = [SBOX[x] for x in s]
        s = _shift_rows(s)
        s = _mix(s)
        s = _add_round(s, rk[r])
    s = [SBOX[x] for x in s]
    s = _shift_rows(s)
    return bytes(_add_round(s, rk[10]))


def decrypt_block(block, rk):
    s = _add_round(list(block), rk[10])
    for r in range(9, 0, -1):
        s = _inv_shift_rows(s)
        s = [INV_SBOX[x] for x in s]
        s = _add_round(s, rk[r])
        s = _inv_mix(s)
    s = _inv_shift_rows(s)
    s = [INV_SBOX[x] for x in s]
    return bytes(_add_round(s, rk[0]))


def cbc_encrypt(data, key, iv):
    rk = _expand(key)
    pad = 16 - len(data) % 16
    data = data + bytes([pad]) * pad
    out = bytearray()
    prev = iv
    for i in range(0, len(data), 16):
        blk = bytes(a ^ b for a, b in zip(data[i:i + 16], prev))
        prev = encrypt_block(blk, rk)
        out += prev
    return bytes(out)


def cbc_decrypt(data, key, iv):
    rk = _expand(key)
    out = bytearray()
    prev = iv
    for i in range(0, len(data), 16):
        blk = data[i:i + 16]
        out += bytes(a ^ b for a, b in zip(decrypt_block(blk, rk), prev))
        prev = blk
    pad = out[-1]
    if 1 <= pad <= 16 and out[-pad:] == bytes([pad]) * pad:
        out = out[:-pad]
    return bytes(out)

# ======================== 常量（自 dex 解出） ========================
BODY_KEY = b"l*bv%Ziq000Biaog"
BODY_IV = b"8597506002939249"
CFG_KEY = b"dnf45as45fs1ace1"
CFG_IV = b"dn5as4fs1ac5f4e1"
SALT = "m4n2hjPeYWkD6tFpqKF^3HO^h24P@idT"
APP_VER = "1.6.0"
UA_DEFAULT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
UA_MEDIA = "Dart/3.4 (dart:io)"
LINES = ["http://198.44.248.101:9672", "http://198.44.248.102:9672",
         "http://122.10.20.249:9672"]
APIS = ["https://api.em1oifd0.com", "https://api.3459381.com", "https://api.61c76a0.com",
        "https://api.87735d5.com", "https://api.c6dd5cc.com", "https://api.j7y675.com",
        "https://api.2b37894.com", "https://api.35a46dd.com", "https://api.43b8477.com",
        "https://api.5ce3771.com", "https://api.632d809.com"]
IMG_FB = "https://imgpw807.s7n7ue8.com"  # flutter_img 明文域名兜底
VIDEO_FB = "https://46e9nz.mfpt8g.com"
PREVIEW_KEYS = ("preview", "trailer", "sample", "_pv.", "pv_")
CLASSES = [("6_3", "国产"), ("6_2", "日本"), ("6_1", "欧美"), ("6_5", "新作"),
           ("3_3", "4K独播"), ("6_4", "直播"), ("manga", "漫画"), ("album", "写真")]


def _b64d(s):
    s = (s or "").strip()
    s += "=" * (-len(s) % 4)
    try:
        return base64.b64decode(s)
    except Exception:
        return base64.urlsafe_b64decode(s)


def _md5(s):
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def _q(s):
    return urllib.parse.quote(str(s), safe="-_.~")


def _clip(n, s):
    s = (s or "").replace("$", " ").replace("#", " ").replace("\r", " ").replace("\n", " ").strip()
    return s[:n] if n > 0 else s


def _hijack(t):
    t = (t or "")[:600].lower()
    return "<html" in t or "hao123" in t or "gotob2" in t or ("<script" in t and "</html>" in t)


def _preview(m):
    if not m:
        return True
    if (m.get("video_download") or "").strip():
        return False
    vf = (m.get("video_file") or "").strip()
    pv = (m.get("preview_video") or "").strip()
    if not vf:
        return bool(pv)
    if pv and pv == vf:
        return True
    low = vf.lower()
    return any(k in low for k in PREVIEW_KEYS)


class Spider(_BaseSpider):
    def __init__(self):
        self.ext = {}
        self.token = ""
        self.base = ""
        self.domains = {}
        self.uuid = ""
        self.userkey = ""
        self.ready = False
        self._lock = threading.Lock()
        self._cache = {}
        self._bad = set()

    # ---------------- 壳子入口 ----------------
    def getName(self):
        return "一点播"

    def init(self, extend=""):
        if isinstance(extend, dict):
            self.ext = dict((str(k), str(v)) for k, v in extend.items())
        else:
            self.ext = {}
            for kv in re.split(r"[&\n;]+", extend or ""):
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    self.ext[k.strip()] = v.strip()
        self.uuid = self._e("uuid") or self._gen_uuid()
        self.userkey = self._e("userkey") or self._e("user_key") or self._gen_userkey()
        self.token = self._e("token")
        self.base = self._e("api")
        self.ready = False

    def destroy(self):
        self._cache = {}

    def isVideoFormat(self, url):
        return bool(url) and (".m3u8" in url or ".mp4" in url)

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        # 图片/视频均为公网直链，壳子直连即可
        return [404, "text/plain", "", {}]

    # ---------------- TVBox 接口 ----------------
    def homeContent(self, filter=False):
        out = {"class": [{"type_id": t, "type_name": n} for t, n in CLASSES], "filters": {}}
        return json.dumps(out, ensure_ascii=False)

    def homeVideoContent(self):
        try:
            self._boot()
            rows = self._discovery(6, 5, 1, size=20)
            return json.dumps({"list": [x for x in (self._vod(r) for r in rows) if x]},
                              ensure_ascii=False)
        except Exception:
            return json.dumps({"list": []}, ensure_ascii=False)

    def categoryContent(self, tid, pg, filter=False, extend=None):
        try:
            self._boot()
            tid = (tid or "6_3").strip()
            try:
                page = max(1, int(str(pg).strip()))
            except Exception:
                page = 1
            if tid in ("manga", "album"):
                path = "v2.5/series/manga/list" if tid == "manga" else "v2.5/series/album/list"
                data = self._call(path, {"page": page, "size": 20}, 300).get("data") or []
                lst = [self._vod_s(tid, r) for r in data if r.get("id")]
                return json.dumps({"page": page, "pagecount": page + 1 if len(lst) >= 20 else page,
                                   "limit": 20, "total": len(lst), "list": lst},
                                  ensure_ascii=False)
            model, tag = (tid.split("_") + ["0"])[:2] if "_" in tid else ("6", tid)
            rows = self._category(int(model or 0), int(tag or 0), page)
            lst, seen = [], set()
            for r in rows:
                rid = str(r.get("id") or "")
                if rid and rid not in seen:
                    seen.add(rid)
                    v = self._vod(r)
                    if v:
                        lst.append(v)
            return json.dumps({"page": page, "pagecount": page + 1 if len(rows) >= 20 else page,
                               "limit": 20, "total": len(lst), "list": lst},
                              ensure_ascii=False)
        except Exception as e:
            return json.dumps({"page": 1, "pagecount": 1, "limit": 20, "total": 1,
                               "list": [self._diag("列表拉取失败", "%s %s" % (type(e).__name__, e),
                                                   "ext 可填 line= 换引导线路")]},
                              ensure_ascii=False)

    def detailContent(self, ids):
        try:
            self._boot()
            raw = str((ids or [""])[0] if isinstance(ids, (list, tuple)) else (ids or "")).strip()
            prefix = ""
            if raw[:2] in ("m:", "a:"):
                prefix, raw = raw[0], raw[2:]
            if not raw.isdigit():
                return json.dumps({"list": [self._diag("详情参数不对", "id=" + raw,
                                                       "换个条目再点一次")]}, ensure_ascii=False)
            aid = int(raw)
            if prefix:
                return json.dumps(self._series_detail(aid, prefix), ensure_ascii=False)
            art = self._call("v2.5/article/detail", {"id": aid}, 900).get("data") or {}
            vod = self._vod(art) or {}
            vod["vod_id"] = str(aid)
            vod["vod_director"] = "小迷弟的小弟"
            if not vod.get("vod_content"):
                vod["vod_content"] = self._plain(art.get("content"), 500)
            src = self._play_sources(art)
            sid = str(art.get("series_id") or "").strip()
            if not src and sid.isdigit() and sid != "0":
                return json.dumps(self._series_detail(int(sid), "a"), ensure_ascii=False)
            froms, urls = [], []
            if src:
                froms.append("One")
                urls.append("#".join("%s$%s" % (lab, u) for lab, u, _ in src))
            pics = self._pics(art)
            if pics:
                froms.append("图集")
                urls.append("图集$pics://" + "&&".join(pics))
            if not froms:
                vod["vod_remarks"] = "预览" if _preview(art) else "无视频源"
            vod["vod_play_from"] = "$$$".join(froms)
            vod["vod_play_url"] = "$$$".join(urls)
            return json.dumps({"list": [vod]}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"list": [self._diag("详情请求失败",
                                                   "%s %s" % (type(e).__name__, e),
                                                   "换个分类再点一次")]}, ensure_ascii=False)

    def searchContent(self, key, quick=False, pg="1"):
        try:
            self._boot()
            try:
                page = max(1, int(str(pg).strip()))
            except Exception:
                page = 1
            data = self._call("v2.5/article/search",
                              {"keyword": key or "", "page": page, "size": 20}, 180).get("data") or []
            lst, seen = [], set()
            for r in data:
                rid = str(r.get("id") or "")
                if rid and rid not in seen:
                    seen.add(rid)
                    v = self._vod(r)
                    if v:
                        lst.append(v)
            return json.dumps({"list": lst, "page": page,
                               "pagecount": page + 1 if len(lst) >= 20 else page,
                               "limit": 20, "total": len(lst)}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"list": [self._diag("搜索失败", "%s %s" % (type(e).__name__, e),
                                                   "换个关键词")]}, ensure_ascii=False)

    def playerContent(self, flag, pid, vipFlags=None):
        head = self._play_header()
        try:
            self._boot()
            pid = (pid or "").strip()
            if pid.startswith("pics://"):
                return json.dumps({"parse": 0, "playUrl": "", "url": pid, "header": {}},
                                  ensure_ascii=False)
            if pid.startswith("http://") or pid.startswith("https://"):
                return json.dumps({"parse": 0, "playUrl": "", "url": pid, "header": head},
                                  ensure_ascii=False)
            sid = pid.split("$")[-1]
            if sid[:2] in ("m:", "a:"):
                sid = sid[2:]
            if not sid.isdigit():
                return json.dumps({"parse": 0, "playUrl": "", "url": "", "header": {},
                                   "error": "无法识别的播放 id"}, ensure_ascii=False)
            art = self._call("v2.5/article/detail", {"id": int(sid)}, 900).get("data") or {}
            src = self._play_sources(art)
            if src:
                return json.dumps({"parse": 0, "playUrl": "", "url": src[0][1], "header": head},
                                  ensure_ascii=False)
            pics = self._pics(art)
            if pics:
                return json.dumps({"parse": 0, "playUrl": "", "url": "pics://" + "&&".join(pics),
                                   "header": head}, ensure_ascii=False)
            return json.dumps({"parse": 0, "playUrl": "", "url": "", "header": {},
                               "error": "该条目没有可播放的正片"}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"parse": 0, "playUrl": "", "url": "", "header": {},
                               "error": "%s %s" % (type(e).__name__, e)}, ensure_ascii=False)

    # ---------------- 内部：ext / 身份 ----------------
    def _e(self, k, d=""):
        v = self.ext.get(k)
        return (v if v else d)

    @staticmethod
    def _gen_uuid():
        h = "".join(random.choice("0123456789abcdef") for _ in range(32))
        return "%s-%s-4%s-a%s-%s" % (h[:8], h[8:12], h[13:16], h[17:20], h[20:32])

    @staticmethod
    def _gen_userkey():
        return "".join(random.choice("0123456789abcdef") for _ in range(16))

    def _headers(self, token=None):
        ts = str(int(time.time()))
        sign = _md5(_md5("0.0.0.0.3.%s.%s.%s" % (ts, self.userkey, self.uuid)) + SALT)
        return {"User-Agent": self._e("ua", UA_DEFAULT), "Accept": "*/*",
                "Content-Type": "application/x-www-form-urlencoded",
                "ip": "0.0.0.0", "uuid": self.uuid, "timestamp": ts, "platform": "3",
                "token": self.token if token is None else token, "sign": sign,
                "user-key": self.userkey, "app-version": APP_VER}

    # ---------------- 内部：网络 ----------------
    def _post(self, url, body=b"", hdrs=None, timeout=15):
        req = urllib.request.Request(url, data=body, headers=hdrs or {}, method="POST")
        ctx = ssl._create_unverified_context()
        kw = {"timeout": timeout}
        try:
            kw["context"] = ctx
            resp = urllib.request.urlopen(req, **kw)
        except TypeError:
            resp = urllib.request.urlopen(req, timeout=timeout)
        try:
            return resp.getcode(), resp.read()
        finally:
            resp.close()

    def _boot(self):
        if self.ready:
            return
        with self._lock:
            if self.ready:
                return
            err = None
            for host in ([self.base] if self.base else []) + APIS:
                try:
                    code, raw = self._post(host.rstrip("/") + "/v2.5/bootstrap", b"",
                                           self._headers(token=""))
                    if code >= 400 or not raw:
                        continue
                    txt = raw.decode("utf-8", "replace").strip()
                    obj = json.loads(txt) if txt.startswith("{") else \
                        json.loads(cbc_decrypt(_b64d(txt), BODY_KEY, BODY_IV).decode("utf-8"))
                    if str(obj.get("code")) != "200":
                        err = "%s %s %s" % (host, obj.get("code"), obj.get("message"))
                        continue
                    data = obj.get("data") or {}
                    tok = ((data.get("user") or {}).get("token") or "")
                    if not tok:
                        err = host + " no token"
                        continue
                    self.token = tok
                    self.base = host.rstrip("/") + "/"
                    self.domains = data.get("domain") or {}
                    self.ready = True
                    return
                except Exception as e:
                    err = "%s %s" % (host, e)
            for line in ([self._e("line")] if self._e("line") else []) + LINES:
                try:
                    cfg = json.loads(zlib.decompress(cbc_decrypt(
                        self._post(line.rstrip("/") + "/box/api/config?channel=Channel", b"",
                                   {"Content-Type": "application/x-www-form-urlencoded",
                                    "User-Agent": UA_DEFAULT})[1], CFG_KEY, CFG_IV)))
                    data = cfg.get("data") or {}
                    tok = ""
                    for t in (data.get("token") or []):
                        if t.get("name") == "token_one":
                            tok = t.get("token") or ""
                            break
                    if not tok:
                        err = line + " 无 token_one"
                        continue
                    self.token = tok
                    self.base = line.rstrip("/") + "/"
                    self.domains = data.get("domain") or {}
                    self.ready = True
                    return
                except Exception as e:
                    err = "%s %s" % (line, e)
            raise RuntimeError("初始化失败: " + str(err))

    def _call(self, path, params=None, ttl=900):
        self._boot()
        params = dict((k, v) for k, v in (params or {}).items() if v not in (None, ""))
        ck = path + "|" + "&".join("%s=%s" % (k, params[k]) for k in sorted(params))
        if ttl > 0 and ck in self._cache and time.time() - self._cache[ck][0] < ttl:
            return self._cache[ck][1]
        body = b""
        if params:
            body = base64.b64encode(cbc_encrypt(
                "&".join("%s=%s" % (_q(k), _q(v)) for k, v in params.items()).encode("utf-8"),
                BODY_KEY, BODY_IV))
        hosts, seen, last = [self.base] + [a.rstrip("/") + "/" for a in APIS], set(), None
        for host in hosts:
            if not host or host in seen or host in self._bad:
                continue
            seen.add(host)
            try:
                code, raw = self._post(host.rstrip("/") + "/" + path.lstrip("/"), body,
                                       self._headers())
                txt = raw.decode("utf-8", "replace").strip()
                if code >= 400:
                    raise RuntimeError("HTTP %s" % code)
                if _hijack(txt):
                    self._bad.add(host)
                    raise RuntimeError("host 被劫持")
                if txt.startswith("{"):
                    obj = json.loads(txt)
                else:
                    ct = _b64d(txt)
                    if len(ct) % 16:
                        raise RuntimeError("响应非 16 字节对齐")
                    obj = json.loads(cbc_decrypt(ct, BODY_KEY, BODY_IV).decode("utf-8"))
                if str(obj.get("code")) in ("0", "200"):
                    self.base = host.rstrip("/") + "/"
                    if ttl > 0:
                        self._cache[ck] = (time.time(), obj)
                    return obj
                if str(obj.get("code")) == "401" or "expired" in str(obj.get("message", "")).lower():
                    self.ready = False
                    self.token = ""
                    raise RuntimeError("凭证已过期(Expired token)")
                raise RuntimeError("服务端 %s: %s" % (obj.get("code"), obj.get("message")))
            except Exception as e:
                last = e
        raise RuntimeError("request 失败: %s" % last)

    # ---------------- 内部：域名/字段 ----------------
    def _dom(self, kind, fb):
        lst = self.domains.get(kind) or []
        if isinstance(lst, str):
            lst = [lst]
        return lst[0].rstrip("/") if lst else fb

    def _img_dom(self):
        # 只走明文图片域名：image/flutter_enc_img 返回加密字节（大小恒为
        # 16 倍数），壳子无法显示；flutter_img/resource 返回正常图片。
        host = self._e("imghost")
        if host:
            return host.rstrip("/")
        for kind in ("flutter_img", "resource"):
            lst = self.domains.get(kind) or []
            if isinstance(lst, str):
                lst = [lst]
            if lst:
                return lst[0].rstrip("/")
        return IMG_FB

    def _img(self, u):
        u = (u or "").strip()
        if not u:
            return ""
        if u.startswith("http"):
            try:
                enc = set()
                for kind in ("image", "flutter_enc_img"):
                    lst = self.domains.get(kind) or []
                    if isinstance(lst, str):
                        lst = [lst]
                    for d in lst:
                        enc.add(urllib.parse.urlparse(d).netloc)
                if urllib.parse.urlparse(u).netloc in enc:
                    plain = urllib.parse.urlparse(self._img_dom())
                    u = urllib.parse.urlunparse(urllib.parse.urlparse(u)._replace(
                        scheme=plain.scheme or "https", netloc=plain.netloc))
            except Exception:
                pass
            return u
        return self._img_dom() + "/" + u.lstrip("/")

    def _media(self, u, kind="video"):
        u = (u or "").strip()
        if not u:
            return ""
        if u.startswith("http"):
            return u
        return self._dom(kind, VIDEO_FB) + "/" + u.lstrip("/")

    def _play_header(self):
        h = {"User-Agent": self._e("mediaua", UA_MEDIA)}
        if self._e("playref") == "1":
            b = self._dom("api", self.base or "https://api.em1oifd0.com").rstrip("/")
            h["Referer"] = b
            h["Origin"] = b
        return h

    @staticmethod
    def _plain(html, limit=500):
        t = re.sub(r"<[^>]+>", " ", html or "")
        return re.sub(r"\s+", " ", t).strip()[:limit]

    def _discovery(self, model, tag, page, published_at=None, size=20):
        if not published_at:
            t = time.localtime()
            published_at = "%04d-%02d" % (t.tm_year, t.tm_mon)
        return self._call("v2.5/article/discovery", {
            "model_id": model, "demand_tag_id": tag, "page": page,
            "published_at": published_at, "size": size, "sort": "published_at"}, 900).get("data") or []

    def _month(self, back):
        t = time.localtime()
        y, m = t.tm_year, t.tm_mon - back
        while m <= 0:
            m += 12
            y -= 1
        return "%04d-%02d" % (y, m)

    def _category(self, model, tag, page):
        try:
            months = max(0, int(self._e("months", "12")))
        except Exception:
            months = 12
        off, empty = (max(1, page) - 1) * 20, 0
        for k in range(months):
            try:
                rows = self._discovery(model, tag, 1, self._month(k), 100)
            except Exception:
                if k == 0:
                    raise
                continue
            if not rows:
                empty += 1
                if k > 0 and empty >= 3:
                    return []
                continue
            if off < len(rows):
                return rows[off:off + 20]
            off -= len(rows)
            empty = 0
        return []

    def _series_detail(self, sid, kind):
        data = self._call("v2.5/series/chapters", {"series_id": sid}, 900).get("data") or {}
        chs = data.get("chapters") or []
        parts, seen = [], set()
        for c in chs:
            cid = str(c.get("id") or "")
            if not cid or cid in seen:
                continue
            seen.add(cid)
            title = c.get("title") or ("第%s话" % c.get("chapter"))
            parts.append("%s$%s" % (_clip(40, title), cid))
            for lab, uv, _ in self._play_sources(c)[:3]:
                parts.append("%s %s$%s" % (_clip(30, title), lab, uv))
        vod = {"vod_id": str(sid), "vod_name": _clip(80, data.get("title")),
               "vod_pic": self._img(data.get("thumb")), "vod_year": _clip(4, data.get("first_at")),
               "vod_area": "", "vod_class": "", "vod_director": "",
               "vod_actor": _clip(40, data.get("author")),
               "vod_content": _clip(0, data.get("description")) or self._plain(data.get("content")),
               "vod_remarks": "共%d话" % len(chs),
               "vod_play_from": "漫画" if kind == "m" else "写真",
               "vod_play_url": "#".join(parts)}
        return {"list": [vod]}

    def _play_sources(self, art):
        out, prev = [], _preview(art)
        vd = (art.get("video_download") or "").strip()
        vf = (art.get("video_file") or "").strip()
        if vd:
            out.append(("完整片", self._media(vd), "完整版 MP4"))
        if vf and vf != vd:
            out.append(("预告" if prev else "正片", self._media(vf),
                        "预告片（非完整版）" if prev else "MP4"))
        if not out or prev:
            for k, lab in (("video_hls", "HLS 备用"), ("video_hls_h265", "HLS H265 备用")):
                u = (art.get(k) or "").strip()
                if u:
                    out.append((lab, self._media(u, "video_hls"), "加密清单"))
        af = (art.get("audio_file") or "").strip()
        if af:
            out.append(("音频", self._media(af, "audio"), "音频"))
        if not out:
            pv = (art.get("preview_video") or "").strip()
            if pv:
                out.append(("预览", self._media(pv), "预览片段"))
        seen, uniq = set(), []
        for x in out:
            if x[1] and x[1] not in seen:
                seen.add(x[1])
                uniq.append(x)
        return uniq

    def _pics(self, art):
        urls = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']',
                          art.get("content") or art.get("description") or "")
        if not urls:
            for k in ("multiple_pic", "multi_pic_thumbnail800", "multi_pic_thumbnail"):
                v = art.get(k)
                if isinstance(v, list) and v:
                    urls = [str(x) for x in v]
                    break
                if isinstance(v, str) and v.startswith("["):
                    urls = re.findall(r'["\']([^"\']*)["\']', v)
                    break
        out = []
        for u in urls:
            u = self._img(u)
            if u and u not in out:
                out.append(u)
        return out

    def _vod(self, m):
        if not m or m.get("id") is None:
            return None
        length = _clip(20, m.get("video_length"))
        if not length and _preview(m) and ((m.get("preview_video") or "").strip()
                                           or (m.get("video_file") or "").strip()):
            length = "预告"
        return {"vod_id": str(m.get("id")), "vod_name": _clip(80, m.get("title")),
                "vod_pic": self._img(m.get("thumb") or m.get("thumbnail")),
                "vod_remarks": length, "vod_year": _clip(4, m.get("published_at")),
                "vod_content": _clip(0, m.get("description")),
                "vod_play_from": "One", "vod_play_url": "正片$%s" % m.get("id")}

    def _vod_s(self, kind, m):
        vid = ("m:" if kind == "manga" else "a:") + str(m.get("id"))
        return {"vod_id": vid, "vod_name": _clip(80, m.get("title")),
                "vod_pic": self._img(m.get("thumb") or m.get("thumbnail")),
                "vod_remarks": _clip(10, m.get("latest_at")),
                "vod_year": _clip(4, m.get("first_at")),
                "vod_content": "作者: " + _clip(40, m.get("author")),
                "vod_play_from": "漫画" if kind == "manga" else "写真",
                "vod_play_url": "全篇$" + vid}

    @staticmethod
    def _diag(name, why, tips):
        return {"vod_id": "diag", "vod_name": "【诊断】" + _clip(40, name), "vod_pic": "",
                "vod_remarks": "看简介", "vod_year": "",
                "vod_content": "▸ %s\n\n原因：%s\n\n%s" % (_clip(120, name), _clip(200, why), tips),
                "vod_play_from": "", "vod_play_url": ""}
