# coding=utf-8
# !/usr/bin/python
import re
import base64
import sys
import requests
import random
from bs4 import BeautifulSoup
from Crypto.Cipher import AES
from base.spider import Spider

sys.path.append('..')


class Spider(Spider):

    def getName(self):
        return "黄果短剧"

    def init(self, extend):
        self.xurl = self.get_domain().rstrip('/')
        self.session = requests.Session()
        self.headerx = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 16; 2407FRK8EC Build/BP2A.250605.031.A3) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/137.0.7151.115 Mobile Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }

    def get_domain(self):
        auto = None
        try:
            r = requests.get("https://huangguoai.pages.dev/publish.js?20240903", headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            t = r.text
            sm = re.search(r"var subdomains = \[(.*?)\]", t, re.DOTALL)
            subs = re.findall(r"'([^']+)'", sm.group(1)) if sm else ['thu', 'pku', 'fdu']
            um = re.search(r"var urls=\[(.*?)\]", t, re.DOTALL)
            urls = re.findall(r"'([^']+)'", um.group(1)) if um else ['ediayikma.cc/', 'agdkczeyx.cc/']
            auto = f"https://{random.choice(subs)}.{random.choice(urls).rstrip('/')}"
        except Exception:
            pass
        if auto:
            try:
                if requests.get(auto, headers={"User-Agent": "Mozilla/5.0"}, timeout=5).status_code == 200:
                    return auto
            except Exception:
                pass
        return "https://huangguoai.com/"

    def fetch(self, url):
        try:
            h = dict(self.headerx)
            h["Accept"] = "text/html,application/xhtml+xml"
            r = self.session.get(url=url, headers=h, timeout=15)
            return r.text if r.status_code == 200 else ""
        except Exception:
            return ""

    def _href(self, href):
        return self.xurl + href if href.startswith('/') else href

    def _img(self, src):
        if not src or not src.startswith('http') or src.startswith('data:'):
            return ''
        b = base64.b64encode(src.encode('utf-8')).decode('ascii')
        return f"{self.getProxyUrl()}&type=pic&url={b}"

    def _build(self, vid, name, pic='', remark='', desc=''):
        return {"vod_id": vid, "vod_name": name, "vod_pic": pic, "vod_remarks": remark, "vod_content": desc}

    def parse(self, html, mode='drama'):
        videos, doc, seen = [], BeautifulSoup(html, "lxml"), set()

        if mode == 'drama':
            for card in doc.find_all('div', class_='hg-drama-card'):
                a = card.find('a', href=True)
                if not a:
                    continue
                img = card.find('img')
                pic = self._img(img.get('data-src') or img.get('src', '')) if img else ''
                title = (img.get('alt', '') if img else '') or card.get('data-track-title', '')
                if not title:
                    t = card.find('h2', class_='hg-drama-card__title')
                    title = t.get_text(strip=True) if t else ''
                parts = [s.get_text(strip=True) for s in card.find_all('span', class_=re.compile('hg-drama-card__(badge|score|episode)'))]
                desc = card.find('p', class_='hg-drama-card__desc')
                videos.append(self._build(self._href(a['href']), title, pic, ' | '.join(parts), desc.get_text(strip=True) if desc else ''))

        elif mode == 'rank':
            for item in doc.find_all('div', class_='hg-rank-item'):
                a = item.find('a', href=True, class_='hg-rank-item__cover') or item.find('a', href=True)
                if not a:
                    continue
                img = item.find('img')
                pic = self._img(img.get('data-src') or img.get('src', '')) if img else ''
                title = item.get('data-track-title', '') or (img.get('alt', '') if img else '')
                if not title:
                    t = item.find('h2', class_='hg-rank-item__title')
                    title = t.get_text(strip=True) if t else ''
                heat = item.find('span', class_='hg-rank-item__heat-value')
                remark = '🔥' + heat.get_text(strip=True) if heat else ''
                desc = item.find('p', class_='hg-rank-item__desc')
                videos.append(self._build(self._href(a['href']), title, pic, remark, desc.get_text(strip=True) if desc else ''))

        elif mode == 'topic':
            for card in doc.find_all('a', class_='hg-topic-card'):
                slug = card['href'].strip('/').split('/')[-1]
                img = card.find('img')
                pic = self._img(img.get('data-src') or img.get('src', '')) if img else ''
                title = ''
                t = card.find('h2', class_='hg-topic-card__title')
                if t:
                    title = t.get_text(strip=True)
                elif img:
                    title = img.get('alt', '')
                meta = card.find('p', class_='hg-topic-card__meta')
                remark = meta.get_text(strip=True) if meta else ''
                videos.append({"vod_id": "dir_topic_" + slug, "vod_name": title, "vod_pic": pic, "vod_remarks": remark, "vod_tag": "folder"})

        elif mode == 'post':
            for card in doc.find_all('a', class_='hg-post-card'):
                href = card.get('href', '')
                if not href:
                    continue
                img = card.find('img')
                pic = self._img(img.get('data-src') or img.get('src', '')) if img else ''
                h3 = card.find('h3')
                title = h3.get_text(strip=True) if h3 else ''
                date = card.find('span', class_='hg-post-card__date')
                cat = card.find('span', class_='hg-post-card__cat')
                parts = [s.get_text(strip=True) for s in [date, cat] if s]
                videos.append(self._build(self._href(href), title, pic, ' | '.join(parts)))

        elif mode == 'search':
            for a in doc.find_all('a', href=re.compile(r'/detail/\d+')):
                img = a.find('img')
                if not img:
                    continue
                m = re.search(r'/detail/(\d+)', a.get('href', ''))
                if not m or m.group(1) in seen:
                    continue
                seen.add(m.group(1))
                pic = self._img(img.get('data-src') or img.get('src', ''))
                title = img.get('alt', '') or img.get('title', '') or a.get('title', '')
                if not title:
                    t = a.find(class_=re.compile('title'))
                    title = t.get_text(strip=True) if t else ''
                remark = ''
                for cls in ['episode', 'score']:
                    s = a.find(class_=re.compile(cls))
                    if s:
                        remark = s.get_text(strip=True)
                        break
                if title:
                    videos.append(self._build(m.group(1), title, pic, remark))

        return videos

    def homeVideoContent(self):
        try:
            return {"list": self.parse(self.fetch(f"{self.xurl}/recommend/1/"))}
        except Exception:
            return {"list": []}

    def homeContent(self, filter):
        return {
            "class": [
                {"type_id": "recommend", "type_name": "精选推荐"},
                {"type_id": "newest", "type_name": "最近上新"},
                {"type_id": "ai-duanju", "type_name": "AI成人短剧"},
                {"type_id": "ai-manju", "type_name": "AI成人漫剧"},
                {"type_id": "ai-huanlian", "type_name": "AI换脸"},
                {"type_id": "ai-mogai", "type_name": "AI魔改"},
                {"type_id": "topic", "type_name": "📌专题"},
                {"type_id": "ranks", "type_name": "排行榜"},
                {"type_id": "chigua", "type_name": "黄果吃瓜"},
                {"type_id": "author", "type_name": "黄果官方"},
            ],
            "list": [],
            "filters": {
                "ranks": [{"key": "类型", "name": "类型", "value": [
                    {"n": "热播榜", "v": "hot"}, {"n": "推荐榜", "v": "recommend"}, {"n": "潜力榜", "v": "potential"}
                ]}],
                "chigua": [{"key": "类型", "name": "类型", "value": [
                    {"n": "全部", "v": "page"}, {"n": "热门吃瓜", "v": "remen"}, {"n": "AI原创", "v": "yuanchuang"}
                ]}],
                "author": [{"key": "类型", "name": "类型", "value": [
                    {"n": "黄果官方", "v": "156291"}, {"n": "黄果ai大师", "v": "156305"}
                ]}]
            }
        }

    def _result(self, videos, pg, pagecount=9999):
        return {"list": videos, "page": pg, "pagecount": pagecount, "limit": 90, "total": 999999 if pagecount > 1 else len(videos)}

    def categoryContent(self, cid, pg, filter, ext):
        page = int(pg) if pg else 1
        rc = ext.get('类型', cid)

        try:
            if cid.startswith("dir_topic_"):
                return self._result(self.parse(self.fetch(f"{self.xurl}/topics/{cid.replace('dir_topic_', '')}/?page={page}"), 'drama'), pg)

            urls = {
                "recommend": f"{self.xurl}/recommend/{page}/",
                "newest": f"{self.xurl}/newest/{page}/",
                "topic": f"{self.xurl}/topics/",
                "ranks": f"{self.xurl}/ranks/{rc if rc in ['hot','recommend','potential'] else 'hot'}/",
                "chigua": f"{self.xurl}/chigua/{rc if rc in ['page','remen','yuanchuang'] else 'page'}/{page}/",
                "author": f"{self.xurl}/author/{rc if rc in ['156291','156305'] else '156291'}/video/{page}/",
            }

            if cid in ["ai-duanju", "ai-manju", "ai-huanlian", "ai-mogai"]:
                url, mode, pc = f"{self.xurl}/{cid}/{page}/", 'drama', 9999
            elif cid in urls:
                url, mode = urls[cid], {'topic': 'topic', 'ranks': 'rank', 'chigua': 'post'}.get(cid, 'drama')
                pc = 1 if cid in ['topic', 'ranks'] else 9999
            else:
                return self._result([], pg, 1)

            return self._result(self.parse(self.fetch(url), mode), pg, pc)

        except Exception:
            return self._result([], pg, 1)

    def detailContent(self, ids):
        did = ids[0]

        if '/archives/' in did:
            return self._detail_chigua(did)

        try:
            html = self.fetch(did)
        except Exception:
            return {"list": []}

        title = ''
        m = re.search(r'<title>(.*?)</title>', html)
        if m:
            title = m.group(1).split('|')[0].strip()

        vid = re.search(r'/detail/(\d+)/', did)
        vid = vid.group(1) if vid else (did if did.isdigit() else None)
        vurl = f"{self.xurl}/video/{vid}/" if vid else did.replace('/detail/', '/video/')

        try:
            vhtml = self.fetch(vurl)
        except Exception:
            return {"list": []}

        ep = re.search(r'<div class="hg-play__episodes">(.*?)</div>', vhtml, re.DOTALL)
        if ep:
            eps = re.findall(r'<a class="hg-play__ep-item[^"]*" href="([^"]*)" data-ep-id="([^"]*)"[^>]*>([^<]*)</a>', ep.group(1))
            play = '#'.join([f"{e[2].strip() or '第'+e[1]+'集'}${self._href(e[0])}" for e in eps])
        else:
            play = f"全1集${vurl}"

        video = self._build(did, title, desc=title, remark='')
        video["type_name"] = "黄果短剧"
        video["vod_year"] = ""
        video["vod_area"] = ""
        video["vod_actor"] = ""
        video["vod_director"] = ""
        video["vod_play_from"] = "黄果短剧"
        video["vod_play_url"] = play
        return {"list": [video]}

    def _detail_chigua(self, url):
        try:
            html = self.fetch(url)
        except Exception:
            return {"list": []}

        title = ''
        m = re.search(r'<title>(.*?)</title>', html)
        if m:
            title = m.group(1).split('|')[0].strip()

        players = re.findall(r'<div class="post-video-player"[^>]*data-player-key="([^"]*)"[^>]*data-src="([^"]*)"', html)
        play = '#'.join([f"{k}${v.replace('&amp;', '&')}" for k, v in players])

        video = self._build(url, title, desc=title, remark='')
        video["type_name"] = "黄果吃瓜"
        video["vod_year"] = ""
        video["vod_area"] = ""
        video["vod_actor"] = ""
        video["vod_director"] = ""
        video["vod_play_from"] = "黄果吃瓜"
        video["vod_play_url"] = play
        return {"list": [video]}

    def playerContent(self, flag, id, vipFlags):
        result = {"parse": 0, "playUrl": '', "url": id}

        if flag == "黄果吃瓜":
            result["header"] = {"User-Agent": self.headerx["User-Agent"], "Referer": self.xurl + "/"}
            return result

        try:
            m = re.search(r'<article class="hg-play__slide is-active"[^>]*data-play-src="([^"]*)"', self.fetch(id))
            if m:
                result["url"] = m.group(1).replace('&amp;', '&')
                result["header"] = {"User-Agent": self.headerx["User-Agent"], "Referer": self.xurl + "/"}
        except Exception:
            pass

        return result

    def searchContent(self, key, quick, pg="1"):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, page):
        try:
            pg = int(page) if page else 1
            videos = self.parse(self.fetch(f'{self.xurl}/search/video/{key}/{pg}/'), 'search')
        except Exception:
            videos = []
            pg = 1
        return {"page": pg, "pagecount": pg + 1 if len(videos) >= 20 else pg, "limit": 20, "total": 0, "list": videos}

    def localProxy(self, params):
        if params['type'] == "pic":
            return self.proxyPic(params)
        return None

    def proxyPic(self, params):
        url = base64.b64decode(params['url']).decode('utf-8')
        data = self.decrypt_image(requests.get(url, headers={'User-Agent': 'Mozilla/5.0', 'Referer': self.xurl + '/'}).content)
        ext = self.detect_extension(data)
        mime = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'gif': 'image/gif', 'webp': 'image/webp'}
        return [200, mime.get(ext, 'application/octet-stream'), data]

    def decrypt_image(self, encrypted_data):
        return AES.new(b'f5d965df75336270', AES.MODE_CBC, b'97b60394abc2fbe1').decrypt(encrypted_data).rstrip(b'\x00')

    def detect_extension(self, data):
        if data[:8] == b'\x89PNG\r\n\x1a\n':
            return 'png'
        if data[:3] == b'\xff\xd8\xff':
            return 'jpg'
        if data[:6] in (b'GIF87a', b'GIF89a'):
            return 'gif'
        if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
            return 'webp'
        return 'bin'