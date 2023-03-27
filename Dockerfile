FROM ubuntu:22.04

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3-dev python3-pip python3-setuptools ca-certificates uwsgi python3-gevent uwsgi-plugin-gevent-python3 uwsgi-plugin-python3 texlive-latex-base dvipng \
    && rm -rf /var/lib/apt/lists/*

RUN pip install -U poetry 

WORKDIR /app

COPY . /app/

RUN poetry config virtualenvs.create false && poetry lock && poetry install -n 


WORKDIR /data


CMD ["/usr/bin/uwsgi", "--ini", "/data/uwsgi.ini"]

