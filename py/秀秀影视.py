# coding=utf-8
# !/usr/bin/python
"""
秀秀影院  https://hsrl.ypisp.com
MacCMS(v10系, ptv5/tv22模板) 伪静态路由  (T4 六接口)

路由形态(已实测):
  分类  /ph/{tid}.html            每页 10 条
        分页  /ph/{tid}-{pg}.html  上限 500 页(501 即 404)
  详情  /ysdq/{vid}.html          内嵌播放列表 /watch/{vid}-{src}-{ep}.html
  播放  /watch/{vid}-{src}-{ep}.html 内 iframe
        api.cssstatic.com/?url=<URL编码m3u8>  -> 解出直链 m3u8
        实测 master/子列表/分片 均 200 可播; 分片需带 Referer(播放头携带)

注意:
  首页 /index.php 有 _guard 类频率防护(偶发 200, 随后 404), 因此
  homeVideoContent 直接取主分类 ph/1(电影) 第 1 页作推荐列表, 稳定可访问.
  站点端搜索已禁用(qrsearch 未定义 + 全部搜索路由 404), searchContent
  返回空列表(如实反映站点能力, 不伪造).

分类(5主+13子):
  1电影 2连续剧 3综艺 4动漫 45短剧漫剧
  6动作 7喜剧 8爱情 9科幻 10恐怖 11剧情 12战争 17纪录片
  28悬疑 29动画 30犯罪 31奇幻 32邵氏
"""

import re
import sys
from urllib.parse import unquote, urljoin

import requests

from base.spider import Spider

sys.path.append("..")

DEFAULT_HOST = "https://hsrl.ypisp.com"

# (type_id, type_name) 主分类 + 子分类, 与站端导航一致
CATEGORIES = [
    ("1", "电影"), ("2", "连续剧"), ("3", "综艺"), ("4", "动漫"),
    ("45", "短剧漫剧"),
    ("6", "动作片"), ("7", "喜剧片"), ("8", "爱情片"),
    ("9", "科幻片"), ("10", "恐怖片"), ("11", "剧情片"),
    ("12", "战争片"), ("17", "纪录片"), ("28", "悬疑片"),
    ("29", "动画片"), ("30", "犯罪片"), ("31", "奇幻片"), ("32", "邵氏电影"),
]

MAX_PAGE = 500  # 站端分类分页上限(实测 501 页即 404)
EMPTY_RESULT_PAGES = 1  # 搜索禁用时空结果页数(如实表达, 非伪分页)


