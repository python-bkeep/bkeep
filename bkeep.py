#!/usr/bin/env python3

import csv, json, re, datetime

###
###     エイリアス
###

# コメントの削除
rmcomment = lambda x: re.sub(r"#.*$", "", x)

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


    def __init__(self):

        # 元帳データの作成
        self.ledger = {"assets" : {}, "liabilities" : {},
                       "equity" : {}, 
                       "expenses" : {}, "income" : {}}

    def init(self, path, date):
        """ スタートファイル (json 形式の残高試算表) を読み込み、
        self.initial に格納する関数
        date はスタート時点の日付であり、datetime.date 型とする """

        with open(path, "r", encoding="utf-8") as rf:
            self.initial = json.load(rf)

        # TB データを元帳に変換
        for x in self.initial.keys():
            for y in self.initial[x].keys():
                if self.initial[x][y]:
                    self.ledger[x][y] = [[date, self.initial[x][y]]]
                else:
                    self.ledger[x][y] = []

    def read(self, path, date):
        """ txt (コンマ区切り, utf-8) データを読み込み、
        self.journal に格納する関数 """

        with open(path, "r", encoding="utf-8", newline="") as rf:
            # csv データを借方と貸方に分類
            tmp = ((x[:2], x[2:]) for x in csv.reader(rf))
            self.journal = dict(zip(("Dr", "Cr"), zip(*tmp)))
            self._date = date

        # 金額データの整数化
        self.journal["Dr"] = list(self._alignjnl(self.journal["Dr"]))
        self.journal["Cr"] = list(self._alignjnl(self.journal["Cr"]))

        # エラー判定
        if (sum(x[1] for x in self.journal["Dr"]) !=
            sum(x[1] for x in self.journal["Cr"])):

            raise ValueError("Unbalanced in " + path)

    def apply(self):
        """ self.journal に保存されている通常の仕訳データを
        self.ledger に格納する関数。日付は self._date を参照する"""

        # 借方項目の転記
        for x in self.journal["Dr"]:
            self._applydata(self._date, x[0], x[1])
        
        # 貸方項目の転記
        for x in self.journal["Cr"]:
            self._applydata(self._date, x[0], -x[1])


    # 内部関数
    def _alignjnl(self, data):
        """ journal dict の金額部分について、コメントを除き、整数化する"""
        for x, y in data:
            x, y = rmcomment(x), rmcomment(y)
            y = int(y) if y else 0
            yield x, y

    def _applydata(self, dt, name, amount):
       """ self.apply の内部関数。
       equity の surplus (利益剰余金) 勘定に、収益・費用に追加した額
       を同時に計上する""" 
       if not name:
           pass
       elif name in self.initial["assets"].keys():
           self.ledger["assets"][name].append([dt, amount])
       elif name in self.initial["liabilities"].keys():
           self.ledger["liabilities"][name].append([dt, -amount]) 
       elif name in self.initial["equity"].keys():
           self.ledger["equity"][name].append([dt, -amount])
       elif name in self.initial["income"].keys():
           self.ledger["income"][name].append([dt, -amount])
           self.ledger["equity"]["surplus"].append([dt, -amount])
       elif name in self.initial["expenses"].keys():
           self.ledger["expenses"][name].append([dt, amount])
           self.ledger["equity"]["surplus"].append([dt, -amount])
       else:
           raise ValueError(name + " isn't included in initial data.")
