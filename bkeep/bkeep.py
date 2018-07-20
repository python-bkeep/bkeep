# -*- coding: utf-8 -*-

import sys, os, re, copy, csv, json, datetime
from collections import OrderedDict as od

###
###     エイリアス
###

# コメント部分の正規表現
cmt = re.compile(r"#(.*$)")
nnum = re.compile(r"[^0-9]")

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
    """ datetime.date を指定すると、その月の月末日を返す """
    try:
        return maxday(datetime.date(x.year, x.month, x.day + 1))
    except:
        return x

# datetime と ファイル名の組み合わせの作成
# ファイル名からなる iterable を受け取り、dict を返す
def mkfiledict(files):
    rslt = {}
    for path in files:

        # datetime 部分の抽出
        dt = nnum.sub("", os.path.basename(path))

        # datetime.date への変換
        if len(dt) == 6:        # YYYYMM
            dt = datetime.date(int(dt[:4]), int(dt[4:]), 1)
        elif len(dt) == 8:      # YYYYMMDD
            dt = strdt(dt)
        else:                   # 破損データ
            dt = None

        # dict への格納
        if dt:
            rslt[dt] = path

    # 結果の出力
    return rslt

# bk ファイルや adj ファイルを列挙する関数
def pathtract(path, match):
    """ path と match を指定すると、mkfiledict 関数を利用して
    datetime と file の組み合わせを返す関数 """
    opj, ol = os.path.join, os.listdir
    files = (opj(path, x) for x in ol(path) if re.match(match, x))
    return mkfiledict(files)


###
###     クラスの定義
###

