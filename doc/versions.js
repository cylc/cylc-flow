/* global CUR_VERSION, ROOT_DIR, PAGE_NAME, CUR_FORMAT */
// these variables come from versions.html in the Sphinx theme

$('#versions-and-formats')
    .append(
        $('<span />')
            .addClass('rst-current-version')
            .attr({'data-toggle': 'rst-current-version'})
            .append(
                $('<span />')
                    .addClass('fa fa-book')
                    .append('Versions'),
                $('<span />').append('v: ' + CUR_VERSION),
                $('<span />')
                    .addClass('fa fa-caret-down')
            ),
        $('<div />')
            .addClass('rst-other-versions')
            .attr({'id': 'versions'})
            .append(
                $('<h4 />')
                    .append('Versions')
            ),
        $('<div />')
            .addClass('rst-other-versions')
            .attr({'id': 'formats'})
            .append(
                $('<h4 />')
                    .append('Formats')
            )
    )

// path to JSON file with versions and formats dictionary
const VERSIONS_URL = ROOT_DIR + '/versions.json';

function url(version, format) {
    // return the URL of the curret page in the documentation
    var ret = ROOT_DIR + '/' + version + '/' + format + '/';
    if (format === 'html') {
        ret += PAGE_NAME + '.html';
    } else if (format === 'singlehtml') {
        ret += 'index.html#document-' + PAGE_NAME;
    } else if (format === 'epub') {
        ret += 'Cylc.epub';
    } else if (format == 'latex') {
        ret += 'cylc.pdf'
    } else {
        ret += 'index.html';
    }
    return ret
}

$(document).ready(function() {
    const version_div = $('#versions');
    const format_div = $('#formats')

    $.ajax({
        'type': 'GET',
        'url': VERSIONS_URL,
        dataType: 'json',
        success: function (versions) {
            console.log(`versions: ${versions}, cur: ${CUR_VERSION}`);
            console.log(versions)

            // write list versions (for all formats)
            var vn_fmt;
            for (let version of Object.keys(versions).sort()) {
                if (versions[version].indexOf(CUR_FORMAT) === -1) {
                    vn_fmt = 'html';  // fallback to html
                } else {
                    vn_fmt = CUR_FORMAT;  // link current format
                }
                version_div.append(
                    $('<a />')
                        .attr({'href': url(version, vn_fmt)})
                        .css({'padding-left': '1em'})
                        .append(version)
                );
            }

            // write formats for current version
            for (let format of versions[CUR_VERSION]) {
                format_div.append(
                    $('<a />')
                        .attr({'href': url(CUR_VERSION, format)})
                        .css({'padding-left': '1em'})
                        .append(format)
                );
            }
        }
    });
});
