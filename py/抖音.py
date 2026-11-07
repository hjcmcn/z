"""抖音直播源（Python）。

首頁分區 / 遊戲題材文件夾 / 分區列表 / 搜尋 / 房間詳情 / 多線路播放 / FLV 代理 / PushFrame 彈幕。
"""

import hashlib
import json
import random
import re
import threading
import time
from urllib.parse import quote, unquote

from base.spider import Spider as BaseSpider

try:
    import zlib
except ImportError:  # 極端精簡的執行環境：退回純 Python inflate
    zlib = None

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
)
UA_PHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_4_1 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Mobile/15E148 Safari/604.1"
)
STYLE = {"type": "rect", "ratio": 1.78}
FOLDER = {"type": "oval", "ratio": 1}
NAME = "抖音"

DOUYIN = "https://live.douyin.com"
LIMIT = 15
COVER = "https://p3-sign.douyinpic.com/tos-cn-i-0813c001_ov~tplv-dy-360p.jpeg"
AMEMV = ("https://webcast.amemv.com/webcast/room/reflow/info/"
         "?type_id=0&live_id=1&room_id={rid}&app_id=1128")
ENTER = "https://live.douyin.com/webcast/room/web/enter/?web_rid={rid}"
CATEGORY = "https://live.douyin.com/categorynew/{cid}"
# partition 端點必須帶結尾斜線，少了會被 301 導向（實測）
PARTITION = "https://webcast.amemv.com/webcast/web/partition/detail/room/v2/"
# 抖音 FLV 的清晰度檔位（服務端 key，由高到低）
TIER_KEYS = ["FULL_HD1", "HD1", "SD2", "SD1"]
# 抖音彈幕（PushFrame 推播通道）連線主機
WS_HOST = "webcast5-ws-web-lq.douyin.com"
# 握手 query 裡的瀏覽器版本字串（含空格與括號，需編碼後才能放進請求行）
BROWSER_VERSION = ("5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
# 抖音匿名設備標識（服務端簽發，與帳號/IP 無關）。
# 握手失敗（0 條彈幕）時，用瀏覽器打開 https://www.douyin.com/ ，
# F12 → Application → Cookies → 複製 ttwid 的值替換這裡即可。
TTWID = "1%7CBlJW6QLUOMobm9QCkBo2ylE6B9fmHaGaRaKpvfqnB-c%7C1793245161%7Ce4118363fae163cf41626d20b5da4ce144c2dfbabe1c4a0569e78a8e2c7b4199"

GROUPS = [
    {
        "id": "4_101",
        "name": "聊天"
    },
    {
        "id": "4_102",
        "name": "音樂"
    },
    {
        "id": "4_103",
        "name": "遊戲"
    },
    {
        "id": "4_104",
        "name": "二次元"
    },
    {
        "id": "4_105",
        "name": "舞蹈"
    },
    {
        "id": "4_106",
        "name": "文化"
    },
    {
        "id": "4_107",
        "name": "生活"
    },
    {
        "id": "4_108",
        "name": "運動"
    }
]

TIERS = [
    {
        "extra": "flv-hd",
        "name": "高清",
        "key": "HD1"
    },
    {
        "extra": "flv-full",
        "name": "原畫",
        "key": "FULL_HD1"
    },
    {
        "extra": "flv-sd2",
        "name": "標清",
        "key": "SD2"
    },
    {
        "extra": "flv-sd1",
        "name": "流暢",
        "key": "SD1"
    }
]

THEMES = [
    {
        "id": "1",
        "name": "射擊",
        "icon": "射击"
    },
    {
        "id": "2",
        "name": "競技",
        "icon": "竞技"
    },
    {
        "id": "3",
        "name": "單機",
        "icon": "单机"
    },
    {
        "id": "4",
        "name": "棋牌",
        "icon": "棋牌"
    },
    {
        "id": "5",
        "name": "休閒益智",
        "icon": "休闲益智"
    },
    {
        "id": "6",
        "name": "角色扮演",
        "icon": "角色扮演"
    },
    {
        "id": "7",
        "name": "策略卡牌",
        "icon": "策略卡牌"
    }
]

# 平台回傳的遊戲名 → 封面圖；不在表內的回退到通用封面
ICONS = {
    "聊天": "https://sta-op.douyucdn.cn/dycatr/4ded577f1e24c20a154224d8f3c1314e.png",
    "音乐": "https://sta-op.douyucdn.cn/dycatr/6802657732dcf0d2b697ef2812b560fe.png",
    "游戏": "https://sta-op.douyucdn.cn/dycatr/029aebe5e2870c641fc892d1ec557340.png",
    "二次元": "https://huyaimg.msstatic.com/cdnimage/game/2633-MS.png",
    "舞蹈": "https://sta-op.douyucdn.cn/dycatr/6513d0c06eb21b58180391f7f40acfab.png",
    "文化": "https://huyaimg.msstatic.com/cdnimage/game/5883-MS.png",
    "生活": "https://huyaimg.msstatic.com/cdnimage/game/2165-MS.png",
    "运动": "https://huyaimg.msstatic.com/cdnimage/game/2356-MS.png",
    "和平精英": "https://sta-op.douyucdn.cn/dycatr/7a279ffad4cc5210630fdf48e079e498.png",
    "无畏契约": "https://sta-op.douyucdn.cn/dycatr/94701504720fb986ae5b331f7035f670.png",
    "绝地求生": "https://huyaimg.msstatic.com/cdnimage/game/2793-MS.png",
    "CSGO": "https://huyaimg.msstatic.com/cdnimage/game/862-MS.png",
    "三角洲行动": "https://huyaimg.msstatic.com/cdnimage/game/9449-MS.png",
    "穿越火线": "https://huyaimg.msstatic.com/cdnimage/game/4-MS.png",
    "暗区突围": "https://sta-op.douyucdn.cn/dycatr/e25f37f9f8708f522575d2ac30fd035f.png",
    "萤火突击": "https://sta-op.douyucdn.cn/dycatr/9bb006fc766d7e451ecaa0ad2ca945ae.png",
    "逆战": "https://huyaimg.msstatic.com/cdnimage/game/135-MS.png",
    "穿越火线：枪战王者": "https://huyaimg.msstatic.com/cdnimage/game/6079-MS.png",
    "Apex英雄": "https://sta-op.douyucdn.cn/dycatr/07ab87b4ad7669a7acf00a6c7ac54b7a.png",
    "使命召唤手游": "https://sta-op.douyucdn.cn/dycatr/0ccda2540d5859e678fd925eb15732fe.png",
    "使命召唤": "https://sta-op.douyucdn.cn/dycatr/933548f19fded4bf60868c612a14a5aa.png",
    "漫威争锋": "https://sta-op.douyucdn.cn/dycatr/18aa221277a72cd34063a241d1ee7669.jpg",
    "守望先锋": "https://sta-op.douyucdn.cn/dycatr/8def0af581d3f883e67e4a932c0207ce.png",
    "反恐精英OL": "https://sta-op.douyucdn.cn/dycatr/4d38b219e425e858aa4c45783e393abb.png",
    "逃离塔科夫": "https://sta-op.douyucdn.cn/dycatr/d19b35ea855a0d22f9cf51f2796b7f92.png",
    "荒野行动": "https://sta-op.douyucdn.cn/dycatr/5e474b73543f55e488fdfd2098ade110.png",
    "战地5": "https://sta-op.douyucdn.cn/dycatr/e22e30b1ecdb4681ea08e80017302014.png",
    "战地1": "https://sta-op.douyucdn.cn/dycatr/a7a4a69989af446dfb61802dc676cea4.png",
    "超凡先锋": "https://sta-op.douyucdn.cn/dycatr/023c3c4f555748a59933696642688dab.png",
    "高能英雄": "https://sta-op.douyucdn.cn/dycatr/c8104984900354030c2f5d0c617b7f82.png",
    "战术小队": "https://sta-op.douyucdn.cn/dycatr/f22e827fd6a7c20c2e6f33c22e9dbc43.png",
    "生死狙击2": "https://sta-op.douyucdn.cn/dycatr/a7fdce05db9e4d6100ece5ad8ac581a7.png",
    "生死狙击": "https://sta-op.douyucdn.cn/dycatr/b92c11252d1906df43972413575641d4.png",
    "The Finals": "https://sta-op.douyucdn.cn/dycatr/5c131884efe9212ef18ae34ba4887ccf.png",
    "堡垒之夜": "https://sta-op.douyucdn.cn/dycatr/db3c68535c0ca07b28680f85c9489eb2.png",
    "火线精英2": "https://sta-op.douyucdn.cn/dycatr/145c29db806a635ea2cacecacca21687.png",
    "不羁联盟": "https://sta-op.douyucdn.cn/dycatr/499323877039778e4b29ebc19cba33a8.png",
    "迷你枪战精英": "https://sta-op.douyucdn.cn/dycatr/884c66c19449b1f8f24eb523625f2c29.png",
    "香肠派对": "https://sta-op.douyucdn.cn/dycatr/92a2d549e03db169bfb83b93596da403.png",
    "卡拉彼丘": "https://sta-op.douyucdn.cn/dycatr/a113cb415f53268bbccfc5a8320eacda.png",
    "金铲铲之战": "https://sta-op.douyucdn.cn/dycatr/2b8d3e8459f5eef5a6dd8668daf1b4e9.png",
    "英雄联盟手游": "https://huyaimg.msstatic.com/cdnimage/game/6203-MS.png",
    "王者荣耀": "https://sta-op.douyucdn.cn/dycatr/3b2ace365b8d7bf14fef476e5d9840a9.png",
    "英雄联盟": "https://sta-op.douyucdn.cn/dycatr/560457aa8334716cc698b4a5eb15e10a.png",
    "永劫无间": "https://sta-op.douyucdn.cn/dycatr/38fb15f3fbd665fba505d132d05a2679.png",
    "云顶之弈": "https://sta-op.douyucdn.cn/dycatr/5b18b5d30d3617fcfe75f2850eba8a3a.png",
    "第五人格": "https://sta-op.douyucdn.cn/dycatr/93cb91b313debb482afe5d2c78573b4a.png",
    "永劫无间手游": "https://sta-op.douyucdn.cn/dycatr/30ad2e7c1bea3a30bd6e48774fd126d5.png",
    "魔兽争霸3": "https://sta-op.douyucdn.cn/dycatr/38de3e53bea36b535b85674ab90c1f9e.png",
    "炉石传说": "https://sta-op.douyucdn.cn/dycatr/00900615a0d66965e6f95d62d624b79a.png",
    "巅峰极速": "https://sta-op.douyucdn.cn/dycatr/3254c715df6d3d347918b77320bbf6dc.png",
    "QQ飞车端游": "https://huyaimg.msstatic.com/cdnimage/game/2928-MS.png",
    "DOTA2": "https://sta-op.douyucdn.cn/dycatr/6e265cc11d4acd1b3aa15b672c5092e3.png",
    "QQ飞车手游": "https://sta-op.douyucdn.cn/dycatr/62ca8041f563dd30423866af2b500555.png",
    "DOTA1": "https://huyaimg.msstatic.com/cdnimage/game/7-MS.png",
    "无畏契约：源能行动": "https://huyaimg.msstatic.com/cdnimage/game/62639-MS.png",
    "暗区突围：无限": "https://huyaimg.msstatic.com/cdnimage/game/10963-MS.png",
    "逆战手游": "https://huyaimg.msstatic.com/cdnimage/game/135-MS.png",
    "失控进化": "https://i0.hdslb.com/bfs/live/4852b4750f4115a0f47631db01317ee5bde9c1f7.png",
    "彩虹六号：围攻": "https://huyaimg.msstatic.com/cdnimage/game/2327-MS.png",
    "解限机": "https://huyaimg.msstatic.com/cdnimage/game/10961-MS.png",
    "远光84": "https://i0.hdslb.com/bfs/live/20fba7aa84c17b0a9aa5dec01404a2b3201458f4.jpg",
    "超自然行动组": "https://i0.hdslb.com/bfs/live/49ab6e850ad2334d5f3bb1d6ed66c15d74518f56.jpg",
    "坦克世界": "https://huyaimg.msstatic.com/cdnimage/game/802-MS.png",
    "红色警戒2": "https://i0.hdslb.com/bfs/live/3515dc05ff44427b0e3f01a7a7655ce82f5a0544.png",
    "战争雷霆": "https://huyaimg.msstatic.com/cdnimage/game/624-MS.png",
    "狼人杀": "https://huyaimg.msstatic.com/cdnimage/game/2785-MS.png",
    "跑跑卡丁车": "https://huyaimg.msstatic.com/cdnimage/game/162-MS.png",
    "跑跑卡丁车官方竞速版": "https://huyaimg.msstatic.com/cdnimage/game/162-MS.png",
    "王者万象棋": "https://huyaimg.msstatic.com/cdnimage/game/8127-MS.png",
    "星际争霸": "https://huyaimg.msstatic.com/cdnimage/game/5-MS.png",
    "三国杀": "https://huyaimg.msstatic.com/cdnimage/game/1669-MS.png",
    "极品飞车：集结": "https://huyaimg.msstatic.com/cdnimage/game/9421-MS.png",
    "战舰世界": "https://huyaimg.msstatic.com/cdnimage/game/1947-MS.png",
    "恐惧饥荒": "https://huyaimg.msstatic.com/cdnimage/game/74-MS.png",
    "王牌竞速": "https://huyaimg.msstatic.com/cdnimage/game/6463-MS.png",
    "皇室战争": "https://huyaimg.msstatic.com/cdnimage/game/2439-MS.png",
    "猫和老鼠": "https://i0.hdslb.com/bfs/vc/1608107c14864384b9f569185ad5c804433e04a3.png",
    "星际争霸2": "https://i0.hdslb.com/bfs/vc/7217538bea375fd81ec908723fbae0ab455ec693.png",
    "决战！平安京": "https://i0.hdslb.com/bfs/live/3ea2ad8569e0508f5de1a176b20e4c313b119e8a.png",
    "实况足球": "https://huyaimg.msstatic.com/cdnimage/game/3741-MS.png",
    "决胜巅峰": "https://huyaimg.msstatic.com/cdnimage/game/7537-MS.png",
    "极品飞车": "https://huyaimg.msstatic.com/cdnimage/game/9421-MS.png",
    "逃跑吧！少年": "https://huyaimg.msstatic.com/cdnimage/game/4137-MS.png",
    "极限竞速：地平线5": "https://huyaimg.msstatic.com/cdnimage/game/2634-MS.png",
    "坦克世界：闪电战": "https://huyaimg.msstatic.com/cdnimage/game/802-MS.png",
    "游戏王：决斗链接": "https://huyaimg.msstatic.com/cdnimage/game/4451-MS.png",
    "哈利波特：魔法觉醒": "https://huyaimg.msstatic.com/cdnimage/game/5835-MS.png",
    "荒野乱斗": "https://huyaimg.msstatic.com/cdnimage/game/4613-MS.png",
    "AmongUs": "https://huyaimg.msstatic.com/cdnimage/game/6163-MS.png",
    "曙光英雄": "https://huyaimg.msstatic.com/cdnimage/game/6169-MS.png",
    "梦三国": "https://huyaimg.msstatic.com/cdnimage/game/489-MS.png",
    "宝可梦大集结": "https://i0.hdslb.com/bfs/im/b15cf67865399226ac699b15fb7de38c1509c7ee.png",
    "极限竞速：地平线4": "https://huyaimg.msstatic.com/cdnimage/game/2634-MS.png",
    "阴阳师：妖怪小班": "https://huyaimg.msstatic.com/cdnimage/game/2598-MS.png",
    "影之诗": "https://i0.hdslb.com/bfs/live/82edc4454c681a39a75c3fc1f43c213d329edbb1.png",
    "植物大战僵尸": "https://huyaimg.msstatic.com/cdnimage/game/485-MS.png",
    "黑神话：悟空": "https://huyaimg.msstatic.com/cdnimage/game/6111-MS.png",
    "方舟": "https://huyaimg.msstatic.com/cdnimage/game/1997-MS.png",
    "星露谷物语": "https://huyaimg.msstatic.com/cdnimage/game/2443-MS.png",
    "饥荒": "https://huyaimg.msstatic.com/cdnimage/game/74-MS.png",
    "星际战甲": "https://i0.hdslb.com/bfs/live/915f580c0cd68e8303ef5f8f140da4f7ddfc55fa.png",
    "俄罗斯钓鱼4": "https://huyaimg.msstatic.com/cdnimage/game/5495-MS.png",
    "艾尔登法环": "https://huyaimg.msstatic.com/cdnimage/game/5801-MS.png",
    "泰拉瑞亚": "https://message.biliimg.com/bfs/im/ff37eb0c1a7ace5cecbfc0dee5c701809d801746.png",
    "拳皇97": "https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/702120/library_600x900.jpg",
    "幻兽帕鲁": "https://huyaimg.msstatic.com/cdnimage/game/9961-MS.png",
    "只狼：影逝二度": "https://huyaimg.msstatic.com/cdnimage/game/4505-MS.png",
    "荒野大镖客2": "https://i0.hdslb.com/bfs/vc/b7e12939b9ff865fc478283b4fcedb971e5b0092.png",
    "猛兽派对": "https://huyaimg.msstatic.com/cdnimage/game/6165-MS.png",
    "双影奇境": "https://huyaimg.msstatic.com/cdnimage/game/70355-MS.png",
    "流放之路2": "https://huyaimg.msstatic.com/cdnimage/game/427-MS.png",
    "骑马与砍杀2：霸主": "https://i0.hdslb.com/bfs/vc/4185dad552d1110b7821506da1b6747affacb611.png",
    "空洞骑士：丝之歌": "https://i0.hdslb.com/bfs/live/6b7dfc1a6a7c3cb1278f78b5f4a60e0fa158e3e3.jpg",
    "怪物猎人：荒野": "https://huyaimg.msstatic.com/cdnimage/game/69017-MS.png",
    "流放之路": "https://huyaimg.msstatic.com/cdnimage/game/427-MS.png",
    "绝地潜兵2": "https://i0.hdslb.com/bfs/live/56c6c46f8eae445492d1c4f17983e17f7701f3f3.png",
    "命运2": "https://huyaimg.msstatic.com/cdnimage/game/2942-MS.png",
    "塞尔达传说：旷野之息": "https://i0.hdslb.com/bfs/live/ce88445ce681501f9c38c6e046a98b4512180ca4.png",
    "森林之子": "https://huyaimg.msstatic.com/cdnimage/game/7943-MS.png",
    "拳皇98": "https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/222420/library_600x900.jpg",
    "天国拯救2": "https://huyaimg.msstatic.com/cdnimage/game/69105-MS.png",
    "战神": "https://message.biliimg.com/bfs/im/2994a3abe6d20c419e26fffdae76b132c3b3c511.png",
    "人类：一败涂地": "https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/477160/library_600x900.jpg",
    "超级兔子人": "https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/673750/library_600x900.jpg",
    "消逝的光芒2：人与仁之战": "https://huyaimg.msstatic.com/cdnimage/game/7581-MS.png",
    "森林": "https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/242760/library_600x900.jpg",
    "不祥之夜：回魂": "https://huyaimg.msstatic.com/cdnimage/game/10821-MS.png",
    "剑星": "https://huyaimg.msstatic.com/cdnimage/game/10567-MS.png",
    "三国志14": "https://huyaimg.msstatic.com/cdnimage/game/2270-MS.png",
    "都市：天际线": "https://huyaimg.msstatic.com/cdnimage/game/2201-MS.png",
    "赛博朋克2077": "https://i0.hdslb.com/bfs/vc/b4f20cc20baf98214dc611e74065e69745b4da44.png",
    "怪物猎人：崛起": "https://huyaimg.msstatic.com/cdnimage/game/6479-MS.png",
    "塞尔达传说：王国之泪": "https://huyaimg.msstatic.com/cdnimage/game/7883-MS.png",
    "无人深空": "https://huyaimg.msstatic.com/cdnimage/game/2566-MS.png",
    "刺客信条：奥德赛": "https://huyaimg.msstatic.com/cdnimage/game/1962-MS.png",
    "全面战争：三国": "https://huyaimg.msstatic.com/cdnimage/game/3004-MS.png",
    "第一后裔": "https://i0.hdslb.com/bfs/live/ec30fec1c1ddf6e9d3a5344da07a8a342e396ef1.png",
    "博德之门3": "https://huyaimg.msstatic.com/cdnimage/game/6147-MS.png",
    "匹诺曹的谎言": "https://i0.hdslb.com/bfs/live/8a2d92c20b8168e408b7c693646704f44ed2686b.png",
    "鬼谷八荒": "https://huyaimg.msstatic.com/cdnimage/game/6571-MS.png",
    "刺客信条：英灵殿": "https://huyaimg.msstatic.com/cdnimage/game/1962-MS.png",
    "三国志11": "https://huyaimg.msstatic.com/cdnimage/game/2270-MS.png",
    "仁王": "https://huyaimg.msstatic.com/cdnimage/game/5795-MS.png",
    "鬼泣5": "https://i0.hdslb.com/bfs/vc/414ae4211a774d8fa055771e3d737b759d8af4dd.png",
    "消逝的光芒": "https://i0.hdslb.com/bfs/live/a0bd9fbe293d3cf16e00ab76aa696ae510f86556.png",
    "致命公司": "https://huyaimg.msstatic.com/cdnimage/game/9959-MS.png",
    "无主之地": "https://i0.hdslb.com/bfs/live/1511b3a742a00b8e0be35d347b2c0d0fbb02153c.png",
    "指尖四川麻将": "https://huyaimg.msstatic.com/cdnimage/game/7215-MS.png",
    "天天象棋": "https://huyaimg.msstatic.com/cdnimage/game/4997-MS.png",
    "欢乐斗地主": "https://huyaimg.msstatic.com/cdnimage/game/1749-MS.png",
    "JJ斗地主": "https://huyaimg.msstatic.com/cdnimage/game/3841-MS.png",
    "腾讯欢乐麻将": "https://huyaimg.msstatic.com/cdnimage/game/1751-MS.png",
    "蛋仔派对": "https://huyaimg.msstatic.com/cdnimage/game/6909-MS.png",
    "我的世界": "https://huyaimg.msstatic.com/cdnimage/game/1732-MS.png",
    "鹅鸭杀（手游）": "https://i0.hdslb.com/bfs/live/5445c7491d8c77b15507e5d2389a4219156e7a7a.png",
    "迷你世界": "https://huyaimg.msstatic.com/cdnimage/game/2683-MS.png",
    "元梦之星": "https://huyaimg.msstatic.com/cdnimage/game/9521-MS.png",
    "球球大作战": "https://huyaimg.msstatic.com/cdnimage/game/2411-MS.png",
    "群雄逐鹿": "https://huyaimg.msstatic.com/cdnimage/game/1612-MS.png",
    "罗布乐思": "https://huyaimg.msstatic.com/cdnimage/game/5771-MS.png",
    "忍者必须死3": "https://huyaimg.msstatic.com/cdnimage/game/4041-MS.png",
    "天天酷跑": "https://huyaimg.msstatic.com/cdnimage/game/1715-MS.png",
    "腾讯桌球": "https://huyaimg.msstatic.com/cdnimage/game/2444-MS.png",
    "燕云十六声": "https://huyaimg.msstatic.com/cdnimage/game/8019-MS.png",
    "魔兽世界": "https://huyaimg.msstatic.com/cdnimage/game/8-MS.png",
    "洛克王国手游": "https://i0.hdslb.com/bfs/live/d0bdc2347681140a8fe8c2e3a0498e532c55500a.png",
    "梦幻西游": "https://i0.hdslb.com/bfs/vc/91d5e60dbd60ee8f84b0fc62baa23550c012fdf1.png",
    "大话西游2": "https://message.biliimg.com/bfs/im/2bd0c6fc3922b2c5724ee3504a56f9fec49ebdd8.png",
    "火影忍者手游": "https://huyaimg.msstatic.com/cdnimage/game/2429-MS.png",
    "原神": "https://huyaimg.msstatic.com/cdnimage/game/5489-MS.png",
    "鸣潮": "https://huyaimg.msstatic.com/cdnimage/game/8037-MS.png",
    "梦幻西游手游": "https://i0.hdslb.com/bfs/vc/91d5e60dbd60ee8f84b0fc62baa23550c012fdf1.png",
    "明日之后": "https://huyaimg.msstatic.com/cdnimage/game/3483-MS.png",
    "地下城与勇士": "https://huyaimg.msstatic.com/cdnimage/game/2-MS.png",
    "逆水寒手游": "https://huyaimg.msstatic.com/cdnimage/game/7725-MS.png",
    "光遇": "https://i0.hdslb.com/bfs/live/7a87708bd374a12377afbb8813bbbac65123ae91.png",
    "绝区零": "https://huyaimg.msstatic.com/cdnimage/game/7711-MS.png",
    "逆水寒": "https://huyaimg.msstatic.com/cdnimage/game/2952-MS.png",
    "火炬之光：无限": "https://huyaimg.msstatic.com/cdnimage/game/6399-MS.png",
    "剑网3": "https://huyaimg.msstatic.com/cdnimage/game/900-MS.png",
    "问道": "https://huyaimg.msstatic.com/cdnimage/game/107-MS.png",
    "王者荣耀：世界": "https://huyaimg.msstatic.com/cdnimage/game/71519-MS.png",
    "地下城与勇士：起源": "https://huyaimg.msstatic.com/cdnimage/game/2-MS.png",
    "大话西游": "https://message.biliimg.com/bfs/im/2bd0c6fc3922b2c5724ee3504a56f9fec49ebdd8.png",
    "七日世界": "https://huyaimg.msstatic.com/cdnimage/game/9995-MS.png",
    "命运方舟": "https://huyaimg.msstatic.com/cdnimage/game/3058-MS.png",
    "明日方舟：终末地": "https://huyaimg.msstatic.com/cdnimage/game/8363-MS.png",
    "神武4": "https://huyaimg.msstatic.com/cdnimage/game/3227-MS.png",
    "无限暖暖": "https://i0.hdslb.com/bfs/live/cb7fdba6a106bb3a04f4274fb2a87751235a589a.png",
    "洛克王国": "https://i0.hdslb.com/bfs/live/d0bdc2347681140a8fe8c2e3a0498e532c55500a.png",
    "新大话西游3": "https://huyaimg.msstatic.com/cdnimage/game/200-MS.png",
    "诛仙世界": "https://huyaimg.msstatic.com/cdnimage/game/7749-MS.png",
    "晶核": "https://i0.hdslb.com/bfs/live/8b934c849ebc053866f3526232d902ac200a24af.png",
    "天涯明月刀": "https://huyaimg.msstatic.com/cdnimage/game/1219-MS.png",
    "暗黑破坏神：不朽": "https://huyaimg.msstatic.com/cdnimage/game/6385-MS.png",
    "航海王热血航线": "https://i0.hdslb.com/bfs/im/0a4d0191a1715f95696bd7ae890dff9021884cd6.png",
    "一梦江湖": "https://huyaimg.msstatic.com/cdnimage/game/3082-MS.png",
    "月圆之夜": "https://i0.hdslb.com/bfs/live/3802030a4ebc11f1ec15f24bfd6a647e6d587e0e.jpg",
    "航海王：壮志雄心": "https://i0.hdslb.com/bfs/live/6a01837f4ab0f8c0ba4f589b50d21eeae6f9a367.png",
    "黎明觉醒：生机": "https://i0.hdslb.com/bfs/live/c7a440696ea9e357b360aa706bba234da644cdd4.png",
    "崩坏3": "https://i0.hdslb.com/bfs/vc/242c92ee54d374e379820521353d9ae6199be7fc.png",
    "激战2": "https://huyaimg.msstatic.com/cdnimage/game/406-MS.png",
    "妄想山海": "https://huyaimg.msstatic.com/cdnimage/game/6007-MS.png",
    "冒险岛：枫之传说": "https://huyaimg.msstatic.com/cdnimage/game/8005-MS.png",
    "龙之谷世界": "https://i0.hdslb.com/bfs/vc/db5908c6fb8afb4df9b5a671afdf90c26efd6f57.png",
    "元气骑士": "https://i0.hdslb.com/bfs/live/103b523635399450afe1a0d177b7127187f593e8.png",
    "时空猎人3": "https://message.biliimg.com/bfs/im/e492b3b83ee37efa41a12bd12fae44ca759e118b.png",
    "星球：重启": "https://i0.hdslb.com/bfs/live/ee16ab101229217d08d291f783c9f09303ea14b6.jpg",
    "新天龙八部": "https://huyaimg.msstatic.com/cdnimage/game/5671-MS.png",
    "仙剑世界": "https://i0.hdslb.com/bfs/live/93c6fdb8895b3a0e1746eb9a02c2ad91646a22cd.png",
    "全境封锁2": "https://huyaimg.msstatic.com/cdnimage/game/5023-MS.png",
    "新笑傲江湖": "https://huyaimg.msstatic.com/cdnimage/game/5669-MS.png",
    "天龙八部2：飞龙战天": "https://huyaimg.msstatic.com/cdnimage/game/7929-MS.png",
    "崩坏：星穹铁道": "https://huyaimg.msstatic.com/cdnimage/game/7349-MS.png",
    "明日方舟": "https://huyaimg.msstatic.com/cdnimage/game/4925-MS.png",
    "阴阳师": "https://huyaimg.msstatic.com/cdnimage/game/2598-MS.png",
    "率土之滨": "https://huyaimg.msstatic.com/cdnimage/game/2691-MS.png",
    "三国志·战略版": "https://huyaimg.msstatic.com/cdnimage/game/5619-MS.png",
    "大话西游：归来": "https://huyaimg.msstatic.com/cdnimage/game/8239-MS.png",
    "部落冲突": "https://huyaimg.msstatic.com/cdnimage/game/1797-MS.png",
    "植物大战僵尸2": "https://i0.hdslb.com/bfs/live/9705a2883bcae2e153ebadf34915eecb119f249b.png",
    "斗罗大陆：魂师对决": "https://huyaimg.msstatic.com/cdnimage/game/6745-MS.png",
    "航海王：燃烧意志": "https://huyaimg.msstatic.com/cdnimage/game/3943-MS.png",
    "蔚蓝档案": "https://i0.hdslb.com/bfs/live/d20380b9b6d66725aba33f2d67fb0cb78bfc98b4.png",
    "赛尔号": "https://i0.hdslb.com/bfs/live/6bdd3499a3a66f5e7e9c7753b87575b00594bdae.png",
    "无期迷途": "https://i0.hdslb.com/bfs/live/341db928251b2471ea9a411739b88d8f67646c01.png",
    "重返未来1999": "https://i0.hdslb.com/bfs/live/0ed147f627a6117206ff14f23349c86b0eb30fc0.png",
    "龙族：卡塞尔之门": "https://i0.hdslb.com/bfs/live/87b2f0a9d21f741755a0b4574dbc732845fb1382.png",
    "光与夜之恋": "https://i0.hdslb.com/bfs/live/b8decda6fabe84824ad300d1086351ea893c0fd5.png",
    "小冰冰传奇": "https://i0.hdslb.com/bfs/live/54e93b711f32c8754f47a602820238c29f5acec1.png",
    "以闪亮之名": "https://i0.hdslb.com/bfs/live/af9a1f7100d177cb6139e712c7ba1a56482cd72f.png",
    "梦幻模拟战": "https://huyaimg.msstatic.com/cdnimage/game/3481-MS.png",
    "射击": "https://sta-op.douyucdn.cn/dycatr/94701504720fb986ae5b331f7035f670.png",
    "竞技": "https://sta-op.douyucdn.cn/dycatr/560457aa8334716cc698b4a5eb15e10a.png",
    "单机": "https://huyaimg.msstatic.com/cdnimage/game/6111-MS.png",
    "棋牌": "https://huyaimg.msstatic.com/cdnimage/game/1749-MS.png",
    "休闲益智": "https://huyaimg.msstatic.com/cdnimage/game/1732-MS.png",
    "角色扮演": "https://huyaimg.msstatic.com/cdnimage/game/5489-MS.png",
    "策略卡牌": "https://huyaimg.msstatic.com/cdnimage/game/4925-MS.png"
}

# 平台標籤是簡體，這裡只做「已知標籤」的繁簡對照；
# 遊戲名、主播名、直播標題屬於平台內容，保留原文，避免逐字轉換出錯。
LABELS = {
    "聊天": "聊天",
    "音乐": "音樂",
    "游戏": "遊戲",
    "二次元": "二次元",
    "舞蹈": "舞蹈",
    "文化": "文化",
    "生活": "生活",
    "运动": "運動",
    "户外": "戶外",
    "探索": "探索",
    "宠粉": "寵粉",
    "派对": "派對",
    "盛典": "盛典",
    "好物": "好物",
    "交友": "交友",
    "情感": "情感",
    "颜值": "顏值",
    "才艺": "才藝",
    "娱乐": "娛樂",
    "三农": "三農",
    "知识": "知識",
    "财经": "財經",
    "汽车": "汽車",
    "房产": "房產",
    "旅行": "旅行",
    "美食": "美食",
    "亲子": "親子",
    "宠物": "寵物",
    "时尚": "時尚",
    "摄影": "攝影",
    "手工": "手工",
    "绘画": "繪畫",
    "国风": "國風",
    "非遗": "非遺",
    "健身": "健身",
    "射击": "射擊",
    "竞技": "競技",
    "单机": "單機",
    "棋牌": "棋牌",
    "休闲益智": "休閒益智",
    "角色扮演": "角色扮演",
    "策略卡牌": "策略卡牌",
    "主机": "主機",
    "网游": "網遊",
    "手游": "手遊",
    "综合": "綜合",
    "热门": "熱門",
    "音乐人": "音樂人",
    "舞者": "舞者",
    "歌手": "歌手",
    "演员": "演員",
    "相声": "相聲",
    "戏曲": "戲曲",
    "蓝光": "藍光",
    "超清": "超清",
    "高清": "高清",
    "标清": "標清",
    "原画": "原畫",
    "流畅": "流暢"
}

# 抖音彈幕簽名（byted_acrawler 1.0.0.53）：握手必須帶 signature（X-Bogus），
# 而且簽名與 room_id + user_unique_id 綁定，無法預先算好寫死。
# 這裡放的是經反混淆 + 按執行路徑裁剪 + terser 壓縮後的版本（475KB → 65KB），
# 輸出與原版完全一致；若日後抖音升級校驗（症狀是一直握手失敗、彈幕 0 條），
# 按同一流程重新裁剪後整段替換即可。
SIGN_LIB = r"""var douyinSign = (function () {
var UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36";function douyinSign(md5){var document={},window={},navigator={userAgent:UA},process=void 0,require=void 0,module=void 0,exports=void 0,crawler,crawler,_0x19937e;if(document={},window={},navigator={userAgent:"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},!window.byted_acrawler){function w_0x5c3140(e,t,r){function n(e,t){var r=parseInt(e.slice(t,t+2),16);return r>>>7==0?[1,r]:r>>>6==2?(r=(63&r)<<8,[2,r+=parseInt(e.slice(t+2,t+4),16)]):(r=(63&r)<<16,[3,r+=parseInt(e.slice(t+2,t+6),16)])}var o,a=0,i=[],c=[],f=parseInt(e.slice(0,8),16),s=parseInt(e.slice(8,16),16);if(1213091658!==f||1077891651!==s)throw new Error("mhe");if(0!==parseInt(e.slice(16,18),16))throw new Error("ve");for(o=0;o<4;++o)a+=(3&parseInt(e.slice(24+2*o,26+2*o),16))<<2*o;var u=parseInt(e.slice(32,40),16),d=2*parseInt(e.slice(48,56),16);for(o=56;o<d+56;o+=2)i.push(parseInt(e.slice(o,o+2),16));var _=d+56,l=parseInt(e.slice(_,_+4),16);for(_+=4,o=0;o<l;++o){var x=n(e,_);_+=2*x[0];for(var h="",p=0;p<x[1];++p){var b=n(e,_);h+=String.fromCharCode(a^b[1]),_+=2*b[0]}c.push(h)}return t.p=null,function e(t,r,n,o,a){var f,s,u,d,_,l=-1,x=[],h=[0,null],p=null,b=[r];for(s=Math.min(r.length,n),u=0;u<s;++u)b.push(r[u]);b.p=o;for(var v=[];;)try{var y=i[t++];if(y<39)if(y<19)if(y<7)y<3?x[++l]=y<1||1!==y&&null:y<5?3===y?(f=i[t++],x[++l]=f<<24>>24):(f=(i[t]<<8)+i[t+1],t+=2,x[++l]=f<<16>>16):5===y?(f=((f=((f=i[t++])<<8)+i[t++])<<8)+i[t++],x[++l]=(f<<8)+i[t++]):(f=(i[t]<<8)+i[t+1],t+=2,x[++l]=+c[f]);else if(y<13)y<11?7===y?(f=(i[t]<<8)+i[t+1],t+=2,x[++l]=c[f]):x[++l]=void 0:11===y?x[++l]=a:(f=(i[t]<<8)+i[t+1],t+=2,l=l-f+1,s=x.slice(l,l+f),x[l]=s);else if(y<17)13===y?x[++l]={}:(f=(i[t]<<8)+i[t+1],t+=2,s=c[f],u=x[l--],x[l][s]=u);else if(17===y){for(s=i[t++],u=i[t++],d=b;s>0;--s)d=d.p;x[++l]=d[u]}else f=(i[t]<<8)+i[t+1],t+=2,s=c[f],x[l]=x[l][s];else if(y<27)if(y<23)if(y<21)if(19===y)s=x[l--],x[l]=x[l][s];else{for(s=i[t++],u=i[t++],d=b;s>0;--s)d=d.p;d[u]=x[l--]}else 21===y?(f=(i[t]<<8)+i[t+1],t+=2,s=c[f],u=x[l--],d=x[l--],u[s]=d):(s=x[l--],u=x[l--],d=x[l--],u[s]=d);else if(y<25)if(23===y){for(s=i[t++],u=i[t++],d=b,d=b;s>0;--s)d=d.p;x[++l]=d,x[++l]=u}else s=x[l--],x[l]+=s;else 25===y?(s=x[l--],x[l]-=s):(s=x[l--],x[l]*=s);else y<35?y<29?27===y?(s=x[l--],x[l]/=s):(s=x[l--],x[l]%=s):29===y?x[l]=-x[l]:(s=x[l--],u=x[l--],x[++l]=u[s]++):y<37?35===y?(s=x[l--],x[l]=x[l]==s):(s=x[l--],x[l]=x[l]!=s):37===y?(s=x[l--],x[l]=x[l]===s):(s=x[l--],x[l]=x[l]!==s);else if(y<57)y<47?y<43?y<41?(s=x[l--],x[l]=x[l]<s):41===y?(s=x[l--],x[l]=x[l]>s):(s=x[l--],x[l]=x[l]>=s):y<45?43===y?(s=x[l--],x[l]=x[l]<<s):(s=x[l--],x[l]=x[l]>>s):45===y?(s=x[l--],x[l]=x[l]>>>s):(s=x[l--],x[l]=x[l]&s):y<52?y<50?47===y?(s=x[l--],x[l]=x[l]|s):(s=x[l--],x[l]=x[l]^s):50===y?x[l]=!x[l]:(f=(f=(i[t]<<8)+i[t+1])<<16>>16,t+=2,x[l]?--l:t+=f):y<54?52===y?(f=(f=(i[t]<<8)+i[t+1])<<16>>16,t+=2,x[l]?t+=f:--l):(s=x[l--],(u=x[l--])[s]=x[l]):54===y?(s=x[l--],x[l]=x[l]in s):(s=x[l--],x[l]=x[l]instanceof s);else if(y<66)if(y<61)y<59?57===y?(s=x[l--],u=x[l--],x[++l]=delete u[s]):x[l]=typeof x[l]:59===y?(f=i[t++],s=x[l--],(u=function e(){var t=e._v;return(0,e._u)(t[0],arguments,t[1],t[2],this)})._v=[s,f,b],u._u=e,x[++l]=u):(f=i[t++],s=x[l--],(d=[u=function e(){var t=e._v;return(0,e._u)(t[0],arguments,t[1],t[2],this)}]).p=b,u._v=[s,f,d],u._u=e,x[++l]=u);else if(y<64)61===y?(f=(f=(i[t]<<8)+i[t+1])<<16>>16,t+=2,(s=v[v.length-1])[1]=t+f):(f=(f=(i[t]<<8)+i[t+1])<<16>>16,t+=2,(s=v[v.length-1])&&!s[1]?(s[0]=3,s.push(t)):v.push([1,0,t]),t+=f);else{if(64===y)throw s=x[l--];if(u=(s=v.pop())[0],d=h[0],1===u)t=s[1];else if(0===u)if(0===d)t=s[1];else{if(1!==d)throw h[1];if(!p)return h[1];t=p[1],a=p[2],b=p[3],v=p[4],x[++l]=h[1],h=[0,null],p=p[0]}else t=s[2],s[0]=0,v.push(s)}else if(y<71)if(y<68)if(66===y){for(s=x[l--],u=null;d=v.pop();)if(2===d[0]||3===d[0]){u=d;break}if(u)h=[1,s],t=u[2],u[0]=0,v.push(u);else{if(!p)return s;t=p[1],a=p[2],b=p[3],v=p[4],x[++l]=s,h=[0,null],p=p[0]}}else l-=f=i[t++],u=x.slice(l+1,l+f+1),s=x[l--],d=x[l--],s._u===e?(s=s._v,p=[p,t,a,b,v],t=s[0],null==d&&(d=function(){return this}()),a=d,(b=[u].concat(u)).length=Math.min(s[1],f)+1,b.p=s[2],v=[]):x[++l]=s.apply(d,u);else if(68===y){for(f=i[t++],d=[void 0],_=f;_>0;--_)d[_]=x[l--];u=x[l--],s=Function.bind.apply(u,d),x[++l]=new s}else t+=2+(f=(f=(i[t]<<8)+i[t+1])<<16>>16);else y<73?71===y?(f=(f=(i[t]<<8)+i[t+1])<<16>>16,t+=2,(s=x[l--])||(t+=f)):(f=(f=(i[t]<<8)+i[t+1])<<16>>16,t+=2,s=x[l--],x[l]===s&&(--l,t+=f)):73===y?--l:(s=x[l],x[++l]=s)}catch(e){for(h=[0,null];(f=v.pop())&&!f[0];);if(!f){e:for(;p;){for(s=p[4];f=s.pop();)if(f[0])break e;p=p[0]}if(!p)throw e;t=p[1],a=p[2],b=p[3],v=p[4],p=p[0]}1===(s=f[0])?(t=f[2],f[0]=0,v.push(f),x[++l]=e):2===s?(t=f[2],f[0]=0,v.push(f),h=[3,e]):(t=f[3],f[0]=2,v.push(f),x[++l]=e)}}(u,[],0,t,r)}_0x19937e=function(_0x1d18f2){"use strict";function _0x137ba2(e){var t,r;function n(t,r){try{var a=e[t](r),i=a.value,c=i instanceof _0x59d886;Promise.resolve(c?i.v:i).then(function(r){if(c){var f="return"===t?"return":"next";if(!i.k||r.done)return n(f,r);r=e[f](r).value}o(a.done?"return":"normal",r)},function(e){n("throw",e)})}catch(e){o("throw",e)}}function o(e,o){switch(e){case"return":t.resolve({value:o,done:!0});break;case"throw":t.reject(o);break;default:t.resolve({value:o,done:!1})}(t=t.next)?n(t.key,t.arg):r=null}this._invoke=function(e,o){return new Promise(function(a,i){var c={key:e,arg:o,resolve:a,reject:i,next:null};r?r=r.next=c:(t=r=c,n(e,o))})},"function"!=typeof e.return&&(this.return=void 0)}function _0x59d886(e,t){this.v=e,this.k=t}var _0x15b960,_0x500e9f;function _0x4591cd(){function e(e,t){return function(n){!function(e){if(e.v)throw new Error("attempted to call addInitializer after decoration was finished")}(t),r(n,"An initializer"),e.push(n)}}function t(t,r,n,o,a,i,c,f){var s,u,d;switch(a){case 1:s="accessor";break;case 2:s="method";break;case 3:s="getter";break;case 4:s="setter";break;default:s="field"}var _={kind:s,name:c?"#"+r:r,static:i,private:c},l={v:!1};0!==a&&(_.addInitializer=e(o,l)),0===a?c?(u=n.get,d=n.set):(u=function(){return this[r]},d=function(e){this[r]=e}):2===a?u=function(){return n.value}:(1!==a&&3!==a||(u=function(){return n.get.call(this)}),1!==a&&4!==a||(d=function(e){n.set.call(this,e)})),_.access=u&&d?{get:u,set:d}:u?{get:u}:{set:d};try{return t(f,_)}finally{l.v=!0}}function r(e,t){if("function"!=typeof e)throw new TypeError(t+" must be a function")}function n(e,t){var n=typeof t;if(1===e){if("object"!==n||null===t)throw new TypeError("accessor decorators must return an object with get, set, or init properties or void 0");void 0!==t.get&&r(t.get,"accessor.get"),void 0!==t.set&&r(t.set,"accessor.set"),void 0!==t.init&&r(t.init,"accessor.init")}else if("function"!==n)throw new TypeError((0===e?"field":10===e?"class":"method")+" decorators must return a function or void 0")}function o(e,r,o,a,i,c,f,s){var u,d,_,l,x,h,p=o[0];if(f?u=0===i||1===i?{get:o[3],set:o[4]}:3===i?{get:o[3]}:4===i?{set:o[3]}:{value:o[3]}:0!==i&&(u=Object.getOwnPropertyDescriptor(r,a)),1===i?_={get:u.get,set:u.set}:2===i?_=u.value:3===i?_=u.get:4===i&&(_=u.set),"function"==typeof p)void 0!==(l=t(p,a,u,s,i,c,f,_))&&(n(i,l),0===i?d=l:1===i?(d=l.init,x=l.get||_.get,h=l.set||_.set,_={get:x,set:h}):_=l);else for(var b=p.length-1;b>=0;b--){var v;void 0!==(l=t(p[b],a,u,s,i,c,f,_))&&(n(i,l),0===i?v=l:1===i?(v=l.init,x=l.get||_.get,h=l.set||_.set,_={get:x,set:h}):_=l,void 0!==v&&(void 0===d?d=v:"function"==typeof d?d=[d,v]:d.push(v)))}if(0===i||1===i){if(void 0===d)d=function(e,t){return t};else if("function"!=typeof d){var y=d;d=function(e,t){for(var r=t,n=0;n<y.length;n++)r=y[n].call(e,r);return r}}else{var g=d;d=function(e,t){return g.call(e,t)}}e.push(d)}0!==i&&(1===i?(u.get=_.get,u.set=_.set):2===i?u.value=_:3===i?u.get=_:4===i&&(u.set=_),f?1===i?(e.push(function(e,t){return _.get.call(e,t)}),e.push(function(e,t){return _.set.call(e,t)})):2===i?e.push(_):e.push(function(e,t){return _.call(e,t)}):Object.defineProperty(r,a,u))}function a(e,t){for(var r,n,a=[],c=new Map,f=new Map,s=0;s<t.length;s++){var u=t[s];if(Array.isArray(u)){var d,_,l=u[1],x=u[2],h=u.length>3,p=l>=5;if(p?(d=e,0!=(l-=5)&&(_=n=n||[])):(d=e.prototype,0!==l&&(_=r=r||[])),0!==l&&!h){var b=p?f:c,v=b.get(x)||0;if(!0===v||3===v&&4!==l||4===v&&3!==l)throw new Error("Attempted to decorate a public method/accessor that has the same name as a previously decorated public method/accessor. This is not currently supported by the decorators plugin. Property name was: "+x);!v&&l>2?b.set(x,l):b.set(x,!0)}o(a,d,u,x,l,p,h,_)}}return i(a,r),i(a,n),a}function i(e,t){t&&e.push(function(e){for(var r=0;r<t.length;r++)t[r].call(e);return e})}return function(t,r,o){return{e:a(t,r),get c(){return function(t,r){if(r.length>0){for(var o=[],a=t,i=t.name,c=r.length-1;c>=0;c--){var f={v:!1};try{var s=r[c](a,{kind:"class",name:i,addInitializer:e(o,f)})}finally{f.v=!0}void 0!==s&&(n(10,s),a=s)}return[a,function(){for(var e=0;e<o.length;e++)o[e].call(a)}]}}(t,o)}}}}function _0x49af1f(e,t,r){return(_0x49af1f=_0x4591cd())(e,t,r)}function _0x3d6fc9(e){function t(e){if(Object(e)!==e)return Promise.reject(new TypeError(e+" is not an object."));var t=e.done;return Promise.resolve(e.value).then(function(e){return{value:e,done:t}})}return(_0x3d6fc9=function(e){this.s=e,this.n=e.next}).prototype={s:null,n:null,next:function(){return t(this.n.apply(this.s,arguments))},return:function(e){var r=this.s.return;return void 0===r?Promise.resolve({value:e,done:!0}):t(r.apply(this.s,arguments))},throw:function(e){var r=this.s.return;return void 0===r?Promise.reject(e):t(r.apply(this.s,arguments))}},new _0x3d6fc9(e)}function _0x385d19(){_0x385d19=function(){return e};var e={},t=Object.prototype,r=t.hasOwnProperty,n=Object.defineProperty||function(e,t,r){e[t]=r.value},o="function"==typeof Symbol?Symbol:{},a=o.iterator||"@@iterator",i=o.asyncIterator||"@@asyncIterator",c=o.toStringTag||"@@toStringTag";function f(e,t,r){return Object.defineProperty(e,t,{value:r,enumerable:!0,configurable:!0,writable:!0}),e[t]}try{f({},"")}catch(e){f=function(e,t,r){return e[t]=r}}function s(e,t,r,o){var a,i,c,f,s=t&&t.prototype instanceof _?t:_,l=Object.create(s.prototype),x=new A(o||[]);return n(l,"_invoke",{value:(a=e,i=r,c=x,f="suspendedStart",function(e,t){if("executing"===f)throw new Error("Generator is already running");if("completed"===f){if("throw"===e)throw t;return{value:void 0,done:!0}}for(c.method=e,c.arg=t;;){var r=c.delegate;if(r){var n=m(r,c);if(n){if(n===d)continue;return n}}if("next"===c.method)c.sent=c._sent=c.arg;else if("throw"===c.method){if("suspendedStart"===f)throw f="completed",c.arg;c.dispatchException(c.arg)}else"return"===c.method&&c.abrupt("return",c.arg);f="executing";var o=u(a,i,c);if("normal"===o.type){if(f=c.done?"completed":"suspendedYield",o.arg===d)continue;return{value:o.arg,done:c.done}}"throw"===o.type&&(f="completed",c.method="throw",c.arg=o.arg)}})}),l}function u(e,t,r){try{return{type:"normal",arg:e.call(t,r)}}catch(e){return{type:"throw",arg:e}}}e.wrap=s;var d={};function _(){}function l(){}function x(){}var h={};f(h,a,function(){return this});var p=Object.getPrototypeOf,b=p&&p(p(S([])));b&&b!==t&&r.call(b,a)&&(h=b);var v=x.prototype=_.prototype=Object.create(h);function y(e){["next","throw","return"].forEach(function(t){f(e,t,function(e){return this._invoke(t,e)})})}function g(e,t){var o;n(this,"_invoke",{value:function(n,a){function i(){return new t(function(o,i){!function n(o,a,i,c){var f=u(e[o],e,a);if("throw"!==f.type){var s=f.arg,d=s.value;return d&&"object"==typeof d&&r.call(d,"__await")?t.resolve(d.__await).then(function(e){n("next",e,i,c)},function(e){n("throw",e,i,c)}):t.resolve(d).then(function(e){s.value=e,i(s)},function(e){return n("throw",e,i,c)})}c(f.arg)}(n,a,o,i)})}return o=o?o.then(i,i):i()}})}function m(e,t){var r=t.method,n=e.iterator[r];if(void 0===n)return t.delegate=null,"throw"===r&&e.iterator.return&&(t.method="return",t.arg=void 0,m(e,t),"throw"===t.method)||"return"!==r&&(t.method="throw",t.arg=new TypeError("The iterator does not provide a '"+r+"' method")),d;var o=u(n,e.iterator,t.arg);if("throw"===o.type)return t.method="throw",t.arg=o.arg,t.delegate=null,d;var a=o.arg;return a?a.done?(t[e.resultName]=a.value,t.next=e.nextLoc,"return"!==t.method&&(t.method="next",t.arg=void 0),t.delegate=null,d):a:(t.method="throw",t.arg=new TypeError("iterator result is not an object"),t.delegate=null,d)}function w(e){var t={tryLoc:e[0]};1 in e&&(t.catchLoc=e[1]),2 in e&&(t.finallyLoc=e[2],t.afterLoc=e[3]),this.tryEntries.push(t)}function E(e){var t=e.completion||{};t.type="normal",delete t.arg,e.completion=t}function A(e){this.tryEntries=[{tryLoc:"root"}],e.forEach(w,this),this.reset(!0)}function S(e){if(e){var t=e[a];if(t)return t.call(e);if("function"==typeof e.next)return e;if(!isNaN(e.length)){var n=-1,o=function t(){for(;++n<e.length;)if(r.call(e,n))return t.value=e[n],t.done=!1,t;return t.value=void 0,t.done=!0,t};return o.next=o}}return{next:k}}function k(){return{value:void 0,done:!0}}return l.prototype=x,n(v,"constructor",{value:x,configurable:!0}),n(x,"constructor",{value:l,configurable:!0}),l.displayName=f(x,c,"GeneratorFunction"),e.isGeneratorFunction=function(e){var t="function"==typeof e&&e.constructor;return!!t&&(t===l||"GeneratorFunction"===(t.displayName||t.name))},e.mark=function(e){return Object.setPrototypeOf?Object.setPrototypeOf(e,x):(e.__proto__=x,f(e,c,"GeneratorFunction")),e.prototype=Object.create(v),e},e.awrap=function(e){return{__await:e}},y(g.prototype),f(g.prototype,i,function(){return this}),e.AsyncIterator=g,e.async=function(t,r,n,o,a=Promise){var i=new g(s(t,r,n,o),a);return e.isGeneratorFunction(r)?i:i.next().then(function(e){return e.done?e.value:i.next()})},y(v),f(v,c,"Generator"),f(v,a,function(){return this}),f(v,"toString",function(){return"[object Generator]"}),e.keys=function(e){var t=Object(e),r=[];for(var n in t)r.push(n);return r.reverse(),function e(){for(;r.length;){var n=r.pop();if(n in t)return e.value=n,e.done=!1,e}return e.done=!0,e}},e.values=S,A.prototype={constructor:A,reset:function(e){if(this.prev=0,this.next=0,this.sent=this._sent=void 0,this.done=!1,this.delegate=null,this.method="next",this.arg=void 0,this.tryEntries.forEach(E),!e)for(var t in this)"t"===t.charAt(0)&&r.call(this,t)&&!isNaN(+t.slice(1))&&(this[t]=void 0)},stop:function(){this.done=!0;var e=this.tryEntries[0].completion;if("throw"===e.type)throw e.arg;return this.rval},dispatchException:function(e){if(this.done)throw e;var t=this;function n(r,n){return i.type="throw",i.arg=e,t.next=r,n&&(t.method="next",t.arg=void 0),!!n}for(var o=this.tryEntries.length-1;o>=0;--o){var a=this.tryEntries[o],i=a.completion;if("root"===a.tryLoc)return n("end");if(a.tryLoc<=this.prev){var c=r.call(a,"catchLoc"),f=r.call(a,"finallyLoc");if(c&&f){if(this.prev<a.catchLoc)return n(a.catchLoc,!0);if(this.prev<a.finallyLoc)return n(a.finallyLoc)}else if(c){if(this.prev<a.catchLoc)return n(a.catchLoc,!0)}else{if(!f)throw new Error("try statement without catch or finally");if(this.prev<a.finallyLoc)return n(a.finallyLoc)}}}},abrupt:function(e,t){for(var n=this.tryEntries.length-1;n>=0;--n){var o=this.tryEntries[n];if(o.tryLoc<=this.prev&&r.call(o,"finallyLoc")&&this.prev<o.finallyLoc){var a=o;break}}a&&("break"===e||"continue"===e)&&a.tryLoc<=t&&t<=a.finallyLoc&&(a=null);var i=a?a.completion:{};return i.type=e,i.arg=t,a?(this.method="next",this.next=a.finallyLoc,d):this.complete(i)},complete:function(e,t){if("throw"===e.type)throw e.arg;return"break"===e.type||"continue"===e.type?this.next=e.arg:"return"===e.type?(this.rval=this.arg=e.arg,this.method="return",this.next="end"):"normal"===e.type&&t&&(this.next=t),d},finish:function(e){for(var t=this.tryEntries.length-1;t>=0;--t){var r=this.tryEntries[t];if(r.finallyLoc===e)return this.complete(r.completion,r.afterLoc),E(r),d}},catch:function(e){for(var t=this.tryEntries.length-1;t>=0;--t){var r=this.tryEntries[t];if(r.tryLoc===e){var n=r.completion;if("throw"===n.type){var o=n.arg;E(r)}return o}}throw new Error("illegal catch attempt")},delegateYield:function(e,t,r){return this.delegate={iterator:S(e),resultName:t,nextLoc:r},"next"===this.method&&(this.arg=void 0),d}},e}function _0x1db123(e){return(_0x1db123="function"==typeof Symbol&&"symbol"==typeof Symbol.iterator?function(e){return typeof e}:function(e){return e&&"function"==typeof Symbol&&e.constructor===Symbol&&e!==Symbol.prototype?"symbol":typeof e})(e)}function _0x34d29a(){_0x34d29a=function(e,t){return new r(e,void 0,t)};var e=RegExp.prototype,t=new WeakMap;function r(e,n,o){var a=new RegExp(e,n);return t.set(a,o||t.get(e)),_0x2e2f47(a,r.prototype)}function n(e,r){var n=t.get(r);return Object.keys(n).reduce(function(t,r){var o=n[r];if("number"==typeof o)t[r]=e[o];else{for(var a=0;void 0===e[o[a]]&&a+1<o.length;)a++;t[r]=e[o[a]]}return t},Object.create(null))}return _0x5dda7d(r,RegExp),r.prototype.exec=function(t){var r=e.exec.call(this,t);if(r){r.groups=n(r,this);var o=r.indices;o&&(o.groups=n(o,this))}return r},r.prototype[Symbol.replace]=function(r,o){if("string"==typeof o){var a=t.get(this);return e[Symbol.replace].call(this,r,o.replace(/\$<([^>]+)>/g,function(e,t){var r=a[t];return"$"+(Array.isArray(r)?r.join("$"):r)}))}if("function"==typeof o){var i=this;return e[Symbol.replace].call(this,r,function(){var e=arguments;return"object"!=typeof e[e.length-1]&&(e=[].slice.call(e)).push(n(e,i)),o.apply(this,e)})}return e[Symbol.replace].call(this,r,o)},_0x34d29a.apply(this,arguments)}function _0x4a7824(e,t,r){return(t=_0x32e885(t))in e?Object.defineProperty(e,t,{value:r,enumerable:!0,configurable:!0,writable:!0}):e[t]=r,e}function _0x36f54f(){return(_0x36f54f=Object.assign?Object.assign.bind():function(e){for(var t=1;t<arguments.length;t++){var r=arguments[t];for(var n in r)Object.prototype.hasOwnProperty.call(r,n)&&(e[n]=r[n])}return e}).apply(this,arguments)}function _0x5dda7d(e,t){if("function"!=typeof t&&null!==t)throw new TypeError("Super expression must either be null or a function");e.prototype=Object.create(t&&t.prototype,{constructor:{value:e,writable:!0,configurable:!0}}),Object.defineProperty(e,"prototype",{writable:!1}),t&&_0x2e2f47(e,t)}function _0x22af63(e){return(_0x22af63=Object.setPrototypeOf?Object.getPrototypeOf.bind():function(e){return e.__proto__||Object.getPrototypeOf(e)})(e)}function _0x2e2f47(e,t){return(_0x2e2f47=Object.setPrototypeOf?Object.setPrototypeOf.bind():function(e,t){return e.__proto__=t,e})(e,t)}function _0x3390dc(){if("undefined"==typeof Reflect||!Reflect.construct)return!1;if(Reflect.construct.sham)return!1;if("function"==typeof Proxy)return!0;try{return Boolean.prototype.valueOf.call(Reflect.construct(Boolean,[],function(){})),!0}catch(e){return!1}}function _0x920a3d(e,t,r){return(_0x920a3d=_0x3390dc()?Reflect.construct.bind():function(e,t,r){var n=[null];n.push.apply(n,t);var o=new(Function.bind.apply(e,n));return r&&_0x2e2f47(o,r.prototype),o}).apply(null,arguments)}function _0x5cb0d7(e){return-1!==Function.toString.call(e).indexOf("[native code]")}function _0x16f283(e){var t="function"==typeof Map?new Map:void 0;return(_0x16f283=function(e){if(null===e||!_0x5cb0d7(e))return e;if("function"!=typeof e)throw new TypeError("Super expression must either be null or a function");if(void 0!==t){if(t.has(e))return t.get(e);t.set(e,r)}function r(){return _0x920a3d(e,arguments,_0x22af63(this).constructor)}return r.prototype=Object.create(e.prototype,{constructor:{value:r,enumerable:!1,writable:!0,configurable:!0}}),_0x2e2f47(r,e)})(e)}function _0x1629e6(e){if("function"!=typeof WeakMap)return null;var t=new WeakMap,r=new WeakMap;return(_0x1629e6=function(e){return e?r:t})(e)}function _0x2b3a8b(e,t){for(;!Object.prototype.hasOwnProperty.call(e,t)&&null!==(e=_0x22af63(e)););return e}function _0x33bfa4(){return(_0x33bfa4="undefined"!=typeof Reflect&&Reflect.get?Reflect.get.bind():function(e,t,r){var n=_0x2b3a8b(e,t);if(n){var o=Object.getOwnPropertyDescriptor(n,t);return o.get?o.get.call(arguments.length<3?e:r):o.value}}).apply(this,arguments)}function _0x5b010c(e,t,r,n){return(_0x5b010c="undefined"!=typeof Reflect&&Reflect.set?Reflect.set:function(e,t,r,n){var o,a=_0x2b3a8b(e,t);if(a){if((o=Object.getOwnPropertyDescriptor(a,t)).set)return o.set.call(n,r),!0;if(!o.writable)return!1}if(o=Object.getOwnPropertyDescriptor(n,t)){if(!o.writable)return!1;o.value=r,Object.defineProperty(n,t,o)}else _0x4a7824(n,t,r);return!0})(e,t,r,n)}function _0x5c885(e){return _0x1ae312(e)||_0x1853c6(e)||_0x525331(e)||_0x25b697()}function _0x1ae312(e){if(Array.isArray(e))return e}function _0x1853c6(e){if("undefined"!=typeof Symbol&&null!=e[Symbol.iterator]||null!=e["@@iterator"])return Array.from(e)}function _0x525331(e,t){if(e){if("string"==typeof e)return _0x537c83(e,t);var r=Object.prototype.toString.call(e).slice(8,-1);return"Object"===r&&e.constructor&&(r=e.constructor.name),"Map"===r||"Set"===r?Array.from(e):"Arguments"===r||/^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(r)?_0x537c83(e,t):void 0}}function _0x537c83(e,t){(null==t||t>e.length)&&(t=e.length);for(var r=0,n=new Array(t);r<t;r++)n[r]=e[r];return n}function _0x25b697(){throw new TypeError("Invalid attempt to destructure non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method.")}function _0x4ad3b0(e,t){if("object"!=typeof e||null===e)return e;var r=e[Symbol.toPrimitive];if(void 0!==r){var n=r.call(e,t||"default");if("object"!=typeof n)return n;throw new TypeError("@@toPrimitive must return a primitive value.")}return("string"===t?String:Number)(e)}function _0x32e885(e){var t=_0x4ad3b0(e,"string");return"symbol"==typeof t?t:String(t)}_0x137ba2.prototype["function"==typeof Symbol&&Symbol.asyncIterator||"@@asyncIterator"]=function(){return this},_0x137ba2.prototype.next=function(e){return this._invoke("next",e)},_0x137ba2.prototype.throw=function(e){return this._invoke("throw",e)},_0x137ba2.prototype.return=function(e){return this._invoke("return",e)};var _0x371360=0,_0x4d6c78,_0x312e19,_0x2a32a1,_0x371ac2;function _0xdaf8f6(){_0xdaf8f6=function(){return e};var e={elementsDefinitionOrder:[["method"],["field"]],initializeInstanceElements:function(e,t){["method","field"].forEach(function(r){t.forEach(function(t){t.kind===r&&"own"===t.placement&&this.defineClassElement(e,t)},this)},this)},initializeClassElements:function(e,t){var r=e.prototype;["method","field"].forEach(function(n){t.forEach(function(t){var o=t.placement;if(t.kind===n&&("static"===o||"prototype"===o)){var a="static"===o?e:r;this.defineClassElement(a,t)}},this)},this)},defineClassElement:function(e,t){var r=t.descriptor;if("field"===t.kind){var n=t.initializer;r={enumerable:r.enumerable,writable:r.writable,configurable:r.configurable,value:void 0===n?void 0:n.call(e)}}Object.defineProperty(e,t.key,r)},decorateClass:function(e,t){var r=[],n=[],o={static:[],prototype:[],own:[]};if(e.forEach(function(e){this.addElementPlacement(e,o)},this),e.forEach(function(e){if(!_0x51f3b5(e))return r.push(e);var t=this.decorateElement(e,o);r.push(t.element),r.push.apply(r,t.extras),n.push.apply(n,t.finishers)},this),!t)return{elements:r,finishers:n};var a=this.decorateConstructor(r,t);return n.push.apply(n,a.finishers),a.finishers=n,a},addElementPlacement:function(e,t,r){var n=t[e.placement];if(!r&&-1!==n.indexOf(e.key))throw new TypeError("Duplicated element ("+e.key+")");n.push(e.key)},decorateElement:function(e,t){for(var r=[],n=[],o=e.decorators,a=o.length-1;a>=0;a--){var i=t[e.placement];i.splice(i.indexOf(e.key),1);var c=this.fromElementDescriptor(e),f=this.toElementFinisherExtras((0,o[a])(c)||c);e=f.element,this.addElementPlacement(e,t),f.finisher&&n.push(f.finisher);var s=f.extras;if(s){for(var u=0;u<s.length;u++)this.addElementPlacement(s[u],t);r.push.apply(r,s)}}return{element:e,finishers:n,extras:r}},decorateConstructor:function(e,t){for(var r=[],n=t.length-1;n>=0;n--){var o=this.fromClassDescriptor(e),a=this.toClassDescriptor((0,t[n])(o)||o);if(void 0!==a.finisher&&r.push(a.finisher),void 0!==a.elements){e=a.elements;for(var i=0;i<e.length-1;i++)for(var c=i+1;c<e.length;c++)if(e[i].key===e[c].key&&e[i].placement===e[c].placement)throw new TypeError("Duplicated element ("+e[i].key+")")}}return{elements:e,finishers:r}},fromElementDescriptor:function(e){var t={kind:e.kind,key:e.key,placement:e.placement,descriptor:e.descriptor};return Object.defineProperty(t,Symbol.toStringTag,{value:"Descriptor",configurable:!0}),"field"===e.kind&&(t.initializer=e.initializer),t},toElementDescriptors:function(e){if(void 0!==e)return _0x5c885(e).map(function(e){var t=this.toElementDescriptor(e);return this.disallowProperty(e,"finisher","An element descriptor"),this.disallowProperty(e,"extras","An element descriptor"),t},this)},toElementDescriptor:function(e){var t=String(e.kind);if("method"!==t&&"field"!==t)throw new TypeError('An element descriptor\'s .kind property must be either "method" or "field", but a decorator created an element descriptor with .kind "'+t+'"');var r=_0x32e885(e.key),n=String(e.placement);if("static"!==n&&"prototype"!==n&&"own"!==n)throw new TypeError('An element descriptor\'s .placement property must be one of "static", "prototype" or "own", but a decorator created an element descriptor with .placement "'+n+'"');var o=e.descriptor;this.disallowProperty(e,"elements","An element descriptor");var a={kind:t,key:r,placement:n,descriptor:Object.assign({},o)};return"field"!==t?this.disallowProperty(e,"initializer","A method descriptor"):(this.disallowProperty(o,"get","The property descriptor of a field descriptor"),this.disallowProperty(o,"set","The property descriptor of a field descriptor"),this.disallowProperty(o,"value","The property descriptor of a field descriptor"),a.initializer=e.initializer),a},toElementFinisherExtras:function(e){return{element:this.toElementDescriptor(e),finisher:_0x22df7b(e,"finisher"),extras:this.toElementDescriptors(e.extras)}},fromClassDescriptor:function(e){var t={kind:"class",elements:e.map(this.fromElementDescriptor,this)};return Object.defineProperty(t,Symbol.toStringTag,{value:"Descriptor",configurable:!0}),t},toClassDescriptor:function(e){var t=String(e.kind);if("class"!==t)throw new TypeError('A class descriptor\'s .kind property must be "class", but a decorator created a class descriptor with .kind "'+t+'"');this.disallowProperty(e,"key","A class descriptor"),this.disallowProperty(e,"placement","A class descriptor"),this.disallowProperty(e,"descriptor","A class descriptor"),this.disallowProperty(e,"initializer","A class descriptor"),this.disallowProperty(e,"extras","A class descriptor");var r=_0x22df7b(e,"finisher");return{elements:this.toElementDescriptors(e.elements),finisher:r}},runClassFinishers:function(e,t){for(var r=0;r<t.length;r++){var n=(0,t[r])(e);if(void 0!==n){if("function"!=typeof n)throw new TypeError("Finishers must return a constructor.");e=n}}return e},disallowProperty:function(e,t,r){if(void 0!==e[t])throw new TypeError(r+" can't have a ."+t+" property.")}};return e}function _0x51f3b5(e){return e.decorators&&e.decorators.length}function _0x22df7b(e,t){var r=e[t];if(void 0!==r&&"function"!=typeof r)throw new TypeError("Expected '"+t+"' to be a function");return r}"function"!=typeof Object.assign&&Object.defineProperty(Object,"assign",{value:function(e,t){if(null==e)throw new TypeError("Cannot convert undefined or null to object");for(var r=Object(e),n=1;n<arguments.length;n++){var o=arguments[n];if(null!=o)for(var a in o)Object.prototype.hasOwnProperty.call(o,a)&&(r[a]=o[a])}return r},writable:!0,configurable:!0}),Object.keys||(_0x4d6c78=Object.prototype.hasOwnProperty,_0x312e19=!{toString:null}.propertyIsEnumerable("toString"),_0x2a32a1=["toString","toLocaleString","valueOf","hasOwnProperty","isPrototypeOf","propertyIsEnumerable","constructor"],_0x371ac2=_0x2a32a1.length,Object.keys=function(e){if("function"!=typeof e&&("object"!==_0x1db123(e)||null===e))throw new TypeError("Object.keys called on non-object");var t,r,n=[];for(t in e)_0x4d6c78.call(e,t)&&n.push(t);if(_0x312e19)for(r=0;r<_0x371ac2;r++)_0x4d6c78.call(e,_0x2a32a1[r])&&n.push(_0x2a32a1[r]);return n});var _0x45b94b={__version__:"2.11.0",feVersion:2,domNotValid:!1,refererKey:"__ac_referer",pushVersion:"B4Z6wo",secInfoHeader:"X-Mssdk-Info"};function _0x598972(e,t){if("string"==typeof t)for(var r,n=e+"=",o=t.split(/[;&]/),a=0;a<o.length;a++){for(r=o[a];" "===r.charAt(0);)r=r.substring(1,r.length);if(0===r.indexOf(n))return r.substring(n.length,r.length)}}function _0x24dc34(e){try{var t="";return window.sessionStorage&&(t=window.sessionStorage.getItem(e))||window.localStorage&&(t=window.localStorage.getItem(e))?t:_0x598972(e,document.cookie)}catch(e){return""}}function _0x2ecc5a(e){try{window.sessionStorage&&window.sessionStorage.removeItem(e),window.localStorage&&window.localStorage.removeItem(e),document.cookie=e+"=; expires=Mon, 20 Sep 2010 00:00:00 UTC; path=/;"}catch(e){}}for(var _0x462335={boe:!1,aid:0,dfp:!1,sdi:!1,enablePathList:[],_enablePathListRegex:[],urlRewriteRules:[],_urlRewriteRules:[],initialized:!1,enableTrack:!1,track:{unitTime:0,unitAmount:0,fre:0},triggerUnload:!1,region:"",regionConf:{},umode:0,v:!1,_enableSignature:[],perf:!1,xxbg:!0},_0x3d40ff={debug:function(e,t){_0x462335.boe}},_0x100715="0123456789abcdef".split(""),_0x1f510e=[],_0x37750d=[],_0x1cb307=0;_0x1cb307<256;_0x1cb307++)_0x1f510e[_0x1cb307]=_0x100715[_0x1cb307>>4&15]+_0x100715[15&_0x1cb307],_0x1cb307<16&&(_0x1cb307<10?_0x37750d[48+_0x1cb307]=_0x1cb307:_0x37750d[87+_0x1cb307]=_0x1cb307);function _0x55de18(e){for(var t=e.length,r="",n=0;n<t;)r+=_0x1f510e[e[n++]];return r}function _0x655940(e){for(var t=e.length>>1,r=t<<1,n=new Uint8Array(t),o=0,a=0;a<r;)n[o++]=_0x37750d[e.charCodeAt(a++)]<<4|_0x37750d[e.charCodeAt(a++)];return n}var _0x42e709={encode:_0x55de18,decode:_0x655940},_0x1e7721="undefined"!=typeof globalThis?globalThis:void 0!==window?window:"undefined"!=typeof global?global:"undefined"!=typeof self?self:{};function _0x56409e(e){var t={exports:{}};return e(t,t.exports),t.exports}var _0x90795=_0x56409e(function(_0xb9c7d1){(function(){var _0x1f977a="input is invalid type",_0x5a87b4="object"==typeof window,_0x11d177=_0x5a87b4?window:{};_0x11d177.JS_MD5_NO_WINDOW&&(_0x5a87b4=!1);var _0x387fd8=!_0x5a87b4&&"object"==typeof self,_0x2e1226=!_0x11d177.JS_MD5_NO_NODE_JS&&"object"==typeof process&&process.versions&&process.versions.node;_0x2e1226?_0x11d177=_0x1e7721:_0x387fd8&&(_0x11d177=self);var _0x299a21=!_0x11d177.JS_MD5_NO_COMMON_JS&&_0xb9c7d1.exports,_0x5efc8f=!1,_0x1edc95=!_0x11d177.JS_MD5_NO_ARRAY_BUFFER&&"undefined"!=typeof ArrayBuffer,_0x142491="0123456789abcdef".split(""),_0x146907=[128,32768,8388608,-2147483648],_0x4d13bd=[0,8,16,24],_0x3f581b=["hex","array","digest","buffer","arrayBuffer","base64"],_0xcb4d61="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/".split(""),_0x5c5e45=[],_0x54b265;if(_0x1edc95){var _0x171107=new ArrayBuffer(68);_0x54b265=new Uint8Array(_0x171107),_0x5c5e45=new Uint32Array(_0x171107)}function _0x2e393f(e){return function(t){return new _0x22f902(!0).update(t)[e]()}}function _0x1edabb(){var e=_0x2e393f("hex");_0x2e1226&&(e=_0x4d7e2d(e)),e.create=function(){return new _0x22f902},e.update=function(t){return e.create().update(t)};for(var t=0;t<_0x3f581b.length;++t){var r=_0x3f581b[t];e[r]=_0x2e393f(r)}return e}function _0x4d7e2d(_0x1afe1b){var _0x3e0a6e=eval("var _0x13db80 = w_0x25f3;require(_0x13db80(628));"),_0x5bfe7e=eval("var _0x20dc8b = w_0x25f3;require('buffer')[_0x20dc8b(424)];");function _0x3d7396(e){if("string"==typeof e)return _0x3e0a6e.createHash("md5").update(e,"utf8").digest("hex");if(null==e)throw _0x1f977a;return e.constructor===ArrayBuffer&&(e=new Uint8Array(e)),Array.isArray(e)||ArrayBuffer.isView(e)||e.constructor===_0x5bfe7e?_0x3e0a6e.createHash("md5").update(new _0x5bfe7e(e)).digest("hex"):_0x1afe1b(e)}return _0x3d7396}function _0x22f902(e){if(e)_0x5c5e45[0]=_0x5c5e45[16]=_0x5c5e45[1]=_0x5c5e45[2]=_0x5c5e45[3]=_0x5c5e45[4]=_0x5c5e45[5]=_0x5c5e45[6]=_0x5c5e45[7]=_0x5c5e45[8]=_0x5c5e45[9]=_0x5c5e45[10]=_0x5c5e45[11]=_0x5c5e45[12]=_0x5c5e45[13]=_0x5c5e45[14]=_0x5c5e45[15]=0,this.blocks=_0x5c5e45,this.buffer8=_0x54b265;else if(_0x1edc95){var t=new ArrayBuffer(68);this.buffer8=new Uint8Array(t),this.blocks=new Uint32Array(t)}else this.blocks=[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0];this.h0=this.h1=this.h2=this.h3=this.start=this.bytes=this.hBytes=0,this.finalized=this.hashed=!1,this.first=!0}!_0x11d177.JS_MD5_NO_NODE_JS&&Array.isArray||(Array.isArray=function(e){return"[object Array]"===Object.prototype.toString.call(e)}),!_0x1edc95||!_0x11d177.JS_MD5_NO_ARRAY_BUFFER_IS_VIEW&&ArrayBuffer.isView||(ArrayBuffer.isView=function(e){return"object"==typeof e&&e.buffer&&e.buffer.constructor===ArrayBuffer}),_0x22f902.prototype.update=function(e){if(!this.finalized){var t,r=typeof e;if("string"!==r){if("object"!==r)throw _0x1f977a;if(null===e)throw _0x1f977a;if(_0x1edc95&&e.constructor===ArrayBuffer)e=new Uint8Array(e);else if(!(Array.isArray(e)||_0x1edc95&&ArrayBuffer.isView(e)))throw _0x1f977a;t=!0}for(var n,o,a=0,i=e.length,c=this.blocks,f=this.buffer8;a<i;){if(this.hashed&&(this.hashed=!1,c[0]=c[16],c[16]=c[1]=c[2]=c[3]=c[4]=c[5]=c[6]=c[7]=c[8]=c[9]=c[10]=c[11]=c[12]=c[13]=c[14]=c[15]=0),t)if(_0x1edc95)for(o=this.start;a<i&&o<64;++a)f[o++]=e[a];else for(o=this.start;a<i&&o<64;++a)c[o>>2]|=e[a]<<_0x4d13bd[3&o++];else if(_0x1edc95)for(o=this.start;a<i&&o<64;++a)(n=e.charCodeAt(a))<128?f[o++]=n:n<2048?(f[o++]=n>>6|192,f[o++]=63&n|128):n<55296||n>=57344?(f[o++]=n>>12|224,f[o++]=n>>6&63|128,f[o++]=63&n|128):(n=65536+((1023&n)<<10|1023&e.charCodeAt(++a)),f[o++]=n>>18|240,f[o++]=n>>12&63|128,f[o++]=n>>6&63|128,f[o++]=63&n|128);else for(o=this.start;a<i&&o<64;++a)(n=e.charCodeAt(a))<128?c[o>>2]|=n<<_0x4d13bd[3&o++]:n<2048?(c[o>>2]|=(n>>6|192)<<_0x4d13bd[3&o++],c[o>>2]|=(63&n|128)<<_0x4d13bd[3&o++]):n<55296||n>=57344?(c[o>>2]|=(n>>12|224)<<_0x4d13bd[3&o++],c[o>>2]|=(n>>6&63|128)<<_0x4d13bd[3&o++],c[o>>2]|=(63&n|128)<<_0x4d13bd[3&o++]):(n=65536+((1023&n)<<10|1023&e.charCodeAt(++a)),c[o>>2]|=(n>>18|240)<<_0x4d13bd[3&o++],c[o>>2]|=(n>>12&63|128)<<_0x4d13bd[3&o++],c[o>>2]|=(n>>6&63|128)<<_0x4d13bd[3&o++],c[o>>2]|=(63&n|128)<<_0x4d13bd[3&o++]);this.lastByteIndex=o,this.bytes+=o-this.start,o>=64?(this.start=o-64,this.hash(),this.hashed=!0):this.start=o}return this.bytes>4294967295&&(this.hBytes+=this.bytes/4294967296|0,this.bytes=this.bytes%4294967296),this}},_0x22f902.prototype.finalize=function(){if(!this.finalized){this.finalized=!0;var e=this.blocks,t=this.lastByteIndex;e[t>>2]|=_0x146907[3&t],t>=56&&(this.hashed||this.hash(),e[0]=e[16],e[16]=e[1]=e[2]=e[3]=e[4]=e[5]=e[6]=e[7]=e[8]=e[9]=e[10]=e[11]=e[12]=e[13]=e[14]=e[15]=0),e[14]=this.bytes<<3,e[15]=this.hBytes<<3|this.bytes>>>29,this.hash()}},_0x22f902.prototype.hash=function(){var e,t,r,n,o,a,i=this.blocks;this.first?t=((t=((e=((e=i[0]-680876937)<<7|e>>>25)-271733879|0)^(r=((r=((n=((n=(2004318071&e^-1732584194)+i[1]-117830708)<<12|n>>>20)+e|0)&(-271733879^e)^-271733879)+i[2]-1126478375)<<17|r>>>15)+n|0)&(n^e))+i[3]-1316259209)<<22|t>>>10)+r|0:(e=this.h0,t=this.h1,r=this.h2,t=((t+=((e=((e+=((n=this.h3)^t&(r^n))+i[0]-680876936)<<7|e>>>25)+t|0)^(r=((r+=(t^(n=((n+=(r^e&(t^r))+i[1]-389564586)<<12|n>>>20)+e|0)&(e^t))+i[2]+606105819)<<17|r>>>15)+n|0)&(n^e))+i[3]-1044525330)<<22|t>>>10)+r|0),t=((t+=((e=((e+=(n^t&(r^n))+i[4]-176418897)<<7|e>>>25)+t|0)^(r=((r+=(t^(n=((n+=(r^e&(t^r))+i[5]+1200080426)<<12|n>>>20)+e|0)&(e^t))+i[6]-1473231341)<<17|r>>>15)+n|0)&(n^e))+i[7]-45705983)<<22|t>>>10)+r|0,t=((t+=((e=((e+=(n^t&(r^n))+i[8]+1770035416)<<7|e>>>25)+t|0)^(r=((r+=(t^(n=((n+=(r^e&(t^r))+i[9]-1958414417)<<12|n>>>20)+e|0)&(e^t))+i[10]-42063)<<17|r>>>15)+n|0)&(n^e))+i[11]-1990404162)<<22|t>>>10)+r|0,t=((t+=((e=((e+=(n^t&(r^n))+i[12]+1804603682)<<7|e>>>25)+t|0)^(r=((r+=(t^(n=((n+=(r^e&(t^r))+i[13]-40341101)<<12|n>>>20)+e|0)&(e^t))+i[14]-1502002290)<<17|r>>>15)+n|0)&(n^e))+i[15]+1236535329)<<22|t>>>10)+r|0,t=((t+=((n=((n+=(t^r&((e=((e+=(r^n&(t^r))+i[1]-165796510)<<5|e>>>27)+t|0)^t))+i[6]-1069501632)<<9|n>>>23)+e|0)^e&((r=((r+=(e^t&(n^e))+i[11]+643717713)<<14|r>>>18)+n|0)^n))+i[0]-373897302)<<20|t>>>12)+r|0,t=((t+=((n=((n+=(t^r&((e=((e+=(r^n&(t^r))+i[5]-701558691)<<5|e>>>27)+t|0)^t))+i[10]+38016083)<<9|n>>>23)+e|0)^e&((r=((r+=(e^t&(n^e))+i[15]-660478335)<<14|r>>>18)+n|0)^n))+i[4]-405537848)<<20|t>>>12)+r|0,t=((t+=((n=((n+=(t^r&((e=((e+=(r^n&(t^r))+i[9]+568446438)<<5|e>>>27)+t|0)^t))+i[14]-1019803690)<<9|n>>>23)+e|0)^e&((r=((r+=(e^t&(n^e))+i[3]-187363961)<<14|r>>>18)+n|0)^n))+i[8]+1163531501)<<20|t>>>12)+r|0,t=((t+=((n=((n+=(t^r&((e=((e+=(r^n&(t^r))+i[13]-1444681467)<<5|e>>>27)+t|0)^t))+i[2]-51403784)<<9|n>>>23)+e|0)^e&((r=((r+=(e^t&(n^e))+i[7]+1735328473)<<14|r>>>18)+n|0)^n))+i[12]-1926607734)<<20|t>>>12)+r|0,t=((t+=((a=(n=((n+=((o=t^r)^(e=((e+=(o^n)+i[5]-378558)<<4|e>>>28)+t|0))+i[8]-2022574463)<<11|n>>>21)+e|0)^e)^(r=((r+=(a^t)+i[11]+1839030562)<<16|r>>>16)+n|0))+i[14]-35309556)<<23|t>>>9)+r|0,t=((t+=((a=(n=((n+=((o=t^r)^(e=((e+=(o^n)+i[1]-1530992060)<<4|e>>>28)+t|0))+i[4]+1272893353)<<11|n>>>21)+e|0)^e)^(r=((r+=(a^t)+i[7]-155497632)<<16|r>>>16)+n|0))+i[10]-1094730640)<<23|t>>>9)+r|0,t=((t+=((a=(n=((n+=((o=t^r)^(e=((e+=(o^n)+i[13]+681279174)<<4|e>>>28)+t|0))+i[0]-358537222)<<11|n>>>21)+e|0)^e)^(r=((r+=(a^t)+i[3]-722521979)<<16|r>>>16)+n|0))+i[6]+76029189)<<23|t>>>9)+r|0,t=((t+=((a=(n=((n+=((o=t^r)^(e=((e+=(o^n)+i[9]-640364487)<<4|e>>>28)+t|0))+i[12]-421815835)<<11|n>>>21)+e|0)^e)^(r=((r+=(a^t)+i[15]+530742520)<<16|r>>>16)+n|0))+i[2]-995338651)<<23|t>>>9)+r|0,t=((t+=((n=((n+=(t^((e=((e+=(r^(t|~n))+i[0]-198630844)<<6|e>>>26)+t|0)|~r))+i[7]+1126891415)<<10|n>>>22)+e|0)^((r=((r+=(e^(n|~t))+i[14]-1416354905)<<15|r>>>17)+n|0)|~e))+i[5]-57434055)<<21|t>>>11)+r|0,t=((t+=((n=((n+=(t^((e=((e+=(r^(t|~n))+i[12]+1700485571)<<6|e>>>26)+t|0)|~r))+i[3]-1894986606)<<10|n>>>22)+e|0)^((r=((r+=(e^(n|~t))+i[10]-1051523)<<15|r>>>17)+n|0)|~e))+i[1]-2054922799)<<21|t>>>11)+r|0,t=((t+=((n=((n+=(t^((e=((e+=(r^(t|~n))+i[8]+1873313359)<<6|e>>>26)+t|0)|~r))+i[15]-30611744)<<10|n>>>22)+e|0)^((r=((r+=(e^(n|~t))+i[6]-1560198380)<<15|r>>>17)+n|0)|~e))+i[13]+1309151649)<<21|t>>>11)+r|0,t=((t+=((n=((n+=(t^((e=((e+=(r^(t|~n))+i[4]-145523070)<<6|e>>>26)+t|0)|~r))+i[11]-1120210379)<<10|n>>>22)+e|0)^((r=((r+=(e^(n|~t))+i[2]+718787259)<<15|r>>>17)+n|0)|~e))+i[9]-343485551)<<21|t>>>11)+r|0,this.first?(this.h0=e+1732584193|0,this.h1=t-271733879|0,this.h2=r-1732584194|0,this.h3=n+271733878|0,this.first=!1):(this.h0=this.h0+e|0,this.h1=this.h1+t|0,this.h2=this.h2+r|0,this.h3=this.h3+n|0)},_0x22f902.prototype.hex=function(){this.finalize();var e=this.h0,t=this.h1,r=this.h2,n=this.h3;return _0x142491[e>>4&15]+_0x142491[15&e]+_0x142491[e>>12&15]+_0x142491[e>>8&15]+_0x142491[e>>20&15]+_0x142491[e>>16&15]+_0x142491[e>>28&15]+_0x142491[e>>24&15]+_0x142491[t>>4&15]+_0x142491[15&t]+_0x142491[t>>12&15]+_0x142491[t>>8&15]+_0x142491[t>>20&15]+_0x142491[t>>16&15]+_0x142491[t>>28&15]+_0x142491[t>>24&15]+_0x142491[r>>4&15]+_0x142491[15&r]+_0x142491[r>>12&15]+_0x142491[r>>8&15]+_0x142491[r>>20&15]+_0x142491[r>>16&15]+_0x142491[r>>28&15]+_0x142491[r>>24&15]+_0x142491[n>>4&15]+_0x142491[15&n]+_0x142491[n>>12&15]+_0x142491[n>>8&15]+_0x142491[n>>20&15]+_0x142491[n>>16&15]+_0x142491[n>>28&15]+_0x142491[n>>24&15]},_0x22f902.prototype.toString=_0x22f902.prototype.hex,_0x22f902.prototype.digest=function(){this.finalize();var e=this.h0,t=this.h1,r=this.h2,n=this.h3;return[255&e,e>>8&255,e>>16&255,e>>24&255,255&t,t>>8&255,t>>16&255,t>>24&255,255&r,r>>8&255,r>>16&255,r>>24&255,255&n,n>>8&255,n>>16&255,n>>24&255]},_0x22f902.prototype.array=_0x22f902.prototype.digest,_0x22f902.prototype.arrayBuffer=function(){this.finalize();var e=new ArrayBuffer(16),t=new Uint32Array(e);return t[0]=this.h0,t[1]=this.h1,t[2]=this.h2,t[3]=this.h3,e},_0x22f902.prototype.buffer=_0x22f902.prototype.arrayBuffer,_0x22f902.prototype.base64=function(){for(var e,t,r,n="",o=this.array(),a=0;a<15;)e=o[a++],t=o[a++],r=o[a++],n+=_0xcb4d61[e>>>2]+_0xcb4d61[63&(e<<4|t>>>4)]+_0xcb4d61[63&(t<<2|r>>>6)]+_0xcb4d61[63&r];return e=o[a],n+(_0xcb4d61[e>>>2]+_0xcb4d61[e<<4&63]+"==")};var _0x336469=_0x1edabb();_0x299a21?_0xb9c7d1.exports=_0x336469:(_0x11d177.md5=_0x336469,_0x5efc8f&&(void 0)(function(){return _0x336469}))})()});function _0x5dd467(e){return w_0x5c3140("484e4f4a403f5243000027194f9666590000000044a16fed000000270700001400013e000a140002070001140001413d000d0211010011010243011400014111000142000200200d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d0d",{get 0(){return _0x90795},1:arguments,2:e},this)}function _0x176a57(){return!!document.documentMode}var _0x39693d={sec:9,asgw:5,init:0},_0x6caf={bogusIndex:0,msNewTokenList:[],moveList:[],clickList:[],keyboardList:[],activeState:[],aidList:[]};function _0x389396(e,t){return w_0x5c3140("484e4f4a403f52430031032581faca6c0000000093505d60000001c60700001400010d1400020700011100020700021607000311000207000416070005110002070006161100021101021314000307000714000403001400061101011200081100060303182a4700b11101014a1200091700062143010400ff2e03102b1101014a1200091700062143010400ff2e03082b2f1101014a1200091700062143010400ff2e2f1400051100041100034a12000a1100050500fc00002e03122c43011817000435491100041100034a12000a110005050003f0002e030c2c43011817000435491100041100034a12000a110005040fc02e03062c43011817000435491100041100034a12000a110005033f2e430118170004354945ff3f110101120008110006190300294700b41101014a1200091700062143010400ff2e03102b110101120008110006294700161101014a12000911000643010400ff2e03082b45000203002f1400051100041100034a12000a1100050500fc00002e03122c43011817000435491100041100034a12000a110005050003f0002e030c2c4301181700043549110004110101120008110006294700161100034a12000a110005040fc02e03062c430145000311000118170004354911000411000118170004354911000442000b011441686b6a6d6c6f6e616063626564676679787b7a7d7c7f7e717073484b4a4d4c4f4e414043424544474659585b5a5d5c5f5e51505319181b1a1d1c1f1e1110020614025a19416d424d594e411d73625a786b111906644f5f5e1a1f7160187b1b1c027e7c68456c401e67654b4658707d66795c53446f4363475b505110617f6e4a487a5d6a4c14025a18416d424d594e411d73625a786b111906644f5f5e1a1f7160187b1b1c047e7c68456c401e67654b4658707d66795c53446f4363475b505110617f6e4a487a5d6a4c14025a1b0006454c474e5d410a4a41485b6a464d4c685d064a41485b685d",{0:arguments,1:e,2:t},this)}function _0x3262d3(e){return"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/".indexOf(e)}function _0xb5350b(e){var t,r,n,o,a,i="";for(t=0;t<e.length-3;t+=4)r=_0x3262d3(e.charAt(t)),n=_0x3262d3(e.charAt(t+1)),o=_0x3262d3(e.charAt(t+2)),a=_0x3262d3(e.charAt(t+3)),i+=String.fromCharCode(r<<2|n>>>4),"="!==e.charAt(t+2)&&(i+=String.fromCharCode(n<<4&240|o>>>2&15)),"="!==e.charAt(t+3)&&(i+=String.fromCharCode(o<<6&192|a));return i}_0x6caf.envcode=0,_0x6caf.msToken="",_0x6caf.msStatus=_0x39693d.init,_0x6caf.__ac_testid="",_0x6caf.ttwid="",_0x6caf.tt_webid="",_0x6caf.tt_webid_v2="";var _0x28d239=0,_0x2d6b72,_0x1e9bba,_0xdc7355,_0xf08186;function _0x33f406(e){return e&=63,String.fromCharCode(e+(e<26?65:e<52?71:e<62?-4:-17))}function _0x4da136(e){var t=_0x33f406;return t(e>>24)+t(e>>18)+t(e>>12)+t(e>>6)+t(e)}_0x2d6b72=_0x1e9bba=function(e){return _0x2d6b72=_0xdc7355,_0x28d239=e,_0x4da136(e>>2)},_0xdc7355=function(e){_0x2d6b72=_0xf08186;var t=_0x28d239<<28|e>>>4;return _0x28d239=e,_0x4da136(t)},_0xf08186=function(e){return _0x2d6b72=_0x1e9bba,_0x4da136(_0x28d239<<26|e>>>6)+_0x33f406(e)};var _0x539097=2654435769,_0x12ada0;function _0x75d5b3(e,t){var r=e.length,n=r<<2;if(t){var o=e[r-1];if(o<(n-=4)-3||o>n)return null;n=o}for(var a=0;a<r;a++)e[a]=String.fromCharCode(255&e[a],e[a]>>>8&255,e[a]>>>16&255,e[a]>>>24&255);var i=e.join("");return t?i.substring(0,n):i}function _0x183951(e,t){var r,n=e.length,o=n>>2;3&n&&++o,t?(r=new Array(o+1))[o]=n:r=new Array(o);for(var a=0;a<n;++a)r[a>>2]|=e.charCodeAt(a)<<((3&a)<<3);return r}function _0x25c901(e){return-1&e}function _0x38d33e(e,t,r,n,o,a){return(r>>>5^t<<2)+(t>>>3^r<<4)^(e^t)+(a[3&n^o]^r)}function _0x231484(e){return e.length<4&&(e.length=4),e}function _0x4aaf04(e,t){var r,n,o,a,i,c=e.length,f=c-1;for(r=e[0],o=_0x25c901(Math.floor(6+52/c)*_0x539097);0!==o;o=_0x25c901(o-_0x539097)){for(a=o>>>2&3,i=f;i>0;--i)n=e[i-1],r=e[i]=_0x25c901(e[i]-_0x38d33e(o,r,n,i,a,t));n=e[f],r=e[0]=_0x25c901(e[0]-_0x38d33e(o,r,n,0,a,t))}return e}function _0x532596(e){if(/^[\x00-\x7f]*$/.test(e))return e;for(var t=[],r=e.length,n=0,o=0;n<r;++n,++o){var a=e.charCodeAt(n);if(a<128)t[o]=e.charAt(n);else if(a<2048)t[o]=String.fromCharCode(a>>6|192,63&a|128);else{if(!(a<55296||a>57343)){if(n+1<r){var i=e.charCodeAt(n+1);if(a<56320&&i>=56320&&i<=57343){var c=65536+((1023&a)<<10|1023&i);t[o]=String.fromCharCode(c>>18&63|240,c>>12&63|128,c>>6&63|128,63&c|128),++n;continue}}throw new Error("Malformed string")}t[o]=String.fromCharCode(a>>12|224,a>>6&63|128,63&a|128)}}return t.join("")}function _0x45fbef(e,t){for(var r=new Array(t),n=0,o=0,a=e.length;n<t&&o<a;n++){var i=e.charCodeAt(o++);switch(i>>4){case 0:case 1:case 2:case 3:case 4:case 5:case 6:case 7:r[n]=i;break;case 12:case 13:if(!(o<a))throw new Error("Unfinished UTF-8 octet sequence");r[n]=(31&i)<<6|63&e.charCodeAt(o++);break;case 14:if(!(o+1<a))throw new Error("Unfinished UTF-8 octet sequence");r[n]=(15&i)<<12|(63&e.charCodeAt(o++))<<6|63&e.charCodeAt(o++);break;case 15:if(!(o+2<a))throw new Error("Unfinished UTF-8 octet sequence");var c=((7&i)<<18|(63&e.charCodeAt(o++))<<12|(63&e.charCodeAt(o++))<<6|63&e.charCodeAt(o++))-65536;if(!(c>=0&&c<=1048575))throw new Error("Character outside valid Unicode range: 0x"+c.toString(16));r[n++]=c>>10&1023|55296,r[n]=1023&c|56320;break;default:throw new Error("Bad UTF-8 encoding 0x"+i.toString(16))}}return n<t&&(r.length=n),String.fromCharCode.apply(String,r)}function _0x25bfe1(e,t){for(var r=[],n=new Array(32768),o=0,a=0,i=e.length;o<t&&a<i;o++){var c=e.charCodeAt(a++);switch(c>>4){case 0:case 1:case 2:case 3:case 4:case 5:case 6:case 7:n[o]=c;break;case 12:case 13:if(!(a<i))throw new Error("Unfinished UTF-8 octet sequence");n[o]=(31&c)<<6|63&e.charCodeAt(a++);break;case 14:if(!(a+1<i))throw new Error("Unfinished UTF-8 octet sequence");n[o]=(15&c)<<12|(63&e.charCodeAt(a++))<<6|63&e.charCodeAt(a++);break;case 15:if(!(a+2<i))throw new Error("Unfinished UTF-8 octet sequence");var f=((7&c)<<18|(63&e.charCodeAt(a++))<<12|(63&e.charCodeAt(a++))<<6|63&e.charCodeAt(a++))-65536;if(!(f>=0&&f<=1048575))throw new Error("Character outside valid Unicode range: 0x"+f.toString(16));n[o++]=f>>10&1023|55296,n[o]=1023&f|56320;break;default:throw new Error("Bad UTF-8 encoding 0x"+c.toString(16))}if(o>=32766){var s=o+1;n.length=s,r[r.length]=String.fromCharCode.apply(String,n),t-=s,o=-1}}return o>0&&(n.length=o,r[r.length]=String.fromCharCode.apply(String,n)),r.join("")}function _0x31dfb5(e,t){return(null==t||t<0)&&(t=e.length),0===t?"":/^[\x00-\x7f]*$/.test(e)||!/^[\x00-\xff]*$/.test(e)?t===e.length?e:e.substr(0,t):t<65535?_0x45fbef(e,t):_0x25bfe1(e,t)}function _0x4bb829(e,t){return null==e||0===e.length?e:(t=_0x532596(t),_0x31dfb5(_0x75d5b3(_0x4aaf04(_0x183951(e,!1),_0x231484(_0x183951(t,!1))),!0)))}function _0x39dfe4(){var e="";try{window.sessionStorage&&(e=window.sessionStorage.getItem("_byted_param_sw")),e&&!window.localStorage||(e=window.localStorage.getItem("_byted_param_sw"))}catch(e){}if(e)try{var t=_0x4bb829(_0xb5350b(e.slice(8)),e.slice(0,8));if("on"===t)return!0;if("off"===t)return!1}catch(e){}return!1}function _0x1b4bf1(){return w_0x5c3140("484e4f4a403f524300023a25866a0150000000002b0aa01b000001541101001200004a12000143001400011100014a120002070003430103002a47000201420700041400021101013a070004254700060700044500090211010211010143011100022534000d1101014a1200054300070006263400161101031200071200054a12000811010143010700062634001e1101043a07000425470006070004450009021101021101044301110002253400151101044a12000543004a120002070009430103002734001e1101003a070004254700060700044500090211010211010043011100022534000d1101004a120005430007000a263400121101001200004a12000207000b430103002a34001e1101053a07000425470006070004450009021101021101054301110002254700020042021101064300324700331101073a070004254700060700044500090211010211010743011100022534000d1101074a120005430007000c2647000200420142000d096f697f685b7d7f746e0b6e7556756d7f68597b697f0773747e7f62557c087f767f796e687574096f747e7f7c73747f7e086e75496e6873747d0f417578707f796e3a4d73747e756d47096a68756e756e636a7f04797b7676085e75796f777f746e12417578707f796e3a547b6c737d7b6e7568470570697e757710417578707f796e3a5273696e75686347",{get 0(){return void 0!==navigator?navigator:void 0},get 1(){return void 0!==window?window:void 0},get 2(){return _0x1db123},3:Object,get 4(){return void 0!==document?document:void 0},get 5(){return"undefined"!=typeof location?location:void 0},get 6(){return _0x176a57},get 7(){return"undefined"!=typeof history?history:void 0},8:arguments},this)}function _0x1f9824(){var e="";if(_0x6caf.PLUGIN)e=_0x6caf.PLUGIN;else{for(var t=[],r=navigator.plugins||[],n=0;n<5;n++)try{for(var o=r[n],a=[],i=0;i<o.length;i++)o.item(i)&&a.push(o.item(i).type);var c=o.name+"";o.version&&(c+=o.version+""),c+=o.filename+"",c+=a.join(""),t.push(c)}catch(e){}e=t.join("##"),_0x6caf.PLUGIN=e}return e.slice(0,1024)}function _0x5863d1(){return w_0x5c3140("484e4f4a403f524300341b3e336a785800000000dbd5951f000001b50114000111010012000000254700070014000145001b1101001200000125470007011400014500090211010143001400010d010e0001010e0002010e00031100010e0004010e0005010e0006010e0007010e0008010e0009010e000a010e000b000e000c1400020211010243001100021500051100021200053247005c021101031100024301490211010411000243014902110105430011000215000702110106430011000215000802110107430011000215000902110108430011000215000b0211010943001100021500030211010a4300110002150002030014000311000303012f170003354911000311000212000b03012b2f170003354911000311000212000a03022b2f170003354911000311000212000903032b2f170003354911000311000212000803042b2f170003354911000311000212000703052b2f17000335491100031100020700061303062b2f170003354911000311000212000503072b2f17000335491100031100020700041303082b2f170003354911000311000212000303092b2f1700033549110003110002120002030a2b2f170003354911010b12000d1100032f11010b07000d354911000242000e0e547b6a796a66587c627f686344650a6f62796e687f58626c650a6864657862787f6e657f086764686a7f62646506787c627f6863036f6466086f6e697e6c6c6e790465646f6e077b636a657f6466097c6e696f79627d6e7909626568646c65627f640463646460047f6e787f076e657d68646f6e",{get 0(){return _0x462335},get 1(){return _0x39dfe4},get 2(){return _0x1b4bf1},get 3(){return _0x53b77d},get 4(){return _0x49b1d7},get 5(){return _0x3ed707},get 6(){return _0x532cd9},get 7(){return _0x3391fc},get 8(){return _0x462256},get 9(){return _0x3cee0e},get 10(){return _0x28e2ec},get 11(){return _0x6caf},12:arguments},this)}function _0x20b77a(e){return Array.isArray(e)?e.map(_0x20b77a):e instanceof Object?Object.keys(e).sort().reduce(function(t,r){return t[r]=_0x20b77a(e[r]),t},{}):e}function _0xc6f828(e){var t,r=document.createElement("canvas");r.width=48,r.height=16;var n=r.getContext("2d");n.font="14px serif",n.fillText("龘ฑภ경",2,12),n.shadowBlur=2,n.showOffsetX=1,n.showColor="lime",n.arc(8,8,8,0,2),n.stroke(),t=r.toDataURL();for(var o=0;o<32;o++)e=65599*e+t.charCodeAt(e%t.length)>>>0;return e}var _0x37a93a=0;function _0x1a39c4(){if(_0x37a93a)return _0x37a93a;_0x37a93a=_0xc6f828(3735928559)}var _0x45ece5={fpProfileUrl:"https://mssdk.bytedance.com/websdk/v1/getInfo"},_0x47ec2a={};function _0x487576(){if(_0x6caf.GPUINFO)return _0x6caf.GPUINFO;try{var e=document.createElement("canvas").getContext("webgl"),t=e.getExtension("WEBGL_debug_renderer_info"),r=e.getParameter(t.UNMASKED_VENDOR_WEBGL)+"/"+e.getParameter(t.UNMASKED_RENDERER_WEBGL);return _0x6caf.GPUINFO=r,r}catch(e){return""}}function _0x5e5a64(e,t){for(var r={},n=0;n<t.length;n++){var o=t[n],a=e[o];null==a&&(a=!1),null===a||"function"!=typeof a&&"object"!==_0x1db123(a)||(a=!0),r[o]=a}return r}function _0x2a6ac2(){return _0x5e5a64(navigator,["appCodeName","appName","platform","product","productSub","hardwareConcurrency","cpuClass","maxTouchPoints","oscpu","vendor","vendorSub","doNotTrack","vibrate","credentials","storage","requestMediaKeySystemAccess","bluetooth"])}function _0x226933(){return _0x5e5a64(window,["Image","innerHeight","innerWidth","screenX","screenY","isSecureContext","devicePixelRatio","toolbar","locationbar","ActiveXObject","external","mozRTCPeerConnection","postMessage","webkitRequestAnimationFrame","BluetoothUUID","netscape"])}function _0x1e5a7f(){return _0x5e5a64(document,["characterSet","compatMode","documentMode","layers","images"])}function _0x11a1d6(){var e=document.createElement("canvas"),t=null;try{t=e.getContext("webgl")||e.getContext("experimental-webgl")}catch(e){}return t||=null,t}function _0x39c3d8(e){var t=e.getExtension("EXT_texture_filter_anisotropic")||e.getExtension("WEBKIT_EXT_texture_filter_anisotropic")||e.getExtension("MOZ_EXT_texture_filter_anisotropic");if(t){var r=e.getParameter(t.MAX_TEXTURE_MAX_ANISOTROPY_EXT);return 0===r&&(r=2),r}return null}function _0x425568(){if(_0x6caf.WEBGL)return _0x6caf.WEBGL;var e=_0x11a1d6();if(!e)return{};var t={supportedExtensions:e.getSupportedExtensions()||[],antialias:e.getContextAttributes().antialias,blueBits:e.getParameter(e.BLUE_BITS),depthBits:e.getParameter(e.DEPTH_BITS),greenBits:e.getParameter(e.GREEN_BITS),maxAnisotropy:_0x39c3d8(e),maxCombinedTextureImageUnits:e.getParameter(e.MAX_COMBINED_TEXTURE_IMAGE_UNITS),maxCubeMapTextureSize:e.getParameter(e.MAX_CUBE_MAP_TEXTURE_SIZE),maxFragmentUniformVectors:e.getParameter(e.MAX_FRAGMENT_UNIFORM_VECTORS),maxRenderbufferSize:e.getParameter(e.MAX_RENDERBUFFER_SIZE),maxTextureImageUnits:e.getParameter(e.MAX_TEXTURE_IMAGE_UNITS),maxTextureSize:e.getParameter(e.MAX_TEXTURE_SIZE),maxVaryingVectors:e.getParameter(e.MAX_VARYING_VECTORS),maxVertexAttribs:e.getParameter(e.MAX_VERTEX_ATTRIBS),maxVertexTextureImageUnits:e.getParameter(e.MAX_VERTEX_TEXTURE_IMAGE_UNITS),maxVertexUniformVectors:e.getParameter(e.MAX_VERTEX_UNIFORM_VECTORS),shadingLanguageVersion:e.getParameter(e.SHADING_LANGUAGE_VERSION),stencilBits:e.getParameter(e.STENCIL_BITS),version:e.getParameter(e.VERSION)};return _0x6caf.WEBGL=t,t}function _0x18707d(){var e={};return e.navigator=_0x2a6ac2(),e.window=_0x226933(),e.document=_0x1e5a7f(),e.webgl=_0x425568(),e.gpu=_0x487576(),e.plugins=_0x1f9824(),_0x6caf.SECINFO=e,e}var _0x2e10da={kHttp:0,kWebsocket:1},_0x3f742e=_0x45b94b,_0x5dde58={WEB_DEVICE_INFO:8};function _0x3d13cf(e){try{return window.localStorage?window.localStorage.getItem(e):null}catch(e){return null}}function _0x21db29(e,t){for(var r,n=[],o=0,a="",i=0;i<256;i++)n[i]=i;for(var c=0;c<256;c++)o=(o+n[c]+e.charCodeAt(c%e.length))%256,r=n[c],n[c]=n[o],n[o]=r;var f=0;o=0;for(var s=0;s<t.length;s++)o=(o+n[f=(f+1)%256])%256,r=n[f],n[f]=n[o],n[o]=r,a+=String.fromCharCode(t.charCodeAt(s)^n[(n[f]+n[o])%256]);return a}var _0x45bf15=_0x21db29,_0x48a082={pb:2,json:1},_0x216650={kNoMove:2,kNoClickTouch:4,kNoKeyboardEvent:8,kMoveFast:16,kKeyboardFast:32,kFakeOperations:64},_0x5dc9cc={sTm:0,acc:0},_0xf63a81={T_MOVE:1,T_CLICK:2,T_KEYBOARD:3},_0x2786f5=!1,_0x9fb121=[],_0x207cc5=[],_0x191fa5=[],_0xe06992={ubcode:0};function _0x388856(e,t){return e+t}function _0x20a3d9(e){return e*e}function _0x9c0be2(e,t){if(e.length>200&&e.splice(0,100),e.length>0){var r=e[e.length-1];if(t.d-r.d<=0||"y"in t&&t.x===r.x&&t.y===r.y)return}e.push(t)}function _0x1d26db(e,t,r){if(_0x462335.enableTrack){if(r!==_0xf63a81.T_MOVE)return r===_0xf63a81.T_CLICK?(e.length>=500&&_0x450b73(),void e.push(t)):r===_0xf63a81.T_KEYBOARD?(e.length>500&&_0x450b73(),void e.push(t)):void 0;if(e.length>=500&&_0x450b73(),e.length>0){var n=e[e.length-1],o=n.x,a=n.y,i=n.ts;if(o===t.x&&a===t.y)return;if(t.ts-i<500)return}e.push(t)}}var _0x19ffaf={init:0,running:1,exit:2,flush:3},_0x1a755e={mousemove:_0x3dcfd5,touchmove:_0x3dcfd5,keydown:_0x56114b,touchstart:_0x19d89b,mousedown:_0x19d89b},_0x18582a=!1;function _0x1dbe74(){if(document&&document.addEventListener&&!_0x18582a){for(var e=0,t=Object.keys(_0x1a755e);e<t.length;e++){var r=t[e];document.addEventListener(r,_0x1a755e[r])}_0x18582a=!0}}function _0x3dcfd5(e){var t=e,r=e.type;e.changedTouches&&"touchmove"===r&&(t=e.touches[0],_0x2786f5=!0);var n={x:Math.floor(t.clientX),y:Math.floor(t.clientY),d:Date.now()};_0x9c0be2(_0x9fb121,n),_0x1d26db(_0x6caf.moveList,{ts:n.d,x:n.x,y:n.y},_0xf63a81.T_MOVE)}function _0x56114b(e){var t=0;(e.altKey||e.ctrlKey||e.metaKey||e.shiftKey)&&(t=1);var r={x:t,d:Date.now()};_0x9c0be2(_0x191fa5,r),_0x1d26db(_0x6caf.keyboardList,{ts:r.d},_0xf63a81.T_KEYBOARD)}function _0x19d89b(e){var t=e,r=e.type;e.changedTouches&&"touchstart"===r&&(t=e.touches[0],_0x2786f5=!0);var n={x:Math.floor(t.clientX),y:Math.floor(t.clientY),d:Date.now()};_0x9c0be2(_0x207cc5,n),_0x1d26db(_0x6caf.clickList,{ts:n.d,x:n.x,y:n.y},_0xf63a81.T_CLICK)}function _0x42fe9b(e){return e.reduce(_0x388856)/e.length}function _0x3ea7d6(e){if(e.length<=1)return 0;var t=_0x42fe9b(e),r=e.map(function(e){return e-t});return Math.sqrt(r.map(_0x20a3d9).reduce(_0x388856)/(e.length-1))}function _0x52f064(e,t,r){var n=0,o=0;if(e.length>t){for(var a=[],i=0;i<e.length-1;i++){var c=e[i+1],f=e[i],s=c.d-f.d;s&&(r?a.push(1/s):a.push(Math.sqrt(_0x20a3d9(c.x-f.x)+_0x20a3d9(c.y-f.y))/s))}n=_0x42fe9b(a),0===(o=_0x3ea7d6(a))&&(o=.01)}return[n,o]}function _0x26d461(){var e=!1,t=0;try{document&&document.createEvent&&(document.createEvent("TouchEvent"),e=!0)}catch(e){}var r=_0x52f064(_0x9fb121,1),n=_0x52f064(_0x191fa5,5,!0),o=1;!e&&_0x2786f5&&(o|=64,t|=_0x216650.kFakeOperations),0===_0x9fb121.length?(o|=2,t|=_0x216650.kNoMove):r[0]>50&&(o|=16,t|=_0x216650.kMoveFast),0===_0x207cc5.length&&(o|=4,t|=_0x216650.kNoClickTouch),0===_0x191fa5.length?(o|=8,t|=_0x216650.kNoKeyboardEvent):n[0]>.5&&(o|=32,t|=_0x216650.kKeyboardFast),_0xe06992.ubcode=t;var a=o.toString(32);return 1===a.length?a="00"+a:2===a.length&&(a="0"+a),a}function _0x4145f8(e,t){for(var r=t.length,n=new ArrayBuffer(r+1),o=new Uint8Array(n),a=0,i=0;i<r;i++)o[i]=t[i],a^=t[i];o[r]=a;var c=255&Math.floor(255*Math.random()),f=String.fromCharCode.apply(null,o),s=_0x21db29(String.fromCharCode(c),f),u="";return u+=String.fromCharCode(e),u+=String.fromCharCode(c),_0x389396(u+=s,"s1")}function _0x1633f2(e,t,r,n,o){_0x5863d1(),_0x26d461(),void 0!==n&&""!==n&&(n="");var a=_0x5dd467(n);o||="00000000000000000000000000000000";var i=new ArrayBuffer(9),c=new Uint8Array(i),f=e<<6|t<<5|(1&Math.floor(100*Math.random()))<<4;_0x6caf.bogusIndex++,_0x6caf.envcode=1;var s=63&_0x6caf.bogusIndex;c[0]=r<<6|s,c[1]=_0x6caf.envcode>>8&255,c[2]=255&_0x6caf.envcode,c[3]=_0xe06992.ubcode;var u=_0x42e709.decode(_0x5dd467(_0x42e709.decode(a)));c[4]=u[14],c[5]=u[15];var d=_0x42e709.decode(_0x5dd467(_0x42e709.decode(o)));return c[6]=d[14],c[7]=d[15],c[8]=255&Math.floor(255*Math.random()),_0x4145f8(f,c)}function _0x34c70a(e,t,r){return{"X-Bogus":_0x1633f2(_0x2e10da.kWebsocket,_0x462335.initialized,e,null,r)}}function _0x5c2014(e){return w_0x5c3140("484e4f4a403f524300362d0a5f00233c0000000029b6a730000000630214000103001400020700001400030700011400041101031100031347000d11010311000313140001450023110103110004134700130211010011010311000413430114000145000607000214000102110101110002021100014303140005110005420003096b1e7e601e606766710c6b1e7e601e63726a7f7c7277200303030303030303030303030303030303030303030303030303030303030303",{get 0(){return _0x5dd467},get 1(){return _0x34c70a},2:arguments,3:e},this)}var _0x3c4305=!1;function _0x5141ac(){return _0x3d13cf("xmst")||""}var _0x2d8bb4={navigator:{},wID:{},window:{},webgl:{},document:{},screen:{},plugins:{},custom:{}},_0x548676=null,_0x3c4266="undefined"!=typeof URL&&URL instanceof Object,_0x3311d7="undefined"!=typeof Request&&Request instanceof Object,_0x4f1fa4="undefined"!=typeof Headers&&Headers instanceof Object;function _0x3f720d(){_0x3af1be(),_0x1d82ac(),_0x344a4d()}function _0x3bfecb(e){this.name="ConfigException",this.message=e}var _0x589057={cn:{host:"https://mssdk.bytedance.com"}},_0x2bbf08=["/web/report"],_0x3d70a4;function _0x43f5a3(e){var t;return{host:t=e.boe||e.dev?e.boeHost:_0x589057[e.region].host,pathList:_0x2bbf08,reportUrl:t+_0x2bbf08[0]}}var _0x383bd7=!1,_0xd39ee2,_0x9e520d;function _0x53ee31(e){return w_0x5c3140("484e4f4a403f524300263203ec75a3740000000817718683000003051100011100022e4211011507000013002547000a070001110115070002160d03000e0003000e00040c00000e00050c00000e0006010e0007010e00000700080e0002010e00090d0305033c1a0e000a03020e000b0305033c1a0e000c0e000d0700080e000e000e000f03030e00101400011101004a1200111100011101154302491100011200030300253400161101014a120012110001120003430111000112000326470009110102070013440140110001120014330007110001120015324700091101020700164401401101031200174a12001811000112000343014911010412000303002547000c1100011200031101041500031100011200043247009c110001120002070008254700091101020700194401401100011200020700012447000911010207001a44014011000112000211010415000202110105110001430111010415001b021101061101071100011200100403e81a43024911000112001c0826330005110001022647002e11010412001d4a12001811000112001c43014911010412001d4a12001e05000000003b024301323211010415001c11000112000d4700a60011010415001f11010847006411000112000d12000a33001311000112000d12000a11010412000d12000a2947003f021101091101084301491101004a1200110d11010412000d11000112000d430311010415000d0211010a11010b11010412000d12000a0403e81a43021401084500351101004a1200110d11010412000d11000112000d430311010415000d0211010a11010b11010412000d12000a0403e81a430214010811000112002047001c1100011200201101041500200211010611010c03050403e81a4302491100010b1500210211010d4300490211010e1100011200054301490211010f1100011200064301490211011043004911011132330006110001120007470020001401111100011200071101041500070211010611011203050403e81a43024911000112000f4700241101041200223247001a0011010415002202110106110113030a0403e81a11000143034900110104150023084200240350524402575a064651535d5b5a03555d50055d4767707f0e515a555658516455405c785d47400f414658665143465d405166415851470347505d0003505142035246510a415a5d4075595b415a4008415a5d40605d595105404655575f04595b5051044c4c56530450504640065547475d535a0552585b5b461e5b44405d5b5a14555d501c7d5a40515351461d145d47145a51515051501503565b5107565b517c5b474024565b517c5b474014594147401456511444465b425d505150145d5a14565b5114595b505107555d50785d4740044441475c0f4651535d5b5a145d47145a41585815124651535d5b5a145d47145d5a4255585d50150a4651535d5b5a775b5a520142106b515a55565851675d535a5540414651064651504157510b515a55565851604655575f0444514652075b44405d5b5a47046b5052440b5d5a5d405d55585d4e5150",{0:Object,1:Math,get 2(){return _0x3bfecb},get 3(){return _0x6caf},get 4(){return _0x462335},get 5(){return _0x43f5a3},get 6(){return setTimeout},get 7(){return _0x5c328e},get 8(){return _0x3d70a4},set 8(e){_0x3d70a4=e},get 9(){return clearInterval},get 10(){return setInterval},get 11(){return _0x450b73},get 12(){return _0x1a39c4},get 13(){return _0x3f720d},get 14(){return _0x59992f},get 15(){return _0x39d569},get 16(){return _0x1dbe74},get 17(){return _0x383bd7},set 17(e){_0x383bd7=e},get 18(){return _0x18707d},get 19(){return _0x1c3b6d},20:arguments,21:e},this)}function _0x3498af(e){}function _0x59992f(e){for(var t=0;t<e.length;t++)e[t]&&_0x462335._enablePathListRegex.push(new RegExp(e[t]))}function _0x39d569(e){if(void 0!==e)for(var t=0;t<e.length;t++)_0x462335._urlRewriteRules.push([new RegExp(e[t][0]),e[t][1]])}function _0x32e4a6(){return window.__ac_referer||""}function _0x5b850b(){for(var e=document.cookie.split(";"),t=[],r=0;r<e.length;r++)if("__ac_testid"==(t=e[r].split("="))[0].trim()){_0x6caf.__ac_testid=t[1];break}}function _0x498349(e){return new _0x53ee31(e)}function _0x475194(e){}function _0x4a4111(e,t){1===e&&(_0x462335.track=Object.assign({},_0x462335.track,t))}function _0x271dea(e){void 0!==e&&""!=e&&(_0x6caf.ttwid=e)}function _0x3a4a1a(e){void 0!==e&&""!=e&&(_0x6caf.tt_webid=e)}function _0x3f0a66(e){void 0!==e&&""!=e&&(_0x6caf.tt_webid_v2=e)}_0x53ee31.prototype.frontierSign=_0x5c2014,_0x53ee31.prototype.getReferer=_0x32e4a6,_0x53ee31.prototype.setUserMode=_0x3498af,_0xd39ee2=_0x24dc34(_0x45b94b.refererKey)||"",_0x2ecc5a(_0x45b94b.refererKey),"__ac_blank"===_0xd39ee2?_0xd39ee2="":""===_0xd39ee2&&(_0xd39ee2=document.referrer),_0xd39ee2&&(window.__ac_referer=_0xd39ee2),_0x9e520d=_0x5141ac(),_0x9e520d&&(_0x6caf.msToken=_0x9e520d,_0x6caf.msStatus=_0x39693d.asgw),_0x5b850b(),_0x59992f(["/web/report"]);var _0x1649bc=!0;crawler=_0x5c2014,_0x1d18f2.frontierSign=_0x5c2014,_0x1d18f2.getReferer=_0x32e4a6,_0x1d18f2.init=_0x498349,_0x1d18f2.isWebmssdk=_0x1649bc,_0x1d18f2.report=_0x475194,_0x1d18f2.setConfig=_0x4a4111,_0x1d18f2.setTTWebid=_0x3a4a1a,_0x1d18f2.setTTWebidV2=_0x3f0a66,_0x1d18f2.setTTWid=_0x271dea,_0x1d18f2.setUserMode=_0x3498af,Object.defineProperty(_0x1d18f2,"__esModule",{value:!0})},_0x19937e(window.byted_acrawler={})}function get_sign(e){return crawler({"X-MS-STUB":e})["X-Bogus"]}return"function"==typeof get_sign?get_sign(md5):""}
return douyinSign;
})();"""

# 宿主 js.eval 只接受「單一表達式」，因此把庫和呼叫包進 IIFE，最後回傳簽名字串
JS_SIGN = "(() => {\n" + SIGN_LIB + "\nreturn douyinSign(seed);\n})()"


class Spider(BaseSpider):
    def init(self, extend=""):
        self.options = _options(extend)
        self._active_stop = None
        self._seq = 0
        self._lock = threading.RLock()
        self._tree = None

    # ==================== 入口 ====================

    def homeContent(self, filter):
        return {"class": [
            {"type_id": item["id"], "type_name": item["name"], "land": 1, "ratio": 1.78}
            for item in self._groups()
        ]}

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        extend = extend if isinstance(extend, dict) else {}
        text = str(tid).strip()
        current = _page_number(pg)

        keyword = re.match(r"^douyin/s/(.*)$", text)
        if keyword:
            return self._search_rooms(unquote(keyword.group(1) or ""), current)

        picked = str(extend.get("game") or extend.get("cateId") or "").strip()
        if picked:
            return self._path(picked, current)

        folder = re.match(r"^game_(.+)$", text)
        if folder:
            return self._path(folder.group(1), current)

        if any(item["id"] == text for item in self._groups()):
            tree = self._game_tree_quiet()
            if tree and tree.get("subs") and text == tree.get("id"):
                return self._game_page(current)
            return self._rooms(text, current)

        if re.fullmatch(r"\d+_\d+(_\d+_\d+)*", text):
            return self._rooms(text, current)

        # 入口默認值「douyin」進遊戲分區；其餘無法識別的分區直接報錯，
        # 不要靜默回遊戲頁（使用者點 A 分區卻看到 B 分區，比報錯更難排查）
        if text == "douyin":
            return self._game_page(current)
        raise RuntimeError("未知直播分區")

    def searchContent(self, key, quick, pg="1"):
        current = _page_number(pg)
        keyword = str(key).strip()
        card = {
            "vod_id": "douyin/s/" + quote(keyword, safe=""),
            "vod_name": "抖音：%s" % keyword,
            "vod_remarks": "搜尋主播或房間編號",
            "vod_tag": "folder",
            "style": {"type": "list"},
        }
        return _page([card], current, 1)

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        result = []
        for raw in ids:
            result.append(self._detail_vod(_room_id(raw)["id"]))
        return {"list": result}

    def playerContent(self, flag, id, vipFlags):
        room = _room_id(id)
        result = self._live_source(room["id"], room["extra"])
        result["position"] = 0
        result["danmaku"] = [{"name": "即時彈幕",
                              "url": self.danmakuUrl("douyin:%s" % room["id"])}]
        return result

    def proxy(self, params):
        params = params if isinstance(params, dict) else {}
        room = _room_id(params.get("live"))
        kind = params.get("kind")

        def source():
            url = self._stream_url(room["id"], kind)
            if re.search(r"\.m3u8(\?|$)", url, re.I):
                raise RuntimeError("此平台播放地址為 HLS 格式，無法代理")
            return url

        cache_key = "stream:douyin:" + room["id"]
        source()
        options = {"headers": _headers(), "timeout": 15000, "callTimeout": 0}

        def open_stream():
            reader = self.net.openStream(source(), options)
            if reader.code in (401, 403, 404):
                reader.close()
                self.net.clearCache(cache_key)
                self.net.clearCache("room:douyin:" + room["id"])
                reader = self.net.openStream(source(), options)
            if reader.code != 200:
                reader.close()
                raise RuntimeError("直播串流 HTTP %s" % reader.code)
            return reader

        response = self.net.stream(_mount_flv(self, open_stream, 10000))
        return [200, "video/x-flv", response["stream"],
                {"Cache-Control": "no-store", "Accept-Ranges": "none"}]

    # ==================== 分類 ====================

    def _log(self, message):
        try:
            self.log(message)
        except Exception:
            pass

    def _groups(self):
        def load():
            tree = self._category_tree()
            # 抓不到就不要快取：否則一次風控會把「只剩遊戲」的結果鎖死一整天
            if not tree:
                raise RuntimeError("抖音分類暫無資料")
            return tree

        try:
            items = self.net.cached("groups:douyin_v3", {"ttl": 86400000, "persist": True}, load)
            if isinstance(items, list) and items:
                return items
        except Exception:
            self._log("抖音分類暫時無法取得，改用內建分類")
        return GROUPS

    def _rsc(self, cid):
        url = CATEGORY.replace("{cid}", cid)
        for _ in range(2):
            for agent in (UA, UA_PHONE):
                response = self.net.req(url, {"headers": {"User-Agent": agent, "Referer": DOUYIN + "/"}})
                if response.get("error") or response.get("code") != 200:
                    continue
                content = str(response.get("content") or "")
                block = _rsc_push(content)
                if not block:
                    continue
                try:
                    return _rsc_value(block)
                except Exception:
                    continue
        return None

    def _category_tree(self):
        data = self._rsc("4_103")
        items = []
        for item in (data.get("categoryData") if isinstance(data, dict) else None) or []:
            partition = (item or {}).get("partition") or {}
            ident = str(partition.get("id_str") or "")
            kind = str(partition.get("type") or "")
            name = partition.get("title") or ""
            if ident and kind and name:
                items.append({"id": "%s_%s" % (kind, ident), "name": _label(name)})
        return items

    def _game_tree(self):
        now = time.time()
        if self._tree and now - self._tree["stamp"] < 600:
            return self._tree["data"]
        data = self._rsc("4_103")
        nodes = (data.get("categoryData") if isinstance(data, dict) else None) or []
        node = None
        for item in nodes:
            if str(((item or {}).get("partition") or {}).get("id_str") or "") == "103":
                node = item
                break
        kind = str(((node or {}).get("partition") or {}).get("type") or "")
        if not node or not kind:
            return None
        subs = []
        for sub in node.get("sub_partition") or []:
            partition = (sub or {}).get("partition") or {}
            ident = str(partition.get("id_str") or "")
            sub_kind = str(partition.get("type") or "")
            name = partition.get("title") or ""
            if not ident or not sub_kind or not name:
                continue
            children = []
            for game in sub.get("sub_partition") or []:
                inner = (game or {}).get("partition") or {}
                gid = str(inner.get("id_str") or "")
                gtype = str(inner.get("type") or "")
                gname = inner.get("title") or ""
                if gid and gtype and gname:
                    children.append({"id": gid, "type": gtype, "name": gname})
            subs.append({"id": ident, "type": sub_kind, "name": name, "subs": children})
        tree = {"id": "%s_103" % kind, "name": "遊戲", "subs": subs}
        self._tree = {"stamp": now, "data": tree}
        return tree

    def _game_tree_quiet(self):
        try:
            return self._game_tree()
        except Exception:
            return None

    def _partitions(self, partition, kind, offset):
        options = {
            "params": {
                "aid": "6383", "app_name": "douyin_web", "live_id": "1",
                "device_platform": "web", "count": str(LIMIT), "offset": str(offset),
                "partition": str(partition), "partition_type": str(kind), "req_from": "2",
            },
            "headers": {"User-Agent": UA_PHONE, "Accept": "application/json, text/plain, */*",
                        "Referer": DOUYIN + "/"},
        }
        try:
            result = self.net.json(PARTITION, options)
        except Exception:
            return None
        if not isinstance(result, dict) or _int(result.get("status_code"), -1) != 0:
            return None
        rooms = (result.get("data") or {}).get("data")
        if not isinstance(rooms, list):
            return None
        return [card for card in (_room_item(item) for item in rooms) if card]

    def _category_rooms(self, cid):
        data = self._rsc(cid)
        rooms = (data.get("roomsData") or {}) if isinstance(data, dict) else {}
        items = rooms.get("data") if isinstance(rooms, dict) else None
        return [card for card in (_room_item(item) for item in (items or [])) if card]

    def _game_folders(self, tree):
        folders = []
        if any(item["subs"] for item in tree["subs"]):
            for sub in tree["subs"]:
                folders.append({"id": "%s@@%s_%s" % (tree["id"], sub["type"], sub["id"]),
                                "name": _label(sub["name"]),
                                "pic": ICONS.get(sub["name"], ""), "remarks": "遊戲題材"})
        else:
            for game in tree["subs"]:
                folders.append({"id": "%s@@%s_%s" % (tree["id"], game["type"], game["id"]),
                                "name": _label(game["name"]),
                                "pic": ICONS.get(game["name"], ""), "remarks": "熱門遊戲"})
            for theme in THEMES:
                folders.append({"id": "%s@@1_%s" % (tree["id"], theme["id"]),
                                "name": theme["name"],
                                "pic": ICONS.get(theme["icon"], ""), "remarks": "遊戲題材"})
        return folders

    def _game_page(self, current):
        tree = self._game_tree()
        if not tree or not tree["subs"]:
            return self._rooms((tree or {}).get("id") or GROUPS[0]["id"], current)
        return self._folders(self._game_folders(tree), current)

    def _click(self, parts, current):
        if not parts:
            raise RuntimeError("抖音分類路徑無效")
        if len(parts) == 1:
            return self._game_page(current)
        if len(parts) == 3:
            return self._rooms("%s_%s_%s" % (parts[0], parts[1], parts[2]), current)
        pieces = str(parts[1]).split("_")
        kind = pieces[0] if pieces else ""
        ident = pieces[1] if len(pieces) > 1 else ""
        tree = self._game_tree()
        node = None
        for item in (tree or {}).get("subs") or []:
            if item["type"] == kind and item["id"] == ident and item["subs"]:
                node = item
                break
        if not node:
            return self._rooms("%s_%s" % (parts[0], parts[1]), current)
        games = sorted(node["subs"], key=lambda game: _pin(game["name"]))
        folders = [{"id": "%s@@%s@@%s_%s" % (parts[0], parts[1], game["type"], game["id"]),
                    "name": _label(game["name"]), "pic": ICONS.get(game["name"], ""),
                    "remarks": "遊戲"} for game in games]
        return self._folders(folders, current)

    def _path(self, path, current):
        ident = str(path).strip()
        if re.fullmatch(r"\d+_\d+", ident):
            if any(item["id"] == ident for item in self._groups()):
                tree = self._game_tree_quiet()
                if tree and tree.get("subs") and ident == tree.get("id"):
                    return self._game_page(current)
                return self._rooms(ident, current)
        return self._click([part for part in ident.split("@@") if part], current)

    def _rooms(self, cid, current):
        if not re.fullmatch(r"\d+_\d+(_\d+_\d+)*", str(cid)):
            raise RuntimeError("抖音分類編號格式錯誤")
        partition, kind = _partition_of(cid)
        rooms = self._partitions(partition, kind, (current - 1) * LIMIT) if partition else None
        if rooms is None:
            if current > 1:
                return {"list": [], "page": current, "pagecount": current, "limit": LIMIT, "total": 0}
            rooms = self._category_rooms(cid)
            if not rooms:
                raise RuntimeError("抖音分類沒有取得直播間")
        cards = [card for card in (_douyin_card(card) for card in rooms) if card]
        return {"list": cards, "page": current,
                "pagecount": current + 1 if len(cards) >= LIMIT else max(1, current),
                "limit": LIMIT, "total": len(cards)}

    def _folders(self, items, current):
        cards = [{"vod_id": "game_" + item["id"], "vod_name": item["name"],
                  "vod_pic": _image(item.get("pic") or COVER),
                  "vod_remarks": item.get("remarks") or "", "vod_tag": "folder",
                  "style": dict(FOLDER)} for item in items]
        return {"list": cards, "page": current, "pagecount": 1,
                "limit": len(items) or 20, "total": len(items)}

    def _search_rooms(self, keyword, current):
        empty = {"list": [], "page": current, "pagecount": 1, "limit": 1, "total": 0}
        if current != 1:
            return empty
        if not re.search(r"\d{9,20}", keyword):
            # 抖音沒有關鍵詞搜索接口：只認抖音號 / 房間號，明確告知比回空列表好排查
            raise RuntimeError("抖音僅支持按抖音號或房間號搜尋（純數字）")
        # 抖音只能按（抖音號 / 房間號）查，查不到時直接把原因交給宿主顯示，
        # 不要吞成空列表——否則使用者分不清「號碼錯了」和「主播沒開播」
        info = self._room(keyword)
        ident = info.get("web_rid") or info.get("room_id")
        card = _douyin_card({"room_id": ident, "web_rid": info.get("web_rid"),
                             "title": info.get("title"), "nickname": info.get("nickname"),
                             "cover": info.get("cover"), "users": 0, "game": info.get("game")})
        return {"list": [card] if card else [], "page": 1, "pagecount": 1,
                "limit": 1, "total": 1 if card else 0}

    # ==================== 房間 ====================

    def _room(self, raw):
        return self.net.cached("stream:douyin:" + str(raw), {"ttl": 5000, "stale": False},
                               lambda: self._fetch_room(raw))

    def _amemv(self, room_id):
        try:
            result = self.net.json(AMEMV.replace("{rid}", room_id), {"headers": {"User-Agent": UA_PHONE}})
        except Exception:
            return None
        if not isinstance(result, dict) or _int(result.get("status_code"), -1) != 0:
            return None
        room = (result.get("data") or {}).get("room")
        if not isinstance(room, dict) or not room.get("stream_url"):
            return None
        return {"stream": room["stream_url"], "room": room}

    def _enter_room(self, web_rid):
        options = {"headers": {"User-Agent": UA,
                               "Cookie": "s_v_web_id=verify_%d" % int(time.time() * 1000),
                               "Referer": DOUYIN + "/"}}
        try:
            result = self.net.json(ENTER.replace("{rid}", web_rid), options)
        except Exception:
            return None
        if not isinstance(result, dict) or _int(result.get("status_code"), -1) != 0:
            return None
        data = result.get("data")
        if not isinstance(data, dict) or not data.get("stream_url"):
            return None
        room = data.get("room")
        return {"stream": data["stream_url"], "room": room if isinstance(room, dict) else data}

    def _fetch_room(self, raw):
        target = _input(raw)
        if not target:
            raise RuntimeError("抖音房間編號格式錯誤")
        if target["room_id"]:
            found = self._amemv(target["room_id"])
            if found:
                info = _stream_info(found["stream"], found["room"], target["room_id"], "", "amemv")
                if info:
                    return info
            first = self._web_room(target["room_id"])
            if first and first.get("web_rid") and str(first["web_rid"]) != str(target["room_id"]):
                second = self._web_room(first["web_rid"])
                if second:
                    return second
            if first:
                return first
            raise RuntimeError("抖音目前未開播或直播間不存在")
        info = self._web_room(target["web_rid"])
        if info:
            return info
        found = self._enter_room(target["web_rid"])
        if found:
            built = _stream_info(found["stream"], found["room"], "", target["web_rid"], "enter")
            if built:
                return built
        raise RuntimeError("抖音目前未開播或直播間不存在")

    def _web_room(self, web_rid):
        options = {"headers": {"User-Agent": UA,
                               "Cookie": "s_v_web_id=verify_%d" % int(time.time() * 1000),
                               "Referer": DOUYIN + "/", "Accept-Language": "zh-CN,zh;q=0.9"}}
        response = self.net.req(DOUYIN + "/" + str(web_rid), options)
        if response.get("error") or response.get("code") != 200:
            return None
        content = str(response.get("content") or "")
        out = {"room_id": "", "web_rid": web_rid, "title": "", "nickname": "", "cover": "",
               "hls": "", "flv": "", "flvs": [], "game": "", "signature": "",
               "user_count_str": "", "total_user_str": "", "source": "web", "room": None}

        found = re.search(r'\\"roomId\\":\\"(\d+)\\"', content) \
            or re.search(r'\\"id_str\\":\\"(\d{15,20})\\"', content)
        if found:
            out["room_id"] = found.group(1)

        start = content.find('\\"roomStore\\":{\\"roomInfo\\":{\\"room\\":{')
        if start > 0:
            block = content[start:start + 2500]
            head = re.search(r'\\"status\\":(\d+),\\"status_str\\":\\"\d+\\",\\"title\\":'
                             r'\\"((?:[^"\\]|\\u[0-9a-fA-F]{4})*)\\"', block)
            if head:
                out["title"] = _deescape(head.group(2))
            cover = re.search(r'\\"cover\\":\{\\"url_list\\":\[\s*'
                              r'\\"((?:[^"\\]|\\u[0-9a-fA-F]{4})*)\\"', block)
            if cover:
                out["cover"] = _deescape(cover.group(1))

        anchor = re.search(r'\\"anchor\\":\{[^\n]*?\\"nickname\\":'
                           r'\\"((?:[^"\\]|\\u[0-9a-fA-F]{4})*)\\"', content)
        if anchor:
            out["nickname"] = _deescape(anchor.group(1))

        for match in re.finditer(r'\\"game_tag_name\\":\\"((?:[^"\\]|\\u[0-9a-fA-F]{4})*)\\"', content):
            name = _deescape(match.group(1))
            if name:
                out["game"] = name
                break

        users = re.search(r'\\"user_count_str\\":\\"((?:[^"\\]|\\u[0-9a-fA-F]{4})*)\\"', content)
        if users:
            out["user_count_str"] = _deescape(users.group(1))
        total = re.search(r'\\"total_user_str\\":\\"((?:[^"\\]|\\u[0-9a-fA-F]{4})*)\\"', content)
        if total:
            out["total_user_str"] = _deescape(total.group(1))

        owner = content.find('\\"owner\\":{')
        if owner > 0:
            signature = re.search(r'\\"signature\\":\\"((?:[^"\\]|\\u[0-9a-fA-F]{4})*)\\"',
                                  content[owner:owner + 4000])
            if signature:
                out["signature"] = _deescape(signature.group(1))

        stream = content.find('\\"stream_url\\":{')
        if stream > 0:
            block = content[stream:stream + 6000]
            # 先反轉義，再從 flv_pull_url 這個 map 裡逐個檔位取
            plain = _deescape(block)
            pull = re.search(r'"flv_pull_url":\{([^}]*)\}', plain)
            if pull:
                for key in TIER_KEYS:
                    hit = re.search('"%s":"(https?:[^"]+)"' % key, pull.group(1))
                    if hit:
                        out["flvs"].append({"key": key, "url": hit.group(1)})
            if out["flvs"]:
                out["flv"] = out["flvs"][0]["url"]
            hls = re.search(r'\\"hls_pull_url_map\\":\{[^\n]*?\\"FULL_HD1\\":'
                            r'\\"((?:[^"\\]|\\u[0-9a-fA-F]{4})*)\\"', block)
            if hls:
                out["hls"] = _deescape(hls.group(1))
            if not out["hls"]:
                fallback = re.search(r'\\"hls_pull_url\\":\\"((?:[^"\\]|\\u[0-9a-fA-F]{4})*)\\"', block)
                if fallback:
                    out["hls"] = _deescape(fallback.group(1))

        if not out["hls"]:
            fallback = re.search(r'\\"hls_pull_url\\":\\"(https?:\/\/[^"\\]+)', content)
            if fallback:
                out["hls"] = _deescape(fallback.group(1))
        if not out["flv"]:
            fallback = re.search(r'\\"flv_pull_url\\":\{[^}]*?\\"FULL_HD1\\":\\"(https?:\/\/[^"\\]+)',
                                 content)
            if fallback:
                out["flv"] = _deescape(fallback.group(1))
        if not out["hls"] and not out["flv"]:
            return None
        return out

    def _detail_vod(self, ident):
        info = self._room(ident)
        room = info.get("room")
        if not room and info.get("room_id"):
            found = self._amemv(info["room_id"])
            room = (found or {}).get("room")
        room = room if isinstance(room, dict) else {}
        owner = room.get("owner") if isinstance(room.get("owner"), dict) else {}
        follow = owner.get("follow_info") if isinstance(owner.get("follow_info"), dict) else {}

        content = ["狀態：直播中"]
        start = _int(room.get("start_time"), 0)
        if start > 0:
            duration = _duration_text(int(time.time()) - start)
            if duration:
                content.append("已開播：" + duration)
        if info.get("game"):
            content.append("分區：" + info["game"])
        if info.get("user_count_str") and info["user_count_str"] != "0":
            content.append("在線觀眾：" + info["user_count_str"])
        if info.get("total_user_str") and info["total_user_str"] != "0":
            content.append("累計進入：" + info["total_user_str"])
        if room.get("like_count"):
            content.append("本場點贊：" + _count(room["like_count"]))
        actor = info.get("nickname") or str(owner.get("nickname") or "")
        account = str(owner.get("display_id") or "")
        content.append("主播：" + actor + ("（抖音號：%s）" % account if account else ""))
        if follow.get("follower_count_str"):
            content.append("粉絲：" + str(follow["follower_count_str"]))
        if owner.get("city"):
            content.append("所在地：" + str(owner["city"]))
        about = "\n".join([line.strip() for line in re.split(r"\r?\n",
                           str(info.get("signature") or owner.get("signature") or ""))
                           if line.strip()][:3])[:120]
        if about:
            content.append("主播簡介：" + about)

        title = str(info.get("title") or "").strip()
        name = info.get("name") or (title if title and not re.fullmatch(r"\d+", title) else "") \
            or actor or info.get("web_rid") or info.get("room_id")
        remark = "人氣 " + info["user_count_str"] \
            if info.get("user_count_str") and info["user_count_str"] != "0" else "直播中"
        vod = _card("douyin", info.get("web_rid") or info.get("room_id"), name,
                    info.get("cover") or COVER, remark)
        if not vod:
            raise RuntimeError("直播列表缺少房間編號或名稱")
        vod["vod_actor"] = actor
        vod["type_name"] = info.get("game") or ""
        vod["vod_content"] = "\n".join(content)

        # 僅保留 FLV 線路：HLS 為第三方 CDN 帶簽名直鏈，會快速過期且無法代理，棄用
        tiers = info.get("flvs") if isinstance(info.get("flvs"), list) else []
        keys = [tier["key"] for tier in tiers]
        lines = ["%s$%s@%s" % (tier["name"], vod["vod_id"], tier["extra"])
                 for tier in TIERS if tier["key"] in keys]
        if not lines and info.get("flv"):
            lines.append("FLV直播$%s@flv" % vod["vod_id"])
        vod["vod_play_from"] = NAME
        vod["vod_play_url"] = "#".join(lines) or ("直播$" + vod["vod_id"])
        return vod

    def _stream_url(self, ident, value):
        info = self._room(ident)
        url = _tier_url(info, value)
        if not url:
            raise RuntimeError("抖音目前沒有可播放的直播")
        return url

    def _live_source(self, ident, value):
        self._stream_url(ident, value)
        return {"parse": 0,
                "url": self.proxyUrl({"live": "douyin:" + ident, "kind": value or "flv"}),
                "header": _headers(), "format": "video/x-flv"}

    # ==================== 彈幕（PushFrame 推播） ====================

    def _random_text(self, length):
        chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
        return "".join(random.choice(chars) for _ in range(length))

    def _random_digits(self, length):
        return "".join(str(random.randint(0, 9)) for _ in range(length))

    def _ttwid(self, web_rid):
        if TTWID:
            return TTWID

        def load():
            problems = []
            jar = _cookie_value(self.net.getCookie(DOUYIN + "/"), "ttwid")
            if jar:
                return jar
            for url in (DOUYIN + "/" + (web_rid or ""), "https://www.douyin.com/"):
                try:
                    # cookie: True → 讓宿主把 Set-Cookie 寫進 Cookie 罐，再讀回來
                    self.net.req(url, {"cookie": True, "headers": {
                        "User-Agent": UA_PHONE, "Accept": "text/html,application/xhtml+xml",
                        "Referer": DOUYIN + "/", "Accept-Language": "zh-CN,zh;q=0.9"}})
                    hit = _cookie_value(self.net.getCookie(DOUYIN + "/"), "ttwid")
                    if hit:
                        return hit
                    problems.append(url + " 未回傳 ttwid")
                except Exception as error:
                    problems.append("%s：%s" % (url, error))
            try:
                # 註冊接口：cookie: True 讓宿主收下 Set-Cookie，再從 Cookie 罐讀 ttwid
                self.net.req("https://ttwid.bytedance.com/ttwid/union/register/", {
                    "method": "POST", "cookie": True,
                    "headers": {"User-Agent": UA, "Content-Type": "application/json",
                                "Origin": DOUYIN, "Referer": DOUYIN + "/"},
                    "body": json.dumps({"region": "cn", "aid": 6383, "needFid": False,
                                        "service": "live.douyin.com", "mplatform": "pc",
                                        "union": True}),
                })
                hit = _cookie_value(self.net.getCookie(DOUYIN + "/"), "ttwid")
                if hit:
                    return hit
                problems.append("註冊接口未回傳 ttwid")
            except Exception as error:
                problems.append("註冊接口：%s" % error)
            raise RuntimeError("抖音 ttwid 取得失敗（%s）：請在檔案頂部 TTWID 填入瀏覽器取得的 ttwid"
                               % "；".join(problems))

        return self.net.cached("ttwid:douyin", {"ttl": 600000, "stale": False}, load)

    def _signature(self, params):
        seed = hashlib.md5(params.encode("utf-8")).hexdigest()
        value = self.js.eval(JS_SIGN, {"globals": {"seed": seed}, "timeout": 5000})
        if not value:
            raise RuntimeError("抖音彈幕簽名計算失敗")
        return str(value)

    def _room_id_of(self, web_rid):
        def load():
            options = {"headers": {"User-Agent": UA,
                                   "Cookie": "s_v_web_id=verify_%d" % int(time.time() * 1000),
                                   "Referer": DOUYIN + "/", "Accept-Language": "zh-CN,zh;q=0.9"}}
            response = self.net.req(DOUYIN + "/" + str(web_rid), options)
            if response.get("error") or response.get("code") != 200:
                raise RuntimeError("抖音直播頁載入失敗")
            content = str(response.get("content") or "")
            found = re.search(r'\\"roomId\\":\\"(\d+)\\"', content) \
                or re.search(r'\\"id_str\\":\\"(\d{15,20})\\"', content)
            if not found:
                raise RuntimeError("抖音直播間編號解析失敗")
            return found.group(1)

        return self.net.cached("roomid:douyin:%s" % web_rid, {"ttl": 5000, "stale": False}, load)

    def _ws_url(self, room_id, web_rid):
        ttwid = self._ttwid(web_rid or "")
        ms_token = self._random_text(107)
        did = self._random_digits(19)
        now = int(time.time() * 1000)
        internal = ("internal_src:dim|wss_push_room_id:%s|wss_push_did:%s|first_req_ms:%d"
                    "|fetch_time:%d|seq:1|wss_info:0-%d-0-0|wrds_v:7392094459690748497"
                    % (room_id, did, now, now, now))
        query = "&".join([
            "app_name=douyin_web", "version_code=180800",
            "webcast_sdk_version=1.0.14-beta.0", "update_version_code=1.0.14-beta.0",
            "compress=gzip", "device_platform=web", "cookie_enabled=true",
            "screen_width=1536", "screen_height=864", "browser_language=zh-CN",
            "browser_platform=Win32", "browser_name=Mozilla",
            # 值裡有空格與括號：瀏覽器建立 WebSocket 時會自動編碼，這裡必須照做，
            # 否則請求行含空白，CDN 直接回 400（實測）
            "browser_version=" + quote(BROWSER_VERSION, safe="()"),
            "browser_online=true", "tz_name=Asia/Shanghai",
            "cursor=d-1_u-1_fh-7392091211001140287_t-%d_r-1" % now,
            "internal_ext=" + quote(internal, safe=""),
            "host=" + DOUYIN, "aid=6383", "live_id=1", "did_rule=3",
            "endpoint=live_pc", "support_wrds=1", "user_unique_id=" + did,
            "im_path=/webcast/im/fetch/", "identity=audience",
            "need_persist_msg_count=15", "insert_task_id=", "live_reason=",
            "room_id=" + room_id, "heartbeatDuration=0",
        ])
        sign_params = ",".join([
            "live_id=1", "aid=6383", "version_code=180800",
            "webcast_sdk_version=1.0.14-beta.0", "room_id=" + room_id, "sub_room_id=",
            "sub_channel_id=", "did_rule=3", "user_unique_id=" + did,
            "device_platform=web", "device_type=", "ac=", "identity=audience",
        ])
        signature = self._signature(sign_params)
        url = ("wss://" + WS_HOST + "/webcast/im/push/v2/?" + query
               + "&signature=" + quote(signature, safe=""))
        return {"url": url, "cookie": "ttwid=%s; msToken=%s" % (ttwid, ms_token)}

    def danmaku(self, id, emit):
        # 宿主切源/重連會再次呼叫 danmaku：先停掉上一條連線，避免兩條同時上屏
        with self._lock:
            self._seq += 1
            seq = self._seq
            previous = self._active_stop
            self._active_stop = None
        if previous:
            try:
                previous()
            except Exception:
                pass

        room = _room_id(id)
        web_rid = room["id"]
        try:
            live_id = self._room_id_of(web_rid)
            socket = self._ws_url(str(live_id), web_rid)
            if not socket or not socket.get("url"):
                raise RuntimeError("彈幕握手未拿到可用地址（可能未取得 ttwid/msToken）")
        except Exception as error:
            # 握手失敗明確冒泡，方便在播放器看到具體原因（而非靜默無彈幕）
            _emit_safe(emit, {"state": "error", "msg": "抖音彈幕握手失敗：%s" % error})
            return lambda: None

        # 這輪啟動途中已被後一次 danmaku 取代：直接結束，不再建立連線
        with self._lock:
            if seq != self._seq:
                return lambda: None

        stop = self._subscribe({"webRid": web_rid, "roomId": str(live_id),
                                "cookie": socket["cookie"], "wsUrl": socket["url"]}, emit)
        with self._lock:
            if seq != self._seq:
                try:
                    stop()
                except Exception:
                    pass
                return lambda: None
            self._active_stop = stop
        return stop

    def _subscribe(self, room, emit):
        ctx = {"stopped": False, "ready": False, "informed": False,
               "activity": time.time(), "socket": None, "watchdog": None, "fallback": None,
               "delay": 3.0, "stamp": 0.0}
        lock = threading.RLock()
        options = {"timeout": 10000, "idle": 90000, "reconnect": True,
                   "headers": {"Origin": DOUYIN, "Referer": DOUYIN + "/" + (room.get("webRid") or ""),
                               "User-Agent": UA, "Cookie": room.get("cookie") or ""}}

        def stop():
            with lock:
                if ctx["stopped"]:
                    return
                ctx["stopped"] = True
                watchdog, fallback, socket = ctx["watchdog"], ctx["fallback"], ctx["socket"]
                ctx["watchdog"] = ctx["fallback"] = ctx["socket"] = None
            _cancel(watchdog)
            _cancel(fallback)
            if socket:
                try:
                    socket.cancel()
                except Exception:
                    pass

        def mark_ready():
            if ctx["ready"] or ctx["stopped"]:
                return
            ctx["ready"] = True
            _emit_safe(emit, {"state": "ready"})

        def fail(error):
            if ctx["stopped"]:
                return
            stop()
            message = str(error)[:512]
            _emit_safe(emit, {"state": "error", "msg": message})
            # 部分宿主不顯示 state:error，補一條紅字，避免出現「沒彈幕也沒提示」
            if not ctx["informed"]:
                ctx["informed"] = True
                _emit_safe(emit, {"text": "[抖音] 彈幕中斷：" + message[:120],
                                  "color": 0xFF5555, "size": 20, "type": 1, "nick": "抖音"})

        def tick():
            try:
                if ctx["stopped"]:
                    return
                idle = time.time() - ctx["activity"]
                if not ctx["ready"] and idle > 15:
                    reconnect()
                elif ctx["ready"] and idle > 150:
                    reconnect()
            finally:
                if not ctx["stopped"]:
                    arm()

        def arm():
            with lock:
                if ctx["watchdog"]:
                    ctx["watchdog"].cancel()
                if ctx["stopped"]:
                    return
                timer = threading.Timer(5.0, tick)
                timer.daemon = True
                ctx["watchdog"] = timer
            timer.start()

        def do_reconnect():
            with lock:
                ctx["fallback"] = None
                # 宿主已自行重連（activity 前進）或已就緒時不要再開第二條
                if ctx["stopped"] or ctx["ready"] or ctx["activity"] > ctx["stamp"]:
                    return
                old = ctx["socket"]
                ctx["socket"] = None
                ctx["delay"] = min(10.0, ctx["delay"] * 1.6)
            if old:
                try:
                    old.cancel()
                except Exception:
                    pass
            connect()

        def reconnect():
            # 自助重連兜底：宿主已開 reconnect，避免兩條連線搶同一房間
            if ctx["stopped"]:
                return
            _cancel(ctx["fallback"])
            ctx["stamp"] = ctx["activity"]
            timer = threading.Timer(ctx["delay"], do_reconnect)
            timer.daemon = True
            with lock:
                ctx["fallback"] = timer
            timer.start()

        def open_(connection):
            ctx["ready"] = False
            ctx["activity"] = time.time()
            ctx["delay"] = 3.0
            # 推播通道由伺服器主動推送，連線建立即視為訂閱就緒
            mark_ready()
            arm()

        def connect():
            with lock:
                old = ctx["socket"]
                ctx["socket"] = None
            if old:
                try:
                    old.cancel()
                except Exception:
                    pass
            connection = self.net.connect(room["wsUrl"], options,
                                          lambda conn, event: dispatch(conn, event))
            with lock:
                ctx["socket"] = connection
                ctx["activity"] = time.time()
                ctx["ready"] = False
            arm()

        def dispatch(connection, event):
            if ctx["stopped"]:
                return
            kind = event.get("type")
            try:
                if kind == "open":
                    open_(connection)
                elif kind == "message" and event.get("binary"):
                    ctx["activity"] = time.time()
                    for item in _douyin_messages(event.get("content"), mark_ready):
                        if ctx["stopped"]:
                            return
                        _emit_safe(emit, item)
                    # 只要收到任何封包就確認通道暢通，冷清房間亦回報就緒
                    mark_ready()
                elif kind == "retry":
                    ctx["ready"] = False
                    _emit_safe(emit, {"state": "retrying", "msg": "彈幕連線中斷，等待恢復"})
                elif kind in ("error", "close"):
                    ctx["ready"] = False
                    _emit_safe(emit, {"state": "retrying", "msg": "彈幕連線中斷，等待恢復"})
                    reconnect()
            except Exception as error:
                fail(error)

        ctx["activity"] = time.time()
        connect()
        return stop

    def destroy(self):
        with self._lock:
            stop = self._active_stop
            self._active_stop = None
        if stop:
            try:
                stop()
            except Exception:
                pass


# ==================== 模組級工具 ====================

def _options(extend):
    if isinstance(extend, dict):
        return extend
    if extend:
        try:
            value = json.loads(extend)
        except Exception:
            raise ValueError("Site.ext 必須是 JSON 物件")
        if not isinstance(value, dict):
            raise ValueError("Site.ext 必須是 JSON 物件")
        return value
    return {}


def _page(items, current, limit, total=None):
    size = limit or 20
    amount = 0 if total is None else total
    return {
        "list": items,
        "page": current,
        "pagecount": 1 if total is None else max(1, -(-amount // size)),
        "limit": size,
        "total": len(items) if total is None else amount,
    }


def _page_number(value):
    text = str(value).strip()
    if not re.fullmatch(r"-?\d+", text):
        raise RuntimeError("頁碼格式錯誤")
    return max(1, int(text))


def _int(value, default=0):
    try:
        return int(float(value))
    except Exception:
        return default


def _room_id(value):
    raw = "" if value is None else str(value).strip()
    try:
        plain = unquote(raw)
    except Exception:
        plain = raw
    live = re.search(r"[?&]live=([^&]*)", plain)
    text = live.group(1) if live else plain
    cut = text.find("?")
    if cut >= 0:
        text = text[:cut]
    at = text.rfind("@")
    head = text[:at] if at > 0 else text
    tail = text[at + 1:] if at > 0 else ""
    match = re.fullmatch(r"douyin:([A-Za-z0-9_-]{1,64})", head)
    if not match:
        # 兜底：整串裡任意位置出現 douyin:xxx 都認（?id=、路徑、danmaku:// 之類）
        match = re.search(r"douyin:([A-Za-z0-9_-]{1,64})", plain)
        tail = ""
    if not match:
        raise RuntimeError("直播房間編號格式錯誤")
    if tail and not re.fullmatch(r"(hls|flv|flv-full|flv-hd|flv-sd1|flv-sd2|\d{1,2})", tail):
        raise RuntimeError("直播播放線路格式錯誤")
    return {"platform": "douyin", "id": match.group(1), "extra": tail}


def _input(raw):
    text = "" if raw is None else str(raw).strip()
    if not text:
        return None
    found = re.search(r"\d{9,20}", text)
    digits = found.group(0) if found else text
    if not re.fullmatch(r"\d+", digits):
        return None
    if len(digits) == 19:
        return {"room_id": digits, "web_rid": ""}
    if 9 <= len(digits) <= 13:
        return {"room_id": "", "web_rid": digits}
    return None


def _partition_of(cid):
    parts = str(cid).split("_")
    if len(parts) >= 2:
        kind = parts[-2]
        ident = parts[-1]
        if re.fullmatch(r"\d+", kind) and re.fullmatch(r"\d+", ident):
            return ident, kind
    return None, None


def _headers():
    return {"User-Agent": UA, "Referer": DOUYIN + "/", "Origin": DOUYIN}


def _image(value):
    if not isinstance(value, str):
        return ""
    return "https://" + value[2:] if value.startswith("//") else value


def _card(platform, ident, name, pic, remark):
    if not ident or not name:
        return None
    return {"vod_id": "%s:%s" % (platform, ident), "vod_name": str(name),
            "vod_pic": _image(pic), "vod_remarks": remark or "", "style": dict(STYLE)}


def _count(value):
    try:
        number = float(value)
    except Exception:
        return ""
    if number <= 0:
        return ""
    if number >= 100000000:
        return "%.1f億" % (number / 100000000)
    if number >= 10000:
        return "%.1f萬" % (number / 10000)
    return str(int(number))


def _duration_text(value):
    try:
        seconds = int(float(value))
    except Exception:
        return ""
    if seconds <= 0:
        return ""
    hours = seconds // 3600
    minutes = seconds % 3600 // 60
    if hours > 0:
        return "%d小時%d分鐘" % (hours, minutes)
    if minutes > 0:
        return "%d分鐘" % minutes
    return "%d秒" % seconds


def _label(value):
    text = str(value if value is not None else "").strip()
    if not text:
        return ""
    if text in LABELS:
        return LABELS[text]
    head = re.split(r"\s+", text)[0]
    return text.replace(head, LABELS[head], 1) if head in LABELS else text


def _pin(name):
    return 0 if name in ("拳皇97", "拳皇98") else 1


def _deescape(value):
    text = str(value)
    text = text.replace('\\\\"', '"').replace('\\"', '"')
    text = text.replace("\\u0026", "&").replace("\\/", "/")
    text = text.replace("\\u003d", "=").replace("\\u003F", "?")
    text = text.replace("\\u003A", ":").replace("\\u005C", "\\")
    return text


def _cookie_value(jar, name):
    found = re.search(r"(?:^|[;,\s])%s=([^;,]+)" % re.escape(name), str(jar or ""), re.I)
    return found.group(1) if found else ""


def _emit_safe(emit, item):
    try:
        emit(item)
    except Exception:
        pass


def _cancel(handle):
    if handle is None:
        return
    try:
        handle.cancel()
    except Exception:
        pass


def _cover_value(value):
    if isinstance(value, list):
        return value[0] if value and isinstance(value[0], str) else ""
    if isinstance(value, dict):
        items = value.get("url_list")
        return items[0] if isinstance(items, list) and items and isinstance(items[0], str) else ""
    return str(value) if value else ""


def _url_value(value):
    if not isinstance(value, str) or not value:
        return ""
    text = "https:" + value if value.startswith("//") else value
    return text.replace("http://", "https://")


def _room_item(item):
    if not isinstance(item, dict):
        return None
    room = item.get("room") if isinstance(item.get("room"), dict) else {}
    ident = str(room.get("id_str") or "")
    if not ident:
        return None
    owner = room.get("owner") if isinstance(room.get("owner"), dict) else {}
    return {
        "room_id": ident,
        "web_rid": str(item.get("web_rid") or ""),
        "title": str(room.get("title") or ""),
        "nickname": str(owner.get("nickname") or ""),
        "cover": _cover_value(room.get("cover") or item.get("cover")),
        "users": room.get("user_count") or 0,
        "game": str(item.get("game_tag") or ""),
    }


def _douyin_card(item):
    if not isinstance(item, dict):
        return None
    ident = str(item.get("web_rid") or item.get("room_id") or "")
    if not ident:
        return None
    title = str(item.get("title") or "").strip()
    nickname = str(item.get("nickname") or "").strip()
    name = title or nickname or str(item.get("room_id") or "")
    if nickname and nickname not in name:
        name = "%s - %s" % (nickname, title) if title else nickname
    users = item.get("users") or 0
    remark = str(item.get("game") or "").strip() or \
        ("人氣 " + (_count(users) or str(users)) if users else "直播中")
    return {"vod_id": "douyin:%s" % ident, "vod_name": name,
            "vod_pic": _image(_url_value(item.get("cover")) or COVER),
            "vod_remarks": remark, "style": dict(STYLE)}


def _tier_url(info, value):
    items = info.get("flvs") if isinstance(info.get("flvs"), list) else []
    want = next((tier for tier in TIERS if tier["extra"] == value), None)
    if want:
        hit = next((item for item in items if item["key"] == want["key"]), None)
        if hit:
            return hit["url"]
    # 沒指定檔位（舊收藏、或只帶 @flv）時，按 720p30 → 720p → 原畫 → 540p 取第一個可用
    for key in ("HD1", "SD2", "FULL_HD1", "SD1"):
        hit = next((item for item in items if item["key"] == key), None)
        if hit:
            return hit["url"]
    return info.get("flv") or ""


def _stream_info(stream, room, room_id, web_rid, source):
    if not isinstance(stream, dict):
        return None
    hls_map = stream.get("hls_pull_url_map") if isinstance(stream.get("hls_pull_url_map"), dict) else {}
    flv_map = stream.get("flv_pull_url_map") if isinstance(stream.get("flv_pull_url_map"), dict) else {}
    hls = _url_value(stream.get("hls_pull_url")) or _url_value(
        hls_map.get("FULL_HD1") or hls_map.get("HD1") or hls_map.get("SD1") or "")
    nested = stream.get("flv_pull_url") if isinstance(stream.get("flv_pull_url"), dict) else {}
    direct = stream.get("flv_pull_url") if isinstance(stream.get("flv_pull_url"), str) else ""
    # 同一場直播同時提供四檔 FLV，碼率差 6 倍，全部留給用戶選
    flvs = []
    for key in TIER_KEYS:
        url = _url_value(flv_map.get(key)) or _url_value(nested.get(key))
        if url:
            flvs.append({"key": key, "url": url})
    flv = _url_value(stream.get("rtmp_pull_url") or direct) or (flvs[0]["url"] if flvs else "")
    if not hls and not flv:
        return None
    room = room if isinstance(room, dict) else {}
    owner = room.get("owner") if isinstance(room.get("owner"), dict) else {}
    return {
        "room_id": room_id,
        "web_rid": web_rid,
        "title": str(room.get("title") or ""),
        "nickname": str(owner.get("nickname") or room.get("nickname") or ""),
        "cover": _url_value(_cover_value(room.get("cover"))) or COVER,
        "hls": hls,
        "flv": flv,
        "flvs": flvs,
        "game": "",
        "signature": "",
        "user_count_str": "",
        "total_user_str": "",
        "source": source,
        "room": room or None,
    }


# ==================== RSC（SSR）解析 ====================

def _rsc_push(content):
    """抖音的 RSC 資料被拆成多個 self.__pace_f.push([1,"…"]) 塊，業務資料不一定在第一塊。"""
    mark = "self.__pace_f.push([1,"
    start_from = 0
    while True:
        index = content.find(mark, start_from)
        if index < 0:
            return ""
        start = content.find("[", index)
        if start < 0:
            return ""
        end = _bracket_end(content, start)
        if end < 0:
            return ""
        block = content[start:end + 1]
        start_from = end + 1
        # 先做字串比對再解析，避開巨大區塊的無謂 json.loads
        if "categoryData" not in block and "roomsData" not in block:
            continue
        try:
            array = json.loads(block)
            text = array[1] if isinstance(array, list) and len(array) > 1 else None
            if isinstance(text, str) and ("categoryData" in text or "roomsData" in text):
                return block
        except Exception:
            continue


def _bracket_end(text, start):
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return index
    return -1


def _rsc_value(block):
    array = json.loads(block)
    text = array[1] if isinstance(array, list) and len(array) > 1 else ""
    # RSC 前綴為任意位數的行號（如「5:」「123:」），需整體剝離
    if isinstance(text, str):
        text = re.sub(r"^\d+:", "", text)
    root = json.loads(text)
    categories = _deep_object(root, "categoryData")
    rooms = _rooms_object(root)
    if categories:
        if rooms and rooms.get("roomsData") and not categories.get("roomsData"):
            categories["roomsData"] = rooms["roomsData"]
        return categories
    return rooms or root


def _deep_object(node, key, depth=0):
    if depth > 32:
        return None
    if isinstance(node, list):
        for item in node:
            found = _deep_object(item, key, depth + 1)
            if found:
                return found
        return None
    if isinstance(node, dict):
        if isinstance(node.get(key), list):
            return node
        for value in node.values():
            found = _deep_object(value, key, depth + 1)
            if found:
                return found
    return None


def _rooms_object(node):
    if isinstance(node, list):
        for item in node:
            found = _rooms_object(item)
            if found:
                return found
        return None
    if isinstance(node, dict):
        if "roomsData" in node:
            return node
        for value in node.values():
            found = _rooms_object(value)
            if found:
                return found
    return None


# ==================== protobuf ====================

def _pb_varint(data, pos):
    value = 0
    shift = 0
    length = len(data)
    while pos < length:
        byte = data[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, pos
        shift += 7
    return None


def _pb_parse(data):
    fields = {}
    if not data:
        return fields
    pos = 0
    length = len(data)
    while pos < length:
        head = _pb_varint(data, pos)
        if head is None:
            break
        key, pos = head
        number = key >> 3
        wire = key & 7
        bucket = fields.setdefault(number, [])
        if wire == 0:
            got = _pb_varint(data, pos)
            if got is None:
                break
            item, pos = got
            bucket.append(item)
        elif wire == 2:
            got = _pb_varint(data, pos)
            if got is None:
                break
            size, pos = got
            end = pos + size
            if end > length:
                break
            bucket.append(data[pos:end])
            pos = end
        elif wire == 5:
            bucket.append(data[pos:pos + 4])
            pos += 4
        elif wire == 1:
            bucket.append(data[pos:pos + 8])
            pos += 8
        else:
            break
    return fields


def _pb_bytes(fields, number):
    items = fields.get(number)
    if not items:
        return b""
    value = items[0]
    return value if isinstance(value, (bytes, bytearray)) else b""


def _pb_text(value):
    if value is None:
        return ""
    if isinstance(value, (bytes, bytearray)):
        try:
            return bytes(value).decode("utf-8", "ignore")
        except Exception:
            return ""
    return str(value)


# ==================== gzip / inflate ====================

def _gunzip(payload):
    if not payload or len(payload) < 18:
        return b""
    if zlib is not None:
        try:
            return zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(bytes(payload))
        except Exception:
            pass
    try:
        return _inflate(_gzip_body(bytes(payload)))
    except Exception:
        # 資料損毀 / 截斷：當作沒有內容，讓上層靜默跳過這一包
        return b""


def _gzip_body(payload):
    """跳過 gzip 標頭（含可選欄位），回傳 deflate 資料（去掉 8 位元組尾）。"""
    pos = 10
    flags = payload[3]
    if flags & 4:
        extra = payload[pos] | (payload[pos + 1] << 8)
        pos += 2 + extra
    if flags & 8:
        while pos < len(payload) and payload[pos] != 0:
            pos += 1
        pos += 1
    if flags & 16:
        while pos < len(payload) and payload[pos] != 0:
            pos += 1
        pos += 1
    if flags & 2:
        pos += 2
    return payload[pos:len(payload) - 8]


INFLATE_LEN_BASE = [3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59,
                    67, 83, 99, 115, 131, 163, 195, 227, 258]
INFLATE_LEN_EXTRA = [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3,
                     4, 4, 4, 4, 5, 5, 5, 5, 0]
INFLATE_DIST_BASE = [1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513,
                     769, 1025, 1537, 2049, 3073, 4097, 6145, 8193, 12289, 16385, 24577]
INFLATE_DIST_EXTRA = [0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8,
                      9, 9, 10, 10, 11, 11, 12, 12, 13, 13]
INFLATE_ORDER = [16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15]


class _Bits:
    """LSB 優先的位元流讀取器（DEFLATE 用）。"""

    def __init__(self, data):
        self.data = data
        self.pos = 0
        self.buf = 0
        self.count = 0

    def fill(self, size, strict=True):
        while self.count < size:
            if self.pos >= len(self.data):
                if strict:
                    raise ValueError("inflate: unexpected EOF")
                return
            self.buf |= self.data[self.pos] << self.count
            self.pos += 1
            self.count += 8

    def read(self, size):
        if size == 0:
            return 0
        self.fill(size)
        value = self.buf & ((1 << size) - 1)
        self.buf >>= size
        self.count -= size
        return value

    def align(self):
        drop = self.count & 7
        self.buf >>= drop
        self.count -= drop


def _inflate_table(lengths):
    max_bits = max(lengths) if lengths else 0
    if not max_bits:
        return None
    counts = [0] * (max_bits + 1)
    for length in lengths:
        if length:
            counts[length] += 1
    codes = [0] * (max_bits + 1)
    code = 0
    for bits in range(1, max_bits + 1):
        code = (code + counts[bits - 1]) << 1
        codes[bits] = code
    size = 1 << max_bits
    table = [0] * size
    for symbol, length in enumerate(lengths):
        if not length:
            continue
        current = codes[length]
        codes[length] += 1
        # canonical 碼是 MSB 序，位流是 LSB 序，逐位反轉
        rev = 0
        for _ in range(length):
            rev = (rev << 1) | (current & 1)
            current >>= 1
        entry = (symbol << 4) | length
        for index in range(rev, size, 1 << length):
            table[index] = entry
    return {"table": table, "max": max_bits, "mask": size - 1}


_FIXED = []


def _inflate_fixed():
    if _FIXED:
        return _FIXED
    lit = [8] * 144 + [9] * 112 + [7] * 24 + [8] * 8
    _FIXED.append(_inflate_table(lit))
    _FIXED.append(_inflate_table([5] * 32))
    return _FIXED


def _inflate_symbol(bits, huffman):
    if not huffman:
        raise ValueError("inflate: empty Huffman table")
    if bits.count < huffman["max"]:
        bits.fill(huffman["max"], strict=False)
    entry = huffman["table"][bits.buf & huffman["mask"]]
    if not entry:
        raise ValueError("inflate: invalid Huffman code")
    length = entry & 15
    if length > bits.count:
        raise ValueError("inflate: unexpected EOF")
    bits.buf >>= length
    bits.count -= length
    return entry >> 4


def _inflate(source):
    data = bytes(source)
    bits = _Bits(data)
    out = bytearray()

    def block(lit, dist):
        while True:
            symbol = _inflate_symbol(bits, lit)
            if symbol < 256:
                out.append(symbol)
            elif symbol == 256:
                return
            else:
                index = symbol - 257
                if index >= len(INFLATE_LEN_BASE):
                    raise ValueError("inflate: invalid length code")
                length = INFLATE_LEN_BASE[index] + bits.read(INFLATE_LEN_EXTRA[index])
                code = _inflate_symbol(bits, dist)
                if code >= len(INFLATE_DIST_BASE):
                    raise ValueError("inflate: invalid distance code")
                distance = INFLATE_DIST_BASE[code] + bits.read(INFLATE_DIST_EXTRA[code])
                if distance > len(out):
                    raise ValueError("inflate: distance too far")
                start = len(out) - distance
                # distance < length 時是重疊複製（LZ77 常態），逐位元組寫入才正確
                for offset in range(length):
                    out.append(out[start + offset])

    def dynamic():
        hlit = bits.read(5) + 257
        hdist = bits.read(5) + 1
        hclen = bits.read(4) + 4
        lengths = [0] * 19
        for index in range(hclen):
            lengths[INFLATE_ORDER[index]] = bits.read(3)
        coder = _inflate_table(lengths)
        all_lengths = []
        while len(all_lengths) < hlit + hdist:
            symbol = _inflate_symbol(bits, coder)
            if symbol < 16:
                all_lengths.append(symbol)
            elif symbol == 16:
                repeat = bits.read(2) + 3
                previous = all_lengths[-1] if all_lengths else 0
                all_lengths.extend([previous] * repeat)
            elif symbol == 17:
                all_lengths.extend([0] * (bits.read(3) + 3))
            elif symbol == 18:
                all_lengths.extend([0] * (bits.read(7) + 11))
            else:
                raise ValueError("inflate: invalid code length")
        all_lengths = all_lengths[:hlit + hdist]
        return _inflate_table(all_lengths[:hlit]), _inflate_table(all_lengths[hlit:])

    while True:
        final = bits.read(1)
        kind = bits.read(2)
        if kind == 0:
            bits.align()
            size = bits.read(16)
            bits.read(16)
            for _ in range(size):
                out.append(bits.read(8))
        elif kind == 1:
            lit, dist = _inflate_fixed()
            block(lit, dist)
        elif kind == 2:
            lit, dist = dynamic()
            block(lit, dist)
        else:
            raise ValueError("inflate: invalid block type")
        if final:
            break
    return bytes(out)


# ==================== 抖音彈幕解碼 ====================

def _douyin_messages(data, on_ready):
    """解 PushFrame：frame[8] 是 payload（gzip）→ Response[1] 是訊息列表。"""
    results = []
    if not data:
        return results
    try:
        frame = _pb_parse(bytes(data))
        payload = _pb_bytes(frame, 8)
        if not payload:
            return results
        if payload[0] == 0x1F and payload[1] == 0x8B:
            payload = _gunzip(payload)
        if not payload:
            return results
        response = _pb_parse(payload)
        for raw in response.get(1) or []:
            try:
                item = _pb_parse(raw)
                if _pb_text((item.get(1) or [None])[0]) != "WebcastChatMessage":
                    continue
                body = _pb_parse(_pb_bytes(item, 2))
                content = _pb_text((body.get(3) or [None])[0])
                if not content or len(content) > 500:
                    continue
                user = _pb_parse(_pb_bytes(body, 2))
                nick = _pb_text((user.get(3) or [None])[0]) or "抖音觀眾"
            except Exception:
                continue
            on_ready()
            # color 必須是數字：傳 "#FFFFFF" 字串會被宿主丟棄整條彈幕
            results.append({"text": content, "color": 0xFFFFFF, "size": 20,
                            "type": 1, "nick": nick})
        # 抖音推播閘道收到客戶端任何幀（ack / hb）都會立刻關閉連線，
        # 因此本端只解析下行 PushFrame，不主動回送任何幀；斷線由 _subscribe 重連。
    except Exception:
        pass
    return results


# ==================== FLV ====================

class _ReadError(Exception):
    def __init__(self, origin):
        super().__init__(str(origin))
        self.origin = origin


class _ByteReader:
    def __init__(self, reader):
        self._reader = reader
        self._chunk = b""
        self._offset = 0

    def read(self, size):
        out = bytearray()
        while len(out) < size:
            if self._offset >= len(self._chunk):
                try:
                    value = self._reader.read()
                except Exception as error:
                    raise _ReadError(error)
                if not value:
                    return None
                self._chunk = bytes(value)
                self._offset = 0
            take = min(size - len(out), len(self._chunk) - self._offset)
            out += self._chunk[self._offset:self._offset + take]
            self._offset += take
        return bytes(out)


def _uint24(data, offset):
    return data[offset] * 65536 + data[offset + 1] * 256 + data[offset + 2]


def _uint32(data, offset):
    return data[offset] * 16777216 + _uint24(data, offset + 1)


def _write_timestamp(tag, value):
    value &= 0xFFFFFFFF
    tag[4] = (value >> 16) & 0xFF
    tag[5] = (value >> 8) & 0xFF
    tag[6] = value & 0xFF
    tag[7] = (value >> 24) & 0xFF


def _is_media(kind, data, length):
    if length < 2 or kind == 18:
        return False
    if kind == 8:
        return (data[0] >> 4) != 10 or data[1] == 1
    codec = data[0] & 15
    return (codec != 7 and codec != 12) or data[1] == 1


def _timestamp(tag, clock, timeline, media):
    if not media:
        return max(0, timeline["last"])
    value = _uint24(tag, 4) + tag[7] * 16777216
    if clock["previous"] - value > 2147483648:
        clock["wrap"] += 4294967296
    clock["previous"] = value
    current = value + clock["wrap"]
    if clock["base"] is None:
        clock["base"] = current
    result = max(0, clock["start"] + current - clock["base"])
    timeline["last"] = max(timeline["last"], result)
    return result


def _mount_flv(spider, open_stream, min_duration=0):
    timeline = {"started": False, "last": -1}
    delays = [500, 1000, 2000]
    failures = 0
    while True:
        reader = open_stream()
        previous = timeline["last"]
        failure = None
        try:
            yield from _read_flv(spider, reader, timeline)
        except _ReadError as error:
            failure = error.origin
        finally:
            try:
                reader.close()
            except Exception:
                pass
        duration = timeline["last"] - previous
        if failure is None and duration >= min_duration:
            failures = 0
        else:
            if duration >= 10000:
                failures = 0
            if failures == len(delays):
                raise failure if failure else RuntimeError("直播串流反覆提前結束")
            failures += 1
        if failures:
            spider.net.sleep(delays[failures - 1])


def _read_flv(spider, reader, timeline):
    read = _ByteReader(reader).read
    header = _read_flv_header(read)
    continuing = timeline["started"]
    if not continuing:
        timeline["started"] = True
        yield header

    clock = {"base": None, "start": timeline["last"] + 1, "previous": 0, "wrap": 0}
    count = 0
    batch = []
    size = 0
    flush_at = time.time() + 0.25
    failure = None
    try:
        while True:
            tag = read(11)
            if tag is None:
                break
            kind = tag[0]
            length = _uint24(tag, 1)
            if kind not in (8, 9, 18) or _uint24(tag, 8) != 0:
                raise RuntimeError("直播 FLV 封包無效")
            data = read(length + 4)
            if data is None:
                break
            if _uint32(data, length) != length + 11:
                raise RuntimeError("直播 FLV 封包長度錯誤")
            if kind == 18 and continuing:
                continue
            media = _is_media(kind, data, len(data) - 4)
            if media:
                count += 1
            mutable = bytearray(tag)
            _write_timestamp(mutable, _timestamp(mutable, clock, timeline, media))
            batch.append(bytes(mutable))
            batch.append(data)
            size += len(mutable) + len(data)
            if size >= 65536 or time.time() >= flush_at:
                yield b"".join(batch)
                batch = []
                size = 0
                flush_at = time.time() + 0.25
    except _ReadError:
        raise
    except Exception as error:
        failure = error
    if size:
        yield b"".join(batch)
    if failure:
        raise failure
    if not count:
        raise RuntimeError("直播串流已結束，沒有可續接的媒體資料")


def _read_flv_header(read):
    header = read(9)
    if header is None or header[0] != 70 or header[1] != 76 or header[2] != 86 or header[3] != 1:
        raise RuntimeError("直播串流不是 FLV")
    offset = _uint32(header, 5)
    if offset < 9 or offset > 65536:
        raise RuntimeError("直播 FLV 標頭無效")
    extra = read(offset - 9 + 4)
    if extra is None:
        raise RuntimeError("直播 FLV 標頭不完整")
    return header + extra
