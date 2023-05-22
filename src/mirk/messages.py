# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+


import laniakea.typing as T

__all__ = ['message_templates', 'message_prestyle_event_data', 'render_template_colors']


COLORS = [
    ('green', '#27ae60'),
    ('orange', '#f39c1f'),
    ('red', '#da4453'),
    ('purple', '#8e44ad'),
    ('lbgrey', '#34495e'),
    ('bgrey', '#2c3e50'),
    ('dgrey', '#31363b'),
]


def render_template_colors(template: str) -> str:
    """Replace color tags with their HTML equivalents."""
    result = template
    for cname, ccode in COLORS:
        result = result.replace('<%s>' % cname, '<font color="%s">' % ccode)
        result = result.replace('</%s>' % cname, '</font>')
    return result


def message_prestyle_event_data(data):
    '''
    Invoked at the very start and allows styling some aspects
    of the data already.
    '''

    def lbgrey(m):
        return '<font color="#34495e">%s</font>' % m

    def dgrey(m):
        return '<font color="#31363b">%s</font>' % m

    # color all version numbers the same way
    if 'version' in data:
        data['version'] = lbgrey(data['version'])
    if 'version_new' in data:
        data['version_new'] = lbgrey(data['version_new'])
    if 'version_old' in data:
        data['version_old'] = lbgrey(data['version_old'])
    if 'version_src' in data:
        data['version_src'] = lbgrey(data['version_src'])
    if 'version_dest' in data:
        data['version_dest'] = lbgrey(data['version_dest'])

    # prefix all architectures with a gear
    if 'architecture' in data:
        data['architecture'] = dgrey('\N{GEAR}' + data['architecture'])
    if 'job_architecture' in data:
        data['job_architecture'] = dgrey('\N{GEAR}' + data['job_architecture'])
    if 'architectures' in data:
        data['architectures'] = dgrey('\N{GEAR}' + ', \N{GEAR}'.join(a for a in data['architectures']))

    return data


#
# Templates for jobs
#

templates_jobs = {
    '_lk.jobs.job-assigned': (
        'Assigned {job_kind} job <a href="{url_webview}/jobs/job/{job_id}">{job_id:11.11}</a> '
        'on architecture {job_architecture} to <em>{client_name}</em>'
    ),
    '_lk.jobs.job-accepted': (
        'Job <a href="{url_webview}/jobs/job/{job_id}">{job_id:11.11}</a> was <green>accepted</green> '
        'by <em>{client_name}</em>'
    ),
    '_lk.jobs.job-rejected': (
        'Job <a href="{url_webview}/jobs/job/{job_id}">{job_id:11.11}</a> was <red>rejected</red> '
        'by <em>{client_name}</em>'
    ),
    '_lk.jobs.job-finished': (
        'Job <a href="{url_webview}/jobs/job/{job_id}">{job_id:11.11}</a> finished with result <em>{result}</em>'
    ),
}

#
# Templates for Synchrotron
#


def pretty_package_imported(tag, data):
    info = 'package <b>{name}</b> from {src_os} <em>{suite_src}</em> → <em>{suite_dest}</em>, new version is {version}.'.format(
        **data
    )
    if data.get('forced'):
        return 'Enforced import of ' + info
    else:
        return 'Imported ' + info


templates_synchrotron = {
    '_lk.synchrotron.src-package-imported': pretty_package_imported,
    '_lk.synchrotron.new-autosync-issue': (
        'New automatic synchronization issue for <red><b>{name}</b></red> from {src_os} '
        '<em>{suite_src}</em> → <em>{suite_dest}</em> (source: {version_src}, '
        'destination: {version_dest}). Type: {kind}'
    ),
    '_lk.synchrotron.resolved-autosync-issue': (
        'The <em>{kind}</em> synchronization issue for <b>{name}</b> from {src_os} '
        '<em>{suite_src}</em> → <em>{suite_dest}</em> was <green>resolved</green>.'
    ),
}


#
# Templates for Rubicon
#


