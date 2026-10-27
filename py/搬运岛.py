# 搬运岛 OK影视/TVBox 爬虫插件 | 基于 base.spider
# 站点: https://pan.movedaos.com (Z-Blog + DiskShare 主题, 网盘资源站)
# 结构: 列表页 ds-card 卡片 / 详情页 ds-download-group 按网盘平台分组
# 建模: 网盘平台(夸克/百度) = 播放线路, 下载卡片 = 集(版本)
import re
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
requests.packages.urllib3.disable_warnings()

from base.spider import Spider


class Spider(Spider):
    # ========== 插件基础配置 ==========
    def getName(self):
        return "搬运岛"

    # ========== 初始化全局配置 ==========
    def init(self, extend=""):
        super().init(extend)
        self.site_url = "https://pan.movedaos.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Mobile Safari/537.36",
            "Referer": self.site_url,
            "Accept-Language": "zh-CN,zh;q=0.9"
        }
        self.sess = requests.Session()
        self.sess.mount("https://", HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])))
        self.sess.mount("http://", HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])))
        self.page_size = 24
        self.total = 9999
        # 分类映射: 分类ID -> (页面序号, 名称)
        self.categories = [
            {"type_name": "影视", "type_id": "2"},
            {"type_name": "动漫", "type_id": "3"},
            {"type_name": "电影", "type_id": "4"},
            {"type_name": "韩剧", "type_id": "5"},
            {"type_name": "文档", "type_id": "6"},
            {"type_name": "书籍下载", "type_id": "7"},
            {"type_name": "资料下载", "type_id": "8"},
        ]

    # ========== 通用请求方法 ==========
    def fetch(self, url, timeout=10):
        try:
            res = self.sess.get(url, headers=self.headers, timeout=timeout, verify=False)
            res.encoding = "utf-8"
            return res
        except Exception as e:
            return None

    # ========== 工具方法: 解析 ds-card 列表卡片 ==========
    def _parse_cards(self, html):
        """从列表页 HTML 提取 ds-card 卡片, 返回视频列表
        注意: 搜索页标题带 <strong> 高亮, 需剥离 HTML 标签
        """
        video_list = []
        for m in re.finditer(r'<article class="ds-card".*?</article>', html, re.S):
            block = m.group(0)
            # 详情链接 (vod_id)
            href = re.search(r'href="(https://pan\.movedaos\.com/post/\d+\.html)"', block)
            # 标题: 优先 ds-card__title 内 itemprop=name, 兜底 cover-link title
            name_m = re.search(r'<span itemprop="name">(.*?)</span>', block)
            if not name_m:
                name_m = re.search(r'class="ds-card__cover-link"[^>]*title="([^"]*)"', block)
            # 封面: 取 block 内第一个 src (封面 img 的 src 在 alt 之前, 不受高亮标签干扰)
            pic_m = re.search(r'<img[^>]*\bsrc="([^"]+)"', block)
            # 评分徽标
            badge_m = re.search(r'ds-card__badge">([^<]*)</span>', block)
            if href and name_m and pic_m:
                vod_id = href.group(1)
                vod_name = re.sub(r'<[^>]+>', '', name_m.group(1)).strip()
                pic_url = pic_m.group(1)
                if pic_url.startswith("//"):
                    pic_url = "https:" + pic_url
                elif not pic_url.startswith(("http://", "https://")):
                    pic_url = self.site_url + (pic_url if pic_url.startswith("/") else "/" + pic_url)
                video_list.append({
                    "vod_id": vod_id,
                    "vod_name": vod_name,
                    "vod_pic": pic_url,
                    "vod_remarks": badge_m.group(1).strip() if badge_m else "",
                    "style": {"type": "rect", "ratio": 1.33}
                })
        return video_list

    # ========== 首页分类接口 ==========
    def homeContent(self, filter):
        return {"class": self.categories}

    # ========== 分类列表接口 ==========
    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg) if str(pg).isdigit() else 1
        # Z-Blog 分页: 第1页 category-N.html, 第2页起 category-N_2.html
        if pg <= 1:
            list_url = f"{self.site_url}/category-{tid}.html"
        else:
            list_url = f"{self.site_url}/category-{tid}_{pg}.html"
        res = self.fetch(list_url)
        video_list = []
        if res and res.ok:
            video_list = self._parse_cards(res.text)
        pagecount = pg + 1 if len(video_list) else pg
        return {
            "list": video_list,
            "page": pg,
            "pagecount": pagecount,
            "limit": self.page_size,
            "total": self.total
        }

    # ========== 视频详情接口 ==========
    def detailContent(self, ids):
        vod_id = ids[0] if ids else ""
        if not vod_id:
            return {"list": [{"vod_name": "视频ID为空"}]}
        res = self.fetch(vod_id)
        if res and res.ok:
            html = res.text
            # 标题: og:title / twitter:title / <title>
            name = ""
            tm = re.search(r'property="og:title" content="([^"]*)"', html)
            if tm:
                name = tm.group(1).strip()
            else:
                tm2 = re.search(r'<title>([^<]*)</title>', html)
                if tm2:
                    name = re.sub(r'\s*-\s*搬运岛\s*$', '', tm2.group(1)).strip()
            # 封面: og:image
            pic = ""
            pm = re.search(r'property="og:image" content="([^"]*)"', html)
            if pm:
                pic = pm.group(1).strip()
            # 简介: og:description
            content = ""
            cm = re.search(r'property="og:description" content="([^"]*)"', html)
            if cm:
                content = cm.group(1).strip()
            # 解析下载分组: ds-download-group 可能带标题(平台名)也可能不带
            play_from = []
            play_url_map = {}  # 平台 -> [名称$url]
            group_title = None
            # 按 ds-download-card 遍历, 用 data-pvr-platform 提取平台
            for cm2 in re.finditer(
                r'<article class="ds-download-card">.*?'
                r'<h4 class="ds-download-card__name" title="([^"]*)"[^>]*>.*?'
                r'<a href="(https?://[^"]+)"[^>]*data-pvr-platform="([^"]*)"',
                html, re.S):
                card_name = cm2.group(1).strip()
                link = cm2.group(2).strip()
                platform = cm2.group(3).strip() or group_title or "网盘"
                play_url_map.setdefault(platform, []).append(f"{card_name}${link}")
            # 组标题兜底(个别模板可能只用 h3 分组不带 data 属性)
            for gm in re.finditer(r'<h3 class="ds-download-group__title">([^<]*)</h3>', html):
                group_title = gm.group(1).strip()
            if play_url_map:
                play_from = list(play_url_map.keys())
                # TVBox 多线路格式: 线路间用 $$$ 分隔, 线路内资源用 # 分隔, 资源名与地址用 $ 分隔
                lines = []
                for p in play_from:
                    lines.append("#".join(play_url_map[p]))
                play_url = "$$$".join(lines)
            else:
                # 兜底: 直接抓所有 ds-btn--dl 链接
                dls = re.findall(r'<a href="(https?://[^"]+)"[^>]*class="ds-btn[^"]*ds-btn--dl"', html)
                if dls:
                    play_from = ["网盘"]
                    play_url = "#".join([f"资源{i+1}${u}" for i, u in enumerate(dls)])
                else:
                    play_from = []
                    play_url = ""
            detail_info = {
                "vod_id": vod_id,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": "",
                "type_name": "",
                "vod_content": content,
                "vod_play_from": "$".join(play_from),
                "vod_play_url": play_url
            }
            return {"list": [detail_info]}
        return {"list": [{"vod_id": vod_id, "vod_name": "视频详情解析失败"}]}

    # ========== 搜索接口 ==========
    def searchContent(self, key, quick, pg=1):
        pg = int(pg) if str(pg).isdigit() else 1
        search_url = f"{self.site_url}/search.php?act=Search&q={requests.utils.quote(key)}"
        res = self.fetch(search_url)
        video_list = []
        if res and res.ok:
            video_list = self._parse_cards(res.text)
        pagecount = pg + 1 if len(video_list) else pg
        return {
            "list": video_list,
            "page": pg,
            "pagecount": pagecount,
            "limit": self.page_size,
            "total": len(video_list) if len(video_list) < self.total else self.total
        }

    # ========== 播放解析接口 ==========
    def playerContent(self, flag, id, vipFlags):
        play_url = id.split("$")[1] if "$" in id else id
        if not play_url:
            return {"parse": 0, "url": "", "header": self.headers}
        # 网盘分享链接: 无需二次解析, 交由网盘播放器/解析器处理
        return {
            "parse": 0,
            "url": play_url,
            "header": self.headers
        }
