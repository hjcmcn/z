/*
@header({
  searchable: 1,
  filterable: 1,
  quickSearch: 1,
  title: '围观短剧',
  lang: 'cat'
})
*/

let siteName = '围观短剧';
let siteKey = '';
let siteType = 0;

/* v6 防频控版（修复 v5「第一次能播、后续就不行了」）
   2026-10-31 实测根因：
   1) 服务端对同一 deviceId 有请求配额，连续超过 60 笔后返回 code=7001「请求过于频繁」，且短时间内不恢复；
      高频突发时新 deviceId 也会被一并限流（实测约 240 秒后恢复）。
   2) v5 打开一部剧的详情会逐集请求全部分集（50～74 笔），一趟就把配额耗尽，于是「第一次能播、后续分类/详情全空」。
   3) 播放直链本身有效期很长（实测 7 小时前签发的直链仍可正常播放），并非链接过期导致。
   本版对策：详情只花 1 笔取剧目信息，分集列表只记录「集号+标识」，播放时才按需取当前直链；配合 deviceId 配额轮换、
   请求限速、命中 7001 冷却与内存缓存（直链 3 小时内复用），保证连续播放不再中断。
   通道仍为官方 H5 免签名通道（os_type=2 + deviceId），不依赖已失效的 App 客户端签名。 */
let UA = "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.91 Mobile Safari/537.36";

let rule = {
    host: 'https://api.drama.9ddm.com',
    homeUrl: '/drama/home/newShortVideos',
    tagsUrl: '/drama/home/shortVideoTags',
    searchUrl: '/drama/home/searchV2',
    detailUrl: '/drama/play/h5/detail'
};

const DEFAULT_HEADERS = {
    'User-Agent': UA,
    'Content-Type': 'application/json',
    'Accept': 'application/json'
};

const PAGE_SIZE = 30;      // 实测 H5 searchV2 pageSize 上限 30

/* 请求预算与限频规避参数（依据 2026-10-31 实测配额） */
const REQ_PER_DEVICE = 40;         // 单 deviceId 请求上限（实测 60 笔触发 7001，留余量）
const MIN_INTERVAL_MS = 120;       // 相邻请求最小间隔
const WINDOW_MS = 30000;           // 限速窗口
const WINDOW_MAX_REQ = 20;         // 窗口内最多请求笔数
const COOLDOWN_MS = 20000;         // 命中 7001 后的冷却时长
const META_TTL = 1800 * 1000;      // 剧目信息缓存 30 分钟
const LINK_TTL = 3 * 3600 * 1000;  // 播放直链缓存 3 小时（实测直链 7 小时仍有效）
const LIST_TTL = 600 * 1000;       // 列表缓存 10 分钟

/* ================= AES-256-CBC 解密（内嵌，TVBox 壳内无 CryptoJS） ================= */

const SBOX = [
    0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
    0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
    0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
    0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
    0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
    0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
    0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
    0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
    0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
    0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
    0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
    0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
    0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
    0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
    0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
    0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16
];

function buildInvSbox() {
    var inv = [];
    for (var i = 0; i < 256; i++) inv[SBOX[i]] = i;
    return inv;
}
var INV_SBOX = buildInvSbox();

function gmul(a, b) {
    var p = 0;
    while (b) {
        if (b & 1) p ^= a;
        var hi = a & 0x80;
        a = (a << 1) & 0xff;
        if (hi) a ^= 0x1b;
        b >>= 1;
    }
    return p;
}

function subWord(word) {
    var b0 = SBOX[(word >>> 24) & 0xff];
    var b1 = SBOX[(word >>> 16) & 0xff];
    var b2 = SBOX[(word >>> 8) & 0xff];
    var b3 = SBOX[word & 0xff];
    return ((b0 << 24) | (b1 << 16) | (b2 << 8) | b3) >>> 0;
}

var RCON = [0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x80,0x1b,0x36,0x6c,0xd8,0xab,0x4d,0x9a];

