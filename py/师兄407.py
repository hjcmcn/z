#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 大师兄影视 v4.0.7 (zde) - 2026-10-28 沙箱实测, 由 v4.0.8 版原样改参 (只改下面 6 处参数 + 协议面补齐 + covip 解析分支, 其余逻辑一字不动)
# APK: _____-v4.0.7.apk_0_aeqv.1 (44,107,201 字节), 包名 com.suishenji.cdscc.zde, 应用名 大师兄影视
# API: http://app2.dsx.ac/ndsx.php/v7/logs (沙箱 DNS 毒化, 实测走真实 IP 178.107.143.4; 设备端正常解析域名即可, 成品不写死 IP)
# 密钥: key = md5(build_time + "^~!@#[-" + pkg) 原始 16 字节; 请求体 = base64url(iv + AES-CBC-PKCS7(明文JSON)); 明文 = {"method":..., "data":..., "csrf":毫秒戳}
#   注意: build-time 沿用 v4.0.8 的 1791599166397, 沙箱实测 zde 包下 nav/video_list/video_detail/search 均回 code=1,
#   说明服务端不严格校验 build-time 与包名是否匹配 (v4.0.7 真实 build-time 未在 APK 明文串中找到, 属 Dart 代码内整型常量).
#   同理 sign_md5/apk_length/apk_path 沿用 v4.0.8 值, 详情在 zde 下同样通过; extend 可覆盖 api/sign_md5/apk_length (见 init).
# 播放线实测 (2026-10-28 沙箱):
#   BBA (短剧/AI漫剧主力): bt.php 解析 -> onewsvod.com MP4, 首集+第77集均验 ftyp isom, 可播.
#   covip (独家5, 多数影片默认首线): 本版新增分支, 走详情给的 extra_parse_api (coffee.1ljx.com) -> 新鲜 m3u8;
#     正片已验到分片字节: m3u8 200 真 #EXTM3U, 首分片首字节 0x47 且 188 网格齐全, 可播.
#     普通话轨: 清单可取但其分片宿主 cibn-edge-5g.1ljx.com 回 402 (源站问题, 非蜘蛛问题, 有/无 Referer 均 402).
#     注意 coffee 链接带时效 auth_key, 须现取现播, 旧链接会 302 到失效部署 (402 DEPLOYMENT_DISABLED).
#   xiguam3u8/bfzym3u8: 直链 m3u8 已拿到 (svip.xgplay17.com), 但沙箱拉流 RemoteDisconnected (CDN 拒沙箱出口), 设备端待验.
#   seven/Dong/Ksvideo/qsvip: xx.php 回 RSA 密文 (base64 解出 256/384/512 字节二进制), 本代码不含 RSA 解密, 暂不可播 (v4.0.8 版同款局限, 非本版回归);
#     仅有 Dong/Ksvideo 两线的影片 (如 爱尔兰灰烬/魔法农场) 目前无可播线, 须等 RSA 解密攻克或等新线.
#   qq/bytedance/mgtv/NBY/Ace/lzm3u8/dsxzb: 沿用 v4.0.8 原逻辑, 本轮未逐一重验.
# 传输说明: 本文件沿用 v4.0.8 版 urllib 栈 (设备已验的传输层, 不换成 requests 以免引入未验证变量);
#   Accept-Encoding 仅 gzip (无 br), HTTPS 用 unverified context, import 时不建网络对象.

import re
import sys
import json
import time
import base64
import hashlib
import gzip
import ssl
import urllib.request
import urllib.error
import urllib.parse

try:
    sys.path.append("..")
    sys.path.append("../../")
except Exception:
    pass

try:
    from base.spider import Spider as _BaseSpider
except ImportError:
    class _BaseSpider(object):
        def init(self, extend=""):
            pass

_HTTP_INSECURE_CTX = None
try:
    _HTTP_INSECURE_CTX = ssl._create_unverified_context()
except Exception:
    _HTTP_INSECURE_CTX = None

# =================== 站点配置 ===================
API_HOSTS = ['app2.dsx.ac']
API_PATH = '/ndsx.php/v7/logs'
PKG = 'com.suishenji.cdscc.zde'
BUILD_TIME = '1791599166397'  # 沿用 v4.0.8 值, zde 下实测 code=1 (见头注释)
APP_VERSION = '4.0.7'
VERSION_CODE = '4007'
PLATFORM_VER = 'CP2A.260605.016'
SIGN_MD5 = '41167263796ca047e0b4cb57ba67a388'
APK_LENGTH = 44160353
APK_PATH = '/data/app/~~6GQJgNwL7YmiMN0338Upuw==/com.suishenji.cdscc.zft-ud3NDvW5FJIYeCR1HSom9g==/base.apk'

UA_API = 'Dart/3.13 (dart:io)'
UA_PLAY = 'Mozilla/5.0 (Linux; Android 13) Chrome/120 Mobile Safari/537'

BT_API = 'http://202.189.6.83:12991/xx/bt.php?url='
YPARSE_API = 'https://yparse.ik9.cc/index.php?url='
NIUMA_API = 'https://nm.4688888.xyz/niuma.php?key=dfl&url='

SUPPORT_CODES = {'BBA': '独家1', 'xiguam3u8': '大师兄', 'bfzym3u8': '澳门人脉-勿信广告',
                 'Ace': '独家3', 'qsvip': '独家4', 'qingshan': '独家6', 'IMDB': '独家7',
                 'dsxzb': '直播',
                 'seven': '独家2', 'Dong': '独家5', 'bytedance': '独家8',
                 'Ksvideo': '独家9', 'qiyi': '奇艺', 'qq': 'TX'}
