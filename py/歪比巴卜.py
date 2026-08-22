# -*- coding: utf-8 -*-
import re
import json
import hashlib
import base64
import time
from urllib.parse import quote
from base.spider import Spider

# ---------- 纯Python实现的RC4和AES（无需第三方库） ----------
def rc4_crypt(data, key):
    S = list(range(256))
    j = 0
    for i in range(256):
        j = (j + S[i] + key[i % len(key)]) % 256
        S[i], S[j] = S[j], S[i]
    i = j = 0
    out = bytearray()
    for ch in data:
        i = (i + 1) % 256
        j = (j + S[i]) % 256
        S[i], S[j] = S[j], S[i]
        out.append(ch ^ S[(S[i] + S[j]) % 256])
    return out

def aes_cbc_decrypt(data, key, iv):
    raise NotImplementedError("AES解密需要 pycryptodome 库")

# 尝试导入官方库
try:
    from Crypto.Cipher import ARC4, AES
    from Crypto.Util.Padding import unpad
    def rc4_crypt(data, key):
        cipher = ARC4.new(key)
        return cipher.decrypt(data)
    def aes_cbc_decrypt(data, key, iv):
        cipher = AES.new(key.encode('utf-8'), AES.MODE_CBC, iv.encode('utf-8'))
        decrypted = unpad(cipher.decrypt(base64.b64decode(data)), AES.block_size)
        return decrypted.decode('utf-8')
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    print("[歪比影视] 提示: pycryptodome未安装，播放解密可能失败")

