# -*- coding: utf-8 -*-
"""
Anyreel (anyreel.app) 站源
基于 Next.js RSC + /api/home-feed API 采集
视频播放使用腾讯云 VOD (Tencent Cloud VOD) with pSign
"""
import json
import re
import base64
from urllib.parse import urljoin, quote

try:
    import requests
except Exception:
    requests = None

from base.spider import Spider


class Spider(Spider):
    name = "Anyreel"
    host = "https://www.anyreel.app"
    api = host + "/api/home-feed"
    page_size = 20
    lang = "zh"

    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36",
        "Referer": host + "/zh",
        "Accept": "application/json, text/html, */*",
    }

    # 分类标签 (tagId, tagName) — 英文名与 API 返回的 tagName 一致
    TAGS = [
        ("68ca5582eb2cc9e67988bd17", "Forbidden Love"),
        ("6810b21c382650ff8b40a80a", "Passion"),
        ("68ca5590eb2cc9e67988bd18", "Mafia"),
        ("68ca5645eb2cc9e67988bd1e", "Contract Lover"),
        ("667e6ca47d72def17769e11b", "Sweet Love"),
        ("667e6ba97d72def17769e11a", "Bad girl"),
        ("667e6b74ba23222bbc4985ad", "CEO"),
        ("667e6b7fc43bdcf54521d746", "Millionaire"),
        ("667e6b9dba23222bbc4985af", "Genius Baby"),
        ("667e6cc9ba23222bbc4985b1", "Subtitute"),
        ("667e6cdb7d72def17769e11c", "Fantasy"),
        ("667e6cfa7d72def17769e11d", "Divorced"),
        ("667e6d0c7d72def17769e11e", "Motherhood"),
        ("667e72adc43bdcf54521d74d", "Betrayal"),
        ("670a4a33b04ef4cffc1116f3", "Urban"),
        ("670a4a575e713c2d0938b3c5", "Family"),
        ("67c6a3c91178a22c7606959a", "Bitter Love"),
        ("67c6a416ab40913d4c8d4b1e", "Twisted Fate"),
        ("67ea4f984d21a3781be60793", "Midlife"),
        ("67765e8c27752850c04b339c", "Original Drama"),
        ("680a09f34468edd8e5254788", "Mystery"),
        ("6810b157374695779a6b6a17", "Military"),
        ("681820dccd61c01ab7738f5e", "Flash Marriage"),
        ("684d80e8bf295ebef7929cd3", "Vampire"),
        ("68521d45e91044f094bd07e8", "Boys' Love"),
        ("6878bbddb51ad3fc89b3d0f9", "Crime"),
        ("68c3d59d203fc00dafb0e2a0", "Love Triangle"),
        ("68c3d6898e365b8e7f22ca22", "Weak to Strong"),
        ("68c3d7d28e365b8e7f22ca23", "Love at First Sight"),
        ("68c3d9888e365b8e7f22ca24", "Career Woman"),
        ("68c3d9a1d91abf8421261090", "Fated Love"),
        ("68c3da94d91abf8421261091", "Wife Chasing"),
        ("68ca54d3720d019589044058", "BG"),
        ("68ca54e3720d019589044059", "Family Intrigue"),
        ("68ca5512eb2cc9e67988bd14", "Second Chance"),
        ("68ca5534720d01958904405b", "Mistaken Identity"),
        ("68ca5552720d01958904405c", "Werewolf"),
        ("68ca5606eb2cc9e67988bd1c", "One Night Stand"),
        ("68ca5615eb2cc9e67988bd1d", "Independent Woman"),
        ("68ca5654720d019589044060", "Single Mom"),
        ("68e9f4065a5f7b6cb472bf29", "campus Romance"),
        ("68e9f423933fd23453602eb5", "Thriller"),
        ("68f0c5f93346ff671abd59c9", "Enemies Become Lovers"),
        ("68f6e7e086455c3551693d07", "All-Too-Late"),
        ("6900612a1c7cd4d16ef15eb4", "Rebirth"),
        ("69e060c3e81259c28a857a3c", "Forced Love"),
        ("69f082d50558562585595f03", "Bully"),
        ("66a073482e1c0d9f9a16f8bf", "Alternative History"),
        ("66b20e54b31420169f57e375", "Village"),
        ("67a96c2c753fae18957d751d", "Abuse"),
        ("6a5091c6eb7659e6c0853b24", "Billionaire"),
        ("6a5091daeb7659e6c0853b25", "Elite"),
        ("6a509200eb7659e6c0853b27", "Baby"),
        ("6a50921beb7659e6c0853b28", "Young Adult"),
        ("6a50924eeb7659e6c0853b2a", "Doctor"),
        ("6a509261eb7659e6c0853b2b", "Master"),
        ("6a50927deb7659e6c0853b2d", "Celebrity"),
        ("6a5092aceb7659e6c0853b2e", "Royalty"),
        ("6a5092bfeb7659e6c0853b2f", "Police"),
        ("6a50932aeb7659e6c0853b34", "Fantasy Deity"),
        ("6a50936beb7659e6c0853b36", "Teacher"),
        ("6a509388eb7659e6c0853b37", "Soldier"),
        ("6a509396eb7659e6c0853b38", "Dragon"),
        ("6a5093adeb7659e6c0853b39", "Revenge"),
        ("6a5093d5eb7659e6c0853b3b", "Powerful Heroine"),
        ("6a5093e7eb7659e6c0853b3c", "Hidden Identity"),
        ("6a5093fdeb7659e6c0853b3d", "Erotic"),
        ("6a50940aeb7659e6c0853b3e", "Family Saga"),
        ("6a509461eb7659e6c0853b41", "Comeback"),
        ("6a509492eb7659e6c0853b43", "Win Her Back"),
        ("6a5094a8eb7659e6c0853b44", "Sweet Romance"),
        ("6a5094c6eb7659e6c0853b45", "One-Night Stand"),
        ("6a5094f5eb7659e6c0853b48", "Conspiracy"),
        ("6a509509eb7659e6c0853b49", "Office Romance"),
        ("6a50951feb7659e6c0853b4a", "Reunion"),
        ("6a50953deb7659e6c0853b4b", "Possessive Romance"),
        ("6a509597eb7659e6c0853b4e", "Fated"),
        ("6a5095ffeb7659e6c0853b51", "Love After Marriage"),
        ("6a509657eb7659e6c0853b55", "Time Travel"),
        ("6a509670eb7659e6c0853b56", "Enemies to Lovers"),
        ("6a50969deb7659e6c0853b58", "Age Gap"),
        ("6a5096dfeb7659e6c0853b5b", "BL"),
        ("68ca556eeb2cc9e67988bd16", "Age-Gap Love"),
        ("6a55a4ffd1199204374de39b", "Counterattack"),
    ]

    def __init__(self):
        self.session = requests.Session() if requests else None
        if self.session:
            self.session.headers.update(self.headers)
        self._all_series = None

    def getName(self):
        return self.name

    def init(self, extend=""):
        if isinstance(extend, dict):
            data = extend
        else:
            try:
                data = json.loads(extend) if extend else {}
            except Exception:
                data = {}
        if isinstance(data, dict):
            self.host = str(data.get("host") or self.host).rstrip("/")
            self.lang = str(data.get("lang") or self.lang)
            self.api = self.host + "/api/home-feed"

    # ========== 工具方法 ==========

    @staticmethod
    def _page(pg):
        try:
            return max(1, int(pg))
        except Exception:
            return 1

    @staticmethod
    def _response_text(response):
        if response is None:
            return ""
        if isinstance(response, str):
            return response
        if isinstance(response, bytes):
            return response.decode("utf-8", "ignore")
        if isinstance(response, dict):
            for key in ("body", "text", "content", "data"):
                value = response.get(key)
                if isinstance(value, bytes):
                    return value.decode("utf-8", "ignore")
                if isinstance(value, str):
                    return value
            return json.dumps(response, ensure_ascii=True)
        text = getattr(response, "text", None)
        if isinstance(text, str):
            return text
        content = getattr(response, "content", None)
        if isinstance(content, bytes):
            return content.decode("utf-8", "ignore")
        return ""

    def _get(self, url, is_json=False):
        """GET 请求，多通道容错"""
        responses = []
        if self.session:
            try:
                responses.append(self.session.get(url, timeout=15))
            except Exception:
                pass
        fetch_fn = getattr(self, "fetch", None)
        if callable(fetch_fn):
            try:
                responses.append(fetch_fn(url, headers=self.headers))
            except Exception:
                pass
        post_fn = getattr(self, "post", None)
        if callable(post_fn):
            try:
                responses.append(post_fn(url, headers=self.headers))
            except Exception:
                pass
        for response in responses:
            try:
                text = self._response_text(response) or ""
                if not text:
                    continue
                if is_json:
                    try:
                        return json.loads(text)
                    except Exception:
                        continue
                if len(text) > 200:
                    return text
            except Exception:
                continue
        try:
            from urllib.request import Request, urlopen
            req = Request(url, headers=self.headers)
            raw = urlopen(req, timeout=15).read()
            text = raw.decode("utf-8", "ignore")
            if is_json:
                return json.loads(text)
            return text
        except Exception:
            return {} if is_json else ""

    def _full_url(self, path):
        path = str(path or "").strip()
        if not path:
            return ""
        if path.startswith("http"):
            return path
        if not path.startswith("/"):
            path = "/" + path
        return urljoin(self.host + "/", path)

    def _pic(self, url):
        url = str(url or "").strip()
        if not url:
            return ""
        if url.startswith("http"):
            return url
        if url.startswith("//"):
            return "https:" + url
        return self._full_url(url)

    @staticmethod
    def _strip_tags(text):
        return re.sub(r"<[^>]+>", "", str(text or "")).strip()

    @staticmethod
    def _extract_rsc(html):
        """提取 Next.js __next_f RSC 数据块"""
        chunks = []
        for m in re.finditer(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html, re.S):
            raw = m.group(1)
            try:
                text = raw.encode("utf-8").decode("unicode_escape")
            except Exception:
                text = raw.replace('\\"', '"').replace("\\\\", "\\")
            chunks.append(text)
        return "\n".join(chunks)

    # ========== Home Feed 缓存 ==========

    def _load_feed(self):
        """加载并缓存 home-feed 数据，返回所有 series 列表"""
        if self._all_series is not None:
            return self._all_series
        data = self._get(self.api + "?lang=" + self.lang, is_json=True)
        if not data:
            return []
        feed = data.get("data") or data
        sections = feed.get("sectionConfigs") or []
        all_series = []
        seen_ids = set()
        for section in sections:
            for sr in section.get("series") or []:
                sid = str(sr.get("seriesShortId") or "")
                if not sid or sid in seen_ids:
                    continue
                seen_ids.add(sid)
                tags = []
                for tag in (sr.get("tags") or []) + (sr.get("displayTags") or []):
                    tag_name = tag.get("tagName") or tag.get("nameEn") or ""
                    if tag_name and tag_name not in tags:
                        tags.append(tag_name)
                all_series.append({
                    "vod_id": sid,
                    "vod_name": str(sr.get("name") or ""),
                    "vod_pic": self._pic(sr.get("coverImageUrl")),
                    "vod_remarks": "全{}集".format(sr.get("totalEpisodes") or ""),
                    "vod_content": str(sr.get("synopsis") or ""),
                    "vod_tag": ",".join(tags),
                    "_tags": tags,
                    "_total_eps": int(sr.get("totalEpisodes") or 0),
                })
        self._all_series = all_series
        return all_series

    # ========== 标准接口 ==========

    def homeContent(self, filter=False):
        classes = [{"type_id": tid, "type_name": name} for tid, name in self.TAGS]
        filters = {}
        for tid, _ in self.TAGS:
            filters[tid] = []
        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        series = self._load_feed()
        result = []
        for sr in series:
            result.append({
                "vod_id": sr["vod_id"],
                "vod_name": sr["vod_name"],
                "vod_pic": sr["vod_pic"],
                "vod_remarks": sr["vod_remarks"],
            })
        return {"list": result}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        page = self._page(pg)
        all_series = self._load_feed()
        # tid 是 tagId，按标签名匹配
        tag_name = ""
        for t_id, t_name in self.TAGS:
            if t_id == str(tid):
                tag_name = t_name
                break
        if tag_name:
            filtered = [s for s in all_series if tag_name in s.get("_tags", [])]
        else:
            filtered = all_series
        start = (page - 1) * self.page_size
        end = start + self.page_size
        page_list = filtered[start:end]
        total = len(filtered)
        pagecount = max(1, (total + self.page_size - 1) // self.page_size)
        result = []
        for sr in page_list:
            result.append({
                "vod_id": sr["vod_id"],
                "vod_name": sr["vod_name"],
                "vod_pic": sr["vod_pic"],
                "vod_remarks": sr["vod_remarks"],
            })
        return {
            "list": result,
            "page": page,
            "pagecount": pagecount,
            "limit": self.page_size,
            "total": total,
        }

    def detailContent(self, ids):
        vod_id = ids[0] if isinstance(ids, list) and ids else ids
        vod_id = str(vod_id or "")
        if not vod_id:
            return {"list": []}

        # 尝试从 home-feed 获取基本信息
        all_series = self._load_feed()
        feed_info = None
        for sr in all_series:
            if sr["vod_id"] == vod_id:
                feed_info = sr
                break

        # 抓取详情页
        url = self._full_url("/" + self.lang + "/movie/" + vod_id)
        html = self._get(url)

        # 提取 RSC 数据
        rsc = self._extract_rsc(html) if html else ""

        # 提取标题 — 优先从 feed_info（API 数据），其次 JSON-LD，再 HTML meta
        name = ""
        if feed_info:
            name = feed_info["vod_name"]
        if not name:
            # 从 JSON-LD 提取 TVSeries name
            for m_ld in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S):
                try:
                    ld = json.loads(m_ld.group(1).strip())
                    candidates = ld if isinstance(ld, list) else [ld]
                    for obj in candidates:
                        if isinstance(obj, dict):
                            graph = obj.get("@graph") or []
                            for node in graph:
                                if isinstance(node, dict) and node.get("@type") in ("TVSeries", "Movie"):
                                    name = node.get("name") or ""
                                    if name:
                                        break
                            if not name and obj.get("@type") in ("TVSeries", "Movie"):
                                name = obj.get("name") or ""
                            if name:
                                break
                except Exception:
                    continue
                if name:
                    break
        if not name:
            # og:title — 去除中文模板前后缀
            m = re.search(r'<meta property="og:title" content="([^"]+)"', html)
            if m:
                raw = m.group(1).strip()
                # 去掉 " – Anyreel" 后缀
                raw = re.split(r'\s*[–\-]\s*Anyreel\s*$', raw)[0].strip()
                # 去掉中文模板前后缀
                raw = re.sub(r'^免费在线观看\s*', '', raw)
                raw = re.sub(r'\s*全集高清短剧\s*$', '', raw)
                raw = re.sub(r'\s*–\s*Anyreel$', '', raw)
                name = raw.strip()
        if not name:
            m = re.search(r'<title>([^<]+)</title>', html)
            if m:
                raw = m.group(1).strip()
                raw = re.split(r'\s*[–\-]\s*Anyreel\s*$', raw)[0].strip()
                raw = re.sub(r'^免费在线观看\s*', '', raw)
                raw = re.sub(r'\s*全集高清短剧\s*$', '', raw)
                name = raw.strip()

        # 提取封面图 — 优先从 feed_info（API 数据），其次 RSC/HTML
        pic = ""
        if feed_info:
            pic = feed_info["vod_pic"]
        if not pic:
            m = re.search(r'"coverImageUrl":"([^"]+)"', rsc)
            if m:
                pic = m.group(1)
        if not pic:
            m = re.search(r'<meta property="og:image" content="([^"]+)"', html)
            if m:
                pic = m.group(1)
        pic = self._pic(pic)

        # 提取简介 — 优先从 feed_info（API 数据更干净）
        content = ""
        if feed_info:
            content = feed_info["vod_content"]
        if not content:
            m = re.search(r'"synopsis":"(.*?)(?<!\\)"', rsc)
            if m:
                content = m.group(1).replace("\\n", "\n").replace('\\"', '"')

        # 提取标签
        tags = []
        for m in re.finditer(r'"tagName":"([^"]+)"', rsc):
            tag = m.group(1)
            if tag and tag not in tags:
                tags.append(tag)
        vod_tag = ",".join(tags)

        # 提取总集数
        total_eps = 0
        # RSC 数据中 totalEpisodes 的第一个值是当前剧集的
        m = re.search(r'"totalEpisodes":(\d+)', rsc)
        if m:
            total_eps = int(m.group(1))
        if not total_eps and feed_info:
            total_eps = feed_info.get("_total_eps", 0)

        # 从 HTML 中的 "集" 也能获取
        if not total_eps:
            m = re.search(r'(\d+)\s*集', html)
            if m:
                total_eps = int(m.group(1))

        # 从电影详情页 RSC 提取 episodes 数组（含 locked 字段）
        free_eps = 0
        ep_array_match = re.search(r'"episodes":\[', rsc)
        if ep_array_match:
            start = ep_array_match.end() - 1
            depth = 0
            end_pos = start
            for i in range(start, min(start + 100000, len(rsc))):
                if rsc[i] == '[':
                    depth += 1
                elif rsc[i] == ']':
                    depth -= 1
                    if depth == 0:
                        end_pos = i + 1
                        break
            try:
                ep_list = json.loads(rsc[start:end_pos])
                free_eps = sum(1 for e in ep_list if not e.get("locked"))
            except Exception:
                pass

        # 如果未从 episodes 数组获取到免费集数，从 episode 页面 RSC 获取
        if not free_eps:
            ep1_url = self._full_url("/" + self.lang + "/video/episode-1-" + str(vod_id))
            ep1_html = self._get(ep1_url)
            if ep1_html:
                ep1_rsc = self._extract_rsc(ep1_html)
                ep_sorts = re.findall(r'episodeSort[\"\\]*:(\d+)', ep1_rsc)
                real_eps = [int(s) for s in ep_sorts if int(s) >= 1]
                free_eps = len(real_eps)

        # 构建播放列表 — 生成所有集数（和网站一致）
        play_list = []
        if total_eps > 0:
            for i in range(1, total_eps + 1):
                play_list.append("第{}集${}|{}".format(i, vod_id, i))
        else:
            # 回退：从 HTML 提取已有的集数链接
            ep_pattern = re.compile(
                r'href="/' + re.escape(self.lang) + r'/video/episode-(\d+)-([^"]+)"',
                re.S
            )
            seen_eps = set()
            for m in ep_pattern.finditer(html):
                ep_num = m.group(1)
                if ep_num not in seen_eps:
                    seen_eps.add(ep_num)
                    play_list.append("第{}集${}|{}".format(ep_num, vod_id, ep_num))

        remarks = "全{}集".format(total_eps) if total_eps else ""
        if free_eps and total_eps and free_eps < total_eps:
            remarks = "全{}集(免费{}集)".format(total_eps, free_eps)

        vod = {
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_remarks": remarks,
            "vod_content": content,
            "vod_type": vod_tag,
            "vod_play_from": "Anyreel",
            "vod_play_url": "#".join(play_list),
        }
        return {"list": [vod]}

    def searchContent(self, key, quick=False, pg=1):
        page = self._page(pg)
        key = str(key or "").strip().lower()
        if not key:
            return {"list": [], "page": page, "pagecount": 1, "limit": self.page_size, "total": 0}
        all_series = self._load_feed()
        filtered = []
        for sr in all_series:
            name = sr["vod_name"].lower()
            tags = " ".join(sr.get("_tags", [])).lower()
            if key in name or key in tags:
                filtered.append(sr)
        start = (page - 1) * self.page_size
        end = start + self.page_size
        page_list = filtered[start:end]
        total = len(filtered)
        pagecount = max(1, (total + self.page_size - 1) // self.page_size)
        result = []
        for sr in page_list:
            result.append({
                "vod_id": sr["vod_id"],
                "vod_name": sr["vod_name"],
                "vod_pic": sr["vod_pic"],
                "vod_remarks": sr["vod_remarks"],
            })
        return {
            "list": result,
            "page": page,
            "pagecount": pagecount,
            "limit": self.page_size,
            "total": total,
        }

    def playerContent(self, flag, id, vipFlags=None):
        text = str(id or "").strip()
        if "|" not in text:
            return {"parse": 0, "url": "", "header": {}}
        parts = text.split("|")
        if len(parts) < 2:
            return {"parse": 0, "url": "", "header": {}}
        vod_id = parts[0]
        ep_num = parts[1]

        try:
            ep_num_int = int(ep_num)
        except Exception:
            ep_num_int = 1

        # 构建视频页面 URL（slug 非必需，没有 slug 也能访问）
        video_url = self._full_url("/" + self.lang + "/video/episode-" + str(ep_num) + "-" + str(vod_id))
        html = self._get(video_url)

        if not html:
            return {"parse": 1, "url": video_url, "header": {}}

        # 从 RSC 数据中提取 episode 列表
        rsc = self._extract_rsc(html)

        # 提取所有 episode 的 episodeSort -> videoId -> pSign 三元组
        # 格式: "episodeSort":N,...,"videoId":"xxx",...,"pSign":"yyy"
        ep_entries = re.findall(
            r'episodeSort[\"\\]*:(\d+).{0,800}?videoId[\"\\]*:[\"\\]*([^\"\\,]+).{0,800}?pSign[\"\\]*:[\"\\]*([^\"\\,]+)',
            rsc
        )

        # 如果没有匹配，尝试反向顺序 (pSign 在 videoId 之前)
        if not ep_entries:
            # 尝试直接匹配 videoId 和 pSign 对
            vid_psign = re.findall(
                r'videoId[\"\\]*:[\"\\]*([^\"\\,]+).{0,800}?pSign[\"\\]*:[\"\\]*([^\"\\,]+)',
                rsc
            )
            ep_sorts = re.findall(r'episodeSort[\"\\]*:(\d+)', rsc)
            if vid_psign and ep_sorts and len(vid_psign) == len(ep_sorts):
                ep_entries = list(zip(ep_sorts, [v[0] for v in vid_psign], [v[1] for v in vid_psign]))

        # 按 episodeSort 匹配对应集数
        video_id = ""
        psign = ""
        app_id = "1500065780"

        if ep_entries:
            # 只精确匹配 episodeSort == ep_num_int
            # episodeSort 0=预览, 1=第1集, 2=第2集...
            for ep_sort, vid, ps in ep_entries:
                if int(ep_sort) == ep_num_int:
                    video_id = vid
                    psign = ps
                    break
            # 如果没找到精确匹配，说明该集是锁定集（网页不可播放）
            # 不使用其他集的 videoId/pSign，直接走 parse=1 回退

        # 提取 appId
        if not app_id or app_id == "1500065780":
            m_app = re.search(r'"appId":"?(\d+)"?', rsc)
            if m_app:
                app_id = m_app.group(1)

        if video_id and psign:
            # 解码 JWT 获取 appId（更可靠）
            try:
                jwt_parts = psign.split(".")
                if len(jwt_parts) >= 2:
                    payload_b64 = jwt_parts[1]
                    payload_b64 += "=" * (4 - len(payload_b64) % 4)
                    payload = json.loads(base64.urlsafe_b64decode(payload_b64))
                    app_id = str(payload.get("appId") or app_id)
            except Exception:
                pass

            # 调用腾讯云 VOD API v4 获取实际 m3u8 播放地址
            vod_api = "https://playvideo.qcloud.com/getplayinfo/v4/{}/{}?psign={}".format(
                app_id, video_id, psign
            )
            vod_data = self._get(vod_api, is_json=True)

            play_url = ""
            if vod_data and isinstance(vod_data, dict):
                media = vod_data.get("media") or {}
                streaming = media.get("streamingInfo") or {}
                # 优先 adaptive (多码率 m3u8)
                plain_output = streaming.get("plainOutput") or {}
                play_url = plain_output.get("url") or ""
                # 回退: MP4
                if not play_url:
                    mp4_output = streaming.get("mp4Output") or {}
                    if mp4_output and isinstance(mp4_output, list) and len(mp4_output) > 0:
                        play_url = mp4_output[0].get("url") or ""

            if play_url:
                # 确保使用 HTTPS
                if play_url.startswith("http://"):
                    play_url = "https://" + play_url[7:]
                return {
                    "parse": 0,
                    "url": play_url,
                    "header": {
                        "User-Agent": self.headers["User-Agent"],
                        "Referer": self.host + "/",
                    },
                }

            # 如果 VOD API 失败，回退到直接构造 CDN URL
            # 格式: https://{domain}/{t}/{fileId}.m3u8?psign={psign}
            try:
                jwt_parts = psign.split(".")
                if len(jwt_parts) >= 2:
                    payload_b64 = jwt_parts[1]
                    payload_b64 += "=" * (4 - len(payload_b64) % 4)
                    payload = json.loads(base64.urlsafe_b64decode(payload_b64))
                    url_info = payload.get("urlAccessInfo") or {}
                    domain = url_info.get("domain") or "videoint.anyreel.app"
                    url_key = url_info.get("t") or ""
                    file_id = payload.get("fileId") or video_id
                    if url_key:
                        play_url = "https://{}/{}/{}.m3u8?psign={}".format(
                            domain, url_key, file_id, psign
                        )
                    else:
                        play_url = "https://{}/{}.m3u8?psign={}".format(
                            domain, file_id, psign
                        )
                    if play_url:
                        return {
                            "parse": 0,
                            "url": play_url,
                            "header": {
                                "User-Agent": self.headers["User-Agent"],
                                "Referer": self.host + "/",
                            },
                        }
            except Exception:
                pass

        # 回退：搜索 m3u8 / mp4 直链
        m = re.search(r'(https?://[^"\'<>\s]+\.m3u8[^"\'<>\s]*)', html)
        if m:
            return {
                "parse": 0,
                "url": m.group(1),
                "header": {
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": self.host + "/",
                },
            }
        m = re.search(r'(https?://[^"\'<>\s]+\.mp4[^"\'<>\s]*)', html)
        if m:
            return {
                "parse": 0,
                "url": m.group(1),
                "header": {
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": self.host + "/",
                },
            }

        # 最终回退：交给解析器
        return {"parse": 1, "url": video_url, "header": {}}

    def isVideoFormat(self, url):
        u = str(url or "").lower()
        return ".m3u8" in u or ".mp4" in u

    def localProxy(self, param):
        return [404, "text/plain", ""]