LIVE_API = 'https://cn2.globa1.nmtv.icu/live/?key=u41QJorpBYhqc8FA&url='
XX_MAIN = 'http://202.189.6.83:12991/xx/%s?url='
XX_MIRROR = 'http://191.101.132.92/xx/%s?url='
XX_LINES = {'Ace': ('ace.php', 'MR'),
            'qsvip': ('xd.php', 'RM'), 'qingshan': ('xd.php', 'RM'), 'IMDB': ('xd.php', 'RM')}
_PLAY_CACHE = {}
MCDN_CODES = {'xiguam3u8', 'bfzym3u8'}
MCDN_RELAYS = ['http://202.189.6.83:9222/?url=', 'http://191.101.132.92:1899/?url=']
WEB_CODES = {'qq': 'TX', 'bytedance': '独家8', 'qiyi': '奇艺', 'youku': 'YK'}
_JX_API = ''
RSA_CODES = {'seven': '独家2', 'Dong': '独家5', 'bytedance': '独家8', 'Ksvideo': '独家9',
             'qiyi': '奇艺', 'qq': 'TX'}
_PARSE_API_CACHE = {}

_TIMEOUT = 12
_NEG_HOST_UNTIL = 0

_STAT = {'api': 0, 'api_ok': 0, 'api_err': 0, 'bt': 0, 'bt_ok': 0, 'bt_err': 0,
         'seg': 0, 'seg_ok': 0, 'web': 0, 'web_ok': 0, 'web_err': 0,
         'rsa': 0, 'rsa_ok': 0, 'rsa_err': 0, 'last': ''}
VERSION = 'v4.0.7'


def _st(key, ok=None):
    _STAT[key] = _STAT.get(key, 0) + 1
    if ok is not None:
        _STAT[key + ('_ok' if ok else '_err')] = _STAT.get(key + ('_ok' if ok else '_err'), 0) + 1


def _quote_url(u):
    try:
        if u and not u.startswith('http'):
            return u
        return urllib.parse.quote(u, safe=':/?&=%#$+,@[]!')
    except Exception:
        return u


def _telemetry():
    return ('[大师兄%s] api {api_ok}/{api} bt {bt_ok}/{bt} web {web_ok}/{web} '
            'rsa {rsa_ok}/{rsa} 探活 {seg_ok}/{seg} {last}').format(
            **dict(_STAT, last=_STAT['last'] or 'ok')) % VERSION


def _aes_gen_tables():
    sbox = [0] * 256
    p = q = 1
    while True:
        p = p ^ ((p << 1) & 0xff) ^ (0x1b if p & 0x80 else 0)
        q ^= (q << 1) & 0xff
        q ^= (q << 2) & 0xff
        q ^= (q << 4) & 0xff
        if q & 0x80:
            q ^= 0x09
        x = (q ^ ((q << 1) | (q >> 7)) ^ ((q << 2) | (q >> 6)) ^
             ((q << 3) | (q >> 5)) ^ ((q << 4) | (q >> 4)))
        sbox[p] = (x ^ 0x63) & 0xff
        if p == 1:
            break
    sbox[0] = 0x63
    return sbox


_SBOX = _aes_gen_tables()
_RCON = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1b, 0x36]


def _aes_xt(a):
    return ((a << 1) ^ 0x1b) & 0xff if a & 0x80 else (a << 1)


def _aes_gmul(a, n):
    r = 0
    while n:
        if n & 1:
            r ^= a
        a = _aes_xt(a)
        n >>= 1
    return r & 0xff