function keyExpansion(keyBytes) {
    var w = [];
    for (var i = 0; i < 8; i++) {
        w.push((keyBytes[4*i] << 24) | (keyBytes[4*i+1] << 16) | (keyBytes[4*i+2] << 8) | keyBytes[4*i+3]);
    }
    for (var i = 8; i < 60; i++) {
        var temp = w[i-1];
        if (i % 8 === 0) {
            temp = (((temp << 8) | (temp >>> 24)) >>> 0);
            temp = subWord(temp) ^ (RCON[(i/8) - 1] << 24);
        } else if (i % 8 === 4) {
            temp = subWord(temp);
        }
        w.push((w[i-8] ^ temp) >>> 0);
    }
    return w;
}

function addRoundKey(s, w, round) {
    var base = round * 4;
    for (var r = 0; r < 4; r++) {
        for (var c = 0; c < 4; c++) {
            var word = w[base + c];
            var shift = 24 - 8*r;
            s[r][c] ^= (word >>> shift) & 0xff;
        }
    }
}

function invShiftRows(s) {
    for (var r = 0; r < 4; r++) {
        var row = [s[r][0], s[r][1], s[r][2], s[r][3]];
        for (var c = 0; c < 4; c++) s[r][c] = row[(c + 4 - r) % 4];
    }
}

function invSubBytes(s) {
    for (var r = 0; r < 4; r++) {
        for (var c = 0; c < 4; c++) s[r][c] = INV_SBOX[s[r][c]];
    }
}

function invMixColumns(s) {
    for (var c = 0; c < 4; c++) {
        var a0 = s[0][c], a1 = s[1][c], a2 = s[2][c], a3 = s[3][c];
        s[0][c] = gmul(a0,0x0e) ^ gmul(a1,0x0b) ^ gmul(a2,0x0d) ^ gmul(a3,0x09);
        s[1][c] = gmul(a0,0x09) ^ gmul(a1,0x0e) ^ gmul(a2,0x0b) ^ gmul(a3,0x0d);
        s[2][c] = gmul(a0,0x0d) ^ gmul(a1,0x09) ^ gmul(a2,0x0e) ^ gmul(a3,0x0b);
        s[3][c] = gmul(a0,0x0b) ^ gmul(a1,0x0d) ^ gmul(a2,0x09) ^ gmul(a3,0x0e);
    }
}

function decryptBlock(inBytes, w) {
    var s = [[0,0,0,0],[0,0,0,0],[0,0,0,0],[0,0,0,0]];
    for (var r = 0; r < 4; r++) {
        for (var c = 0; c < 4; c++) s[r][c] = inBytes[r + 4*c];
    }
    addRoundKey(s, w, 14);
    for (var round = 13; round >= 1; round--) {
        invShiftRows(s);
        invSubBytes(s);
        addRoundKey(s, w, round);
        invMixColumns(s);
    }
    invShiftRows(s);
    invSubBytes(s);
    addRoundKey(s, w, 0);
    var out = [];
    for (var r = 0; r < 4; r++) {
        for (var c = 0; c < 4; c++) out[r + 4*c] = s[r][c];
    }
    return out;
}

function aes256CbcDecrypt(cipherBytes, keyBytes, ivBytes) {
    var w = keyExpansion(keyBytes);
    var out = [];
    var prev = ivBytes.slice(0);
    for (var i = 0; i < cipherBytes.length; i += 16) {
        var block = cipherBytes.slice(i, i + 16);
        var dec = decryptBlock(block, w);
        for (var j = 0; j < 16; j++) out.push((dec[j] ^ prev[j]) & 0xff);
        prev = block;
    }
    return out;
}

var B64_CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';

function base64ToBytes(b64) {
    var out = [];
    var buf = 0, bits = 0;
    for (var i = 0; i < b64.length; i++) {
        var c = b64.charAt(i);
        if (c === '=') break;
        var v = B64_CHARS.indexOf(c);
        if (v < 0) continue;
        buf = (buf << 6) | v;
        bits += 6;
        if (bits >= 8) {
            bits -= 8;
            out.push((buf >> bits) & 0xff);
        }
    }
    return out;
}

