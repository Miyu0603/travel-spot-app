# Travel Spot App

從社群媒體（IG / FB / Threads）貼文自動萃取旅遊景點資訊的工具。

## 架構

```
travel-spot-app/
├── backend/          # FastAPI 後端
│   ├── app/
│   │   ├── main.py           # FastAPI 入口
│   │   ├── config.py         # 環境變數設定
│   │   ├── database.py       # SQLAlchemy 資料庫連線
│   │   ├── models/           # ORM 模型（Spot, Source, Tag）
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   ├── services/         # 核心服務
│   │   │   ├── scraper.py        # Apify 爬蟲（IG/FB）
│   │   │   ├── ai_extractor.py   # GPT 景點萃取
│   │   │   ├── geo_service.py    # Google Places 地理補齊
│   │   │   └── whisper_service.py # 影片轉逐字稿
│   │   └── routers/          # API 路由
│   │       ├── spots.py          # 景點 CRUD
│   │       └── sources.py        # 來源匯入 pipeline
│   ├── requirements.txt
│   └── .env.example
└── frontend/         # Next.js 前端
    └── src/
        ├── app/page.tsx          # 主頁面
        ├── components/           # UI 元件
        └── lib/api.ts            # API client
```

## 快速開始

### 後端

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 填入你的 API keys
uvicorn app.main:app --reload
```

API 文件：http://localhost:8000/docs

### 前端

```bash
cd frontend
npm install
npm run dev
```

開啟：http://localhost:3000

## 環境變數

| 變數 | 說明 | 必要 |
|------|------|------|
| `APIFY_API_TOKEN` | Apify API token（爬 IG/FB） | 使用 URL 抓取時 |
| `OPENAI_API_KEY` | OpenAI API key（GPT + Whisper） | AI 萃取時 |
| `GOOGLE_MAPS_API_KEY` | Google Maps API key | 地理補齊時 |

## 主要流程

1. 使用者貼上社群網址 → Apify 抓取貼文內容
2. 若有影片 → Whisper 轉逐字稿
3. 文字內容 → GPT 萃取結構化景點資料
4. Google Places API 補齊地址 / 座標 / 地圖連結
5. 儲存至資料庫並顯示
