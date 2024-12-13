# app.py

from flask import Flask, jsonify, render_template, request, redirect
import threading
import queue
import os
import json
import atexit
import chardet
import ast
from trigger_manager import TriggerManager
from random_trigger import RandomTrigger
from api_client import get_comment_from_llm
from logger import get_logger


def create_app():
    app = Flask(__name__)

    # 設定ファイルのパス
    settings_file = "settings.json"

    # メッセージを保持するキュー
    app.message_queue = queue.Queue()

    @app.route("/", methods=["GET", "POST"])
    def index():
        if request.method == "POST":
            # フォームから設定を取得
            filepath = request.form["filepath"].strip()
            model_name = request.form["model_name"].strip()
            system_prompt = request.form["system_prompt"].strip()
            min_interval_str = request.form.get("min_interval", "").strip()
            max_interval_str = request.form.get("max_interval", "").strip()
            context_str = request.form.get("context", "").strip()

            # サーバーサイドでのバリデーション
            errors = []
            if not filepath:
                errors.append("ファイルパスを入力してください。")
            if not model_name:
                errors.append("モデル名を入力してください。")
            if not system_prompt:
                errors.append("システムプロンプトを入力してください。")
            try:
                min_interval = int(min_interval_str)
            except ValueError:
                errors.append("最小インターバルは整数値で入力してください。")
            try:
                max_interval = int(max_interval_str)
            except ValueError:
                errors.append("最大インターバルは整数値で入力してください。")

            if errors:
                error_message = "\n".join(errors)
                settings = {
                    "filepath": filepath,
                    "model_name": model_name,
                    "system_prompt": system_prompt,
                    "min_interval": min_interval_str,
                    "max_interval": max_interval_str,
                }
                return render_template("error.html", error_message=error_message)

            # 設定を辞書にまとめる
            settings = {
                "filepath": filepath,
                "model_name": model_name,
                "system_prompt": system_prompt,
                "min_interval": min_interval,
                "max_interval": max_interval,
                "context_str": context_str,
            }

            # アプリケーションを初期化
            try:
                success = initialize_app(app, settings)
                if success:
                    # 設定を保存
                    save_settings(settings_file, settings)
                    return redirect("/chat")
                else:
                    error_message = "アプリケーションの初期化に失敗しました。設定を確認してください。"
                    return render_template("error.html", error_message=error_message)
            except Exception as e:
                # エラー詳細をテンプレートに渡す
                error_message = str(e)
                return render_template("error.html", error_message=error_message)
        else:
            settings = load_settings(settings_file)
            return render_template("index.html", settings=settings)

    @app.route("/chat")
    def chat():
        return render_template("chat.html")

    @app.route("/get_messages")
    def get_messages():
        messages = []
        while not app.message_queue.empty():
            message = app.message_queue.get()
            messages.append(message)
        return jsonify(messages)

    @app.route("/pause", methods=["POST"])
    def pause():
        if hasattr(app, "trigger_manager") and app.trigger_manager:
            app.trigger_manager.on_pause()
        if hasattr(app, "random_trigger") and app.random_trigger:
            app.random_trigger.pause()
        return jsonify({"status": "success"})

    @app.route("/resume", methods=["POST"])
    def resume():
        if hasattr(app, "trigger_manager") and app.trigger_manager:
            app.trigger_manager.on_resume()
        if hasattr(app, "random_trigger") and app.random_trigger:
            app.random_trigger.resume()
        return jsonify({"status": "success"})

    @app.route("/error")
    def error():
        error_message = request.args.get(
            "error_message", "不明なエラーが発生しました。"
        )
        return render_template("error.html", error_message=error_message)

    # アプリケーション終了時に呼び出す関数を登録
    def on_exit():
        if hasattr(app, "trigger_manager") and app.trigger_manager:
            app.trigger_manager.save_log()
            if hasattr(app, "random_trigger") and app.random_trigger:
                app.random_trigger.stop()

    atexit.register(on_exit)

    return app


def load_settings(settings_file):
    default_settings = {
        "filepath": "",
        "model_name": "llama3.2",
        "system_prompt": "ロールプレイしてください。あなたは文芸好きの女の子で、執筆中の私を見守っています。あなたはセリフのみ返します。",
        "min_interval": 5,
        "max_interval": 30,
    }

    if os.path.exists(settings_file):
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                settings = json.load(f)
                # 必要なキーが揃っているか確認
                for key in default_settings.keys():
                    if key not in settings:
                        print(
                            f"設定ファイルに '{key}' が見つかりません。デフォルト値を使用します。"
                        )
                        settings[key] = default_settings[key]
                return settings
        except json.JSONDecodeError as e:
            print(f"設定ファイルの読み込み中にエラーが発生しました: {e}")
            print("デフォルトの設定値を使用します。")
            return default_settings
    else:
        print("設定ファイルが存在しません。デフォルトの設定値を使用します。")
        return default_settings


def save_settings(settings_file, settings):
    try:
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"設定ファイルの保存中にエラーが発生しました: {e}")


def detect_encoding(filepath):
    """
    ファイルのエンコーディングを自動検出
    """
    with open(filepath, "rb") as f:
        raw_data = f.read(1024)  # 先頭 1024 バイトを検出に使用
    result = chardet.detect(raw_data)
    return (
        result["encoding"] if result["confidence"] > 0.8 else "utf-8"
    )  # 信頼度が低い場合は utf-8 にフォールバック


def initialize_app(app, settings, use_previous_context=False):
    filepath = settings["filepath"]
    model_name = settings["model_name"]
    system_prompt = settings["system_prompt"]
    min_interval = settings["min_interval"]
    max_interval = settings["max_interval"]
    context_str = settings["context_str"]

    if not os.path.exists(filepath):
        raise FileNotFoundError(f"指定されたファイルが存在しません: {filepath}")

    try:
        encoding = detect_encoding(filepath)
        with open(filepath, "r", encoding=encoding) as f:
            f.read()
    except Exception as e:
        raise IOError(f"ファイルを開くことができません: {e}")

    if context_str:
        context = ast.literal_eval(context_str)

    logger = get_logger()

    if not context_str:
        print("システムプロンプトを送信します...")
        response, context = get_comment_from_llm(system_prompt, model_name=model_name)
        if context:
            print(f"APIとの通信に成功しました。LLMからのレスポンス: {response}")
            logger.set_model_info(model_name, system_prompt, context)
            processed_response = logger.add_log(system_prompt, response)
            app.message_queue.put(processed_response)
        else:
            raise ConnectionError(
                "レスポンスの取得に失敗しました。APIとの通信に問題がある可能性があります。"
            )
    else:
        print("前回の設定を使用します。")
        logger.set_model_info(model_name, system_prompt, context)
        restart_prompt = "ただいま戻りました。お出迎えの挨拶をお願いします。"
        response, new_context = get_comment_from_llm(
            restart_prompt, context, model_name
        )
        processed_response = logger.add_log(restart_prompt, response)
        app.message_queue.put(response)

    if hasattr(app, "random_trigger") and app.random_trigger:
        app.random_trigger.stop()

    trigger_manager = TriggerManager(
        filepath, encoding, app.message_queue, context, model_name
    )
    trigger_manager.logger.set_model_info(model_name, system_prompt, context)
    app.trigger_manager = trigger_manager

    random_trigger = RandomTrigger(
        min_interval=min_interval,
        max_interval=max_interval,
        trigger_function=trigger_manager.on_random_message,
    )
    app.random_trigger = random_trigger

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=False, port=5000)
