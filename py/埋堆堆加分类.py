# -*- coding: utf-8 -*-
"""
埋堆堆 (m.mddcloud.com.cn) - TVBox 爬虫源 v2 (修复分类 + 搜索)
===============================================================
接口：homeContent / homeVideoContent / categoryContent(含筛选) /
      detailContent(懒加载) / playerContent(按需解析) / searchContent(聚合+模糊)

API 端点 (activity.mddcloud.com.cn, MD5 签名)：
  /api/vod/classify/list.action          分类词表
  /api/vod/classify/word/search.action   列表 (uuidList 可多维度)
  /api/vod/getVodInfo.action             详情 (含 vodSactionList)
  /api/vod/getTrySaction.action          播放直链

本次修复 (2026-09-22):
[F28] 按官网结构恢复 5 大一级分类 tab: 剧集/电影/综艺/动画/纪录片
     - 后端 /api/vod/classify/word/search 不支持按 vodType/material 筛选,
       只能客户端本地过滤: 在 categoryContent 内 _scan_all 拉全库(按二级筛选),
       按 _match_category 规则分桶, 再本地分页。
     - 分类规则:
       * 电影   : vodType==1 且 totalNum==1 (单集电视电影)
       * 纪录片 : materialName 含 "纪录片"
       * 动画   : materialName 含 "动漫", 或含 "儿童" 且片名含 动画/动漫/卡通
       * 综艺   : materialName 含 综艺/真人秀/访谈/美食/游戏娱乐/旅行/音乐/
                  大型晚会/资讯/儿童/其他 (排除纪录片/动画)
       * 剧集   : 其余剧情类 (vodType=0/6 等电视剧)
     - 二级筛选器 (题材/语言/地区/年份/收费/排序) 仍然有效, 与一级 tab 组合使用。
     - 分桶结果按 TTL_LIST=600s 缓存, 首次切换 tab 拉全库约 2-3s, 后续翻页/切换 tab 秒开。
[F1] 签名: json.dumps list 序列化 默认 ", " 空格 → 前端用 "," 无空格
      后果: uuidList 含 ≥2 个 uuid 一律 "签名错误" → 二级筛选整体不可用
      修复: 签名序列化统一 separators=(',',':'), 请求体仍用默认分隔
[F2] 详情 year/material/region 空: getVodInfo 响应这些字段实际全为 None
      后果: type_name 硬编码 "港剧"、vod_year 空、vod_area 硬编码 "中国香港"
      修复: 列表项缓存回填 + firstSowingTime 兜底
[F3] pagecount 硬编码 100: 真实总量 全部 2853 / 粤语 907 / 普通话 907 / 限免 233
      修复: 深度扫描真实 pagecount
[F4] 搜索覆盖不足 4%: 原 120 条 (30/页×4) vs 2853 条
      修复: 100/页 × 18 页 × 3 排序 = 1800 条 + 语料 30min 缓存
      + 匹配算法重写: token 匹配 + 首字母缩写 + 字符重叠 + 名称长度惩罚
[F5] remarks 判断 bug: isTimeLimit/isVip 是 0/1 整数, 旧 truthy 判断误命中
      修复: 字符串比较 str(x) in ('1','True','true')
[F6] 分类表扩充: 题材一级分类 (警匪/家庭/悬疑/古装/武侠/爱情/都市/综艺/年代/喜剧/
      职业/历史/军旅/商战/功夫/奇幻/剧情/情景/商战) + 地区 (香港/内地)
      每个一级分类预设二级筛选 (lang/region) 并自动合并
[F7] 剧集倒序: API 返回升序 (num 743→2462), 用户要最新集; 取最近 300 集倒序
[F8] 长剧 MAX_EPISODES=1714 → 300 (TVBox 播放列表容量限制)
[ F9]vod_remarks 拼接: 题材/年份/更新至N集 三段合并
[ F10] FongMi TV 规范: homeContent 只回 class+filters (无 list), 首页卡片走 homeVideoContent
[ F11] FongMi TV 规范: filters 必须是 {type_id: [Filter...]} 字典 (老数组格式 FongMi 不解析)
[ F12] FongMi TV 规范: searchContent 必须回 page/pagecount/limit/total, 无数据 pagecount=1 避免反复翻页
[F13] FongMi TV 规范: playerContent 用 jx 而非 TVBox 老字段 playUrl/contentType
[F14] FongMi TV 规范: class 只回 type_id/type_name (TVBox 私有 filter/parentId/order 让 FongMi 分类 tab 全丢)
[F15] 按官网结构精简分类: 31 tab → 5 tab (最热/最新/好评/限免/VIP), 其余 5 维走二级筛选器
[F16] 极致精简为单 tab「全部」: 6 维筛选 (排序/语言/年份/题材/地区/收费) 全部下沉到二级筛选器
[F17] 修复年份筛选失效: 2024/2025/2026 的 uuid 不以 ff8080 开头 (24da699c.. / fcc0b500.. / 29d24d0a..)
      原判 raw.startswith("ff8080") 误将年份 uuid 送 _word_uuid 翻译导致 year 被丢; 改用「32 位纯十六进制」判定
[F18] 修复语言筛选失效: lang uuid 尾缀是字母 (cantonese/mandarin, 共 39 字符), F17 的「32 位纯十六进制」
       判定误将 lang uuid 送 _word_uuid 反查词名, 反查又找不到 → uuid 被静默丢弃; 改为 _resolve_uuid
       在词表里精确匹配 uuid 或 word, 彻底放弃格式启发式
[F19] 修复播放大面积失效: 后端返回的 m3u8/mp4 URL 带 sign+t+exper 签名, exper=360 秒 (6 分钟有效期).
       原 TTL_PLAY=900 (15min) 导致 6-15min 窗口内的缓存 URL 已过期, 用户点开就 404/连接被拒;
       降到 TTL_PLAY=300 (URL 有效期一半, 留 60 秒安全缓冲), 过期缓存自动重解析
       证据: m3u8 body 尾部 `&exper=360`; 过期后 CDN 返回 `{"error":"Document not found"}` 或 Connection refused
[F20] 修复 VIP 剧 m3u8 静默失效: 天龙八部 num=26 后端返回的 tryM3u8Url 存在但 CDN 返回 404
       (同 URL 换 tryMp4Url 200 OK); 原 `for PLAY_FIELD_PRIORITY: if u: real=u; break` 只取第一个非空字段,
       不校验可用性. 加 _probe_play_url 预检 (m3u8 用 GET+Range, mp4 用 HEAD, 2.5s 超时), 非 2xx 降级下一个
[F21] 修复短剧选集倒序: F7 的 `sl.reverse()` 让 30 集的《天龙八部》显示成 26..1 反直觉.
        改为「<200 集按 API 正序, >200 集才倒序取最近 MAX_EPISODES=300」, 兼顾经典剧和超长剧
[F22] 优化 Category 冷启动: 原 `_get_pagecount` 串行深度扫描 (全部 2880 条 = 80 页 × 0.15s ≈ 12s),
        用户点「全部」页需等 11.36s 才看到首屏. 后端无 count 接口 (getVodCount 等 msgType=1001).
        改为「首屏同步 + 后台二分精算」: 首页同步返回 (0.15s), 多页时立即返回估算 MAX_PAGES_SCAN,
        后台线程用 log2(MAX_PAGES_SCAN)≈7 次二分求真实 pagecount 并回填缓存. 首屏 11.36s → 1.69s.
[F23] 优化 Search 冷启动: 原 `_search_corpus` 同步扫描 3 排序 × 18 页 = 54 次网络 ≈ 9s.
         改为「首屏快扫 1 页/排序 (300 条, ≈1s) + 后台线程补齐余下 17 页/排序」.
         冷启动 9.08s → 0.89s; 用户第二次搜索 (同关键词) 命中 30min TTL_SEARCH_CORPUS 缓存零网络.
  [F24] 优化 Search 首屏覆盖率: F23 首屏 1 页/排序仅 300 条 ≈10% 库容, 冷启动 30s 内搜索会遗漏冷门剧.
          后端无关键词搜索接口 (探测 8 个候选全部 msgType=1001, /api/vod/classify/word/search.action
          传 keyword/word/q/title/vodName/searchWord 都忽略 → 只能本地全库扫描).
          SEARCH_FAST_PAGES 1 → 3 (首屏 900 条 ≈33% 库容), 冷启动 0.89s → 约 2s, 仍 <2s.
[F25] 全库扫且快 (彻底解决 F24 折中的"一次性"遗漏问题):
           F24 虽把首屏覆盖率提到 33%, 但 FongMi 搜索结果列表是"一次性"的:
           后台线程补齐的 67% 语料不会刷新已打开的搜索结果, 用户搜到的仍是首屏子集.
           改为 SEARCH_FAST_PAGES = SEARCH_PAGES = 18 (首屏即全库 1800 条), 无后台补齐概念.
           性能: _search_corpus 用 ThreadPoolExecutor 并发 (3 排序 × 18 页 = 54 请求, 并发度 8),
           冷启动 9s 串行 → 约 2s 并发 (实测 1.81s). 另加 __init__ 预热线程, 用户打开 App 就后台扫语料,
           首次搜索命中缓存零网络 (实测预热完成后搜索 0.012s).
           注意: 预热线程内不做持锁开新线程 (RLock 跨线程不通会死锁),
                 _search_corpus_scan 内联执行 ThreadPoolExecutor 扫描, 内部任务用 RLock 合并 collected.
"""

