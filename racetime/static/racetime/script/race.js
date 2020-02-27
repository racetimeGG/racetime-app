function Race() {
    this.socketListeners = {
        close: this.onSocketClose.bind(this),
        error: this.onSocketError.bind(this),
        message: this.onSocketMessage.bind(this),
        open: this.onSocketOpen.bind(this)
    };
    this.messageIDs = [];

    try {
        this.vars = JSON.parse($('#race-vars').text());
        for (var i in this.vars.chat_history) {
            if (!this.vars.chat_history.hasOwnProperty(i)) continue;
            this.addMessage(this.vars.chat_history[i]);
        }
        this.open();
    } catch (e) {
        if ('notice_exception' in window) {
            window.notice_exception(e);
        } else {
            throw e;
        }
    }
}

Race.prototype.ajaxifyActionForm = function(form) {
    var self = this;
    $(form).ajaxForm({
        clearForm: true,
        beforeSubmit: function() {
            $('.race-action-form button').prop('disabled', true);
        },
        beforeSerialize: function($form) {
            if ($form.hasClass('add_comment')) {
                var comment = prompt('Enter a comment:');
                if (!comment) return false;
                var $input = $('<input type="hidden" name="comment">');
                $input.val(comment);
                $input.appendTo($form);
            }
        },
        error: self.onError.bind(self)
    });
};

Race.prototype.addMessage = function(message) {
    var self = this;

    if (self.messageIDs.indexOf(message.id) !== -1) {
        return true;
    }

    var $messages = $('.race-chat .messages');
    if ($messages.length) {
        $messages.append(self.createMessageItem(message));
        $messages[0].scrollTop = $messages[0].scrollHeight;
    }

    self.messageIDs.push(message.id);

    if (self.messageIDs.length > 100) {
        self.messageIDs.shift();
    }
    if ($messages.children().length > 100) {
        $messages.children().first().remove();
    }
};

Race.prototype.createMessageItem = function(message) {
    var date = new Date(message.posted_at);
    var timestamp = ('00' + date.getHours()).slice(-2) + ':' + ('00' + date.getMinutes()).slice(-2);

    var $li = $(
        '<li>'
        + '<span class="timestamp">' + timestamp + '</span>'
        + '<span class="message"></span>'
        + '</li>'
    );

    if (message.is_system) {
        $li.addClass('system');
    } else if (message.is_bot) {
        $li.addClass('bot');
        var $bot = $('<span class="name"></span>');
        $bot.text(message.bot);
        $bot.insertAfter($li.children('.timestamp'));
    } else {
        var $user = $('<span class="name"></span>');
        $user.addClass(message.user.flair);
        $user.text(message.user.name);
        $user.insertAfter($li.children('.timestamp'));
    }
    if (message.highlight) {
        $li.addClass('highlight')
    }
    var $message = $li.children('.message');
    $message.text(message.message);
    if (message.is_system) {
        $message.html($message.html().replace(/##(\w+?)##(.+?)##/g, function(matches, $1, $2) {
            return '<span class="' + $1 + '">' + $2 + '</span>';
        }));
    }
    $message.html($message.html().replace(/(https?:\/\/[^\s]+)/g, function(matches, $1) {
        return '<a href="' + $1 + '" target="_blank">' + $1 + '</a>';
    }));

    /*
    Disabled for now. See #22
    var delay = new Date(date.getTime() + message.delay * 1000).getTime() - Date.now();
    if (delay > 0 && !((message.user && this.vars.user.id === message.user.id) || this.vars.user.can_monitor)) {
        $li.hide();
        setTimeout(function() {
            $li.show();
            var $messages = $('.race-chat .messages');
            $messages[0].scrollTop = $messages[0].scrollHeight
        }, delay);
    }
    */

    return $li;
};

Race.prototype.guid = function() {
    return Math.random().toString(36).substring(2, 15)
        + Math.random().toString(36).substring(2, 15);
};

Race.prototype.heartbeat = function() {
    clearTimeout(this.pingTimeout);
    clearTimeout(this.pongTimeout);
    this.pingTimeout = setTimeout(function() {
        try {
            this.chatSocket.send(JSON.stringify({
                'action': 'ping'
            }));
        } catch (e) {}
    }.bind(this), 20000);
    this.pongTimeout = setTimeout(function() {
        this.chatSocket.close();
    }.bind(this), 30000);
};

