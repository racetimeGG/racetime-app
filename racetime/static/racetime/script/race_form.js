$(function() {
    var $submit = $('.race-form button[type="submit"]');
    var $goal = $('#id_goal').closest('li');
    var $customGoal = $goal.next();
    var changedFields = [];
    var additionalSectionCollapsed = false;
    var timezoneOffset = new Date().getTimezoneOffset();
    $('#id_timezone_offset, input[name="timezone_offset"]').val(timezoneOffset);

    function convertRevealAtToLocal() {
        var $revealAtField = $('#id_reveal_at');
        if ($revealAtField.length && $revealAtField.val() && $('.race-edit-form').length > 0 && !$revealAtField.attr('data-converted')) {
            var utcTime = new Date($revealAtField.val());
            var localTime = new Date(utcTime.getTime() - (timezoneOffset * 60000));
            
            var year = localTime.getFullYear();
            var month = String(localTime.getMonth() + 1).padStart(2, '0');
            var day = String(localTime.getDate()).padStart(2, '0');
            var hours = String(localTime.getHours()).padStart(2, '0');
            var minutes = String(localTime.getMinutes()).padStart(2, '0');
            var localTimeString = year + '-' + month + '-' + day + 'T' + hours + ':' + minutes;
            
            $revealAtField.val(localTimeString);
            $revealAtField.attr('data-converted', 'true');
        }
    }

    function updateRevealAtEnabled() {
        var $revealAtField = $('#id_reveal_at');
        var isUnlisted = $('#id_unlisted').is(':checked');
        var hasCustomGoal = $customGoal.length > 0 && $customGoal.val() !== '';
        var isRanked = $('#id_ranked').is(':checked');
        var shouldEnable = isUnlisted && !isRanked;

        $revealAtField.prop('disabled', !shouldEnable);
        if (!shouldEnable) {
            $revealAtField.val('');
            $revealAtField.addClass('disabled');
        } else {
            $revealAtField.removeClass('disabled');
        }
    }

    function handleGoalChange(goal_id) {
        if ($('.race-edit-form').length > 0) {
            if (goal_id) {
                $submit.prop('disabled', false);
                $customGoal.hide().find('input').val('');
                $('#id_ranked').prop('checked', true).prop('disabled', false);
            } else {
                if ($customGoal.find('input').val() === '') {
                    $submit.prop('disabled', true);
                }
                $customGoal.show();
                $('#id_ranked').prop('checked', false).prop('disabled', true);
            }
            setTimeout(updateRevealAtEnabled, 10);
            return;
        }

        var data = {
            'bare': 1,
            'goal': goal_id,
            'timezone_offset': timezoneOffset
        };
        changedFields.forEach(function(name) {
            if (name === 'id_custom_goal' && goal_id) return;
            var $field = $('#' + name);
            data[$field.attr('name')] = $field.val();
        });
        $('.race-form').addClass('is-loading');
        $('.race-form > ul input').prop('disabled', true);
        $('.race-form .js-error').remove();
        $.get({
            url: window.location,
            data: data,
            success: function(html) {
                var toggleOn = $('.toggle-additional .hide:visible').length > 0;
                $('.race-form > ul').replaceWith(html);
                setupForm(!goal_id, toggleOn);
                $('.race-form').removeClass('is-loading');
                additionalSectionCollapsed = false;
                setTimeout(updateRevealAtEnabled, 10);
            },
            error: function() {
                $('#id_goal input').prop('checked', false).prop('disabled', false);
                $('.race-form').removeClass('is-loading');
                $('#id_goal').parent().after(
                    '<li class="js-error"><span class="errorlist">' +
                    'Failed to load goal settings. Try again, or reload the page.' +
                    '</span></li>'
                );
            }
        });
    }

    function setupForm(custom, toggleOn) {
        var $lastMain = $('#id_invitational').closest('li');
        $lastMain.nextAll().hide();
        var $toggle = $('<li class="toggle-additional">' +
            '<span class="show"><i class="material-icons">expand_more</i> Show additional options</span>' +
            '<span class="hide" style="display: none"><i class="material-icons">expand_less</i> Hide additional options</span>' +
            '</li>').insertAfter($lastMain);
        if (custom) {
            if ($customGoal.find('input').val() === '') {
                $submit.prop('disabled', true);
            }
            $goal.next().show();
            $('#id_ranked').prop('checked', false).prop('disabled', true);
        } else {
            $submit.prop('disabled', false);
            $goal.next().hide().find('input').val('');
        }
        if (toggleOn) {
            $toggle.children('.hide, .show').toggle();
            $lastMain.nextAll().show();
        }
    }

    if ($goal.length) {
        if ($goal.find('input').length === 1) {
            $goal.find('input').prop('checked', true);
        }

        var $selectedGoal = $goal.find(':checked');
        setupForm($selectedGoal.length > 0 && $selectedGoal.val() === '', false);

        if ($selectedGoal.length > 0) {
            handleGoalChange($selectedGoal.val() || null);
        } else {
            if ($customGoal.find('input').val() === '') {
                $submit.prop('disabled', true);
            }
            $goal.nextAll().hide();
        }
        updateRevealAtEnabled();

        $(document).on('click', '.race-form .toggle-additional', function () {
            var isHiding = $(this).children('.hide').is(':visible');
            $(this).nextAll().toggle();
            $(this).children('.hide, .show').toggle();
            additionalSectionCollapsed = isHiding;
            setTimeout(updateRevealAtEnabled, 10);
        });

        if ($('.race-form').hasClass('race-edit-form')) {
            $('.race-form .toggle-additional').trigger('click');
        }

        $(document).on('change', '.race-form [name="goal"]', function () {
            handleGoalChange($(this).val());
        });
        $(document).on('change input keyup', '.race-form [name="custom_goal"]', function () {
            $submit.prop('disabled', $(this).val() === '');
            updateRevealAtEnabled();
        });
        $(document).on('change input keyup', '.race-form input', function () {
            if ($(this).attr('name') === 'goal') return;
            if (changedFields.indexOf($(this).attr('id')) === -1) {
                changedFields.push($(this).attr('id'));
            }
        });
        $(document).on('change', '.race-form [name="unlisted"]', function () {
            updateRevealAtEnabled();
        });
        $(document).on('change', '.race-form [name="ranked"]', function () {
            updateRevealAtEnabled();
        });
        $(document).on('click', '.race-form [name="ranked"]', function () {
            setTimeout(updateRevealAtEnabled, 10);
        });
    }
    // Convert reveal_at time after DOM is ready
    setTimeout(convertRevealAtToLocal, 50);
});
