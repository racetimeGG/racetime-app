$(function() {
    $(document).on('click', '.audit-log .show-detail', function() {
        $(this).closest('li').addClass('with-detail');
    });
    $(document).on('click', '.audit-log .hide-detail', function() {
        $(this).closest('li').removeClass('with-detail');
    });
});
