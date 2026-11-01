# coding=utf-8
# //@name:鲍鱼盒子
# //@version:1.2
# //@desc: 逆向自 鲍鱼盒子_5.0.10 Flutter。HLS 为 AES-128，key.key 返回伪路径串（非标准16字节），
#         标准播放器可能仍无法解；本版展开主清单+代理改写相对 ts。个人研究用。

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider:
        def getName(self): return ""
        def init(self, extend=""): pass
        def homeContent(self, filter=None): return {}
        def homeVideoContent(self): return {}
        def categoryContent(self, tid, pg, filter=None, extend=None): return {}
        def detailContent(self, ids): return {}
        def searchContent(self, key, quick=False, pg="1"): return {}
        def playerContent(self, flag, id, vipFlags=None): return {}
        def localProxy(self, param): return [404, "text/plain", ""]
        def getDependence(self): return ""
        def isVideoFormat(self, url): return False
        def manualVideoCheck(self): return False


import re
import time
import json
import ssl
import uuid
import base64
import hashlib
import http.cookiejar
import urllib.request
import urllib.parse

_SKIP = ("萝莉", "幼女", "小学生", "儿童", "未成年", "幼幼", "女童", "小孩", "幼齿")


class Spider(BaseSpider):
    def getName(self):
        return "鲍鱼盒子"

    def init(self, extend=""):
        self.hosts = [
            "https://103.44.236.131:8001",
            "https://kk.zzijzn.com:8001",
        ]
        self.host = self.hosts[0]
        self.device = "byhz-" + uuid.uuid4().hex[:16]
        self.token = ""
        self.token_ts = 0
        self.ua = "Dart/3.5 (dart:io)"
        self._ctx = ssl._create_unverified_context()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=self._ctx),
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
        )
        if extend:
            try:
                ext = json.loads(extend) if isinstance(extend, str) else (extend or {})
                if isinstance(ext, dict):
                    if ext.get("host"):
                        self.host = str(ext["host"]).rstrip("/")
                    if ext.get("device"):
                        self.device = str(ext["device"])
            except Exception:
                pass
        self._login()

    def getDependence(self):
        return ""

    def _headers(self, auth=True):
        h = {
            "User-Agent": self.ua,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if auth and self.token:
            h["Authorization"] = "Bearer " + self.token
        return h

    def _req(self, method, path, data=None, auth=True, retry=2):
        if time.time() - self.token_ts > 86400:
            self._login()
        url = path if str(path).startswith("http") else (self.host + path)
        body = None
        if data is not None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        last = None
        for i in range(retry + 1):
            try:
                req = urllib.request.Request(url, data=body, headers=self._headers(auth), method=method)
                with self._opener.open(req, timeout=18) as resp:
                    raw = resp.read().decode("utf-8", "ignore")
                obj = json.loads(raw) if raw.strip()[:1] in "{[" else {}
                if obj.get("code") in (1009, 1035) and auth:
                    self._login()
                    continue
                return obj
            except Exception as e:
                last = e
                time.sleep(0.3 * (i + 1))
        return {"code": -1, "msg": str(last), "data": None}

    def _login(self):
        for h in [self.host] + [x for x in self.hosts if x != self.host]:
            try:
                self.host = h
                url = h + "/api/tourist_login"
                body = json.dumps({"source": "android", "device": self.device}).encode("utf-8")
                req = urllib.request.Request(
                    url, data=body,
                    headers={"User-Agent": self.ua, "Accept": "application/json", "Content-Type": "application/json"},
                    method="POST",
                )
                with self._opener.open(req, timeout=15) as resp:
                    raw = resp.read().decode("utf-8", "ignore")
                obj = json.loads(raw)
                if obj.get("code") == 200:
                    data = obj.get("data") or {}
                    self.token = data.get("access_token") or data.get("token") or ""
                    if self.token:
                        self.token_ts = time.time()
                        return True
            except Exception:
                continue
        self.token = ""
        return False

    @staticmethod
    def _bad(name):
        return any(k in (name or "") for k in _SKIP)

    @staticmethod
    def _fix_pic(url):
        if not url:
            return ""
        u = str(url).replace("\\/", "/").strip()
        u = re.sub(r"(https?://[^/]+)/+", r"\1/", u)
        if u.startswith("//"):
            u = "https:" + u
        elif u.startswith("/"):
            u = "https://yn7ux.ooat88.com" + u
        return u

    def _vod(self, it):
        if not isinstance(it, dict):
            return None
        vid = it.get("id") or it.get("vid") or it.get("video_id")
        name = it.get("name") or ""
        if not vid or self._bad(name):
            return None
        pic = self._fix_pic(it.get("cover") or it.get("vertical_cover") or it.get("img_url") or "")
        remarks = "VIP" if it.get("is_vip") else ""
        dur = it.get("duration")
        if dur and not remarks:
            try:
                m, s = divmod(int(dur), 60)
                remarks = "%d:%02d" % (m, s % 60) if m < 60 else "%d:%02d:%02d" % (m // 60, m % 60, s % 60)
            except Exception:
                pass
        return {
            "vod_id": str(vid),
            "vod_name": name,
            "vod_pic": pic,
            "vod_remarks": remarks or it.get("categor_name") or "",
        }

    def homeContent(self, filter=None):
        classes = [{"type_id": "rec", "type_name": "推荐"}]
        obj = self._req("GET", "/api/module/app_module")
        data = obj.get("data") or {}
        video = data.get("video") if isinstance(data, dict) else None
        if isinstance(video, dict):
            for ch in video.get("children") or []:
                cid, name = ch.get("id"), ch.get("name") or ""
                if cid is None or not name:
                    continue
                classes.append({"type_id": "c%s" % cid, "type_name": name})
        if isinstance(data, dict):
            for k, mod in data.items():
                if k == "video" or not isinstance(mod, dict):
                    continue
                code, name = mod.get("code") or k, mod.get("name") or k
                classes.append({"type_id": "m%s" % code, "type_name": name})
                for ch in mod.get("children") or []:
                    cid, cn = ch.get("id"), ch.get("name") or ""
                    if cid is None or not cn:
                        continue
                    classes.append({"type_id": "c%s" % cid, "type_name": "%s-%s" % (name, cn)})
        rec = self._req("GET", "/api/video/home_recommend?page=1&limit=24")
        videos, rows = [], []
        rd = rec.get("data")
        if isinstance(rd, list):
            for block in rd:
                if isinstance(block, dict) and isinstance(block.get("list"), list):
                    rows.extend(block["list"])
                elif isinstance(block, dict) and (block.get("vid") or block.get("id")):
                    rows.append(block)
        elif isinstance(rd, dict):
            rows = rd.get("list") or []
        for it in rows:
            v = self._vod(it)
            if v:
                videos.append(v)
        return {"class": classes, "filters": {}, "list": videos}

    def homeVideoContent(self):
        return {"list": (self.homeContent().get("list") or [])}

    def categoryContent(self, tid, pg, filter=None, extend=None):
        page = int(pg) if str(pg).isdigit() else 1
        tid = str(tid or "rec")
        videos, total = [], 0
        if tid in ("rec", "-200", "c-200"):
            obj = self._req("GET", "/api/video/home_recommend?page=%d&limit=20" % page)
            rd, rows = obj.get("data"), []
            if isinstance(rd, list):
                for block in rd:
                    if isinstance(block, dict) and isinstance(block.get("list"), list):
                        rows.extend(block["list"])
                    elif isinstance(block, dict):
                        rows.append(block)
            elif isinstance(rd, dict):
                rows = rd.get("list") or []
            for it in rows:
                v = self._vod(it)
                if v:
                    videos.append(v)
            total = page * 20 + (20 if videos else 0)
        elif tid.startswith("c"):
            obj = self._req("GET", "/api/category/category_video?category_id=%s&page=%d&limit=20" % (tid[1:], page))
            data = obj.get("data") or {}
            if isinstance(data, dict):
                total = int(data.get("count") or 0)
                for it in data.get("list") or []:
                    v = self._vod(it)
                    if v:
                        videos.append(v)
        else:
            obj = self._req("GET", "/api/video/home_recommend?page=%d&limit=20" % page)
            rd = obj.get("data")
            if isinstance(rd, list):
                for block in rd:
                    if isinstance(block, dict) and isinstance(block.get("list"), list):
                        for it in block["list"]:
                            v = self._vod(it)
                            if v:
                                videos.append(v)
        pagecount = max(1, (total + 19) // 20) if total else (page + 1 if len(videos) >= 15 else page)
        return {"list": videos, "page": page, "pagecount": pagecount, "limit": 20, "total": total or len(videos)}

    def detailContent(self, ids):
        vid = re.sub(r"\D", "", str(ids[0] if isinstance(ids, (list, tuple)) and ids else ids or ""))
        if not vid:
            return {"list": []}
        obj = self._req("GET", "/api/video/detail/%s" % vid)
        data = obj.get("data") or {}
        video = data.get("video") if isinstance(data, dict) else None
        if not isinstance(video, dict):
            return {"list": []}
        name = video.get("name") or ""
        if self._bad(name):
            return {"list": []}
        pic = self._fix_pic(video.get("cover") or video.get("vertical_cover") or "")
        content = video.get("brief") or ""
        tags = [t.get("name") for t in (video.get("interest_tags_text") or []) if isinstance(t, dict) and t.get("name")]
        cats = [c.get("name") for c in (video.get("categorys") or []) if isinstance(c, dict) and c.get("name")]
        area = (video.get("area") or {}).get("name") if isinstance(video.get("area"), dict) else ""
        links = video.get("link") or []
        play_from, play_url = [], []
        if isinstance(links, list):
            for i, lk in enumerate(links):
                if not isinstance(lk, dict):
                    continue
                flag = lk.get("tongdao_name") or lk.get("tongdao") or ("线路%d" % (i + 1))
                u = (lk.get("url") or lk.get("gaoqin") or "").replace("\\/", "/")
                if u:
                    play_from.append(flag)
                    play_url.append("正片$%s" % u)
        try_url = (video.get("try_play_url") or "").replace("\\/", "/")
        if try_url and not play_url:
            play_from.append("试看")
            play_url.append("试看$%s" % try_url)
        if not play_url:
            play_from, play_url = ["鲍鱼"], ["正片$%s" % vid]
        return {"list": [{
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content or name,
            "vod_remarks": "/".join(cats) or area,
            "vod_actor": video.get("actors") or "",
            "vod_area": area,
            "vod_tag": ",".join(tags),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    def searchContent(self, key, quick=False, pg="1"):
        key = (key or "").strip()
        if not key:
            return {"list": []}
        page = int(pg) if str(pg).isdigit() else 1
        q = urllib.parse.urlencode({"keyword": key, "page": page, "limit": 20})
        obj = self._req("GET", "/api/index/word_search?%s" % q)
        data = obj.get("data") or {}
        videos = []
        if isinstance(data, dict):
            for it in data.get("list") or []:
                v = self._vod(it)
                if v:
                    videos.append(v)
        return {
            "list": videos, "page": page,
            "pagecount": page + 1 if len(videos) >= 15 else page,
            "limit": 20,
            "total": int(data.get("count") or len(videos)) if isinstance(data, dict) else len(videos),
        }

    def _http_get(self, url, headers=None):
        h = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/131.0.0.0 Mobile Safari/537.36",
            "Referer": "https://sjjda3.ooat88.com/",
            "Origin": "https://sjjda3.ooat88.com",
        }
        if headers:
            h.update(headers)
        req = urllib.request.Request(url, headers=h)
        with self._opener.open(req, timeout=20) as resp:
            return resp.read(), dict(resp.headers)

    def _resolve_media_m3u8(self, url):
        try:
            raw, _ = self._http_get(url)
            text = raw.decode("utf-8", "ignore")
        except Exception:
            return url
        if "#EXT-X-STREAM-INF" not in text:
            return url
        base = url.rsplit("/", 1)[0] + "/"
        best = None
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if not line.startswith("#EXT-X-STREAM-INF"):
                continue
            for j in range(i + 1, min(i + 5, len(lines))):
                u = lines[j].strip()
                if u and not u.startswith("#"):
                    best = u if u.startswith("http") else urllib.parse.urljoin(base, u)
                    break
        return best or url

    def _rewrite_m3u8(self, text, base_url):
        base = base_url.rsplit("/", 1)[0] + "/"
        out = []
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("#EXT-X-KEY"):
                m = re.search(r'URI="([^"]+)"', s)
                if m:
                    uri = m.group(1)
                    if not uri.startswith("http"):
                        uri = urllib.parse.urljoin(base, uri)
                    b64 = base64.b64encode(uri.encode("utf-8")).decode("ascii")
                    s = re.sub(r'URI="[^"]+"', 'URI="proxy://key&url=%s"' % b64, s)
                out.append(s)
            elif s and not s.startswith("#"):
                out.append(s if s.startswith("http") else urllib.parse.urljoin(base, s))
            else:
                out.append(line)
        return "\n".join(out) + "\n"

    def playerContent(self, flag, id, vipFlags=None):
        url = str(id or "").strip()
        if "$" in url and not url.startswith("http"):
            url = url.split("$", 1)[1].strip()
        header = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
            "Referer": "https://sjjda3.ooat88.com/",
            "Origin": "https://sjjda3.ooat88.com",
            "Accept": "*/*",
        }
        if re.match(r"^\d+$", url):
            d = self.detailContent([url])
            vod = (d.get("list") or [{}])[0]
            pu = (vod.get("vod_play_url") or "").split("$$$")[0]
            if "$" in pu:
                url = pu.split("$", 1)[1]
        if url.startswith("http") and (".m3u8" in url.lower() or "/hls" in url.lower() or "/video/" in url):
            media = self._resolve_media_m3u8(url)
            b64 = base64.b64encode(media.encode("utf-8")).decode("ascii")
            # 同时给直链兜底（部分壳不走 proxy）
            return {
                "parse": 0,
                "jx": 0,
                "url": media,
                "header": header,
                "extra": {"proxy": "proxy://m3u8&url=" + b64},
            }
        if url.startswith("http"):
            return {"parse": 0, "jx": 0, "url": url, "header": header}
        return {"parse": 0, "jx": 0, "url": "", "msg": "无播放地址"}

    def isVideoFormat(self, url):
        u = str(url or "").lower()
        return any(x in u for x in (".m3u8", ".mp4", "/video/", "/hls/"))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        try:
            ptype = str(param.get("type") or param.get("name") or "")
            raw = param.get("url") or param.get("path") or ""
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", "ignore")
            raw = urllib.parse.unquote(str(raw))
            if not raw.startswith("http"):
                try:
                    raw = base64.b64decode(raw).decode("utf-8", "ignore")
                except Exception:
                    pass
            if not raw.startswith("http") and isinstance(param, dict):
                for k, v in param.items():
                    sv = str(v)
                    if sv.startswith("http"):
                        raw = sv
                        break
                    if k == "url":
                        try:
                            raw = base64.b64decode(sv).decode("utf-8", "ignore")
                        except Exception:
                            pass
            headers = {
                "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/131.0.0.0 Mobile Safari/537.36",
                "Referer": "https://sjjda3.ooat88.com/",
            }
            if "key" in ptype or raw.endswith("key.key") or "/key.key" in raw:
                body, _ = self._http_get(raw, headers)
                if len(body) == 16:
                    return [200, "application/octet-stream", body]
                # 伪 key（路径串）— 标准播放器仍可能失败；返回 md5 兜底
                if body and (body[:1] == b"/" or len(body) != 16):
                    return [200, "application/octet-stream", hashlib.md5(body).digest()]
                return [200, "application/octet-stream", body]
            body, _ = self._http_get(raw, headers)
            text = self._rewrite_m3u8(body.decode("utf-8", "ignore"), raw)
            return [200, "application/vnd.apple.mpegurl", text.encode("utf-8")]
        except Exception as e:
            return [500, "text/plain", str(e).encode("utf-8")]


if __name__ == "__main__":
    sp = Spider()
    sp.init()
    print("token", bool(sp.token), "host", sp.host)
    h = sp.homeContent()
    print("list", len(h.get("list") or []))
    if h.get("list"):
        vid = h["list"][0]["vod_id"]
        d = sp.detailContent([vid])
        vod = (d.get("list") or [{}])[0]
        print("detail", vod.get("vod_name"), (vod.get("vod_play_url") or "")[:100])
        play = sp.playerContent("x", (vod.get("vod_play_url") or "").split("$")[-1])
        print("play", play.get("url", "")[:120])
        # resolve leaf
        if play.get("url"):
            media = sp._resolve_media_m3u8(play["url"])
            print("leaf", media[:120])
            raw, _ = sp._http_get(media)
            print("leaf head", raw[:120])
