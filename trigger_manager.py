# trigger_manager.py

import threading
import time
import random
import re
from datetime import datetime
from api_client import get_comment_from_llm
from logger import get_logger


class TriggerManager:
    def __init__(self, filepath, encoding, message_queue, initial_context, model_name):
        self.filepath = filepath
        self.encoding = encoding
        self.message_queue = message_queue
        self.context = initial_context  # 最初のコンテキストを使用し、以降は上書きしない
        self.model_name = model_name
        self.lock = threading.Lock()
        self.api_lock = threading.Lock()
        self.api_in_progress = False  # APIリクエストが進行中かどうかを示すフラグ
        self.last_api_response_time = 0  # 最後のAPIレスポンスの時間
        self.start_time = time.time()  # アプリの開始時間を記録
        self.logger = get_logger()  # 共通の Logger インスタンスを取得

    def read_file(self):
        try:
            with open(self.filepath, "r", encoding=self.encoding) as file:
                text = file.read()
            return text
        except Exception as e:
            print(f"テキストの読み込み中にエラーが発生しました: {e}")
            return ""

    def on_pause(self):
        self.pause_time = time.time()

        print("TriggerManager: 休憩メッセージを送信します。")
        prompt = "休憩のため席を外します。"
        self.send_to_llm(prompt)

    def on_resume(self):
        paused_duration = time.time() - self.pause_time
        self.start_time += paused_duration

        print("TriggerManager: 再開メッセージを送信します。")
        prompt = "用事が終わりました。今から執筆を再開します。"
        self.send_to_llm(prompt)

    def on_random_message(self):
        print("TriggerManager: on_random_message が発火しました。")

        current_time = datetime.now()
        time_str = current_time.strftime("%H時%M分")
        uptime_minutes = int((time.time() - self.start_time) // 60)

        prompts_with_weights = [
            (
                2,
                "現在時刻について",
                "現在は{time_str}です。時間帯について独り言のような一言をお願いします。",
                False,
            ),
            (
                1,
                "時間の経過について",
                "執筆を開始してから{uptime_minutes}分経過しました。あなたは時間の経過について呟きます。",
                False,
            ),
            (
                3,
                "気になった点について",
                "以下は私の書いた文章です。\n〔{combined_text}〕\nあなたはこの文章を読んで気になった点を一つ呟きます",
                True,
            ),
            (
                3,
                "最初に思いついたこと",
                "以下は私の書いた文章です。\n〔{combined_text}〕\nあなたはこの文章を読んで最初に思いついたことを一つ呟きます。",
                True,
            ),
        ]

        total_weight = sum(w for w, _, _, _ in prompts_with_weights)
        rand_value = random.uniform(0, total_weight)
        cumulative_weight = 0
        selected = None

        for weight, label, template, needs_text in prompts_with_weights:
            cumulative_weight += weight
            if rand_value <= cumulative_weight:
                selected = (label, template, needs_text)
                break

        if not selected:
            print("プロンプトの選択に失敗しました。")
            return

        label, template, needs_text = selected

        # テキストが必要な場合のみファイル読み込みや要約抽出を行う
        if needs_text:
            text = self.read_file()
            summary = self.extract_summary(text)
            body = self.remove_summary_blocks(text)
            body = self.logger.format_scenario(body)
            last_body = body[-3000:]
            if summary:
                combined_text = f"要約:\n{summary}\n\n本文:\n{last_body}"
            else:
                combined_text = last_body
        else:
            # テキストが不要なシナリオはcombined_textなしで生成可能。
            combined_text = ""

        # プロンプト生成
        final_prompt = template.format(
            time_str=time_str,
            uptime_minutes=uptime_minutes,
            combined_text=combined_text,
        )

        self.send_to_llm(final_prompt, label)

    def remove_summary_blocks(self, text):
        pattern = r"<!--\s*SUMMARY_START\s*-->(.*?)<!--\s*SUMMARY_END\s*-->"
        return re.sub(pattern, "", text, flags=re.DOTALL)

    def extract_summary(self, text):
        # コメントブロックで囲まれた要約部分を抽出。
        pattern = r"<!--\s*SUMMARY_START\s*-->(.*?)<!--\s*SUMMARY_END\s*-->"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
        else:
            return None

    def send_to_llm(self, prompt, label):
        with self.lock:
            if self.api_in_progress:
                print("APIリクエストが進行中のため、新しいリクエストをスキップします。")
                return
            self.api_in_progress = True

        print(f"LLMに送信するプロンプト:{label}...")

        def task():
            try:
                # LLMにプロンプトを送信
                response, _ = get_comment_from_llm(
                    prompt, context=self.context, model_name=self.model_name
                )
                print(f"LLMからのレスポンス: {response}")
                # ログに追加し、レスポンスを加工
                processed_response = self.logger.add_log(
                    f"ラベル:{label}\n{prompt}", response
                )
                self.message_queue.put(processed_response)
                print(f"LLMからのレスポンス: {processed_response}")
            finally:
                with self.lock:
                    self.last_api_response_time = time.time()
                    self.api_in_progress = False

        threading.Thread(target=task).start()

    def save_log(self, log_type="auto"):
        self.logger.save_log(log_type)
