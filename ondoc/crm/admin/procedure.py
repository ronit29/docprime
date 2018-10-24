from reversion.admin import VersionAdmin
from ondoc.crm.admin.doctor import AutoComplete
from ondoc.procedure.models import Procedure


class ProcedureAdmin(AutoComplete, VersionAdmin):
    model = Procedure
    search_fields = ['name']
