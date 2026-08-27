from rest_framework import serializers
from django.db import models
from product.models import Product, ProductVariant, ProductVariantOptionValue, ProductImage
from order.models import OrderItem
from review.models import Review
from review.serializers import ReviewSerializer
from .variant import ProductVariantSerializer
from .image import ProductImageSerializer


class ProductSerializer(serializers.ModelSerializer):
    variants = ProductVariantSerializer(many=True)
    images = ProductImageSerializer(many=True, required=False, allow_null=True)
    is_stock = serializers.SerializerMethodField(read_only=True)
    shop_data = serializers.SerializerMethodField(read_only=True)
    sub_category_data = serializers.SerializerMethodField(read_only=True)
    available_options = serializers.SerializerMethodField(read_only=True)
    eligible_for_review = serializers.SerializerMethodField(read_only=True)
    average_rating = serializers.SerializerMethodField(read_only=True)
    reviews = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Product
        fields = ['id', 'name', 'is_stock', 'slug', 'shop', 'shop_data', 'average_rating', 'sub_category', 'sub_category_data', 'weight', 'variants', 'images', 'available_options', 'created_at', 'updated_at', 'eligible_for_review', 'reviews']
        read_only_fields = ['shop', 'created_at', 'updated_at']

    def get_shop_data(self, obj):
        return {
            "shop_name": obj.shop.name,
            "shop_id": obj.shop.id,
            "shop_owner_id": obj.shop.owner_id,
        }


    def get_sub_category_data(self, obj):
        return {
            "sub_category_name": obj.sub_category.name,
            "sub_category_id": obj.sub_category.id,
        }

    def get_is_stock(self, obj):
        return obj.variants.annotate(
            available_stock_calc=models.F('stock') - models.F('reserved_quantity')
        ).filter(available_stock_calc__gt=0).exists()

    def get_available_options(self, obj):
        variants = obj.variants.annotate(
            available_stock_calc=models.F('stock') - models.F('reserved_quantity')
        ).filter(available_stock_calc__gt=0).prefetch_related(
            'option_values__option_value__product_category_option'
        )
        options = {}
        for variant in variants:
            for ov in variant.option_values.all():
                option_name = ov.option_value.product_category_option.name
                value = ov.option_value.value
                value_id = ov.option_value.id
                if option_name not in options:
                    options[option_name] = {}
                options[option_name][value] = value_id
        result = {}
        for opt_name, val_dict in options.items():
            result[opt_name] = [{"id": vid, "value": val} for val, vid in val_dict.items()]
        return result

    def get_eligible_for_review(self, obj):
        user = self.context['request'].user
        if not user.is_authenticated:
            return False

        purchased = OrderItem.objects.filter(
            shop_order__order__user=user,
            shop_order__status="delivered",
            product_variant__product=obj
        ).exists()

        if purchased and Review.objects.filter(product=obj, user=user).exists():
            return False
        return purchased

    def get_reviews(self, obj):
        all_reviews = obj.reviews.all()
        sorted_reviews = sorted(all_reviews, key=lambda r: r.created_at, reverse=True)[:10]
        return ReviewSerializer(sorted_reviews, many=True).data

    def get_average_rating(self, obj):
        all_reviews = obj.reviews.all()
        if not all_reviews:
            return 0
        total = sum(int(r.rating) for r in all_reviews)
        count = len(all_reviews)
        return round(total / count, 1) if count else 0

    def validate(self, attrs):
        if self.instance:
            user = self.context['request'].user
            shop = self.instance.shop
            if shop.owner != user:
                raise serializers.ValidationError({"detail": "You are not authorized to update this product because you are not the owner of the shop."})
            if not user.is_active:
                raise serializers.ValidationError({"detail": "Your account has been deactivated."})
            if not shop.is_active:
                raise serializers.ValidationError({"detail": "Your shop has been suspended."})
            if shop.is_deactivated:
                raise serializers.ValidationError({"detail": "Your shop has been deactivated."})
            if shop.status != 'approved':
                raise serializers.ValidationError({"detail": f"Your shop is currently {shop.status}."})
        return attrs

    def create(self, validated_data):
        variants_data = validated_data.pop('variants', [])
        images_data = validated_data.pop('images', [])
        product = Product.objects.create(**validated_data)

        for variant_data in variants_data:
            option_values_data = variant_data.pop('option_values', [])
            variant = ProductVariant.objects.create(product=product, **variant_data)

            for ov_data in option_values_data:
                ProductVariantOptionValue.objects.create(variant=variant, **ov_data)

        for image_data in images_data:
            ProductImage.objects.create(product=product, **image_data)
        return product

    def update(self, instance, validated_data):
        request = self.context.get('request')
        variants_data = validated_data.pop('variants', None)
        images = validated_data.pop('images', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if variants_data is not None:
            keep_variants = []
            for variant_data in variants_data:
                variant_id = variant_data.get('id')
                option_values_data = variant_data.pop('option_values', [])

                if variant_id:
                    try:
                        variant = ProductVariant.objects.get(id=variant_id, product=instance)
                        for attr, value in variant_data.items():
                            setattr(variant, attr, value)
                        variant.save()
                    except ProductVariant.DoesNotExist:
                        variant = ProductVariant.objects.create(product=instance, **variant_data)
                else:
                    variant = ProductVariant.objects.create(product=instance, **variant_data)

                keep_variants.append(variant.id)

                variant.option_values.all().delete()
                for ov_data in option_values_data:
                    ov_data.pop('id', None)
                    ProductVariantOptionValue.objects.create(variant=variant, **ov_data)

            instance.variants.exclude(id__in=keep_variants).delete()

        image_keys = [k for k in request.data.keys() if k.startswith('images[')]

        if image_keys or 'images' in request.data:
            existing_image_ids = []
            new_images = []

            if images is not None:
                for image_data in images:
                    if isinstance(image_data, dict):
                        image_id = image_data.get('id')
                        if image_id:
                            existing_image_ids.append(image_id)
                        elif image_data.get('image'):
                            new_images.append(image_data)
                    else:
                        new_images.append({'image': image_data})

            for image_data in new_images:
                ProductImage.objects.create(product=instance, **image_data)

            if existing_image_ids:
                instance.images.exclude(id__in=existing_image_ids).delete()

        return instance
