import subprocess
import requests
import json
import time
import logging
import os

logger = logging.getLogger(__name__)

AGY_PATH = "/Users/my/.local/bin/agy"

# 1. ⚡ Antigravity 官方模型庫
AGY_MODELS = [
    {"id": "Gemini 3.8 Flash (Low)", "name": "Gemini 3.8 Flash (Low)", "desc": "低思考預算，極速回覆 (推薦)", "backend": "agy"},
    {"id": "Gemini 3.8 Flash (Medium)", "name": "Gemini 3.8 Flash (Med)", "desc": "平衡思考預算", "backend": "agy"},
    {"id": "Gemini 3.8 Flash (High)", "name": "Gemini 3.8 Flash (High)", "desc": "高思考預算，深度推理", "backend": "agy"},
    {"id": "Gemini 3.7 Flash (High)", "name": "Gemini 3.7 Flash (High)", "desc": "3.7 Flash 深度推理", "backend": "agy"},
    {"id": "Gemini 3.1 Pro (High)", "name": "Gemini 3.1 Pro (High)", "desc": "長文本架構分析", "backend": "agy"},
    {"id": "Claude Sonnet 4.6 (Thinking)", "name": "Claude Sonnet 4.6 (Thinking)", "desc": "深度思維與投行金融分析", "backend": "agy"},
    {"id": "Claude Opus 4.6 (Thinking)", "name": "Claude Opus 4.6 (Thinking)", "desc": "最強頂級推理與極限建模", "backend": "agy"},
    {"id": "GPT-OSS 120B (Medium)", "name": "GPT-OSS 120B (Med)", "desc": "開源百億參數模型", "backend": "agy"}
]

# 2. 💻 SenseNova / 備援 API 模型庫
API_MODELS = [
    {"id": "sensenova/sensenova-6.8-flash-lite", "name": "SenseNova 6.8 Flash Lite", "desc": "毫秒響應、高並發防限流", "backend": "api"},
    {"id": "sensenova/glm-5.2", "name": "GLM 5.2 金融智商", "desc": "中文語境分析與邏輯嚴謹", "backend": "api"},
    {"id": "sensenova/deepseek-v4-flash", "name": "DeepSeek V4 Flash", "desc": "深度推演與複雜模型構建", "backend": "api"},
    {"id": "sensenova/sensenova-6.7-flash-lite", "name": "SenseNova 6.7 穩定版", "desc": "官方備份線路", "backend": "api"}
]

ALL_MODELS = AGY_MODELS + API_MODELS

class LLMClient:
    def __init__(self, base_url: str, api_key: str, default_model: str = "Gemini 3.8 Flash (Low)"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.current_model = default_model

    def set_model(self, model_id: str):
        self.current_model = model_id

    def get_current_model(self) -> str:
        return self.current_model

    def get_model_info(self, model_id: str = None) -> dict:
        mid = model_id or self.current_model
        for m in ALL_MODELS:
            if m["id"] == mid:
                return m
        return {"id": mid, "name": mid, "desc": "", "backend": "agy"}

    def _call_agy(self, model: str, prompt: str, timeout: int = 90) -> str:
        """透過本地 agy CLI 驅動 Antigravity 官方模型"""
        if not os.path.exists(AGY_PATH):
            raise RuntimeError(f"找不到 agy 執行檔: {AGY_PATH}")

        cmd = [
            AGY_PATH,
            f"--model={model}",
            "--dangerously-skip-permissions",
            f"--print={prompt}"
        ]
        
        logger.info(f"正在調用 Antigravity 模型 [{model}]...")
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout
        )
        if result.returncode == 0:
            out = result.stdout.strip()
            if out:
                return out
        err = result.stderr.strip()
        raise RuntimeError(f"agy 回傳失敗 (code {result.returncode}): {err[:150]}")

    def _call_api(self, model_id: str, system_prompt: str, user_prompt: str) -> str:
        """調用 SenseNova API"""
        clean_model = model_id.replace("sensenova/", "")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": clean_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 2800
        }
        url = f"{self.base_url}/chat/completions"
        logger.info(f"正在調用 API 模型 [{clean_model}]...")
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        if resp.status_code == 200:
            data = resp.json()
            msg = data["choices"][0]["message"]
            content = msg.get("content") or msg.get("reasoning_content") or msg.get("reasoning") or ""
            if content.strip():
                return content.strip()
        raise RuntimeError(f"API Error {resp.status_code}: {resp.text[:100]}")

    def chat_complete(self, system_prompt: str, user_prompt: str) -> str:
        info = self.get_model_info(self.current_model)
        chinese_rule = "【語言最高規範：思考與所有輸出必須 100% 全程使用繁體中文！嚴格禁止輸出任何非必要英文句子或段落！】"
        full_prompt = f"[{chinese_rule}]\n[系統指示: {system_prompt}]\n\n[用戶提問與任務要求]:\n{user_prompt}\n\n[請務必全程以繁體中文交付完整專業金融分析報告]"

        # 1. 如果選擇的是 Antigravity 模型
        if info.get("backend") == "agy":
            try:
                return self._call_agy(self.current_model, full_prompt)
            except Exception as e:
                logger.warning(f"Antigravity 模型 [{self.current_model}] 失敗: {e}，切換備用 API 模型...")
                # 自動 Fallback 到 SenseNova 高速模型
                try:
                    return self._call_api("sensenova-6.8-flash-lite", system_prompt, user_prompt)
                except Exception as ex:
                    return f"⚠️ 分析推論失敗: {str(e)} | 備援失敗: {str(ex)}"

        # 2. 如果選擇的是 API 模型
        else:
            try:
                return self._call_api(self.current_model, system_prompt, user_prompt)
            except Exception as e:
                logger.warning(f"API 模型 [{self.current_model}] 失敗: {e}，嘗試切換備援...")
                for fallback in ["sensenova-6.8-flash-lite", "glm-5.2"]:
                    try:
                        return self._call_api(fallback, system_prompt, user_prompt)
                    except Exception:
                        continue
                return f"⚠️ 模型調用遇到限制或超時: {str(e)}"
