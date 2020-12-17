from rest_framework_simplejwt.serializers import TokenObtainPairSerializer as SimpleJwtTokenObtainPairSerializer


class TokenObtainPairSerializer(SimpleJwtTokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super(TokenObtainPairSerializer, cls).get_token(user)
        token['sub'] = user.hashid
        token['name'] = user.get_full_name()
        return token
