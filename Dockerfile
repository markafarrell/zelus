FROM python:3.11-alpine3.18

RUN  apk add iproute2

COPY . /tmp/zelus

RUN cd /tmp/zelus && \
    pip3 install .

RUN mkdir -p /etc/zelus/ && \
    cp /tmp/zelus/example/zelus.yml /etc/zelus/zelus.yml

RUN rm -rf /tmp/zelus

ENV ZELUS_LOGLEVEL=0

ENTRYPOINT ["/usr/local/bin/zelus", "-c", "/etc/zelus/zelus.yml"]
