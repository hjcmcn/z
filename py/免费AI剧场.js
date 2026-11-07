import { Crypto, load, _ } from 'assets://js/lib/cat.js';

let HOST = 'https://zangyougou.com';
let siteKey = '', siteType = '', sourceKey = '', ext = '';

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36';

const HTML_HEADERS = {
    'User-Agent': UA,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1'
};

const PLAY_CACHE = {};
const SEARCH_CACHE = {};
const EP_CACHE = {};



async function request(url, ref, retry = 1) {
    const headers = Object.assign({}, HTML_HEADERS);
    if (ref) headers['Referer'] = ref;
    try {
        const res = await req(url, { method: 'get', headers: headers, timeout: 12000 });
        if (res && res.content) return res.content;
        return '';
    } catch (e) {
        if (retry > 0) return await request(url, ref, retry - 1);
        return '';
    }
}

function joinUrl(url) {
    if (!url) return '';
    url = String(url).replace(/&amp;/g, '&');
    if (url.indexOf('http') === 0) return url;
    if (url.indexOf('//') === 0) return 'https:' + url;
    if (url.indexOf('/') === 0) return HOST + url;
    return HOST + '/' + url;
}

function fixText(t) {
    return String(t || '').replace(/\u00a0/g, ' ').replace(/\s+/g, ' ').trim();
}


