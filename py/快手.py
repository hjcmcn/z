"""快手直播源（Python）。

首頁分區 / 遊戲文件夾 / 熱榜列表 / 搜尋 / 房間詳情 / 播放 / FLV 代理 / 即時彈幕。

彈幕走官方 /live_api/liveroom/recall 回溯接口：匿名可取，無需簽名或 Cookie，
回應是 base64 的 protobuf CommentFeed，按 id 去重後輪詢上屏。
"""

import base64
import json
import re
import threading
import time
from urllib.parse import quote, unquote

from base.spider import Spider as BaseSpider

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
)
KUAISHOU = "https://live.kuaishou.com"
NAME = "快手"
STYLE = {"type": "rect", "ratio": 1.78}
FOLDER = {"type": "oval", "ratio": 1}
MAX_PAGE = 49
LIMIT = 50
BOARD_LIMIT = 20
MAX_SEEN = 800
SEEN_TTL_MS = 300000

GROUPS = [
    {"id": "DQRM", "name": "熱門"},
    {"id": "WYJJ", "name": "網遊"},
    {"id": "DJRY", "name": "單機"},
    {"id": "SYXX", "name": "手遊"},
    {"id": "QP", "name": "棋牌"},
    {"id": "YL", "name": "娛樂"},
    {"id": "ZH", "name": "綜合"},
    {"id": "KJ", "name": "文化"},
]

TRAD_LABELS = {
    "聊天": "聊天", "音乐": "音樂", "游戏": "遊戲", "二次元": "二次元", "舞蹈": "舞蹈", "文化": "文化", "生活": "生活",
    "运动": "運動", "户外": "戶外", "探索": "探索", "宠粉": "寵粉", "派对": "派對", "盛典": "盛典", "好物": "好物",
    "交友": "交友", "情感": "情感", "颜值": "顏值", "才艺": "才藝", "娱乐": "娛樂", "三农": "三農", "知识": "知識",
    "财经": "財經", "汽车": "汽車", "房产": "房產", "旅行": "旅行", "美食": "美食", "亲子": "親子", "宠物": "寵物",
    "时尚": "時尚", "摄影": "攝影", "手工": "手工", "绘画": "繪畫", "国风": "國風", "非遗": "非遺", "健身": "健身",
    "射击": "射擊", "竞技": "競技", "单机": "單機", "棋牌": "棋牌", "休闲益智": "休閒益智", "角色扮演": "角色扮演",
    "策略卡牌": "策略卡牌", "主机": "主機", "网游": "網遊", "手游": "手遊", "综合": "綜合", "热门": "熱門",
    "音乐人": "音樂人", "舞者": "舞者", "歌手": "歌手", "演员": "演員", "相声": "相聲", "戏曲": "戲曲",
    "蓝光": "藍光", "超清": "超清", "高清": "高清", "标清": "標清", "原画": "原畫", "流畅": "流暢",
}

LIVE_KEYS = ("url", "src", "playUrl", "play_url", "hlsUrl", "flvUrl")


