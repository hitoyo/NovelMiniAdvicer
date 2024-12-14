# NovelMiniAdvicer
**プロトタイプ**

動作確認環境
- Windows11
- Python 3.10.6

## 概要
執筆中の小説などをサポートするためのツールです。  
リアルタイムでコメントを提供します。  
指定されたテキストファイルを一定時間ごとに読み込み、ランダムにLLMからの応答を表示します。  
  
※プロトタイプではollamaのみ利用できます。  

## 環境の準備
- [Ollama](https://github.com/ollama/ollama)をインストール[（Hugging Faceからモデルをダウンロードする方法）](https://huggingface.co/docs/hub/ollama)

- 必要なPythonパッケージをインストールします。

```
pip install -r requirements.txt
```

## アプリケーションの起動
- ターミナルで以下のコマンドを実行します。
```
python app.py
```
- ブラウザで `http://localhost:5000/` にアクセスします。