$(function() {
    $(document).on('click', '.race-streams .visibility', function() {
        var $li = $(this).closest('li');
        $li.toggleClass('playing not-playing');
        if ($li.hasClass('playing')) {
            $('<iframe allowfullscreen>').attr('src', $li.data('embed-uri'))
                .appendTo($li.find('.player'));
        } else {
            $li.find('.player iframe').remove();
        }
    });
    $(document).on('click', '.race-stream-control .open-all', function() {
        if ($('.race-streams .not-playing').length) {
            $('.race-streams .not-playing .visibility').trigger('click');
        } else {
            $('.race-streams .playing .visibility').trigger('click');
        }
    });
    $(document).on('click', '.race-stream-control .streamctl', function() {
        $('body').addClass($(this).data('class'))
            .removeClass($(this).data('unclass'));
    });
    $(document).on('raceTick', '.race-streams', function(event, html) {
        // Special handling for the streams render. Clobbering the whole div
        // is bad because it kills any open streams. So instead we have to
        // expend some effort to add/remove individual streams as needed.
        var streams = $('.race-streams > ol > li').map(function() {
            return $(this).attr('id');
        }).get();
        var previous = null;
        $('<div />').html(html).children('ol').children('li').each(function() {
            var index = streams.indexOf($(this).attr('id'));
            if (index === -1) {
                if (previous) {
                    $(this).insertAfter(previous);
                } else {
                    $(this).prependTo('.race-streams > ol');
                }
                previous = this;
            } else {
                var id = streams.splice(index, 1)[0];
                previous = $('#' + id)[0];
            }
        });
        if (streams.length > 0) {
            $('#' + streams.join(', #')).remove();
        }
    });
});
