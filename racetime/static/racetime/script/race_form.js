$(function() {
    var $submit = $('.race-form button[type="submit"]');
    var $goal = $('#id_goal').closest('li');

    if ($goal.length) {
        var $customGoal = $goal.next();

        if ($goal.find('input').length === 1) {
            $goal.find('input').prop('checked', true);
        }

        var $selectedGoal = $goal.find(':checked');
        if ($selectedGoal.length > 0) {
            if ($selectedGoal.val() === '') {
                if ($customGoal.find('input').val() === '') {
                    $submit.prop('disabled', true);
                }
            } else {
                $customGoal.hide();
            }
        } else {
            $submit.prop('disabled', true);
            $customGoal.hide();
        }

        var $lastMain = $('#id_invitational').closest('li');
        var $additional = $lastMain.nextAll().hide();

        $('<li class="toggle-additional">' +
            '<span class="show"><i class="material-icons">expand_more</i> Show additional options</span>' +
            '<span class="hide" style="display: none"><i class="material-icons">expand_less</i> Hide additional options</span>' +
            '</li>').insertAfter($lastMain);

        $(document).on('click', '.race-form .toggle-additional', function () {
            $additional.toggle();
            $(this).children('.hide, .show').toggle();
        });

        if ($('.race-form').hasClass('race-edit-form')) {
            $('.race-form .toggle-additional').trigger('click');
        }

        $(document).on('change', '.race-form [name="goal"]', function () {
            if ($(this).val() === '') {
                $submit.prop('disabled', true);
                $customGoal.show();
            } else {
                $submit.prop('disabled', false);
                $customGoal.hide().find('input').val('');
            }
        });
        $(document).on('change input keyup', '.race-form [name="custom_goal"]', function () {
            if ($(this).val() === '') {
                $submit.prop('disabled', true);
            } else {
                $submit.prop('disabled', false);
            }
        });
    }
});
