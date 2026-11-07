"""虎牙直播源（Python）。

首頁分區 / 遊戲文件夾 / 分區列表 / 搜尋 / 房間詳情 / 多線路播放 / FLV 代理 / TARS 彈幕。
"""

import base64
import json
import re
import struct
import threading
import time
from urllib.parse import parse_qsl, quote, unquote

from base.spider import Spider as BaseSpider

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
)
HUYA = "https://www.huya.com"
NAME = "虎牙"
STYLE = {"type": "rect", "ratio": 1.78}
FOLDER = {"type": "oval", "ratio": 1}

GROUPS = [
    {"id": "1", "name": "網遊"},
    {"id": "2", "name": "單機"},
    {"id": "3", "name": "手遊"},
    {"id": "8", "name": "娛樂"},
]
DANMU_URL = "wss://cdnws.api.huya.com/"
PULSE = bytes([0, 20, 29, 0, 12])


class Spider(BaseSpider):
    def init(self, extend=""):
        self.options = _options(extend)
        self._active_stop = None
        self._seq = 0
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
        text = str(tid)
        current = _page_number(pg)

        keyword = re.match(r"^huya/s/(.*)$", text)
        if keyword:
            return self._search_rooms(unquote(keyword.group(1) or ""), current)

        picked = str(extend.get("game") or extend.get("cateId") or "")
        if picked:
            if not re.fullmatch(r"\d+", picked):
                raise RuntimeError("遊戲編號格式錯誤")
            return self._rooms(picked, current)

        direct = re.match(r"^(?:huya/g/|game_)(\d+)$", text)
        if direct:
            return self._rooms(direct.group(1), current)

        group = next((item for item in GROUPS if item["id"] == text), None)
        if group is None and text == "huya":
            group = GROUPS[0]
        if group is None:
            if not re.fullmatch(r"\d+", text):
                raise RuntimeError("未知直播分區")
            return self._rooms(text, current)
        return self._folders(group["id"], current)

    def searchContent(self, key, quick, pg="1"):
        current = _page_number(pg)
        keyword = str(key).strip()
        card = {
            "vod_id": "huya/s/" + quote(keyword, safe=""),
            "vod_name": "虎牙：%s" % keyword,
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
        cdn = params.get("cdn")

        def source():
            url = self._stream_url(room["id"], cdn)
            if re.search(r"\.m3u8(\?|$)", url, re.I):
                raise RuntimeError("此平台播放地址為 HLS 格式，無法代理")
            return url

        cache_key = "room:huya:" + room["id"]
        source()
        options = {"headers": _headers(), "timeout": 15000, "callTimeout": 0}

        def open_stream():
            reader = self.net.openStream(source(), options)
            if reader.code in (401, 403, 404):
                reader.close()
                self.net.clearCache(cache_key)
                reader = self.net.openStream(source(), options)
            if reader.code != 200:
                reader.close()
                raise RuntimeError("直播串流 HTTP %s" % reader.code)
            return reader

        response = self.net.stream(_mount_flv(self, open_stream, 10000))
        return [200, "video/x-flv", response["stream"],
                {"Cache-Control": "no-store", "Accept-Ranges": "none"}]

    # ==================== 介面 ====================

    def _games(self, group=""):
        def load():
            data = self.net.json("https://live.cdn.huya.com/liveconfig/game/bussLive",
                                 {"params": {"bussType": group}, "headers": _headers()})
            listing = data.get("data") if isinstance(data, dict) else None
            if not isinstance(listing, list):
                raise RuntimeError("虎牙分類缺少資料")
            items = []
            for item in listing:
                if _int(item.get("isHide"), 0) == 1:
                    continue
                ident = str(_int(item.get("gid"), 0))
                name = item.get("gameFullName") or ""
                if ident == "0" or not name:
                    continue
                items.append({
                    "id": ident, "name": name, "rooms": _int(item.get("profileNum"), 0),
                    "pic": "https://huyaimg.msstatic.com/cdnimage/game/%s-MS.jpg" % ident,
                })
            return items

        return self.net.cached("catalog:huya:%s" % group, {"ttl": 86400000, "persist": True}, load)

    def _room(self, ident):
        def load():
            result = self.net.json("https://mp.huya.com/cache.php", {
                "params": {"m": "Live", "do": "profileRoom", "roomid": ident},
                "headers": _headers(),
            })
            if result.get("status") != 200 or not isinstance(result.get("data"), dict) \
                    or not isinstance(result["data"].get("profileInfo"), dict):
                raise RuntimeError("虎牙：%s" % (result.get("message") or "房間不存在"))
            return result["data"]

        return self.net.cached("room:huya:" + ident, {"ttl": 5000, "stale": False}, load)

    def _lines(self, ident):
        data = self._room(ident)
        if data.get("realLiveStatus") != "ON":
            raise RuntimeError("虎牙主播目前未開播")
        stream = data.get("stream")
        lines = stream.get("baseSteamInfoList") if isinstance(stream, dict) else None
        if not isinstance(lines, list):
            raise RuntimeError("虎牙缺少播放線路")
        available = [item for item in lines if _is_number(item.get("iWebPriorityRate"))
                     and item["iWebPriorityRate"] > 0]
        available.sort(key=lambda item: item["iWebPriorityRate"], reverse=True)
        if not available:
            raise RuntimeError("虎牙沒有可播放的線路")
        return available

    def _stream_url(self, ident, cdn):
        line = next((item for item in self._lines(ident) if item.get("sCdnType") == cdn), None)
        if not line:
            raise RuntimeError("虎牙播放線路已失效")
        return _huya_url(line)

    def _live_source(self, ident):
        values = [{"n": item.get("sCdnType"),
                   "v": self.proxyUrl({"live": "huya:" + ident, "cdn": item.get("sCdnType")})}
                  for item in self._lines(ident)]
        return {"parse": 0, "url": {"values": values, "position": 0},
                "header": _headers(), "format": "video/x-flv"}

    def _folders(self, group, current):
        items = self._games(group)
        if not items:
            return self._rooms(group, current)
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

    def _rooms(self, game, current):
        result = self.net.json(HUYA + "/cache.php", {
            "params": {"m": "LiveList", "do": "getLiveListByPage",
                       "gameId": game, "tagAll": 0, "page": current},
            "headers": _headers(),
        })
        data = result.get("data") if isinstance(result, dict) else None
        if result.get("status") != 200 or not isinstance(data, dict) \
                or not isinstance(data.get("datas"), list) or not isinstance(data.get("totalPage"), int):
            raise RuntimeError("虎牙直播列表格式錯誤")
        cards = [item for item in (
            _card("huya", raw.get("profileRoom"),
                  raw.get("introduction") or raw.get("roomName") or raw.get("nick"),
                  raw.get("screenshot"), raw.get("nick"))
            for raw in data["datas"]) if item]
        return {"list": cards, "page": current, "pagecount": max(1, data["totalPage"]),
                "limit": data.get("pageSize") or 120, "total": data.get("totalCount")}

    def _search_rooms(self, keyword, current):
        if re.fullmatch(r"[0-9]+", keyword):
            if current != 1:
                return {"list": [], "page": current, "pagecount": 1, "limit": 1}
            result = self.detailContent(["huya:" + keyword])
            cards = [dict(item, style=dict(STYLE)) for item in result["list"]]
            return {"list": cards, "page": 1, "pagecount": 1, "limit": 1}
        result = self.net.json("https://search.cdn.huya.com/", {
            "params": {"m": "Search", "do": "getSearchContent", "q": keyword,
                       "typ": -5, "rows": 20, "start": (current - 1) * 20, "v": 4},
            "headers": _headers(),
        })
        data = result.get("response", {}).get("1") if isinstance(result, dict) else None
        header = result.get("responseHeader") if isinstance(result, dict) else None
        if not isinstance(header, dict) or header.get("status") != 0 \
                or not isinstance(data, dict) or not isinstance(data.get("docs"), list) \
                or not isinstance(data.get("numFound"), int):
            raise RuntimeError("虎牙搜尋回應格式錯誤")
        # 服務端對 start>0 的請求會回超過 rows 條（實測第 2 頁回 40 條），
        # 不截斷的話相鄰兩頁會重疊 20 條，翻頁看起來像「回到上一頁」
        docs = data["docs"][:20]
        cards = [item for item in (
            _card("huya", raw.get("room_id"), raw.get("live_intro") or raw.get("game_nick"),
                  raw.get("game_avatarUrl180"),
                  str(raw.get("game_nick") or "") + ("" if raw.get("gameLiveOn") else " · 未開播"))
            for raw in docs) if item]
        return _page(cards, current, 20, data["numFound"])

    def _detail_vod(self, room):
        data = self._room(room["id"])
        live = data.get("liveData") if isinstance(data.get("liveData"), dict) else {}
        profile = data.get("profileInfo") if isinstance(data.get("profileInfo"), dict) else {}
        online = data.get("realLiveStatus") == "ON"
        nick = _wrap(live.get("nick") or profile.get("nick"), 40)
        title = _wrap(live.get("introduction") or live.get("roomName"), 80)
        game = _wrap(live.get("gameFullName"), 40)
        started = _int(live.get("startTime"), 0)
        duration = _duration_text(int(time.time()) - started) if online and started > 0 else ""
        viewers = _count(live.get("totalCount"))

        vod = _card(room["platform"], room["id"], title or nick or ("虎牙" + room["id"]),
                    live.get("screenshot") or live.get("avatar180") or profile.get("avatar180"),
                    ("人氣 " + viewers) if online and viewers else ("直播中" if online else "未開播"))
        if not vod:
            raise RuntimeError("虎牙房間資料不完整")
        vod["vod_actor"] = nick
        vod["type_name"] = game

        lines = ["狀態：" + ("直播中" + ("（已開播 %s）" % duration if duration else "") if online else "未開播")]
        if not online and started > 0:
            lines.append("上次開播：" + _clock_text(started))
        if game:
            lines.append("分區：" + game)
        if online and viewers:
            lines.append("人氣：" + viewers)
        activity = _count(live.get("activityCount"))
        if online and activity:
            lines.append("活動值：" + activity)
        level = _int(live.get("level") if live.get("level") is not None else profile.get("level"), 0)
        if level > 0:
            lines.append("主播等級：%d級" % level)
        uid = str(live.get("uid") if live.get("uid") is not None else profile.get("uid") or "").strip()
        if uid:
            lines.append("主播UID：" + uid)
        intro = _wrap(live.get("introduction"), 120)
        if intro and intro != title:
            lines.append("簡介：" + intro)
        welcome = _wrap(data.get("welcomeText"), 120)
        if welcome and welcome != title:
            lines.append("公告：" + welcome)

        vod["vod_content"] = "\n".join(lines)
        vod["vod_play_from"] = NAME
        if not vod.get("vod_play_url"):
            vod["vod_play_url"] = "觀看直播$" + vod["vod_id"]
        return vod

    # ==================== 彈幕（TARS） ====================

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
        if data.get("realLiveStatus") != "ON":
            raise RuntimeError("虎牙主播目前未開播")
        stream = data.get("stream")
        lines = stream.get("baseSteamInfoList") if isinstance(stream, dict) else None
        first = lines[0] if isinstance(lines, list) and lines else None
        if not isinstance(first, dict):
            raise RuntimeError("虎牙缺少彈幕房間資料")
        room["uid"] = first.get("lPresenterUid")
        room["top"] = first.get("lChannelId")
        room["sub"] = first.get("lSubChannelId")

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
            "attempts": 0, "ready_at": 0.0, "informed": False, "socket": None,
            "heartbeat": None, "watchdog": None, "fallback": None,
        }
        lock = threading.RLock()
        options = {"timeout": 10000, "idle": 90000, "reconnect": True}

        def stop():
            with lock:
                if ctx["stopped"]:
                    return
                ctx["stopped"] = True
                heartbeat, watchdog, fallback = ctx["heartbeat"], ctx["watchdog"], ctx["fallback"]
                socket = ctx["socket"]
                ctx["heartbeat"] = ctx["watchdog"] = ctx["fallback"] = ctx["socket"] = None
            _cancel(heartbeat)
            _cancel(watchdog)
            _cancel(fallback)
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
                _emit_safe(emit, {"text": "[虎牙] 彈幕中斷：" + message[:120],
                                  "color": 0xFF5555, "size": 20, "type": 1, "nick": "虎牙"})

        def tick():
            try:
                if ctx["stopped"]:
                    return
                idle = time.time() - ctx["activity"]
                if not ctx["ready"] and idle > 15:
                    move("等待訂閱回應逾時")
                elif ctx["ready"] and idle > 150:
                    move("長時間沒有封包")
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
            """宿主 3 秒內沒恢復時自建連線（宿主重連優先，避免雙連線搶同一房間）。"""
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
            if attempts >= 6:
                fail("虎牙彈幕連線屢次失敗：%s" % (ctx.get("reason") or ""))
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
            if not send(connection, _huya_login(room)):
                return
            if send(connection, PULSE):
                timer = _Ticker(30.0, lambda: beat(connection))
                with lock:
                    ctx["heartbeat"] = timer
            arm()

        def beat(connection):
            if ctx["stopped"]:
                return
            try:
                send(connection, PULSE)
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
            connection = self.net.connect(DANMU_URL, options,
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
                    for item in _huya_messages(event.get("content"), mark_ready):
                        if ctx["stopped"]:
                            return
                        _emit_safe(emit, item)
                    mark_ready()
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
        connect()
        return stop

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


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


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
    match = re.fullmatch(r"huya:([A-Za-z0-9_-]{1,64})", head)
    if not match:
        match = re.search(r"huya:([A-Za-z0-9_-]{1,64})", plain)
        tail = ""
    if not match:
        raise RuntimeError("直播房間編號格式錯誤")
    if tail and not re.fullmatch(r"(hls|flv|flv-full|flv-hd|flv-sd1|flv-sd2|\d{1,2})", tail):
        raise RuntimeError("直播播放線路格式錯誤")
    return {"platform": "huya", "id": match.group(1), "extra": tail}


def _headers():
    return {"User-Agent": UA, "Referer": HUYA + "/"}


def _image(value):
    if not isinstance(value, str):
        return ""
    return "https://" + value[2:] if value.startswith("//") else value


def _card(platform, ident, name, pic, remark):
    if not ident or not name:
        return None
    return {"vod_id": "%s:%s" % (platform, ident), "vod_name": str(name),
            "vod_pic": _image(pic), "vod_remarks": remark or "", "style": dict(STYLE)}


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


def _clock_text(value):
    try:
        moment = time.localtime(int(float(value)))
    except Exception:
        return ""
    return time.strftime("%m-%d %H:%M", moment)


def _wrap(value, limit=120):
    text = re.sub(r"\s*\r?\n\s*", " ", str(value if value is not None else ""))
    return text.strip()[:limit]


class _Ticker:
    """固定周期任务：每次执行完重新计时，cancel 后不再触发。"""

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


# ==================== 虎牙播放簽名 ====================

def _huya_url(stream):
    raw = dict(parse_qsl(str(stream.get("sFlvAntiCode") or ""), keep_blank_values=True))
    template = _b64(raw.get("fm") or "").decode("utf-8", "replace")
    if "$0_$1_$2_$3" not in template:
        raise RuntimeError("虎牙播放簽名格式已改變")
    query = {key: value for key, value in raw.items() if key != "fm"}
    stamp = int(time.time() * 1000)
    seqid = str(stamp)
    digest = _md5("%s|%s|%s" % (seqid, query.get("ctype") or "", query.get("t") or ""))
    secret = (template.replace("$0", "0")
              .replace("$1", str(stream.get("sStreamName") or ""))
              .replace("$2", digest)
              .replace("$3", query.get("wsTime") or ""))
    query.update({
        "wsSecret": _md5(secret), "u": "0", "seqid": seqid, "ver": "1",
        "uuid": str(stamp % 4294967295), "sdk_sid": str(stamp),
    })
    return "%s/%s.%s?%s" % (stream.get("sFlvUrl"), stream.get("sStreamName"),
                            stream.get("sFlvUrlSuffix"), _query(query))


def _b64(text):
    clean = re.sub(r"[^A-Za-z0-9+/_-]", "", str(text or "")).replace("-", "+").replace("_", "/")
    if not clean:
        return b""
    clean += "=" * (-len(clean) % 4)
    try:
        return base64.b64decode(clean)
    except Exception:
        return b""


def _query(pairs):
    return "&".join("%s=%s" % (quote(str(key), safe=""), quote(str(value), safe="")) for key, value in pairs.items())


def _md5(text):
    import hashlib
    return hashlib.md5(text.encode("utf-8")).hexdigest()


# ==================== TARS ====================

def _encode_integer(tag, value):
    number = int(value)
    if number == 0:
        return bytes([(tag << 4) | 12])
    if -128 <= number <= 127:
        size, kind = 1, 0
    elif -32768 <= number <= 32767:
        size, kind = 2, 1
    elif -2147483648 <= number <= 2147483647:
        size, kind = 4, 2
    else:
        size, kind = 8, 3
    unsigned = number & ((1 << (size * 8)) - 1)
    return bytes([(tag << 4) | kind]) + unsigned.to_bytes(size, "big")


def _huya_login(room):
    body = (
        _encode_integer(0, _int(room.get("uid"), 0)) + _encode_integer(1, 1) + b"\x26\x00\x36\x00"
        + _encode_integer(4, _int(room.get("top"), 0)) + _encode_integer(5, _int(room.get("sub"), 0))
        + _encode_integer(6, 0) + _encode_integer(7, 0)
    )
    return (_encode_integer(0, 1) + b"\x1d\x00" + _encode_integer(0, len(body)) + body)


def _tars(data):
    if not isinstance(data, (bytes, bytearray)):
        raise RuntimeError("虎牙彈幕封包格式錯誤")
    data = bytes(data)
    if len(data) > 1048576:
        raise RuntimeError("虎牙彈幕封包格式錯誤")
    state = {"offset": 0}

    def read(size):
        if size < 0 or size > len(data) - state["offset"]:
            raise RuntimeError("虎牙彈幕封包不完整")
        value = data[state["offset"]:state["offset"] + size]
        state["offset"] += size
        return value

    def field(depth):
        if depth > 20:
            raise RuntimeError("虎牙彈幕巢狀層數過多")
        head = read(1)[0]
        kind = head & 15
        tag = read(1)[0] if head >> 4 == 15 else head >> 4
        if kind <= 3:
            size = 1 << kind
            read(size)
            start = state["offset"] - size
            value = int.from_bytes(data[start:start + size], "big", signed=True)
        elif kind in (4, 5):
            size = 4 if kind == 4 else 8
            read(size)
            start = state["offset"] - size
            value = struct.unpack(">f" if kind == 4 else ">d", data[start:start + size])[0]
        elif kind in (6, 7):
            size = read(1)[0] if kind == 6 else struct.unpack(">I", read(4))[0]
            value = read(size).decode("utf-8", "replace")
        elif kind in (8, 9):
            count = field(depth + 1)[2]
            if not isinstance(count, int) or count < 0 or count > 4096:
                raise RuntimeError("虎牙彈幕集合長度錯誤")
            value = []
            for _ in range(count):
                if kind == 8:
                    value.append([field(depth + 1)[2], field(depth + 1)[2]])
                else:
                    value.append(field(depth + 1)[2])
        elif kind == 10:
            value = record(depth + 1)
        elif kind in (11, 12):
            value = 0
        elif kind == 13:
            if read(1)[0] != 0:
                raise RuntimeError("虎牙彈幕 byte 類型錯誤")
            value = read(field(depth + 1)[2])
        else:
            raise RuntimeError("虎牙彈幕包含未知類型")
        return tag, kind, value

    def record(depth):
        result = {}
        while state["offset"] < len(data):
            tag, kind, value = field(depth)
            if kind == 11:
                break
            result[tag] = value
        return result

    return record(0)


def _huya_messages(data, on_ready):
    envelope = _tars(data)
    if envelope.get(0) == 2:
        inner = envelope.get(1)
        if not isinstance(inner, (bytes, bytearray)) or _tars(inner).get(0) != 0:
            raise RuntimeError("虎牙彈幕訂閱失敗")
        on_ready()
        return []
    if envelope.get(0) != 7:
        return []
    inner = envelope.get(1)
    if not isinstance(inner, (bytes, bytearray)):
        return []
    push = _tars(inner)
    if push.get(1) != 1400:
        return []
    body = push.get(2)
    if not isinstance(body, (bytes, bytearray)):
        return []
    message = _tars(body)
    text = message.get(3)
    if not isinstance(text, str) or not text.strip():
        return []
    on_ready()
    fmt = message.get(6)
    if not isinstance(fmt, dict):
        fmt = {}
    colors = [value for value in fmt.get(6) if _is_rgb(value)][:8] \
        if isinstance(fmt.get(6), list) else []
    if colors:
        color = colors[0]
    else:
        color = fmt.get(0) if _is_rgb(fmt.get(0)) else 0xFFFFFF
    item = {"text": text, "color": color, "size": 20, "type": 1}
    if len(colors) > 1:
        item["colors"] = colors
    return [item]


def _is_rgb(value):
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 0xFFFFFF


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
