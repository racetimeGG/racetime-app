from django.urls import path, include

from . import views

urlpatterns = [
    path('account', views.EditAccount.as_view(), name='edit_account'),
    path('account/login', views.Login.as_view(), name='login'),
    path('account/logout', views.Logout.as_view(), name='logout'),
    path('account/create', views.CreateAccount.as_view(), name='create_account'),
    path('account/twitch_auth', views.TwitchAuth.as_view(), name='twitch_auth'),
    path('account/derp', views.PasswordResetView.as_view(), name='password_reset'),
    path('account/derp/done', views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('account/reset/<uidb64>/<token>', views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('account/reset/complete', views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),

    path('', views.Home.as_view(), name='home'),
    path('request_category', views.RequestCategory.as_view(), name='request_category'),

    path('<str:category>', views.Category.as_view(), name='category'),
    path('<str:category>/startrace', views.CreateRace.as_view(), name='create_race'),
    path('<str:category>/edit', views.EditCategory.as_view(), name='edit_category'),

    path('<str:category>/<str:race>', views.Race.as_view(), name='race'),

    path('<str:category>/<str:race>/', include([
        path('chat', views.RaceChat.as_view(), name='race_chat'),
        path('data', views.RaceData.as_view(), name='race_data'),
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

            path('accept_request/<str:entrant>', views.AcceptRequest.as_view(), name='accept_request'),
            path('force_unready/<str:entrant>', views.ForceUnready.as_view(), name='force_unready'),
            path('override_stream/<str:entrant>', views.OverrideStream.as_view(), name='override_stream'),
            path('remove/<str:entrant>', views.Remove.as_view(), name='remove'),
            path('disqualify/<str:entrant>', views.Disqualify.as_view(), name='disqualify'),
            path('undisqualify/<str:entrant>', views.Undisqualify.as_view(), name='undisqualify'),
            path('add_monitor/<str:entrant>', views.AddMonitor.as_view(), name='add_monitor'),
            path('remove_monitor/<str:entrant>', views.RemoveMonitor.as_view(), name='remove_monitor'),
        ])),
    ])),
]
