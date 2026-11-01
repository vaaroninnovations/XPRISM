from django.contrib import admin
from django.urls import include, path

admin.site.site_header = 'XPRISM • Platform administration'
admin.site.site_title = 'XPRISM admin'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('lab.urls')),
]
handler404 = 'lab.views_public.not_found'
handler403 = 'lab.views_public.forbidden'
