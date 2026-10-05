# WiseBasket inference service: PaddleOCR on CPU.
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
# Railway builds with the repo ROOT as context (same convention as services/api/Dockerfile).
COPY services/inference/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY services/inference/app ./app
COPY packages/receipt_purchase_rules.py ./packages/receipt_purchase_rules.py
COPY services/inference/scripts/start.sh ./start.sh

EXPOSE 8000
CMD ["bash", "start.sh"]
