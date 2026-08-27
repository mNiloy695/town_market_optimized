
from django.contrib import admin
from django.urls import path,include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('v1/accounts/', include('accounts.urls')),
    path('v1/shop/',include('shop.urls')),
    path('v1/product/',include('product.urls')),
    path('v1/order/',include('order.urls')),
    path('v1/cart/',include('cart.urls')),
    path("v1/invoice/",include("invoice.urls")),
    path("v1/review/",include("review.urls")),
    path("v1/chat/", include("chat.urls")),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)