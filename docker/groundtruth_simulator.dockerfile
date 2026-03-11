FROM python:3.11-slim

WORKDIR /app

COPY docker/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir "xarray[complete]"

COPY ./Groundtruth-Simulator .

CMD ["sleep", "infinity"]