class Spider(BaseSpider):
    def init(self, extend=""):
        self.options = _options(extend)
        self._rooms = {}
        self._active_stop = None
        self._seq = 0
        self._seen = {}
        self._seen_room = ""
        self._seen_time = 0.0
        self._post_mode = ""
        self._lock = threading.RLock()

    # ==================== 入口 ====================

    def homeContent(self, filter):
        return {"class": [
            {"type_id": item["id"], "type_name": item["name"], "land": 1, "ratio": 1.78}
            for item in GROUPS
        ]}

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        extend = extend if isinstance(extend, dict) else {}
        text = str(tid).strip()
        current = _page_number(pg)

        keyword = re.match(r"^kuaishou/s/(.*)$", text)
        if keyword:
            return self._search_rooms(unquote(keyword.group(1) or ""), current)

        picked = str(extend.get("game") or extend.get("cateId") or "").strip()
        if picked:
            return self._game_rooms(picked, current)

        direct = re.match(r"^(?:kuaishou/g/|game_)([A-Za-z0-9_-]{1,64})$", text)
        if direct:
            return self._game_rooms(direct.group(1), current)

        if any(item["id"] == text for item in GROUPS):
            group = text
        elif text == "kuaishou":
            group = GROUPS[0]["id"]
        else:
            group = ""
        if not group:
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", text):
                raise RuntimeError("未知直播分區")
            return self._game_rooms(text, current)

        items = self._games(group)
        if not items:
            return self._hot_page(group, current)
        return _folders(items, current)

    def searchContent(self, key, quick, pg="1"):
        current = _page_number(pg)
        keyword = str(key).strip()
        card = {
            "vod_id": "kuaishou/s/" + unquote_plus_safe(keyword),
            "vod_name": "快手：%s" % keyword,
            "vod_remarks": "搜尋主播或房間編號",
            "vod_tag": "folder",
            "style": {"type": "list"},
        }
        return _page([card], current, 1)

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        result = []
        for raw in ids:
            room = _room_id(raw)
            vod = self._detail_vod(room["id"])
            vod["vod_play_from"] = NAME
            if not vod.get("vod_play_url"):
                vod["vod_play_url"] = "觀看直播$" + vod["vod_id"]
            result.append(vod)
        return {"list": result}

    def playerContent(self, flag, id, vipFlags):
        room = _room_id(id)
        result = self._live_source(room["id"], room["extra"])
        result["position"] = 0
        result["danmaku"] = [{"name": "即時彈幕", "url": self.danmakuUrl(id)}]
        return result

    def proxy(self, params):
        params = params if isinstance(params, dict) else {}
        room = _room_id(params.get("live"))
        index = params.get("index")

        def source():
            url = self._stream_url(room["id"], index)
            if re.search(r"\.m3u8(\?|$)", url, re.I):
                raise RuntimeError("此平台播放地址為 HLS 格式，無法代理")
            return url

        cache_key = "stream:kuaishou:" + room["id"]
        source()
        options = {"headers": _headers(), "timeout": 15000, "callTimeout": 0}

        def open_stream():
            reader = self.net.openStream(source(), options)
            if reader.code in (401, 403, 404):
                reader.close()
                self.net.clearCache(cache_key)
                self.net.clearCache("room:kuaishou:" + room["id"])
                self._rooms.pop(room["id"], None)
                reader = self.net.openStream(source(), options)
            if reader.code != 200:
                reader.close()
                raise RuntimeError("直播串流 HTTP %s" % reader.code)
            return reader

        response = self.net.stream(_mount_flv(self, open_stream, 10000))
        return [200, "video/x-flv", response["stream"],
                {"Cache-Control": "no-store", "Accept-Ranges": "none"}]

    # ==================== 介面 ====================

    def _api(self, url, params=None):
        try:
            result = self.net.json(url, {"params": params or {}, "headers": _headers()})
        except Exception:
            raise RuntimeError("快手接口連線失敗")
        if not isinstance(result, dict):
            raise RuntimeError("快手接口回應格式錯誤")
        return result

    def _remember(self, items):
        stamp = time.time() * 1000
        for item in items:
            if not isinstance(item, dict):
                continue
            ident = str(item.get("id") or "").strip()
            if ident:
                self._rooms[ident] = {"stamp": stamp, "item": item}
        if len(self._rooms) > 3000:
            for key in list(self._rooms.keys())[:1500]:
                self._rooms.pop(key, None)

    def _hot(self, type_, current, keyword=None):
        key = "hot:kuaishou:%s:%s:%s" % (type_ or "DQRM", current, keyword or "")

        def load():
            params = {"type": type_ or "DQRM", "page": current}
            if keyword:
                params["keyword"] = keyword
            result = self._api(KUAISHOU + "/live_api/hot/list", params)
            data = result.get("data")
            items = data.get("list") if isinstance(data, dict) and isinstance(data.get("list"), list) else []
            self._remember(items)
            return items

        return self.net.cached(key, {"ttl": 15000, "stale": False}, load)

    def _board(self, game, current):
        result = self._api(KUAISHOU + "/live_api/gameboard/list", {"gameId": game, "page": current})
        data = result.get("data") if isinstance(result.get("data"), dict) else {}
        items = data.get("list") if isinstance(data.get("list"), list) else []
        self._remember(items)
        return {"items": items, "hasMore": data.get("hasMore") is True}

    def _tree(self):
        def load():
            result = self._api(KUAISHOU + "/live_api/category/tag")
            if not isinstance(result.get("data"), list):
                raise RuntimeError("快手分類格式錯誤")
            return result["data"]

        return self.net.cached("catalog:kuaishou", {"ttl": 86400000, "persist": True}, load)

    def _catalog(self):
        def load():
            result = self._api(KUAISHOU + "/live_api/home/category")
            data = result.get("data")
            listing = data.get("list") if isinstance(data, dict) and isinstance(data.get("list"), list) else []
            if not listing:
                raise RuntimeError("快手完整分類暫無資料")
            table = {}
            for group in listing:
                games = group.get("gameInfos") if isinstance(group, dict) else None
                if not isinstance(games, list):
                    continue
                for game in games:
                    if not isinstance(game, dict):
                        continue
                    key = str(game.get("categoryAbbr") or "").strip().upper()
                    if key:
                        table.setdefault(key, []).append(game)
            if not table:
                raise RuntimeError("快手完整分類格式錯誤")
            return table

        try:
            return self.net.cached("catalog:kuaishou:home", {"ttl": 86400000, "persist": True}, load)
        except Exception:
            self._log("快手完整遊戲清單暫不可用，改用精選清單")
            return {}

    def _games(self, type_):
        full = self._catalog()
        items = full.get(type_)
        if isinstance(items, list) and items:
            return [item for item in (_folder_of(game) for game in items) if item]

        tree = self._tree()
        node = next((item for item in tree if isinstance(item, dict) and str(item.get("type") or "") == type_), None)
        listing = node.get("list") if isinstance(node, dict) and isinstance(node.get("list"), list) else []
        return [item for item in (_folder_of(game) for game in listing) if item]

    def _find(self, ident):
        cached = self._rooms.get(ident)
        if cached and time.time() * 1000 - cached["stamp"] < 30000:
            return cached["item"]
        self._parallel([(self._hot, (group["id"], 1)) for group in GROUPS])
        cached = self._rooms.get(ident)
        return cached["item"] if cached else None

    def _parallel(self, jobs):
        """並行跑多個無參/單參任務；單個失敗不影響其它（回查需要「盡量都跑完」）。"""
        errors = []

        def run(fn, args):
            try:
                fn(*args)
            except Exception as error:
                errors.append(error)

        threads = [threading.Thread(target=run, args=(fn, args), daemon=True) for fn, args in jobs]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        return errors

    def _room(self, ident):
        def load():
            item = self._find(ident)
            if not item:
                raise RuntimeError("快手熱榜裡找不到這個直播間（可能已下播，或已掉出榜單）")
            return item

        return self.net.cached("room:kuaishou:" + ident, {"ttl": 60000, "stale": False}, load)

    def _streams(self, ident):
        def load():
            item = self._room(ident)
            urls = _collect_urls(item)
            urls.sort(key=_quality, reverse=True)
            return urls

        return self.net.cached("stream:kuaishou:" + ident, {"ttl": 5000, "stale": False}, load)

    def _stream_url(self, ident, value):
        urls = self._streams(ident)
        index = 0 if value in (None, "") else _index(value)
        if index >= len(urls):
            raise RuntimeError("快手播放線路已失效")
        return urls[index]

    def _live_source(self, ident, value):
        urls = self._streams(ident)
        index = 0 if value in (None, "") else _index(value)
        if index >= len(urls):
            raise RuntimeError("快手播放線路已失效")
        url = urls[index]
        fmt = "application/x-mpegURL" if re.search(r"\.m3u8(\?|$)", url, re.I) else "video/x-flv"
        target = url if fmt == "application/x-mpegURL" else self.proxyUrl(
            {"live": "kuaishou:" + ident, "index": str(index)})
        return {"parse": 0, "url": target, "header": _headers(), "format": fmt}

    def _game_rooms(self, game, current):
        result = self._board(game, current)
        cards = [item for item in (_ks_card(raw) for raw in result["items"]) if item]
        if not cards:
            return self._hot_page(self._game_type(game), current)
        pagecount = MAX_PAGE if len(result["items"]) >= BOARD_LIMIT and result["hasMore"] else max(1, current)
        return {"list": cards, "page": current, "pagecount": pagecount,
                "limit": BOARD_LIMIT, "total": len(cards)}

    def _game_type(self, game):
        for group in GROUPS:
            if any(item["id"] == game for item in self._games(group["id"])):
                return group["id"]
        return GROUPS[0]["id"]

    def _hot_page(self, type_, current):
        items = self._hot(type_, current)
        cards = [item for item in (_ks_card(raw) for raw in items) if item]
        pagecount = min(MAX_PAGE, current + 1) if len(items) >= LIMIT else max(1, current)
        return {"list": cards, "page": current, "pagecount": pagecount,
                "limit": LIMIT, "total": len(cards)}

    def _search_rooms(self, keyword, current):
        key = keyword.lower()
        items = []
        try:
            items.extend(self._hot("DQRM", current, keyword))
        except Exception:
            self._log("快手搜尋關鍵字查詢失敗，改用分類掃描")
        filtered = _filter_rooms(items, key)
        if not filtered:
            collected = []
            for group in GROUPS:
                try:
                    collected.extend(self._hot(group["id"], 1))
                except Exception:
                    self._log("快手分類 %s 搜尋掃描失敗" % group["id"])
            filtered = _filter_rooms(collected, key)
        cards = [item for item in (_ks_card(raw) for raw in filtered) if item]
        return {"list": cards, "page": current, "pagecount": 1, "limit": LIMIT, "total": len(cards)}

    def _detail_vod(self, ident):
        item = self._room(ident)
        urls = _collect_urls(item)
        urls.sort(key=_quality, reverse=True)
        lines = ["狀態：直播中"]
        duration = _ks_duration(item)
        if duration:
            lines.append("已開播：" + duration)
        name = str(item.get("caption") or "").strip() or _author(item) or str(item.get("id") or "")
        watching = item.get("watchingCount") or item.get("viewCount") or 0
        game = _game(item)
        if game:
            lines.append("分區：" + game)
        if watching:
            lines.append("在看：" + _ks_count(watching))
        if item.get("likeCount"):
            lines.append("點贊：" + _ks_count(item.get("likeCount")))
        quality = str(item.get("qualityLabel") or "").strip()
        if quality:
            lines.append("畫質：" + _label(quality))
        if _author(item):
            lines.append("主播：" + _author(item))
        author = item.get("author") if isinstance(item.get("author"), dict) else {}
        city = str(author.get("cityName") or "").strip()
        if city:
            lines.append("城市：" + city)
        verified = author.get("verifiedStatus")
        verified = str(verified.get("description") or "").strip() if isinstance(verified, dict) else ""
        if verified:
            lines.append("認證：" + verified)
        about = "\n".join([
            line.strip() for line in re.split(r"\r?\n", str(author.get("description") or "").strip())
            if line.strip()
        ][:3])[:120]
        if about:
            lines.append("主播簡介：" + about)

        vod = _card("kuaishou", ident, name, _picture(item.get("poster") or item.get("cover")),
                    ("%s人在看" % _ks_count(watching)) if watching else "直播中")
        vod["vod_content"] = "\n".join(lines)
        vod["vod_actor"] = _author(item)
        vod["type_name"] = game
        vod["vod_play_url"] = "#".join(
            "%s$kuaishou:%s@%d" % (_quality_label(link, index), ident, index)
            for index, link in enumerate(urls)
        ) if urls else "直播$kuaishou:%s" % ident
        return vod

    # ==================== 彈幕（recall 輪詢） ====================

    def danmaku(self, id, emit):
        try:
            room = _room_id(id)
        except Exception as error:
            _report(emit, error)
            raise

        with self._lock:
            self._seq += 1
            seq = self._seq
            previous = self._active_stop
            self._active_stop = None
        if previous:
            try:
                previous()
            except Exception:
                pass

        room["liveStreamId"] = room["id"]
        stop = self._start_recall(room, emit)
        if stop is None:
            data = None
            try:
                data = self._room(room["id"])
            except Exception:
                pass
            real = ""
            if isinstance(data, dict):
                real = str(data.get("liveStreamID") or data.get("liveStreamId")
                           or data.get("streamID") or data.get("id") or "")
            if real and real != room["id"]:
                room["liveStreamId"] = real
                stop = self._start_recall(room, emit)

        if stop is None:
            error = RuntimeError("快手彈幕拉取失敗（recall 無回應），主播可能已下播，或網絡暫時不通")
            _report(emit, error)
            raise error

        with self._lock:
            if seq != self._seq:
                try:
                    stop()
                except Exception:
                    pass
                return lambda: None
            self._active_stop = stop
        return stop

    def _start_recall(self, room, emit):
        live_id = str(room.get("liveStreamId") or room.get("id") or "")
        if not live_id:
            return None
        first = self._recall(live_id)
        if not isinstance(first, dict) or str(first.get("result")) != "1":
            return None

        now = time.time() * 1000
        if self._seen_room != live_id or now - self._seen_time > SEEN_TTL_MS:
            self._seen = {}
            self._seen_room = live_id
        self._seen_time = now
        seen = self._seen

        stopped = threading.Event()
        _emit_safe(emit, {"state": "ready"})
        for item in self._harvest(first, 8, seen):
            _emit_safe(emit, item)
        self._log("[快手彈幕] recall 通道已連線，歷史 %d 條" % len(
            ((first.get("backTraceFeedMap") or {}).get("1") or {}).get("historyFeedList") or []))

        def tick():
            wait = 5.0
            while not stopped.is_set():
                try:
                    data = self._recall(live_id)
                    if stopped.is_set():
                        return
                    if isinstance(data, dict) and str(data.get("result")) == "1":
                        for item in self._harvest(data, 0, seen):
                            if stopped.is_set():
                                return
                            _emit_safe(emit, item)
                        wait = 2.0
                except Exception as error:
                    self._log("[快手彈幕] 輪詢異常：%s" % str(error)[:120])
                if stopped.is_set():
                    return
                stopped.wait(wait)

        threading.Thread(target=tick, name="kuaishou-danmaku", daemon=True).start()
        return stopped.set

    def _recall(self, live_id):
        url = KUAISHOU + "/live_api/liveroom/recall"
        payload = {"liveStreamId": str(live_id), "feedTypeCursorMap": {"1": 0, "2": 0}}
        headers = {
            "User-Agent": UA,
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": KUAISHOU,
            "Referer": KUAISHOU + "/",
        }
        modes = (self._post_mode,) if self._post_mode else ("json", "body")
        for mode in modes:
            if mode == "json":
                options = {"method": "POST", "postType": "json", "data": payload,
                           "headers": headers, "timeout": 10000}
            else:
                options = {"method": "POST", "body": json.dumps(payload),
                           "headers": headers, "timeout": 10000}
            try:
                response = self.net.req(url, options)
                text = response.get("content") or ""
                if isinstance(text, bytes):
                    text = text.decode("utf-8", "replace")
                text = str(text)
                if not text or not text.startswith("{"):
                    continue
                parsed = json.loads(text)
                if not isinstance(parsed, dict) or not parsed.get("data"):
                    continue
                self._post_mode = mode
                return parsed["data"]
            except Exception:
                continue
        return None

    def _harvest(self, data, limit, seen):
        back = data.get("backTraceFeedMap") if isinstance(data, dict) else None
        node = back.get("1") if isinstance(back, dict) else None
        listing = node.get("historyFeedList") if isinstance(node, dict) else None
        if not isinstance(listing, list):
            listing = []
        batch = []
        for index in range(len(listing) - 1, -1, -1):
            raw = _base64(str(listing[index] or ""))
            if not raw:
                continue
            ident = ""
            try:
                ident = _pb_text(_pb_parse(raw), 1)
            except Exception:
                pass
            if not ident:
                ident = "i%d:%s" % (index, str(listing[index])[:24])
            if ident in seen:
                continue
            seen[ident] = 1
            item = _recall_comment(raw)
            if item:
                batch.append(item)
        if len(seen) > MAX_SEEN:
            for key in list(seen.keys())[:len(seen) - MAX_SEEN // 2]:
                seen.pop(key, None)
        return batch[-limit:] if limit > 0 else batch

    # ==================== 工具 ====================

    def _log(self, message):
        try:
            self.log(message)
        except Exception:
            pass

    def destroy(self):
        with self._lock:
            stop = self._active_stop
            self._active_stop = None
        if stop:
            try:
                stop()
            except Exception:
                pass


# ==================== 模組級工具 ====================

def _options(extend):
    if isinstance(extend, dict):
        return extend
    if extend:
        try:
            value = json.loads(extend)
        except Exception:
            raise ValueError("Site.ext 必須是 JSON 物件")
        if not isinstance(value, dict):
            raise ValueError("Site.ext 必須是 JSON 物件")
        return value
    return {}


def unquote_plus_safe(text):
    return quote(str(text), safe="")


def _page(items, current, limit, total=None):
    size = limit or 20
    amount = 0 if total is None else total
    return {
        "list": items,
        "page": current,
        "pagecount": 1 if total is None else max(1, -(-amount // size)),
        "limit": size,
        "total": len(items) if total is None else amount,
    }


def _page_number(value):
    text = str(value).strip()
    if not re.fullmatch(r"-?\d+", text):
        raise RuntimeError("頁碼格式錯誤")
    return max(1, int(text))


def _index(value):
    text = str(value).strip()
    if not re.fullmatch(r"\d+", text):
        raise RuntimeError("快手播放線路已失效")
    return int(text)


def _room_id(value):
    raw = "" if value is None else str(value).strip()
    try:
        plain = unquote(raw)
    except Exception:
        plain = raw
    live = re.search(r"[?&]live=([^&]*)", plain)
    text = live.group(1) if live else plain
    cut = text.find("?")
    if cut >= 0:
        text = text[:cut]
    at = text.rfind("@")
    head = text[:at] if at > 0 else text
    tail = text[at + 1:] if at > 0 else ""
    match = re.fullmatch(r"kuaishou:([A-Za-z0-9_-]{1,64})", head)
    if not match:
        match = re.search(r"kuaishou:([A-Za-z0-9_-]{1,64})", plain)
        tail = ""
    if not match:
        raise RuntimeError("直播房間編號格式錯誤")
    if tail and not re.fullmatch(r"(hls|flv|flv-full|flv-hd|flv-sd1|flv-sd2|\d{1,2})", tail):
        raise RuntimeError("直播播放線路格式錯誤")
    return {"platform": "kuaishou", "id": match.group(1), "extra": tail}


def _headers():
    return {
        "User-Agent": UA,
        "Referer": KUAISHOU + "/",
        "Origin": KUAISHOU,
        "Accept": "application/json, text/plain, */*",
    }


def _image(value):
    if not isinstance(value, str):
        return ""
    return "https://" + value[2:] if value.startswith("//") else value


def _card(platform, ident, name, pic, remark):
    if not ident or not name:
        raise RuntimeError("直播列表缺少房間編號或名稱")
    return {"vod_id": "%s:%s" % (platform, ident), "vod_name": str(name),
            "vod_pic": _image(pic), "vod_remarks": remark or "", "style": dict(STYLE)}


def _count(value):
    if value in (None, ""):
        return ""
    try:
        number = float(value)
    except Exception:
        return ""
    if number >= 100000000:
        return "%.1f億" % (number / 100000000)
    if number >= 10000:
        return "%.1f萬" % (number / 10000)
    return str(int(number))


def _duration_text(value):
    try:
        seconds = int(float(value))
    except Exception:
        return ""
    if seconds <= 0:
        return ""
    hours = seconds // 3600
    minutes = seconds % 3600 // 60
    if hours > 0:
        return "%d小時%d分鐘" % (hours, minutes)
    if minutes > 0:
        return "%d分鐘" % minutes
    return "%d秒" % seconds


def _label(value):
    text = str(value or "").strip()
    if not text:
        return ""
    if text in TRAD_LABELS:
        return TRAD_LABELS[text]
    head = re.split(r"\s+", text)[0]
    if head in TRAD_LABELS:
        return text.replace(head, TRAD_LABELS[head], 1)
    return text


def _author(item):
    author = item.get("author") if isinstance(item, dict) else None
    if not isinstance(author, dict):
        return ""
    return str(author.get("name") or author.get("userName") or "").strip()


def _game(item):
    info = item.get("gameInfo") if isinstance(item, dict) else None
    name = info.get("name") if isinstance(info, dict) else ""
    return str(name or item.get("gameName") or "").strip()


def _picture(value):
    text = value.strip() if isinstance(value, str) else ""
    return text if re.match(r"^https?://", text) else ""


def _ks_count(value):
    try:
        number = float(value)
    except Exception:
        return str(value if value is not None else "").strip()
    return _count(number) or str(int(number))


def _ks_card(item):
    if not isinstance(item, dict):
        return None
    ident = str(item.get("id") or "").strip()
    if not ident:
        return None
    title = str(item.get("caption") or "").strip()
    watching = item.get("watchingCount") or item.get("viewCount") or 0
    likes = item.get("likeCount") or 0
    segments = []
    if title:
        segments.append(title)
    if watching:
        segments.append(_ks_count(watching) + "觀看")
    if likes:
        segments.append(_ks_count(likes) + "贊")
    return {
        "vod_id": "kuaishou:" + ident,
        "vod_name": _author(item) or title or ident,
        "vod_pic": _picture(item.get("poster") or item.get("cover")),
        "vod_remarks": " · ".join(segments),
        "style": dict(STYLE),
    }


def _folder_of(game):
    if not isinstance(game, dict):
        return None
    ident = str(game.get("id") or game.get("gameId") or "").strip()
    if not ident:
        return None
    rooms = game.get("roomCount") or game.get("roomNumber") or 0
    return {
        "id": ident,
        "name": _label(str(game.get("name") or "").strip()) or ("遊戲 " + ident),
        "pic": _picture(game.get("coverUrl") or game.get("poster") or game.get("iconUrl")),
        "remarks": ("直播間 " + _ks_count(rooms)) if rooms else "",
    }


def _folders(items, current):
    cards = []
    for item in items:
        cards.append({
            "vod_id": "game_" + item["id"],
            "vod_name": item["name"],
            "vod_pic": _image(item.get("pic")),
            "vod_remarks": item.get("remarks") or "",
            "vod_tag": "folder",
            "style": dict(FOLDER) if item.get("pic") else {"type": "list"},
        })
    return {"list": cards, "page": current, "pagecount": 1,
            "limit": len(items) or 20, "total": len(items)}


def _ks_duration(item):
    try:
        start = int(float(item.get("statrtTime") or 0) / 1000)
    except Exception:
        return ""
    if start <= 0:
        return ""
    return _duration_text(int(time.time()) - start)


def _live_url(text):
    return bool(re.search(r"\.flv|\.m3u8|\.mp4|txsecret|txtime|ty_secret|ty_time|wssecret|wstime",
                          str(text).lower()))


def _quality(url):
    match = re.search(r"Avc(Sd|Hd|Fhd)(L\d)?", str(url).split("?")[0], re.I)
    if not match:
        return 0
    return {"sd": 1, "hd": 2, "fhd": 3}.get(match.group(1).lower(), 0)


def _quality_label(url, index):
    match = re.search(r"Avc(Sd|Hd|Fhd)(L\d)?", str(url).split("?")[0], re.I)
    return (match.group(1).upper() if match else "") + str(index + 1)


def _collect_urls(node):
    urls = []
    known = set()

    def add(value):
        text = value.strip() if isinstance(value, str) else ""
        if text and text not in known and _live_url(text):
            known.add(text)
            urls.append(text)

    def walk(current):
        if isinstance(current, list):
            for item in current:
                walk(item)
            return
        if not isinstance(current, dict):
            return
        for value in current.values():
            if isinstance(value, (dict, list)):
                walk(value)
        for key in LIVE_KEYS:
            value = current.get(key)
            if isinstance(value, str):
                add(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        add(item)
                    elif isinstance(item, dict):
                        for inner in LIVE_KEYS:
                            if isinstance(item.get(inner), str):
                                add(item[inner])

    walk(node)
    return urls


def _filter_rooms(items, key):
    result = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        ident = str(item.get("id") or "")
        if ident and ident in seen:
            continue
        if ident:
            seen.add(ident)
        hay = " ".join([str(item.get("caption") or ""), _author(item), _game(item)]).lower()
        if key in hay:
            result.append(item)
    return result


# ==================== Protobuf ====================

def _pb_varint(data, pos):
    result = 0
    shift = 0
    while pos < len(data):
        byte = data[pos]
        pos += 1
        result += (byte & 0x7F) * (1 << shift)
        if byte & 0x80 == 0:
            return result, pos
        shift += 7
        if shift > 63:
            break
    return None, pos


def _pb_parse(data):
    fields = {}
    pos = 0
    total = len(data)
    while pos < total:
        key, pos = _pb_varint(data, pos)
        if key is None:
            break
        field = key >> 3
        wire = key & 7
        if field == 0:
            break
        bucket = fields.setdefault(field, [])
        if wire == 0:
            value, pos = _pb_varint(data, pos)
            if value is None:
                break
            bucket.append(value)
        elif wire == 2:
            length, pos = _pb_varint(data, pos)
            if length is None:
                break
            end = pos + length
            if end > total:
                break
            bucket.append(data[pos:end])
            pos = end
        elif wire == 5:
            bucket.append(data[pos:pos + 4])
            pos += 4
        elif wire == 1:
            bucket.append(data[pos:pos + 8])
            pos += 8
        else:
            break
    return fields


def _pb_get(fields, number, index=0):
    bucket = fields.get(number)
    if not bucket or index >= len(bucket):
        return None
    return bucket[index]


def _pb_text(fields, number, index=0):
    value = _pb_get(fields, number, index)
    if value is None:
        return ""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8", "replace")
    return ""


def _pb_num(fields, number, index=0):
    value = _pb_get(fields, number, index)
    return value if isinstance(value, int) else 0


def _base64(text):
    clean = re.sub(r"[^A-Za-z0-9+/_-]", "", str(text or "")).replace("-", "+").replace("_", "/")
    if not clean:
        return b""
    clean += "=" * (-len(clean) % 4)
    try:
        return base64.b64decode(clean)
    except Exception:
        return b""


def _recall_comment(raw):
    try:
        feed = _pb_parse(raw)
        if _pb_num(feed, 7) == 2:
            return None
        content = _pb_text(feed, 3)
        if not content:
            return None
        nick = ""
        user = _pb_get(feed, 2)
        if isinstance(user, (bytes, bytearray)):
            nick = _pb_text(_pb_parse(bytes(user)), 2)
        return {"text": content, "color": 0xFFFFFF, "size": 20, "type": 1,
                "nick": nick or "快手用戶"}
    except Exception:
        return None


def _emit_safe(emit, item):
    try:
        emit(item)
    except Exception:
        pass


def _report(emit, error):
    message = str(error)[:200]
    _emit_safe(emit, {"text": "[快手] " + message[:150], "color": 0xFF5555,
                      "size": 20, "type": 1, "nick": "快手"})
    _emit_safe(emit, {"state": "error", "msg": message})


# ==================== FLV ====================

class _ReadError(Exception):
    def __init__(self, origin):
        super().__init__(str(origin))
        self.origin = origin


class _ByteReader:
    def __init__(self, reader):
        self._reader = reader
        self._chunk = b""
        self._offset = 0

    def read(self, size):
        out = bytearray()
        while len(out) < size:
            if self._offset >= len(self._chunk):
                try:
                    value = self._reader.read()
                except Exception as error:
                    raise _ReadError(error)
                if not value:
                    return None
                self._chunk = bytes(value)
                self._offset = 0
            take = min(size - len(out), len(self._chunk) - self._offset)
            out += self._chunk[self._offset:self._offset + take]
            self._offset += take
        return bytes(out)


def _uint24(data, offset):
    return data[offset] * 65536 + data[offset + 1] * 256 + data[offset + 2]


def _uint32(data, offset):
    return data[offset] * 16777216 + _uint24(data, offset + 1)


def _write_timestamp(tag, value):
    value &= 0xFFFFFFFF
    tag[4] = (value >> 16) & 0xFF
    tag[5] = (value >> 8) & 0xFF
    tag[6] = value & 0xFF
    tag[7] = (value >> 24) & 0xFF


def _is_media(kind, data, length):
    if length < 2 or kind == 18:
        return False
    if kind == 8:
        return (data[0] >> 4) != 10 or data[1] == 1
    codec = data[0] & 15
    return (codec != 7 and codec != 12) or data[1] == 1


def _timestamp(tag, clock, timeline, media):
    if not media:
        return max(0, timeline["last"])
    value = _uint24(tag, 4) + tag[7] * 16777216
    if clock["previous"] - value > 2147483648:
        clock["wrap"] += 4294967296
    clock["previous"] = value
    current = value + clock["wrap"]
    if clock["base"] is None:
        clock["base"] = current
    result = max(0, clock["start"] + current - clock["base"])
    timeline["last"] = max(timeline["last"], result)
    return result


def _mount_flv(spider, open_stream, min_duration=0):
    """把「開流 → 解析 tag → 續接」的迴圈封裝成可 yield bytes 的生成器。"""
    timeline = {"started": False, "last": -1}
    delays = [500, 1000, 2000]
    failures = 0
    while True:
        reader = open_stream()
        previous = timeline["last"]
        failure = None
        try:
            yield from _read_flv(spider, reader, timeline)
        except _ReadError as error:
            failure = error.origin
        finally:
            try:
                reader.close()
            except Exception:
                pass
        duration = timeline["last"] - previous
        if failure is None and duration >= min_duration:
            failures = 0
        else:
            if duration >= 10000:
                failures = 0
            if failures == len(delays):
                raise failure if failure else RuntimeError("直播串流反覆提前結束")
            failures += 1
        if failures:
            spider.net.sleep(delays[failures - 1])


def _read_flv(spider, reader, timeline):
    read = _ByteReader(reader).read
    header = _read_flv_header(read)
    continuing = timeline["started"]
    if not continuing:
        timeline["started"] = True
        yield header

    clock = {"base": None, "start": timeline["last"] + 1, "previous": 0, "wrap": 0}
    count = 0
    batch = []
    size = 0
    flush_at = time.time() + 0.25
    failure = None
    try:
        while True:
            tag = read(11)
            if tag is None:
                break
            kind = tag[0]
            length = _uint24(tag, 1)
            if kind not in (8, 9, 18) or _uint24(tag, 8) != 0:
                raise RuntimeError("直播 FLV 封包無效")
            data = read(length + 4)
            if data is None:
                break
            if _uint32(data, length) != length + 11:
                raise RuntimeError("直播 FLV 封包長度錯誤")
            if kind == 18 and continuing:
                continue
            media = _is_media(kind, data, len(data) - 4)
            if media:
                count += 1
            mutable = bytearray(tag)
            _write_timestamp(mutable, _timestamp(mutable, clock, timeline, media))
            batch.append(bytes(mutable))
            batch.append(data)
            size += len(mutable) + len(data)
            if size >= 65536 or time.time() >= flush_at:
                yield b"".join(batch)
                batch = []
                size = 0
                flush_at = time.time() + 0.25
    except _ReadError:
        raise
    except Exception as error:
        failure = error
    if size:
        yield b"".join(batch)
    if failure:
        raise failure
    if not count:
        raise RuntimeError("直播串流已結束，沒有可續接的媒體資料")


def _read_flv_header(read):
    header = read(9)
    if header is None or header[0] != 70 or header[1] != 76 or header[2] != 86 or header[3] != 1:
        raise RuntimeError("直播串流不是 FLV")
    offset = _uint32(header, 5)
    if offset < 9 or offset > 65536:
        raise RuntimeError("直播 FLV 標頭無效")
    extra = read(offset - 9 + 4)
    if extra is None:
        raise RuntimeError("直播 FLV 標頭不完整")
    return header + extra
