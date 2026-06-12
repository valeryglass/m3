FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir .

COPY app ./app
COPY config ./config
COPY model ./model
COPY roles ./roles

CMD ["python", "-m", "app.telegram_bot"]
