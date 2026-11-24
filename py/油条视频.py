# -*- coding: utf-8 -*-
# TG交流群 https://t.me/hshsjk9

import re, json, base64, hashlib, os, random, sys
from urllib.parse import quote, unquote
sys.path.append('..')
try:
    from base.spider import Spider as _BSpider
except ImportError:
    class _BSpider(object):
        def getProxyUrl(self, local=True):
            return 'http://127.0.0.1:9978/proxy?do=py'
CATS = [("10", "国产自拍"), ("33", "抖音视频"), ("35", "网红头条"), ("36", "网爆黑料"),
        ("9", "美女主播"), ("2", "麻豆传媒"), ("4", "三级伦理"),
        ("1", "无码专区"), ("3", "制服诱惑"), ("13", "女同性爱"), ("14", "多人群交"),
        ("38", "女优明星"), ("11", "熟女人妻"), ("12", "萝莉少女"), ("15", "美乳巨乳"),
        ("8", "欧美系列"), ("37", "欧美无码"), ("7", "卡通动漫"),
        ("16", "强奸乱伦"), ("6", "中文字幕"), ("5", "AI换脸"), ("39", "SM调教"), ("40", "AV解说"), ("34", "韩国主播")]
try:
    import requests as _requests
except Exception:
    _requests = None
_SBOX = [
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
0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16]
_RCON = [0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x80,0x1b,0x36,0x6c,0xd8,0xab,0x4d]
def _xtime(a):
    a &= 0xff
    return ((a << 1) ^ 0x1b) & 0xff if a & 0x80 else (a << 1) & 0xff
def _mul(a, b):
    r = 0
    while b:
        if b & 1:
            r ^= a
        a = _xtime(a)
        b >>= 1
    return r
