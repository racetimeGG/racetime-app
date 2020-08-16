import requests
from django.conf import settings


class TalksToTwitch:
    @staticmethod
    def fetch_token():
        resp = requests.post('https://id.twitch.tv/oauth2/token', {
            'client_id': settings.TWITCH_CLIENT_ID,
            'client_secret': settings.TWITCH_CLIENT_SECRET,
            'grant_type': 'client_credentials',
        })
        if resp.status_code != 200:
            raise requests.RequestException

        data = resp.json()
        return data.get('access_token')
