FROM nginx:1.25.3-alpine
MAINTAINER Davy Jones <dj@nextolab.com>


RUN apk update && apk add openssh python3 py3-pip \
    && rm  -rf /tmp/* /var/cache/apk/*

RUN ssh-keygen -A && passwd -d root \
    && mkdir /root/.ssh && touch /root/.ssh/authorized_keys && chmod 600 /root/.ssh/authorized_keys \
    && sed -i s/#PasswordAuthentication\ yes/PasswordAuthentication\ no/ /etc/ssh/sshd_config \
    && sed -i s/#PubkeyAuthentication\ yes/PubkeyAuthentication\ yes/ /etc/ssh/sshd_config \
    && sed -i s/AllowTcpForwarding\ no/AllowTcpForwarding\ yes/ /etc/ssh/sshd_config

RUN pip install docker
RUN mkdir /app


COPY docker/nginx/nginx.conf /etc/nginx
COPY docker/nginx/index.html /usr/share/nginx/html
COPY daemon.py /app


CMD ["sh", "-c", "nginx -g 'daemon off;' & /usr/sbin/sshd -e & python /app/daemon.py"]
EXPOSE 22
