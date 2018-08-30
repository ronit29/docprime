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
# from .v1.account.router import urlpatterns as acct_url


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
]
