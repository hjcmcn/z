"""斗魚直播源（Python）。

首頁分類 / 遊戲文件夾 / 分區列表 / 搜尋 / 房間詳情 / 多清晰度播放 / 回看 / FLV 代理 / STT 彈幕。

播放簽名由官方 /swf_api/homeH5Enc 下發的混淆腳本計算，Python 側沒有等價實現，
經 self.js.eval 在隔離環境執行（內建 md5X），與原 JS 源完全一致。
"""

import json
import re
import struct
import threading
import time
import uuid
from urllib.parse import parse_qsl, urlsplit

from base.spider import Spider as BaseSpider

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
)
MOBILE_UA = (
    "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)
DOUYU = "https://www.douyu.com"
NAME = "斗魚"
STYLE = {"type": "rect", "ratio": 1.78}
FOLDER = {"type": "oval", "ratio": 1}

RATES = [{"name": "原畫", "value": ""}, {"name": "超清", "value": "3"}, {"name": "高清", "value": "2"}]
GROUPS = ("1", "15", "9", "2", "8", "11")

DANMU_HOSTS = (
    "wss://danmuproxy.douyu.com:8504/",
    "wss://danmuproxy.douyu.com:8501/",
    "wss://danmuproxy.douyu.com:8502/",
    "wss://danmuproxy.douyu.com:8503/",
)
DANMU_COLORS = (0xFFFFFF, 0xFF2E2E, 0x00CCFF, 0x66FF00, 0xFF6600, 0xCC00FF, 0xF6447F)
MAX_PACKET = 1048576


class Spider(BaseSpider):
    def init(self, extend=""):
        self.options = _options(extend)
        self._device = ""
        self._active_stop = None
        self._seq = 0
        self._lock = threading.RLock()

    # ==================== 入口 ====================

    def homeContent(self, filter):
        items = self._groups()
        result = {"class": [
            {"type_id": item["id"], "type_name": item["name"], "land": 1, "ratio": 1.78}
            for item in items
        ]}
        if filter:
            try:
                table = self._catalog()
                result["filters"] = {
                    item["id"]: [{
                        "key": "game",
                        "name": "遊戲",
                        "value": [{"n": sub["name"], "v": sub["id"]} for sub in table.get(item["id"], [])],
                    }]
                    for item in items
                }
            except Exception as error:
                self._log("斗魚遊戲篩選暫時無法取得：%s" % str(error)[:80])
        return result

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        extend = extend if isinstance(extend, dict) else {}
        text = str(tid)
        current = _page_number(pg)

        keyword = re.match(r"^douyu/s/(.*)$", text)
        if keyword:
            from urllib.parse import unquote
            return self._search_rooms(unquote(keyword.group(1) or ""), current)

        picked = str(extend.get("game") or extend.get("cateId") or "")
        if picked:
            if not re.fullmatch(r"\d+", picked):
                raise RuntimeError("遊戲編號格式錯誤")
            return self._game_rooms(picked, current)

        direct = re.match(r"^(?:douyu/g/|game_)(\d+)$", text)
        if direct:
            return self._game_rooms(direct.group(1), current)

        items = self._groups()
        if not any(item["id"] == text for item in items):
            if text != "douyu":
                if not re.fullmatch(r"\d+", text):
                    raise RuntimeError("未知直播分區")
                return self._game_rooms(text, current)
            return self._folders(items[0]["id"], current)
        return self._folders(text, current)

    def searchContent(self, key, quick, pg="1"):
        from urllib.parse import quote
        current = _page_number(pg)
        keyword = str(key).strip()
        card = {
            "vod_id": "douyu/s/" + quote(keyword, safe=""),
            "vod_name": "斗魚：%s" % keyword,
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
            vod = self._detail_vod(room)
            result.append(vod)
        return {"list": result}

    def playerContent(self, flag, id, vipFlags):
        room = _room_id(id)
        values = self._parallel_values(
            [(self._live_source, (room["id"], room["extra"])),
             (self._timeshift, (room["id"],))],
        )
        source = values[0]
        timeshift = values[1]
        result = source
        if isinstance(timeshift, dict):
            result["timeshift"] = timeshift
        result["position"] = 0
        result["danmaku"] = [{"name": "即時彈幕",
                              "url": self.danmakuUrl("%s:%s" % (room["platform"], room["id"]))}]
        return result

    def proxy(self, params):
        params = params if isinstance(params, dict) else {}
        if params.get("replay"):
            room = _room_id(params.get("replay"))
            payload = self._replay(room["id"], params.get("time"))
            return [200, "application/json; charset=utf-8",
                    json.dumps(payload, ensure_ascii=False), {"Cache-Control": "no-store"}]

        room = _room_id(params.get("live"))
        rate = _rate(room["extra"])

        def source():
            url = self._url(room["id"], rate)
            if re.search(r"\.m3u8(\?|$)", url, re.I):
                raise RuntimeError("此平台播放地址為 HLS 格式，無法代理")
            return url

        cache_key = "stream:douyu:%s:%s" % (room["id"], rate)
        source()
        options = {"headers": _headers(), "timeout": 15000, "callTimeout": 0}

        def open_stream():
            reader = self.net.openStream(source(), options)
            if reader.code in (401, 403, 404):
                reader.close()
                self.net.clearCache(cache_key)
                self.net.clearCache("room:douyu:" + room["id"])
                reader = self.net.openStream(source(), options)
            if reader.code != 200:
                reader.close()
                raise RuntimeError("直播串流 HTTP %s" % reader.code)
            return reader

        response = self.net.stream(_mount_flv(self, open_stream, 0))
        return [200, "video/x-flv", response["stream"],
                {"Cache-Control": "no-store", "Accept-Ranges": "none"}]

    # ==================== 目錄 ====================

    def _groups(self):
        def load():
            listing = self._api(DOUYU + "/japi/weblist/api/getC1List")
            if not isinstance(listing, list) or not listing:
                raise RuntimeError("斗魚主分類格式錯誤")
            return [{"id": str(item.get("cid1")), "name": item.get("cname1")} for item in listing]

        items = self.net.cached("groups:douyu", {"ttl": 86400000, "persist": True}, load)
        shown = [item for item in
                 (next((raw for raw in items if raw["id"] == ident), None) for ident in GROUPS)
                 if item and item.get("name")]
        return shown or items

    def _catalog(self):
        def load():
            data = self.net.json("https://m.douyu.com/api/cate/list",
                                 {"headers": dict(_headers(), Referer="https://m.douyu.com/")})
            payload = data.get("data") if isinstance(data, dict) else None
            listing = payload.get("cate2Info") if isinstance(payload, dict) else None
            if not isinstance(listing, list) or not listing:
                raise RuntimeError("斗魚分類格式錯誤")
            table = {}
            for item in listing:
                parent = str(item.get("cate1Id") or "")
                ident = str(item.get("cate2Id") or "")
                name = item.get("cate2Name") or ""
                if parent not in GROUPS or not ident or ident == "0" or not name:
                    continue
                pic = _image(item.get("icon") or item.get("pic")) or \
                    "https://static.douyu.com/images/default_cate.png"
                table.setdefault(parent, []).append(
                    {"id": ident, "name": name, "pic": pic,
                     "rooms": _int(item.get("count"), 0)})
            return table

        return self.net.cached("catalog:douyu", {"ttl": 86400000, "persist": True}, load)

    def _games(self, group=""):
        table = self._catalog()
        if group:
            return table.get(group, [])
        merged = []
        for value in table.values():
            merged.extend(value)
        return merged

    # ==================== 介面 ====================

    def _api(self, url, options=None):
        result = self.net.json(url, options or {})
        if not isinstance(result, dict):
            raise RuntimeError("斗魚接口回應格式錯誤")
        code = result.get("error") if result.get("error") is not None else result.get("code")
        if code not in (0, "0"):
            raise RuntimeError("斗魚：%s" % (result.get("msg") or "接口回應錯誤"))
        if result.get("data") is None:
            raise RuntimeError("斗魚接口缺少資料")
        return result["data"]

    def _did(self):
        if not self._device:
            self._device = uuid.uuid4().hex
        return self._device

    def _stream(self, ident, rate):
        key = "stream:douyu:%s:%s" % (ident, rate)
        return self.net.cached(key, {"ttl": 5000, "stale": False},
                               lambda: self._fetch_stream(ident, rate))

    def _fetch_stream(self, ident, rate):
        scripts = self.net.cached(
            "sign:douyu:" + ident, {"ttl": 300000, "stale": False},
            lambda: self._api(DOUYU + "/swf_api/homeH5Enc", {"params": {"rids": ident}}))
        source = scripts.get("room" + ident) if isinstance(scripts, dict) else None
        if not isinstance(source, str) or not source:
            raise RuntimeError("斗魚播放簽名資料無效")
        signed = self._sign(source, ident)
        params = dict(parse_qsl(signed, keep_blank_values=True))
        payload = dict(params)
        payload["cdn"] = ""
        payload["rate"] = rate or 0
        return self._api(DOUYU + "/lapi/live/getH5Play/" + ident,
                         {"method": "POST", "postType": "form", "data": payload})

    def _sign(self, source, ident):
        code = ("(() => { var CryptoJS = {MD5: md5X};\n%s\n"
                "return ub98484234(rid, did, tt); })()") % source
        value = self.js.eval(code, {
            "globals": {"rid": str(ident), "did": self._did(), "tt": str(int(time.time()))},
            "timeout": 5000,
        })
        if not isinstance(value, str) or not value:
            raise RuntimeError("斗魚播放簽名計算失敗")
        return value

    def _url(self, ident, rate):
        data = self._stream(ident, rate or "0")
        rtmp = data.get("rtmp_url")
        live = data.get("rtmp_live")
        if rtmp and live:
            return _https(rtmp).rstrip("/") + "/" + str(live).lstrip("/")
        if data.get("hls_url"):
            return _https(data["hls_url"])
        raise RuntimeError("斗魚目前沒有可播放的直播")

    def _live_source(self, ident, extra):
        rate = _rate(extra)
        url = self._url(ident, rate)
        fmt = "application/x-mpegURL" if urlsplit(url).path.endswith(".m3u8") else "video/x-flv"
        target = url if fmt == "application/x-mpegURL" else self.proxyUrl(
            {"live": "douyu:" + ident + (("@" + rate) if rate else "")})
        return {"parse": 0, "url": target, "header": _headers(), "format": fmt}

    # ==================== 回看 ====================

    def _replay_info(self, ident):
        def load():
            result = self.net.json(DOUYU + "/wgapi/live/liveweb/roomapi/biz/getSwitch",
                                   {"params": {"rid": ident}, "headers": _headers()})
            data = result.get("data") if isinstance(result, dict) else None
            if not isinstance(result, dict) or result.get("code") not in (0, "0"):
                raise RuntimeError("斗魚回看資料無效")
            playback = data.get("playback") if isinstance(data, dict) else None
            if not isinstance(playback, dict) or not isinstance(data.get("roomInfo"), dict):
                raise RuntimeError("斗魚回看資料無效")
            show = _int(playback.get("show"), 0)
            start = _int(playback.get("startTime"), 0) * 1000
            now = time.time() * 1000
            if show == 1 and (start <= 0 or start >= now):
                raise RuntimeError("斗魚回看時間無效")
            window = (24 if _int(data["roomInfo"].get("aiLiveSummary"), 0) == 1 else 2) * 3600000
            return {"show": show, "start": start, "window": window}

        return self.net.cached("replay:douyu:" + ident, {"ttl": 60000, "stale": False}, load)

    def _timeshift(self, ident):
        try:
            info = self._replay_info(ident)
            if info["show"] != 1:
                return None
            return {"url": self.proxyUrl({"replay": "douyu:" + ident, "time": "{time}"}),
                    "start": info["start"], "window": info["window"]}
        except Exception:
            self._log("斗魚回看資料暫時無法取得，保留直播播放")
            return None

    def _replay(self, ident, value):
        text = str(value if value is not None else "")
        if not re.fullmatch(r"\d+", text):
            raise RuntimeError("回看時間無效")
        moment = int(text)
        if moment == 0:
            return self._live_source(ident, "")
        now = time.time() * 1000
        if moment <= 0 or moment >= now:
            raise RuntimeError("回看時間無效")
        info = self._replay_info(ident)
        if info["show"] != 1:
            raise RuntimeError("斗魚目前未提供回看")
        start = max(moment, info["start"], now - info["window"])
        data = self._api(DOUYU + "/japi/universe/playback/getVodStream", {"params": {
            "rid": ident, "startTime": int(-(-start // 1000)), "pt": 2, "rate": 0,
            "client_sys": "web", "timeshiftReplay": 1, "isloopclick": 0,
        }})
        url = data.get("timeshiftUrl") if isinstance(data, dict) else None
        if not isinstance(url, str) or not re.match(r"^https?://", url):
            raise RuntimeError("斗魚沒有回傳回看播放網址")
        return {"parse": 0, "url": url, "header": _headers(), "format": "application/x-mpegURL"}

    # ==================== 列表 ====================

    def _folders(self, group, current):
        items = self._games(group)
        if not items:
            return self._group_rooms(group, current)
        cards = [{
            "vod_id": "game_" + item["id"],
            "vod_name": item["name"],
            "vod_pic": item["pic"],
            "vod_tag": "folder",
            "style": dict(FOLDER),
            "vod_remarks": ("%s間" % item["rooms"]) if item["rooms"] else "",
        } for item in items]
        return {"list": cards, "page": current, "pagecount": 1,
                "limit": max(1, len(items)), "total": len(items)}

    def _game_rooms(self, game, current):
        return self.net.cached("list:douyu:2_%s:%s" % (game, current),
                               {"ttl": 20000, "stale": False},
                               lambda: self._rooms("2_" + game, current))

    def _group_rooms(self, group, current):
        return self.net.cached("list:douyu:1_%s:%s" % (group, current),
                               {"ttl": 20000, "stale": False},
                               lambda: self._rooms("1_" + group, current))

    def _rooms(self, game, current):
        data = self._api("%s/gapi/rkc/directory/mixList/%s/%s" % (DOUYU, game, current))
        listing = data.get("rl")
        if not isinstance(listing, list) or not isinstance(data.get("pgcnt"), int):
            raise RuntimeError("斗魚直播列表格式錯誤")
        cards = [item for item in (
            _card("douyu", raw.get("rid"), raw.get("rn"), raw.get("rs16") or raw.get("rs1"), raw.get("nn"))
            for raw in listing) if item]
        return {"list": cards, "page": current, "pagecount": max(1, data["pgcnt"]), "limit": 120}

    def _search_rooms(self, keyword, current):
        if re.fullmatch(r"[0-9]+", keyword):
            if current != 1:
                return {"list": [], "page": current, "pagecount": 1, "limit": 1}
            result = self.detailContent(["douyu:" + keyword])
            cards = [dict(item, style=dict(STYLE)) for item in result["list"]]
            return {"list": cards, "page": 1, "pagecount": 1, "limit": 1}
        # 搜索接口必須帶 dy_did（裝置標識），否則大概率回 error 9「搜索过于频繁」（實測）
        data = self._api(DOUYU + "/japi/search/api/searchShow",
                         {"params": {"kw": keyword, "page": current, "pageSize": 20},
                          "headers": dict(_headers(), **{"Cookie": "dy_did=" + self._did()})})
        listing = data.get("relateShow")
        if not isinstance(listing, list) or not isinstance(data.get("total"), int):
            raise RuntimeError("斗魚搜尋回應格式錯誤")
        cards = [item for item in (
            _card("douyu", raw.get("rid"), raw.get("roomName"), raw.get("roomSrc"), raw.get("nickName"))
            for raw in listing) if item]
        return _page(cards, current, 20, data["total"])

    # ==================== 詳情 ====================

    def _room_info(self, ident):
        def load():
            result = self.net.json("https://m.douyu.com/api/room/info", {
                "params": {"rid": ident},
                "headers": dict(_headers(), **{"User-Agent": MOBILE_UA, "Referer": "https://m.douyu.com/"}),
            })
            room = result.get("data", {}).get("roomInfo") if isinstance(result, dict) else None
            if not room or not room.get("rid"):
                raise RuntimeError("斗魚房間不存在")
            return room

        return self.net.cached("info:douyu:" + ident, {"ttl": 15000, "stale": False}, load)

    def _room_extra(self, ident):
        def load():
            try:
                result = self.net.json(DOUYU + "/betard/" + ident, {
                    "headers": dict(_headers(), Accept="application/json, text/plain, */*")})
                room = result.get("room") if isinstance(result, dict) else None
                return room if isinstance(room, dict) else {}
            except Exception:
                return {}

        return self.net.cached("betard:douyu:" + ident, {"ttl": 300000, "stale": False}, load)

    def _detail_vod(self, room):
        ident = room["id"]
        info, extra = self._parallel_values(
            [(self._room_info, (ident,)), (self._room_extra, (ident,))])
        if not isinstance(extra, dict):
            extra = {}
        live = str(info.get("isLive")) == "1"
        title = _wrap(info.get("roomName"), 80)
        actor = _wrap(info.get("nickname"), 40)
        game = _wrap(info.get("cate2Name") or extra.get("second_lvl_name"), 40)
        started = int(float(info.get("showTime") or extra.get("show_time") or 0))
        duration = _duration_text(int(time.time()) - started) if live and started > 0 else ""
        heat = _wrap(info.get("hn"), 20)

        name = "%s - %s" % (title, actor) if title and actor else (title or actor or str(info.get("rid")))
        vod = _card(room["platform"], str(info.get("rid")), name,
                    info.get("roomSrc") or extra.get("room_src") or info.get("avatar"),
                    ("熱度 " + heat) if live and heat and heat != "0" else ("直播中" if live else "未開播"))
        vod["vod_actor"] = actor
        vod["type_name"] = game

        lines = ["狀態：" + ("直播中" + ("（已開播 %s）" % duration if duration else "") if live else "未開播")]
        if not live and started > 0:
            lines.append("上次開播：" + _clock_text(started))
        if game:
            lines.append("分區：" + game)
        if live and heat and heat != "0":
            lines.append("熱度：" + heat)
        if actor:
            lines.append("主播：" + actor)
        uid = str(info.get("ownerId") or extra.get("owner_uid") or "").strip()
        if uid:
            lines.append("主播UID：" + uid)
        level_info = extra.get("levelInfo")
        level = str(level_info.get("level") or "").strip() if isinstance(level_info, dict) else ""
        if level:
            lines.append("主播等級：" + level)
        badge = _fans_badge(extra.get("fans_bn"))
        if badge:
            lines.append("粉絲牌：" + badge)
        biz = extra.get("room_biz_all")
        club = _wrap(biz.get("clubOrgName") if isinstance(biz, dict) else "", 40)
        if club:
            lines.append("公會：" + club)
        city = _wrap(extra.get("cityname") or info.get("liveCity"), 30)
        if city:
            lines.append("所在地：" + city)
        notice = _wrap(info.get("notice") or extra.get("show_details"), 120)
        if notice:
            lines.append("公告：" + notice)

        vod["vod_content"] = "\n".join(lines)
        vod["vod_play_from"] = NAME
        vod["vod_play_url"] = "#".join(
            "%s$%s%s" % (item["name"], vod["vod_id"], ("@" + item["value"]) if item["value"] else "")
            for item in RATES)
        return vod

    # ==================== 彈幕（STT） ====================

    def danmaku(self, id, emit):
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

        room = _room_id(id)
        stop = self._subscribe(room, emit)
        with self._lock:
            if seq != self._seq:
                try:
                    stop()
                except Exception:
                    pass
                return lambda: None
            self._active_stop = stop
        return stop

    def _subscribe(self, room, emit):
        ctx = {
            "gate": 0, "attempts": 0, "stopped": False, "ready": False,
            "activity": time.time(), "generation": 0, "ready_at": 0.0,
            "informed": False, "socket": None, "pending": b"", "timer": None,
        }
        lock = threading.RLock()
        options = {
            "timeout": 10000,
            "idle": 150000,
            "reconnect": True,
            "headers": {
                "Origin": "https://www.douyu.com",
                "Referer": "https://www.douyu.com/",
                "User-Agent": UA,
            },
        }

        def url():
            return DANMU_HOSTS[ctx["gate"] % len(DANMU_HOSTS)]

        def stop():
            with lock:
                if ctx["stopped"]:
                    return
                ctx["stopped"] = True
                timer = ctx["timer"]
                ctx["timer"] = None
                socket = ctx["socket"]
                ctx["socket"] = None
            if timer:
                try:
                    timer.cancel()
                except Exception:
                    pass
            if socket:
                try:
                    socket.cancel()
                except Exception:
                    pass

        def send(connection, text):
            try:
                return bool(connection.send(_stt_packet(text)))
            except Exception:
                return False

        def mark_ready(connection):
            if ctx["ready"]:
                return
            ctx["ready"] = True
            ctx["ready_at"] = time.time()
            _emit_safe(emit, {"state": "ready"})
            if not send(connection, "type@=joingroup/rid@=%s/gid@=1/" % room["id"]):
                fail("斗魚彈幕進房失敗")

        def fail(error):
            if ctx["stopped"]:
                return
            stop()
            message = str(error)[:512]
            _emit_safe(emit, {"state": "error", "msg": message})
            if not ctx["informed"]:
                ctx["informed"] = True
                _emit_safe(emit, {"text": "[斗魚] 彈幕中斷：" + message[:120],
                                  "color": 0xFF5555, "size": 20, "type": 1, "nick": "斗魚"})

        def open_(connection):
            ctx["ready"] = False
            ctx["pending"] = b""
            ctx["activity"] = time.time()
            login = ("type@=loginreq/roomid@=%s/dfl@=/username@=/uid@=/ver@=20220825/"
                     "aver@=218101901/ct@=0/" % room["id"])
            if not send(connection, login):
                return
            arm()

        def tick():
            try:
                if ctx["stopped"]:
                    return
                idle = time.time() - ctx["activity"]
                if not ctx["ready"] and idle > 12:
                    reconnect("等待登入回應逾時")
                elif ctx["ready"] and idle > 150:
                    reconnect("長時間沒有封包")
            finally:
                if not ctx["stopped"]:
                    arm()

        def arm():
            with lock:
                if ctx["timer"]:
                    ctx["timer"].cancel()
                if ctx["stopped"]:
                    return
                timer = threading.Timer(5.0, tick)
                timer.daemon = True
                ctx["timer"] = timer
            timer.start()

        def connect():
            with lock:
                old = ctx["socket"]
                ctx["socket"] = None
                ctx["generation"] += 1
                generation = ctx["generation"]
            if old:
                try:
                    old.cancel()
                except Exception:
                    pass
            connection = self.net.connect(
                url(), options,
                lambda conn, event: dispatch(conn, event, generation))
            with lock:
                ctx["socket"] = connection
                ctx["activity"] = time.time()
            arm()

        def reconnect(reason):
            if ctx["stopped"]:
                return
            ctx["ready"] = False
            ctx["pending"] = b""
            ctx["gate"] += 1
            if ctx["gate"] % len(DANMU_HOSTS) == 0:
                if ctx["ready_at"] and time.time() - ctx["ready_at"] > 30:
                    ctx["attempts"] = 0
                ctx["attempts"] += 1
                if ctx["attempts"] >= 2:
                    fail("斗魚彈幕連線屢次失敗：%s" % (reason or ""))
                    return
            _emit_safe(emit, {"state": "retrying", "msg": "彈幕連線中斷，等待恢復"})
            connect()

        def dispatch(connection, event, generation):
            if ctx["stopped"] or generation != ctx["generation"]:
                return
            kind = event.get("type")
            try:
                if kind == "open":
                    open_(connection)
                elif kind == "message" and event.get("binary"):
                    ctx["activity"] = time.time()
                    for fields in _stt_packets(event.get("content"), ctx):
                        if ctx["stopped"]:
                            return
                        name = fields.get("type")
                        if name == "loginres":
                            mark_ready(connection)
                        elif name == "pingreq":
                            send(connection, "type@=pingres/")
                        elif name == "keeplive":
                            send(connection, "type@=keeplive/")
                        elif name == "error":
                            code = str(fields.get("code") or "")
                            fail("斗魚彈幕服務端拒絕（code=%s）：%s" % (
                                code or "未知", str(fields.get("msg") or fields.get("error") or "")[:120]))
                            return
                        elif name == "chatmsg" and str(fields.get("txt") or "").strip():
                            _emit_safe(emit, {"text": fields["txt"],
                                              "color": _douyu_color(fields.get("col")),
                                              "size": 20, "type": 1})
                            ctx["activity"] = time.time()
                elif kind == "retry":
                    ctx["ready"] = False
                    _emit_safe(emit, {"state": "retrying", "msg": "彈幕連線中斷，等待恢復"})
                elif kind in ("error", "close"):
                    reconnect(str(event.get("error") or "連線關閉"))
            except Exception as error:
                fail(error)

        connect()
        return stop

    def _log(self, message):
        try:
            self.log(message)
        except Exception:
            pass

    def _parallel_values(self, jobs):
        """並行取值（保序）；首個異常向外拋，其餘異常記為 None。"""
        results = [None] * len(jobs)
        errors = [None] * len(jobs)

        def run(index, fn, args):
            try:
                results[index] = fn(*args)
            except Exception as error:
                errors[index] = error

        threads = [threading.Thread(target=run, args=(index, fn, args), daemon=True)
                   for index, (fn, args) in enumerate(jobs)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        if errors[0]:
            raise errors[0]
        return results

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


def _int(value, default=0):
    try:
        return int(float(value))
    except Exception:
        return default


def _room_id(value):
    from urllib.parse import unquote
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
    match = re.fullmatch(r"douyu:([A-Za-z0-9_-]{1,64})", head)
    if not match:
        match = re.search(r"douyu:([A-Za-z0-9_-]{1,64})", plain)
        tail = ""
    if not match:
        raise RuntimeError("直播房間編號格式錯誤")
    if tail and not re.fullmatch(r"(hls|flv|flv-full|flv-hd|flv-sd1|flv-sd2|\d{1,2})", tail):
        raise RuntimeError("直播播放線路格式錯誤")
    return {"platform": "douyu", "id": match.group(1), "extra": tail}


def _headers():
    return {"User-Agent": UA, "Referer": DOUYU + "/"}


def _image(value):
    if not isinstance(value, str):
        return ""
    return "https://" + value[2:] if value.startswith("//") else value


def _card(platform, ident, name, pic, remark):
    if not ident or not name:
        return None
    return {"vod_id": "%s:%s" % (platform, ident), "vod_name": str(name),
            "vod_pic": _image(pic), "vod_remarks": remark or "", "style": dict(STYLE)}


def _https(value):
    text = str(value)
    if text.startswith("//"):
        text = "https:" + text
    return re.sub(r"^http:", "https:", text)


def _rate(extra):
    text = str(extra or "")
    for item in RATES:
        if item["value"] and item["value"] == text:
            return item["value"]
    return ""


def _duration_text(value):
    try:
        seconds = int(float(value))
    except Exception:
        return ""
    if seconds <= 0:
        return ""
    hours = seconds // 3600
    minutes = seconds % 3600 // 60
    if hours >= 24:
        return "%d天%d小時" % (hours // 24, hours % 24)
    if hours > 0:
        return "%d小時%d分鐘" % (hours, minutes)
    if minutes > 0:
        return "%d分鐘" % minutes
    return "%d秒" % seconds


def _clock_text(value):
    try:
        moment = time.localtime(int(float(value)))
    except Exception:
        return ""
    return time.strftime("%m-%d %H:%M", moment)


def _wrap(value, limit=120):
    text = re.sub(r"\s*\r?\n\s*", " ", str(value if value is not None else ""))
    return text.strip()[:limit]


def _fans_badge(value):
    if not value:
        return ""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            return value.strip()
    if isinstance(value, dict):
        return str(value.get("bn") or "").strip()
    return ""


# ==================== STT ====================

def _stt_packet(text):
    body = text.encode("utf-8") + b"\x00"
    return struct.pack("<III", len(body) + 8, len(body) + 8, 689) + body


def _stt_packets(chunk, ctx):
    data = bytes(chunk)
    pending = ctx.get("pending") or b""
    if len(pending) + len(data) > MAX_PACKET:
        raise RuntimeError("斗魚彈幕封包過大")
    if pending:
        data = pending + data
    messages = []
    offset = 0
    total = len(data)
    while offset + 12 <= total:
        length = struct.unpack_from("<I", data, offset)[0]
        if length < 9 or length > MAX_PACKET - 4 or length != struct.unpack_from("<I", data, offset + 4)[0]:
            raise RuntimeError("斗魚彈幕封包格式錯誤")
        end = offset + length + 4
        if end > total:
            break
        fields = {}
        body = data[offset + 12:end - 1].decode("utf-8", "replace")
        for item in body.split("/"):
            index = item.find("@=")
            if index >= 0:
                fields[item[:index]] = item[index + 2:].replace("@S", "/").replace("@A", "@")
        messages.append(fields)
        offset = end
    ctx["pending"] = data[offset:] if offset < total else b""
    return messages


def _douyu_color(value=""):
    text = re.sub(r"^0+", "", str(value or ""))
    if len(text) == 1 and text in "123456":
        return DANMU_COLORS[int(text)]
    return 0xFFFFFF


def _emit_safe(emit, item):
    try:
        emit(item)
    except Exception:
        pass


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