class Bkeep:
    """ 総勘定元帳のデータを格納するクラス。read メソッドによって、仕訳帳
    データを変換し、データをアップデートする """

    def __init__(self, path, date, encoding="utf-8", order=True):
        """ スタートファイル (json 形式の残高試算表) を読み込み、
        self.initial に格納する
        date はスタート時点の日付であり、datetime.date 型とする """

        # initial ファイルのパス、文字コード
        self._inittype = path, encoding

        # ordered の属性
        self._ordered = order
        
        # initial ファイルの読み込み
        with open(path, "r", encoding=encoding) as rf:
            if order:
                self.initial = json.load(rf, object_pairs_hook=od)
            else:
                self.initial = json.load(rf)

        # nested list の作成
        self._mkNamesDict()

        # 財務諸表データの初期化
        self.fs = {}

        # 試算表データの初期化
        self.clear_tb()

        # 元帳データの初期化
        self.clear_ledger()

        # 仕訳帳データの作成
        self.journal = {date : []}

        # init データを仕訳帳に仕訳 (_bal は beginning balance)
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


    # 仕訳・転記・締切

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

    def close(self):
        """ 締め切り
        試算表上の収益・費用の各項目を _closing を対照勘定
        として仕訳し、転記する (次年度の start ファイルを作成
        する際に活用できる) """
        pass


    # 試算表・財務諸表の作成

    def prepare(self, start, end):
        """ 試算表の作成
        self.tb に格納"""

        # tb の初期化
        self.clear_tb()

        # tb の名前を記憶
        self._tbname = (start, end)

        # assets, liabilities, equity
        for elem in ("assets", "liabilities", "equity"):
            for ac in self.initial[elem].keys():
                self.tb[elem][ac] = sum(
                    x[2] for x in self.ledger[elem][ac]
                    if x[0] <= end
                )

        # expenses, income
        for elem in ("expenses", "income"):
            for ac in self.initial[elem].keys():
                self.tb[elem][ac] = sum(
                    x[2] for x in self.ledger[elem][ac]
                    if x[0] >= start and x[0] <= end
                )

    def make(self, add=False):
        """ 貸借対照表・損益計算書の作成 
        add=True ならば、データを追加する
        期間は self._tbname を参照する"""

        # add=False なら self.fs を初期化
        if not add:
            self.fs = {}

        # fs 項目の初期化
        self.fs[self._tbname] = self.clear_fs()
        fs = self.fs[self._tbname]

        # fs 項目の格納
        for elem in fs.keys():

            # tb 項目のプールの作成
            pool = [x.split(":") for x in self._acquire_keys(self.tb)]

            # fs の各項目の計算対象の抽出
            for x in fs[elem].keys():
                s = x.replace(":", "")
                trg = (":".join(y) for y in pool if s in y) 

                # 計算対象の合計と格納
                fs[elem][x] = sum(self.tb[elem][y] for y in trg)

            # 項目の合計値の格納
            fs[elem][elem.upper()] = sum(self.tb[elem].values())
                

    def cat(self, path=None, encoding="utf-8"):
        """ 貸借対照表・損益計算書の作成
        self.fs を参照する """

        fs = self.fs[self._tbname]
        total = {x : fs[x][x.upper()] for x in fs.keys()}
        earn = total["income"] - total["expenses"]
        epi = earn / total["income"] if total["income"] else 0

        # 費用項目のデフレート
        # income に唯一の salary が存在するならば、salary をデフレーターにし、
        # そうでない場合は、収益総額をデフレーターにする
        namebox = [s for s in fs['income'].keys() if 'salary' in s]
        exdeflator = fs['income'][namebox[0]] if len(namebox) == 1 else total['income']

        # 勘定科目名の最大値
        n = max(len(x.replace(":", "  ")) for x in self._acquire_keys(fs))
        m = max(len("{:,d}".format(x)) for x in self._acquire_values(fs)) 
        m = max([5, m])

        # path が指定されている場合はそこに出力する
        if path:
            sys.stdout = open(path, "w", encoding=encoding)

        # 結果の print (assets ~ expenses)
        for elem in fs.keys():
            print(elem.upper())
            print("=============")
            if elem == 'expenses':
                for x in list(fs[elem].items())[:-1]:
                    print("{:<{}}{:>{},d}{:>{}.2%}".format(x[0].replace(":", "  "), n+1, x[1], m, (x[1] / exdeflator), m))
                print("-------------")
                print("{:<{}}{:>{},d}{:>{}.2%}\n".format("TOTAL", n+1, total[elem], m, (total[elem] / exdeflator), m))
            else:
                for x in list(fs[elem].items())[:-1]:
                    print("{:<{}}{:>{},d}".format(x[0].replace(":", "  "), n+1, x[1], m))
                print("-------------")
                print("{:<{}}{:>{},d}\n".format("TOTAL", n+1, total[elem], m))

        # 結果の print (summary)
        print("SUMMARY")
        print("=============")
        print("{:<{}}{:>{},d}".format("earn", n+1, earn, m))
        print("{:<{}}{:>{}.2%}".format("epi", n+1, epi, m))

        # print の出力先を元に戻す
        if path:
            sys.stdout.close()
            sys.stdout = sys.__stdout__


    # 月次・週次データの作成

    def mkMonth(self, start, end):
        """ 月次 csv 用の start -- end の組み合わせ作成 """

        while start <= end:
            mid = maxday(start)
            mid = mid if mid < end else end
            yield (start, mid)
            start = mid + datetime.timedelta(days=1)

    def mkSpan(self, start, end, span=7):
        """ 任意の期間の start -- end の組み合わせ作成
        起点は end
        逆順になっているため、利用側で reversed を実施する """

        while start <= end:
            mid = end - datetime.timedelta(days=span-1)
            mid = mid if mid > start else start
            yield (mid, end)
            end = mid - datetime.timedelta(days=1)

    def calcSpan(self, span):
        """ span (start -- end のタプルからなる iterable) をもとに
        prepare, make をおこなう """

        self.fs = {}
        for x in span:
            self.prepare(*x)
            self.make(add=True)

    def saveSpan(self, path, encoding="utf-8"):
        """ 複数期間からなる FS を path に保存する """

        span = sorted(self.fs.keys(), key=lambda x: (x[1], x[0]))
        name = ["start", "end", "earn", "epi"]
        name.extend(self._acquire_keys(self.fs[self._tbname]))
        rslt = [name]
        for prd in span:
            # start と end
            x = list(prd)

            # income と expenses の計算
            R = self.fs[prd]["income"]["INCOME"]
            L = self.fs[prd]["expenses"]["EXPENSES"]

            # earn の計算
            x.append(R - L)

            # epi の計算
            x.append(x[-1] / R if R else 0)

            # 他の部分の追加
            x.extend(self._acquire_values(self.fs[prd]))

            # rslt への append
            rslt.append(x)

        # データの保存
        with open (path, "w", encoding=encoding) as wf:
            csv.writer(wf).writerows(rslt)



    # 特殊なデータの読み込み・初期化

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
        if self._ordered:
            self.tb = od()
            for x in self.initial.keys():
                self.tb[x] = od()
        else:
            self.tb = {x : {} for x in self.initial.keys()}

    def clear_fs(self):
        """ fs の要素を初期化 """

        # ordered 属性がある場合、od を適用
        cldict = od if self._ordered else dict

        # box は要素の重複をチェックする集合
        fs, box = cldict(), set()

        # 5 要素のループ
        for elem in self.initial.keys():

            fs[elem] = cldict()

            # 勘定科目のループ
            for accs in self.initial[elem].keys():

                spc = ""    # 階層ごとにインデント

                # 階層のループ
                for x in accs.split(":"):
                    if x not in box:
                        fs[elem][spc + x] = 0
                        box.add(x)

                    # インデントの追加
                    spc += ":"

        # 返り値
        return fs

    def sort(self):
        """ ledger の各勘定について、datetime.date の順でソートする """
        for elem in self.ledger.keys():
            for ac in self.ledger[elem].keys():
                self.ledger[elem][ac].sort(key=lambda x: x[0])


    # 内部関数

    def _mkNamesDict(self):
        keys = self._acquire_keys(self.initial)
        self._nestdict = {x.split(":")[-1] : x for x in keys}

    def _getanm(self, name):
        """ 省略形 (最終項目名のみ) 表示を正式名称に変換する """
        return self._nestdict[name] if name else ""

    def _alignjnl(self, data):
        """ 仕訳データの金額部分について、コメントを除き、整数化する"""
        for Dname, Damount, Cname, Camount in data:
            comment = getcmt(Camount) if cmt.search(Camount) else ""
            Camount = rmcmt(Camount)
            Damount = int(Damount) if Dname else 0
            Camount = int(Camount) if Cname else 0
            Dname, Cname = self._getanm(Dname), self._getanm(Cname)
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

    def _makeData(self, start, end, names=False):
        """ 各種 calc のために prepare, make する """

        # 試算表の作成
        self.prepare(start, end)

        # 列名作成の場合
        if names:

            # データの作成 (列名の作成)
            rslt = ["start", "end", "earn", "epi"]
            for elem in self.tb.keys():
                rslt.extend(self.tb[elem].keys())
                rslt.append(elem.upper())

        # データ出力の場合
        else:

            # 各要素の合計、利益、利益率の計算
            total = {x : sum(self.tb[x].values()) for x in self.tb.keys()}
            earn = total["income"] - total["expenses"]
            epi = earn / total["income"] if total["income"] else 0

            # 出力データの作成
            rslt = [dtstr(start), dtstr(end), earn, epi]
            for elem in self.tb.keys():
                rslt.extend(self.tb[elem].values())
                rslt.append(total[elem])

        # データの出力
        return rslt


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

    def _acquire_keys(self, data):
        """ self.initial から要素・勘定科目名を抽出する関数"""
        for elem in data.keys():
            for x in data[elem].keys():
                yield x

    def _acquire_values(self, data):
        """ data (tb もしくは fs) から各科目の金額を抽出する関数 """
        for elem in data.keys():
            for x in data[elem].values():
                yield x
