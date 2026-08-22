# coding=utf-8
# !/usr/bin/python
"""
红果短剧 TVBox / OK影视 / 影视仓 Python 源。

合并优化点：
1. 参考模板动态读取红果官网 selectorList，自动生成标准筛选器。
2. 保留底部分类入口：热门短剧、全部短剧、官网背景分类。
3. 不依赖播放桥，播放时直接解析官方播放器页 video_player_info.main_url。
4. 只展示官网网页端当前可访问的集数，避免后续未开放集数点开 404 黑屏。
5. 播放直链失败时回退 parse=1，交给 OK影视/影视仓通用解析。
"""

import json
import math
import re
import sys
import time
from urllib.parse import quote, urlencode

import requests

sys.path.append("..")
sys.path.append("../../")
try:
    from base.spider import Spider
except ImportError:
    class Spider:
        pass


class Spider(Spider):
    def __init__(self):
        self.host = "https://hongguoduanju.com"
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 12; TV) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
            ),
            "Referer": self.host + "/",
            "Origin": self.host,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        self.timeout = 20
        self.page_size = 30
        self._cache = {}
        self.class_list = []
        self.search_pool = []

    def getName(self):
        return "红果短剧"

    def init(self, extend=""):
        return

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return

    def homeContent(self, filter):
        data = self._router_data(self.host + "/category?sort_type=1") or {}
        page = self._pick_page(data, "category_page")
        selector_list = page.get("selectorList") or []
        filters = self._build_filters(selector_list)

        classes = [
            {"type_id": "home", "type_name": "热门短剧"},
            {"type_id": "all", "type_name": "全部短剧"},
        ]

        if selector_list:
            for item in selector_list[0].get("items", []):
                name = item.get("show_name")
                value = item.get("selector_item_id")
                if name and value:
                    classes.append({"type_id": str(value), "type_name": str(name)})

        self.class_list = classes
        result = {
            "class": classes,
            "list": self.homeVideoContent().get("list", []),
        }
        if filter:
            result["filters"] = filters
        return result

    def homeVideoContent(self):
        try:
            data = self._router_data(self.host + "/") or {}
            page = self._pick_page(data, "page")
            videos = page.get("videoList") or []
            if not videos:
                videos = self._category_items({"sort_type": "1"})
            return {"list": self._vod_list(videos[:self.page_size])}
        except Exception as exc:
            print("红果首页读取失败:", exc)
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        page_num = self._safe_int(pg, 1)
        try:
            if str(tid) == "home":
                data = self._router_data(self.host + "/") or {}
                page = self._pick_page(data, "page")
                videos = page.get("videoList") or []
                if not videos:
                    videos = self._category_items({"sort_type": "1"})
            else:
                query = self._category_query(tid, extend or {})
                videos = self._category_items(query)

            total = len(videos)
            start = (page_num - 1) * self.page_size
            end = start + self.page_size
            return {
                "page": page_num,
                "pagecount": max(1, int(math.ceil(total / float(self.page_size)))) if total else 1,
                "limit": self.page_size,
                "total": total,
                "list": self._vod_list(videos[start:end]),
            }
        except Exception as exc:
            print("红果分类读取失败:", exc)
            return {"list": [], "page": page_num, "pagecount": page_num}

    def detailContent(self, ids):
        sid = ids[0] if isinstance(ids, list) else ids
        try:
            data = self._router_data(self.host + "/detail?series_id=" + quote(str(sid))) or {}
            page = self._pick_page(data, "detail_page")
            detail = page.get("seriesDetail") or {}
            if not detail:
                return {"list": []}

            sid = str(detail.get("series_id") or sid)
            name = detail.get("series_name") or ""
            pic = detail.get("series_cover") or ""
            intro = detail.get("series_intro") or ""
            tags = detail.get("tags") or []

            actors = []
            for item in detail.get("celebrities") or []:
                actor = item.get("nickname") or ""
                role = item.get("sub_title") or ""
                if actor:
                    actors.append(actor + ((" " + role) if role else ""))

            vids = [str(x) for x in (detail.get("vid_list") or []) if str(x)]
            total = self._safe_int(detail.get("episode_cnt") or len(vids), len(vids))
            accessible_count = self._safe_int(detail.get("accessible_episode_cnt") or 0, 0)
            if accessible_count <= 0 or accessible_count > len(vids):
                accessible_count = len(vids)

            playable_vids = vids[:accessible_count]
            play_urls = [
                "第%s集$%s|%s" % (index, sid, vid)
                for index, vid in enumerate(playable_vids, 1)
            ]

            tag_text = " / ".join([str(x) for x in tags[:4]]) if isinstance(tags, list) else str(tags)
            remark = "可播%s集/全%s集" % (len(playable_vids), total) if total else ""

            vod = {
                "vod_id": sid,
                "vod_name": name,
                "vod_pic": pic,
                "type_name": tag_text,
                "vod_year": "",
                "vod_area": "大陆",
                "vod_remarks": remark,
                "vod_actor": " / ".join(actors),
                "vod_director": "",
                "vod_content": intro,
                "vod_play_from": "红果直连",
                "vod_play_url": "#".join(play_urls),
            }
            return {"list": [vod]}
        except Exception as exc:
            print("红果详情读取失败:", exc)
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        page_num = self._safe_int(pg, 1)
        keyword = str(key or "").strip().lower()
        if not keyword:
            return {"list": [], "page": page_num}

        try:
            pool = self._get_search_pool()
            matched = []
            exists = set()
            for item in pool:
                sid = str(item.get("series_id") or "")
                if not sid or sid in exists:
                    continue
                text = " ".join([
                    str(item.get("series_name") or ""),
                    str(item.get("series_intro") or ""),
                    " ".join([str(x) for x in (item.get("tags") or [])]),
                ]).lower()
                if keyword in text:
                    matched.append(item)
                    exists.add(sid)

            total = len(matched)
            start = (page_num - 1) * self.page_size
            end = start + self.page_size
            return {
                "page": page_num,
                "pagecount": max(1, int(math.ceil(total / float(self.page_size)))) if total else 1,
                "limit": self.page_size,
                "total": total,
                "list": self._vod_list(matched[start:end]),
            }
        except Exception as exc:
            print("红果搜索失败:", exc)
            return {"list": [], "page": page_num}

    def searchContentPage(self, key, quick, pg):
        return self.searchContent(key, quick, pg)

    def playerContent(self, flag, pid, vipFlags):
        sid, vid = self._split_play_id(pid)
        if not sid:
            return {"parse": 1, "playUrl": "", "url": str(pid or "")}

        page_url = self.host + "/player/" + quote(sid)
        if vid:
            page_url += "/" + quote(vid)

        try:
            data = self._router_data(page_url) or {}
            info = self._first_value_by_key(data.get("loaderData") or {}, "video_player_info") or {}
            play_url = str(info.get("main_url") or info.get("backup_url") or "")
            poster = str(info.get("poster_url") or "")

            if play_url:
                return {
                    "parse": 0,
                    "playUrl": "",
                    "url": play_url,
                    "header": {
                        "User-Agent": self.headers["User-Agent"],
                        "Referer": page_url,
                        "Origin": self.host,
                    },
                    "jx": 0,
                    "pic": poster,
                }
        except Exception as exc:
            print("红果直链解析失败，尝试通用解析:", exc)

        return {
            "parse": 1,
            "playUrl": "",
            "url": page_url,
            "header": {
                "User-Agent": self.headers["User-Agent"],
                "Referer": self.host + "/",
            },
        }

    def localProxy(self, params):
        return [404, "text/plain", "not found"]

    def _router_data(self, url):
        cached = self._cache.get(url)
        if cached and time.time() - cached[0] < 300:
            return cached[1]

        response = requests.get(url, headers=self.headers, timeout=self.timeout)
        response.raise_for_status()
        response.encoding = "utf-8"
        match = re.search(
            r"window\._ROUTER_DATA\s*=\s*(\{.*?\})\s*</script>",
            response.text,
            re.S,
        )
        if not match:
            return {}

        data = json.loads(match.group(1))
        self._cache[url] = (time.time(), data)
        return data

    def _pick_page(self, router_data, preferred):
        loader = (router_data or {}).get("loaderData") or {}
        if isinstance(loader.get(preferred), dict):
            return loader.get(preferred) or {}
        for key, value in loader.items():
            if isinstance(value, dict) and key.endswith("/page"):
                return value
        for value in loader.values():
            if isinstance(value, dict):
                return value
        return {}

    def _build_filters(self, selector_list):
        key_map = {
            1: ("background", "背景"),
            2: ("topic", "主题"),
            3: ("setting", "设定"),
            4: ("gender", "受众"),
            5: ("time", "时间"),
            6: ("sort_type", "排序"),
        }

        values = []
        for row in selector_list or []:
            row_id = row.get("row_id")
            key, name = key_map.get(row_id, ("row_%s" % row_id, row.get("row_name") or "筛选"))
            value = [{"n": "全部", "v": ""}]
            for item in row.get("items") or []:
                n = item.get("show_name")
                v = item.get("selector_item_id")
                if n and v is not None:
                    value.append({"n": str(n), "v": str(v)})
            if len(value) > 1:
                values.append({"key": key, "name": name, "value": value})

        filters = {"home": values, "all": values}
        for cls in self.class_list:
            tid = cls.get("type_id")
            if tid:
                filters[str(tid)] = values
        if selector_list:
            for item in selector_list[0].get("items", []):
                tid = item.get("selector_item_id")
                if tid:
                    filters[str(tid)] = values
        return filters

    def _category_query(self, tid, extend):
        query = {}
        data = extend if isinstance(extend, dict) else {}
        for key in ("background", "topic", "setting", "gender", "time", "sort_type"):
            value = data.get(key)
            if value is not None and str(value) != "":
                query[key] = str(value)

        tid = str(tid or "")
        if tid == "all":
            if not query.get("sort_type"):
                query["sort_type"] = "1"
            return query

        if tid.startswith("cate_") and not query.get("background"):
            query["background"] = tid
        elif "=" in tid:
            key, value = tid.split("=", 1)
            if key and value:
                query[key] = value

        if not query.get("sort_type"):
            query["sort_type"] = "1"
        return query

    def _category_items(self, query):
        if isinstance(query, dict):
            url = self.host + "/category"
            if query:
                url += "?" + urlencode(query)
        else:
            text = str(query or "")
            url = self.host + "/category" + (("?" + text) if text else "")

        data = self._router_data(url) or {}
        page = self._pick_page(data, "category_page")
        items = page.get("recommendList") or []
        if not items:
            category_data = page.get("categoryData") or {}
            if isinstance(category_data, dict):
                items = category_data.get("recommendList") or []

        seen = set()
        result = []
        for item in items:
            sid = str(item.get("series_id") or "")
            if sid and sid not in seen:
                seen.add(sid)
                result.append(item)
        return result

    def _vod_list(self, videos):
        result = []
        for item in videos or []:
            sid = str(item.get("series_id") or "")
            if not sid:
                continue

            tags = item.get("tags") or []
            tag_text = " / ".join([str(x) for x in tags[:2]]) if isinstance(tags, list) else str(tags)
            remark = item.get("episode_right_text") or ""
            if not remark:
                count = item.get("episode_cnt") or len(item.get("vid_list") or [])
                remark = ("全%s集" % count) if count else tag_text
            elif tag_text:
                remark = remark + " · " + tag_text

            result.append({
                "vod_id": sid,
                "vod_name": item.get("series_name") or "",
                "vod_pic": (
                    item.get("series_cover")
                    or item.get("background_cover")
                    or item.get("background_cover_mobile")
                    or ""
                ),
                "vod_remarks": remark,
                "vod_content": item.get("series_intro") or "",
            })
        return result

    def _get_search_pool(self):
        if self.search_pool:
            return self.search_pool

        pool = []
        for url, preferred, key in [
            (self.host + "/", "page", "videoList"),
            (self.host + "/category?sort_type=1", "category_page", "recommendList"),
            (self.host + "/category?sort_type=2", "category_page", "recommendList"),
        ]:
            try:
                data = self._router_data(url) or {}
                page = self._pick_page(data, preferred)
                pool.extend(page.get(key) or [])
            except Exception:
                pass

        self.search_pool = pool
        return pool

    def _split_play_id(self, play_id):
        raw = str(play_id or "")
        if "|" in raw:
            sid, vid = raw.split("|", 1)
            return sid.strip(), vid.strip()
        if "@@@" in raw:
            sid, vid = raw.split("@@@", 1)
            return sid.strip(), vid.strip()
        parts = raw.strip("/").split("/")
        if len(parts) >= 2 and parts[-2].isdigit():
            return parts[-2], parts[-1]
        if parts and parts[-1].isdigit():
            return parts[-1], ""
        return raw, ""

    def _safe_int(self, value, default=0):
        try:
            return int(value)
        except Exception:
            return default

    def _first_value_by_key(self, obj, target_key):
        if isinstance(obj, dict):
            if target_key in obj:
                return obj.get(target_key)
            for value in obj.values():
                found = self._first_value_by_key(value, target_key)
                if found is not None:
                    return found
        elif isinstance(obj, list):
            for value in obj:
                found = self._first_value_by_key(value, target_key)
                if found is not None:
                    return found
        return None
