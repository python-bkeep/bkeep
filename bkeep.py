#!/usr/bin/env python3

import os, re, copy, csv, json, datetime

###
###     エイリアス
###

# コメント部分の正規表現
cmt = re.compile(r"#(.*$)")

# コメントの取得
getcmt = lambda x: cmt.search(x).group(1).strip()

# コメントの削除
rmcmt = lambda x: cmt.sub("", x).strip()

# datetime.date 型を文字列に変換
dtstr = lambda x: x.strftime("%Y%m%d")

# 文字列日付を datetime.date 型に変換
strdt = lambda x: datetime.date(int(x[:4]), int(x[4:6]), int(x[6:]))

# 月末日の計算
def maxday(x):
    try:
        return maxday(datetime.date(x.year, x.month, x.day + 1))
    except:
        return x

###
###     クラスの定義
###

class Bkeep:
    """ 総勘定元帳のデータを格納するクラス。read メソッドによって、仕訳帳
    データを変換し、データをアップデートする """

    def __init__(self, path, date, encoding="utf-8"):
        """ スタートファイル (json 形式の残高試算表) を読み込み、
        self.initial に格納する
        date はスタート時点の日付であり、datetime.date 型とする """

        # initial ファイルのパス、文字コード
        self._inittype  = path, encoding
        
        # initial ファイルの読み込み
        with open(path, "r", encoding=encoding) as rf:
            self.initial = json.load(rf)

        # 試算表データの初期化
        self.clear_tb()

        # 元帳データの初期化
        self.clear_ledger()

        # 仕訳帳データの作成
        self.journal = {date : []}

        # TB データを仕訳帳に仕訳 (_bal は beginning balance)
        for x in self.initial.keys():

            # 借方科目の場合
            if x in {"assets", "expenses"}:
                for y in self.initial[x].keys():
                    if self.initial[x][y] != 0:
                        self.journal[date].append((
                            y, self.initial[x][y],
                            "_bal", self.initial[x][y], ""
                        ))

            # 貸方科目の場合
            else:
                for y in self.initial[x].keys():
                    if self.initial[x][y] != 0:
                        self.journal[date].append((
                            "_bal", self.initial[x][y],
                            y, self.initial[x][y], ""
                        ))

    def journalize(self, comb, adj=False, encoding="utf-8"):
        """ 仕訳
        {date : path, ...} からなる dict を受けとり、
        各組み合わせごとに self.journal に格納する
        adj=True の場合、仕訳を date から月末までの日数に
        分割する"""

        for filedate, path in comb.items():
            
            # csv データの読み込み
            with open(path, "r", encoding=encoding, newline="") as rf:
                # 借方勘定、借方金額、貸方勘定、貸方金額、コメント
                # の形式に変換
                data = list(self._alignjnl(csv.reader(rf)))

            # journal に既に同日のデータが格納されているなら
            # extend、そうでなければ追加
            if adj:
                for x in data:
                    self._adjentry(filedate, x)
            else:
                self._inputtodict(filedate, data)

            # エラー判定
            if (sum(x[1] for x in self.journal[filedate]) !=
                sum(x[3] for x in self.journal[filedate])):

                raise ValueError("Unbalanced in " + path)

    def post(self):
        """ 転記
        self.journal に保存されている通常の仕訳データを
        self.ledger に格納する"""

        for day in sorted(self.journal.keys()):

            # 損益勘定の初期化
            self._incoming = []

            for x in self.journal[day]:

                # 行の貸借金額が一致するならば対照勘定、
                # そうでなければ sundry (諸口) とする
                Dcont = x[2] if x[1] == x[3] else "sundry"
                Ccont = x[0] if x[1] == x[3] else "sundry"

                # 借方項目の転記 (借方勘定、貸方勘定、借方金額、コメント)
                self._apply(day, x[0], Dcont, x[1], x[-1])

                # 貸方項目の転記 (貸方勘定、借方勘定、貸方金額、コメント)
                self._apply(day, x[2], Ccont, -x[3], x[-1])

            # 損益勘定の剰余金への振り替え
            if self._incoming:
                self.ledger["equity"]["retained"].append(
                    [day, "_incoming",
                     sum(x[2] for x in self._incoming), ""]
                )

    def prepare(self, start, end):
        """ 試算表の作成
        self.tb に格納"""

        # tb の初期化
        self.clear_tb()

        # assets, liabilities, equity
        for elem in ("assets", "liabilities", "equity"):
            for ac in self.ledger[elem].keys():
                self.tb[elem][ac] = sum(
                    x[2] for x in self.ledger[elem][ac]
                    if x[0] <= end
                )

        # expenses, income
        for elem in ("expenses", "income"):
            for ac in self.ledger[elem].keys():
                self.tb[elem][ac] = sum(
                    x[2] for x in self.ledger[elem][ac]
                    if x[0] >= start and x[0] <= end
                )

    def close(self):
        """ 締め切り
        試算表上の収益・費用の各項目を _closing を対照勘定
        として仕訳し、転記する (次年度の start ファイルを作成
        する際に活用できる) """
        pass

    def read_ledger(self, path):
        """ ledger ファイル (json) を self.ledger に読み込む """
        with open(path, "r", encoding="utf-8") as rf:
            self.ledger = json.load(rf)
            self._dtparse()

    def write_journal(self, path, encoding="utf-8"):
        """ journal をファイルに保存 """

        # 書き出し用データの作成
        rslt = [["date", "Dr", "amount",
                 "Cr", "amount", "comment"]]
        for day in sorted(self.journal.keys()):
            for x in self.journal[day]:
                rslt.append([dtstr(day)])
                rslt[-1].extend(x)

        # データの書き出し
        with open(path, "w", encoding=encoding) as wf:
            csv.writer(wf).writerows(rslt)
        

    def write_ledger(self, path, encoding="utf-8"):
        """ ledger をファイルに保存 """
        with open(path, "w", encoding=encoding) as wf:
            self._dtfmt()
            json.dump(self.ledger, wf, 
                      indent=4, ensure_ascii=False)
            self._dtparse()

    def write_tb(self, path, encoding="utf-8"):
        """ ledger をファイルに保存 """
        with open(path, "w", encoding=encoding) as wf:
            json.dump(self.tb, wf,
                      indent=4, ensure_ascii=False)

    def clear_journal(self):
        """ journal を初期化 """
        self.journal = {}

    def clear_ledger(self):
        """ ledger を初期化 """
        self.ledger = {x : {} for x in self.initial.keys()}
        for x in self.ledger.keys():
            self.ledger[x] = {y : [] for y in self.initial[x].keys()}

    def clear_tb(self):
        """ tb を初期化"""
        self.tb = {x : {} for x in self.initial.keys()}

    def sort(self):
        """ ledger の各勘定について、datetime.date の順でソートする """
        for elem in self.ledger.keys():
            for ac in self.ledger[elem].keys():
                self.ledger[elem][ac].sort(key=lambda x: x[0])

    def order(self):
        """ initial, ledger, tb について、start ファイルで指定した順序
        で並び換える (python 3.6 未満の dict が順序を記憶しない
        ことに対応する暫定措置) """

        from collections import OrderedDict as od

        path, encoding = self._inittype
        
        # start ファイルの再読み込み
        with open(path, "r", encoding=encoding) as rf:
            self.initial = json.load(rf, object_pairs_hook=od)

        # ledger のならびかえ
        ledger = copy.deepcopy(self.initial)
        for elem in self.initial.keys():
            for ac in self.initial[elem].keys():
                ledger[elem][ac] = self.ledger[elem][ac]

        self.ledger = copy.deepcopy(ledger)

        # tb のならびかえ
        if self.tb["assets"]:
            tb = copy.deepcopy(self.initial)
            for elem in self.initial.keys():
                for ac in self.initial[elem].keys():
                    tb[elem][ac] = self.tb[elem][ac]

            self.tb = copy.deepcopy(tb)

    # 内部関数
    def _alignjnl(self, data):
        """ 仕訳データの金額部分について、コメントを除き、整数化する"""
        for Dname, Damount, Cname, Camount in data:
            comment = getcmt(Camount) if cmt.search(Camount) else ""
            Camount = rmcmt(Camount)
            Damount = int(Damount) if Dname else 0
            Camount = int(Camount) if Cname else 0
            yield Dname, Damount, Cname, Camount, comment

    def _adjentry(self, date, entry):
        """ journalize に adj=T がついたときの内部関数"""
        maxd = maxday(date)
        days = (maxd - date).days + 1
        Drnum, Crnum = entry[1] // days, entry[3] // days
        ordentry = [(entry[0], Drnum,
                     entry[2], Crnum, entry[4])]
        lastentry = [(entry[0], entry[1] - ((days-1) * Drnum),
                      entry[2], entry[1] - ((days-1) * Crnum),
                      entry[4])]

        while date < maxd:
            self._inputtodict(date, ordentry)
            date += datetime.timedelta(days=1)
        else:
            self._inputtodict(date, lastentry)

    def _inputtodict(self, date, entry):
        """ journal dict に entry を入れる内部関数 """

        # date が未登録の場合は空ベクトルとする
        if date not in self.journal.keys():
            self.journal[date] = []

        # 日付の key に entry を挿入
        self.journal[date].extend(entry)

    def _apply(self, dt, name, contrast, amount, comment):
       """ self.post の内部関数。
       equity の retained (利益剰余金) 勘定に、収益・費用に追加した額
       を同時に計上する""" 

       Plus = [dt, contrast, amount, comment]
       PlusE = [dt, name, amount, comment]
       Minus = [dt, contrast, -amount, comment]
       MinusE = [dt, name, -amount, comment]

       if not name or name[0] == "_":
           pass
       elif name in self.initial["assets"].keys():
           self.ledger["assets"][name].append(Plus)
       elif name in self.initial["liabilities"].keys():
           self.ledger["liabilities"][name].append(Minus)
       elif name in self.initial["equity"].keys():
           self.ledger["equity"][name].append(Minus)
       elif name in self.initial["income"].keys():
           self.ledger["income"][name].append(Minus)
           self._incoming.append(MinusE)
       elif name in self.initial["expenses"].keys():
           self.ledger["expenses"][name].append(Plus)
           self._incoming.append(MinusE)
       else:
           raise ValueError(name + " isn't included in initial data.")

    def _dtfmt(self):
        """ self.ledger の日付を文字列に変換 """
        for elem in self.ledger.keys():
            for ac in self.ledger[elem].keys():
                for tr in self.ledger[elem][ac]:
                    if isinstance(tr[0], datetime.date):
                        tr[0] = dtstr(tr[0])

    def _dtparse(self):
        """ self.ledger の日付を datetime.date に変換 """
        for elem in self.ledger.keys():
            for ac in self.ledger[elem].keys():
                for tr in self.ledger[elem][ac]:
                    if isinstance(tr[0], str):
                        tr[0] = strdt(tr[0])

if __name__ == "__main__":

    bk = Bkeep("start.json", datetime.date(2017, 1, 1))
    path = "/home/ugos/bk"
    files = os.listdir(path)
    bkdata = [x for x in files if re.match("bk", x)]
    adjdata = [x for x in files if re.match("adj", x)]
    inpdict = {strdt(re.sub(r"[^0-9]", "", x)) : os.path.join(path, x) for x in bkdata}
    adjdict = {datetime.date(int(re.sub(r"[^0-9]", "", x)[:4]), int(re.sub(r"[^0-9]", "", x)[4:]), 1) : os.path.join(path, x) for x in adjdata}

    bk.journalize(inpdict)
    bk.journalize(adjdict, adj=True)
    bk.post()
    bk.prepare(datetime.date(2017, 9, 1), datetime.date(2017, 9, 30))
    bk.order()
    bk.write_journal("tmp.csv")
    bk.write_ledger("tmp.json")
    bk.write_tb("tb.json")
