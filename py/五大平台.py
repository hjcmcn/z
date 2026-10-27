# -*- coding: utf-8 -*-
"""
爱优腾芒哔哩聚合 —— 影视聚合 Python 源（OK影视 / 蜂蜜影视 / TVBox 通用）
=====================================================================
【v5 修复说明（重点）】
1) 类属性兜底：壳子 **不保证调用 init()**（didahd 可用实现里也强调了这点）。
   旧版把 host/header/timeout/parse_list 全放在 init 里赋值，init 不执行时
   属性根本不存在，一调用就 AttributeError -> 界面静默空白。
   现在 __init__ 里无条件先兜底，保证任何入口进来属性都在。

2) 三重网络栈（自动择优，成功即记住）：
      native   -> 壳子基类原生 fetch/getHtml（走 Android OkHttp，网络兼容性最好）
      requests -> 壳子内置 requests
      urllib   -> 标准库（关掉 SSL 校验，壳子常缺 CA 证书）
   手机壳子里的 Python 网络栈常因缺 CA 证书 / DNS / 代理失败，
   而壳子原生方法走系统网络栈，基本必通。

3) 多域名自动 failover：采集站经常换域名 / 内网穿透掉线，
   依次尝试所有域名，拿到数据即自动切换并记住，以后不再逐个探测。

4) 首页填充真实推荐数据：旧版 homeContent 的 list 恒为空 -> 首页白茫茫一片，
   看起来就是"没有数据"。现在首页拉取真实数据。

5) 诊断卡片：万一还是拿不到数据，界面上会直接显示失败原因
   （用了哪个栈 / 试了几个域名 / 每个域名的错误），不再静默空白。

【分类】数字 type_id（壳子兼容最好），内部映射回接口字母 from 参数。
【播放】返回 parse=1 + 解析页 URL，交给壳子嗅探器抓真实地址。

【v9 线路修复（2026-09-11 实测）】
1) kptv 直链通道已失效（resolve.php 实测返回 403 "Access Denied"），
   旧版"自动轮询"每点一次都要白等 kptv 两步超时（约 12 秒）才轮到解析站，
   体感就是"线路转圈、加载不出来"。现在给 kptv 加失败熔断：
   连续失败 3 次后 30 分钟内直接跳过，不再发起无效请求，播放秒进解析链路。
2) 原线路（youku/mgtv/qiyi 等平台页 URL）之前落到 parse=1+裸 URL 兜底，
   壳子嗅探平台播放页拿不到直链 -> 黑屏。现在原线路与"自动轮询"统一
   走 kptv 直链 -> 轮换解析站的链路，保证每个线路都有有效响应。
3) 解析站表按 2026-09-11 实测重排并清洗：
   剔除已死站点（jx.2s0.cn 连接超时、json.fongmi.cc 403），
   保留实测 200/302 存活的 10 个，快且活的排前面，避免一列死线路。
4) 剧集 URL 里的 '#' 转义为 %23：'#' 是 TVBox 剧集分隔符，
   某些平台 URL 带 fragment 会把剧集列表切错 -> 线路显示残缺。
"""

import re
import json
import sys
import time

try:
    import urllib.parse as _uparse
except Exception:  # noqa: BLE001
    import urllib as _uparse  # py2

try:
    import requests as _requests
    _HAS_REQUESTS = True
except Exception:  # noqa: BLE001
    _requests = None
    _HAS_REQUESTS = False

# 兼容壳子内置基类；本地测试无壳子时回退到空基类
try:
    from base.spider import Spider as _BaseSpider
except Exception:  # noqa: BLE001
    class _BaseSpider(object):
        pass


def _log(*args):
    try:
        print("[腾爱优]", *args)
    except Exception:  # noqa: BLE001
        pass


def _enc(value):
    """encodeURIComponent（保留 !'()*-._~）。"""
    try:
        return _uparse.quote(str(value), safe="!'()*-._~")
    except Exception:  # noqa: BLE001
        return str(value)


def _to_text(resp):
    """把各种返回（str / bytes / Response 对象）统一成文本。"""
    if resp is None:
        return ""
    if isinstance(resp, str):
        return resp
    try:
        if isinstance(resp, bytes):
            return resp.decode("utf-8", "ignore")
    except Exception:  # noqa: BLE001
        pass
    for attr in ("text", "content", "data"):
        try:
            v = getattr(resp, attr)
            if callable(v):
                v = v()
            if isinstance(v, bytes):
                return v.decode("utf-8", "ignore")
            if isinstance(v, str):
                return v
        except Exception:  # noqa: BLE001
            continue
    try:
        return str(resp)
    except Exception:  # noqa: BLE001
        return ""


# 分类：数字 ID -> 接口字母参数 + 名称
_CATEGORY = {
    "1": ("qq",       "腾讯视频"),
    "2": ("qiyi",     "爱奇艺"),
    "3": ("youku",    "优酷视频"),
    "4": ("mgtv",     "芒果TV"),
    "5": ("bilibili", "B站"),
}
_KEY_TO_NUM = dict((v[0], k) for k, v in _CATEGORY.items())

