DATABASE_LABEL_APPS_MAPPING = {
    'bookinganalytics' : 'sql_server'
}

class DatabaseRouter:
    """
    A router to control all database operations on models in the
    docprime application.
    """
    def db_for_read(self, model, **hints):
        if model._meta.app_label in DATABASE_LABEL_APPS_MAPPING:
            return DATABASE_LABEL_APPS_MAPPING[model._meta.app_label]
        return 'default'

    def db_for_write(self, model, **hints):
        if model._meta.app_label in DATABASE_LABEL_APPS_MAPPING:
            return DATABASE_LABEL_APPS_MAPPING[model._meta.app_label]
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label not in DATABASE_LABEL_APPS_MAPPING:
            return True
        return False