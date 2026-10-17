#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""听书采集 —— 「随身听书书源插件 ShunSources v3」的独立 Python 移植版

从手机 App 的 JS 书源插件移植而来, 只用 Python 标准库, 无任何第三方依赖。
收录的都是走 JSON 接口、不需要浏览器就能跑的源:

  哔哩哔哩   有声书/广播剧视频(播放的是视频的音轨, 多 P 视频每个 P 是一集)
  懒人听书   正版源, 免费书籍较少, [VIP]/[精品] 需要账号
  蜻蜓FM     免费专辑可直接听(音频地址用 HMAC-MD5 签名), 收费专辑只有试听
  博看有声   图书馆数字资源, 经典名著/人文社科
  云图有声   正版有声书平台
  书音FM     有声小说/广播剧/评书/百家讲坛, 不需要登录
  央视听音   央视网"听节目"频道(播的是节目视频的声音, HLS 流)
  听友听书   有声小说和评书, 不需要登录

用法:
  python3 听书采集.py list                      列出全部书源
  python3 听书采集.py check                     一键体检: 每个源都打一遍, 谁通谁空谁错一目了然
  python3 听书采集.py check 鬼吹灯              用指定关键词体检
  python3 听书采集.py check 鬼吹灯 哔哩哔哩      只体检某个源
  python3 听书采集.py search 哔哩哔哩 斗罗大陆    搜索(源名可只写前几个字, 关键词可以有空格)
  python3 听书采集.py search 哔哩哔哩 斗罗大陆 2  搜索翻页
  python3 听书采集.py detail 哔哩哔哩 1          第 1 本书的详情和章节(序号来自上次搜索)
  python3 听书采集.py detail 哔哩哔哩 <书籍URL>  也可以直接给 URL
  python3 听书采集.py detail 哔哩哔哩 1 --first  只加载第一页章节(章节很多的书更快)
  python3 听书采集.py audio 哔哩哔哩 3           第 3 集的播放地址(序号来自上次详情)
  python3 听书采集.py audio 哔哩哔哩 <章节URL>

说明:
  - 需要登录/会员才能听的内容(蜻蜓收费专辑、懒人 VIP 等), 本工具不登录拿不到地址
  - 取到的播放地址如果带 Referer 要求, 会一并打印出来; 下载时记得带上, 否则可能 403
  - 搜索/详情的序号会记在系统临时目录里, 换着用几个源时各源互不干扰
  - 哪个源「没数据」先跑 check: 它区分「接口通了但真没这本书」和「接口返错/被拒」, 并把原因带出来
  - 也可以整个文件丢进 TVBox / PeekPro 这类「读 py」的壳当源用, 首页分类就是这些书源, 搜索是全源聚合
  - 壳接口有两套同时提供: 模块函数式(homeContent/searchContent...) + 类式(class Spider)。
    只认 Spider 类的壳会走类; 直接调函数的壳走函数, 两种壳都不用改。
