from django.contrib.admin.views.autocomplete import AutocompleteJsonView

class CustomAutoComplete(AutocompleteJsonView):
    def has_perm(self, request, obj=None):
        return True
        """Check if user has permission to access the related model."""
        #return self.model_admin.has_change_permission(request, obj=obj)


class PackageAutoComplete(AutocompleteJsonView):

    def get_queryset(self):
        return super().get_queryset().filter(lab_test__is_package=False, package__is_package=True)


class PackageAutoCompleteView:
    def autocomplete_view(self, request):
        return PackageAutoComplete.as_view(model_admin=self)(request)
