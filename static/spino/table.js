// Names from http://chir.ag/projects/name-that-color/
var coloursClass = ["buttercup", "wisteria", "curious-blue", "shamrock", "blue-dianne"];

$(document).ready(function() {
    $('#spino-btn').find('button').each(function(index) {
        $(this).addClass(coloursClass[index])
    });

    $("#table-samples").dataTable({
        dom: 'C<"clear">lfrtip',  // needed for the colVis extension (column visibility)
        "pageLength": 25,
        "scrollX": true,  // enable horizontal scrolling
        "processing": true,
        "serverSide": true,
        "ajax": {
            "url": "/samples/get",
            "type": "POST"
        },
        "order": [ 15, "desc" ],
        "columns": [{
            "name": "id",
            "data": "id",
            "orderable": false,
            "render": function(data) {
                var id = data[0],
                    changestatus = data[1];

                if (changestatus === true) {
                    return '<input type="checkbox" name="setstatus" value="' + id + '">';
                } else {
                    return '<input type="checkbox" disabled>';
                }
            }
        }, {
            "name": "sampleid",
            "data": "sampleid"
        }, {
            "name": "platformid",
            "data": "platformid"
        },{
            "name": "files",
            "data": "files",
            "orderable": false,
            "render": function(data) {
                if (data.length === 1) {
                    return '<a href="/files/' + data[0][1] + '">Link</a>';
                } else {
                    return '<button type="button" class="btn btn-link btn-show-links" data-toggle="modal" data-target="#show-links-modal">Links</button>';
                }
            }
        }, {
            "name": "users",
            "data": "users",
            "render": function(data) {
                 if (data[1] !== null && data[0] !== data[1]) {
                     return data[0] + " (" + data[1] + ")";
                 } else {
                     return data[0];
                 }
            }
        }, {
            "name": "position",
            "data": "position",
            "orderable": false,
            "visible": false
        }, {
            "name": "laneusage",
            "data": "laneusage",
            "orderable": false,
            "visible": false
        }, {
            "name": "barcode",
            "data": "barcode",
            "orderable": false,
            "visible": false,
            "render": function(data) {
                if (data !== null) {
                    return data.replace(/ /g, '\u00a0');  // no-break space character
                } else {
                    return data;
                }
            }
        }, {
            "name": "volumne",
            "data": "volume",
            "orderable": false,
            "visible": false
        }, {
            "name": "application",
            "data": "application"
        }, {
            "name": "organism",
            "data": "organism"
        }, {
            "name": "celline",
            "data": "cellline"
        }, {
            "name": "treatment",
            "data": "treatment",
            "orderable": false
        }, {
            "name": "timepoint",
            "data": "timepoint",
            "orderable": false
        }, {
            "name": "antibody",
            "data": "antibody"
        }, {
            "name": "date",
            "data": "date"
        }, {
            "name": "comment",
            "data": "comment",
            "orderable": false,
            "render": function ( data, type, full, meta ) {
                if (data === null) {
                    return data;
                } else {
                    return '<button type="button" class="btn btn-default btn-sm btn-show-comment" data-toggle="modal" data-target="#modal-comment">Show</button>';
                }
                return data;
            }
        }, {
            "name": "edit",
            "data": "edit",
            "orderable": false,
            "render": function(data) {
                if (data === true) {
                    return '<button type="button" class="btn btn-default btn-sm btn-edit-open" data-toggle="modal" data-target="#modal-edit">Edit</button>';
                } else {
                    return null;
                }
            }
        }],
        // Post process each row once their are fetched from the server
        "rowCallback": function(row, data) {
            // Button to display comment
            if (data.comment !== null) {
                var modalComment = $("#modal-comment");

                $(row).find(".btn-show-comment").click(function() {
                    $(modalComment).find("textarea").val(data.comment);
                });
            }

            // Button to edit sample
            if (data.edit === true) {
                $(row).find(".btn-edit-open").click(function() {
                    var modalEdit = $("#modal-edit"),
                        letterId, attachments, selectHTML;

                    letterId = data.sampleid.substr(data.sampleid.length - 1);  // Last character (letter)

                    // Set the sample's values to their input/select element
                    $(modalEdit).find("input[name='realid']").val(data.id[0]); // Hidden input for the sample's ID
                    $(modalEdit).find("input[name='date']").val(data.date);
                    $(modalEdit).find("input[name='sampleletterid']").val(letterId);
                    $(modalEdit).find("input[name='sampleid']").val(data.sampleid);
                    $(modalEdit).find("input[name='laneusage']").val(data.laneusage);
                    $(modalEdit).find("input[name='volume']").val(data.volume);
                    $(modalEdit).find("select[name='organism']").val(data.organism);
                    $(modalEdit).find("input[name='treatment']").val(data.treatment);
                    $(modalEdit).find("input[name='platformid']").val(data.platformid);
                    $(modalEdit).find("input[name='position']").val(data.position);
                    $(modalEdit).find("input[name='barcode']").val(data.barcode);
                    $(modalEdit).find("select[name='application']").val(data.application);
                    $(modalEdit).find("input[name='cellline']").val(data.cellline);
                    $(modalEdit).find("input[name='timepoint']").val(data.timepoint);
                    $(modalEdit).find("input[name='comment']").val(data.comment);
                    $(modalEdit).find("input[name='antibody']").val(data.antibody);
                    /*$(modalEdit).find("input[name='']").val();
                    $(modalEdit).find("input[name='']").val();*/
                    //$(modalEdit).find("input[name='owner-id']").val();

                    // Remove eventual errors displayed (if the user did not fill the fields and close the modal)
                    $(modalEdit).find(".help-block").each(function() {
                        $(this).remove();
                    });

                    // Remove the has-error class (still in case of previous errors)
                    $(modalEdit).find(".form-group").each(function() {
                        if ($(this).hasClass("has-error")) {
                            $(this).removeClass("has-error");
                        }
                    });

                    // Hide the alert
                    $(modalEdit).find('.alert').hide();

                    attachments = $(modalEdit).find(".attachments");
                    selectHTML = $(attachments).find("select").first().html();
                    // Empty the div
                    $(attachments).empty();

                    $.each(data.files, function(index, value) {
                        var newFormGroup, selectName;

                        if (index === 0) {
                            selectName = "file";
                        } else {
                            selectName = "file" + (index + 1);
                        }
                        newFormGroup = '<div class="form-group"><select class="form-control" name="' + selectName + '">'+ selectHTML +'</select></div>';

                        // Add the newly created form-group with the select inside
                        attachments.append(newFormGroup);

                        // Set the select to the current file
                        attachments.find("[name=" + selectName + "]").val(value[0]).rules("add", {
                            required: true
                        });
                    });

                    if (data.files.length > 1) {
                        $(modalEdit).find(".btn-del-file").removeAttr("disabled");
                    }
                });
            }

            // Button to show links
            $(row).find(".btn-show-links").click(function () {
                var files = data.files,
                    modalBody = $('#show-links-modal').find('.modal-body');

                modalBody.empty();
                $.each(files, function(index, value) {
                    var file = value[1];
                    modalBody.append('<div class="form-group"><div class="input-group"><input type="text" class="form-control" value="' + file.split('_')[1] +'" disabled><span class="input-group-addon"><a href="/files/'+ file +'"><span class="glyphicon glyphicon glyphicon-download"></span> Download</a></span></div></div>');
                });
            });

            $(row).addClass(coloursClass[data.status]);
        }
    }).fnSetFilteringDelay(); // Enable filtration delay

    var scrolls = $("#samples").find(".dataTables_scrollHead, .dataTables_scrollBody");

    // Add an horizontal scrollbar under the table header (so above the table doy)
    $(scrolls[0]).css("overflow", "auto");

    // Synchronize the top scrollbar with the bottom one
    $(scrolls[0]).scroll(function(){
        $(scrolls[1]).scrollLeft($(scrolls[0]).scrollLeft());
    });
} );
