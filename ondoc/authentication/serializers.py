from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from django.contrib.auth import get_user_model
User = get_user_model()

class UserAuthSerializer(serializers.ModelSerializer):
    # phone_number = serializers.CharField(max_length=10, validators=[UniqueValidator(queryset=User.objects.all())])
    password = serializers.CharField(required=False)
    phone_number = serializers.CharField(required=True)


    def create(self, validated_data):
        user = User(phone_number=validated_data['phone_number'], user_type=self.context['user_type'], email=validated_data['email'], is_phone_number_verified=validated_data['is_phone_number_verified'])

        # user.set_password(validated_data['password'])
        user.save()
        return user

    def validate(self, data):

        if len(data['phone_number']) != 10:
            raise serializers.ValidationError("Invalid Phone Number")
        if User.objects.filter(phone_number=data['phone_number'], user_type=self.context['user_type']).count() > 0:
            raise serializers.ValidationError("User with this phone number already exists")
        return data



    class Meta:
        model = get_user_model()
        fields = ('id', 'phone_number', 'password', 'email', 'is_phone_number_verified')