class Spider(Spider):
    BASE_URL = "https://wbbb1.com"
    PARSE_DOMAIN = "xn--qvr2v.850088.xyz"

    def_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": BASE_URL + "/",
        "Connection": "keep-alive",
    }

    play_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": BASE_URL + "/",
        "Accept": "*/*",
    }

    CATEGORY_MAP = {"1": "1", "2": "2", "3": "3", "4": "4"}
    CATEGORY_NAMES = {"1": "电影", "2": "剧集", "3": "动漫", "4": "综艺"}

    _cookies = ""

    # ---------- 加密工具 ----------
    def _md5(self, s):
        return hashlib.md5(s.encode('utf-8')).hexdigest()

    def _rc4_encrypt(self, data, key):
        key_bytes = key.encode('utf-8') if isinstance(key, str) else key
        data_bytes = data.encode('utf-8') if isinstance(data, str) else data
        encrypted = rc4_crypt(data_bytes, key_bytes)
        return base64.b64encode(encrypted).decode('utf-8')

    def _rc4_decrypt(self, data, key):
        key_bytes = key.encode('utf-8') if isinstance(key, str) else key
        data_bytes = base64.b64decode(data)
        decrypted = rc4_crypt(data_bytes, key_bytes)
        return decrypted.decode('utf-8')

    def _aes_decrypt(self, data, key, iv):
        if not CRYPTO_AVAILABLE:
            raise Exception("AES解密需要 pycryptodome 库")
        return aes_cbc_decrypt(data, key, iv)

    # ---------- 页面请求 ----------
    def _fetch_cookies(self):
        try:
            headers = {"User-Agent": self.def_headers["User-Agent"], "Accept": "text/html", "Referer": self.BASE_URL + "/"}
            resp = self.fetch(self.BASE_URL, headers=headers)
            cookie_list = []
            # 尝试多种方式获取Set-Cookie
            if hasattr(resp, 'cookies') and resp.cookies:
                try:
                    for cookie in resp.cookies:
                        cookie_list.append(f"{cookie.name}={cookie.value}")
                except:
                    pass
            if not cookie_list:
                if hasattr(resp.headers, "get_all"):
                    raw = resp.headers.get_all("Set-Cookie")
                    for c in raw:
                        cookie_list.append(c.split(";")[0])
                elif "Set-Cookie" in resp.headers:
                    raw = resp.headers["Set-Cookie"]
                    if isinstance(raw, list):
                        for c in raw:
                            cookie_list.append(c.split(";")[0])
                    else:
                        cookie_list.append(raw.split(";")[0])
            self._cookies = "; ".join(cookie_list)
            if self._cookies:
                print(f"[歪比影视] Cookie获取成功")
        except Exception as e:
            print(f"[歪比影视] Cookie获取失败: {e}")
            self._cookies = ""

    def _fetch_html(self, url):
        headers = self.def_headers.copy()
        if self._cookies:
            headers["Cookie"] = self._cookies
        try:
            resp = self.fetch(url, headers=headers)
            return resp.text
        except Exception as e:
            print(f"[歪比影视] 请求失败: {url}, {e}")
            # 如果失败且没有cookie，尝试重新获取cookie后重试
            if not self._cookies:
                print("[歪比影视] 尝试重新获取Cookie...")
                self._fetch_cookies()
                if self._cookies:
                    headers["Cookie"] = self._cookies
                    try:
                        resp = self.fetch(url, headers=headers)
                        return resp.text
                    except Exception as e2:
                        print(f"[歪比影视] 重试失败: {e2}")
            return ""

    # ---------- 工具函数：清理HTML标签 ----------
    def _clean_html(self, text):
        if not text:
            return ""
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    # ---------- 解析函数 ----------
    def _parse_video_list(self, html):
        """通用解析（用于首页/分类页）"""
        videos = []
        # 使用更宽松的正则匹配，兼容class顺序变化
        pattern = r'<a[^>]*href="/detail/(\d+\.html)"[^>]*class="[^"]*module-poster-item[^"]*"[^>]*>.*?<div[^>]*class="[^"]*module-item-note[^"]*"[^>]*>([^<]*)</div>.*?<img[^>]*data-original="([^"]+)"[^>]*>.*?<div[^>]*class="[^"]*module-poster-item-title[^"]*"[^>]*>([^<]*)</div>'
        for match in re.finditer(pattern, html, re.DOTALL):
            detail_url = match.group(1)
            vod_id = detail_url.replace(".html", "")
            vod_pic = match.group(3).strip()
            # 处理协议相对URL
            if vod_pic.startswith("//"):
                vod_pic = "https:" + vod_pic
            videos.append({
                "vod_id": vod_id,
                "vod_name": match.group(4).strip(),
                "vod_pic": vod_pic,
                "vod_remarks": match.group(2).strip(),
            })
        return videos

    def _parse_search_list(self, html):
        """专门解析搜索页（参考JS选择器）"""
        videos = []
        # 使用更宽松的正则匹配
        items = re.finditer(r'<div[^>]*class="[^"]*module-card-item[^"]*"[^>]*>(.*?)</div>\s*(?=<div[^>]*class="[^"]*module-card-item|$)', html, re.DOTALL)
        for item in items:
            block = item.group(1)
            # 提取链接
            link_match = re.search(r'<a[^>]*href="(/detail/[^"]+\.html)"', block)
            if not link_match:
                continue
            vod_id = link_match.group(1).replace("/detail/", "").replace(".html", "")
            # 提取标题
            title_match = re.search(r'<div[^>]*class="[^"]*module-card-item-title[^"]*"[^>]*>.*?<strong>([^<]*)</strong>', block, re.DOTALL)
            vod_name = title_match.group(1).strip() if title_match else "未知"
            # 提取图片
            pic_match = re.search(r'<img[^>]*data-original="([^"]+)"', block)
            vod_pic = pic_match.group(1) if pic_match else ""
            if vod_pic and vod_pic.startswith("//"):
                vod_pic = "https:" + vod_pic
            # 提取备注
            note_match = re.search(r'<div[^>]*class="[^"]*module-item-note[^"]*"[^>]*>([^<]*)</div>', block)
            vod_remarks = note_match.group(1).strip() if note_match else ""
            videos.append({
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_remarks": vod_remarks,
            })
        return videos

    def _parse_play_sources(self, html, vod_id):
        """
        提取每个线路的集数，线路名称准确提取
        """
        sources = []

        # 1. 提取线路名称（按顺序）- 优先使用 data-dropdown-value
        source_names = []
        for m in re.finditer(r'data-dropdown-value="([^"]+)"', html):
            name = m.group(1).strip()
            if name and name not in source_names:
                source_names.append(name)
        if not source_names:
            tab_box = re.search(r'<div[^>]*class="[^"]*module-tab-items-box[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
            if tab_box:
                for m in re.finditer(r'<div[^>]*class="[^"]*tab-item[^"]*"[^>]*>.*?<span[^>]*>([^<]*)</span>', tab_box.group(1)):
                    name = m.group(1).strip()
                    if name and name not in source_names:
                        source_names.append(name)
        if not source_names:
            for m in re.finditer(r'<span[^>]*class="[^"]*module-tab-value"[^>]*>([^<]*)</span>', html):
                name = m.group(1).strip()
                if name and name not in source_names:
                    source_names.append(name)
        if not source_names:
            source_names = ["默认"]

        # 2. 提取所有 module-list 块
        list_blocks = []
        start_tag = '<div class="module-list sort-list tab-list his-tab-list" id="panel1">'
        pos = 0
        while True:
            start = html.find(start_tag, pos)
            if start == -1:
                break
            start += len(start_tag)
            depth = 0
            end = None
            i = start
            while i < len(html):
                if html[i:i+5] == '<div ':
                    depth += 1
                    i += 5
                elif html[i:i+6] == '</div>':
                    if depth == 0:
                        end = i + 6
                        break
                    else:
                        depth -= 1
                        i += 6
                else:
                    i += 1
            if end is not None:
                block_html = html[start:end]
                if '/vplay/' in block_html:
                    list_blocks.append(block_html)
                pos = end
            else:
                pos = start + 1

        if not list_blocks:
            blocks = []
            start_tag2 = '<div class="module-play-list"'
            pos = 0
            while True:
                start = html.find(start_tag2, pos)
                if start == -1:
                    break
                start += len(start_tag2)
                depth = 0
                end = None
                i = start
                while i < len(html):
                    if html[i:i+5] == '<div ':
                        depth += 1
                        i += 5
                    elif html[i:i+6] == '</div>':
                        if depth == 0:
                            end = i + 6
                            break
                        else:
                            depth -= 1
                            i += 6
                    else:
                        i += 1
                if end is not None:
                    block_html = html[start:end]
                    if '/vplay/' in block_html:
                        list_blocks.append(block_html)
                    pos = end
                else:
                    pos = start + 1

        if not list_blocks:
            simple = re.findall(r'<div class="module-play-list"[^>]*>(.*?)</div>', html, re.DOTALL)
            for b in simple:
                if '/vplay/' in b:
                    list_blocks.append(b)

        # 3. 对齐名称与块数量
        if len(source_names) > len(list_blocks):
            source_names = source_names[:len(list_blocks)]
        while len(source_names) < len(list_blocks):
            source_names.append(f"源{len(source_names)+1}")

        # 4. 解析每个块的集数
        for idx, block in enumerate(list_blocks):
            eps = []
            for m in re.finditer(r'<a[^>]*href="(/vplay/(\d+)-(\d+)-(\d+)\.html)"[^>]*>.*?<span>([^<]*)</span>', block):
                link = m.group(1)
                id_ = m.group(2)
                sid = m.group(3)
                nid = m.group(4)
                name = m.group(5).strip()
                eps.append({"name": name, "link": f"{id_}-{sid}-{nid}"})
            if eps:
                sources.append({
                    "source_name": source_names[idx] if idx < len(source_names) else f"源{idx+1}",
                    "episodes": eps
                })

        if not sources:
            eps = []
            for m in re.finditer(r'<a[^>]*href="(/vplay/(\d+)-(\d+)-(\d+)\.html)"[^>]*>.*?<span>([^<]*)</span>', html):
                link = m.group(1)
                id_ = m.group(2)
                sid = m.group(3)
                nid = m.group(4)
                name = m.group(5).strip()
                eps.append({"name": name, "link": f"{id_}-{sid}-{nid}"})
            if eps:
                sources.append({"source_name": "默认", "episodes": eps})

        return sources

    # ---------- 播放地址获取 ----------
    def _get_play_url(self, vod_id, sid, nid):
        try:
            play_page = f"{self.BASE_URL}/vplay/{vod_id}-{sid}-{nid}.html"
            html = self._fetch_html(play_page)
            if not html:
                return None

            # 检查iframe
            iframe_match = re.search(r'<iframe[^>]*src="([^"]+)"', html)
            if iframe_match:
                iframe_url = iframe_match.group(1)
                if iframe_url.startswith('//'):
                    iframe_url = 'https:' + iframe_url
                elif iframe_url.startswith('/'):
                    iframe_url = self.BASE_URL + iframe_url
                print(f"[歪比影视] 发现iframe: {iframe_url}")
                return iframe_url

            # 提取加密URL - 使用更安全的大括号匹配算法，支持嵌套JSON
            enc_url = None
            m1 = re.search(r'var\s+player_aaaa\s*=\s*', html)
            if m1:
                start = m1.end()
                # 跳过空白字符
                while start < len(html) and html[start] in ' \t\n\r':
                    start += 1
                # 找到匹配的大括号
                if start < len(html) and html[start] == '{':
                    depth = 1
                    i = start + 1
                    while i < len(html) and depth > 0:
                        if html[i] == '{':
                            depth += 1
                        elif html[i] == '}':
                            depth -= 1
                        i += 1
                    if depth == 0:
                        json_str = html[start:i]
                        try:
                            player_data = json.loads(json_str)
                            enc_url = player_data.get("url", "")
                            print(f"[歪比影视] 提取到player_aaaa.url: {enc_url[:50]}...")
                        except Exception as e:
                            print(f"[歪比影视] player_aaaa JSON解析失败: {e}")
            
            # 兜底：直接搜索url字段
            if not enc_url:
                m2 = re.search(r'"url"\s*:\s*"([^"]+)"', html)
                if m2:
                    enc_url = m2.group(1)
                    print(f"[歪比影视] 兜底提取到url: {enc_url[:50]}...")

            if not enc_url:
                print("[歪比影视] 未能提取到加密URL")
                return None

            # 如果无加密库，返回解析页面
            if not CRYPTO_AVAILABLE:
                fallback_url = f"https://{self.PARSE_DOMAIN}/player/?url={enc_url}&next=//&title="
                print(f"[歪比影视] 无加密库，使用解析页面: {fallback_url}")
                return fallback_url

            try:
                domain = self.PARSE_DOMAIN
                l = (self._md5(enc_url) + " P")[-22:]
                key = l.encode('utf-8')
                h = self._rc4_encrypt(self._md5(enc_url + "stray"), key)
                timestamp = str(int(time.time()))
                u = self._rc4_encrypt(timestamp + self._md5(key.decode('utf-8') + "stray"), key)
                y = self._rc4_encrypt(self._md5(domain + "stray"), key)

                api_url = f"https://{domain}/player/api.php"
                headers = {
                    "User-Agent": self.play_headers["User-Agent"],
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Origin": f"https://{domain}",
                    "Referer": f"https://{domain}/player/?url={enc_url}",
                    "X-Requested-With": "XMLHttpRequest",
                    "Content-Type": "application/x-www-form-urlencoded"
                }
                if self._cookies:
                    headers["Cookie"] = self._cookies

                post_data = {"url": enc_url, "key": h, "vkey": u, "ckey": y}
                print(f"[歪比影视] 请求API: {api_url}")
                resp = self.post(api_url, data=post_data, headers=headers)
                result = json.loads(resp.text)
                print(f"[歪比影视] API返回: code={result.get('code')}")
                
                if result.get("code") == 200:
                    aes_key = self._rc4_decrypt(result["aes_key"], key)
                    aes_iv = self._rc4_decrypt(result["aes_iv"], key)
                    enc_play = result["url"]
                    play_url = self._aes_decrypt(enc_play, aes_key, aes_iv)
                    print(f"[歪比影视] 解密成功: {play_url[:80]}...")
                    return play_url
                else:
                    fallback_url = f"https://{domain}/player/?url={enc_url}&next=//&title="
                    print(f"[歪比影视] API返回非200，使用解析页面: {fallback_url}")
                    return fallback_url
            except Exception as e:
                print(f"[歪比影视] 解密异常: {e}")
                fallback_url = f"https://{self.PARSE_DOMAIN}/player/?url={enc_url}&next=//&title="
                return fallback_url
        except Exception as e:
            print(f"[歪比影视] 获取播放地址异常: {e}")
            return None

    # ---------- TVBox接口 ----------
    def init(self, extend=''):
        self._fetch_cookies()
        print("[歪比影视] 初始化完成")

    def homeContent(self, filter):
        return {"class": [{"type_id": tid, "type_name": name} for tid, name in self.CATEGORY_NAMES.items()]}

    def homeVideoContent(self):
        try:
            html = self._fetch_html(self.BASE_URL)
            if not html:
                return {"list": []}
            # 尝试匹配"正在热映"
            block = re.search(r'<div class="module">.*?<h2[^>]*class="[^"]*module-title[^"]*"[^>]*>正在热映.*?</div>(.*?)</div>\s*<div class="module">', html, re.DOTALL)
            if not block:
                # 兜底：尝试匹配第一个module块
                block = re.search(r'<div class="module">(.*?)</div>\s*<div class="module">', html, re.DOTALL)
            if not block:
                return {"list": []}
            videos = self._parse_video_list(block.group(1))
            return {"list": videos[:20]}
        except Exception as e:
            print(f"[歪比影视] homeVideoContent 异常: {e}")
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = int(pg)
            if tid not in self.CATEGORY_MAP:
                return {"list": [], "pagecount": 1, "page": pg}
            if pg == 1:
                url = f"{self.BASE_URL}/show/{tid}-----------.html"
            else:
                url = f"{self.BASE_URL}/show/{tid}--------{pg}---.html"
            print(f"[歪比影视] 分类请求: {url}")
            html = self._fetch_html(url)
            if not html:
                return {"list": [], "pagecount": 1, "page": pg}
            videos = self._parse_video_list(html)
            last = re.search(r'<a[^>]*href="/show/\d+--------(\d+)---\.html"[^>]*>尾页</a>', html)
            pagecount = int(last.group(1)) if last else 1
            return {"list": videos, "pagecount": pagecount, "page": pg}
        except Exception as e:
            print(f"[歪比影视] categoryContent 异常: {e}")
            return {"list": [], "pagecount": 1, "page": pg}

    def searchContent(self, key, quick, pg='1'):
        try:
            pg = int(pg)
            # 对搜索关键词进行URL编码，修复中文搜索失败
            encoded_key = quote(key)
            url = f"{self.BASE_URL}/search/{encoded_key}-------------.html"
            print(f"[歪比影视] 搜索请求: {url}")
            html = self._fetch_html(url)
            if not html:
                return {"list": [], "page": pg}
            videos = self._parse_search_list(html)
            return {"list": videos, "page": pg}
        except Exception as e:
            print(f"[歪比影视] searchContent 异常: {e}")
            return {"list": [], "page": pg}

    def detailContent(self, ids):
        try:
            vod_id = ids[0]
            url = f"{self.BASE_URL}/detail/{vod_id}.html"
            print(f"[歪比影视] 详情请求: {url}")
            html = self._fetch_html(url)
            if not html:
                return {"list": []}

            title = re.search(r'<h1>([^<]*)</h1>', html)
            vod_name = title.group(1).strip() if title else "未知"
            
            # 更宽松的图片匹配，兼容class变化
            pic = re.search(r'<div[^>]*class="[^"]*module-item-pic[^"]*"[^>]*>.*?<img[^>]*data-original="([^"]+)"', html, re.DOTALL)
            vod_pic = pic.group(1) if pic else ""
            if vod_pic.startswith("//"):
                vod_pic = "https:" + vod_pic
            
            desc = re.search(r'<div[^>]*class="[^"]*module-info-introduction-content[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
            vod_content = self._clean_html(desc.group(1)) if desc else ""
            
            actor = re.search(r'主演：</span>.*?<div[^>]*class="[^"]*module-info-item-content[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
            vod_actor = self._clean_html(actor.group(1)) if actor else ""
            
            director = re.search(r'导演：</span>.*?<div[^>]*class="[^"]*module-info-item-content[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
            vod_director = self._clean_html(director.group(1)) if director else ""
            
            year = re.search(r'<a[^>]*title="(\d{4})"', html)
            vod_year = year.group(1) if year else ""

            sources = self._parse_play_sources(html, vod_id)
            if not sources:
                print(f"[歪比影视] 未能解析到播放源")
                return {"list": []}

            from_list = []
            url_list = []
            for src in sources:
                from_list.append(src["source_name"])
                eps_str = "#".join([f"{ep['name']}${ep['link']}" for ep in src["episodes"]])
                url_list.append(eps_str)

            vod_play_from = "$$$".join(from_list)
            vod_play_url = "$$$".join(url_list)

            video = {
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_year": vod_year,
                "vod_area": "",
                "vod_actor": vod_actor,
                "vod_director": vod_director,
                "vod_content": vod_content,
                "vod_play_from": vod_play_from,
                "vod_play_url": vod_play_url,
            }
            print(f"[歪比影视] 详情解析成功: {vod_name}, 线路: {vod_play_from}")
            return {"list": [video]}
        except Exception as e:
            print(f"[歪比影视] detailContent 异常: {e}")
            return {"list": []}

    def playerContent(self, flag, vid, vip_flags):
        try:
            parts = vid.split("-")
            if len(parts) != 3:
                return {"jx": 0, "parse": 0, "url": "", "header": ""}
            vod_id, sid, nid = parts
            play_url = self._get_play_url(vod_id, sid, nid)
            if play_url:
                # 判断URL类型，决定parse标志
                # 如果是直接的视频文件或m3u8，parse=0；否则parse=1（需要TVBox嗅探/解析）
                is_direct = any(ext in play_url.lower() for ext in ['.m3u8', '.mp4', '.flv', '.ts', '.mkv', '.avi', '.mov', '.wmv'])
                is_direct = is_direct or 'm3u8' in play_url.lower() or 'mp4' in play_url.lower()
                parse_flag = 0 if is_direct else 1
                # header必须是JSON字符串
                header_str = json.dumps(self.play_headers)
                print(f"[歪比影视] 播放URL: {play_url[:80]}..., parse={parse_flag}")
                return {"jx": 0, "parse": parse_flag, "url": play_url, "header": header_str}
            return {"jx": 0, "parse": 0, "url": "", "header": ""}
        except Exception as e:
            print(f"[歪比影视] playerContent 异常: {e}")
            return {"jx": 0, "parse": 0, "url": "", "header": ""}

    def getName(self):
        return "歪比影视"

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    def localProxy(self, param):
        pass
