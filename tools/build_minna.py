#!/usr/bin/env python3
"""みんなのデータ（集めた記録）から、アプリに見せる集計 public/minna.json を作る。

使い方:
  1. 記録の受け口のスプレッドシートで records シートを開き、
     ファイル → ダウンロード → カンマ区切り形式（.csv）で保存する。
  2. python3 tools/build_minna.py ダウンロードしたファイル.csv
  3. できた public/minna.json を GitHub に push する（アプリは次に開いたときに読む）。

出すのは、個人が特定できない集計だけ:
  - 場所ごとの回数だけを出す。送信ID・日付・分単位の時刻は出さない。
  - 回数が --min-count 未満、または運転手が --min-drivers 人未満のマスは出さない。
    （1人や2人の記録だけで決まるマスを出すと、その人の動きが分かってしまうため）

標準ライブラリだけで動く。
"""
import argparse
import csv
import datetime
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

NEED = ['送信ID', '日付', '乗車時', '乗車分', '乗車エリア', '乗車町']


def place(area, town):
    """シートの「エリア・町」→ アプリの中の場所の名前（駅は駅名、住所は区＋町）。"""
    area, town = (area or '').strip(), (town or '').strip()
    if not town:
        return ''
    return town if area == '駅' else area + town


def num(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def read_rows(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        rd = csv.DictReader(f)
        missing = [c for c in NEED if c not in (rd.fieldnames or [])]
        if missing:
            sys.exit('見出しに ' + '・'.join(missing) + ' がありません。records シートをそのままCSVにしたファイルを指定してください。')
        seen, out = set(), []
        for r in rd:
            sid, d = (r.get('送信ID') or '').strip(), (r.get('日付') or '').strip()[:10].replace('/', '-')
            h, m = num(r.get('乗車時')), num(r.get('乗車分'))
            try:
                day = datetime.date.fromisoformat(d)
            except ValueError:
                continue
            if not sid or h is None or m is None:
                continue
            pu = place(r.get('乗車エリア'), r.get('乗車町'))
            k = (sid, d, h, m, pu)
            if k in seen:  # 同じ記録の送り直しは1回に数える
                continue
            seen.add(k)
            dh, dm = num(r.get('降車時')), num(r.get('降車分'))
            out.append({
                'sid': sid, 'd': d, 'we': day.weekday() >= 5, 'h': h, 't': h * 60 + m,
                'dt': dh * 60 + dm if dh is not None and dm is not None else None,
                'pu': pu, 'dp': place(r.get('降車エリア'), r.get('降車町')),
            })
        return out


def build(rows, min_count, min_drivers, top_now, top_after):
    drivers = {r['sid'] for r in rows}
    out = {'v': 1, 'made': datetime.date.today().isoformat(), 'rides': 0, 'drivers': 0,
           'minCount': min_count, 'minDrivers': min_drivers, 'days': {}, 'now': {}, 'after': {}}
    if len(drivers) < min_drivers:
        return out, f'運転手が {len(drivers)} 人で、{min_drivers} 人に満たないため、中身は空にしました。'
    out['rides'], out['drivers'] = len(rows), len(drivers)
    out['from'], out['to'] = min(r['d'] for r in rows)[:7], max(r['d'] for r in rows)[:7]

    def ok(cnt, sids):
        return cnt >= min_count and len(sids) >= min_drivers

    # いま：平日／土日 × 時 × 場所
    cell = defaultdict(lambda: [0, set()])
    days = defaultdict(set)
    for r in rows:
        dt = '土日' if r['we'] else '平日'
        days[dt].add((r['sid'], r['d']))
        if r['pu']:
            c = cell[(dt, r['h'], r['pu'])]
            c[0] += 1
            c[1].add(r['sid'])
    out['days'] = {k: len(v) for k, v in days.items()}
    now = defaultdict(lambda: defaultdict(list))
    for (dt, h, p), (n, sids) in cell.items():
        if ok(n, sids):
            now[dt][str(h)].append([p, n])
    for dt in now:
        for h in now[dt]:
            now[dt][h] = sorted(now[dt][h], key=lambda x: -x[1])[:top_now]
    out['now'] = {dt: dict(v) for dt, v in now.items()}

    # 降ろしたあと：同じ人・同じ日の連続する2乗車（空き 0〜180 分）
    by = defaultdict(list)
    for r in rows:
        by[(r['sid'], r['d'])].append(r)
    pair = defaultdict(lambda: [[], set()])
    for (sid, _), rs in by.items():
        rs.sort(key=lambda r: r['t'])
        for a, b in zip(rs, rs[1:]):
            if a['dt'] is None or not a['dp'] or not b['pu']:
                continue
            gap = b['t'] - a['dt']
            if 0 <= gap <= 180:
                c = pair[(a['dp'], b['pu'])]
                c[0].append(gap)
                c[1].add(sid)
    after = defaultdict(list)
    for (dp, np_), (gaps, sids) in pair.items():
        if ok(len(gaps), sids):
            after[dp].append([np_, len(gaps), round(statistics.median(gaps))])
    out['after'] = {dp: sorted(v, key=lambda x: -x[1])[:top_after] for dp, v in after.items()}
    return out, None


def main():
    ap = argparse.ArgumentParser(description='集めた記録（records シートのCSV）から public/minna.json を作る')
    ap.add_argument('csv', help='records シートをダウンロードしたCSV')
    ap.add_argument('-o', '--out', default=str(Path(__file__).resolve().parent.parent / 'public' / 'minna.json'))
    ap.add_argument('--min-count', type=int, default=5, help='この回数に満たないマスは出さない（既定 5）')
    ap.add_argument('--min-drivers', type=int, default=3, help='この人数に満たないマスは出さない（既定 3。下げないこと）')
    ap.add_argument('--top-now', type=int, default=20)
    ap.add_argument('--top-after', type=int, default=10)
    a = ap.parse_args()
    if a.min_drivers < 3:
        print('注意: --min-drivers を 3 未満にすると、1人・2人の記録だけで決まるマスが外に出ます。', file=sys.stderr)
    rows = read_rows(a.csv)
    out, warn = build(rows, a.min_count, a.min_drivers, a.top_now, a.top_after)
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    cells = sum(len(v) for d in out['now'].values() for v in d.values())
    print(f'読んだ記録 {len(rows)} 件・運転手 {len({r["sid"] for r in rows})} 人')
    if warn:
        print(warn)
    print(f'出したマス：いま {cells}・降ろしたあと {sum(len(v) for v in out["after"].values())} → {a.out}')


if __name__ == '__main__':
    main()
