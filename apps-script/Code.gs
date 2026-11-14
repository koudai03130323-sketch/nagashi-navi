/**
 * 流しナビ：記録の受け口（Google Apps Script）
 *
 * 役割: アプリから「同意のうえで送られた」記録を、このスクリプトに紐づいたスプレッドシートに1行ずつ追記する。
 * 読み出しの口は作らない（doGet は状態確認の文字列だけ返す）。
 *
 * 設置手順（運営者が1回だけ）:
 *  1. Googleスプレッドシートを新規作成 → 拡張機能 → Apps Script を開き、このファイルの中身を貼る
 *  2. デプロイ → 新しいデプロイ → 種類「ウェブアプリ」
 *     実行ユーザー: 自分 / アクセスできるユーザー: 全員
 *  3. 表示された「ウェブアプリのURL」を、アプリの public/config.js の collectUrl に入れる
 *  ※ このファイルを直したら、デプロイ → デプロイを管理 → 編集 → バージョン「新バージョン」で出し直す（URLは変わらない）
 *
 * アプリが送ってくる形（Content-Type は text/plain。中身はJSON）:
 *  { consent: true, v: 同意文の版, sid: 送信ID, bid: かたまりの印, rows: [{ d, wd, h, m, dh, dm, pa, pt, da, dt, km }, ...] }
 *
 * まだ未実装: 集計シートの作成。
 */

const SHEET_NAME = 'records';
const MAX_ROWS_PER_POST = 2000;
const MAX_POSTS_PER_10MIN = 12; // 同じ送信IDから10分に受け付ける回数（アプリは1000行ずつに分けて送る）
const HEADER = ['受信日時', '送信ID', '日付', '曜日', '乗車時', '乗車分', '降車時', '降車分', '乗車エリア', '乗車町', '降車エリア', '降車町', '営業km'];

function doGet() {
  return ContentService.createTextOutput('ok');
}

function doPost(e) {
  try {
    const body = JSON.parse(e.postData.contents);
    // 形式チェック: 同意フラグ・送信ID（端末ごとのランダム値。個人名ではない）・行の配列
    if (body.consent !== true || typeof body.sid !== 'string' || !/^[a-z0-9]{8,40}$/.test(body.sid)) return out({ ok: false, error: 'bad_request' });
    if (!Array.isArray(body.rows) || body.rows.length === 0 || body.rows.length > MAX_ROWS_PER_POST) return out({ ok: false, error: 'bad_rows' });

    // 同じ送信IDからの送信は、10分に MAX_POSTS_PER_10MIN 回まで
    const cache = CacheService.getScriptCache();
    const sidKey = 'sid_' + body.sid;
    const count = Number(cache.get(sidKey) || 0);
    if (count >= MAX_POSTS_PER_10MIN) return out({ ok: false, error: 'too_many_requests' });
    cache.put(sidKey, String(count + 1), 600);

    // 同じかたまりの送り直し（返事が届かずアプリがやり直したとき）は、二重に書かない
    const bidKey = typeof body.bid === 'string' && /^[a-z0-9]{4,20}$/.test(body.bid) ? 'bid_' + body.sid + '_' + body.bid : null;
    if (bidKey && cache.get(bidKey)) return out({ ok: true, saved: 0, dup: true });

    const now = new Date();
    const clean = [];
    for (const r of body.rows) {
      // アプリ側で町名までに丸めたものだけを受け付ける（丁目の番号や番地は入れない）
      if (!/^\d{4}-\d{2}-\d{2}$/.test(r.d)) continue;
      const s = (v, n) => (typeof v === 'string' ? v.slice(0, n) : '');
      const n = (v, lo, hi) => (typeof v === 'number' && v >= lo && v <= hi ? v : '');
      clean.push([now, body.sid, r.d, s(r.wd, 1), n(r.h, 0, 30), n(r.m, 0, 59), n(r.dh, 0, 30), n(r.dm, 0, 59), s(r.pa, 20), s(r.pt, 40).replace(/\d+$/, ''), s(r.da, 20), s(r.dt, 40).replace(/\d+$/, ''), n(r.km, 0, 300)]);
    }
    if (!clean.length) return out({ ok: false, error: 'no_valid_rows' });

    // 同時に届いたときに行が重ならないよう、書き込みは1つずつ
    const lock = LockService.getScriptLock();
    lock.waitLock(20000);
    try {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const sh = ss.getSheetByName(SHEET_NAME) || ss.insertSheet(SHEET_NAME);
      if (sh.getLastRow() === 0) sh.appendRow(HEADER);
      sh.getRange(sh.getLastRow() + 1, 1, clean.length, HEADER.length).setValues(clean);
    } finally {
      lock.releaseLock();
    }
    if (bidKey) cache.put(bidKey, '1', 21600);
    return out({ ok: true, saved: clean.length });
  } catch (err) {
    return out({ ok: false, error: 'server_error' });
  }
}

function out(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
