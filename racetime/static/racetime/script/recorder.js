const ajaxifyActionForm = function(form) {
    $(form).ajaxForm({
        clearForm: true,
        beforeSubmit: function() {
            $('.race-action-form button').prop('disabled', true);
        },
        error: function(xhr) {
            if (xhr.status === 422) {
                if (xhr.responseJSON && 'errors' in xhr.responseJSON) {
                    xhr.responseJSON.errors.forEach(function(msg) {
                        alert(msg);
                    });
                } else {
                    alert(xhr.responseText);
                }
                $('.race-action-form button:not(.on-hold)').prop('disabled', false);
            } else {
                alert(
                    'Something went wrong (code ' + xhr.status + '). ' +
                    'Try reloading the page.'
                );
            }
        },
        success: function() {
            $('.race-action-form button:not(.on-hold)').prop('disabled', false);
            const $li = $($(form).parents('li')[1]);
            $li.slideUp(250, () => {
                let $state;
                if ($(form).parent().hasClass('record')) {
                    $li.addClass('finalized recorded');
                    $state = $('<span class="state">(recorded)</span>');
                } else {
                    $li.addClass('finalized not-recorded');
                    $state = $('<span class="state">(not recorded)</span>');
                }
                const $a = $li.find('a').first();
                $a.empty().append($li.find('.slug'));
                $li.empty().append($a, $state);
                $li.prependTo('.recorder.finalized > ol').slideDown(250);
            })
        }
    });
};

$(function() {
    $('.race-action-form').each(function() {
        ajaxifyActionForm(this);
    });
    $('.recorder .skip button').on('click', function() {
        const $li = $($(this).parents('li')[1]);
        $li.slideUp(250, () => {
            $li.addClass('finalized skipped');
            const $state = $('<span class="state">(skipped)</span>');
            const $a = $li.find('a').first();
            $a.empty().append($li.find('.slug'));
            $li.empty().append($a, $state);
            $li.prependTo('.recorder.finalized > ol').slideDown(250);
        });
    });

    let keypressDebounce = false;
    $(document).on('keypress', function(ev) {
        if (keypressDebounce) return false;
        if (ev.which === 114) { // r
            $('.record .race-action-form button').first().click();
        } else if (ev.which === 100) { // d
            $('.cancel .race-action-form button').first().click();
        } else if (ev.which === 115) { // s
            $('.skip button').first().click();
        }
        keypressDebounce = true;
        setTimeout(function() {
            keypressDebounce = false;
        }, 500);
    });
});
