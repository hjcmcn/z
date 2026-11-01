import { Crypto, load, _ } from 'assets://js/lib/cat.js';

let HOSTS = [
    'https://kanju17.com',
    'https://www.kanju17.com',
    'https://kanju.ai',
    'http://kanju17.com'
];
let HOST = HOSTS[0];

const SIGN_KEY = '557d0e4ae929f438da6bd84412374e6086b8af09b3fed54bf22601d5bf8c54a0';
const CLIENT_NAME = 'dianyingtiantang-frontend';
const CLIENT_VERSION = '1.0.0';
const BUILD_VERSION = 'dianyingtiantang-v2026.10.30.2-api-build-boundary-ee3385411179-web';
const PROTOCOL_VERSION = '2026-07-05.library-v2.playback-v1';

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36';

const PAGE_LIMIT = 24;
const LINE_CACHE = {};   
const PLAY_CACHE = {};   
const HOME_CACHE = {};   
const PL_CACHE = {};     
const CUR_CACHE = {};   


const SHA_K = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
];

function utf8Bytes(str) {
    const out = [];
    for (let i = 0; i < str.length; i++) {
        let c = str.charCodeAt(i);
        if (c < 0x80) {
            out.push(c);
        } else if (c < 0x800) {
            out.push(0xc0 | (c >> 6), 0x80 | (c & 0x3f));
        } else if (c >= 0xd800 && c <= 0xdbff && i + 1 < str.length) {
            const c2 = str.charCodeAt(i + 1);
            const cp = 0x10000 + ((c - 0xd800) << 10) + (c2 - 0xdc00);
            out.push(0xf0 | (cp >> 18), 0x80 | ((cp >> 12) & 0x3f), 0x80 | ((cp >> 6) & 0x3f), 0x80 | (cp & 0x3f));
            i++;
        } else {
            out.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 0x3f), 0x80 | (c & 0x3f));
        }
    }
    return out;
}

function bytesToHex(bytes) {
    let s = '';
    for (let i = 0; i < bytes.length; i++) {
        s += (bytes[i] < 16 ? '0' : '') + bytes[i].toString(16);
    }
    return s;
}

function rotr(x, n) {
    return (x >>> n) | (x << (32 - n));
}

function sha256Bytes(bytes) {
    const len = bytes.length;
    const bitLen = len * 8;
    const withPad = [];
    for (let i = 0; i < len; i++) withPad.push(bytes[i] & 0xff);
    withPad.push(0x80);
    while (withPad.length % 64 !== 56) withPad.push(0);
    const hi = Math.floor(bitLen / 0x100000000);
    withPad.push((hi >>> 24) & 0xff, (hi >>> 16) & 0xff, (hi >>> 8) & 0xff, hi & 0xff);
    withPad.push((bitLen >>> 24) & 0xff, (bitLen >>> 16) & 0xff, (bitLen >>> 8) & 0xff, bitLen & 0xff);

    let h0 = 0x6a09e667, h1 = 0xbb67ae85, h2 = 0x3c6ef372, h3 = 0xa54ff53a,
        h4 = 0x510e527f, h5 = 0x9b05688c, h6 = 0x1f83d9ab, h7 = 0x5be0cd19;

    const w = new Array(64);

    for (let off = 0; off < withPad.length; off += 64) {
        for (let i = 0; i < 16; i++) {
            w[i] = ((withPad[off + i * 4] << 24) | (withPad[off + i * 4 + 1] << 16) |
                (withPad[off + i * 4 + 2] << 8) | withPad[off + i * 4 + 3]) | 0;
        }
        for (let i = 16; i < 64; i++) {
            const s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >>> 3);
            const s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >>> 10);
            w[i] = (w[i - 16] + s0 + w[i - 7] + s1) | 0;
        }
        let a = h0, b = h1, c = h2, d = h3, e = h4, f = h5, g = h6, h = h7;
        for (let i = 0; i < 64; i++) {
            const S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
            const ch = (e & f) ^ (~e & g);
            const t1 = (h + S1 + ch + SHA_K[i] + w[i]) | 0;
            const S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
            const maj = (a & b) ^ (a & c) ^ (b & c);
            const t2 = (S0 + maj) | 0;
            h = g; g = f; f = e; e = (d + t1) | 0;
            d = c; c = b; b = a; a = (t1 + t2) | 0;
        }
        h0 = (h0 + a) | 0; h1 = (h1 + b) | 0; h2 = (h2 + c) | 0; h3 = (h3 + d) | 0;
        h4 = (h4 + e) | 0; h5 = (h5 + f) | 0; h6 = (h6 + g) | 0; h7 = (h7 + h) | 0;
    }

    const out = [];
    [h0, h1, h2, h3, h4, h5, h6, h7].forEach(function (x) {
        out.push((x >>> 24) & 0xff, (x >>> 16) & 0xff, (x >>> 8) & 0xff, x & 0xff);
    });
    return out;
}

