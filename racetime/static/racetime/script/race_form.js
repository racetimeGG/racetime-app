$(function() {
    var $submit = $('.race-form button[type="submit"]');
    var $goal = $('#id_goal').closest('li');
    var $customGoal = $goal.next();
    var $prevGoalSelected = null;
    var $unlisted = $('#id_unlisted');
    var $ranked = $('#id_ranked');

    var changedFields = [];
    var rankedWasChecked = true;

    function updateFormByGoal(goal_id) {
        if ($('.race-edit-form').length > 0) {
            if (goal_id) {
                $submit.prop('disabled', false);
                $customGoal.hide().find('input').val('');
                $('#id_ranked')
                    .prop('checked', rankedWasChecked)
                    .prop('disabled', false);
            } else {
                if ($customGoal.find('input').val() === '') {
                    $submit.prop('disabled', true);
                }
                $customGoal.show();
                rankedWasChecked = $('#id_ranked').prop('checked');
                $('#id_ranked')
                    .prop('checked', false)
                    .prop('disabled', true);
            }
            updateRevealAtVisibility();
            return;
        }
        var data = {
            'bare': 1,
            'goal': goal_id
        }
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
                $prevGoalSelected = $('#id_goal input:checked');
            },
            error: function() {
                $('#id_goal input')
                    .prop('checked', false)
                    .prop('disabled', false);
                if (!!$prevGoalSelected) {
                    $prevGoalSelected.prop('checked', true);
                }
                $('#id_goal').parent().after(
                    '<li class="js-error"><span class="errorlist">' +
                    'Failed to load goal settings. Try again, or reload the page.' +
                    '</span></li>'
                );
                $('.race-form').removeClass('is-loading');
            }
        });
    }

    function updateRevealAtVisibility() {
        var $revealAt = $('#id_reveal_at').closest('li');
        var $customGoal = $('#id_custom_goal');
        var isUnlisted = $unlisted.is(':checked');
        var hasCustomGoal = $customGoal.val() !== '';
        var isRanked = $ranked.is(':checked');
        var isNotRecordable = hasCustomGoal || !isRanked;
        
        if (isUnlisted && isNotRecordable) {
            $revealAt.show();
        } else {
            $revealAt.hide();
            $('#id_reveal_at').val('');
        }
    }

    function setupForm(custom, toggleOn) {
        var $goal = $('#id_goal').closest('li');
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
            $('#id_ranked')
                .prop('checked', false)
                .prop('disabled', true);
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
            rankedWasChecked = $('#id_ranked').prop('checked');
            updateFormByGoal($selectedGoal.val() || null);
        } else {
            if ($customGoal.find('input').val() === '') {
                $submit.prop('disabled', true);
            }
            $goal.nextAll().hide();
            updateRevealAtVisibility();
        }

        // Ensure reveal_at visibility is correct on page load
        updateRevealAtVisibility();

        $(document).on('click', '.race-form .toggle-additional', function () {
            $(this).nextAll().toggle();
            $(this).children('.hide, .show').toggle();
        });

        if ($('.race-form').hasClass('race-edit-form')) {
            $('.race-form .toggle-additional').trigger('click');
        }

        $(document).on('change', '.race-form [name="goal"]', function () {
            updateFormByGoal($(this).val());
        });
        $(document).on('change input keyup', '.race-form [name="custom_goal"]', function () {
            if ($(this).val() === '') {
                $submit.prop('disabled', true);
            } else {
                $submit.prop('disabled', false);
            }
            updateRevealAtVisibility();
        });
        $(document).on('change input keyup', '.race-form input', function () {
            if ($(this).attr('name') === 'goal') return;
            if (changedFields.indexOf($(this).attr('id')) === -1) {
                changedFields.push($(this).attr('id'));
            }
        });
        $(document).on('change', '.race-form [name="unlisted"]', function () {
            updateRevealAtVisibility();
        });
        $(document).on('change', '.race-form [name="ranked"]', function () {
            updateRevealAtVisibility();
        });
    }
});
