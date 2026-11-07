"""YY 直播源（Python）。

首頁分類 / 分區文件夾 / 分頁列表 / 搜尋 / 房間詳情 / 取流 / FLV 代理 / 即時彈幕。

彈幕走 h5-sinchl 的自有二進位協議：訪客登入 → AP 登入 → 進頻道 → 訂閱聊天組，
訊息體是 XML 片段（<txt data="…"/>），需按標籤白名單取值。
"""

import json
import re
import struct
import threading
import time
import uuid
from urllib.parse import quote, unquote

from base.spider import Spider as BaseSpider

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
)
YY = "https://www.yy.com"
NAME = "YY"
STYLE = {"type": "rect", "ratio": 1.78}
FOLDER = {"type": "oval", "ratio": 1}
VERSION = "5.23.0-beta.2"

BIZ = {
    "sing": "音樂", "music": "音樂", "talk": "脫口秀", "show": "脫口秀", "dance": "舞蹈", "dancing": "舞蹈",
    "pretty": "顏值", "mc": "喊麥", "sport": "體育", "travel": "戶外", "acg": "二次元",
    "game": "遊戲", "wzry": "王者榮耀", "king": "王者榮耀", "lol": "英雄聯盟", "wwyy": "英雄聯盟",
    "chicken": "和平精英", "jdqs": "和平精英", "cjzc": "和平精英", "pe": "和平精英", "lolm": "英雄聯盟手遊",
    "seer": "摩爾莊園", "zonghe": "綜合", "mobilelive": "手機直播", "nice": "猜你喜歡", "INDEX": "綜合",
}