Race.prototype.onError = function(xhr) {
    var self = this;
    if (xhr.status === 422) {
        if (xhr.responseJSON && 'errors' in xhr.responseJSON) {
            xhr.responseJSON.errors.forEach(function(msg) {
                self.whoops(msg);
            });
        } else {
            self.whoops(xhr.responseText);
        }
        $('.race-action-form button').prop('disabled', false);
    } else {
        self.whoops(
            'Something went wrong (code ' + xhr.status + '). ' +
            'Reload the page to continue.'
        );
    }
};

Race.prototype.onSocketClose = function(event) {
    $('.race-chat').addClass('disconnected');
    this.reconnect();
};

Race.prototype.onSocketError = function(event) {
    $('.race-chat').addClass('disconnected');
    this.reconnect();
};

Race.prototype.onSocketMessage = function(event) {
    try {
        var data = JSON.parse(event.data);
    } catch (e) {
        if ('notice_exception' in window) {
            window.notice_exception(e);
            return;
        } else {
            throw e;
        }
    }

    this.heartbeat();

    switch (data.type) {
        case 'race.data':
            this.raceTick();
            if (this.vars.user.can_moderate)
                break;
            this.vars.user.can_monitor = Boolean(data.race.monitors.some(user => user.id === this.vars.user.id));
            break;
        case 'chat.message':
            this.addMessage(data.message);
            break;
    }
};

Race.prototype.onSocketOpen = function(event) {
    $('.race-chat').removeClass('disconnected');
};

Race.prototype.open = function() {
    var proto = location.protocol === 'https:' ? 'wss://' : 'ws://';
    this.chatSocket = new WebSocket(proto + location.host + this.vars.urls.chat);
    for (var type in this.socketListeners) {
        this.chatSocket.addEventListener(type, this.socketListeners[type]);
    }
    this.heartbeat();
};

Race.prototype.raceTick = function() {
    var self = this;
    $.get(self.vars.urls.renders, function(data, status, xhr) {
        var latency = 0;
        if (xhr.getResponseHeader('X-Date-Exact')) {
            latency = new Date(xhr.getResponseHeader('X-Date-Exact')) - new Date();
        }
        requestAnimationFrame(function() {
            for (var segment in data) {
                if (!data.hasOwnProperty(segment)) continue;
                var $segment = $('.race-' + segment);
                $segment.html(data[segment]);
                $segment.find('time').data('latency', latency);
                window.localiseDates.call($segment[0]);
                window.addAutocompleters.call($segment[0]);
                $segment.find('.race-action-form').each(function() {
                    self.ajaxifyActionForm(this);
                });
            }
            // This is kind of a fudge but replacing urlize is awful.
            $('.race-info .info a').each(function() {
                $(this).attr('target', '_blank');
            });
        });
    });
};

Race.prototype.reconnect = function() {
    for (var type in this.socketListeners) {
        this.chatSocket.removeEventListener(type, this.socketListeners[type]);
    }

    setTimeout(function() {
        this.open();
    }.bind(this), 1000);
};

Race.prototype.whoops = function(message) {
    var $messages = $('.race-chat .messages');
    var date = new Date();
    var timestamp = ('00' + date.getHours()).slice(-2) + ':' + ('00' + date.getMinutes()).slice(-2);
    var $li = $(
        '<li class="error">' +
        '<span class="timestamp">' + timestamp + '</span>' +
        '<span class="message"></span>' +
        '</li>'
    );
    $li.find('.message').text(message);
    $messages.append($li);
    $messages[0].scrollTop = $messages[0].scrollHeight
};

$(function() {
    var race = new Race();
    window.race = race;

    $('.race-action-form').each(function() {
        race.ajaxifyActionForm(this);
    });

    var guid = race.guid();
    var sending = null;
    $('.race-chat form').ajaxForm({
        beforeSubmit: function(data, $form) {
            var message = $form.find('[name="message"]').val().trim();
            if (message === '' || message === sending) {
                return false;
            }
            data.push({name: 'guid', value: guid});
            sending = message;
        },
        complete: function() {
            guid = race.guid();
            sending = null;
        },
        error: race.onError.bind(race),
        success: function() {
            $('.race-chat form textarea').val('').height(18);
        }
    });

    $(document).on('keydown', '.race-chat form textarea', function(event) {
        if (event.which === 13) {
            if ($(this).val()) {
                $(this).closest('form').submit();
            }
            return false;
        }
    });

    $(document).on('change input keyup', '.race-chat form textarea', function() {
        $(this).height($(this)[0].scrollHeight - 10);
    });

    $(document).on('click', '.dangerous .btn', function() {
        return confirm($(this).text().trim() + ': are you sure you want to do that?');
    });
});
