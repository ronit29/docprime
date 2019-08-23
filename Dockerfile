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
