import colorsys
import json
import random
from collections import OrderedDict
from datetime import datetime
from urllib.parse import urlencode

import requests
from channels_redis.core import RedisChannelLayer as BaseRedisChannelLayer
from django.apps import apps
from django.conf import settings
from django.core.mail import send_mail
from django.core.serializers.json import DjangoJSONEncoder
from django.db.transaction import atomic
from django.template.loader import render_to_string
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.utils.module_loading import import_string
from hashids import Hashids

__all__ = [
    'RedisChannelLayer',
    'SafeException',
    'ShieldedUser',
    'SyncError',
    'chunkify',
    'delete_user',
    'determine_ip',
    'exception_to_msglist',
    'generate_race_slug',
    'generate_team_name',
    'get_action_button',
    'get_chat_history',
    'get_hashids',
    'notice_exception',
    'patreon_auth_url',
    'patreon_update_memberships',
    'timer_html',
    'timer_str',
    'twitch_auth_url',
]

slug_adjectives = [
    'adequate',
    'agreeable',
    'amazing',
    'amused',
    'awesome',
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
    'cold',
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
    'flying',
    'foolish',
    'fortunate',
    'frantic',
    'fried',
    'funky',
    'gentle',
    'gnarly',
    'good',
    'golden',
    'gorgeous',
    'graceful',
    'grumpy',
    'helpful',
    'hot',
    'hungry',
    'hyper',
    'innocent',
    'intrepid',
    'invincible',
    'jammy',
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
    'messy',
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
    'skyward',
    'sleepy',
    'smart',
    'smelly',
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
    'klonoa',
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
    'medli',
    'megaman',
    'meowth',
    'meta',
    'metroid',
    'mewtwo',
    'midna',
    'mips',
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
    'shantae',
    'shantotto',
    'shiva',
    'shulk',
    'sidon',
    'sim',
    'simon',
    'skip',
    'skipskip',
    'slime',
    'slowpoke',
    'snake',
    'snorlax',
    'sonic',
    'sourpls',
    'spaceman',
    'split',
    'spyro',
    'squirtle',
    'stanley',
    'star',
    'stardrop',
    'starfox',
    'subpixel',
    'sun',
    'taco',
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
    'trip',
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
    'alliance',
    'battletoads',
    'bosses',
    'brigade',
    'buccaneers',
    'bunch',
    'cactuars',
    'charmers',
    'checkpoints',
    'chickens',
    'chocobos',
    'clippers',
    'citizens',
    'cohort',
    'company',
    'contingent',
    'crewmates',
    'dancers',
    'detectives',
    'dodgers',
    'dreamers',
    'gamers',
    'gang',
    'geniuses',
    'glitchers',
    'guards',
    'hatters',
    'heroes',
    'hotdogs',
    'hoverers',
    'inklings',
    'kerbals',
    'kids',
    'knights',
    'legends',
    'lumas',
    'meeple',
    'moogles',
    'nachos',
    'nerds',
    'party',
    'pikmin',
    'placeholders',
    'platoon',
    'poggers',
    'polygons',
    'raiders',
    'resetters',
    'roadies',
    'runners',
    'sentinels',
    'skippers',
    'souls',
    'spacers',
    'spelunkers',
    'splits',
    'squad',
    'swabbies',
    'team',
    'tooltips',
    'trainers',
    'tricksters',
    'trolls',
    'vikings',
    'villagers',
    'yoshis',
    'zeroes',
    'zoomers',
]