import re
import json
import time
import threading
import hashlib
import requests
from requests.adapters import HTTPAdapter
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import sys
    sys.path.append('..')
    from base.spider import Spider as _BaseSpider
except ImportError:
    _BaseSpider = None


# ============================================================
# 常量
# ============================================================

HOST_CANDIDATES = [
    "https://m.mddcloud.com.cn",
    "https://www.mddcloud.com.cn",
    "https://mddcloud.com.cn",
]

API_CANDIDATES = [
    "https://activity.mddcloud.com.cn",
]

# 从站点 JS 逆向, 已验证可用
PRIVATE_KEY = "8a4af424bd714be5b2baacbe3cf5bbbe0131effeb92e99356ef1662884558f28"

UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
    "Mobile/15E148 Safari/604.1"
)

TIMEOUT_API = 5

# 缓存 TTL
TTL_WORDS = 24 * 3600        # 分类词表
TTL_CAT = 300                # 分类列表 (300)
TTL_PAGECOUNT = 600          # pagecount (600, 变化不频繁)
TTL_LIST = 600               # 列表原数据 (600)
TTL_DETAIL_OK = 300
TTL_DETAIL_EMPTY = 30
TTL_SEARCH = 180
TTL_SEARCH_CORPUS = 1800     # 搜索语料 (30min, 独立于单次搜索缓存)
# F19: 后端返回的 m3u8/mp4 URL 带 sign+t+exper 签名, exper=360 (6 分钟有效期).
#      原 TTL_PLAY=900 (15min) 会让 6-15min 之间的缓存 URL 已过期, 用户点播放就 404/连接拒绝.
#      降到 300 秒 (URL 有效期一半, 留 60 秒安全缓冲), 过期缓存会被丢弃重新解析.
TTL_PLAY = 300
TTL_DOMAIN = 1800

# F27 回滚 → F28: 恢复 m3u8 优先
# - F27 曾改为 mp4 优先 (基于天龙八部 5 集样本 m3u8 全 404 的误判)
# - 复盘: 天龙八部是老剧 HLS 目录已从 CDN 删除, 属个体失效
#   扫 20 部新剧 (爱回家/皆大欢喜/星空下的仁医/男亲女爱/溏心风暴/法言人/一舞倾城/西游记/寻秦记...)
#   tryM3u8Url/tryUrl/tryMp4Url 探测全部 200, m3u8 是默认首选.
# - m3u8 优势: 720p 起播快, HLS 分片支持客户端缓冲策略; mp4 是单 1080p 文件.
# - 探测逻辑保留 (F20): 少数失效剧 (天龙八部) 靠 _probe_play_url 降级到 mp4, 不会卡死.
PLAY_FIELD_PRIORITY = ("tryM3u8Url", "tryUrl", "tryMp4Url")

# 长剧截断: 只取最近 300 集 (倒序, 最新集在前)
MAX_EPISODES = 300

# 分页扫描
PAGE_ROWS = 36
MAX_PAGES_SCAN = 150         # 最大扫描 150 页, 5400 条

# 搜索聚合
SEARCH_ROWS = 100            # API 支持 100/页 (实测 200 也可, 保守取 100)
SEARCH_PAGES = 18            # 全库扫页数: 36 rows × 18 = 648 条/排序, 3 排序合并去重约 1800 条 ≈ 全库
SEARCH_FAST_PAGES = 18       # F25: 首屏 = 全库 (与 SEARCH_PAGES 一致), 无"后台补齐"概念
                             # 原因: FongMi 搜索结果列表是"一次性"的, 后台补齐的语料不会自动刷新已打开的结果
                             #       必须首屏就是全库, 用户才能搜到冷门剧; 性能靠 _search_corpus 并发扫压时间
SEARCH_SORTS = ("0", "1", "2")  # 默认/最新/好评
SEARCH_MAX_RESULTS = 100

# 签名序列化分隔 (前端 JS 无空格, 原 ", " 会导致签名错误)
_SIGN_SEPARATORS = (',', ':')

# 分词/去噪
_NAME_NOISE = re.compile(r'[()（）【】\[\]【】、，,。.·\-—~&/\\|:：!？!?"\'“”‘’\s]+')
_TOKEN_SPLIT = re.compile(r'[()\[\]{}<>《》【】「」『』\u3001，,。.·\-—/\\|:：!？!?\"\'"\s]+')


