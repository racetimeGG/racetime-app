from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework import permissions

from racetime.serializers import TokenObtainPairSerializer


class TokenObtainPairSerializerView(TokenObtainPairView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = TokenObtainPairSerializer