shielded_forenames = [
    'Agent',
    'Arthur',
    'Athena',
    'Banjo',
    'Baron',
    'Barry',
    'Captain',
    'Cerberus',
    'Cloud',
    'Disco',
    'Doctor',
    'Donkey',
    'Falco',
    'Fox',
    'Fuzzy',
    'Ganondorf',
    'Hythlodaeus',
    'Leroy',
    'Lonk',
    'M.',
    'Marco',
    'Miles',
    'Montblanc',
    'Obi-Wan',
    'Phoenix',
    'Professor',
    'Reggie',
    'Resident',
    'Samus',
    'Samwise',
    'Skelly',
    'Solid',
    'Sonic',
    'Spartacus',
    'Tifa',
    'Zagreus',
]
shielded_surnames = [
    '& Knuckles',
    ', Attorney-at-law',
    ', Ladder Technician (BSc)',
    '-Kazooie',
    'Aran',
    'Bomberman',
    'Crackers',
    'Dragmire',
    'E. Gadd',
    'Edgeworth',
    'Eggman',
    'Falcon',
    'Jenkins',
    'Kenobi',
    'Kong',
    'Layton',
    'LikeandSubscribe',
    'Lockheart',
    'Lombardi',
    'M.D., Esq.',
    'McCloud',
    'Morgan',
    'Pickles',
    'Polo',
    'Prower',
    'Rasmodius',
    'Shepard',
    'Snake',
    'Spartacus',
    'Strife',
    'Von Rosenburg',
    'Wright',
    'from Pennsylvania',
    'of Dalmasca',
    'of Ronka',
    'the Brave',
    'the Hedgehog',
    'the Numpty',
    'the Third',
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


class ShieldedUser:
    active = True
    is_shielded = True
    pronouns = None
    use_discriminator = False

    def __init__(self, race, entrant_id):
        seeded_random = random.Random(f'r{race.id}e{entrant_id}')
        forename = seeded_random.choice(shielded_forenames)
        surname = seeded_random.choice(shielded_surnames)
        self.name = ''.join([
            forename, ' ' if not surname.startswith((',', '-')) else '', surname
        ])

        h, s, l = seeded_random.random(), 0.5 + seeded_random.random() / 2.0, 0.4 + seeded_random.random() / 5.0
        rgb = [int(256 * i) for i in colorsys.hls_to_rgb(h, l, s)]
        self.colour = 'rgb(' + ','.join([str(x) for x in rgb]) + ')'

        self.race = race

    @property
    def hashid(self):
        return get_hashids(self.__class__).encode(self.name, self.race.id)

    def api_dict_summary(self, category=None, race=None):
        return {
            'id': self.hashid,
            'full_name': self.name,
            'name': self.name,
            'discriminator': None,
            'url': None,
            'avatar': None,
            'pronouns': None,
            'flair': '',
            'twitch_name': None,
            'twitch_display_name': None,
            'twitch_channel': None,
            'can_moderate': False,
        }

    def __str__(self):
        return self.name


class SafeException(Exception):
    """
    Used to indicate an exception whose message is safe to display to end-users.
    """
    pass

class SyncError(SafeException):
    """
    Used to indicate an exception caused by a state mismatch between the user and the server.
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


def delete_user(request, user, protect=True):
    if protect and (user.is_system or user.is_superuser or user.is_staff):
        raise Exception('Cannot delete protected user.')
    if user.active_race_entrant:
        raise Exception('User is currently racing.')

    user_email = user.email
    email_context = {
        'home_url': settings.RT_SITE_URI + reverse('home'),
        'name': user.name,
    }

    with atomic():
        # Delete comments
        Entrant = apps.get_model('racetime', 'Entrant')
        Entrant.objects.filter(user=user).update(comment=None)

        # Anonymise system messages that mention the user
        MessageLink = apps.get_model('racetime', 'MessageLink')
        for message_link in MessageLink.objects.filter(user=user).select_related('message'):
            message_link.message.message = message_link.anonymised_message
            message_link.message.save()

        # Anonymise older system messages
        MESSAGE_LINK_MIGRATION = datetime(2025, 3, 25, tzinfo=timezone.utc)
        Message = apps.get_model('racetime', 'Message')
        UserLog = apps.get_model('racetime', 'UserLog')

        name_map = OrderedDict()
        for user_log in UserLog.objects.filter(
            user=user,
            changed_at__lte=MESSAGE_LINK_MIGRATION,
        ).order_by('changed_at'):
            name_map[user_log.changed_at] = user_log.user_str
        name_map[MESSAGE_LINK_MIGRATION] = str(user)

        date_from = None
        for date_to, name in name_map.items():
            messages = Message.objects.filter(
                user=None,
                bot=None,
                posted_at__lte=date_to,
                message__contains=name,
            )
            if date_from:
                messages = messages.filter(posted_at__gte=date_from)
            for message in messages:
                message.message = message.message.replace(name, '(deleted user)')
                message.save()
            date_from = date_to

        user.delete()

    send_mail(
        subject=render_to_string('racetime/email/delete_account_subject.txt', email_context, request),
        message=render_to_string('racetime/email/delete_account_email.txt', email_context, request),
        html_message=render_to_string('racetime/email/delete_account_email.html', email_context, request),
        from_email=settings.EMAIL_FROM,
        recipient_list=[user_email],
    )


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
        'partition': {'label': 'Ready', 'class': ''},
        'not_live': {'label': 'Not live', 'class': ''},
        'unready': {'label': 'Not ready', 'class': ''},
        'leave': {'label': 'Quit', 'class': ''},
        'add_comment': {'label': 'Add comment…', 'class': ''},
        'change_comment': {'label': 'Change comment…', 'class': ''},
        'done': {'label': 'Done', 'class': ''},
        'undone': {'label': 'Undo finish', 'class': 'dangerous'},
        'forfeit': {'label': 'Forfeit', 'class': 'dangerous'},
        'unforfeit': {'label': 'Undo forfeit', 'class': 'dangerous'},
    }
    button = race_action_buttons.get(action)
    if not button:
        raise KeyError
    try:
        url = reverse(action, kwargs={'category': category_slug, 'race': race_slug})
    except NoReverseMatch:
        url = None
    return action, url, button.get('label'), button.get('class')


def get_chat_history(race_id, user=None, last_message_id=None):
    if not race_id:
        return OrderedDict()

    Message = apps.get_model('racetime', 'Message')

    messages = Message.objects.filter(
        race_id=race_id,
        deleted=False,
    ).order_by('posted_at')

    if last_message_id:
        messages = messages.filter(id__gt=last_message_id)

    pin_ids = []
    message_ids = []
    for msg_id, user_id, direct_to_id, pinned in messages.values_list('id', 'user_id', 'direct_to_id', 'pinned'):
        if not direct_to_id:
            if pinned:
                pin_ids.append(msg_id)
            else:
                message_ids.append(msg_id)
        elif user and user.is_authenticated and user.id in (user_id, direct_to_id):
            message_ids.append(msg_id)

    msgs_to_query = [*pin_ids, *message_ids[-100:]]

    return OrderedDict(
        (message.hashid, message.as_dict)
        for message in Message.objects.filter(
            id__in=msgs_to_query,
        ).order_by('pinned', 'posted_at').prefetch_related('user', 'bot')
    )


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


def patreon_auth_url(request):
    return 'https://www.patreon.com/oauth2/authorize?' + urlencode({
        'client_id': settings.PATREON_CLIENT_ID,
        'redirect_uri': settings.RT_SITE_URI + reverse('patreon_auth'),
        'response_type': 'code',
        'scope': 'identity',
        'state': request.META.get('CSRF_COOKIE'),
    })


def patreon_update_memberships(**user_filter):
    try:
        data = requests.get(
            f'https://www.patreon.com/api/oauth2/v2/campaigns/{settings.PATREON_CAMPAIGN_ID}/members',
            {'include': 'user', 'page[count]': 1000},
            headers={'Authorization': f'Bearer {settings.PATREON_ACCESS_TOKEN}'},
            timeout=3,
        ).json().get('data')
    except requests.RequestException:
        return 0, 0

    patreon_ids = []
    for user in data:
        user_id = user.get('relationships').get('user').get('data').get('id')
        if user_id:
            patreon_ids.append(user_id)

    User = apps.get_model('racetime', 'User')
    user_qs = User.objects.filter(**user_filter)
    added = user_qs.filter(is_supporter=False, patreon_id__in=patreon_ids).update(is_supporter=True)
    removed = user_qs.filter(is_supporter=True).exclude(patreon_id__in=patreon_ids).update(is_supporter=False)

    return added, removed


def timer_html(delta, deciseconds=True):
    if deciseconds:
        return _format_timer(delta, '{}{:01}:{:02}:{:02}<small>.{}</small>')
    return _format_timer(delta, '{}{:01}:{:02}:{:02}')


def timer_str(delta, deciseconds=True):
    if deciseconds:
        return _format_timer(delta, '{}{:01}:{:02}:{:02}.{}')
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