function utf8ToString(bytes) {
    var s = '';
    for (var i = 0; i < bytes.length;) {
        var b = bytes[i];
        if (b < 0x80) {
            s += String.fromCharCode(b);
            i++;
        } else if ((b & 0xe0) === 0xc0) {
            s += String.fromCharCode(((b & 0x1f) << 6) | (bytes[i+1] & 0x3f));
            i += 2;
        } else if ((b & 0xf0) === 0xe0) {
            s += String.fromCharCode(((b & 0x0f) << 12) | ((bytes[i+1] & 0x3f) << 6) | (bytes[i+2] & 0x3f));
            i += 3;
        } else {
            var cp = ((b & 0x07) << 18) | ((bytes[i+1] & 0x3f) << 12) | ((bytes[i+2] & 0x3f) << 6) | (bytes[i+3] & 0x3f);
            s += String.fromCodePoint(cp);
            i += 4;
        }
    }
    return s;
}

// h5PlayUrl 结构：base64(前16字节=IV, 其余=密文)，h5PlayKey=base64(密钥)
function decryptH5Play(h5PlayUrl, h5PlayKey) {
    var raw = base64ToBytes(h5PlayUrl);
    var iv = raw.slice(0, 16);
    var ct = raw.slice(16);
    var key = base64ToBytes(h5PlayKey);
    var pt = aes256CbcDecrypt(ct, key, iv);
    var pad = pt[pt.length - 1];
    var data = pt.slice(0, pt.length - pad);
    return utf8ToString(data);
}

/* ================= 通用工具 ================= */

function init(cfg) {
    try {
        siteName = (cfg.skey && cfg.skey.split('_')[1]) || (cfg.key && cfg.key.split('_')[1]) || cfg.skey || cfg.key || '围观短剧';
        siteKey = cfg.skey;
        siteType = cfg.stype;
        console.log(`【${siteName}】初始化完成`);
    } catch (e) {
        console.log(`【${siteName}】初始化失败: ${e.message}`);
    }
}

function safeJSONParse(str, defaultValue) {
    var def = defaultValue === undefined ? {} : defaultValue;
    if (!str) return def;
    if (typeof str === 'object') return str;
    try {
        return JSON.parse(str);
    } catch (e) {
        console.log(`【${siteName}】JSON解析失败: ${e.message}`);
        return def;
    }
}

/* ================= deviceId 配额轮换、请求限速与内存缓存 ================= */

var curDeviceId = '';
var devReqCount = 0;
var reqStamps = [];
var cooldownUntil = 0;

var META_CACHE = {};   // oneId -> {t, v: 详情 data}
var LINK_CACHE = {};   // "oneId:集号" -> {t, v: {超清,高清,流畅}}
var LIST_CACHE = {};   // 列表键 -> {t, v: 视频数组}
var HOME_CACHE = null; // {t, v: {class, filters}}

// H5 端需要 deviceId（与官网前端相同生成规则，服务端不校验真实值）
function newDevice() {
    var r = '';
    var chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
    for (var i = 0; i < 9; i++) r += chars.charAt(Math.floor(Math.random() * chars.length));
    curDeviceId = 'device_' + Date.now() + '_' + r;
    devReqCount = 0;
    return curDeviceId;
}

// 每个 deviceId 用完配额即轮换，避免第 61 笔起被 7001 拒绝
function takeDevice() {
    if (!curDeviceId || devReqCount >= REQ_PER_DEVICE) newDevice();
    devReqCount++;
    return curDeviceId;
}

// 壳内没有可靠的 setTimeout，需要间隔时用受控短忙等（单次最多 1.2 秒）节流
function pauseSync(ms) {
    if (!ms || ms <= 0) return;
    var end = Date.now() + Math.min(ms, 1200);
    while (Date.now() < end) {}
}

