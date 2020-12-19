from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView


class ApiUserdata(APIView):
    def get(self, request):
        return Response(data={"name": str(request.user)}, status=status.HTTP_200_OK)


