# coding=utf-8
#!/usr/bin/python
import sys, re, base64, json, requests, time
from base.spider import Spider
from datetime import datetime, timedelta
from urllib.parse import quote, urljoin
from urllib3.util.retry import Retry
sys.path.append('..')

class Spider(Spider):
    def init(self, extend="{}"):
        origin = 'https://zh.stripchat.com'
        self.host = origin
        self.Doppiocdn = "doppiocdn.org"
        #domains = [
        #    "doppiocdn.com",       # cf cdn只能图片用，播放不了，可能触发验证码风控
        #    "doppiocdn.org",       # 靠谱云cdn，国内有节点
        #    "doppiocdn.net"        # cft cdn
        #]
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:153.0) Gecko/20100101 Firefox/153.0"
        self.headers = {'Origin': origin, 'Referer': f"{origin}/", 'User-Agent': user_agent, "Accept-Language": "zh,en;q=0.5"}
        self.stripchat_preferredVideoCodec = "H265"
        self.stripchat_key = "YzWScuyQRGAGcxx1KIJmiQ7BY9Vi35ftwLqUOVO8uoo="
        self.stripchat_pkey = "Fq6m2TO2ZeBkRPm9"
        self.stripchat_play='0 0'
        self.create_session_with_retry()

    def getName(self): return "StripChat"

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    def homeVideoContent(self):
        pass

    def normalize_username_for_hdstream(self, username):
        return username.replace('-', '_').lower()

    def homeContent(self, filter):
        CLASSES = [{'type_name': '女主播g', 'type_id': 'girls'}, {'type_name': '情侣c', 'type_id': 'couples'}, {'type_name': '男主播m', 'type_id': 'men'}, {'type_name': '跨性别t', 'type_id': 'trans'}]
        VALUE = [{'n': '中国', 'v': 'tagLanguageChinese'}, {'n': '亚洲', 'v': 'ethnicityAsian'}, {'n': '白人', 'v': 'ethnicityWhite'}, {'n': '拉丁', 'v': 'ethnicityLatino'}, {'n': '混血', 'v': 'ethnicityMultiracial'}, {'n': '印度', 'v': 'ethnicityIndian'}, {'n': '阿拉伯', 'v': 'ethnicityMiddleEastern'}, {'n': '黑人', 'v': 'ethnicityEbony'}]
        VALUE_MEN = [{'n': '情侣', 'v': 'sexGayCouples'}, {'n': '直男', 'v': 'orientationStraight'}]
        TIDS = ('girls', 'couples', 'men', 'trans')
        filters = {tid: [{'key': 'tag', 'value': VALUE_MEN + VALUE if tid == 'men' else VALUE}] for tid in TIDS}
        return {'class': CLASSES, 'filters': filters}

    def categoryContent(self, tid, pg, filter, extend):
        # 🔥 修复：明确定义limit变量
        limit = 60
        offset = limit * (int(pg) - 1)
        url = f"{self.host}/api/front/models?improveTs=false&removeShows=false&limit={limit}&offset={offset}&primaryTag={tid}&sortBy=stripRanking&rcmGrp=A&rbCnGr=true&prxCnGr=false&nic=false"
        if 'tag' in extend: url += f'&filterGroupTags=[["{extend["tag"]}"]]'
        rsp = self.session_get(url).json()
        videos = [{"vod_id": str(v['username']), "vod_name": f"{self.country_code_to_flag(str(v['country']))}{v['username']}", "vod_pic": f"https://img.{self.Doppiocdn}/snapshot/{v['id']}/{v['snapshotTimestamp']}", "vod_remarks": "" if v.get('status') == "public" else "🎫"} for v in rsp.get('models', [])]
        total = int(rsp.get('filteredCount', 0))
        return {"list": videos, "page": pg, "pagecount": (total + limit - 1) // limit, "limit": limit, "total": total}

    def detailContent(self, array):
        username = array[0]
        
        try:
            rsp = self.session_get(f"{self.host}/api/front/v2/models/username/{username}/cam").json()
            info, user = rsp['cam'], rsp['user']['user']
            uid, isLive = str(user['id']), user['isLive']
            oldName = self.stripchat_play.rsplit(' ', 1)[-1]
            if username != oldName:
                timestp = int(time.time())
                self.stripchat_play = f"0 {timestp} {username}"
            flag = self.country_code_to_flag(str(user['country']).strip())
            remark = "🔴 直播中" if isLive else "⚫ 已下播"
            show = info.get('show') or info.get('groupShowAnnouncement')
            if show:
                startAt = show.get('createdAt') or show.get('startAt')
                if startAt: remark = f"🎫 始于 {(datetime.strptime(startAt, '%Y-%m-%dT%H:%M:%SZ') + timedelta(hours=8)).strftime('%m月%d日 %H:%M')}"
            director = f"{flag}{username}"
            return {'list': [{"vod_id": username, "vod_name": str(info['topic'])[:80], "vod_pic": str(user['avatarUrl']), "vod_director": director, "vod_remarks": remark, 'vod_play_from': 'StripChat$$$LemonCams', 'vod_play_url': f"{uid}${uid}$$${uid}$lemon_{uid}"}]}
        except: return {'list': []}

    def searchContent(self, key, quick, pg="1"):
        if int(pg) > 1: return {}
        tags = {'G': 'girls', 'C': 'couples', 'M': 'men', 'T': 'trans'}
        parts = key.split(maxsplit=1)
        tag, key = (tags.get(parts[0].upper()), parts[1].strip()) if len(parts) > 1 and parts[0].upper() in tags else ('girls', key.strip())
        rsp = self.session_get(f"{self.host}/api/front/v4/models/search/group/username?query={key}&limit=900&primaryTag={tag}").json()
        return {'list': [{"vod_id": str(u['username']), "vod_name": f"{self.country_code_to_flag(str(u['country']))}{u['username']}", "vod_pic": f"https://img.{self.Doppiocdn}/snapshot/{u['id']}/{u['snapshotTimestamp']}", "vod_remarks": "" if u['status'] == "public" else "🎫"} for u in rsp.get('models', []) if u['isLive']]}

    def playerContent(self, flag, id, vipFlags):
        if id.startswith('lemon'):
            id = id.split('_')[1]
            rsp = self.session_get(f"https://edge-hls.growcdnssedge.com/hls/{id}/master/{id}_auto.m3u8?playlistType=lowLatency").text
            lines = rsp.strip().split('\n')
            urls = []
            for i, line in enumerate(lines):
                if '#EXT-X-STREAM-INF' in line:
                    qn_start = line.find('NAME="')+6
                    qn = line[qn_start:line.find('"', qn_start)]
                    url = lines[i + 1]
                    urls.extend([qn, url])
            lemon_headers = {
                'User-Agent': self.headers.get('User-Agent'),
                'Origin': 'https://www.lemoncams.com',
                'Referer': 'https://www.lemoncams.com/'
            }
            return {"url": urls, "parse": '0', "header": lemon_headers}

        try:
            rsp = self.session_get(f"https://edge-hls.{self.Doppiocdn}/hls/{id}/master/{id}_auto.m3u8?playlistType=lowLatency").text
            lines = rsp.strip().split('\n')
            psch, pkey, urls, processed = 'v2', self.stripchat_pkey, [], False
            for i, line in enumerate(lines):
                #if line.startswith('#EXT-X-MOUFLON:') and not processed:
                #    if len(parts := line.split(':')) >= 4: psch, pkey, processed = parts[2], parts[3], True
                if '#EXT-X-STREAM-INF' in line:
                    qn_start = line.find('NAME="')+6
                    qn = line[qn_start:line.find('"', qn_start)]
                    full_url = f"{lines[i+1]}&psch={psch}&pkey={pkey}&preferredVideoCodec={self.stripchat_preferredVideoCodec}"
                    urls.extend([qn, f"{self.getProxyUrl()}&url={quote(full_url)}"])
            headers = self.headers.copy()
            headers.pop('Accept-Language', None)
            return {"url": urls, "parse": '0', "header": headers}
        except: return {"url": [], "parse": 0}

    def update_vod(self, username):
        content_data = self.detailContent([username]).get('list')[0]
        #content_data.pop('vod_id')
        payload = {"json": json.dumps(content_data)}
        self.post("http://127.0.0.1:9978/action?do=refresh&type=vod", data=payload)
    
    def localProxy(self, param):
        url, type = param['url'], param.get('type', '')
        if type == 'rec_img':
            data = self.session_get(url, self.search_headers)
            return [200, 'application/octet-stream', data.content]
        rsp = self.session_get(url)
        oldCode, oldtmp, username = self.stripchat_play.rsplit(' ')
        timestp = int(time.time())
        is_time_up = (timestp - 10) > int(oldtmp)
        is_code_changed = (int(oldCode) != 0 and rsp.status_code != int(oldCode))
        if is_time_up or is_code_changed:
            self.stripchat_play = f"{rsp.status_code} {timestp} {username}"
            self.log('计划更新')
            self.update_vod(username)
            if is_code_changed:
                self.log('code变更')
                self.post("http://127.0.0.1:9978/action?do=refresh&type=player")
                return [404, "text/plain", ""]
        if rsp.status_code == 403: rsp = self.session_get(re.sub(r'(_\d+p\d*)?\.m3u8', '_160p_blurred.m3u8', url))
        if rsp.status_code != 200: return [404, "text/plain", ""]
        data = self.process_m3u8(rsp.text) if "#EXT-X-MOUFLON:URI:" in rsp.text else rsp.text
        return [200, "application/vnd.apple.mpegur", data]

    URL_PATTERN = re.compile(r'https://media-hls\.doppiocdn\.\w+/b-hls-\d+/media\.mp4')
    def process_m3u8(self, content):
        lines = content.strip().split('\n')
        for i, line in enumerate(lines):
            if line.startswith('#EXT-X-MOUFLON:URI:') and 'media.mp4' in lines[i+1]:
                mouflon = line.split(':', 2)[2].strip()
                encrypted = re.sub(r'(_part\d+)?\.mp4$', '', mouflon).rsplit('_', 2)[1]
                lines[i+1] = self.URL_PATTERN.sub(mouflon.replace(encrypted, self._decode(encrypted[::-1], self.stripchat_key)), lines[i+1])
        return '\n'.join(lines)

    def country_code_to_flag(self, code):
        return ''.join(chr(ord(c.upper()) - ord('A') + 0x1F1E6) for c in code) if len(code) == 2 and code.isalpha() else code

    def _decode(self, encrypted_b64: str, key_b64: str) -> str:
        # 补齐Base64填充，避免Incorrect padding错误
        missing_padding = len(encrypted_b64) % 4
        if missing_padding:
            encrypted_b64 += '=' * (4 - missing_padding)
        key_bytes = base64.b64decode(key_b64)
        encrypted = base64.b64decode(encrypted_b64)
        decrypted = bytearray(len(encrypted))
        for i in range(len(encrypted)):
            decrypted[i] = encrypted[i] ^ (key_bytes[i % len(key_bytes)] & 0xFF)
        return decrypted.decode('utf-8')

    def create_session_with_retry(self):
        self.session = requests.Session()
        retry = Retry(total=5, backoff_factor=0.3, status_forcelist=[429, 500, 502, 503, 504], raise_on_status=False)
        adapter = requests.adapters.HTTPAdapter(max_retries=retry, pool_connections=100, pool_maxsize=100, pool_block=False)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

    def session_get(self, url, headers=None, stream=False): return self.session.get(url, headers = self.headers if headers is None else headers, timeout=5, stream=stream, allow_redirects = True)
