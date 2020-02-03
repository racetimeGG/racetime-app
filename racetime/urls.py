from django.urls import path, include

from . import views

urlpatterns = [
    path('account', views.EditAccount.as_view(), name='edit_account'),
    path('account/', include([
        path('login', views.Login.as_view(), name='login'),
        path('logout', views.Logout.as_view(), name='logout'),
        path('create', views.CreateAccount.as_view(), name='create_account'),
        path('twitch_auth', views.TwitchAuth.as_view(), name='twitch_auth'),
        path('derp', views.PasswordResetView.as_view(), name='password_reset'),
        path('derp/done', views.PasswordResetDoneView.as_view(), name='password_reset_done'),
        path('reset/<uidb64>/<token>', views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
        path('reset/complete', views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    ])),

    path('', views.Home.as_view(), name='home'),
    path('request_category', views.RequestCategory.as_view(), name='request_category'),
    path('user/<str:user>', views.ViewProfile.as_view(), name='view_profile'),

    path('o/userinfo', views.OAuthUserInfo.as_view(), name='oauth2_userinfo'),
    path('o/', include('oauth2_provider.urls', namespace='oauth2_provider')),

    path('<str:category>', views.Category.as_view(), name='category'),
    path('<str:category>/', include([
        path('data', views.CategoryData.as_view(), name='category_data'),
        path('edit', views.EditCategory.as_view(), name='edit_category'),
        path('leaderboards', views.CategoryLeaderboards.as_view(), name='leaderboards'),
        path('startrace', views.CreateRace.as_view(), name='create_race'),
    ])),

    path('<str:category>/<str:race>', views.Race.as_view(), name='race'),
    path('<str:category>/<str:race>/', include([
        path('data', views.RaceData.as_view(), name='race_data'),
        path('mini', views.RaceMini.as_view(), name='race_mini'),
        path('log', views.RaceChatLog.as_view(), name='race_log'),
        path('renders', views.RaceRenders.as_view(), name='race_renders'),

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

        path('monitor/', include([
            path('edit', views.EditRace.as_view(), name='edit_race'),
            path('begin', views.BeginRace.as_view(), name='begin_race'),
            path('cancel', views.CancelRace.as_view(), name='cancel_race'),
            path('invite', views.InviteToRace.as_view(), name='invite_to_race'),
            path('record', views.RecordRace.as_view(), name='record_race'),
            path('unrecord', views.UnrecordRace.as_view(), name='unrecord_race'),

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