// 限速：窗口总量 + 相邻请求最小间隔，避免高频突发触发 IP 级限流
function paceRequest() {
    var now = Date.now();
    var keep = [];
    for (var i = 0; i < reqStamps.length; i++) {
        if (now - reqStamps[i] < WINDOW_MS) keep.push(reqStamps[i]);
    }
    reqStamps = keep;
    if (reqStamps.length >= WINDOW_MAX_REQ) {
        pauseSync(WINDOW_MS - (now - reqStamps[0]) + 20);
        reqStamps = [];
        now = Date.now();
    }
    if (reqStamps.length) {
        var gap = now - reqStamps[reqStamps.length - 1];
        if (gap < MIN_INTERVAL_MS) pauseSync(MIN_INTERVAL_MS - gap);
    }
    reqStamps.push(Date.now());
    if (reqStamps.length > 80) reqStamps.splice(0, reqStamps.length - 80);
}

function cacheGet(store, key, ttl) {
    var item = store[key];
    if (item && (Date.now() - item.t) < ttl) return item.v;
    return null;
}
function cacheStale(store, key) {
    var item = store[key];
    return item ? item.v : null;
}
function cacheSet(store, key, v) {
    store[key] = { t: Date.now(), v: v };
    return v;
}

/* base64 编解码：分集标识只存 {"o":oneId,"n":集号}，避免 # $ 等分隔符污染播放列表 */
function utf8ToBytes(s) {
    var out = [];
    for (var i = 0; i < s.length; i++) {
        var c = s.charCodeAt(i);
        if (c < 0x80) {
            out.push(c);
        } else if (c < 0x800) {
            out.push(0xc0 | (c >> 6), 0x80 | (c & 63));
        } else if (c < 0xd800 || c >= 0xe000) {
            out.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63));
        } else {
            i++;
            var cp = 0x10000 + (((c & 0x3ff) << 10) | (s.charCodeAt(i) & 0x3ff));
            out.push(0xf0 | (cp >> 18), 0x80 | ((cp >> 12) & 63), 0x80 | ((cp >> 6) & 63), 0x80 | (cp & 63));
        }
    }
    return out;
}

function b64Encode(s) {
    var bytes = utf8ToBytes(s);
    var out = '';
    for (var i = 0; i < bytes.length; i += 3) {
        var b0 = bytes[i];
        var b1 = (i + 1 < bytes.length) ? bytes[i + 1] : 0;
        var b2 = (i + 2 < bytes.length) ? bytes[i + 2] : 0;
        out += B64_CHARS.charAt(b0 >> 2);
        out += B64_CHARS.charAt(((b0 & 3) << 4) | (b1 >> 4));
        out += (i + 1 < bytes.length) ? B64_CHARS.charAt(((b1 & 15) << 2) | (b2 >> 6)) : '=';
        out += (i + 2 < bytes.length) ? B64_CHARS.charAt(b2 & 63) : '=';
    }
    return out;
}

function b64DecodeText(s) {
    try {
        var bytes = base64ToBytes(s);
        if (!bytes || bytes.length === 0) return '';
        return utf8ToString(bytes);
    } catch (e) {
        return '';
    }
}

function pickPoster(it) {
    return it.vertPoster || it.horzPoster || it.vertMidPoster || '';
}

// 单次请求：附加 deviceId + os_type=2（H5 免签名通道）
// GET 走 URL query；POST 同时传 body(字符串) + data(对象)：FongMi 快鸭壳 Req.data 是 Gson JsonElement，
// 传字符串会被当 JsonPrimitive 转义成非法 JSON，传对象则 Gson 序列化规范；body 字符串供请求体原样兜底。
async function rawAttempt(url, paramsArr, bodyObj, deviceId) {
    var pairs = [];
    if (paramsArr && paramsArr.length) {
        for (var i = 0; i < paramsArr.length; i++) {
            pairs.push(encodeURIComponent(String(paramsArr[i][0])) + '=' + encodeURIComponent(String(paramsArr[i][1])));
        }
    }
    pairs.push('deviceId=' + encodeURIComponent(deviceId));
    pairs.push('os_type=2');
    var fullUrl = url + '?' + pairs.join('&');

    var headers = Object.assign({}, DEFAULT_HEADERS);
    var dataStr = '';
    var dataObj = null;
    if (bodyObj) {
        dataStr = JSON.stringify(bodyObj);
        dataObj = bodyObj;
        headers['Content-Type'] = 'application/json;charset=UTF-8';
    }

    var resp = await req(fullUrl, {
        method: bodyObj ? 'POST' : 'GET',
        headers: headers,
        body: dataStr,
        data: dataObj,
        timeout: 15000
    });

    var content = (resp && resp.content) || (resp && resp.data) || resp;
    if (typeof content === 'string') {
        return safeJSONParse(content, null);
    }
    return content || null;
}

