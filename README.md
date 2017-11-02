# Bkeep

複式簿記システムに基づく家計簿スクリプト

## Features:

- python 3.x
- シェルコマンドとして利用可能

## Installation:

- `# python3 setup.py install` OR
- `$ python3 setup.py install --user`

## Preparation:

- ディレクトリの作成
    - 初期化ファイルおよび記帳ファイルを保存しているディレクトリ (以下、INPUT)、および、bkeep スクリプトが計算した元帳や財務諸表データを保存するディレクトリ (以下、OUTPUT) を作成
    - `.bashrc` などに、環境変数
      ```
      export BKINPUT="INPUT へのパス"
      export BKOUTPUT="OUTPUT へのパス"
      ```
      を設定しておくと、コマンドラインからの bkeep の利用の際に、INPUT および OUTPUT のパスを指定しなくても実行できる
- 初期化ファイルの作成
    - 以下のような json ファイルを INPUT に `init.json` という名前で保存
      ```
      {
          "assets" : {
              "cash" : 20,
              "deposit" : 30
          },
          "liabilities" : {
              "credit" : 40
          },
          "equity" : {
              "retained" : 10
          },
          "income" : {
              "salary" : 0
          },
          "expenses" : {
              "dining" : 0,
              "travel" : 0,
              "insurance" : 0
          }
      }
      ```
    - "assets", "liabilities", "equity", "income", "expenses" (簿記の 5 要素) は、上記のとおりの科目名を用いなければならない
    - "equity" の要素として、"retained" (剰余金) という要素を設定しなればならない
- 記帳データの作成ルール
- 日割計算データの作成ルール

## Usage:

- コマンドライン上の利用:
    - 環境変数 BKINPUT および BKOUTPUT を設定している場合
      ```
      $ bkeep
      ```
    - 設定していない場合
      ```
      $ bkeep -i INPUT へのパス -o OUTPUT へのパス
      ```
- python 上での利用:
  ```
  # bkeep パッケージのインストール
  import bkeep
  
  # Bkeep オブジェクトの初期化
  bk = bkeep.Bkeep(
      "PATH TO INITIAL JSON FILE",
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

## Future:

- クラスを定義するファイルと実行ファイルを分離
- --point 引数によって、make の時点を指定できるようにする
- -y (--year)、-w (--week) を指定すると、年・週単位で make する