class Spider(Spider):
    def getName(self):
        return "秀秀影院"

    def init(self, extend=""):
        host = (extend or "").strip().rstrip("/") or DEFAULT_HOST
        if not host.startswith("http"):
            host = "https://" + host
        self.host = host
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
                "Mobile/15E148 Safari/604.1"
            ),
            "Referer": self.host + "/",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    # ------------------------------------------------------------------ #
    #  内部工具
    # ------------------------------------------------------------------ #

    def _get(self, url):
        """GET 页面文本, 失败返回空串"""
        try:
            r = self.session.get(url, timeout=15)
            r.raise_for_status()
            r.encoding = r.apparent_encoding or "utf-8"
            return r.text
        except Exception:
            return ""

    def _pic(self, url):
        url = str(url or "").strip()
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("http"):
            return url
        return urljoin(self.host + "/", url)

    @staticmethod
    def _clean(html_text):
        """去除 HTML 标签 / 空白, 返回纯文本"""
        if not html_text:
            return ""
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html_text)).strip()

    def _probe_media(self, url):
        """真直链门禁: m3u8 必须返回含 #EXTM3U 的响应, mp4 需 video/ftyp 指纹"""
        try:
            r = self.session.get(url, timeout=10, stream=True)
            data = next(r.iter_content(4096), b"")
            ctype = (r.headers.get("Content-Type") or "").lower()
            if not r.ok:
                return ""
            if b"#EXTM3U" in data:
                return url
            if "video/" in ctype or data[4:12].find(b"ftyp") >= 0:
                return url
        except Exception:
            pass
        return ""

    # ------------------------------------------------------------------ #
    #  列表解析
    # ------------------------------------------------------------------ #

    def _parse_list(self, html):
        """分类/推荐页条目: href, 标题, 海报(data-tpl-bg), 评分(pic-tag), 备注(pic-text)"""
        out = []
        seen = set()
        for m in re.finditer(
            r'<a href="(/ysdq/(\d+)\.html)" class="myui-vodlist__thumb" '
            r'title="([^"]*)" data-tpl-bg="([^"]+)">(.*?)</a>',
            html,
            re.S,
        ):
            vid = m.group(2)
            if vid in seen:
                continue
            seen.add(vid)
            title = self._clean(m.group(3)).replace("在线观看", "").strip()
            pic = self._pic(m.group(4))
            inner = m.group(5)
            tag_m = re.search(r'pic-tag[^"]*"[^>]*>([^<]+)', inner)
            txt_m = re.search(r'pic-text[^"]*"[^>]*>([^<]+)', inner)
            remarks = ""
            if txt_m:
                remarks = self._clean(txt_m.group(1))
            elif tag_m:
                remarks = self._clean(tag_m.group(1))
            item = {
                "vod_id": vid,
                "vod_name": title or vid,
                "vod_pic": pic,
            }
            if remarks:
                item["vod_remarks"] = remarks
            out.append(item)
        return out

    # ------------------------------------------------------------------ #
    #  六接口
    # ------------------------------------------------------------------ #

    def homeContent(self, filter):
        return {
            "class": [{"type_id": t, "type_name": n} for t, n in CATEGORIES],
            "filters": {},
        }

    def homeVideoContent(self):
        # 首页 /index.php 有频率防护, 用主分类"电影"第 1 页作推荐列表
        html = self._get("%s/ph/1.html" % self.host)
        return {"list": self._parse_list(html)[:30]}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = max(1, int(pg or 1))
        except (TypeError, ValueError):
            page = 1
        page = min(page, MAX_PAGE)
        url = "%s/ph/%s.html" % (self.host, tid)
        if page > 1:
            url = "%s/ph/%s-%d.html" % (self.host, tid, page)
        html = self._get(url)
        items = self._parse_list(html)
        return {
            "page": page,
            "pagecount": MAX_PAGE,
            "limit": len(items) or 10,
            "total": MAX_PAGE * 10,
            "list": items,
        }

    def searchContent(self, key, quick=False, pg="1"):
        # 站点端搜索已禁用(实测全部搜索路由 404, qrsearch 未定义), 如实返回空
        page = EMPTY_RESULT_PAGES
        return {"list": [], "page": page, "pagecount": page, "limit": 0, "total": 0}

    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, (list, tuple)) else ids)
        html = self._get("%s/ysdq/%s.html" % (self.host, vid))
        if not html:
            return {"list": []}

        # 标题
        name = ""
        m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = re.search(r"og:title\" content=\"([^\"]+)\"", html)
            if m:
                name = self._clean(m.group(1))
        if not name:
            m = re.search(r"<title>(.*?)</title>", html)
            if m:
                name = self._clean(m.group(1)).split("_")[0].strip()

        # 海报
        pic = ""
        m = re.search(r'og:image" content="([^"]+)"', html)
        if m:
            pic = self._pic(m.group(1))
        if not pic:
            m = re.search(r'data-tpl-bg="(https?://[^"]+)"', html)
            if m:
                pic = self._pic(m.group(1))

        # 简介: 详情正文区 (含简介/剧情这类长文本的 div)
        content = ""
        for pat in (
            r'<div[^>]*class="[^"]*(?:content|detail|intro)[^"]*"[^>]*>(.*?)</div>',
            r'<p[^>]*class="[^"]*(?:content|intro)[^"]*"[^>]*>(.*?)</p>',
        ):
            m = re.search(pat, html, re.S)
            if m:
                txt = self._clean(m.group(1))
                if len(txt) > 20:
                    content = txt
                    break

        # 播放列表: 每个播放源(tab) 对应一组 /watch/{vid}-{src}-{ep}.html
        sources = []  # [(flag_name, [(ep_name, url), ...]), ...]
        tabs = list(
            re.finditer(r'<a href="#(playlist\d+)"[^>]*data-toggle="tab">([^<]+)</a>', html)
        )
        seen_pids = set()
        for t in tabs:
            pid, flag = t.group(1), self._clean(t.group(2))
            if pid in seen_pids:
                continue
            seen_pids.add(pid)
            # 找该 playlist div 的完整内容
            blk_m = re.search(
                r'<div id="%s"[^>]*>(.*?)(?=<div id="playlist|\Z)' % pid,
                html[t.end():],
                re.S,
            )
            if not blk_m:
                continue
            seg = blk_m.group(1)
            eps = []
            for em in re.finditer(r'href="(/watch/[\d-]+\.html)"[^>]*>\s*([^<]{1,16})\s*', seg):
                eps.append((em.group(2).strip(), "%s%s" % (self.host, em.group(1))))
            eps = list(dict.fromkeys(eps))  # 去重保序
            if eps:
                sources.append((flag or pid, eps))

        # 组装 flag / play_url (线路内 # 分隔集, 线路间 $$$ 分隔)
        play_from = "$$$".join(flag for flag, _ in sources)
        play_parts = []
        for _, eps in sources:
            play_parts.append("#".join("%s$%s" % (n, u) for n, u in eps))
        play_url = "$$$".join(play_parts)

        return {
            "list": [
                {
                    "vod_id": vid,
                    "vod_name": name or vid,
                    "vod_pic": pic,
                    "vod_content": content,
                    "vod_play_from": play_from,
                    "vod_play_url": play_url,
                }
            ]
        }

    def playerContent(self, flag, id, vipFlags=None):
        play = str(id or "")
        if "$" in play:
            play = play.split("$", 1)[-1]
        # 播放页 iframe: <iframe src="https://api.cssstatic.com/?url=<编码m3u8>">
        m3u8 = ""
        if play.startswith("http"):
            html = self._get(play)
            fm = re.search(r'<iframe[^>]+src="(https?://api\.cssstatic\.com/\?url=([^"]+))"', html)
            if fm:
                m3u8 = unquote(fm.group(2))
            if not m3u8:
                # 兜底: 任意 api.cssstatic iframe
                fm = re.search(r'<iframe[^>]+src="([^"]*cssstatic[^"]*)"', html)
                if fm:
                    mm = re.search(r"url=([^&\"']+)", fm.group(1))
                    if mm:
                        m3u8 = unquote(mm.group(1))
        if not m3u8:
            m3u8 = play
        # 真直链门禁: 仅当响应确认为 m3u8/mp4 媒体时才报 parse:0, 否则回退兜底
        final_url = self._probe_media(m3u8)
        if not final_url:
            final_url = m3u8
        return {
            "parse": 0,
            "jx": 0,
            "playUrl": "",
            "url": final_url,
            "header": {
                "User-Agent": self.headers["User-Agent"],
                "Referer": self.host + "/",
            },
        }

    def localProxy(self, params):
        return [200, "text/plain", b"ok"]