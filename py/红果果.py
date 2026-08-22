from base.spider import Spider
import requests
import re
import json
import urllib.parse

host = "https://www.hongguoguo.tv"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36',
    'Referer': host
}
timeout = 10

# TVBox 兼容的 header 字符串格式
def _header_str():
    return f"User-Agent={headers['User-Agent']}&Referer={headers['Referer']}"


class Spider(Spider):
    def getName(self):
        return "红果果短剧"

    def init(self, extend):
        pass

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def homeContent(self, filter):
        # 福利短剧(fuliduanju)需要会员权限，已移除
        classes = [
            {"type_id": "jingxuanduanju", "type_name": "精选短剧"}
        ]
        return {"class": classes}

    def homeVideoContent(self):
        try:
            r = requests.get(host, headers=headers, timeout=timeout)
            return {'list': self._parse_list(r.text)}
        except Exception as e:
            print(f"[homeVideoContent] error: {e}")
            return {'list': []}

    def categoryContent(self, cid, pg, filter, ext):
        page = int(pg) if pg else 1
        if page == 1:
            url = f"{host}/vod/show/id/{cid}.html"
        else:
            url = f"{host}/vod/show/id/{cid}/page/{page}.html"
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            videos = self._parse_list(r.text)
            return {
                'list': videos,
                'page': pg,
                'pagecount': 9999,
                'limit': 24,
                'total': 999999
            }
        except Exception as e:
            print(f"[categoryContent] error: {e}")
            return {'list': []}

    def detailContent(self, ids):
        did = str(ids[0])
        try:
            play_page = f"{host}/vod/play/id/{did}/sid/1/nid/1.html"
            r = requests.get(play_page, headers=headers, timeout=timeout)
            text = r.text

            # 权限检查
            if '没有权限' in text or '升级会员' in text:
                print(f"[detailContent] ID={did} 需要会员权限")
                return {'list': []}

            # 提取 player_aaaa（支持多种闭合标签）
            player = None
            for pattern in [
                r'var player_aaaa=(\{.*?\})</script>',
                r'var player_aaaa=(\{.*?\});',
                r'player_aaaa=(\{.*?\})</script>',
            ]:
                m = re.search(pattern, text, re.DOTALL)
                if m:
                    try:
                        player = json.loads(m.group(1))
                        break
                    except json.JSONDecodeError:
                        continue

            if not player:
                print(f"[detailContent] ID={did} 未找到 player_aaaa")
                return {'list': []}

            vod_data = player.get('vod_data', {})
            play_url = player.get('url', '').replace('\\/', '/')
            play_from = player.get('from', 'm3u8')

            if not play_url:
                print(f"[detailContent] ID={did} 无播放地址")
                return {'list': []}

            # 提取封面
            pic = ''
            pic_m = re.search(r'"thumbnailUrl":"([^"]+)"', text)
            if pic_m:
                pic = pic_m.group(1).replace('\\/', '/')

            # 提取简介
            content = ''
            desc_m = re.search(r'<p[^>]*class="[^"]*desc[^"]*"[^>]*>(.*?)</p>', text, re.DOTALL)
            if desc_m:
                content = re.sub(r'<[^>]+>', '', desc_m.group(1)).strip()

            # 提取集数按钮
            ep_pattern = r'href="/vod/play/id/' + did + r'/sid/(\d+)/nid/(\d+)\.html"[^>]*>([^<]*)</a>'
            episodes = re.findall(ep_pattern, text)

            play_from_list = []
            play_url_list = []

            if not episodes:
                # 单集短剧
                play_from_list.append(play_from)
                vod_name = vod_data.get('vod_name', '第1集')
                play_url_list.append(f"{vod_name}${play_url}")
            else:
                # 按线路分组
                lines = {}
                for sid, nid, name in episodes:
                    sid = int(sid)
                    if sid not in lines:
                        lines[sid] = []
                    lines[sid].append((int(nid), name.strip()))

                for sid in sorted(lines.keys()):
                    line_eps = sorted(lines[sid], key=lambda x: x[0])
                    urls = []
                    line_name = None

                    for idx, (nid, name) in enumerate(line_eps):
                        if sid == 1 and nid == 1:
                            # 当前页面（第一集）
                            line_name = play_from
                            urls.append(f"{name}${play_url}")
                        else:
                            # 请求其他集页面
                            ep_url = f"{host}/vod/play/id/{did}/sid/{sid}/nid/{nid}.html"
                            try:
                                rr = requests.get(ep_url, headers=headers, timeout=8)
                                if '没有权限' in rr.text:
                                    continue
                                for pattern in [
                                    r'var player_aaaa=(\{.*?\})</script>',
                                    r'var player_aaaa=(\{.*?\});',
                                    r'player_aaaa=(\{.*?\})</script>',
                                ]:
                                    mm = re.search(pattern, rr.text, re.DOTALL)
                                    if mm:
                                        try:
                                            ep_player = json.loads(mm.group(1))
                                            ep_url_real = ep_player.get('url', '').replace('\\/', '/')
                                            if ep_url_real:
                                                urls.append(f"{name}${ep_url_real}")
                                            if line_name is None:
                                                line_name = ep_player.get('from', f'线路{sid}')
                                            break
                                        except json.JSONDecodeError:
                                            continue
                            except Exception as e:
                                print(f"[detailContent] 获取集 {sid}/{nid} 失败: {e}")
                                continue

                    if urls and line_name:
                        play_from_list.append(line_name)
                        play_url_list.append("#".join(urls))

            # 如果多线路处理失败，回退到单集
            if not play_from_list:
                play_from_list.append(play_from)
                vod_name = vod_data.get('vod_name', '第1集')
                play_url_list.append(f"{vod_name}${play_url}")

            VOD = {
                "vod_id": did,
                "vod_name": vod_data.get('vod_name', ''),
                "vod_pic": pic,
                "vod_actor": vod_data.get('vod_actor', ''),
                "vod_director": vod_data.get('vod_director', ''),
                "type_name": vod_data.get('vod_class', ''),
                "vod_remarks": "短剧",
                "vod_content": content,
                "vod_play_from": "$$$".join(play_from_list),
                "vod_play_url": "$$$".join(play_url_list)
            }
            return {'list': [VOD]}
        except Exception as e:
            print(f"[detailContent] 获取详情失败: {e}")
            return {'list': []}

    def playerContent(self, flag, id, vipFlags):
        print(f"[playerContent] flag={flag}, url={id[:80]}...")
        return {
            "parse": 0,
            "playUrl": '',
            "url": id,
            "header": _header_str()
        }

    def searchContent(self, key, quick, pg=1):
        page = int(pg) if pg else 1
        keyword = urllib.parse.quote(key)
        if page == 1:
            url = f"{host}/vod/search.html?wd={keyword}"
        else:
            url = f"{host}/vod/search.html?wd={keyword}&page={page}"
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            videos = self._parse_list(r.text)
            return {
                'list': videos,
                'page': page,
                'pagecount': 9999,
                'limit': 24,
                'total': 999999
            }
        except Exception as e:
            print(f"[searchContent] error: {e}")
            return {'list': []}

    def _parse_list(self, text):
        videos = []
        pattern = (
            r'<a[^>]*href="/vod/play/id/(\d+)/sid/1/nid/1\.html"[^>]*>'
            r'.*?<div class="Image">.*?'
            r'<div class="lazy" data-original="([^"]+)"[^>]*>.*?</div>'
            r'.*?<span class="f">([^<]*)</span>'
            r'.*?<span class="b">([^<]*)</span>'
            r'.*?</div>.*?'
            r'<h2 class="tim-title">([^<]*)</h2>'
            r'.*?</a>'
        )
        matches = re.findall(pattern, text, re.DOTALL)
        for m in matches:
            vid, pic, score, status, name = m
            videos.append({
                "vod_id": vid,
                "vod_name": name.strip(),
                "vod_pic": pic.strip(),
                "vod_remarks": f"{score.strip()} {status.strip()}",
                "vod_content": ""
            })
        return videos