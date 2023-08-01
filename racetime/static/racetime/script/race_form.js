$(function() {
    var $submit = $('.race-form button[type="submit"]');
    var $goal = $('#id_goal').closest('li');
    var $customGoal = $goal.next();

    var changedFields = [];

    function updateFormByGoal(goal_id) {
        if ($('.race-edit-form').length > 0) {
            if (goal_id) {
                $submit.prop('disabled', false);
                $customGoal.hide().find('input').val('');
            } else {
                if ($customGoal.find('input').val() === '') {
                    $submit.prop('disabled', true);
                }
                $customGoal.show();
            }
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
        $('.race-form > ul input').prop('disabled', true);
        $.get(window.location, data, function(html) {
            var toggleOn = $('.toggle-additional .hide:visible').length > 0;
            $('.race-form > ul').replaceWith(html);
            setupForm(!goal_id, toggleOn);
        });
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
            updateFormByGoal($selectedGoal.val() || null);
        } else {
            if ($customGoal.find('input').val() === '') {
                $submit.prop('disabled', true);
            }
            $goal.nextAll().hide();
        }


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
        });
        $(document).on('change input keyup', '.race-form input', function () {
            if ($(this).attr('name') === 'goal') return;
            if (changedFields.indexOf($(this).attr('id')) === -1) {
                changedFields.push($(this).attr('id'));
            }
        });
    }
});
