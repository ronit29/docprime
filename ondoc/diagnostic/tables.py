import django_tables2 as tables
from .models import AvailableLabTest
from django.utils.safestring import mark_safe


class CheckBoxColumnWithName(tables.CheckBoxColumn):
    @property
    def header(self):
        return self.verbose_name


class LabTestTable(tables.Table):
    MRP_TEMPLATE = '<input disabled id="mrp" class="mrp input-sm" maxlength="10" name="mrp" type="number" value={{ value|default_if_none:"" }} >'
    CUSTOM_AGREED_TEMPLATE = '''<input disabled  class="custom_agreed_price input-sm" maxlength="10" name="custom_agreed_price" type="number" value={{ value|default_if_none:"" }} >'''
    CUSTOM_DEAL_TEMPLATE = '''<input disabled  class="custom_deal_price input-sm"  maxlength="10" name="custom_deal_price" type="number" value={{ value|default_if_none:"" }} >'''

    id = tables.Column(attrs={'td': {'class': 'hidden'}, 'th': {'class': 'hidden'}},
                       orderable=False)
    testid = tables.Column(attrs={'td': {'class': 'hidden'}, 'th': {'class': 'hidden'}},
                           accessor='get_testid',
                           orderable=False)
    enabled = CheckBoxColumnWithName(verbose_name="Enabled", accessor="enabled")
    mrp = tables.TemplateColumn(MRP_TEMPLATE)
    computed_agreed_price = tables.Column()
    custom_agreed_price = tables.TemplateColumn(CUSTOM_AGREED_TEMPLATE)
    computed_deal_price = tables.Column()
    custom_deal_price = tables.TemplateColumn(CUSTOM_DEAL_TEMPLATE)
    edit = tables.TemplateColumn('<button class="edit-row btn btn-danger">Edit</button><button class="save-row btn btn-primary hidden">Save</button>',
                                 verbose_name=u'Edit',
                                 orderable=False)

    def render_enabled(self, record):
        if record.enabled:
            return mark_safe('<input disabled class="enabled" type="checkbox" checked/>')
        else:
            return mark_safe('<input disabled class="enabled" type="checkbox"/>')


    class Meta:
        model = AvailableLabTest
        template_name = 'table.html'
        fields = ('id', 'enabled', 'test', 'mrp', 'computed_agreed_price', 'custom_agreed_price', 'computed_deal_price', 'custom_deal_price', 'edit')
        row_attrs = {'data-id': lambda record: record.pk, 'data-test-id': lambda record: record.test.id}
        attrs = {'class':'table table-condensed table-striped'}

