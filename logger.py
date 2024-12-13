# logger.py

import re
import threading
import os
from datetime import datetime


class Logger:
    def __init__(self):
        self.log = []
        self.lock = threading.Lock()
        self.logs_directory = "logs"
        # ログフォルダが存在しない場合は作成
        if not os.path.exists(self.logs_directory):
            os.makedirs(self.logs_directory)

    def set_model_info(self, model_name, system_prompt, context):
        with self.lock:
            self.model_name = model_name
            self.system_prompt = system_prompt
            self.context = context

    def process_response(self, response):
        # レスポンスの加工処理
        response = re.sub(r"<\|.*?\|>", "", response)
        response = re.sub(r"<\|.*?\|", "", response)
        response = re.sub(r"\|.*?\|>", "", response)
        response = response.replace("|im-start|", "")
        response = response.replace("|im-end|", "")
        if (
            response.startswith("「")
            and response.endswith("」")
            and response.count("「") == 1
            and response.count("」") == 1
        ):
            response = response[1:-1]

        response = response.strip()  # 両端の空白を除去

        # 末尾が「。」「？」「?」「！」「!」以外なら「。」を追加
        if not response.endswith(("。", "？", "?", "！", "!")):
            response += "。"
        return response

    def shorten_prompt(self, prompt, max_length=100):
        # プロンプトの短縮処理
        pattern = r"〔(.*?)〕"
        matches = re.findall(pattern, prompt, re.DOTALL)
        shortened_prompt = prompt
        for match in matches:
            # 改行を除去
            cleaned_match = self.format_scenario(match)  # match.replace("\n\n", "\n")
            if len(cleaned_match) > max_length:
                # 前後を含めて短縮
                trimmed_prompt = (
                    cleaned_match[:max_length] + "..." + cleaned_match[-max_length:]
                )
                shortened_prompt = shortened_prompt.replace(match, trimmed_prompt)
        return shortened_prompt

    # ※自分用 正規表現を使って形式を変換
    def format_scenario(self, text):
        # キャラクター名とセリフの部分を1行にまとめる
        def replace_match(match):
            name = match.group(1)  # 名前部分
            dialogue = (
                match.group(2).replace("\n", "").strip()
            )  # セリフ部分を1行にまとめる
            return f"{name}：{dialogue}\n"

        # 正規表現でキャラクター名とセリフ部分を取得・変換
        text = re.sub(r"# (\S+)\n((?:[^#>\n].*\n?)+)", replace_match, text)

        # 空行を削除
        text = re.sub(r"\n+", "\n", text).strip()

        return text

    def add_log(self, prompt, response):
        with self.lock:
            processed_response = self.process_response(response)
            shortened_prompt = self.shorten_prompt(prompt)
            self.log.append(
                {"prompt": shortened_prompt, "response": processed_response}
            )
            return processed_response  # 必要に応じて加工済みのレスポンスを返す

    def save_log(self, log_type="auto"):
        with self.lock:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"chat_log_{log_type}_{timestamp}.txt"
            filepath = os.path.join(self.logs_directory, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("=== メタ情報 ===\n")
                f.write(f"モデル名: {self.model_name or '不明'}\n")
                f.write(f"システムプロンプト: {self.system_prompt or '不明'}\n")
                f.write(f"コンテキスト: {self.context or 'なし'}\n")
                f.write("=== ログ ===\n")
                for entry in self.log:
                    f.write("Prompt:\n")
                    f.write(entry["prompt"] + "\n")
                    f.write("Response:\n")
                    f.write(entry["response"] + "\n")
                    f.write("-" * 40 + "\n")
            print(f"ログを保存しました: {filepath}")
            return filepath


_logger_instance = None
_logger_lock = threading.Lock()


def get_logger():
    global _logger_instance
    with _logger_lock:
        if _logger_instance is None:
            _logger_instance = Logger()
    return _logger_instance
