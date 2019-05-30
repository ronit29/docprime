from django.contrib import admin
from ondoc.reports import models as report_models
from django.shortcuts import render
from ondoc.api.v1.utils import RawSql
from django.forms import ModelForm
import django_tables2 as tables
from django_tables2 import RequestConfig
from django_tables2.export.export import TableExport
import datetime
from django.db import connection
from collections import namedtuple, OrderedDict

def get_table_class(keys):
    def get_table_column(field, value):
        if isinstance(value,datetime.datetime):
            return tables.DateTimeColumn()
        else:
            return tables.Column()

    attrs = dict(
        (f, get_table_column(f,keys[f])) for
        f in keys
    )
    attrs['Meta'] = type('Meta', (), {'attrs': {"class": "table"}, "order_by": ("-created_at",)})
    klass = type('DTable', (tables.Table,), attrs)
    return klass


class ReportForm(ModelForm):

    class Meta:
        model = report_models.GeneratedReport
        fields = ('report_name', 'description', 'sql')


class ReportAdmin(admin.ModelAdmin):
    change_form_template = 'report.html'
    add_form_template = 'admin/change_form.html'
    list_display = ('report_name', )
    search_fields = ['report_name', ]
    form = ReportForm

    def get_queryset(self, request):
        return report_models.Report.objects.all()

    def change_view(self, request, object_id=None, extra_context=None):
        if not object_id:
            return render(request, 'access_denied.html')

        object = report_models.GeneratedReport.objects.get(pk=object_id)
        if not object:
            return render(request, 'access_denied.html')
        query_string = object.sql
        result = self.__execute_query(query_string)
        if result:
            table_class = get_table_class(result[0])
            table = table_class(result)
            table.export_formats = ['xls']
            RequestConfig(request).configure(table)
            export_format = request.GET.get('_export', None)
            if TableExport.is_valid_format(export_format):
                exporter = TableExport(export_format, table)
                return exporter.response('table.{}'.format(export_format))
            form = ReportForm(instance=object, prefix="report")

            extra_context = {'result': table, 'form': form, 'id': object_id, 'request': request, 'report': object}
            return super().change_view(request, object_id, extra_context=extra_context)
    def __execute_query(self, query):
        with connection.cursor() as cursor:
            cursor.execute(query, [])
            columns = [col[0] for col in cursor.description]
            print(columns)
            result = [
                OrderedDict(zip(columns, row))
                for row in cursor.fetchall()
            ]
            return result