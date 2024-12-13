# random_trigger.py

import threading
import random


class RandomTrigger:
    def __init__(self, min_interval, max_interval, trigger_function):
        self.min_interval = min_interval
        self.max_interval = max_interval
        self.trigger_function = trigger_function
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.thread = threading.Thread(target=self.run)
        self.thread.start()
        print("ランダムトリガーを開始しました。")

    def run(self):
        while not self.stop_event.is_set():
            interval = random.uniform(self.min_interval, self.max_interval)
            print(f"次のランダムトリガーまで {interval:.2f} 秒")
            if self.stop_event.wait(interval):
                break
            # 一時停止中は待機
            while self.pause_event.is_set():
                if self.stop_event.wait(1):
                    return
            self.trigger_function()

    def pause(self):
        self.pause_event.set()
        print("ランダムトリガーを一時停止しました。")

    def resume(self):
        if self.pause_event.is_set():
            self.pause_event.clear()
            print("ランダムトリガーを再開しました。")
            # 再開時にすぐにトリガーを発火させる
            self.trigger_function()

    def stop(self):
        self.stop_event.set()
        self.thread.join()
        print("ランダムトリガーを停止しました。")
