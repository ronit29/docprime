from django.shortcuts import render, redirect, HttpResponse
from django.shortcuts import render_to_response
from django.utils.safestring import mark_safe
from django.conf import settings
from .models import Lab, LabTest, AvailableLabTest, LabPricingGroup, LabTestPricingGroup
from .forms import LabForm, LabMapForm
from dal import autocomplete
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
import django_tables2 as tables
from django.http import HttpResponseRedirect
from django_tables2 import RequestConfig
from .serializers import AjaxAvailableLabTestSerializer
import decimal
import math
from django.contrib.auth.decorators import user_passes_test
from decimal import Decimal
from django.contrib import messages


class LabTestAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        query = self.request.GET.get('query')
        print(query)
        if not self.request.user:
            return LabTest.objects.none()
        qs = LabTest.objects.all()
        if query:
            qs = qs.filter(name__istartswith=query)
        return qs


def labajaxmodelsave(request):
    if request.method == "POST":
        id = request.POST.get('id')
        model_instance = LabPricingGroup.objects.get(id=id)


        pap = decimal.Decimal(request.POST['lab-pathology_agreed_price_percentage']) if request.POST.get('lab-pathology_agreed_price_percentage') else None
        rap = decimal.Decimal(request.POST['lab-radiology_agreed_price_percentage']) if request.POST.get('lab-radiology_agreed_price_percentage') else None

        if pap and pap<20 or rap and rap<20:
            messages.add_message(request, messages.ERROR, "Agreed Percent cannot be less than 20 percent")
            return HttpResponseRedirect('/admin/diagnostic/labpricinggroup/'+id+'/change/')

        if pap and pap>100 or rap and rap>100:
            messages.add_message(request, messages.ERROR, "Agreed Percent cannot be greater than 100 percent")
            return HttpResponseRedirect('/admin/diagnostic/labpricinggroup/'+id+'/change/')


        if not pap and AvailableLabTest.objects.filter(lab_pricing_group=model_instance,test__test_type=LabTest.PATHOLOGY).exists():
            messages.add_message(request, messages.ERROR, "Delete Pathology tests first")
            return HttpResponseRedirect('/admin/diagnostic/labpricinggroup/'+id+'/change/')

        if not rap and AvailableLabTest.objects.filter(lab_pricing_group=model_instance,test__test_type=LabTest.RADIOLOGY).exists():
            messages.add_message(request, messages.ERROR, "Delete Radiology tests first")
            return HttpResponseRedirect('/admin/diagnostic/labpricinggroup/'+id+'/change/')


        model_instance.pathology_agreed_price_percentage = pap
        model_instance.radiology_agreed_price_percentage = rap

        multiplier = Decimal(1.2)
        if pap:
            model_instance.pathology_deal_price_percentage = min(math.ceil(multiplier*pap),100.0)

        if rap:
            model_instance.radiology_deal_price_percentage = min(math.ceil(multiplier*rap),100.0)

        model_instance.save()
        return HttpResponseRedirect('/admin/diagnostic/labpricinggroup/'+id+'/change/')
    else:
        return HttpResponseRedirect('/admin')


def availablelabtestajaxsave(request):
    if request.method == "POST" and request.is_ajax():
        instance = None
        if(request.POST.get('id')):
            instance = AvailableLabTest.objects.get(pk=request.POST.get('id'))

        serialized_data = AjaxAvailableLabTestSerializer(instance=instance, data=request.POST)

        if serialized_data.is_valid(raise_exception=True):
            data = serialized_data.validated_data
            id = data.get('id')
            data['computed_agreed_price'] = get_computed_agreed_price(data)
            data['computed_deal_price'] = get_computed_deal_price(data)
            data['custom_agreed_price'] = None
            data['custom_deal_price'] = None

            if id:
                record = AvailableLabTest.objects.filter(id=id)
                if record:
                    record.update(**data)
                    return JsonResponse({'success': 1,'id' : id, 'computed_agreed_price': data['computed_agreed_price'], 'computed_deal_price': data['computed_deal_price']})
            else:
                new_record = AvailableLabTest.objects.create(**data)
                return JsonResponse({'success': 1, 'id' : new_record.id, 'computed_agreed_price': data['computed_agreed_price'], 'computed_deal_price': data['computed_deal_price']})
    else:
        return JsonResponse({'error': "Invalid Request"})


