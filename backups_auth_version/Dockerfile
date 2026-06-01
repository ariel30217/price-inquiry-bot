# 使用 Playwright 官方 Python 映像檔 (已預裝 Chrome 系統依賴)
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# 設定工作目錄
WORKDIR /app

# 設定環境變數，確保 Python 輸出直接顯示在日誌中
ENV PYTHONUNBUFFERED=1
# 告訴 Playwright 瀏覽器的存放位置 (加速啟動)
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# 複製依賴清單並安裝
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 安裝 Chromium 瀏覽器
RUN playwright install chromium

# 複製其餘專案檔案
COPY . .

# 如果你有 auth.json 或是 price_cache.json，確保它們有寫入權限 (選用)
RUN touch price_cache.json && chmod 666 price_cache.json

# 啟動機器人 (對應你的 telegram_bot.py)
CMD ["python", "telegram_bot.py"]
