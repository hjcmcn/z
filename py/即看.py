# -*- coding: utf-8 -*-
import re, json, base64
import urllib.parse
from base.spider import Spider
from bs4 import BeautifulSoup


class Spider(Spider):
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Mobile Safari/537.36",
        "Referer": "https://www.jkan.app/"
    }

    def init(self, extend=""):
        self.host = "https://www.jkan.app"
        self._timeout = 15

    def _soup(self, html):
        return BeautifulSoup(html, "html.parser") if html else None

    def _fetch(self, url):
        return self.fetch(url, headers=self.headers, timeout=self._timeout, verify=False)

    def _fix(self, u):
        if not u: return ""
        if u.startswith("//"): return "https:" + u
        if u.startswith("/"): return self.host + u
        return u

    def _parse_list(self, html):
        videos, seen = [], set()
        soup = self._soup(html)
        if soup is None:
            return videos
        for a in soup.select('a[href*="/video/"]'):
            href = a.get("href", "")
            if not href or href in seen:
                continue
            if a.get("class") and "text_muted" in a.get("class"):
                continue
            seen.add(href)
            title = a.get("title", "") or a.get_text(strip=True)[:100]
            pic = a.get("data-original", "") or a.get("data-background-image", "")
            if not pic:
                bg = re.search(r"background(?:-image)?\s*:\s*url\([\"']?([^\"')]+)[\"']?\)", a.get("style", "") or "")
                if bg:
                    pic = bg.group(1)
            remark = ""
            rt = a.select_one("span.xszxj, span.pic_text")
            if rt:
                remark = rt.get_text(strip=True)
            videos.append({"vod_id": href, "vod_name": title, "vod_pic": self._fix(pic), "vod_remarks": remark})
            if len(videos) >= 50:
                break
        return videos

    def _get_filters(self, tid):
        return [
            {"key": "class", "name": "类型", "value": [
                {"n": "全部", "v": ""}, {"n": "喜剧", "v": "喜剧"}, {"n": "爱情", "v": "爱情"},
                {"n": "恐怖", "v": "恐怖"}, {"n": "动作", "v": "动作"}, {"n": "科幻", "v": "科幻"},
                {"n": "剧情", "v": "剧情"}, {"n": "战争", "v": "战争"}, {"n": "悬疑", "v": "悬疑"},
                {"n": "惊悚", "v": "惊悚"}, {"n": "冒险", "v": "冒险"}, {"n": "犯罪", "v": "犯罪"},
                {"n": "动画", "v": "动画"}, {"n": "奇幻", "v": "奇幻"}, {"n": "武侠", "v": "武侠"},
                {"n": "古装", "v": "古装"}, {"n": "历史", "v": "历史"}, {"n": "记录", "v": "记录"},
            ]},
            {"key": "area", "name": "地区", "value": [
                {"n": "全部", "v": ""}, {"n": "中国大陆", "v": "中国大陆"}, {"n": "美国", "v": "美国"},
                {"n": "韩国", "v": "韩国"}, {"n": "日本", "v": "日本"}, {"n": "香港", "v": "香港"},
                {"n": "台湾", "v": "台湾"}, {"n": "泰国", "v": "泰国"}, {"n": "英国", "v": "英国"},
                {"n": "法国", "v": "法国"}, {"n": "德国", "v": "德国"}, {"n": "印度", "v": "印度"},
            ]},
            {"key": "year", "name": "年份", "value":
                [{"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)]},
            {"key": "sort", "name": "排序", "value": [
                {"n": "按时间", "v": "time"}, {"n": "按人气", "v": "hits"}, {"n": "按评分", "v": "score"},
            ]},
        ]

    def homeContent(self, filter):
        return {
            "class": [
                {"type_id": "1", "type_name": "电影"},
                {"type_id": "2", "type_name": "电视剧"},
                {"type_id": "3", "type_name": "动漫"},
                {"type_id": "4", "type_name": "综艺"},
            ],
            "filters": {tid: self._get_filters(tid) for tid in ["1", "2", "3", "4"]}
        }

    def homeVideoContent(self):
        try:
            rsp = self._fetch(self.host)
            return {"list": self._parse_list(rsp.text)}
        except:
            return {"list": []}

    def _build_vodshow_url(self, tid, pg, extend):
        segs = [""] * 12
        segs[0] = tid
        if extend.get("area"): segs[1] = extend["area"]
        if extend.get("sort"): segs[2] = extend["sort"]
        if extend.get("class"): segs[3] = extend["class"]
        if extend.get("year"): segs[11] = extend["year"]
        url = f"{self.host}/show/{'-'.join(segs)}.html"
        if pg != "1":
            url = f"{self.host}/show/{'-'.join(segs)}-{pg}.html"
        return url

    def categoryContent(self, tid, pg, filter, extend):
        try:
            if filter and any(v for v in extend.values()):
                url = self._build_vodshow_url(tid, pg, extend)
            else:
                url = f"{self.host}/show/{tid}-----------{pg}.html"
            rsp = self._fetch(url)
            return {"list": self._parse_list(rsp.text), "page": str(pg), "pagecount": 999}
        except:
            return {"list": [], "page": str(pg), "pagecount": 0}

    def _get_detail(self, vid):
        if vid.startswith("/"):
            url = self._fix(vid)
        elif vid.startswith("http"):
            url = vid
        else:
            url = f"{self.host}/video/{vid}.html"
        try:
            rsp = self._fetch(url)
        except:
            return {"vod_id": vid}
        html = rsp.text
        if re.search(r"(模板文件不存在|系统安全验证)", html, re.I):
            return {"vod_id": "0", "vod_name": ""}
        vod = {"vod_id": vid}
        soup = self._soup(html)
        if soup is None:
            return vod
        vod["vod_name"] = self._og(soup, "og:title")
        vod["vod_pic"] = self._og(soup, "og:image")
        vod["vod_content"] = self._og(soup, "og:description")
        vod["vod_year"] = self._og(soup, "og:video:release_date")
        vod["vod_area"] = self._og(soup, "og:video:area")
        vod["vod_director"] = self._og(soup, "og:video:director")
        vod["vod_actor"] = self._og(soup, "og:video:actor")
        vod["type_name"] = self._og(soup, "og:video:class")
        score = self._og(soup, "og:video:score")
        if score: vod["vod_score"] = score
        # extract play sources and episodes
        src_tabs = soup.select_one(".play_source_tab")
        src_names = [a.get("alt", "").strip() or a.get_text(strip=True) for a in src_tabs.select("a")] if src_tabs else []
        for i, ul in enumerate(soup.select("ul.content_playlist, ul.playlist")):
            source = src_names[i] if i < len(src_names) else "默认"
            episodes = []
            seen_urls = set()
            for a in ul.select("a[href]"):
                ep_url = a.get("href", "")
                if ep_url in seen_urls:
                    continue
                seen_urls.add(ep_url)
                ep_name = a.get_text(strip=True) or "播放"
                episodes.append(f"{ep_name}${self._fix(ep_url)}")
            if episodes:
                vod.setdefault("vod_play_from", []).append(source)
                vod.setdefault("vod_play_url", []).append("#".join(episodes))
        if "vod_play_from" in vod:
            vod["vod_play_from"] = "$$$".join(vod.pop("vod_play_from"))
            vod["vod_play_url"] = "$$$".join(vod.pop("vod_play_url"))
        else:
            vod["vod_play_from"] = "默认线路"
            vod["vod_play_url"] = ""
        return vod

    def _og(self, soup, prop):
        m = soup.select_one(f'meta[property="{prop}"]')
        if m: return m.get("content", "")
        m = soup.select_one(f'meta[name="{prop}"]')
        if m: return m.get("content", "")
        return ""

    def detailContent(self, ids):
        return {"list": [self._get_detail(ids[0])]}

    def playerContent(self, flag, id, vipFlags):
        play_url = self._fix(id)
        if self.isVideoFormat(play_url):
            return {"parse": 0, "url": play_url, "header": self.headers}
        try:
            rsp = self._fetch(play_url)
            return self._parse_player(rsp.text, play_url)
        except:
            return {"parse": 0, "url": play_url, "header": self.headers}

    def _parse_player(self, html, play_url):
        match = re.search(r'player_aaaa\s*=\s*(\{[\s\S]*?\});?\s*</script>', html, re.I)
        if not match:
            return {"parse": 1, "url": play_url, "header": self.headers}
        try:
            data = json.loads(match.group(1))
            url_enc = data.get("url", "")
            enc_type = str(data.get("encrypt", "0"))
            if enc_type == "1":
                url_enc = urllib.parse.unquote(url_enc)
            elif enc_type == "2":
                url_enc = urllib.parse.unquote(base64.b64decode(url_enc).decode())
            real_url = self._unescape(url_enc)
            return {"parse": 0, "url": real_url or play_url, "header": self.headers}
        except:
            return {"parse": 0, "url": play_url, "header": self.headers}

    def _unescape(self, s):
        result, i, n = [], 0, len(s)
        while i < n:
            if s[i] == '%' and i + 5 < n and s[i + 1] == 'u':
                result.append(chr(int(s[i + 2:i + 6], 16)))
                i += 6
            elif s[i] == '%' and i + 2 < n:
                result.append(chr(int(s[i + 1:i + 3], 16)))
                i += 3
            else:
                result.append(s[i])
                i += 1
        return ''.join(result)

    def searchContent(self, key, quick, pg="1"):
        # 搜索翻页格式: ---------{N}--- (page1: 13 dashes, pageN: 10 dashes + N + 3 dashes)
        try:
            kw = urllib.parse.quote(key)
            if pg == "1":
                url = f"{self.host}/search/{kw}-------------.html"
            else:
                url = f"{self.host}/search/{kw}----------{pg}---.html"
            rsp = self._fetch(url)
            videos = self._parse_list(rsp.text)
            return {"list": videos, "page": str(pg), "pagecount": 99}
        except:
            return {"list": [], "pagecount": 0}

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(mp4|m3u8|flv|avi|mkv|ts|webm|mpg|mpeg)\b', url, re.I))

    def destroy(self):
        pass


