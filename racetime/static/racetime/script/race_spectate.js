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
});
