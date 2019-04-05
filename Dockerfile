FROM python:3.6
ENV PYTHONUNBUFFERED 1
ARG ENV_CG
ARG JOB
ARG BIT_ENV_URL
ARG COLLECTSTATIC
#ARG MIGRATE
RUN apt-get update && apt-get install binutils libproj-dev gdal-bin nano apt-utils -y
RUN apt-get update


RUN apt-get -y install libxss1 libappindicator1 libindicator7
RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
#RUN dpkg -i google-chrome*.deb
#RUN apt-get -y install -f
RUN apt-get -y install xvfb unzip
RUN wget -N http://chromedriver.storage.googleapis.com/2.26/chromedriver_linux64.zip
RUN unzip chromedriver_linux64.zip
RUN chmod +x chromedriver
RUN mv -f chromedriver /usr/local/share/chromedriver
RUN ln -s /usr/local/share/chromedriver /usr/local/bin/chromedriver
RUN ln -s /usr/local/share/chromedriver /usr/bin/chromedriver


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
