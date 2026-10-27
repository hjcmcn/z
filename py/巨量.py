# -*- coding: utf-8 -*-
"""
巨量资源 - https://juliang.app (资源站 2.0, AppleCMS V10 JSON 采集接口)
接口: https://api.juliang.live/api/provide/vod/  (ac=detail/ac=list, t=分类, wd=搜索, pg=页码, h=最近小时)

结构参照用户的 秘书ai短剧.py (base.spider 基类 + 生命周期方法 + 模块级入口函数)。

相对原插件的修复:
  1. 去掉 Cookie 获取/维护逻辑 (JSON 采集接口无需 Cookie);
  2. 去掉请求限速 (接口为采集 API, 放宽为不限速, 仅保留重试退避);
  3. 搜索缓存加 TTL (120s) + 数量上限 (30 条, 淘汰最旧), 不再无限增长;
  4. 全部用 JSON 解析, 不再依赖脆弱的 HTML 正则;
  5. 翻页使用接口返回的真实 page/pagecount/total, 不再用假分页值;
  6. 域名/接口可通过 extend 的 host 字段覆盖, 方便换备用接口。

实测 (2026-10-24, 沙箱验证):
  分类: ?ac=list 返回全量 class (顶级 1-7 + 全部子分类);
  列表: ?ac=detail&t=5&pg=1 → 20 条/页, 真实 pagecount/total;
  详情: ?ac=detail&ids={id} → 含 vod_play_from/vod_play_url (名称$链接 多线路多集);
  搜索: ?wd=关键词 → 正常返回;
  播放: jlm3u8 线路为直链 smart.m3u8 (parse=0 直放), jlplayer 线路为网页链接 (parse=1 兜底)。
"""
import json
import time
from urllib.parse import quote
import requests
from base.spider import Spider


