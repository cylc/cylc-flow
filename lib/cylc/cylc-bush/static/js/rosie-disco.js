/******************************************************************************
 * (C) British crown copyright 2012-7 Met Office.
 *
 * This file is part of Rose, a framework for scientific suites.
 *
 * Rose is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * Rose is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with Rose. If not, see <http://www.gnu.org/licenses/>.
 *
 ******************************************************************************/
var Rosie = {};
Rosie.cookie_get = function(name) {
    var cookies = document.cookie.split("; ");
    var value = null;
    $.each(cookies, function(i, item) {
        var pair = item.split("=");
        if (pair[0] == name) {
            value = unescape(pair[1]);
            return false;
        }
    });
    return value;
};
Rosie.cookie_set = function(name, value) {
    document.cookie = name + "=" + escape(value);
};
Rosie.query = function() {
    var q = "";
    var q_ubound = 0;
    var q_open_groups = 0;
    $("#query-table > tbody > tr").each(function(i) {
        if (i > q_ubound) {
            q_ubound = i;
        }
        var row = $(this);
        var conjunction = $(".q_conjunction", row).val();
        var group0 = $(".q_group0", row).val();
        var key = $(".q_key", row).val();
        var operator = $(".q_operator", row).val();
        var value = encodeURIComponent($(".q_value", row).val());
        var group1 = $(".q_group1", row).val();
        if (i != 0) {
            q += "&";
        }
        var filter_list = [conjunction, key, operator, value];
        if (group0) {
            filter_list.splice(1, 0, group0);
            q_open_groups += group0.length
        }
        if (group1) {
            filter_list.push(group1);
            q_open_groups -= group1.length
        }
        q += "q=" + filter_list.join("+");
        var suffix = row.attr("id").substr(1);
    });
    if ($("#query-all").attr("checked")) {
        q += "&all_revs=1"
    }
    if (q_open_groups != 0) {
        alert("Parenthesis error");
        return
    }
    location = "query?" + q;
};
Rosie.query_add = function() {
    var tbody = $("#query-table tbody");
    var rows = $("> tr", tbody);
    var row = rows.last().clone().appendTo(tbody);
    var index = (Number(rows.last().attr("id").substr(2)) + 1).toString();
    row.attr("id", "q_" + index);

    $("select, input", row).each(function() {
        $(this).attr("name", $(this).attr("class") + "_" + index);
    });

    $("select", row).removeAttr("disabled");
    $("button", row).click(Rosie.query_remove);
    $("> tr button", tbody).removeAttr("disabled");
};
Rosie.query_reset = function() {
    var rows = $("#query-table > tbody > tr");
    $("button", rows).click(Rosie.query_remove);
    $(".q_conjunction", rows.first()).attr("disabled", "disabled");
    if (rows.length == 1) {
        rows.first().find("button").prop("disabled", "disabled");
    }
};
Rosie.query_remove = function() {
    $(this).closest("tr").remove();
    Rosie.query_reset();
};
Rosie.query_groups_toggle = function (event_obj) {
    var tbody = $("#query-table tbody");
    var control = $("#show-groups");
    var show_groups = null;
    if (event_obj == null) {
        if (location.search.indexOf("(") > -1) {
            control.button("toggle");
        }
        else {
            control.button("reset");
        }
        show_groups = control.hasClass("active");
        control.click(Rosie.query_groups_toggle);
    }
    else {
        show_groups = !control.hasClass("active");
    }
    $("#query-table > tbody > tr").each(function(i) {
        var row = $(this);
        var group0 = $(".q_group0", row);
        var group1 = $(".q_group1", row);
        if (show_groups) {
            group0.show();
            group1.show();
        }
        else {
            group0.hide();
            group1.hide();
        }
    });
};
Rosie.show = function(method) {
    $("." + method + "-button").siblings().removeClass("active");
    $("." + method + "-button").addClass("active");
    $("#" + method).show();
    $("form[id!=" + method + "]").hide()
};
$(function() {
    $("#list-result-table").dataTable({
        /* "dom": "C<\"clear\">lfrtip", */
        "info": false,
        "paging": false,
        "searching": false
    });
    var pathnames = location.pathname.split("/");
    var method = pathnames.pop();
    var prefix = pathnames.pop();
    if (location.search.length > 0) {
        Rosie.show(method);
        if (method == "search" || method == "query") {
            Rosie.cookie_set("prev." + prefix, method + location.search);
        }
    }
    else {
        Rosie.show("search");
        if (prefix) {
            var prev = Rosie.cookie_get("prev." + prefix);
            if (prev) {
                location = prev;
            }
        }
    }
    Rosie.query_groups_toggle();
    Rosie.query_reset();
    $(".infotip").popover();
});
