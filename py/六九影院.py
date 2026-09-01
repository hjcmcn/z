# -*- coding: utf-8 -*-
"""
目标站: 六九影院 (https://www.easga.com)
模板: 苹果CMS (MyTheme风格)
功能: 分类浏览、详情解析、多线路播放列表、搜索、m3u8播放
修复: 短剧分类数据、播放列表按线路分组去重
"""
import re
import json
import urllib.parse
from base.spider import Spider as BaseSpider
import requests
from bs4 import BeautifulSoup


class Spider(BaseSpider):

    def getName(self):
        return "六九影院"

    def init(self, extend=""):
        self.host = "https://www.easga.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; 22127RK46C Build/TKQ1.220905.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/104.0.5112.97 Mobile Safari/537.36",
            "Referer": self.host + "/",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }

    def get(self, url):
        try:
            r = requests.get(url, headers=self.headers, timeout=15)
            r.raise_for_status()
            r.encoding = "utf-8"
            return r.text
        except:
            return ""

    def parse_card(self, el):
        """解析视频卡片"""
        a = el.select_one("a[href^='/stvvod/']")
        if not a:
            return None

        href = str(a.get("href", ""))
        m = re.search(r"/stvvod/(\d+)\.html", href)
        if not m:
            return None

        vid = m.group(1)
        title = str(a.get("title", "") or a.get_text(strip=True))

        # 图片
        pic = ""
        img = el.select_one("img")
        if img:
            pic = str(img.get("data-src", "") or img.get("src", "") or "")
            if pic and pic.startswith("/"):
                pic = self.host + pic

        # 备注
        remark = ""
        txt = el.select_one(".module-item-text")
        if txt:
            remark = txt.get_text(strip=True)

        return {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": remark,
        }

    def _parse_videos(self, html):
        """从HTML解析视频列表"""
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        videos = [v for v in (self.parse_card(el) for el in soup.select(".module-item")) if v]
        return videos

    def homeContent(self, filter):
        return {
            "class": [
                {"type_name": "电影", "type_id": "1"},
                {"type_name": "电视剧", "type_id": "2"},
                {"type_name": "综艺", "type_id": "3"},
                {"type_name": "动漫", "type_id": "4"},
                {"type_name": "短剧", "type_id": "30"},
                {"type_name": "预告", "type_id": "55"},
            ],
            "filters": {}
        }

    def homeVideoContent(self):
        html = self.get(self.host)
        return {"list": self._parse_videos(html)}

    def categoryContent(self, tid, pg, filter, extend):
        if int(pg) == 1:
            url = f"{self.host}/stvlist/{tid}.html"
        else:
            url = f"{self.host}/stvlist/{tid}-{pg}.html"

        html = self.get(url)
        if not html:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 30, "total": 0}

        soup = BeautifulSoup(html, "html.parser")

        # 分页: /stvlist/{tid}-{pg}.html
        pagecount = int(pg)
        for a in soup.select("a[href*='/stvlist/']"):
            href = str(a.get("href", ""))
            m = re.search(r"/stvlist/\d+-(\d+)\.html", href)
            if m:
                pagecount = max(pagecount, int(m.group(1)))

        return {
            "list": self._parse_videos(html),
            "page": pg,
            "pagecount": max(pagecount, 1),
            "limit": 30,
            "total": 99999
        }

    def detailContent(self, ids):
        vid = ids[0]
        html = self.get(f"{self.host}/stvvod/{vid}.html")
        if not html:
            return {"list": []}

        soup = BeautifulSoup(html, "html.parser")

        # 标题
        title = ""
        h1 = soup.select_one("h1")
        if h1:
            title = h1.get_text(strip=True)
        if not title:
            t = soup.find("title")
            if t:
                title = re.sub(r"\s*[-_|]\s*.{0,20}$", "", t.get_text(strip=True)).strip()
        title = title or f"视频{vid}"

        # 图片
        pic = ""
        for sel in ['.module-item-pic img', '.vodimg img', '.poster img']:
            img = soup.select_one(sel)
            if img:
                pic = str(img.get("data-src", "") or img.get("src", ""))
                if pic and "loading" not in pic:
                    break
        if not pic:
            og = soup.select_one('meta[property="og:image"]')
            if og:
                pic = str(og.get("content", ""))
        if pic and pic.startswith("/"):
            pic = self.host + pic

        # 简介
        desc = ""
        for sel in ['.video-text', '.vodinfo', '.summary', '.content']:
            d = soup.select_one(sel)
            if d:
                desc = d.get_text(strip=True)
                if len(desc) > 10:
                    break

        # 解析播放列表：按线路分组去重
        # URL 格式: /stvplayer/{vid}-{line}-{ep}.html
        lines_map = {}  # {line_num: {ep_text: ep_url}}

        for a2 in soup.select("a[href*='/stvplayer/']"):
            href = str(a2.get("href", ""))
            ep_text = a2.get_text(strip=True)
            if not href or not ep_text:
                continue
            # 跳过非集数链接（如立即播放可能有重复）
            if ep_text in ["立即播放"] and len(soup.select("a[href*='/stvplayer/']")) > 2:
                continue

            # 解析线路号
            m = re.search(r"/stvplayer/\d+-(\d+)-\d+\.html", href)
            line_num = m.group(1) if m else "0"
            line_num = int(line_num) if line_num.isdigit() else 0

            ep_url = self.host + href if href.startswith("/") else href

            if line_num not in lines_map:
                lines_map[line_num] = {}
            # 同一集去重（URL 去重）
            if ep_text not in lines_map[line_num]:
                lines_map[line_num][ep_text] = ep_url

        # 线路名称映射（根据常见CMS线路顺序）
        line_names = {
            0: "秒播",
            1: "量子",
            2: "新浪",
            3: "虎牙",
            4: "闪电",
        }

        play_from_list = []
        play_url_list = []

        # 按线路号排序
        for line_num in sorted(lines_map.keys()):
            eps = lines_map[line_num]
            if not eps:
                continue
            # 对集数排序：尝试按数字排序
            def _ep_sort_key(item):
                text = item[0]
                m = re.search(r'第?0*(\d+)', text)
                if m:
                    return (0, int(m.group(1)))
                # 全集/正片排最后
                if text in ["全集", "正片", "立即播放"]:
                    return (2, 0)
                return (1, 0)

            sorted_eps = sorted(eps.items(), key=_ep_sort_key)
            ep_items = [f"{text}${url}" for text, url in sorted_eps]
            if ep_items:
                line_name = line_names.get(line_num, f"线路{line_num + 1}")
                play_from_list.append(line_name)
                play_url_list.append("#".join(ep_items))

        # 兜底
        if not play_from_list:
            play_from_list.append("默认线路")
            play_url_list.append(f"播放${self.host}/stvplayer/{vid}-0-0.html")

        return {"list": [{
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_content": desc,
            "vod_play_from": "$$$".join(play_from_list),
            "vod_play_url": "$$$".join(play_url_list),
        }]}

    def searchContent(self, key, quick, pg="1"):
        encoded = urllib.parse.quote(key)
        url = f"{self.host}/search.php?searchword={encoded}"
        if int(pg) > 1:
            url += f"&page={pg}"

        html = self.get(url)
        if not html:
            return {"list": []}

        return {"list": self._parse_videos(html), "page": pg, "pagecount": int(pg) + 1, "limit": 30, "total": 99999}

    def playerContent(self, flag, id, vipFlags):
        try:
            url = id
            if not url.startswith("http"):
                url = self.host + url if url.startswith("/") else self.host + "/" + url

            # 请求播放页
            html = self.get(url)
            if not html:
                return {"parse": 1, "url": url, "header": self.headers}

            # 尝试多种方式提取m3u8
            # 1. 从iframe提取
            soup = BeautifulSoup(html, "html.parser")
            iframe = soup.select_one("iframe")
            if iframe:
                src = str(iframe.get("src", ""))
                if src:
                    if src.startswith("//"):
                        src = "https:" + src
                    elif src.startswith("/"):
                        src = self.host + src
                    # 如果iframe直接指向m3u8
                    if ".m3u8" in src.lower():
                        return {"parse": 0, "playUrl": "", "url": src, "header": json.dumps(self.headers)}
                    # 否则请求iframe内容
                    iframe_html = self.get(src)
                    if iframe_html:
                        for p in [r"(https?://[^\s'\"<>]+\.m3u8[^\s'\"<>]*)", r"(https?://[^\s'\"<>]+\.mp4[^\s'\"<>]*)"]:
                            m = re.search(p, iframe_html, re.I)
                            if m:
                                return {"parse": 0, "playUrl": "", "url": m.group(1), "header": json.dumps(self.headers)}

            # 2. 从script提取
            for script in soup.find_all("script"):
                txt = script.string or ""
                for p in [r"""(https?://[^\s'"<>]+\.m3u8[^\s'"<>]*)""", r"""(https?://[^\s'"<>]+\.mp4[^\s'"<>]*)"""]:
                    m = re.search(p, txt, re.I)
                    if m:
                        return {"parse": 0, "playUrl": "", "url": m.group(1), "header": json.dumps(self.headers)}

            # 3. 从mac_player或player相关变量提取
            for pattern in [
                r"var\s+url\s*=\s*['\"]([^'\"]+)['\"]",
                r"var\s+src\s*=\s*['\"]([^'\"]+)['\"]",
                r"var\s+video\s*=\s*['\"]([^'\"]+)['\"]",
                r"url:\s*['\"]([^'\"]+)['\"]",
                r"src:\s*['\"]([^'\"]+)['\"]",
            ]:
                m = re.search(pattern, html, re.I)
                if m:
                    video_url = m.group(1)
                    if ".m3u8" in video_url.lower() or ".mp4" in video_url.lower():
                        return {"parse": 0, "playUrl": "", "url": video_url, "header": json.dumps(self.headers)}

            # 4. 从JSON格式提取
            for m in re.finditer(r"['\"](https?://[^'\"<>]+\.m3u8[^'\"<>]*)['\"]", html, re.I):
                return {"parse": 0, "playUrl": "", "url": m.group(1), "header": json.dumps(self.headers)}

            # 如果都没找到，返回播放页URL让TVBox尝试解析
            return {"parse": 1, "url": url, "header": self.headers}

        except Exception as e:
            return {"parse": 0, "playUrl": "", "url": "", "header": json.dumps(self.headers)}

    def localProxy(self, param):
        return {"code": 404, "content": ""}

    def isVideoFormat(self, url):
        return ".m3u8" in url.lower() or ".mp4" in url.lower()

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass
