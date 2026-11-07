# coding: utf-8
"""
夜勾心事 (ygxs) — TVBox/FongMi Python 源
主域: https://oeh.ygxs.lat  (发布页提示 ygxs.buzz)
架构: MacCMS v10  |  列表: /index.php/ajax/data (JSON, 忽略 tid)
分类/搜索/详情/播放: HTML 页 (必须移动端 UA 过 Cloudflare)
  - 分类: /index.php/vod/show/id/{tid}/page/{pg}.html
  - 搜索: /index.php/vod/search/page/{pg}/wd/{kw}.html
  - 详情: /index.php/vod/detail/id/{vid}.html
  - 播放: /index.php/vod/play/id/{vid}/sid/1/nid/1.html  -> player_aaaa 明文 encrypt=0
图片CDN: https://ckbhjpg2.top   流CDN: thm3u8.co / ckbhm3u8.com / ckts2.top
播放格式: m3u8 (图片流伪装 .jpg 分片 + AES-128 分段混排)
去广告: m3u8_analyzer 取证 suspicious_ad_dirs 为空 -> 直接透传直链，不套代理
验证日期: 2026-11-02
"""
import re
import json
import posixpath
from urllib.parse import quote, unquote, urljoin, urlparse

from base.spider import Spider as BaseSpider


IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
VIDEO_EXT = (".ts", ".m4s", ".mp4", ".aac", ".m4a")


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://oeh.ygxs.lat"
        self.name = "夜勾心事"
        self.ua = ("Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36")
        self.headers = {
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/",
        }
        self.classes = [
    {"type_id": "20", "type_name": "学生少女"},
    {"type_id": "21", "type_name": "技师风采"},
    {"type_id": "22", "type_name": "熟女少妇"},
    {"type_id": "23", "type_name": "国产热播"},
    {"type_id": "24", "type_name": "反差母狗"},
    {"type_id": "25", "type_name": "美脚丝足"},
    {"type_id": "26", "type_name": "情侣自拍"},
    {"type_id": "27", "type_name": "私房俱乐部"},
    {"type_id": "28", "type_name": "偷情约炮"},
    {"type_id": "29", "type_name": "真实偷拍"},
    {"type_id": "30", "type_name": "高潮喷水"},
    {"type_id": "31", "type_name": "强奸迷奸"},
    {"type_id": "32", "type_name": "户外露出"},
    {"type_id": "33", "type_name": "SM调教"},
    {"type_id": "34", "type_name": "情趣内衣"},
    {"type_id": "35", "type_name": "精选探花"},
    {"type_id": "36", "type_name": "网曝门事件"},
    {"type_id": "37", "type_name": "校园猛料"},
    {"type_id": "38", "type_name": "网红流出"},
    {"type_id": "39", "type_name": "明星黑料"},
    {"type_id": "40", "type_name": "裸贷肉偿"},
    {"type_id": "41", "type_name": "婚闹恶俗"},
    {"type_id": "42", "type_name": "抓奸名场面"},
    {"type_id": "43", "type_name": "男同女同"},
    {"type_id": "44", "type_name": "JK少女"},
    {"type_id": "45", "type_name": "黑丝白丝"},
    {"type_id": "46", "type_name": "女仆"},
    {"type_id": "47", "type_name": "cosplay"},
    {"type_id": "48", "type_name": "OL制服"},
    {"type_id": "49", "type_name": "旗袍"},
    {"type_id": "50", "type_name": "空姐制服"},
    {"type_id": "51", "type_name": "护士医生"},
    {"type_id": "52", "type_name": "伦理之爱"},
    {"type_id": "53", "type_name": "禁忌母子"},
    {"type_id": "54", "type_name": "兄弟姐妹"},
    {"type_id": "55", "type_name": "爱上嫂子"},
    {"type_id": "56", "type_name": "狂操小姨"},
    {"type_id": "57", "type_name": "换夫换妻"},
    {"type_id": "58", "type_name": "淫荡儿媳"},
    {"type_id": "59", "type_name": "爷爷奶奶"},
    {"type_id": "60", "type_name": "伦理精选"},
    {"type_id": "61", "type_name": "啪啪直播"},
    {"type_id": "62", "type_name": "学生直播"},
    {"type_id": "63", "type_name": "自慰诱惑"},
    {"type_id": "64", "type_name": "乱伦直播"},
    {"type_id": "65", "type_name": "户外勾搭"},
    {"type_id": "66", "type_name": "车震直播"},
    {"type_id": "67", "type_name": "国产AV"},
    {"type_id": "68", "type_name": "网红主播"},
    {"type_id": "69", "type_name": "欧美精选"},
    {"type_id": "70", "type_name": "户外搭讪"},
    {"type_id": "71", "type_name": "美女自慰"},
    {"type_id": "72", "type_name": "乱伦直播"},
    {"type_id": "73", "type_name": "黑人大屌"},
    {"type_id": "74", "type_name": "群P大作战"},
    {"type_id": "75", "type_name": "欧美重口"},
    {"type_id": "76", "type_name": "人兽性交"},
    {"type_id": "77", "type_name": "SM性虐"},
    {"type_id": "78", "type_name": "人妖伪娘"},
    {"type_id": "79", "type_name": "孕妇内射"},
    {"type_id": "80", "type_name": "吃屎喝尿"},
    {"type_id": "81", "type_name": "扩阴拳交"},
    {"type_id": "82", "type_name": "阳具巨物"},
    {"type_id": "83", "type_name": "3D动漫"},
    {"type_id": "84", "type_name": "同人动漫"},
    {"type_id": "85", "type_name": "剧情故事"},
    {"type_id": "86", "type_name": "国产动漫"},
    {"type_id": "87", "type_name": "日韩动漫"},
    {"type_id": "88", "type_name": "欧美动漫"},
    {"type_id": "89", "type_name": "港台动漫"},
    {"type_id": "90", "type_name": "海外动漫"},
    {"type_id": "91", "type_name": "日本中文"},
    {"type_id": "92", "type_name": "无码流出"},
    {"type_id": "93", "type_name": "FC2"},
    {"type_id": "94", "type_name": "HEYZO"},
    {"type_id": "95", "type_name": "东京热"},
    {"type_id": "96", "type_name": "一本道"},
    {"type_id": "97", "type_name": "人妻斩"},
    {"type_id": "98", "type_name": "主播网黄"},
    {"type_id": "99", "type_name": "色情综艺"},
    {"type_id": "100", "type_name": "情色AV"},
        ]
        self.filters = {}

    def getName(self):
        return self.name

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def destroy(self):
        pass

    def _get(self, url, timeout=15):
        try:
            r = self.fetch(url, headers=self.headers, timeout=timeout)
            if not r or r.status_code != 200:
                return ""
            return r.text or ""
        except Exception as e:
            self.log({"get": "fail", "err": type(e).__name__})
            return ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        html = self._get(self.host + "/")
        return {"list": self._parse_cards(html)}

    # ---------- 卡片解析（三条选择器链） ----------
    @staticmethod
    def _parse_cards(html):
        if not html:
            return []
        out, seen = [], set()
        pat_a = re.compile(
            r'<li>\s*<a href="(/index\.php/vod/detail/id/(\d+)\.html)"\s+title="([^"]*)"\s*>'
            r'\s*<img src="([^"]*)"[^>]*/?>\s*<h2>([^<]*)</h2>', re.S)
        pat_b = re.compile(
            r'<li><a href="(/index\.php/vod/detail/id/(\d+)\.html)" title="([^"]*)">'
            r'<img src="([^"]*)"><br\s*/?><span>([^<]*)</span>\s*([^<]*)</a></li>', re.S)
        for m in pat_a.finditer(html):
            vid, name, pic = m.group(2), m.group(5), m.group(4)
            if vid in seen or not name:
                continue
            seen.add(vid)
            out.append({"vod_id": vid, "vod_name": name.strip(),
                        "vod_pic": pic, "vod_remarks": ""})
        if out:
            return out
        for m in pat_b.finditer(html):
            vid, name, pic, stamp = m.group(2), m.group(3), m.group(4), m.group(5)
            if vid in seen or not name:
                continue
            seen.add(vid)
            out.append({"vod_id": vid, "vod_name": name.strip(),
                        "vod_pic": pic, "vod_remarks": (stamp or "").strip()})
        return out

    def _parse_extend(self, extend):
        if not extend:
            return {}
        if isinstance(extend, dict):
            return extend
        if isinstance(extend, str):
            s = extend.strip()
            if s.startswith("{"):
                try:
                    return json.loads(s)
                except Exception:
                    pass
            out = {}
            for part in s.split(","):
                if "=" in part:
                    k, v = part.split("=", 1)
                    out[k.strip()] = v.strip()
            return out
        return {}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg or 1)
        except Exception:
            page = 1
        tid = str(tid or "").strip() or "20"
        if page <= 1:
            url = "%s/index.php/vod/show/id/%s.html" % (self.host, tid)
        else:
            url = "%s/index.php/vod/show/id/%s/page/%d.html" % (self.host, tid, page)
        html = self._get(url)
        lst = self._parse_cards(html)
        pagecount = 1
        m = re.search(r'/page/(\d+)\.html" title="尾页"', html)
        if m:
            try:
                pagecount = int(m.group(1))
            except Exception:
                pagecount = 9999
        elif lst:
            pagecount = 9999
        return {"list": lst, "page": page, "pagecount": pagecount,
                "limit": 20, "total": pagecount * 20}

    @staticmethod
    def _norm_ids(ids):
        if ids is None:
            return ""
        if isinstance(ids, (list, tuple)):
            if not ids:
                return ""
            ids = ids[0]
        if isinstance(ids, bytes):
            ids = ids.decode("utf-8", errors="ignore")
        return str(ids).strip()

    def _skeleton(self, vid, title="", pic="", remarks="解析中"):
        pid = str(vid).split("|$|")[0].replace("$", "|")
        return {"list": [{
            "vod_id": str(vid), "vod_name": title or "未知标题",
            "vod_pic": pic or "", "vod_remarks": remarks, "vod_content": "",
            "vod_play_from": "默认", "vod_play_url": "正片$" + pid,
        }]}

    def detailContent(self, ids):
        raw = self._norm_ids(ids)
        if not raw:
            return {"list": []}
        vid = raw.split("|$|")[0]
        url = "%s/index.php/vod/detail/id/%s.html" % (self.host, vid)
        html = self._get(url)
        if not html:
            return self._skeleton(vid)

        title = ""
        m = re.search(r'<title>(.*?)</title>', html, re.S)
        if m:
            title = re.sub(r"\s*-\s*夜勾心事\s*$", "", m.group(1).strip())
            title = re.split(r"详情介绍|在线观看", title)[0].strip() or title
        if not title:
            m = re.search(r'<dt>片名：([^<]*)</dt>', html)
            title = m.group(1).strip() if m else ""

        pic = ""
        m = re.search(r'<div class="media"><ul>\s*<li><a[^>]*><img src="([^"]*)"', html)
        if m:
            pic = m.group(1)
        if not pic:
            m = re.search(r'og:image" content="([^"]*)"', html)
            pic = m.group(1) if m else ""

        # 线路：详情页唯一的 sid/nid 组合
        pairs = []
        for mm in re.finditer(r'/play/id/%s/sid/(\d+)/nid/(\d+)\.html' % re.escape(vid), html):
            key = (mm.group(1), mm.group(2))
            if key not in pairs:
                pairs.append(key)
        if not pairs:
            pairs = [("1", "1")]

        eps = []
        for i, (sid, nid) in enumerate(pairs):
            name = "正片" if len(pairs) == 1 else ("第%d集" % (i + 1))
            pid = "%s/sid/%s/nid/%s" % (vid, sid, nid)
            eps.append(name + "$" + pid)
        if not eps:
            return self._skeleton(vid, title, pic)

        vod = {
            "vod_id": raw,
            "vod_name": title or "未知标题",
            "vod_pic": pic,
            "vod_remarks": "",
            "vod_content": title or "",
            "vod_play_from": "ckm3u8",
            "vod_play_url": "#".join(eps),
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg or 1)
        except Exception:
            page = 1
        kw = quote(str(key or "").strip(), safe="")
        if page <= 1:
            url = "%s/index.php/vod/search/wd/%s.html" % (self.host, kw)
        else:
            url = "%s/index.php/vod/search/page/%d/wd/%s.html" % (self.host, page, kw)
        html = self._get(url)
        return {"list": self._parse_cards(html), "page": page}

    def playerContent(self, flag, id, vipFlags):
        raw = str(id or "").strip()
        if "$" in raw:
            raw = raw.split("$", 1)[1]
        if not raw:
            return {"parse": 1, "url": "", "header": self.headers}
        if raw.startswith(("http://", "https://")):
            return {"parse": 0, "url": raw, "header": {"User-Agent": self.ua}}
        # 形如 122080/sid/1/nid/1 -> 拼播放页
        if "/sid/" in raw:
            vid = raw.split("/")[0]
            m = re.search(r"/sid/(\d+)/nid/(\d+)", raw)
            sid = m.group(1) if m else "1"
            nid = m.group(2) if m else "1"
            play_url = "%s/index.php/vod/play/id/%s/sid/%s/nid/%s.html" % (self.host, vid, sid, nid)
        else:
            play_url = "%s/index.php/vod/play/id/%s/sid/1/nid/1.html" % (self.host, raw)

        html = self._get(play_url)
        if not html:
            return {"parse": 1, "url": play_url, "header": self.headers}
        real = self._grab_player_url(html)
        if real:
            # 该站片头固定挂两段广告目录，统一走本地代理清洗
            return {"parse": 0, "url": self._m3u8_proxy_url(real),
                    "header": {"User-Agent": self.ua, "Referer": self.host + "/"}}
        return {"parse": 1, "url": play_url, "header": self.headers}

    @staticmethod
    def _grab_player_url(html):
        m = re.search(r"player_aaaa\s*=\s*(\{.*?\})\s*</script>", html, re.S)
        if not m:
            return ""
        s = m.group(1).replace("\\/", "/")
        for attempt in range(2):
            try:
                data = json.loads(s)
                return str(data.get("url") or "").strip()
            except Exception:
                s = re.sub(r",\s*}", "}", s)
        m2 = re.search(r'"url"\s*:\s*"([^"]+)"', s)
        return m2.group(1).replace("\\/", "/") if m2 else ""

    def recommendContent(self, ids, pg):
        return {"list": []}

    def localProxy(self, param):
        """m3u8 代理：图片流后缀原样透传，按分片目录众数锚点剔除片头广告"""
        target = unquote(str((param or {}).get("url", "") or ""))
        if not re.match(r"^https?://", target, re.I):
            return [400, "text/plain", b"invalid url"]
        try:
            r = self.fetch(target, headers=self.headers, timeout=15)
            if not r or r.status_code != 200:
                return [502, "text/plain", b"m3u8 fetch failed"]
            text = r.text or ""
            if "#EXTM3U" not in text:
                return [502, "text/plain", b"invalid m3u8"]
            cleaned = self._clean_m3u8(text, target)
            if isinstance(cleaned, str):
                cleaned = cleaned.encode("utf-8")
            return [200, "application/vnd.apple.mpegurl", cleaned]
        except Exception as e:
            self.log({"proxy": "error", "err": type(e).__name__})
            return [500, "text/plain", b"m3u8 proxy error"]

    # ---------- m3u8 清洗：图片流铁律（后缀不改写、不提前 return、众数锚点、全滤兜底） ----------
    @staticmethod
    def _is_fake_image_stream(text):
        has_video = has_image = False
        for line in str(text or "").split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            path = line.split("?")[0].split("#")[0].lower()
            if path.endswith(VIDEO_EXT):
                has_video = True
            elif path.endswith(IMAGE_EXT):
                has_image = True
        return has_image and not has_video

    @staticmethod
    def _resolve_main_dir(lines, source_url, is_image_stream):
        base_dir = posixpath.dirname(urlparse(source_url).path)
        if not base_dir.endswith("/"):
            base_dir += "/"
        if is_image_stream:
            counter = {}
            for line in lines:
                if not line or line.startswith("#"):
                    continue
                p = urlparse(urljoin(source_url, line)).path
                d = posixpath.dirname(p)
                if d and d != "/":
                    counter[d + "/"] = counter.get(d + "/", 0) + 1
            if counter:
                return max(counter.items(), key=lambda kv: kv[1])[0]
            return base_dir
        for line in lines:
            if not line.startswith("#EXT-X-KEY") or "URI=" not in line:
                continue
            m = re.search(r'URI="([^"]+)"', line)
            if not m:
                continue
            key_uri = m.group(1)
            if not key_uri.startswith("http"):
                key_uri = urljoin(source_url, key_uri)
            key_dir = posixpath.dirname(urlparse(key_uri).path)
            if key_dir and key_dir != "/":
                return key_dir + "/"
        return base_dir

    @staticmethod
    def _rewrite_tag(line, source_url):
        if line.startswith(("#EXT-X-KEY", "#EXT-X-MAP", "#EXT-X-SESSION-KEY")):
            def repl(m):
                uri = m.group(1)
                if uri.startswith(("http://", "https://")):
                    return 'URI="' + uri + '"'
                return 'URI="' + urljoin(source_url, uri) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)
        if line and not line.startswith("#"):
            if line.startswith(("http://", "https://")):
                return line
            return urljoin(source_url, line)
        return line

    def _clean_m3u8(self, text, source_url):
        lines = [l.strip() for l in str(text or "").replace("\r", "").split("\n") if l.strip()]
        if not lines:
            return "#EXTM3U\n"
        is_img = self._is_fake_image_stream(text)
        # 多码率主表：只把子流转代理，其余透传
        if any(l.startswith("#EXT-X-STREAM-INF") for l in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = urljoin(source_url, line)
                    out.append(self._m3u8_proxy_url(child) if ".m3u8" in child.lower() else child)
            return "\n".join(out) + "\n"
        anchor = self._resolve_main_dir(lines, source_url, is_img)
        kept, removed = [], 0
        pending = []
        for line in lines:
            if line.startswith("#EXTINF"):
                pending = [line]
                continue
            if pending and line.startswith("#"):
                pending.append(line)
                continue
            if pending:
                media = urljoin(source_url, line)
                d = posixpath.dirname(urlparse(media).path)
                if d and d != "/":
                    d += "/"
                if d and not d.startswith(anchor.rstrip("/")):
                    removed += 1
                else:
                    kept.extend(pending)
                    kept.append(media)
                pending = []
                continue
            kept.append(self._rewrite_tag(line, source_url))
        if removed > 0 and (not kept or removed > len(kept)):
            self.log({"clean": "fallback_no_filter", "removed": removed, "kept": len(kept)})
            return "\n".join(self._rewrite_tag(l, source_url) for l in lines) + "\n"
        out = []
        for line in kept:
            if line in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
                if not out or out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
                    continue
            out.append(line)
        while len(out) > 1 and out[-2] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
            out.pop(-2)
        if removed:
            self.log({"clean": "done", "removed": removed, "kept": len(out), "anchor": anchor})
        return "\n".join(out) + "\n"

    def _m3u8_proxy_url(self, url):
        base = self.getProxyUrl()
        sep = "&" if "?" in base else "?"
        return base + sep + "url=" + quote(str(url or ""), safe="")


class M3U8AdFilter:
    """预留：本站取证无广告目录，正片直连。若后续出现广告，在此补五层管线。"""
    pass
