from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import include, path
from apps.core.views import home, system_status

urlpatterns = [
    path('', home, name='home'),
    path('accounts/login/', LoginView.as_view(), name='login'),
    path('accounts/logout/', LogoutView.as_view(), name='logout'),
    path('catalogos/', include('apps.catalogos.urls')),
    path('conceptos/', include('apps.conceptos.urls')),
    path('sistema/status/', system_status, name='system_status'),
    path('admin/', admin.site.urls),
]
