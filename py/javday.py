#!/usr/bin/python
# -*- coding: utf-8 -*-
import json
import re
from urllib.parse import urljoin, quote, urlparse
import requests
from lxml import etree
from base.spider import Spider


class Spider(Spider):
    def getName(self):
        return "javday"

    def init(self, extend=""):
        self.host = "https://javday.app"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; 22127RK46C Build/TKQ1.220905.001) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/152.0.7965.2 Mobile Safari/537.36",
            "Referer": self.host + "/",
            "Origin": self.host,
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.categories = [
            {"type_id": "category/new-release", "type_name": "\u65b0\u4f5c\u4e0a\u5e02"},
            {"type_id": "label/new", "type_name": "\u6700\u8fd1\u66f4\u65b0"},
            {"type_id": "label/groups", "type_name": "\u570b\u7522AV\u5ee0\u5546"},
            {"type_id": "label/hot", "type_name": "\u4eba\u6c23\u7cfb\u5217"},
            {"type_id": "category/aiav", "type_name": "AI\u77ed\u5267"},
            {"type_id": "category/censored", "type_name": "\u6709\u78bc"},
            {"type_id": "category/uncensored", "type_name": "\u7121\u78bc"},
            {"type_id": "category/chinese-av", "type_name": "\u570b\u7522AV"},
            {"type_id": "category/uncensored-leaked", "type_name": "\u7121\u78bc\u6d41\u51fa"},
            {"type_id": "category/sex8", "type_name": "\u674f\u5427"},
            {"type_id": "category/hongkongdoll", "type_name": "HongKongDoll"},
        ]

    def _get(self, url):
        try:
            r = self.session.get(url, headers=self.headers, timeout=15, verify=False)
            r.encoding = r.apparent_encoding or "utf-8"
            return r.text
        except Exception:
            return ""

    def _post(self, url, data=None):
        try:
            r = self.session.post(url, data=data or {}, headers=self.headers, timeout=15, verify=False)
            r.encoding = r.apparent_encoding or "utf-8"
            return r.text
        except Exception:
            return ""

    def _fix(self, url):
        return urljoin(self.host + "/", url or "")

    def _text(self, s):
        return re.sub(r"\s+", " ", s or "").strip()

    def _is_media(self, url):
        return bool(re.search(r"\.(?:m3u8|mp4)(?:$|[?#])", urlparse(url).path, re.I))

    def _probe_media(self, url):
        if not url or not self._is_media(url):
            return False
        try:
            r = self.session.get(url, headers=self.headers, timeout=10, verify=False, stream=True)
            chunk = next(r.iter_content(4096), b"")
            return b"#EXTM3U" in chunk or chunk[:4] in (b"\x00\x00\x00\x1c", b"ftyp")
        except Exception:
            return False

    def _list(self, html):
        items, seen = [], set()
        # XBPQ: loaded">&&</a > -- extract block between loaded"> and </a >
        blocks = re.findall(r'loaded">(.*?)(?:</a\s*>|</a\s+>)', html or "", re.S)
        if not blocks:
            # Fallback: loaded"[^>]*"> for tags with extra attrs after class
            blocks = re.findall(r'loaded"[^>]*>(.*?)(?:</a\s*>|</a\s+>)', html or "", re.S)
        if not blocks:
            # Fallback 2: find <a> tags with href and title containing site path
            blocks = re.findall(r'<a[^>]+href="[^"]*"[^>]*title="[^"]*"[^>]*>(.*?)(?:</a\s*>|</a\s+>)', html or "", re.S)
        for chunk in blocks:
            # XBPQ title: title="&&" (attr) or title">&&< (element)
            title = ""
            m = re.search(r'title="([^"]*)"', chunk)
            if m:
                title = self._text(m.group(1))
            if not title:
                m = re.search(r'title[^>]*">([^<]*)<', chunk)
                if m:
                    title = self._text(m.group(1))
            # XBPQ pic: url("&&") or url(&&)
            pic = ""
            m = re.search(r'url\("([^"]+)"\)', chunk)
            if not m:
                m = re.search(r'url\(([^)]+)\)', chunk)
            if m:
                pic = self._text(m.group(1)).strip("'\"")
            # XBPQ subtitle: number">&&<
            remark = ""
            m = re.search(r'number[^>]*">([^<]*)<', chunk)
            if m:
                remark = self._text(m.group(1))
            # XBPQ link: href="&&"
            link = ""
            m = re.search(r'href="([^"]*)"', chunk)
            if m:
                link = self._text(m.group(1))
            if not link or link in seen:
                continue
            seen.add(link)
            items.append({
                "vod_id": link,
                "vod_name": title or "\u672a\u77e5",
                "vod_pic": self._fix(pic) if pic else "",
                "vod_remarks": remark,
            })
        return items

    def _pagecount(self, html, pg):
        nums = [int(x) for x in re.findall(r"/page/(\d+)/", html or "")]
        if nums:
            return max(nums)
        if re.search(r"next|下一页|\u4e0b\u9875", html or "", re.I):
            return pg + 1
        return pg

    def homeContent(self, filter):
        html = self._get(self.host)
        return {"class": self.categories, "list": self._list(html), "filters": {}}

    def homeVideoContent(self):
        return {"list": self._list(self._get(self.host))}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg) if str(pg).isdigit() else 1
        if pg <= 1:
            url = f"{self.host}/{tid}"
        else:
            url = f"{self.host}/{tid}/page/{pg}/"
        html = self._get(url)
        items = self._list(html)
        limit = len(items) or 12
        pc = self._pagecount(html, pg)
        return {"page": pg, "pagecount": pc, "limit": limit, "total": pc * limit, "list": items}

    def detailContent(self, ids):
        out = []
        for vid in ids:
            try:
                url = self._fix(str(vid))
                html = self._get(url)
                tree = etree.HTML(html) if html else None
                if tree is None:
                    continue
                # Title from h1 or <title>
                title = ""
                h1 = tree.xpath("//h1")
                if h1:
                    title = self._text(h1[0].xpath("string()"))
                if not title:
                    t = tree.xpath("//title/text()")
                    if t:
                        title = self._text(t[0].split("|")[0])
                # Pic from background url() or img src
                pic = ""
                styles = tree.xpath('//*[@style]')
                for el in styles:
                    style = el.get("style", "")
                    m = re.search(r'url\("([^"]+)"\)', style)
                    if not m:
                        m = re.search(r"url\(([^)]+)\)", style)
                    if m:
                        pic = self._fix(m.group(1).strip("'\""))
                        break
                if not pic:
                    imgs = tree.xpath('//img/@src')
                    if imgs:
                        pic = self._fix(imgs[0])
                # Year from title
                year = ""
                m = re.search(r"(\d{4})", title or "")
                if m:
                    year = m.group(1)
                # Content/intro
                content = ""
                meta = tree.xpath('//meta[@name="description"]/@content')
                if meta:
                    content = self._text(meta[0])
                # Lines (XBPQ: p:.video-title, title=❤️+p:->text)
                line_els = tree.xpath('//*[contains(@class,"video-title")]')
                line_names = ["\u2764\ufe0f" + self._text(el.xpath("string()")) for el in line_els]
                fs, us = [], []
                # Method 1: AI短剧 -- .episode-list > button[data-url][data-name]
                ep_containers = tree.xpath('//*[contains(@class,"episode-list")]')
                for i, ep_cont in enumerate(ep_containers):
                    buttons = ep_cont.xpath(".//button")
                    ep_links = []
                    for j, btn in enumerate(buttons, 1):
                        data_url = btn.get("data-url", "")
                        data_name = btn.get("data-name", "")
                        if data_url:
                            ep_name = data_name if data_name else f"\u7b2c{j}\u96c6"
                            ep_links.append(f"{ep_name}${data_url}")
                    if ep_links:
                        ln = line_names[i] if i < len(line_names) else f"\u2764\ufe0f\u7eb2\u8def{i + 1}"
                        fs.append(ln)
                        us.append("#".join(ep_links))
                # Method 2: normal content -- <video><source src="xxx.m3u8">
                if not fs:
                    video_els = tree.xpath("//video")
                    for i, video in enumerate(video_els):
                        sources = video.xpath(".//source")
                        links = []
                        for j, source in enumerate(sources, 1):
                            src = source.get("src", "")
                            if src and ".m3u8" in src:
                                if not src.endswith(".m3u8"):
                                    src += ".m3u8"
                                links.append(f"\U0001f449\u7b2c{j}\u96c6${src}")
                        if links:
                            ln = line_names[i] if i < len(line_names) else f"\u2764\ufe0f\u7eb2\u8def{i + 1}"
                            fs.append(ln)
                            us.append("#".join(links))
                # Fallback: any m3u8 on page
                if not fs:
                    m3u8_urls = re.findall(r"https?://[^'\"\s<>]+\.m3u8", html)
                    if m3u8_urls:
                        fs.append("\u2764\ufe0f\u7eb2\u8def1")
                        us.append("#".join([f"\U0001f449\u7b2c1\u96c6${u}" for u in m3u8_urls[:1]]))
                vod = {
                    "vod_id": str(vid),
                    "vod_name": title or str(vid),
                    "vod_pic": pic,
                    "vod_year": year,
                    "vod_content": content,
                    "vod_play_from": "$$$".join(fs) if fs else "\u2764\ufe0f\u7eb2\u8def1",
                    "vod_play_url": "$$$".join(us) if us else "",
                }
                out.append(vod)
            except Exception:
                continue
        return {"list": out}

    def searchContent(self, key, quick, pg="1"):
        try:
            url = f"{self.host}/?s={quote(key)}"
            html = self._get(url)
            items = self._list(html)
            if not items:
                url2 = f"{self.host}/search/{quote(key)}/"
                html2 = self._get(url2)
                items = self._list(html2)
            return {"list": items, "page": int(pg) if str(pg).isdigit() else 1}
        except Exception:
            return {"list": [], "page": int(pg) if str(pg).isdigit() else 1}

    def playerContent(self, flag, id, vipFlags):
        url = id
        if self._is_media(url) and self._probe_media(url):
            return {"parse": 0, "url": url, "header": json.dumps(self.headers)}
        # Try fetching the page for m3u8
        html = self._get(self._fix(url))
        m = re.search(r"https?://[^'\"\s<>]+\.m3u8", html)
        if m and self._probe_media(m.group(0)):
            return {"parse": 0, "url": m.group(0), "header": json.dumps(self.headers)}
        return {"parse": 1, "url": self._fix(url), "header": json.dumps(self.headers)}
