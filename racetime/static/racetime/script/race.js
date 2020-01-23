function Race() {
    this.vars = JSON.parse($('#race-vars').text());

    this.chatDisconnected = false;
    this.chatTickRate = 1000;
    this.chatTickTimeout = null;
    this.lastChatTick = null;
    this.lastRaceTick = null;
    this.messageIDs = [];

    setInterval(this.monitor, 1000);
}

Race.prototype.ajaxifyActionForm = function() {
    $(this).ajaxForm({
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
        error: this.onError,
        success: this.chatTick
    });
};

Race.prototype.chatTick = function(timeout) {
    var self = this;

    if (self.chatTickTimeout) {
        clearTimeout(self.chatTickTimeout);
    }

    self.chatTickTimeout = setTimeout(function() {
        $.get({
            url: self.vars.urls.chat,
            data: {
                since: self.messageIDs[self.messageIDs.length - 1]
            },
            success: function(data) {
                if (!data) return;

                var $messages = $('.race-chat .messages');

                var updateRace = false;
                var doScroll = false;

                data.messages.forEach(function(message) {
                    if (self.messageIDs.indexOf(message.id) !== -1) {
                        return true;
                    }

                    var date = new Date(message.posted_at);
                    var timestamp = ('00' + date.getHours()).slice(-2) + ':' + ('00' + date.getMinutes()).slice(-2);

                    if (message.is_system) {
                        if (message.message !== '.reload') {
                            var $li = $(
                                '<li class="system ' + (message.highlight ? 'highlight' : '') + '">' +
                                '<span class="timestamp">' + timestamp + '</span>' +
                                '<span class="message"></span>' +
                                '</li>'
                            );
                            var $message = $li.find('.message');
                            $message.text(message.message);
                            $message.html($message.html().replace(/##(\w+?)##(.+?)##/g, function(matches, $1, $2) {
                                return '<span class="' + $1 + '">' + $2 + '</span>';
                            }));
                            $messages.append($li);
                            doScroll = true;
                        }
                        updateRace = true;
                    } else {
                        var $li = $(
                            '<li class="' + (message.highlight ? 'highlight' : '') + '">' +
                            '<span class="timestamp">' + timestamp + '</span>' +
                            '<span class="user"></span>' +
                            '<span class="message"></span>' +
                            '</li>'
                        );
                        $li.find('.user').text(message.user.name);
                        var $message = $li.find('.message');
                        $message.text(message.message);
                        $message.html($message.html().replace(/(https?:\/\/[^\s]+)/g, function(matches, $1) {
                            return '<a href="' + $1 + '" target="_blank">' + $1 + '</a>';
                        }));
                        $messages.append($li);
                        doScroll = true;
                    }
                    self.messageIDs.push(message.id);
                });

                $('.race-chat').removeClass('disconnected');
                self.chatDisconnected = false;
                self.chatTickRate = data.tick_rate;
                self.lastChatTick = new Date();

                if (doScroll) {
                    $messages[0].scrollTop = $messages[0].scrollHeight
                }
                if (updateRace) {
                    self.raceTick();
                }
                self.chatTick(data.tick_rate);
            },
            error: function() {
                self.chatTick(1000);
            }
        });
    }, timeout || 4);
};

Race.prototype.monitor = function() {
    // Warn the user if chat isn't updating
    if (!this.chatDisconnected && new Date() - this.lastChatTick > Math.max(10000, this.chatTickRate * 10)) {
        this.chatDisconnected = true;
        $('.race-chat').addClass('disconnected');
    }
};

Race.prototype.onError = function(xhr) {
    var self = this;
    if (xhr.status === 422) {
        if (xhr.responseText.indexOf('<ul class="errorlist">') !== -1) {
            var $errors = $(xhr.responseText);
            $errors.children('li').each(function() {
                var field = $(this).text();
                $errors.children('li').each(function() {
                    self.whoops(field + ': ' + $(this).text());
                });
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
                $segment.find('.race-action-form').each(self.ajaxifyActionForm)
            }
            // This is kind of a fudge but replacing urlize is awful.
            $('.race-info .info a').each(function() {
                $(this).attr('target', '_blank');
            });
            self.lastRaceTick = new Date();
        });
    });
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

    race.chatTick();
    $('.race-action-form').each(race.ajaxifyActionForm);

    $('.race-chat form').ajaxForm({
        error: race.onError,
        success: function() {
            race.chatTick();
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
