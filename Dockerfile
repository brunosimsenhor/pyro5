FROM python:3.9-slim

WORKDIR /app

# RUN apt update && \
#         apt install -y sqlite3 && \
#         rm -rf /var/cache/apt/archives

COPY requirements.txt .

RUN pip install -r requirements.txt && pip install pymongo

COPY . .
