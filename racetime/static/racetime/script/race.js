$(function() {
    var onError = function(xhr) {
        if (xhr.status === 422) {
            if (xhr.responseText.indexOf('<ul class="errorlist">') !== -1) {
                var $errors = $(xhr.responseText);
                $errors.children('li').each(function() {
                    var field = $(this).text();
                    $errors.children('li').each(function() {
                        whoops(field + ': ' + $(this).text());
                    });
                });
            } else {
                whoops(xhr.responseText);
            }
            $('.race-action-form button').prop('disabled', false);
        } else {
            whoops(
                'Something went wrong (code ' + xhr.status + '). ' +
                'Reload the page to continue.'
            );
        }
    };

    var whoops = function(message) {
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

    var raceTick = function() {
        $.get(raceRendersLink, function(data, status, xhr) {
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
                    $segment.find('.race-action-form').each(ajaxifyActionForm)
                }
            });
        });
    };

    var ajaxifyActionForm = function() {
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
            error: onError,
            success: function() {
                chatTick();
            }
        });
    };

    var chatTickTimeout = null;
    var messageIDs = [];
    var chatTick = function(lastEnd, timeout) {
        if (chatTickTimeout) {
            clearTimeout(chatTickTimeout);
        }
        chatTickTimeout = setTimeout(function() {
            $.get(raceChatLink, {since: lastEnd}, function(data) {
                var $messages = $('.race-chat .messages');
                var updateRace = false;
                var doScroll = false;
                data.messages.forEach(function(message) {
                    if (messageIDs.indexOf(message.id) !== -1) {
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
                            $li.find('.message').text(message.message);
                            $messages.append($li);
                            doScroll = true;
                        }
                        updateRace = true;
                    }
                    else {
                        var $li = $(
                            '<li class="' + (message.highlight ? 'highlight' : '') + '">' +
                            '<span class="timestamp">' + timestamp + '</span>' +
                            '<span class="user"></span>' +
                            '<span class="message"></span>' +
                            '</li>'
                        );
                        $li.find('.user').text(message.user.full_name);
                        $li.find('.message').text(message.message);
                        $messages.append($li);
                        doScroll = true;
                    }
                    messageIDs.push(message.id);
                });
                if (doScroll) {
                    $messages[0].scrollTop = $messages[0].scrollHeight
                }
                if (updateRace) {
                    raceTick();
                }
                chatTick(data.end, data.tick_rate);
            });
        }, timeout || 4);
    };

    chatTick();

    $('.race-action-form').each(ajaxifyActionForm);

    $('.race-chat form').ajaxForm({
        error: onError,
        success: function() {
            chatTick();
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
        console.log($(this)[0].scrollHeight - 10);
        $(this).height($(this)[0].scrollHeight - 10);
    });

    $(document).on('click', '.dangerous .btn', function() {
        return confirm($(this).text().trim() + ': are you sure you want to do that?');
    })
});