def _expand(key):
    nk = len(key) // 4
    nr = nk + 6
    w = [list(key[i*4:(i+1)*4]) for i in range(nk)]
    for i in range(nk, 4 * (nr + 1)):
        t = list(w[i-1])
        if i % nk == 0:
            t = [_SBOX[t[1]] ^ _RCON[i//nk - 1], _SBOX[t[2]], _SBOX[t[3]], _SBOX[t[0]]]
        elif nk > 6 and i % nk == 4:
            t = [_SBOX[c] for c in t]
        w.append([w[i-nk][j] ^ t[j] for j in range(4)])
    return w, nr
def _enc_block(block, w, nr):
    s = [[block[4*c+r] for c in range(4)] for r in range(4)]
    def _addrk(rnd):
        for c in range(4):
            for r in range(4):
                s[r][c] ^= w[rnd*4+c][r]
    def _sub():
        for r in range(4):
            for c in range(4):
                s[r][c] = _SBOX[s[r][c]]
    def _shift():
        for r in range(1, 4):
            s[r] = s[r][r:] + s[r][:r]
    def _mix():
        for c in range(4):
            a = [s[r][c] for r in range(4)]
            s[0][c] = _mul(a[0],2) ^ _mul(a[1],3) ^ a[2] ^ a[3]
            s[1][c] = a[0] ^ _mul(a[1],2) ^ _mul(a[2],3) ^ a[3]
            s[2][c] = a[0] ^ a[1] ^ _mul(a[2],2) ^ _mul(a[3],3)
            s[3][c] = _mul(a[0],3) ^ a[1] ^ a[2] ^ _mul(a[3],2)
    _addrk(0)
    for rnd in range(1, nr):
        _sub(); _shift(); _mix(); _addrk(rnd)
    _sub(); _shift(); _addrk(nr)
    return bytes(s[r][c] for c in range(4) for r in range(4))
def _aes_ctr(data, key, iv):
    w, nr = _expand(key)
    out = bytearray()
    ctr = bytearray(iv)
    for off in range(0, len(data), 16):
        ks = _enc_block(bytes(ctr), w, nr)
        chunk = data[off:off+16]
        out.extend(bytes(b ^ ks[i] for i, b in enumerate(chunk)))
        for i in range(15, -1, -1):
            ctr[i] = (ctr[i] + 1) & 0xff
            if ctr[i]:
                break
    return bytes(out)


class Spider(_BSpider):
    def __init__(self):
        self.site = "https://www.yt8x1.top"
        self.name = "油条视频"
        self.header = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-S9080) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.site + "/index",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept": "application/json, text/html, */*",
        }
        self.s = self.session = self.sess = _requests.Session() if _requests else None
        self._extend = {}
        self._aes_key = None
        self._appjs = None
        self._device_id = None
        self._home = None
        self._groups = [
            ("folder:cn", "国产", [("10", "国产自拍"), ("2", "麻豆传媒"), ("33", "抖音视频"), ("35", "网红头条"), ("36", "网爆黑料"), ("9", "美女主播"), ("4", "三级伦理")]),
            ("folder:jp", "日韩", [("1", "无码专区"), ("38", "女优明星"), ("3", "制服诱惑"), ("11", "熟女人妻"), ("12", "萝莉少女"), ("13", "女同性爱"), ("14", "多人群交"), ("15", "美乳巨乳")]),
            ("folder:eu", "外文", [("8", "欧美系列"), ("37", "欧美无码")]),
            ("folder:dm", "动漫", [("7", "卡通动漫")]),
            ("folder:zh", "综合", [("34", "韩国主播"), ("5", "AI换脸"), ("39", "SM调教"), ("40", "AV解说"), ("16", "强奸乱伦"), ("6", "中文字幕")]),
        ]
        self._icon = {"folder:cn": "📁国产", "folder:jp": "📁日韩", "folder:eu": "📁外文",
                      "folder:dm": "📁动漫", "folder:zh": "📁综合"}
        self._cpic = {}
        self._fmap = {}
        for gid, gname, subs in self._groups:
            self._fmap[gid] = subs
        self._ALL = CATS

    def getDependence(self):
        return []

    def manualVideoCheck(self):
        return False

    def getName(self):
        return self.name

    def isVideoFormat(self, url):
        if not url:
            return False
        u = str(url).lower()
        return u.endswith((".m3u8", ".mp4", ".flv", ".mkv", ".ts", ".avi")) or "m3u8" in u

    def destroy(self):
        pass

    def action(self, action):
        return {}

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

    def _http_get(self, url):
        h = dict(self.header)
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

    def _http_post(self, url, body):
        h = dict(self.header)
        h["Content-Type"] = "application/json;charset=utf-8"
        if self.s is not None:
            try:
                r = self.s.post(url, data=body.encode("utf-8"), headers=h, timeout=15)
                if r.status_code < 400:
                    if not r.encoding or r.encoding.lower() in ("iso-8859-1", "ascii"):
                        r.encoding = "utf-8"
                    return r.text
            except Exception:
                pass
        try:
            import urllib.request
            req = urllib.request.Request(url, data=body.encode("utf-8"), headers=h)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read().decode("utf-8", "ignore")
        except Exception:
            return ""

    def _device(self):
        if not self._device_id:
            self._device_id = hashlib.md5(os.urandom(16)).hexdigest()
        return self._device_id

    def _key(self):
        if self._aes_key:
            return self._aes_key
        if self._appjs is None:
            self._appjs = self._http_get(self.site + "/assets/app.js")
        js = self._appjs or ""
        if not js:
            return None
        varname = ""
        anchors = ["interceptors.response.use", "数据解密失败"]
        for anchor in anchors:
            idx = js.find(anchor)
            if idx < 0:
                continue
            seg = js[idx:idx+600] if anchor.startswith("interceptors") else js[max(0, idx-400):idx]
            m = re.search(r"([A-Za-z_$][\w$]*)\(\s*t\.data\s*,\s*([A-Za-z_$][\w$]*)\s*\)", seg)
            if m:
                varname = m.group(2)
                break
        if not varname:
            return None
        m = re.search(re.escape(varname) + r"\s*=\s*\"([^\"]{16,64})\"", js)
        if not m:
            return None
        self._aes_key = m.group(1).encode("utf-8")
        return self._aes_key

    def _enc(self, obj):
        key = self._key()
        if not key:
            return None
        iv = os.urandom(16)
        raw = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)
        ct = _aes_ctr(raw.encode("utf-8"), key, iv)
        return {"data": base64.b64encode(ct).decode(), "iv": base64.b64encode(iv).decode()}

    def _dec(self, resp):
        if not isinstance(resp, dict):
            return resp
        if "data" in resp and "iv" in resp:
            key = self._key()
            if not key:
                return resp
            try:
                plain = _aes_ctr(base64.b64decode(resp["data"]), key, base64.b64decode(resp["iv"]))
                return json.loads(plain.decode("utf-8"))
            except Exception:
                return resp
        return resp

    def _api_get(self, path):
        try:
            txt = self._http_get(self.site + path + "?lang=zh_cn")
            if not txt:
                return {}
            return self._dec(json.loads(txt))
        except Exception:
            return {}

    def _api_post(self, path, params):
        try:
            env = self._enc(params)
            if env is None:
                return {}
            txt = self._http_post(self.site + path + "?lang=zh_cn", json.dumps(env, ensure_ascii=False))
            if not txt:
                return {}
            return self._dec(json.loads(txt))
        except Exception:
            return {}

    def _dur(self, secs):
        try:
            secs = int(secs or 0)
        except Exception:
            secs = 0
        if secs <= 0:
            return ""
        return "%02d:%02d" % (secs // 60, secs % 60)

    def _item(self, v):
        # ★必加①(方法级) 大图四件套 style rect/1.78 + land + ratio + type_name
        if not isinstance(v, dict):
            return None
        vid = str(v.get("id", "") or "")
        if not vid:
            return None
        pic = v.get("coverUrl") or v.get("thumbnailUrl") or ""
        rem = self._dur(v.get("durationSecs")) or str(v.get("createdAt", "") or "")
        return {"vod_id": vid, "vod_name": str(v.get("title", "") or "").strip(), "vod_pic": self._u(pic), "vod_remarks": rem,
                "type_name": "油条视频", "style": {"type": "rect", "ratio": 1.78}, "land": 1, "ratio": 1.78}

    def _card(self, vid, name, rem, tname, pic=""):
        # ★必加①(方法级) 资料夹卡四件套 style/land/ratio/type_name + vod_tag=folder + 真实封面
        return {"vod_id": vid, "vod_name": name, "vod_pic": pic or "", "vod_remarks": rem, "vod_tag": "folder", "type_name": tname,
                "style": {"type": "rect", "ratio": 1.78}, "land": 1, "ratio": 1.78}

    def _items(self, arr):
        out = []
        seen = set()
        for v in arr or []:
            try:
                it = self._item(v)
            except Exception:
                continue
            if not it or it["vod_id"] in seen:
                continue
            seen.add(it["vod_id"])
            out.append(it)
        return out

    def _home_list(self):
        if self._home is not None:
            return self._home
        out = []
        try:
            res = self._api_get("/api/home")
            data = res.get("data") if isinstance(res, dict) else None
            secs = (data or {}).get("sections") or []
            for s in secs:
                if not isinstance(s, dict) or s.get("type") != "video_list":
                    continue
                out.extend(self._items(s.get("data") or []))
        except Exception:
            pass
        seen = set()
        ded = []
        for it in out:
            if it["vod_id"] in seen:
                continue
            seen.add(it["vod_id"])
            ded.append(it)
        self._home = ded
        return ded

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
        # ★必加②(方法级) 资料夹两级：一级 5 项（国产7/日韩8/外文2/动漫1/综合6），每资料夹在 filters 挂本组子分类 + 排序行
        # ★必检④(方法级) 分类覆盖度：5 入口 / 24 个真实分类 / 24 张分类卡（一级卡封面取本组首分类首片图）
        cats = [{"type_id": gid, "type_name": gname, "land": 1, "ratio": 1.78} for gid, gname, _ in self._groups]
        return {"class": cats, "filters": self._filters(), "list": self._home_list()}

    def homeVideoContent(self):
        # ★必加①(方法级) 首页推荐：/api/home 的 5 个 video_list section 去重合并（实测 40 条）
        return {"list": self._home_list()}

    def _filters(self):
        sorts = [{"n": "最新", "v": "created_at"}, {"n": "最多播放", "v": "views_count"}, {"n": "最多点赞", "v": "like_count"}]
        f = {}
        for gid, gname, subs in self._groups:
            vals = [{"n": "全部", "v": gid}]
            for sid, sname in subs:
                vals.append({"n": sname, "v": "c" + sid})
            f[gid] = [{"key": "filter", "name": "分类", "value": vals}, {"key": "sort", "name": "排序", "value": sorts}]
        return f

    def _cover(self, cid):
        # ★必加①(方法级) 一级资料夹卡封面：取该分类首片 coverUrl（CDN 明文 JPEG 无防盗链），命中 _cpic 直接复用
        cid = str(cid)
        if self._cpic.get(cid):
            return self._cpic[cid]
        pic = ""
        try:
            res = self._api_post("/api/category/list", {"categoryId": int(cid), "sortBy": "created_at", "sortOrder": "desc", "page": 1, "pageSize": 1})
            data = res.get("data") if isinstance(res, dict) else None
            lst = data.get("list") if isinstance(data, dict) else None
            if lst and isinstance(lst[0], dict):
                pic = self._u(lst[0].get("coverUrl") or lst[0].get("thumbnailUrl") or "")
        except Exception:
            pic = ""
        if pic:
            self._cpic[cid] = pic
        return pic
    def _fdir(self, tid):
        # ★必加②(方法级) 资料夹二级卡：vod_tag=folder + vod_id=c<分类id> + 封面并发取图（_cpic 缓存），不出占位/裂图
        subs = self._fmap.get(tid) or []
        nm = self._icon.get(tid, "资料夹")
        pics = {}
        if subs:
            try:
                from concurrent.futures import ThreadPoolExecutor
                with ThreadPoolExecutor(max_workers=min(8, len(subs))) as ex:
                    pics = dict(zip([s[0] for s in subs], list(ex.map(lambda s: self._cover(s[0]), subs))))
            except Exception:
                pics = {}
        cards = [self._card("c" + i, n, "进入分类", nm, pics.get(i, "")) for i, n in subs]
        return {"list": cards, "page": 1, "pagecount": 1, "limit": len(cards) or 24, "total": len(cards)}

    def _resolve_tid(self, tid, extend):
        tid = str(tid)
        ext = extend
        if isinstance(ext, str) and ext.strip():
            try:
                e = json.loads(ext)
                ext = e if isinstance(e, dict) else self._extend
            except Exception:
                ext = self._extend
        if not isinstance(ext, dict):
            ext = self._extend
        fl = str(ext.get("filter", "") or "").strip()
        if fl.startswith("c") and fl[1:].isdigit():
            return fl
        if fl in self._fmap:
            subs = self._fmap.get(fl) or []
            if subs:
                return "c" + subs[0][0]
        return tid

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        # ★必检①(方法级) 真分页 page/pagecount/limit/total（站点 data.total 为真值）
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1
        t = str(tid or "")
        ex = extend
        if isinstance(ex, str) and ex.strip():
            try:
                e = json.loads(ex)
                ex = e if isinstance(e, dict) else {}
            except Exception:
                ex = {}
        if not isinstance(ex, dict):
            ex = {}
        fl = str(ex.get("filter", "") or "").strip()
        if t.startswith("folder:") and not (fl[:1] == "c" and fl[1:].isdigit()):
            return self._fdir(t)
        t = self._resolve_tid(t, ex)
        sb = str(ex.get("sort", "") or "").strip()
        if sb not in ("created_at", "views_count", "like_count"):
            sb = "created_at"
        cid = t[1:] if t[:1] == "c" else t
        try:
            cidn = int(cid)
        except Exception:
            return {"list": [], "page": pg, "pagecount": pg, "limit": 24, "total": pg * 24}
        res = self._api_post("/api/category/list", {"categoryId": cidn, "sortBy": sb, "sortOrder": "desc", "page": pg, "pageSize": 24})
        data = res.get("data") if isinstance(res, dict) else None
        if not isinstance(data, dict) or res.get("code") != 1:
            return {"list": [], "page": pg, "pagecount": pg, "limit": 24, "total": pg * 24}
        lst = self._items(data.get("list") or [])
        try:
            total = int(data.get("total") or 0)
        except Exception:
            total = 0
        if total <= 0:
            total = len(lst)
        pc = (total + 23) // 24
        if pc < 1:
            pc = 1
        return {"list": lst, "page": pg, "pagecount": pc, "limit": 24, "total": total}

    def detailContent(self, ids):
        # ★必检②(方法级) 单线路细节：playerType=2 走 playerUrl 外链，否则直取 currentEpisode.playUrl
        vid = ids
        if isinstance(ids, (list, tuple)):
            vid = ids[0] if ids else ""
        vid = str(vid or "").strip()
        if ":" in vid:
            vid = vid.split(":")[0]
        if vid.startswith("folder:") or (vid[:1] == "c" and vid[1:].isdigit()):
            return {"list": []}
        try:
            vidn = int(vid)
        except Exception:
            return {"list": []}
        res = self._api_post("/api/video/detail", {"videoId": vidn, "episodeNo": 1, "deviceId": self._device()})
        data = res.get("data") if isinstance(res, dict) else None
        if not isinstance(data, dict) or res.get("code") != 1:
            return {"list": []}
        eps = data.get("episodes") or []
        if not eps:
            eps = [{"episodeNo": 1}]
        play = []
        for ep in eps:
            try:
                no = int(ep.get("episodeNo") or 1)
            except Exception:
                no = 1
            play.append("第%d集$%d:%d" % (no, vidn, no))
        cats = data.get("categories") or []
        cname = cats[0].get("name", "") if cats and isinstance(cats[0], dict) else ""
        return {"list": [{"vod_id": str(vidn), "vod_name": str(data.get("title", "") or "").strip(),
                          "vod_pic": self._u(data.get("coverUrl") or ""),
                          "vod_content": str(data.get("description", "") or "").strip(),
                          "vod_director": "", "vod_actor": "",
                          "vod_area": str(data.get("area", "") or ""),
                          "vod_year": str(data.get("year", "") or ""),
                          "type_name": cname,
                          "vod_play_from": self.name,
                          "vod_play_url": "#".join(play)}]}

    def searchContent(self, key, quick=False, pg="1"):
        # ★必加③(方法级) 搜索：关键词 quote() 归一（本站走 JSON body，编码后再 unquote 还原，特殊字符安全）
        key = unquote(quote(str(key or "").strip(), safe=""))
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1
        if not str(key or "").strip():
            return {"list": [], "page": pg, "pagecount": 1, "limit": 24, "total": 0}
        res = self._api_post("/api/search", {"keyword": str(key), "page": pg, "pageSize": 24})
        data = res.get("data") if isinstance(res, dict) else None
        if not isinstance(data, dict) or res.get("code") != 1:
            return {"list": [], "page": pg, "pagecount": pg, "limit": 24, "total": pg * 24}
        lst = self._items(data.get("list") or [])
        try:
            total = int(data.get("total") or 0)
        except Exception:
            total = 0
        if total <= 0:
            total = len(lst)
        pc = (total + 23) // 24
        if pc < 1:
            pc = 1
        return {"list": lst, "page": pg, "pagecount": pc, "limit": 24, "total": total}

    def playerContent(self, flag, ids, vipFlags=None):
        url = ids
        if isinstance(ids, (list, tuple)):
            url = ids[0] if ids else ""
        url = str(url or "").strip()
        if not url:
            return {"parse": 0, "url": "", "header": dict(self.header)}
        if url.startswith("http") and "m3u8" in url.lower():
            return {"parse": 0, "url": url, "header": dict(self.header)}
        vid = url
        epno = 1
        if ":" in vid:
            parts = vid.split(":")
            vid = parts[0]
            try:
                epno = int(parts[1])
            except Exception:
                epno = 1
        try:
            vidn = int(vid)
        except Exception:
            return {"parse": 0, "url": "", "header": dict(self.header)}
        res = self._api_post("/api/video/detail", {"videoId": vidn, "episodeNo": epno, "deviceId": self._device()})
        data = res.get("data") if isinstance(res, dict) else None
        if not isinstance(data, dict) or res.get("code") != 1:
            return {"parse": 0, "url": "", "header": dict(self.header)}
        cur = data.get("currentEpisode") or {}
        play = str(cur.get("playUrl", "") or "").strip()
        if not play:
            return {"parse": 0, "url": "", "header": dict(self.header)}
        if data.get("playerType") == 2:
            base = str(data.get("playerUrl", "") or "")
            return {"parse": 1, "url": self._u(base + play), "header": dict(self.header)}
        return {"parse": 0, "url": self._u(play), "header": dict(self.header)}

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
