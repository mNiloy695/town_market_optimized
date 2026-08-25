from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from .models import Review
from .serializers import ReviewSerializer
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend


class IsReviewOwnerOrReadOnly(permissions.BasePermission):
    """
    VULN-03: Object-level permission to ensure only the review author
    can delete their own review. All other write operations (PUT/PATCH)
    are blocked at the viewset level via http_method_names.
    """
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.user == request.user


class ReviewPagination(PageNumberPagination):
    page_size = 10
    max_page_size = 1000
    page_size_query_param = 'page_size'
    page_query_param = 'page'

class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsReviewOwnerOrReadOnly]
    pagination_class = ReviewPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['product_id']
    # Reviews are immutable once created – only allow create, list, retrieve, and delete.
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_queryset(self):
        # Allow filtering by product_id
        queryset = Review.objects.all()
        product_id = self.request.query_params.get('product_id')
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        return queryset

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

