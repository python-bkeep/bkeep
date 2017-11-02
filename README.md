# Bkeep

複式簿記システムに基づく家計簿スクリプト

## Features:

- python 3.x
- シェルコマンドとして利用可能

## Installation:

- `# python setup.py install` OR
- `$ python setup.py install --user`

## Usage:

- コマンドライン上の利用:
- python 上での利用:
  ```
  # bkeep パッケージのインストール
  import bkeep
  
  # Bkeep オブジェクトの初期化
  bk = bkeep.Bkeep(
      "path to initial json file",
       datetime.date(YYYY, MM, DD) 
  )
  
  # 日々の記帳データの仕訳
  bk.journalize(
      {
        datetime.date(YYYY, MM, D1) : "bkYYYYMMD1.txt",
        datetime.date(YYYY, MM, D2) : "bkYYYYMMD2.txt",
        datetime.date(YYYY, MM, D3) : "bkYYYYMMD3.txt"
      }
  )
  
  # 日割計算データの仕訳
  bk.journalize(
      {
        datetime.date(YYYY, M1, 1) : "adjYYYYM1.txt",
        datetime.date(YYYY, M2, 1) : "adjYYYYM2.txt",
        datetime.date(YYYY, M3, 1) : "adjYYYYM3.txt"
      },
      adj = True
  )
  
  # 仕訳帳の元帳への転記
  bk.post()
  
  # 試算表の作成
  bk.prepare(
      datetime.date(START DAY),
      datetime.date(END DAY)
  )
  
  # 財務諸表の出力
  bk.make()
  ```