def pretty_job_upload_accepted(tag, data):
    if data.get('job_failed'):
        tmpl = 'Accepted upload for <red>failed</red> job <a href="{url_webview}/jobs/job/{job_id}">{job_id:11.11}</a>.'
    else:
        tmpl = (
            'Accepted upload for <green>successful</green> '
            'job <a href="{url_webview}/jobs/job/{job_id}">{job_id:11.11}</a>.'
        )
    return render_template_colors(tmpl).format(**data)


templates_rubicon = {
    '_lk.rubicon.job-upload-accepted': pretty_job_upload_accepted,
    '_lk.rubicon.job-upload-rejected': '<b>Rejected</b> upload <code>{dud_filename}</code>. Reason: <code>{reason}</code>',
}


#
# Templates for Isotope
#


templates_isotope = {
    '_lk.isotope.recipe-created': (
        'Created new <code>{format}</code> image build recipe <code>{name}</code> for {distribution} <b>{suite}</b>, '
        '<b>{environment}</b> environment and style <b>{style}</b> on {architectures}'
    ),
    '_lk.isotope.build-job-added': (
        'Created <code>{format}</code> image build job on {architecture} for {distribution} <b>{suite}</b> using the '
        '<b>{environment}</b> environment and style <b>{style}</b>. '
        '| <a href="{url_webview}/jobs/job/{job_id}">\N{CIRCLED INFORMATION SOURCE}</a>'
    ),
    '_lk.isotope.image-build-failed': (
        'A <code>{format}</code> image for {distribution} <red>failed</red> '
        'to build for <b>{suite}</b>, environment '
        '<b>{environment}</b>/{style} on {architecture}. '
        '| <a href="{url_webview}/jobs/job/{job_id}">\N{CIRCLED INFORMATION SOURCE}</a>'
    ),
    '_lk.isotope.image-build-success': (
        'A <code>{format}</code> image for {distribution} was built <green>successfully</green> for <b>{suite}</b>, '
        'environment <b>{environment}</b>/{style} on {architecture}. '
        'The image has been <green>published</green> for download.'
        ' | <a href="{url_webview}/jobs/job/{job_id}">\N{CIRCLED INFORMATION SOURCE}</a>'
    ),
}


#
# Templates for the Archive
#


def pretty_source_package_published(tag, data):
    data['suites_str'] = ', '.join(data['suites'])

    tmpl = (
        'Source package <b>{name}</b> {version} was <green>published</green> in the archive, available in suites '
        '<em>{suites_str}</em> <bgrey><em>[{component}]</em></bgrey>.'
    )
    if data['suites']:
        first_suite = data['suites'][0]
        tmpl = tmpl + (
            ' | <a href="{url_webswview}/package/src/'
            + first_suite
            + '/{name}'
            + '">\N{CIRCLED INFORMATION SOURCE}</a>'
            ' <a href="{url_webview}/raw/changelogs/{component}/{name:1.1}/{name}/'
            + data['suites'][0]
            + '_changelog">\N{DOCUMENT}</a>'
        )

    return render_template_colors(tmpl).format(**data)


def pretty_binary_package_published(tag, data):
    data['suites_str'] = '; '.join(data['suites'])

    tmpl = (
        'Binary package <b>{name}</b> {version} from <b>'
        '<bgrey>{source_name}</bgrey></b> was <green>published</green> in the archive '
        'for {architecture} in suite <em>{suites_str}</em> <bgrey><em>[{component}]</em></bgrey>.'
    )
    if data['suites']:
        first_suite = data['suites'][0]
        tmpl = tmpl + (
            ' | <a href="{url_webswview}/package/bin/'
            + first_suite
            + '/{name}'
            + '">\N{CIRCLED INFORMATION SOURCE}</a>'
            ' <a href="{url_webview}/raw/changelogs/{component}/{source_name:1.1}/{source_name}/'
            + first_suite
            + '_changelog">\N{DOCUMENT}</a>'
        )

    return render_template_colors(tmpl).format(**data)