def get_computed_agreed_price(obj):
    if obj.get('test').test_type == LabTest.RADIOLOGY:
        agreed_percent = obj.get('lab_pricing_group').radiology_agreed_price_percentage if obj.get('lab_pricing_group').radiology_agreed_price_percentage else None
    else:
        agreed_percent = obj.get('lab_pricing_group').pathology_agreed_price_percentage if obj.get('lab_pricing_group').pathology_agreed_price_percentage else None
    mrp = decimal.Decimal(obj.get('mrp'))

    if agreed_percent is not None:
        price = math.ceil(mrp * (agreed_percent / 100))
        if price>mrp:
            price=mrp
        return price
    else:
        return None


def get_computed_deal_price(obj):
    if obj.get('test').test_type == LabTest.RADIOLOGY:
        deal_percent = obj.get('lab_pricing_group').radiology_deal_price_percentage if obj.get('lab_pricing_group').radiology_deal_price_percentage else None
    else:
        deal_percent = obj.get('lab_pricing_group').pathology_deal_price_percentage if obj.get('lab_pricing_group').pathology_deal_price_percentage else None
    mrp = decimal.Decimal(obj.get('mrp'))
    computed_agreed_price = obj.get('computed_agreed_price')
    if deal_percent is not None:
        price = math.ceil(mrp * (deal_percent / 100))
        # ceil to next 10 and subtract 1 so it end with a 9
        price = math.ceil(price/10.0)*10-1
        if price>mrp:
            price=mrp
        if computed_agreed_price is not None:
            if price<computed_agreed_price:
                price=computed_agreed_price
        return price
    else:
        return None




# class LabTestTable(tables.Table):
#     MRP_TEMPLATE = '<input disabled id="mrp" class="mrp input-sm" maxlength="10" name="mrp" type="number" value={{ value|default_if_none:"" }} >'
#     CUSTOM_AGREED_TEMPLATE = '''<input disabled  class="custom_agreed_price input-sm" maxlength="10" name="custom_agreed_price" type="number" value={{ value|default_if_none:"" }} >'''
#     CUSTOM_DEAL_TEMPLATE = '''<input disabled  class="custom_deal_price input-sm"  maxlength="10" name="custom_deal_price" type="number" value={{ value|default_if_none:"" }} >'''

#     id = tables.Column(attrs={'td': {'class': 'hidden'}, 'th': {'class': 'hidden'}},
#                        orderable=False)
#     testid = tables.Column(attrs={'td': {'class': 'hidden'}, 'th': {'class': 'hidden'}},
#                            accessor='get_testid',
#                            orderable=False)
#     enabled = CheckBoxColumnWithName(verbose_name="Enabled", accessor="enabled")
#     mrp = tables.TemplateColumn(MRP_TEMPLATE)
#     computed_agreed_price = tables.Column()
#     custom_agreed_price = tables.TemplateColumn(CUSTOM_AGREED_TEMPLATE)
#     computed_deal_price = tables.Column()
#     custom_deal_price = tables.TemplateColumn(CUSTOM_DEAL_TEMPLATE)
#     edit = tables.TemplateColumn('<button class="edit-row btn btn-danger">Edit</button><button class="save-row btn btn-primary hidden">Save</button>',
#                                  verbose_name=u'Edit',
#                                  orderable=False)

#     def render_enabled(self, record):
#         if record.enabled:
#             return mark_safe('<input disabled class="enabled" type="checkbox" checked/>')
#         else:
#             return mark_safe('<input disabled class="enabled" type="checkbox"/>')


#     class Meta:
#         model = AvailableLabTest
#         template_name = 'table.html'
#         fields = ('id', 'enabled', 'test', 'mrp', 'computed_agreed_price', 'custom_agreed_price', 'computed_deal_price', 'custom_deal_price', 'edit')
#         row_attrs = {'data-id': lambda record: record.pk, 'data-test-id': lambda record: record.test.id}
#         attrs = {'class':'table table-condensed table-striped'}


@user_passes_test(lambda u: u.groups.filter(name='lab_pricing_team').exists() or u.is_superuser,login_url='/admin/')
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
    return render(request, 'labtest.html', {'labtesttable': table, 'form': form, 'id': pk, 'request': request,'lab':existing})


@user_passes_test(lambda u: u.groups.filter(name='qc_team').exists() or u.is_superuser,login_url='/admin/')
def lab_map_view(request):
    labs = Lab.objects.all()
    form = LabMapForm()
    if request.GET:
        filtering_params = {key: True if value == "on" else value for key, value in request.GET.items()}
        labs = Lab.objects.filter(**filtering_params)
        form = LabMapForm(request.GET)
    lab_locations = [{"id": lab.id, "longitude": lab.location.x, "latitude": lab.location.y,
                      "name": lab.name} for lab in labs if lab.location]
    return render_to_response('lab_map.html',
                              {'labs': lab_locations, "form": form,
                               'google_map_key': settings.GOOGLE_MAPS_API_KEY})
