from rest_framework.viewsets import ModelViewSet
from shop.models import Market
from shop.serializers import MarketSerializer


class MarketView(ModelViewSet):
    queryset = Market.objects.all()
    serializer_class = MarketSerializer
    http_method_names = ['get']
