from rest_framework import serializers
from .models import Review
from order.models import OrderItem, ShopOrder

class ReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.name', read_only=True)
    rating_display = serializers.CharField(source='get_rating_display', read_only=True)

    class Meta:
        model = Review
        fields = ["id", "user", "user_name", "product", "rating", "rating_display", "review_text", "created_at", "updated_at"]
        read_only_fields = ["user", "created_at", "updated_at"]

    def validate(self, attrs):
        request = self.context.get("request")
        if not request or not request.user:
            raise serializers.ValidationError("Authentication required")
            
        user = request.user
        product = attrs["product"]
        

        purchased = OrderItem.objects.filter(
            shop_order__order__user=user,
            shop_order__status="delivered",
            product_variant__product=product
        ).exists()

        if not purchased:
            raise serializers.ValidationError(
                {"error":"You can only review products that have been delivered to you."}
            )

        # Check duplicate review
        if Review.objects.filter(user=user, product=product).exists():
            raise serializers.ValidationError(
               {"error": "You have already reviewed this product."}
            )

        return attrs

    def create(self, validated_data):
        # Automatically set the user to the current authenticated user
        validated_data['user'] = self.context['request'].user
        rating_val = validated_data.get("rating")
        review_text = validated_data.get("review_text", "")
        
        if rating_val and (not review_text or review_text.strip() == ""):
            rating = int(rating_val)
            if rating == 5:
                review_text = "I am extremely satisfied with this product."
            elif rating == 4:
                review_text = "I am satisfied with this product."
            elif rating == 3:
                review_text = "This product is decent and meets my expectations."
            elif rating == 2:
                review_text = "I am somewhat dissatisfied with this product."
            elif rating == 1:
                review_text = "I am very disappointed with this product."
            validated_data["review_text"] = review_text
        return super().create(validated_data)