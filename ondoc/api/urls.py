from django.conf.urls import url, include
from django.urls import path

from .v1.doctor.router import urlpatterns as doctor_url
from .v1.auth.router import urlpatterns as auth_url
from .v1.diagnostic.router import urlpatterns as diag_url
from .v1.chat.router import urlpatterns as chat_url
from .v1.notification.router import urlpatterns as noti_url
from .v1.payout.router import urlpatterns as payout_url
from .v1.article.router import urlpatterns as article_url
from .v1.admin.router import urlpatterns as admin_url
from .v1.web.router import urlpatterns as web_url
from .v1.common.router import urlpatterns as common_url
from .v1.location.router import urlpatterns as location_url
from .v1.tracking.router import urlpatterns as track_url
from .v1.ratings.router import urlpatterns as rating_url
from .v1.geoip.router import urlpatterns as geoip_url
from .v1.insurance.router import urlpatterns as insurance_url
# from .v1.account.router import urlpatterns as acct_url
from .v1.coupon.router import urlpatterns as coupon_url
from .v1.procedure.router import urlpatterns as procedure_url


urlpatterns = [
    path('v1/doctor/', include(doctor_url)),
    path('v1/user/', include(auth_url)),
    path('v1/diagnostic/', include(diag_url)),
    path('v1/chat/', include(chat_url)),
    path('v1/notification/', include(noti_url)),
    # path('v1/account/', include(acct_url)),
    path('v1/payout/', include(payout_url)),
    path('v1/article/', include(article_url)),
    path('v1/web/', include(web_url)),
    path('v1/admin/', include(admin_url)),
    path('v1/common/', include(common_url)),
    path('v1/location/', include(location_url)),
    path('v1/tracking/', include(track_url)),
    path('v1/ratings/', include(rating_url)),
    path('v1/geoip/', include(geoip_url)),
    path('v1/insurance/', include(insurance_url)),
    path('v1/coupon/', include(coupon_url)),
    path('v1/procedure/', include(procedure_url)),
]
