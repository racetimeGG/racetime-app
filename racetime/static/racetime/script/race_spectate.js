$(function() {
    $(document).on('click', '.race-streams .visibility', function() {
        var $li = $(this).closest('li');
        $li.toggleClass('playing');
        if ($li.hasClass('playing')) {
            $('<iframe>').attr('src', $li.data('embed-uri'))
                .appendTo($li.find('.player'));
        } else {
            $li.find('.player iframe').remove();
        }
    });
    $(document).on('click', '.race-stream-control .streamctl', function() {
        $('body').addClass($(this).data('class'))
            .removeClass($(this).data('unclass'));
    });
});
