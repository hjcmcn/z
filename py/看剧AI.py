# coding=utf-8
"""
目标站: 看剧AI (kanju.ai)
模板: 影视聚合搜索 / 爬虫播放
站点类型: 综合影视
核心逻辑: 调用 HMAC-SHA256 签名 JSON API, 提取视频信息和真实播放链接
支持: 首页, 分类, 搜索, 详情, 播放
"""
import re
import sys
import json
import time
import hmac
import hashlib
import os
import urllib.parse

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    def init(self, extend=""):
        self.site_url = "https://kanju.ai"
        # API 签名密钥 (从前端 JS 提取)
        self.api_secret = "557d0e4ae929f438da6bd84412374e6086b8af09b3fed54bf22601d5bf8c54a0"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': self.site_url + "/",
            'Origin': self.site_url,
        }
        self.default_pic = "https://pic.rmb.bdstatic.com/bjh/user/default.png"
        # 分类映射: content_kind -> 中文名
        self.categories = {
            "movie": "电影",
            "series": "电视剧",
            "anime": "动漫",
            "variety": "综艺",
            "short_drama": "短剧",
        }

    # ========== 工具方法 ==========

    def _sign_headers(self, method, path_with_search):
        """生成 API 签名请求头

        签名串格式: {METHOD}\n{pathname}{search}\n{timestamp}\n{nonce}
        算法: HMAC-SHA256(密钥, 签名串) -> hex
        """
        ts = str(int(time.time() * 1000))
        nonce = os.urandom(16).hex()
        msg = "{0}\n{1}\n{2}\n{3}".format(method, path_with_search, ts, nonce)
        sig = hmac.new(self.api_secret.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()
        return {
            **self.headers,
            'x-ai-movie-timestamp': ts,
            'x-ai-movie-nonce': nonce,
            'x-ai-movie-signature': sig,
        }

    def _api_get(self, path):
        """调用签名 GET API 并返回解析后的 JSON 字典"""
        url = self.site_url + path
        headers = self._sign_headers("GET", path)
        try:
            resp = self.fetch(url, headers=headers)
            if not resp:
                return {}
            return json.loads(resp.text)
        except Exception:
            return {}

    def _api_post(self, path, payload):
        """调用签名 POST API 并返回解析后的 JSON 字典"""
        url = self.site_url + path
        headers = self._sign_headers("POST", path)
        headers['Content-Type'] = 'application/json'
        try:
            resp = self.fetch(url, headers=headers, data=json.dumps(payload, ensure_ascii=False))
            if not resp:
                return {}
            return json.loads(resp.text)
        except Exception:
            return {}

    def _parse_card(self, card):
        """将 API 卡片对象转换为 vod 字典 (列表页通用)"""
        vid = card.get("id", "") or ""
        name = card.get("title", "") or ""
        pic = card.get("poster_url", "") or ""
        remark = card.get("remarks", "") or ""
        year = card.get("year", "")
        if year:
            year = str(year)
        else:
            year = ""
        area = card.get("area", "") or ""
        genres = card.get("genres", [])
        type_name = " / ".join(genres[:3]) if genres else ""
        return {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic if pic else self.default_pic,
            "vod_remarks": remark,
            "vod_year": year,
            "vod_area": area,
            "vod_type": type_name,
        }

    def _calc_pagecount(self, pag, page, limit):
        """根据分页信息计算总页数"""
        total = pag.get("total", 0)
        if total and limit:
            return (total + limit - 1) // limit
        if pag.get("has_more"):
            return page + 1
        return page

    def _is_valid_video_url(self, url):
        """过滤掉明显不是视频直链的地址（如封面图片）"""
        if not url:
            return False
        url_lower = url.lower()
        for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"]:
            if ext in url_lower:
                return False
        return True

    # ========== 首页 ==========

    def homeContent(self, filter):
        """获取首页内容: 分类列表 + 推荐视频"""
        categories = [{"type_id": k, "type_name": v} for k, v in self.categories.items()]

        data = self._api_get("/v1/feed/home")
        videos = []
        seen = set()
        for sec in data.get("sections", []):
            for card in sec.get("cards", []):
                vid = card.get("id", "")
                if not vid or vid in seen:
                    continue
                seen.add(vid)
                videos.append(self._parse_card(card))

        return {"class": categories, "list": videos[:30], "filters": {}}

    def homeVideoContent(self):
        """获取首页推荐视频列表"""
        data = self._api_get("/v1/feed/home")
        videos = []
        seen = set()
        for sec in data.get("sections", []):
            for card in sec.get("cards", []):
                vid = card.get("id", "")
                if not vid or vid in seen:
                    continue
                seen.add(vid)
                videos.append(self._parse_card(card))
        return {"list": videos[:30]}

    # ========== 分类 ==========

    def categoryContent(self, tid, pg, filter, extend):
        """获取分类列表

        tid: content_kind (movie/series/anime/variety/short_drama)
        pg:  页码
        """
        page = int(pg) if pg else 1
        limit = 30
        path = "/v1/browse/catalog?kind={0}&page={1}&limit={2}".format(tid, page, limit)
        data = self._api_get(path)

        cards = data.get("cards", []) or []
        videos = [self._parse_card(c) for c in cards if c.get("id")]

        pag = data.get("pagination", {}) or {}
        total = pag.get("total", 0)
        if not total:
            total = len(videos)
        pagecount = self._calc_pagecount(pag, page, limit)

        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": limit,
            "total": total,
        }

    # ========== 搜索 ==========

    def searchContent(self, key, quick, pg="1"):
        """搜索内容

        key: 搜索关键词
        pg:  页码
        """
        page = int(pg) if pg else 1
        limit = 30
        encoded = urllib.parse.quote(key)
        path = "/v1/browse/catalog?q={0}&page={1}&limit={2}".format(encoded, page, limit)
        data = self._api_get(path)

        cards = data.get("cards", []) or []
        videos = [self._parse_card(c) for c in cards if c.get("id")]

        pag = data.get("pagination", {}) or {}
        total = pag.get("total", 0)
        if not total:
            total = len(videos)
        pagecount = self._calc_pagecount(pag, page, limit)

        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": limit,
            "total": total,
        }

    # ========== 详情 ==========

    def detailContent(self, ids):
        """获取视频详情 (含播放选集)

        ids[0]: 卡片 ID (av_ 开头的长字符串)
        详情接口 /v1/catalog/{id} 返回完整信息
        剧集列表现在只包含 token, 真实播放地址需在 playerContent 中通过 resolve API 换取
        """
        if not ids:
            return {"list": []}

        vid = ids[0]
        data = self._api_get("/v1/catalog/{0}".format(vid))
        if not data or "id" not in data:
            return {"list": []}

        # 基本信息
        title = data.get("title", "") or ""
        pic = data.get("poster_url", "") or self.default_pic
        content = data.get("description", "") or ""
        actors = data.get("actors", [])
        actor = " / ".join(actors[:20]) if actors else ""
        directors = data.get("directors", [])
        director = " / ".join(directors[:10]) if directors else ""
        year = str(data.get("year", "")) if data.get("year") else ""
        area = data.get("area", "") or ""
        genres = data.get("genres", [])
        type_name = " / ".join(genres[:5]) if genres else ""

        # 播放源与选集
        play_from = []
        play_url = []

        def extract_episodes(episodes, provider_id=""):
            """从 episodes 列表中提取 title$token@@provider_id 格式"""
            ep_list = []
            suffix = "@@{0}".format(provider_id) if provider_id else ""
            for ep in episodes:
                ep_title = ep.get("title", "") or ""
                if not ep_title:
                    num = ep.get("number")
                    if num is not None:
                        ep_title = "第{0}集".format(num)
                    else:
                        ep_title = "播放"
                token = ep.get("token", "")
                if not token:
                    continue
                ep_list.append("{0}${1}{2}".format(ep_title, token, suffix))
            return ep_list

        # 优先使用详情页自带的 episodes, 没有则调用 episodes 接口
        episodes = data.get("episodes", [])
        if not episodes:
            ep_data = self._api_get("/v1/catalog/{0}/episodes".format(vid))
            episodes = ep_data.get("episodes", [])

        if episodes:
            # 用第一集 token 预拉取线路列表, 同一部剧各集线路基本一致
            first_token = ""
            for ep in episodes:
                if ep.get("token"):
                    first_token = ep.get("token")
                    break

            valid_lines = []
            if first_token:
                resolve_data = self._api_get("/v1/playback/resolve/{0}".format(first_token))
                line_options = resolve_data.get("line_options", []) or []
                # 过滤掉没有 url 的线路, 并按 provider_id 去重
                seen_providers = set()
                for opt in line_options:
                    if not opt.get("url"):
                        continue
                    pid = opt.get("provider_id")
                    if pid in seen_providers:
                        continue
                    seen_providers.add(pid)
                    valid_lines.append(opt)

                # 排序: 官方 resolve_ticket 线路优先, 其次资源类 m3u8 直链, 最后按 preference_weight 降序
                def line_rank(opt):
                    kind = opt.get("url_kind", "")
                    name = (opt.get("provider_name") or "").lower()
                    if kind == "resolve_ticket":
                        return 2
                    if "资源" in name:
                        return 0
                    return 1

                valid_lines.sort(key=lambda x: (-line_rank(x), -x.get("preference_weight", 0)))
                # 限制数量, 避免播放源列表过长
                valid_lines = valid_lines[:12]

            if valid_lines:
                for line in valid_lines:
                    provider_name = line.get("provider_name") or line.get("label") or "默认线路"
                    provider_id = line.get("provider_id") or ""
                    play_from.append(provider_name)
                    ep_list = extract_episodes(episodes, provider_id)
                    if ep_list:
                        play_url.append("#".join(ep_list))

            if not play_from:
                play_from.append("默认线路")
                ep_list = extract_episodes(episodes)
                if ep_list:
                    play_url.append("#".join(ep_list))

        # 兜底
        if not play_from:
            play_from.append("默认线路")
            play_url.append("播放${0}/v1/catalog/{1}".format(self.site_url, vid))

        result = [{
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_year": year,
            "vod_area": area,
            "vod_type": type_name,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]
        return {"list": result}

    # ========== 播放 ==========

    def playerContent(self, flag, id, vipFlags):
        """获取播放链接

        id 格式: ep_title$episode_token@@provider_id (从 vod_play_url 拆分而来)
        flag: 当前选中的播放源名称 (对应 provider_name)
        逻辑:
          1) 从 id 中拆出 token 与用户指定的 provider_id
          2) GET /v1/playback/resolve/{token} 获取所有线路
          3) 优先使用指定线路; 若无效则按 preference_weight 自动 fallback
          4) 对 resolve_ticket 类型调用 resolve-line 换取真实地址
          5) 对 m3u8/mp4 类资源线路直接返回直链
        """
        # 拆分出真实 token 与可选的指定线路
        raw_id = id
        if "$" in raw_id:
            raw_id = raw_id.split("$")[-1]
        raw_id = raw_id.strip()

        token = raw_id
        selected_provider = ""
        if "@@" in token:
            token, selected_provider = token.split("@@", 1)
        token = token.strip()

        if not token:
            return {"parse": 1, "url": id, "header": self.headers}

        # 如果已经是直链 (资源类线路 detailContent 已直接写入 url)
        if token.startswith("http") and ('.m3u8' in token or '.mp4' in token):
            return {
                "parse": 0,
                "url": token,
                "header": {
                    'User-Agent': self.headers['User-Agent'],
                    'Referer': self.site_url + "/",
                }
            }

        # 非 token 则直接嗅探
        if not token.startswith("YJ-"):
            return {"parse": 1, "url": token, "header": self.headers}

        try:
            path = "/v1/playback/resolve/{0}".format(urllib.parse.quote(token))
            resolve_data = self._api_get(path)
            line_options = resolve_data.get("line_options", [])
            if not line_options:
                return {"parse": 1, "url": id, "header": self.headers}
        except Exception:
            return {"parse": 1, "url": id, "header": self.headers}

        # 排序: 用户选中的线路放最前, 其余按权重降序作为 fallback 候选
        def is_selected(opt):
            if selected_provider and opt.get("provider_id") == selected_provider:
                return True
            if selected_provider and opt.get("play_from") == selected_provider:
                return True
            if flag and opt.get("provider_name") == flag:
                return True
            return False

        sorted_lines = sorted(
            line_options,
            key=lambda x: (not is_selected(x), -x.get("preference_weight", 0))
        )

        # 遍历尝试, 直到拿到可用真实地址
        for line in sorted_lines:
            raw_url = line.get("url", "")
            if not raw_url:
                continue
            url_kind = line.get("url_kind", "")

            # 资源类直链 (url_kind 为 m3u8 等)
            if url_kind in ["m3u8", "mp4", "hls"] and raw_url.startswith("http"):
                if self._is_valid_video_url(raw_url):
                    return {
                        "parse": 0,
                        "url": raw_url,
                        "header": {
                            'User-Agent': self.headers['User-Agent'],
                            'Referer': self.site_url + "/",
                        }
                    }

            # resolve_ticket 类型: 换取真实地址
            if url_kind == "resolve_ticket":
                ticket = raw_url.replace("resolve://", "")
                if not ticket:
                    continue
                payload = {
                    "ticket": ticket,
                    "line": line.get("playback_source_id", ""),
                    "provider_id": line.get("provider_id", ""),
                    "play_from": line.get("play_from", ""),
                }
                try:
                    line_data = self._api_post("/v1/playback/resolve-line", payload)
                    line_info = line_data.get("line", {})
                    real_url = line_info.get("url", "")
                except Exception:
                    continue
                if real_url and self._is_valid_video_url(real_url):
                    return {
                        "parse": 0,
                        "url": real_url,
                        "header": {
                            'User-Agent': self.headers['User-Agent'],
                            'Referer': self.site_url + "/",
                        }
                    }

        # 兜底: 所有线路均失败则回到站点播放页 webview 嗅探
        return {
            "parse": 1,
            "url": "{0}/yj/{1}".format(self.site_url, token.replace("YJ-", "")),
            "header": self.headers
        }
