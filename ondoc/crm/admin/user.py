from django.contrib.gis import admin
from django.contrib.auth.forms import UserChangeForm
from django.contrib.auth.admin import UserAdmin
from reversion.admin import VersionAdmin
from django import forms
from ondoc.authentication.models import (StaffProfile)
from ondoc.authentication.models import UserNumberUpdate
from django.db import transaction


class StaffProfileInline(admin.TabularInline):
    model = StaffProfile
    extra = 0
    can_delete = False
    show_change_link = False




# class UserNumberUpdateInline(admin.TabularInline):
#     model = UserNumberUpdate
#     extra = 0
#     max_num = 1
#     can_delete = False
#     show_change_link = False
#     fields = ('new_number', 'otp', 'is_successfull')
#     readonly_fields = ('is_successfull',)
#     form = UserNumberUpdateForm



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
        # UserNumberUpdateInline
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


class UserNumberUpdateForm(forms.ModelForm):
    user_otp = forms.IntegerField(required=False, label="User otp")

    def __init__(self, *args, **kwargs):
        super(UserNumberUpdateForm, self).__init__(*args, **kwargs)
        instance = getattr(self, 'instance', None)
        if not instance or (instance and instance.is_successfull):
            self.fields['user_otp'].disabled = True
            self.fields['user_otp'].disabled = True

    def clean(self):
        if self.cleaned_data.get('user_otp'):
            user = self.cleaned_data.get('user')
            obj = UserNumberUpdate.objects.filter(user=user, old_number=user.phone_number, new_number=self.cleaned_data.get('new_number')).order_by('id').last()

            if obj and obj.otp != self.cleaned_data.get('user_otp'):
                raise forms.ValidationError('')

        new_number = self.cleaned_data.get('new_number')

        if not UserNumberUpdate.can_be_changed(new_number):
            raise forms.ValidationError('Given new number is already in used by some other person.')

        return super().clean()


class UserNumberUpdateAdmin(admin.ModelAdmin):

    model = UserNumberUpdate
    date_hierarchy = 'created_at'
    fields = ('user','new_number', 'user_otp', 'is_successfull')
    readonly_fields = ('is_successfull',)
    form = UserNumberUpdateForm

    autocomplete_fields = ['user']

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        if obj and obj.id and form.data and form.data.get('user_otp'):
            obj._process_update = True

        super().save_model(request, obj, form, change)

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.is_successfull:
            return ['user', 'new_number', 'is_successfull', ]
        else:
            if obj and obj.id and not obj.is_successfull:
                return ['is_successfull']
            else:
                return ['is_successfull']