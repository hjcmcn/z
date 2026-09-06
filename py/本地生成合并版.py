# -*- coding: utf-8 -*-
"""
ss.py - TVBox配置生成器
强制生成到固定路径 /storage/emulated/0/VodPlus/wwwroot/ss.json
"""

import os
import json
import sys
import base64
import re

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider(object):
        pass
# ==================== 用户可修改配置 ====================
# 主目录：扫描目录、生成配置和设置文件通常统一放在此目录下。
OUTPUT_PATH = "/storage/emulated/0/VodPlus/wwwroot/vodplus.json"
DEFAULT_OUTPUT_PATH = OUTPUT_PATH
SETTINGS_PATH = "/storage/emulated/0/VodPlus/wwwroot/vodplus_settings.json"

# 存储根目录：用于将扫描到的绝对路径转换为宿主可读取的 file:// 地址。
STORAGE_ROOT = '/storage/emulated/0'
# PHP 服务默认端口：自动检测失败时使用该端口。
DEFAULT_PHP_PORT = 8901
# 最大扫描深度：0 表示仅扫描当前目录，5 表示最多进入五层子目录。
MAX_SCAN_DEPTH = 5
# 默认扫描文件类型：可在“扫描设置”弹窗中独立开关。
SCAN_FILE_TYPES = {'py': 'PY', 'js': 'JS', 'wv.js': 'WV.JS', 'php': 'PHP', 'html': 'HTML', 'xbpq': 'XBPQ', 'xyq': 'XYQ', 'json': 'JSON', 'txt': 'TXT', 'm3u': 'M3U', 'db': 'DB', 'zip': 'ZIP', 'pkg': 'PKG'}
DEFAULT_SCAN_EXTENSIONS = list(SCAN_FILE_TYPES)
# 默认扫描模式：source 为站源模式，file 为文件模式。
DEFAULT_SCAN_MODE = 'source'
SCAN_MODE_LABELS = {'source': '站源模式', 'file': '文件模式'}
# 18+ 默认开关和标签：关闭时不扫描路径链中命中任一标签的文件夹。
DEFAULT_ADULT_ENABLED = False
DEFAULT_ADULT_TAGS = ['[密]', '[18]']
# 直播目录名：该目录及其子目录的支持文件会生成 lives，而不是 sites。
LIVE_DIR_NAME = '直播文件'

# 置顶站点：始终排在自动扫描站点之前。
PINNED_SITES = [
      {
            "key": "lf_js_search",
            "name": "🏠  豆瓣[首页]",
            "api": "./lib/js/lf_search3_min.js",
            "type": 3,
            "searchable": 0,
            "changeable": 1,
            "quickSearch": 0,
            "filterable": 0
        },
     {'key': '本地加载', 'name': '⭐本地加载[设置]', 'type': 3, 'api': './vodplus.py', 'searchable': 1, 'quickSearch': 1, 'filterable': 1},
    {'key': '⚙️Nostrʷᵖ|配置', 'name': '⚙️Nostrʷᵖ|配置', 'type': 3, 'api': 'csp_Config', 'jar': './lib/vox.jar', 'searchable': 0, 'changeable': 0},
         
        {
            "key": "config0",
            "name": "🔌  切换本地包",
            "type": 3,
            "searchable": 0,
            "quickSearch": 0,
            "changeable": 0,
            "api": "./lib/切换本地包/start.py"
        },
        {
            "key": "php-server",
            "name": "🌟  全能王",
            "type": 3,
            "api": "csp_PhpServer",
            "tmeout": 120,
            "searchable": 0,
            "quickSearch": 0,
            "changeable": 0,
            "filterable": 1,
            "jar": "./lib/fm_xMydev.jar"
        },
        {
            "key": "config8",
            "name": "📁  资源管理",
            "type": 3,
            "searchable": 0,
            "quickSearch": 0,
            "changeable": 0,
            "api": "./资源管理.py"
        },
        {
            "key": "🕍在线转本地",
            "name": "🕍在线转本地",
            "type": 3,
            "style": {
                "type": "list",
                "ratio": 1.43
            },
            "api": "./lib/在线转本地/在线转本地@v3[pro版].py",
            "ext": {
                "config_file": "./lib/在线转本地/down_config.json"
            }
        },
        {
            "key": "XueLuo",
            "name": "❄️雪咯[音乐]",
            "type": 3,
            "api": "csp_XueLuo",
            "jar": "./lib/yt.jar",
            "searchable": 0,
            "quickSearch": 0,
            "filterable": 0,
            "changeable": 0,
            "indexs": 0,
            "style": {
                "type": "list"
            }
        },
        {
            "key": "WvMcp",
            "name": "wv | WvMcp",
            "api": "csp_WvMcp",
            "type": "3",
            "jar": "./lib/WvSpider.jar"
        },
        {
            "key": "文件在这个目录下写死了/storage/emulated/0/TVData/db/song_9c8ec.db",
            "name": "🎤  爱KTV",
            "type": 3,
            "api": "csp_爱KTV",
            "searchable": 1,
            "quickSearch": 1,
            "changeable": 1,
            "filterable": 1,
            "jar": "./lib/爱KTV.jar"
        },
        {
            "key": "push_agent",
            "name": "Push | 推送",
            "type": 3,
            "hide": 1,
            "api": "csp_Push"
        }
]

# 扫描根目录：按列表顺序扫描，支持绝对路径和相对主目录路径。
SCAN_DIRS = ['/storage/emulated/0/VodPlus/wwwroot/']
# 屏蔽文件夹：命中名称的目录及其全部子目录不会扫描。
NO_SCAN_DIRS = {'webview', '直播转点播辅助文件', '全能王', '道长', 'lib', 'labeditor', 'pycache', '.git', '.idea'}
# 不显示的源文件：命中名称的文件不会生成 site。
EXCLUDE_FILES = {'index.php', 'test_runner.php', 'config.php', 'start.py', 'start.php', 'T4Proxy.php', 'FileExplorer.php', 'ss.json'}
# 特殊目录关键词：目录名命中后，其所有子目录都继承对应解析类型。
XBPQ_DIR_KEYWORDS = ['PQ类']
XYQ_DIR_KEYWORDS = ['YQ类']
DRPY2_DIR_KEYWORDS = ['JS[Drpy]']
# 本地包目录关键词：目录名命中后，其所有子目录都继承"本地包"类型（zip/pkg/json 等按文件包处理）。
LOCAL_PACKAGE_DIR_KEYWORDS = ['本地包', 'package', 'pkg', '包']

# 首页卡片图标：替换链接即可修改对应功能图标。
LOCAL_UI_ICONS = {
    # 本地加载：扫描本地目录并生成 TVBox 配置。
    'scan': 'https://cdn.jsdelivr.net/gh/tabler/tabler-icons/icons/outline/refresh.svg',
    # 扫描目录：查看或修改本地源文件扫描路径。
    'folder': 'https://cdn.jsdelivr.net/gh/tabler/tabler-icons/icons/outline/folder.svg',
    # 状态提示：显示操作结果、说明和错误信息。
    'status': 'https://cdn.jsdelivr.net/gh/tabler/tabler-icons/icons/outline/info-circle.svg',
    # 生成文件：查看或修改 JSON 输出文件及其保存位置。
    'download': 'https://cdn.jsdelivr.net/gh/tabler/tabler-icons/icons/outline/file-download.svg',
    # 屏蔽设置：管理屏蔽文件夹、不显示源文件和18+标签。
    'block': 'https://cdn.jsdelivr.net/gh/tabler/tabler-icons/icons/outline/eye-off.svg',
    # 解析设置：管理解析名称、解析URL及启用状态。
    'parse': 'https://cdn.jsdelivr.net/gh/tabler/tabler-icons/icons/outline/link.svg'
}

# 手动站点：始终排在自动扫描站点之后。
MANUAL_SITES = [{'key': '熊猫视频', 'name': '🔞熊猫视频[采集]', 'type': 3, 'api': 'csp_XMVideo', 'jar': './jar/custom_spider.jar', 'searchable': 1, 'filterable': 1}]
# 内置直播：始终排在扫描到的直播源之前。
DEFAULT_LIVES = [{'name': '十八摸', 'type': 0, 'url': 'https://down.nigx.cn/mpimg.cn/down.php/25da10b0cb7b90d422ae22852bd7d414.txt', 'playerType': 1, 'ua': 'okhttp/3.12.13', 'epg': 'https://epg.imxd.top/?ch={name}&date={date}', 'logo': 'https://live.imxd.top/logo/{name}.png'}]
# 配置外观和 Spider JAR。
CONFIG_SPIDER = './lib/新xyqxbpq.jar'
CONFIG_LOGO = 'https://gss0.baidu.com/-vo3dSag_xI4khGko9WTAnF6hhy/zhidao/pic/item/a2cc7cd98d1001e99498eddaba0e7bec55e797bb.jpg'
CONFIG_WALLPAPER = 'https://p0.itc.cn/q_70/images03/20200828/8a58426e820e4c3ea4da42a3948f6f06.gif'


# ==================== 工具函数 ====================

