from django.conf.urls import url
from django.urls import path, include
from oauth2_provider import views as oauth2_views
from rest_framework_simplejwt import views as jwt_views

from . import views
from .views import api as api_views

urlpatterns = [
    path('account', views.EditAccount.as_view(), name='edit_account'),
    path('account/', include([
        path('auth', views.LoginRegister.as_view(), name='login_or_register'),
        path('connections', views.EditAccountConnections.as_view(), name='edit_account_connections'),
        path('security', views.EditAccountSecurity.as_view(), name='edit_account_security'),
        path('standing', views.AccountStanding.as_view(), name='account_standing'),
        path('login', views.Login.as_view(), name='login'),
        path('logout', views.Logout.as_view(), name='logout'),
        path('create', views.CreateAccount.as_view(), name='create_account'),
        path('twitch_auth', views.TwitchAuth.as_view(), name='twitch_auth'),
        path('twitch_disconnect', views.TwitchDisconnect.as_view(), name='twitch_disconnect'),
        path('derp', views.PasswordResetView.as_view(), name='password_reset'),
        path('derp/done', views.PasswordResetDoneView.as_view(), name='password_reset_done'),
        path('reset/<uidb64>/<token>', views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
        path('reset/complete', views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    ])),

    path('o/', include([
        path('authorize', oauth2_views.AuthorizationView.as_view(), name='oauth2_authorize'),
        path('token', oauth2_views.TokenView.as_view(), name='oauth2_token'),
        path('revoke_token', oauth2_views.RevokeTokenView.as_view(), name='oauth2_revoke'),

        path('delete/<pk>', views.OAuthDeleteToken.as_view(), name='oauth2_delete'),
        path('done', views.OAuthDone.as_view(), name='oauth2_authorize_done'),
        path('userinfo', views.OAuthUserInfo.as_view(), name='oauth2_userinfo'),
        path('<str:category>/startrace', views.OAuthCreateRace.as_view(), name='oauth2_create_race'),
        path('<str:category>/<str:race>/edit', views.OAuthEditRace.as_view(), name='oauth2_edit_race'),
    ])),

    url(r'^openid/', include('oidc_provider.urls', namespace='oidc_provider')),

    path('api/', include([
        path('categories', api_views.CategoryViewSet.as_view(
            {'get': 'list', 'post': 'create'}),
            name="api_category_list",
        ),
        path('category/<str:slug>', api_views.CategoryViewSet.as_view({
            'get': 'retrieve',
            'put': 'update',
            'patch': 'partial_update',
            'delete': 'destroy'
        }), name="api_category_detail"),
    ])),

    path('autocomplete/', include([
        path('user', views.AutocompleteUser.as_view(), name='autocomplete_user'),
    ])),

    path('', views.Home.as_view(), name='home'),
    path('request_category', views.RequestCategory.as_view(), name='request_category'),
    path('races/data', views.RaceListData.as_view(), name='race_list_data'),
    path('user/search', views.AutocompleteUser.as_view(), name='autocomplete_user'),
    path('user/<str:user>', views.ViewProfile.as_view(), name='view_profile'),
    path('user/<str:user>/', include([
        path('data', views.UserProfileData.as_view(), name='user_profile_data'),
        path('races/data', views.UserRaceData.as_view(), name='user_race_list_data'),
    ])),

    path('<str:category>', views.Category.as_view(), name='category'),
    path('<str:category>/', include([
        path('data', views.CategoryData.as_view(), name='category_data'),
        path('races/data', views.CategoryRaceData.as_view(), name='category_race_list_data'),
        path('manage/', include([
            path('edit', views.EditCategory.as_view(), name='edit_category'),
            path('deactivate', views.DeactivateCategory.as_view(), name='category_deactivate'),
            path('reactivate', views.ReactivateCategory.as_view(), name='category_reactivate'),
            path('archive', views.ArchiveCategory.as_view(), name='category_archive'),
            path('restore', views.RestoreCategory.as_view(), name='category_restore'),
            path('goals', views.GoalList.as_view(), name='category_goals'),
            path('goals/new', views.CreateGoal.as_view(), name='new_category_goal'),
            path('goals/<str:goal>/edit', views.EditGoal.as_view(), name='edit_category_goal'),
            path('goals/<str:goal>/deactivate', views.DeactivateGoal.as_view(), name='deactivate_category_goal'),
            path('goals/<str:goal>/reactivate', views.ReactivateGoal.as_view(), name='reactivate_category_goal'),
            path('bots', views.BotList.as_view(), name='category_bots'),
            path('bots/new', views.CreateBot.as_view(), name='new_category_bot'),
            path('bots/<str:bot>/deactivate', views.DeactivateBot.as_view(), name='deactivate_category_bot'),
            path('bots/<str:bot>/reactivate', views.ReactivateBot.as_view(), name='reactivate_category_bot'),
            path('mods', views.CategoryModerators.as_view(), name='category_mods'),
            path('mods/add_owner', views.AddOwner.as_view(), name='category_owners_add'),
            path('mods/remove_owner', views.RemoveOwner.as_view(), name='category_owners_remove'),
            path('mods/add_moderator', views.AddModerator.as_view(), name='category_mods_add'),
            path('mods/remove_moderator', views.RemoveModerator.as_view(), name='category_mods_remove'),
            path('log', views.CategoryAudit.as_view(), name='category_audit_log'),
        ])),
        path('leaderboards', views.CategoryLeaderboards.as_view(), name='leaderboards'),
        path('leaderboards/data', views.CategoryLeaderboardsData.as_view(), name='leaderboards_data'),
        path('startrace', views.CreateRace.as_view(), name='create_race'),
        path('star', views.FavouriteCategory.as_view(), name='star'),
        path('unstar', views.UnfavouriteCategory.as_view(), name='unstar'),
    ])),

    path('<str:category>/<str:race>', views.Race.as_view(), name='race'),
    path('<str:category>/<str:race>/', include([
        path('csv', views.RaceCSV.as_view(), name='race_csv'),
        path('data', views.RaceData.as_view(), name='race_data'),
        path('mini', views.RaceMini.as_view(), name='race_mini'),
        path('log', views.RaceChatLog.as_view(), name='race_log'),
        path('renders', views.RaceRenders.as_view(), name='race_renders'),
        path('spectate', views.RaceSpectate.as_view(), name='race_spectate'),

        path('message', views.Message.as_view(), name='message'),
        path('join', views.Join.as_view(), name='join'),
        path('leave', views.Leave.as_view(), name='leave'),
        path('request_invite', views.RequestInvite.as_view(), name='request_invite'),
        path('cancel_invite', views.CancelInvite.as_view(), name='cancel_invite'),
        path('accept_invite', views.AcceptInvite.as_view(), name='accept_invite'),
        path('decline_invite', views.DeclineInvite.as_view(), name='decline_invite'),
        path('ready', views.Ready.as_view(), name='ready'),
        path('unready', views.Unready.as_view(), name='unready'),
        path('done', views.Done.as_view(), name='done'),
        path('undone', views.Undone.as_view(), name='undone'),
        path('forfeit', views.Forfeit.as_view(), name='forfeit'),
        path('unforfeit', views.Unforfeit.as_view(), name='unforfeit'),
        path('add_comment', views.AddComment.as_view(), name='add_comment'),
        path('add_comment', views.AddComment.as_view(), name='change_comment'),

        path('monitor/', include([
            path('edit', views.EditRace.as_view(), name='edit_race'),
            path('open', views.MakeOpen.as_view(), name='make_open'),
            path('invitational', views.MakeInvitational.as_view(), name='make_invitational'),
            path('begin', views.BeginRace.as_view(), name='begin_race'),
            path('cancel', views.CancelRace.as_view(), name='cancel_race'),
            path('invite', views.InviteToRace.as_view(), name='invite_to_race'),
            path('record', views.RecordRace.as_view(), name='record_race'),
            path('unrecord', views.UnrecordRace.as_view(), name='unrecord_race'),
            path('rematch', views.Rematch.as_view(), name='rematch'),
            path('delete/<str:message>', views.RaceChatDelete.as_view(), name='chat_delete'),
            path('purge/<str:message>', views.RaceChatPurge.as_view(), name='chat_purge'),

            path('<str:entrant>/', include([
                path('accept_request', views.AcceptRequest.as_view(), name='accept_request'),
                path('force_unready', views.ForceUnready.as_view(), name='force_unready'),
                path('override_stream', views.OverrideStream.as_view(), name='override_stream'),
                path('remove', views.Remove.as_view(), name='remove'),
                path('disqualify', views.Disqualify.as_view(), name='disqualify'),
                path('undisqualify', views.Undisqualify.as_view(), name='undisqualify'),
                path('add_monitor', views.AddMonitor.as_view(), name='add_monitor'),
                path('remove_monitor', views.RemoveMonitor.as_view(), name='remove_monitor'),
            ])),
        ])),
    ])),
]
