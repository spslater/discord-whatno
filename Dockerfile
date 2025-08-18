FROM python:3.12.8-slim-bookworm

RUN apt update -y
RUN apt install -y ffmpeg

WORKDIR /app
ENV PYTHONPATH=/app

RUN mkdir logs
RUN mkdir storage

ADD whatno whatno
ADD requirements.txt .
ADD logging.conf .
# ADD external.txt .

RUN python -m ensurepip --upgrade
RUN python -m pip install --upgrade pip

RUN python -m pip install -r requirements.txt

CMD ["python", "-m", "whatno"]
