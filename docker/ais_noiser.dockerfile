FROM python:3.11-slim

WORKDIR /app

COPY docker/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY ./AIS-Noiser .

CMD ["sleep", "infinity"]