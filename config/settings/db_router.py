from django.conf import settings

DATABASE_LABEL_APPS_MAPPING = {
    'bookinganalytics' : 'sql_server'
}

class DatabaseRouter:
    """
    A router to control all database operations on models in the
    docprime application.
    """

    def __init__(self):
        from django.db import DEFAULT_DB_ALIAS

        self.DEFAULT_DB_ALIAS = DEFAULT_DB_ALIAS
        self.state = 'default'

    def set_state(self, state):
        if state in list(settings.DATABASES.keys()):
            self.state = state
        else:
            self.state = 'default'

    def db_for_read(self, model, **hints):
        if model._meta.app_label in DATABASE_LABEL_APPS_MAPPING:
            return DATABASE_LABEL_APPS_MAPPING[model._meta.app_label]
        return self.state

    def db_for_write(self, model, **hints):
        if model._meta.app_label in DATABASE_LABEL_APPS_MAPPING:
            return DATABASE_LABEL_APPS_MAPPING[model._meta.app_label]
        return self.DEFAULT_DB_ALIAS

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label not in DATABASE_LABEL_APPS_MAPPING:
            return True
        return False