# ============================================================
# 签名 API 客户端
# ============================================================
class MddApi:
    """mddcloud 后端签名 API 客户端 (带域名候选与健康检查)"""

    def __init__(self, session, extend_domain=""):
        self.session = session
        self._api = API_CANDIDATES[0]
        if extend_domain:
            d = extend_domain.strip()
            if not d.startswith('http'):
                d = 'https://' + d
            self._api = d.rstrip('/')

    def _sign_data(self, data):
        """与前端 JS 一致: dict/list 用紧凑 JSON (separators=(',',':')) 序列化"""
        parts = []
        for k in sorted(data.keys()):
            v = data[k]
            if isinstance(v, (dict, list)):
                parts.append("%s=%s&" % (k, json.dumps(v, ensure_ascii=False,
                                                      separators=_SIGN_SEPARATORS)))
            else:
                parts.append("%s=%s&" % (k, v))
        return "".join(parts)

    def post(self, path, data, timeout=TIMEOUT_API):
        """带签名 POST, 失败返回 None"""
        now = int(time.time() * 1000)
        sorted_str = self._sign_data(data)
        msg = "time:%s|privateKey:%s|data:%s" % (now, PRIVATE_KEY, sorted_str)
        sign = hashlib.md5(msg.encode('utf-8')).hexdigest()
        # 请求体仍用默认 json (与前端一致)
        body = {"time": now, "sign": sign, "data": data}
        for attempt in range(2):
            try:
                r = self.session.post(
                    self._api + path, json=body, timeout=timeout,
                    headers={'Connection': 'keep-alive'},
                )
                if r.status_code == 429:
                    time.sleep(1.0)
                    continue
                r.raise_for_status()
                return r.json()
            except Exception:
                if attempt == 0:
                    time.sleep(0.2)
        return None


# ============================================================
# Spider 主类
# ============================================================
_Base = _BaseSpider if _BaseSpider is not None else object