class Spider(Spider):
    name = "巨量资源"
    API_URL = "https://api.juliang.live/api/provide/vod/"
    SITE_URL = "https://juliang.app/"

    searchable = 1
    quickSearch = 1
    filterable = 1
    changeable = 1

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://juliang.app/",
    }

    play_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "*/*",
    }

    # 接口不可用时的兜底分类 (顶级)
    FALLBACK_CLASSES = [
        {"type_id": 1, "type_name": "电影"},
        {"type_id": 2, "type_name": "电视剧"},
        {"type_id": 3, "type_name": "动漫"},
        {"type_id": 4, "type_name": "综艺"},
        {"type_id": 5, "type_name": "短剧"},
        {"type_id": 6, "type_name": "体育赛事"},
        {"type_id": 7, "type_name": "AI制作"},
    ]

    FILTERS = {}

    # 搜索缓存: TTL 120s, 最多保留 30 个关键词, 超出淘汰最旧
    _SEARCH_CACHE = {}
    _SEARCH_CACHE_TTL = 120
    _SEARCH_CACHE_MAX = 30

    def __init__(self):
        super().__init__()
        self._session = requests.Session()
        self._session.headers.update(self.headers)

    def _log(self, msg):
        print(f"[{self.name}] {msg}")

    @staticmethod
    def _clean(x):
        if not x:
            return ""
        try:
            import re as _re
            x = _re.sub(r"<[^>]+>", "", str(x))
        except Exception:
            x = str(x)
        return x.replace("&nbsp;", " ").strip()

    def _get_json(self, params, max_retry=3, timeout=15):
        """请求采集接口并返回解析后的 dict, 失败返回 {}"""
        for attempt in range(max_retry):
            try:
                resp = self._session.get(self.API_URL, params=params,
                                         timeout=timeout)
                if resp.status_code == 200 and resp.text:
                    data = resp.json()
                    if isinstance(data, dict):
                        return data
                    self._log(f"接口返回异常类型: {type(data)}")
                else:
                    self._log(f"接口异常状态 {resp.status_code}")
            except Exception as e:
                self._log(f"接口请求失败({attempt + 1}/{max_retry}): {e}")
            if attempt < max_retry - 1:
                time.sleep(0.5 * (attempt + 1))
        return {}

    @staticmethod
    def _pick_vod_card(v):
        """从接口 vod 记录中提取列表页所需字段"""
        return {
            "vod_id": str(v.get("vod_id", "")),
            "vod_name": str(v.get("vod_name", "")).strip(),
            "vod_pic": str(v.get("vod_pic", "") or ""),
            "vod_remarks": str(v.get("vod_remarks", "") or "").strip(),
        }

    @classmethod
    def _class_list_from_api(cls, data):
        """从接口 class 字段构建 TVBox 分类列表 (顶级 + 子分类)"""
        classes = data.get("class") or []
        out = []
        seen = set()
        top = [c for c in classes if not c.get("type_pid")]
        subs = [c for c in classes if c.get("type_pid")]
        for c in top + subs:
            tid = str(c.get("type_id", ""))
            if not tid or tid in seen:
                continue
            seen.add(tid)
            out.append({"type_id": tid, "type_name": str(c.get("type_name", tid))})
        return out

    def init(self, extend=""):
        try:
            if extend:
                ext = json.loads(extend) if isinstance(extend, str) else extend
                if isinstance(ext, dict):
                    host = ext.get("host")
                    if host:
                        # host 可为完整接口地址或站点根地址
                        host = str(host).rstrip("/")
                        if host.endswith("/api/provide/vod"):
                            self.API_URL = host + "/"
                        elif host.endswith("/api/provide/vod/"):
                            self.API_URL = host
                        else:
                            self.API_URL = host + "/api/provide/vod/"
                        self._session.headers["Referer"] = host + "/"
        except Exception as e:
            self._log(f"解析 extend 失败: {e}")
        self._log("初始化完成")

    def getName(self):
        return self.name

    def homeContent(self, filter=False):
        data = self._get_json({"ac": "list"})
        classes = self._class_list_from_api(data)
        if not classes:
            classes = [dict(c) for c in self.FALLBACK_CLASSES]
        result = {"class": classes}
        if filter:
            result["filters"] = self.FILTERS
            result["filter"] = self.FILTERS
        return result

    def homeVideoContent(self):
        # h=24: 最近 24 小时更新的内容
        data = self._get_json({"ac": "detail", "h": 24})
        items = [self._pick_vod_card(v) for v in (data.get("list") or []) if v.get("vod_id")]
        return {"list": items[:36]}

    def categoryContent(self, tid, pg, filter=False, content=None):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1
        data = self._get_json({"ac": "detail", "t": str(tid), "pg": pg})
        items = [self._pick_vod_card(v) for v in (data.get("list") or []) if v.get("vod_id")]
        try:
            pagecount = int(data.get("pagecount") or 1)
            total = int(data.get("total") or len(items))
            limit = int(data.get("limit") or 20)
        except Exception:
            pagecount, total, limit = 1, len(items), 20
        return {"list": items, "page": pg, "pagecount": pagecount,
                "limit": limit, "total": total}

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, (list, tuple)) else ids
        data = self._get_json({"ac": "detail", "ids": str(vid)})
        raw = None
        for v in (data.get("list") or []):
            if str(v.get("vod_id")) == str(vid):
                raw = v
                break
        if not raw:
            return {"list": []}
        # vod_play_from / vod_play_url: 多线路用 $$$ 分隔, 集数用 # 分隔, 名称$链接
        froms = str(raw.get("vod_play_from", "") or "").split("$$$")
        urls = str(raw.get("vod_play_url", "") or "").split("$$$")
        pairs = [(f.strip(), u.strip()) for f, u in zip(froms, urls)
                if f.strip() and u.strip()]
        play_from = "$$$".join(f for f, _ in pairs)
        play_url = "$$$".join(u for _, u in pairs)
        vod = {
            "vod_id": str(vid),
            "vod_name": self._clean(raw.get("vod_name")),
            "vod_pic": str(raw.get("vod_pic", "") or ""),
            "type_name": str(raw.get("type_name", "") or ""),
            "vod_year": str(raw.get("vod_year", "") or ""),
            "vod_area": str(raw.get("vod_area", "") or ""),
            "vod_remarks": str(raw.get("vod_remarks", "") or ""),
            "vod_actor": self._clean(raw.get("vod_actor")),
            "vod_director": self._clean(raw.get("vod_director")),
            "vod_content": self._clean(raw.get("vod_content") or raw.get("vod_blurb")),
            "vod_play_from": play_from,
            "vod_play_url": play_url,
        }
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags=None):
        url = str(id) if str(id).startswith("http") else self.base_site() + str(id)
        header = dict(self.play_headers)
        # m3u8 直链直接播放; 其余 (如 jlplayer 网页线路) 交由嗅探/网页解析
        if ".m3u8" in url or ".mp4" in url:
            return {"parse": 0, "playUrl": "", "url": url, "header": header}
        return {"parse": 1, "playUrl": "", "url": url, "header": header}

    def base_site(self):
        return self.SITE_URL

    def searchContent(self, key, quick=False, pg="1"):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1
        ckey = (str(key), pg)
        now = time.time()
        # 清理过期与超量缓存
        hit = self._SEARCH_CACHE.get(ckey)
        if hit and now - hit[0] < self._SEARCH_CACHE_TTL:
            return hit[1]
        self._gc_search_cache(now)
        data = self._get_json({"ac": "detail", "wd": str(key), "pg": pg})
        items = [self._pick_vod_card(v) for v in (data.get("list") or []) if v.get("vod_id")]
        try:
            pagecount = int(data.get("pagecount") or 1)
            total = int(data.get("total") or len(items))
        except Exception:
            pagecount, total = 1, len(items)
        result = {"list": items, "page": pg, "pagecount": pagecount,
                  "limit": 20, "total": total}
        # 数量上限: 超出淘汰最旧
        while len(self._SEARCH_CACHE) >= self._SEARCH_CACHE_MAX:
            oldest = min(self._SEARCH_CACHE, key=lambda k: self._SEARCH_CACHE[k][0])
            self._SEARCH_CACHE.pop(oldest, None)
        self._SEARCH_CACHE[ckey] = (now, result)
        return result

    def _gc_search_cache(self, now):
        for k in [k for k, v in self._SEARCH_CACHE.items()
                  if now - v[0] >= self._SEARCH_CACHE_TTL]:
            self._SEARCH_CACHE.pop(k, None)

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        try:
            self._session.close()
        except Exception:
            pass

    def localProxy(self, param):
        return None


_spider = None


def _get_spider():
    global _spider
    if _spider is None:
        _spider = Spider()
    return _spider


def init(extend=""):
    return _get_spider().init(extend)


def homeContent(filter=False):
    return _get_spider().homeContent(filter)


def homeVideoContent():
    return _get_spider().homeVideoContent()


def categoryContent(tid, pg, filter=False, extend=None):
    return _get_spider().categoryContent(tid, pg, filter, extend)


def detailContent(ids):
    return _get_spider().detailContent(ids)


def playerContent(flag, id, vipFlags=None):
    return _get_spider().playerContent(flag, id, vipFlags)


def searchContent(key, quick=False, pg="1"):
    return _get_spider().searchContent(key, quick, pg)


def isVideoFormat(url):
    return _get_spider().isVideoFormat(url)


def manualVideoCheck():
    return _get_spider().manualVideoCheck()


def localProxy(param):
    return _get_spider().localProxy(param)
