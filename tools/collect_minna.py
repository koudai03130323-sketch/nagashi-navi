#!/usr/bin/env python3
"""受け口のシートから、前回からあとに届いた記録を、運営者の手元の「ためておく場所」に足していく。

使い方:
  python3 tools/collect_minna.py 受け口をダウンロードしたCSV --store ためておくCSV
  python3 tools/collect_minna.py --store ためておくCSV --forget 送信ID   （「消してほしい」と頼まれたとき）

- ためておくCSVは、運転手の記録そのもの（日付・分まで）が入るので、このリポジトリの外に置く。
  リポジトリは公開なので、絶対に public/ や docs/ に置かない・コミットしない。
- 件数が少なくても、届いた分は全部ためる（同じ記録の送り直しは1回に数える）。
- そのあと、ためた全部から public/minna.json を作り直す。アプリに出すのは build_minna.py の決まり
  （回数5回以上・運転手3人以上のマスだけ。日付・分・送信IDは出さない）のまま。
- 受け口のシートで行を消しても、ためておくCSVには残る。消す依頼は --forget でこちらからも消す。

標準ライブラリだけで動く。
"""
import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_minna  # noqa: E402

HEADER = ['受信日時', '送信ID', '日付', '曜日', '乗車時', '乗車分', '降車時', '降車分', '乗車エリア', '乗車町', '降車エリア', '降車町', '営業km', '乗車丁目', '降車丁目']
NEED = HEADER[1:13]  # 丁目の2列は、あとから足した列なので、なくてもよい
SID = re.compile(r'^[a-z0-9]{8,40}$')


def norm_date(v):
    v = (v or '').strip()[:10].replace('/', '-')
    m = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})$', v)
    return f'{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}' if m else ''


def key(r):
    return (r['送信ID'], r['日付'], str(build_minna.num(r['乗車時'])), str(build_minna.num(r['乗車分'])), r['乗車エリア'], r['乗車町'])


def read(path):
    p = Path(path)
    if not p.exists():
        return []
    with open(p, encoding='utf-8-sig', newline='') as f:
        rd = csv.DictReader(f)
        missing = [c for c in NEED if c not in (rd.fieldnames or [])]
        if missing:
            sys.exit(f'{path} の見出しに ' + '・'.join(missing) + ' がありません。受け口の records シートをCSVにしたものを指定してください。')
        out = []
        for r in rd:
            r = {k: (r.get(k) or '').strip() for k in HEADER}
            r['日付'] = norm_date(r['日付'])
            # 形の合わない行（でたらめに送られたものなど）はためない
            if not SID.match(r['送信ID']) or not r['日付'] or build_minna.num(r['乗車時']) is None or build_minna.num(r['乗車分']) is None:
                continue
            out.append(r)
        return out


def write(path, rows):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix('.tmp')
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        w.writerows(rows)
    tmp.replace(p)


def main():
    ap = argparse.ArgumentParser(description='受け口の記録を、前回からの分だけ手元にためていき、minna.json を作り直す')
    ap.add_argument('csv', nargs='?', help='受け口の records シートをダウンロードしたCSV')
    ap.add_argument('--store', required=True, help='ためておくCSV（リポジトリの外に置く）')
    ap.add_argument('--forget', metavar='送信ID', help='この送信IDの記録を、ためておくCSVから消す')
    ap.add_argument('--no-build', action='store_true', help='minna.json は作り直さない')
    a = ap.parse_args()

    repo = Path(__file__).resolve().parent.parent
    if repo in Path(a.store).resolve().parents:
        sys.exit('ためておくCSVは、リポジトリの外に置いてください（リポジトリは公開です）。')

    store = read(a.store)
    seen = {key(r) for r in store}
    before, before_sids = len(store), {r['送信ID'] for r in store}

    if a.forget:
        store = [r for r in store if r['送信ID'] != a.forget]
        print(f'送信ID {a.forget} の記録を {before - len(store)} 件消しました。')
    if a.csv:
        new = []
        for r in read(a.csv):
            k = key(r)
            if k in seen:
                continue
            seen.add(k)
            new.append(r)
        store += new
        by = Counter(r['送信ID'] for r in new)
        print(f'前回からの分：{len(new)} 件（{len(by)} 人分）' + ('' if new else '　新しい記録はありませんでした。'))
        for sid, n in by.most_common():
            print(f'  {sid}  {n} 件' + ('' if sid in before_sids else '  ← はじめての人'))
    write(a.store, store)
    sids = {r['送信ID'] for r in store}
    days = [r['日付'] for r in store]
    print(f'ためた記録の合計：{len(store)} 件・{len(sids)} 人' + (f'（{min(days)} 〜 {max(days)}）' if days else ''))

    if not a.no_build:
        out, warn = build_minna.build(build_minna.read_rows(a.store), 5, 3, 20, 10)
        dest = repo / 'public' / 'minna.json'
        dest.write_text(json.dumps(out, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
        cells = sum(len(v) for d in out['now'].values() for v in d.values())
        print(f'アプリに出す集計：いま {cells} マス・降ろしたあと {sum(len(v) for v in out["after"].values())} 件 → public/minna.json')
        if warn:
            print(warn)


if __name__ == '__main__':
    main()
