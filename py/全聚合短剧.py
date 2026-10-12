import base64
import hashlib
import hmac
import json
import re
import sys
import time
import uuid
from urllib.parse import urlencode, quote, unquote
from datetime import datetime

import requests
try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass

sys.path.append('..')
from base.spider import Spider

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad, unpad
except Exception:
    AES = None
    pad = None
    unpad = None

try:
    from cryptography.hazmat.primitives import serialization, hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.backends import default_backend
    cryptography_available = True
except Exception:
    cryptography_available = False

try:
    from Crypto.PublicKey import RSA
    from Crypto.Signature import pkcs1_15
    from Crypto.Hash import SHA256
except Exception:
    RSA = None
    pkcs1_15 = None
    SHA256 = None

class Spider(Spider):
    siteName = '聚合短剧'

    def __init__(self, extend=''):
        try:
            super().__init__()
        except Exception:
            pass
        self.session = requests.Session()
        self.timeout = 10
        self.xingya_headers = {}
        self.niuniu_headers = {}
        self.niuniu_token = ''
        self.niuniu_access_token = ''
        self.sh_token = ''
        self.xifu_categories = []
        
        self.mobileUA = 'Mozilla/5.0 (Linux; Android 10; SM-G970F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Mobile Safari/537.36'

        self.yimi_privateKey = '''-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDwCPsMptVn80Im4VVfJ2uAkjs7NpJzzsyGxleK1uN9ux/KTiY2o8kiXcRIcAYVChfdX4ywUs0jrjh8iTcC91r6qgeBaDS8wWsL5bZrn7O/8sqq2hbizV4AvvsqhxVJzRUJZjbNOcMZOPJoeL5K4U4YsiOyV8a9lt5C6zEC4Qy0xjscvOTGyVTqtWeJedEedXtiKLQxAiy6OKJxyHQqdwMHUfAgAbLzAHcVpg1RSXwud+5vtTJNXOXT98FHoFDcRIEcHiiqfU9dskzAhG2nPbFujO+YFq9tZBrWmrhPaXcHfXZqtEYePM4vuvMYjhmANdG4Ehl6pN9nuEaLZ+L35/3nAgMBAAECggEBAOe+M+s2E2ll8WMqQEs6+s5J4Ee9201Vxh8E1TYlW8Ni60FdjAVKwgCc+Mla5nRfp0TCYElH1+hv5vdNXsBNYhgKGm701Z27O4dkA2gK6vcSCFtFbb0Qu4YK3OFlQ8dZ6cqGVbhz4Qmz8k2s7UPMHKM5Mb+YgTc/tlxzR4FZF/RaY8MDpv6iMcXPY27xJzZAV1jROCXjZTZNYbgjsKDAbthRDkjMyuKCIdq7rAHrEyFSx3n7/uxnZYh42bXzWyyWudbkAJoq1ZYx+NyYj5TsN/WNoYbCPcX0Ko+CNnpkC/6qtQbHrBiMprnld67qdLCVhWpmOBYukXVPwFMJjOFlYKkCgYEA+WDh3LpitYSO6hn7mhnbqEQba13cutbJW9RQa0BjGf1OGXdqXpimcWK7viZYAKhLlyGWQmoWduDq4bjSRx7ZxY8pMtpIUWoVkKItD7D2yvmYN1guHNRpHlUIAsSH3HGwQIeXy36hJcB5gC+3XgRVPz/juTMWJDC0usECNFz17bsCgYEA9miWi6JPnZ1ffQzAyE+P6vGC/Vrl7Uyr9gqxI/OkZa8bUqfZtGo5UDGSaGRUsoTsYiEJ8m5blPY0X4xr5x1kO6rfk0gHxn1OXlCP42yT2+CqQvjNO2DHOnWNryKjmAqaAITbmC2lgj0PiiPO32ZT3aXTOgwxTKbFP3LBDmwA18UCgYAQuEgsbmqz1OFoHLnbySQLEhXsiuyDsmbpu0BxEG4UjgEwf+sn0IBIVeBUjWmVEbOPvHbAmTBMZCQbYjLnBdCACGswt6Xln4E2o0j2Jl1Fmpp0C3t7/1nU6MqStO6O/yhcCztIL4NKbq82wvw+V3gHt5bjEePIJWPYqZwmOp1ahQKBgCqfHKs6gBr7RbETq6T6XiJ9c/Lu7iaFxJjicJGPazhLeaZqcjXKye8dI/36nMvkQh8XJ+lPPXgeviBo4aEwbE4F2HZZVz72HcAin0DvXwQBcHH1J0rGCrAJ9V/91d5OtySv1mwUOTS16yIx3260/HyyWj8ILN7dWfEHoG0mMV8hAoGBAI0KBzR9WfzxNKI4ZqRD9/sN+SH4oxymo2oJ+FnOW7hk1E0EyrsGzIDCrS/f7MPzLJI7F4DULsrU5RIQyouIybZra29Vqe4L8kdIae5O0R4Y2r7gt/yWo4cWnW53Q0f5o7mzV10Dc8ewuT1DyJrt25dMWsGsP8rQ/0pVUBLEf93b
-----END PRIVATE KEY-----'''

        self.aggConfig = {
            'keys': 'd3dGiJc651gSQ8w1',
            'charMap': {
                '+': 'P', '/': 'X', '0': 'M', '1': 'U', '2': 'l', '3': 'E', '4': 'r', '5': 'Y', '6': 'W', '7': 'b', '8': 'd', '9': 'J',
                'A': '9', 'B': 's', 'C': 'a', 'D': 'I', 'E': '0', 'F': 'o', 'G': 'y', 'H': '_', 'I': 'H', 'J': 'G', 'K': 'i', 'L': 't',
                'M': 'g', 'N': 'N', 'O': 'A', 'P': '8', 'Q': 'F', 'R': 'k', 'S': '3', 'T': 'h', 'U': 'f', 'V': 'R', 'W': 'q', 'X': 'C',
                'Y': '4', 'Z': 'p', 'a': 'm', 'b': 'B', 'c': 'O', 'd': 'u', 'e': 'c', 'f': '6', 'g': 'K', 'h': 'x', 'i': '5', 'j': 'T',
                'k': '-', 'l': '2', 'm': 'z', 'n': 'S', 'o': 'Z', 'p': '1', 'q': 'V', 'r': 'v', 's': 'j', 't': 'Q', 'u': '7', 'v': 'D',
                'w': 'w', 'x': 'n', 'y': 'L', 'z': 'e'
            },
            'headers': {
                'default': {'User-Agent': 'okhttp/4.10.0', 'Content-Type': 'application/json'},
                'niuniu': {'Cache-Control': 'no-cache', 'Content-Type': 'application/json;charset=UTF-8', 'User-Agent': 'okhttp/4.12.0'},
                'baidu': {'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 9; 22081212C Build/PQ3B.190801.002) Talos/1.8.13 SP-engine/3.47.0 bd_dvt/1 baiduboxapp/15.21.0.10 (Baidu; P1 9)'},
                'haokan': {
                    'User-Agent': 'Mozilla/5.0 (Linux; Android 11; M2012K10C Build/RP1A.200720.011; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/87.0.4280.141 Mobile Safari/537.36 haokan/7.80.0.18 (Baidu; P1 11)/imoaiX_03_11_C01K2102M/1043677m/5ACDB023CFB9D64743B08E51953F7C76%7CVSAJ32AVA/1/7.80.0.18/780001/1/immersiveMode/modeV4PlusWhite/isFirstInstall/bbqMode/bbqModeV2/blackStyle/isPlaylet Talos/1.8.7',
                    'Talos-Module-Name': 'shortDrama', 'Talos-Module-Version': '1.0.71.1',
                    'Content-Type': 'application/x-www-form-urlencoded; charset=utf-8',
                    'Cookie': 'BAIDUCUID=giHCu0azv80G8SfQ0avU8gaaH8jfiv86ju2MugiR2i8-k3a35avAa1_mA'
                },
                'hema': {
                    'alg': 'HG45LKBS',
                    'datas': 'phM9hgPlRJYhe1CnGhmAXAGxykuiUzMzDg9O6gim3BYyV82hDVoeHMMzRimC6OhW7BLsDRmEnSa5Tv/yZHZ2+Q3hypMQTA6hentuuRFdFSRnRqGF0aeskqdImcXPXZOKfNWw8w2syoAxXUCYd+8H5fX+hF34F5UQidB8DN8KHWmNn79AAEb2xTXFsB4mcn5YYDGm1iIDRaosixoS5pFySNGOLtkMgjIbRSrN1cxPq/BNE/7isNe/25z+svVABRWfFFM1ehaWgLSnsAn96c8Ptc3TwLjx7kDCWnNx2MP9f04T6qA8mP/SworDn4Hhoo0Tsrjmg5enoPwLs3V1HHazSMPxC+pIC6bW3GrQ0Ar0uhIVXXmX+zYQGcyI4bXphY9iFObo81h6d9LIxR47RbNHfGZ2NJUHJmF5lFHXCInleDrNjw+gf91VG6EjPaBNmN60ka7/nVpYmGK3GC8cw6iEi52jCn+AgRbeygGPH2CdMLcunIOgEIT+aL4YnVxP13peX//bi1+gfeItPB0rsL5YPh3XWas/73dLYTtTYZVVYQspAnYwj2BTvlCfnjGcKNgPa7YfB21xLLuCCAnrrmy7zgkKmyTr2zGVPgaCv5IhiNtrbw8XQMODjgEhijC+arxig3wPaXkHbSkHFwlpO4UaWgLxz8gUYxKDSFXa+5Z8988z7EcDtsOepH1EwyV277SV+McDi/4QDNhC4UV8hA0bDQ==',
                    'x-request-id': '267871ed-5d33-469d-b349-d0a4df6730cc', 'content-type': 'application/json; charset=utf-8', 'accept-encoding': 'gzip', 'user-agent': 'okhttp/4.10.0'
                },
                'xingxing': {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.87 Safari/537.36'}
            }
        }

        self.rule = {
            '河马': {'host': 'https://freevideo.zqqds.cn', 'list': '/free-video-portal/portal/1125', 'detail': '/free-video-portal/portal/1131', 'play': '/free-video-portal/portal/1139', 'search': '/free-video-portal/portal/1803'},
            '七猫': {'host': 'https://api-store.qmplaylet.com', 'list': '/api/v1/playlet/index', 'detail': 'https://api-read.qmplaylet.com/player/api/v1/playlet/info', 'search': '/api/v1/playlet/search'},
            '百度': {'host': 'https://mbd.baidu.com', 'detailHost': 'https://sv.baidu.com', 'list': '/feedapi/v1/videoserver/playlets/list?service=bdbox', 'search': '/feedapi/v1/videoserver/playlets/search?service=bdbox', 'detail': '/haokan/ui-video/playlet/rec/detail?log=vhk&tn=1020970b&ctn=1008350n&blur=1', 'play': '/appui/api?cmd=video/relate&log=vhk&tn=1020970b&ctn=1008350n&blur=1'},
            '牛牛': {'host': 'https://new.tianjinzhitongdaohe.com', 'list': '/api/v1/app/screen/screenMovie', 'detail': '/api/v1/app/play/movieDetails', 'search': '/api/v1/app/search/searchMovie', 'desc': '/api/v1/app/play/movieDesc', 'visitor': '/api/v1/app/user/visitorInfo', 'login': 'https://csj-sp.csjdeveloper.com/csj_sp/api/v1/user/login?siteid=5627189', 'detail2': 'https://csj-sp.csjdeveloper.com/csj_sp/api/v1/shortplay/detail?siteid=5627189', 'unlock': 'https://csj-sp.csjdeveloper.com/csj_sp/api/v1/pay/ad_unlock?siteid=5627189'},
            '围观': {'host': 'https://api.drama.9ddm.com', 'list': '/drama/home/shortVideoTags?version_code=1500&os_type=1', 'detail': '/drama/home/shortVideoDetail?version_code=1000&os_type=1', 'search': '/drama/home/search?version_code=1500&os_type=1'},
            '西饭': {'host': 'https://xifan-api-cn.youlishipin.com', 'list': '/xifan/drama/portalPage', 'detail': '/xifan/drama/getDuanjuInfo', 'search': '/xifan/search/getSearchList'},
            '星星': {'host': 'http://read.api.duodutek.com', 'list': '/novel-api/app/pageModel/getResourceById', 'detail': '/novel-api/basedata/book/getChapterList'},
            '好看': {'host': 'https://sv.baidu.com', 'list': '/haokan/ui-feed/playletTagsFeed?osbranch=a0', 'home': '/haokan/ui-feed/playletShelfFeed?osbranch=a0', 'detail_list': '/appui/api?osbranch=a0', 'detail': '/haokan/ui-video/playlet/rec/detail?osbranch=a0', 'play': '/appui/api?osbranch=a0', 'search': '/haokan/ui-interact/playlet/search/sugs?osbranch=a0'},
            '星芽': {'host': 'https://app.whjzjx.cn', 'list': '/cloud/v2/theater/home_page?theater_class_id', 'detail': '/v2/theater_parent/detail', 'search': '/v3/search', 'login': 'https://u.shytkjgs.com/user/v1/account/login'},
            '山海': {'host': 'https://api.app.gxshxy.com', 'login': 'https://u.app.gxshxy.com/user/v3/account/login', 'list': '/shanhai-theater/v2/theater_parent/cloud/v2/theater/home_page', 'detail': '/v2/theater_parent/detail', 'search': '/cloud/v3/search'},
            '薏米': {'host': 'https://yimi-api.zhangyue.com', 'list': '/bookstore/local/visual/channel/list', 'detail': '/video/client/short_play/episode_list', 'search': '/bookstore/search/recommend_data'},
            '爽爽': {'host': 'https://djw123.com', 'url': '/show/fyclassfyfilter.html', 'searchUrl': '/search/-------------.html', 'class_url': 'duanju'},
            '喜福': {'host': 'https://minidrama-api.contentchina.com', 'list': '/web/v1/home/categoryList?isLeft=1', 'dramaList': '/web/v1/drama/list', 'playAuth': '/web/v1/drama/play_auth'},
            '五五': {'host': 'https://www.duanju55.com', 'list': '/index.php/vod/show/class/', 'search': '/index.php/vod/search/wd/', 'detail': '/index.php/vod/detail/id/'}
        }

        self.platformList = [
            {'name': '河马短剧', 'id': '河马'}, {'name': '七猫短剧', 'id': '七猫'}, {'name': '星芽短剧', 'id': '星芽'},
            {'name': '百度短剧', 'id': '百度'}, {'name': '山海短剧', 'id': '山海'}, {'name': '薏米短剧', 'id': '薏米'},
            {'name': '牛牛短剧', 'id': '牛牛'}, {'name': '围观短剧', 'id': '围观'}, {'name': '西饭短剧', 'id': '西饭'},
            {'name': '好看短剧', 'id': '好看'}, {'name': '喜福短剧', 'id': '喜福'}, {'name': '星星短剧', 'id': '星星'},
            {'name': '爽爽短剧', 'id': '爽爽'}, {'name': '五五短剧', 'id': '五五'}
        ]
        
        self.ruleFilterDef = {
            '河马': {'area': '10@强爽男频'}, '七猫': {'area': '0'}, '百度': {'area': '新剧'}, '牛牛': {'area': '现言'},
            '围观': {'area': ''}, '西饭': {'area': '68@都市'}, '星星': {'area': '1287'}, '好看': {'area': '1'},
            '星芽': {'area': '1'}, '山海': {'area': '1'}, '薏米': {'area': 'channel_c6f50cd9'},
            '爽爽': {'area': ''}, '喜福': {'area': ''}, '五五': {'area': '全部'}
        }
        
        self.filterOptions = self._make_filters()
        self.init(extend)

    def getName(self):
        return self.siteName

    def init(self, extend=''):
        print(f'【{self.siteName}】初始化开始')
        
        # 星芽初始化
        try:
            r = self.req(self.rule['星芽']['login'], method='POST', headers={'User-Agent': 'okhttp/4.10.0', 'platform': '1', 'Content-Type': 'application/json'}, data={'device': '24250683a3bdb3f118dff25ba4b1cba1a'})
            token = (self.safe_json(r).get('data') or {}).get('token') or self.safe_json(r).get('token') or self.safe_json(r).get('access_token')
            self.xingya_headers = dict(self.aggConfig['headers']['default'])
            if token:
                self.xingya_headers['authorization'] = token
        except Exception:
            self.xingya_headers = dict(self.aggConfig['headers']['default'])

        # 牛牛初始化
        nnDeviceId = str(uuid.uuid4())
        try:
            tkhtml = self.req(self.rule['牛牛']['host'] + self.rule['牛牛']['visitor'], headers={'deviceid': nnDeviceId, 'token': '', 'User-Agent': 'okhttp/4.12.0', 'client': 'app', 'devicetype': 'Android'}, timeout=15, verify=False)
            self.niuniu_token = ((self.safe_json(tkhtml).get('data') or {}).get('token') or '')
        except Exception:
            self.niuniu_token = ''
        self.niuniu_headers = dict(self.aggConfig['headers']['niuniu'])
        self.niuniu_headers.update({'token': self.niuniu_token, 'deviceid': nnDeviceId})

        try:
            t = str(int(time.time()))
            body = f'ac=wifi&os=Android&vod_version=1.10.21.6-tob&os_version=9&type=1&clientVersion=v5.2.5&uuid=Y4WNZ3SAWK7MAJMH7CXCDHJ4VMPVFRZQTBSIA4XTYO4AWEUHIK6Q01&resolution=1280*2618&openudid=889edced38f1069b&dt=Pixel%204&sha1=46121F77CE2FCAD3DBC3B9EC8A24908C1A8AD6D9&os_api=28&install_id=1549688030634536&device_brand=google&sdk_version=1.1.3.0&package_name=com.niuniu.ztdh.app&siteid=5627189&dev_log_aid=667431&oaid=&timestamp={t}'
            nonce = 'VX1KKGtoBDCi1fB1'
            signature = self.hmacSHA256(t + nonce + body, 'aceaa47f96b4875d446b2e1d97e03bbb')
            encbody = self.aesEncryptECB(body, 'dafdb3d2a5c343d6')
            loginpost = self.req(self.rule['牛牛']['login'], method='POST', headers={'X-Salt': '786774955F', 'X-Nonce': nonce, 'X-Timestamp': t, 'X-Signature': signature, 'Content-Type': 'application/x-www-form-urlencoded'}, data=encbody)
            if loginpost:
                self.niuniu_access_token = (self.safe_json(self.aesDecryptECB(loginpost, 'dafdb3d2a5c343d6')).get('data') or {}).get('access_token', '')
        except Exception:
            print('牛牛广告解锁模块加载失败')
            
        self.shanhaiauth()
        
        # 喜福初始化
        try:
            cd = self.safe_json(self.req(f"{self.rule['喜福']['host']}{self.rule['喜福']['list']}", headers={'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36'}))
            cats = cd.get('data', {}).get('categories', [])
            self.xifu_categories = [{'id': c.get('id'), 'name': f"精彩{c.get('name')}"} for c in cats]
        except Exception as e:
            print(f'【喜福初始化异常】{e}')
            
        return True

    def homeContent(self, filter):
        classes = [{'type_name': x['name'], 'type_id': x['id'], 'type_flag': '[CFS][SUBSITE2][FILTERBAR]'} for x in self.platformList]
        filters = dict(self.filterOptions)
        
        # 动态添加喜福分类
        cats = [{'n': '全部', 'v': ''}]
        for c in self.xifu_categories:
            cats.append({'n': c['name'], 'v': str(c['id'])})
        filters['喜福'] = [{'key': 'area', 'name': '分类', 'value': cats}]
        
        return {'class': classes, 'filters': filters, 'type_flag': '3-00-S'}

    def homeVideoContent(self):
        list_data = []
        for i, p in enumerate(self.platformList):
            list_data.append({'vod_id': f"tab:id:{p['id']}", 'vod_name': p['name'], 'vod_pic': f"clan://assets/tab.png?bgcolor={i+1}"})
        return {'list': list_data}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg or 1)
        if not isinstance(filter, dict): filter = {}
        if not isinstance(extend, dict): extend = {}
            
        area = filter.get('area') or extend.get('area') or ''
        if not area and isinstance(filter.get('filters'), list):
            for f in filter['filters']:
                if f.get('key') == 'area' and f.get('select'):
                    area = f['select']; break
        if not area:
            area = self.ruleFilterDef.get(tid, {}).get('area', '')
            
        videos = []
        p = self.rule.get(tid, {})
        prefix = f"{tid}短剧 | "
        
        try:
            if tid == '河马':
                a = area.split('@')
                body = self.hemaEncrypt(json.dumps({'recSwitch': True, 'storePageId': 10002, 'channelGroupId': '10', 'channelId': a[0] if a else '10', 'channelName': a[1] if len(a) > 1 else '男频', 'pageFlag': page, 'theaterSubscriptSwitch': True}, ensure_ascii=False))
                res = self.safe_json(self.req(p['host'] + p['list'], method='POST', headers=self.aggConfig['headers']['hema'], data=body))
                data = self.safe_json(self.hemaDecrypt(res.get('data', '')))
                for v in (((data.get('columnData') or [{}])[0]).get('videoData') or []):
                    videos.append({'vod_id': f'河马@{v.get("bookId")}', 'vod_name': v.get('bookName', ''), 'vod_pic': v.get('coverWap', ''), 'vod_remarks': prefix + v.get('finishStatusCn', ''), 'vod_content': ''})
            elif tid == '七猫':
                params = {'operation': 1, 'playlet_privacy': 1}
                if area: params['tag_id'] = area
                if page > 1: params['next_id'] = page
                params['sign'] = self.md5(''.join([f'{k}={params[k]}' for k in sorted(params.keys())]) + self.aggConfig['keys'])
                res = self.safe_json(self.req(p['host'] + p['list'] + '?' + urlencode(params), headers=self.getQiMaoHeaders()))
                for it in ((res.get('data') or {}).get('list') or []):
                    videos.append({'vod_id': '七猫@' + quote(str(it.get('playlet_id') or it.get('id') or '')), 'vod_name': it.get('title', ''), 'vod_pic': it.get('image_link', ''), 'vod_remarks': prefix + (str(it.get('total_episode_num')) + '集' if it.get('total_episode_num') else ''), 'vod_content': it.get('tags', '')})
            elif tid == '百度':
                sub = area if area in ['新剧', '限时免费', '精选', '独播'] else '新剧'
                tcsub = '' if area in ['全部', '全部题材'] else area
                t = int(time.time()); version = self.md5(str(t) + 'v2')
                post = {'data': json.dumps({'data': {'extRequest': {'flow_tabid': '13'}, 'from': 'feed', 'page': 'channel_video_landing', 'pd': 'feed', 'refreshIndex': page, 'cursor': '', 'theme': '', 'timestamp': t, 'version': version, 'themes': [{'kind': '综合', 'names': [sub]}, {'kind': '题材', 'names': [tcsub]}]}}, ensure_ascii=False)}
                res = self.safe_json(self.req(p['host'] + p['list'], method='POST', headers=self.aggConfig['headers']['baidu'], data=post))
                for it in ((res.get('data') or {}).get('items') or [])[:20]:
                    videos.append({'vod_id': f'百度@{it.get("collId")}', 'vod_name': it.get('title', '未知短剧'), 'vod_pic': it.get('img', ''), 'vod_remarks': prefix + it.get('updateStatus', '更新中'), 'vod_content': it.get('description', '')})
            elif tid == '牛牛':
                condition = {'typeId': 'S1'}
                if area and area != '全部': condition['classify'] = area
                res = self.safe_json(self.req(p['host'] + p['list'], method='POST', headers=self.niuniu_headers, data={'condition': condition, 'pageNum': page, 'pageSize': 24}, timeout=15, verify=False))
                for it in ((res.get('data') or {}).get('records') or []):
                    videos.append({'vod_id': f'牛牛@{it.get("id")}', 'vod_name': it.get('name', ''), 'vod_pic': it.get('cover', ''), 'vod_remarks': prefix + (str(it.get('totalEpisode')) + '集' if it.get('totalEpisode') else ''), 'vod_content': it.get('description', '')})
            elif tid == '围观':
                res = self.safe_json(self.req(p['host'] + p['search'], method='POST', data={'audience': '全部受众', 'page': page, 'pageSize': 30, 'searchWord': '', 'subject': '全部主题'}))
                for it in (res.get('data') or []):
                    videos.append({'vod_id': f'围观@{it.get("oneId")}', 'vod_name': it.get('title', '未知短剧'), 'vod_pic': it.get('vertPoster') or it.get('horizonPoster') or '', 'vod_remarks': prefix + f'集数:{it.get("episodeCount",0)}', 'vod_content': it.get('description', '')})
            elif tid == '西饭':
                typeId, typeName = (area.split('@') + ['都市'])[:2]
                offset = (page - 1) * 30; ts = int(time.time())
                url = f'{p["host"]}{p["list"]}?reqType=aggregationPage&offset={offset}&categoryId={typeId}&quickEngineVersion=-1&scene=&categoryNames={quote(typeName)}&categoryVersion=1&density=1.5&pageID=page_theater&version=2001001&androidVersionCode=28&requestId={ts}aa498144140ef297&appId=drama&teenMode=false&userBaseMode=false'
                res = self.safe_json(self.req(url))
                for soup in ((res.get('result') or {}).get('elements') or []):
                    for vod in (soup.get('contents') or []):
                        dj = vod.get('duanjuVo') or {}
                        if dj.get('duanjuId'):
                            videos.append({'vod_id': f'西饭@{dj.get("duanjuId")}#{dj.get("source")}', 'vod_name': dj.get('title', ''), 'vod_pic': dj.get('coverImageUrl', ''), 'vod_remarks': prefix + '推荐', 'vod_content': dj.get('desc', '')})
            elif tid == '星星':
                params = {'productId': '2a8c14d1-72e7-498b-af23-381028eb47c0', 'vestId': '2be070e0-c824-4d0e-a67a-8f688890cadb', 'channel': 'oppo19', 'osType': 'android', 'version': '20', 'token': '202509271001001446030204698626', 'resourceId': area, 'pageNum': str(page), 'pageSize': '20'}
                res = self.safe_json(self.req(p['host'] + p['list'] + '?' + urlencode(params), headers=self.aggConfig['headers']['xingxing']))
                for vod in ((res.get('data') or {}).get('datalist') or []):
                    videos.append({'vod_id': f'星星@{vod.get("id")}@{quote(vod.get("introduction", ""))}', 'vod_name': vod.get('name', ''), 'vod_pic': vod.get('icon', ''), 'vod_remarks': prefix + f'{vod.get("heat",0)}万播放', 'vod_content': vod.get('introduction', '')})
            elif tid == '好看':
                res = self.safe_json(self.req(p['host'] + p['list'], method='POST', headers=self.aggConfig['headers']['haokan'], data=f'tag_id={area}&rn=20&pn={page}'))
                for item in ((res.get('data') or {}).get('list') or []):
                    tags = item.get('tags') or []
                    videos.append({'vod_id': f'好看@{item.get("playlet_id")}', 'vod_name': item.get('playlet_title', ''), 'vod_pic': item.get('playlet_poster', ''), 'vod_remarks': prefix + item.get('episodes_num_text', ''), 'vod_content': '·'.join(tags) if isinstance(tags, list) else str(tags)})
            elif tid == '星芽':
                res = self.safe_json(self.req(f'{p["host"]}{p["list"]}={area}&type=1&class2_ids=0&page_num={page}&page_size=24', headers=self.xingya_headers))
                for it in ((res.get('data') or {}).get('list') or []):
                    th = it.get('theater') or {}
                    videos.append({'vod_id': f'星芽@{th.get("id")}', 'vod_name': th.get('title', ''), 'vod_pic': th.get('cover_url', ''), 'vod_remarks': prefix + (str(th.get('total')) + '集' if th.get('total') else ''), 'vod_content': f'播放量:{th.get("play_amount_str",0)}'})
            elif tid == '山海':
                url = f'{p["host"]}{p["list"]}?theater_class_id=1&type=1&class2_ids={area}&page_num={page}&page_size=24'
                res = self.shanhaifetch(url)
                for item in (res.get('items') or []):
                    th = item.get('theater') or {}
                    videos.append({'vod_id': f'山海@{th.get("id")}', 'vod_name': th.get('title', ''), 'vod_pic': th.get('cover_url', ''), 'vod_remarks': prefix + f'共{th.get("total",0)}集', 'vod_content': ''})
            elif tid == '薏米':
                path = '/bookstore/local/visual/channel/list'
                baseParams = f'key={area}&p1=1750574688516674369&p16=22081212C&p2=341201&p21=10&p22=15&p24=0&p25=21200&p28=cca83346da195d11&p29=zy9351ae&p3=102120009&p31=29d1af74b128f29f&p33=com.zhangyue.app.shortplay&p34=force_fsg_nav_bar&p35=BUZGFVakskazFWG2XwZ/LNs4fOnQczc4iivy1qLFvZqmerp2Abe2hv5Tu1jOHQJO5PGANizg3JbzgaTOon0qkmQ==&p4=501609&p5=16&p7=cca83346da195d11&p9=3&page={page}&pc=10&usr=tj1290623468&zyeid=4fc4c6737a87b603e1b8ce9210032bae'
                headers = self.yimiGetHeaders(path, baseParams, 'AAF4IWZnITkqeX4hJCB5eio4IWc4IH4=')
                url = p['host'] + path + '?' + baseParams
                response = self.req(url, method='GET', headers=headers)
                if response:
                    json_data = self.safe_json(response)
                    list_data = json_data.get('body', {}).get('list', [])
                    if list_data and isinstance(list_data, list) and len(list_data) > 0:
                        for item in list_data[0].get('short_plays', []):
                            if item.get('id'):
                                videos.append({'vod_id': f'薏米@{item["id"]}', 'vod_name': item.get('short_play_name', ''), 'vod_pic': item.get('cover_url', ''), 'vod_remarks': prefix + f'热度值:{item.get("favor_count_format",0)}', 'vod_content': ''})
            elif tid == '爽爽':
                fa = area
                if not fa:
                    opts = self.filterOptions.get('爽爽')
                    if opts and opts[0]:
                        n = next((v for v in (opts[0].get('value') or []) if v.get('v')), None)
                        if n: fa = n['v']
                    if not fa: fa = '女频恋爱'
                html = self.req(f"{p['host']}/show/duanju---{quote(fa)}-----{page}---.html", headers={'User-Agent': self.mobileUA})
                cards = re.findall(r'<div class="a-con-inner">[\s\S]*?</div>(?=\s*<div class="a-con-inner"|$)', html, re.I)
                for c in cards:
                    tm = re.search(r'<a[^>]*title="([^"]+)"[^>]*>', c)
                    um = re.search(r'<a[^>]*href="([^"]+)"[^>]*>', c)
                    if tm and um:
                        pic_m = re.search(r'<img[^>]*data-original="([^"]+)"', c)
                        rem_m = re.search(r'<span[^>]*>([^<]+)</span>', c)
                        videos.append({'vod_id': f"爽爽@{quote(um.group(1))}", 'vod_name': tm.group(1), 'vod_pic': pic_m.group(1) if pic_m else '', 'vod_remarks': prefix + (rem_m.group(1) if rem_m else '')})
            elif tid == '喜福':
                cid = area
                if not cid and self.xifu_categories: cid = str(self.xifu_categories[0]['id'])
                u = f"{p['host']}{p['dramaList']}?pageSize=24&currentPage={page}"
                if cid: u += f"&filterCategories[]={cid}"
                res = self.safe_json(self.req(u, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36'}))
                for v in (res.get('data', {}).get('data') or []):
                    videos.append({'vod_id': f"喜福@{v.get('albumId')}@{v.get('total')}", 'vod_name': v.get('title'), 'vod_pic': v.get('coverUrl'), 'vod_remarks': prefix + f"共{v.get('total', 0)}集"})
            elif tid == '五五':
                u = f"{p['host']}/index.php/vod/type/id/1.html" if area == '全部' else f"{p['host']}/index.php/vod/show/class/{quote(area)}/id/1.html"
                if page > 1: u += f"?page={page}"
                html = self.req(u, headers=self.aggConfig['headers']['default'])
                for v in self.parseWuWuList(html, p['host']):
                    videos.append({'vod_id': f"五五@{v['id']}", 'vod_name': v['name'], 'vod_pic': v['pic'], 'vod_remarks': prefix + v['rem']})
        except Exception as e:
            print(f'【分类异常】{tid} p{page}: {e}')
        return {'list': self.dedup(videos), 'page': page, 'pagecount': page + 1, 'limit': len(videos), 'total': len(videos) * (page + 1)}

    def detailContent(self, ids):
        idv = ids[0] if isinstance(ids, list) else ids
        
        platform, did = (idv.split('@', 1) + [''])[:2]
        p = self.rule.get(platform, {})
        vod = {'vod_id': idv, 'vod_name': '', 'vod_play_from': platform + '专线', 'vod_play_url': '暂无播放地址$0'}
        
        try:
            if platform == '河马':
                body = self.hemaEncrypt(json.dumps({'bookId': did, 'needNextChapter': 0, 'isNeedAlias': '', 'bookAlias': '', 'resolutionRate': '720P'}, ensure_ascii=False))
                res = self.safe_json(self.req(p['host'] + p['detail'], method='POST', headers=self.aggConfig['headers']['hema'], data=body))
                data = self.safe_json(self.hemaDecrypt(res.get('data', '')))
                info = data.get('videoInfo') or {}; chapters = data.get('chapterList') or []; last = chapters[-1].get('chapterId', '') if chapters else ''
                vod.update({'vod_name': info.get('bookName', '未知剧名'), 'vod_type': ','.join(info.get('bookTags') or []), 'vod_pic': info.get('coverWap', ''), 'vod_remarks': info.get('finishStatusCn', ''), 'vod_actor': ','.join(info.get('protagonist') or []), 'vod_content': info.get('introduction', '暂无简介'), 'vod_play_from': '河马专线', 'vod_play_url': '#'.join([f'{c.get("chapterName")}${did}@{c.get("chapterId")}@{last}' for c in chapters])})
            elif platform == '七猫':
                did2 = unquote(did); sign = self.md5(f'playlet_id={did2}{self.aggConfig["keys"]}')
                res = self.safe_json(self.req(f'{p["detail"]}?playlet_id={did2}&sign={sign}', headers=self.getQiMaoHeaders()))
                data = res.get('data') or {}
                vod.update({'vod_name': data.get('title', '未知标题'), 'vod_pic': data.get('image_link', ''), 'vod_remarks': f'{data.get("tags","")} {data.get("total_episode_num",0)}集', 'vod_content': data.get('intro', '未知剧情'), 'vod_play_from': '七猫专线', 'vod_play_url': '#'.join([f'{it.get("sort")}${it.get("video_url")}' for it in (data.get('play_list') or [])])})
            elif platform == '百度':
                res = self.safe_json(self.req(p['detailHost'] + p['detail'], method='POST', headers={'Content-Type': 'application/x-www-form-urlencoded'}, data={'playlet_id': did, 'vid': 'undefined'}))
                d = res.get('data') or {}; vids = d.get('vid_list') or []
                vod.update({'vod_name': d.get('playlet_title', '未知短剧'), 'vod_pic': d.get('playlet_poster', ''), 'vod_content': f'热度值:{d.get("hot_value",0)}\n题材:{d.get("tag_text","")}\n集数:{d.get("episodes_num",0)}\n简介:{d.get("description","")}', 'vod_remarks': f'共{len(vids)}集', 'vod_director': d.get('tag_text', ''), 'vod_year': d.get('create_time', ''), 'vod_play_from': '百度专线', 'vod_play_url': '#'.join([f'第{i+1}集${did}@{v}' for i, v in enumerate(vids)])})
            elif platform == '牛牛':
                desc = self.safe_json(self.req(p['host'] + p['desc'], method='POST', headers=self.niuniu_headers, data={'id': did, 'typeId': 'S1'}, timeout=15, verify=False)).get('data') or {}
                lst = self.safe_json(self.req(p['host'] + p['detail'], method='POST', headers=self.niuniu_headers, data={'id': did, 'source': 0, 'typeId': 'S1', 'userId': '546932'}, timeout=15, verify=False)).get('data') or {}
                playUrls = '#'.join([f'{ep.get("episode")}${did}+{ep.get("id")}' for ep in (lst.get('episodeList') or [])]) if lst.get('url') else ''
                if not playUrls and lst.get('thirdPlayId'):
                    thirdPlayId = lst.get('thirdPlayId')
                    data1 = 'not_include=0&lock_free=1&type=1&clientVersion=v5.2.5&uuid=6IDYUSASPQY5BBVACWQW3LLTPV4V7DE26UOCX5TZTVUGX4VUJNXQ01&resolution=1080*2320&openudid=82f4175d577a2939&dt=22021211RC&os_api=31&install_id=1496879012031075&sdk_version=1.1.3.0&siteid=5627189&dev_log_aid=667431&oaid=abec0dfff623201b&timestamp=1752498494&direction=0&ac=mobile&os=Android&vod_version=1.10.21.6-tob&os_version=12&count=1&index=1&shortplay_id=' + str(thirdPlayId) + '&sha1=46121F77CE2FCAD3DBC3B9EC8A24908C1A8AD6D9&device_brand=Redmi&package_name=com.niuniu.ztdh.app'
                    html1 = self.niuniuPost(self.rule['牛牛']['detail2'], data1, '1')
                    ep_list = ((html1.get('data') or {}).get('episode_right_list') or [])
                    playUrls = '#'.join([f'第{it.get("index")}集${it.get("index")}+{it.get("lock_type") or "free"}+{thirdPlayId}' for it in ep_list])
                vod.update({'vod_name': desc.get('name') or lst.get('name') or '未知名称', 'vod_pic': desc.get('cover') or lst.get('cover') or '', 'vod_content': f'类型：{desc.get("classify","")}\n评分：{desc.get("score","")}\n简介：{desc.get("introduce","")}', 'vod_remarks': f'共{desc.get("totalEpisode") or lst.get("totalEpisode") or 0}集', 'vod_play_from': '牛牛专线', 'vod_play_url': playUrls or '暂无播放地址$0'})
            elif platform == '围观':
                res = self.safe_json(self.req(f'{p["host"]}{p["detail"]}&oneId={did}&page=1&pageSize=1000'))
                data = res.get('data') or []; first = data[0] if data else {}
                arr = []
                for ep in data:
                    ps = ep.get('playSetting') or ep.get('videoClarityList') or []
                    if isinstance(ps, str): ps = self.safe_json(ps, {})
                    url = ''
                    if isinstance(ps, dict):
                        url = ps.get('super') or ps.get('high') or ps.get('normal') or ps.get('url') or ps.get('playUrl') or ''
                    elif isinstance(ps, list) and ps:
                        best = next((x for x in ps if x.get('clarity') in ['1080P', '1080p', 'super', '超清']), ps[0]); url = best.get('url') or best.get('playUrl') or ''
                    title = f'第{ep.get("playOrder") or ep.get("episode") or len(arr)+1}集'
                    arr.append(f'{title}${url or ep.get("playUrl","")}')
                vod.update({'vod_name': first.get('title', ''), 'vod_pic': first.get('vertPoster') or first.get('horizonPoster') or '', 'vod_remarks': f'共{len(data)}集', 'vod_content': f'播放量:{first.get("viewCount",0)} 收藏:{first.get("collectionCount",0)} 评论:{first.get("commentCount",0)}', 'vod_play_from': '围观专线', 'vod_play_url': '#'.join(arr)})
            elif platform == '西饭':
                duanjuId, source = (did.split('#') + [''])[:2]
                data = self.safe_json(self.req(f'{p["host"]}{p["detail"]}?duanjuId={duanjuId}&source={source}')).get('result') or {}
                vod.update({'vod_name': data.get('title', ''), 'vod_pic': data.get('coverImageUrl', ''), 'vod_content': data.get('desc', '未知'), 'vod_remarks': (f'{data.get("total",0)}集 已完结' if data.get('updateStatus') == 'over' else f'更新{data.get("total",0)}集'), 'vod_play_from': '西饭专线', 'vod_play_url': '#'.join([f'{ep.get("index")}${ep.get("playUrl")}' for ep in (data.get('episodeList') or [])])})
            elif platform == '星星':
                bookId, contentDesc = (did.split('@') + [''])[:2]
                params = {'bookId': bookId, 'productId': '2a8c14d1-72e7-498b-af23-381028eb47c0', 'vestId': '2be070e0-c824-4d0e-a67a-8f688890cadb', 'channel': 'oppo19', 'osType': 'android', 'version': '20', 'token': '202509271001001446030204698626'}
                data = self.safe_json(self.req(p['host'] + p['detail'] + '?' + urlencode(params), headers=self.aggConfig['headers']['xingxing'])).get('data') or []
                arr = []
                for i, item in enumerate(data):
                    try:
                        u = item['shortPlayList'][0]['chapterShortPlayVoList'][0]['shortPlayUrl']
                        if u: arr.append(f'第{i+1}集${u}')
                    except Exception: pass
                vod.update({'vod_name': '星星短剧', 'vod_content': unquote(contentDesc), 'vod_play_from': '星星专线', 'vod_play_url': '#'.join(arr) or '暂无播放地址$0'})
            elif platform == '好看':
                commonlistId = str(int(time.time() * 1000))[:13]
                inner = f'enable_enter_playlet=0&seek_time=0&hotspot=0&auto_show_hot_point_panel=0&type=playlet&commonlist_id={commonlistId}&scene=&vid=&enable_atlas=0&mark_pn=&uk=&ctime=0&from=playlet_new&id={did}&rn=20&pn=1&direction=3'
                res1 = self.safe_json(self.req(p['host'] + p['detail_list'], method='POST', headers=self.aggConfig['headers']['haokan'], data='video/commonlist=' + quote(inner), timeout=30))
                results = (((res1.get('video/commonlist') or {}).get('data') or {}).get('results') or [])
                first = results[0] if results else {}
                vid = first.get('vid') or (first.get('content') or {}).get('vid') or ''
                d = {}
                if vid:
                    d = self.safe_json(self.req(p['host'] + p['detail'], method='POST', headers=self.aggConfig['headers']['haokan'], data=f'vid={vid}&playlet_id={did}', timeout=20)).get('data') or {}
                vids = d.get('vid_list') or [x.get('vid') or (x.get('content') or {}).get('vid') for x in (d.get('results') or []) if x.get('vid') or (x.get('content') or {}).get('vid')]
                if vids:
                    play_url = '#'.join([f'第{i+1}集${did}@{v}' for i, v in enumerate(vids)])
                else:
                    arr = []
                    for i, x in enumerate(results):
                        c = x.get('content') or {}
                        u = c.get('video_src') or c.get('url') or x.get('video_src') or ''
                        if u: arr.append(f"{c.get('title') or x.get('title') or f'第{i+1}集'}${u}")
                    play_url = '#'.join(arr)
                c0 = first.get('content') or {}
                title = d.get('playlet_title') or c0.get('title') or ''
                title = re.sub(r'\s*0*1\s*$', '', title).strip() or title
                vod.update({'vod_name': title, 'vod_pic': d.get('playlet_poster') or c0.get('poster') or c0.get('cover_src') or '', 'vod_remarks': f'{d.get("hot_value","")}播放·{d.get("episodes_num", len(results) or "")}集', 'vod_director': c0.get('author') or '', 'vod_content': d.get('description') or c0.get('title') or '', 'vod_play_from': '好看专线', 'vod_play_url': play_url or '暂无播放地址$0'})
            elif platform == '星芽':
                data = self.safe_json(self.req(f'{p["host"]}{p["detail"]}?theater_parent_id={did}', headers=self.xingya_headers)).get('data') or {}
                vod.update({'vod_name': data.get('title', '未知剧名'), 'vod_type': ','.join([c.get('class_name','') for c in (data.get('class_two') or [])]), 'vod_pic': data.get('cover_url', ''), 'vod_remarks': '连载中' if data.get('is_over') == 2 else '已完结', 'vod_content': data.get('introduction') or data.get('desc') or '', 'vod_play_from': '星芽专线', 'vod_play_url': '#'.join([f'第{it.get("num")}集${it.get("son_video_url")}' for it in (data.get('theaters') or [])]) or '暂无播放地址$0'})
            elif platform == '山海':
                detail = self.shanhaifetch(f'{p["host"]}{p["detail"]}?theater_parent_id={did}')
                eps = [f'{item.get("son_title")}${item.get("son_video_url")}' for item in (detail.get('theaters') or [])]
                vod.update({'vod_name': detail.get('title', '未知短剧'), 'vod_pic': detail.get('cover_url', ''), 'vod_remarks': f'标签:{(" ".join(detail.get("desc_tags") or []))}', 'vod_content': detail.get('introduction', ''), 'vod_play_from': '山海短剧', 'vod_play_url': '#'.join(eps) or '暂无播放地址$0'})
            elif platform == '薏米':
                path = '/video/client/short_play/episode_list'
                pageSize = 30; start_id = 1; total = 999999; episodes = []; body_info = {}
                try:
                    originalStr1 = f'end_id=30&p1=1750574688516674369&p16=22081212C&p2=341201&p21=10&p22=15&p24=0&p25=21200&p28=cca83346da195d11&p29=zy9351ae&p3=102120009&p31=29d1af74b128f29f&p33=com.zhangyue.app.shortplay&p34=force_fsg_nav_bar&p35=BUZGFVakskazFWG2XwZ/LNs4fOnQczc4iivy1qLFvZqmerp2Abe2hv5Tu1jOHQJO5PGANizg3JbzgaTOon0qkmQ==&p4=501609&p5=16&p7=cca83346da195d11&p9=3&pc=10&play_id={did}&start_id=1&usr=tj1290623468&zyeid=4fc4c6737a87b603e1b8ce9210032bae'
                    while start_id <= total:
                        end_id = start_id + pageSize - 1
                        str1 = re.sub(r'(start_id=)\d+', r'\g<1>' + str(start_id), originalStr1)
                        str1 = re.sub(r'(end_id=)\d+', r'\g<1>' + str(end_id), str1)
                        headers = self.yimiGetHeaders(path, str1, 'AAFzKmZkKjIqenUqJCNycSo7Kmw4I3U=')
                        response = self.req(p['host'] + path + '?' + str1, method='GET', headers=headers)
                        json_data = self.safe_json(response)
                        body_info = json_data.get('body', {})
                        list_data = body_info.get('episode_list', [])
                        if not list_data: break
                        if start_id == 1: total = body_info.get('target_count', total)
                        for ep in list_data:
                            playUrl = ep.get('play_url', '')
                            if 'zhangyuecdn' in playUrl: playUrl = 'https://mother-t.d.ireader.com' + playUrl.split('com')[1]
                            episodes.append(f'第{ep.get("order")}集${playUrl}')
                        start_id += pageSize
                    vod.update({'vod_name': body_info.get('name', '未知剧名'), 'vod_pic': body_info.get('cover', ''), 'vod_content': body_info.get('introduce', ''), 'vod_play_from': '薏米短剧', 'vod_play_url': '#'.join(episodes) or '暂无播放地址$0'})
                except Exception: pass
            elif platform == '爽爽':
                try:
                    du = unquote(did)
                    du = du if du.startswith('http') else p['host'] + du
                    html0 = self.req(du, headers={'User-Agent': self.mobileUA})
                    fpu = du
                    mv = re.search(r'<div[^>]*class=["\']movbox["\'][^>]*>[\s\S]*?<a[^>]*href=["\']([^"\']+)["\']', html0, re.I)
                    if mv: fpu = mv.group(1)
                    else:
                        pl = re.search(r'<a[^>]*href=["\']([^"\']*/play/[^"\']+)["\']', html0, re.I)
                        if pl: fpu = pl.group(1)
                    if not fpu.startswith('http'): fpu = p['host'] + fpu
                    
                    playHtml = self.req(fpu, headers={'User-Agent': self.mobileUA})
                    tabs, tabUrls = [], []
                    xl = re.search(r'<div[^>]*class=["\']xianlu["\'][^>]*>([\s\S]*?)</div>', playHtml, re.I)
                    if xl:
                        for m in re.finditer(r'<a[^>]*>([\s\S]*?)</a>', xl.group(1), re.I):
                            th = m.group(0)
                            hr = re.search(r'href=["\']([^"\']+)["\']', th, re.I)
                            if hr:
                                raw = re.sub(r'<[^>]+>', '', th).strip()
                                sm = re.search(r'<small[^>]*>([^<]+)</small>', th, re.I)
                                if sm: raw = raw.replace(sm.group(1), '').strip()
                                tabs.append(raw)
                                u = hr.group(1)
                                if 'javascript' in u: u = fpu
                                elif not u.startswith('http'): u = p['host'] + u
                                tabUrls.append(u)
                    if not tabUrls:
                        tabs.append('爽爽专线')
                        tabUrls.append(fpu)
                    lists = [f"全集${u}" for u in tabUrls]
                    
                    vn_m = re.search(r'<h1[^>]*>([^<]+)</h1>', html0)
                    vn = vn_m.group(1).strip() if vn_m else '爽爽短剧'
                    vp_m = re.search(r'<img[^>]*data-original="([^"]+)"', html0)
                    vp = vp_m.group(1) if vp_m else ''
                    st = re.search(r'<p[^>]*class=["\'][^"\']*zhuangtai[^"\']*["\'][^>]*>([\s\S]*?)</p>', html0, re.I)
                    vr = re.sub(r'<[^>]+>', '', st.group(1)).strip() if st else ''
                    
                    vod.update({'vod_name': vn, 'vod_pic': vp, 'vod_remarks': vr or '爽爽短剧', 'vod_content': '', 'vod_play_from': '$$$'.join(tabs), 'vod_play_url': '$$$'.join(lists)})
                except Exception:
                    vod.update({'vod_name': '爽爽短剧', 'vod_play_from': '爽爽专线', 'vod_play_url': '暂无播放地址$0'})
            elif platform == '喜福':
                dp = did.split('@')
                aid = dp[1] if len(dp)>1 else dp[0]
                total = int(dp[2] if len(dp)>2 else (dp[1] if len(dp)>1 else 1))
                items = [f"{i}${aid}@{i}" for i in range(1, total + 1)]
                vod.update({'vod_name': '喜福短剧', 'vod_play_from': '喜福专线', 'vod_play_url': '#'.join(items) or '暂无播放地址$0'})
            elif platform == '五五':
                html = self.req(f"{p['host']}{p['detail']}{did}.html", headers=self.aggConfig['headers']['default'])
                tm = re.search(r'<title>(.*?)</title>', html, re.I)
                vn = re.split(r'[-_|]', tm.group(1))[0].strip() if tm else '五五短剧'
                
                im = re.search(r'<img[^>]*class="[^"]*\bDramaDetail_bookCover\b[^"]*"[^>]*\bsrc="([^"]+)"', html, re.I) or re.search(r'property="og:image"[^>]+content="([^"]+)"', html, re.I)
                vp = (im.group(1) if im.group(1).startswith('http') else p['host'] + im.group(1)) if im else ''
                
                cm = re.search(r'class="[^"]*(?:detail-content|vod-content|content|descr|intro)[^"]*"[^>]*>([\s\S]*?)</div>', html, re.I)
                vc = re.sub(r'<[^>]+>', '', cm.group(1)).strip() if cm else ''
                
                sources, urls = [], []
                boxes = re.findall(r'<div class="pcDrama_contentBox[\s\S]*?</ul>', html, re.I)
                for box in boxes:
                    titleMatch = re.search(r'pcDrama_titleText">([\s\S]*?)</h3>', box, re.I)
                    if not titleMatch: continue
                    line = re.sub(r'<[^>]+>', '', titleMatch.group(1)).strip()
                    eps = []
                    for m in re.finditer(r'<a[^>]*class="[^"]*\bpcDrama_catalogItem\b[^"]*"[^>]*href="([^"]*vod/play/id/\d+/sid/\d+/nid/(\d+)\.html)"[^>]*>([\s\S]*?)</a>', box, re.I):
                        eps.append({'nid': int(m.group(2)), 'name': m.group(3).strip() or f"第{m.group(2)}集", 'href': m.group(1)})
                    if eps:
                        eps.sort(key=lambda x: x['nid'])
                        sources.append(line)
                        urls.append('#'.join([f"{e['name']}${e['href'] if e['href'].startswith('http') else p['host'] + e['href']}" for e in eps]))
                        
                vod.update({'vod_name': vn, 'vod_pic': vp, 'vod_content': vc, 'vod_play_from': '$$$'.join(sources) or '五五专线', 'vod_play_url': '$$$'.join(urls) or '暂无播放地址$0'})
        except Exception as e:
            print(f'【详情异常】{idv}: {e}')
        return {'list': [vod]}

    def playerContent(self, flag, id, vipFlags):
        idv = id
        try:
            if '五五' in (flag or '') or 'duanju55.com' in idv:
                html = self.req(idv, headers={'Referer': 'https://www.duanju55.com/'})
                vu = ''
                pm = re.search(r'var\s+player_\w+\s*=\s*\{.*?"url"\s*:\s*"([^"]*)"', html, re.I)
                if pm: vu = pm.group(1).replace('\\/', '/')
                if not vu:
                    bm = re.search(r'["\']url["\']\s*:\s*["\']([^"\']+)["\']', html, re.I)
                    if bm and re.match(r'^[A-Za-z0-9+/=]{16,}$', bm.group(1)):
                        try: vu = self.base64Decode(bm.group(1).strip())
                        except: pass
                if not vu:
                    vm = re.search(r'(?:https?:)?//[^\s"\'<>]+\.(?:m3u8|mp4)', html, re.I) or re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html, re.I)
                    if vm: vu = vm.group(1) if len(vm.groups())>0 else vm.group(0)
                if vu:
                    if vu.startswith('//'): vu = 'https:' + vu
                    return {'parse': 0, 'url': vu, 'header': {'User-Agent': self.aggConfig['headers']['default']['User-Agent'], 'Referer': 'https://www.duanju55.com/'}}
                return {'parse': 0, 'url': idv}

            if re.search('好看|百度', flag or ''):
                playletId, vid = (idv.split('@') + [''])[:2]
                inner = f'method=post&vid={vid}&immersive_mode=v4_5&tplname=feed_small_video&tag=playlet_talos&tab=detail&external_from=&is_dp_video=0&immersive_square_type=3&video_set_id={playletId}&play_screen_type=1&play_volume_type=2&play_external_device_type=1'
                url = self.rule['百度']['detailHost'] + self.rule['百度']['play'] if '百度' in flag else self.rule['好看']['host'] + self.rule['好看']['play']
                headers = self.aggConfig['headers']['baidu'] if '百度' in flag else self.aggConfig['headers']['haokan']
                vd = ((self.safe_json(self.req(url, method='POST', headers=headers, data='video/relate=' + quote(inner))).get('video/relate') or {}).get('data') or {}).get('cur_video') or {}
                urlMap = {}
                for c in (vd.get('clarityUrl') or []):
                    if c.get('title') and c.get('url'): urlMap[c.get('title')] = c.get('url')
                if isinstance(vd.get('video_list'), dict):
                    urlMap.update({k: v for k, v in vd.get('video_list').items() if v and k not in urlMap})
                order = {'4k': 0, '2k': 1, '高清': 2, '蓝光': 3, '超清': 4, '标清': 5}
                arr = []
                for q in sorted(urlMap.keys(), key=lambda x: order.get(x, 999)):
                    arr += [q, urlMap[q]]
                return {'parse': 0, 'url': arr or idv}
                
            if '河马' in (flag or ''):
                parts = idv.split('@')
                body = self.hemaEncrypt(json.dumps({'bookId': parts[0], 'chapterIds': [parts[1]], 'unClockType': 'load', 'chapterId': parts[2] if len(parts) > 2 else '', 'resolutionRate': '720P'}, ensure_ascii=False))
                res = self.safe_json(self.req(self.rule['河马']['host'] + self.rule['河马']['play'], method='POST', headers=self.aggConfig['headers']['hema'], data=body))
                try:
                    d = self.safe_json(self.hemaDecrypt(res.get('data', '')))
                    url = (((d.get('chapterInfo') or [{}])[0].get('content') or {}).get('mp4SwitchUrl') or [idv])[0]
                    return {'parse': 0, 'url': url, 'header': self.aggConfig['headers']['hema']}
                except: return {'parse': 0, 'url': idv}

            if '牛牛' in (flag or ''):
                arr = idv.split('+')
                if len(arr) == 2:
                    ep = re.search(r'\d+', arr[0]); ep = ep.group(0) if ep else ''
                    res = self.safe_json(self.req(self.rule['牛牛']['host'] + '/api/v1/app/play/movieDetails', method='POST', headers=self.niuniu_headers, data={'id': arr[1], 'source': 0, 'typeId': 'S1', 'userId': '546932', 'episodeId': ep}, timeout=15, verify=False))
                    if res.get('code') == 200 and (res.get('data') or {}).get('url'):
                        return {'parse': 0, 'url': res['data']['url']}
                elif len(arr) == 3:
                    index, lock_type, thirdPlayId = arr[0], arr[1], arr[2]
                    if lock_type == "free":
                        data1 = 'not_include=0&lock_free=1&type=1&clientVersion=v5.2.5&uuid=6IDYUSASPQY5BBVACWQW3LLTPV4V7DE26UOCX5TZTVUGX4VUJNXQ01&resolution=1080*2320&openudid=82f4175d577a2939&dt=22021211RC&os_api=31&install_id=1496879012031075&sdk_version=1.1.3.0&siteid=5627189&dev_log_aid=667431&oaid=abec0dfff623201b&timestamp=1752498494&direction=0&ac=mobile&os=Android&vod_version=1.10.21.6-tob&os_version=12&count=1&index=1&shortplay_id=' + str(thirdPlayId) + '&sha1=46121F77CE2FCAD3DBC3B9EC8A24908C1A8AD6D9&device_brand=Redmi&package_name=com.niuniu.ztdh.app'
                        fr = self.niuniuPost(self.rule['牛牛']['detail2'], data1, index)
                        lst = ((fr.get('data') or {}).get('list') or [])
                        if lst:
                            u = (((lst[0].get('video_model') or {}).get('video_list') or {}).get('video_1') or {}).get('main_url')
                            if u: return {'parse': 0, 'url': self.base64Decode(u)}
                    else:
                        uld = 'ac=mobile&os=Android&vod_version=1.10.21.6-tob&os_version=12&lock_ad=3&lock_free=3&type=1&clientVersion=v5.2.5&uuid=6IDYUSASPQY5BBVACWQW3LLTPV4V7DE26UOCX5TZTVUGX4VUJNXQ01&resolution=1080*2320&openudid=82f4175d577a2939&shortplay_id=' + str(thirdPlayId) + '&dt=22021211RC&sha1=46121F77CE2FCAD3DBC3B9EC8A24908C1A8AD6D9&lock_index=21&os_api=31&install_id=1496879012031075&device_brand=Redmi&sdk_version=1.1.3.0&package_name=com.niuniu.ztdh.app&siteid=5627189&dev_log_aid=667431&oaid=abec0dfff623201b&timestamp=1752498493'
                        self.niuniuPost(self.rule['牛牛']['unlock'], uld, index)
                        ud = 'not_include=0&lock_free=1&type=1&clientVersion=v5.2.5&uuid=6IDYUSASPQY5BBVACWQW3LLTPV4V7DE26UOCX5TZTVUGX4VUJNXQ01&resolution=1080*2320&openudid=82f4175d577a2939&dt=22021211RC&os_api=31&install_id=1496879012031075&sdk_version=1.1.3.0&siteid=5627189&dev_log_aid=667431&oaid=abec0dfff623201b&timestamp=1752498494&direction=0&ac=mobile&os=Android&vod_version=1.10.21.6-tob&os_version=12&count=1&index=1&shortplay_id=' + str(thirdPlayId) + '&sha1=46121F77CE2FCAD3DBC3B9EC8A24908C1A8AD6D9&device_brand=Redmi&package_name=com.niuniu.ztdh.app'
                        un = self.niuniuPost(self.rule['牛牛']['detail2'], ud, index)
                        lst = ((un.get('data') or {}).get('list') or [])
                        if lst:
                            u = (((lst[0].get('video_model') or {}).get('video_list') or {}).get('video_1') or {}).get('main_url')
                            if u: return {'parse': 0, 'url': self.base64Decode(u)}
                return {'parse': 0, 'url': idv}

            if '爽爽' in (flag or '') or 'djw123.com' in idv:
                pu = idv
                if not pu.startswith('http'):
                    up = idv.split('@')
                    pu = up[1] if len(up)>1 else idv
                    if not pu.startswith('http'): pu = self.rule['爽爽']['host'] + pu
                html = self.req(pu, headers={'User-Agent': self.mobileUA})
                m = re.search(r'var player_[a-zA-Z0-9]+=(.*?)<', html) or re.search(r'player_[a-zA-Z0-9]+=(.*?)<', html) or re.search(r'({"flag":"play".*?})', html)
                if m:
                    pd = json.loads(m.group(1))
                    vu = pd.get('url')
                    if str(pd.get('encrypt')) == "1": vu = unquote(vu)
                    elif str(pd.get('encrypt')) == "2":
                        vu = self.base64Decode(vu)
                        if '%' in vu: vu = unquote(vu)
                    if vu and vu.startswith('http'): return {'parse': 0, 'url': vu}
                vt = re.search(r'<video[^>]*src=["\']([^"\']+)["\']', html, re.I) or re.search(r'<source[^>]*src=["\']([^"\']+)["\']', html, re.I)
                if vt: return {'parse': 0, 'url': vt.group(1)}
                
            if '喜福' in (flag or ''):
                aid, seq = idv.split('@')
                ar = self.safe_json(self.req(f"{self.rule['喜福']['host']}{self.rule['喜福']['playAuth']}?albumId={aid}&seq={seq}", headers={'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36'}))
                if ar.get('data'):
                    vid = ar['data']['vid']
                    cred = json.loads(self.base64Decode(ar['data']['playAuth']))
                    ts = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
                    params = {
                        'Action': 'GetPlayInfo', 'Version': '2017-03-21', 'Format': 'JSON',
                        'AccessKeyId': cred['AccessKeyId'], 'SecurityToken': cred['SecurityToken'],
                        'VideoId': vid, 'AuthInfo': cred.get('AuthInfo', ''), 'Timestamp': ts,
                        'SignatureMethod': 'HMAC-SHA1', 'SignatureVersion': '1.0', 'SignatureNonce': str(uuid.uuid4())
                    }
                    if cred.get('PlayConfig'): params['PlayConfig'] = json.dumps(cred['PlayConfig'])
                    
                    sorted_keys = sorted(params.keys())
                    cqs = '&'.join([f"{quote(k, safe='-._~')}={quote(str(params[k]), safe='-._~')}" for k in sorted_keys])
                    sts = f"GET&%2F&{quote(cqs, safe='-._~')}"
                    key = f"{cred['AccessKeySecret']}&".encode('utf-8')
                    sig = base64.b64encode(hmac.new(key, sts.encode('utf-8'), hashlib.sha1).digest()).decode('utf-8')
                    
                    fu = f"https://vod.{cred.get('Region', 'cn-shanghai')}.aliyuncs.com/?{cqs}&Signature={quote(sig, safe='-._~')}"
                    vr = self.safe_json(self.req(fu, headers={'Accept': '*/*', 'Origin': 'https://minidrama.contentchina.com', 'Referer': 'https://minidrama.contentchina.com/', 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}))
                    if vr.get('PlayInfoList', {}).get('PlayInfo'):
                        return {'parse': 0, 'url': vr['PlayInfoList']['PlayInfo'][0]['PlayURL']}

            if '薏米' in (flag or '') or 'yimi' in (flag or ''):
                valid, vu, ctype = self._validate_media(idv)
                if valid:
                    return {'parse': 0, 'url': vu, 'header': {'User-Agent': self.mobileUA}}
            if '星芽' in (flag or '') or 'xingya' in (flag or ''):
                valid, vu, ctype = self._validate_media(idv)
                if valid:
                    return {'parse': 0, 'url': vu, 'header': {'User-Agent': self.mobileUA}}
        except Exception as e:
            print(f'【播放异常】{flag} {idv}: {e}')
        return {'parse': 0, 'url': idv}

    def searchContent(self, key, quick, pg='1'):
        page = int(pg or 1)
        results = []
        for plat in self.platformList:
            if plat['id'] in ['星星', '喜福']:
                continue
            try:
                results.extend(self.cfs(plat['id'], key, page))
            except Exception as e:
                print(f'【搜索单站异常】{plat["id"]}: {e}')
        return {'list': self.dedup(results), 'page': page, 'pagecount': page + 1, 'limit': len(results), 'total': len(results) * (page + 1)}

    def cfs(self, siteId, wd, page):
        reslist = []
        p = self.rule[siteId]
        prefix = f"{siteId} | "
        
        if siteId == '河马':
            body = self.hemaEncrypt(json.dumps({'keyword': wd, 'page': page, 'size': 15, 'searchSource': '搜索按钮', 'hotWordType': 2, 'tagIds': '', 'reservationSwitch': True}, ensure_ascii=False))
            data = self.safe_json(self.hemaDecrypt(self.safe_json(self.req(p['host'] + p['search'], method='POST', headers=self.aggConfig['headers']['hema'], data=body)).get('data','')))
            for v in data.get('searchVos') or []: reslist.append({'vod_id': f'河马@{v.get("bookId")}', 'vod_name': v.get('bookName',''), 'vod_pic': v.get('coverWap',''), 'vod_remarks': prefix + v.get('finishStatusCn','')})
        elif siteId == '七猫':
            params = {'extend': '', 'page': str(page), 'read_preference': '0', 'track_id': 'ec1280db127955061754851657967', 'wd': wd}
            params['sign'] = self.md5(''.join([f'{k}={params[k]}' for k in sorted(params.keys())]) + self.aggConfig['keys'])
            data = self.safe_json(self.req(p['host'] + p['search'] + '?' + urlencode(params), headers=self.getQiMaoHeaders())).get('data') or {}
            for it in data.get('list') or []: reslist.append({'vod_id': '七猫@' + quote(str(it.get('id') or it.get('playlet_id') or '')), 'vod_name': re.sub('<[^>]+>', '', it.get('title','')).strip(), 'vod_pic': it.get('image_link',''), 'vod_remarks': prefix + str(it.get('total_num',''))})
        elif siteId == '百度':
            t = int(time.time()); version = self.md5(str(t) + 'v2')
            post = {'data': json.dumps({'data': {'from': 'feed', 'pd': 'feed', 'query': wd, 'refreshIndex': page, 'timestamp': t, 'version': version}}, ensure_ascii=False)}
            for it in ((self.safe_json(self.req(p['host'] + p['search'], method='POST', headers=self.aggConfig['headers']['baidu'], data=post)).get('data') or {}).get('items') or []): reslist.append({'vod_id': f'百度@{it.get("collId")}', 'vod_name': it.get('title',''), 'vod_pic': it.get('img',''), 'vod_remarks': prefix + it.get('updateStatus','更新中')})
        elif siteId == '牛牛':
            for it in ((self.safe_json(self.req(p['host'] + p['search'], method='POST', headers=self.niuniu_headers, data={'condition': {'typeId': 'S1', 'value': wd}, 'pageNum': page, 'pageSize': 24}, timeout=15, verify=False)).get('data') or {}).get('records') or []): reslist.append({'vod_id': f'牛牛@{it.get("id")}', 'vod_name': it.get('name',''), 'vod_pic': it.get('cover',''), 'vod_remarks': prefix + (str(it.get('totalEpisode'))+'集' if it.get('totalEpisode') else '')})
        elif siteId == '围观':
            for it in self.safe_json(self.req(p['host'] + p['search'], method='POST', data={'audience': '全部受众', 'page': page, 'pageSize': 30, 'searchWord': wd, 'subject': '全部主题'})).get('data') or []: reslist.append({'vod_id': f'围观@{it.get("oneId")}', 'vod_name': it.get('title',''), 'vod_pic': it.get('vertPoster') or it.get('horizonPoster') or '', 'vod_remarks': f'围观 | 集数:{it.get("episodeCount",0)}'})
        elif siteId == '西饭':
            ts = int(time.time()); url = f'{p["host"]}{p["search"]}?keyword={quote(wd)}84&pageIndex={page}&version=2001001&androidVersionCode=28&requestId={ts}ea3a14bc0317d76f&appId=drama&teenMode=false&userBaseMode=false'
            for soup in ((self.safe_json(self.req(url)).get('result') or {}).get('elements') or []):
                for vod in soup.get('contents') or []:
                    dj = vod.get('duanjuVo') or {}; reslist.append({'vod_id': f'西饭@{dj.get("duanjuId")}#{dj.get("source")}', 'vod_name': dj.get('title',''), 'vod_pic': dj.get('coverImageUrl',''), 'vod_remarks': prefix + '推荐'})
        elif siteId == '好看':
            for item in self.safe_json(self.req(p['host'] + p['search'], method='POST', headers=self.aggConfig['headers']['haokan'], data='search_word=' + quote(wd))).get('data') or []: reslist.append({'vod_id': f'好看@{item.get("id")}', 'vod_name': item.get('title',''), 'vod_pic': item.get('cover_url',''), 'vod_remarks': prefix + (item.get('tag','').replace('/', '·') if item.get('tag') else '')})
        elif siteId == '星芽':
            for item in (((self.safe_json(self.req(p['host'] + p['search'], method='POST', headers=self.xingya_headers, data={'text': wd})).get('data') or {}).get('theater') or {}).get('search_data') or []): reslist.append({'vod_id': f'星芽@{item.get("id")}', 'vod_name': item.get('title',''), 'vod_pic': item.get('cover_url',''), 'vod_remarks': prefix + (str(item.get('total'))+'集' if item.get('total') else ''), 'vod_content': item.get('introduction','')})
            if reslist and wd: reslist = [it for it in reslist if it.get('vod_name') and wd in it['vod_name']]
        elif siteId == '山海':
            try:
                res = self.shanhaifetch(f'{p["host"]}{p["search"]}?text={quote(wd)}')
                search_data = res.get('search_data') or res.get('data') or []
                for i in search_data: reslist.append({'vod_id': f'山海@{i.get("id")}', 'vod_name': i.get('title', ''), 'vod_pic': i.get('cover_url', ''), 'vod_remarks': prefix + f'{i.get("total",0)}集', 'vod_content': i.get('introduction', '')})
            except Exception: pass
        elif siteId == '薏米':
            try:
                path = '/bookstore/search/recommend_data'
                qp = {'keyword': wd, 'p1': '1750574688516674369', 'p16': '22081212C', 'p2': '341201', 'p21': '3', 'p22': '15', 'p24': '0', 'p25': '21200', 'p28': 'cca83346da195d11', 'p29': 'zy9351ae', 'p3': '102120009', 'p31': '29d1af74b128f29f', 'p33': 'com.zhangyue.app.shortplay', 'p34': 'force_fsg_nav_bar', 'p35': 'BUZGFVakskazFWG2XwZ/LNs4fOnQczc4iivy1qLFvZqmerp2Abe2hv5Tu1jOHQJO5PGANizg3JbzgaTOon0qkmQ==', 'p4': '501609', 'p5': '16', 'p7': 'cca83346da195d11', 'p9': '3', 'page': str(page), 'pc': '10', 'resource_type': 'short_play', 'size': '10', 'sort': '1', 'source_type': '0,1', 'type': '0', 'usr': 'tj1290623468', 'zyeid': '4fc4c6737a87b603e1b8ce9210032bae'}
                s1 = '&'.join(f'{k}={qp[k]}' for k in sorted(qp))
                headers = self.yimiGetHeaders(path, s1, 'AAF4IWZnITkqeX4hJCB5eio4IWc4IH4=')
                res = self.safe_json(self.req(f"{p['host']}{path}?{s1}", headers=headers))
                for data in (res.get('body', {}).get('short_play', {}).get('list', [])):
                    reslist.append({'vod_id': f'薏米@{data.get("id")}', 'vod_name': data.get('name', ''), 'vod_pic': data.get('pic', ''), 'vod_remarks': prefix + f'播放量:{data.get("popularity",0)}', 'vod_content': ''})
                if reslist and wd: reslist = [it for it in reslist if it.get('vod_name') and wd in it['vod_name']]
            except Exception: pass
        elif siteId == '爽爽':
            html = self.req(f"{p['host']}{p['searchUrl']}?wd={quote(wd)}", headers={'User-Agent': self.mobileUA})
            sc = re.search(r'<div[^>]*class="search-con"[^>]*>[\s\S]*?</div>', html)
            if sc:
                items = re.findall(r'<li[^>]*>[\s\S]*?</li>', sc.group(0), re.I)
                for it in items:
                    tm = re.search(r'<a[^>]*title="([^"]+)"[^>]*>', it)
                    um = re.search(r'<a[^>]*href="([^"]+)"[^>]*>', it)
                    if tm and um:
                        pm = re.search(r'<img[^>]*data-original="([^"]+)"', it)
                        rm = re.search(r'<span[^>]*class="state"[^>]*>([^<]+)</span>', it)
                        reslist.append({'vod_id': f'爽爽@{quote(um.group(1))}', 'vod_name': tm.group(1), 'vod_pic': pm.group(1) if pm else '', 'vod_remarks': prefix + (rm.group(1) if rm else '')})
        elif siteId == '五五':
            su = f"{p['host']}{p['search']}{quote(wd)}.html"
            if page > 1: su += f"?page={page}"
            html = self.req(su, headers=self.aggConfig['headers']['default'])
            for v in self.parseWuWuList(html, p['host']):
                reslist.append({'vod_id': f"五五@{v['id']}", 'vod_name': v['name'], 'vod_pic': v['pic'], 'vod_remarks': prefix + v['rem']})
                
        return reslist

    def parseWuWuList(self, html, host):
        items = {}
        regex_arr = [
            {'name': 'SecondList_bookName', 'img': 'SecondList_bookImage', 'rem': 'SecondList_totalChapterNum'},
            {'name': 'TagBookList_bookName', 'img': 'TagBookList_bookImageBox', 'rem': 'TagBookList_totalChapterNum'},
            {'name': 'BrowseList_bookName', 'img': 'BrowseList_imageBox', 'rem': 'BrowseList_totalChapterNum'}
        ]
        for pat in regex_arr:
            pat_name, pat_img, pat_rem = pat['name'], pat['img'], pat['rem']
            for m in re.finditer(f'<a[^>]*class="[^"]*\\b{pat_name}\\b[^"]*"[^>]*href="[^"]*vod/detail/id/(\\d+)\\.html"[^>]*>([\\s\\S]*?)</a>', html, re.I):
                id_val, raw_name = m.group(1), m.group(2)
                if id_val not in items: items[id_val] = {'id': id_val, 'name': '', 'pic': '', 'rem': ''}
                sm = re.search(r'<span[^>]*>([^<]+)</span>', raw_name, re.I)
                items[id_val]['name'] = sm.group(1).strip() if sm else re.sub(r'<[^>]+>', '', raw_name).strip()
            for m in re.finditer(f'<a[^>]*class="[^"]*\\b{pat_img}\\b[^"]*"[^>]*href="[^"]*vod/detail/id/(\\d+)\\.html"[^>]*>([\\s\\S]*?)</a>', html, re.I):
                if m.group(1) in items:
                    im = re.search(r'<img[^>]*\bsrc="([^"]+)"', m.group(2), re.I)
                    if im: items[m.group(1)]['pic'] = im.group(1) if im.group(1).startswith('http') else host + im.group(1)
            for m in re.finditer(f'<a[^>]*class="[^"]*\\b{pat_rem}\\b[^"]*"[^>]*href="[^"]*vod/detail/id/(\\d+)\\.html"[^>]*>([\\s\\S]*?)</a>', html, re.I):
                if m.group(1) in items: items[m.group(1)]['rem'] = re.sub(r'<[^>]+>', '', m.group(2)).strip()
        return list(items.values())

    def _make_filters(self):
        simple = {
            '河马': [('强爽男频','10@强爽男频'),('女频虐恋','11@女频虐恋'),('古装大剧','12@古装大剧'),('豪门总裁','13@豪门总裁'),('重生逆袭','14@重生逆袭')],
            '七猫': [('全部',''),('推荐','0'),('新剧','-1'),('都市情感','1273'),('古装','1272'),('都市','571'),('玄幻仙侠','1286'),('奇幻','570'),('乡村','590'),('民国','573'),('年代','572'),('青春校园','1288'),('武侠','371'),('科幻','594'),('末世','556'),('二次元','1289'),('逆袭','400'),('穿越','373'),('复仇','795'),('系统','787'),('权谋','790'),('重生','784'),('女性成长','1294'),('打脸虐渣','716'),('闪婚','480'),('强者回归','402'),('追妻火葬场','715'),('家庭','670'),('马甲','558'),('职场','724'),('宫斗','343'),('高手下山','1299'),('娱乐明星','1295'),('异能','727'),('宅斗','342'),('替身','712'),('穿书','338'),('商战','723'),('种田经商','1291'),('伦理','1293'),('社会话题','1290'),('致富','492'),('偷听心声','1258'),('脑洞','526'),('豪门总裁','624'),('萌宝','356'),('战神','527'),('真假千金','812'),('赘婿','36'),('神医','1269'),('神豪','37'),('小人物','1296'),('团宠','545'),('欢喜冤家','464'),('女帝','617'),('银发','1297'),('兵王','28'),('虐恋','16'),('甜宠','21'),('悬疑','27'),('搞笑','793'),('灵异','1287')],
            '百度': [('新剧','新剧'),('限时免费','限时免费'),('精选','精选'),('独播','独播'),('全部','全部题材'),('神医','神医'),('连续剧','连续剧'),('都市','都市'),('现代言情','现代言情'),('异能','异能'),('逆袭','逆袭'),('甜宠','甜宠'),('总裁','总裁'),('萌宝','萌宝'),('战神','战神'),('宫斗宅斗','宫斗宅斗'),('神豪','神豪'),('虐恋','虐恋'),('闪婚','闪婚'),('玄幻','玄幻'),('穿越重生','穿越重生'),('年代','年代'),('家庭伦理','家庭伦理'),('古代言情','古代言情'),('武侠武打','武侠武打'),('赘婿','赘婿'),('单元剧','单元剧'),('青春校园','青春校园'),('历史架空','历史架空'),('王妃','王妃'),('鉴宝','鉴宝'),('科幻','科幻'),('军旅战争','军旅战争'),('种田','种田')],
            '牛牛': [('全部',''),('现言','现言'),('古言','古言'),('历史','历史'),('都市','都市'),('活动','活动'),('逆袭','逆袭'),('豪门','豪门'),('现代言情','现代言情'),('战神','战神'),('甜宠','甜宠'),('穿越','穿越'),('古装','古装'),('虐心','虐心'),('神医','神医'),('赘婿','赘婿'),('亲情','亲情'),('复仇','复仇'),('玄幻','玄幻'),('古代言情','古代言情'),('热血','热血'),('动作','动作'),('喜剧','喜剧'),('悬疑','悬疑'),('军事','军事'),('二次元','二次元'),('未来','未来'),('快速穿越','快速穿越'),('烧脑','烧脑'),('治愈','治愈'),('其他剧情','其他剧情')],
            '围观': [('全部','')],
            '西饭': [('都市','68@都市'),('青春','68@青春'),('现代言情','81@现代言情'),('豪门','81@豪门'),('大女主','80@大女主'),('逆袭','79@逆袭'),('打脸虐渣','79@打脸虐渣'),('穿越','81@穿越')],
            '星星': [('甜宠','1287'),('逆袭','1288'),('热血','1289'),('现代','1290'),('古代','1291')],
            '好看': [('热播剧','1'),('新剧','2'),('战神','1001'),('神豪','2001'),('神医','1002'),('甜宠','1007'),('赘婿','1003'),('穿越重生','2004'),('异能','2005'),('虐恋','1006'),('宫斗宅斗','2006'),('玄幻','2009')],
            '星芽': [('剧场','1'),('热播剧','2'),('会员专享','8'),('星选好剧','7'),('新剧','3'),('阳光剧场','5')],
            '山海': [('剧场','1'),('热播剧','2'),('会员专享','8'),('星选好剧','7'),('新剧','3'),('阳光剧场','5')],
            '薏米': [('精选','channel_c6f50cd9'),('逆袭','channel_a8e10abc'),('复仇','channel_d26dd434'),('恋爱','channel_75afe84a'),('重生','channel_2272aac5'),('古风','channel_73190d4f'),('神医','channel_2d7eae6b'),('言情','channel_614820bd'),('都市','channel_13dfce8b'),('悬疑','channel_861b9642'),('历史','channel_18157927')],
            '爽爽': [('全部',''),('女频恋爱','女频恋爱'),('脑洞悬疑','脑洞悬疑'),('年代穿越','年代穿越'),('古装仙侠','古装仙侠'),('现代都市','现代都市'),('反转','反转'),('爽文','爽文'),('短剧','短剧')],
            '五五': [('全部','全部'),('男频','男频'),('女频','女频'),('都市','都市'),('虐渣','虐渣'),('励志','励志'),('逆袭','逆袭'),('古风','古风'),('复仇','复仇'),('家庭','家庭'),('悬疑','悬疑'),('奇幻','奇幻')]
        }
        return {k: [{'key': 'area', 'name': '分类', 'value': [{'n': n, 'v': v} for n, v in vals]}] for k, vals in simple.items()}

    def req(self, url, method='GET', headers=None, data=None, timeout=None, verify=None):
        try:
            h = dict(self.aggConfig['headers']['default']); h.update(headers or {})
            if method.upper() == 'POST':
                body = data
                if isinstance(data, (dict, list)):
                    ct = h.get('Content-Type') or h.get('content-type') or ''
                    body = json.dumps(data, ensure_ascii=False) if 'json' in ct else urlencode(data)
                r = self.session.post(url, headers=h, data=body, timeout=timeout or self.timeout, verify=verify)
            else:
                r = self.session.get(url, headers=h, timeout=timeout or self.timeout, verify=verify)
            r.encoding = r.apparent_encoding or 'utf-8'
            return r.text
        except Exception as e:
            print(f'【请求异常】{url} - {e}')
            return ''

    def safe_json(self, s, default=None):
        if default is None: default = {}
        if isinstance(s, (dict, list)): return s
        try: return json.loads(s or '{}')
        except Exception: return default

    def dedup(self, arr):
        seen, out = set(), []
        for x in arr:
            vid = x.get('vod_id')
            if vid and vid not in seen:
                seen.add(vid); out.append(x)
        return out

    def md5(self, s): return hashlib.md5(str(s).encode()).hexdigest().lower()
    def hmacSHA256(self, data, key): return hmac.new(key.encode(), data.encode(), hashlib.sha256).hexdigest()
    def base64Encode(self, text): return base64.b64encode(text.encode()).decode()
    def base64Decode(self, text):
        try: return base64.b64decode(text).decode()
        except Exception: return ''

    def yimiRsaSign(self, data):
        if RSA is None or pkcs1_15 is None or SHA256 is None: return ''
        try:
            private_key = RSA.import_key(self.yimi_privateKey)
            h = SHA256.new(data.encode())
            signature = pkcs1_15.new(private_key).sign(h)
            return base64.b64encode(signature).decode()
        except Exception as e:
            return ''

    def yimiGetHeaders(self, path, params, sec):
        x_sig_timestamp = str(int(time.time() * 1000))
        str3 = '&' + params + '&' + path + '&' + x_sig_timestamp + '&' + sec
        sign = self.yimiRsaSign(str3)
        return {
            'x-appid': 'zy9351ae',
            'x-sig-timestamp': x_sig_timestamp,
            'x-sig-alg': 'RSA-SHA256',
            'x-sig-sign': sign,
            'x-sig-ver': 'v1.1',
            'x-sig-sec': sec,
            'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 15; 22081212C Build/AQ3A.241006.001)'
        }

    def shanhaiaesGcmDecrypt(self, cipherHex, ivHex):
        if AES is None: return {}
        try:
            key = 'xxxxxxwhwqedqder'.encode()
            iv = bytes.fromhex(ivHex)
            ciphertext = bytes.fromhex(cipherHex)
            tag_length = 16
            data = ciphertext[:-tag_length]
            tag = ciphertext[-tag_length:]
            cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
            decrypted = cipher.decrypt_and_verify(data, tag)
            return json.loads(decrypted.decode())
        except Exception as e:
            return {}

    def shanhaifetch(self, url, method='GET', data=None):
        if not self.sh_token: self.shanhaiauth()
        if not self.sh_token: return {}
        headers = {'authorization': self.sh_token, 'Content-Type': 'application/json'}
        try:
            response = self.req(url, method='POST', headers=headers, data=data) if method == 'POST' else self.req(url, headers=headers)
            if not response: return {}
            res = json.loads(response)
            if not res.get('data') or not res['data'].get('data') or not res['data'].get('nonce'): return {}
            return self.shanhaiaesGcmDecrypt(res['data']['data'], res['data']['nonce'])
        except Exception as e:
            return {}

    def shanhaiauth(self):
        if self.sh_token: return
        try:
            body = json.dumps({'device': '22ebfeec0a5ad3c0397bae448b8658cc3', 'install_first_open': True, 'first_install_time': 1751687627754, 'last_update_time': 1751687627754, 'report_link_url': '', 'android_id': '8f7db6f23d745890', 'package_name': 'com.shanhai.duanju', 'authorization': '', 'timestamp': int(time.time() * 1000)}, ensure_ascii=False)
            encrypted_body = self.aesEncryptECB(body, 'B@ecf920Od8A4df7')
            login_res = self.req(self.rule['山海']['login'], method='POST', headers={'content-type': 'application/json; charset=utf-8'}, data=encrypted_body)
            if login_res:
                res = json.loads(login_res)
                if res.get('data') and res['data'].get('token'):
                    self.sh_token = res['data']['token']
        except Exception: pass

    def niuniuPost(self, url1, data1, index):
        try:
            t10 = str(int(time.time()))
            nonce = 'X9UknYKtLa3DmtjC'
            body1 = re.sub(r'&lock_free=\d+', '&lock_free=1', data1)
            body1 = re.sub(r'&timestamp=\d+', '&timestamp=' + t10, body1)
            body1 = re.sub(r'&count=\d+', '&count=1', body1)
            body1 = re.sub(r'&index=\d+', '&index=' + str(index), body1)
            body1 = re.sub(r'&lock_ad=\d+', '&lock_ad=1', body1)
            body1 = re.sub(r'&lock_index=\d+', '&lock_index=' + str(index), body1)
            enc = self.aesEncryptECB(body1, 'ce49b18dd4e0a4d8')
            sign = self.hmacSHA256(t10 + nonce + body1, 'aceaa47f96b4875d446b2e1d97e03bbb')
            res = self.req(url1, method='POST', headers={'X-Salt': 'FD8188A8D5', 'X-Nonce': nonce, 'X-Timestamp': t10, 'X-Access-Token': self.niuniu_access_token, 'X-Signature': sign, 'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': 'okhttp/4.12.0'}, data=enc, timeout=20)
            dec = self.aesDecryptECB(res, 'ce49b18dd4e0a4d8') if res else ''
            return self.safe_json(dec)
        except Exception: return {}

    def aesEncryptECB(self, text, key):
        if AES is None: return ''
        return base64.b64encode(AES.new(key.encode(), AES.MODE_ECB).encrypt(pad(text.encode(), 16))).decode()
    def aesDecryptECB(self, ciphertext, key):
        if AES is None: return ''
        try: return unpad(AES.new(key.encode(), AES.MODE_ECB).decrypt(base64.b64decode(ciphertext)), 16).decode()
        except Exception: return ''
    def hemaEncrypt(self, plaintext):
        if AES is None: return ''
        key = base64.b64decode('ZHpramdmeXhnc2h5bGd6bQ=='); iv = base64.b64decode('YXBpdXBkb3duZWRjcnlwdA==')
        return base64.b64encode(AES.new(key, AES.MODE_CBC, iv).encrypt(pad(plaintext.encode(), 16))).decode()
    def hemaDecrypt(self, ciphertext):
        if AES is None: return '{}'
        try:
            key = base64.b64decode('ZHpramdmeXhnc2h5bGd6bQ=='); iv = base64.b64decode('YXBpdXBkb3duZWRjcnlwdA==')
            return unpad(AES.new(key, AES.MODE_CBC, iv).decrypt(base64.b64decode(ciphertext)), 16).decode()
        except Exception: return '{}'

    def getQiMaoHeaders(self):
        sessionId = str(int(time.time() * 1000))
        js = json.dumps({'static_score':'0.8','uuid':'00000000-7fc7-08dc-0000-000000000000','device-id':'20250220125449b9b8cac84c2dd3d035c9052a2572f7dd0122edde3cc42a70','mac':'','sourceuid':'aa7de295aad621a6','refresh-type':'0','model':'22021211RC','wlb-imei':'','client-id':'aa7de295aad621a6','brand':'Redmi','oaid':'','oaid-no-cache':'','sys-ver':'12','trusted-id':'','phone-level':'H','imei':'','wlb-uid':'aa7de295aad621a6','session-id':sessionId}, separators=(',', ':'))
        b64 = self.base64Encode(js).replace('\n','').replace('\r','').replace(' ','')
        qm = ''.join([self.aggConfig['charMap'].get(c, c) for c in b64])
        sign = self.md5(f'AUTHORIZATION=app-version=10001application-id=com.duoduo.readchannel=unknownis-white=net-env=5platform=androidqm-params={qm}reg={self.aggConfig["keys"]}')
        h = {'net-env':'5','reg':'','channel':'unknown','is-white':'','platform':'android','application-id':'com.duoduo.read','AUTHORIZATION':'','app-version':'10001','User-Agent':'okhttp/4.10.0','qm-params':qm,'sign':sign,'Content-Type':'application/json'}
        return h

    def isVideoFormat(self, url): return True
    def manualVideoCheck(self): return True
    def destroy(self): pass

    def _validate_media(self, url, timeout=8):
        """真直链验证门禁：对 parse:0 直链做轻量探测，确认可访问且为媒体内容。
        返回 (valid, probe_url, ctype)；探测失败不阻塞播放，交由播放器自行兜底。"""
        try:
            if not url or not str(url).startswith('http'):
                return (True, url, '')
            import requests as _req
            r = _req.get(str(url), headers={'User-Agent': self.mobileUA}, stream=True, timeout=timeout, verify=False)
            ctype = (r.headers.get('Content-Type') or '').lower()
            ctype = ctype.split(';')[0].strip()
            head = r.raw.read(12) if r.raw else b''
            r.close()
            valid = ('video/' in ctype or 'audio/' in ctype or 'application/octet-stream' in ctype
                     or head[:4] == b'\x00\x00\x00\x18\x66\x74\x79\x70' or url.endswith(('.mp4', '.m3u8', '.ts', '.flv')))
            return (valid, url, ctype)
        except Exception:
            return (True, url, '')

