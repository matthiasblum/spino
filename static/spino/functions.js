function isValidDate(value) {
    /**
     * Check if a date is valid or not (input format: YYYY-MM-DD)
     * @type {Array|{index: number, input: string}|st.selectors.match|*|bc.selectors.match|m.selectors.match|fb.selectors.match}
     */
    var dtArray = value.match(/^(\d{4})-(\d{2})-(\d{2})$/);

    if (dtArray === null) {
        return false;
    }

    // dtArray should be like: ["2013-11-14", "2013", "11", "14"]
    var dtYear = parseInt(dtArray[1], 10),
        dtMonth = parseInt(dtArray[2], 10),
        dtDay = parseInt(dtArray[3], 10);

    if (dtMonth < 1 || dtMonth > 12) {
        return false;
    } else if (dtDay < 1 || dtDay > 31) {
        return false;
    } else if ((dtMonth === 4 || dtMonth === 6 || dtMonth === 9 || dtMonth === 11) && dtDay === 31) {
        return false;
    } else if (dtMonth === 2) {
        var isLeap = (dtYear % 4 == 0 && (dtYear % 100 != 0 || dtYear % 400 == 0));

        if (dtDay > 29 || (dtDay === 29 && ! isLeap)) {
            return false;
        }
    }
    return true;
}

function isValidDivision(value) {
    /**
     * Check if the given value is a proper division (and its result is not greather than two)
     * @type {Array|{index: number, input: string}|st.selectors.match|*|bc.selectors.match|m.selectors.match|fb.selectors.match}
     */
    var intArr = value.match(/^(\d+)\/(\d+)$/);

    if (intArr === null) {
        return false;
    }

    var i = parseInt(intArr[1], 10),
        j = parseInt(intArr[2], 10),
        k = i / j;

    return !(k === 0 || k > 2);
}

function isValidSampleId(value) {
    return /^\d{6}-[a-zA-Z]$/.test(value);
}

function setSampleID(dtArray, letter, sampleIdElt) {
    /**
     * Change the value of the given element to the sample ID (composed of a date and a letter)
     */
    var sampleId;

    if (letter.length && dtArray !== null) {
        sampleId = dtArray[3].concat(dtArray[2], dtArray[1].substr(2), '-', letter);
    } else {
        sampleId = null;
    }

    sampleIdElt.val(sampleId);
    return sampleId;
}

function removeDuplicates(sortedArray) {
    var array = [];

    for (var i = 0, j = sortedArray.length; i < j; i += 1) {
        if (i === 0) {
            array.push(sortedArray[i]);
        } else if (sortedArray[i] !== sortedArray[i-1]) {
            array.push(sortedArray[i]);
        }
    }
    return array;
}

function setStatus(newStatus) {
    var params = $("#samples").serializeArray(),
        strParams = '';

    $.each(params, function(index, field) {
        if (field.name === "setstatus") {
            strParams += "id=" + field.value + '&';
        }
    });
    if (strParams.length) {
        strParams += "status=" + newStatus;
        $.ajax({
            url: "/samples/status",
            type: "post",
            data: strParams,
            success: function(response) {
                if (response === "0") {
                    $('#table-samples').DataTable().ajax.reload();  // Reload the table with the new sample
                }
            }
        });
    }

}