// 带预算轮换、限速与限频规避的请求：
// 1) 冷却期内不发新请求（改用缓存，避免把风控激化）；
// 2) 命中 7001 先换 deviceId 再试，连续两次仍 7001 则进入冷却；
// 3) 其他异常同样换设备重试，最多 3 次。
async function request(url, paramsArr, bodyObj) {
    if (Date.now() < cooldownUntil) {
        console.log(`【${siteName}】限频冷却中（${Math.ceil((cooldownUntil - Date.now()) / 1000)}秒），改用缓存数据`);
        return null;
    }
    var last = null;
    var throttled = 0;
    for (var attempt = 0; attempt < 3; attempt++) {
        paceRequest();
        last = await rawAttempt(url, paramsArr, bodyObj, takeDevice());
        if (last && last.code === 200) return last;
        var code = last ? last.code : 0;
        var msg = last ? String(last.msg || '') : '请求失败';
        newDevice();   // 该设备计数可能已接近上限，直接换新
        if (code === 7001 || msg.indexOf('频繁') >= 0) {
            throttled++;
            console.log(`【${siteName}】命中限频（第${throttled}次）`);
            if (throttled >= 2) {
                cooldownUntil = Date.now() + COOLDOWN_MS;
                console.log(`【${siteName}】进入 ${COOLDOWN_MS / 1000} 秒冷却，其间改用缓存`);
                break;
            }
        } else {
            console.log(`【${siteName}】请求异常 code=${code}，换设备重试`);
        }
    }
    return last;
}

/* ================= TVBox 接口 ================= */

async function home() {
    if (HOME_CACHE && (Date.now() - HOME_CACHE.t) < META_TTL) {
        return JSON.stringify(HOME_CACHE.v);   // 分类标签缓存，避免每次进首页都发请求
    }
    var classes = [{ type_name: '全部', type_id: '全部' }];
    var filters = { '全部': [] };

    var data = await request(rule.host + rule.tagsUrl);
    if (data && data.code === 200) {
        var audiences = data.audiences || [];
        var tags = data.tags || [];
        var orders = data.orders || [];
        if (audiences.length === 0) audiences = ['男频', '女频'];

        // 标签筛选（实测 subject 传中文标签生效）
        var tagValues = [{ n: '全部', v: '' }];
        for (var j = 0; j < tags.length; j++) {
            tagValues.push({ n: tags[j], v: tags[j] });
        }

        // 排序（实测接口只接受中文原值，如「最热」，拒绝 hot/new）
        var orderValues = [{ n: '全部', v: '' }];
        for (var k = 0; k < orders.length; k++) {
            orderValues.push({ n: orders[k], v: orders[k] });
        }

        // 「全部」也提供标签与排序筛选（audience 留空 = 不限受众）
        filters['全部'] = [
            { key: 'tag', name: '标签', value: tagValues },
            { key: 'order', name: '排序', value: orderValues }
        ];

        for (var i = 0; i < audiences.length; i++) {
            var audience = audiences[i];
            classes.push({ type_name: audience, type_id: audience });
            filters[audience] = [
                { key: 'tag', name: '标签', value: tagValues },
                { key: 'order', name: '排序', value: orderValues }
            ];
        }
    }

    if (classes.length > 1) {
        HOME_CACHE = { t: Date.now(), v: { class: classes, filters: filters } };
    } else if (HOME_CACHE) {
        console.log(`【${siteName}】分类标签现取失败，回退缓存`);
        return JSON.stringify(HOME_CACHE.v);
    }

    return JSON.stringify({ class: classes, filters: filters });
}

