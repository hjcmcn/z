# -*- coding: utf-8 -*-
import sys
import json
import time
import base64
import hashlib
import requests

sys.path.append('..')
try:
    from base.spider import Spider
except ImportError:
    class Spider:
        pass

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad, unpad
    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False


class Spider(Spider):
    def __init__(self):
        self.siteUrl = ''
        self.key = ''
        self.iv = ''
        self.apiPrefix = 'getappapi.index'
        self.initSuffix = 'init'
        self.headers = {
            'User-Agent': 'okhttp/3.10.0',
            'app-user-device-id': '291b226282010337c9443590d6457be15',
            'app-version-code': '112'
        }
        self.searchApiSuffix = 'searchList'
        self.souParamName = ''
        self.souSalt = ''
        self.extraSearchHeaders = {}
        self.homeVods = []
        self._class_list = []
        self._filters = {}
        self._inited = False

    def init(self, extend=""):
        if not extend:
            extend = '{"host":"http://110.42.67.130:1226","key":"kj37zs29q22jk96t","init":"V122","api":2,"ua":"okhttp/3.10.0"}'
        try:
            ext = json.loads(extend) if isinstance(extend, str) else extend
        except:
            ext = {}
        host = ext.get('host', '')
        if host:
            self.siteUrl = host.rstrip('/') + '/api.php'
        self.key = ext.get('key', '')
        self.iv = ext.get('iv', '') or self.key

        prefix_map = {'1': 'getappapi.index', '2': 'qijiappapi.index', '3': 'appapi'}
        api_num = str(ext.get('api', ''))
        if api_num in prefix_map:
            self.apiPrefix = prefix_map[api_num]

        init_val = ext.get('init', '')
        if isinstance(init_val, str) and init_val.startswith('V'):
            self.initSuffix = 'init' + init_val

        ua = ext.get('ua', '')
        if ua:
            self.headers['User-Agent'] = ua

        self._do_init()
        self._inited = True
        return {}

    def _do_init(self):
        try:
            url = f"{self.siteUrl}/{self.apiPrefix}/{self.initSuffix}"
            r = requests.post(url, headers=self.headers, timeout=15)
            ret = r.json()
            data = json.loads(self._aes_decode(ret.get('data', ''), self.key, self.iv))

            if data.get('box_config'):
                swapped = self.key[::-1]
                md5_key = hashlib.md5(swapped.encode()).hexdigest()
                dynamic_iv = md5_key[:16]
                box = json.loads(self._aes_decode(data['box_config'], swapped, dynamic_iv))
                if box.get('search_name'):
                    self.searchApiSuffix = box['search_name']
                if box.get('signature_name') and box.get('signature_value'):
                    self.souParamName = box['signature_name']
                    self.souSalt = self._process_sig(box['signature_value'])
                if box.get('api_header') and box['api_header'].get('key'):
                    self.extraSearchHeaders[box['api_header']['key']] = box['api_header']['value']
            else:
                self.searchApiSuffix = 'searchList'

            self.homeVods = []
            self._class_list = []
            self._filters = {}

            for item in data.get('type_list', []):
                tid = str(item.get('type_id', ''))
                self._class_list.append({
                    'type_id': tid,
                    'type_name': item.get('type_name', '')
                })
                if item.get('type_id', 0) > 0 and item.get('recommend_list'):
                    self.homeVods.extend(item['recommend_list'])

                flist = []
                for f in item.get('filter_type_list', []):
                    fv = [{'n': i, 'v': i} for i in f.get('list', [])]
                    fname = f.get('name', '')
                    if fname == 'class':
                        flist.append({'key': 'class', 'name': '分类', 'value': fv})
                    elif fname == 'area':
                        flist.append({'key': 'area', 'name': '区域', 'value': fv})
                    elif fname == 'lang':
                        flist.append({'key': 'lang', 'name': '语言', 'value': fv})
                    elif fname == 'year':
                        flist.append({'key': 'year', 'name': '年份', 'value': fv})
                    elif fname == 'sort':
                        flist.append({'key': 'sort', 'name': '排序', 'value': fv})
                if flist:
                    self._filters[tid] = flist
        except Exception as e:
            print(f"[XH] init error: {e}")

    def _process_sig(self, sig):
        if not sig:
            return ''
        if len(sig) < 8:
            return sig[::-1]
        return sig[:-8][::-1] + sig[-8:][::-1]

    def _aes_decode(self, s, key, iv):
        if not _HAS_CRYPTO:
            return ''
        try:
            cipher = AES.new(key.encode('utf-8'), AES.MODE_CBC, iv.encode('utf-8'))
            pt = cipher.decrypt(base64.b64decode(s))
            return unpad(pt, 16).decode('utf-8')
        except Exception:
            return ''

    def _aes_encode(self, s, key, iv):
        if not _HAS_CRYPTO:
            return ''
        try:
            cipher = AES.new(key.encode('utf-8'), AES.MODE_CBC, iv.encode('utf-8'))
            ct = cipher.encrypt(pad(s.encode('utf-8'), 16))
            return base64.b64encode(ct).decode('utf-8')
        except Exception:
            return ''

    def _request(self, url, data=None, extra_headers=None, method='post'):
        h = dict(self.headers)
        if extra_headers:
            h.update(extra_headers)
        if method == 'post':
            r = requests.post(url, data=data, headers=h, timeout=15)
        else:
            r = requests.get(url, params=data, headers=h, timeout=15)
        try:
            return r.json()
        except:
            return {}

    def _check_init(self):
        if not self._inited:
            self.init()

    def homeContent(self, filter=False):
        self._check_init()
        return {
            'class': self._class_list,
            'filters': self._filters,
            'list': []
        }

    def homeVideoContent(self):
        self._check_init()
        return {'list': self.homeVods}

    def categoryContent(self, tid, pg=1, filter=False, extend=""):
        self._check_init()
        if isinstance(extend, dict):
            ext = extend
        else:
            try:
                ext = json.loads(extend) if extend else {}
            except:
                ext = {}
        pg = int(pg) if str(pg).isdigit() else 1
        if pg <= 0:
            pg = 1

        url = f"{self.siteUrl}/{self.apiPrefix}/typeFilterVodList"
        params = {
            "area": ext.get('area', '全部'),
            "sort": ext.get('sort', '最新'),
            "class": ext.get('class', '全部'),
            "type_id": tid,
            "year": ext.get('year', '全部'),
            "lang": ext.get('lang', '全部'),
            "page": pg,
        }
        ret = self._request(url, params)
        enc_data = ret.get('data', '')
        if not enc_data:
            return {'list': [], 'page': pg, 'pagecount': 0, 'limit': 0, 'total': 0}
        data = json.loads(self._aes_decode(enc_data, self.key, self.iv))
        videos = data.get('recommend_list', [])
        return {
            'list': videos,
            'page': pg,
            'pagecount': 9999,
            'limit': len(videos),
            'total': len(videos)
        }

    def detailContent(self, ids):
        self._check_init()
        vid = ids[0] if isinstance(ids, list) else str(ids)
        url = f"{self.siteUrl}/{self.apiPrefix}/vodDetail"
        ret = self._request(url, {'vod_id': vid})
        enc_data = ret.get('data', '')
        if not enc_data:
            return {'list': []}
        info = json.loads(self._aes_decode(enc_data, self.key, self.iv))
        vod = info.get('vod', {})

        # ========== 【修复】vod_play_list 在 info 根层级，不在 vod 里 ==========
        vod_play_list = info.get('vod_play_list', []) or vod.get('vod_play_list', [])

        froms = []
        urls = []

        for item in vod_play_list:
            player = item.get('player_info', {})
            parse = player.get('parse', '')
            ua = player.get('user_agent', '')
            name_urls = []
            for u in item.get('urls', []):
                name = u.get('name', '')
                play_url = u.get('url', '')
                token = u.get('token', '')
                parse_api = u.get('parse_api_url', '')
                nid = u.get('nid', 1)
                # 格式: name$url@@parse@@token@@parse_api@@ua@@vid@@nid
                name_urls.append(f"{name}${play_url}@@{parse}@@{token}@@{parse_api}@@{ua}@@{vid}@@{nid}")
            froms.append(player.get('show', 'Unknown'))
            urls.append('#'.join(name_urls))

        # 兜底：如果 vod_play_list 为空，尝试 vod 里的直接字段
        if not froms and vod.get('vod_play_from'):
            froms = vod.get('vod_play_from', '').split('$$$')
            urls = vod.get('vod_play_url', '').split('$$$')

        # show 名去重（同名加数字后缀）
        show_count = {}
        new_froms = []
        for f in froms:
            if f in show_count:
                show_count[f] += 1
                new_froms.append(f"{f}{show_count[f]}")
            else:
                show_count[f] = 1
                new_froms.append(f)
        froms = new_froms

        return {
            'list': [{
                'vod_id': vod.get('vod_id', ''),
                'vod_name': vod.get('vod_name', ''),
                'vod_pic': vod.get('vod_pic', ''),
                'type_name': vod.get('vod_class', ''),
                'vod_year': vod.get('vod_year', ''),
                'vod_area': vod.get('vod_area', ''),
                'vod_remarks': vod.get('vod_remarks', ''),
                'vod_actor': vod.get('vod_actor', ''),
                'vod_director': vod.get('vod_director', ''),
                'vod_content': vod.get('vod_content', ''),
                'vod_play_from': '$$$'.join(froms),
                'vod_play_url': '$$$'.join(urls)
            }]
        }

    def playerContent(self, flag, id, vipFlags=None):
        parts = id.split('@@')
        play_url = parts[0] if parts else ''
        parse = parts[1] if len(parts) > 1 else ''
        token = parts[2] if len(parts) > 2 else ''
        parse_api_url = parts[3] if len(parts) > 3 else ''
        ua = parts[4] if len(parts) > 4 else ''
        vid = parts[5] if len(parts) > 5 else ''
        nid = parts[6] if len(parts) > 6 else '1'

        # 直链
        if play_url.startswith('http') and ('m3u8' in play_url or 'mp4' in play_url or 'mkv' in play_url) and not parse_api_url:
            result = {'parse': 0, 'url': play_url}
            if ua:
                result['header'] = {'User-Agent': ua}
            return result

        # 外部解析接口
        if parse.startswith('http'):
            purl = parse + play_url
            if token:
                purl += '&token=' + token
            h = dict(self.headers)
            if ua:
                h['User-Agent'] = ua
            r = requests.get(purl, headers=h, timeout=15)
            text = r.text
            if '<!DOCTYPE html>' in text or '<html>' in text:
                result = {'parse': 1, 'url': purl}
                if ua:
                    result['header'] = {'User-Agent': ua}
                return result
            try:
                j = r.json()
                result = {'parse': 0, 'url': j.get('url') or j.get('data', {}).get('url', '')}
                if ua:
                    result['header'] = {'User-Agent': ua}
                return result
            except:
                result = {'parse': 1, 'url': purl}
                if ua:
                    result['header'] = {'User-Agent': ua}
                return result

        # 本地解析
        url = f"{self.siteUrl}/{self.apiPrefix}/vodParse"
        params = {
            'parse_api': parse,
            'url': self._aes_encode(play_url, self.key, self.iv),
            'token': token,
        }
        h = dict(self.headers)
        if ua:
            h['User-Agent'] = ua
        ret = self._request(url, params, h)
        enc_data = ret.get('data', '')
        if enc_data:
            decoded = self._aes_decode(enc_data, self.key, self.iv)
            parsed = json.loads(decoded)
            final = json.loads(parsed.get('json', '{}'))
            result = {'parse': 0, 'url': final.get('url', '')}
            if ua:
                result['header'] = {'User-Agent': ua}
            return result
        return {'parse': 0, 'url': play_url}

    def searchContent(self, key, quick=False, pg="1"):
        self._check_init()
        pg = int(pg) if str(pg).isdigit() else 1
        url = f"{self.siteUrl}/{self.apiPrefix}/{self.searchApiSuffix}"
        params = {
            'page': str(pg),
            'type_id': '0',
            'keywords': key,
        }
        if self.souParamName and self.souSalt:
            ts = str(int(time.time()))
            sou_str = f"/{self.souParamName}-{ts}-sb-0-{self.souSalt}"
            md5_val = hashlib.md5(sou_str.encode()).hexdigest()
            params[self.souParamName] = f"{ts}-sb-0-{md5_val}"

        h = dict(self.headers)
        h.update(self.extraSearchHeaders)
        ret = self._request(url, params, h)
        enc_data = ret.get('data', '')
        if not enc_data:
            return {'list': []}
        data = json.loads(self._aes_decode(enc_data, self.key, self.iv))
        videos = data.get('search_list', [])
        return {
            'list': videos,
            'page': pg,
            'pagecount': 9999,
            'limit': len(videos),
            'total': len(videos)
        }

    def localProxy(self, param):
        return [404, 'text/plain', b'']