function toPlayId(href) {
    if (!href) return '';
    let h = String(href).replace(/&amp;/g, '&').trim();
    h = h.replace(/^https?:\/\/[^\/]+\//, '').replace(/^\/+/, '');
    
    let m = h.match(/^video\/(\d+)\.html(\?.*)?$/);
    if (m) return m[1] + (m[2] || '');
    return h;
}

function pageUrlOf(pid) {
    const p = String(pid || '').trim();
    let m = p.match(/^(\d+)(\?.*)?$/);
    if (m) return HOST + '/video/' + m[1] + '.html' + (m[2] || '');
    if (/^https?:\/\//.test(p)) return p;
    return HOST + '/' + p;
}

function cleanCeleb(t) {
    return String(t || '')
        .replace(/\s*([、,，\/；;])\s*/g, '$1')
        .replace(/\s+/g, ' ')
        .trim();
}



function parseVodList(html) {
    const $ = load(html || '');
    const list = [];
    const seen = {};

    let nodes = $('article.video-card');
    if (!nodes || nodes.length === 0) nodes = $('div.video-card');

    const pushCard = function (card) {
        const link = card.find('a.video-card-link').first();
        let href = link.attr('href') || '';
        if (!href) {
            const anyA = card.find('a[href*="/detail/"]').first();
            href = anyA.attr('href') || '';
        }
        if (!href) href = card.attr('data-url') || '';
        const m = String(href).match(/detail\/(\d+)\.html/);
        if (!m) return;
        const vid = m[1];
        if (seen[vid]) return;

        let name = link.attr('title') || fixText(link.text());
        if (!name) name = fixText(card.find('.as-h3').text());
        if (!name) name = fixText(card.find('img').first().attr('alt'));
        if (!name) return;
        name = fixText(name.replace(/^《|》$/g, ''));

        let pic = card.find('.video-card-media img').first().attr('src') || '';
        if (!pic) pic = card.find('img').first().attr('data-original') || card.find('img').first().attr('src') || '';
        if (!pic) return;

        const remarks = fixText(card.find('.video-status-badge').first().text());
        const score = fixText(card.find('.video-score').first().text()).replace(/[★\s]/g, '');
        const eyebrow = fixText(card.find('.eyebrow').first().text());
        const desc = fixText(card.find('.video-card-body p').first().text());
        const area = fixText(card.find('.video-card-meta span').first().text());

        const eParts = eyebrow.split('·').map(function (s) { return s.trim(); }).filter(Boolean);

        seen[vid] = 1;
        list.push({
            vod_id: vid,
            vod_name: name,
            vod_pic: joinUrl(pic),
            vod_remarks: remarks || (score ? '★' + score : ''),
            vod_type: eParts[0] || '',
            vod_year: eParts[1] || '',
            vod_area: area || '',
            vod_content: desc
        });
    };

    nodes.each(function (_, el) {
        pushCard($(el));
    });

   
    if (list.length === 0) {
        $('a[href*="/detail/"]').each(function (_, el) {
            const a = $(el);
            const m = String(a.attr('href') || '').match(/detail\/(\d+)\.html/);
            if (!m || seen[m[1]]) return;
            let name = fixText(a.attr('title') || a.text());
            if (!name || name.length > 40) name = fixText(a.find('img').attr('alt'));
            if (!name) return;
            let pic = a.find('img').attr('src') || a.find('img').attr('data-original') || '';
            seen[m[1]] = 1;
            list.push({ vod_id: m[1], vod_name: name, vod_pic: joinUrl(pic), vod_remarks: '' });
        });
    }

    return list;
}


const CLASSES = [
    { type_id: 'all', type_name: '全部' },
    { type_id: 'movie', type_name: '电影' },
    { type_id: 'tv', type_name: '电视剧' },
    { type_id: 'anime', type_name: '动漫' },
    { type_id: 'variety', type_name: '综艺' },
    { type_id: 'short', type_name: '短剧' },
    { type_id: 'sport', type_name: '体育' },
    { type_id: 'commentary', type_name: '影视解说' },
    { type_id: 'trailer', type_name: '预告片' }
];

const GENRES = {
    all: ['剧情', '真人秀', '喜剧', '惊悚', '爱情', '动作', '犯罪', '音乐', '歌舞', '晚会', '悬疑', '科幻', '冒险', '短片', '恐怖', '动画', '历史', '奇幻'],
    movie: ['剧情', '爱情', '喜剧', '动作', '犯罪', '恐怖', '惊悚', '冒险', '战争', '悬疑', '科幻', '奇幻', '历史', '古装', '歌舞', '西部', '家庭', '武侠'],
    tv: ['剧情', '爱情', '喜剧', '古装', '悬疑', '犯罪', '奇幻', '动作', '家庭', '战争', '历史', '惊悚', '科幻', '武侠', '冒险', '短片', '恐怖', '传记'],
    anime: ['动画', '剧情', '喜剧', '奇幻', '冒险', '动作', '科幻', '爱情', '家庭', '短片', '悬疑', '儿童', '运动', '古装', '犯罪', '武侠', '惊悚', '恐怖'],
    variety: ['真人秀', '音乐', '脱口秀', '爱情', '纪录', '歌舞', '喜剧', '剧情', '晚会', '运动', '悬疑', '儿童', '家庭', '冒险', '犯罪', '历史', '访谈', '生活'],
    short: ['爱情', '短片', '喜剧'],
    sport: [],
    commentary: ['剧情', '爱情', '喜剧', '动作', '犯罪', '惊悚', '悬疑', '传记', '历史', '冒险', '奇幻', '科幻', '家庭', '战争', '古装', '恐怖', '音乐', '武侠'],
    trailer: ['剧情', '喜剧', '动作', '冒险', '犯罪', '动画', '科幻', '悬疑', '奇幻', '爱情', '惊悚', '家庭', '纪录', '恐怖', '儿童', '音乐', '历史', '战争']
};

const REGIONS = ['中国大陆', '中国香港', '中国台湾', '美国', '日本', '韩国', '英国', '法国', '德国', '印度', '泰国', '俄罗斯', '西班牙', '加拿大', '其他'];
const LANGUAGES = ['普通话', '粤语', '英语', '日语', '韩语', '法语', '德语', '俄语', '意大利语', '泰语', '印地语', '其他'];
const YEARS = ['2029', '2028', '2027', '2026', '2025', '2024', '2023', '2022', '2021', '2020', '2019', '2018', '2017', '2016', '2015', '2014', '2013', '2012', '2011', '2010', 'older'];

function buildFilters(tid) {
    const arr = [];
    const genres = GENRES[tid] || [];
    if (genres.length > 0) {
        const g = [{ n: '全部', v: '' }];
        for (let i = 0; i < genres.length; i++) g.push({ n: genres[i], v: genres[i] });
        arr.push({ key: 'genre', name: '类型', value: g });
    }
    const r = [{ n: '全部', v: '' }];
    for (let i = 0; i < REGIONS.length; i++) r.push({ n: REGIONS[i], v: REGIONS[i] });
    arr.push({ key: 'region', name: '地区', value: r });

    const l = [{ n: '全部', v: '' }];
    for (let i = 0; i < LANGUAGES.length; i++) l.push({ n: LANGUAGES[i], v: LANGUAGES[i] });
    arr.push({ key: 'language', name: '语言', value: l });

    const y = [{ n: '全部', v: '' }];
    for (let i = 0; i < YEARS.length; i++) y.push({ n: YEARS[i] === 'older' ? '更早' : YEARS[i], v: YEARS[i] });
    arr.push({ key: 'year', name: '年份', value: y });

    arr.push({
        key: 'state', name: '状态', value: [
            { n: '全部', v: '' },
            { n: '连载中', v: 'ongoing' },
            { n: '已完结', v: 'completed' }
        ]
    });
    arr.push({
        key: 'sort', name: '排序', value: [
            { n: '最近更新', v: 'latest' },
            { n: '来源热度', v: 'popular' },
            { n: '本站热门', v: 'site' },
            { n: '来源评分', v: 'rating' },
            { n: '上映日期', v: 'release' }
        ]
    });
    return arr;
}



function init(cfg) {
    siteKey = cfg.skey;
    siteType = cfg.stype;
    sourceKey = cfg.sourceKey;
    ext = cfg.ext || '';
    if (ext && ext.indexOf('http') === 0) HOST = ext.replace(/\/+$/, '');
}

async function home(filter) {
    const filters = {};
    for (let i = 0; i < CLASSES.length; i++) {
        filters[CLASSES[i].type_id] = buildFilters(CLASSES[i].type_id);
    }
    return JSON.stringify({ class: CLASSES, filters: filters });
}

async function homeVod() {
    try {
        const html = await request(HOST + '/', HOST + '/');
        return JSON.stringify({ list: parseVodList(html) });
    } catch (e) {
        return JSON.stringify({ list: [] });
    }
}

async function category(tid, pg, filter, extend) {
    pg = parseInt(pg, 10) || 1;
    extend = extend || {};
    const channel = tid === 'all' ? '' : String(tid || '');

    let base = HOST + '/library';
    if (channel) base += '/' + channel;

    const qs = [];
    if (extend.genre) qs.push('genre=' + encodeURIComponent(extend.genre));
    if (extend.region) qs.push('region=' + encodeURIComponent(extend.region));
    if (extend.language) qs.push('language=' + encodeURIComponent(extend.language));
    if (extend.year) qs.push('year=' + encodeURIComponent(extend.year));
    if (extend.state) qs.push('state=' + encodeURIComponent(extend.state));
    if (extend.sort && extend.sort !== 'latest') qs.push('sort=' + encodeURIComponent(extend.sort));
    if (pg > 1) qs.push('page=' + pg);

    const url = base + (qs.length > 0 ? '?' + qs.join('&') : '');

    try {
        const html = await request(url, HOST + '/');
        const list = parseVodList(html);
        const hasNext = (html.indexOf('rel="next"') >= 0) || list.length >= 24;
        return JSON.stringify({
            page: pg,
            pagecount: hasNext ? pg + 1 : pg,
            limit: 24,
            total: hasNext ? (pg + 1) * 24 : (pg - 1) * 24 + list.length,
            list: list
        });
    } catch (e) {
        return JSON.stringify({ page: pg, pagecount: 0, limit: 24, total: 0, list: [] });
    }
}


async function fetchEpisodePage(slug, line, page) {
    const url = HOST + '/video/' + slug + '/episodes?line=' + line + '&page=' + page + '&format=html';
    const body = await request(url, HOST + '/video/' + slug);
    if (!body) return [];
    let html = body;
    try {
        const j = JSON.parse(body);
        if (j && j.html) html = j.html;
    } catch (e) { }
    const $f = load(html || '');
    const arr = [];
    $f('a.episode-link').each(function (_, el) {
        const a = $f(el);
        const href = a.attr('href') || '';
        let name = fixText(a.text());
        const pid = toPlayId(href);
        if (!pid) return;
        if (!name) name = '第' + (arr.length + 1) + '集';
        arr.push({ name: name, pid: pid });
    });
    return arr;
}

async function detail(id) {
    try {
        const html = await request(HOST + '/detail/' + id + '.html', HOST + '/');
        if (!html) return JSON.stringify({ list: [] });
        const $ = load(html);

        const vod = { vod_id: id };
        vod.vod_name = fixText($('h1#video-detail-heading').text()) || fixText($('h1').first().text());
        vod.vod_pic = joinUrl($('img.film-detail-poster').first().attr('src') || '');

       
        let summary = '';
        $('.film-detail-actions p').each(function (_, el) {
            const t = fixText($(el).text());
            if (t.indexOf('·') >= 0) summary = t;
        });
        const parts = summary.split('·').map(function (s) { return s.trim(); }).filter(Boolean);
        if (parts.length > 0) vod.vod_type = parts[0];
        if (parts.length > 1 && /^\d{4}$/.test(parts[1])) vod.vod_year = parts[1];
        if (parts.length > 2) vod.vod_area = parts[2];
        if (parts.length > 3) vod.vod_remarks = parts[3];

        
        let alias = '';
        $('.detail-main p.lead').each(function (_, el) {
            const t = fixText($(el).text());
            if (t && t !== vod.vod_name) alias = t;
        });

        
        $('.facts span').each(function (_, el) {
            const t = fixText($(el).text());
            if (!t || t.indexOf('更新于') >= 0) return;
            if (/^\d{4}$/.test(t)) { vod.vod_year = t; return; }
            if (t.indexOf('来源评分') >= 0) { vod.vod_score = t.replace('来源评分', '').trim(); return; }
            if (t.indexOf('次浏览') >= 0) { vod.vod_hits = t.replace('次浏览', '').trim(); return; }
            if (t.indexOf('集') >= 0 && t.length <= 12) { if (!vod.vod_remarks) vod.vod_remarks = t; return; }
            if (/(语|话)$/.test(t) && t.length <= 10) { vod.vod_lang = t; return; }
        });

        
        $('dl.fact-grid > div').each(function (_, el) {
            const dt = fixText($(el).find('dt').first().text());
            const dd = fixText($(el).find('dd').first().text());
            if (!dt || !dd) return;
            if (dt === '导演') vod.vod_director = cleanCeleb(dd);
            else if (dt === '演员') vod.vod_actor = cleanCeleb(dd);
            else if (dt === '编剧') vod.vod_writer = cleanCeleb(dd);
            else if (dt === '分类') { if (!vod.vod_type) vod.vod_type = dd; }
            else if (dt === '标签') vod.vod_tag = cleanCeleb(dd);
            else if (dt === '年份') { if (!vod.vod_year) vod.vod_year = dd; }
            else if (dt === '地区') { if (!vod.vod_area) vod.vod_area = dd; }
        });

       
        const copies = [];
        $('p.detail-copy').each(function (_, el) {
            const t = fixText($(el).text());
            if (t) copies.push(t);
        });
        const contentParts = [];
        if (alias) contentParts.push('别名：' + alias);
        if (vod.vod_director) contentParts.push('导演：' + vod.vod_director);
        if (vod.vod_actor) contentParts.push('主演：' + vod.vod_actor);
        if (copies.length > 0) contentParts.push(copies[0]);
        if (copies.length > 1) contentParts.push(copies[1]);
        vod.vod_content = contentParts.join('\n');

       
        let eps = [];
        let watchHtml = '';
        if (EP_CACHE[id]) {
            watchHtml = EP_CACHE[id];
        } else {
            watchHtml = await request(HOST + '/video/' + id + '.html', HOST + '/');
            if (watchHtml) EP_CACHE[id] = watchHtml;
        }

        if (watchHtml) {
            const $w = load(watchHtml);
            const total = parseInt($w('[data-episode-pages]').attr('data-total') || '0', 10) || 0;

            $w('a.episode-link').each(function (_, el) {
                const a = $w(el);
                const pid = toPlayId(a.attr('href') || '');
                if (!pid) return;
                let name = fixText(a.text());
                if (!name) name = '第' + (eps.length + 1) + '集';
                eps.push({ name: name, pid: pid });
            });

            if (total > eps.length) {
                const nextUrl = $w('[data-load-episodes]').attr('data-next-url') || '';
                const mm = String(nextUrl).replace(/&amp;/g, '&').match(/\/video\/([^\/]+)\/episodes\?line=([^&]+)/);
                if (mm) {
                    const slug = mm[1];
                    const line = mm[2];
                    const pages = Math.min(Math.ceil(total / 50), 40);
                    let page = 2;
                    while (page <= pages) {
                        const batch = [];
                        for (let k = 0; k < 6 && page <= pages; k++, page++) {
                            batch.push(fetchEpisodePage(slug, line, page));
                        }
                        const results = await Promise.all(batch);
                        for (let b = 0; b < results.length; b++) {
                            const arr = results[b] || [];
                            for (let c = 0; c < arr.length; c++) eps.push(arr[c]);
                        }
                    }
                }
            }
        }

        if (eps.length === 0) eps = [{ name: '正片', pid: String(id) }];

        const from = [];
        const urls = [];
        const seenPid = {};
        const finalEps = [];
        for (let i = 0; i < eps.length; i++) {
            const e = eps[i];
            const key = e.pid + '|' + e.name;
            if (seenPid[key]) continue;
            seenPid[key] = 1;
            finalEps.push(String(e.name).replace(/[$#]/g, ' ') + '$' + e.pid);
        }
        from.push('在线播放');
        urls.push(finalEps.join('#'));

        vod.vod_play_from = from.join('$$$');
        vod.vod_play_url = urls.join('$$$');

        return JSON.stringify({ list: [vod] });
    } catch (e) {
        return JSON.stringify({ list: [] });
    }
}

async function search(wd, quick, pg) {
    pg = parseInt(pg, 10) || 1;
    const cacheKey = wd + '_' + pg;
    if (SEARCH_CACHE[cacheKey]) return SEARCH_CACHE[cacheKey];

    try {
        let url = HOST + '/search?q=' + encodeURIComponent(wd);
        if (pg > 1) url += '&page=' + pg;
        const html = await request(url, HOST + '/');
        const list = parseVodList(html);
        const result = JSON.stringify({
            page: pg,
            pagecount: list.length >= 24 ? pg + 1 : pg,
            limit: 24,
            total: list.length >= 24 ? (pg + 1) * 24 : (pg - 1) * 24 + list.length,
            list: list
        });
        SEARCH_CACHE[cacheKey] = result;
        return result;
    } catch (e) {
        return JSON.stringify({ page: pg, pagecount: 0, limit: 24, total: 0, list: [] });
    }
}



function normalizeMediaUrl(u) {
    let s = String(u || '').trim();
    try { s = decodeURIComponent(s); } catch (e) { }
    try { s = encodeURI(s); } catch (e) { }
    return s;
}


async function probePlayable(url) {
    const alt = url.indexOf('https://') === 0
        ? 'http://' + url.slice(8)
        : (url.indexOf('http://') === 0 ? 'https://' + url.slice(7) : '');

    const tryOnce = async function (u) {
        try {
            const res = await req(u, {
                method: 'get',
                headers: { 'User-Agent': UA },
                timeout: 8000
            });
            const body = (res && res.content) || '';
            return String(body).indexOf('#EXTM3U') >= 0;
        } catch (e) {
            return false;
        }
    };

   
    for (let round = 0; round < 2; round++) {
        if (await tryOnce(url)) return { url: url, header: { 'User-Agent': UA } };
    }
   
    if (alt) {
        if (await tryOnce(alt)) return { url: alt, header: { 'User-Agent': UA } };
    }
    return null;
}

async function play(flag, id, flags) {
    const pid = String(id || '').trim();
    const cacheKey = pid;
    if (PLAY_CACHE[cacheKey]) return PLAY_CACHE[cacheKey];

    const pageUrl = pageUrlOf(pid);
    let result = '';

    try {
        const html = await request(pageUrl, HOST + '/');
        let embedPath = '';
        const m = String(html).match(/src="(\/video\/[^"]*?\/embed[^"]*)"/);
        if (m) embedPath = m[1].replace(/&amp;/g, '&');

        let fallbackFrame = '';
        let m3u8Candidates = [];

        if (embedPath) {
            const embedUrl = joinUrl(embedPath);
            const embedHtml = await request(embedUrl, pageUrl);

            const c = String(embedHtml).match(/const\s+candidates\s*=\s*(\[[\s\S]*?\])\s*;/);
            if (c) {
                let arr = null;
                try { arr = JSON.parse(c[1]); } catch (e) { arr = null; }
                if (arr && arr.length) {
                    for (let i = 0; i < arr.length; i++) {
                        const item = arr[i] || {};
                        const raw = String(item.url || '');
                        if (!raw) continue;
                        if (!fallbackFrame) fallbackFrame = raw;
                        const um = raw.match(/[?&]url=([^&]+)/);
                        if (um) {
                            const media = normalizeMediaUrl(um[1]);
                            if (/^https?:\/\//.test(media)) m3u8Candidates.push(media);
                        }
                    }
                }
            }
            if (!fallbackFrame) {
                const fm = String(embedHtml).match(/src="(https?:\/\/[^"]+)"/);
                if (fm) fallbackFrame = fm[1].replace(/&amp;/g, '&');
            }
        }

        for (let i = 0; i < m3u8Candidates.length; i++) {
            const media = m3u8Candidates[i];
            const hit = await probePlayable(media);
            if (hit) {
                result = JSON.stringify({ parse: 0, url: hit.url, header: hit.header });
                PLAY_CACHE[cacheKey] = result;
                return result;
            }
        }

        if (m3u8Candidates.length > 0) {
            
            return JSON.stringify({
                parse: 0,
                url: m3u8Candidates[0],
                header: { 'User-Agent': UA }
            });
        }

        if (fallbackFrame) {
            result = JSON.stringify({ parse: 1, url: fallbackFrame, header: { 'User-Agent': UA } });
            PLAY_CACHE[cacheKey] = result;
            return result;
        }

        result = JSON.stringify({ parse: 1, url: pageUrl, header: { 'User-Agent': UA } });
        return result;
    } catch (e) {
        return JSON.stringify({ parse: 1, url: pageUrl, header: { 'User-Agent': UA } });
    }
}

export function __jsEvalReturn() {
    return { init, home, homeVod, category, detail, search, play };
}
