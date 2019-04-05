FROM python:3.6
ENV PYTHONUNBUFFERED 1
ARG ENV_CG
ARG JOB
ARG BIT_ENV_URL
ARG COLLECTSTATIC
#ARG MIGRATE
RUN apt-get update && apt-get install binutils libproj-dev gdal-bin nano apt-utils -y
RUN apt-get update
RUN apt-get install -y xvfb fluxbox x11vnc dbus libasound2 libqt4-dbus libqt4-network libqtcore4 libqtgui4 libxss1 libpython2.7 libqt4-xml libaudio2 libmng1 fontconfig liblcms1 lib32stdc++6 lib32asound2 ia32-libs libc6-i386 lib32gcc1 nano
RUN apt-get install -y python-gobject-2
RUN apt-get install -y curl git

RUN mkdir -p /home/docprime/workspace/backend
RUN mkdir /env
RUN mkdir -p /home/docprime/workspace/entrypoint
# RUN git clone -b jwt_auth --single-branch https://ronit29pb:KFSfpRpjJwBCbGLdZufx@bitbucket.org/arunpb/ondocbackend.git /code
COPY / home/docprime/workspace/backend/


#GET ENVIRONEMENT AND CONFIGURATIONS
RUN git clone $BIT_ENV_URL /env
RUN cp /env/$JOB/django/gunicorn_config.py /home/docprime/workspace/backend/
RUN cp /env/$JOB/django/django_env /home/docprime/workspace/backend/.env
RUN cp /env/$JOB/django/entrypoint /home/docprime/workspace/entrypoint
RUN chmod +x /home/docprime/workspace/entrypoint/entrypoint


#NGINX CONFIGURATION
#WORKDIR /etc/nginx
#RUN mkdir -p sites-enabled
#RUN mv /env/$JOB/django/nginx.conf /etc/nginx/
#RUN ["ln", "-s", "/etc/nginx/nginx.conf", "/etc/nginx/sites-enabled/"]


#DJANGO MANAGEMENT COMMANDS
WORKDIR /home/docprime/workspace/backend
RUN pip install -r requirements/local.txt
ENV DJANGO_SETTINGS_MODULE=config.settings.$ENV_CG
RUN if [ "$COLLECTSTATIC" = "true" ] ; then\
 python manage.py collectstatic --no-input ; \
fi

EXPOSE 8080
#CMD ["sh", "/home/docprime/workspace/entrypoint/entrypoint"]