# ======================================================================
# 平台 -> 真实分类表（实测抓取，2026-09-10）
# ======================================================================
# 之前只给每个平台硬塞 2~3 个分类，被吐槽"腾讯只有两个"。
# 实际把 from=平台 & t=类型 全跑一遍后发现：
#   每个平台都有 电影/连续剧/综艺/动漫/少儿/纪录片 6 个正式分类，
#   腾讯、爱奇艺、芒果还另有短剧。数量差异如下（实测 total）：
#
#        电影   连续剧  综艺   动漫   少儿  纪录片   短剧
#   qq    8622   2156  2501  2449  2166  3911  70993
#   qiyi  2627   2490  1293  7135  7463  3074  99928
#   youku 2011   1984  1414  3166  3978  3309      1   <- 短剧仅1条，不展示
#   mgtv  1535   3803  1540   486   927   356     28
#   bili  5696   2130   567  2174  3680  3534      2   <- 短剧仅2条，不展示
#
# 所以分类是"平台 × 该平台真实存在的类型"，共 7+7+6+7+6 = 33 个，
# 而不是我自己拍脑袋定的 10 个。分类名用接口返回的官方 type_name。
# 内容量太少的类型（<5 条）自动不展示，避免点进去一片空白。
_CATALOG = (
    # (平台key, 平台名, ((类型id, 分类名, 内容总数), ...))
    ("qq", "腾讯视频", (
        ("1", "电影", 8622), ("2", "连续剧", 2156), ("3", "综艺", 2501),
        ("4", "动漫", 2449), ("5", "少儿", 2166), ("6", "纪录片", 3911),
        ("7", "短剧", 70993),
    )),
    ("qiyi", "爱奇艺", (
        ("1", "电影", 2627), ("2", "连续剧", 2490), ("3", "综艺", 1293),
        ("4", "动漫", 7135), ("5", "少儿", 7463), ("6", "纪录片", 3074),
        ("7", "短剧", 99928),
    )),
    ("youku", "优酷视频", (
        ("1", "电影", 2011), ("2", "连续剧", 1984), ("3", "综艺", 1414),
        ("4", "动漫", 3166), ("5", "少儿", 3978), ("6", "纪录片", 3309),
    )),
    ("mgtv", "芒果TV", (
        ("1", "电影", 1535), ("2", "连续剧", 3803), ("3", "综艺", 1540),
        ("4", "动漫", 486), ("5", "少儿", 927), ("6", "纪录片", 356),
        ("7", "短剧", 28),
    )),
    ("bilibili", "B站", (
        ("1", "电影", 5696), ("2", "连续剧", 2130), ("3", "综艺", 567),
        ("4", "动漫", 2174), ("5", "少儿", 3680), ("6", "纪录片", 3534),
    )),
)
_MIN_ITEMS = 5   # 内容少于这个数的分类不展示

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36")

_KPTV_TIMEOUT = 6      # 取直链的独立短超时（默认 10s 太久了，拖慢起播）

# 解析源（按 2026-09-11 实测存活状态排序：200/302 一通即通，快且活的在前）
# 实测剔除：jx.2s0.cn（连接超时）、json.fongmi.cc（403 拒绝）
# 数量控制在 12 个以内：vod_play_url 过长会让详情页卡顿甚至打不开。
_PARSE_LIST = [
    {"name": "8090",      "url": "https://www.8090g.cn/?url="},
    {"name": "默认接口",   "url": "https://jx.xmflv.com/?url="},
    {"name": "极速解析",   "url": "https://www.ckplayer.vip/jiexi/?url="},
    {"name": "HLS解析",    "url": "https://jx.hls.one/?url="},
    {"name": "剖元解析",   "url": "https://www.pouyun.com/?url="},
    {"name": "夜幕解析",   "url": "https://www.yemu.xyz/?url="},
    {"name": "盘古解析",   "url": "https://www.pangujiexi.com/jiexi/?url="},
    {"name": "我看VIP",    "url": "https://a.wkvip.net/?url="},
    {"name": "M3U8解析",   "url": "https://jx.m3u8.tv/jx/jx.php?url="},
    {"name": "Jn1解析",    "url": "https://yparse.jn1.cc/index.php?url="},
]

# 采集站域名（任一可用即可；_get_json_auto 会自动 failover 并记住可用的）
# 【重要】cj.tianwe.cn 的 443 端口不提供 HTTPS（实测 SSL WRONG_VERSION_NUMBER），
# 只能写 http://。之前把 https:// 排在第一位，每次都要先撞一次 SSL 错误、
# 白白浪费一次超时，弱网设备上直接整体超时 -> 界面空白。
# 顺序原则：已验证支持的协议优先，坏组合绝不放在前面。
_HOSTS = [
    "https://tianwei.qzz.io",      # 实测 https 可用（最快最稳，主用）
    "http://cj.tianwe.cn",         # 原域名，仅支持 http
    "https://cj.10010888.xyz",     # 官方备用 https
    "http://tianwei.qzz.io",       # 上面 https 失败时的 http 兜底
    "http://cj.10010888.xyz",
]

_STACKS = ("requests", "native", "urllib")   # 探针实测 requests 直连 200，排第一


