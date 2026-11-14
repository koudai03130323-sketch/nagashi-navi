"""住所・駅の位置辞書 public/geo.json を作り直すスクリプト。

使い方: python3 tools/build_geo.py
- 住所: Geolonia 住所データ（GitHub上の api/ja/<都道府県>/<市区町村>.json）から、東京都・神奈川県の町丁目の代表点を取る
- 駅: open-data-jp-railway-stations の stations.json から東京都(13)・神奈川県(14)の駅
- 地図タイルの範囲情報（tiles）は build_tiles.py が書いた public/tilesmeta.json から入れる
出典表示: 「住所の位置：Geolonia 住所データ」「駅の位置：open-data-jp-railway-stations」をアプリ内に残すこと。
"""
import json, os, re, unicodedata, urllib.parse, urllib.request, concurrent.futures as cf

PREFS = ['東京都', '神奈川県']
CACHE = 'tools/.cache/geolonia'
BASE = 'https://raw.githubusercontent.com/geolonia/japanese-addresses/master/api/ja'
STATIONS_URL = 'https://raw.githubusercontent.com/piuccio/open-data-jp-railway-stations/master/stations.json'
KN = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}


def kan(s):
    if s.isdigit():
        return int(s)
    if '十' in s:
        a, b = s.split('十')
        return (KN.get(a, 1) if a else 1) * 10 + (KN.get(b, 0) if b else 0)
    return KN.get(s, 0)


def nz(s):
    return unicodedata.normalize('NFKC', s).replace('ヶ', 'ケ').replace('之', 'の')


def get(url, path):
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with urllib.request.urlopen(url, timeout=60) as r, open(path, 'wb') as f:
            f.write(r.read())
    return json.load(open(path))


def main():
    ja = get(BASE + '.json', f'{CACHE}/ja.json')
    jobs = [(p, c) for p in PREFS for c in ja[p]]

    def fetch(pc):
        p, c = pc
        return p, c, get(f'{BASE}/{urllib.parse.quote(p)}/{urllib.parse.quote(c)}.json', f'{CACHE}/{p}_{c}.json')

    areas = {}
    with cf.ThreadPoolExecutor(6) as ex:
        for pref, city, towns_raw in ex.map(fetch, jobs):
            m = re.match(r'^(.+?市)(.+区)$', city)
            area = nz(m.group(2) if m else city)  # 政令市は区名で引く（例: 宮前区）
            towns = {}
            for t in towns_raw:
                if t.get('lat') is None:
                    continue
                name = nz(t['town'])
                mm = re.match(r'^(.+?)([一二三四五六七八九十]+)丁目$', name)
                base = mm.group(1) if mm else name
                e = towns.setdefault(base, {'pts': [], 'ch': {}})
                e['pts'].append((t['lat'], t['lng']))
                if mm:
                    e['ch'][kan(mm.group(2))] = [round(t['lat'], 5), round(t['lng'], 5)]
            out = {}
            for k, e in towns.items():
                la = sum(p[0] for p in e['pts']) / len(e['pts'])
                lo = sum(p[1] for p in e['pts']) / len(e['pts'])
                out[k] = [round(la, 5), round(lo, 5)] + ([e['ch']] if e['ch'] else [])
            areas.setdefault(area, []).append({'city': city, 'towns': out})
    # 同じ区名が複数ある場合（中央区・南区・緑区）は 東京23区/横浜市 を優先し、相模原市を後ろに
    for v in areas.values():
        v.sort(key=lambda c: c['city'].startswith('相模原'))

    st = get(STATIONS_URL, f'{CACHE}/stations.json')
    stations = {}
    for g in st:
        if g['prefecture'] not in ('13', '14'):
            continue
        for s in g['stations']:
            stations.setdefault(nz(s['name_kanji']), [round(s['lat'], 5), round(s['lon'], 5)])

    tiles = json.load(open('public/tilesmeta.json'))
    json.dump({'areas': areas, 'stations': stations, 'tiles': tiles}, open('public/geo.json', 'w'), ensure_ascii=False, separators=(',', ':'))
    print('areas', len(areas), 'stations', len(stations))


if __name__ == '__main__':
    main()