function hmacSha256Hex(keyStr, msgStr) {
    let key = utf8Bytes(keyStr);
    if (key.length > 64) key = sha256Bytes(key);
    while (key.length < 64) key.push(0);
    const oKey = [], iKey = [];
    for (let i = 0; i < 64; i++) {
        oKey.push(key[i] ^ 0x5c);
        iKey.push(key[i] ^ 0x36);
    }
    const inner = sha256Bytes(iKey.concat(utf8Bytes(msgStr)));
    return bytesToHex(sha256Bytes(oKey.concat(inner)));
}


function nowMs() {
    return new Date().getTime();
}

function pruneCache(obj, max) {
    const keys = Object.keys(obj);
    if (keys.length <= max) return;
    for (let i = 0; i < keys.length - max; i++) delete obj[keys[i]];
}

function randomHex(n) {
    let s = '';
    for (let i = 0; i < n; i++) {
        s += '0123456789abcdef'.charAt(Math.floor(Math.random() * 16));
    }
    return s;
}

function buildHeaders(pathQ, method) {
    const ts = String(nowMs());
    const nc = randomHex(32);
    const sig = hmacSha256Hex(SIGN_KEY, method + '\n' + pathQ + '\n' + ts + '\n' + nc);
    return {
        'Accept': 'application/json',
        'User-Agent': UA,
        'Referer': HOST + '/',
        'Origin': HOST,
        'x-ai-movie-client-name': CLIENT_NAME,
        'x-ai-movie-client-version': CLIENT_VERSION,
        'x-ai-movie-build-version': BUILD_VERSION,
        'x-ai-movie-protocol-version': PROTOCOL_VERSION,
        'x-ai-movie-timestamp': ts,
        'x-ai-movie-nonce': nc,
        'x-ai-movie-signature': sig
    };
}

function rawText(res) {
    if (!res) return '';
    if (typeof res === 'string') return res;
    if (typeof res.content === 'string') return res.content;
    if (typeof res.body === 'string') return res.body;
    if (res.data !== undefined && res.data !== null) {
        return typeof res.data === 'string' ? res.data : JSON.stringify(res.data);
    }
    return '';
}

async function apiOnce(host, pathQ, method, bodyObj) {
    const headers = buildHeaders(pathQ, method);
    const opt = {
        method: method === 'GET' ? 'get' : 'post',
        headers: headers,
        timeout: 15000
    };
    if (bodyObj !== undefined && bodyObj !== null) {
        const payload = JSON.stringify(bodyObj);
        headers['Content-Type'] = 'application/json';
        opt.body = payload;
        opt.data = payload;
        opt.postType = 'json';
    }
    const res = await req(host + pathQ, opt);
    const code = res && (res.code || res.status || (res.headers && res.headers[':status']));
    if (code && code >= 400 && code < 500) {
        const err = new Error('http ' + code);
        err.fatal = true;
        throw err;
    }
    const text = rawText(res);
    if (!text) throw new Error('empty response');
    return JSON.parse(text);
}