def _aes_key_expand(key):
    w = [list(key[i * 4:i * 4 + 4]) for i in range(4)]
    for i in range(4, 44):
        t = list(w[i - 1])
        if i % 4 == 0:
            t = t[1:] + t[:1]
            t = [_SBOX[b] for b in t]
            t[0] ^= _RCON[i // 4 - 1]
        w.append([a ^ b for a, b in zip(w[i - 4], t)])
    return [bytes(sum((w[r * 4 + c] for c in range(4)), [])) for r in range(11)]


def _aes_shift_rows(s):
    o = list(s)
    for r in range(1, 4):
        for c in range(4):
            o[((c - r) % 4) * 4 + r] = s[c * 4 + r]
    return o


def _aes_mix_cols(s):
    o = []
    for c in range(4):
        a, b, cc, d = s[c * 4:c * 4 + 4]
        o += [_aes_gmul(a, 2) ^ _aes_gmul(b, 3) ^ cc ^ d,
              a ^ _aes_gmul(b, 2) ^ _aes_gmul(cc, 3) ^ d,
              a ^ b ^ _aes_gmul(cc, 2) ^ _aes_gmul(d, 3),
              _aes_gmul(a, 3) ^ b ^ cc ^ _aes_gmul(d, 2)]
    return o


def _aes_encrypt_block(blk, rk):
    s = [a ^ b for a, b in zip(blk, rk[0])]
    for r in range(1, 10):
        s = [_SBOX[b] for b in s]
        s = _aes_shift_rows(s)
        s = _aes_mix_cols(s)
        s = [a ^ b for a, b in zip(s, rk[r])]
    s = [_SBOX[b] for b in s]
    s = _aes_shift_rows(s)
    return bytes(a ^ b for a, b in zip(s, rk[10]))


def _aes_encrypt(data, key, iv):
    rk = _aes_key_expand(key)
    pad = 16 - len(data) % 16
    data = data + bytes([pad]) * pad
    out, prev = [], iv
    for i in range(0, len(data), 16):
        blk = bytes(a ^ b for a, b in zip(data[i:i + 16], prev))
        eb = _aes_encrypt_block(blk, rk)
        out.append(eb)
        prev = eb
    return b''.join(out)


_REQ_KEY = hashlib.md5(('%s^~!@#[-%s' % (BUILD_TIME, PKG)).encode()).digest()


def _b64u_enc(b):
    return base64.urlsafe_b64encode(b).decode().rstrip('=')


def _log_en(obj):
    plain = json.dumps(obj, separators=(',', ':'), ensure_ascii=False).encode()
    iv = ('%016x' % (int(time.time() * 1000) & 0xffffffffffffffff))[:16].encode()
    return _b64u_enc(iv + _aes_encrypt(plain, _REQ_KEY, iv))


def _http(url, headers=None, data=None, timeout=_TIMEOUT):
    hd = {'User-Agent': UA_API, 'Accept-Encoding': 'gzip'}
    if headers:
        hd.update(headers)
    req = urllib.request.Request(url, data=data, headers=hd)
    try:
        r = urllib.request.urlopen(req, timeout=timeout, context=_HTTP_INSECURE_CTX)
        raw = r.read()
        if r.headers.get('Content-Encoding') == 'gzip':
            try:
                raw = gzip.decompress(raw)
            except Exception:
                pass
        return raw.decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        try:
            return e.read().decode('utf-8', 'replace')
        except Exception:
            return ''
    except Exception:
        return ''


_DETAIL_CACHE = {}


def _api(method, data):
    global _NEG_HOST_UNTIL
    if time.time() < _NEG_HOST_UNTIL:
        _STAT['last'] = '域名冷却'
        return {}
    obj = {'method': method, 'data': data, 'csrf': int(time.time() * 1000)}
    body = _log_en(obj).encode()
    headers = {
        'Content-Type': 'text/plain', 'Content-Length': str(len(body)),
        'version': APP_VERSION, 'version-number': VERSION_CODE,
        'pk-id': PKG, 'build-time': BUILD_TIME,
        'platform': 'android', 'platform-version': PLATFORM_VER,
    }
    _st('api')
    saw_empty = False
    for host in API_HOSTS:
        for _try in range(3):
            txt = _http('http://%s%s' % (host, API_PATH), headers=headers, data=body)
            try:
                d = json.loads(txt)
            except Exception:
                d = {}
            if d.get('code') == 1 or (d.get('code') in (2, 3) and d.get('msg')):
                _st('api', True)
                return d
            _st('api', False)
            if not txt:
                saw_empty = True
                continue
            if d:
                _STAT['last'] = 'api:' + str(d.get('msg', ''))[:20]
                return d
    # 手机网络抖动时空响应是常态: 全部尝试耗尽才冷却, 且只冷30秒。
    # 原逻辑是单次空响应即冷120秒, 抖动一次就锁死整个会话, 正是设备端诊断卡的成因。
    if saw_empty:
        _NEG_HOST_UNTIL = time.time() + 30
        _STAT['last'] = 'API域无响应'
    return {}


class Spider(_BaseSpider):
    searchable = 1
    quickSearch = 1
    filterable = 1
    changeable = 1

    _FALLBACK_CLASS = [{'type_id': 1, 'type_name': '电影'}, {'type_id': 2, 'type_name': '剧集'},
                       {'type_id': 3, 'type_name': '综艺'}, {'type_id': 4, 'type_name': '动漫'},
                       {'type_id': 63, 'type_name': '短剧'}, {'type_id': 62, 'type_name': '少儿'}]

    def __init__(self):
        pass

    def getName(self):
        return '大师兄影视'

    def init(self, extend=""):
        try:
            ext = (extend or "").strip()
            if ext.startswith("{"):
                c = json.loads(ext)
                for k in ('api', 'sign_md5', 'apk_length'):
                    if c.get(k):
                        v = c[k]
                        globals()['API_HOSTS' if k == 'api' else k.upper()] = (
                            [v] if isinstance(v, str) and k == 'api' else v)
                global _JX_API
                jx = str(c.get('jxapi') or '').strip()
                if jx.startswith('http'):
                    _JX_API = jx if jx.endswith('=') else jx + '='
                if 'yparse' in c:
                    yp = str(c.get('yparse') or '').strip()
                    if yp == '':
                        globals()['YPARSE_API'] = ''
                    elif yp.startswith('http'):
                        globals()['YPARSE_API'] = yp if yp.endswith('=') else yp + '='
                if 'niuma' in c:
                    nm = str(c.get('niuma') or '').strip()
                    if nm == '':
                        globals()['NIUMA_API'] = ''
                    elif nm.startswith('http'):
                        globals()['NIUMA_API'] = nm if nm.endswith('=') else nm + '='
        except Exception:
            pass

    def homeContent(self, filter=True):
        try:
            nav = _api('nav', {'token': ''})
            classes, filters = [], {}
            for t in (nav.get('data') or []):
                tid = t.get('type_id')
                tname = t.get('type_name', '')
                classes.append({'type_id': tid, 'type_name': tname})
                te = t.get('type_extend') or {}
                fl = []
                for key, name in (('class', '类型'), ('area', '地区'),
                                  ('lang', '语言'), ('year', '年份')):
                    vals = str(te.get(key, '') or '').split(',')
                    vals = [v for v in vals if v.strip()]
                    if vals:
                        fl.append({'key': key, 'name': name,
                                   'value': [{'n': '全部', 'v': ''}] +
                                            [{'n': v, 'v': v} for v in vals]})
                if fl:
                    filters[str(tid)] = fl
            if classes:
                lst = self._video_list(1, 1) or []
            else:
                classes = [dict(c) for c in self._FALLBACK_CLASS]
                lst = [{'vod_id': 'diag', 'vod_name': '[诊断] API未通 ' + _telemetry(),
                        'vod_pic': '', 'vod_remarks': _telemetry(),
                        'vod_content': '接口连不上: 先截图此卡发我; 稍后重进自动重试'}]
            return {'class': classes, 'filters': filters, 'list': lst}
        except Exception as e:
            return {'class': [dict(c) for c in self._FALLBACK_CLASS], 'filters': {},
                    'list': [{'vod_id': 'diag', 'vod_name': '[诊断] home异常',
                              'vod_pic': '', 'vod_remarks': _telemetry(),
                              'vod_content': 'homeContent: %s' % str(e)[:80]}]}

    @staticmethod
    def _diag_card(tag, err=''):
        msg = ('%s %s' % (err, _telemetry())).strip()
        return {'vod_id': 'diag', 'vod_name': '[诊断] %s未取到' % tag,
                'vod_pic': '', 'vod_remarks': msg[:80] or 'ok',
                'vod_content': '持续显示此卡请截图发我(含下方状态行)。\n%s' % _telemetry()}

    def homeVideoContent(self):
        try:
            lst = self._video_list(1, 1)
            return {'list': lst if lst else [self._diag_card('首页推荐')]}
        except Exception as e:
            return {'list': [self._diag_card('首页推荐', str(e))]}

    def categoryContent(self, tid='1', pg='1', filter=False, extend=None):
        try:
            try:
                ext = json.loads(extend or '{}')
            except Exception:
                ext = {}
            try:
                pg = int(pg or 1)
            except Exception:
                pg = 1
            if pg < 1:
                pg = 1
            lst = self._video_list(tid, pg, ext)
            if lst is None:
                return {'list': [self._diag_card('分类')], 'page': pg,
                        'pagecount': 0, 'limit': 20, 'total': 0}
            if not lst:
                return {'list': [], 'page': pg, 'pagecount': max(pg - 1, 0),
                        'limit': 20, 'total': max(pg - 1, 0) * 20}
            pc = pg if len(lst) < 20 else 99999
            return {'list': lst, 'page': pg, 'pagecount': pc, 'limit': 20, 'total': pc * 20}
        except Exception as e:
            return {'list': [self._diag_card('分类', str(e))], 'page': 1,
                    'pagecount': 0, 'limit': 20, 'total': 0}

    def _video_list(self, tid, pg, ext=None):
        ext = ext or {}
        d = _api('video_list', {'pg': int(pg or 1), 'tid': int(tid),
                                'class': ext.get('class', ''), 'area': ext.get('area', ''),
                                'lang': ext.get('lang', ''), 'year': ext.get('year', ''),
                                'token': ''})
        if not d:
            return None
        out = []
        for v in (d.get('data') or []):
            out.append({'vod_id': str(v.get('vod_id')), 'vod_name': v.get('vod_name'),
                        'vod_pic': v.get('vod_pic', ''),
                        'vod_remarks': v.get('vod_remarks', ''),
                        'type_id': tid})
        return out

    @staticmethod
    def _search_keys(key):
        key = str(key or '').strip()
        keys = [key] if key else []
        if len(key) > 2:
            c = re.sub(r'[\s:：·,，.。!！?？~～\-_—《》【】\[\]()（）\'"]+', '', key)
            if c and c not in keys:
                keys.append(c)
            toks = [t for t in re.split(r'[\s:：·,，.。!！?？~～\-_—《》【】\[\]()（）\'"]+', key) if t]
            cjk = sorted((t for t in toks if re.search(r'[\u4e00-\u9fff]', t) and len(t) >= 2),
                         key=len, reverse=True)
            for t in cjk[:2]:
                if t not in keys:
                    keys.append(t)
        return keys[:4]

    def searchContent(self, key='', quick=False, pg=1):
        try:
            out, seen = [], set()
            for k in self._search_keys(key):
                if out and (quick or len(out) >= 5):
                    break
                d = _api('search', {'text': k, 'pg': int(pg or 1), 'token': ''})
                for v in (d.get('data') or []):
                    vid = str(v.get('vod_id'))
                    if vid in seen:
                        continue
                    seen.add(vid)
                    out.append({'vod_id': vid, 'vod_name': v.get('vod_name'),
                                'vod_pic': v.get('vod_pic', ''),
                                'vod_remarks': v.get('vod_remarks', '')})
            if not out:
                out = [{'vod_id': 'diag', 'vod_name': '[诊断] 搜索无结果 ' + key,
                        'vod_pic': '', 'vod_remarks': _telemetry()}]
            return {'list': out}
        except Exception as e:
            return {'list': [{'vod_id': 'diag', 'vod_name': '[诊断] 搜索异常 ' + key,
                              'vod_pic': '', 'vod_remarks': str(e)[:60]}]}

    def searchContentPage(self, key, quick=False, pg=1):
        return self.searchContent(key, quick, pg)

    def _detail(self, vid):
        key = str(vid)
        hit = _DETAIL_CACHE.get(key)
        if hit and time.time() - hit[0] < 1800:
            return hit[1]
        d = _api('video_detail', {'id': int(vid), 'sign_md5': SIGN_MD5,
                                  'apk_path': APK_PATH, 'apk_length': APK_LENGTH,
                                  'token': ''})
        vi = (d.get('data') or {}).get('vod_info')
        if not vi:
            return None
        if len(_DETAIL_CACHE) > 200:
            _DETAIL_CACHE.clear()
        _DETAIL_CACHE[key] = (time.time(), vi)
        return vi

    def detailContent(self, ids):
        vid = str(ids[0]) if isinstance(ids, (list, tuple)) and ids else str(ids)
        if vid == 'diag' or not vid.isdigit():
            return {'list': [self._diag_vod(vid, '诊断卡', '这是诊断卡片, 不是影片。')]}
        try:
            vi = self._detail(vid)
        except Exception as e:
            return {'list': [self._diag_vod(vid, '详情异常', str(e)[:80])]}
        if not vi:
            return {'list': [self._diag_vod(vid, '详情未取到', 'API 状态: ' + _telemetry())]}
        play_from, play_url = [], []
        for p in (vi.get('vod_url_with_player') or []):
            code = str(p.get('code', ''))
            url = str(p.get('url', ''))
            if not url:
                continue
            eps = [e for e in url.split('#') if '$' in e]
            if not eps:
                continue
            neweps = []
            for i, e in enumerate(eps):
                name, _u = e.split('$', 1)
                neweps.append('%s$%s|%s|%d' % (name, vid, code, i))
            play_from.append(str(p.get('name') or '') or code)
            play_url.append('#'.join(neweps))
        if not play_url:
            play_url = ['无线路$none']
            play_from = ['提示']
        vod = {
            'vod_id': vid, 'vod_name': vi.get('vod_name'),
            'vod_pic': vi.get('vod_pic', ''),
            'type_name': vi.get('vod_class', ''),
            'vod_year': vi.get('vod_year', ''),
            'vod_area': vi.get('vod_area', ''),
            'vod_actor': vi.get('vod_actor', ''),
            'vod_director': vi.get('vod_director', ''),
            'vod_content': re.sub(r'<[^>]+>', '', str(vi.get('vod_blurb') or vi.get('vod_content') or '')),
            'vod_remarks': vi.get('vod_remarks', ''),
            'vod_play_from': '$$$'.join(play_from),
            'vod_play_url': '$$$'.join(play_url),
        }
        return {'list': [vod]}

    @staticmethod
    def _diag_vod(vid, title, text):
        return {'vod_id': vid, 'vod_name': '%s %s' % (title, VERSION),
                'vod_pic': '', 'type_name': '', 'vod_year': '', 'vod_area': '',
                'vod_actor': '', 'vod_director': '',
                'vod_content': text + '\nAPI 状态: ' + _telemetry() + '\n若持续显示此卡请截图发我。',
                'vod_remarks': _telemetry(),
                'vod_play_from': '提示', 'vod_play_url': '无线路$diag'}

    def _get_parse_apis(self, vi, code):
        cached = _PARSE_API_CACHE.get(code)
        if cached:
            return cached
        main_api, extra_api = '', ''
        for p in ((vi or {}).get('vod_url_with_player') or []):
            if str(p.get('code')) == code:
                main_api = str(p.get('parse_api') or '')
                extra_api = str(p.get('extra_parse_api') or '')
                break
        result = (main_api, extra_api)
        _PARSE_API_CACHE[code] = result
        return result

    def _try_rsa_resolve(self, vi, code, target):
        _st('rsa')
        main_api, extra_api = self._get_parse_apis(vi, code)
        apis = []
        if main_api:
            apis.append(main_api)
        if extra_api and extra_api != main_api:
            apis.append(extra_api)
        for api_base in apis:
            try:
                txt = _http(api_base + target, headers={'User-Agent': UA_API}, timeout=10)
                if not txt:
                    continue
                if txt.strip().startswith('{'):
                    j = json.loads(txt)
                    u = str(j.get('url') or '')
                    if str(j.get('code')) in ('200', '1') and u.startswith('http'):
                        _st('rsa', True)
                        return _quote_url(u)
                    _STAT['last'] = 'rsa:%s code=%s' % (code, j.get('code'))
                else:
                    _STAT['last'] = 'rsa:%s 密文(RSA)' % code
            except Exception:
                continue
        _st('rsa', False)
        return ''

    def _find_web_url(self, vi, idx):
        players = (vi or {}).get('vod_url_with_player') or []
        priority = ['qiyi', 'qq', 'youku', 'bytedance']
        for code in priority:
            for p in players:
                if str(p.get('code')) != code:
                    continue
                raw = str(p.get('url', ''))
                eps = [e for e in raw.split('#') if '$' in e]
                if idx >= len(eps):
                    break
                target = eps[idx].split('$', 1)[1]
                if target.startswith('http'):
                    return code, target
        return None

    def _resolve_line(self, vi, code, idx):
        raw = ''
        for p in ((vi or {}).get('vod_url_with_player') or []):
            if str(p.get('code')) == code:
                raw = str(p.get('url', ''))
                break
        eps = [e for e in raw.split('#') if '$' in e]
        if idx >= len(eps):
            return ''
        target = eps[idx].split('$', 1)[1]
        if not target:
            return ''
        try:
            if code == 'BBA':
                u = self._play_eth(target)
            elif code in XX_LINES:
                u = self._xx_resolve(code, target)
            elif code in RSA_CODES:
                u = self._try_rsa_resolve(vi, code, target)
            elif target.startswith('http') and self._looks_webpage(target):
                u = self._resolve_web_page(target)
            else:
                u = _quote_url(target)
        except Exception:
            return ''
        if u and u.startswith('http') and self._verify_level(u) == 0:
            _STAT['last'] = '%s假直链' % code
            return ''
        return u

    _FALLBACK_ORDER = ('BBA', 'Ace', 'xiguam3u8', 'qsvip', 'qingshan', 'IMDB', 'bfzym3u8')
    _SWAP_CACHE = {}

    @staticmethod
    def _norm_name(n):
        return re.sub(r'[\s:：·,，.。!！?？《》【】\[\]()（）\'"\-—_]+', '', str(n or ''))

    def _swap_source(self, vi, vid, idx):
        try:
            name = self._norm_name((vi or {}).get('vod_name'))
            if not name or len(name) < 2:
                return ''
            ck = (name, idx)
            hit = self._SWAP_CACHE.get(ck)
            if hit and time.time() - hit[0] < 1800:
                return hit[1]
            _STAT['last'] = 'swap:搜索%s' % name[:12]
            sr = self.searchContent(name) or {}
            for it in (sr.get('list') or []):
                cid = str(it.get('vod_id', ''))
                if not cid.isdigit() or cid == vid or self._norm_name(it.get('vod_name')) != name:
                    continue
                try:
                    cvi = self._detail(cid)
                except Exception:
                    continue
                if not cvi:
                    continue
                players = cvi.get('vod_url_with_player') or []
                codes = [str(p.get('code')) for p in players]
                order = [c for c in self._FALLBACK_ORDER if c in codes] + \
                        [c for c in codes if c not in self._FALLBACK_ORDER and c != 'dsxzb']
                for c in order:
                    u = self._resolve_line(cvi, c, idx)
                    if u and self._probe(u, timeout=4):
                        if len(self._SWAP_CACHE) > 200:
                            self._SWAP_CACHE.clear()
                        self._SWAP_CACHE[ck] = (time.time(), u)
                        _STAT['last'] = 'swap→%s#%s' % (cid, c)
                        return u
        except Exception:
            pass
        return ''

    def playerContent(self, flag='', pid='', vipFlags=None):
        ret = {'parse': 0, 'playUrl': '', 'url': '', 'header': '', 'jx': '0'}
        try:
            vid, code, idx = (str(pid).split('|') + ['0', '0'])[:3]
            idx = int(idx)
            vi = self._detail(vid)
            raw = ''
            for p in ((vi or {}).get('vod_url_with_player') or []):
                if str(p.get('code')) == code:
                    raw = str(p.get('url', ''))
                    break
            eps = [e for e in raw.split('#') if '$' in e]
            target = eps[idx].split('$', 1)[1] if idx < len(eps) else ''
            if not target:
                raise ValueError('集地址缺失')
            if code == 'BBA':
                url = self._play_eth(target)
            elif code == 'covip':
                url = self._try_rsa_resolve(vi, code, target)
            elif code in XX_LINES:
                url = self._xx_resolve(code, target)
            elif code == 'dsxzb':
                url = self._live_resolve(vi, target)
            elif code in RSA_CODES:
                url = self._try_rsa_resolve(vi, code, target)
            else:
                if target.startswith('http') and self._looks_webpage(target):
                    real = self._resolve_web_page(target)
                    if real and not self._fmp4_hls(real):
                        ret['url'] = real
                        hd = {'User-Agent': UA_PLAY}
                        if 'mgtv.com' in real:
                            hd['Referer'] = 'https://www.mgtv.com/'
                        ret['header'] = json.dumps(hd)
                        _STAT['last'] = 'webcode→直链:%s' % code
                        return ret
                    self._web_real = real or ''
                    url = ''
                    if not real:
                        ret['parse'] = 1
                        ret['url'] = self._yparse_wrap(target)
                        ret['header'] = json.dumps({'User-Agent': UA_PLAY})
                        _STAT['last'] = 'webcode→yparse:%s' % code
                        return ret
                url = _quote_url(target)
            primary_url = url
            if url and code != 'dsxzb' and self._verify_level(url) == 0:
                _STAT['last'] = '%s线路不可播, 换线兜底' % code
                url = ''
            if not url and code in RSA_CODES:
                for alt in self._FALLBACK_ORDER:
                    if alt == code:
                        continue
                    u2 = self._resolve_line(vi, alt, idx)
                    if u2:
                        url, code = u2, alt
                        _STAT['last'] = 'rsa→fb:%s' % alt
                        break
            if not url and code in RSA_CODES:
                web = self._find_web_url(vi, idx)
                if web:
                    web_code, web_url = web
                    real = self._resolve_web_page(web_url)
                    if real:
                        ret['url'] = real
                        ret['header'] = json.dumps({'User-Agent': UA_PLAY})
                        _STAT['last'] = 'rsa→jx:%s' % web_code
                        return ret
                    ret['parse'] = 1
                    ret['url'] = self._yparse_wrap(web_url)
                    ret['header'] = json.dumps({'User-Agent': UA_PLAY})
                    _STAT['last'] = 'rsa→yparse:%s' % web_code
                    return ret
            if not url:
                for alt in self._FALLBACK_ORDER:
                    if alt == code:
                        continue
                    u2 = self._resolve_line(vi, alt, idx)
                    if u2:
                        url, code = u2, alt
                        _STAT['last'] = 'fb→%s' % alt
                        break
            if not url:
                url = self._swap_source(vi, vid, idx)
                if url:
                    code = 'swap'
            if not url and primary_url:
                url = primary_url
                _STAT['last'] = '全灭退原链'
            if not url and getattr(self, '_web_real', ''):
                url = self._web_real
                self._web_real = ''
                _STAT['last'] = 'fMP4垫底'
            if not url:
                raise ValueError('全线路解析失败')
            if code in WEB_CODES:
                page = target if target.startswith('http') else (
                    'https://www.iesdouyin.com/share/video/' + target)
                real = self._resolve_web_page(page)
                if real:
                    ret['url'] = real
                    ret['header'] = json.dumps({'User-Agent': UA_PLAY})
                else:
                    ret['parse'] = 1
                    ret['url'] = self._yparse_wrap(page)
                    _STAT['last'] = 'web→yparse'
            elif code == 'BBA':
                self._probe(url, timeout=4)
                ret['url'] = url
            elif code in MCDN_CODES:
                if self._probe(url, timeout=2.5):
                    ret['url'] = url
                else:
                    ret['url'] = self._mcdn_relay(target) or url
            else:
                self._probe(url, timeout=4)
                ret['url'] = url
            if not ret['header']:
                ret['header'] = json.dumps({'User-Agent': UA_PLAY})
        except Exception as e:
            _STAT['last'] = 'pc:%s' % str(e)[:40]
            ret['parse'] = 1
            ret['url'] = ''
        return ret

    @staticmethod
    def _looks_webpage(u):
        u = str(u).lower()
        if any(x in u for x in ('.m3u8', '.mp4', '.flv', '.ts', '.mkv')):
            return False
        return ('.html' in u or '.shtml' in u or
                any(d in u for d in ('v.qq.com', 'youku.com', 'iqiyi.com',
                                     'mgtv.com', 'bilibili.com',
                                     'iesdouyin.com', 'douyin.com')))

    @staticmethod
    def _yparse_wrap(page_url):
        yp = globals().get('YPARSE_API') or ''
        if not yp:
            return page_url
        return yp + urllib.parse.quote(page_url, safe='')

    def _m3u8_minutes(self, u):
        try:
            t = _http(u, headers={'User-Agent': UA_PLAY}, timeout=10)
            if 'EXTINF' not in t:
                v = re.findall(r'(https?://\S+\.m3u8\S*)', t)
                if not v:
                    return 999.0
                t = _http(v[0], headers={'User-Agent': UA_PLAY}, timeout=10)
            durs = [float(x) for x in re.findall(r'EXTINF:([\d.]+)', t)]
            return sum(durs) / 60 if durs else 999.0
        except Exception:
            return 999.0

    def _niuma_resolve(self, page_url):
        api = globals().get('NIUMA_API') or ''
        if not api:
            return ''
        key = ('niuma', page_url)
        hit = _PLAY_CACHE.get(key)
        if hit and time.time() - hit[0] < 600:
            return hit[1]
        try:
            _st('niuma')
            txt = _http(api + urllib.parse.quote(page_url, safe=''),
                        headers={'User-Agent': UA_PLAY}, timeout=12)
            j = json.loads(txt or '')
            u = str(j.get('url') or '')
            if str(j.get('code')) == '200' and u.startswith('http'):
                mins = self._m3u8_minutes(u)
                if mins >= 3.0:
                    u = _quote_url(u)
                    if len(_PLAY_CACHE) > 300:
                        _PLAY_CACHE.clear()
                    _PLAY_CACHE[key] = (time.time(), u)
                    _st('niuma', True)
                    return u
                _STAT['last'] = 'niuma试看%.1f分丢弃' % mins
            else:
                _STAT['last'] = 'niuma:%s' % str(j.get('msg') or '')[:16]
        except Exception:
            _STAT['last'] = 'niuma:异常'
        _st('niuma', False)
        return ''

    def _fmp4_hls(self, url):
        try:
            t = _http(url, headers={'User-Agent': UA_PLAY}, timeout=8)
            return ('#EXT-X-MAP' in t) or ('.m4s' in t)
        except Exception:
            return False

    def _resolve_web_page(self, page_url):
        u = self._niuma_resolve(page_url)
        if u:
            return u
        return self._jx_resolve(page_url)

    def _jx_resolve(self, page_url):
        if not _JX_API:
            return ''
        try:
            _st('web')
            txt = _http(_JX_API + _quote_url(page_url),
                        headers={'User-Agent': UA_PLAY}, timeout=20)
            j = json.loads(txt or '')
            u = self._pick_url(j)
            if u and self._media_ok(u):
                _st('web', True)
                return u
            _STAT['last'] = 'jx:' + str(j.get('code'))[:12]
        except Exception:
            _STAT['last'] = 'jx:解析异常'
        _st('web', False)
        return ''

    def _media_ok(self, url, timeout=6):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers={
                'User-Agent': UA_PLAY, 'Range': 'bytes=0-1023'}), timeout=timeout,
                context=_HTTP_INSECURE_CTX)
            ct = (r.headers.get('Content-Type') or '').lower()
            data = r.read(64)
            if not data or len(data) < 8:
                return False
            if 'html' in ct or 'json' in ct:
                return False
            if data[:7] == b'#EXTM3U':
                return True
            if data[:3] == b'FLV' or data[4:8] == b'ftyp' or data[0] in (0x00, 0x47, 0x1A):
                return True
            return any(t in ct for t in ('video/', 'mpegurl', 'octet-stream', 'mp2t', 'mp4'))
        except Exception:
            return False

    @staticmethod
    def _pick_url(obj):
        if isinstance(obj, str):
            return obj if obj.startswith(('http://', 'https://')) else ''
        if isinstance(obj, list):
            for x in obj:
                u = Spider._pick_url(x)
                if u:
                    return u
            return ''
        if not isinstance(obj, dict):
            return ''
        for k in ('url', 'play_url', 'source_url', 'videoUrl', 'video_url'):
            v = obj.get(k)
            if isinstance(v, str) and v.startswith(('http://', 'https://')):
                return v
        for v in obj.values():
            u = Spider._pick_url(v)
            if u:
                return u
        return ''

    def _live_resolve(self, vi, target):
        api = ''
        for p in ((vi or {}).get('vod_url_with_player') or []):
            if str(p.get('code')) == 'dsxzb':
                api = str(p.get('parse_api') or '')
                break
        if not api:
            api = LIVE_API
        try:
            _st('bt')
            txt = _http(api + target, headers={'User-Agent': UA_PLAY}, timeout=12)
            j = json.loads(txt or '')
            u = str(j.get('url') or '')
            if str(j.get('code')) == '200' and u.startswith('http'):
                _st('bt', True)
                return u
            _STAT['last'] = 'live code=%s' % j.get('code')
        except Exception:
            _STAT['last'] = 'live:解析异常'
        _st('bt', False)
        return ''

    def _xx_resolve(self, code, cipher):
        ep, order = XX_LINES.get(code, ('', ''))
        if not ep:
            return ''
        key = (code, cipher)
        hit = _PLAY_CACHE.get(key)
        if hit and time.time() - hit[0] < 600:
            return hit[1]
        for h in order:
            base = (XX_MAIN if h == 'M' else XX_MIRROR) % ep
            try:
                _st('bt')
                txt = _http(base + cipher, headers={'User-Agent': UA_API}, timeout=12)
                j = json.loads(txt or '')
                u = str(j.get('url') or '')
                if str(j.get('code')) == '200' and u.startswith('http'):
                    _st('bt', True)
                    u = _quote_url(u)
                    if len(_PLAY_CACHE) > 300:
                        _PLAY_CACHE.clear()
                    _PLAY_CACHE[key] = (time.time(), u)
                    return u
                _STAT['last'] = 'xx:%s code=%s' % (code, j.get('code'))
            except Exception:
                _STAT['last'] = 'xx:%s 非JSON(RSA?)' % code
                continue
        _st('bt', False)
        return ''

    def _mcdn_relay(self, raw_url):
        for relay in MCDN_RELAYS:
            try:
                txt = _http(relay + _quote_url(raw_url),
                            headers={'User-Agent': UA_PLAY}, timeout=10)
                j = json.loads(txt or '')
                mu = str(j.get('url') or '')
                if mu and self._probe(mu, timeout=4):
                    _st('bt', True)
                    return mu
            except Exception:
                continue
        _st('bt', False)
        return ''

    def _play_eth(self, eth):
        _st('bt')
        txt = _http(BT_API + eth, timeout=15)
        try:
            j = json.loads(txt)
            if j.get('code') == 200 and j.get('url'):
                _st('bt', True)
                u = str(j['url'])
                return 'https://' + u[7:] if u.startswith('http://') else u
            _STAT['last'] = 'bt:' + str(j.get('msg', ''))[:24]
        except Exception:
            _STAT['last'] = 'bt:密文响应'
        _st('bt', False)
        return ''

    def _mp4_seconds(self, url):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': UA_PLAY, 'Range': 'bytes=0-98303'})
            r = urllib.request.urlopen(req, timeout=8, context=_HTTP_INSECURE_CTX)
            d = r.read(98304)
            i = d.find(b'mvhd')
            if i < 0 or i + 36 > len(d):
                return -1
            ver = d[i + 4]
            if ver == 1:
                ts = int.from_bytes(d[i + 24:i + 28], 'big')
                du = int.from_bytes(d[i + 28:i + 36], 'big')
            else:
                ts = int.from_bytes(d[i + 16:i + 20], 'big')
                du = int.from_bytes(d[i + 20:i + 24], 'big')
            if ts > 0:
                return du / float(ts)
        except Exception:
            pass
        return -1

    def _verify_level(self, url, timeout=5):
        try:
            if 'preview=true' in url:
                return 0
            r = urllib.request.urlopen(urllib.request.Request(url, headers={
                'User-Agent': UA_PLAY, 'Range': 'bytes=0-98303'}),
                timeout=timeout, context=_HTTP_INSECURE_CTX)
            ct = (r.headers.get('Content-Type') or '').lower()
            data = r.read(98304)
            if not data or len(data) < 16:
                return 0
            if 'html' in ct or 'json' in ct:
                return 0
            if data[:7] == b'#EXTM3U' or '.m3u8' in url:
                return 2 if self._m3u8_minutes(url) >= 1.0 else 0
            if data[4:8] == b'ftyp':
                sec = self._mp4_seconds(url)
                if sec < 0:
                    return 1
                return 2 if sec >= 45.0 else 0
            if data[:3] == b'FLV' or data[0] in (0x47, 0x1A):
                return 2
            if any(x in ct for x in ('video/', 'mpegurl', 'octet-stream', 'mp2t', 'mp4')):
                return 1
            return 0
        except urllib.error.HTTPError as e:
            return 0 if e.code in (404, 410) else 1
        except Exception:
            return 0

    def _probe(self, url, timeout=6):
        try:
            _st('seg')
            req = urllib.request.Request(url, headers={
                'User-Agent': UA_PLAY, 'Range': 'bytes=0-1023'})
            r = urllib.request.urlopen(req, timeout=timeout, context=_HTTP_INSECURE_CTX)
            data = r.read(16)
            ok = r.status in (200, 206) and len(data) >= 8
            _st('seg', ok)
            if not ok:
                _STAT['last'] = '探活空响应'
            return ok
        except urllib.error.HTTPError as e:
            dead = e.code in (404, 410)
            _st('seg', not dead)
            _STAT['last'] = '探活%d' % e.code
            return not dead
        except Exception:
            _st('seg', False)
            _STAT['last'] = '探活超时'
            return False

    def isVideoFormat(self, url):
        try:
            u = str(url).lower()
            return ('.m3u8' in u) or ('.mp4' in u)
        except Exception:
            return False

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return [404, 'text/plain', b'not found']

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        return lambda *a, **k: None

    def close(self):
        self.destroy()

    def proxy(self, param):
        return self.localProxy(param)

    def destroy(self):
        _DETAIL_CACHE.clear()

    def liveContent(self, url=''):
        return ''

    def getDependence(self):
        return ''

    def download(self, param):
        return None

    def isVPAYard(self, url):
        return False

    def getHomeContent(self, filter=True):
        return self.homeContent(filter)

    def getCategoryContent(self, tid='1', pg='1', filter=False, extend=None):
        return self.categoryContent(tid, pg, filter, extend)

    def getDetailContent(self, ids):
        return self.detailContent(ids)

    def getSearchContent(self, key, quick=False, pg=1):
        return self.searchContent(key, quick, pg)

    def getPlayerContent(self, flag, pid, vipFlags=None):
        return self.playerContent(flag, pid, vipFlags)


_spider_instance = None


def _get_spider():
    global _spider_instance
    if _spider_instance is None:
        _spider_instance = Spider()
        try:
            _spider_instance.init()
        except Exception:
            pass
    return _spider_instance


def getName():
    return _get_spider().getName()


def init(extend=""):
    return _get_spider().init(extend)


def homeContent(filter=True):
    return _get_spider().homeContent(filter)


def homeVideoContent():
    return _get_spider().homeVideoContent()


def categoryContent(tid, pg, filter=False, extend=None):
    return _get_spider().categoryContent(tid, pg, filter, extend)


def detailContent(ids):
    return _get_spider().detailContent(ids)


def searchContent(key, quick=False, pg=1):
    return _get_spider().searchContent(key, quick, pg)


def searchContentPage(key, quick=False, pg=1):
    return _get_spider().searchContentPage(key, quick, pg)


def playerContent(flag, pid, vipFlags=None):
    return _get_spider().playerContent(flag, pid, vipFlags)


def isVideoFormat(url):
    return _get_spider().isVideoFormat(url)


def manualVideoCheck():
    return False


def localProxy(param):
    return [404, 'text/plain', b'not found']
