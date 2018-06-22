from django.shortcuts import render, redirect, HttpResponse
from django.utils.safestring import mark_safe
from .models import Lab, LabTest, AvailableLabTest
from .forms import LabForm
from dal import autocomplete
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
import django_tables2 as tables
from django.http import HttpResponseRedirect
from django_tables2 import RequestConfig
from ondoc.api.v1.diagnostic.serializers import AjaxAvailableLabTestSerializer
from django.contrib.admin.views.decorators import staff_member_required



class LabTestAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user:
            return LabTest.objects.none()
        qs = LabTest.objects.all()
        if self.q:
            qs = qs.filter(name__istartswith=self.q)
        return qs


def labajaxmodelsave(request):
    if request.method == "POST":
        id = request.POST.get('id')
        model_instance = Lab.objects.get(id=id)
        model_instance.pathology_agreed_price_percent = request.POST['lab-pathology_agreed_price_percent'] if request.POST.get('lab-pathology_agreed_price_percent') else None
        model_instance.pathology_deal_price_percent = request.POST['lab-pathology_deal_price_percent'] if request.POST.get('lab-pathology_deal_price_percent') else None
        model_instance.radiology_agreed_price_percent = request.POST['lab-radiology_agreed_price_percent'] if request.POST.get('lab-radiology_agreed_price_percent') else None
        model_instance.radiology_deal_price_percent = request.POST['lab-radiology_deal_price_percent'] if request.POST.get('lab-radiology_deal_price_percent') else None
        model_instance.save()
        return HttpResponseRedirect('/labtest/'+id)
    else:
        return HttpResponseRedirect('/')


def availablelabtestajaxsave(request):
    if request.method == "POST" and request.is_ajax():
        serialized_data = AjaxAvailableLabTestSerializer(data=request.POST)
        if serialized_data.is_valid():
            data = serialized_data.validated_data
            id = data.get('id')
            if id:
                record = AvailableLabTest.objects.filter(id=id)
                if record:
                    record.update(**data)
                    return JsonResponse({'success': id})
            else:
                new_record = serialized_data.save()
                return JsonResponse({'success': new_record.id})
    else:
        return JsonResponse({'error': "Invalid Request"})


class CheckBoxColumnWithName(tables.CheckBoxColumn):
    @property
    def header(self):
        return self.verbose_name


class LabTestTable(tables.Table):
    MRP_TEMPLATE = '''<input disabled id="mrp" class="mrp input-sm" maxlength="10" name="mrp" type="text" value={{ value|default_if_none:"" }} >'''
    AGREED_TEMPLATE = '''<input disabled  class="agreed_price input-sm" maxlength="10" name="agreed_price" type="text" value={{ value|default_if_none:"" }} >'''
    CUSTOM_AGREED_TEMPLATE = '''<input disabled  class="custom_agreed_price input-sm" maxlength="10" name="custom_agreed_price" type="text" value={{ value|default_if_none:"" }} >'''
    DEAL_TEMPLATE = '''<input disabled  class="deal_price input-sm"  maxlength="10" name="deal_price" type="text" value={{ value|default_if_none:"" }} >'''
    CUSTOM_DEAL_TEMPLATE = '''<input disabled  class="custom_deal_price input-sm"  maxlength="10" name="custom_deal_price" type="text" value={{ value|default_if_none:"" }} >'''

    id = tables.Column(attrs={'td': {'class': 'hidden'}, 'th': {'class': 'hidden'}},
                       orderable=False)
    testid = tables.Column(attrs={'td': {'class': 'hidden'}, 'th': {'class': 'hidden'}},
                           accessor='get_testid',
                           orderable=False)
    enabled = CheckBoxColumnWithName(verbose_name="Enabled", accessor="enabled")
    mrp = tables.TemplateColumn(MRP_TEMPLATE)
    agreed_price = tables.TemplateColumn(AGREED_TEMPLATE)
    custom_agreed_price = tables.TemplateColumn(CUSTOM_AGREED_TEMPLATE)
    deal_price = tables.TemplateColumn(DEAL_TEMPLATE)
    custom_deal_price = tables.TemplateColumn(CUSTOM_DEAL_TEMPLATE)
    edit = tables.TemplateColumn('<a class="edit-row">Edit</a><a class="save-row hidden">Save</a>',
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
        fields = ('id', 'enabled', 'test', 'mrp', 'agreed_price', 'custom_agreed_price', 'deal_price', 'custom_deal_price', 'edit')
        row_attrs = {'data-id': lambda record: record.pk}


@staff_member_required
def labtestformset(request, pk):
    if not pk:
        return render(request, 'access_denied.html')
    existing = None
    existing = Lab.objects.get(pk=pk)
    if not existing:
        return render(request, 'access_denied.html')
    form = LabForm(instance=existing, prefix="lab")
    table = LabTestTable(AvailableLabTest.objects.filter(lab=pk), order_by="-id")
    # RequestConfig(request, paginate={"per_page": 10}).configure(table)
    RequestConfig(request).configure(table)
    return render(request, 'labtest.html', {'labtesttable': table, 'form': form, 'id': pk, 'request': request})
