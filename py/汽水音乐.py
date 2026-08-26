#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""汽水音乐 TVBox Python 单源（Android App 20.5.0 分类版）。"""
"""蜜果-http://6i.pw/"""
import base64
import gzip
import hashlib
import json
import time
import urllib.parse
import urllib.request

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider(object):
        pass


class Spider(BaseSpider):
    API = "https://api.qishui.com"
    UA = "Mozilla/5.0 (Linux; Android 10; TVBox) AppleWebKit/537.36 Chrome/124 Safari/537.36"
    VIDEO_CATEGORIES = [
        ("推荐", "0"), ("小说", "7517124833219647498"),
        ("音乐", "7475643857839036443"), ("现言", "7532767202778847282"),
        ("爽文", "7532779130690492426"), ("助眠", "7425531925765429274"),
        ("脱口秀", "7446747083388524571"), ("男频", "7532758933284804618"),
        ("女频", "7532763414768146458"), ("影视解说", "7425531055719716915"),
        ("相声", "7426586511761954843"), ("历史", "7425531262276229158"),
        ("社会时政", "7517125056763320329"), ("科普", "7425531697234319397"),
        ("财经", "7425531430040328218"), ("职场", "7446749038886688778"),
        ("悬疑", "7532766138716510235"), ("重生", "7532768064795465774"),
        ("脑洞", "7532768160219568179"), ("穿越", "7532767797405112347"),
    ]
    HOME_ORDER = [
        "默认模式", "熟悉模式", "新鲜模式", "图书馆", "专注模式", "摸鱼", "深夜EMO", "DJ模式", "助眠模式",
        "动感健身", "抖音漫游", "洗澡", "Chill放松", "快乐时光", "电音", "好运", "粤语", "通勤必听",
        "失恋必听", "躺平", "欧美", "打扫", "国风", "打游戏", "驾车", "说唱", "沉浸0.8x", "夜晚",
        "治愈", "轻音乐", "小酒馆", "KTV必点", "起床", "浪漫情歌", "摇滚", "R&B", "佛系时间",
        "怀旧老歌", "民谣", "甜美女声", "K-pop", "日语", "旅行", "儿歌", "雨天", "海边", "乡村", "古典",
    ]
    HOT_CHART_ID = "7036274230471712007"
    NEW_CHART_ID = "7060812597884869927"
    NOSTALGIA_RADIO_ID = "7408841207276748809"
    QISHUI_ICON = ("https://is1-ssl.mzstatic.com/image/thumb/Purple211/v4/23/19/5a/"
                   "23195ac8-3fbf-d33b-16ed-20854f9afd35/"
                   "AppIcon-0-0-1x_U007epad-0-1-0-85-220.png/512x512bb.jpg")

    def __init__(self):
        try:
            super(Spider, self).__init__()
        except Exception:
            pass
        self.timeout = 18
        self.headers = {"User-Agent": self.UA, "Accept": "application/json, text/plain, */*",
                        "Referer": "https://music.douyin.com/"}

    def getName(self):
        return "汽水音乐"

    def init(self, extend=""):
        try:
            cfg = json.loads(extend) if isinstance(extend, str) and extend.strip() else extend
            if isinstance(cfg, dict):
                self.timeout = max(5, min(60, int(cfg.get("timeout", self.timeout))))
                if cfg.get("user_agent"):
                    self.headers["User-Agent"] = str(cfg["user_agent"])
        except Exception:
            pass

    def _request_json(self, url, data=None):
        headers, body = dict(self.headers), None
        if data is not None:
            body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode()
            headers["Content-Type"] = "application/json; charset=utf-8"
        req = urllib.request.Request(url, data=body, headers=headers, method="POST" if body else "GET")
        with urllib.request.urlopen(req, timeout=self.timeout) as res:
            raw = res.read()
            if res.headers.get("Content-Encoding", "").lower() == "gzip":
                raw = gzip.decompress(raw)
        return json.loads(raw.decode("utf-8", "replace"))

    def _api(self, path, data=None, query=None):
        url = self.API + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        return self._request_json(url, data)

    @staticmethod
    def _first(value, default=""):
        return value[0] if isinstance(value, list) and value else (value or default)

    def _image_url(self, image):
        if not isinstance(image, dict):
            return ""
        uri, url = str(image.get("uri") or ""), str(self._first(image.get("urls"), ""))
        if url and url.rstrip("/").endswith("/img"):
            if not uri:
                return ""
            result = url.rstrip("/") + "/" + uri.lstrip("/")
            template = str(image.get("template_prefix") or "")
            return result + ("~" + template + "-ori.image" if template else "")
        return url or uri

    @staticmethod
    def _pack(kind, value):
        raw = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
        return kind + ":" + base64.urlsafe_b64encode(raw).decode().rstrip("=")

    @staticmethod
    def _unpack(value, kind):
        text, prefix = str(value or ""), kind + ":"
        if not text.startswith(prefix):
            return None
        raw = text[len(prefix):]
        return json.loads(base64.urlsafe_b64decode((raw + "=" * (-len(raw) % 4)).encode()).decode())

    @staticmethod
    def _result(items, page=1, more=False, size=20):
        page = max(1, int(page))
        return {"list": items, "page": page, "pagecount": page + 1 if more else page,
                "limit": size, "total": (page - 1) * size + len(items) + (size if more else 0),
                "parse": 0, "jx": 0}

    @staticmethod
    def _extend(extend, key, default=""):
        value = extend.get(key, default) if isinstance(extend, dict) else default
        if isinstance(value, list):
            value = value[0] if value else default
        if isinstance(value, dict):
            value = value.get("v") or value.get("value") or default
        return str(value or default)

    @staticmethod
    def _track(obj):
        if not isinstance(obj, dict):
            return None
        if obj.get("id") and (obj.get("name") or obj.get("title")):
            return obj
        for path in (("track",), ("entity", "track_wrapper", "track"),
                     ("track_wrapper", "track"), ("entity", "track")):
            value = obj
            for key in path:
                value = value.get(key) if isinstance(value, dict) else None
            if isinstance(value, dict) and value.get("id"):
                return value
        return None

    def _track_card(self, obj, prefix=""):
        track = self._track(obj)
        if not track or not track.get("id"):
            return None
        artists = " / ".join(str(a.get("name") or a.get("simple_display_name") or "")
                             for a in track.get("artists") or [] if isinstance(a, dict))
        album = track.get("album") or {}
        remark = artists or str(album.get("name") or "汽水音乐")
        return {"vod_id": str(track["id"]), "vod_name": str(track.get("name") or "未知歌曲"),
                "vod_pic": self._image_url(album.get("url_cover") or track.get("url_cover") or {}),
                "vod_remarks": prefix + ((" · " + remark) if prefix and remark else remark)}

    # TVBox 分类
    def homeContent(self, filter):
        return {"class": [{"type_id": "home", "type_name": "模式"},
                          {"type_id": "discover", "type_name": "发现"},
                          {"type_id": "listen_video", "type_name": "听抖音"}],
                "filters": {"listen_video": [{"key": "cate", "name": "分类",
                    "value": [{"n": n, "v": v} for n, v in self.VIDEO_CATEGORIES]}]}}

    def homeVideoContent(self):
        try:
            return self._home_modes(1)
        except Exception:
            return self._result([], 1)

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = max(1, int(pg or 1))
            if str(tid) == "home":
                return self._home_modes(page)
            if str(tid) == "discover":
                return self._discover(page)
            return self._listen_videos(self._extend(extend, "cate", "0"), page)
        except Exception:
            return self._result([], int(pg or 1))

    def _home_modes(self, page):
        data = self._api("/luna/feed/mode", {"ab_param": "", "feed_extra": None})
        # 三种基础偏好模式没有稳定的匿名实体 ID，单独建模，避免把专注/摸鱼
        # 等场景实体错误地按位置改名。
        modes = [
            {"id": "default", "name": "默认模式", "kind": "preference", "sub": ""},
            {"id": "familiar", "name": "熟悉模式", "kind": "preference", "sub": ""},
            {"id": "fresh", "name": "新鲜模式", "kind": "preference", "sub": ""},
        ]
        for group in data.get("feed_mode_block") or []:
            for mode in group.get("feed_mode") or []:
                scene = ((mode.get("entity") or {}).get("feed_scene_mode") or {})
                modes.append({"id": str(scene.get("scene_mode_id") or mode.get("text") or ""),
                              "name": str(mode.get("text") or "听歌模式"), "kind": "scene",
                              "sub": str(scene.get("sub_queue_type") or "")})

        # 模式海报墙统一使用汽水音乐官方 App 图标。
        common_pic = self.QISHUI_ICON
        cards = []
        seen = set()
        for info in modes:
            normalized = info["name"].lower().replace(" ", "")
            if not info["id"] or normalized in seen:
                continue
            seen.add(normalized)
            info["pic"] = common_pic
            cards.append({"vod_id": self._pack("mode", info), "vod_name": info["name"],
                          "vod_pic": common_pic, "vod_remarks": "听歌模式"})
        order = {name.lower().replace(" ", ""): i for i, name in enumerate(self.HOME_ORDER)}
        cards.sort(key=lambda x: order.get(x["vod_name"].lower().replace(" ", ""), len(order)))
        return self._result(cards, page, False, max(1, len(cards)))

    def _discover(self, page):
        data = self._api("/luna/discover", {"ab_param": "", "selected_boost": None,
            "playlist_mix_param": None, "feed_discover_extra": None, "first_request": True})
        blocks = list(data.get("blocks") or [])
        # App 首包只返回一小部分卡片；继续加载推荐混合流，合并后作为发现一级内容。
        for _ in range(2):
            mixed = self._api("/luna/discover/mix", {
                "block_type": "discover_playlist_mix", "sub_channel_id": 0,
                "latest_douyin_liked_playlist_show_ts": None, "feed_discover_extra": {},
                "cursor": None, "count": 50, "session_id": None, "ab_param": ""})
            blocks.append({"inner_block": mixed.get("inner_block") or [], "title": "发现"})
        cards, seen = [], set()
        for block in blocks:
            inners = block.get("inner_block") or ([block] if block.get("resources") else [])
            for inner in inners:
                for resource in inner.get("resources") or []:
                    style = resource.get("style") or {}
                    kind = str(resource.get("type") or "radio")
                    rid = str(resource.get("resource_id") or inner.get("inner_block_id") or "")
                    marker = kind + ":" + rid
                    if not rid or marker in seen:
                        continue
                    seen.add(marker)
                    cover = style.get("cover_url") or self._first(style.get("cover_url_list"), {})
                    entity = resource.get("entity") or {}
                    if not cover and isinstance(entity.get("playlist"), dict):
                        cover = entity["playlist"].get("url_cover") or {}
                    info = {"id": str(resource.get("resource_id") or inner.get("inner_block_id") or ""),
                            "kind": kind,
                            "name": str(style.get("title") or inner.get("title") or "发现"),
                            "desc": str(style.get("desc") or block.get("title") or "发现"),
                            "pic": self._image_url(cover or {})}
                    cards.append({"vod_id": self._pack("collection", info), "vod_name": info["name"],
                                  "vod_pic": info["pic"], "vod_remarks": info["desc"][:80]})
        return self._result(cards, page, False, max(1, len(cards)))

    def _category_name(self, cid):
        return next((n for n, v in self.VIDEO_CATEGORIES if v == str(cid)), "推荐")

    def _listen_videos(self, cid, page):
        name = self._category_name(cid)
        keyword = "热门视频" if name == "推荐" else name
        payload = {"search_type": "listen_video", "q": keyword,
                   "cursor": None if page == 1 else str((page - 1) * 20),
                   "search_id": hashlib.md5((keyword + ":video").encode()).hexdigest(),
                   "search_method": "input", "search_scene": "search_result", "scene_name": "listen_video"}
        data = self._api("/luna/search/listen_video", payload, {"device_platform": "web"})
        group = next((g for g in data.get("result_groups") or [] if g.get("id") == "listen_video"), {})
        cards = []
        for item in group.get("data") or []:
            video = ((item.get("entity") or {}).get("video") or {})
            vid = str(video.get("vid") or ((video.get("clip") or {}).get("vid") or ""))
            if not vid:
                continue
            artists = video.get("artists") or []
            author = str((((artists[0].get("user_info") or {}) if artists else {}).get("nickname")) or "汽水视频")
            title = str(video.get("title") or video.get("description") or "听抖音")
            info = {"vid": vid, "video_id": str(video.get("video_id") or ""), "name": title,
                    "pic": self._image_url(video.get("cover_url") or video.get("image_url") or {}),
                    "author": author, "duration": int(video.get("duration") or 0)}
            cards.append({"vod_id": self._pack("video", info), "vod_name": title,
                          "vod_pic": info["pic"], "vod_remarks": author})
        return self._result(cards, page, bool(group.get("has_more")), 20)

    def _radio_tracks(self, rid):
        data = self._api("/luna/feed/radio/tracks", {"radio_id": str(rid), "played_media": [],
            "feed_radio_media_extra": {"real_groups": []}, "flow_type": 2, "full_media": True})
        return [t for t in (self._track(x) for x in data.get("items") or []) if t]

    def _chart_tracks(self, chart_id):
        data = self._api("/luna/charts/" + urllib.parse.quote(str(chart_id)))
        chart = data.get("chart") or {}
        items = (chart.get("track_ranks") or chart.get("tracks") or
                 data.get("track_ranks") or data.get("tracks") or data.get("items") or [])
        return [t for t in (self._track(x) for x in items) if t]

    def _playlist_tracks(self, playlist_id):
        data = self._api("/luna/playlist/detail", {
            "playlist_id": str(playlist_id), "cursor": None, "count": 100, "type": None,
            "feed_playlist_extra": {"har": None, "commerce_block_pattern": None},
            "sort_type": None, "session_id": None, "reverse": False, "ab_param": "",
            "limited_free_scene": 0}, {"max_length": 4194304})
        return [t for t in (self._track(x) for x in data.get("media_resources") or []) if t]

    def _search_tracks(self, keyword, page=1):
        payload = {"search_type": "track", "q": keyword,
                   "cursor": None if page == 1 else str((page - 1) * 20),
                   "search_id": hashlib.md5(keyword.encode()).hexdigest(),
                   "search_method": "input", "search_scene": "search_result"}
        data = self._api("/luna/search/track", payload, {"device_platform": "web"})
        group = next((g for g in data.get("result_groups") or [] if g.get("id") == "tracks"), {})
        return group, [t for t in (self._track(x) for x in group.get("data") or []) if t]

    def searchContent(self, key, quick, pg="1"):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg="1"):
        try:
            page, keyword = max(1, int(pg or 1)), str(key or "").strip()
            group, tracks = self._search_tracks(keyword, page)
            return self._result([c for c in (self._track_card(t) for t in tracks) if c],
                                page, bool(group.get("has_more")), 20)
        except Exception:
            return self._result([], 1)

    def _seo(self, track_id):
        return self._api("/luna/h5/seo_track", query={"track_id": str(track_id), "device_platform": "web"})

    @staticmethod
    def _safe_name(name):
        return str(name or "播放").replace("$", " ").replace("#", " ")

    def _playlist_detail(self, info, tracks):
        valid_tracks = [t for t in tracks if t.get("id")]
        streams = []
        # TVBox 在合集页直接播放分集，不会再打开单曲详情，因此音质线路必须
        # 在合集这一层生成。用列表中首个可解析曲目的真实档位作为线路名称。
        for track in valid_tracks[:3]:
            try:
                streams = self._audio_streams(self._seo(track["id"]))
                if streams:
                    break
            except Exception:
                pass
        if streams:
            sources, groups = [], []
            for stream in streams:
                sources.append(stream["label"])
                groups.append("#".join(
                    self._safe_name(t.get("name")) + "$a:" + str(t["id"]) + ":" + stream["key"]
                    for t in valid_tracks))
        else:
            sources = ["最高音质"]
            groups = ["#".join(self._safe_name(t.get("name")) + "$a:" + str(t["id"]) + ":auto"
                               for t in valid_tracks)]
        return {"vod_id": self._pack("collection", info), "vod_name": info.get("name") or "汽水音乐",
                "vod_pic": info.get("pic") or "", "vod_remarks": info.get("desc") or "",
                "vod_content": info.get("desc") or "汽水音乐 App 分类",
                "vod_play_from": "$$$".join(sources), "vod_play_url": "$$$".join(groups)}

    def detailContent(self, array):
        value = str(array[0] if isinstance(array, (list, tuple)) else array)
        try:
            video = self._unpack(value, "video")
            if video:
                sec = int(video.get("duration") or 0) // 1000
                return {"list": [{"vod_id": value, "vod_name": video.get("name") or "听抖音",
                    "vod_pic": video.get("pic") or "", "vod_actor": video.get("author") or "",
                    "vod_remarks": "%02d:%02d" % (sec // 60, sec % 60) if sec else "听抖音",
                    "vod_content": video.get("name") or "", "vod_play_from": "抖音视频",
                    "vod_play_url": "播放$v:" + video["vid"]}], "parse": 0, "jx": 0}
            collection = self._unpack(value, "collection")
            if collection:
                kind = collection.get("kind")
                if kind == "radio":
                    tracks = self._radio_tracks(collection["id"])
                elif kind in ("brief_chart", "chart"):
                    tracks = self._chart_tracks(collection["id"])
                elif kind == "playlist":
                    tracks = self._playlist_tracks(collection["id"])
                else:
                    tracks = []
                if not tracks:
                    _, tracks = self._search_tracks(collection.get("name") or "热门歌曲")
                return {"list": [self._playlist_detail(collection, tracks)], "parse": 0, "jx": 0}
            mode = self._unpack(value, "mode")
            if mode:
                if mode.get("id") == "default":
                    tracks = self._chart_tracks(self.HOT_CHART_ID)
                elif mode.get("id") == "familiar":
                    tracks = self._radio_tracks(self.NOSTALGIA_RADIO_ID)
                elif mode.get("id") == "fresh":
                    tracks = self._chart_tracks(self.NEW_CHART_ID)
                else:
                    _, tracks = self._search_tracks(mode.get("name") or "热门歌曲")
                info = {"name": mode.get("name"), "pic": mode.get("pic"), "desc": "听歌模式"}
                return {"list": [self._playlist_detail(info, tracks)], "parse": 0, "jx": 0}
            return {"list": [self._song_detail(value)], "parse": 0, "jx": 0}
        except Exception:
            return {"list": [{"vod_id": value, "vod_name": "汽水音乐", "vod_play_from": "汽水音乐",
                               "vod_play_url": "播放$a:" + value + ":auto"}], "parse": 0, "jx": 0}

    @staticmethod
    def _stream_label(bitrate, index):
        kbps = max(0, int(bitrate or 0) // 1000)
        name = "无损音质" if kbps >= 900 else ("极高音质" if kbps >= 190 else
               ("标准音质" if kbps >= 96 else "省流音质"))
        return "%s(%dK)" % (name, kbps) if kbps else name + str(index + 1)

    def _audio_streams(self, data):
        player, result = data.get("track_player") or {}, []
        model = player.get("video_model")
        if isinstance(model, str) and model:
            try:
                model = json.loads(model)
            except Exception:
                model = {}
        for index, item in enumerate((model or {}).get("video_list") or []):
            if not isinstance(item, dict) or item.get("encrypt_info"):
                continue
            meta = item.get("video_meta") or {}
            bitrate = int(meta.get("bitrate") or meta.get("real_bitrate") or 0)
            url = item.get("main_url") or item.get("backup_url")
            if url:
                result.append({"key": str(meta.get("quality") or index),
                    "label": self._stream_label(bitrate, index), "bitrate": bitrate, "url": str(url)})
        if not result and player.get("url_player_info"):
            info = self._request_json(str(player["url_player_info"]))
            for index, item in enumerate((((info.get("Result") or {}).get("Data") or {}).get("PlayInfoList") or [])):
                bitrate, url = int(item.get("Bitrate") or 0), item.get("MainPlayUrl") or item.get("BackupPlayUrl")
                if url:
                    result.append({"key": str(index), "label": self._stream_label(bitrate, index),
                                   "bitrate": bitrate, "url": str(url)})
        unique = {(x["key"], x["bitrate"]): x for x in result}
        return sorted(unique.values(), key=lambda x: x["bitrate"], reverse=True)

    def _song_detail(self, track_id):
        data = self._seo(track_id)
        track = self._track(data.get("seo_track") or {}) or {"id": track_id}
        card = self._track_card(track) or {"vod_id": track_id, "vod_name": "汽水音乐", "vod_pic": ""}
        artists = " / ".join(str(a.get("name") or "") for a in track.get("artists") or [] if a.get("name"))
        album, streams = track.get("album") or {}, self._audio_streams(data)
        if streams:
            # streams 已按码率从高到低排列；TVBox 默认选中第一个播放来源。
            sources = [stream["label"] for stream in streams]
            urls = [self._safe_name(track.get("name")) + "$a:" + track_id + ":" + stream["key"]
                    for stream in streams]
        else:
            sources = ["汽水音乐"]
            urls = [self._safe_name(track.get("name")) + "$a:" + track_id + ":auto"]
        vod = dict(card)
        vod.update({"type_name": "音乐", "vod_actor": artists,
                    "vod_content": "专辑：" + str(album.get("name") or "未知专辑") + "\n" +
                                   str((data.get("lyric") or {}).get("content") or "")[:1800],
                    "vod_play_from": "$$$".join(sources), "vod_play_url": "$$$".join(urls)})
        return vod

    def playerContent(self, flag, pid, vipFlags):
        value = str(pid or "")
        try:
            if value.startswith("v:"):
                url = "https://aweme.snssdk.com/aweme/v1/play/?" + urllib.parse.urlencode(
                    {"video_id": value[2:], "ratio": "1080p", "line": "0"})
                return {"parse": 0, "jx": 0, "url": url,
                        "header": {"User-Agent": self.headers["User-Agent"]}}
            if value.startswith("a:"):
                _, track_id, quality = value.split(":", 2)
            else:
                track_id, quality = value, "auto"
            streams = self._audio_streams(self._seo(track_id))
            selected = next((x for x in streams if x["key"] == quality), streams[0])
            # 手机端专用的显式分流标记。旧版/TV 端会安全忽略未知字段，
            # 只有已适配的手机端会据此进入音乐播放器。
            return {"parse": 0, "jx": 0, "url": selected["url"], "music_player": 1,
                    "header": {"User-Agent": self.headers["User-Agent"],
                               "Referer": "https://music.douyin.com/"}}
        except Exception:
            return {"parse": 1, "jx": 0, "url": value, "header": {}}

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def localProxy(self, params):
        return [404, "text/plain", b""]


if __name__ == "__main__":
    print(json.dumps(Spider().homeContent(True), ensure_ascii=False, indent=2))
