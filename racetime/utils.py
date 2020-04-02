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
    'determine_ip',
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
    'banzai',
    'bonus',
    'brainy',
    'brave',
    'calm',
    'casual',
    'chaotic',
    'charming',
    'classic',
    'clean',
    'clever',
    'clumsy',
    'comic',
    'crafty',
    'crazy',
    'critical',
    'cunning',
    'curious',
    'cute',
    'dapper',
    'dazzling',
    'disco',
    'dizzy',
    'dynamax',
    'dynamic',
    'eager',
    'elegant',
    'epic',
    'famous',
    'fancy',
    'foolish',
    'fortunate',
    'frantic',
    'funky',
    'gentle',
    'gnarly',
    'good',
    'gorgeous',
    'graceful',
    'grumpy',
    'helpful',
    'hungry',
    'hyper',
    'innocent',
    'intrepid',
    'invincible',
    'jolly',
    'kind',
    'lawful',
    'lazy',
    'legendary',
    'lucky',
    'lurking',
    'magic',
    'magnificent',
    'mecha',
    'mega',
    'mini',
    'mysterious',
    'neutral',
    'obedient',
    'odd',
    'outrageous',
    'overpowered',
    'perfect',
    'pogtastic',
    'powerful',
    'priceless',
    'proud',
    'prudent',
    'puzzled',
    'quick',
    'reliable',
    'salty',
    'saucy',
    'scrawny',
    'scruffy',
    'secret',
    'shiny',
    'silly',
    'sleepy',
    'smart',
    'snug',
    'speedy',
    'splendid',
    'sublime',
    'sunken',
    'superb',
    'swag',
    'tactical',
    'tasty',
    'travelling',
    'trusty',
    'unlimited',
    'vanilla',
    'virtual',
    'wild',
    'witty',
    'wonderful',
    'zany',
]

slug_nouns = [
    'ash',
    'bahamut',
    'banjo',
    'battletoad',
    'bayonetta',
    'beedle',
    'bobomb',
    'boo',
    'booyah',
    'bowser',
    'brock',
    'cactuar',
    'cadence',
    'callie',
    'celeste',
    'charizard',
    'checkpoint',
    'chell',
    'chip',
    'chocobo',
    'chrom',
    'cid',
    'clip',
    'cloud',
    'codsworth',
    'conker',
    'corrin',
    'cortana',
    'crash',
    'crusher',
    'cuphead',
    'cutscene',
    'daddy',
    'daisy',
    'dedede',
    'diddy',
    'doge',
    'doomguy',
    'dungeon',
    'eevee',
    'epona',
    'ezlo',
    'falco',
    'fez',
    'fortress',
    'fran',
    'frankerz',
    'ganondorf',
    'garuda',
    'geralt',
    'glados',
    'glitch',
    'glitterworld',
    'goomba',
    'greninja',
    'hitbox',
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
    'jynx',
    'kazooie',
    'ken',
    'kerbal',
    'kirby',
    'knuckles',
    'koopa',
    'lara',
    'layton',
    'lightning',
    'link',
    'lootbox',
    'lucario',
    'luigi',
    'luma',
    'lyra',
    'magikarp',
    'mario',
    'marth',
    'megaman',
    'meowth',
    'meta',
    'metroid',
    'mewtwo',
    'midna',
    'misty',
    'moogle',
    'moon',
    'mudkip',
    'mushroom',
    'navi',
    'ness',
    'noob',
    'olimar',
    'omochao',
    'overworld',
    'pacman',
    'palutena',
    'peach',
    'pichu',
    'pikachu',
    'pipboy',
    'pit',
    'pokey',
    'princess',
    'raichu',
    'ramuh',
    'rayman',
    'red',
    'resetti',
    'richter',
    'ridley',
    'rikku',
    'rimworld',
    'robin',
    'robotnik',
    'rosalina',
    'roy',
    'samus',
    'sans',
    'shadow',
    'shane',
    'shiva',
    'shulk',
    'sidon',
    'sim',
    'simon',
    'skip',
    'slime',
    'slowpoke',
    'snake',
    'snorlax',
    'sonic',
    'sourpls',
    'spaceman',
    'spyro',
    'squirtle',
    'stanley',
    'star',
    'stardrop',
    'starfox',
    'subpixel',
    'sun',
    'tails',
    'tatl',
    'terry',
    'tetra',
    'theresa',
    'tingle',
    'toad',
    'toadstool',
    'togepi',
    'tonberry',
    'villager',
    'vivi',
    'waluigi',
    'wario',
    'wiggler',
    'wolf',
    'yoshi',
    'yuna',
    'zelda',
    'zip',
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


def determine_ip(request):
    if settings.REAL_IP_HEADER:
        return request.headers.get(settings.REAL_IP_HEADER)
    return request.META.get('REMOTE_ADDR')


def exception_to_msglist(ex):
    errors = []
    for arg in ex.args:
        if isinstance(arg, str):
            errors.append(arg)
        elif isinstance(arg, dict):
            for field, messages in arg.items():
                errors += [
                    f'{field}: {message}'
                    if field != '__all__' else message
                    for message in messages
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


def _format_timer(delta, format_str):
    if delta.total_seconds() < 0:
        negative = True
        delta = abs(delta)
    else:
        negative = False

    hours, remainder = divmod(delta.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)

    return format_str.format(
        '-' if negative else '',
        int(hours),
        int(minutes),
        int(seconds),
        min(round(delta.microseconds / 100000), 9),
    )


def timer_str(delta, deciseconds=True):
    if deciseconds:
        return _format_timer(delta, '{}{:01}:{:02}:{:02}.{}')
    return _format_timer(delta, '{}{:01}:{:02}:{:02}')


def timer_html(delta, deciseconds=True):
    if deciseconds:
        return _format_timer(delta, '{}{:01}:{:02}:{:02}<small>.{}</small>')
    return _format_timer(delta, '{}{:01}:{:02}:{:02}')


def twitch_auth_url(request):
    return 'https://id.twitch.tv/oauth2/authorize?' + urlencode({
        'client_id': settings.TWITCH_CLIENT_ID,
        'redirect_uri': settings.RT_SITE_URI + reverse('twitch_auth'),
        'response_type': 'code',
        'scope': '',
        'force_verify': 'true',
        'state': request.META.get('CSRF_COOKIE'),
    })