MACHINE = "B8-97-5A-17-AD-4D"
TIMESTAMP_WRAP = 2 ** 32
AUDIO_WAIT_MS = 400
SAMPLE_RATES = (96000, 88200, 64000, 48000, 44100, 32000, 24000, 22050, 16000, 12000, 11025, 8000, 7350)
SILENT_FRAMES = {
    1: bytes([0, 200, 0, 128, 35, 128]),
    2: bytes([33, 0, 73, 144, 2, 25, 0, 35, 128]),
}
ENTITIES = {"amp": "&", "lt": "<", "gt": ">", "quot": '"', "apos": "'"}


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
        return {"class": [
            {"type_id": item["id"], "type_name": item["name"], "land": 1, "ratio": 1.78}
            for item in items
        ]}

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        extend = extend if isinstance(extend, dict) else {}
        text = str(tid)
        current = _page_number(pg)

        keyword = re.match(r"^yy/s/(.*)$", text)
        if keyword:
            return self._search_rooms(unquote(keyword.group(1) or ""), current)

        picked = str(extend.get("game") or extend.get("cateId") or "")
        if picked:
            if not re.fullmatch(r"\d+", picked):
                raise RuntimeError("分類編號格式錯誤")
            return self._game_rooms(picked, current)

        direct = re.match(r"^(?:yy/g/|game_)(\d+)$", text)
        if direct:
            return self._game_rooms(direct.group(1), current)

        items = self._groups()
        if any(item["id"] == text for item in items):
            return self._folders(text, current)
        if re.fullmatch(r"\d+", text):
            return self._game_rooms(text, current)
        if text != "yy":
            raise RuntimeError("未知直播分區")
        return self._folders(items[0]["id"], current)

    def searchContent(self, key, quick, pg="1"):
        current = _page_number(pg)
        keyword = str(key).strip()
        card = {
            "vod_id": "yy/s/" + quote(keyword, safe=""),
            "vod_name": "YY：%s" % keyword,
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
            result.append(self._detail_vod(room))
        return {"list": result}

    def playerContent(self, flag, id, vipFlags):
        room = _room_id(id)
        result = self._live_source(room["id"])
        result["position"] = 0
        result["danmaku"] = [{"name": "即時彈幕",
                              "url": self.danmakuUrl("%s:%s" % (room["platform"], room["id"]))}]
        return result

    def proxy(self, params):
        params = params if isinstance(params, dict) else {}
        room = _room_id(params.get("live"))

        def source():
            url = self._stream_source(room["id"])["url"]
            if re.search(r"\.m3u8(\?|$)", url, re.I):
                raise RuntimeError("此平台播放地址為 HLS 格式，無法代理")
            return url

        cache_key = "stream:yy:" + room["id"]
        source()
        options = {"headers": _headers(), "timeout": 15000, "callTimeout": 0}

        def open_stream():
            reader = self.net.openStream(source(), options)
            if reader.code in (401, 403, 404):
                reader.close()
                self.net.clearCache(cache_key)
                self.net.clearCache("room:yy:" + room["id"])
                reader = self.net.openStream(source(), options)
            if reader.code != 200:
                reader.close()
                raise RuntimeError("直播串流 HTTP %s" % reader.code)
            return reader

        response = self.net.stream(_mount_flv(self, open_stream, 10000, _yy_normalizer))
        return [200, "video/x-flv", response["stream"],
                {"Cache-Control": "no-store", "Accept-Ranges": "none"}]

    # ==================== 分類 ====================

    def _groups(self):
        def load():
            result = self.net.json(YY + "/yyweb/module/data/header", {"headers": _headers()})
            tabs = result.get("categoryTabs") if isinstance(result, dict) else None
            if not isinstance(tabs, list) or not tabs:
                raise RuntimeError("YY分類格式錯誤")
            items = []
            for tab in tabs:
                subs = []
                navs = tab.get("navs") if isinstance(tab.get("navs"), list) else []
                for nav in navs:
                    ident = nav.get("id")
                    title = nav.get("title")
                    if isinstance(ident, int) and title:
                        subs.append({"id": str(ident), "name": str(title).strip(), "url": _pick(nav)})
                ident = str(tab.get("id") or "")
                name = str(tab.get("title") or "").strip()
                if ident and name and subs:
                    items.append({"id": ident, "name": name, "url": _pick(tab), "subs": subs})
            if not items:
                raise RuntimeError("YY分類資料無效")
            return items

        items = self.net.cached("groups:yy:v2", {"ttl": 86400000, "persist": True}, load)
        if not isinstance(items, list) or not items or any(
                not isinstance(item, dict) or not isinstance(item.get("subs"), list) for item in items):
            return load()
        return items

    def _find(self, game):
        for tab in self._groups():
            if tab["id"] == game:
                return tab
            for sub in tab["subs"]:
                if sub["id"] == game:
                    return sub
        return None

    def _games(self, group=""):
        tab = next((item for item in self._groups() if item["id"] == str(group)), None)
        return tab["subs"] if tab else []

    def _directory(self, game):
        if game == "0":
            return {"moduleId": -1, "biz": "index", "subBiz": "idx"}

        def load():
            item = self._find(game)
            if not item:
                raise RuntimeError("未知YY分類")
            response = self.net.req(item["url"], {"headers": _headers()})
            if response.get("error") or response.get("code") != 200:
                raise RuntimeError("YY分類載入失敗：%s" % (response.get("error") or response.get("code")))
            content = str(response.get("content") or "")
            block = re.search(r"pageBar\s*:\s*\{([^}]+)\}", content)
            source = block.group(1) if block else ""
            total = re.search(r"\btotalCount\s*:\s*(\d+)", source)
            module = re.search(r"\bmoduleId\s*:\s*(-?\d+)", source)
            biz = re.search(r"""\bbiz\s*:\s*["']([^"']+)["']""", source)
            sub = re.search(r"""\bsubBiz\s*:\s*["']([^"']+)["']""", source)
            if not total or not module or not biz or not sub:
                raise RuntimeError("YY分類分頁資料無效")
            if int(module.group(1)) == 0 and int(total.group(1)) == 0:
                return {"total": 0}
            if int(module.group(1)) <= 0 or biz.group(1) == "null" or sub.group(1) == "null":
                raise RuntimeError("YY分類分頁資料無效")
            return {"moduleId": int(module.group(1)), "biz": biz.group(1), "subBiz": sub.group(1)}

        return self.net.cached("directory:yy:" + game, {"ttl": 20000, "stale": False}, load)

    def _rooms(self, game, current):
        directory = self._directory(game)
        if directory.get("total") == 0:
            return _page([], current, 60, 0)
        params = dict(directory)
        params.update({"page": current, "pageSize": 60})
        result = self.net.json(YY + "/more/page.action", {"params": params, "headers": _headers()})
        data = result.get("data") if isinstance(result, dict) else None
        if result.get("resultCode") != 0 or not isinstance(data, dict) \
                or not isinstance(data.get("totalCount"), int) or data["totalCount"] < 0:
            raise RuntimeError("YY直播列表格式錯誤")
        total = data["totalCount"]
        count = max(1, -(-total // 60))
        if current > count or (data.get("data") is None and total == 0):
            return _page([], current, 60, total)
        listing = data.get("data")
        if not isinstance(listing, list):
            raise RuntimeError("YY直播列表格式錯誤")
        cards = [item for item in (_yy_card(raw) for raw in listing) if item]
        return _page(cards, current, 60, total)

    def _game_rooms(self, game, current):
        return self.net.cached("list:yy:%s:%s" % (game, current),
                               {"ttl": 20000, "stale": False},
                               lambda: self._rooms(game, current))

    def _search_rooms(self, keyword, current):
        result = self.net.json(YY + "/apiSearch/doSearch.json", {
            "params": {"q": keyword, "t": 1, "n": current, "s": 15},
            "headers": _headers(),
        })
        data = result.get("data") if isinstance(result, dict) else None
        response = data.get("searchResult", {}).get("response", {}).get("1") \
            if isinstance(data, dict) else None
        if not isinstance(result, dict) or result.get("success") is not True \
                or result.get("status") != 0 or not isinstance(data, dict) \
                or not isinstance(data.get("totalPage"), int) or data["totalPage"] < 0 \
                or not isinstance(response, dict) or not isinstance(response.get("docs"), list) \
                or not isinstance(response.get("numFound"), int) or response["numFound"] < 0:
            raise RuntimeError("YY搜尋回應格式錯誤")
        count = max(1, data["totalPage"])
        cards = [] if current > count else [item for item in
                                            (_yy_card(raw) for raw in response["docs"]) if item]
        return {"list": cards, "page": current, "pagecount": count,
                "limit": 15, "total": response["numFound"]}

    def _folders(self, group, current):
        items = self._games(group)
        if not items:
            return self._game_rooms(group, current)
        pics = self._covers([item["id"] for item in items])
        cards = [{
            "vod_id": "game_" + item["id"],
            "vod_name": item["name"],
            "vod_pic": pics.get(item["id"], ""),
            "vod_tag": "folder",
            "style": dict(FOLDER),
        } for item in items]
        return {"list": cards, "page": current, "pagecount": 1,
                "limit": max(1, len(items)), "total": len(items)}

    def _covers(self, ids):
        if not ids:
            return {}

        def load():
            result = {}
            errors = []

            def run(ident):
                try:
                    page = self._rooms(ident, 1)
                    result[ident] = next(
                        (item["vod_pic"] for item in page["list"] if item.get("vod_pic")), "")
                except Exception as error:
                    errors.append(error)
                    result[ident] = ""

            threads = [threading.Thread(target=run, args=(ident,), daemon=True) for ident in ids]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            return result

        return self.net.cached("cover:yy:" + ",".join(ids),
                               {"ttl": 43200000, "persist": True}, load)

    # ==================== 房間 ====================

    def _room(self, ident):
        def load():
            sid, ssid = (ident.split("_", 1) + [""])[:2]
            if not ssid:
                response = self.net.req(YY + "/" + sid, {"headers": _headers()})
                if response.get("error") or response.get("code") != 200:
                    raise RuntimeError("YY房間載入失敗：%s" % (response.get("error") or response.get("code")))
                content = str(response.get("content") or "")
                block = re.search(r"\bvar\s+pageInfo\s*=\s*\{([\s\S]*?)\r?\n\s*\};", content)
                source = block.group(1) if block else ""
                found_sid = re.search(r"""\bsid\s*:\s*["'](\d+)["']""", source)
                found_ssid = re.search(r"""\bssid\s*:\s*["'](\d+)["']""", source)
                sid = found_sid.group(1) if found_sid else None
                ssid = found_ssid.group(1) if found_ssid else None
                if not sid or not ssid:
                    raise RuntimeError("YY房間不存在或資料無效")
            result = self.net.json("%s/api/liveInfoDetail/%s/%s/0" % (YY, sid, ssid),
                                   {"headers": _headers()})
            if result.get("resultCode") != 0:
                raise RuntimeError("YY詳情回應錯誤")
            room = result.get("data") if isinstance(result, dict) else None
            if not isinstance(room, dict) or not re.fullmatch(r"\d+", str(room.get("sid") or "")) \
                    or not re.fullmatch(r"\d+", str(room.get("ssid") or "")) or not room.get("name"):
                raise RuntimeError("YY目前未開播或房間不存在")
            return room

        return self.net.cached("room:yy:" + ident, {"ttl": 5000, "stale": False}, load)

    def _stream_source(self, ident):
        def load():
            room = self._room(ident)
            sid = str(room["sid"])
            ssid = str(room["ssid"])
            stamp = int(time.time() * 1000)
            result = self.net.json("https://stream-manager.yy.com/v3/channel/streams", {
                "method": "POST",
                "postType": "json",
                "params": {"uid": 0, "cid": sid, "sid": ssid, "appid": 0,
                           "sequence": stamp, "encode": "json"},
                "headers": dict(_headers(), **{"Origin": YY,
                                               "Content-Type": "application/json; charset=utf-8"}),
                "data": {
                    "head": {"seq": stamp, "appidstr": "0", "bidstr": "120", "cidstr": sid,
                             "sidstr": ssid, "uid64": 0, "client_type": 108, "client_ver": VERSION,
                             "stream_sys_ver": 1, "app": "www.yy.com", "playersdk_ver": VERSION,
                             "thundersdk_ver": "0", "streamsdk_ver": VERSION},
                    "client_attribute": {"client": "web", "model": "web0", "cpu": "",
                                         "graphics_card": "", "os": "chrome", "osversion": "148.0.0.0",
                                         "vsdk_version": "", "app_identify": "", "app_version": "",
                                         "business": "", "width": "1920", "height": "1080", "scale": "",
                                         "client_type": 8, "h265": 0},
                    "avp_parameter": {"version": 1, "client_type": 8, "service_type": 0, "imsi": 0,
                                      "send_time": stamp // 1000, "line_seq": -1, "gear": 4,
                                      "ssl": 1, "stream_format": 0},
                },
            })
            url = _stream_url(result)
            joiner = "&" if "?" in url else "?"
            return {"parse": 0,
                    "url": "%s%splayeruid=0&uuid=%s" % (url, joiner, self._uid()),
                    "header": _headers(), "format": "video/x-flv"}

        return self.net.cached("stream:yy:" + ident, {"ttl": 5000, "stale": False}, load)

    def _live_source(self, ident):
        source = dict(self._stream_source(ident))
        source["url"] = self.proxyUrl({"live": "yy:" + ident})
        return source

    def _detail_vod(self, room):
        data = self._room(room["id"])
        online = str(data.get("liveOn", "1")) != "0"
        title = _wrap(data.get("desc"), 80)
        actor = _wrap(data.get("name"), 40)
        game = BIZ.get(str(data.get("biz") or "").strip(), "")
        users = _int(data.get("users"), 0)
        started = _int(data.get("startTime"), 0)
        duration = _duration_text(int(time.time()) - started) if online and started > 0 else ""

        vod = _yy_card(data)
        if not vod:
            raise RuntimeError("YY房間資料不完整")
        vod["vod_name"] = title or actor or vod["vod_name"]
        vod["vod_remarks"] = ("%s人在看" % _count(users)) if users > 0 else ("直播中" if online else "未開播")
        vod["vod_actor"] = actor
        vod["type_name"] = game or NAME

        lines = ["狀態：" + ("直播中" + ("（已開播 %s）" % duration if duration else "") if online else "未開播")]
        if game:
            lines.append("分區：" + game)
        if users > 0:
            lines.append("人氣：" + _count(users))
        total = _int(data.get("totalViewer"), 0)
        if total > 0:
            lines.append("累計觀看：" + _count(total))
        if actor:
            lines.append("主播：" + actor)
        uid = str(data.get("uid") or "").strip()
        if uid:
            lines.append("主播UID：" + uid)
        if _int(data.get("linkMic"), 0) > 0:
            lines.append("連麥中")

        vod["vod_content"] = "\n".join(lines)
        vod["vod_play_from"] = NAME
        if not vod.get("vod_play_url"):
            vod["vod_play_url"] = "觀看直播$" + vod["vod_id"]
        return vod

    def _uid(self):
        if not self._device:
            self._device = uuid.uuid4().hex
        return self._device

    def _log(self, message):
        try:
            self.log(message)
        except Exception:
            pass

    # ==================== 彈幕 ====================

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
        data = self._room(room["id"])
        room["top"] = str(data.get("sid"))
        room["sub"] = str(data.get("ssid"))
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
            "stopped": False, "ready": False, "switching": False, "activity": time.time(),
            "chat": time.time(), "attempts": 0, "ready_at": 0.0, "informed": False,
            "socket": None, "heartbeat": None, "watchdog": None, "fallback": None,
            "session": None,
        }
        lock = threading.RLock()
        options = {"timeout": 10000, "idle": 90000, "reconnect": True,
                   "headers": {"Origin": "https://www.yy.com"}}

        def stop():
            with lock:
                if ctx["stopped"]:
                    return
                ctx["stopped"] = True
                heartbeat, watchdog, fallback = ctx["heartbeat"], ctx["watchdog"], ctx["fallback"]
                socket, session = ctx["socket"], ctx["session"]
                ctx["heartbeat"] = ctx["watchdog"] = ctx["fallback"] = None
                ctx["socket"] = ctx["session"] = None
            _cancel(heartbeat)
            _cancel(watchdog)
            _cancel(fallback)
            if session:
                try:
                    session["clear"]()
                except Exception:
                    pass
            if socket:
                try:
                    socket.cancel()
                except Exception:
                    pass

        def clear_heartbeat():
            with lock:
                heartbeat = ctx["heartbeat"]
                ctx["heartbeat"] = None
            _cancel(heartbeat)

        def send(connection, data):
            try:
                if connection.send(data):
                    return True
            except Exception:
                pass
            clear_heartbeat()
            return False

        def mark_ready():
            if ctx["ready"]:
                return
            ctx["ready"] = True
            ctx["ready_at"] = time.time()
            _emit_safe(emit, {"state": "ready"})

        def fail(error):
            if ctx["stopped"]:
                return
            stop()
            message = str(error)[:512]
            _emit_safe(emit, {"state": "error", "msg": message})
            if not ctx["informed"]:
                ctx["informed"] = True
                _emit_safe(emit, {"text": "[YY] 彈幕中斷：" + message[:120],
                                  "color": 0xFF5555, "size": 20, "type": 1, "nick": "YY"})

        def tick():
            try:
                if ctx["stopped"]:
                    return
                idle = time.time() - ctx["activity"]
                if not ctx["ready"] and idle > 15:
                    move("等待訂閱完成逾時")
                elif ctx["ready"] and time.time() - ctx["chat"] > 300:
                    move("訂閱後長時間沒有彈幕")
            finally:
                if not ctx["stopped"]:
                    arm()

        def arm():
            with lock:
                if ctx["watchdog"]:
                    ctx["watchdog"].cancel()
                if ctx["stopped"]:
                    return
                timer = threading.Timer(5.0, tick)
                timer.daemon = True
                ctx["watchdog"] = timer
            timer.start()

        def do_move():
            with lock:
                ctx["switching"] = False
                if ctx["stopped"] or ctx["ready"] or ctx["activity"] > ctx["stamp"]:
                    return
                if ctx["ready_at"] and time.time() - ctx["ready_at"] > 30:
                    ctx["attempts"] = 0
                ctx["attempts"] += 1
                attempts = ctx["attempts"]
                old = ctx["socket"]
                ctx["socket"] = None
            if attempts >= 8:
                fail("YY 彈幕連線屢次失敗：%s" % (ctx.get("reason") or ""))
                return
            if old:
                try:
                    old.cancel()
                except Exception:
                    pass
            connect()

        def move(reason):
            if ctx["stopped"]:
                return
            clear_heartbeat()
            ctx["ready"] = False
            ctx["switching"] = True
            ctx["stamp"] = ctx["activity"]
            ctx["reason"] = reason
            _emit_safe(emit, {"state": "retrying", "msg": "彈幕連線中斷，等待恢復"})
            with lock:
                socket = ctx["socket"]
                previous = ctx["fallback"]
            if socket:
                try:
                    socket.cancel()
                except Exception:
                    pass
            _cancel(previous)
            timer = threading.Timer(3.0, do_move)
            timer.daemon = True
            with lock:
                ctx["fallback"] = timer
            timer.start()

        def open_(connection):
            clear_heartbeat()
            ctx["ready"] = False
            ctx["activity"] = time.time()
            ctx["chat"] = time.time()
            session = _yy_session(room, lambda data: send(connection, data), mark_ready)
            ctx["session"] = session
            if session["start"]():
                timer = _Ticker(5.0, lambda: beat(connection))
                with lock:
                    ctx["heartbeat"] = timer
            arm()

        def beat(connection):
            if ctx["stopped"]:
                return
            try:
                session = ctx["session"]
                if session:
                    session["pulse"]()
            except Exception as error:
                fail(error)

        def connect():
            with lock:
                old = ctx["socket"]
                ctx["socket"] = None
            if old:
                try:
                    old.cancel()
                except Exception:
                    pass
            url = "wss://h5-sinchl.yy.com/websocket?appid=yymwebh5&version=3.2.14&uuid=%s" % _uuid()
            connection = self.net.connect(url, options,
                                          lambda conn, event: dispatch(conn, event))
            with lock:
                ctx["socket"] = connection
                ctx["activity"] = time.time()
            arm()

        def dispatch(connection, event):
            if ctx["stopped"]:
                return
            kind = event.get("type")
            try:
                if kind == "open":
                    open_(connection)
                elif kind == "message" and event.get("binary"):
                    ctx["activity"] = time.time()
                    session = ctx["session"]
                    if not session:
                        return
                    for item in session["decode"](event.get("content")):
                        if ctx["stopped"]:
                            return
                        _emit_safe(emit, item)
                        ctx["chat"] = time.time()
                elif kind == "retry":
                    clear_heartbeat()
                    ctx["ready"] = False
                    _emit_safe(emit, {"state": "retrying", "msg": "彈幕連線中斷，等待恢復"})
                elif kind in ("error", "close"):
                    if ctx["switching"]:
                        return
                    move(str(event.get("error") or "連線關閉"))
            except Exception as error:
                fail(error)

        ctx["activity"] = time.time()
        ctx["chat"] = time.time()
        connect()
        return stop

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


def _pick(item):
    url = item.get("url") if isinstance(item, dict) else ""
    if isinstance(url, str) and re.match(r"^https?://www\.yy\.com/", url):
        return url.replace("http:", "https:", 1)
    return ""


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
    match = re.fullmatch(r"yy:([A-Za-z0-9_-]{1,64})", head)
    if not match:
        match = re.search(r"yy:([A-Za-z0-9_-]{1,64})", plain)
        tail = ""
    if not match:
        raise RuntimeError("直播房間編號格式錯誤")
    if not re.fullmatch(r"\d+(?:_\d+)?", match.group(1)):
        raise RuntimeError("YY直播房間編號格式錯誤")
    if tail and not re.fullmatch(r"(hls|flv|flv-full|flv-hd|flv-sd1|flv-sd2|\d{1,2})", tail):
        raise RuntimeError("直播播放線路格式錯誤")
    return {"platform": "yy", "id": match.group(1), "extra": tail}


def _headers():
    return {"User-Agent": UA, "Referer": YY + "/"}


def _image(value):
    if not isinstance(value, str):
        return ""
    return "https://" + value[2:] if value.startswith("//") else value


def _card(platform, ident, name, pic, remark):
    if not ident or not name:
        return None
    return {"vod_id": "%s:%s" % (platform, ident), "vod_name": str(name),
            "vod_pic": _image(pic), "vod_remarks": remark or "", "style": dict(STYLE)}


def _yy_card(item):
    if not isinstance(item, dict):
        return None
    sid = str(item.get("sid") or "")
    ssid = "" if item.get("ssid") is None else str(item.get("ssid"))
    if not re.fullmatch(r"\d+", sid) or (item.get("ssid") is not None and not re.fullmatch(r"\d+", ssid)):
        return None
    offline = str(item.get("liveOn")) == "0"
    ident = "%s_%s" % (sid, ssid) if ssid else sid
    return _card("yy", ident, item.get("desc") or item.get("name"),
                 item.get("thumb2") or item.get("thumb") or item.get("headurl") or item.get("avatar"),
                 str(item.get("name") or "") + (" · 未開播" if offline else ""))


def _stream_url(result):
    if not isinstance(result, dict):
        raise RuntimeError("YY播放資料無效")
    code = result.get("result", 0)
    streams = result.get("channel_stream_info", {}).get("streams") \
        if isinstance(result.get("channel_stream_info"), dict) else None
    addresses = result.get("avp_info_res", {}).get("stream_line_addr") \
        if isinstance(result.get("avp_info_res"), dict) else None
    if code != 0 or not isinstance(streams, list) or not isinstance(addresses, dict):
        raise RuntimeError("YY播放資料無效")
    for item in streams:
        if not isinstance(item, dict) or item.get("type") != 2 or not isinstance(item.get("json"), str):
            continue
        try:
            info = json.loads(item["json"])
        except Exception:
            continue
        if not isinstance(info, dict) or info.get("is_cdn") != 1 or info.get("encoderType") != 100:
            continue
        node = addresses.get("%s_%s" % (item.get("appidstr"), item.get("stream_name")))
        url = node.get("cdn_info", {}).get("url") if isinstance(node, dict) else None
        if isinstance(url, str) and re.match(r"^https?://", url):
            return url
    raise RuntimeError("YY目前沒有可播放的直播")


def _count(value):
    try:
        number = float(value)
    except Exception:
        return ""
    if number <= 0:
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
    if hours >= 24:
        return "%d天%d小時" % (hours // 24, hours % 24)
    if hours > 0:
        return "%d小時%d分鐘" % (hours, minutes)
    if minutes > 0:
        return "%d分鐘" % minutes
    return "%d秒" % seconds


def _wrap(value, limit=120):
    text = re.sub(r"\s*\r?\n\s*", " ", str(value if value is not None else ""))
    return text.strip()[:limit]


def _uuid():
    return str(uuid.uuid4())


class _Ticker:
    def __init__(self, seconds, action):
        self.seconds = seconds
        self.action = action
        self._timer = None
        self._stopped = False
        self._lock = threading.Lock()
        self._arm(seconds)

    def _arm(self, delay):
        with self._lock:
            if self._stopped:
                return
            timer = threading.Timer(delay, self._tick)
            timer.daemon = True
            self._timer = timer
        timer.start()

    def _tick(self):
        if self._stopped:
            return
        try:
            self.action()
        except Exception:
            pass
        self._arm(self.seconds)

    def cancel(self):
        with self._lock:
            self._stopped = True
            timer = self._timer
            self._timer = None
        if timer:
            timer.cancel()


def _cancel(handle):
    if handle is None:
        return
    try:
        handle.cancel()
    except Exception:
        pass


def _emit_safe(emit, item):
    try:
        emit(item)
    except Exception:
        pass


# ==================== YY 二進位協議 ====================

def _pack_number(value, size=4):
    return (int(value) & ((1 << (size * 8)) - 1)).to_bytes(size, "little")


def _pack_blob(data, size=2):
    return _pack_number(len(data), size) + data


def _pack_string(value):
    return _pack_blob(str(value).encode("utf-8"))


def _pack_packet(uri, *parts):
    body = b"".join(parts)
    return _pack_number(len(body) + 10) + _pack_number(uri) + _pack_number(200, 2) + body


class _Reader:
    def __init__(self, data):
        self.data = bytes(data)
        self.offset = 0

    def remaining(self):
        return len(self.data) - self.offset

    def read(self, size):
        if size < 0 or size > self.remaining():
            raise RuntimeError("YY 彈幕封包不完整")
        value = self.data[self.offset:self.offset + size]
        self.offset += size
        return value

    def number(self, size=4):
        value = self.read(size)
        return int.from_bytes(value, "little")

    def blob(self, size=2):
        return self.read(self.number(size))

    def string(self):
        return self.blob().decode("utf-8", "replace")

    def wide(self):
        raw = self.blob(4)
        try:
            return raw.decode("utf-16-le")
        except Exception:
            raise RuntimeError("YY 彈幕文字格式錯誤")


def _unescape(text):
    if re.search(r"[\u0000-\u0008\u000b\u000c\u000e-\u001f\ufffe\uffff]", text):
        raise RuntimeError("YY 彈幕文字實體錯誤")
    if re.search(r"&(?!(?:#x[0-9a-fA-F]+|#[0-9]+|amp|lt|gt|quot|apos);)", text):
        raise RuntimeError("YY 彈幕文字實體錯誤")

    def replace(match):
        name = match.group(1)
        if not name.startswith("#"):
            return ENTITIES[name]
        number = int(name[2:], 16) if name[:2].lower() == "#x" else int(name[1:])
        if (number < 0x20 and number not in (9, 10, 13)) or number > 0x10FFFF \
                or 0xD800 <= number <= 0xDFFF or number in (0xFFFE, 0xFFFF):
            raise RuntimeError("YY 彈幕文字實體錯誤")
        return chr(number)

    return re.sub(r"&(#x[0-9a-fA-F]+|#[0-9]+|amp|lt|gt|quot|apos);", replace, text)


def _attributes(source):
    attributes = {}
    while source.strip():
        match = re.match(r"""\s+([A-Za-z_:][\w:.-]*)\s*=\s*(["'])(.*?)\2""", source, re.S)
        if not match or match.group(1) in attributes:
            raise RuntimeError("YY 彈幕文字格式錯誤")
        attributes[match.group(1)] = _unescape(match.group(3))
        source = source[match.end():]
    return attributes


TOKEN = re.compile(
    r"<!--.*?-->|<\?.*?\?>|</?[A-Za-z_][\w:.-]*(?:[^<>\"']|\"[^\"<]*\"|'[^'<]*')*>", re.S)
TAG = re.compile(r"^<(/)?([A-Za-z_][\w:.-]*)(.*?)(/)?>$", re.S)


def _yy_text(value):
    if not re.match(r"^\s*<", value):
        return value
    if re.search(r"<!DOCTYPE|<!ENTITY", value, re.I):
        raise RuntimeError("YY 彈幕文字格式錯誤")
    parts = []
    stack = []
    offset = 0
    root = False
    for match in TOKEN.finditer(value):
        gap = value[offset:match.start()]
        if "<" in gap or (not stack and gap.strip()):
            raise RuntimeError("YY 彈幕文字格式錯誤")
        _unescape(gap)
        offset = match.end()
        token = match.group(0)
        if token.startswith("<!--"):
            continue
        if token.startswith("<?"):
            if root or not re.match(r"^<\?xml\s.*\?>$", token, re.S):
                raise RuntimeError("YY 彈幕文字格式錯誤")
            continue
        tag = TAG.match(token)
        if not tag:
            raise RuntimeError("YY 彈幕文字格式錯誤")
        if tag.group(1):
            if tag.group(3).strip() or tag.group(4) or not stack or stack.pop() != tag.group(2):
                raise RuntimeError("YY 彈幕文字格式錯誤")
            continue
        if not stack:
            if root:
                raise RuntimeError("YY 彈幕文字格式錯誤")
            root = True
        attributes = _attributes(tag.group(3))
        if tag.group(2) == "txt" and "data" in attributes:
            parts.append(attributes["data"])
        if len(stack) >= 20:
            raise RuntimeError("YY 彈幕文字層級過多")
        if not tag.group(4):
            stack.append(tag.group(2))
    if not root or stack or value[offset:].strip():
        raise RuntimeError("YY 彈幕文字格式錯誤")
    return "".join(parts)


def _is_rgb(value):
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 0xFFFFFF


def _yy_session(room, send, on_ready):
    top = _int(room.get("top"), 0)
    sub = _int(room.get("sub"), 0)
    if not (0 < top <= 0xFFFFFFFF and 0 < sub <= 0xFFFFFFFF):
        raise RuntimeError("YY 彈幕房間無效")
    ctx = {"uid": 0, "stage": "closed", "pending": b""}
    instance = _uuid()

    def transmit(uri, *parts):
        if ctx["stage"] == "closed":
            return False
        if send(_pack_packet(uri, *parts)):
            return True
        clear()
        return False

    def clear():
        ctx["uid"] = 0
        ctx["stage"] = "closed"
        ctx["pending"] = b""

    def start():
        clear()
        ctx["stage"] = "guest"
        machine = _pack_string(MACHINE)
        guest = b"".join((_pack_string(""), _pack_number(0), machine, machine,
                          _pack_number(0), _pack_string("yymwebh5")))
        return transmit(778244, _pack_string(""), _pack_number(19822), _pack_blob(guest, 4))

    def login(reader):
        reader.string()
        result = reader.number()
        if result != 200 or reader.number() != 20078:
            raise RuntimeError("YY 彈幕訪客登入失敗")
        guest = _Reader(reader.blob(4))
        guest.string()
        if guest.number() not in (0, 200):
            raise RuntimeError("YY 彈幕訪客登入失敗")
        legacy = guest.number()
        guest.number()
        account = guest.string()
        password = guest.string()
        cookie = guest.blob()
        guest.blob()
        guest.string()
        guest.string()
        uid = guest.number(8) if guest.remaining() else 0
        ctx["uid"] = uid or legacy
        if not ctx["uid"] or not account or not password or not cookie:
            raise RuntimeError("YY 彈幕訪客資料無效")
        auth = b"".join((
            _pack_string(account), _pack_string(password), _pack_number(2), _pack_number(0),
            _pack_number(0), _pack_string("yytianlaitv"), _pack_string(MACHINE),
            _pack_string("yymwebn_yymwebh5"), _pack_number(0), _pack_number(0),
            _pack_number(0), _pack_number(0), _pack_string(instance),
        ))
        ctx["stage"] = "ap"
        transmit(775684, _pack_blob(auth, 4), _pack_number(259), _pack_number(ctx["uid"], 8),
                 _pack_number(0, 1), _pack_blob(b""), _pack_blob(cookie), _pack_string("259:0"),
                 _pack_string(""), _pack_string(""), _pack_string(""), _pack_number(0, 1),
                 _pack_number(0), _pack_number(0), _pack_number(-1), _pack_string(""),
                 _pack_number(1), _pack_string("BCIFVer"), _pack_string("V2"))

    def join():
        uri = 2048258
        service = "channelAuther"
        trace = "F%d_yymwebh5_%d_1" % (ctx["uid"], int(time.time() * 1000))
        ext = b"".join((_pack_number(2), _pack_number(1), _pack_blob(_pack_number(top)),
                        _pack_number(103), _pack_string(trace)))
        headers = b"".join((
            _pack_number(0x01000008), _pack_number(uri), _pack_number(0x02000010),
            _pack_number(259), _pack_number(ctx["uid"], 8), _pack_number(0x0400000c),
            _pack_number(0), _pack_number(0), _pack_number(0x05000008), _pack_number(0),
            _pack_number(0x06000000 | (22 + len(service))), _pack_number(0), _pack_number(0, 2),
            _pack_number(0), _pack_string(service), _pack_number(0), _pack_string(""),
            _pack_number(0x07000000 | (4 + len(ext))), ext, _pack_number(0x08000006),
            _pack_string(""), _pack_number(4286085240),
        ))
        payload = b"".join((_pack_number(ctx["uid"]), _pack_number(top), _pack_number(sub),
                            _pack_number(0), _pack_number(ctx["uid"], 8)))
        if transmit(538456, _pack_number(ctx["uid"], 8), _pack_number(1), _pack_number(31)):
            transmit(513035, _pack_string(""), _pack_number(uri), _pack_number(0, 2),
                     _pack_blob(payload, 4), _pack_blob(headers, 4))

    def groups(entries):
        flat = []
        for entry in entries:
            flat.extend(entry)
        return transmit(537944, _pack_number(ctx["uid"], 8), _pack_number(len(entries)),
                        b"".join(_pack_number(value) for value in flat), _pack_string(""))

    def channel(reader):
        nonlocal top, sub
        reader.string()
        uri = reader.number()
        code = reader.number(2)
        data = reader.blob(4)
        if uri != 2048514 or ctx["stage"] != "join":
            return
        if code != 200:
            raise RuntimeError("YY 彈幕進入頻道失敗")
        result = _Reader(data)
        actual_top = result.number()
        result.number()
        actual_sub = result.number()
        result.number()
        result.number()
        result.number(1)
        result.string()
        if actual_top != top or actual_sub != sub:
            pass
        if isinstance(actual_top, int) and 0 < actual_top <= 0xFFFFFFFF:
            top = actual_top
        if isinstance(actual_sub, int) and 0 < actual_sub <= 0xFFFFFFFF:
            sub = actual_sub
        if not groups([[1, 0, top, 0], [2, 0, sub, 0], [1024, 259, sub, top],
                       [768, 259, 0, top], [256, 259, 0, top], [256, 259, sub, top]]):
            return
        if not groups([[1, 0, top, 0], [2, 0, sub, 0]]):
            return
        ctx["stage"] = "subscribed"
        on_ready()

    def chat(uri, reader):
        if uri == 533080:
            reader.number(8)
            reader.number(8)
            appid = reader.number()
            data = reader.blob(4)
        else:
            appid = reader.number(2)
            reader.number()
            data = reader.blob()
        if appid != 31:
            return []
        packet = _Reader(data)
        if packet.number() != len(data):
            raise RuntimeError("YY 彈幕訊息長度錯誤")
        if packet.number() != 3104600:
            return []
        if packet.number(2) != 200:
            raise RuntimeError("YY 彈幕訊息狀態錯誤")
        packet.number()
        actual_top = packet.number()
        actual_sub = packet.number()
        if actual_top != top or actual_sub != sub:
            return []
        fmt = _Reader(packet.blob())
        fmt.number()
        fmt.wide()
        color = fmt.number()
        fmt.number()
        text = _yy_text(fmt.wide())
        fmt.number()
        if not text.strip():
            return []
        return [{"text": text, "color": color if _is_rgb(color) and color != 0 else 0xFFFFFF,
                 "size": 20, "type": 1}]

    def dispatch(uri, reader, code):
        if uri == 795140:
            raise RuntimeError("YY 彈幕連線被關閉")
        if uri == 778500 and ctx["stage"] == "guest":
            login(reader)
        elif uri == 775940 and ctx["stage"] == "ap":
            reader.number()
            if reader.number() != 200 or reader.string() != "259:0":
                raise RuntimeError("YY 彈幕服務登入失敗")
            ctx["stage"] = "join"
            join()
        elif uri == 512011:
            channel(reader)
        elif ctx["stage"] == "subscribed" and uri in (533080, 28760):
            if code != 200:
                raise RuntimeError("YY 彈幕聊天封包狀態錯誤")
            return chat(uri, reader)
        return []

    def decode(chunk):
        if ctx["stage"] == "closed":
            return []
        data = bytes(chunk)
        pending = ctx["pending"]
        if len(pending) + len(data) > 1048576:
            raise RuntimeError("YY 彈幕封包過大")
        if pending:
            data = pending + data
        messages = []
        offset = 0
        total = len(data)
        while offset + 10 <= total:
            size = struct.unpack_from("<I", data, offset)[0]
            if size < 10 or size > 1048576:
                raise RuntimeError("YY 彈幕封包長度錯誤")
            if offset + size > total:
                break
            uri = struct.unpack_from("<I", data, offset + 4)[0]
            code = struct.unpack_from("<H", data, offset + 8)[0]
            if uri in (778500, 775940, 512011) and code != 200:
                raise RuntimeError("YY 彈幕服務回應失敗")
            messages.extend(dispatch(uri, _Reader(data[offset + 10:offset + size]), code))
            offset += size
            if ctx["stage"] == "closed":
                return messages
        ctx["pending"] = data[offset:] if offset < total else b""
        return messages

    def pulse():
        if ctx["stage"] == "closed":
            return False
        if ctx["stage"] in ("guest", "ap"):
            return True
        return transmit(794116, _pack_number(0))

    return {"start": start, "decode": decode, "pulse": pulse, "clear": clear}


# ==================== YY FLV 歸一化 ====================

def _yy_normalizer():
    state = {"base": None, "restart": False, "config": None, "silence": None,
             "duration": 0.0, "next_audio": None, "reference": None, "last": {}}

    def timestamp(value):
        if state["reference"] is not None:
            value -= int((value - state["reference"] + TIMESTAMP_WRAP / 2) // TIMESTAMP_WRAP) * TIMESTAMP_WRAP
        state["reference"] = max(state["reference"] if state["reference"] is not None else value, value)
        if state["base"] is None:
            state["base"] = value
        if state["restart"]:
            state["base"] = min(state["base"], value - max(state["last"].values()) - 1)
            state["restart"] = False
        return value - state["base"]

    def fill_audio(stamp):
        while state["silence"] and state["next_audio"] + AUDIO_WAIT_MS < stamp:
            value = int(round(state["next_audio"]))
            yield _audio_tag(max(0, value), state["silence"])
            state["last"][8] = value
            state["next_audio"] += state["duration"]

    def normalize(source, data):
        kind = source[0]
        body = data[:len(data) - 4]
        stamp = _uint24(source, 4) + source[7] * 16777216
        if kind == 18 and state["last"]:
            state["restart"] = True
            state["next_audio"] = None
            state["reference"] = None
        if kind == 8 and len(body) >= 4 and (body[0] >> 4) == 10 and body[1] == 0 \
                and bytes(body) != state["config"]:
            state["config"] = bytes(body)
            state["silence"], state["duration"] = _audio_config(body)
            state["next_audio"] = None

        packets = []
        if kind in (8, 9) and len(body) >= 2 and body[1] == 1:
            stamp = timestamp(stamp)
            if kind in state["last"] and stamp <= state["last"][kind]:
                return packets
            if state["next_audio"] is None:
                state["next_audio"] = stamp
            if kind == 9:
                packets.extend(fill_audio(stamp))
            else:
                state["next_audio"] = stamp + state["duration"]
            state["last"][kind] = stamp
        else:
            stamp -= state["base"] or 0
        tag = bytearray(source)
        _write_timestamp(tag, max(0, int(stamp)))
        packets.append((bytes(tag), data))
        return packets

    return normalize


def _audio_config(data):
    profile = data[2] >> 3
    index = (data[2] & 7) * 2 + (data[3] >> 7)
    channels = (data[3] >> 3) & 15
    if profile != 2 or index >= len(SAMPLE_RATES) or channels not in SILENT_FRAMES or data[3] & 7:
        return None, 0.0
    return bytes([data[0], 1]) + SILENT_FRAMES[channels], 1024000.0 / SAMPLE_RATES[index]


def _audio_tag(stamp, data):
    tag = bytearray(11)
    body = bytearray(len(data) + 4)
    tag[0] = 8
    tag[1] = len(data) >> 16 & 0xFF
    tag[2] = len(data) >> 8 & 0xFF
    tag[3] = len(data) & 0xFF
    _write_timestamp(tag, stamp)
    body[:len(data)] = data
    struct.pack_into(">I", body, len(data), len(data) + 11)
    return bytes(tag), bytes(body)


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


def _mount_flv(spider, open_stream, min_duration=0, factory=None):
    timeline = {"started": False, "last": -1}
    delays = [500, 1000, 2000]
    failures = 0
    while True:
        reader = open_stream()
        previous = timeline["last"]
        failure = None
        normalize = factory() if factory else None
        try:
            yield from _read_flv(spider, reader, timeline, normalize)
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


def _read_flv(spider, reader, timeline, normalize=None):
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
            packets = normalize(tag, data) if normalize else [(tag, data)]
            for item_tag, item_data in packets:
                if item_tag[0] == 18 and continuing:
                    continue
                media = _is_media(item_tag[0], item_data, len(item_data) - 4)
                if media:
                    count += 1
                mutable = bytearray(item_tag)
                _write_timestamp(mutable, _timestamp(mutable, clock, timeline, media))
                batch.append(bytes(mutable))
                batch.append(item_data)
                size += len(mutable) + len(item_data)
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
