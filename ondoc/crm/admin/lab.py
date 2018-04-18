
class LabTimingInline(admin.TabularInline):
    model = LabTiming
    extra = 0
    can_delete = True
    show_change_link = False


class LabImageInline(admin.TabularInline):
    model = LabImage   
    extra = 0
    can_delete = True
    show_change_link = False
    max_num = 3


class LabManagerInline(admin.TabularInline):
    model = LabManager
    formfield_overrides = {
        models.BigIntegerField: {'widget': forms.TextInput},
    }

    extra = 0
    can_delete = True
    show_change_link = False

class LabAccreditationInline(admin.TabularInline):
    model = LabAccreditation
    extra = 0
    can_delete = True
    show_change_link = False


class LabAwardForm(forms.ModelForm):
    year = forms.ChoiceField(choices=award_year_choices_no_blank, required=True)


class LabAwardInline(admin.TabularInline):
    model = LabAward
    form = LabAwardForm
    extra = 0
    can_delete = True
    show_change_link = False

class LabCertificationInline(admin.TabularInline):
    model = LabCertification
    extra = 0
    can_delete = True
    show_change_link = False


class LabForm(forms.ModelForm):
    about = forms.CharField(widget=forms.Textarea, required=False)
    operational_since = forms.ChoiceField(required=False, choices=hospital_operational_since_choices)

    def validate_qc(self):
        qc_required = {'name':'req','location':'req','operational_since':'req','parking':'req',
            'license':'req','building':'req','locality':'req','city':'req','state':'req',
            'country':'req','pin_code':'req','network_type':'req','labimage':'count'}
        for key,value in qc_required.items():
            if value=='req' and not self.cleaned_data[key]:
                raise forms.ValidationError(key+" is required for Quality Check")
            if value=='count' and int(self.data[key+'_set-TOTAL_FORMS'])<=0:
                raise forms.ValidationError("Atleast one entry of "+key+" is required for Quality Check")
        if self.cleaned_data['network_type']==2 and not self.cleaned_data['network']:
            raise forms.ValidationError("Network cannot be empty for Network Lab")


    def clean(self):
        if not self.request.user.is_superuser:
            if self.instance.data_status == 3:
                raise forms.ValidationError("Cannot update QC approved Lab")

            if self.instance.data_status == 2 and not self.request.user.groups.filter(name=constants['QC_GROUP_NAME']).exists():
                raise forms.ValidationError("Cannot update Lab submitted for QC approval")

            if self.instance.data_status == 1 and self.instance.created_by != self.request.user:
                raise forms.ValidationError("Cannot modify Lab added by other users")


            if '_submit_for_qc' in self.data:
                self.validate_qc()
                if self.instance.network and self.instance.network.data_status <2:
                    raise forms.ValidationError("Cannot submit for QC without submitting associated Lab Network: " + self.instance.network.name)

            if '_qc_approve' in self.data:
                self.validate_qc()
                if self.instance.network and  self.instance.network.data_status < 3:
                    raise forms.ValidationError("Cannot approve QC check without approving associated Lab Network: " + self.instance.network.name)

            if '_mark_in_progress' in self.data:
                if self.instance.data_status == 3:
                    raise forms.ValidationError("Cannot reject QC approved data")

        return super(LabForm, self).clean()


class LabAdmin(admin.GeoModelAdmin, VersionAdmin, ActionAdmin):
    change_form_template = 'custom_change_form.html'

    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        if '_submit_for_qc' in request.POST:
            obj.data_status = 2
        if '_qc_approve' in request.POST:
            obj.data_status = 3
        if '_mark_in_progress' in request.POST:
            obj.data_status = 1

        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if request.user.groups.filter(name=constants['QC_GROUP_NAME']).exists():
            return qs.filter(Q(data_status=2) | Q(data_status=3))
        if request.user.groups.filter(name=constants['DOCTOR_NETWORK_GROUP_NAME']).exists():
            return qs.filter(created_by=request.user )

    def get_form(self, request, obj=None, **kwargs):
        form = super(LabAdmin, self).get_form(request, obj=obj, **kwargs)
        form.request = request
        form.base_fields['network'].queryset = LabNetwork.objects.filter(Q(data_status = 2) | Q(data_status = 3) | Q(created_by = request.user))

        return form

    list_display = ('name', 'updated_at', 'data_status', 'created_by')
    form = LabForm
    search_fields = ['name']
    inlines = [LabCertificationInline, LabAwardInline, LabAccreditationInline,
        LabManagerInline, LabTimingInline]

    map_width = 200
    map_template = 'admin/gis/gmap.html'
    extra_js = ['js/admin/GoogleMap.js','https://maps.googleapis.com/maps/api/js?key=AIzaSyAfoicJaTk8xQOoAOQn9vtHJzgTeZDJRtA&callback=initGoogleMap']
