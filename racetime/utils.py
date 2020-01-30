import json
import random
from urllib.parse import urlencode

from channels_redis.core import RedisChannelLayer as BaseRedisChannelLayer
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse
from django.utils.module_loading import import_string
from hashids import Hashids

__all__ = [
    'RedisChannelLayer',
    'SafeException',
    'exception_to_msglist',
    'generate_race_slug',
    'get_hashids',
    'timer_html',
    'timer_str',
    'twitch_auth_url',
]

slug_adjectives = [
    'adequate',
    'agreeable',
    'amazing',
    'amused',
    'artful',
    'brainy',
    'brave',
    'calm',
    'chaotic',
    'charming',
    'clean',
    'clumsy',
    'comic',
    'crazy',
    'curious',
    'cute',
    'dapper',
    'dazzling',
    'disco',
    'dizzy',
    'dynamax',
    'eager',
    'elegant',
    'famous',
    'fancy',
    'foolish',
    'fortunate',
    'frantic',
    'gentle',
    'good',
    'gorgeous',
    'graceful',
    'grumpy',
    'helpful',
    'hungry',
    'innocent',
    'intrepid',
    'jolly',
    'kind',
    'lawful',
    'lazy',
    'lucky',
    'magnificent',
    'mega',
    'mysterious',
    'neutral',
    'obedient',
    'odd',
    'pogtastic',
    'proud',
    'prudent',
    'puzzled',
    'reliable',
    'saucy',
    'scrawny',
    'scruffy',
    'shiny',
    'silly',
    'sleepy',
    'smart',
    'splendid',
    'sublime',
    'superb',
    'tasty',
    'trusty',
    'wild',
    'witty',
    'wonderful',
    'zany',
]

slug_nouns = [
    'ash',
    'bahamut',
    'banjo',
    'bayonetta',
    'booyah',
    'bowser',
    'brock',
    'cactuar',
    'charizard',
    'chell',
    'chip',
    'chocobo',
    'chrom',
    'cid',
    'cloud',
    'codsworth',
    'corrin',
    'crash',
    'daddy',
    'daisy',
    'dedede',
    'diddy',
    'falco',
    'fez',
    'ganondorf',
    'garuda',
    'geralt',
    'glitterworld',
    'greninja',
    'hitman',
    'ifrit',
    'ike',
    'incineroar',
    'inkling',
    'isabelle',
    'ivysaur',
    'jebediah',
    'jigglypuff',
    'joker',
    'kazooie',
    'ken',
    'kerbal',
    'kirby',
    'lara',
    'lightning',
    'link',
    'lucario',
    'luigi',
    'luma',
    'lyra',
    'mario',
    'marth',
    'megaman',
    'mewtwo',
    'misty',
    'moogle',
    'moon',
    'mushroom',
    'ness',
    'olimar',
    'pacman',
    'palutena',
    'peach',
    'pichu',
    'pikachu',
    'pit',
    'ramuh',
    'richter',
    'ridley',
    'robin',
    'rosalina',
    'roy',
    'samus',
    'sans',
    'shadow',
    'shane',
    'shiva',
    'shulk',
    'simon',
    'slime',
    'snake',
    'sonic',
    'squirtle',
    'stanley',
    'star',
    'stardrop',
    'starfox',
    'sun',
    'tails',
    'terry',
    'theresa',
    'villager',
    'waluigi',
    'wario',
    'wolf',
    'yoshi',
    'yuna',
    'zelda',
    'zombie',
]


class RedisChannelLayer(BaseRedisChannelLayer):
    """
    Custom channel layer that correctly serializes Django-ey data.
    """
    def serialize(self, message):
        value = json.dumps(message, cls=DjangoJSONEncoder)
        if self.crypter:
            value = self.crypter.encrypt(value)
        return value

    def deserialize(self, message):
        if self.crypter:
            message = self.crypter.decrypt(message, self.expiry + 10)
        return json.loads(message)


class SafeException(Exception):
    """
    Used to indicate an exception whose message is safe to display to end-users.
    """
    pass


def exception_to_msglist(ex):
    errors = []
    for arg in ex.args:
        if isinstance(arg, str):
            errors.append(arg)
        elif isinstance(arg, dict):
            for field, messages in arg.items():
                errors += [
                    f'{field}: {message}' for message in messages
                ]
    return errors


def generate_race_slug(custom_nouns=None):
    return '-'.join([
        random.choice(slug_adjectives),
        random.choice(custom_nouns if custom_nouns else slug_nouns),
        '%04d' % random.randint(1, 9999),
    ])


def get_hashids(cls):
    """
    Return a Hashids object for generating hashids scoped to the given class.
    """
    return Hashids(salt=str(cls) + settings.SECRET_KEY, min_length=16)


def notice_exception(exception):
    """
    Take notice of an exception. This function should be called when an error
    is deliberately squashed instead of being raised, but still needs to be
    logged somewhere.
    """
    try:
        receiver = import_string(settings.RT_EXCEPTION_RECV)
    except (AttributeError, ImportError):
        # No exception receiver set up.
        pass
    else:
        receiver(exception)


def timer_str(delta, deciseconds=True):
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if deciseconds:
        return '{:01}:{:02}:{:02}.{}'.format(
            hours,
            minutes,
            seconds,
            min(round(delta.microseconds / 100000), 9),
        )
    return '{:01}:{:02}:{:02}'.format(
        hours,
        minutes,
        seconds,
    )


def timer_html(delta, deciseconds=True):
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if deciseconds:
        return '{:01}:{:02}:{:02}<small>.{}</small>'.format(
            hours,
            minutes,
            seconds,
            min(round(delta.microseconds / 100000), 9),
        )
    return '{:01}:{:02}:{:02}'.format(
        hours,
        minutes,
        seconds,
    )


def twitch_auth_url(request):
    return 'https://id.twitch.tv/oauth2/authorize?' + urlencode({
        'client_id': settings.TWITCH_CLIENT_ID,
        'redirect_uri': request.build_absolute_uri(reverse('twitch_auth')),
        'response_type': 'code',
        'scope': '',
        'force_verify': 'true',
        'state': request.META.get('CSRF_COOKIE'),
    })
