$(function() {
    var getNavigatorLanguage = function() {
        if (navigator.languages && navigator.languages.length) {
            return navigator.languages[0];
        } else {
            return navigator.userLanguage || navigator.language || navigator.browserLanguage || 'en';
        }
    };

    window.globalLatency = 0;

    var updateTimer = function() {
        $(this).attr('datetime');

        var timer = Date.now() - new Date($(this).attr('datetime'));
        timer += window.globalLatency;
        var negative = timer < 0;

        if (negative && timer >= -100) {
            $(this).closest('.race-status').addClass('go');
        }

        timer = Math.abs(timer);

        if ($('body').hasClass('timer-no-deciseconds')) {
            // Always round up to the nearest second if deciseconds are hidden
            timer = timer + 1000 - (timer % 100);
        }

        var hours = (timer - (timer % 3600000)) / 3600000;
        timer -= hours * 3600000;
        var mins = (timer - (timer % 60000)) / 60000;
        timer -= mins * 60000;
        var secs = (timer - (timer % 1000)) / 1000;
        timer -= secs * 1000;
        var ds = (timer - (timer % 100)) / 100;

        $(this).html(
            (negative ? '-' : '')
            + hours
            + ':' + ('00' + mins).slice(-2)
            + ':' + ('00' + secs).slice(-2)
            + '<small>.' + ('' + ds) + '</small>'
        );
    };
    var autotick = function() {
        $('time.autotick').each(updateTimer);
        requestAnimationFrame(autotick);
    };

    autotick();

    $(document).on('click', '.timer', function() {
        $('body').toggleClass('timer-no-deciseconds');
    });

    window.localiseDates = function() {
        $(this).find('time.datetime').each(function () {
            var date = new Date(
                new Date($(this).attr('datetime')).getTime()
                + window.globalLatency
            );
            $(this).html(date.toLocaleString(getNavigatorLanguage()));
        });
        $(this).find('time.onlydate').each(function () {
            var date = new Date(
                new Date($(this).attr('datetime')).getTime()
                + window.globalLatency
            );
            $(this).html(date.toLocaleDateString(getNavigatorLanguage()));
        });
        $(this).find('time.onlytime').each(function () {
            var date = new Date(
                new Date($(this).attr('datetime')).getTime()
                + window.globalLatency
            );
            $(this).html(date.toLocaleTimeString(getNavigatorLanguage()));
        });
    };
    window.localiseDates.call(document.body);

    window.addAutocompleters = function() {
        $(this).find('.autocomplete-user').each(function() {
            var self = this;
            $(this).autocomplete({
                source: $(this).data('source'),
                minLength: 2,
                response: function(event, ui) {
                    var content = ui.content.pop();
                    $.each(content, (k, item) => ui.content.push(item));
                },
                select: function(event, ui) {
                    $(self).closest('.user-pop')
                        .find('.avatar')
                        .css('background-image', ui.item.avatar ? 'url(' + ui.item.avatar + ')' : '');
                    $(self).closest('form').find('[name="user"]').val(ui.item.id);
                    $(self).val(ui.item.full_name);
                    return false;
                }
            });
            $(this).autocomplete('instance')._renderItem = function(ul, item) {
                var $avatar = $('<span class="avatar">');
                $avatar.css('background-image', item.avatar ? 'url(' + item.avatar + ')' : '');

                var $name = $('<span class="name">');
                $name.text(item.full_name);

                var $pop = $('<span class="user-pop">');
                $pop.append($avatar, $name);

                return $('<li>').append($pop).appendTo(ul);
            };
            if ($(this).hasClass('above')) {
                $(this).autocomplete('option', 'position', {
                    my: 'right top',
                    at: 'right bottom'
                });
            }
        });
    };
    window.addAutocompleters.call(document.body);

    var lastCopyClicked = null;
    $(document).on('click', '.copy-to-clipboard', function(e) {
        if (this === lastCopyClicked) {
            return true;
        }
        lastCopyClicked = this;

        var $textarea = $('<textarea />');
        var target = $(this).data('target') || this;
        $textarea.val($(target).text().trim());
        $textarea.appendTo('body');

        $textarea[0].select();
        document.execCommand('copy');

        $textarea.remove();

        var $copied = $('<span class="copied-to-clipboard" />');
        $copied.css({
            left: e.clientX + 10,
            top: e.clientY
        });
        $copied.appendTo('body');
        setTimeout(function() {
            $copied.fadeOut(300, function () {
                $(this).remove();
                lastCopyClicked = null;
            });
        }, 400);
    });

    $('.bulletin').each(function() {
        if (!localStorage.getItem('bulletin.' + $(this).attr('id'))) {
            $(this).removeClass('hidden');
        }
    });
    $(document).on('click', '.bulletin .action-close', function(e) {
        var $bulletin = $(this).closest('.bulletin');
        localStorage.setItem('bulletin.' + $bulletin.attr('id'), '1');
        $bulletin.addClass('hidden');
    });

    $(document).on('mouseenter', '.entrant-row > .user > .comment', function() {
        var props = $(this).offset();
        props.position = 'absolute';
        $(this).css(props).addClass('open');
    });
    $(document).on('mouseleave', '.entrant-row > .user > .comment', function() {
        $(this).removeClass('open').css({
            'left': '',
            'position': '',
            'top': ''
        });
    });

    $('.category-info form.favourite').each(function() {
        $(this).ajaxForm({
            beforeSubmit: function(data, $form) {
                $form.parent().children('.undo').removeClass('undo');
                $form.addClass('undo');
            },
            error: function(xhr, _1, _2, $form) {
                $form.parent().children(':not(.undo)').addClass('undo');
                $form.removeClass('undo');
                alert('Something went wrong (code ' + xhr.status + '). Sorry about that.');
            }
        });
    });
});
