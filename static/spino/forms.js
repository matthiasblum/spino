/**
 * Add several valdation methods for the sample add/edit forms
 */
jQuery.validator.addMethod("isDate", function(value, element) {
    return this.optional(element) || isValidDate(value);
}, "Please specify a valid date.");

jQuery.validator.addMethod("isPosition", function(value, element) {
    return this.optional(element) || /^[a-zA-Z][0-9]$/.test(value);
}, "Please specify a valid position (one letter and one digit).");

jQuery.validator.addMethod("isLetter", function(value, element) {
    return this.optional(element) || /^[a-zA-Z]$/.test(value);
}, "Please specify a single letter.");

jQuery.validator.addMethod("isDivision", function(value, element) {
    return this.optional(element) || isValidDivision(value);
}, "Please specify a valid number of samples/lane.");

$(document).ready(function () {
    var date = new Date(),
        y = date.getFullYear(),

        // Add a zero, then keep the two last numbers only.
        // Increment month because in JavaScript, january is 0
        m = ('0' + (date.getMonth() + 1)).slice(-2),
        d = ('0' + date.getDate()).slice(-2);

    // Default date (today)
    $('#form-add').find("[name='date']").first().val(y + '-' + m + '-' + d);

    /**
     * Updates the sample ID when letter changes
     */
    $("[name='sampleletterid']").change(function() {
        var letter = $(this).val().trim(),
            form = $(this).closest('form'),
            dateInput = $(form).find("[name='date']").first(),
            dateArray = $(dateInput).val().match(/^(\d{4})-(\d{2})-(\d{2})$/);

        setSampleID(dateArray, letter,  $(form).find("[name='sampleid']").first());

    });

    /**
     * Updates the sample ID when the date changes
     */
    $("[name='date']").change(function() {
        var form = $(this).closest('form'),
            letter = $(form).find("[name='sampleletterid']").val().trim(),
            dtArray = $(this).val().match(/^(\d{4})-(\d{2})-(\d{2})$/);

        setSampleID(dtArray, letter, $(form).find("[name='sampleid']").first());
    });


    /**
     * File upload form
     */
    $('#form-upload').validate({
        rules: {
            inputfile: {
                required: true
            }
        },
        highlight: function(element) {
            $(element).closest('.form-group').addClass('has-error');
        },
        unhighlight: function(element) {
            $(element).closest('.form-group').removeClass('has-error');
        },
        errorElement: 'p',
        errorClass: 'help-block',
        errorPlacement: function(error, element) {
            if(element.parent('.input-group').length) {
                error.insertAfter(element.parent());
            } else {
                error.insertAfter(element);
            }
        }
    });

    /**
     * Set form rules for adding and editing a sample
     */
    $.each([$('#form-add'), $('#form-edit')], function(idx, formElt) {
        // Basic rules
        $(formElt).validate({
            rules: {
                date: { isDate: true },
                position: {isPosition: true},
                sampleletterid: {isLetter: true},
                laneusage: {isDivision: true},
                timepoint: {min: 0},
                volume: {min: 1},
                comment: {maxlength: 250},
                file: {required: true}
            },
            highlight: function(element) {
                $(element).closest('.form-group').addClass('has-error');
            },
            unhighlight: function(element) {
                $(element).closest('.form-group').removeClass('has-error');
            },
            errorElement: 'span',
            errorClass: 'help-block',
            errorPlacement: function(error, element) {
                if(element.parent('.input-group').length) {
                    error.insertAfter(element.parent());
                } else {
                    error.insertAfter(element);
                }
            }
        });

        // Add a required rule for each input/select if the user is not a "creator"
        if (! spinoCreator) {
            $(formElt).find('input, select').each(function() {
               $(this).rules('add', {
                   required: true
               })
            });
        }
    });

    /**
     * Add a select input for attachment files
     */
    $('.btn-add-file').click(function() {
        var attachments = $(this).parents().eq(1).find(".attachments"),
            numFiles = attachments.children(".form-group").length,
            selectHTML = attachments.find("select").first().html(),
            delBtn = $(this).parent().find('.btn-del-file');

        // Add a new from-group with the select inside
        attachments.append('<div class="form-group"><select class="form-control" name="file' + (numFiles + 1) + '">'+ selectHTML +'</select></div>');

        // Select the last form-group (just created), select its select element and add a required rule
        attachments.children(".form-group").last().children("select").rules("add", {
            required: true
        });

        if (delBtn.attr('disabled') === 'disabled') {
            delBtn.removeAttr('disabled');
        }
    });

    /**
     * Delete the last select input
     */
    $('.btn-del-file').click(function() {
        var selects = $(this).parent().parent().children('.attachments').children();

        if (selects.length > 1) {
            selects.last().remove();
        }

        if (selects.length <= 2) {
            $(this).attr('disabled', 'disabled');
        }
    });

    /**
     * Submit the form and add a new sample
     */
    $('#btn-add-submit').click(function() {
        var form = $('#form-add');

        if (form.valid()) {
            var ajaxParams= '',
                sampleId = $(form).find("[name='sampleid']").first().val();

            $.each(form.serializeArray(), function(i, field) {
                // We want all the files with the same param name
                var param = /^file([0-9]+)?$/.test(field.name) ? "file" : field.name

                // After the first param, we need the add an ampersand
                if (i > 0) {
                    ajaxParams += '&'
                }
                ajaxParams += param + '=' + field.value;
            });

            if (isValidSampleId(sampleId)) {
                ajaxParams += '&sampleid=' + sampleId;
            }

            $.ajax({
                url: '/samples/add',
                type: 'post',
                data: ajaxParams,
                success: function(response) {
                    var alertDiv = $(form).find('.alert').first();

                    response = JSON.parse(response);
                    if (response.code === 0) {
                        // Everything went right, the sample is created
                        $(alertDiv).hide();
                        $(alertDiv).removeClass();
                        $(alertDiv).addClass('alert');
                        $(alertDiv).addClass(response.class);
                        $(alertDiv).html(response.html).show().delay(3000).fadeOut(400);
                        $('#table-samples').DataTable().ajax.reload();  // Reload the table with the new sample
                        // scroll down to the updated table (wrapped created by DataTable)
                        //$('html, body').animate({scrollTop: $('#table-samples_wrapper').offset().top -100 }, 'slow');
                    } else {
                        // An error occurred
                        $(alertDiv).removeClass();
                        $(alertDiv).addClass('alert');
                        $(alertDiv).addClass(response.class);
                        $(alertDiv).html(response.html).show();
                    }
                },
                error: function(jqXHR, textStatus) {
                    // Fuck the user :)
                }
            });
        }
    });

    /**
     * Reset the form for adding new samples
     */
    $('.form-reset').click(function() {
        var form = $('#form-add');
        $(form)[0].reset();
        $(form).find('.alert').hide();
    });

    /**
     * Submit the form and save the changes made on a sample
     */
    $('#btn-edit-submit').click(function() {
        var form = $('#form-edit');

        if (form.valid()) {
            var ajaxParams= '',
                sampleId = $(form).find("[name='sampleid']").first().val();

            $.each(form.serializeArray(), function(i, field) {
                // We want all the files with the same param name
                var param = /^file([0-9]+)?$/.test(field.name) ? "file" : field.name

                // After the first param, we need the add an ampersand
                if (i > 0) {
                    ajaxParams += '&'
                }

                ajaxParams += param + '=' + field.value;
            });

            if (isValidSampleId(sampleId)) {
                ajaxParams += '&sampleid=' + sampleId;
            }

            $.ajax({
                url: '/samples/edit',
                type: 'post',
                data: ajaxParams,
                success: function(response) {
                    var alertDiv = $(form).find('.alert').first();

                    response = JSON.parse(response);
                    if (response.code === 0) {
                        // Everything went right, the sample is edited
                        $("#table-samples").DataTable().ajax.reload();  // Reload the table with the new sample
                        $("#modal-edit").modal("hide");  // Hide the modal
                    } else {
                        // An error occurred
                        $(alertDiv).removeClass();
                        $(alertDiv).addClass('alert');
                        $(alertDiv).addClass(response.class);
                        $(alertDiv).html(response.html).show();
                    }
                },
                error: function(jqXHR, textStatus) {
                    // Fuck the user :)
                }
            });
        }
    });

    /**
     * Delete the sample
     */
    $('#btn-edit-delete').click(function() {
        var sampleId = $('#form-edit').find("[name='realid']").val();

        $.ajax({
            url: '/samples/delete',
            type: 'post',
            data: 'id=' + sampleId,
            success: function(response) {
                if (response === '0') {
                    $("#table-samples").DataTable().ajax.reload();  // Reload the table
                }
                $("#modal-edit").modal("hide");  // Hide the modal
            }
        });
    });

    $('#btn-waiting').click(function() {setStatus(0);});
    $('#btn-queue').click(function() {setStatus(1);});
    $('#btn-sequencing').click(function() {setStatus(2);});
    $('#btn-sequenced').click(function() {setStatus(3);});
    $('#btn-archived').click(function() {setStatus(4);});
});