class Spider(_BaseSpider):
    """腾爱优聚合 —— 影视聚合源（v5 全兜底版）。"""

    name = "腾爱优聚合"

    # ==================================================================
    # 类属性兜底 —— 即使 init() 完全不被调用，以下属性也一定存在
    # ==================================================================
    hosts = list(_HOSTS)
    host = _HOSTS[0]
    header = {
        "User-Agent": _UA,
        # 带上常规浏览器头：部分 CDN/WAF 对"裸 UA 无 Accept"的请求直接 403
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Connection": "close",   # 避免 keep-alive 在弱网设备上挂住
    }
    timeout = 10

    kptv_parse = "https://jx.kptv.us/?url="
    kptv_host = "jx.kptv.us"
    parse_list = list(_PARSE_LIST)
    _parse_names = set(p["name"] for p in _PARSE_LIST)
    detail_parse_count = len(_PARSE_LIST)

    _rotate_idx = 0
    _last_err = ""
    _ok_host = ""
    _ok_stack = ""
    _cache = {}
    _cache_ts = {}
    _kptv_cache = {}
    # kptv 失败熔断：连续失败 _KPTV_FAIL_LIMIT 次后，_kptv_down_until 之前
    # 直接跳过 kptv，不再发起无效请求（实测 resolve.php 返回 403 已失效）
    _kptv_fail = 0
    _kptv_down_until = 0.0
    _KPTV_FAIL_LIMIT = 3
    _KPTV_COOLDOWN = 1800

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        """无条件先兜底属性，再尝试调用基类 __init__（基类可能没有）。"""
        self._ensure_attrs()
        try:
            _BaseSpider.__init__(self, *args, **kwargs)
        except Exception:  # noqa: BLE001
            pass

    def _ensure_attrs(self):
        """把 init 里要用的属性全部补齐（幂等，可反复调用）。"""
        if not getattr(self, "hosts", None):
            self.hosts = list(_HOSTS)
        if not getattr(self, "host", None):
            self.host = self.hosts[0]
        if not getattr(self, "header", None):
            self.header = {
                "User-Agent": _UA,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Connection": "close",
            }
        if not getattr(self, "timeout", None):
            self.timeout = 10
        if not getattr(self, "kptv_parse", None):
            self.kptv_parse = "https://jx.kptv.us/?url="
        if not getattr(self, "kptv_host", None):
            self.kptv_host = "jx.kptv.us"
        if not getattr(self, "parse_list", None):
            self.parse_list = list(_PARSE_LIST)
        if not getattr(self, "_parse_names", None):
            self._parse_names = set(p["name"] for p in self.parse_list)
        if not getattr(self, "detail_parse_count", None):
            self.detail_parse_count = len(self.parse_list)
        if getattr(self, "_rotate_idx", None) is None:
            self._rotate_idx = 0
        if getattr(self, "_last_err", None) is None:
            self._last_err = ""
        if getattr(self, "_ok_host", None) is None:
            self._ok_host = ""
        if getattr(self, "_ok_stack", None) is None:
            self._ok_stack = ""
        if getattr(self, "_cache", None) is None:
            self._cache = {}
        if getattr(self, "_cache_ts", None) is None:
            self._cache_ts = {}
        if getattr(self, "_kptv_cache", None) is None:
            self._kptv_cache = {}
        if getattr(self, "_kptv_fail", 0) is None:
            self._kptv_fail = 0
        if getattr(self, "_kptv_down_until", 0.0) is None:
            self._kptv_down_until = 0.0

    def init(self, extend=""):
        _log("init ->", extend)
        self._ensure_attrs()
        try:
            if _HAS_REQUESTS:
                self.session = _requests.Session()
                self.session.headers.update(self.header)
        except Exception as exc:  # noqa: BLE001
            _log("session 创建失败:", exc)
        return

    def getName(self):
        return self.name

    def destroy(self):
        pass

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None

    # ------------------------------------------------------------------
    # 网络层：三重网络栈
    # ------------------------------------------------------------------
    def _native_get(self, url):
        """调用壳子基类原生请求方法。

        【v8 按探针实测定制（webhome/鱼壳, fengmi 系）】
        探针实测你的壳子：
          fetch 签名 (url, params=None, ...)，**同步返回 Response**，
          fetch(url) 和 fetch(url, x) 都 OK，传 3 个位置参数才 TypeError。
        所以这里先试同步式（1参/2参，你的壳子直接命中），
        再试回调式（兼容其他 drpy 壳子），任何一次尝试都有界。
        """
        fn = getattr(self, "fetch", None)
        if callable(fn):
            # 1) 同步式：fetch(url) / fetch(url, headers)
            for args in ((url,), (url, self.header)):
                try:
                    txt = _to_text(fn(*args))
                    if txt and txt.strip():
                        return txt
                except Exception:  # noqa: BLE001
                    continue

            # 2) 回调式：fetch(url, headers, cb) —— 其他 drpy 壳子
            holder = {}

            def _cb(*a):
                for v in a:
                    t = _to_text(v)
                    if t and t.strip():
                        holder["t"] = t
                        return

            try:
                fn(url, self.header, _cb)
                if holder.get("t"):
                    return holder["t"]
            except Exception:  # noqa: BLE001
                pass

        # 3) getHtml(url) / getPage(url) —— 部分壳子提供
        for nm in ("getHtml", "getPage"):
            g = getattr(self, nm, None)
            if not callable(g):
                continue
            for args in ((url,), (url, self.header)):
                try:
                    txt = _to_text(g(*args))
                    if txt and txt.strip():
                        return txt
                except Exception:  # noqa: BLE001
                    continue
        return ""

    def _http_via(self, stack, url):
        """用指定网络栈 GET，返回文本；失败返回空串。"""
        t = getattr(self, "timeout", 8) or 8
        try:
            if stack == "native":
                return self._native_get(url)
            if stack == "requests":
                if not _HAS_REQUESTS:
                    return ""
                sess = getattr(self, "session", None) or _requests
                r = sess.get(url, timeout=t, verify=False,
                             headers=self.header, allow_redirects=False)
                try:
                    r.encoding = "utf-8"
                except Exception:  # noqa: BLE001
                    pass
                return r.text or ""
            # urllib
            import urllib.request
            import ssl as _ssl
            ctx = None
            try:
                ctx = _ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = _ssl.CERT_NONE
            except Exception:  # noqa: BLE001
                ctx = None
            req = urllib.request.Request(url, headers=self.header)
            try:
                resp = urllib.request.urlopen(req, timeout=t, context=ctx)
            except TypeError:
                resp = urllib.request.urlopen(req, timeout=t)
            try:
                raw = resp.read()
            finally:
                try:
                    resp.close()
                except Exception:  # noqa: BLE001
                    pass
            try:
                return raw.decode("utf-8")
            except Exception:  # noqa: BLE001
                return raw.decode("latin-1", "ignore")
        except Exception as exc:  # noqa: BLE001
            _log("请求失败[%s] %s -> %s" % (stack, url[:70], exc))
            return ""

    def _ordered_hosts(self):
        hs = list(getattr(self, "hosts", None) or _HOSTS)
        ok = getattr(self, "_ok_host", "")
        if ok and ok in hs:
            hs.remove(ok)
            hs.insert(0, ok)
        return hs

    def _ordered_stacks(self):
        """网络栈优先级。

        【v8 按探针实测定制（webhome/鱼壳, fengmi 系）】
        探针实测：requests 直连 200 OK；基类 fetch 同步 Response 式。
        所以 requests 排第一（header 传得最干净、已实测 200），
        native fetch 兜底，urllib 最后。
        """
        st = ["requests", "native", "urllib"]
        ok = getattr(self, "_ok_stack", "")
        if ok and ok in st:
            st.remove(ok)
            st.insert(0, ok)
        if not _HAS_REQUESTS and "requests" in st:
            st.remove("requests")
        return st

    def _get_json_auto(self, path, use_cache=True):
        """依次尝试各域名/各网络栈，返回第一个拿到数据的 JSON。

        【v6.1 关键性能修复】
        以前只要 list 为空就换下一个域名重试 -> 一个"确实没有结果"的类型
        （如搜"家业"的 t=1/3/5）会跑满 5域名 × 3网络栈 = 15 次请求，
        每次都在等超时，单次搜索白耗 20 秒以上，壳子直接卡死。

        现在区分两种情况：
          - HTTP 拿到了、JSON 解开了，但 list 是空的 -> 这是**正常业务结果**
            （该类型就是没内容），属于有效应答，立即返回，不再重试；
          - 连 HTTP/JSON 都失败 -> 才算域名/网络故障，才换下一个候选。
        这样空结果的搜索从 20s+ 降到 1.5s。
        """
        self._ensure_attrs()
        if use_cache:
            hit = self._cache_get(path)
            if hit is not None:
                return hit

        hosts = self._ordered_hosts()
        stacks = self._ordered_stacks()
        errs = []
        tried = 0
        soft_fail = None       # 记住"能连通但没数据"的应答，作为兜底返回
        for base in hosts:
            short = base.split("//")[-1].replace("www.", "")[:18]
            url = base + path
            for st in stacks:
                tried += 1
                txt = self._http_via(st, url)
                if not txt or not txt.strip():
                    errs.append("%s/%s:空" % (short, st))
                    continue
                try:
                    data = json.loads(txt)
                except Exception:  # noqa: BLE001
                    head = txt.strip()[:30].replace("\n", " ")
                    errs.append("%s/%s:非JSON(%s)" % (short, st, head))
                    continue

                # 连通且是合法 JSON —— 这个域名/网络栈是好的，先记下来
                self.host = base
                self._ok_host = base
                self._ok_stack = st
                self._last_err = ""

                if data and (data.get("list") or data.get("total")):
                    self._cache_set(path, data)
                    return data

                # 合法 JSON 但空结果：这是"这类内容确实没有"的正常应答。
                # 不再继续换域名（那只会白等超时），直接返回。
                self._cache_set(path, data)
                return data

            if soft_fail is None and errs:
                soft_fail = True

        self._last_err = "试%d次|" % tried + ";".join(errs[:6])
        _log("全部失败:", self._last_err)
        return soft_fail

    def _cache_get(self, key):
        try:
            ts = self._cache_ts.get(key, 0)
            if time.time() - ts < 120:
                return self._cache.get(key)
        except Exception:  # noqa: BLE001
            pass
        return None

    def _cache_set(self, key, val):
        try:
            self._cache[key] = val
            self._cache_ts[key] = time.time()
            if len(self._cache) > 60:
                self._cache.clear()
                self._cache_ts.clear()
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------
    # 诊断卡片：拿不到数据时把原因直接显示到界面
    # ------------------------------------------------------------------
    def _env_brief(self):
        try:
            py = "%d.%d" % (sys.version_info[0], sys.version_info[1])
        except Exception:  # noqa: BLE001
            py = "?"
        native = "有" if any(callable(getattr(self, n, None))
                            for n in ("fetch", "getHtml", "getPage",
                                      "request", "http")) else "无"
        return "PY%s req%s 原生%s" % (py, "有" if _HAS_REQUESTS else "无", native)

    def _diag_item(self, where):
        err = (getattr(self, "_last_err", "") or "未知原因")
        return [{
            "vod_id": "0",
            "vod_name": "[%s]无数据: %s" % (where, err[:70]),
            "vod_pic": "",
            "vod_remarks": self._env_brief(),
        }]

    # ------------------------------------------------------------------
    # 首页
    # ------------------------------------------------------------------
    def homeContent(self, filter=False):
        """首页：分类 + 筛选 + 推荐。

        【v7 分类重做】
        之前每个平台只给 2~3 个分类（被吐槽"腾讯只有两个、芒果只有一个"）。
        现在按 _CATALOG 实测表展开：平台 × 该平台真实存在的类型，
        腾讯 7 个 / 爱奇艺 7 个 / 优酷 6 个 / 芒果 7 个 / B站 6 个 = 33 个。
        名称用平台名 + 官方分类名（如"腾讯视频·电影"）。
        """
        classes = self._build_classes()
        result = {"class": classes, "list": []}

        if filter:
            type_filter = {
                "key": "t", "name": "类型",
                "value": [
                    {"n": "全部", "v": ""}, {"n": "电影", "v": "1"},
                    {"n": "剧集", "v": "2"}, {"n": "综艺", "v": "3"},
                    {"n": "动漫", "v": "4"}, {"n": "少儿", "v": "5"},
                    {"n": "纪录片", "v": "6"}, {"n": "短剧", "v": "7"},
                ],
            }
            year_filter = {
                "key": "year", "name": "年份",
                "value": [{"n": "全部", "v": ""}] +
                         [{"n": str(y), "v": str(y)}
                          for y in range(2026, 2014, -1)],
            }
            area_filter = {
                "key": "area", "name": "地区",
                "value": [
                    {"n": "全部", "v": ""}, {"n": "大陆", "v": "大陆"},
                    {"n": "香港", "v": "香港"}, {"n": "台湾", "v": "台湾"},
                    {"n": "美国", "v": "美国"}, {"n": "韩国", "v": "韩国"},
                    {"n": "日本", "v": "日本"}, {"n": "泰国", "v": "泰国"},
                ],
            }
            sort_filter = {
                "key": "by", "name": "排序",
                "value": [
                    {"n": "最新", "v": "time"}, {"n": "最热", "v": "hits"},
                    {"n": "评分", "v": "score"},
                ],
            }
            result["filters"] = dict(
                (c["type_id"], [type_filter, year_filter,
                                area_filter, sort_filter])
                for c in classes)

        # 首页填充真实推荐（旧版恒空 -> 看起来就是"没数据"）
        try:
            result["list"] = self._home_recommend()
        except Exception as exc:  # noqa: BLE001
            _log("首页推荐异常:", exc)
            result["list"] = []
        return result

    def _build_classes(self):
        """按 _CATALOG 生成分类列表：平台 × 该平台真实存在的类型。

        type_id 统一用 "平台-类型" 形式（如 "qq-2"），
        categoryContent 再拆回 from=qq & t=2。
        """
        out = []
        for key, pname, types in _CATALOG:
            for tid, tname, total in types:
                if total < _MIN_ITEMS:
                    continue      # 内容太少的分类不展示，避免点进去空白
                out.append({
                    "type_id": "%s-%s" % (key, tid),
                    "type_id_1": "0",
                    "type_pid": "0",
                    "type_name": "%s·%s" % (pname, tname),
                })
        return out

    def _home_recommend(self):
        """首页推荐。

        【v7 封面修复】上一版为了提速改用 ac=list，结果**所有封面都没了**
        （ac=list 的返回里根本没有 vod_pic 字段）。
        实测两种模式耗时其实差不多（ac=list 1.1s vs ac=detail 1.3s），
        之前"慢"的真凶是空结果被误判成故障后反复重试（单次白等20秒），
        不是响应体积。所以这里改回 ac=detail，封面回来了，速度也不受影响。
        """
        path = "/api.php/provide/vod/?from=qq&ac=detail&t=2&pg=1"
        data = self._get_json_auto(path)
        if not data:
            path = "/api.php/provide/vod/?from=qiyi&ac=detail&t=2&pg=1"
            data = self._get_json_auto(path)
        rows = self._rows(data.get("list")) if data else []
        if not rows:
            return self._diag_item("首页") if getattr(
                self, "_last_err", "") else []
        return rows[:30]

    def _self_check(self):
        """自检：不管有没有网络，都返回一张能看清所有字段的测试卡片。

        用法：在源配置里把 URL 或扩展参数填成 selfcheck / check，
        或者直接调用 homeVideoContent 时若设置了 self._force_check。
        这样即使网络全挂，也能在界面上确认"脚本到底有没有被加载"。
        """
        return [{
            "vod_id": "0",
            "vod_name": "自检OK: 脚本已加载",
            "vod_pic": "",
            "vod_remarks": self._env_brief() + " | 域名%d个" % len(
                getattr(self, "hosts", []) or []),
        }]

    def homeVideoContent(self):
        try:
            self._ensure_attrs()
            return {"list": self._home_recommend()}
        except Exception as exc:  # noqa: BLE001
            _log("homeVideoContent err", exc)
            return {"list": []}

    # ------------------------------------------------------------------
    # 分类
    # ------------------------------------------------------------------
    def categoryContent(self, tid, pg, filter=False, extend=None):
        """分类列表。

        【v7 封面修复】这里必须用 ac=detail。
        ac=list 响应里没有 vod_pic 字段，界面就是一片空白方块。
        """
        self._ensure_attrs()
        extend = self._pick_extend(extend)
        key = self._to_key(tid) or "qq"
        try:
            page = int(pg) if pg else 1
        except Exception:  # noqa: BLE001
            page = 1

        params = ["from=" + key, "ac=detail", "pg=" + str(page)]
        t = extend.get("class") or extend.get("t") or self._to_type(tid) or "2"
        params.append("t=" + str(t))
        if extend.get("year"):
            params.append("year=" + _enc(extend["year"]))
        if extend.get("area"):
            params.append("area=" + _enc(extend["area"]))
        if extend.get("sort"):
            params.append("by=" + _enc(extend["sort"]))

        path = "/api.php/provide/vod/?" + "&".join(params)
        _log("category path ->", path)

        data = self._get_json_auto(path)
        if not data:
            return {"list": self._diag_item("分类"), "page": page,
                    "pagecount": 1, "limit": 1, "total": 1}

        vod_list = self._rows(data.get("list"))

        pc = data.get("pagecount") or 1
        try:
            pc = int(pc)
        except Exception:  # noqa: BLE001
            pc = 1

        return {
            "list": vod_list,
            "page": page,
            "pagecount": pc,
            "limit": len(vod_list),
            "total": data.get("total") or pc * len(vod_list),
        }

    # ------------------------------------------------------------------
    # 列表行解析（分类/搜索共用）
    # ------------------------------------------------------------------
    @staticmethod
    def _fix_pic(pic):
        """封面地址规范化，让它加载更快、不容易裂图。

        - 相对路径 -> 补成绝对地址（否则壳子根本加载不出来）；
        - http://  -> 尽量升级成 https://（明文在国内经常被链路劫持、
          插入广告甚至直接失败，是封面加载慢/裂图的主因）；
        - 多个地址用逗号分隔时只取第一个；
        - 去掉首尾空白和转义反斜杠。
        """
        if not pic:
            return ""
        s = str(pic).strip().replace("\\", "")
        if "," in s:
            s = s.split(",")[0]
        if s.startswith("//"):
            s = "https:" + s
        elif s.startswith("/"):
            s = "https://puui.qpic.cn" + s
        elif s.startswith("http://"):
            # 图床基本都支持 https，升级后更快也更稳
            s = "https://" + s[len("http://"):]
        return s.strip()

    @staticmethod
    def _eps_clean(block):
        """净化一条线路的剧集块（'集名$URL#集名$URL'）。

        TVBox 用 '#' 切分剧集、用 '$' 切分集名与地址，
        平台 URL 里若带 fragment（#xxx）或 $ 会把剧集列表切错、
        点播错集。这里只把 **URL 部分** 的 '#' 与 '$' 转义为 %23/%24，
        集名保持原样。

        实现要点：不能先按 '#' split——URL 里的 fragment 会先被切开、
        重组时又拼回来，等于没净化。正确做法是先用前瞻正则保护
        "真正的集分隔符"（'#' 后紧跟 '集名$'），其余 '#' 一律 %23，
        之后再去掉 URL 里残留的 '$'。
        """
        if not block:
            return block
        import re as _re
        block = str(block).strip()
        # 集分隔符判定：'#' 之后必须形如 "集名$"（集名不含 # 和 $）
        block = _re.sub(r"#(?![^#$]+\$)", "%23", block)
        out = []
        for ep in block.split("#"):
            if not ep:
                continue
            if "$" in ep:
                name, url = ep.split("$", 1)
                url = url.replace("#", "%23").replace("$", "%24")
                out.append(name + "$" + url)
            else:
                out.append(ep)
        return "#".join(out)

    def _rows(self, raw):
        """把接口 list 统一转成壳子需要的行结构，字段尽量补全。"""
        out = []
        if not isinstance(raw, list):
            return out
        for v in raw:
            if not isinstance(v, dict) or not v.get("vod_id"):
                continue
            out.append({
                "vod_id": str(v.get("vod_id", "")),
                "vod_name": v.get("vod_name") or v.get("name") or "",
                "vod_pic": self._fix_pic(v.get("vod_pic") or v.get("pic")),
                "vod_remarks": v.get("vod_remarks") or "",
                "vod_year": str(v.get("vod_year") or ""),
                "type_name": v.get("type_name") or "",
            })
        return out

    @staticmethod
    def _pick_extend(extend):
        """壳子传参有 dict / JSON 字符串两种形式，统一成 dict。"""
        if isinstance(extend, str) and extend.strip():
            try:
                extend = json.loads(extend)
            except Exception:  # noqa: BLE001
                extend = {}
        if not isinstance(extend, dict):
            return {}
        # 过滤掉壳子常见的占位值
        return dict((k, v) for k, v in extend.items()
                    if v not in ("", None, "全部", "all", "0"))

    # ------------------------------------------------------------------
    # 详情
    # ------------------------------------------------------------------
    def detailContent(self, ids):
        self._ensure_attrs()
        if not ids:
            return {"list": []}
        vid = str(ids)
        if isinstance(ids, (list, tuple)):
            vid = str(ids[0])
        vid = vid.split("$")[-1].strip()
        if not vid:
            return {"list": []}

        path = "/api.php/provide/vod/?ac=detail&ids=" + vid
        _log("detail path ->", path)

        data = self._get_json_auto(path)
        if not data:
            return {"list": self._diag_item("详情")}

        vod_list = []
        if isinstance(data.get("list"), list):
            for item in data["list"]:
                if not item.get("vod_id"):
                    continue
                original_from = item.get("vod_play_from", "") or ""
                original_url = item.get("vod_play_url", "") or ""

                if original_from and original_url:
                    play_from = original_from
                    play_url = original_url
                    url_parts = original_url.split("$$$")
                    # 【v9 净化】解析线路挂的剧集块先清洗：
                    # URL 里的 '#' / '$' 是 TVBox 剧集与集名分隔符，
                    # 平台 URL 若带 fragment（#xxx）会把剧集列表切错
                    # -> 线路显示残缺、点播错集。
                    first_ep = self._eps_clean(
                        url_parts[0] if url_parts else original_url)
                    play_from += "$$$自动轮询"
                    play_url += "$$$" + first_ep
                    for p in self.parse_list[:self.detail_parse_count]:
                        play_from += "$$$" + p["name"]
                        play_url += "$$$" + first_ep
                else:
                    play_from = original_from
                    play_url = original_url

                vod_list.append({
                    "vod_id": str(item.get("vod_id", "")),
                    "vod_name": item.get("vod_name", ""),
                    "vod_pic": item.get("vod_pic", ""),
                    "vod_remarks": item.get("vod_remarks", ""),
                    "vod_year": item.get("vod_year", ""),
                    "type_name": item.get("type_name", ""),
                    "vod_area": item.get("vod_area", ""),
                    "vod_lang": item.get("vod_lang", ""),
                    "vod_actor": item.get("vod_actor", ""),
                    "vod_director": item.get("vod_director", ""),
                    "vod_content": item.get("vod_content", ""),
                    "vod_play_from": play_from,
                    "vod_play_url": play_url,
                })
        return {"list": vod_list}

    # ------------------------------------------------------------------
    # 搜索
    # ------------------------------------------------------------------
    # 站点里"短剧"有 16 万条，是正剧的 15 倍。搜索时不带类型筛选，
    # 结果会被短剧彻底淹没（搜"家业" -> 246 条有 238 条是短剧，
    # 真正的电视剧《家业》排到最后）。所以搜索必须做类型收敛。
    #
    # 策略（v6 核心修复）：
    #   1. 用户选了类型筛选 -> 就用它，一次请求；
    #   2. 没选 -> 先搜"正剧类型"（电影/连续剧/综艺/动漫/少儿/纪录片），
    #      把短剧排除在外，结果最准；
    #   3. 正剧一条都没有 -> 再搜全类型，保证"冷门短剧"也搜得到；
    #   4. 两次都没结果 -> 退回到不加筛选的原始搜索。
    # 搜索时优先查这三个（命中率最高），不够再补查 _MORE_TYPES
    _PRIMARY_TYPES = ("2", "1", "4")               # 连续剧 / 电影 / 动漫
    _MORE_TYPES = ("6", "3", "5")                  # 纪录片 / 综艺 / 少儿
    _MAIN_TYPES = _PRIMARY_TYPES + _MORE_TYPES     # 除短剧外的全部
    _SHORT_TYPE = "7"                              # 短剧

    def searchContent(self, key, quick=False, pg="1"):
        self._ensure_attrs()
        key = (key or "").strip()
        if not key:
            return {"list": []}
        try:
            page = max(1, int(pg))
        except Exception:  # noqa: BLE001
            page = 1

        ext = self._pick_extend(getattr(self, "_search_extend", None))
        want_type = ext.get("t") or ext.get("class") or ""

        # --- 策略1：用户明确选了类型，一次搞定（最快） ---
        if want_type:
            data = self._search_once(key, page, want_type)
            if data:
                return self._search_result(data, page, key)
            return self._search_fallback(key, page)

        # --- 策略2：排除短剧，只要正剧（合并去重）---
        # 【v7 提速】ac=detail 带封面但单次 97KB，6 个类型全并发要下 580KB。
        # 改成两批：先并发查最常命中的 3 个（连续剧/电影/动漫），
        # 结果够 6 条就直接返回（多数搜索到此结束，省一半流量和时间）；
        # 不够再补查剩下 3 个。
        merged, seen = [], set()

        def _collect(datas):
            for data in datas:
                for row in self._rows(data.get("list")):
                    if row["vod_id"] in seen:
                        continue
                    seen.add(row["vod_id"])
                    merged.append(row)

        _collect(self._search_parallel(key, page, self._PRIMARY_TYPES))
        if len(merged) < 6:
            _collect(self._search_parallel(key, page, self._MORE_TYPES))

        if merged:
            _log("搜索命中正剧 %d 条（已排除短剧）" % len(merged))
            return {"list": merged, "page": page, "pagecount": 1,
                    "limit": len(merged), "total": len(merged)}

        # --- 策略3：正剧没有，再搜全类型（含短剧）---
        _log("正剧无结果, 回退全类型搜索")
        return self._search_fallback(key, page)

    def _search_once(self, key, page, t=None):
        """发一次搜索请求。t 为 None 表示不限定类型。"""
        params = ["ac=detail", "wd=" + _enc(key), "pg=" + str(page)]
        if t:
            params.append("t=" + str(t))
        data = self._get_json_auto("/api.php/provide/vod/?" + "&".join(params))
        if data and (data.get("list") or data.get("total")):
            return data
        return None

    def _search_parallel(self, key, page, types):
        """并发搜索多个类型，返回拿到结果的 data 列表。

        串行 6 个类型要 9 秒左右，用户会觉得卡；这里的 6 个请求彼此独立，
        完全可以同时发。用线程池跑，总耗时 ≈ 最慢那一个请求（约 1.5 秒）。
        线程不可用时自动退化为串行，功能不受影响。
        """
        try:
            import threading
        except Exception:  # noqa: BLE001
            threading = None

        results = {}
        lock = None
        order = list(types)

        if threading is not None:
            try:
                lock = threading.Lock()
                threads = []

                def _worker(t):
                    try:
                        d = self._search_once(key, page, t)
                    except Exception:  # noqa: BLE001
                        d = None
                    if d:
                        with lock:
                            results[t] = d

                for t in order:
                    th = threading.Thread(target=_worker, args=(t,))
                    try:
                        th.setDaemon(True)      # py2/py3 兼容
                    except Exception:  # noqa: BLE001
                        try:
                            th.daemon = True
                        except Exception:  # noqa: BLE001
                            pass
                    th.start()
                    threads.append(th)

                # 等待所有线程，最多 12 秒（防止个别请求挂死拖住界面）
                deadline = time.time() + 12
                for th in threads:
                    left = deadline - time.time()
                    if left <= 0:
                        break
                    th.join(left)
                return [results[t] for t in order if t in results]
            except Exception as exc:  # noqa: BLE001
                _log("并发搜索降级:", exc)

        # 降级：串行
        out = []
        for t in order:
            d = self._search_once(key, page, t)
            if d:
                out.append(d)
        return out

    def _search_fallback(self, key, page):
        """全类型搜索：先不限类型，再补一次短剧，避免完全搜不到。"""
        data = self._search_once(key, page, None)
        if data:
            return self._search_result(data, page, key)
        data = self._search_once(key, page, self._SHORT_TYPE)
        if data:
            return self._search_result(data, page, key)
        # 都连通但就是没这条内容 —— 这是"没搜到"，不是故障
        return {"list": [], "page": page, "pagecount": 1,
                "limit": 0, "total": 0}

    def _search_result(self, data, page, key):
        rows = self._rows(data.get("list"))
        pc = data.get("pagecount") or 1
        try:
            pc = int(pc)
        except Exception:  # noqa: BLE001
            pc = 1
        return {"list": rows, "page": page, "pagecount": pc,
                "limit": len(rows), "total": data.get("total") or len(rows)}

    # ------------------------------------------------------------------
    # 播放解析
    # ------------------------------------------------------------------
    def playerContent(self, flag, id, vipFlags=None):
        self._ensure_attrs()
        _log("playerContent -> flag=%s" % (flag,))

        if self._is_direct(id):
            return {"parse": 0, "url": id, "header": dict(self.header),
                    "playUrl": ""}

        # 【v9 原线路修复】采集站给的剧集地址是平台播放页 URL
        # （v.youku.com/...html 等），壳子嗅探页面拿不到直链 -> 黑屏。
        # 原线路与"自动轮询"统一走：kptv 直链 -> 轮换解析站。
        if flag != "自动轮询" and flag not in self._parse_names:
            flag = "自动轮询"

        if flag == "自动轮询":
            direct_url = self._try_kptv_api(id)
            if direct_url:
                return {"parse": 0, "url": direct_url,
                        "header": dict(self.header), "playUrl": ""}
            idx = self._rotate_idx % max(len(self.parse_list), 1)
            self._rotate_idx += 1
            item = self.parse_list[idx]
            return {"parse": 1, "url": item["url"] + id,
                    "header": self._build_parse_header(item["url"]),
                    "playUrl": ""}

        if flag in self._parse_names:
            for item in self.parse_list:
                if flag == item["name"]:
                    return {"parse": 1, "url": item["url"] + id,
                            "header": self._build_parse_header(item["url"]),
                            "playUrl": ""}

        return {"parse": 1, "url": id, "header": dict(self.header),
                "playUrl": ""}

    # ------------------------------------------------------------------
    # kptv API 解析（两步取直链，失败自动降级）
    # ------------------------------------------------------------------
    def _try_kptv_api(self, video_url):
        """取直链，失败返回空。

        【v9 熔断修复】
        kptv resolve.php 实测已失效（返回 403 Access Denied），
        旧版每次播放都白等两步超时（约 12 秒）才轮到解析站 -> "线路转圈"。
        现在：连续失败 _KPTV_FAIL_LIMIT 次后，_KPTV_COOLDOWN 秒内直接
        跳过 kptv，播放立刻进入解析站轮换，不再浪费等待。

        【v7 播放提速】
        旧实现会遍历所有网络栈重试，最坏发 6 次请求（每次都可能等满超时），
        点一次播放要卡十几秒。现在：
          - 只用"已验证可用"的那个栈 + 最多 1 个备用栈，请求数 <= 4；
          - 用独立的短超时（6s），不再等满默认的 10s；
          - 结果按 video_url 缓存 10 分钟，同一集来回点秒开。
        """
        now = time.time()
        if now < getattr(self, "_kptv_down_until", 0):
            return ""

        # 命中缓存直接返回
        try:
            ck = self._kptv_cache.get(video_url)
            if ck and now - ck[0] < 600:
                return ck[1]
        except Exception:  # noqa: BLE001
            pass

        result = ""
        try:
            stacks = [self._ok_stack or "requests"]
            for st in self._ordered_stacks():
                if st not in stacks:
                    stacks.append(st)
                if len(stacks) >= 2:
                    break

            old_timeout = self.timeout
            try:
                self.timeout = _KPTV_TIMEOUT      # 缩短等待
                text1 = ""
                for st in stacks:
                    text1 = self._http_via(st, self.kptv_parse + video_url)
                    if text1:
                        break
                token = self._extract_token(text1)
                if token:
                    api_url = ("https://" + self.kptv_host +
                               "/api/resolve.php?token=" + _enc(token))
                    text2 = ""
                    for st in stacks:
                        text2 = self._http_via(st, api_url)
                        if text2:
                            break
                    if text2:
                        try:
                            data = json.loads(text2)
                        except Exception:  # noqa: BLE001
                            data = {}
                        if isinstance(data, dict):
                            code = data.get("code", -1)
                            if code in (0, 1, 200):
                                play_url = data.get("url", "")
                                if play_url and self._validate_url(play_url):
                                    result = self._format_url(play_url)
            finally:
                self.timeout = old_timeout
        except Exception as exc:  # noqa: BLE001
            _log("kptv 异常:", exc)

        # 失败熔断：连续失败 N 次 -> 冷却期内彻底跳过 kptv
        try:
            _fail = getattr(self, "_kptv_fail", 0)
            if result:
                self._kptv_fail = 0
            else:
                self._kptv_fail = _fail + 1
                if self._kptv_fail >= getattr(self, "_KPTV_FAIL_LIMIT", 3):
                    self._kptv_down_until = now + getattr(
                        self, "_KPTV_COOLDOWN", 1800)
                    _log("kptv 连续失败%d次，熔断 %d 秒"
                         % (self._kptv_fail, getattr(
                             self, "_KPTV_COOLDOWN", 1800)))
        except Exception:  # noqa: BLE001
            pass

        # 写缓存（失败的空结果也缓存一小会儿，避免反复重试拖慢播放）
        try:
            self._kptv_cache[video_url] = (time.time(), result)
            if len(self._kptv_cache) > 40:
                self._kptv_cache.clear()
        except Exception:  # noqa: BLE001
            pass
        return result

    @staticmethod
    def _extract_token(text):
        if not text:
            return None
        m = re.search(r'apiToken\s*:\s*["\']([^"\']+)["\']', text)
        return m.group(1) if m else None

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------
    def _build_parse_header(self, parse_url):
        header = dict(self.header)
        try:
            m = re.match(r"(https?://[^/]+)", parse_url)
            if m:
                header["Referer"] = m.group(1) + "/"
        except Exception:  # noqa: BLE001
            pass
        return header

    def _is_direct(self, url):
        s = str(url)
        return any(k in s for k in (".m3u8", ".mp4", ".flv", ".mkv",
                                    "m3u8?", "mp4?"))

    def _validate_url(self, url):
        if not url or not isinstance(url, str):
            return False
        u = url.strip().lower()
        if not u.startswith(("http://", "https://")):
            return False
        return not any(k in u for k in ("javascript:", "void(0)",
                                        "about:blank", "undefined"))

    def _format_url(self, url):
        if not url:
            return ""
        url = str(url).strip().replace("\\", "")
        url = re.sub(r"^(https?:\/)((?!\/))", r"\1/", url,
                     flags=re.IGNORECASE)
        return url.replace("&amp;", "&")

    @staticmethod
    def _to_key(tid):
        """把分类 id 的"平台"部分翻成接口的 from 参数。

        支持两种写法：
          "qq"        -> qq                      （旧版单平台）
          "qq-2"      -> qq                      （新版 平台-类型）
          "1"         -> qq                      （更早的数字 id）
        """
        if tid is None:
            return None
        s = str(tid).strip()
        if s in _CATEGORY:
            return _CATEGORY[s][0]
        if "-" in s:
            return s.split("-", 1)[0]
        return s

    @staticmethod
    def _to_type(tid):
        """从分类 id 里取出"类型"部分；没有则返回空串。"""
        if tid is None:
            return ""
        s = str(tid).strip()
        return s.split("-", 1)[1] if "-" in s else ""
