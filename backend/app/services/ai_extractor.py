"""
AI Extractor: Uses LLM (OpenAI GPT) to parse unstructured social media text
into structured travel spot data.
"""

import json

import httpx

from app.config import settings

SYSTEM_PROMPT = """你是一個旅遊資訊萃取助手。使用者會提供來自社群媒體的貼文內容（可能是文字或影片逐字稿）。
你的任務是從中萃取所有提到的旅遊景點，並以 JSON 格式回傳。

重要提示：
- 一篇貼文可能包含多個景點，請全部萃取。
- 景點資訊不一定出現在貼文說明中，有時只在影片逐字稿中提到。
- 若貼文或逐字稿只提到景點名稱但缺乏地址等詳細資訊，請根據你的知識補充該景點的地址、營業時間等資訊。

每個景點請提供以下資訊（若貼文中未提及且無法推斷則留空字串）：
- title: 景點名稱
- description: 景點簡述
- address: 地址（盡量完整）
- business_hours: 營業時間
- notes: 注意事項（如預約制、休息日、費用等）
- region: 地區分類，值為 "taiwan" / "japan" / "international"
- continent: 若 region 為 "international"，填寫洲別: "asia" / "europe" / "north_america" / "south_america" / "oceania" / "africa"
- country: 國家名稱
- city: 一級行政區名稱（不含後綴）。日本填都道府縣名（例如「福岡」「大分」「東京」「北海道」「大阪」「京都」）；台灣填縣市名（例如地址含「桃園市」填「桃園」、「新北市」填「新北」、「台北市」填「台北」、「花蓮縣」填「花蓮」，注意「平鎮區」屬於「桃園」、「板橋區」屬於「新北」）；其他國家填主要城市或州省名（例如「紐約」「巴黎」「首爾」）。請從地址推斷。

請以 JSON array 格式回傳，即使只有一個景點也用 array。
只回傳 JSON，不要加任何說明文字。"""


async def extract_spots_from_text(text: str) -> list[dict]:
    """Use OpenAI API to extract spot info from text."""
    if not settings.openai_api_key:
        return []

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
            },
        )

        if response.status_code != 200:
            return []

        data = response.json()
        content = data["choices"][0]["message"]["content"]

        try:
            parsed = json.loads(content)
            # Handle various response formats from the LLM
            if isinstance(parsed, list):
                return parsed
            elif isinstance(parsed, dict):
                # Find the first list value in the dict (e.g. "spots", "attractions", etc.)
                for value in parsed.values():
                    if isinstance(value, list):
                        return value
                # If no list found, treat the dict itself as a single spot
                if "title" in parsed:
                    return [parsed]
            return []
        except json.JSONDecodeError:
            return []
