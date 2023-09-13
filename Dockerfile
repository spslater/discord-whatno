FROM python:3.11.4-slim-bookworm

RUN apt update -y
RUN apt install -y git

WORKDIR /app
ENV PYTHONPATH /app

RUN mkdir extension
RUN mkdir logs

ADD whatno whatno
ADD requirements.txt .
ADD logging.conf .

RUN python -m ensurepip --upgrade
RUN python -m pip install --upgrade pip

RUN python -m pip install -r requirements.txt

CMD ["python", "-m", "whatno"]
