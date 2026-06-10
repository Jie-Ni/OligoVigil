FROM python:3.11-slim

WORKDIR /app
COPY . /app

EXPOSE 8077
CMD ["sh", "-c", "test -f data/oligosafety.db || python scripts/init_db.py; python app/server.py --host 0.0.0.0 --port 8077"]
