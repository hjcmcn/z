# -*- coding: utf-8 -*-
# @Author: Spider
# @Date: 2026-08-24
# @Description: PaPa视频 TVBox py源

import sys
import re
import json
import random
import time
from datetime import datetime
from urllib.parse import urljoin
sys.path.append("..")
from base.spider import Spider


class Spider(Spider):
    def __init__(self):
        super().__init__()
        self.pub_url = "http://ojxmjdmfsa.744tv.com/"
        self.domains = []       # 从发布页提取的域名列表
        self.base_url = ""      # 当前可用的基础URL（已清理随机参数）
        self.header = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "http://ojxmjdmfsa.744tv.com/",
        }
        self.cache_ttl = 1800   # 域名缓存30分钟
        self.cache_time = 0

    def getName(self):
        return "PaPa视频"

    def init(self, extend=""):
        pass

    def isVideoFormat(self, url):
        return True

    def manualVideoCheck(self):
        pass

    def _fetch(self, url, timeout=15):
        """统一请求封装"""
        try:
            resp = self.fetch(url, headers=self.header, timeout=timeout)
            return resp
        except Exception as e:
            self.log(f"请求失败: {url} -> {e}")
            return None

    def _get_domains(self):
        """从发布页提取域名列表"""
        resp = self._fetch(self.pub_url)
        if not resp:
            return ["duduo.vip", "dudu2.vip"]
        html = resp.text if hasattr(resp, 'text') else resp
        # 匹配 JS 中的域名，如 .duduo.vip/6? 或 .dudu2.vip/6?
        domains = re.findall(r'\.([a-z0-9]+\.vip)/6\?', html)
        # 去重保序
        seen = set()
        result = []
        for d in domains:
            if d not in seen:
                seen.add(d)
                result.append(d)
        if not result:
            result = ["duduo.vip", "dudu2.vip"]
        return result

    def _verify_domain(self, domain):
        """验证单个域名是否可用，返回True/False"""
        year_month = datetime.now().strftime("%Y%m")
        rand_str = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=10))
        test_url = f"http://{year_month}.{domain}/6?{rand_str}"
        try:
            resp = self._fetch(test_url, timeout=10)
            if not resp:
                return False
            html = resp.text if hasattr(resp, 'text') else resp
            # 检查是否有影片列表特征
            if 'stui-vodlist__item' in html or 'player_data' in html:
                return True
        except Exception as e:
            self.log(f"验证失败: {test_url} -> {e}")
        return False

    def _ensure_base_url(self, force=False):
        """确保有可用的基础URL（不带随机参数）"""
        now = time.time()
        if not force and self.base_url and (now - self.cache_time) < self.cache_ttl:
            return self.base_url

        self.domains = self._get_domains()
        self.log(f"从发布页提取域名: {self.domains}")
        year_month = datetime.now().strftime("%Y%m")

        for domain in self.domains:
            if self._verify_domain(domain):
                # 只保留干净的基础路径，去掉随机参数
                self.base_url = f"http://{year_month}.{domain}/6/"
                self.cache_time = now
                self.log(f"使用域名: {self.base_url}")
                return self.base_url

        # 全部失败，fallback 硬编码
        self.base_url = f"http://{year_month}.duduo.vip/6/"
        self.cache_time = now
        self.log(f"Fallback域名: {self.base_url}")
        return self.base_url

    def _get_full_url(self, path):
        """拼接完整URL"""
        base = self._ensure_base_url()
        if path.startswith("http"):
            return path
        return urljoin(base, path)

    def _parse_videos(self, html):
        """解析影片列表"""
        videos = []
        # 按 <li class="stui-vodlist__item"> 块分割
        blocks = re.split(r'<li class="stui-vodlist__item">', html)
        for block in blocks[1:]:
            # 标题
            title_match = re.search(r'title="([^"]+)"', block)
            title = title_match.group(1) if title_match else ""
            # 图片
            img_match = re.search(r'data-original="([^"]+)"', block)
            pic = img_match.group(1) if img_match else ""
            # 链接
            link_match = re.search(r'<a[^>]+href="(/6/index\.php/vod/play/id/\d+/sid/\d+/nid/\d+\.html)"', block)
            if not link_match:
                link_match = re.search(r'href="(/6/index\.php/vod/play/id/\d+/sid/\d+/nid/\d+\.html)"', block)
            if link_match and title:
                link = link_match.group(1)
                # 提取ID
                id_match = re.search(r'/id/(\d+)/', link)
                vid = id_match.group(1) if id_match else link
                videos.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": "",
                })
        return videos

    def homeContent(self, filter):
        """首页内容"""
        base = self._ensure_base_url()
        resp = self._fetch(base)
        if not resp:
            return {"class": [], "list": []}
        html = resp.text if hasattr(resp, 'text') else resp

        # 提取分类
        classes = []
        nav_items = re.findall(
            r'<a href="/6/index\.php/vod/type/id/(\d+)\.html"><strong>([^<]+)</strong></a>',
            html
        )
        for cate_id, cate_name in nav_items:
            classes.append({"type_id": cate_id, "type_name": cate_name})

        # 提取首页影片
        videos = self._parse_videos(html)

        return {"class": classes, "list": videos}

    def homeVideoContent(self):
        """首页推荐"""
        return self.homeContent(None)

    def categoryContent(self, tid, pg, filter, extend):
        """分类内容"""
        base = self._ensure_base_url()
        url = f"{base}index.php/vod/type/id/{tid}/page/{pg}.html"
        resp = self._fetch(url)
        if not resp:
            return {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}
        html = resp.text if hasattr(resp, 'text') else resp

        videos = self._parse_videos(html)

        # 提取总页数
        pagecount = int(pg)
        last_match = re.search(r'page/(\d+)\.html[^>]*>尾页', html)
        if last_match:
            pagecount = int(last_match.group(1))
        else:
            # 尝试其他翻页标记
            pages = re.findall(r'page/(\d+)\.html', html)
            if pages:
                pagecount = max(int(p) for p in pages)

        return {
            "list": videos,
            "page": int(pg),
            "pagecount": pagecount,
            "limit": 24,
            "total": pagecount * 24,
        }

    def detailContent(self, ids):
        """详情内容（直接获取播放地址）"""
        vid = ids[0]
        base = self._ensure_base_url()
        url = f"{base}index.php/vod/play/id/{vid}/sid/1/nid/1.html"
        resp = self._fetch(url)
        if not resp:
            return {"list": []}
        html = resp.text if hasattr(resp, 'text') else resp

        # 提取 player_data
        pd_match = re.search(r'var player_data=({.+?})</script>', html)
        if not pd_match:
            return {"list": []}

        try:
            player_data = json.loads(pd_match.group(1))
        except Exception:
            return {"list": []}

        play_url = player_data.get("url", "")
        title = ""
        pic = ""
        # 尝试从页面提取标题和图片
        title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        if title_match:
            title = title_match.group(1).strip()
        if not title:
            title_match = re.search(r'<title>([^<]+)</title>', html)
            if title_match:
                title = title_match.group(1).strip().split("-")[0].strip()

        pic_match = re.search(r'data-original="([^"]+)"', html)
        if pic_match:
            pic = pic_match.group(1)

        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": "",
            "vod_content": title,
            "vod_play_from": "PaPa",
            "vod_play_url": f"PaPa${play_url}",
        }
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags):
        """播放内容"""
        return {
            "parse": 0,
            "url": id,
            "header": self.header,
        }

    def searchContent(self, key, quick, pg=1):
        """搜索内容"""
        base = self._ensure_base_url()
        url = f"{base}index.php/vod/search/page/{pg}/wd/{key}.html"
        resp = self._fetch(url)
        if not resp:
            return {"list": []}
        html = resp.text if hasattr(resp, 'text') else resp
        videos = self._parse_videos(html)
        return {"list": videos, "page": pg}

    def searchContentPage(self, key, quick, pg):
        return self.searchContent(key, quick, pg)

    def localProxy(self, param):
        """本地代理"""
        return [200, "video/MP2T", "", ""]

    def log(self, msg):
        print(f"[{self.getName()}] {msg}")
