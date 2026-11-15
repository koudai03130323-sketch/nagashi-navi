// 流しナビの設定（運営者が書きかえる）
// collectUrl が空のあいだは、「記録の提供」の画面そのものが出ない（どこにも送らない）。
window.NAVI_CONFIG = {
  // 記録の受け口（apps-script/Code.gs をデプロイして出てきた「ウェブアプリのURL」）
  collectUrl: 'https://script.google.com/macros/s/AKfycbx93ycjKR7zzCpriUIfSFIZHVCnZsekgS3zkdmDwusx3q9PGOp1as-DaiGoZaEPNVsu/exec',
  // 同意画面に出す、記録の送り先（運営者）の名前。例：'流しナビ運営（山田）'
  operator: '流しナビ運営',
  // 同意画面に出す、問い合わせ先（送った記録を消してほしいときの連絡先）。例：'メール xxx@example.com'
  contact: 'このアプリを教えてくれた人に、送信IDを添えて伝えてください',
  // 同意画面に出す、集める目的。空なら決まった文が出る
  purpose: ''
};
