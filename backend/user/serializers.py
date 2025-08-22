from rest_framework import serializers
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import User

class UserOutSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id','username','email','phone_number','avatar','status','login_date','first_name','last_name','remark']

class LoginSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username  # 非敏感声明，减少频繁查库
        token['status'] = user.status
        return token

    def validate(self, attrs):
        data = super().validate(attrs)  # 复用 SimpleJWT 的鉴权（等价 authenticate）
        user = self.user
        if user.status == 0:
            # 这里示意禁用态，你也可以用 0=正常/1=禁用，根据你的枚举调整
            raise AuthenticationFailed('账号已被禁用')
        user.login_date = timezone.now()
        user.save(update_fields=['login_date'])
        data['user'] = UserOutSerializer(user).data
        return data
