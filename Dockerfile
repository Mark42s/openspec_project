FROM python:3.11-slim

WORKDIR /app

# 先装依赖层(利用构建缓存)
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

ENV PLANNER_DB_PATH=/data/travel.db
ENV PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
