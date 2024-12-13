# api_client.py

import requests
import json


def get_comment_from_llm(
    prompt,
    context=None,
    model_name="hf.co/QuantFactory/Llama-3-ELYZA-JP-8B-GGUF:Q4_K_M",
    api_url="http://localhost:11434/api/generate",
):
    try:
        payload = {"model": model_name, "prompt": prompt, "stream": False}
        if context is not None:
            payload["context"] = context

        headers = {"Content-Type": "application/json"}
        response = requests.post(api_url, json=payload, headers=headers)

        if response.status_code != 200:
            print(
                f"APIリクエストが失敗しました。ステータスコード: {response.status_code}"
            )
            return "コメントの取得に失敗しました。", None

        # レスポンスをJSONとして解析
        data = response.json()
        comment = data.get("response", "").strip()
        new_context = data.get("context")

        return comment, new_context
    except Exception as e:
        print(f"LLMへの問い合わせ中にエラーが発生しました: {e}")
        return "コメントの取得に失敗しました。", None


# テスト用コード
if __name__ == "__main__":
    test_prompt = "あなたは優しく励ますアシスタントです。"
    # 初期のcontextはなし
    response, context = get_comment_from_llm(test_prompt)
    print(f"LLMからのテストレスポンス: {response}")
    print(f"受け取ったcontext: {context}")
