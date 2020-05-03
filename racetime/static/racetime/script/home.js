$(function() {
    var homeFilter = function() {
        var value = $(this).val().toLowerCase().replace(/"/g, '');
        var $all = $('.home-categories').children(':not(.request-category, [data-slug="misc"])');
        var $misc = $('.home-categories').children('.request-category, [data-slug="misc"]');
        if (value) {
            var $found = $all.hide().filter('[data-search*="' + value + '"]').show();
            $misc.not($found)[$found.length === 0 ? 'show' : 'hide']();
        } else {
            $all.show();
            $misc.show();
        }
    };
    $(document).on('change input keyup', '.home-filter', homeFilter);
    $('.home-filter').each(homeFilter);
});
