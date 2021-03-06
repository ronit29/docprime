FROM python:3.6

ENV PYTHONUNBUFFERED 1
ARG ENV_CG
ARG JOB
ARG BIT_ENV_URL
ARG COLLECTSTATIC
ARG SMS_AUTH_KEY
ARG EMAIL_HOST_PASSWORD
ARG AWS_ACCESS_KEY_ID
ARG AWS_SECRET_ACCESS_KEY
ARG DATABASE
ARG DBUSER
ARG DBPASS

ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update && apt-get install binutils libproj-dev gdal-bin nano apt-utils -y
RUN apt-get update

# install chrome libraries
#RUN apt-get install -y gconf-service libasound2 libatk1.0-0 libcairo2 libcups2 libfontconfig1 libgdk-pixbuf2.0-0 libgtk-3-0 libnspr4 libpango-1.0-0 libxss1 fonts-liberation
#RUN apt-get install -y libappindicator1 libnss3 lsb-release xdg-utils libappindicator3-1 libindicator3-7
# install chrome
#RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
#RUN dpkg -i google-chrome-stable_current_amd64.deb; apt-get -fy install
#RUN ln -s /usr/bin/google-chrome-stable /usr/bin/chrome
#install Microsoft ODBC Driver for debian 9
#RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
#RUN curl https://packages.microsoft.com/config/debian/9/prod.list > /etc/apt/sources.list.d/mssql-release.list
#RUN unlink /usr/lib/apt/methods/https
#RUN ln -s  /usr/lib/apt/methods/http /usr/lib/apt/methods/https
#RUN apt-get update && ACCEPT_EULA=Y apt-get install msodbcsql17 -y
#RUN echo 'export PATH="$PATH:/opt/mssql-tools/bin"' >> ~/.bash_profile
#RUN echo 'export PATH="$PATH:/opt/mssql-tools/bin"' >> ~/.bashrc
#RUN . ~/.bashrc
#RUN apt-get install unixodbc-dev



RUN mkdir -p /home/docprime/workspace/backend
RUN mkdir /env
RUN mkdir -p /home/docprime/workspace/entrypoint
COPY / home/docprime/workspace/backend/


#GET ENVIRONEMENT AND CONFIGURATIONS
RUN git clone $BIT_ENV_URL /env
RUN cp /env/$JOB/django/gunicorn_config.py /home/docprime/workspace/backend/
RUN cp /env/$JOB/django/entrypoint /home/docprime/workspace/entrypoint
RUN cp /env/$JOB/django/celery_entrypoint /home/docprime/workspace/entrypoint
RUN chmod +x /home/docprime/workspace/entrypoint/entrypoint
RUN chmod +x /home/docprime/workspace/entrypoint/celery_entrypoint


#NGINX CONFIGURATION
#WORKDIR /etc/nginx
#RUN mkdir -p sites-enabled
#RUN mv /env/$JOB/django/nginx.conf /etc/nginx/
#RUN ["ln", "-s", "/etc/nginx/nginx.conf", "/etc/nginx/sites-enabled/"]

#DJANGO MANAGEMENT COMMANDS
WORKDIR /home/docprime/workspace/backend
RUN if [ "$ENV_CG" = "staging" ] ; then\
    sed  -e "s/\${ENV_CG}/$ENV_CG/" -e "s/\${SMS_AUTH_KEY}/$SMS_AUTH_KEY/" -e "s/\${EMAIL_HOST_PASSWORD}/$EMAIL_HOST_PASSWORD/" -e "s/\${AWS_ACCESS_KEY_ID}/$AWS_ACCESS_KEY_ID/" -e "s~\${AWS_SECRET_ACCESS_KEY}~$AWS_SECRET_ACCESS_KEY~" -e "s/\${DBUSER}/$DBUSER/" -e "s/\${DBPASS}/$DBPASS/" -e "s/\${DATABASE}/$DATABASE/" -e "s/\${QA_SERVER}/$JOB/" env.example > .env ; \
fi
RUN if [ "$ENV_CG" = "production" ] ; then\
    cp /env/$JOB/django/django_env /home/docprime/workspace/backend/.env ; \
fi
RUN pip install -r requirements/$ENV_CG.txt
ENV DJANGO_SETTINGS_MODULE=config.settings.$ENV_CG
RUN if [ "$COLLECTSTATIC" = "true" ] ; then\
 python manage.py collectstatic --no-input ; \
fi

EXPOSE 8080
#CMD ["sh", "/home/docprime/workspace/entrypoint/entrypoint"]
