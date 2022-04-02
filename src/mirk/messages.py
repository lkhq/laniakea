# -*- coding: utf-8 -*-
#
# Copyright (C) 2018-2022 Matthias Klumpp <matthias@tenstral.net>
#
# SPDX-License-Identifier: LGPL-3.0+


__all__ = ['message_templates', 'message_prestyle_event_data']


def green(m):
    return '<font color="#27ae60">{}</font>'.format(m)


def orange(m):
    return '<font color="#f39c1f">{}</font>'.format(m)


def red(m):
    return '<font color="#da4453">{}</font>'.format(m)


def purple(m):
    return '<font color="#8e44ad">{}</font>'.format(m)


def lbgrey(m):
    return '<font color="#34495e">{}</font>'.format(m)


def bgrey(m):
    return '<font color="#2c3e50">{}</font>'.format(m)


def dgrey(m):
    return '<font color="#31363b">{}</font>'.format(m)


def message_prestyle_event_data(data):
    '''
    Invoked at the very start and allows styling some aspects
    of the data already.
    '''

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
        'Job <a href="{url_webview}/jobs/job/{job_id}">{job_id:11.11}</a> was '
        + green('accepted')
        + ' by <em>{client_name}</em>'
    ),
    '_lk.jobs.job-rejected': (
        'Job <a href="{url_webview}/jobs/job/{job_id}">{job_id:11.11}</a> was '
        + red('rejected')
        + ' by <em>{client_name}</em>'
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
        'New automatic synchronization issue for ' + red('<b>{name}</b>') + ' from {src_os} '
        '<em>{suite_src}</em> → <em>{suite_dest}</em> (source: {version_src}, '
        'destination: {version_dest}). Type: {kind}'
    ),
    '_lk.synchrotron.resolved-autosync-issue': (
        'The <em>{kind}</em> synchronization issue for <b>{name}</b> from {src_os} '
        '<em>{suite_src}</em> → <em>{suite_dest}</em> was ' + green('resolved') + '.'
    ),
}


#
# Templates for Rubicon
#


def pretty_job_upload_accepted(tag, data):
    if data.get('job_failed'):
        tmpl = (
            'Accepted upload for '
            + red('failed')
            + ' job <a href="{url_webview}/jobs/job/{job_id}">{job_id:11.11}</a>.'
        )
    else:
        tmpl = (
            'Accepted upload for '
            + green('successful')
            + ' job <a href="{url_webview}/jobs/job/{job_id}">{job_id:11.11}</a>.'
        )
    return tmpl.format(**data)


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
        'A <code>{format}</code> image for {distribution} '
        + red('failed')
        + ' to build for <b>{suite}</b>, environment '
        '<b>{environment}</b>/{style} on {architecture}. '
        '| <a href="{url_webview}/jobs/job/{job_id}">\N{CIRCLED INFORMATION SOURCE}</a>'
    ),
    '_lk.isotope.image-build-success': (
        'A <code>{format}</code> image for {distribution} was built ' + green('successfully') + ' for <b>{suite}</b>, '
        'environment <b>{environment}</b>/{style} on {architecture}. '
        'The image has been '
        + green('published')
        + ' for download. | <a href="{url_webview}/jobs/job/{job_id}">\N{CIRCLED INFORMATION SOURCE}</a>'
    ),
}


#
# Templates for the Archive
#


def pretty_source_package_published(tag, data):
    data['suites_str'] = ', '.join(data['suites'])

    tmpl = (
        'Source package <b>{name}</b> {version} was ' + green('published') + ' in the archive, available in suites '
        '<em>{suites_str}</em> ' + bgrey('<em>[{component}]</em>') + '.'
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

    return tmpl.format(**data)


def pretty_binary_package_published(tag, data):
    data['suites_str'] = '; '.join(data['suites'])

    tmpl = (
        'Binary package <b>{name}</b> {version} from <b>'
        + bgrey('{source_name}')
        + '</b> was '
        + green('published')
        + ' in the archive '
        'for {architecture} in suite <em>{suites_str}</em> ' + bgrey('<em>[{component}]</em>') + '.'
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

    return tmpl.format(**data)


templates_archive = {
    '_lk.archive.package-build-success': (
        'Package build for <b>{pkgname}</b> {version} on {architecture} in <em>{suite}</em> was '
        + green('successful')
        + '. '
        '| <a href="{url_webswview}/package/builds/job/{job_id}">\N{CIRCLED INFORMATION SOURCE}</a>'
    ),
    '_lk.archive.package-build-failed': (
        'Package build for <b>{pkgname}</b> {version} on {architecture} in <em>{suite}</em> has ' + red('failed') + '. '
        '| <a href="{url_webswview}/package/builds/job/{job_id}">\N{CIRCLED INFORMATION SOURCE}</a>'
    ),
    '_lk.archive.binary-package-published': pretty_binary_package_published,
    '_lk.archive.source-package-published': pretty_source_package_published,
    '_lk.archive.source-package-published-in-suite': 'Source package <b>{name}</b> {version} was '
    + green('added')
    + ' to suite <em>{suite_new}</em> '
    + bgrey('<em>[{component}]</em>')
    + '.',
    '_lk.archive.source-package-suite-removed': 'Source package <b>{name}</b> {version} was '
    + red('removed')
    + ' from suite <em>{suite_old}</em> '
    + bgrey('<em>[{component}]</em>')
    + '.',
    '_lk.archive.removed-source-package': 'Package <b>{name}</b> {version} '
    + bgrey('<em>[{component}]</em>')
    + ' was '
    + orange('removed')
    + ' from the archive.',
}


#
# Templates for Spears
#


def pretty_excuse_change(tag, data):
    removal = False
    if data.get('version_new') == '-':
        data['version_new'] = '(' + red('removal') + ')'
        removal = True

    if tag == '_lk.spears.new-excuse':
        if data.get('version_old') == '-':
            old_ver_info = 'Package is ' + green('new') + ' to target!'
        else:
            old_ver_info = 'Version in target is: {version_old}'

        tmpl = (
            'Package <b>{source_package}</b> {version_new} was '
            + red('blocked')
            + ' from its <em>{suite_source}</em> → <em>{suite_target}</em> '
            'migration. '
            + old_ver_info
            + ' | <a href="{url_webview}/migrations/excuse/{uuid}">\N{CIRCLED INFORMATION SOURCE}</a>'
        )

    elif tag == '_lk.spears.excuse-removed':
        tmpl = 'Migration excuse for package <b>{source_package}</b> {version_new} was ' + green('invalidated') + '.'
        if removal:
            tmpl = (
                tmpl + ' The package is now deleted from <em>{suite_target}</em>. Previous version was: {version_old}'
            )
        else:
            if data.get('version_old') == '-':
                old_ver_info = 'This package is ' + green('new') + ' in <em>{suite_target}</em>.'
            else:
                old_ver_info = 'Previous version in target was: {version_old}'

            tmpl = (
                tmpl + ' The package migrated from <em>{suite_source}</em> → <em>{suite_target}</em>. ' + old_ver_info
            )

    return tmpl.format(**data)


templates_spears = {'_lk.spears.new-excuse': pretty_excuse_change, '_lk.spears.excuse-removed': pretty_excuse_change}


#
# Assemble complete template set
#
message_templates = {}
message_templates.update(templates_jobs)
message_templates.update(templates_synchrotron)
message_templates.update(templates_rubicon)
message_templates.update(templates_isotope)
message_templates.update(templates_archive)
message_templates.update(templates_spears)
