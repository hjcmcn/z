# -*- coding: utf-8 -*-
import re, urllib.parse
import json
from bs4 import BeautifulSoup
import requests
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def init(self, extend=""):
        self.host = "https://maihaolian.com/"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }

    def getName(self):
        return '枫叶影院'

    def homeContent(self, filter):
        return {"class": [
            {'type_id': "/label/qq", 'type_name': "腾讯VIP精选"},
            {'type_id': "/label/bli", 'type_name': "B站VIP精选"},
            {'type_id': "/label/youku", 'type_name': "优酷VIP精选"},
            {"type_id": "2", "type_name": "电视剧"},
            {"type_id": "1", "type_name": "电影"},
            {"type_id": "4", "type_name": "动漫"},
            {"type_id": "3", "type_name": "综艺"},
            {"type_id": "5", "type_name": "热门短剧"},
            {"type_id": "/label/duanju", "type_name": "红果短剧"},
        ], "filters": self._build_filters()}

    def _build_filters(self):
        area = [{"n": "全部", "v": ""}, {"n": "大陆", "v": "大陆"}, {"n": "香港", "v": "香港"},
                {"n": "台湾", "v": "台湾"}, {"n": "美国", "v": "美国"}, {"n": "韩国", "v": "韩国"},
                {"n": "日本", "v": "日本"}, {"n": "泰国", "v": "泰国"}, {"n": "新加坡", "v": "新加坡"},
                {"n": "马来西亚", "v": "马来西亚"}, {"n": "印度", "v": "印度"}, {"n": "英国", "v": "英国"},
                {"n": "法国", "v": "法国"}, {"n": "加拿大", "v": "加拿大"}, {"n": "西班牙", "v": "西班牙"},
                {"n": "俄罗斯", "v": "俄罗斯"}, {"n": "其它", "v": "其它"}]
        year = [{"n": "全部", "v": ""}, {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"},
                {"n": "2024", "v": "2024"}, {"n": "2023", "v": "2023"}, {"n": "2022", "v": "2022"},
                {"n": "2021", "v": "2021"}, {"n": "2020", "v": "2020"}, {"n": "2019", "v": "2019"},
                {"n": "2018", "v": "2018"}, {"n": "2017", "v": "2017"}, {"n": "2016", "v": "2016"},
                {"n": "2015", "v": "2015"}, {"n": "2014", "v": "2014"}, {"n": "2013", "v": "2013"},
                {"n": "2012", "v": "2012"}, {"n": "2011", "v": "2011"}, {"n": "2010", "v": "2010"},
                {"n": "2009", "v": "2009"}, {"n": "2008", "v": "2008"}, {"n": "2007", "v": "2007"},
                {"n": "2006", "v": "2006"}, {"n": "2005", "v": "2005"}, {"n": "2004", "v": "2004"}]
        lang = [{"n": "全部", "v": ""}, {"n": "国语", "v": "国语"}, {"n": "英语", "v": "英语"},
                {"n": "粤语", "v": "粤语"}, {"n": "闽南语", "v": "闽南语"}, {"n": "韩语", "v": "韩语"},
                {"n": "日语", "v": "日语"}, {"n": "法语", "v": "法语"}, {"n": "德语", "v": "德语"},
                {"n": "其它", "v": "其它"}]
        sort = [{"n": "时间", "v": "time"}, {"n": "人气", "v": "hits"}, {"n": "评分", "v": "score"}]
        letter = [{"n": "全部", "v": ""}, {"n": "A", "v": "A"}, {"n": "B", "v": "B"}, {"n": "C", "v": "C"},
                  {"n": "D", "v": "D"}, {"n": "E", "v": "E"}, {"n": "F", "v": "F"}, {"n": "G", "v": "G"},
                  {"n": "H", "v": "H"}, {"n": "I", "v": "I"}, {"n": "J", "v": "J"}, {"n": "K", "v": "K"},
                  {"n": "L", "v": "L"}, {"n": "M", "v": "M"}, {"n": "N", "v": "N"}, {"n": "O", "v": "O"},
                  {"n": "P", "v": "P"}, {"n": "Q", "v": "Q"}, {"n": "R", "v": "R"}, {"n": "S", "v": "S"},
                  {"n": "T", "v": "T"}, {"n": "U", "v": "U"}, {"n": "V", "v": "V"}, {"n": "W", "v": "W"},
                  {"n": "X", "v": "X"}, {"n": "Y", "v": "Y"}, {"n": "Z", "v": "Z"}, {"n": "0-9", "v": "0-9"}]
        return {
            "2": [
                {"key": "class", "name": "类型",
                 "value": [{"n": "全部", "v": "2"}, {"n": "国产剧", "v": "13"}, {"n": "日韩剧", "v": "15"},
                           {"n": "海外剧", "v": "16"}]},
                {"key": "area", "name": "地区", "value": area},
                {"key": "genre", "name": "剧情", "value": [{"n": v[0], "v": v[1]} for v in
                                                           [("全部", ""), ("古装", "古装"), ("战争", "战争"),
                                                            ("青春偶像", "青春偶像"), ("喜剧", "喜剧"),
                                                            ("家庭", "家庭"), ("犯罪", "犯罪"), ("动作", "动作"),
                                                            ("奇幻", "奇幻"), ("剧情", "剧情"), ("历史", "历史"),
                                                            ("经典", "经典"), ("乡村", "乡村"), ("情景", "情景"),
                                                            ("商战", "商战"), ("网剧", "网剧"), ("其他", "其他")]]},
                {"key": "year", "name": "年份", "value": year},
                {"key": "lang", "name": "语言", "value": lang},
                {"key": "letter", "name": "字母", "value": letter},
                {"key": "sort", "name": "排序", "value": sort},
            ],
            "1": [
                {"key": "class", "name": "类型",
                 "value": [{"n": "全部", "v": "1"}, {"n": "动作片", "v": "6"}, {"n": "喜剧片", "v": "7"},
                           {"n": "恐怖片", "v": "8"}, {"n": "科幻片", "v": "9"}, {"n": "爱情片", "v": "10"},
                           {"n": "剧情片", "v": "11"}, {"n": "战争片", "v": "12"}, {"n": "纪录片", "v": "20"}]},
                {"key": "area", "name": "地区", "value": area},
                {"key": "genre", "name": "剧情", "value": [{"n": v[0], "v": v[1]} for v in
                                                           [("全部", ""), ("喜剧", "喜剧"), ("爱情", "爱情"),
                                                            ("恐怖", "恐怖"), ("动作", "动作"), ("科幻", "科幻"),
                                                            ("剧情", "剧情"), ("战争", "战争"), ("警匪", "警匪"),
                                                            ("犯罪", "犯罪"), ("动画", "动画"), ("奇幻", "奇幻"),
                                                            ("武侠", "武侠"), ("冒险", "冒险"), ("枪战", "枪战"),
                                                            ("悬疑", "悬疑"), ("惊悚", "惊悚"), ("经典", "经典"),
                                                            ("青春", "青春"), ("文艺", "文艺"), ("微电影", "微电影"),
                                                            ("古装", "古装"), ("历史", "历史"), ("运动", "运动"),
                                                            ("农村", "农村"), ("儿童", "儿童"),
                                                            ("网络电影", "网络电影")]]},
                {"key": "year", "name": "年份", "value": year},
                {"key": "lang", "name": "语言", "value": lang},
                {"key": "letter", "name": "字母", "value": letter},
                {"key": "sort", "name": "排序", "value": sort},
            ],
            "4": [
                {"key": "class", "name": "类型",
                 "value": [{"n": "全部", "v": "4"}, {"n": "国产动漫", "v": "25"}, {"n": "日韩动漫", "v": "26"}]},
                {"key": "genre", "name": "剧情", "value": [{"n": v[0], "v": v[1]} for v in
                                                           [("全部", ""), ("情感", "情感"), ("科幻", "科幻"),
                                                            ("热血", "热血"), ("推理", "推理"), ("搞笑", "搞笑"),
                                                            ("冒险", "冒险"), ("奇幻", "奇幻"), ("战斗", "战斗"),
                                                            ("校园", "校园"), ("萝莉", "萝莉"), ("治愈", "治愈"),
                                                            ("原创", "原创"), ("亲子", "亲子"), ("益智", "益智"),
                                                            ("励志", "励志"), ("其他", "其他")]]},
                {"key": "area", "name": "地区",
                 "value": [{"n": "全部", "v": ""}, {"n": "大陆", "v": "大陆"}, {"n": "香港", "v": "香港"},
                           {"n": "台湾", "v": "台湾"}, {"n": "美国", "v": "美国"}, {"n": "韩国", "v": "韩国"},
                           {"n": "日本", "v": "日本"}, {"n": "法国", "v": "法国"}, {"n": "英国", "v": "英国"},
                           {"n": "其它", "v": "其它"}]},
                {"key": "year", "name": "年份", "value": year},
                {"key": "lang", "name": "语言", "value": lang},
                {"key": "letter", "name": "字母", "value": letter},
                {"key": "sort", "name": "排序", "value": sort},
            ],
            "3": [
                {"key": "class", "name": "类型",
                 "value": [{"n": "全部", "v": "3"}, {"n": "大陆综艺", "v": "21"}, {"n": "日韩综艺", "v": "22"}]},
                {"key": "genre", "name": "剧情", "value": [{"n": v[0], "v": v[1]} for v in
                                                           [("全部", ""), ("选秀", "选秀"), ("情感", "情感"),
                                                            ("访谈", "访谈"), ("播报", "播报"), ("音乐", "音乐"),
                                                            ("美食", "美食"), ("旅游", "旅游"), ("搞笑", "搞笑"),
                                                            ("游戏", "游戏"), ("亲子", "亲子"), ("其它", "其它")]]},
                {"key": "area", "name": "地区",
                 "value": [{"n": "全部", "v": ""}, {"n": "大陆", "v": "大陆"}, {"n": "香港", "v": "香港"},
                           {"n": "台湾", "v": "台湾"}, {"n": "美国", "v": "美国"}, {"n": "韩国", "v": "韩国"},
                           {"n": "日本", "v": "日本"}, {"n": "英国", "v": "英国"}, {"n": "其它", "v": "其它"}]},
                {"key": "year", "name": "年份", "value": year},
                {"key": "lang", "name": "语言", "value": lang},
                {"key": "letter", "name": "字母", "value": letter},
                {"key": "sort", "name": "排序", "value": sort},
            ],
        }

    def homeVideoContent(self):
        html = self._fetch('/')
        return {"list": self._parse_video_list(html)}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg)
        except:
            page = 1
        if str(tid).startswith('/label'):
            base = str(tid).replace('.html', '').rstrip('/')
            url = f'{base}.html' if page == 1 else f'{base}/page/{page}.html'
            html = self._fetch(url)
            items = self._parse_video_list(html)
            pagecount = self._page_count(html, page)
            return {"list": items, "page": page, "pagecount": pagecount, "limit": 24, "total": pagecount * 24}
        args = {}
        if extend and isinstance(extend, dict):
            for k, v in extend.items():
                if v:
                    args[k] = str(v)
        if isinstance(filter, dict):
            for k, v in filter.items():
                if v and k not in args:
                    args[k] = str(v)
        route_tid = args.get('class', args.get('tid', str(tid)))
        area = args.get('area', '')
        genre = args.get('genre', '')
        year = args.get('year', '')
        lang = args.get('lang', '')
        letter = args.get('letter', '')
        sort = args.get('sort', '')
        params = {"mid": "1", "tid": route_tid, "page": str(page)}
        if area: params["area"] = area
        if genre: params["class"] = genre
        if year: params["year"] = year
        if lang: params["lang"] = lang
        if letter: params["letter"] = letter
        if sort:
            params["by"] = sort
            params["order"] = sort
        data = self._fetch_json('/ajax/data?' + urllib.parse.urlencode(params))
        items = self._parse_ajax_list(data)
        if items:
            pagecount = int(data.get('pagecount') or page)
            total = int(data.get('total') or len(items))
            limit = int(data.get('limit') or len(items) or 10)
            return {"list": items, "page": page, "pagecount": pagecount, "limit": limit, "total": total}
        path = f'/cupfox-list/{route_tid}-----------.html' if page == 1 else f'/cupfox-list/{route_tid}--------{page}---.html'
        html = self._fetch(path)
        items = [] if '系统安全验证' in html else self._parse_video_list(html)
        pagecount = self._page_count(html, page) if items else 0
        return {"list": items, "page": page, "pagecount": pagecount, "limit": 36, "total": pagecount * 36}

    def detailContent(self, ids):
        result = {"list": []}
        vid = ids[0].split(',')[0].strip()
        try:
            html = self._fetch(f'/detail/{vid}.html')
            if not html: return result
            soup = BeautifulSoup(html, 'html.parser')
            vod_name = soup.select_one('h3.slide-info-title')
            vod_name = vod_name.text.strip() if vod_name else ''
            vod_pic = soup.select_one('img.lazy')
            vod_pic = self._fix_pic(vod_pic.get('data-src', '')) if vod_pic else ''
            vod_director = ''
            vod_actor = ''
            for el in soup.select('.slide-info'):
                text = el.get_text(' ', strip=True)
                if text.startswith('导演：'):
                    vod_director = text.replace('导演：', '').strip()
                elif text.startswith('演员：'):
                    vod_actor = text.replace('演员：', '').strip()
            vod_content = soup.select_one('#height_limit')
            vod_content = vod_content.get_text(' ', strip=True) if vod_content else ''
            play_from, play_url = [], []
            for tab in soup.select('.anthology-tab a.swiper-slide'):
                src_name = re.sub(r'<[^>]+>', '', str(tab)).strip() or tab.get_text(' ', strip=True).strip()
                if src_name:
                    play_from.append(src_name)
            tab_blocks = soup.select('.anthology-list-box')
            for i, block in enumerate(tab_blocks):
                ep_list = []
                for a in block.select('li a'):
                    href = a.get('href', '')
                    m = re.search(r'/play/(.*?)\.html', href)
                    if m:
                        ep_list.append(f'{a.text.strip()}${vid}-{m.group(1)}')
                ep_list.reverse()
                if ep_list and i < len(play_from):
                    play_url.append('#'.join(ep_list))
            valid_from = [pf for i, pf in enumerate(play_from) if i < len(play_url)]
            
            # 将至臻4K线路置顶
            def sort_4k_first(names, urls):
                combined = list(zip(names, urls))
                idx = -1
                for i, (name, _) in enumerate(combined):
                    if '至臻4k' in name.lower():
                        idx = i
                        break
                if idx > 0:
                    combined.insert(0, combined.pop(idx))
                return [n for n, _ in combined], [u for _, u in combined]
            
            valid_from, play_url = sort_4k_first(valid_from, play_url)
            
            result["list"].append({
                "vod_id": vid, "vod_name": vod_name, "vod_pic": vod_pic,
                "vod_director": vod_director, "vod_actor": vod_actor,
                "vod_content": vod_content,
                "vod_play_from": "$$$".join(valid_from),
                "vod_play_url": "$$$".join(play_url),
            })
        except:
            pass
        return result

    def searchContent(self, key, quick, pg="1"):
        try:
            decoded = urllib.parse.unquote(key)
        except:
            decoded = key
        html = self._fetch(f'/cupfox-search/{urllib.parse.quote(decoded)}----------{pg}---.html')
        items = self._parse_search_list(html)
        return {"list": items, "page": int(pg), "pagecount": 1, "limit": 36, "total": len(items)}

    def playerContent(self, flag, id, vipFlags):
        url = ''
        try:
            url = id if id.startswith('http') else f'{self.host}/play/{id}.html'
            html = self._fetch(url)
            if html:
                m = re.search(r'player_aaaa=(.*?)</script>', html, re.S)
                if m:

                    try:
                        pd = json.loads(m.group(1))
                    except Exception as e:
                        print(e)
                        pd = {}
                    # print('pd:', pd)
                    play_url = pd.get('url')
                    play_id = pd.get('from')

                    if not play_url:
                        return {"parse": 0, "url": 'https://php.doube.eu.org/error.m3u8',
                                "header": {'User-Agent': 'Mozilla/5.0'}}
                    # 直接链接检测（支持带参数）
                    if play_url.startswith('http'):
                        lower_url = play_url.lower()
                        if any(ext in lower_url for ext in ['.m3u8', '.mp4', '.flv', '.ts']):
                            return {"parse": 0, "url": play_url, "header": {'User-Agent': 'Mozilla/5.0'}}

                    # 参考 JS 版：根据 flag（线路名）选择解析接口
                    is_2k = '2k' in flag.lower()
                    parse_api = 'https://zzrs.mfdyvip.com' if is_2k else 'https://fgsrg.hzqingshan.com'

                    headers = {
                        'User-Agent': "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
                        'Accept': "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                        'accept-language': "zh-CN,zh;q=0.9",
                        'cache-control': "no-cache",
                        'pragma': "no-cache",
                        'priority': "u=0, i",
                        'referer': "https://www.ht10010.com/",
                        'Content-Type': 'application/x-www-form-urlencoded',
                    }
                    # 第一步 GET 获取 token
                    response = requests.get(f"{parse_api}/player/?url={play_url}", headers=headers)
                    token = re.search(r'data-te="(.*?)"', response.text)
                    if token:
                        token = token.group(1)
                        payload = {
                            'url': play_url,
                            'token': token
                        }
                        try:
                            # 第二步 POST 获取真实播放地址
                            response = self.post(f"{parse_api}/player/mplayer.php", data=payload, headers=headers)
                            response.raise_for_status()
                            result = response.json()
                            if result.get('code') == 200 and 'url' in result:
                                play_url = result['url']
                                return {"parse": 0, "url": play_url, "header": {
                                    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1'}}
                        except Exception as e:
                            print(e)
        except Exception as e:
            print(e)
        return {"parse": 1, "url": url}

    def localProxy(self, param=''):
        return {}

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def _fetch(self, url):
        try:
            if not url.startswith('http'):
                url = self.host.rstrip('/') + '/' + url.lstrip('/')
            rsp = self.fetch(url, headers=self.headers)
            return rsp.text if rsp else ''
        except:
            return ''

    def _fix_pic(self, u):
        if not u: return ''
        if u.startswith('//'): return 'https:' + u
        if u.startswith('/'):
            return self.host.rstrip('/') + u
        return u.replace('&amp;', '&')

    def _fix_url(self, u):
        if not u: return ''
        if u.startswith('//'): return 'https:' + u
        if u.startswith('/'):
            return self.host.rstrip('/') + u
        return u

    def _fetch_json(self, url):
        try:
            if not url.startswith('http'):
                url = self.host.rstrip('/') + '/' + url.lstrip('/')
            headers = dict(self.headers)
            headers.update({'Accept': 'application/json,text/plain,*/*', 'Referer': self.host})
            try:
                rsp = self.fetch(url, headers=headers)
                text = rsp.text if rsp else ''
            except:
                rsp = requests.get(url, headers=headers, timeout=15)
                rsp.encoding = rsp.apparent_encoding or 'utf-8'
                text = rsp.text
            return json.loads(text) if text else {}
        except Exception as e:
            print(f'[枫叶影院] ajax数据获取失败: {e}')
            return {}

    def _parse_ajax_list(self, data):
        videos, seen = [], set()
        for v in (data.get('list') or []):
            try:
                vod_id = str(v.get('vod_id') or '').strip()
                if not vod_id or vod_id in seen: continue
                seen.add(vod_id)
                vod_name = str(v.get('vod_name') or '').strip()
                vod_pic = self._fix_pic(str(v.get('vod_pic') or v.get('vod_pic_thumb') or '').strip())
                vod_remarks = str(v.get('vod_remarks') or v.get('vod_serial') or v.get('vod_score') or '').strip()
                vod_year = ','.join([str(x).strip() for x in [v.get('vod_year'), v.get('vod_area'), v.get('type_name')] if x])
                videos.append({"vod_id": vod_id, "vod_name": vod_name, "vod_pic": vod_pic, "vod_remarks": vod_remarks, "vod_year": vod_year})
            except Exception as e:
                print(f'[枫叶影院] 单条分类数据解析失败: {e}')
                continue
        return videos

    def _page_count(self, html, page=1):
        try:
            soup = BeautifulSoup(html or '', 'html.parser')
            pagecount = int(page)
            for a in soup.select('a.page-link'):
                text = a.get_text('', strip=True)
                href = a.get('href', '')
                if text in ('尾页', '末页'):
                    m = re.search(r'/page/(\d+)\.html|---(\d+)---', href)
                    if m:
                        return int(m.group(1) or m.group(2))
                if text.isdigit():
                    pagecount = max(pagecount, int(text))
            return pagecount
        except:
            return int(page)

    def _parse_video_list(self, html):
        videos, seen = [], set()
        soup = BeautifulSoup(html, 'html.parser')
        cards = soup.select('a.public-list-exp')
        for a in cards:
            href = a.get('href', '')
            m = re.search(r'/detail/(\d+)\.html', href)
            if not m: continue
            vod_id = m.group(1)
            if vod_id in seen: continue
            seen.add(vod_id)
            span = ','.join([span.text for span in a.select('span.public-prt')])
            # print('span', span)
            vod_name = a.get('title', '') or (a.select_one('img') and a.select_one('img').get('alt', '')) or ''
            pic_el = a.select_one('img')
            vod_pic = self._fix_pic(pic_el.get('data-src', '')) if pic_el else ''
            remark_el = a.select_one('.ft2') or a.select_one('.public-list-prb')
            vod_remarks = remark_el.text.strip() if remark_el else ''
            videos.append(
                {"vod_id": vod_id, "vod_name": vod_name.strip(), "vod_pic": vod_pic, "vod_remarks": vod_remarks, "vod_year": span})
        return videos

    def _parse_search_list(self, html):
        videos, seen = [], set()
        soup = BeautifulSoup(html, 'html.parser')
        cards = soup.select('a.public-list-exp')
        for a in cards:
            href = a.get('href', '')
            m = re.search(r'/detail/(\d+)\.html', href)
            if not m: continue
            vod_id = m.group(1)
            if vod_id in seen: continue
            seen.add(vod_id)
            pic_el = a.select_one('img')
            vod_pic = self._fix_pic(pic_el.get('data-src', '')) if pic_el else ''
            title_el = soup.select_one(f'a.thumb-txt[href="/detail/{vod_id}.html"]')
            if title_el:
                vod_name = title_el.text.strip()
            else:
                vod_name = a.select_one('img') and a.select_one('img').get('alt', '') or ''
            remark_el = a.select_one('.public-list-prb') or a.select_one('.ft2')
            vod_remarks = remark_el.text.strip() if remark_el else ''
            videos.append(
                {"vod_id": vod_id, "vod_name": vod_name.strip(), "vod_pic": vod_pic, "vod_remarks": vod_remarks})
        return videos
