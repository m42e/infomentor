FROM python:3.7.3-stretch

COPY requirements.txt /tmp/
COPY entrypoint.sh /

RUN pip install -r /tmp/requirements.txt
COPY . /tmp/infomentor
RUN pip install /tmp/infomentor

RUN useradd --create-home appuser
WORKDIR /home/appuser
USER appuser
VOLUME ["/home/appuser"]
ENTRYPOINT ["/entrypoint.sh"]
