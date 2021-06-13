import json
import random
from urllib.parse import urlencode
from math import floor
from datetime import timedelta

from channels_redis.core import RedisChannelLayer as BaseRedisChannelLayer
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse, NoReverseMatch
from django.utils.module_loading import import_string
from hashids import Hashids

__all__ = [
    'RedisChannelLayer',
    'SafeException',
    'chunkify',
    'determine_ip',
    'exception_to_msglist',
    'generate_race_slug',
    'generate_team_name',
    'get_action_button',
    'get_hashids',
    'notice_exception',
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
    'daring',
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
    'fearless',
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

team_names = [
    'aces',
    'adventurers',
    'all-stars',
    'battletoads',
    'bosses',
    'brigade',
    'buccaneers',
    'bunch',
    'cactuars',
    'charmers',
    'checkpoints',
    'chocobos',
    'citizens',
    'cohort',
    'company',
    'contingent',
    'crewmates',
    'detectives',
    'dreamers',
    'gamers',
    'gang',
    'geniuses',
    'glitchers',
    'heroes',
    'inklings',
    'kerbals',
    'kids',
    'legends',
    'lumas',
    'meeple',
    'moogles',
    'nachos',
    'nerds',
    'party',
    'pikmin',
    'platoon',
    'polygons',
    'raiders',
    'resetters',
    'roadies',
    'runners',
    'sentinels',
    'spacers',
    'spelunkers',
    'splits',
    'squad',
    'swabbies',
    'team',
    'tooltips',
    'trainers',
    'tricksters',
    'vikings',
    'villagers',
    'yoshis',
    'zeroes',
    'zoomers',
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


def chunkify(items, size=100):
    """
    Generator that splits an iterable into chunks of given size.
    """
    n = 0
    while True:
        chunk = items[n:n + size]
        if not chunk:
            break
        yield chunk
        n += size


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


def generate_team_name():
    name = ('The %s %s' % (
        random.choice(slug_adjectives),
        random.choice(team_names),
    )).title()
    return name


def get_action_button(action, race_slug, category_slug):
    race_action_buttons = {
        'join': {'label': 'Join', 'class': ''},
        'request_invite': {'label': 'Request to join', 'class': ''},
        'cancel_invite': {'label': 'Withdraw join request', 'class': ''},
        'accept_invite': {'label': 'Accept invite', 'class': ''},
        'decline_invite': {'label': 'Decline invite', 'class': ''},
        'set_team': {'label': 'Choose team…', 'class': ''},
        'ready': {'label': 'Ready', 'class': ''},
        'not_live': {'label': 'Not live', 'class': ''},
        'unready': {'label': 'Not ready', 'class': ''},
        'leave': {'label': 'Quit', 'class': ''},
        'add_comment': {'label': 'Add comment…', 'class': ''},
        'change_comment': {'label': 'Change comment…', 'class': ''},
        'done': {'label': 'Done', 'class': ''},
        'undone': {'label': 'Undo finish', 'class': 'dangerous'},
        'forfeit': {'label': 'Forfeit', 'class': 'dangerous'},
        'unforfeit': {'label': 'Undo forfeit', 'class': ''},
    }
    button = race_action_buttons.get(action)
    if not button:
        raise KeyError
    try:
        url = reverse(action, kwargs={'category': category_slug, 'race': race_slug})
    except NoReverseMatch:
        url = None
    return action, url, button.get('label'), button.get('class')


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


def _round_down_to_second(delta):
    rounded_seconds = floor(delta.total_seconds() / 1000) * 1000
    return timedelta(seconds=rounded_seconds)


def timer_html(delta, deciseconds=True):
    if deciseconds:
        return _format_timer(delta, '{}{:01}:{:02}:{:02}<small>.{}</small>')
    return _format_timer(_round_down_to_second(delta), '{}{:01}:{:02}:{:02}')


def timer_str(delta, deciseconds=True):
    if deciseconds:
        return _format_timer(delta, '{}{:01}:{:02}:{:02}.{}')
    return _format_timer(_round_down_to_second(delta), '{}{:01}:{:02}:{:02}')


def twitch_auth_url(request):
    return 'https://id.twitch.tv/oauth2/authorize?' + urlencode({
        'client_id': settings.TWITCH_CLIENT_ID,
        'redirect_uri': settings.RT_SITE_URI + reverse('twitch_auth'),
        'response_type': 'code',
        'scope': '',
        'force_verify': 'true',
        'state': request.META.get('CSRF_COOKIE'),
    })
