FROM ubuntu:22.04

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3-dev python3-pip python3-setuptools ca-certificates uwsgi python3-gevent uwsgi-plugin-gevent-python3 uwsgi-plugin-python3 texlive-latex-base dvipng git locales python-is-python3 \
    && rm -rf /var/lib/apt/lists/*

RUN sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && locale-gen

ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8


RUN pip install -U poetry 

WORKDIR /app

COPY . /app/

RUN poetry config virtualenvs.create false && poetry lock && poetry install -n 


WORKDIR /data


CMD ["/usr/bin/uwsgi", "--ini", "/data/uwsgi.ini"]

