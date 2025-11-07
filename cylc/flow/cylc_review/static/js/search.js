/******************************************************************************
 * THIS FILE IS PART OF THE CYLC SUITE ENGINE.
 * Copyright (C) NIWA & British Crown (Met Office) & Contributors.
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
var FileLoader = ( function () {
    // wrapper to highlight the selected line
    var mark = ['<span class="highlight">', '</span>'];
    var previous_search = null;
    var previous_mode = null;

    var user = null;
    var suite = null;
    var path = null;
    var path_in_tar = null;
    var mode = null;


    var loadFile = function (search_string, goto) {
        /* Loads in a file from the provided url, populates the line
         * numbers and scrolls to the goto line is provided. */

        // detect search mode
        var search_mode = $(document.forms['file-search']['search-mode']).val();
        // get script path
        var script_path = $(document.forms['file-search']['script']).val();
        // update previous search
        previous_search = search_string;
        previous_mode = search_mode;
        // the search url
        var url = script_path + '/viewsearch/' + user;
        // search data
        var kwargs = {'suite': suite, 'path': path, 'path_in_tar': path_in_tar,
                'search_string': search_string, 'search_mode': search_mode,
                'mode': mode};
        // args passed as strings so remove null, 'None' values here
        $.each(kwargs, function (key, value) {
            if (value == 'None' || !value) {
                delete kwargs[key];
            }
        });

        // asynchronously load file
        $.ajax({
            method: 'POST',
            url: url,
            data: kwargs,
            success: function (result) {
                $('#file-container').html(result);
                bindLineNumbers();
                if (goto) {
                    selectLine(goto);
                }
                if (typeof prettyPrint != 'undefined') {
                    $(prettyPrint);
                }
            },
            error: function (error) {
                alert('Search failed!\nCheck that you entered a valid search ' +
                    'string.');
            }
        });
    };


    this.selectLine = function (num) {
        /* Highlights and scrolls to the line of code with the provided
        * number. */
        num = parseInt(num);

        if (previous_search) {
            loadFile("", num);
            return;
        }

        // Remove previously highlighted lines.
        var highlights = $($('#filecode')[0]).find('span.highlight');
        for (high=0; high<highlights.length; high++) {
            $(highlights[high]).replaceWith(highlights[high].innerHTML);
        }

        // Extract text lines from document
        var lines = $('#filecode')[0].innerHTML.split('\n');

        // Mark highlighted line.
        lines[num - 1] = mark[0] + lines[num - 1] + mark[1];

        // Set filecode html content.
        $('#filecode').html(lines.join('\n'));

        // scroll to selected line
        $('html, body').animate({scrollTop: $('#' + num).offset().top}, 500);
    };


    this.fileSearch = function () {
        /* Called on submit by form:file_search to initiate a search. */
        var search_string = document.forms['file-search']['search-string'].value;
        var search_mode = $(document.forms['file-search']['search-mode']).val();
        if (search_string === previous_search &&
                search_mode === previous_mode) {
            return false;
        }
        if (search_string !== "" && search_string !== null) {
            loadFile(search_string);
        } else {
            loadFile("");
        }
        return false;
    };


    this.init = function () {
        var form = document.forms['file-search'];
        user = form['user'].value;
        suite = form['suite'].value;
        path = form['path'].value;
        path_in_tar = form['path_in_tar'].value;
        mode = form['mode'].value;
    };


    this.bindLineNumbers = function () {
        /* Attatch handler on .line-number to goto the selected line number
         * when clicked. */
        $('.line-number').on('click', function () {
            FileLoader.selectLine(parseFloat($(this).attr('id')));
        });
    }


    var self = {
        /* Export public functions. */
        selectLine: this.selectLine,
        fileSearch: this.fileSearch,
        init: this.init,
        bindLineNumbers: this.bindLineNumbers
    };


    return self;

})();


$(function () {
    // load file once all resources (incl FileLoader) have been obtained
    FileLoader.init();
    FileLoader.bindLineNumbers();
    $('form[name="file-search"]').on('submit', function () {
        return FileLoader.fileSearch();
    });

    // search - mode option default value
    var ele = $($('form[name=file-search] .toggle-selector li a')[0]);
    $('form[name=file-search]').find('button span.toggle-target')
            .html(ele.html());
    $(document.forms['file-search']['search-mode']).val(ele.data('value'));

    // scroll to line if specified in URL
    $(document).ready(function (){
        var hash = window.location.hash;
        if (hash) {
            FileLoader.selectLine(hash.split('#')[1]);
        }
    });
});


// search - mode option dropdown
$('form[name=file-search]').find('.toggle-selector li a')
        .on('click', function () {
    var ele = $(this);
    $('form[name=file-search]').find('button span.toggle-target')
            .html(ele.html());
    $(document.forms['file-search']['search-mode']).val(ele.data('value'));
});
