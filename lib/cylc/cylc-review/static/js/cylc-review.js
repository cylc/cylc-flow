/******************************************************************************
 * THIS FILE IS PART OF THE CYLC SUITE ENGINE.
 * Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 ******************************************************************************/
$(function() {
    $(".collapse").collapse();
    $(".livestamp").each(function() {
        $(this).livestamp($(this).attr("title"));
    });
    $(".entry select.seq_log").change(function() {
        this.form.submit();
    });
    var dt_as_m_and_s = function(dt) {
        var s = dt.seconds();
        if (s < 10) {
            s = "0" + s.toString();
        }
        else {
            s = s.toString();
        }
        var m = Math.floor(dt.asMinutes());
        return m.toString() + ":" + s;
    }

    var toggle_fuzzy_time_init = true;
    var toggle_fuzzy_time = function() {
        var state = $("#toggle-fuzzy-time").attr("data-no-fuzzy-time");
        if (toggle_fuzzy_time_init) {
            state = (state == "0") ? "1" : "0";
        }
        toggle_fuzzy_time_init = false;
        if (state == "1") {
            $("form input[name='no_fuzzy_time']").attr("value", "0");
            $("#toggle-fuzzy-time").attr("data-no-fuzzy-time", "0");
            $(".livestamp").each(function() {
                $(this).livestamp($(this).attr("title"));
            });
            $(".job-entry-head-init-time").html("queue \&Delta;t");
            $(".job-entry-head-exit-time").html("run \&Delta;t");
            $(".entry").each(function() {
                var s_init = $(".t_init", this).attr("title");
                if (s_init == null) {
                    return;
                }
                var s_submit = $(".t_submit", this).attr("title");
                var m_submit = moment(s_submit);
                var m_init = moment(s_init);
                if (m_init.isBefore(m_submit)) {
                    m_init = m_submit;
                }
                var dt_q = moment.duration(m_init.diff(m_submit));
                $(".t_init", this).text(dt_as_m_and_s(dt_q));
                var s_exit = $(".t_exit", this).attr("title");
                if (s_exit == null) {
                    return;
                }
                var m_exit = moment(s_exit);
                if (m_exit.isBefore(m_init)) {
                    m_exit = m_init;
                }
                var dt_r = moment.duration(m_exit.diff(m_init));
                $(".t_exit", this).text(dt_as_m_and_s(dt_r));
            });
            $("#toggle-fuzzy-time").addClass("active");
        }
        else {
            $("form input[name='no_fuzzy_time']").attr("value", "1");
            $("#toggle-fuzzy-time").attr("data-no-fuzzy-time", "1");
            $(".livestamp").each(function() {
                $(this).livestamp("destroy");
            });
            $(".job-entry-head-init-time").text("start time");
            $(".job-entry-head-exit-time").text("exit time");
            $(".entry").each(function() {
                var s_init = $(".t_init", this).attr("title");
                if (s_init == null) {
                    return;
                }
                var m_submit = moment($(".t_submit", this).attr("title"));
                var m_init = moment(s_init);
                if (m_init.isSame(m_submit, "day")) {
                    m_init.utc();
                    s_init = m_init.format("HH:mm:ss");
                }
                $(".t_init", this).text(s_init);
                var s_exit = $(".t_exit", this).attr("title");
                if (s_exit == null) {
                    return;
                }
                var m_exit = moment(s_exit);
                if (m_exit.isSame(m_submit, "day")) {
                    m_exit.utc();
                    s_exit = m_exit.format("HH:mm:ss");
                }
                $(".t_exit", this).text(s_exit);
            });
            $("#toggle-fuzzy-time").removeClass("active");
        }
    }
    toggle_fuzzy_time();
    $("#toggle-fuzzy-time").click(toggle_fuzzy_time);
    $("#page").change(function() {
        this.form.submit();
    });
    $("#page-next").click(function() {
        $("#page").prop("selectedIndex", $("#page").prop("selectedIndex") + 1);
    });
    $("#page-prev").click(function() {
        $("#page").prop("selectedIndex", $("#page").prop("selectedIndex") - 1);
    });
    $("#per_page_max").click(function() {
        $("#per_page").prop("disabled", $(this).prop("checked"));
    });
    $("#uncheck_task_statuses").click(function() {
        $("input.task_status").prop("checked", false);
    });
    $("#check_task_statuses").click(function() {
        $("input.task_status").prop("checked", true);
    });
    $("#reset_task_statuses").click(function() {
        // default task statuses - if updating please also change the
        // def taskjobs function in review.py
        $("input.task_status").prop("checked", true);
        $("input.task_status[value=waiting]").prop("checked", false);
    });
});