async function homeVod() {
    try {
        var cachedVod = cacheGet(LIST_CACHE, 'homevod', LIST_TTL);
        if (cachedVod) return JSON.stringify({ list: cachedVod });

        var videos = [];
        var data = await request(rule.host + rule.homeUrl, [['page', 1], ['pageSize', PAGE_SIZE]]);
        var list = (data && data.data) || [];
        for (var i = 0; i < list.length; i++) {
            var it = list[i];
            if (it && it.oneId) {
                videos.push({
                    vod_id: String(it.oneId),
                    vod_name: it.title || '未知标题',
                    vod_pic: pickPoster(it),
                    vod_remarks: '集数:' + (it.episodeCount || 0),
                    vod_content: it.description || ''
                });
            }
        }
        if (videos.length) {
            cacheSet(LIST_CACHE, 'homevod', videos);
        } else {
            var staleVod = cacheStale(LIST_CACHE, 'homevod');
            if (staleVod) return JSON.stringify({ list: staleVod });
        }
        return JSON.stringify({ list: videos });
    } catch (e) {
        console.log(`【${siteName}】homeVod失败: ${e.message}`);
        return JSON.stringify({ list: cacheStale(LIST_CACHE, 'homevod') || [] });
    }
}

async function category(tid, pg, filter, extend) {
    var videos = [];
    var page = Number(pg) || 1;

    var tag = (extend && extend.tag) ? extend.tag : ((filter && filter.tag) ? filter.tag : '');
    var order = (extend && extend.order) ? extend.order : ((filter && filter.order) ? filter.order : '');
    var audience = (tid === '全部' || tid === '推荐') ? '' : tid;

    var cacheKey = 'cat|' + tid + '|' + page + '|' + tag + '|' + order;
    var cachedCat = cacheGet(LIST_CACHE, cacheKey, LIST_TTL);
    if (cachedCat) {
        var cachedPc = cachedCat.length >= PAGE_SIZE ? page + 1 : page;
        return JSON.stringify({
            list: cachedCat,
            page: page,
            pagecount: cachedPc,
            limit: cachedCat.length,
            total: cachedCat.length
        });
    }

    var postData = {
        audience: audience,
        episodeCount: '',
        order: order,
        page: page,
        pageSize: PAGE_SIZE,
        searchWord: '',
        shortPlayType: '',
        subject: tag,
        uid: '0'
    };

    var data = await request(rule.host + rule.searchUrl, null, postData);
    var list = (data && data.data) || [];
    for (var i = 0; i < list.length; i++) {
        var it = list[i];
        if (it && it.oneId) {
            videos.push({
                vod_id: String(it.oneId),
                vod_name: it.title || '未知标题',
                vod_pic: pickPoster(it),
                vod_remarks: '集数:' + (it.episodeCount || 0) + ' 播放:' + (it.viewCount || 0),
                vod_content: it.description || '',
                vod_year: it.publishDate || ''
            });
        }
    }

    var hasNext = videos.length >= PAGE_SIZE;
    if (videos.length) {
        cacheSet(LIST_CACHE, cacheKey, videos);
    } else {
        var staleCat = cacheStale(LIST_CACHE, cacheKey);
        if (staleCat) {
            console.log(`【${siteName}】分类现取失败，回退缓存列表`);
            videos = staleCat;
            hasNext = videos.length >= PAGE_SIZE;
        }
    }
    return JSON.stringify({
        list: videos,
        page: page,
        pagecount: hasNext ? page + 1 : page,
        limit: videos.length,
        total: videos.length
    });
}

// 解析 H5 详情里的加密播放数据：super/high/normal -> 超清/高清/流畅
function parsePlayPayload(payload) {
    if (!payload || !payload.h5PlayUrl || !payload.h5PlayKey) return null;
    var info;
    try {
        info = safeJSONParse(decryptH5Play(payload.h5PlayUrl, payload.h5PlayKey), {});
    } catch (e) {
        console.log(`【${siteName}】播放数据解密失败: ${e.message}`);
        return null;
    }
    var urls = {};
    if (info.super) urls['超清'] = info.super;
    if (info.high) urls['高清'] = info.high;
    if (info.normal) urls['流畅'] = info.normal;
    if (!urls['超清'] && !urls['高清'] && !urls['流畅']) return null;
    return urls;
}

