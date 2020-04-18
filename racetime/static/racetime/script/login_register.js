$(function() {
    $(document).on('click', '.container > .content > main > .attract', function() {
        $(this).closest('main').addClass('focus').siblings().removeClass('focus');
    });
    $(document).on('focus', '.container > .content > main input', function() {
        $(this).closest('main').addClass('focus').siblings().removeClass('focus');
    });
});