async function api(pathQ, bodyObj, method) {
    method = method || (bodyObj === undefined ? 'GET' : 'POST');
    let lastErr = null;
    for (let i = 0; i < HOSTS.length; i++) {
        const host = HOSTS[i];
        try {
            const data = await apiOnce(host, pathQ, method, bodyObj);
            if (HOST !== host) HOST = host;
            return data;
        } catch (e) {
            lastErr = e;
            if (e && e.fatal) break;
        }
    }
    throw lastErr || new Error('request failed');
}


function enc(o) {
    return encodeURIComponent(o);
}

function joinArr(a, n) {
    if (!a) return '';
    const arr = Array.isArray(a) ? a : [a];
    return arr.slice(0, n || 99).join(',');
}

function pickId(card) {
    if (card.detail_url) {
        const p = String(card.detail_url).split('/');
        return p[p.length - 1];
    }
    return card.id || card.variant_id || '';
}

function picOf(card) {
    return card.poster_url || card.carousel_url || card.backdrop_url || '';
}

function cardToVod(card) {
    let remarks = card.remarks || card.episode_progress_text || '';
    if (!remarks && card.availability && card.availability.label) remarks = card.availability.label;
    if (!remarks && card.year) remarks = String(card.year);
    const vod = {
        vod_id: pickId(card),
        vod_name: card.title || card.normalized_title || '',
        vod_pic: picOf(card),
        vod_remarks: remarks,
        vod_year: card.year ? String(card.year) : '',
        vod_area: card.area || '',
        vod_lang: card.language || '',
        vod_type: joinArr(card.genres, 4),
        vod_actor: joinArr(card.actors, 6),
        vod_director: joinArr(card.directors, 3)
    };
    if (typeof card.score === 'number') vod.vod_score = String(card.score);
    if (card.description) vod.vod_content = card.description;
    if (card.content_kind === 'short_drama') vod.vod_remarks = vod.vod_remarks || '短剧';
    return vod;
}


const AREA_LIST = ['中国大陆', '中国香港', '中国台湾', '美国', '日本', '韩国', '英国', '法国', '德国', '泰国', '印度', '俄罗斯', '加拿大', '澳大利亚', '意大利', '西班牙'];

const YEAR_LIST = ['2026', '2025', '2024', '2023', '2022', '2021', '2020', '2019', '2018', '2017', '2016', '2015', '2014', '2013', '2012', '2011', '2010'];

const GENRE_MAP = {
    movie: ['动作', '喜剧', '爱情', '科幻', '恐怖', '惊悚', '剧情', '悬疑', '犯罪', '战争', '奇幻', '冒险', '动画', '古装', '灾难', '武侠', '家庭', '儿童', '歌舞', '历史', '传记', '音乐', '运动', '4K电影', '同性', '西部'],
    series: ['国产剧', '港剧', '台剧', '日剧', '韩剧', '美剧', '欧美剧', '泰国剧', '短剧', '悬疑', '爱情', '古装', '喜剧', '犯罪', '剧情', '奇幻', '惊悚', '都市', '罪案'],
    anime: ['国产动漫', '日本动漫', '日韩动漫', '欧美动漫', '热血', '搞笑', '恋爱', '奇幻', '冒险', '科幻', '悬疑', '日常', '校园', '治愈', '儿童', '玄幻', '战斗', '泡面', '推理'],
    variety: ['真人秀', '音乐', '晚会', '脱口秀', '文化', '旅游', '喜剧', '竞技', '选秀', '生活', '访谈', '大陆综艺', '日韩综艺', '港台综艺', '欧美综艺', '春晚'],
    documentary: ['历史', '自然', '人文', '社会', '传记', '美食', '音乐', '运动', '冒险', '剧情'],
    sports: ['体育赛事', '赛事', '世界杯', '奥运会', '足球', '篮球'],
    short_drama: ['现代都市', '言情总裁', '反转爽剧', '古装仙侠', '脑洞悬疑', '女频恋爱', '爽文短剧', '现代言情', '年代穿越', '重生民国', '霸总', '闪婚离婚', '穿越', '高手下山', '剧情', '爱情', '奇幻', '古装', '悬疑', '犯罪', '喜剧']
};

