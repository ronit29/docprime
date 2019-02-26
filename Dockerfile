FROM python:3.6
ENV PYTHONUNBUFFERED 1

RUN apt-get update && apt-get install binutils libproj-dev gdal-bin nano apt-utils -y
RUN apt-get update && apt-get install nginx -y 
RUN mkdir -p /home/docprime/workspace/backend
RUN mkdir /env
RUN mkdir -p /home/docprime/workspace/entrypoint
# RUN git clone -b jwt_auth --single-branch https://ronit29pb:KFSfpRpjJwBCbGLdZufx@bitbucket.org/arunpb/ondocbackend.git /code
COPY / home/docprime/workspace/backend/


#GET ENVIRONEMENT AND CONFIGURATIONS
RUN git clone https://ronit29pb:KFSfpRpjJwBCbGLdZufx@bitbucket.org/ronit29pb/environments.git /env
RUN cp /env/django/gunicorn_config.py /home/docprime/workspace/backend/
RUN cp /env/django/django_env /home/docprime/workspace/backend/.env
RUN cp /env/django/entrypoint /home/docprime/workspace/entrypoint
#RUN sed -i 's/\r//' /entrypoint
RUN chmod +x /home/docprime/workspace/entrypoint/entrypoint


#NGINX CONFIGURATION
WORKDIR /etc/nginx
RUN mkdir -p sites-enabled
RUN mv /env/django/nginx.conf /etc/nginx/
RUN ["ln", "-s", "/etc/nginx/nginx.conf", "/etc/nginx/sites-enabled/"]


#DJANGO MANAGEMENT COMMANDS
WORKDIR /home/docprime/workspace/backend
RUN pip install -r requirements/local.txt
ENV DJANGO_SETTINGS_MODULE=config.settings.staging
RUN python manage.py collectstatic --no-input


EXPOSE 80
# RUN cp -r /env/django/supervisor_configs/.  /etc/supervisor/conf.d/
CMD ["sh", "/home/docprime/workspace/entrypoint/entrypoint"]