def pretty_package_upload_accepted(tag, data):
    data['changes'] = data['changes'].strip().replace('\n', '<br/>')
    if data['is_new']:
        if 'source_name' in data:
            tmpl = (
                'Accepted upload <code>{upload_name}</code> by <em>{uploader_name}</em> containing <b>{source_name}</b>/{source_version} '
                'into the <purple>review queue</purple> for {repo}. '
                'Changes:<br/><blockquote>{changes}</blockquote>'
                '<purple>Review</purple> the upload <a href="{url_webview}/review">here</a>'
            )
        else:
            tmpl = (
                'Accepted upload <code>{upload_name}</code> by <em>{uploader_name}</em> into the '
                '<purple>review queue</purple> for {repo}. '
                '<purple>Review</purple> the upload <a href="{url_webview}/review">here</a>'
            )
    else:
        if 'source_name' in data:
            tmpl = (
                '<green>Accepted</green> source upload <code>{upload_name}</code> by <em>{uploader_name}</em> containing '
                '<b>{source_name}</b>/{source_version} into {repo}. '
                'Changes:<br/><blockquote>{changes}</blockquote>'
            )
        else:
            tmpl = '<green>Accepted</green> upload <code>{upload_name}</code> by <em>{uploader_name}</em> into {repo}.'
    return render_template_colors(tmpl).format(**data)


def pretty_package_upload_rejected(tag, data):
    if 'uploader_name' in data:
        tmpl = (
            '<red>Rejected</red> upload <code>{upload_name}</code> by <em>{uploader_name}</em> for {repo}. '
            'Reason:<br/><blockquote>{reason}</blockquote>'
        )
    else:
        tmpl = (
            '<red>Rejected</red> upload <code>{upload_name}</code> for {repo}. '
            'Reason:<br/><blockquote>{reason}</blockquote>'
        )
    return render_template_colors(tmpl).format(**data)


templates_archive = {
    '_lk.archive.package-build-success': (
        'Package build for <b>{pkgname}</b> {version} on {architecture} in {repo}:<em>{suite}</em> was '
        '<green>successful</green>. '
        '| <a href="{url_webswview}/package/builds/job/{job_id}">\N{CIRCLED INFORMATION SOURCE}</a>'
    ),
    '_lk.archive.package-build-failed': (
        'Package build for <b>{pkgname}</b> {version} on {architecture} in {repo}:<em>{suite}</em> has <red>failed</red>. '
        '| <a href="{url_webswview}/package/builds/job/{job_id}">\N{CIRCLED INFORMATION SOURCE}</a>'
    ),
    '_lk.archive.package-build-depwait': (
        'Package build for <b>{pkgname}</b> {version} on {architecture} in {repo}:<em>{suite}</em> is '
        '<orange>waiting for a dependency</orange>. '
        '| <a href="{url_webswview}/package/builds/job/{job_id}">\N{CIRCLED INFORMATION SOURCE}</a>'
    ),
    '_lk.archive.binary-package-published': pretty_binary_package_published,
    '_lk.archive.source-package-published': pretty_source_package_published,
    '_lk.archive.source-package-published-in-suite': (
        'Source package <b>{name}</b> {version} was '
        '<green>added</green> to suite <em>{suite_new}</em> <bgrey><em>[{component}]</em></bgrey>.'
    ),
    '_lk.archive.source-package-suite-removed': (
        'Source package <b>{name}</b> {version} was '
        '<red>removed</red> from suite <em>{suite_old}</em> <bgrey><em>[{component}]</em></bgrey>.'
    ),
    '_lk.archive.removed-source-package': (
        'Package <b>{name}</b> {version} '
        '<bgrey><em>[{component}]</em></bgrey> was <orange>removed</orange> from the archive.'
    ),
    '_lk.archive.package-src-suite-deleted': (
        'Source package <b>{pkg_name}/{pkg_version}</b> was <orange>deleted</orange> from <em>{suite}</em> in <em>{repo}</em>.'
    ),
    '_lk.archive.package-src-marked-removal': (
        'Source package <b>{pkg_name}/{pkg_version}</b> was <orange>marked for removal</orange> in <em>{repo}</em>.'
    ),
    '_lk.archive.package-src-removed': (
        'Source package <b>{pkg_name}/{pkg_version}</b> was <red>deleted</red> from <em>{repo}</em>.'
    ),
    '_lk.archive.package-src-copied': (
        'Copied source package <b>{pkg_name}/{pkg_version}</b> in <em>{repo}</em> to suite <b>{dest_suite}</b>.'
    ),
    '_lk.archive.package-upload-accepted': pretty_package_upload_accepted,
    '_lk.archive.package-upload-rejected': pretty_package_upload_rejected,
}


