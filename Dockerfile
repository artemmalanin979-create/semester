FROM docker.io/library/python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    SEMESTER_ENV=production SEMESTER_DB=/data/semester.sqlite3
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --system --uid 10001 semester \
    && mkdir /data && chown semester /data
COPY semester ./semester
USER semester
EXPOSE 8000
CMD ["gunicorn", "--preload", "--bind=0.0.0.0:8000", "--workers=2", "--threads=2", "semester:create_app()"]