"""

import hashlib
import hmac
import html as _html
import json
import os
import re
import ssl
import sys
import tempfile
import threading
import time
import uuid
from urllib import parse as _uparse
from urllib import request as _ureq

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
UA_MOBILE = ("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36")
TIMEOUT = 20
RETRY = 2

_SSL = ssl.create_default_context()
try:
    _SSL.check_hostname = False
    _SSL.verify_mode = ssl.CERT_NONE
except Exception:
    pass

_STATE_FILE = os.path.join(tempfile.gettempdir(), "tingshu_state.json")


# ================================================================ 基础请求

def _log(msg):
    print(msg, file=sys.stderr)


def _fetch(url, headers=None, data=None, timeout=TIMEOUT):
    """GET/POST 一个地址, 返回文本。data 是 bytes 时为 POST。"""
    hdr = {"User-Agent": UA, "Accept": "*/*", "Accept-Language": "zh-CN,zh;q=0.9"}
    if headers:
        hdr.update(headers)
    last = None
    for i in range(RETRY):
        try:
            req = _ureq.Request(url, data=data, headers=hdr)
            with _ureq.urlopen(req, timeout=timeout, context=_SSL) as resp:
                raw = resp.read()
            enc = None
            m = re.search(rb'charset=["\']?([\w-]+)', raw[:2048], re.I)
            if m:
                enc = m.group(1).decode("ascii", "ignore")
            for e in ([enc] if enc else []) + ["utf-8", "gb18030"]:
                if not e:
                    continue
                try:
                    return raw.decode(e)
                except Exception:
                    continue
            return raw.decode("utf-8", "ignore")
        except Exception as e:
            last = e
            time.sleep(0.4 * (i + 1))
    raise RuntimeError("请求失败 %s\n  %s" % (url, last))


def _get_json(url, headers=None, data=None):
    txt = (_fetch(url, headers, data) or "").strip()
    if txt.startswith("﻿"):
        txt = txt[1:]
    try:
        return json.loads(txt)
    except Exception:
        m = re.search(r"\{.*\}", txt, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        raise RuntimeError("接口返回的不是 JSON：%s" % txt[:120])


def _api_ok(j, who, code_path="code", ok=("0", "1", "200"), msg_path="msg"):
    """接口层校验。

    不少源在「版本被停用 / 被风控 / 域名换过」时, 是 HTTP 200 + 业务错误码 + 空列表,
    照原样读就是一片空白(也就是常说的"没数据")。这里把错误码和原因直接抛出来。
    """
    code = S(j, code_path)
    if code and code not in ok:
        raise RuntimeError("%s 接口返回 %s：%s"
                           % (who, code, S(j, msg_path) or S(j, "message") or "无说明"))
    return j


# ------------------------------------------------ JSON 取值（对应插件里的 str/int/items）

def _walk(obj, path):
    cur = obj
    for part in path.split("."):
        if cur is None:
            return None
        if isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except Exception:
                return None
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def S(obj, path=""):
    v = _walk(obj, path) if path else obj
    return "" if v is None else str(v)


def N(obj, path="", default=0):
    v = _walk(obj, path) if path else obj
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def L(obj, path=""):
    v = _walk(obj, path) if path else obj
    return v if isinstance(v, list) else []


# ================================================================ 书源实现
# 每个源提供: search(关键词, 页码) -> (books, 总页数)
#             detail(书籍URL, 是否加载全部章节) -> 详情 dict
#             audio(章节URL) -> (播放地址, 请求头 dict 或 None)

SOURCES = {}  # key -> {name, desc, search, detail, audio}


def _register(key, name, desc):
    def deco(fn):
        src = fn()
        src["key"] = key
        src["name"] = name
        src["desc"] = desc
        SOURCES[key] = src
        return src
    return deco


def _book(title, book_url, cover="", author="", artist="", intro="", status=""):
    return {"title": title, "bookUrl": book_url, "coverUrl": cover,
            "author": author, "artist": artist, "intro": intro, "status": status}


# ---------------------------------------------------------------- 哔哩哔哩

@_register("bilibili", "哔哩哔哩",
           "B 站的有声书/广播剧等，播放的是视频的声音，多 P 视频每个 P 是一集。")
def _src_bilibili():
    API = "https://api.bilibili.com/x/"
    COOKIE = "buvid3=" + uuid.uuid4().hex.upper() + "infoc"  # B 站接口需要一个随机 buvid3

    def get(url):
        j = _get_json(url, {"Cookie": COOKIE, "Referer": "https://www.bilibili.com/"})
        if N(j, "code") != 0:
            raise RuntimeError("B 站接口返回错误：%s（%s）" % (S(j, "message"), S(j, "code")))
        return j["data"]

    def https(u):
        return "https:" + u if u.startswith("//") else u

    def count(n):
        return ("%0.1f万" % (n / 10000)) if n >= 10000 else str(n)

    def search(keywords, page):
        data = get(API + "web-interface/search/type?search_type=video&keyword=%s&page=%d"
                   % (_uparse.quote(keywords), page))
        books = []
        for v in L(data, "result"):
            title = _html.unescape(re.sub(r"<[^>]+>", "", S(v, "title")))
            books.append(_book(title, "https://m.bilibili.com/video/" + S(v, "bvid"),
                               https(S(v, "pic")), artist=S(v, "author"),
                               intro=_html.unescape(S(v, "description")),
                               status="播放 %s · %s" % (count(N(v, "play")), S(v, "duration"))))
        return books, max(1, N(data, "numPages"))

    def detail(book_url, load_all=True):
        bvid = re.sub(r"/+$", "", book_url).split("/")[-1].split("?")[0]
        data = get(API + "web-interface/view?bvid=" + bvid)
        pages = L(data, "pages")
        episodes = [{"title": S(data, "title") if len(pages) == 1
                     else (S(p, "part") or ("P" + str(N(p, "page")))),
                     "url": "bili:%s:%s" % (S(data, "aid"), S(p, "cid"))} for p in pages]
        return {"title": S(data, "title"), "intro": S(data, "desc"),
                "artist": S(data, "owner.name"), "coverUrl": https(S(data, "pic")),
                "episodes": episodes}

    def audio(url):
        parts = url.split(":")
        if len(parts) != 3 or parts[0] != "bili":
            raise RuntimeError("章节地址格式不对，请重新查看章节列表")
        data = get(API + "player/playurl?avid=%s&cid=%s&platform=html5&otype=json&qn=16&type=mp4&html5=1"
                   % (parts[1], parts[2]))
        link = S(data, "durl.0.url")
        if not link:
            raise RuntimeError("没有获取到播放地址（可能是大会员或付费内容）")
        return link, {"Referer": "https://www.bilibili.com/"}

    return {"search": search, "detail": detail, "audio": audio}


# ---------------------------------------------------------------- 懒人听书

@_register("lrts", "懒人听书",
           "正版源，免费书籍较少。带 [VIP] / [精品] 的书需要登录账号后才能听。")
def _src_lrts():
    PAGE_SIZE = 50

    def parse_book(node):
        cover = S(node, "cover")
        if cover and "180" not in cover:
            dot = cover.rfind(".")
            if dot > 0:
                cover = cover[:dot] + "_180x254" + cover[dot:]
        title = S(node, "name")
        tags = S(node, "tags")
        if "VIP" in tags:
            title = "[VIP] " + title
        elif "精品" in tags:
            title = "[精品] " + title
        sections = N(node, "sections")
        intro = S(node, "recReason")
        if not intro or intro == "null":
            intro = S(node, "desc")
        return _book(title, "https://m.lrts.me?" + S(node, "id"), cover,
                     author=S(node, "author"), artist=S(node, "announcer"), intro=intro,
                     status=("完本" if N(node, "state") == 2 else "连载")
                     + (" · %d 集" % sections if sections > 0 else ""))

    def search(keywords, page):
        j = _get_json("https://m.lrts.me/ajax/search?keyWord=%s&pageSize=40&pageNum=%d&searchOption=1"
                      % (_uparse.quote(keywords), page))
        _api_ok(j, "懒人听书", code_path="apiStatus", ok=("0",))
        r = _walk(j, "data.bookResult") or {}
        books = [parse_book(b) for b in L(r, "list")]
        return books, max((N(r, "count") + 39) // 40, 1)

    def detail(book_url, load_all=True):
        book_id = book_url.split("?")[-1]
        episodes = []
        first = _get_json("https://m.lrts.me/ajax/getBookMenu?bookId=%s&pageNum=1&pageSize=%d&sortType=0"
                          % (book_id, PAGE_SIZE))
        if not first.get("list") and S(first, "msg"):
            raise RuntimeError(S(first, "msg"))

        def parse_page(j, offset):
            eps = []
            for i, t in enumerate(L(j, "list")):
                free = N(t, "payType") == 0
                eps.append({"title": S(t, "name"), "isFree": free, "url":
                            ("https://m.lrts.me/ajax/getPlayPath?entityId=%s&entityType=3&opType=1&sections=[%d]&type=0"
                             % (book_id, N(t, "section"))) if free else
                            "https://m.lrts.me/player?index=%d&entityType=3&sonId=%s&id=%s" % (offset + i, S(t, "id"), book_id)})
            return eps

        episodes = parse_page(first, 0)
        pages = (N(first, "sections") + PAGE_SIZE - 1) // PAGE_SIZE
        for p in range(2, pages + 1 if load_all else 2):
            _log("章节 %d / %d" % (p, pages))
            j = _get_json("https://m.lrts.me/ajax/getBookMenu?bookId=%s&pageNum=%d&pageSize=%d&sortType=0"
                          % (book_id, p, PAGE_SIZE))
            episodes += parse_page(j, len(episodes))
            time.sleep(0.2)
        info = _get_json("https://m.lrts.me/ajax/getBookInfo?id=" + book_id)
        return {"intro": S(info, "extraInfos.0.content"), "artist": S(info, "announcer"),
                "author": S(info, "author"), "coverUrl": S(info, "bestCover"),
                "episodes": episodes}

    def audio(url):
        if "getPlayPath" in url:
            j = _get_json(url)
            path = S(j, "list.0.path")
            if not path:
                raise RuntimeError(S(j, "msg") or "无法获取音频地址")
            return path, None
        raise RuntimeError("这是付费章节，需要登录懒人听书账号（本工具不处理登录）")

    return {"search": search, "detail": detail, "audio": audio}


# ---------------------------------------------------------------- 蜻蜓FM

@_register("qtfm", "蜻蜓FM",
           "免费专辑可以直接听；收费专辑只有前面试听的几集能听。")
def _src_qtfm():
    SITE = "https://www.qtfm.cn"
    CAPI = "https://i.qtfm.cn/capi/"
    PAGE = 100
    SIGN_KEY = b"7l8CZ)SgZgM_bkrw"  # 网页播放器里的固定签名密钥

    def api(url):
        j = _get_json(url, {"Referer": SITE + "/"})
        code = S(j, "errorno") or S(j, "errcode")
        if code and code != "0":
            raise RuntimeError("蜻蜓FM 接口返回错误：%s（%s）"
                               % (S(j, "errormsg") or S(j, "errmsg"), code))
        return j

    def to_book(c):
        play = S(c, "playcount")
        return _book(S(c, "title").strip(), "%s/channels/%s/" % (SITE, S(c, "id")),
                     S(c, "cover").replace("http://", "https://"),
                     artist=S(c, "podcaster"), intro=S(c, "description"),
                     status=("播放 " + play) if play else "")

    def search(keywords, page):
        j = api("https://search.qtfm.cn/v3/search?categoryid=0&k=%s&page=%d&pagesize=20&include=channel_ondemand"
                % (_uparse.quote(keywords), page))
        found = N(j, "data.data.numFound")
        books = [to_book(c) for c in L(j, "data.data.docs")]
        return books, max(1, min(50, (found + 19) // 20))

    def detail(book_url, load_all=True):
        m = re.search(r"channels/(\d+)", book_url)
        if not m:
            raise RuntimeError("不认识的地址：" + book_url)
        cid = m.group(1)
        c = api(CAPI + "v3/channel/" + cid).get("data") or {}
        count = N(c, "program_count")
        d = {"title": S(c, "title").strip(), "coverUrl": S(c, "cover").replace("http://", "https://"),
             "intro": S(c, "description"),
             "artist": "、".join(x for x in (S(p, "nick_name") for p in L(c, "podcasters")) if x),
             "status": ("已完结" if S(c, "finished") == "1" else "连载中")
                       + (" · %d 集" % count if count > 0 else "")}
        paid = N(c, "purchase.item_type") != 0

        def to_eps(j):
            return [{"title": S(p, "title").strip(),
                     "url": "%s/channels/%s/programs/%s/" % (SITE, cid, S(p, "id")),
                     "isFree": (not paid) or p.get("isfree") is True}
                    for p in L(j, "data.programs")]

        base = CAPI + "channel/%s/programs/%s?pagesize=%d&order=asc&curpage=" % (cid, S(c, "v"), PAGE)
        first = api(base + "1")
        episodes = to_eps(first)
        pages = (N(first, "data.total") + PAGE - 1) // PAGE
        for p in range(2, pages + 1 if load_all else 2):
            _log("节目 %d / %d" % (p, pages))
            episodes += to_eps(api(base + str(p)))
        d["episodes"] = episodes
        return d

    def audio(url):
        m = re.search(r"channels/(\d+)/programs/(\d+)", url)
        if not m:
            raise RuntimeError("不认识的章节地址：" + url)
        path = ("/audiostream/redirect/%s/%s?access_token=&device_id=MOBILESITE"
                "&qingting_id=&t=%d" % (m.group(1), m.group(2), int(time.time() * 1000)))
        sign = hmac.new(SIGN_KEY, path.encode("utf-8"), hashlib.md5).hexdigest()
        return "https://audio.qtfm.cn" + path + "&sign=" + sign, None

    return {"search": search, "detail": detail, "audio": audio}


# ---------------------------------------------------------------- 博看有声

@_register("bookan", "博看有声",
           "图书馆数字资源，经典名著、人文社科类有声书。章节地址就是音频直链。")
def _src_bookan():
    INSTANCE = "25304"

    def search(keywords, page):
        books, known = [], {}
        for tp in ("book", "album"):
            j = _get_json("https://es.bookan.com.cn/api/v3/voice/%s?instanceId=%s&keyword=%s"
                          "&pageNum=%d&limitNum=20" % (tp, INSTANCE, _uparse.quote(keywords), page))
            _api_ok(j, "博看有声")
            known[tp] = N(j, "data.last_page", 0)
            books += [_book(S(i, "name"), S(i, "id"), S(i, "cover")) for i in L(j, "data.list")]
        return books, max(page, known.get("book", 0), known.get("album", 0))

    def detail(book_url, load_all=True):
        episodes, page = [], 1
        while True:
            d = _get_json("https://api.bookan.com.cn/voice/album/units?album_id=%s&page=%d&num=20&order=1"
                          % (book_url, page)).get("data") or {}
            episodes += [{"title": S(i, "title"), "url": S(i, "file")} for i in L(d, "list")]
            total = N(d, "last_page", 1)
            if not load_all or page >= total:
                break
            _log("章节 %d / %d" % (page + 1, total))
            page += 1
            time.sleep(0.2)
        return {"episodes": episodes}

    def audio(url):
        return url, None

    return {"search": search, "detail": detail, "audio": audio}


# ---------------------------------------------------------------- 云图有声

@_register("yuntu", "云图有声",
           "正版有声书平台，经典文学、历史、少儿等。章节地址是音频直链。")
def _src_yuntu():
    API = "http://open-service.yuntuys.com/api/w_ys/book/"
    WECHAT = "wechat:07955551-706c-4259-9aa0-db4627dfca57"

    def to_book(i):
        chapters = N(i, "chapters")
        return _book(S(i, "bookName"), S(i, "bookId"), S(i, "cover"),
                     author=S(i, "authorName"), artist=S(i, "anchorName"),
                     intro=S(i, "summary"),
                     status=("共 %d 章" % chapters) if chapters else "")

    def search(keywords, page):
        j = _get_json(API + "search/%s/%s?pageSize=20&pageNum=%d"
                      % (WECHAT, _uparse.quote(keywords), page))
        _api_ok(j, "云图有声")
        data = j.get("data") or {}
        return [to_book(i) for i in L(data, "list")], max(1, N(data, "totalPage"))

    def detail(book_url, load_all=True):
        page, episodes = 1, []
        while True:
            q = _walk(_get_json(API + "getChapters/%s/%s/true/asc?pageSize=200&pageNum=%d"
                                % (WECHAT, book_url, page)), "data.pageQuery") or {}
            episodes += [{"title": S(i, "name"), "url": S(i, "audioUrl")} for i in L(q, "list")]
            total = N(q, "totalPage", 1)
            if not load_all or page >= total:
                break
            _log("章节 %d / %d" % (page + 1, total))
            page += 1
            time.sleep(0.2)
        return {"episodes": episodes}

    def audio(url):
        return url, None

    return {"search": search, "detail": detail, "audio": audio}


# ---------------------------------------------------------------- 书音FM

@_register("mekui", "书音FM",
           "有声小说、广播剧、评书、百家讲坛、相声小品等，内容全、分类细，不需要登录。")
def _src_mekui():
    SITE = "https://m.mekui.com"
    API = SITE + "/ecmsapi/index.php?"
    KEY = "056a308c515e16b2fe5a5c631319339cbc60a8ee0e03d016"
    CHAPTERS = 500

    def options():
        return {"Referer": SITE + "/", "Accept": "application/json, text/plain, */*"}

    def call(query):
        j = _get_json(API + query, options())
        if N(j, "code") != 1:
            raise RuntimeError("书音FM：%s" % (S(j, "message") or S(j, "msg") or "接口返回错误"))
        return j

    def to_book(b):
        return _book(S(b, "title").strip(), "%s/album-%s-%s.html" % (SITE, S(b, "classid"), S(b, "id")),
                     S(b, "titlepic"), artist=S(b, "player"), intro=S(b, "moviesay"),
                     status=S(b, "filetype"))

    def ids(url):
        m = re.search(r"(?:album|audio)[-/](\d+)-(\d+)(?:-(\d+))?\.html", url)
        if not m:
            raise RuntimeError("不认识的地址：" + url)
        return m.group(1), m.group(2), m.group(3)

    def search(keywords, page):
        j = call("act=search&mod=movie&keyword=%s&page=%d&pagesize=20"
                 % (_uparse.quote(keywords), page))
        return [to_book(b) for b in L(j, "data.list")], max(page, N(j, "data.totalpage", page))

    def detail(book_url, load_all=True):
        class_id, book_id, _ = ids(book_url)
        d = _walk(call("mod=movie&act=detail&id=" + book_id), "data.detail") or {}
        out = {"title": S(d, "title").strip(), "coverUrl": S(d, "titlepic"),
               "intro": S(d, "moviesay"),
               "artist": S(d, "player") or S(d, "playadmin"),
               "status": " · ".join(x for x in (S(d, "filetype"), S(d, "firstclassname")) if x),
               "episodes": []}

        def to_eps(j):
            eps = []
            for e in L(j, "data.moielist"):
                free = S(e, "control") == "0" and S(e, "level") == "0" and S(e, "ofen") == "0"
                eps.append({"title": S(e, "title").strip() or ("第 %s 集" % S(e, "id")),
                            "url": "%s/audio/%s-%s-%s.html" % (SITE, class_id, book_id, S(e, "id")),
                            "isFree": free})
            return eps

        base = API + "mod=movie&act=movielist&id=%s&pagesize=%d&page=" % (book_id, CHAPTERS)
        first = _get_json(base + "1", options())
        out["episodes"] = to_eps(first)
        pages = N(first, "data.totalpage", 1)
        for p in range(2, pages + 1 if load_all else 2):
            _log("章节 %d / %d" % (p, pages))
            out["episodes"] += to_eps(_get_json(base + str(p), options()))
        return out

    def audio(url):
        _, book_id, no = ids(url)
        if not no:
            raise RuntimeError("不认识的章节地址：" + url)
        t = int(time.time())
        token = hashlib.md5(("act=wapseries&id=%s&mod=movie&movieId=%s&t=%d&token=%s"
                             % (book_id, no, t, KEY)).encode("utf-8")).hexdigest()
        j = _get_json(API + "act=wapseries&mod=movie&id=%s&movieId=%s&t=%d&token=%s"
                      % (book_id, no, t, token), options())
        if N(j, "code") != 1 or not j.get("data"):
            raise RuntimeError(S(j, "message") or S(j, "msg") or "没有拿到播放地址（可能需要会员）")
        link = S(j, "data.SeriesUrl")
        for u in L(j, "data.signed_urls"):
            if not link and isinstance(u, str) and u:
                link = u
        if not link:
            raise RuntimeError("这一集网站没有给出播放地址（可能需要会员）")
        return link, {"Referer": SITE + "/"}

    return {"search": search, "detail": detail, "audio": audio}


# ---------------------------------------------------------------- 央视听音

@_register("cctv", "央视听音",
           "央视网“听音”频道：百家讲坛等讲座、评书、戏曲、历史人文。播放的是节目视频的声音（HLS 流）。")
def _src_cctv():
    SITE = "https://tv.cctv.com"
    LIST = "https://api.cntv.cn/newVideoset/getVideoAlbumListByPageIdTvty?serviceId=tvty&n=20"

    def options():
        return {"Referer": SITE + "/ty/m/index.shtml"}

    def plain(s):
        return _html.unescape(re.sub(r"<[^>]+>", "", str(s))).strip()

    def search(keywords, page):
        j = _get_json("https://search.cctv.com/m/if3g_search.php?page=%d&qtext=%s&type=audio"
                      "&sort=SCORE&pageSize=20&channel="
                      % (page, _uparse.quote(keywords)),
                      {"Referer": "https://search.cctv.com/m/search.php?type=audio"})
        seen, books = set(), []
        for v in L(j, "list"):
            aid = S(v, "ALBUMID")
            if not aid or aid in seen:
                continue
            seen.add(aid)
            books.append(_book(plain(S(v, "DRETITLE")),
                               S(v, "PAGELINK").split("?")[0].replace("//tv.cctv.cn/", "//tv.cctv.com/"),
                               S(v, "IMAGELINK"), intro=plain(S(v, "DRECONTENT")),
                               status=S(v, "CHANNEL")))
        return books, max(page, min(50, (N(j, "total") + 19) // 20))

    def detail(book_url, load_all=True):
        m = re.search(r"(VIDA[0-9A-Za-z]+)", book_url)
        if not m:
            raise RuntimeError("不认识的地址：" + book_url)
        aid = m.group(1)
        d = {"episodes": []}
        try:
            a = _walk(_get_json("https://api.cntv.cn/NewVideoset/getVideoAlbumInfo?id=%s&serviceId=tvcctv" % aid,
                                options()), "data") or {}
            d["title"] = S(a, "title").strip()
            d["intro"] = S(a, "brief")
            d["coverUrl"] = S(a, "image")
        except Exception as e:
            _log("取专辑信息失败：%s" % e)
        base_book = book_url.split("?")[0]
        for mode in (0, 1):
            if d["episodes"]:
                break
            p = 1
            while p <= 50:
                j = _get_json("https://api.cntv.cn/NewVideo/getVideoListByAlbumIdNew?id=%s"
                              "&serviceId=tvcctv&mode=%d&pub=1&n=100&sort=asc&p=%d" % (aid, mode, p), options())
                lst = L(j, "data.list")
                for v in lst:
                    guid = S(v, "guid")
                    if guid:
                        d["episodes"].append({"title": S(v, "title").strip(),
                                              "url": base_book + "?guid=" + guid})
                if len(lst) < 100 or len(d["episodes"]) >= N(j, "data.total"):
                    break
                _log("节目第 %d 页" % (p + 1))
                p += 1
        d["status"] = ("%d 期" % len(d["episodes"])) if d["episodes"] else ""
        return d

    def audio(url):
        m = re.search(r"[?&]guid=([0-9a-fA-F]+)", url)
        if not m:
            raise RuntimeError("不认识的章节地址：" + url)
        j = _get_json("https://vdn.apps.cntv.cn/api/getHttpVideoInfo.do?pid=" + m.group(1),
                      {"Referer": SITE + "/"})
        hls = S(j, "hls_url")
        if not hls:
            raise RuntimeError("央视网没有给出这期节目的播放地址"
                               + ("：%s" % S(j, "tip_msg") if S(j, "tip_msg") else "（可能有版权限制）"))
        return hls, {"Referer": SITE + "/", "X-Media-Type": "hls"}

    return {"search": search, "detail": detail, "audio": audio}


# ---------------------------------------------------------------- 听友听书

@_register("tingyou", "听友听书",
           "有声小说和评书比较全，更新快，不需要登录。接口域名经常换，会自动探测。")
def _src_tingyou():
    SITE = "https://tingyou.fm"
    BASES = ["https://api-preview.toulaopao.cc/api",
             "https://appp.fdhtbz.cn/api",
             "https://laopaoaappi.oobyvy.vip/api"]
    state = {"base": None, "session": uuid.uuid4().hex}

    def call(path, body=None, allow_empty=False):
        bases = ([state["base"]] if state["base"] else []) + list(BASES)
        try:
            m = re.search(r'https://[a-z0-9.-]+/api(?=["/])',
                          _fetch(SITE + "/listening", {"User-Agent": UA}), re.I)
            if m:
                bases.append(m.group(0))
        except Exception:
            pass
        last = None
        tried = set()
        for base in bases:
            if not base or base in tried:
                continue
            tried.add(base)
            try:
                hdr = {"Origin": SITE, "Referer": SITE + "/", "Accept": "application/json",
                       "x-listening-session": state["session"],
                       "x-listening-timezone": "Asia/Shanghai"}
                data = None
                if body is not None:
                    data = json.dumps(body).encode("utf-8")
                    hdr["Content-Type"] = "application/json"
                text = _fetch(base + "/h5/listening/" + path, hdr, data)
                if not text.strip() and allow_empty:
                    state["base"] = base
                    return {}
                j = json.loads(text)
                if isinstance(j, dict) and j.get("error"):
                    raise RuntimeError(S(j, "message") or "接口返回错误")
                state["base"] = base
                return j
            except Exception as e:
                last = e
        raise RuntimeError("听友听书的接口现在访问不了：%s" % last)

    def to_book(a):
        count = N(a, "count")
        return _book(S(a, "title").strip(), "%s/listening/album/%s" % (SITE, S(a, "id")),
                     S(a, "cover_url"), author=S(a, "author"), artist=S(a, "teller"),
                     intro=S(a, "intro") or S(a, "description") or S(a, "synopsis"),
                     status=("已完结" if N(a, "status") == 0 else "连载中")
                             + (" · %d 集" % count if count > 0 else ""))

    def search(keywords, page):
        j = call("search", {"keyword": keywords, "page": page})
        books = [to_book(a) for a in L(j, "results")]
        total = page + 1 if j.get("has_more") and books else page
        return books, total

    def detail(book_url, load_all=True):
        m = re.search(r"album/(\d+)", book_url)
        if not m:
            raise RuntimeError("不认识的地址：" + book_url)
        aid = m.group(1)
        a = call("album/" + aid)
        if a.get("available") is False:
            raise RuntimeError("这本书已经下架了")
        d = to_book(a)
        d["episodes"] = []
        c = call("chapters/" + aid)
        for ch in L(c, "chapters"):
            d["episodes"].append({"title": S(ch, "title").strip() or ("第 %d 集" % N(ch, "index")),
                                  "url": "%s/listening/album/%s#%d" % (SITE, aid, N(ch, "index"))})
        return d

    def audio(url):
        m = re.search(r"album/(\d+)#(\d+)$", url)
        if not m:
            raise RuntimeError("不认识的章节地址：" + url)
        j = call("play", {"album_id": m.group(1), "chapter_idx": int(m.group(2))})
        link = S(j, "play_url")
        if not link:
            raise RuntimeError(S(j, "detail") or S(j, "message") or "没有拿到播放地址")
        return link, None

    return {"search": search, "detail": detail, "audio": audio}


# ================================================================ 命令行

def _load_state():
    try:
        with open(_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_state(st):
    try:
        with open(_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False)
    except Exception:
        pass


def _resolve_source(name):
    name = name.strip()
    for key, src in SOURCES.items():
        if key == name or src["name"] == name:
            return src
    for key, src in SOURCES.items():
        if key.startswith(name) or src["name"].startswith(name) or name in src["name"]:
            return src
    raise RuntimeError("找不到书源「%s」，用 list 命令看看有哪些源" % name)


def _pick(st, kind, src, arg):
    """detail/audio 的参数：序号(来自上一次 search/detail) 或原始 URL"""
    if re.fullmatch(r"\d+", arg):
        lst = (st.get(kind) or {}).get(src["key"]) or []
        i = int(arg)
        if not lst:
            raise RuntimeError("没有可用的序号记录，先执行一次 search/detail")
        if not (1 <= i <= len(lst)):
            raise RuntimeError("序号超出范围（1 ~ %d）" % len(lst))
        item = lst[i - 1]
        return item["bookUrl"] if kind == "search" else item["url"]
    return arg


def _cut(s, n=60):
    s = (s or "").replace("\n", " ").replace("\r", " ").strip()
    return s if len(s) <= n else s[:n] + "…"


def cmd_list():
    print("可用书源（search/detail/audio 的源名写前几个字就行）：\n")
    for src in SOURCES.values():
        print("  %-8s %s" % (src["name"], _cut(src["desc"], 76)))


def cmd_search(src, keywords, page):
    books, total = src["search"](keywords, page)
    if not books:
        print("没有搜到「%s」（%s）" % (keywords, src["name"]))
        print("接口是通的、只是这个源没这本书 —— 换本书或换个源。"
              "想确认这个源还活着：python3 %s check"
              % os.path.basename(sys.argv[0]))
        return
    st = _load_state()
    st.setdefault("search", {})[src["key"]] = books
    _save_state(st)
    for i, b in enumerate(books, 1):
        extra = " ｜ ".join(x for x in (b.get("artist") or b.get("author"), b.get("status")) if x)
        print("[%2d] %s%s" % (i, b["title"], (" ｜ " + extra) if extra else ""))
        if b.get("intro"):
            print("      %s" % _cut(b["intro"]))
    print("\n第 %d / %d 页。查看某本书：python3 %s detail %s 序号"
          % (page, total, os.path.basename(sys.argv[0]), src["key"]))


def cmd_detail(src, arg, load_all):
    st = _load_state()
    book_url = _pick(st, "search", src, arg)
    d = src["detail"](book_url, load_all)
    eps = d.get("episodes") or []
    st.setdefault("detail", {})[src["key"]] = eps
    _save_state(st)
    for k, label in (("title", "书名"), ("author", "作者"), ("artist", "演播"),
                     ("status", "状态"), ("intro", "简介")):
        if d.get(k):
            print("%s：%s" % (label, _cut(d[k], 200)))
    print("\n共 %d 集%s：" % (len(eps), "（--first 模式下只加载了第一页）" if not load_all else ""))
    for i, e in enumerate(eps, 1):
        mark = "" if e.get("isFree", True) else " 🔒"
        print("[%4d] %s%s" % (i, e["title"], mark))
    print("\n取播放地址：python3 %s audio %s 序号" % (os.path.basename(sys.argv[0]), src["key"]))


def cmd_audio(src, arg):
    st = _load_state()
    url = _pick(st, "detail", src, arg)
    link, headers = src["audio"](url)
    print(link)
    if headers:
        print("\n下载/播放时要带这些请求头（不带可能 403）：")
        for k, v in headers.items():
            print("  %s: %s" % (k, v))
        print("\ncurl 示例：")
        print("  curl -L -O %s '%s'"
              % (" ".join("-H '%s: %s'" % kv for kv in headers.items()), link))


def cmd_check(keywords, only=None):
    """一键体检: 把每个源都真打一遍搜索, 通/空/错 + 耗时, 一眼看出是哪个源出问题。"""
    todo = [s for s in SOURCES.values()
            if not only or only == s["key"] or only in s["name"] or s["key"].startswith(only)]
    if not todo:
        print("没有匹配「%s」的源，用 list 看看有哪些" % only)
        return
    print("书源体检（关键词「%s」）：\n" % keywords)
    rows, ok = [], 0
    for src in todo:
        t0 = time.time()
        try:
            books, total = src["search"](keywords, 1)
            cost = time.time() - t0
            if books:
                ok += 1
                rows.append(("[通]", src["name"], cost, "%d 条（共 %s 页）" % (len(books), total)))
            else:
                rows.append(("[空]", src["name"], cost,
                             "接口通了、0 条 —— 可能这源真没这个词，也可能接口字段改了"))
        except Exception as e:
            rows.append(("[错]", src["name"], time.time() - t0,
                         _cut(str(e).replace("\n", " "), 120)))
    for mark, name, cost, info in rows:
        print("  %s %-8s %5.1fs  %s" % (mark, name, cost, info))
    print("\n通 %d / %d。带 [错] / [空] 的那几行整行甩我，直接定位是哪个源出问题。"
          % (ok, len(rows)))


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("help", "-h", "--help"):
        print(__doc__.strip())
        return
    cmd, rest = args[0], args[1:]
    try:
        if cmd == "list" and not rest:
            cmd_list()
        elif cmd == "check":
            cmd_check(rest[0] if rest else "小说", rest[1] if len(rest) > 1 else None)
        elif cmd == "search" and len(rest) >= 2:
            page = 1
            if len(rest) >= 3 and rest[-1].isdigit():
                page = int(rest[-1])
                rest = rest[:-1]
            cmd_search(_resolve_source(rest[0]), " ".join(rest[1:]), page)
        elif cmd == "detail" and len(rest) >= 2:
            load_all = "--first" not in rest
            rest = [a for a in rest if a != "--first"]
            cmd_detail(_resolve_source(rest[0]), rest[1], load_all)
        elif cmd == "audio" and len(rest) >= 2:
            cmd_audio(_resolve_source(rest[0]), rest[1])
        else:
            print(__doc__.strip())
            sys.exit(2)
    except KeyboardInterrupt:
        print("\n已取消", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print("错误：%s" % e, file=sys.stderr)
        sys.exit(1)


# 直接跑 = 命令行工具；被壳(TVBox / PeekPro 这类读 py 的)加载 = 当源用(见下面「壳接口」)
if globals().get("__name__") == "__main__":
    main()


# ================================================================ 壳(py 源)接口
# 把整个文件丢进 TVBox / PeekPro 这类「读 py」的壳里, 它就是一个能听书的源:
#   首页分类 = 每个书源      分类页 = 用默认词搜一批
#   搜索     = 全源并发聚合  详情    = 章节列表      播放 = 真音频地址
# 壳里 ext 留空即用; 想在壳里固定默认搜索词, ext 填 {"kw":"鬼吹灯"};
# 只想留几个源, ext 填 {"kw":"玄幻","sources":["mekui","tingyou"]}

_SHELL = {"kw": "小说"}


def init(cfg=None):
    """壳先把配置(ext)传进来。给个关键词就是默认搜索词, 给 JSON 还能筛源。

    cfg 允许四种: 空 / "鬼吹灯" / '{"kw":"鬼吹灯"}' / 已经是 dict(有些壳直接丢 dict)
    """
    o = cfg
    if isinstance(o, (bytes, bytearray)):
        try:
            o = o.decode("utf-8", "ignore")
        except Exception:
            o = ""
    if o is None or o == "":
        return
    if not isinstance(o, dict):
        txt = str(o).strip()
        if not txt:
            return
        if txt[0] in "{[":
            try:
                o = json.loads(txt)
            except Exception:
                o = txt
        else:
            o = txt
    if isinstance(o, dict):
        if o.get("kw"):
            _SHELL["kw"] = str(o["kw"])
        if o.get("sources"):
            keep = set(str(x) for x in o["sources"])
            for k in list(SOURCES):
                if k not in keep:
                    SOURCES.pop(k)
        return
    _SHELL["kw"] = str(o).strip()


def _shell_book(src, b):
    return {"vod_id": "%s|%s" % (src["key"], b.get("bookUrl") or ""),
            "vod_name": b.get("title") or "",
            "vod_pic": b.get("coverUrl") or "",
            "vod_remarks": b.get("status") or "",
            "vod_content": b.get("intro") or ""}


def homeContent(filter=None):
    return {"class": [{"type_id": s["key"], "type_name": s["name"]} for s in SOURCES.values()]}


def categoryContent(tid, pg, filter=None, extend=None):
    src = SOURCES.get(str(tid))
    if not src:
        return {"page": pg, "pagecount": 1, "limit": 20, "total": 0, "list": []}
    kw = _SHELL["kw"]
    if isinstance(extend, dict) and extend.get("kw"):
        kw = str(extend["kw"])
    try:
        books, total = src["search"](kw, int(pg or 1))
    except Exception as e:
        _log("[听书壳] %s 取列表失败：%s" % (src["name"], e))
        books, total = [], 1
    return {"page": int(pg or 1), "pagecount": max(1, int(total or 1)), "limit": 20,
            "total": len(books), "list": [_shell_book(src, b) for b in books]}


def detailContent(ids):
    if isinstance(ids, str):
        ids = [ids]
    out = []
    for vid in ids or []:
        key, _, book_url = str(vid).partition("|")
        src = SOURCES.get(key)
        if not src:
            continue
        try:
            d = src["detail"](book_url, True)
        except Exception as e:
            _log("[听书壳] %s 详情失败：%s" % (src["name"], e))
            continue
        plays = []
        for i, e in enumerate(d.get("episodes") or [], 1):
            name = re.sub(r"[#$]", " ", str(e.get("title") or ("第%d集" % i))).strip()
            plays.append("%s$%s|%s" % (name, key, e.get("url") or ""))
        out.append({"vod_id": vid, "vod_name": d.get("title") or book_url,
                    "vod_pic": d.get("coverUrl") or "",
                    "vod_content": d.get("intro") or "",
                    "vod_remarks": d.get("status") or "",
                    "vod_play_from": src["name"],
                    "vod_play_url": "#".join(plays)})
    return {"list": out}


def _shell_search_all(key, pg=1, per=20, wait=12):
    """多源并发搜索, 慢的源到点就丢, 不拖累整体。"""
    lock = threading.Lock()
    hits = []

    def work(src):
        try:
            books, _t = src["search"](key, pg)
        except Exception as e:
            _log("[听书壳] %s 搜索失败：%s" % (src["name"], e))
            return
        with lock:
            for b in (books or [])[:per]:
                hits.append((src["key"], b))

    ths = [threading.Thread(target=work, args=(s,)) for s in list(SOURCES.values())]
    for t in ths:
        t.daemon = True
        t.start()
    for t in ths:
        t.join(wait)
    return hits


def searchContent(key, quick=False, pg=1):
    hits = _shell_search_all(key, int(pg or 1))
    if not hits:
        _log("[听书壳] 全源都没搜到「%s」，跑 check 看是哪些源坏了" % key)
    return {"list": [_shell_book(SOURCES[k], b) for k, b in hits if k in SOURCES]}


def playerContent(flag, id, vipFlags=None):
    key, _, url = str(id).partition("|")
    src = SOURCES.get(key)
    if not src:
        return {"parse": 0, "playUrl": "", "header": {}}
    try:
        link, headers = src["audio"](url)
    except Exception as e:
        _log("[听书壳] %s 取播放地址失败：%s" % (src["name"], e))
        return {"parse": 0, "playUrl": "", "header": {}}
    return {"parse": 0, "playUrl": link, "header": headers or {}}


def homeVideoContent():
    return {"list": []}


# ================================================================ 类式壳接口（Spider 类）
# 壳有两大派：
#   A 派：加载模块后直接调模块里的 homeContent / searchContent 这些函数（上面那批）
#   B 派：加载模块后先找名叫 Spider 的类（实例化成对象再调方法）——
#         找不到就直接整源判失败，报「模块中没有 Spider 类」。
# 下面这层 Spider 把上面的函数按标准签名挂进来，A / B 两派壳都能直接用。

_IFACE = {
    "init": init,
    "homeContent": homeContent,
    "homeVideoContent": homeVideoContent,
    "categoryContent": categoryContent,
    "detailContent": detailContent,
    "searchContent": searchContent,
    "playerContent": playerContent,
}

SPIDER_NAME = "听书合集"


class Spider(object):
    """听书采集的类式入口：一个 Spider 实例 = 8 个听书源的聚合。"""

    def __init__(self, *args, **kwargs):
        self.extend = ""
        self.name = SPIDER_NAME
        if args and isinstance(args[0], (str, bytes, dict)):
            self.extend = args[0]

    # ------------------------------------------------------------ 生命周期
    def init(self, extend="", *args, **kwargs):
        """壳把 ext 传进来：空 = 默认词「小说」；「鬼吹灯」= 默认搜索词；
        '{"kw":"鬼吹灯","sources":["mekui","tingyou"]}' = 顺带筛源。"""
        if extend in (None, "") and args:
            extend = args[0]
        self.extend = extend
        try:
            _IFACE["init"](extend)
        except Exception as e:
            _log("[听书壳] 读取配置失败：%s" % e)
        return self

    def setExtend(self, extend=""):
        return self.init(extend)

    def getName(self):
        return SPIDER_NAME

    def getDependence(self):
        return []

    def manualVideoCheck(self):
        return False

    def isVideoFormat(self, url):
        """央视那种是 HLS 流，交给壳自带的播放器；其余都是 mp3 直链。"""
        return ".m3u8" in str(url or "").lower()

    def destroy(self):
        return None

    def homeLayout(self):
        return None

    # ------------------------------------------------------------ 首页
    def homeContent(self, *args, **kwargs):
        flt = kwargs.get("filter")
        if flt is None and args:
            flt = args[0]
        try:
            return _IFACE["homeContent"](flt)
        except Exception as e:
            _log("[听书壳] 首页分类失败：%s" % e)
            return {"class": [], "list": []}

    def homeVideoContent(self, *args, **kwargs):
        return {"list": []}

    # ------------------------------------------------------------ 分类
    def categoryContent(self, tid, pg="1", filter=None, extend=None):
        try:
            return _IFACE["categoryContent"](tid, pg, filter, extend)
        except Exception as e:
            _log("[听书壳] 分类页失败：%s" % e)
            return {"page": 1, "pagecount": 1, "limit": 20, "total": 0, "list": []}

    # ------------------------------------------------------------ 详情
    def detailContent(self, ids, *args, **kwargs):
        try:
            return _IFACE["detailContent"](ids)
        except Exception as e:
            _log("[听书壳] 详情失败：%s" % e)
            return {"list": []}

    # ------------------------------------------------------------ 搜索
    def searchContent(self, key, quick=False, pg="1"):
        try:
            return _IFACE["searchContent"](key, quick, pg)
        except Exception as e:
            _log("[听书壳] 搜索失败：%s" % e)
            return {"list": []}

    def searchContentPage(self, key, quick=False, pg="1"):
        return self.searchContent(key, quick, pg)

    # ------------------------------------------------------------ 播放
    def playerContent(self, flag, id, vipFlags=None):
        if isinstance(id, (list, tuple)):
            id = id[0] if id else ""
        try:
            d = _IFACE["playerContent"](flag, id, vipFlags)
        except Exception as e:
            _log("[听书壳] 取播放地址失败：%s" % e)
            return {"parse": 0, "url": "", "playUrl": "", "header": {}, "msg": str(e)}
        # 两种壳读的字段名不一样，都给齐
        d = dict(d or {})
        url = d.get("playUrl") or d.get("url") or ""
        d["url"] = url
        d["playUrl"] = url
        d.setdefault("header", {})
        d.setdefault("parse", 0)
        return d