# coding=utf-8
# !/usr/bin/python
"""
作者 【LONGYI】 内容均从互联网收集而来 仅供交流学习使用 严禁用于商业用途 请于24小时内删除
         ====================LONGYI====================
国家中小学智慧教育平台 · 课程教学（同步课堂）
https://basic.smartedu.cn/syncClassroom

筛选：学段 → 年级 / 学科 / 版本 / 册次
列表：教材；详情：按章节列出国家课/精品课；播放：m3u8（本地代理解 HLS 密钥）

播放：无需登录。CDN 仅校验非空鉴权头；AES 密钥经 /signs + md5 签名自动解包。
extend 可选填真实 Access Token（一般不用）。
"""

import base64
import hashlib
import json
import re
import sys
from collections import OrderedDict
from urllib.parse import quote, unquote, urljoin

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

from base.spider import Spider

sys.path.append("..")

CDN = "https://s-file-1.ykt.cbern.com.cn"
CDN2 = "https://s-file-2.ykt.cbern.com.cn"
HOST = "https://basic.smartedu.cn"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
PAGE_SIZE = 24
# CDN 只要非空 token 即可拉 m3u8/ts；真实登录 token 也可通过 extend 覆盖
DUMMY_TOKEN = "0"
NDR_PRIVATE = (
    "r1-ndr-private.ykt.cbern.com.cn",
    "r2-ndr-private.ykt.cbern.com.cn",
    "r3-ndr-private.ykt.cbern.com.cn",
)
NDR_PUBLIC = (
    "r1-ndr.ykt.cbern.com.cn",
    "r2-ndr.ykt.cbern.com.cn",
    "r3-ndr.ykt.cbern.com.cn",
)