function buildFilter(tid) {
    const genres = GENRE_MAP[tid] || [];
    if (genres.length === 0) return [];
    const g = [{ n: '全部', v: '' }];
    genres.forEach(function (x) { g.push({ n: x, v: x }); });
    const a = [{ n: '全部', v: '' }];
    AREA_LIST.forEach(function (x) { a.push({ n: x, v: x }); });
    const y = [{ n: '全部', v: '' }];
    YEAR_LIST.forEach(function (x) { y.push({ n: x, v: x }); });
    return [
        { key: 'genre', name: '类型', value: g },
        { key: 'area', name: '地区', value: a },
        { key: 'year', name: '年份', value: y }
    ];
}


const PROVIDER_NAMES = {
    jinying: '金鹰', hongniu: '红牛', xinlang: '新浪', hhzy: '豪华', jszy: '极速',
    subo: '速播', suoni: '索尼', maotai: '茅台', niuniu: '牛牛', dbzy: '豆瓣',
    zuida: '最大', wsyzy: '无水印', wujin: '无尽', yyzy1080: '1080zyk', ffzy: '非凡',
    bfzy: '暴风', liangzi: '量子', ikun: 'ikun', dytt: '电影天堂', uku: 'U酷',
    zy360: '360', xigua: '西瓜', mdzy: '魔都', iqiyi: '爱奇艺', maoyan: '猫眼',
    ruyi: '如意',
    'official-hot-playback': '腾讯', bytedance: '官方B', dong: '官方D',
    'bytevod-lv2': '官方Z', 'bytevod-cloudflare': '海外C', 'official-r': '官方R',
    'official-mj-hls': 'AI4K-J', 'official-v': '官方V', 'bytevod-lv3': '官方S',
    'bytevod-cloudflare-4k': '4K海外C', 'official-mj': 'AI4K'
};


const PROVIDER_RANK = {
    jinying: 1, hongniu: 2, xinlang: 3, hhzy: 4, jszy: 5, subo: 6, suoni: 7,
    maotai: 8, niuniu: 9, dbzy: 10, zuida: 11, wsyzy: 12, wujin: 13,
    yyzy1080: 14, ffzy: 15, bfzy: 16, liangzi: 17, ikun: 18, dytt: 19,
    uku: 20, zy360: 21, xigua: 22, mdzy: 23, iqiyi: 24, maoyan: 25, ruyi: 26,
    'official-hot-playback': 30, bytedance: 31, dong: 32, 'bytevod-lv2': 33,
    'bytevod-cloudflare': 34, 'official-r': 35, 'official-v': 36,
    'bytevod-lv3': 37, 'official-mj-hls': 38, 'bytevod-cloudflare-4k': 39,
    'official-mj': 40
};

function providerName(o) {
    const pid = o.provider_id || '';
    return PROVIDER_NAMES[pid] || (o.display_label || o.label || o.provider_name || pid || '线路');
}

function providerRank(o) {
    const pid = o.provider_id || '';
    return PROVIDER_RANK[pid] || 50;
}


function originOf(url) {
    const m = String(url || '').match(/^(https?:\/\/[^\/]+)/i);
    return m ? m[1] : HOST;
}

function playable(url) {
    const header = {
        'User-Agent': UA,
        'Referer': originOf(url) + '/'
    };
    return { parse: 0, url: url, header: header };
}

function isDirect(o) {
    const u = String(o.url || '');
    if (!/^https?:\/\//i.test(u)) return false;
    if (o.url_kind === 'resolve_ticket') return false;
    return true;
}

function ticketOf(o) {
    const u = String(o.url || '');
    if (/^resolve:\/\//i.test(u)) return u.slice(10);
    if (o.url_kind === 'resolve_ticket') return u;
    return '';
}

async function getLines(token) {
    if (LINE_CACHE[token]) return LINE_CACHE[token];
    const data = await api('/v1/playback/resolve/' + enc(token));
    const opts = (data && data.line_options) || [];
    LINE_CACHE[token] = opts;
    pruneCache(LINE_CACHE, 150);
    return opts;
}


function uniqProviders(opts) {
    const seen = {};
    const out = [];
    for (let i = 0; i < opts.length; i++) {
        const o = opts[i];
        const key = o.provider_id || o.playback_source_id || o.label;
        if (!key || seen[key]) continue;
        seen[key] = 1;
        out.push(o);
    }
    return out;
}

async function resolveTicket(ticket) {
    const data = await api('/v1/playback/resolve-line?view=compact', { ticket: ticket });
    const line = data && data.line;
    if (line && line.url) return line;
    return null;
}


async function verifyStream(url, timeout) {
    if (!/\.m3u8(\?|$)/i.test(url)) return true;
    try {
        const res = await req(url, {
            method: 'get',
            headers: { 'User-Agent': UA, 'Referer': originOf(url) + '/' },
            timeout: timeout || 6000
        });
        const code = res && (res.code || res.status);
        if (code && code >= 400) return false;
        const text = rawText(res);
        return text.indexOf('#EXTM3U') >= 0 || text.indexOf('#EXTINF') >= 0;
    } catch (e) {
        return false;
    }
}


async function tryLines(opts, preferProvider) {
    const preferred = [];
    const direct = [];
    const ticketed = [];
    const seen = {};
    for (let i = 0; i < opts.length; i++) {
        const o = opts[i];
        const key = o.provider_id || o.playback_source_id || o.label || String(i);
        if (seen[key]) continue;
        seen[key] = 1;
        if (preferProvider && o.provider_id === preferProvider) preferred.push(o);
        else if (isDirect(o)) direct.push(o);
        else if (ticketOf(o)) ticketed.push(o);
    }

    const ordered = preferred.concat(direct).concat(ticketed);
    const start = nowMs();
    let checked = 0;

    for (let i = 0; i < ordered.length; i++) {
        if (nowMs() - start > 22000) break;
        const o = ordered[i];
        try {
            if (isDirect(o)) {
               
                if (checked >= 8) {
                    return { ok: true, url: o.url, opt: o };
                }
                checked++;
                if (await verifyStream(o.url)) {
                    return { ok: true, url: o.url, opt: o };
                }
            } else {
                const tk = ticketOf(o);
                if (!tk) continue;
                const line = await resolveTicket(tk);
                if (line && line.url) return { ok: true, url: line.url, opt: o };
            }
        } catch (e) {
            
        }
    }
    return { ok: false };
}


let EXT_MODE = '';

function init(cfg) {
    try {
        EXT_MODE = '';
        const ext = cfg && cfg.ext ? String(cfg.ext).trim() : '';
        if (!ext) return;
        if (/^https?:\/\//i.test(ext)) {
            HOST = ext.replace(/\/+$/, '');
            HOSTS = [HOST].concat(HOSTS.filter(function (h) { return h !== HOST; }));
        } else {
            EXT_MODE = ext.toLowerCase();
        }
    } catch (e) { }
}

async function home(filter) {
    let classes = [
        { type_id: 'movie', type_name: '电影' },
        { type_id: 'series', type_name: '电视剧' },
        { type_id: 'anime', type_name: '动漫' },
        { type_id: 'variety', type_name: '综艺' },
        { type_id: 'documentary', type_name: '纪录片' },
        { type_id: 'sports', type_name: '体育' },
        { type_id: 'short_drama', type_name: '短剧' },
        { type_id: 'short_hot', type_name: '短剧热榜' },
        { type_id: 'playlist', type_name: '精选片单' }
    ];
    if (EXT_MODE === 'short') {
        classes = [
            { type_id: 'short_drama', type_name: '短剧' },
            { type_id: 'short_hot', type_name: '短剧热榜' }
        ];
    }
    const filters = {};
    classes.forEach(function (c) {
        filters[c.type_id] = buildFilter(c.type_id);
    });
    return JSON.stringify({ class: classes, filters: filters });
}

async function homeVod() {
    const KEY = 'home';
    if (HOME_CACHE[KEY] && nowMs() - HOME_CACHE[KEY].t < 10 * 60 * 1000) {
        return JSON.stringify({ list: HOME_CACHE[KEY].list });
    }
    const seen = {};
    const list = [];
    
    try {
        const data = await api('/v1/feed/home');
        const sections = (data && data.sections) || [];
        for (let i = 0; i < sections.length; i++) {
            const cards = sections[i].cards || [];
            for (let j = 0; j < cards.length; j++) {
                const vod = cardToVod(cards[j]);
                if (!vod.vod_id || seen[vod.vod_id]) continue;
                seen[vod.vod_id] = 1;
                list.push(vod);
            }
        }
    } catch (e) { }
   
    try {
        const short = await api('/v1/short-drama/feed');
        const items = (short && short.items) || [];
        for (let i = 0; i < items.length; i++) {
            const vod = cardToVod(items[i]);
            if (!vod.vod_id || seen[vod.vod_id]) continue;
            seen[vod.vod_id] = 1;
            list.push(vod);
        }
    } catch (e) { }
    HOME_CACHE[KEY] = { t: nowMs(), list: list };
    return JSON.stringify({ list: list });
}

async function category(tid, pg, filter, extend) {
    pg = parseInt(pg) || 1;
    extend = extend || {};
    tid = String(tid || 'movie');

    if (tid === 'short_hot') return await catShortHot(pg);
    if (tid === 'playlist') return await catPlaylist(pg);

    let qs = '/v1/browse/catalog?page=' + pg + '&limit=' + PAGE_LIMIT + '&kind=' + enc(tid);
    if (extend.genre) qs += '&genre=' + enc(extend.genre);
    if (extend.area) qs += '&area=' + enc(extend.area);
    if (extend.year) qs += '&year=' + enc(extend.year);

    try {
        const data = await api(qs);
        const cards = (data && data.cards) || [];
        const pageInfo = (data && data.pagination) || {};
        const hasMore = !!pageInfo.has_more;
        const list = cards.map(cardToVod);
        return JSON.stringify({
            page: pg,
            pagecount: hasMore ? pg + 1 : pg,
            limit: limitOf(pageInfo),
            total: totalOf(pageInfo, pg, list.length),
            list: list
        });
    } catch (e) {
        return JSON.stringify({ page: pg, pagecount: 0, limit: PAGE_LIMIT, total: 0, list: [] });
    }
}


async function catShortHot(pg) {
    const KEY = 'shorthot';
    if (!CUR_CACHE[KEY]) CUR_CACHE[KEY] = { cursors: [null], t: nowMs() };
    if (nowMs() - CUR_CACHE[KEY].t > 10 * 60 * 1000) CUR_CACHE[KEY] = { cursors: [null], t: nowMs() };

    try {
       
        while (CUR_CACHE[KEY].cursors.length < pg) {
            const prev = CUR_CACHE[KEY].cursors[CUR_CACHE[KEY].cursors.length - 1];
            const q = '/v1/short-drama/feed' + (prev ? '?cursor=' + enc(prev) : '');
            const d = await api(q);
            CUR_CACHE[KEY].cursors.push(d && d.next_cursor ? d.next_cursor : null);
            if (!d || !d.next_cursor) break;
        }
        const cur = CUR_CACHE[KEY].cursors[pg - 1];
       
        const q = '/v1/short-drama/feed' + (cur ? '?cursor=' + enc(cur) : '');
        const data = await api(q);
        const items = (data && data.items) || [];
        const hasMore = !!(data && data.next_cursor);
        return JSON.stringify({
            page: pg,
            pagecount: hasMore ? pg + 1 : pg,
            limit: items.length || PAGE_LIMIT,
            total: hasMore ? (pg + 1) * 20 : (pg - 1) * 20 + items.length,
            list: items.map(cardToVod)
        });
    } catch (e) {
        return JSON.stringify({ page: pg, pagecount: 0, limit: PAGE_LIMIT, total: 0, list: [] });
    }
}


async function catPlaylist(pg) {
    const KEY = 'pl';
    try {
        if (!PL_CACHE[KEY] || nowMs() - PL_CACHE[KEY].t > 15 * 60 * 1000) {
            const data = await api('/v1/playlists/explore?limit=12&sort=hot');
            const arr = (data && data.data) || [];
            const seen = {};
            const all = [];
            for (let i = 0; i < arr.length && i < 10; i++) {
                try {
                    const p = await api('/v1/playlists/' + enc(arr[i].id));
                    const items = (p && p.items) || [];
                    for (let j = 0; j < items.length; j++) {
                        const it = items[j];
                        const id = it.target_id || it.id;
                        if (!id || seen[id]) continue;
                        seen[id] = 1;
                        all.push({
                            vod_id: id,
                            vod_name: it.title || '',
                            vod_pic: it.poster_url || '',
                            vod_remarks: (arr[i].title || '片单'),
                            vod_year: it.display && it.display.year ? String(it.display.year) : '',
                            vod_area: it.display && it.display.area ? it.display.area : '',
                            vod_type: joinArr(it.display && it.display.genres, 4),
                            vod_actor: joinArr(it.display && it.display.actors, 6)
                        });
                    }
                } catch (e) { }
            }
            PL_CACHE[KEY] = { t: nowMs(), list: all };
        }
        const all = PL_CACHE[KEY].list;
        const start = (pg - 1) * PAGE_LIMIT;
        const list = all.slice(start, start + PAGE_LIMIT);
        return JSON.stringify({
            page: pg,
            pagecount: start + PAGE_LIMIT < all.length ? pg + 1 : pg,
            limit: PAGE_LIMIT,
            total: all.length,
            list: list
        });
    } catch (e) {
        return JSON.stringify({ page: pg, pagecount: 0, limit: PAGE_LIMIT, total: 0, list: [] });
    }
}

function limitOf(p) {
    return p && p.limit ? p.limit : PAGE_LIMIT;
}

function totalOf(p, pg, n) {
    if (p && typeof p.total === 'number' && p.total > 0) {
        return p.has_more ? Math.max(p.total, (pg + 1) * PAGE_LIMIT) : p.total;
    }
    return p && p.has_more ? (pg + 1) * PAGE_LIMIT : (pg - 1) * PAGE_LIMIT + n;
}

async function detail(id) {
    id = String(id || '');
    if (!id) return JSON.stringify({ list: [] });
    try {
        const d = await api('/v1/catalog/' + enc(id));
        if (!d || !d.id) return JSON.stringify({ list: [] });

        const vod = cardToVod(d);
        vod.vod_id = id;
        vod.vod_name = d.title || vod.vod_name;
        vod.vod_content = d.description || '';
        vod.vod_remarks = d.remarks || d.episode_progress_text || vod.vod_remarks;
        vod.vod_year = d.year ? String(d.year) : vod.vod_year;
        vod.vod_area = d.area || vod.vod_area;
        vod.vod_lang = d.language || vod.vod_lang;
        vod.vod_actor = joinArr(d.actors, 10) || vod.vod_actor;
        vod.vod_director = joinArr(d.directors, 4) || vod.vod_director;
        vod.vod_type = joinArr(d.genres, 6) || vod.vod_type;
        if (d.total_episode_count) vod.vod_total = String(d.total_episode_count);
        if (d.current_episode_count) vod.vod_serial = String(d.current_episode_count);

        const eps = (d.episodes || []).filter(function (e) { return e && e.token; });
        if (eps.length === 0) {
            return JSON.stringify({ list: [vod] });
        }

       
        let providers = [];
        try {
            const opts = await getLines(eps[0].token);
            providers = uniqProviders(opts);
            providers.sort(function (a, b) {
                const da = isDirect(a) ? 0 : 1;
                const db = isDirect(b) ? 0 : 1;
                if (da !== db) return da - db;
                return providerRank(a) - providerRank(b);
            });
        } catch (e) { }

        const flags = [];
        const urls = [];

        
        flags.push('全线路智能');
        urls.push(episodesUrl(eps, ''));

        
        const usedLabel = { '全线路智能': 1 };
        let cap = providers.length;
        const perLine = eps.length * 110;
        if (cap > 6 && cap * perLine > 300000) {
            cap = Math.max(6, Math.floor(300000 / perLine));
        }
        if (cap > 40) cap = 40;
        for (let i = 0; i < cap; i++) {
            const o = providers[i];
            let label = String(providerName(o)).replace(/\$|#|@/g, '');
            if (usedLabel[label]) {
                let n = 2;
                while (usedLabel[label + n]) n++;
                label = label + n;
            }
            usedLabel[label] = 1;
            flags.push(label);
            urls.push(episodesUrl(eps, o.provider_id || ''));
        }

        vod.vod_play_from = flags.join('$$$');
        vod.vod_play_url = urls.join('$$$');
        return JSON.stringify({ list: [vod] });
    } catch (e) {
        return JSON.stringify({ list: [] });
    }
}

function episodesUrl(eps, provider) {
    const arr = [];
    for (let i = 0; i < eps.length; i++) {
        const e = eps[i];
        const name = (e.title || e.display_name || ('第' + (e.number || (i + 1)) + '集')).replace(/\$|#/g, ' ');
        arr.push(name + '$' + e.token + '@' + provider);
    }
    return arr.join('#');
}

async function search(wd, quick, pg) {
    pg = parseInt(pg) || 1;
    wd = String(wd || '').trim();
    if (!wd) return JSON.stringify({ page: pg, pagecount: 0, limit: PAGE_LIMIT, total: 0, list: [] });
    const qs = '/v1/browse/catalog?q=' + enc(wd) + '&page=' + pg + '&limit=' + PAGE_LIMIT;
    try {
        const data = await api(qs);
        const cards = (data && data.cards) || [];
        const pageInfo = (data && data.pagination) || {};
        return JSON.stringify({
            page: pg,
            pagecount: pageInfo.has_more ? pg + 1 : pg,
            limit: PAGE_LIMIT,
            total: totalOf(pageInfo, pg, cards.length),
            list: cards.map(cardToVod)
        });
    } catch (e) {
        return JSON.stringify({ page: pg, pagecount: 0, limit: PAGE_LIMIT, total: 0, list: [] });
    }
}

async function play(flag, id, flags) {
    id = String(id || '');
    if (!id) return JSON.stringify({ parse: 1, url: '' });
    if (/^https?:\/\//i.test(id)) return JSON.stringify(playable(id));

    const parts = id.split('@');
    const token = parts[0];
    const provider = parts[1] || '';

    const cacheKey = token + '@' + provider;
    if (PLAY_CACHE[cacheKey]) return JSON.stringify(playable(PLAY_CACHE[cacheKey]));

    try {
        let opts = await getLines(token);
        if (opts && opts.length > 0) {
            let r = await tryLines(opts, provider);
            if (!r.ok) {
               
                delete LINE_CACHE[token];
                opts = await getLines(token);
                r = await tryLines(opts, provider);
            }
            if (r.ok && r.url) {
                PLAY_CACHE[cacheKey] = r.url;
                pruneCache(PLAY_CACHE, 200);
                return JSON.stringify(playable(r.url));
            }
        }
    } catch (e) {
       
    }

    
    return JSON.stringify({
        parse: 1,
        url: HOST + '/player/' + enc(token),
        header: { 'User-Agent': UA, 'Referer': HOST + '/' }
    });
}

export function __jsEvalReturn() {
    return { init, home, homeVod, category, detail, search, play };
}
