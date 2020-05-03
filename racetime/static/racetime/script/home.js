$(function() {
    var homeFilter = function() {
        var value = $(this).val().toLowerCase().replace('"', '');
        var $all = $('.home-categories').children(':not(.request-category, [data-slug="misc"])');
        if (value) {
            $all.hide().filter('[data-search*="' + value + '"]').show();
        } else {
            $all.show();
        }
    };
    $(document).on('change input keyup', '.home-filter', homeFilter);
    $('.home-filter').each(homeFilter);
});