class Spider(Spider):
    def getName(self):
        return "智慧教育"

    def init(self, extend=""):
        self.headers = {
            "User-Agent": UA,
            "Referer": HOST + "/",
            "Origin": HOST,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.token = DUMMY_TOKEN
        ext = (extend or "").strip()
        if ext:
            if ext.startswith("{"):
                try:
                    obj = json.loads(ext)
                    tok = str(
                        obj.get("token")
                        or obj.get("access_token")
                        or obj.get("accessToken")
                        or ""
                    ).strip()
                    if tok:
                        self.token = tok
                except Exception:
                    pass
            else:
                self.token = ext
        self._tag_root = None
        self._materials = None
        self._filters_cache = {}

    # ---------- http ----------
    def _get_json(self, url, timeout=30):
        try:
            r = self.session.get(url, timeout=timeout)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        if url.startswith(CDN):
            try:
                r = self.session.get(url.replace(CDN, CDN2, 1), timeout=timeout)
                if r.status_code == 200:
                    return r.json()
            except Exception:
                pass
        return None

    def _title(self, obj):
        if not obj:
            return ""
        if isinstance(obj, str):
            return obj.strip()
        t = obj.get("title")
        if isinstance(t, str) and t.strip():
            return t.strip()
        gt = obj.get("global_title") or {}
        if isinstance(gt, dict):
            return (gt.get("zh-CN") or gt.get("zh_cn") or next(iter(gt.values()), "") or "").strip()
        return ""

    def _thumb(self, obj):
        cp = (obj or {}).get("custom_properties") or {}
        thumbs = cp.get("thumbnails") or []
        if isinstance(thumbs, list) and thumbs:
            u = thumbs[0]
            if isinstance(u, str):
                return u.replace("-private", "")
        prev = cp.get("preview") or {}
        if isinstance(prev, dict):
            for v in prev.values():
                if isinstance(v, str) and v.startswith("http"):
                    return v.replace("-private", "")
        return ""

    # ---------- tags / materials ----------
    def _load_tags(self):
        if self._tag_root is not None:
            return self._tag_root
        data = self._get_json(f"{CDN}/zxx/ndrs/tags/national_lesson_tag.json") or {}
        hs = data.get("hierarchies") or []
        root = hs[0] if hs else {}
        self._tag_root = root
        return root

    def _tag_children(self, node):
        if not isinstance(node, dict):
            return []
        hs = node.get("hierarchies")
        if isinstance(hs, list) and hs:
            kids = hs[0].get("children") if isinstance(hs[0], dict) else None
            if isinstance(kids, list):
                return kids
        kids = node.get("children")
        return kids if isinstance(kids, list) else []

    def _stages(self):
        root = self._load_tags()
        return self._tag_children(root)

    def _find_stage(self, stage_id):
        for s in self._stages():
            if str(s.get("tag_id")) == str(stage_id):
                return s
        return None

    def _collect_dim(self, stage_node, dim_id, out=None, seen=None):
        """扁平收集某维度标签（年级/学科/版本/册次）。"""
        if out is None:
            out = OrderedDict()
        if seen is None:
            seen = set()
        for child in self._tag_children(stage_node):
            tid = str(child.get("tag_id") or "")
            name = child.get("tag_name") or ""
            dim = child.get("tag_dimension_id") or ""
            if dim == dim_id and tid and tid not in seen:
                seen.add(tid)
                out[tid] = name
            self._collect_dim(child, dim_id, out, seen)
        return out

    def _build_filters(self, stage_id):
        if stage_id in self._filters_cache:
            return self._filters_cache[stage_id]
        stage = self._find_stage(stage_id)
        if not stage:
            self._filters_cache[stage_id] = []
            return []
        dims = [
            ("年级", "zxxnj"),
            ("学科", "zxxxk"),
            ("版本", "zxxbb"),
            ("册次", "zxxcc"),
        ]
        filters = []
        for label, dim in dims:
            opts = self._collect_dim(stage, dim)
            if not opts:
                continue
            values = [{"n": "全部", "v": ""}]
            for tid, name in opts.items():
                values.append({"n": name, "v": tid})
            filters.append({"key": label, "name": label, "value": values})
        self._filters_cache[stage_id] = filters
        return filters

    def _load_materials(self):
        if self._materials is not None:
            return self._materials
        items = []
        for i in range(100, 110):
            data = self._get_json(
                f"{CDN}/zxx/ndrs/national_lesson/teachingmaterials/part_{i}.json",
                timeout=60,
            )
            if not isinstance(data, list):
                break
            items.extend(data)
        # 只要在线教材
        self._materials = [
            m for m in items if (m.get("status") or "ONLINE").upper() == "ONLINE"
        ]
        return self._materials

    def _mat_tag_ids(self, mat):
        ids = set()
        for t in mat.get("tag_list") or []:
            tid = t.get("tag_id")
            if tid:
                ids.add(str(tid))
        return ids

    def _filter_materials(self, stage_id, ext):
        mats = self._load_materials()
        need = set()
        if stage_id:
            need.add(str(stage_id))
        if isinstance(ext, dict):
            for k in ("年级", "学科", "版本", "册次"):
                v = str(ext.get(k) or "").strip()
                if v:
                    need.add(v)
        if not need:
            return mats
        out = []
        for m in mats:
            ids = self._mat_tag_ids(m)
            if need.issubset(ids):
                out.append(m)
        return out

    def _mat_vod(self, m):
        return {
            "vod_id": "tm_" + str(m.get("id")),
            "vod_name": self._title(m),
            "vod_pic": self._thumb(m),
            "vod_remarks": self._mat_remark(m),
        }

    def _mat_remark(self, m):
        names = []
        want = {"zxxnj", "zxxxk", "zxxbb", "zxxcc"}
        for t in m.get("tag_list") or []:
            if t.get("tag_dimension_id") in want and t.get("tag_name"):
                names.append(t["tag_name"])
        return "·".join(names[:4])

    # ---------- resources / detail ----------
    def _tm_resources(self, tm_id):
        data = self._get_json(
            f"{CDN}/zxx/ndrs/national_lesson/teachingmaterials/{tm_id}/resources/part_100.json",
            timeout=60,
        )
        return data if isinstance(data, list) else []

    def _tm_tree(self, tm_id):
        data = self._get_json(f"{CDN}/zxx/ndrs/national_lesson/trees/{tm_id}.json")
        return data if isinstance(data, list) else []

    def _tm_detail(self, tm_id):
        return (
            self._get_json(
                f"{CDN}/zxx/ndrs/national_lesson/teachingmaterials/details/{tm_id}.json"
            )
            or {}
        )

    def _walk_units(self, nodes, depth=0):
        """取一级单元作线路名；叶子章节用于匹配。"""
        units = []
        for n in nodes or []:
            kids = n.get("child_nodes") or n.get("children") or []
            units.append(
                {
                    "id": n.get("id"),
                    "title": n.get("title") or n.get("rich_title") or "章节",
                    "leaf_ids": self._collect_leaf_ids(n),
                }
            )
        return units

    def _collect_leaf_ids(self, node):
        kids = node.get("child_nodes") or node.get("children") or []
        if not kids:
            return [node.get("id")] if node.get("id") else []
        ids = []
        for c in kids:
            ids.extend(self._collect_leaf_ids(c))
        return ids

    def _activity_detail(self, aid):
        """国家课走 details；精品课等走 ndrv2/resources（details 常 403）。"""
        return (
            self._get_json(
                f"{CDN}/zxx/ndrv2/national_lesson/resources/details/{aid}.json"
            )
            or self._get_json(
                f"{CDN2}/zxx/ndrv2/national_lesson/resources/details/{aid}.json"
            )
            or self._get_json(f"{CDN}/zxx/ndrv2/resources/{aid}.json")
            or self._get_json(f"{CDN2}/zxx/ndrv2/resources/{aid}.json")
            or {}
        )

    def _video_courses(self, detail):
        """取出可播视频列表：国家课 national_course_resource，或精品课 course_resource 中带 m3u8 的项。"""
        rels = detail.get("relations") or {}
        if not isinstance(rels, dict):
            rels = {}
        courses = rels.get("national_course_resource") or []
        if isinstance(courses, list) and courses:
            return courses
        out = []
        for it in rels.get("course_resource") or []:
            if not isinstance(it, dict):
                continue
            for t in it.get("ti_items") or []:
                stor = str((t or {}).get("ti_storage") or "")
                flag = str((t or {}).get("ti_file_flag") or "").lower()
                if ".m3u8" in stor.lower() or "m3u8" in flag:
                    out.append(it)
                    break
        return out

    # ---------- play url / auth ----------
    def _auth_headers(self, url=""):
        tok = self.token or DUMMY_TOKEN
        h = {
            "User-Agent": UA,
            "Referer": HOST + "/",
            "Origin": HOST,
            "Accept": "*/*",
            "Authorization": "Bearer " + tok,
            "accessToken": tok,
            "X-ND-AUTH": 'MAC id="%s",nonce="0",mac="0"' % tok,
        }
        return h

    def _plain_headers(self):
        """密钥接口不能带伪造 Authorization，否则会触发 IP 限制。"""
        return {
            "User-Agent": UA,
            "Referer": HOST + "/",
            "Origin": HOST,
            "Accept": "*/*",
        }

    def _fetch_hls_key(self, key_url):
        """
        ndvideo-key: GET /signs → nonce；sign=md5(nonce+kid)[:16]；
        AES-ECB(sign) 解包返回的 base64 key → 16 字节 HLS 密钥。
        """
        u = (key_url or "").split("?", 1)[0].rstrip("/")
        kid = u.rsplit("/", 1)[-1]
        if not kid:
            return None
        h = self._plain_headers()
        try:
            nonce = self.session.get(u + "/signs", headers=h, timeout=15).json().get(
                "nonce"
            )
            if not nonce:
                return None
            sign = hashlib.md5((nonce + kid).encode("utf-8")).hexdigest()[:16]
            j = self.session.get(
                u, params={"nonce": nonce, "sign": sign}, headers=h, timeout=15
            ).json()
            blob = base64.b64decode(j.get("key") or "")
            pt = AES.new(sign.encode("utf-8"), AES.MODE_ECB).decrypt(blob)
            try:
                key = unpad(pt, 16)
            except Exception:
                key = pt
            return key[:16] if len(key) >= 16 else key
        except Exception:
            return None

    def _expand_storage(self, storage):
        if not storage:
            return []
        s = str(storage)
        if s.startswith("cs_path:${ref-path}"):
            path = s.replace("cs_path:${ref-path}", "")
            urls = []
            for host in NDR_PRIVATE + NDR_PUBLIC:
                urls.append("https://%s%s" % (host, path))
            return urls
        if s.startswith("http"):
            urls = [s]
            for priv, pub in zip(NDR_PRIVATE, NDR_PUBLIC):
                if priv in s:
                    urls.append(s.replace(priv, pub))
                if pub in s:
                    urls.append(s.replace(pub, priv))
            return list(OrderedDict.fromkeys(urls))
        return []

    def _pick_m3u8(self, detail, lesson_index=0):
        """从课程包详情取最佳 m3u8 候选列表。

        注意：部分新课（五四/精品课/video_courses）的 720p/480p/360p 直链会 400，
        仅 href / href-m3u8 可匿名拉取，故优先这两类。
        """
        courses = self._video_courses(detail)
        if not courses:
            courses = [detail]
        try:
            idx = int(lesson_index or 0)
        except Exception:
            idx = 0
        if idx < 0:
            idx = 0
        if idx >= len(courses):
            idx = 0
        courses = [courses[idx]] + [c for i, c in enumerate(courses) if i != idx]
        prefer = (
            "href-m3u8",
            "href",
            "href-720p-m3u8",
            "href-480p-m3u8",
            "href-360p-m3u8",
        )
        urls = []
        for course in courses:
            items = course.get("ti_items") or []
            by_flag = {}
            for it in items:
                flag = (it.get("ti_file_flag") or "").lower()
                by_flag[flag] = it
            for flag in prefer:
                it = by_flag.get(flag)
                if not it:
                    continue
                for u in self._expand_storage(it.get("ti_storage")):
                    if ".m3u8" in u.lower():
                        urls.append(u)
            for it in items:
                for u in self._expand_storage(it.get("ti_storage")):
                    if ".m3u8" in u.lower():
                        urls.append(u)
            # 只取目标课时的完整 URL，避免混入其它课时
            break
        if not urls:
            for u in re.findall(
                r"https://r[123]-ndr(?:-private)?\.ykt\.cbern\.com\.cn[^\"\\]+\.m3u8",
                json.dumps(detail, ensure_ascii=False),
            ):
                urls.append(u)
        return list(OrderedDict.fromkeys(urls))

    def _b64e(self, s):
        return base64.b64encode(str(s).encode("utf-8")).decode("utf-8")

    def _b64d(self, s):
        raw = str(s or "").strip()
        if not raw:
            return ""
        pad = "=" * ((4 - len(raw) % 4) % 4)
        try:
            return base64.b64decode(raw + pad).decode("utf-8", errors="ignore")
        except Exception:
            return unquote(raw)

    def _proxy_url(self, url, kind="m3u8", key_b64=""):
        """
        必须挂在 getProxyUrl() 后面用 &（其已含 do=py）。
        勿再用 ?do=smartedu，否则请求进不了本源 localProxy，表现为一直加载。
        """
        try:
            base = self.getProxyUrl()
        except Exception:
            base = ""
        if not base:
            return url
        parts = [
            base,
            "type=smartedu",
            "kind=%s" % kind,
            "url=%s" % quote(self._b64e(url), safe=""),
        ]
        if key_b64:
            parts.append("kb=%s" % quote(key_b64, safe=""))
        return "&".join(parts) if "?" in base else (base + "?" + "&".join(parts[1:]))

    def _decrypt_ts(self, data, key, iv=None):
        if not key or not data:
            return data
        iv = iv or (b"\x00" * 16)
        n = len(data) - (len(data) % 16)
        if n <= 0:
            return data
        try:
            pt = AES.new(key[:16], AES.MODE_CBC, iv=iv[:16]).decrypt(data[:n])
            # HLS 通常整段对齐，末尾可能有 PKCS7；有 0x47 同步字则视为成功
            if pt and pt[0] == 0x47:
                try:
                    return unpad(pt, 16)
                except Exception:
                    return pt
            return pt
        except Exception:
            return data

    # ---------- spider api ----------
    def homeContent(self, filter):
        classes = []
        filters = {}
        for s in self._stages():
            tid = str(s.get("tag_id") or "")
            name = s.get("tag_name") or ""
            if not tid or not name:
                continue
            # 五•四学制可保留
            classes.append({"type_id": tid, "type_name": name})
            filters[tid] = self._build_filters(tid)
        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        # 首页推荐：小学语文若干
        mats = self._filter_materials("e7bbb2de-0590-11ed-9c79-92fc3b3249d5", {})
        videos = [self._mat_vod(m) for m in mats[:12]]
        return {"list": videos}

    def categoryContent(self, tid, pg, filter, ext):
        try:
            page = max(1, int(pg or 1))
        except Exception:
            page = 1
        if not isinstance(ext, dict):
            ext = {}
        # 兼容 filter 参数
        if not ext and isinstance(filter, dict):
            ext = filter
        mats = self._filter_materials(str(tid or ""), ext)
        total = len(mats)
        start = (page - 1) * PAGE_SIZE
        end = start + PAGE_SIZE
        chunk = mats[start:end]
        pagecount = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        return {
            "list": [self._mat_vod(m) for m in chunk],
            "page": page,
            "pagecount": pagecount,
            "limit": PAGE_SIZE,
            "total": total,
        }

    def detailContent(self, ids):
        vid = str((ids or [""])[0] or "")
        if vid.startswith("tm_"):
            return self._detail_tm(vid[3:])
        if vid.startswith("act_"):
            return self._detail_act(vid[4:])
        # 裸 uuid：优先当教材，再当课程包
        if re.match(r"^[0-9a-fA-F-]{36}$", vid):
            d = self._tm_detail(vid)
            if d.get("id"):
                return self._detail_tm(vid)
            return self._detail_act(vid)
        return {"list": []}

    def _detail_tm(self, tm_id):
        info = self._tm_detail(tm_id)
        title = self._title(info) or tm_id
        pic = self._thumb(info)
        tree = self._tm_tree(tm_id)
        resources = self._tm_resources(tm_id)
        units = self._walk_units(tree)

        # chapter_id -> [resources]
        by_leaf = {}
        unmatched = []
        for r in resources:
            if (r.get("status") or "ONLINE").upper() != "ONLINE":
                continue
            cids = [str(x) for x in (r.get("chapter_ids") or [])]
            placed = False
            # 用路径最后一节匹配叶子
            if cids:
                leaf = cids[-1]
                by_leaf.setdefault(leaf, []).append(r)
                placed = True
            if not placed:
                unmatched.append(r)

        play_from = []
        play_url = []
        used = set()
        for unit in units:
            eps = []
            for lid in unit["leaf_ids"]:
                for r in by_leaf.get(str(lid), []):
                    rid = str(r.get("id") or "")
                    if not rid or rid in used:
                        continue
                    used.add(rid)
                    name = self._title(r) or rid
                    rtype = r.get("resource_type_code_name") or ""
                    cp = r.get("custom_properties") or {}
                    extp = cp.get("ext_properties") or {}
                    lessons = extp.get("lesson_list") or []
                    n_lesson = len(lessons) if isinstance(lessons, list) and lessons else 1
                    if n_lesson <= 1:
                        if rtype:
                            name = "%s[%s]" % (name, rtype)
                        eps.append(
                            "%s$act_%s__0"
                            % (name.replace("#", "＃").replace("$", "＄"), rid)
                        )
                    else:
                        for i in range(n_lesson):
                            epn = "%s·第%d课时" % (name, i + 1)
                            if rtype:
                                epn = "%s[%s]" % (epn, rtype)
                            eps.append(
                                "%s$act_%s__%d"
                                % (epn.replace("#", "＃").replace("$", "＄"), rid, i)
                            )
            if eps:
                play_from.append(unit["title"].replace("#", "＃"))
                play_url.append("#".join(eps))

        # 未归入已用线路的课包
        rest = []
        for r in resources:
            rid = str(r.get("id") or "")
            if not rid or rid in used:
                continue
            if (r.get("status") or "ONLINE").upper() != "ONLINE":
                continue
            used.add(rid)
            name = self._title(r) or rid
            rtype = r.get("resource_type_code_name") or ""
            cp = r.get("custom_properties") or {}
            extp = cp.get("ext_properties") or {}
            lessons = extp.get("lesson_list") or []
            n_lesson = len(lessons) if isinstance(lessons, list) and lessons else 1
            if n_lesson <= 1:
                if rtype:
                    name = "%s[%s]" % (name, rtype)
                rest.append(
                    "%s$act_%s__0" % (name.replace("#", "＃").replace("$", "＄"), rid)
                )
            else:
                for i in range(n_lesson):
                    epn = "%s·第%d课时" % (name, i + 1)
                    if rtype:
                        epn = "%s[%s]" % (epn, rtype)
                    rest.append(
                        "%s$act_%s__%d"
                        % (epn.replace("#", "＃").replace("$", "＄"), rid, i)
                    )
        if rest:
            play_from.append("其他课包")
            play_url.append("#".join(rest))

        tags = " ".join(
            t.get("tag_name") or ""
            for t in (info.get("tag_list") or [])
            if t.get("tag_name")
        )
        remark = self._mat_remark(info) if info.get("tag_list") else tags[:40]
        content = tags or title
        if not play_from:
            # 平台教材目录有条目，但课包未上传（resources=[]），非播放链路故障
            play_from = ["暂无视频"]
            play_url = ["平台未上传课包$smartedu_empty"]
            remark = (remark + "·" if remark else "") + "无课包"
            content = (content + "\n" if content else "") + "该教材在智慧教育平台暂无同步课堂视频（未上传课包）。"

        vod = {
            "vod_id": "tm_" + tm_id,
            "vod_name": title,
            "vod_pic": pic,
            "type_name": "同步课堂",
            "vod_year": "",
            "vod_area": "中国",
            "vod_remarks": remark,
            "vod_actor": "",
            "vod_director": "",
            "vod_content": content,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }
        return {"list": [vod]}

    def _detail_act(self, aid):
        detail = self._activity_detail(aid)
        title = self._title(detail) or aid
        pic = self._thumb(detail)
        courses = self._video_courses(detail)
        eps = []
        if courses:
            for i, c in enumerate(courses):
                name = self._title(c) or ("第%d课时" % (i + 1))
                eps.append(
                    "%s$act_%s__%d"
                    % (name.replace("#", "＃").replace("$", "＄"), aid, i)
                )
        if not eps:
            eps = ["正片$act_%s__0" % aid]
        vod = {
            "vod_id": "act_" + aid,
            "vod_name": title,
            "vod_pic": pic,
            "type_name": detail.get("resource_type_code_name") or "课程包",
            "vod_area": "中国",
            "vod_content": title,
            "vod_play_from": "智慧教育",
            "vod_play_url": "#".join(eps),
        }
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags):
        raw = str(id or "")
        if raw in ("", "smartedu_empty") or raw.endswith("smartedu_empty"):
            return {"parse": 0, "jx": 0, "url": "", "msg": "该教材暂无视频资源"}
        lesson_index = 0
        if "__" in raw:
            # act_{uuid}__{lessonIndex}，避免与选集分隔符 # 冲突
            left, _, idx = raw.rpartition("__")
            raw = left
            try:
                lesson_index = int(idx)
            except Exception:
                lesson_index = 0
        vid = raw[4:] if raw.startswith("act_") else raw
        if not vid or vid == "smartedu_empty":
            return {"parse": 0, "jx": 0, "url": "", "msg": "该教材暂无视频资源"}
        detail = self._activity_detail(vid)
        urls = self._pick_m3u8(detail, lesson_index=lesson_index)
        if not urls:
            return {"parse": 0, "jx": 0, "url": "", "msg": "未找到可播放地址"}
        play = urls[0]
        for u in urls:
            if "-private" in u:
                play = u
                break
        proxy = self._proxy_url(play, kind="m3u8")
        return {
            "parse": 0,
            "jx": 0,
            "playUrl": "",
            "url": proxy if proxy else play,
            "header": {
                "User-Agent": UA,
                "Referer": HOST + "/",
            },
        }

    def searchContent(self, key, quick, pg="1"):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg="1"):
        try:
            page = max(1, int(pg or 1))
        except Exception:
            page = 1
        kw = (key or "").strip()
        if not kw:
            return {"list": [], "page": page, "pagecount": 1, "limit": PAGE_SIZE, "total": 0}
        mats = [
            m
            for m in self._load_materials()
            if kw.lower() in self._title(m).lower()
        ]
        total = len(mats)
        start = (page - 1) * PAGE_SIZE
        chunk = mats[start : start + PAGE_SIZE]
        pagecount = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        return {
            "list": [self._mat_vod(m) for m in chunk],
            "page": page,
            "pagecount": pagecount,
            "limit": PAGE_SIZE,
            "total": total,
        }

    def localProxy(self, param):
        p = param or {}
        # 兼容：type=smartedu（正确） / 旧 do=smartedu
        if str(p.get("type") or "") != "smartedu" and str(p.get("do") or "") != "smartedu":
            return [404, "text/plain", b"not smartedu"]
        kind = str(p.get("kind") or "m3u8").lower()
        raw = p.get("url") or ""
        url = self._b64d(raw)
        if not url.startswith("http"):
            url = unquote(raw)
        if not url.startswith("http"):
            return [400, "text/plain", b"bad url"]
        try:
            # ---- 密钥：解包为原始 16 字节 ----
            if kind in ("key", "keys") or "ndvideo-key" in url or "/resource_keys/" in url:
                key = self._fetch_hls_key(url)
                if not key:
                    return [502, "text/plain", b"key fail"]
                return [200, "application/octet-stream", key]

            # ---- TS：拉密文并本地 AES 解密后返回明文（播放器无需再解 KEY）----
            if kind in ("ts", "media") or url.lower().endswith(".ts"):
                key = None
                kb = p.get("kb") or ""
                if kb:
                    try:
                        kb2 = unquote(kb)
                        kb2 += "=" * ((4 - len(kb2) % 4) % 4)
                        key = base64.b64decode(kb2)
                    except Exception:
                        key = None
                headers = self._auth_headers(url)
                r = self.session.get(url, headers=headers, timeout=30)
                body = r.content
                if key and len(key) >= 16:
                    body = self._decrypt_ts(body, key[:16])
                return [200, "video/mp2t", body]

            # ---- m3u8：去掉 EXT-X-KEY，分片走解密代理 ----
            headers = self._auth_headers(url)
            r = self.session.get(url, headers=headers, timeout=25)
            text = r.content.decode("utf-8", errors="ignore")
            if not text.lstrip().startswith("#EXTM3U"):
                return [r.status_code, "application/octet-stream", r.content]

            base = url.rsplit("/", 1)[0] + "/"
            key_bytes = None
            key_uri = ""
            for line in text.splitlines():
                if line.strip().startswith("#EXT-X-KEY"):
                    m = re.search(r'URI="([^"]+)"', line)
                    if m:
                        key_uri = m.group(1)
                        if not key_uri.startswith("http"):
                            key_uri = urljoin(base, key_uri)
                        key_bytes = self._fetch_hls_key(key_uri)
                    break
            kb = base64.b64encode(key_bytes).decode("ascii") if key_bytes else ""

            out = []
            for line in text.splitlines():
                s = line.strip()
                if s.startswith("#EXT-X-KEY"):
                    # 已在代理侧解密 TS，清单不再声明加密
                    continue
                if s and not s.startswith("#"):
                    abs_u = s if s.startswith("http") else urljoin(base, s)
                    out.append(self._proxy_url(abs_u, kind="ts", key_b64=kb))
                else:
                    out.append(line)
            body = ("\n".join(out) + "\n").encode("utf-8")
            return [200, "application/vnd.apple.mpegurl", body]
        except Exception as e:
            return [500, "text/plain", str(e).encode("utf-8", errors="ignore")]

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass
