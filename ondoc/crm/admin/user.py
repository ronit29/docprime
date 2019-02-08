from django.contrib.gis import admin
from django.contrib.auth.forms import UserChangeForm
from django.contrib.auth.admin import UserAdmin
from reversion.admin import VersionAdmin
from django import forms
from ondoc.authentication.models import (StaffProfile)


class StaffProfileInline(admin.TabularInline):
    model = StaffProfile
    extra = 0
    can_delete = False
    show_change_link = False


class CustomUserChangeForm(UserChangeForm):

    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)
    #     if self.instance.email is None:
    #         self.instance.email = ''
    #         kwargs['instance'] = self.instance
    #         super(CustomUserChangeForm, self).__init__(*args, **kwargs)
    #
    # def clean_email(self):
    #     # if self.initial["email"] is None:
    #     #     return ''
    #     # return self.initial["email"]
    #
    #     email = self.cleaned_data['email']
    #     if email is None:
    #         return ''
    #     return email

    def clean(self):
        if self.cleaned_data.get('is_staff') and not self.data.get('staffprofile-0-employee_id'):
            raise forms.ValidationError("Employee Code must be filled in staff profile.")
        return super().clean()

class CustomUserAdmin(UserAdmin,VersionAdmin):
    list_display = ('email',)
    list_filter = ('is_staff', 'is_superuser')
    ordering = []
    inlines = [
        StaffProfileInline
    ]
    search_fields = ['email', 'phone_number']
    list_display = ('email','phone_number', 'is_active')
    list_select_related = ('staffprofile',)
    form = CustomUserChangeForm
    def save_model(self, request, obj, form, change):
        if not obj.email:
            obj.email = None
        super().save_model(request, obj, form, change)

    def get_fieldsets(self, request, obj=None):
        if not obj:
            return ((None, {'fields': ('email', 'phone_number','groups','user_type','is_staff','is_active','password1','password2')}),)
        return ((None, {'fields': ('email', 'phone_number','groups', 'is_active','is_staff','password')}),)

    # readonly_fields = ['user_type']
    # exclude = ['last_login','is_superuser','user_type','is_phone_number_verified','is_staff']

    # def user_name(self, object):
       # return object.staffprofile

    def get_queryset(self, request):
        # use our manager, rather than the default one
        qs = self.model.objects.get_queryset()

        # we need this from the superclass method
        ordering = self.ordering or () # otherwise we might try to *None, which is bad ;)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs
    def get_changeform_initial_data(self, request):
        return {'user_type': 1}
