import random

from django.conf import settings
from django.utils.module_loading import import_string
from hashids import Hashids

__all__ = [
    'SafeException',
    'generate_race_slug',
    'get_hashids',
    'timer_html',
    'timer_str',
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


class SafeException(Exception):
    """
    Used to indicate an exception whose message is safe to display to end-users.
    """
    pass


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
    return Hashids(salt=str(cls) + settings.SECRET_KEY, min_length=32)


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
