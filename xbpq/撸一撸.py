# coding=utf-8
import sys
import json
import re
import requests
import base64
from bs4 import BeautifulSoup
from urllib.parse import unquote, urljoin

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider():
        def fetch(self, url, headers=None, timeout=10):
            try:
                res = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
                res.encoding = 'utf-8'
                return res
            except Exception as e:
                print(f"fetch error: {e}")
                return None

class Spider(BaseSpider):
    def getName(self):
        return "撸一天"

    def init(self, extend=""):
        self.host = "https://luyitian.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive'
        })

    def homeVideoContent(self):
        return {"list": []}

    def localProxy(self, params):
        return [200, "video/MP2T", ""]

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def fetch(self, url, headers=None, timeout=5):
        try:
            req_headers = headers or self.session.headers
            res = self.session.get(url, headers=req_headers, timeout=timeout, allow_redirects=True)
            res.encoding = 'utf-8'
            return res
        except Exception as e:
            print(f"fetch error: {e}")
            return None

    def _get_topic_filters(self):
        url = f"{self.host}/topic/"
        res = self.fetch(url, timeout=5)
        if not res:
            return []
        soup = BeautifulSoup(res.text, 'html.parser')
        topic_links = soup.select('a[href*="/topicdetail-"]')
        if not topic_links:
            topic_links = soup.select('a[href*="/topicdetail"]')
        filters = []
        seen = set()
        for a in topic_links:
            href = a.get('href', '')
            match = re.search(r'/topicdetail-(\d+)', href)
            if not match:
                match = re.search(r'/topicdetail/(\d+)', href)
            if not match:
                continue
            tid = match.group(1)
            name = a.get_text(strip=True) or a.get('title', '') or f"专题{tid}"
            if len(name) < 2:
                continue
            if tid not in seen:
                seen.add(tid)
                filters.append({"n": name, "v": tid})
        return filters

    def homeContent(self, filter):
        classes = [
            {"type_name": "最近更新", "type_id": "new"},
            {"type_name": "热门影片", "type_id": "hot"},
            {"type_name": "影片专题", "type_id": "topic"},
            {"type_name": "中文字幕", "type_id": "28"},
            {"type_name": "国产", "type_id": "20"},
            {"type_name": "日本有码", "type_id": "21"},
            {"type_name": "日本无码", "type_id": "22"},
            {"type_name": "欧美", "type_id": "23"},
            {"type_name": "动漫", "type_id": "24"},
            {"type_name": "伦理", "type_id": "25"},
            {"type_name": "韩国", "type_id": "36"},
            {"type_name": "另类", "type_id": "41"}
        ]

        filters = {
            "28": [{"key": "tid", "name": "子分类", "value": [
                {"n": "全部", "v": "28"},
                {"n": "日本中字", "v": "51"}
            ]}],
            "20": [{"key": "tid", "name": "子分类", "value": [
                {"n": "全部", "v": "20"},
                {"n": "国产精品", "v": "26"},
                {"n": "国产剧情", "v": "27"},
                {"n": "国产自拍", "v": "29"},
                {"n": "国产主播", "v": "35"},
                {"n": "国模私拍", "v": "85"},
                {"n": "网红明星", "v": "91"},
                {"n": "国产SM", "v": "105"},
                {"n": "台湾辣妹", "v": "107"},
                {"n": "香港正妹", "v": "108"}
            ]}],
            "21": [{"key": "tid", "name": "子分类", "value": [
                {"n": "全部", "v": "21"},
                {"n": "人妻", "v": "31"},
                {"n": "素人", "v": "44"},
                {"n": "口爆颜射", "v": "46"},
                {"n": "萝莉少女", "v": "47"},
                {"n": "美乳巨乳", "v": "48"},
                {"n": "制服诱惑", "v": "52"},
                {"n": "调教", "v": "57"},
                {"n": "出轨", "v": "58"},
                {"n": "有码精品", "v": "101"}
            ]}],
            "22": [{"key": "tid", "name": "子分类", "value": [
                {"n": "全部", "v": "22"},
                {"n": "无码精品", "v": "102"}
            ]}],
            "23": [{"key": "tid", "name": "子分类", "value": [
                {"n": "全部", "v": "23"},
                {"n": "欧美精品", "v": "104"}
            ]}],
            "24": [{"key": "tid", "name": "子分类", "value": [
                {"n": "全部", "v": "24"},
                {"n": "动漫精品", "v": "103"}
            ]}],
            "25": [{"key": "tid", "name": "子分类", "value": [
                {"n": "全部", "v": "25"},
                {"n": "综合三级", "v": "39"}
            ]}],
            "36": [{"key": "tid", "name": "子分类", "value": [
                {"n": "全部", "v": "36"},
                {"n": "韩国主播", "v": "37"}
            ]}],
            "41": [{"key": "tid", "name": "子分类", "value": [
                {"n": "全部", "v": "41"},
                {"n": "Cosplay", "v": "106"}
            ]}]
        }

        topic_values = self._get_topic_filters()
        if topic_values:
            filters["topic"] = [{
                "key": "tid",
                "name": "专题",
                "value": topic_values
            }]

        return {'class': classes, 'filters': filters}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg)
        result = {"list": [], "page": pg, "pagecount": 999, "limit": 20, "total": 9999}

        real_tid = extend.get('tid', tid)
        soup = None

        if real_tid.isdigit() and tid == "topic":
            urls_to_try = [
                f"{self.host}/topicdetail-{real_tid}/",
                f"{self.host}/topicdetail-{real_tid}.html",
                f"{self.host}/topicdetail/{real_tid}/",
                f"{self.host}/topicdetail/{real_tid}.html",
                f"{self.host}/topicdetail-{real_tid}-{pg}/",
                f"{self.host}/topicdetail/{real_tid}-{pg}/"
            ]
            for url in urls_to_try:
                res = self.fetch(url, headers={'Referer': self.host})
                if res and res.status_code == 200 and ('video-img-box' in res.text or 'vodlist' in res.text or 'vodplay' in res.text):
                    soup = BeautifulSoup(res.text, 'html.parser')
                    break
            if not soup:
                return result

        elif real_tid in ["new", "hot", "topic"]:
            if real_tid == "topic":
                return result
            if pg > 1:
                url = f"{self.host}/label/{real_tid}/page/{pg}/"
            else:
                url = f"{self.host}/label/{real_tid}/"
            res = self.fetch(url, headers={'Referer': self.host})
            if not res:
                url = f"{self.host}/label/{real_tid}/"
                res = self.fetch(url, headers={'Referer': self.host})
            if not res:
                return result
            soup = BeautifulSoup(res.text, 'html.parser')

        else:
            urls_to_try = [
                f"{self.host}/vodtype/{real_tid}-{pg}.html",
                f"{self.host}/vodtype/{real_tid}-{pg}/",
                f"{self.host}/type/{real_tid}-{pg}.html",
                f"{self.host}/type/{real_tid}-{pg}/",
                f"{self.host}/vodtype/{real_tid}/",
                f"{self.host}/vodtype/{real_tid}.html"
            ]
            res = None
            for url in urls_to_try:
                res = self.fetch(url, headers={'Referer': self.host})
                if res and res.status_code == 200:
                    if 'video-img-box' in res.text or 'vodlist' in res.text or 'item' in res.text:
                        break
                res = None
            if not res:
                return result
            soup = BeautifulSoup(res.text, 'html.parser')

        vod_list = []
        items = soup.select('.video-img-box') or soup.select('.video-film-list .video-item') or soup.select('.vodlist_item') or soup.select('.item')

        for item in items:
            a = item.select_one('a')
            if not a:
                continue
            href = a.get('href', '')
            vid_match = re.search(r'/vodplay/(\d+)', href) or \
                        re.search(r'/voddetail/(\d+)', href) or \
                        re.search(r'/vod/(\d+)', href) or \
                        re.search(r'/play/(\d+)', href)
            vid = vid_match.group(1) if vid_match else href

            name = ""
            img = item.select_one('img')
            if img and img.get('alt'):
                name = img['alt']
            if not name and a.get('title'):
                name = a['title']
            if not name:
                title_elem = item.select_one('.title a') or item.select_one('.detail .title a')
                if title_elem:
                    name = title_elem.get_text(strip=True)
            if not name:
                name = a.get_text(strip=True)
            if not name:
                name = "未知标题"

            pic = ""
            if img:
                pic = img.get('data-src') or img.get('src', '')
                if pic and not pic.startswith('http'):
                    pic = urljoin(self.host, pic)

            remark = ""
            remark_elem = item.select_one('.sub-title') or item.select_one('.remarks') or item.select_one('.video-remarks')
            if remark_elem:
                remark = remark_elem.get_text(strip=True)
                if len(remark) > 20:
                    remark = remark[:20]
            else:
                text = item.get_text(strip=True)
                parts = [p.strip() for p in text.split('\n') if p.strip()]
                if parts:
                    remark = parts[-1][:20]

            vod_list.append({
                "vod_id": vid,
                "vod_name": name.strip(),
                "vod_pic": pic,
                "vod_remarks": remark
            })

        result['list'] = vod_list

        page_elem = soup.select_one('.pagination a:last-child') or soup.select_one('.page a:last-child')
        if page_elem and page_elem.get('href'):
            try:
                nums = re.findall(r'(\d+)', page_elem['href'])
                if nums:
                    result['pagecount'] = max(int(nums[-1]), 1)
            except:
                pass

        return result

    def detailContent(self, ids):
        vid = ids[0]
        url = f"{self.host}/vodplay/{vid}-1-1/"
        res = self.fetch(url, headers={'Referer': self.host})
        if not res:
            return {"list": []}

        soup = BeautifulSoup(res.text, 'html.parser')
        raw_title = soup.title.text.split('|')[0].replace('在线播放在线观看','').replace('《','').replace('》','').strip()

        vod = {
            "vod_id": vid,
            "vod_name": raw_title,
            "vod_type": "视频",
            "vod_content": "资源来自于网络",
            "vod_play_from": "Luyitian",
            "vod_play_url": f"播放${vid}-1-1"
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg=1):
        url = f"{self.host}/vodsearch/{key}----------{pg}---/"
        res = self.fetch(url, headers={'Referer': self.host})
        if not res:
            return {"list": []}

        soup = BeautifulSoup(res.text, 'html.parser')
        vod_list = []
        items = soup.select('.video-img-box') or soup.select('.video-film-list .video-item')

        for item in items:
            a = item.select_one('a')
            if not a:
                continue
            href = a.get('href', '')
            vid_match = re.search(r'/vodplay/(\d+)', href) or re.search(r'/voddetail/(\d+)', href)
            vid = vid_match.group(1) if vid_match else href

            name = ""
            img = item.select_one('img')
            if img and img.get('alt'):
                name = img['alt']
            if not name and a.get('title'):
                name = a['title']
            if not name:
                title_elem = item.select_one('.title a')
                if title_elem:
                    name = title_elem.get_text(strip=True)
            if not name:
                name = a.get_text(strip=True)
            if not name:
                name = "搜索结果"

            pic = ""
            if img:
                pic = img.get('data-src') or img.get('src', '')

            vod_list.append({
                "vod_id": vid,
                "vod_name": name.strip(),
                "vod_pic": pic,
                "vod_remarks": ""
            })
        return {"list": vod_list}

    def _js_decode(self, js_str):
        b64_match = re.search(r'atob\s*\(\s*["\']([^"\']+)["\']\s*\)', js_str)
        if b64_match:
            try:
                decoded = base64.b64decode(b64_match.group(1)).decode('utf-8')
                return decoded
            except:
                pass
        unescape_match = re.search(r'unescape\s*\(\s*["\']([^"\']+)["\']\s*\)', js_str)
        if unescape_match:
            try:
                decoded = unquote(unescape_match.group(1))
                return decoded
            except:
                pass
        url_match = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', js_str, re.I)
        if url_match:
            return url_match.group(1)
        return None

    def _sniff_xhr(self, html, page_url):
        patterns = [
            r'fetch\s*\(\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
            r'XMLHttpRequest.*?\.open\s*\(\s*["\']GET["\']\s*,\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
            r'\.get\s*\(\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
            r'url\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
            r'src\s*=\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
        ]
        for pat in patterns:
            match = re.search(pat, html, re.I)
            if match:
                url = match.group(1)
                if not url.startswith('http'):
                    url = urljoin(page_url, url)
                return url

        scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.I | re.S)
        for script_content in scripts:
            if script_content.strip():
                found = self._js_decode(script_content)
                if found and '.m3u8' in found:
                    return found
        return None

    def _skip_ad_time(self, m3u8_text, skip_seconds=25):
        """
        解析 m3u8，累积分片时长，跳过前 skip_seconds 秒，生成新的 m3u8。
        同时插入 #EXT-X-START 标签让播放器从指定时间开始。
        """
        lines = m3u8_text.splitlines()
        header_lines = []       # 保留到分片前的全局标签
        media_sequence = 0      # 初始序列号
        target_duration = None
        video_segments = []     # 每个元素 (extinf_line, ts_line)

        i = 0
        # 先提取头部标签
        while i < len(lines) and not lines[i].startswith('#EXTINF'):
            line = lines[i]
            if line.startswith('#EXT-X-MEDIA-SEQUENCE'):
                try:
                    media_sequence = int(line.split(':')[1])
                except:
                    pass
                header_lines.append(line)
            elif line.startswith('#EXT-X-TARGETDURATION'):
                header_lines.append(line)
                try:
                    target_duration = float(line.split(':')[1])
                except:
                    pass
            elif not line.startswith('#'):
                # 意外出现非注释行，可能是分片，跳过
                break
            else:
                header_lines.append(line)
            i += 1

        # 读取分片段
        while i < len(lines):
            if lines[i].startswith('#EXTINF'):
                extinf = lines[i]
                i += 1
                if i < len(lines):
                    ts_line = lines[i]
                    video_segments.append((extinf, ts_line))
                    i += 1
                else:
                    break
            elif lines[i].startswith('#'):
                # 其他标签，忽略或酌情处理
                i += 1
            else:
                # 孤立的 ts，视为一个片段
                video_segments.append(('', lines[i]))
                i += 1

        # 累加时长
        accumulated = 0.0
        start_index = 0
        for idx, (extinf, _) in enumerate(video_segments):
            dur = 0.0
            match = re.search(r'#EXTINF:\s*([\d.]+)', extinf)
            if match:
                dur = float(match.group(1))
            elif target_duration:
                dur = target_duration
            else:
                dur = 3.0  # 假设 3 秒
            accumulated += dur
            if accumulated >= skip_seconds:
                start_index = idx
                break
        else:
            # 总时长不足 skip_seconds，不跳过
            start_index = 0

        # 裁剪片段，更新序列号
        new_segments = video_segments[start_index:]
        new_media_sequence = media_sequence + start_index

        # 构建新的 m3u8 内容
        new_lines = []
        # 添加原始头部但移除原有的 #EXT-X-MEDIA-SEQUENCE 和可能冲突的标签
        for line in header_lines:
            if line.startswith('#EXT-X-MEDIA-SEQUENCE'):
                continue
            if line.startswith('#EXT-X-START'):
                continue
            new_lines.append(line)
        # 添加新的序列号
        new_lines.append(f'#EXT-X-MEDIA-SEQUENCE:{new_media_sequence}')
        # 添加起始跳转标签
        new_lines.append(f'#EXT-X-START:TIME-OFFSET={skip_seconds}')
        # 添加分片
        for extinf, ts in new_segments:
            if extinf:
                new_lines.append(extinf)
            new_lines.append(ts)

        return '\n'.join(new_lines)

    def _get_m3u8_content(self, url, referer):
        try:
            headers = self.session.headers.copy()
            headers['Referer'] = referer
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                resp.encoding = 'utf-8'
                return resp.text
        except Exception as e:
            print(f"下载 m3u8 失败: {e}")
        return None

    def playerContent(self, flag, id, vipFlags=None):
        play_url = f"{self.host}/vodplay/{id}/"
        res = self.fetch(play_url, headers={'Referer': self.host}, timeout=5)
        if not res:
            return {"parse": 1, "url": play_url}

        html = res.text
        m3u8_url = None

        match = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\});', html, re.DOTALL)
        if match:
            try:
                json_str = match.group(1).strip()
                if json_str.endswith(','):
                    json_str = json_str[:-1]
                config = json.loads(json_str)
                m3u8_url = config.get('url', '')
            except:
                pass

        if not m3u8_url:
            m3u8_url = self._js_decode(html)

        if not m3u8_url:
            m3u8_url = self._sniff_xhr(html, play_url)

        if not m3u8_url:
            return {"parse": 1, "url": play_url}

        m3u8_url = unquote(m3u8_url)
        if m3u8_url.startswith('//'):
            m3u8_url = 'https:' + m3u8_url
        elif not m3u8_url.startswith('http'):
            m3u8_url = urljoin(self.host, m3u8_url)

        # 下载原始 m3u8
        m3u8_text = self._get_m3u8_content(m3u8_url, play_url)
        if not m3u8_text:
            return {
                "parse": 0,
                "playUrl": "",
                "url": m3u8_url,
                "header": {
                    "User-Agent": self.session.headers['User-Agent'],
                    "Referer": play_url,
                    "Origin": self.host
                }
            }

        # 跳过前25秒
        filtered_m3u8 = self._skip_ad_time(m3u8_text, skip_seconds=25)

        # 如果没有变化（不足25秒），直接返回原始
        if filtered_m3u8 == m3u8_text:
            return {
                "parse": 0,
                "playUrl": "",
                "url": m3u8_url,
                "header": {
                    "User-Agent": self.session.headers['User-Agent'],
                    "Referer": play_url,
                    "Origin": self.host
                }
            }

        # 打包为 data URI
        encoded_m3u8 = base64.b64encode(filtered_m3u8.encode('utf-8')).decode('ascii')
        data_url = f"data:application/vnd.apple.mpegurl;base64,{encoded_m3u8}"

        return {
            "parse": 0,
            "playUrl": "",
            "url": data_url,
            "header": {
                "User-Agent": self.session.headers['User-Agent'],
                "Referer": play_url,
                "Origin": self.host
            }
        }