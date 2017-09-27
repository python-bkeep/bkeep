#!/usr/bin/env python3

import os, csv, json, re, datetime

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
        date はスタート時点の日付であり、datetime.date 型とする
        initial を journal に格納するか否かは検討課題 (しかし、もし
        そうするのであれば、initial の段階で ledger に代入する必要は
        なくなる) """

        # initial ファイルの読み込み
        with open(path, "r", encoding=encoding) as rf:
            self.initial = json.load(rf)

        # 元帳データの作成
        self.ledger = {x : {} for x in self.initial.keys()}
        for x in self.ledger.keys():
            self.ledger[x] = {y : [] for y in self.initial[x].keys()}

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

    def journalize(self, comb, encoding="utf-8"):
        """ {date : path, ...} からなる dict を受けとり、
        各組み合わせごとに self.journal に格納する関数"""

        for filedate, path in comb.items():
            
            # csv データの読み込み
            with open(path, "r", encoding=encoding, newline="") as rf:
                # 借方勘定、借方金額、貸方勘定、貸方金額、コメント
                # の形式に変換
                data = list(self._alignjnl(csv.reader(rf)))

            # journal に既に同日のデータが格納されているなら
            # extend、そうでなければ追加
            if filedate in self.journal.keys():
                self.journal[filedate].extend(data)
            else:
                self.journal[filedate] = data

            # エラー判定
            if (sum(x[1] for x in self.journal[filedate]) !=
                sum(x[3] for x in self.journal[filedate])):

                raise ValueError("Unbalanced in " + path)

    def post(self):
        """ self.journal に保存されている通常の仕訳データを
        self.ledger に格納する関数"""

        for day in sorted(self.journal.keys()):

            for x in self.journal[day]:

                # 行の貸借金額が一致するならば対照勘定、
                # そうでなければ sundry (諸口) とする
                Dcont = x[2] if x[1] == x[3] else "sundry"
                Ccont = x[0] if x[1] == x[3] else "sundry"

                # 借方項目の転記 (借方勘定、貸方勘定、借方金額、コメント)
                self._apply(day, x[0], Dcont, x[1], x[-1])

                # 貸方項目の転記 (貸方勘定、借方勘定、貸方金額、コメント)
                self._apply(day, x[2], Ccont, -x[3], x[-1])

    def read_ledger(self, path):
        """ ledger ファイル (json) を self.ledger に読み込む """
        with open(path, "r", encoding="utf-8") as rf:
            self.ledger = json.load(rf)
            self._dtparse()
            self.sort()

    def write_ledger(self, path):
        """ ledger をファイルに保存 """
        with open(path, "w") as wf:
            self._dtfmt()
            json.dump(self.ledger, wf, 
                      indent=4, ensure_ascii=False)
            self._dtparse()

    def sort(self):
        """ ledger の各勘定について、datetime.date の順でソートする """
        for elem in self.ledger.keys():
            for ac in self.ledger[elem].keys():
                self.ledger[elem][ac].sort(key=lambda x: x[0])

    # 内部関数
    def _alignjnl(self, data):
        """ journal dict の金額部分について、コメントを除き、整数化する"""
        for Dname, Damount, Cname, Camount in data:
            comment = getcmt(Camount) if cmt.search(Camount) else ""
            Camount = rmcmt(Camount)
            Damount = int(Damount) if Dname else 0
            Camount = int(Camount) if Cname else 0
            yield Dname, Damount, Cname, Camount, comment

    def _apply(self, dt, name, contrast, amount, comment):
       """ self.post の内部関数。
       equity の surplus (利益剰余金) 勘定に、収益・費用に追加した額
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
           self.ledger["equity"]["surplus"].append(MinusE)
       elif name in self.initial["expenses"].keys():
           self.ledger["expenses"][name].append(Plus)
           self.ledger["equity"]["surplus"].append(MinusE)
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
    inpdict = {strdt(re.sub(r"[^0-9]", "", x)) : os.path.join(path, x) for x in bkdata}

    bk.journalize(inpdict)
    bk.post()
