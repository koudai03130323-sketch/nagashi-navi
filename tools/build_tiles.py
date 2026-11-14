"""地図の下絵（国土地理院 淡色地図）を用意するスクリプト。

使い方: python3 tools/build_tiles.py   （要: pip install pillow）
- z13 のタイルを 4x4 枚ずつ 1024px の JPEG にまとめ public/tiles/c13_<x>_<y>.jpg に保存
- 全体の下敷きとして z11 を 1 枚にまとめ public/tiles/o11.jpg に保存
- 範囲情報を public/tilesmeta.json に書く（build_geo.py が geo.json に入れる）
範囲は東京都・神奈川県（島しょ部を除く）。出典「国土地理院」をアプリ内に表示すること。
タイル取得は国土地理院の利用規約に従い、必要な範囲だけ・同時接続を絞って行う。
"""
import json, math, os, urllib.request, concurrent.futures as cf
from PIL import Image

LON0, LAT0, LON1, LAT1 = 138.94, 35.13, 139.93, 35.90
URL = 'https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{x}/{y}.png'
CACHE = 'tools/.cache/tiles'
OUT = 'public/tiles'


def tile(lon, lat, z):
    n = 2 ** z
    x = (lon + 180) / 360 * n
    y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n
    return int(x), int(y)


def fetch(z, x, y):
    p = f'{CACHE}/{z}_{x}_{y}.png'
    if not os.path.exists(p):
        try:
            with urllib.request.urlopen(URL.format(z=z, x=x, y=y), timeout=30) as r:
                open(p, 'wb').write(r.read())
        except Exception:
            return None
    return p


def main():
    os.makedirs(CACHE, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    x0, y0 = tile(LON0, LAT1, 13)
    x1, y1 = tile(LON1, LAT0, 13)
    jobs = [(13, x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]
    ox0, oy0 = tile(LON0, LAT1, 11)
    ox1, oy1 = tile(LON1, LAT0, 11)
    jobs += [(11, x, y) for x in range(ox0, ox1 + 1) for y in range(oy0, oy1 + 1)]
    with cf.ThreadPoolExecutor(4) as ex:
        list(ex.map(lambda j: fetch(*j), jobs))
    chunks = []
    for cx in range(x0, x1 + 1, 4):
        for cy in range(y0, y1 + 1, 4):
            im = Image.new('RGB', (1024, 1024), (255, 255, 255))
            for dx in range(4):
                for dy in range(4):
                    p = f'{CACHE}/13_{cx + dx}_{cy + dy}.png'
                    if os.path.exists(p) and cx + dx <= x1 and cy + dy <= y1:
                        im.paste(Image.open(p).convert('RGB'), (dx * 256, dy * 256))
            name = f'tiles/c13_{cx}_{cy}.jpg'
            im.save(f'public/{name}', quality=60, optimize=True, progressive=True)
            chunks.append([cx, cy, name])
    w, h = ox1 - ox0 + 1, oy1 - oy0 + 1
    ov = Image.new('RGB', (w * 256, h * 256))
    for x in range(ox0, ox1 + 1):
        for y in range(oy0, oy1 + 1):
            p = f'{CACHE}/11_{x}_{y}.png'
            if os.path.exists(p):
                ov.paste(Image.open(p).convert('RGB'), ((x - ox0) * 256, (y - oy0) * 256))
    ov.save('public/tiles/o11.jpg', quality=60, optimize=True)
    # 注意: アプリ側（drawMap）は o11 を 7x7 タイル前提で配置している。範囲を変えたら index.html の 7 * TS * f も直すこと
    json.dump({'z': 13, 'chunks': chunks, 'ov': [ox0, oy0, 'tiles/o11.jpg'], 'ovSize': [w, h]}, open('public/tilesmeta.json', 'w'))
    print('chunks', len(chunks), 'overview', w, h)


if __name__ == '__main__':
    main()
