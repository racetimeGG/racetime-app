import logging
import os
from datetime import timedelta
from itertools import chain
from time import sleep

import requests
from django.conf import settings
from django.db.models import F
from django.utils import timezone

from . import models
from .utils import chunkify, notice_exception


class RaceBot:
    logger = logging.getLogger('racebot')
    pid = None
    last_adoption = None
    last_twitch_refresh = None
    twitch_token = None
    twitch_token_refresh = None
    races = []
    queryset = models.Race.objects.filter(
        state__in=[
            models.RaceStates.open.value,
            models.RaceStates.invitational.value,
            models.RaceStates.pending.value,
            models.RaceStates.in_progress.value,
        ],
    )

    def __init__(self, process_id):
        self.pid = process_id

    def handle(self):
        if (
            not self.twitch_token
            or not self.twitch_token_refresh
            or self.twitch_token_refresh < timezone.now()
        ):
            self.update_twitch_token()

        for race in self.races:
            if timezone.now() - race['last_refresh'] > timedelta(milliseconds=100):
                race['last_refresh'] = timezone.now()
                race['object'].refresh_from_db()
                self.handle_race(race)

        if not self.last_adoption or timezone.now() - self.last_adoption > timedelta(seconds=10):
            self.adopt_race()
            self.unorphan_races()
            self.last_adoption = timezone.now()

        if not self.last_twitch_refresh or timezone.now() - self.last_twitch_refresh > timedelta(seconds=10):
            self.logger.debug('[Twitch] Refreshing stream statuses.')
            self.update_live_status()
            self.last_twitch_refresh = timezone.now()

        sleep(0.01)

    def adopt_race(self):
        """
        Search for any orphan races this process can adopt.

        The first orphaned race found will be adopted by setting the bot_pid
        field on it to this bot's PID.
        """
        self.logger.debug('[Bot] Searching for races to adopt.')

        race = self.queryset.filter(bot_pid=None).first()
        if race:
            race.bot_pid = self.pid
            race.save()
            self.races.append({
                'last_refresh': timezone.now(),
                'object': race,
                'cancel_warning_posted': False,
                'limit_warning_posted': False,
            })
            self.logger.info('[Bot] Adopted race %(race)s.' % {'race': race})

    def unorphan_races(self):
        """
        Search for active races whose bot process is no longer running, and
        clear their bot_pid value. This will allow these races to be picked up
        again by a working racebot process.
        """
        self.logger.debug('[Bot] Searching for orphaned races.')

        queryset = self.queryset.filter(bot_pid__isnull=False)
        queryset = queryset.exclude(bot_pid=self.pid)
        queryset = queryset.values_list('bot_pid', flat=True)
        queryset = queryset.distinct()

        dead = []
        for pid in queryset.all():
            try:
                os.kill(pid, 0)
            except OSError:
                dead.append(pid)
            except SystemError:
                pass

        if dead:
            count = self.queryset.filter(bot_pid__in=dead).update(bot_pid=None)
            self.logger.warning(
                '[Bot] Found %(count)d orphaned race(s) from bot PID(s): %(pids)s'
                % {'count': count, 'pids': ','.join(str(pid) for pid in dead)}
            )
        else:
            self.logger.debug('[Bot] No orphaned races found. Yay!')

    def handle_race(self, race):
        """
        Handle all time-depenedent actions needed on the race object.
        """
        if race['object'].is_preparing:
            self.handle_open_race(race)
        elif race['object'].is_pending:
            self.handle_pending_race(race)
        elif race['object'].is_in_progress:
            self.handle_in_progress_race(race)
        else:
            race['object'].bot_pid = None
            race['object'].save()
            self.races.remove(race)
            self.logger.info(
                '[Race] %(race)s is complete.' % {'race': race['object']}
            )

    def handle_open_race(self, race):
        if len(race['object'].entrant_set.filter(
            state=models.EntrantStates.joined.value,
        )) < 2:
            self.check_open_time_limit_lowentrants(race)
        else:
            self.check_open_time_limit(race)
            self.check_readiness(race)

    def handle_pending_race(self, race):
        self.check_countdown(race)

    def handle_in_progress_race(self, race):
        self.check_time_limit(race)

    def check_countdown(self, race):
        time_to_start = timezone.now() - race['object'].started_at
        for s in chain([10], range(5, 0, -1)):
            scp = str(s) + '_countdown_posted'
            if time_to_start >= timedelta(seconds=-s) and scp not in race:
                race['object'].add_message(
                    str(s) + '…',
                    highlight=True,
                    broadcast=False,
                )
                race[scp] = True
        if time_to_start >= timedelta(0):
            race['object'].state = models.RaceStates.in_progress.value
            race['object'].version = F('version') + 1
            race['object'].save()
            race['object'].add_message(
                'The race has begun! Good luck and have fun.',
                highlight=True,
            )
            self.logger.info('[Race] Started %(race)s.' % {'race': race['object']})

    def check_readiness(self, race):
        """
        If all entrants in the race are ready, begin the race countdown.
        """
        if race['object'].num_unready == 0 and race['object'].auto_start:
            race['object'].begin()
            race['object'].add_message(
                'Everyone is ready. The race will begin in %(delta)d seconds!'
                % {'delta': race['object'].start_delay.seconds},
                highlight=True,
            )
            self.logger.info('[Race] Begun countdown for %(race)s.' % {'race': race['object']})

    def check_open_time_limit(self, race):
        open_for = timezone.now() - race['object'].opened_at
        if open_for >= race['object'].OPEN_TIME_LIMIT:
            race['object'].cancel()
            race['object'].add_message(
                'This race has been cancelled. Reason: dead race room.'
            )
            self.logger.info('[Race] Cancelled %(race)s (dead race room).' % {'race': race['object']})

    def check_open_time_limit_lowentrants(self, race):
        open_for = timezone.now() - race['object'].opened_at
        if open_for >= race['object'].OPEN_TIME_LIMIT_LOWENTRANTS:
            race['object'].cancel()
            race['object'].add_message(
                'This race has been cancelled. Reason: less than 2 '
                'entrants joined.'
            )
            self.logger.info('[Race] Cancelled %(race)s (<2 entrants).' % {'race': race['object']})
        elif (
            open_for >= (race['object'].OPEN_TIME_LIMIT_LOWENTRANTS - timedelta(minutes=5))
            and not race['cancel_warning_posted']
        ):
            race['object'].add_message(
                'Warning: this race will be automatically cancelled in 5 '
                'minutes unless at least two entrants join.',
                highlight=True,
            )
            race['cancel_warning_posted'] = True
            self.logger.info('[Race] Low entrant warning for %(race)s.' % {'race': race['object']})

    def check_time_limit(self, race):
        in_progress_for = timezone.now() - race['object'].started_at
        if in_progress_for >= race['object'].time_limit:
            race['object'].add_message(
                'This race has reached its time limit. All remaining entrants '
                'will now be expunged.'
            )
            race['object'].finish()
            self.logger.info('[Race] Race time limit exceeded for %(race)s.' % {'race': race['object']})
        elif (
            in_progress_for >= (race['object'].time_limit - timedelta(minutes=5))
            and not race['limit_warning_posted']
        ):
            race['object'].add_message(
                'Warning: this race will reach its time limit in 5 minutes. '
                'All remaining entrants will forfeit.',
                highlight=True,
            )
            race['limit_warning_posted'] = True
            self.logger.info('[Race] Race time limit warning for %(race)s.' % {'race': race['object']})

    def update_twitch_token(self):
        try:
            resp = requests.post('https://id.twitch.tv/oauth2/token', {
                'client_id': settings.TWITCH_CLIENT_ID,
                'client_secret': settings.TWITCH_CLIENT_SECRET,
                'grant_type': 'client_credentials',
            })
            if resp.status_code != 200:
                raise requests.RequestException
        except requests.RequestException as ex:
            notice_exception(ex)
            self.logger.error('[Twitch] Could not fetch access token!')
            self.logger.error(str(ex))
        else:
            data = resp.json()
            self.twitch_token = data.get('access_token')
            self.twitch_token_refresh = timezone.now() + timedelta(seconds=data.get('expires_in', 86400) - 3600)
            self.logger.debug('[Twitch] OAuth2 token obtained (expires %s).' % self.twitch_token_refresh)

    def update_live_status(self):
        if not self.races:
            self.logger.debug('[Twitch] No races to check.')
            return

        entrants = {}

        for entrant in models.Entrant.objects.filter(
            race__in=[race['object'] for race in self.races],
            user__twitch_id__isnull=False,
            state=models.EntrantStates.joined.value,
        ).annotate(twitch_id=F('user__twitch_id')):
            entrants[entrant.twitch_id] = entrant

        if not entrants:
            self.logger.debug('[Twitch] No entrants to check.')
            return

        entrants_to_update = []
        races_to_reload = []

        for chunk in chunkify(list(entrants.keys()), size=100):
            try:
                resp = requests.get('https://api.twitch.tv/helix/streams', params={
                    'first': 100,
                    'user_id': chunk,
                }, headers={
                    'Authorization': 'Bearer ' + self.twitch_token,
                    'Client-ID': settings.TWITCH_CLIENT_ID,
                })
                if resp.status_code != 200:
                    raise requests.RequestException
            except requests.RequestException as ex:
                notice_exception(ex)
                self.logger.error('[Twitch] API error occurred!')
                self.logger.error(str(ex))
            else:
                live_users = []
                twitch_names = {}
                for stream in resp.json().get('data', []):
                    if stream.get('user_id'):
                        user_id = int(stream['user_id'])
                        live_users.append(user_id)
                        if stream.get('user_name'):
                            twitch_names[user_id] = stream['user_name']

                for twitch_id in chunk:
                    entrant = entrants.get(twitch_id)
                    entrant_is_live = twitch_id in live_users
                    if entrant:
                        user = entrant.user
                        if entrant.stream_live != entrant_is_live:
                            entrant.stream_live = entrant_is_live
                            entrants_to_update.append(entrant)
                            if entrant.race not in races_to_reload:
                                races_to_reload.append(entrant.race)
                        if twitch_id in twitch_names and user.twitch_name != twitch_names[twitch_id]:
                            user.twitch_name = twitch_names[twitch_id]
                            user.save()
                            if entrant.race not in races_to_reload:
                                races_to_reload.append(entrant.race)
                            self.logger.info(
                                '[Twitch] Updated %(user)s twitch display name to %(twitch_name)s'
                                % {'user': user, 'twitch_name': user.twitch_name}
                            )

        if entrants_to_update:
            models.Entrant.objects.bulk_update(
                entrants_to_update,
                ['stream_live'],
            )
            self.logger.info(
                '[Twitch] Updated %(entrants)d entrant(s) in %(races)d race(s).'
                % {'entrants': len(entrants_to_update), 'races': len(races_to_reload)}
            )
        else:
            self.logger.debug('[Twitch] All stream info is up-to-date.')

        for race in races_to_reload:
            race.increment_version()
            race.broadcast_data()