def decode_base64_file(filepath):
    """
    尝试将文件内容作为 Base64 编码的 JSON 进行解码。
    如果解码成功且结果为合法 JSON，则覆盖原文件。
    否则静默跳过（非 Base64 或非 JSON）。
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        
        # 检查是否已是JSON，如果是则跳过
        try:
            json.loads(content)
            return
        except:
            pass
        
        # 尝试 Base64 解码（自动处理填充）
        decoded_bytes = base64.b64decode(content, validate=True)
        decoded_str = decoded_bytes.decode('utf-8')
        # 验证是否为合法 JSON
        json.loads(decoded_str)
        # 解码成功且为 JSON，覆盖写入原文件
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(decoded_str)
        print(f"✅ Base64 解码成功: {filepath}", file=sys.stderr)
    except Exception:
        # 不是 Base64 或解码后不是有效 JSON，不做任何操作
        pass

def fix_types(obj):
    """递归修正所有 type 为整数"""
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            if k == 'type' and isinstance(v, str) and v.isdigit():
                obj[k] = int(v)
            else:
                fix_types(v)
    elif isinstance(obj, list):
        for item in obj:
            fix_types(item)

# ==================== 构建站点 ====================

# ==================== 扫描状态 ====================

ROOT_DIR = os.path.dirname(OUTPUT_PATH)
SELF_FILE = os.path.basename(__file__)
_SCAN_CACHE = None


# ==================== 扫描工具函数 ====================

def detect_php_port():
    for cmd in ('ps aux', 'pgrep -lf php', 'ps aux | grep php | grep -v grep'):
        try:
            output = os.popen(cmd + ' 2>/dev/null').read()
            for line in output.splitlines():
                if 'php' not in line.lower() or 'grep' in line.lower():
                    continue
                match = re.search(r':(\d{4,5})', line)
                if match:
                    port = int(match.group(1))
                    if 1024 <= port <= 65535:
                        return port
        except Exception:
            pass
    return DEFAULT_PHP_PORT

def get_file_extension_info(filename):
    lower = filename.lower()
    if lower.endswith('.wv.js'):
        return {'full': 'wv.js', 'simple': 'js', 'name': filename[:-6]}
    name, ext = os.path.splitext(filename)
    ext = ext[1:].lower()
    return {'full': ext, 'simple': ext, 'name': name}

def remove_all_tags(text):
    return re.sub(r'\[[^\]]*\]', '', text or '')

def extract_all_tags(text):
    return re.findall(r'\[[^\]]+\]', text or '')

def output_base_dir():
    try:
        return os.path.realpath(os.path.abspath(os.path.dirname(current_output_path())))
    except Exception:
        return os.path.realpath(os.path.abspath(ROOT_DIR))

def file_url(path):
    # 参考本地影仓 v7.0 的 _file_url：不复制源文件，转换为宿主可解析的 file:// 引用。
    absolute = os.path.realpath(os.path.abspath(os.path.expanduser(str(path))))
    storage_root = os.path.realpath(os.path.abspath(STORAGE_ROOT))
    try:
        relative = os.path.relpath(absolute, storage_root).replace(os.sep, '/')
    except Exception:
        relative = ''
    if relative and relative != '..' and not relative.startswith('../'):
        return 'file://' + relative.lstrip('/')
    return 'file://' + absolute

def rel_path(path):
    abs_path = os.path.realpath(os.path.abspath(path))
    base_dir = output_base_dir()
    try:
        # 输出文件同目录/子目录内的源，继续用 ./ 相对路径。
        # 输出目录外的源，不能用 ../ 或裸 /storage/...，否则部分壳能扫到但加载不可用；改用 file://。
        if os.path.commonpath([abs_path, base_dir]) == base_dir:
            rel = './' + os.path.relpath(abs_path, base_dir).replace(os.sep, '/')
            return './' if rel == './.' else rel
    except Exception:
        pass
    return file_url(abs_path)

def abs_scan_path(path):
    path = os.path.expanduser(str(path or '').strip())
    return os.path.abspath(path if os.path.isabs(path) else os.path.join(ROOT_DIR, path))

def split_scan_dirs(value):
    raw = str(value or '').strip()
    for sep in ('｜', '，', '；', ';', '、', ','):
        raw = raw.replace(sep, '|')
    raw = raw.replace('\r', '\n').replace('\n', '|')
    result = []
    for item in raw.split('|'):
        item = item.strip().strip('\"').strip("'")
        if item and item not in result:
            result.append(item)
    return result

def is_supported_file(ext_info, is_xbpq=False, is_xyq=False, is_drpy=False, is_pkg=False):
    ext = ext_info['full']
    selected = set(current_scan_extensions())
    if current_scan_mode() == 'source':
        if ext == 'json':
            if is_xbpq:
                return 'xbpq' in selected
            if is_xyq:
                return 'xyq' in selected
            return False
        return ext in ('py', 'js', 'wv.js', 'php', 'html') and ext in selected
    if ext == 'json':
        return not (is_xbpq or is_xyq) and 'json' in selected
    if ext in ('txt', 'm3u', 'db', 'zip', 'pkg'):
        return not (is_xbpq or is_xyq or is_drpy) and ext in selected
    return False

def is_runtime_generated_file(path):
    try:
        ap = os.path.abspath(path)
        protected = {
            os.path.abspath(DEFAULT_OUTPUT_PATH),
            os.path.abspath(current_output_path()) if 'current_output_path' in globals() else os.path.abspath(DEFAULT_OUTPUT_PATH),
            os.path.abspath(SETTINGS_PATH)
        }
        return ap in protected
    except Exception:
        return False

def get_nearest_tag(tags):
    return tags[-1] if tags else ''
def scan_sort_key(name):
    try:
        return str(name or '').casefold().encode('gbk', 'replace')
    except Exception:
        return str(name or '').casefold()
def keyword_hit(dirname, keywords):
    return any(keyword in dirname for keyword in keywords)

def check_special_directory(dirname, parent_xbpq=False, parent_xyq=False, parent_drpy=False, parent_pkg=False):
    is_xbpq = parent_xbpq or keyword_hit(dirname, XBPQ_DIR_KEYWORDS)
    is_xyq = parent_xyq or keyword_hit(dirname, XYQ_DIR_KEYWORDS)
    is_drpy = parent_drpy or keyword_hit(dirname, DRPY2_DIR_KEYWORDS)
    is_pkg = parent_pkg or keyword_hit(dirname, LOCAL_PACKAGE_DIR_KEYWORDS)
    return is_xbpq, is_xyq, is_drpy, is_pkg

def drpy_api_path():
    fast = os.path.join(ROOT_DIR, 'lib/lib/drpy2-fast.min.js')
    normal = os.path.join(ROOT_DIR, 'lib/drpy2.min.js')
    if os.path.exists(fast):
        return './lib/lib/drpy2-fast.min.js'
    if os.path.exists(normal):
        return './lib/drpy2.min.js'
    return './lib/drpy2.min.js'

def make_full_name(name, tag, label):
    clean_name = remove_all_tags(name).strip() or name
    return f'{clean_name}{tag}({label.upper()})'

def deduplicate_sites(sites):
    seen = {}
    result = []
    for site in sites:
        key = site.get('key')
        if not key:
            result.append(site)
            continue
        if key in seen:
            seen[key] += 1
            new_key = f'{key}_{seen[key]}'
            while new_key in seen:
                seen[key] += 1
                new_key = f'{key}_{seen[key]}'
            site = dict(site)
            site['key'] = new_key
            site['name'] = f"{site.get('name', key)} ({seen[key]})"
            seen[new_key] = 0
        else:
            seen[key] = 0
        result.append(site)
    return result


# ==================== 站点构建规则 ====================

def build_site_config(name, top_tag, ext_info, local_path, php_api_prefix, is_xbpq=False, is_xyq=False, is_drpy=False, is_pkg=False):
    ext = ext_info['full']
    simple_ext = ext_info['simple']

    if is_xbpq and ext == 'json':
        full = make_full_name(name, top_tag, 'xbpq')
        return {'key': full, 'name': full, 'type': 3, 'api': 'csp_XBPQ', 'searchable': 1, 'quickSearch': 1, 'filterable': 1, 'changeable': 1, 'ext': local_path}

    if is_xyq and ext == 'json':
        full = make_full_name(name, top_tag, 'XYQ')
        return {'key': full, 'name': full, 'type': 3, 'api': 'csp_XYQHiker', 'searchable': 1, 'quickSearch': 1, 'filterable': 1, 'changeable': 1, 'ext': local_path}

    if is_drpy and ext == 'js':
        full = make_full_name(name, top_tag, 'js')
        return {'key': full, 'name': full, 'type': 3, 'api': drpy_api_path(), 'searchable': 1, 'quickSearch': 1, 'filterable': 1, 'changeable': 1, 'order_num': 0, 'ext': local_path}


    if ext == 'php':
        full = make_full_name(name, top_tag, 'php')
        clean_path = local_path[2:] if local_path.startswith('./') else local_path
        return {'key': full, 'name': full, 'type': 4, 'api': php_api_prefix + '/' + clean_path, 'searchable': 1, 'quickSearch': 1, 'filterable': 1, 'changeable': 1}

    if ext == 'wv.js':
        full = make_full_name(name, top_tag, 'wv.js')
        return {'key': full, 'name': full, 'type': 3, 'api': 'csp_WvSpider', 'jar': './jar/WvSpider.jar', 'searchable': 1, 'quickSearch': 1, 'filterable': 1, 'switchable': 1, 'ext': local_path}

    if ext == 'py':
        full = make_full_name(name, top_tag, 'py')
        return {'key': full, 'name': full, 'type': 3, 'api': local_path, 'searchable': 1, 'quickSearch': 1, 'filterable': 1, 'switchable': 1}

    if ext == 'js':
        full = make_full_name(name, top_tag, 'js')
        return {'key': full, 'name': full, 'type': 3, 'api': local_path, 'searchable': 1, 'quickSearch': 1, 'filterable': 1, 'switchable': 1}

    if ext == 'html':
        full = make_full_name(name, top_tag, 'html')
        return {'key': full, 'name': full, 'type': 3, 'api': 'csp_Nostr', 'searchable': 1, 'quickSearch': 1, 'filterable': 1, 'switchable': 1, 'homePage': local_path}

    if ext in ('txt', 'm3u', 'json', 'db', 'zip', 'pkg') or simple_ext in ('txt', 'm3u', 'json', 'db', 'zip', 'pkg'):
        full = make_full_name(name, top_tag, ext)
        return {'key': full, 'name': full, 'type': 3, 'api': 'csp_FileSpider', 'jar': './lib/WvSpider.jar', 'searchable': 0, 'quickSearch': 0, 'filterable': 0, 'switchable': 0, 'changeable': 0, 'ext': local_path}

    full = make_full_name(name, top_tag, ext or 'file')
    return {'key': full, 'name': full, 'type': 3, 'api': 'csp_FileSpider', 'jar': './lib/WvSpider.jar', 'searchable': 0, 'quickSearch': 0, 'filterable': 0, 'switchable': 0, 'changeable': 0, 'ext': local_path}


# ==================== 递归扫描引擎 ====================

def scan_directory_recursive(path, scanned_sites, scanned_lives, php_api_prefix, current_depth=0, nearest_tag='', parent_xbpq=False, parent_xyq=False, parent_drpy=False, parent_live=False, parent_pkg=False):
    if current_depth > MAX_SCAN_DEPTH or not os.path.isdir(path):
        return

    current_dir_name = os.path.basename(path)
    if not current_adult_enabled() and any(tag in current_dir_name for tag in current_adult_tags()):
        return
    current_tags = extract_all_tags(current_dir_name)
    current_nearest_tag = get_nearest_tag(current_tags) or nearest_tag
    top_tag = current_nearest_tag

    is_live = parent_live or (current_dir_name == LIVE_DIR_NAME)
    is_xbpq, is_xyq, is_drpy, is_pkg = check_special_directory(current_dir_name, parent_xbpq, parent_xyq, parent_drpy, parent_pkg)

    try:
        items = sorted(os.listdir(path), key=scan_sort_key)
    except Exception as e:
        print(f'⚠️ 扫描目录失败 {path}: {e}', file=sys.stderr)
        return

    for item in items:
        if item in current_blocked_dirs():
            continue

        full_path = os.path.join(path, item)

        if os.path.isdir(full_path):
            scan_directory_recursive(full_path, scanned_sites, scanned_lives, php_api_prefix, current_depth + 1, current_nearest_tag, is_xbpq, is_xyq, is_drpy, is_live, is_pkg)
            continue

        if item in current_excluded_files() or is_runtime_generated_file(full_path):
            continue

        ext_info = get_file_extension_info(item)
        ext = ext_info['full']

        if not is_supported_file(ext_info, is_xbpq, is_xyq, is_drpy, is_pkg):
            continue

        if ext == 'json' and (is_xbpq or is_xyq):
            decode_base64_file(full_path)

        local_path = rel_path(full_path)
        name = remove_all_tags(ext_info['name']).strip() or ext_info['name']

        if is_live:
            scanned_lives.append({'name': name + top_tag, 'type': 0, 'url': local_path, 'playerType': 2, 'epg': 'http://epg.51zmt.top:8000/api/diyp/?ch={name}&date={date}', 'logo': f'https://11.112114.xyz/logo/{name}.png', 'ua': ''})
            continue

        site = build_site_config(name, top_tag, ext_info, local_path, php_api_prefix, is_xbpq, is_xyq, is_drpy, is_pkg)
        scanned_sites.append(site)


# ==================== 设置读写与生成动作 ====================

def default_settings():
    return {
        'output_path': DEFAULT_OUTPUT_PATH,
        'scan_dirs': list(SCAN_DIRS),
        'scan_enabled_dirs': list(SCAN_DIRS),
        'scan_extensions': list(DEFAULT_SCAN_EXTENSIONS),
        'scan_mode': DEFAULT_SCAN_MODE,
        'adult_enabled': DEFAULT_ADULT_ENABLED,
        'blocked_dirs': sorted(NO_SCAN_DIRS, key=scan_sort_key),
        'excluded_files': sorted(EXCLUDE_FILES, key=scan_sort_key),
        'adult_tags': list(DEFAULT_ADULT_TAGS),
        'parse_entries': default_parse_entries()
    }

def load_settings():
    data = default_settings()
    try:
        if os.path.exists(SETTINGS_PATH):
            with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
                saved = json.load(f)
            if isinstance(saved, dict):
                output_path = str(saved.get('output_path') or '').strip()
                if output_path:
                    data['output_path'] = output_path
                if isinstance(saved.get('scan_dirs'), list):
                    dirs = [str(x).strip() for x in saved['scan_dirs'] if str(x).strip()]
                    data['scan_dirs'] = dirs
                    if 'scan_enabled_dirs' not in saved:
                        data['scan_enabled_dirs'] = list(dirs)
                if isinstance(saved.get('scan_enabled_dirs'), list):
                    data['scan_enabled_dirs'] = [str(x).strip() for x in saved['scan_enabled_dirs'] if str(x).strip()]
                if isinstance(saved.get('scan_extensions'), list):
                    data['scan_extensions'] = [x for x in saved['scan_extensions'] if x in SCAN_FILE_TYPES]
                    for special in ('xbpq', 'xyq'):
                        if special not in data['scan_extensions']:
                            data['scan_extensions'].append(special)
                if saved.get('scan_mode') in ('source', 'file'):
                    data['scan_mode'] = saved['scan_mode']
                if 'adult_enabled' in saved:
                    data['adult_enabled'] = bool(saved['adult_enabled'])
                for key in ('blocked_dirs', 'excluded_files', 'adult_tags'):
                    if isinstance(saved.get(key), list):
                        data[key] = [str(x).strip() for x in saved[key] if str(x).strip()]
                if isinstance(saved.get('parse_entries'), list):
                    data['parse_entries'] = [dict(x) for x in saved['parse_entries'] if isinstance(x, dict)]
    except Exception as e:
        print(f'⚠️ 读取设置失败: {e}', file=sys.stderr)
    return data

def save_settings(data):
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return data

def current_output_path():
    return load_settings().get('output_path') or DEFAULT_OUTPUT_PATH

def current_scan_dirs():
    saved = load_settings().get('scan_dirs')
    return saved if isinstance(saved, list) else list(SCAN_DIRS)

def current_enabled_scan_dirs():
    data = load_settings()
    dirs = data.get('scan_dirs', [])
    enabled = set(data.get('scan_enabled_dirs', dirs))
    return [path for path in dirs if path in enabled]

def set_scan_dir_enabled(path, enabled):
    data = load_settings()
    active = set(data.get('scan_enabled_dirs', data.get('scan_dirs', [])))
    active.add(path) if enabled else active.discard(path)
    data['scan_enabled_dirs'] = [x for x in data.get('scan_dirs', []) if x in active]
    save_settings(data)
    reset_scan_cache()
    return enabled

def current_scan_mode():
    mode = load_settings().get('scan_mode')
    return mode if mode in ('source', 'file') else DEFAULT_SCAN_MODE

def scan_mode_text(mode=None):
    return SCAN_MODE_LABELS.get(mode or current_scan_mode(), '站源模式')

def set_scan_mode(mode):
    if mode not in ('source', 'file'):
        raise ValueError('扫描模式无效')
    data = load_settings()
    data['scan_mode'] = mode
    save_settings(data)
    reset_scan_cache()
    return mode

def current_scan_extensions():
    saved = load_settings().get('scan_extensions')
    return [x for x in saved if x in SCAN_FILE_TYPES] if isinstance(saved, list) else list(DEFAULT_SCAN_EXTENSIONS)

def current_adult_enabled():
    value = load_settings().get('adult_enabled')
    return DEFAULT_ADULT_ENABLED if value is None else bool(value)

def current_blocked_dirs():
    return set(load_settings().get('blocked_dirs', NO_SCAN_DIRS))

def current_excluded_files():
    return set(load_settings().get('excluded_files', EXCLUDE_FILES))

def current_adult_tags():
    return load_settings().get('adult_tags', DEFAULT_ADULT_TAGS)

def split_csv(value):
    raw = str(value or '').replace('，', ',').replace('、', ',').replace('\n', ',')
    return list(dict.fromkeys(x.strip() for x in raw.split(',') if x.strip()))

def save_block_settings(blocked_dirs, excluded_files, adult_tags):
    data = load_settings()
    data['blocked_dirs'] = split_csv(blocked_dirs)
    data['excluded_files'] = split_csv(excluded_files)
    data['adult_tags'] = split_csv(adult_tags)
    save_settings(data)
    reset_scan_cache()
    return data

def save_scan_options(extensions, adult_enabled):
    data = load_settings()
    data['scan_extensions'] = [x for x in extensions if x in SCAN_FILE_TYPES]
    data['adult_enabled'] = bool(adult_enabled)
    save_settings(data)
    reset_scan_cache()
    return data

def reset_scan_cache():
    global _SCAN_CACHE
    _SCAN_CACHE = None

def set_output_name(name):
    name = str(name or '').strip().replace('\\', '/').split('/')[-1]
    if not name:
        raise ValueError('文件名不能为空')
    if not name.lower().endswith('.json'):
        name += '.json'
    data = load_settings()
    output_dir = os.path.dirname(data.get('output_path') or DEFAULT_OUTPUT_PATH) or ROOT_DIR
    data['output_path'] = os.path.join(output_dir, name)
    save_settings(data)
    return data['output_path']

def set_output_dir(path):
    path = str(path or '').strip()
    if not path:
        raise ValueError('保存路径不能为空')
    data = load_settings()
    name = os.path.basename(data.get('output_path') or DEFAULT_OUTPUT_PATH) or 'vodplus.json'
    data['output_path'] = os.path.join(path, name)
    save_settings(data)
    return data['output_path']

def set_main_dir(path):
    path = os.path.abspath(os.path.expanduser(str(path or '').strip()))
    if not path or not os.path.isdir(path):
        raise ValueError('主目录不存在')
    data = load_settings()
    name = os.path.basename(data.get('output_path') or DEFAULT_OUTPUT_PATH) or 'vodplus.json'
    data['output_path'] = os.path.join(path, name)
    data['scan_dirs'] = [path]
    data['scan_enabled_dirs'] = [path]
    save_settings(data)
    reset_scan_cache()
    return path

def set_output_full_path(path):
    path = str(path or '').strip()
    if not path:
        raise ValueError('输出路径不能为空')
    if path.endswith('/'):
        path = os.path.join(path, os.path.basename(DEFAULT_OUTPUT_PATH))
    if not path.lower().endswith('.json'):
        path += '.json'
    data = load_settings()
    data['output_path'] = path
    save_settings(data)
    return data['output_path']

def set_scan_dirs(value):
    raw = str(value or '').strip()
    if not raw:
        raise ValueError('扫描路径不能为空')
    dirs = split_scan_dirs(raw)
    if not dirs:
        raise ValueError('扫描路径不能为空')
    data = load_settings()
    data['scan_dirs'] = dirs
    data['scan_enabled_dirs'] = list(dirs)
    save_settings(data)
    reset_scan_cache()
    return dirs

def add_scan_dir(path):
    path = os.path.abspath(os.path.expanduser(str(path or '').strip()))
    if not path or not os.path.isdir(path):
        raise ValueError('目录不存在')
    data = load_settings()
    dirs = data.get('scan_dirs') or []
    if path not in dirs:
        dirs.append(path)
    data['scan_dirs'] = dirs
    enabled = data.get('scan_enabled_dirs', [])
    if path not in enabled:
        enabled.append(path)
    data['scan_enabled_dirs'] = enabled
    save_settings(data)
    reset_scan_cache()
    return path

def remove_scan_dir(path):
    data = load_settings()
    data['scan_dirs'] = [x for x in data.get('scan_dirs', []) if x != path]
    data['scan_enabled_dirs'] = [x for x in data.get('scan_enabled_dirs', []) if x != path]
    save_settings(data)
    reset_scan_cache()
    return path

def generate_and_write_config():
    reset_scan_cache()
    output_path = current_output_path()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    config_data = get_config()
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, indent=2, ensure_ascii=False)
    return {
        'output_path': output_path,
        'sites': len(config_data.get('sites', [])),
        'lives': len(config_data.get('lives', [])),
        'scan_dirs': current_scan_dirs()
    }

# ==================== 输出构建 ====================

def scan_local_entries():
    global _SCAN_CACHE
    if _SCAN_CACHE is not None:
        return _SCAN_CACHE

    sites, lives = [], []
    php_port = detect_php_port()
    php_api_prefix = f'http://0.0.0.0:{php_port}'

    for scan_dir in current_enabled_scan_dirs():
        scan_path = abs_scan_path(scan_dir)
        if not os.path.isdir(scan_path):
            continue
        if os.path.basename(os.path.normpath(scan_path)) in current_blocked_dirs():
            continue
        scan_directory_recursive(scan_path, sites, lives, php_api_prefix)

    _SCAN_CACHE = (deduplicate_sites(sites), lives)
    return _SCAN_CACHE

def build_lives():
    lives = [dict(live) for live in DEFAULT_LIVES]
    lives.extend(scan_local_entries()[1])
    return lives

def build_sites():
    sites = [dict(site) for site in PINNED_SITES]
    scanned_sites, _ = scan_local_entries()
    sites.extend(scanned_sites)

    sites.extend(dict(site) for site in MANUAL_SITES)
    return deduplicate_sites(sites)

# ==================== 额外配置（完整版） ====================

EXTRA_JSON = r'''{
    "parses": [
        {"name":"♻️龙26","type":0,"url":"https://www.mtosz.com/m3u8.php?url=","ext":{"flag":["qq","腾讯","qiyi","iqiyi","爱奇艺","奇艺","youku","优酷","mgtv","芒果","letv","乐视","pptv","PPTV","sohu","bilibili","哔哩哔哩","哔哩"]}},
        {"name":"-BBKDJ-","type":0,"url":"https://jx.yparse.com/index.php?url="},
        {"name":"-777-","type":0,"url":"https://jx.bozrc.com:4433/player/?url="},
        {"name":"-全看-","type":0,"url":"https://jx.quankan.app/?url="}
    ],
    "rules": [
        {"name":"proxy","hosts":["stream-link.org"]},
        {"name":"量子广告","hosts":["vip.lz","hd.lz",".cdnlz"],"regex":["#EXT-X-DISCONTINUITY\\r*\\n*#EXTINF:6\\.666667,[\\s\\S]*?#EXT-X-DISCONTINUITY","#EXTINF.*?\\s+.*?1o.*?\\.ts\\s+"]},
        {"name":"非凡广告","hosts":["vip.ffzy","hd.ffzy"],"regex":["20.52","#EXT-X-DISCONTINUITY\\r*\\n*#EXTINF:7\\.400000,[\\s\\S]*?#EXT-X-DISCONTINUITY","#EXTINF.*?\\s+.*?1170(20|32).*?\\.ts\\s+","#EXTINF.*?\\s+.*?116977.*?\\.ts\\s+"]},
        {"name":"索尼广告","hosts":["suonizy"],"regex":["#EXT-X-DISCONTINUITY\\r*\\n*#EXTINF:1\\.000000,[\\s\\S]*?#EXT-X-DISCONTINUITY","#EXTINF.*?\\s+.*?p1ayer.*?\\.ts\\s+","#EXTINF.*?\\s+.*?\\/video\\/original.*?\\.ts\\s+"]},
        {"name":"暴风广告","hosts":["bfzy","bfbfvip"],"regex":["#EXTINF.*?\\s+.*?adjump.*?\\.ts\\s+"]},
        {"name":"星星广告","hosts":["aws.ulivetv.net"],"regex":["#EXT-X-DISCONTINUITY\\r*\\n*#EXTINF:8,[\\s\\S]*?#EXT-X-DISCONTINUITY"]},
        {"name":"快看广告","hosts":["kuaikan"],"regex":["#EXT-X-KEY:METHOD=NONE\\r*\\n*#EXTINF:5,[\\s\\S]*?#EXT-X-DISCONTINUITY","#EXT-X-KEY:METHOD=NONE\\r*\\n*#EXTINF:2\\.4,[\\s\\S]*?#EXT-X-DISCONTINUITY"]},
        {"name":"夜市","hosts":["yeslivetv.com"],"script":["document.getElementsByClassName('vjs-big-play-button')[0].click()"]},
        {"name":"毛驢","hosts":["www.maolvys.com"],"script":["document.getElementsByClassName('swal-button swal-button--confirm')[0].click()"]},
        {"name":"磁力广告","hosts":["magnet"],"regex":["更多","请访问","example","社 區","x u u","直 播","更 新","社 区","有趣","有 趣","英皇体育","全中文AV在线","澳门皇冠赌场","哥哥快来","美女荷官","裸聊","新片首发","UUE29"]},
        {"name":"一起看广告","hosts":["yqk88"],"regex":["18.4","15.1666","16.5333","#EXT-X-DISCONTINUITY\\r*\\n*[\\s\\S]*?#EXT-X-CUE-IN"]},
        {"name":"火山嗅探","hosts":["huoshan.com"],"regex":["item_id="]},
        {"name":"抖音嗅探","hosts":["douyin.com"],"regex":["is_play_url="]},
        {"name":"proxy","hosts":["raw.githubusercontent.com","googlevideo.com","cdn.v82u1l.com","cdn.iz8qkg.com","cdn.kin6c1.com","c.biggggg.com","c.olddddd.com","haiwaikan.com","www.histar.tv","youtube.com","uhibo.com",".*boku.*",".*nivod.*","*.t4tv.hz.cz",".*ulivetv.*"]},
        {"name":"农民嗅探","hosts":["toutiaovod.com"],"regex":["video/tos/cn"]}
    ],
    "doh": [
        {"name":"Google","url":"https://dns.google/dns-query","ips":["8.8.4.4","8.8.8.8"]},
        {"name":"Cloudflare","url":"https://cloudflare-dns.com/dns-query","ips":["1.1.1.1","1.0.0.1","2606:4700:4700::1111","2606:4700:4700::1001"]},
        {"name":"AdGuard","url":"https://dns.adguard.com/dns-query","ips":["94.140.14.140","94.140.14.141"]},
        {"name":"DNSWatch","url":"https://resolver2.dns.watch/dns-query","ips":["84.200.69.80","84.200.70.40"]},
        {"name":"Quad9","url":"https://dns.quad9.net/dns-quer","ips":["9.9.9.9","149.112.112.112"]},
        {"host":"www.djuu.com","rule":["mp4.djuu.com","m4a"]},
        {"host":"www.sharenice.net","rule":["huoshan.com","/item/video/"],"filter":[]},
        {"host":"www.sharenice.net","rule":["sovv.qianpailive.com","vid="],"filter":[]},
        {"host":"www.sharenice.net","rule":["douyin.com","/play/"]},
        {"host":"m.ysxs8.vip","rule":["ysting.ysxs8.vip:81","xmcdn.com"],"filter":[]},
        {"host":"hdmoli.com","rule":[".m3u8"]},
        {"host":"https://api.live.bilibili.com","rule":["bilivideo.com","/index.m3u8"],"filter":["data.bilibili.com/log/web","i0.hdslb.com/bfs/live/"]},
        {"host":"www.agemys.cc","rule":["cdn-tos","obj/tos-cn"]},
        {"host":"www.fun4k.com","rule":["https://hd.ijycnd.com/play","index.m3u8"]},
        {"host":"zjmiao.com","rule":["play.videomiao.vip/API.php","time=","key=","path="]}
    ],
    "flags": ["youku","优酷","优 酷","优酷视频","qq","腾讯","腾 讯","腾讯视频","iqiyi","qiyi","奇艺","爱奇艺","爱 奇 艺","m1905","xigua","letv","leshi","乐视","乐 视","sohu","搜狐","搜 狐","搜狐视频","tudou","pptv","mgtv","芒果","imgo","芒果TV","芒 果 T V","bilibili","哔 哩","哔 哩 哔 哩"],
    "ijk": [
        {"group":"软解码","options":[{"category":4,"name":"opensles","value":"0"},{"category":4,"name":"overlay-format","value":"842225234"},{"category":4,"name":"framedrop","value":"1"},{"category":4,"name":"soundtouch","value":"1"},{"category":4,"name":"start-on-prepared","value":"1"},{"category":1,"name":"http-detect-range-support","value":"0"},{"category":1,"name":"fflags","value":"fastseek"},{"category":2,"name":"skip_loop_filter","value":"48"},{"category":4,"name":"reconnect","value":"1"},{"category":4,"name":"max-buffer-size","value":"5242880"},{"category":4,"name":"enable-accurate-seek","value":"0"},{"category":4,"name":"mediacodec","value":"0"},{"category":4,"name":"mediacodec-auto-rotate","value":"0"},{"category":4,"name":"mediacodec-handle-resolution-change","value":"0"},{"category":4,"name":"mediacodec-hevc","value":"0"},{"category":1,"name":"dns_cache_timeout","value":"600000000"}]},
        {"group":"硬解码","options":[{"category":4,"name":"opensles","value":"0"},{"category":4,"name":"overlay-format","value":"842225234"},{"category":4,"name":"framedrop","value":"1"},{"category":4,"name":"soundtouch","value":"1"},{"category":4,"name":"start-on-prepared","value":"1"},{"category":1,"name":"http-detect-range-support","value":"0"},{"category":1,"name":"fflags","value":"fastseek"},{"category":2,"name":"skip_loop_filter","value":"48"},{"category":4,"name":"reconnect","value":"1"},{"category":4,"name":"max-buffer-size","value":"5242880"},{"category":4,"name":"enable-accurate-seek","value":"0"},{"category":4,"name":"mediacodec","value":"1"},{"category":4,"name":"mediacodec-auto-rotate","value":"1"},{"category":4,"name":"mediacodec-handle-resolution-change","value":"1"},{"category":4,"name":"mediacodec-hevc","value":"1"},{"category":1,"name":"dns_cache_timeout","value":"600000000"}]}
    ],
    "ads": ["https://img.mjviku.com","wan.51img1.com","iqiyi.hbuioo.com","vip.ffzyad.com","https://lf1-cdn-tos.bytegoofy.com/obj/tos-cn-i-dy/455ccf9e8ae744378118e4bd289288dd","mimg.0c1q0l.cn","www.googletagmanager.com","www.google-analytics.com","mc.usihnbcq.cn","mg.g1mm3d.cn","mscs.svaeuzh.cn","cnzz.hhttm.top","tp.vinuxhome.com","cnzz.mmstat.com","www.baihuillq.com","s23.cnzz.com","z3.cnzz.com","c.cnzz.com","stj.v1vo.top","z12.cnzz.com","img.mosflower.cn","tips.gamevvip.com","ehwe.yhdtns.com","xdn.cqqc3.com","www.jixunkyy.cn","sp.chemacid.cn","hm.baidu.com","s9.cnzz.com","z6.cnzz.com","um.cavuc.com","mav.mavuz.com","wofwk.aoidf3.com","z5.cnzz.com","xc.hubeijieshikj.cn","tj.tianwenhu.com","xg.gars57.cn","k.jinxiuzhilv.com","cdn.bootcss.com","ppl.xunzhuo123.com","xomk.jiangjunmh.top","img.xunzhuo123.com","z1.cnzz.com","s13.cnzz.com","xg.huataisangao.cn","z7.cnzz.com","xg.huataisangao.cn","z2.cnzz.com","s96.cnzz.com","q11.cnzz.com","thy.dacedsfa.cn","xg.whsbpw.cn","s19.cnzz.com","z8.cnzz.com","s4.cnzz.com","f5w.as12df.top","ae01.alicdn.com","www.92424.cn","k.wudejia.com","vivovip.mmszxc.top","qiu.xixiqiu.com","cdnjs.hnfenxun.com","cms.qdwght.com"]
}'''

# ==================== 解析设置 ====================

def default_parse_entries():
    try:
        return [dict(item, enabled=True) for item in json.loads(EXTRA_JSON).get('parses', []) if isinstance(item, dict)]
    except Exception:
        return []

def current_parse_entries():
    entries = load_settings().get('parse_entries')
    return [dict(item) for item in entries] if isinstance(entries, list) else default_parse_entries()

def save_parse_entries(entries):
    data = load_settings()
    data['parse_entries'] = [dict(item) for item in entries if isinstance(item, dict)]
    save_settings(data)
    return data['parse_entries']

def enabled_parses():
    result = []
    for item in current_parse_entries():
        if item.get('enabled', True):
            clean = dict(item)
            clean.pop('enabled', None)
            result.append(clean)
    return result

# ==================== 生成配置 ====================

def get_config():
    """获取完整配置"""
    config = {
        "spider": CONFIG_SPIDER,
        "logo": CONFIG_LOGO,
        "wallpaper": CONFIG_WALLPAPER,
        "lives": build_lives(),
        "sites": build_sites()
    }
    
    # 加载额外配置
    try:
        extra = json.loads(EXTRA_JSON)
        fix_types(extra)
        extra['parses'] = enabled_parses()
        config.update(extra)
    except Exception as e:
        print(f"⚠️ EXTRA_JSON 解析失败: {e}", file=sys.stderr)
    
    return config


# ==================== 卡片交互 Spider ====================

class Spider(BaseSpider):
    LOAD_ID = '__cc_local_load__'
    OUTPUT_ID = '__cc_output_file__'
    MAIN_ID = '__cc_main_dir__'
    OUTPUT_NAME_ID = '__cc_output_name__'
    OUTPUT_PATH_ID = '__cc_output_path__'
    OUTPUT_FULL_ID = '__cc_output_full__'
    SCAN_ID = '__cc_scan_dirs__'
    SCAN_SET_ID = '__cc_scan_set__'
    BLOCK_ID = '__cc_block_settings__'
    PARSE_ID = '__cc_parse_settings__'

    def getName(self):
        return '本地配置工具'

    def init(self, extend=''):
        pass

    def destroy(self):
        pass

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return True

    def _icon(self, key):
        return LOCAL_UI_ICONS.get(key, '')

    def _card(self, vod_id, name, pic_key='status', remarks='', **extra):
        item = {
            'vod_id': vod_id,
            'vod_name': name,
            'vod_pic': self._icon(pic_key),
            'vod_remarks': remarks
        }
        item.update(extra)
        return item

    def _settings_summary(self):
        data = load_settings()
        return data.get('output_path', DEFAULT_OUTPUT_PATH), data.get('scan_dirs', list(SCAN_DIRS))
    def _home_items(self):
        _, scan_dirs = self._settings_summary()
        return [
            self._card(self.LOAD_ID, '本地加载', 'scan', '点击后扫描本地目录并生成配置', action='local_load'),
            self._card(self.OUTPUT_ID, '生成配置', 'download', '主目录设置、接口文件', settings=True, action='edit_output_settings'),
            self._card(self.SCAN_ID, '扫描设置', 'folder', '{} 个目录：{}'.format(len(scan_dirs), ' | '.join(scan_dirs)[:90]), settings=True, scan_settings=True, action='edit_scan_dirs'),
            self._card(self.BLOCK_ID, '屏蔽设置', 'block', '目录、源文件和18+标签', settings=True, action='edit_block_settings'),
            self._card(self.PARSE_ID, '解析设置', 'parse', '{} 个解析'.format(len(current_parse_entries())), settings=True, action='edit_parse_settings')
        ]


    def homeContent(self, filter=False):
        return {'class': [{'type_id': 'setting', 'type_name': '设置'}], 'list': self._home_items()}

    def homeVideoContent(self):
        return {'list': self._home_items()}

    def categoryContent(self, tid, pg, filter, extend):
        return {'list': self._home_items(), 'page': 1, 'pagecount': 1, 'limit': 20, 'total': 5}

    def _detail(self, vod_id, title, content, pic_key='status'):
        return {'list': [{
            'vod_id': vod_id,
            'vod_name': title,
            'vod_pic': self._icon(pic_key),
            'vod_content': content,
            'vod_play_from': '提示',
            'vod_play_url': '返回$cc://noop'
        }]}

    def _output_setting_items(self):
        output_path, _ = self._settings_summary()
        output_dir = os.path.dirname(output_path) or ROOT_DIR
        output_name = os.path.basename(output_path) or 'vodplus.json'
        return [
            self._card(self.MAIN_ID, '主目录设置', 'folder', '当前：' + output_dir, settings=True, input=True, input_type='path', input_key='主目录', input_value=output_dir, input_hint='输入或选择主目录', action='edit_main_dir'),
            self._card(self.OUTPUT_FULL_ID, '接口文件', 'status', output_path, settings=True, input=True, input_type='file', input_key='接口文件', input_value=output_path, input_hint='输入或选择接口文件', action='edit_output_full')
        ]

    def _scan_setting_items(self):
        _, scan_dirs = self._settings_summary()
        value = '|'.join(scan_dirs)
        types = '、'.join(SCAN_FILE_TYPES[x] for x in current_scan_extensions()) or '未选择'
        status = '18+开启' if current_adult_enabled() else '18+关闭'
        mode = scan_mode_text()
        return [
            self._card(self.SCAN_SET_ID, '扫描设置', 'folder', '{}；{}；{}；{}'.format(mode, types, status, value), settings=True, action='edit_scan_dirs'),
            self._card(self.LOAD_ID, '本地加载', 'scan', '按当前扫描目录生成配置', action='local_load')
        ]

    def detailContent(self, ids):
        vod_id = str(ids[0] if isinstance(ids, (list, tuple)) and ids else ids or '')
        output_path, scan_dirs = self._settings_summary()
        if vod_id == self.LOAD_ID:
            try:
                info = generate_and_write_config()
                content = '加载中...\n加载完成！\n站点数量：{}\n直播数量：{}\n生成文件：{}\n扫描目录：{}'.format(info['sites'], info['lives'], info['output_path'], ' | '.join(info['scan_dirs']))
                return self._detail(vod_id, '本地加载完成', content, 'scan')
            except Exception as e:
                return self._detail(vod_id, '本地加载失败', str(e), 'status')
        if vod_id == self.OUTPUT_ID:
            return {'list': [self._card(self.OUTPUT_ID, '生成配置', 'download', '点击操作按钮设置主目录和接口文件', settings=True, action='edit_output_settings')]}
        if vod_id in (self.OUTPUT_NAME_ID, self.OUTPUT_PATH_ID, self.OUTPUT_FULL_ID):
            return self._detail(vod_id, '生成配置', '如果没有弹窗，请用搜索修改：\n文件名=vodplus.json\n路径=/storage/emulated/0/VodPlus/wwwroot/\n输出=/storage/emulated/0/VodPlus/wwwroot/vodplus.json\n\n当前输出：{}'.format(output_path), 'download')
        if vod_id == self.SCAN_ID:
            return {'list': self._scan_setting_items()}
        if vod_id == self.BLOCK_ID:
            return self._detail(vod_id, '屏蔽设置', '请点击卡片操作按钮打开设置弹窗。', 'status')
        if vod_id == self.PARSE_ID:
            text = '\n'.join('{}：{}'.format(x.get('name', ''), x.get('url', '')) for x in current_parse_entries())
            return self._detail(vod_id, '解析设置', text or '暂无解析', 'status')
        if vod_id == self.SCAN_SET_ID:
            return self._detail(vod_id, '扫描设置', '如果没有弹窗，请用搜索修改：\n扫描=/路径1/|/路径2/\n\n当前扫描目录：\n{}'.format('\n'.join(scan_dirs)), 'folder')
        return self._detail(vod_id, '本地配置工具', '请选择首页卡片操作。', 'status')


    def _current_android_activity(self, jclass):
        app_class = jclass('com.fongmi.android.tv.App')
        activity_class = jclass('android.app.Activity')
        modifier_class = jclass('java.lang.reflect.Modifier')
        app_info = app_class.getClass()
        activity_info = activity_class.getClass()
        for method in app_info.getDeclaredMethods():
            try:
                if not modifier_class.isStatic(method.getModifiers()):
                    continue
                if len(method.getParameterTypes()) != 0:
                    continue
                if not activity_info.isAssignableFrom(method.getReturnType()):
                    continue
                method.setAccessible(True)
                try:
                    activity = method.invoke(None, [])
                except Exception:
                    activity = method.invoke(None)
                if activity is not None:
                    return activity
            except Exception:
                continue
        app = None
        for field in app_info.getDeclaredFields():
            try:
                if not modifier_class.isStatic(field.getModifiers()):
                    continue
                if not app_info.isAssignableFrom(field.getType()):
                    continue
                field.setAccessible(True)
                app = field.get(None)
                if app is not None:
                    break
            except Exception:
                continue
        if app is not None:
            for field in app.getClass().getDeclaredFields():
                try:
                    if modifier_class.isStatic(field.getModifiers()):
                        continue
                    if not activity_info.isAssignableFrom(field.getType()):
                        continue
                    field.setAccessible(True)
                    activity = field.get(app)
                    if activity is not None:
                        return activity
                except Exception:
                    continue
        raise ValueError('未找到当前 Android 页面')

    def _open_path_picker(self, kind, callback, start_path=None):
        try:
            from java import dynamic_proxy, jclass
            activity = self._current_android_activity(jclass)
            builder_class = jclass('android.app.AlertDialog$Builder')
            click = jclass('android.content.DialogInterface$OnClickListener')
            current = os.path.abspath(start_path or STORAGE_ROOT)
            owner = self
            class Listener(dynamic_proxy(click)):
                def __init__(self, dialog_ref, path_list):
                    super().__init__()
                    self.dialog_ref = dialog_ref
                    self.path_list = path_list
                def onClick(self, dialog, which):
                    path = self.path_list[which]
                    if path == '__select__':
                        callback(current)
                        dialog.dismiss()
                    elif kind == 'file' and os.path.isfile(path):
                        callback(path)
                        dialog.dismiss()
                    elif os.path.isdir(path):
                        dialog.dismiss()
                        owner._open_path_picker(kind, callback, path)
            def show(path):
                nonlocal current
                current = path
                entries = []
                if os.path.dirname(path) != path:
                    entries.append(os.path.dirname(path))
                try:
                    children = sorted(os.listdir(path), key=scan_sort_key)
                except Exception:
                    children = []
                entries.extend(os.path.join(path, x) for x in children if os.path.isdir(os.path.join(path, x)))
                if kind == 'dir':
                    entries.append('__select__')
                else:
                    entries.extend(os.path.join(path, x) for x in children if os.path.isfile(os.path.join(path, x)))
                labels = []
                for item in entries:
                    if item == '__select__':
                        labels.append('选择当前文件夹：' + path)
                    elif item == os.path.dirname(path):
                        labels.append('📁 ..')
                    else:
                        labels.append(('📁 ' if os.path.isdir(item) else '📄 ') + os.path.basename(item))
                if not labels:
                    labels = ['当前目录没有可选内容']
                    entries = ['__select__'] if kind == 'dir' else []
                builder = builder_class(activity)
                builder.setTitle('选择文件夹' if kind == 'dir' else '选择接口文件')
                builder.setItems(labels, Listener(None, entries))
                dialog = builder.create()
                dialog.show()
            class ShowPicker(dynamic_proxy(jclass('java.lang.Runnable'))):
                def run(self):
                    show(current)
            activity.runOnUiThread(ShowPicker())
            return True, ''
        except Exception as exc:
            return False, '选择器打开失败：{}'.format(exc)

    def _open_text_dialog(self, title, label, value, save_func, picker_kind=None):
        try:
            from java import dynamic_proxy, jclass
            toast_class = jclass('android.widget.Toast')
            edit_text_class = jclass('android.widget.EditText')
            linear_layout_class = jclass('android.widget.LinearLayout')
            text_view_class = jclass('android.widget.TextView')
            input_type = jclass('android.text.InputType')
            click_listener = jclass('android.content.DialogInterface$OnClickListener')
            show_listener = jclass('android.content.DialogInterface$OnShowListener')
            view_click_listener = jclass('android.view.View$OnClickListener')
            runnable_class = jclass('java.lang.Runnable')
            try:
                builder_class = jclass('com.google.android.material.dialog.MaterialAlertDialogBuilder')
            except Exception:
                builder_class = jclass('android.app.AlertDialog$Builder')
            activity = self._current_android_activity(jclass)
            owner = self
            class NoopClickListener(dynamic_proxy(click_listener)):
                def onClick(self, dialog, which):
                    return None
            class NoopShowListener(dynamic_proxy(show_listener)):
                def onShow(self, dialog):
                    return None
            class SaveButtonListener(dynamic_proxy(view_click_listener)):
                def __init__(self, edit, dialog):
                    super().__init__()
                    self.edit = edit
                    self.dialog = dialog
                def onClick(self, view):
                    try:
                        result = save_func(str(self.edit.getText().toString()))
                        toast_class.makeText(activity, '已保存：{}'.format(result), toast_class.LENGTH_LONG).show()
                        self.dialog.dismiss()
                    except Exception as exc:
                        toast_class.makeText(activity, '保存失败：{}'.format(exc), toast_class.LENGTH_LONG).show()
            class ShowDialog(dynamic_proxy(runnable_class)):
                def run(self):
                    density = float(activity.getResources().getDisplayMetrics().density)
                    padding = int(16 * density + 0.5)
                    spacing = int(8 * density + 0.5)
                    container = linear_layout_class(activity)
                    container.setOrientation(linear_layout_class.VERTICAL)
                    container.setPadding(padding, spacing, padding, 0)
                    label_view = text_view_class(activity)
                    label_view.setText(label)
                    edit = edit_text_class(activity)
                    edit.setSingleLine(False)
                    edit.setMinLines(1)
                    edit.setInputType(input_type.TYPE_CLASS_TEXT | input_type.TYPE_TEXT_FLAG_MULTI_LINE)
                    edit.setText(str(value or ''))
                    edit.setSelectAllOnFocus(True)
                    owner._style_input(activity, jclass, edit)
                    try:
                        color = jclass('android.graphics.Color')
                        label_view.setTextColor(color.parseColor('#64748B'))
                        label_view.setTextSize(11)
                        label_view.setPadding(0, 0, 0, owner._dp(activity, 8))
                    except Exception:
                        pass
                    container.addView(label_view)
                    if picker_kind:
                        input_row = linear_layout_class(activity)
                        input_row.setOrientation(linear_layout_class.HORIZONTAL)
                        input_row.setGravity(16)
                        input_row.addView(edit, linear_layout_class.LayoutParams(0, -2, 1.0))
                        picker_button = jclass('android.widget.Button')(activity)
                        picker_button.setText('📁')
                        picker_button.setAllCaps(False)
                        picker_button.setTextSize(12)
                        picker_button.setMinWidth(owner._dp(activity, 44))
                        picker_button.setMinimumWidth(owner._dp(activity, 44))
                        picker_button.setMinHeight(owner._dp(activity, 44))
                        picker_button.setMinimumHeight(owner._dp(activity, 44))
                        picker_button.setPadding(0, 0, 0, 0)
                        class PickerClickListener(dynamic_proxy(view_click_listener)):
                            def onClick(self, view):
                                start = os.path.dirname(str(edit.getText())) if picker_kind == 'file' else str(edit.getText())
                                owner._open_path_picker(picker_kind, lambda selected: edit.setText(str(selected)), start)
                        picker_button.setOnClickListener(PickerClickListener())
                        picker_lp = linear_layout_class.LayoutParams(owner._dp(activity, 44), owner._dp(activity, 44))
                        picker_lp.setMargins(owner._dp(activity, 6), 0, 0, 0)
                        input_row.addView(picker_button, picker_lp)
                        container.addView(input_row)
                    else:
                        container.addView(edit)
                    builder = builder_class(activity)
                    builder.setTitle(title)
                    builder.setView(container)
                    builder.setNegativeButton('取消', NoopClickListener())
                    builder.setPositiveButton('保存', NoopClickListener())
                    dialog = builder.create()
                    dialog.setOnShowListener(NoopShowListener())
                    dialog.show()
                    owner._style_dialog_buttons(activity, jclass, dialog, -1)
                    dialog.getButton(-1).setOnClickListener(SaveButtonListener(edit, dialog))
            activity.runOnUiThread(ShowDialog())
            return True, ''
        except Exception as exc:
            return False, '{}打开失败：{}'.format(title, exc)

    def _open_output_settings_dialog(self):
        try:
            from java import dynamic_proxy, jclass
            activity = self._current_android_activity(jclass)
            linear = jclass('android.widget.LinearLayout')
            edit_text = jclass('android.widget.EditText')
            text_view = jclass('android.widget.TextView')
            button = jclass('android.widget.Button')
            layout_params = jclass('android.widget.LinearLayout$LayoutParams')
            click = jclass('android.view.View$OnClickListener')
            dialog_click = jclass('android.content.DialogInterface$OnClickListener')
            runnable = jclass('java.lang.Runnable')
            color = jclass('android.graphics.Color')
            try:
                builder_class = jclass('com.google.android.material.dialog.MaterialAlertDialogBuilder')
            except Exception:
                builder_class = jclass('android.app.AlertDialog$Builder')
            owner = self
            output_path, _ = self._settings_summary()
            class Noop(dynamic_proxy(dialog_click)):
                def onClick(self, dialog, which):
                    return None
            class Click(dynamic_proxy(click)):
                def __init__(self, fn):
                    super().__init__()
                    self.fn = fn
                def onClick(self, view):
                    self.fn()
            class Show(dynamic_proxy(runnable)):
                def run(self):
                    root = linear(activity)
                    root.setOrientation(linear.VERTICAL)
                    root.setPadding(owner._dp(activity, 16), owner._dp(activity, 8), owner._dp(activity, 16), 0)
                    fields = []
                    for title, value, kind in (('主目录设置', os.path.dirname(output_path), 'dir'), ('接口文件', output_path, 'file')):
                        label = text_view(activity)
                        label.setText(title)
                        label.setTextColor(color.parseColor('#1E293B'))
                        label.setTextSize(12)
                        label.setPadding(0, owner._dp(activity, 8), 0, owner._dp(activity, 5))
                        root.addView(label)
                        row = linear(activity)
                        row.setOrientation(linear.HORIZONTAL)
                        row.setGravity(16)
                        edit = edit_text(activity)
                        edit.setSingleLine(True)
                        edit.setText(value)
                        owner._style_input(activity, jclass, edit)
                        row.addView(edit, layout_params(0, -2, 1.0))
                        pick = button(activity)
                        pick.setText('📁' if kind == 'dir' else '📄')
                        pick.setAllCaps(False)
                        pick.setTextSize(12)
                        pick.setMinWidth(owner._dp(activity, 44))
                        pick.setMinimumWidth(owner._dp(activity, 44))
                        pick.setMinHeight(owner._dp(activity, 44))
                        pick.setMinimumHeight(owner._dp(activity, 44))
                        pick.setPadding(0, 0, 0, 0)
                        def choose(e=edit, k=kind):
                            start = os.path.dirname(str(e.getText())) if k == 'file' else str(e.getText())
                            owner._open_path_picker(k, lambda selected: e.setText(str(selected)), start)
                        pick.setOnClickListener(Click(choose))
                        pick_lp = layout_params(owner._dp(activity, 44), owner._dp(activity, 44))
                        pick_lp.setMargins(owner._dp(activity, 6), 0, 0, 0)
                        row.addView(pick, pick_lp)
                        root.addView(row)
                        fields.append(edit)
                    builder = builder_class(activity)
                    builder.setTitle('生成配置')
                    builder.setView(root)
                    builder.setNegativeButton('取消', Noop())
                    builder.setPositiveButton('保存', Noop())
                    dialog = builder.create()
                    dialog.show()
                    owner._style_dialog_buttons(activity, jclass, dialog, -1)
                    def save():
                        main_dir = str(fields[0].getText()).strip()
                        interface_file = str(fields[1].getText()).strip()
                        set_main_dir(main_dir)
                        set_output_full_path(interface_file)
                        owner._toast('生成配置设置已保存')
                        dialog.dismiss()
                    dialog.getButton(-1).setOnClickListener(Click(save))
            activity.runOnUiThread(Show())
            return True, ''
        except Exception as exc:
            return False, '生成配置弹窗打开失败：{}'.format(exc)

    def _open_main_dir_dialog(self):
        output_path, _ = self._settings_summary()
        return self._open_text_dialog('主目录设置', '主目录路径', os.path.dirname(output_path) or ROOT_DIR, set_main_dir, 'dir')

    def _open_output_name_dialog(self):
        output_path, _ = self._settings_summary()
        return self._open_text_dialog('修改名字', '接口文件名', os.path.basename(output_path) or 'vodplus.json', set_output_name)

    def _open_output_path_dialog(self):
        output_path, _ = self._settings_summary()
        return self._open_text_dialog('修改路径', '保存目录', os.path.dirname(output_path) or ROOT_DIR, set_output_dir)

    def _open_output_full_dialog(self):
        output_path, _ = self._settings_summary()
        return self._open_text_dialog('接口文件', '接口文件路径', output_path, set_output_full_path, 'file')

    def _dp(self, activity, value):
        return int(float(value) * float(activity.getResources().getDisplayMetrics().density) + .5)

    def _rounded_bg(self, jclass, color, radius=8, stroke=None):
        drawable = jclass('android.graphics.drawable.GradientDrawable')()
        drawable.setShape(drawable.RECTANGLE)
        drawable.setCornerRadius(float(radius))
        drawable.setColor(jclass('android.graphics.Color').parseColor(color))
        if stroke:
            drawable.setStroke(1, jclass('android.graphics.Color').parseColor(stroke))
        return drawable

    def _style_input(self, activity, jclass, view):
        color = jclass('android.graphics.Color')
        view.setTextColor(color.parseColor('#1E293B'))
        view.setHintTextColor(color.parseColor('#94A3B8'))
        view.setTextSize(12)
        view.setPadding(self._dp(activity, 12), self._dp(activity, 9), self._dp(activity, 12), self._dp(activity, 9))
        view.setBackgroundDrawable(self._rounded_bg(jclass, '#F8FAFC', self._dp(activity, 8), '#E2E8F0'))

    def _style_dialog_buttons(self, activity, jclass, dialog, primary=-1):
        color = jclass('android.graphics.Color')
        for which in (-1, -2, -3):
            try:
                button = dialog.getButton(which)
                if button is None:
                    continue
                button.setAllCaps(False)
                button.setTextSize(12)
                button.setTextColor(color.parseColor('#6C63FF') if which == primary else color.parseColor('#475569'))
            except Exception:
                pass

    def _open_add_scan_dir_dialog(self):
        owner = self
        def save(path):
            result = add_scan_dir(path)
            owner._open_scan_dirs_dialog()
            return result
        return self._open_text_dialog('添加目录', '扫描目录路径', '', save, 'dir')

    def _open_block_settings_dialog(self):
        try:
            from java import dynamic_proxy, jclass
            activity = self._current_android_activity(jclass)
            linear = jclass('android.widget.LinearLayout')
            text_view = jclass('android.widget.TextView')
            edit_text = jclass('android.widget.EditText')
            scroll = jclass('android.widget.ScrollView')
            runnable = jclass('java.lang.Runnable')
            dialog_click = jclass('android.content.DialogInterface$OnClickListener')
            click = jclass('android.view.View$OnClickListener')
            color = jclass('android.graphics.Color')
            typeface = jclass('android.graphics.Typeface')
            try:
                builder_class = jclass('com.google.android.material.dialog.MaterialAlertDialogBuilder')
            except Exception:
                builder_class = jclass('android.app.AlertDialog$Builder')
            owner = self
            class Noop(dynamic_proxy(dialog_click)):
                def onClick(self, dialog, which):
                    return None
            class Click(dynamic_proxy(click)):
                def __init__(self, fn):
                    super().__init__()
                    self.fn = fn
                def onClick(self, view):
                    self.fn()
            class Show(dynamic_proxy(runnable)):
                def run(self):
                    root = linear(activity)
                    root.setOrientation(linear.VERTICAL)
                    root.setPadding(owner._dp(activity, 16), owner._dp(activity, 8), owner._dp(activity, 16), owner._dp(activity, 4))
                    intro = text_view(activity)
                    intro.setText('使用逗号分隔，可直接增删内容')
                    intro.setTextColor(color.parseColor('#64748B'))
                    intro.setTextSize(11)
                    root.addView(intro)
                    fields = []
                    sections = [
                        ('屏蔽扫描文件夹', '命中名称的目录及其子目录不会扫描', sorted(current_blocked_dirs(), key=scan_sort_key)),
                        ('不显示的源文件', '命中文件名时不写入 sites', sorted(current_excluded_files(), key=scan_sort_key)),
                        ('18+ 标签', '关闭18+扫描时跳过带有这些标签的目录', current_adult_tags())
                    ]
                    for title, hint, values in sections:
                        label = text_view(activity)
                        label.setText('\n' + title)
                        label.setTextColor(color.parseColor('#1E293B'))
                        label.setTextSize(12)
                        label.setTypeface(typeface.DEFAULT_BOLD)
                        root.addView(label)
                        desc = text_view(activity)
                        desc.setText(hint)
                        desc.setTextColor(color.parseColor('#64748B'))
                        desc.setTextSize(10)
                        root.addView(desc)
                        edit = edit_text(activity)
                        edit.setText(','.join(values))
                        edit.setMinLines(2)
                        edit.setMaxLines(4)
                        owner._style_input(activity, jclass, edit)
                        root.addView(edit)
                        fields.append(edit)
                    wrapper = scroll(activity)
                    wrapper.addView(root)
                    builder = builder_class(activity)
                    builder.setTitle('屏蔽设置')
                    builder.setView(wrapper)
                    builder.setNegativeButton('取消', Noop())
                    builder.setPositiveButton('保存', Noop())
                    dialog = builder.create()
                    dialog.show()
                    owner._style_dialog_buttons(activity, jclass, dialog, -1)
                    def save():
                        save_block_settings(str(fields[0].getText()), str(fields[1].getText()), str(fields[2].getText()))
                        owner._toast('屏蔽设置已保存')
                        dialog.dismiss()
                    dialog.getButton(-1).setOnClickListener(Click(save))
            activity.runOnUiThread(Show())
            return True, ''
        except Exception as exc:
            return False, '屏蔽设置弹窗打开失败：{}'.format(exc)

    def _open_add_parse_dialog(self):
        try:
            from java import dynamic_proxy, jclass
            activity = self._current_android_activity(jclass)
            linear = jclass('android.widget.LinearLayout')
            text_view = jclass('android.widget.TextView')
            edit_text = jclass('android.widget.EditText')
            runnable = jclass('java.lang.Runnable')
            dialog_click = jclass('android.content.DialogInterface$OnClickListener')
            click = jclass('android.view.View$OnClickListener')
            color = jclass('android.graphics.Color')
            try:
                builder_class = jclass('com.google.android.material.dialog.MaterialAlertDialogBuilder')
            except Exception:
                builder_class = jclass('android.app.AlertDialog$Builder')
            owner = self
            class Noop(dynamic_proxy(dialog_click)):
                def onClick(self, dialog, which):
                    return None
            class Click(dynamic_proxy(click)):
                def __init__(self, fn):
                    super().__init__()
                    self.fn = fn
                def onClick(self, view):
                    self.fn()
            class Show(dynamic_proxy(runnable)):
                def run(self):
                    root = linear(activity)
                    root.setOrientation(linear.VERTICAL)
                    root.setPadding(owner._dp(activity, 16), owner._dp(activity, 8), owner._dp(activity, 16), 0)
                    fields = []
                    for label_text, hint in (('解析名字', '例如：线路一'), ('解析 URL', '例如：https://example.com/?url=')):
                        label = text_view(activity)
                        label.setText(label_text)
                        label.setTextColor(color.parseColor('#1E293B'))
                        label.setTextSize(12)
                        label.setPadding(0, owner._dp(activity, 8), 0, owner._dp(activity, 5))
                        root.addView(label)
                        edit = edit_text(activity)
                        edit.setHint(hint)
                        edit.setSingleLine(True)
                        owner._style_input(activity, jclass, edit)
                        root.addView(edit)
                        fields.append(edit)
                    builder = builder_class(activity)
                    builder.setTitle('增加解析')
                    builder.setView(root)
                    builder.setNegativeButton('取消', Noop())
                    builder.setPositiveButton('增加', Noop())
                    dialog = builder.create()
                    dialog.show()
                    owner._style_dialog_buttons(activity, jclass, dialog, -1)
                    def add():
                        name, url = str(fields[0].getText()).strip(), str(fields[1].getText()).strip()
                        if not name or not url:
                            owner._toast('解析名字和 URL 不能为空')
                            return
                        entries = current_parse_entries()
                        entries.append({'name': name, 'type': 0, 'url': url, 'enabled': True})
                        save_parse_entries(entries)
                        dialog.dismiss()
                        owner._open_parse_settings_dialog()
                    dialog.getButton(-1).setOnClickListener(Click(add))
            activity.runOnUiThread(Show())
            return True, ''
        except Exception as exc:
            return False, '增加解析弹窗打开失败：{}'.format(exc)

    def _open_parse_settings_dialog(self):
        try:
            from java import dynamic_proxy, jclass
            activity = self._current_android_activity(jclass)
            linear = jclass('android.widget.LinearLayout')
            text_view = jclass('android.widget.TextView')
            switch = jclass('android.widget.Switch')
            button = jclass('android.widget.Button')
            layout_params = jclass('android.widget.LinearLayout$LayoutParams')
            scroll = jclass('android.widget.ScrollView')
            runnable = jclass('java.lang.Runnable')
            click = jclass('android.view.View$OnClickListener')
            dialog_click = jclass('android.content.DialogInterface$OnClickListener')
            color = jclass('android.graphics.Color')
            try:
                builder_class = jclass('com.google.android.material.dialog.MaterialAlertDialogBuilder')
            except Exception:
                builder_class = jclass('android.app.AlertDialog$Builder')
            owner = self
            entries = current_parse_entries()
            class Noop(dynamic_proxy(dialog_click)):
                def onClick(self, dialog, which):
                    return None
            class Click(dynamic_proxy(click)):
                def __init__(self, fn):
                    super().__init__()
                    self.fn = fn
                def onClick(self, view):
                    self.fn()
            class Show(dynamic_proxy(runnable)):
                def run(self):
                    root = linear(activity)
                    root.setOrientation(linear.VERTICAL)
                    root.setPadding(owner._dp(activity, 16), owner._dp(activity, 6), owner._dp(activity, 16), 0)
                    intro = text_view(activity)
                    intro.setText('当前解析列表')
                    intro.setTextColor(color.parseColor('#64748B'))
                    intro.setTextSize(11)
                    root.addView(intro)
                    switches = []
                    for index, entry in enumerate(entries):
                        row = linear(activity)
                        row.setOrientation(linear.HORIZONTAL)
                        row.setGravity(16)
                        row.setPadding(0, owner._dp(activity, 8), 0, owner._dp(activity, 8))
                        enabled = switch(activity)
                        enabled.setText('{}\n{}'.format(entry.get('name', ''), entry.get('url', '')))
                        enabled.setTextColor(color.parseColor('#334155'))
                        enabled.setTextSize(11)
                        enabled.setLineSpacing(owner._dp(activity, 3), 1.15)
                        enabled.setPadding(0, owner._dp(activity, 4), owner._dp(activity, 8), owner._dp(activity, 4))
                        enabled.setChecked(entry.get('enabled', True))
                        row.addView(enabled, layout_params(0, -2, 1.0))
                        switches.append(enabled)
                        delete = button(activity)
                        delete.setText('删除')
                        delete.setAllCaps(False)
                        delete.setTextColor(color.WHITE)
                        delete.setTextSize(11)
                        delete.setMinWidth(owner._dp(activity, 52))
                        delete.setMinimumWidth(owner._dp(activity, 52))
                        delete.setMinHeight(owner._dp(activity, 32))
                        delete.setMinimumHeight(owner._dp(activity, 32))
                        delete.setPadding(owner._dp(activity, 12), owner._dp(activity, 5), owner._dp(activity, 12), owner._dp(activity, 5))
                        delete.setBackgroundDrawable(owner._rounded_bg(jclass, '#EF4444', owner._dp(activity, 7)))
                        def remove(i=index):
                            fresh = current_parse_entries()
                            if 0 <= i < len(fresh):
                                fresh.pop(i)
                                save_parse_entries(fresh)
                            dialog.dismiss()
                            owner._open_parse_settings_dialog()
                        delete.setOnClickListener(Click(remove))
                        row.addView(delete)
                        root.addView(row)
                        if index < len(entries) - 1:
                            divider = text_view(activity)
                            divider.setBackgroundColor(color.parseColor('#E2E8F0'))
                            root.addView(divider, layout_params(-1, owner._dp(activity, 1)))
                    wrapper = scroll(activity)
                    wrapper.addView(root)
                    builder = builder_class(activity)
                    builder.setTitle('解析设置')
                    builder.setView(wrapper)
                    builder.setNegativeButton('增加解析', Noop())
                    builder.setPositiveButton('确认', Noop())
                    dialog = builder.create()
                    dialog.show()
                    owner._style_dialog_buttons(activity, jclass, dialog, -1)
                    def confirm():
                        for i, view in enumerate(switches):
                            if i < len(entries):
                                entries[i]['enabled'] = view.isChecked()
                        save_parse_entries(entries)
                        owner._toast('解析设置已保存')
                        dialog.dismiss()
                    def add():
                        for i, view in enumerate(switches):
                            if i < len(entries):
                                entries[i]['enabled'] = view.isChecked()
                        save_parse_entries(entries)
                        dialog.dismiss()
                        owner._open_add_parse_dialog()
                    dialog.getButton(-1).setOnClickListener(Click(confirm))
                    dialog.getButton(-2).setOnClickListener(Click(add))
            activity.runOnUiThread(Show())
            return True, ''
        except Exception as exc:
            return False, '解析设置弹窗打开失败：{}'.format(exc)

    def _open_scan_dirs_dialog(self):
        try:
            from java import dynamic_proxy, jclass
            activity = self._current_android_activity(jclass)
            linear = jclass('android.widget.LinearLayout')
            text_view = jclass('android.widget.TextView')
            switch = jclass('android.widget.Switch')
            button = jclass('android.widget.Button')
            layout_params = jclass('android.widget.LinearLayout$LayoutParams')
            scroll = jclass('android.widget.ScrollView')
            runnable = jclass('java.lang.Runnable')
            click = jclass('android.view.View$OnClickListener')
            dialog_click = jclass('android.content.DialogInterface$OnClickListener')
            try:
                builder_class = jclass('com.google.android.material.dialog.MaterialAlertDialogBuilder')
            except Exception:
                builder_class = jclass('android.app.AlertDialog$Builder')
            owner = self
            class Noop(dynamic_proxy(dialog_click)):
                def onClick(self, dialog, which):
                    return None
            class Click(dynamic_proxy(click)):
                def __init__(self, fn):
                    super().__init__()
                    self.fn = fn
                def onClick(self, view):
                    self.fn()
            class Show(dynamic_proxy(runnable)):
                def run(self):
                    density = float(activity.getResources().getDisplayMetrics().density)
                    pad = int(16 * density + .5)
                    root = linear(activity)
                    root.setOrientation(linear.VERTICAL)
                    root.setPadding(pad, pad // 2, pad, owner._dp(activity, 4))
                    color = jclass('android.graphics.Color')
                    typeface = jclass('android.graphics.Typeface')
                    title = text_view(activity)
                    title.setText('扫描文件类型（可多选）')
                    title.setTextColor(color.parseColor('#1E293B'))
                    title.setTextSize(12)
                    title.setTypeface(typeface.DEFAULT_BOLD)
                    root.addView(title)
                    checks = {}
                    type_grid = linear(activity)
                    type_grid.setOrientation(linear.VERTICAL)
                    row = None
                    adult = None
                    type_items = list(SCAN_FILE_TYPES.items())
                    grid_items = type_items[:-1] + [('__adult__', '18+'), type_items[-1]]
                    for index, (ext, label) in enumerate(grid_items):
                        if index % 2 == 0:
                            row = linear(activity)
                            row.setOrientation(linear.HORIZONTAL)
                            row.setGravity(16)
                            row.setPadding(0, 0, 0, 0)
                            type_row_lp = layout_params(-1, -2)
                            type_row_lp.setMargins(0, 0, 0, -owner._dp(activity, 2))
                            type_grid.addView(row, type_row_lp)
                        item = switch(activity)
                        item.setText(label)
                        item.setTextColor(color.parseColor('#334155'))
                        item.setTextSize(12)
                        item.setGravity(16)
                        item.setPadding(0, 0, 0, 0)
                        if ext == '__adult__':
                            item.setChecked(current_adult_enabled())
                            adult = item
                        else:
                            item.setChecked(ext in current_scan_extensions())
                            checks[ext] = item
                        item_lp = layout_params(0, -2, 1.0)
                        gap = owner._dp(activity, 8)
                        item_lp.setMargins(0 if index % 2 == 0 else gap, 0, gap if index % 2 == 0 else 0, 0)
                        row.addView(item, item_lp)
                    if len(grid_items) % 2:
                        blank_lp = layout_params(0, -2, 1.0)
                        blank_lp.setMargins(owner._dp(activity, 8), 0, 0, 0)
                        row.addView(text_view(activity), blank_lp)
                    root.addView(type_grid)
                    mode_spacer = text_view(activity)
                    root.addView(mode_spacer, layout_params(-1, owner._dp(activity, 10)))
                    def switch_mode():
                        mode = 'file' if current_scan_mode() == 'source' else 'source'
                        set_scan_mode(mode)
                        mode_button.setText('切换模式（当前 {}）'.format(scan_mode_text(mode)))
                        owner._toast('已切换为' + scan_mode_text(mode))
                    mode_button = button(activity)
                    mode_button.setAllCaps(False)
                    mode_button.setText('切换模式（当前 {}）'.format(scan_mode_text()))
                    mode_button.setTextSize(12)
                    mode_button.setTextColor(color.parseColor('#6C63FF'))
                    mode_button.setBackgroundDrawable(owner._rounded_bg(jclass, '#F1F5F9', owner._dp(activity, 8), '#E2E8F0'))
                    mode_button.setOnClickListener(Click(lambda: switch_mode()))
                    root.addView(mode_button, layout_params(-1, owner._dp(activity, 40)))
                    dirs_title = text_view(activity)
                    dirs_title.setText('\n设置目录列表')
                    dirs_title.setTextColor(color.parseColor('#1E293B'))
                    dirs_title.setTextSize(12)
                    dirs_title.setTypeface(typeface.DEFAULT_BOLD)
                    root.addView(dirs_title)
                    scan_dirs = current_scan_dirs()
                    for index, path in enumerate(scan_dirs, 1):
                        row = linear(activity)
                        row.setOrientation(linear.HORIZONTAL)
                        row.setGravity(16)
                        row.setPadding(0, owner._dp(activity, 8), 0, owner._dp(activity, 8))
                        enabled = switch(activity)
                        enabled.setText('{}. {}'.format(index, path))
                        enabled.setTextColor(color.parseColor('#334155'))
                        enabled.setTextSize(11)
                        enabled.setPadding(0, owner._dp(activity, 3), owner._dp(activity, 4), owner._dp(activity, 3))
                        enabled.setChecked(path in current_enabled_scan_dirs())
                        def toggle(p=path, view=enabled):
                            set_scan_dir_enabled(p, view.isChecked())
                        enabled.setOnClickListener(Click(toggle))
                        row.addView(enabled, layout_params(0, -2, 1.0))
                        delete = button(activity)
                        delete.setText('删除')
                        delete.setAllCaps(False)
                        delete.setTextColor(color.WHITE)
                        delete.setTextSize(11)
                        delete.setMinWidth(owner._dp(activity, 52))
                        delete.setMinimumWidth(owner._dp(activity, 52))
                        delete.setMinHeight(owner._dp(activity, 32))
                        delete.setMinimumHeight(owner._dp(activity, 32))
                        delete.setPadding(owner._dp(activity, 12), owner._dp(activity, 5), owner._dp(activity, 12), owner._dp(activity, 5))
                        delete.setBackgroundDrawable(owner._rounded_bg(jclass, '#EF4444', owner._dp(activity, 7)))
                        def remove(p=path):
                            remove_scan_dir(p)
                            owner._toast('已删除：' + p)
                            try:
                                dialog.dismiss()
                            except Exception:
                                pass
                            owner._open_scan_dirs_dialog()
                        delete.setOnClickListener(Click(remove))
                        row.addView(delete)
                        root.addView(row)
                        if index < len(scan_dirs):
                            divider = text_view(activity)
                            divider.setBackgroundColor(color.parseColor('#E2E8F0'))
                            root.addView(divider, layout_params(-1, owner._dp(activity, 1)))
                    def persist():
                        selected = [ext for ext, view in checks.items() if view.isChecked()]
                        save_scan_options(selected, adult.isChecked())
                    for view in checks.values():
                        view.setOnClickListener(Click(persist))
                    adult.setOnClickListener(Click(persist))
                    wrapper = scroll(activity)
                    wrapper.addView(root)
                    builder = builder_class(activity)
                    builder.setTitle('扫描设置')
                    builder.setView(wrapper)
                    def add():
                        persist()
                        dialog.dismiss()
                        owner._open_add_scan_dir_dialog()
                    builder.setNegativeButton('添加目录', Noop())
                    builder.setPositiveButton('关闭', Noop())
                    dialog = builder.create()
                    dialog.show()
                    owner._style_dialog_buttons(activity, jclass, dialog, -1)
                    dialog.getButton(-2).setOnClickListener(Click(add))
            activity.runOnUiThread(Show())
            return True, ''
        except Exception as exc:
            return False, '扫描设置弹窗打开失败：{}'.format(exc)


    def _toast(self, message):
        try:
            from java import jclass
            toast_class = jclass('android.widget.Toast')
            activity = self._current_android_activity(jclass)
            toast_class.makeText(activity, str(message), toast_class.LENGTH_SHORT).show()
            return True
        except Exception:
            return False

    def _show_message_dialog(self, title, message):
        try:
            from java import dynamic_proxy, jclass
            click_listener = jclass('android.content.DialogInterface$OnClickListener')
            runnable_class = jclass('java.lang.Runnable')
            try:
                builder_class = jclass('com.google.android.material.dialog.MaterialAlertDialogBuilder')
            except Exception:
                builder_class = jclass('android.app.AlertDialog$Builder')
            activity = self._current_android_activity(jclass)
            owner = self
            class NoopClickListener(dynamic_proxy(click_listener)):
                def onClick(self, dialog, which):
                    return None
            class ShowDialog(dynamic_proxy(runnable_class)):
                def run(self):
                    builder = builder_class(activity)
                    builder.setTitle(str(title))
                    builder.setMessage(str(message))
                    builder.setPositiveButton('确定', NoopClickListener())
                    dialog = builder.create()
                    dialog.show()
                    owner._style_dialog_buttons(activity, jclass, dialog, -1)
            activity.runOnUiThread(ShowDialog())
            return True, ''
        except Exception as exc:
            return False, '{}弹窗失败：{}'.format(title, exc)


    def _show_loading_dialog(self, title='本地加载', message='加载中，请稍候...'):
        holder = {'dialog': None}
        try:
            from java import dynamic_proxy, jclass
            runnable_class = jclass('java.lang.Runnable')
            try:
                builder_class = jclass('com.google.android.material.dialog.MaterialAlertDialogBuilder')
            except Exception:
                builder_class = jclass('android.app.AlertDialog$Builder')
            activity = self._current_android_activity(jclass)
            class ShowDialog(dynamic_proxy(runnable_class)):
                def run(self):
                    builder = builder_class(activity)
                    builder.setTitle(str(title))
                    builder.setMessage(str(message))
                    try:
                        builder.setCancelable(False)
                    except Exception:
                        pass
                    dialog = builder.create()
                    holder['dialog'] = dialog
                    dialog.show()
            activity.runOnUiThread(ShowDialog())
            return holder
        except Exception:
            self._toast(message)
            return holder

    def _dismiss_dialog_holder(self, holder):
        try:
            dialog = holder.get('dialog') if isinstance(holder, dict) else None
            if dialog is not None:
                dialog.dismiss()
        except Exception:
            pass

    def action(self, action):
        action = str(action or '')
        if action == 'local_load':
            loading = self._show_loading_dialog('本地加载', '加载中，请稍候...')
            try:
                info = generate_and_write_config()
                self._dismiss_dialog_holder(loading)
                message = '加载完成！\n站点数量：{}\n直播数量：{}\n生成文件：{}\n扫描目录：{}'.format(info['sites'], info['lives'], info['output_path'], ' | '.join(info['scan_dirs']))
                opened, err = self._show_message_dialog('本地加载', message)
                return {'code': 0, 'msg': '' if opened else message}
            except Exception as e:
                self._dismiss_dialog_holder(loading)
                message = '加载失败：{}'.format(e)
                opened, err = self._show_message_dialog('本地加载', message)
                return {'code': 0, 'msg': '' if opened else message}
        if action == 'edit_output_settings':
            opened, message = self._open_output_settings_dialog()
            return {'code': 0, 'msg': '' if opened else message}
        if action == 'edit_main_dir':
            opened, message = self._open_main_dir_dialog()
            return {'code': 0, 'msg': '' if opened else message}
        if action == 'edit_output_name':
            opened, message = self._open_output_name_dialog()
            return {'code': 0, 'msg': '' if opened else message}
        if action == 'edit_output_path':
            opened, message = self._open_output_path_dialog()
            return {'code': 0, 'msg': '' if opened else message}
        if action == 'edit_output_full':
            opened, message = self._open_output_full_dialog()
            return {'code': 0, 'msg': '' if opened else message}
        if action == 'edit_scan_dirs':
            opened, message = self._open_scan_dirs_dialog()
            return {'code': 0, 'msg': '' if opened else message}
        if action == 'edit_block_settings':
            opened, message = self._open_block_settings_dialog()
            return {'code': 0, 'msg': '' if opened else message}
        if action == 'edit_parse_settings':
            opened, message = self._open_parse_settings_dialog()
            return {'code': 0, 'msg': '' if opened else message}
        return {'code': 0, 'msg': ''}

    def searchContent(self, key, quick=False, pg='1'):
        text = str(key or '').strip()
        try:
            if text.startswith(('文件名=', 'name=')):
                value = text.split('=', 1)[1]
                path = set_output_name(value)
                return {'list': [self._card(self.OUTPUT_ID, '文件名已更新', 'download', path)]}
            if text.startswith(('路径=', 'path=')):
                value = text.split('=', 1)[1]
                path = set_output_dir(value)
                return {'list': [self._card(self.OUTPUT_ID, '保存路径已更新', 'folder', path)]}
            if text.startswith(('输出=', 'output=')):
                value = text.split('=', 1)[1]
                path = set_output_full_path(value)
                return {'list': [self._card(self.OUTPUT_ID, '输出文件已更新', 'download', path)]}
            if text.startswith(('扫描=', 'scan=')):
                value = text.split('=', 1)[1]
                dirs = set_scan_dirs(value)
                return {'list': [self._card(self.SCAN_ID, '扫描设置已更新', 'folder', ' | '.join(dirs))]}
        except Exception as e:
            return {'list': [self._card('__cc_error__', '设置失败', 'status', str(e))]}
        return {'list': self._output_setting_items() + self._scan_setting_items()}

    def playerContent(self, flag, id, vipFlags):
        return {'parse': 0, 'playUrl': '', 'url': str(id or ''), 'header': {}}

    def localProxy(self, param):
        return None

# ==================== 命令行入口 ====================

if __name__ == "__main__":
    try:
        if len(sys.argv) > 1 and sys.argv[1] in ('load', 'refresh', '生成', '刷新'):
            json.dump(generate_and_write_config(), sys.stdout, indent=2, ensure_ascii=False)
        else:
            json.dump(Spider().homeVideoContent(), sys.stdout, indent=2, ensure_ascii=False)
    except Exception as e:
        fallback = {
            "spider": "",
            "logo": "",
            "sites": [{"key": "error", "name": f"配置加载失败: {e}", "type": 1, "api": ""}]
        }
        json.dump(fallback, sys.stdout, indent=2, ensure_ascii=False)