import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from ... import models
from ...utils import generate_race_slug

category_names = [
    ('Cadence of Hyrule: Crypt of the NecroDancer Featuring The Legend of Zelda', 'CoH', 'coh'),
    ('Mario Kart 8', 'MK 8', 'mk8'),
    ('The Binding of Isaac', 'BoI', 'tboi'),
    ('The Legend of Zelda: A Link to the Past', 'ALttP', 'alttp'),
    ('The Legend of Zelda: A Link to the Past Randomizer', 'ALttPR', 'alttpr'),
    ('The Legend of Zelda: Majora\'s Mask Randomizer', 'MMR', 'mmr'),
    ('The Legend of Zelda: Ocarina of Time', 'OoT', 'oot'),
    ('The Legend of Zelda: Ocarina of Time Randomizer', 'OoTR', 'ootr'),
    ('Super Mario 64', 'SM64', 'sm64'),
    ('Super Mario Sunshine', 'SMS', 'sms'),
    ('Super Metroid', 'SM', 'sm'),
]
goal_names = [
    'any%',
    '100%',
    '16 stars',
    '70 stars',
    'All dungeons',
    'All medallions',
    'Beat the game',
]
user_names = [
    'Banjo & Kazooie',
    'Bayonetta',
    'Bowser',
    'Bowser Jr.',
    'Captain Falcon',
    'Charizard',
    'Chrom',
    'Cloud',
    'Corrin',
    'Daisy',
    'Dark Pit',
    'Dark Samus',
    'Diddy Kong',
    'Donkey Kong',
    'Dr. Mario',
    'Duck Hunt',
    'Falco',
    'Fox',
    'Ganondorf',
    'Greninja',
    'Hero',
    'Ice Climbers',
    'Ike',
    'Incineroar',
    'Inkling',
    'Isabelle',
    'Ivysaur',
    'Jigglypuff',
    'Joker',
    'Ken',
    'King Dedede',
    'King K. Rool',
    'Kirby',
    'Link',
    'Little Mac',
    'Lucario',
    'Lucas',
    'Lucina',
    'Luigi',
    'Mario',
    'Marth',
    'Mega Man',
    'Meta Knight',
    'Mewtwo',
    'Mii Brawler',
    'Mii Swordfighter',
    'Mii Gunner',
    'Mr. Game & Watch',
    'Ness',
    'Olimar',
    'Pac-Man',
    'Palutena',
    'Peach',
    'Pichu',
    'Pikachu',
    'Piranha Plant',
    'Pit',
    'Richter',
    'Ridley',
    'R.O.B.',
    'Robin',
    'Rosalina & Luma',
    'Roy',
    'Ryu',
    'Samus',
    'Sheik',
    'Shulk',
    'Simon',
    'Snake',
    'Sonic',
    'Squirtle',
    'Terry',
    'Toon Link',
    'Villager',
    'Wario',
    'Wii Fit Trainer',
    'Wolf',
    'Yoshi',
    'Young Link',
    'Zelda',
    'Zero Suit Samus',
]


class Command(BaseCommand):
    @transaction.atomic
    def handle(self, *args, **options):
        users = []
        for name in user_names:
            users.append(models.User.objects.create_user(
                email=slugify(name) + '@racetime.gg',
                password='pass',
                name=name,
            ))

        for name, short_name, slug in category_names:
            cat = models.Category.objects.create(
                name=name,
                short_name=short_name,
                slug=slug,
                owner=random.choice(users),
            )
            cat.moderators.add(*random.sample(users, random.randint(0, 3)))

            goals = []
            for goal_name in random.sample(goal_names, random.randint(1, 3)):
                goals.append(models.Goal.objects.create(
                    category=cat,
                    name=goal_name,
                ))

            continue
            for i in range(random.randrange(0, 10)):
                goal = random.choice([None] + goals)
                custom_goal = None if goal else 'Test custom goal'
                state = random.choice(models.RaceStates.all).value

                opened_at = timezone.now() - timedelta(seconds=random.randint(600, 3600))
                started_at = None
                ended_at = None

                if state in (models.RaceStates.in_progress, models.RaceStates.finished):
                    started_at = opened_at + timedelta(seconds=random.randint(100, 200))
                    if state == models.RaceStates.finished:
                        ended_at = started_at + timedelta(seconds=random.randint(100, 200))

                race = models.Race.objects.create(
                    category=cat,
                    goal=goal,
                    custom_goal=custom_goal,
                    info='Test race information' if random.randint(0, 1) == 0 else None,
                    slug=generate_race_slug(),
                    state=state,
                    opened_by=random.choice(users),
                    opened_at=opened_at,
                    started_at=started_at,
                    ended_at=ended_at,
                )

                for user in random.sample(users, random.randint(2, 10)):
                    models.Entrant.objects.create(
                        user=user,
                        race=race,
                        state=random.choice(models.EntrantStates.all).value,
                        ready=random.choice([True, False]),
                        dnf=random.choice([True, False]),
                        dq=random.choice([True, False]),
                    )
