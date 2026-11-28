#!/usr/bin/env python3
"""Validate a minimized controller-attested packaged Mac acceptance receipt.

This binds execution evidence to exact candidate bytes. It is not independent
hardware attestation: the release maintainer controls the controller and receipt.
Raw logs, target identifiers, paths and OS reports never belong in this object.
"""
import argparse
import json
from pathlib import Path
import re

FIELDS = {'schema', 'sourceRevision', 'version', 'candidateRun', 'archiveSHA256',
          'seed', 'checks', 'cycles', 'soakSeconds', 'coverage', 'cleanupVerified', 'passed'}
COVERAGE = {'downloads', 'uploads', 'dialogs', 'settings', 'native-host-recovery',
            'stop-during-provider', 'unclean-exit-recovery', 'stale-reference-refusal', 'diagnostic-export'}
RELIABILITY_COVERAGE = {'saved-access-choices', 'clean-and-crash-consent',
    'ordinary-and-covered-model-save-reload', 'synthetic-hover-effect',
    'independent-cover-presentation', 'protected-fault-recovery',
    'finite-owner-expiry', 'same-owner-renewal', 'stop-and-disconnect-relock',
    'visible-stop-relaunch-choices', 'cold-boot-choices-with-access-off'}
RELIABILITY_FIELDS = {'coveredDurationSeconds', 'renewableOwnerSeconds', 'sipEnabled', 'onlineDisplays',
                      'stopRelaunchUI', 'coldBootChoices'}
REBOOT_COVERAGE = {'visible-stop-relaunch-choices','cold-boot-choices-with-access-off'}
TIMING_PROFILES = {'standard': (60, 120), 'extended': (900, 960)}
VERSION = re.compile(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)')
SMOKE_SCHEMA = 'machine-control-packaged-smoke/v1'
SMOKE_FIELDS = FIELDS - {'seed', 'checks', 'cycles', 'soakSeconds'}
SMOKE_COVERAGE = {'installed-cli', 'access-off-refusal', 'browser-save-bytes',
                  'boot-bound-consent', 'independent-cover-presentation',
                  'covered-native-effect', 'native-stop-relock'}


def supports_standard_timing(version):
    if not isinstance(version, str) or not VERSION.fullmatch(version):
        raise ValueError('Invalid candidate version')
    return tuple(map(int, version.split('.'))) >= (0, 7, 7)


def validate_envelope(receipt, *, revision, version, run):
    schema = receipt.get('schema') if isinstance(receipt, dict) else None
    enhanced = schema == 'machine-control-packaged-acceptance/v1'
    smoke = schema == SMOKE_SCHEMA
    fields, coverage = FIELDS, COVERAGE
    if enhanced:
        fields, coverage = FIELDS | {'reliability'}, COVERAGE | RELIABILITY_COVERAGE
    elif smoke:
        fields, coverage = SMOKE_FIELDS, SMOKE_COVERAGE
    if (not isinstance(receipt, dict) or set(receipt) != fields
            or schema not in ('machine-control-packaged-acceptance/v0', 'machine-control-packaged-acceptance/v1', SMOKE_SCHEMA)
            or receipt.get('passed') is not True or receipt.get('cleanupVerified') is not True):
        raise ValueError('Missing/failed acceptance or unexpected receipt fields')
    if (not re.fullmatch('[a-f0-9]{40}', revision) or not re.fullmatch(r'[1-9][0-9]*\.[1-9][0-9]*', run)
            or not VERSION.fullmatch(version)
            or receipt['sourceRevision'] != revision or receipt['version'] != version
            or receipt['candidateRun'] != run):
        raise ValueError('Acceptance source/version/candidate mismatch')
    if smoke and not supports_standard_timing(version):
        raise ValueError('Packaged smoke qualification starts with desktop 0.7.7')
    if tuple(map(int, version.split('.'))) >= (0, 6, 11) and not (enhanced or smoke):
        raise ValueError('This release requires covered reliability acceptance')
    if enhanced:
        value = receipt['reliability']
        if (not isinstance(value, dict) or set(value) != RELIABILITY_FIELDS
                or type(value.get('coveredDurationSeconds')) is not int
                or type(value.get('renewableOwnerSeconds')) is not int
                or type(value.get('sipEnabled')) is not bool
                or type(value.get('onlineDisplays')) is not int or not 1 <= value['onlineDisplays'] <= 16
                or value.get('stopRelaunchUI') is not True or value.get('coldBootChoices') is not True):
            raise ValueError('Incomplete covered reliability execution')
        expiry, renewal = value['coveredDurationSeconds'], value['renewableOwnerSeconds']
        extended_expiry, extended_renewal = TIMING_PROFILES['extended']
        extended = expiry == extended_expiry and extended_renewal <= renewal <= 1800
        standard = supports_standard_timing(version) and (expiry, renewal) == TIMING_PROFILES['standard']
        if not (extended or standard):
            raise ValueError('Incomplete covered reliability timing')
    if (not re.fullmatch('[a-f0-9]{64}', str(receipt['archiveSHA256']))
            or not isinstance(receipt['coverage'], list) or len(receipt['coverage']) != len(coverage)
            or any(type(item) is not str for item in receipt['coverage'])
            or set(receipt['coverage']) != coverage):
        raise ValueError('Incomplete bounded packaged acceptance coverage')
    if not smoke and (type(receipt['seed']) is not int or not -(2**63) <= receipt['seed'] < 2**63
            or type(receipt['checks']) is not int or not 20 <= receipt['checks'] <= 5000
            or type(receipt['cycles']) is not int or not 3 <= receipt['cycles'] <= 300
            or type(receipt['soakSeconds']) is not int or not 120 <= receipt['soakSeconds'] <= 1800):
        raise ValueError('Incomplete bounded packaged acceptance coverage')
    return receipt


def validate(receipt, build, *, revision, version, run):
    validate_envelope(receipt, revision=revision, version=version, run=run)
    if (not isinstance(build, dict) or build.get('schema') != 'machine-control-desktop-build/v0'
            or build.get('sourceState') != 'ci_checkout'
            or build.get('sourceRevision') != revision or build.get('version') != version
            or build.get('bundleIdentifier') != 'org.machine-control.app'
            or f"{build.get('workflowRun')}.{build.get('workflowAttempt')}" != run):
        raise ValueError('Acceptance requires the exact CI candidate build')
    archives = [v for v in build.get('artifacts', [])
                if v.get('name') == f'MachineControl_{version}_arm64.app.tar.gz']
    if (len(archives) != 1 or not re.fullmatch('[a-f0-9]{64}', str(receipt['archiveSHA256']))
            or receipt['archiveSHA256'] != archives[0].get('sha256')):
        raise ValueError('Acceptance archive hash mismatch')
    return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('receipt', type=Path)
    p.add_argument('--build', type=Path, help='Also bind archive/source to the downloaded final build')
    for name in ['revision', 'version', 'run']:
        p.add_argument('--' + name, required=True)
    a = p.parse_args()
    if a.receipt.stat().st_size > 16_384:
        p.error('Oversized acceptance receipt')
    value = json.loads(a.receipt.read_text())
    if a.build:
        validate(value, json.loads(a.build.read_text()), revision=a.revision, version=a.version, run=a.run)
    else:
        validate_envelope(value, revision=a.revision, version=a.version, run=a.run)
    print('Exact packaged Mac acceptance verified' if a.build else 'Packaged acceptance envelope verified')


if __name__ == '__main__':
    main()
