from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from .models import Review
from .serializers import ReviewSerializer
from rest_framework.pagination import PageNumberPagination

class ReviewPagination(PageNumberPagination):
    page_size = 20
    max_page_size = 1000
    page_size_query_param = 'page_size'
    page_query_param = 'page'

class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = ReviewPagination
    def get_queryset(self):
        # Allow filtering by product_id
        queryset = Review.objects.all()
        product_id = self.request.query_params.get('product_id')
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        return queryset

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