#
# Templates for Spears
#


def pretty_excuse_change(tag, data):
    removal = False
    if data.get('version_new') == '-':
        data['version_new'] = '(<red>removal</red>)'
        removal = True

    if tag == '_lk.spears.new-excuse':
        if data.get('version_old') == '-':
            old_ver_info = 'Package is <green>new</green> to target!'
        else:
            old_ver_info = 'Version in target is: {version_old}'

        suites_source_str = ' & '.join(data['suites_source'])
        tmpl = (
            'Package <b>{source_package}</b> {version_new} was '
            '<red>blocked</red> from its <em>' + suites_source_str + '</em> → <em>{suite_target}</em> '
            'migration. '
            + old_ver_info
            + ' | <a href="{url_webview}/migrations/excuse/{uuid}">\N{CIRCLED INFORMATION SOURCE}</a>'
        )

    elif tag == '_lk.spears.excuse-removed':
        tmpl = 'Migration excuse for package <b>{source_package}</b> {version_new} was <green>invalidated</green>.'
        if removal:
            tmpl = (
                tmpl + ' The package is now deleted from <em>{suite_target}</em>. Previous version was: {version_old}'
            )
        else:
            if data.get('version_old') == '-':
                old_ver_info = 'This package is <green>new</green> in <em>{suite_target}</em>.'
            else:
                old_ver_info = 'Previous version in target was: {version_old}'

            suites_source_str = ' & '.join(data['suites_source'])
            tmpl = (
                tmpl
                + ' The package migrated from <em>'
                + suites_source_str
                + '</em> → <em>{suite_target}</em>. '
                + old_ver_info
            )
    else:
        raise ValueError('Found unknown Spears issue tag: {}'.format(tag))

    return render_template_colors(tmpl).format(**data)


templates_spears = {'_lk.spears.new-excuse': pretty_excuse_change, '_lk.spears.excuse-removed': pretty_excuse_change}

#
# Templates for Debcheck
#


def pretty_debcheck_issue_change(tag, data):
    if tag == '_lk.debcheck.issue-resolved':
        tmpl = (
            'Dependency issue for <em>{package_type}</em> package <b>{package_name}</b> {package_version} on '
            '\N{GEAR}{architectures} in <em>{repo}</em> <b>{suite}</b> was <green>resolved</green> 🎉'
        )
    elif tag == '_lk.debcheck.issue-found':
        tmpl = (
            'Found <red>new dependency issue</red> '
            'for <em>{package_type}</em> package <b>{package_name}</b> {package_version} on '
            '{architectures} in <em>{repo}</em> <b>{suite}</b> '
            '| <a href="{url_webview}/depcheck/{repo}/{suite}/issue/{uuid}">\N{CIRCLED INFORMATION SOURCE}</a>'
        )
    elif tag == '_lk.debcheck.check-completed':
        if data['new_issues_count'] == 0 and data['resolved_issues_count'] == 0:
            return
        tmpl = (
            'Dependency check for <em>{package_type}</em> packages in <em><b>{repo}<b></em>/<b>{suite}</b> completed:<br/>'
            '<green>{resolved_issues_count}</green> issues were resolved, <red>{new_issues_count}</red> new issues were found. '
            '| <a href="{url_webview}/depcheck/{repo}/{suite}/{package_type}">\N{CIRCLED INFORMATION SOURCE}</a>'
        )
    else:
        raise ValueError('Found unknown Debcheck issue tag: {}'.format(tag))

    return render_template_colors(tmpl).format(**data)


templates_debcheck = {
    '_lk.debcheck.issue-resolved': pretty_debcheck_issue_change,
    '_lk.debcheck.issue-found': pretty_debcheck_issue_change,
    '_lk.debcheck.check-completed': pretty_debcheck_issue_change,
}


#
# Assemble complete template set
#
message_templates: dict[str, T.Any] = {}
message_templates.update(templates_jobs)
message_templates.update(templates_synchrotron)
message_templates.update(templates_rubicon)
message_templates.update(templates_isotope)
message_templates.update(templates_archive)
message_templates.update(templates_spears)
message_templates.update(templates_debcheck)