// 取单集三档直链：优先内存缓存（直链实测 7 小时有效，3 小时内直接复用，不再花请求配额）；
// 取不到时回退旧缓存，保证风控期间已看过的分集仍能播放。
async function episodeLink(oneId, order) {
    var key = oneId + ':' + order;
    var fresh = cacheGet(LINK_CACHE, key, LINK_TTL);
    if (fresh) return fresh;

    var data = await request(rule.host + rule.detailUrl, [['oneId', oneId], ['playOrder', order]], null);
    var payload = (data && data.data) ? data.data : data;
    var urls = parsePlayPayload(payload);
    if (urls) {
        cacheSet(LINK_CACHE, key, urls);
        if (payload && payload.oneId) cacheSet(META_CACHE, oneId, payload);
        return urls;
    }

    var stale = cacheStale(LINK_CACHE, key);
    if (stale) {
        console.log(`【${siteName}】第${order}集现取失败，回退缓存直链`);
        return stale;
    }
    return null;
}

// 详情只花 1 笔请求：取剧目信息与总集数；分集列表只记录「集号+标识」，播放时才现取当前直链，
// 这样打开一部 70 集长剧不再一次性烧掉 deviceId 的请求配额。
async function detail(id) {
    var vid = String(id || '');
    if (!vid) return JSON.stringify({ list: [] });

    var meta = cacheGet(META_CACHE, vid, META_TTL);
    if (!meta) {
        var data = await request(rule.host + rule.detailUrl, [['oneId', vid], ['playOrder', 1]], null);
        var payload = (data && data.data) ? data.data : data;
        if (payload && payload.oneId) {
            meta = payload;
            cacheSet(META_CACHE, vid, payload);
            var first = parsePlayPayload(payload);
            if (first) cacheSet(LINK_CACHE, vid + ':1', first);
        } else {
            meta = cacheStale(META_CACHE, vid);   // 风控期间回退上次的剧目信息
            if (!meta) {
                console.log(`【${siteName}】详情无有效数据: id=${vid}`);
                return JSON.stringify({ list: [] });
            }
        }
    }

    var total = parseInt(meta.episodeCount, 10) || 0;
    if (total <= 0) total = await probeTotal(vid);   // 少见：接口未给集数时按需探测
    if (total <= 0) total = 1;

    var segs = [];
    for (var n = 1; n <= total; n++) {
        segs.push('第' + n + '集$' + b64Encode(JSON.stringify({ o: vid, n: n })));
    }

    var vod = {
        vod_id: vid,
        vod_name: meta.title || '未知剧名',
        vod_pic: meta.vertPoster || '',
        vod_remarks: '共' + total + '集',
        vod_content: meta.description || '',
        vod_play_from: '围观短剧',
        vod_play_url: segs.join('#')
    };
    return JSON.stringify({ list: [vod] });
}

// 接口未返回集数时的兜底：按序探测到首个失败为止（上限 40 集，走同一限速层）
async function probeTotal(vid) {
    var n = 1;
    while (n < 40) {
        var urls = await episodeLink(vid, n + 1);
        if (!urls) break;
        n++;
    }
    return n;
}