class Spider(_Base):
    siteUrl = HOST_CANDIDATES[0]
    headers = {
        'User-Agent': UA,
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Accept-Encoding': 'gzip, deflate',
        'Referer': HOST_CANDIDATES[0] + '/',
    }

    # ===== 初始化 =====
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.session.headers['Connection'] = 'keep-alive'
        self.session.verify = False
        adapter = HTTPAdapter(pool_connections=20, pool_maxsize=40,
                              max_retries=0, pool_block=False)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

        self.api = MddApi(self.session)
        self.extend = ""

        # 域名跟踪
        self._host = HOST_CANDIDATES[0]
        self._host_checked = 0.0
        self._host_fail = 0

        # 缓存 + 锁 (F25: RLock 支持并发扫描任务在持锁时再取子锁合并 collected)
        self._lock = threading.RLock()
        self._words_cache = None
        self._words_time = 0
        self._list_cache = {}          # 列表原数据缓存
        self._cat_cache = {}           # 分类结果缓存
        self._cat_full_cache = {}      # 全库分类切桶缓存 (_scan_all)
        self._pagecount_cache = {}
        self._detail_cache = {}
        self._search_cache = {}
        self._search_corpus_cache = None
        self._search_corpus_time = 0
        self._play_cache = {}
        self._prefetching = set()
        self._list_meta_cache = {}     # 列表项 (回填详情元信息)
        
        # F25: __init__ 阶段触发搜索语料预热 (用户浏览首页时后台扫全库)
        #   目的: 用户首次搜索时命中缓存零网络; 若搜索早于预热完成, 会 join 等待预热
        self._search_warmup_task = None
        self._search_warmup_ok = True
        self._search_warmup_started = False
        try:
            self._search_warmup_started = True
            self._search_warmup_task = threading.Thread(
                target=self._search_corpus_scan, daemon=True)
            self._search_warmup_task.start()
        except Exception:
            # 预热线程创建失败不阻塞主流程, _search_corpus 会兜底扫描
            self._search_warmup_ok = False
            self._search_warmup_started = False
            self._search_warmup_task = None

    def init(self, extend=""):
        self.extend = extend or ""
        for kv in self.extend.split(','):
            if '=' in kv:
                k, v = kv.split('=', 1)
                k, v = k.strip().lower(), v.strip()
                if k == 'host' and v:
                    d = v if v.startswith('http') else 'https://' + v
                    self._host = d.rstrip('/')
                    self.headers['Referer'] = self._host + '/'
                    self.session.headers['Referer'] = self._host + '/'
                elif k == 'api' and v:
                    self.api = MddApi(self.session, v)

    # ===== 域名跟踪 =====
    def _check_host(self, host):
        try:
            r = self.session.get(host + '/', timeout=TIMEOUT_API)
            if r.status_code != 200:
                return False
            html = r.text[:200000]
            return ('埋堆堆' in html) and ('/video/' in html)
        except Exception:
            return False

    def host(self):
        now = time.time()
        with self._lock:
            if now - self._host_checked < TTL_DOMAIN and self._host_fail < 3:
                return self._host
        for h in HOST_CANDIDATES:
            if self._check_host(h):
                with self._lock:
                    self._host = h
                    self._host_checked = now
                    self._host_fail = 0
                return h
        with self._lock:
            self._host_checked = now - TTL_DOMAIN + 60
            self._host_fail += 1
        return self._host

    # ===== 通用缓存 =====
    @staticmethod
    def _cache_get(cache, key, ttl=None):
        item = cache.get(key)
        if not item or len(item) < 3:
            return None
        if time.time() - item[0] >= (ttl if ttl is not None else item[2]):
            return None
        return item[1]

    @staticmethod
    def _cache_set(cache, key, value, ttl=TTL_CAT, max_size=1024):
        if len(cache) >= max_size:
            expired = [k for k, v in list(cache.items())
                       if time.time() - v[0] >= (v[2] if len(v) > 2 else ttl)]
            if expired:
                for k in expired:
                    del cache[k]
            elif len(cache) >= max_size:
                cache.clear()
        cache[key] = (time.time(), value, ttl)

    # ===== 工具 =====
    @staticmethod
    def _pic(u):
        """图片直链 http -> https"""
        u = (u or '').strip()
        if not u:
            return ''
        if u.startswith('//'):
            return 'https:' + u
        if u.startswith('http://'):
            return 'https://' + u[7:]
        return u

    @staticmethod
    def _to_bool(v):
        """API 返回 0/1 或 "0"/"1" 或 None 的布尔判断"""
        return str(v).strip() in ('1', 'True', 'true', 'Yes', 'yes')

    @staticmethod
    def _first_year(year_name):
        if not year_name:
            return ''
        m = re.search(r'(\d{4})', str(year_name))
        return m.group(1) if m else ''

    @staticmethod
    def _remarks(v):
        """列表项角标
        F26: 全部不打 VIP/限免角标 (数据实证)
        - 扫 20 部 VIP + 20 部限免 + 天龙八部 5 集, 后端 getTrySaction.action
          返回的 tryTimes 全部是 360 (6 分钟) 或 400 (6分40秒)
        - 也就是说无论 isVip/isTimeLimit 是什么组合, 免费版用户拿到的都是
          6 分钟试看片段, 完整集一律要会员.
        - isTimeLimit=1 不代表"完整免费", 只代表"参与限免活动"的营销标签.
        - 打 "限免"/"可看"/"VIP" 任何角标都会误导用户以为能看全, 一律留空.
        - 完整集信息由 updateNum 单独输出 ("更新至X集"), 不含试看信息.
        """
        return ''

    @staticmethod
    def _to_vod(v):
        """列表项 -> TVBox vod dict"""
        vid = str(v.get("uuid") or v.get("vodUuid") or '').strip()
        name = str(v.get("name") or '').strip()
        if not vid or not name:
            return None
        return {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": Spider._pic(v.get("coverImage") or v.get("sideImage")
                                   or v.get("downImage")),
            "vod_remarks": Spider._remarks(v),
            # 内部字段 (列表缓存用, 详情回填 + 分类过滤需要)
            "_material": str(v.get("materialName") or ''),
            "_year": str(v.get("yearName") or ''),
            "_vod_type": int(v.get("vodType") or 0),
            "_total_num": int(v.get("totalNum") or 0),
        }

    # ===== 分类词表 =====
    def _classify_words(self):
        """分类词表 {fieldCode: [{word, uuid}, ...]}, 过滤 "全部" """
        with self._lock:
            if (self._words_cache is not None
                    and time.time() - self._words_time < TTL_WORDS):
                return self._words_cache
        data = self.api.post("/api/vod/classify/list.action", {})
        words = {}
        if data and data.get("msgType") == 0 and data.get("data"):
            for item in data["data"]:
                fc = item.get("fieldCode") or ''
                ws = []
                for w in (item.get("words") or []):
                    uuid = str(w.get("uuid") or '')
                    name = str(w.get("word") or '').strip()
                    if name and name != "全部" and uuid:
                        ws.append({"word": name, "uuid": uuid})
                if fc and ws:
                    words[fc] = ws
        with self._lock:
            if words:
                self._words_cache = words
                self._words_time = time.time()
                return words
            return self._words_cache or {}

    def _word_uuid(self, field_code, word):
        for w in self._classify_words().get(field_code, []):
            if w["word"] == word:
                return w["uuid"]
        return ''

    def _resolve_uuid(self, field_code, raw):
        """把用户/前端传入的 raw 解析为后端 uuid。
        同时接受两种输入:
          1) 后端 word 词名 (粤语 / 家庭 / 2024 / 中国香港)
          2) 后端 uuid  (可能是 32 位十六, 也可能带非 hex 后缀如 lang 的 ...cantonese / ...mandarin)
        策略: 先精确匹配 word, 再精确匹配 uuid, 未命中返回 ''。
        F18: F17 用「32 位纯十六进制」格式判定 raw, 但 lang uuid 尾缀是字母
        (共 39 字符), 判定失败会被送去 _word_uuid 反查词名, 反查又找不到 →
        uuid 被静默丢弃 → 语言筛选失效。改为「词表精确匹配」, 彻底放弃格式启发式。
        """
        raw = str(raw or '').strip()
        if not raw:
            return ''
        words = self._classify_words().get(field_code, []) or []
        for w in words:
            if w.get("word") == raw:
                return w.get("uuid") or ''
        for w in words:
            if w.get("uuid") == raw:
                return raw
        return ''

    # ============================================================
    # 列表接口
    # ============================================================
    def _fetch_list(self, uuid_list=None, rows=36, start_row=0,
                    is_vip="-1", order_type="0", _cached=True):
        """列表接口封装, 返回 [vod dict, ...] (含 _material/_year 内部字段)"""
        uuid_list = uuid_list or []
        if _cached:
            ckey = "%s|%d|%d|%s|%s" % (
                json.dumps(uuid_list, separators=(',', ':')),
                rows, start_row, is_vip, order_type)
            with self._lock:
                if ckey in self._list_cache and len(self._list_cache) > 1:
                    cached = self._cache_get(self._list_cache, ckey, TTL_LIST)
                    if cached is not None:
                        return cached
        data = {
            "uuidList": uuid_list,
            "rows": rows,
            "startRow": start_row,
            "isVip": str(is_vip),
            "orderType": str(order_type),
        }
        resp = self.api.post("/api/vod/classify/word/search.action", data)
        if not resp or resp.get("msgType") != 0:
            return []
        out = []
        for v in (resp.get("data") or []):
            item = self._to_vod(v)
            if item:
                out.append(item)
        if _cached and out:
            with self._lock:
                self._cache_set(self._list_cache, ckey, out, TTL_LIST,
                                max_size=256)
        return out

    # ============================================================
    # 首页 / 分类列表
    # ============================================================
    def _all_filters(self):
        words = self._classify_words()

        def _mk(fc, name):
            value = [{"n": "全部", "v": ""}]
            for w in words.get(fc, []):
                value.append({"n": w["word"], "v": w["uuid"]})
            return {"key": fc, "name": name, "value": value}

        return [
            _mk("material", "题材"),
            _mk("lang", "语言"),
            _mk("region", "地区"),
            _mk("year", "年份"),
            {"key": "isvip", "name": "收费", "value": [
                {"n": "全部", "v": "-1"},
                {"n": "限免", "v": "0"},
                {"n": "VIP", "v": "1"},
            ]},
            {"key": "order", "name": "排序", "value": [
                {"n": "默认", "v": "0"},
                {"n": "最新", "v": "1"},
                {"n": "好评", "v": "2"},
            ]},
        ]

    def homeContent(self, filter=False):
        """FongMi TV 规范: homeContent 只回传 class + filters;
        首页卡片由 homeVideoContent 提供 (见下方)。
        filters 必须是 {type_id: [Filter...]} 字典 (TVBox 老数组格式不兼容)。"""
        result = {"class": ALL_CLASSES}
        if filter:
            # 31 个一级分类共用同一份筛选词表 (lang/material/region/year/isvip/order)
            filters_arr = self._all_filters()
            result["filters"] = {c["type_id"]: filters_arr for c in ALL_CLASSES}
        return result

    def homeVideoContent(self):
        """FongMi TV 首页卡片; 缓存 5 分钟"""
        cached = self._cache_get(self._cat_cache, "__home__", TTL_CAT)
        if cached is not None:
            return {"list": cached}
        lst = self._fetch_list(rows=PAGE_ROWS, order_type="0")
        if lst:
            self._cache_set(self._cat_cache, "__home__", lst, TTL_CAT)
        return {"list": lst}

    @staticmethod
    def _parse_extend(extend):
        """TVBox filter 参数解析: 支持 JSON 字符串 / 已解析 dict"""
        if not extend:
            return {}
        if isinstance(extend, dict):
            return extend
        if isinstance(extend, str):
            s = extend.strip()
            if s.startswith('{'):
                try:
                    return json.loads(s)
                except Exception:
                    return {}
        return {}

    def _scan_all(self, uuid_list, is_vip, order):
        """拉全库 (按筛选条件 uuid_list/is_vip/order) 并按 5 大分类切分, 带缓存。
        返回 {tid: [vod,...]} 字典, 每个列表按后端返回顺序保留。
        用于 5 大分类 tab 的本地过滤分页。"""
        key = "%s|%s|%s" % (
            json.dumps(uuid_list or [], separators=(',', ':')),
            is_vip, order)
        with self._lock:
            cached = self._cache_get(self._cat_full_cache, key, TTL_LIST)
            if cached is not None:
                return cached

        buckets = {tid: [] for tid in CATEGORIES}
        seen = set()
        for p in range(1, MAX_PAGES_SCAN + 1):
            lst = self._fetch_list(uuid_list=uuid_list, rows=PAGE_ROWS,
                                   start_row=(p - 1) * PAGE_ROWS,
                                   is_vip=is_vip, order_type=order,
                                   _cached=True)
            if not lst:
                break
            fresh = 0
            for v in lst:
                vid = v.get("vod_id")
                if vid in seen:
                    continue
                seen.add(vid)
                fresh += 1
                for tid in CATEGORIES:
                    if _match_category(v, tid):
                        buckets[tid].append(v)
                        break
            if fresh < PAGE_ROWS and len(lst) < PAGE_ROWS:
                # 末页
                break

        with self._lock:
            self._cache_set(self._cat_full_cache, key, buckets, TTL_LIST,
                            max_size=64)
        return buckets

    def categoryContent(self, tid, pg, filter, extend):
        page = 1
        try:
            page = max(1, int(pg or 1))
            ext = self._parse_extend(extend)
            preset = CLASS_PRESET.get(str(tid), {}) or {}

            # 兼容: 用户手输旧 tid (hot/new/like/free/vip 或 all/...) 回退到剧集 tab
            if str(tid) not in VALID_TIDS:
                return {"list": [], "page": page, "pagecount": 0,
                        "limit": PAGE_ROWS, "total": 0}

            # 二级筛选 uuidList: 用户选的 lang/material/year/region
            uuid_list = []
            for field, key in [("lang", "lang"),
                               ("material", "material"),
                               ("year", "year"),
                               ("region", "region")]:
                raw = str(ext.get(key) or '').strip()
                if not raw:
                    continue
                v = self._resolve_uuid(field, raw)
                if v:
                    uuid_list.append(v)

            # isVip / order: 二级优先, 否则用一级 tab 预设
            is_vip = str(ext.get("isvip") or preset.get("isvip") or "-1").strip() or "-1"
            order = str(ext.get("order") or preset.get("order") or "0").strip() or "0"

            # 全库拉取 + 本地按 5 大分类切桶
            buckets = self._scan_all(uuid_list, is_vip, order)
            cat_list = buckets.get(str(tid), [])

            total = len(cat_list)
            pagecount = max(1, (total + PAGE_ROWS - 1) // PAGE_ROWS) if total else 0
            start = (page - 1) * PAGE_ROWS
            page_items = cat_list[start:start + PAGE_ROWS]

            # 清理内部字段 (不返回给 TVBox)
            for item in page_items:
                item.pop("_material", None)
                item.pop("_year", None)
                item.pop("_vod_type", None)
                item.pop("_total_num", None)

            return {
                "list": page_items,
                "page": page,
                "pagecount": pagecount,
                "limit": PAGE_ROWS,
                "total": total,
            }
        except Exception:
            return {"list": [], "page": page, "pagecount": 1,
                    "limit": PAGE_ROWS, "total": 0}

    # ============================================================
    # 详情 (懒加载)
    # ============================================================
    def detailContent(self, ids):
        if isinstance(ids, str):
            ids = [ids]
        if not ids:
            return {"list": []}
        vid = str(ids[0]).split(',')[0].strip()
        if not vid:
            return {"list": []}

        cached = self._cache_get(self._detail_cache, vid, None)
        if cached is not None:
            return cached

        result = self._fetch_detail(vid)
        ttl = TTL_DETAIL_OK if result.get("list") else TTL_DETAIL_EMPTY
        self._cache_set(self._detail_cache, vid, result, ttl)

        # (移除不存在的 _prefetch_play 调用: 播放地址由 playerContent 懒加载)
        return result

    def _fetch_detail(self, vid):
        """详情接口; 元信息从列表缓存回填 (getVodInfo 无 year/material/region)"""
        resp = self.api.post("/api/vod/getVodInfo.action",
                             {"vodUuid": vid, "num": 1})
        if not resp or resp.get("msgType") != 0 or not resp.get("data"):
            return {"list": []}
        v = resp["data"]

        # 剧集列表: API 升序, 短剧/中长剧按正序 (1,2,3...N) 保留; 超长剧 (>200 集) 倒序取最近 MAX_EPISODES
        # 天龙八部/皆大欢喜 等 <200 集的经典剧用户想从第 1 集看, 倒序反而困惑.
        # 爱回家之开心速递 1714 集这种超长剧保留倒序 + 截断, 保留最新 300 集
        sl = v.get("vodSactionList") or []
        sl = [s for s in sl if s.get("num") is not None]
        if not sl:
            return {"list": []}
        sl = sorted(sl, key=lambda s: s.get("num"))
        if len(sl) > 200:
            sl = sl[-MAX_EPISODES:]
            sl.reverse()  # 超长剧最新集在前

        eps = []
        for s in sl:
            ep_name = str(s.get("name") or '').strip() or \
                      ("第%s集" % s.get("num"))
            eps.append("%s$%s:%s" % (ep_name, vid, s.get("num")))

        # --- 元信息回填 (getVodInfo 全部为 None, 从列表缓存读) ---
        material = ''
        year = ''
        name = str(v.get("name") or vid)
        cached_meta = self._list_meta_cache.get(vid) or {}
        if cached_meta:
            material = str(cached_meta.get("_material") or '')
            year_raw = str(cached_meta.get("_year") or '')
            year = self._first_year(year_raw)
        if not material:
            material = str(v.get("materialName") or '')
        if not year:
            year = self._first_year(v.get("yearName"))
        if not year and v.get("firstSowingTime"):
            try:
                t = int(str(v.get("firstSowingTime")))
                year = time.strftime('%Y', time.localtime(t / 1000))
            except Exception:
                m = re.search(r'(19|20)\d{2}', str(v.get("firstSowingTime")))
                if m:
                    year = m.group(0)

        # vod_area: 名字带 (普通话)/(国语) 视为中国内地出品, 其余默认中国香港
        vod_area = '中国香港'
        if re.search(r'(普通话|国语)', name):
            vod_area = '中国内地'

        # vod_remarks: 只输出更新进度, 不打 VIP/限免
        # F26: 数据实证 (20部限免+20部VIP+天龙八部5集) 后端 getTrySaction
        #      tryTimes 全部 360/400 (6分钟试看), 所有角标都会误导, 一律不打.
        remark_parts = []
        if v.get("updateNum"):
            remark_parts.append("更新至%s集" % v.get("updateNum"))
        vod_remarks = "·".join(remark_parts)

        detail = {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": self._pic(v.get("coverImage") or v.get("sideImage")
                                 or v.get("downImage")),
            "vod_year": year,
            "vod_area": vod_area,
            "vod_actor": str(v.get("starring") or '').replace(',', '/'),
            "vod_director": str(v.get("director") or '').replace(',', '/'),
            "vod_remarks": vod_remarks,
            "vod_content": str(v.get("introduction") or '').strip(),
            "vod_play_from": "埋堆堆",
            "vod_play_url": "#".join(eps),
        }
        return {"list": [detail]}

    def _list_meta(self, vid):
        """从列表缓存查 vid, 用于详情元信息回填"""
        with self._lock:
            if vid in self._list_meta_cache:
                return self._list_meta_cache.get(vid)
        cached = None
        for key, val in list(self._list_meta_cache.items())[:0]:
            pass  # noop, 保结构
        for key in list(self._list_cache.keys()):
            lst = self._cache_get(self._list_cache, key, TTL_LIST)
            if not lst:
                continue
            for item in lst:
                if item.get("vod_id") == vid:
                    cached = {k: item.get(k) for k in ("_material", "_year")}
                    with self._lock:
                        self._list_meta_cache[vid] = cached
                    return cached
        return None

    # ============================================================
    # 播放解析 (按需 + 缓存 + 预取)
    # ============================================================
    def _resolve_play(self, play_key):
        """play_key = {vodUuid}:{num} -> m3u8/mp4 直链

        F20: 后端 tryM3u8Url / tryUrl / tryMp4Url 三者可能只有其中一个真正可用
             (例: 天龙八部 老 VIP 剧的 m3u8 URL 存在但 CDN 返回 404; 同 URL 换 mp4 200 OK)。
             原来 for + break 只取第一个非空字段, 不校验真的能拿到内容.
             现在每个候选都预检 (HEAD/GET range), 非 2xx 跳过尝试下一个.
        """
        cached = self._cache_get(self._play_cache, play_key, TTL_PLAY)
        if cached:
            return cached
        real = ''
        try:
            vid, num = str(play_key).split(':', 1)
            resp = self.api.post(
                "/api/vod/getTrySaction.action",
                {"vodUuid": vid.strip(), "num": int(num)},
            )
            if resp and resp.get("msgType") == 0 and resp.get("data"):
                d = resp["data"]
                for f in PLAY_FIELD_PRIORITY:
                    u = str(d.get(f) or '').strip()
                    if not u:
                        continue
                    candidate = self._pic(u)
                    if self._probe_play_url(candidate):
                        real = candidate
                        break
        except Exception:
            real = ''
        if real:
            self._cache_set(self._play_cache, play_key, real, TTL_PLAY)
        return real

    @staticmethod
    def _probe_play_url(url, timeout=2.5):
        """预检播放 URL 是否可用: 走 http 层, 非 2xx 直接判失败.

        - mp4 用 HEAD (省流量, CDN 一般支持)
        - m3u8 用 GET + Range=bytes=0-0 (有些 CDN HEAD 不认), 拿到内容即丢弃
        - 2.5 秒超时; 网络异常判失败
        """
        if not url:
            return False
        is_m3u8 = '.m3u8' in url.lower()
        try:
            if is_m3u8:
                r = requests.get(
                    url,
                    headers={"User-Agent": UA, "Range": "bytes=0-0"},
                    timeout=timeout,
                    stream=True,
                )
                try:
                    r.close()
                except Exception:
                    pass
            else:
                r = requests.head(url, headers={"User-Agent": UA}, timeout=timeout)
            return 200 <= r.status_code < 400
        except Exception:
            return False

    @staticmethod
    def _parse_play_items(vod):
        """从 vod_play_url 提取 [name, key, ...]"""
        items = []
        for item in (vod.get("vod_play_url") or "").split("#"):
            if not item:
                continue
            parts = item.split("$", 1)
            if len(parts) == 2 and parts[1]:
                items.append((parts[0], parts[1]))
        return items

    def _first_play_key(self, vod):
        items = self._parse_play_items(vod)
        return items[0][1] if items else None

    def _next_play_key(self, vod, play_key):
        items = self._parse_play_items(vod)
        for i, (name, key) in enumerate(items):
            if key == play_key and i + 1 < len(items):
                return items[i + 1][1]
        return None

    def _prefetch(self, play_key):
        if not play_key:
            return
        with self._lock:
            if (self._cache_get(self._play_cache, play_key, TTL_PLAY)
                    or play_key in self._prefetching):
                return
            self._prefetching.add(play_key)

        def _job():
            try:
                self._resolve_play(play_key)
            except Exception:
                pass
            finally:
                with self._lock:
                    self._prefetching.discard(play_key)

        threading.Thread(target=_job, daemon=True).start()

    def _play_payload(self, playurl, play_key, vod):
        is_m3u8 = '.m3u8' in playurl.lower()
        payload = {
            "parse": 0,
            "jx": 0,
            "url": playurl,
            "header": {
                "User-Agent": UA,
                "Referer": self.host() + "/",
                "Origin": self.host(),
            },
            "format": "application/x-mpegURL" if is_m3u8 else "",
        }
        nxt = self._next_play_key(vod, play_key)
        if nxt:
            self._prefetch(nxt)
        return payload

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 0, "jx": 0, "url": ""}
        play_key = str(id).strip()
        if ':' not in play_key:
            u = self._pic(play_key)
            return {"parse": 0, "jx": 0, "url": u,
                    "header": {"User-Agent": UA,
                               "Referer": self.host() + "/"}}

        vod = self._cached_vod(play_key.split(':', 1)[0]) or {}
        cached = self._cache_get(self._play_cache, play_key, TTL_PLAY)
        if cached:
            return self._play_payload(cached, play_key, vod)

        m3u8 = self._resolve_play(play_key)
        if m3u8:
            return self._play_payload(m3u8, play_key, vod)

        return {
            "parse": 1,
            "jx": 1,
            "url": play_key,
            "header": {"User-Agent": UA,
                       "Referer": self.host() + "/"},
        }

    def _cached_vod(self, vid):
        c = self._cache_get(self._detail_cache, vid, TTL_DETAIL_OK)
        if c and c.get("list"):
            return c["list"][0]
        return None

    # ============================================================
    # 搜索 (聚合 + 模糊匹配)
    # ============================================================
    def _search_corpus(self, force=False):
        """
        F25: 全库并发扫描 (SEARCH_FAST_PAGES=SEARCH_PAGES=18), 无"首屏+后台补齐"概念.
        原因: FongMi 搜索结果列表是"一次性"的, 后台补齐的语料不会刷新已打开的搜索结果,
              必须首屏即全库, 用户才能搜到冷门剧.
        性能: ThreadPoolExecutor 并发 (3 排序 × 18 页 = 54 请求, 并发度 8), 冷启动约 2-3s.
              __init__ 预热线程已提前扫一次, 用户通常首次搜索命中缓存.
        返回 dict, key=vid, value=列表项 (已含 _material / _year).
        """
        now = time.time()
        with self._lock:
            if (not force and self._search_corpus_cache is not None
                    and now - self._search_corpus_time < TTL_SEARCH_CORPUS):
                return self._search_corpus_cache
            if force:
                self._search_corpus_cache = {}

        # 若 __init__ 预热线程仍在跑, 等它完成 (最多 30s); 否则触发新扫描
        with self._lock:
            active = self._search_warmup_task
            active_ok = self._search_warmup_ok

        if active is not None and active.is_alive() and active_ok:
            try:
                active.join(timeout=30.0)
            except Exception:
                pass
            with self._lock:
                return dict(self._search_corpus_cache or {})

        # 触发新扫描
        return self._search_corpus_scan()

    def _search_corpus_scan(self):
        """阻塞式全库并发扫描 (最多 30s), 返回 dict 快照.

        注意: 不在持锁时开新线程 —— _warmup_scan_one 内会再拿 self._lock 合并 collected,
        若主线程持锁不放, 新线程永远拿不到, RLock 跨线程也不通, 会死锁。
        因此把 body 直接内联到本方法 (单线程顺序执行, ThreadPoolExecutor 内部再并发 8)。
        """
        collected = {}
        try:
            tasks = [(sk, g) for sk in SEARCH_SORTS
                     for g in range(1, SEARCH_PAGES + 1)]
            with ThreadPoolExecutor(max_workers=8) as ex:
                futs = [ex.submit(self._warmup_scan_one, sk, g, collected)
                        for sk, g in tasks]
                for f in as_completed(futs):
                    try:
                        f.result(timeout=8)
                    except Exception:
                        pass
            with self._lock:
                self._search_corpus_cache = collected
                self._search_corpus_time = time.time()
                self._search_warmup_ok = True
                self._search_warmup_task = None
            return dict(collected)
        except Exception:
            with self._lock:
                self._search_warmup_ok = False
                self._search_warmup_task = None
            return dict(collected)

    def _search_corpus_scan_body(self):
        """__init__ 预热线程主体: 复用 _search_corpus_scan 的单线程扫描逻辑。

        (本方法只做入口包装, 实际扫描在 _search_corpus_scan 内联执行)
        """
        try:
            return self._search_corpus_scan()
        except Exception:
            with self._lock:
                self._search_warmup_ok = False
                self._search_warmup_task = None
            return {}

    def _warmup_scan_one(self, sort_key, group, collected):
        """并发扫描单页: 拉 API 后 merge 到 collected (加锁保证并发安全)."""
        try:
            lst = self._fetch_list(rows=SEARCH_ROWS,
                                   start_row=(group - 1) * SEARCH_ROWS,
                                   order_type=sort_key, is_vip="-1")
            if not lst:
                return
            with self._lock:
                for v in lst:
                    vid = v["vod_id"]
                    if vid not in collected:
                        collected[vid] = dict(v)
        except Exception:
            return

    @staticmethod
    def _normalize_name(name):
        return _NAME_NOISE.sub('', str(name or '')).lower()

    @staticmethod
    def _tokens(name):
        toks = [t for t in _TOKEN_SPLIT.split(str(name or '')) if t]
        return toks if toks else ([_NAME_NOISE.sub('', str(name or '')).lower()]
                                  if str(name or '') else [])

    def _match_score(self, kw, kw_norm, kw_tokens, kw_initials, title,
                     title_norm, title_tokens, title_initials):
        """多档评分: 全匹配 > 变体全等 > 变体包含 > 词匹配 > 缩写匹配 > 字符重叠"""
        best = 0
        if not kw_norm or not title_norm:
            return 0

        # 1. 完整匹配
        if kw_norm == title_norm:
            best = 100
        # 2. 变体全等 (去括号后缀)
        if kw_norm in title_tokens or title_norm in kw_tokens:
            best = max(best, 85)
        # 3. 变体包含
        if kw_norm and (kw_norm in title_norm):
            best = max(best, 65)
        # 4. token 匹配
        if kw_tokens and title_tokens:
            if all(t in title_tokens for t in kw_tokens):
                best = max(best, 55)
            elif any(t in title_tokens for t in kw_tokens):
                best = max(best, 40)
        # 5. 首字母缩写匹配 (TWL -> 唐宫夜宴/天王...)
        if kw_initials and title_initials and len(kw_initials) >= 2:
            if kw_initials in title_initials:
                best = max(best, 30)
        # 6. 字符重叠兜底
        if best == 0 and len(kw_norm) >= 2:
            tset = set(title_norm)
            overlap = sum(1 for c in set(kw_norm) if c in tset)
            if overlap >= max(2, len(set(kw_norm)) * 0.6):
                best = max(best, min(20, overlap * 3))
        return best

    def searchContent(self, key, quick=False, pg="1"):
        """FongMi TV 规范: 必须回传 page/pagecount/limit/total; 无数据时 pagecount=1 避免反复翻页。"""
        if not key:
            return {"list": [], "page": 1, "pagecount": 1,
                    "limit": SEARCH_MAX_RESULTS, "total": 0}
        kw = str(key).strip()
        if not kw:
            return {"list": [], "page": 1, "pagecount": 1,
                    "limit": SEARCH_MAX_RESULTS, "total": 0}
        try:
            page = max(1, int(pg))
        except (TypeError, ValueError):
            page = 1
        ckey = "__search__|%s" % kw
        cached = self._cache_get(self._search_cache, ckey, TTL_SEARCH)
        if cached is not None:
            total = len(cached)
            limit = SEARCH_MAX_RESULTS
            pagecount = max(1, (total + limit - 1) // limit)
            start = (page - 1) * limit
            return {
                "list": cached[start:start + limit],
                "page": page, "pagecount": pagecount,
                "limit": limit, "total": total,
            }

        kw_norm = self._normalize_name(kw)
        kw_tokens = [t.lower() for t in self._tokens(kw)]
        kw_initials = ''.join(t[0] for t in kw_tokens if t).lower()

        corpus = self._search_corpus()

        matched = []
        for item in corpus.values():
            title = item["vod_name"]
            title_norm = self._normalize_name(title)
            title_tokens = [t.lower() for t in self._tokens(title)]
            title_initials = ''.join(
                t[0] for t in title_tokens if t).lower()
            score = self._match_score(kw, kw_norm, kw_tokens, kw_initials,
                                      title, title_norm, title_tokens,
                                      title_initials)
            if score == 0:
                continue
            # 长度惩罚 (同名短名优先)
            score -= min(5, max(0, len(title) - len(kw)))
            matched.append((score, title, item))

        matched.sort(key=lambda x: (-x[0], x[1]))
        result = [it[2] for it in matched[:SEARCH_MAX_RESULTS]]
        for it in result:
            it.pop("_material", None)
            it.pop("_year", None)

        if result:
            self._cache_set(self._search_cache, ckey, result, TTL_SEARCH)
        total = len(result)
        limit = SEARCH_MAX_RESULTS
        pagecount = max(1, (total + limit - 1) // limit)
        start = (page - 1) * limit
        return {
            "list": result[start:start + limit],
            "page": page, "pagecount": pagecount,
            "limit": limit, "total": total,
        }


# ============================================================
# 分类过滤逻辑 (按官网 5 大类)
# ============================================================
# 埋堆堆后端 materialName 是逗号分隔多标签字符串, 含综艺/动漫/纪录片/真人秀/
# 访谈/美食/游戏娱乐/旅行/音乐/大型晚会/资讯/儿童/剧情/警匪/...等数十个子类;
# vodType=1 且 totalNum=1 是电视电影 (单集). 后端 classify/word/search 接口
# 不接受 vodType/material 作为查询参数, 只能在客户端本地按规则分类过滤.
#
# 分类规则 (按官网顶部 5 类):
#   剧集    : 默认电视剧类 (不命中其他 4 类的内容, 主要是 vodType=0 剧情/警匪/古装/...)
#   电影    : vodType == 1 且 totalNum == 1 (单集电视电影/电影)
#   综艺    : material 含「综艺/真人秀/访谈/美食/游戏娱乐/旅行/音乐/大型晚会/资讯/儿童/其他」
#   动画    : material 含「动漫」或「儿童」(动画类)
#   纪录片  : material 含「纪录片」
# 优先级: 纪录片 > 动画 > 电影 > 综艺 > 剧集
# (纪录片/动画标签直接命中最准; 电影按 vodType=1; 综艺聚合所有娱乐类; 剩余归剧集)

VARIETY_LABELS = {
    "综艺", "真人秀", "访谈", "美食", "游戏娱乐", "旅行",
    "音乐", "大型晚会", "资讯", "儿童", "其他",
}

CATEGORIES = ("tv", "movie", "variety", "anime", "documentary")

CATEGORY_NAME = {
    "tv": "剧集",
    "movie": "电影",
    "variety": "综艺",
    "anime": "动画",
    "documentary": "纪录片",
}

_ANIME_NAME_RE = re.compile(r'(动画|动漫|卡通)')

def _match_category(vod, tid):
    """判断 vod 是否属于 tid 分类. 返回 bool."""
    mat_raw = vod.get("_material") or ""
    mats = set(x.strip() for x in str(mat_raw).split(",") if x.strip())
    vt = vod.get("_vod_type") or 0
    tn = vod.get("_total_num") or 0
    name = str(vod.get("vod_name") or "")

    is_doc = "纪录片" in mats
    # 动画: 带"动漫"标签, 或儿童标签且片名含动画/动漫/卡通关键字
    is_anime = ("动漫" in mats) or (("儿童" in mats) and bool(_ANIME_NAME_RE.search(name)))
    is_movie = (vt == 1 and tn == 1)
    # 综艺: 聚合娱乐类 (儿童非动画也归入综艺)
    is_var = bool(mats & VARIETY_LABELS)

    if tid == "documentary":
        return is_doc
    if tid == "anime":
        return is_anime
    if tid == "movie":
        return is_movie
    if tid == "variety":
        return is_var and (not is_doc) and (not is_anime)
    if tid == "tv":
        return (not is_doc) and (not is_anime) and (not is_movie) and (not is_var)
    return False


# ============================================================
# 一级分类表 (官网 5 类: 剧集 / 电影 / 综艺 / 动画 / 纪录片)
# ============================================================
ALL_CLASSES = [
    {"type_id": "tv",          "type_name": "剧集"},
    {"type_id": "movie",       "type_name": "电影"},
    {"type_id": "variety",     "type_name": "综艺"},
    {"type_id": "anime",       "type_name": "动画"},
    {"type_id": "documentary", "type_name": "纪录片"},
]

# 每个一级分类无预设筛选参数 (isvip/order 都由二级筛选器控制);
# 分类归属由 _match_category 在本地判定.
CLASS_PRESET = {c["type_id"]: {} for c in ALL_CLASSES}

VALID_TIDS = {c["type_id"] for c in ALL_CLASSES}


# ============================================================
# 本地调试 (python mddcloud.py)
# ============================================================
if __name__ == "__main__":
    import sys as _sys

    def p(obj, cut=500):
        s = json.dumps(obj, ensure_ascii=False, indent=1)
        print(s[:cut] + ("..." if len(s) > cut else ""))

    sp = Spider()
    sp.init("")

    print("\n===== 域名跟踪 =====")
    print("当前主站:", sp.host())

    print("\n===== homeContent (5 大分类) =====")
    home = sp.homeContent(filter=True)
    print("一级分类:", [(c["type_id"], c["type_name"]) for c in home["class"]])
    for tid, name in [(c["type_id"], c["type_name"]) for c in home["class"]]:
        cat = sp.categoryContent(tid, 1, True, {})
        print(f"  {name}: total={cat['total']} pagecount={cat['pagecount']}"
              f"  前3: {[v['vod_name'] for v in cat['list'][:3]]}")

    print("\n===== detailContent (剧集首页第一条) =====")
    cat_tv = sp.categoryContent("tv", 1, True, {})
    if cat_tv["list"]:
        vid = cat_tv["list"][0]["vod_id"]
        d = sp.detailContent([vid])
        if d["list"]:
            dv = d["list"][0]
            print("片名:", dv["vod_name"])
            print("年份:", dv["vod_year"], " 地区:", dv["vod_area"])
            print("主演:", dv["vod_actor"][:60])
            print("备注:", dv["vod_remarks"])
            eps = dv["vod_play_url"].split("#")
            print("集数:", len(eps), " 首集key:", eps[0][:80])

    print("\n===== searchContent(无穷之路) =====")
    s = sp.searchContent("无穷之路")
    print("结果:", [v["vod_name"] for v in s["list"][:5]])

    print("\n===== searchContent(奖门人) =====")
    s = sp.searchContent("奖门人")
    print("结果:", [v["vod_name"] for v in s["list"][:5]])
