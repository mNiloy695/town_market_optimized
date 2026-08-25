from rest_framework.views import APIView
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db.models import F
from product.models import Product, ProductVariant


class ProductAvailableOptionsView(APIView):
    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)

        selected_option_value_ids = request.data.get('selected_option_value_ids', [])

        if isinstance(selected_option_value_ids, str):
            selected_option_value_ids = [x.strip() for x in selected_option_value_ids.split(',') if x.strip()]

        try:
            selected_ids_set = {int(x) for x in selected_option_value_ids}
        except (ValueError, TypeError):
            selected_ids_set = set()

        variants = product.variants.annotate(
            available_stock_calc=F('stock') - F('reserved_quantity')
        ).filter(available_stock_calc__gt=0).prefetch_related('option_values__option_value__product_category_option')

        if selected_ids_set:
            for val_id in selected_ids_set:
                variants = variants.filter(option_values__option_value_id=val_id)

        options = {}
        for variant in variants:
            for ov in variant.option_values.all():
                option_name = ov.option_value.product_category_option.name
                value = ov.option_value.value
                value_id = ov.option_value.id
                if value_id not in selected_ids_set:
                    if option_name not in options:
                        options[option_name] = {}
                    options[option_name][value] = value_id

        result = {}
        for opt_name, val_dict in options.items():
            result[opt_name] = [{"id": vid, "value": val} for val, vid in val_dict.items()]
        return Response(result)

    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk)

        selected_option_value_ids = request.query_params.get('selected_option_value_ids', '')
        if isinstance(selected_option_value_ids, str):
            selected_option_value_ids = [x.strip() for x in selected_option_value_ids.split(',') if x.strip()]

        try:
            selected_ids_set = {int(x) for x in selected_option_value_ids}
        except (ValueError, TypeError):
            selected_ids_set = set()

        variants = product.variants.annotate(
            available_stock_calc=F('stock') - F('reserved_quantity')
        ).filter(available_stock_calc__gt=0).prefetch_related('option_values__option_value__product_category_option')

        if selected_ids_set:
            for val_id in selected_ids_set:
                variants = variants.filter(option_values__option_value_id=val_id)

        options = {}
        for variant in variants:
            for ov in variant.option_values.all():
                option_name = ov.option_value.product_category_option.name
                value = ov.option_value.value
                value_id = ov.option_value.id
                if value_id not in selected_ids_set:
                    if option_name not in options:
                        options[option_name] = {}
                    options[option_name][value] = value_id

        result = {}
        for opt_name, val_dict in options.items():
            result[opt_name] = [{"id": vid, "value": val} for val, vid in val_dict.items()]
        return Response(result)


class FindVariantView(APIView):
    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)

        option_value_ids = request.data.get('option_value_ids', [])

        if isinstance(option_value_ids, str):
            option_value_ids = [x.strip() for x in option_value_ids.split(',') if x.strip()]

        try:
            target_set = {int(x) for x in option_value_ids}
        except (ValueError, TypeError):
            return Response({'error': 'Invalid option_value_ids format'}, status=status.HTTP_400_BAD_REQUEST)

        if not target_set:
            return Response({'error': 'option_value_ids is required'}, status=status.HTTP_400_BAD_REQUEST)

        variants = product.variants.annotate(
            available_stock_calc=F('stock') - F('reserved_quantity')
        ).filter(available_stock_calc__gt=0).prefetch_related('option_values')

        for variant in variants:
            variant_option_ids = {ov.option_value_id for ov in variant.option_values.all()}
            if target_set == variant_option_ids:
                return Response({
                    'variant_id': variant.id,
                    'is_stock': True,
                    'available_stock': max(variant.available_stock, 0),
                })

        return Response({
            'error': 'No variant found with the given option values',
            'searched_ids': list(target_set)
        }, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk)

        option_value_ids = request.query_params.get('option_value_ids', '')
        if isinstance(option_value_ids, str):
            option_value_ids = [x.strip() for x in option_value_ids.split(',') if x.strip()]

        try:
            target_set = {int(x) for x in option_value_ids}
        except (ValueError, TypeError):
            return Response({'error': 'Invalid option_value_ids format'}, status=status.HTTP_400_BAD_REQUEST)

        if not target_set:
            return Response({'error': 'option_value_ids is required'}, status=status.HTTP_400_BAD_REQUEST)

        variants = product.variants.annotate(
            available_stock_calc=F('stock') - F('reserved_quantity')
        ).filter(available_stock_calc__gt=0).prefetch_related('option_values')

        for variant in variants:
            variant_option_ids = {ov.option_value_id for ov in variant.option_values.all()}
            if target_set == variant_option_ids:
                return Response({
                    'variant_id': variant.id,
                    'is_stock': True,
                    'available_stock': max(variant.available_stock, 0),
                })

        return Response({
            'error': 'No variant found with the given option values',
            'searched_ids': list(target_set)
        }, status=status.HTTP_400_BAD_REQUEST)


class RestockView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, variant_id):
        from product.serializers import RestockSerializer
        from product.models import ProductVariant

        serializer = RestockSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        quantity = serializer.validated_data['quantity']

        try:
            variant = ProductVariant.objects.select_related('product__shop').get(id=variant_id)
        except ProductVariant.DoesNotExist:
            return Response({"error": "Variant not found"}, status=status.HTTP_404_NOT_FOUND)

        if variant.product.shop.owner != request.user:
            return Response({"error": "You do not own this product's shop"}, status=status.HTTP_403_FORBIDDEN)

        ProductVariant.objects.filter(id=variant_id).update(
            stock=F('stock') + quantity
        )
        variant.refresh_from_db(fields=['stock'])

        return Response({
            "message": f"Added {quantity} units",
            "variant_id": variant.id,
            "new_stock": variant.stock,
        }, status=status.HTTP_200_OK)