// 解析播放 id：新版为 base64({"o":oneId,"n":集号})；兼容旧版 encodeURIComponent(JSON) 与直接 URL
function parsePlayId(id) {
    var res = { o: '', n: 0, urls: null, url: '' };
    var text = '';
    if (typeof id === 'string') {
        var raw = id.indexOf('$') >= 0 ? id.split('$')[1] : id;
        if (raw.indexOf('http') === 0) {
            res.url = raw;
            return res;
        }
        text = b64DecodeText(raw);
        if (!text || text.charAt(0) !== '{') {
            try { text = decodeURIComponent(raw); } catch (e) { text = ''; }
        }
        if (!text || text.charAt(0) !== '{') text = raw;
    } else if (id && typeof id === 'object') {
        text = JSON.stringify(id);
    }
    var obj = safeJSONParse(text, null);
    if (obj && typeof obj === 'object') {
        if (obj.o) {
            res.o = String(obj.o);
            res.n = Number(obj.n) || 1;
        } else if (obj.oneId) {
            res.o = String(obj.oneId);
            res.n = Number(obj.playOrder) || 1;
        }
        if (obj['超清'] || obj['高清'] || obj['流畅']) {
            res.urls = { '超清': obj['超清'] || '', '高清': obj['高清'] || '', '流畅': obj['流畅'] || '' };
        }
    }
    return res;
}

// 播放：按「oneId+集号」现取当前直链（3 小时内命中缓存不花配额），取不到时回退缓存或旧版自带直链
async function play(flag, id, flags) {
    var pid = parsePlayId(id);
    var urls = null;

    if (pid.o && pid.n) {
        urls = await episodeLink(pid.o, pid.n);
    }
    if (!urls && pid.urls) urls = pid.urls;
    if (!urls && pid.url) {
        return JSON.stringify({ parse: 0, url: pid.url });
    }

    var clarityOrder = ['超清', '高清', '流畅'];
    var list = [];
    if (urls) {
        for (var i = 0; i < clarityOrder.length; i++) {
            var u = urls[clarityOrder[i]];
            if (u && u.indexOf('http') === 0 && list.indexOf(u) < 0) {
                list.push(clarityOrder[i]);
                list.push(u);
            }
        }
    }
    if (list.length === 0) {
        return JSON.stringify({ parse: 0, url: '', msg: '暂无可用播放地址' });
    }
    return JSON.stringify({ parse: 0, url: list });
}

async function search(wd, quick, pg) {
    if (!wd || wd.trim() === '') {
        return JSON.stringify({ list: [], page: 1 });
    }

    var page = Number(pg) || 1;
    var cacheKey = 'search|' + wd + '|' + page;
    var cachedSearch = cacheGet(LIST_CACHE, cacheKey, LIST_TTL);
    if (cachedSearch) {
        var cachedSpc = cachedSearch.length >= PAGE_SIZE ? page + 1 : page;
        return JSON.stringify({
            list: cachedSearch,
            page: page,
            pagecount: cachedSpc,
            limit: cachedSearch.length,
            total: cachedSearch.length
        });
    }

    var postData = {
        audience: '',
        episodeCount: '',
        order: '',
        page: page,
        pageSize: PAGE_SIZE,
        searchWord: wd,
        shortPlayType: '',
        subject: '',
        uid: '0'
    };

    var data = await request(rule.host + rule.searchUrl, null, postData);
    var videos = [];
    var list = (data && data.data) || [];
    for (var i = 0; i < list.length; i++) {
        var it = list[i];
        if (it && it.oneId) {
            videos.push({
                vod_id: String(it.oneId),
                vod_name: it.title || '未知标题',
                vod_pic: pickPoster(it),
                vod_remarks: '集数:' + (it.episodeCount || 0) + ' 播放:' + (it.viewCount || 0),
                vod_content: it.description || '',
                vod_year: it.publishDate || ''
            });
        }
    }

    if (videos.length) {
        cacheSet(LIST_CACHE, cacheKey, videos);
    } else {
        var staleSearch = cacheStale(LIST_CACHE, cacheKey);
        if (staleSearch) {
            console.log(`【${siteName}】搜索现取失败，回退缓存列表`);
            videos = staleSearch;
        }
    }
    return JSON.stringify({
        list: videos,
        page: page,
        pagecount: videos.length >= PAGE_SIZE ? page + 1 : page,
        limit: videos.length,
        total: videos.length
    });
}

export function __jsEvalReturn() {
    return {
        init: init,
        home: home,
        homeVod: homeVod,
        category: category,
        detail: detail,
        play: play,
        search: search
    };
}