"""Reuse only unchanged, dependency-matched ARM64 engine compilation units.

Source and all compiler-recorded app dependencies must match a preserved,
successful build. Changed units compile normally in the new isolated stage.
No prior stage, object, app or shader is modified.
"""
import json
import hashlib
import os
import posixpath
from pathlib import Path
import shlex
import struct
import subprocess
import tempfile


def archive_content_hash(path):
    """Hash every archive byte except member-header dates (never object data)."""
    digest=hashlib.sha256()
    with path.open('rb') as source:
        magic=source.read(8)
        if magic!=b'!<arch>\n':raise ValueError('Expected a regular object archive')
        digest.update(magic)
        while True:
            header=source.read(60)
            if not header:break
            if (len(header)!=60 or header[58:]!=b'`\n' or not header[48:58].strip().isdigit()
                    or any(c!=32 and not 48<=c<=57 for c in header[16:28])):
                raise ValueError('Invalid object archive header')
            size=int(header[48:58]);digest.update(header[:16]+b'0'.ljust(12)+header[28:])
            while size:
                chunk=source.read(min(size,1024*1024))
                if not chunk:raise ValueError('Truncated object archive')
                digest.update(chunk);size-=len(chunk)
            if int(header[48:58])&1:
                pad=source.read(1)
                if pad!=b'\n':raise ValueError('Invalid archive padding')
                digest.update(pad)
    return digest.hexdigest()


def materialize_cache(directory, objects, record, digest_file, preserved=None):
    """Repeat a build only with identical archive content and attested inputs.

    Never overwrite the archive/receipt used by an earlier successful build.
    The caller has already attested each object and its compiler dependencies.
    Older libtool outputs carry wall-clock member dates; compare those archives
    ignoring only header dates while retaining their exact recorded file hash.
    """
    library = directory / 'libunchanged_engine.a'
    receipt = directory / 'verification.json'
    if preserved is not None and directory.exists():
        if (directory.is_symlink() or set(p.name for p in directory.iterdir())!={library.name,receipt.name}
                or any(p.is_symlink() or not p.is_file() for p in (library,receipt))):
            raise ValueError('Existing generated cache differs; preserve it and use a new build output')
        existing=json.loads(receipt.read_text())
        expected=dict(record,library=str(library),library_sha256=preserved.get('library_sha256'))
        source=Path(preserved['library'])
        if (existing!=expected or preserved.get('reused_units')!=record.get('reused_units')
                or preserved.get('recompile_units')!=record.get('recompile_units')
                or any(p.is_symlink() for p in (source,*source.parents))
                or json.loads((source.parent/'verification.json').read_text())!=preserved
                or digest_file(source)!=existing['library_sha256'] or digest_file(library)!=existing['library_sha256']):
            raise ValueError('Existing archive/member proof differs; preserve it and use a new build output')
        return existing
    if preserved is not None and not directory.exists():
        # prepare() has re-attested every object and compiler dependency. Reuse
        # the exact previously linked archive only when the ordered member proof
        # also matches, so low disk space never requires dropping validation.
        source=Path(preserved['library'])
        if (any(p.is_symlink() for p in (source,*source.parents))
                or not source.is_file() or source.name!=library.name
                or json.loads((source.parent/'verification.json').read_text())!=preserved
                or preserved.get('reused_units')!=record.get('reused_units')
                or preserved.get('recompile_units')!=record.get('recompile_units')
                or digest_file(source)!=preserved.get('library_sha256')):
            raise ValueError('Preserved archive/member proof differs; preserve it and use a new build output')
        directory.mkdir(mode=0o700)
        subprocess.run(['/bin/cp','-c',str(source),str(library)],check=True,capture_output=True)
        if digest_file(library)!=preserved['library_sha256']:raise ValueError('Cloned archive differs')
        observation=dict(record,library=str(library),library_sha256=preserved['library_sha256'])
        receipt.write_text(json.dumps(observation,indent=2)+'\n')
        return observation
    with tempfile.TemporaryDirectory(prefix='zgta-link-cache-', dir=directory.parent) as tmp:
        candidate = Path(tmp) / library.name
        subprocess.run(['/usr/bin/libtool', '-static', '-o', str(candidate), *objects], env=dict(os.environ,ZERO_AR_DATE='1'), check=True, capture_output=True)
        observation = dict(record, library=str(library), library_sha256=digest_file(candidate))
        if directory.exists() or directory.is_symlink():
            if (directory.is_symlink() or not directory.is_dir()
                    or set(p.name for p in directory.iterdir()) != {library.name, receipt.name}
                    or any(p.is_symlink() or not p.is_file() for p in (library, receipt))):
                raise ValueError('Existing generated cache differs; preserve it and use a new build output')
            preserved=json.loads(receipt.read_text())
            expected=dict(observation,library_sha256=preserved.get('library_sha256'))
            if (preserved!=expected or digest_file(library)!=preserved['library_sha256']
                    or archive_content_hash(library)!=archive_content_hash(candidate)):
                raise ValueError('Existing generated cache differs; preserve it and use a new build output')
            observation=preserved
        else:
            directory.mkdir(mode=0o700)
            candidate.replace(library)
            receipt.write_text(json.dumps(observation, indent=2) + '\n')
    return observation


def unit_flags(spec, name):
    """Per-file XcodeGen flags are compiler inputs, just like source headers."""
    entries = spec['targets']['PlayGTA5Native']['sources']
    direct = [e for e in entries if isinstance(e, dict) and e.get('path') == 'Generated/' + name + '.c']
    if len(direct) > 1:
        raise ValueError('Duplicate generated source entry')
    if direct:
        flags = direct[0].get('compilerFlags', '')
    else:
        folder = [e for e in entries if isinstance(e, dict) and e.get('path') == 'Generated']
        if len(folder) != 1:
            raise ValueError('Expected one generated source folder')
        import fnmatch
        if any(fnmatch.fnmatchcase(name + '.c', pattern) for pattern in folder[0].get('excludes', [])):
            raise ValueError('Generated unit excluded without an explicit source entry')
        flags = folder[0].get('compilerFlags', '')
    return shlex.split(flags) if isinstance(flags, str) else list(flags)


def dependencies(path):
    text = path.read_text().replace('\\\n', ' ')
    if not text.startswith('dependencies:'):
        raise ValueError('Expected Xcode compiler dependency list')
    return [Path(p) for p in shlex.split(text.split(':', 1)[1])]


def matching_dependencies(paths, previous_app, app, digest):
    for old in paths:
        if old.is_relative_to(previous_app):
            current = app / old.relative_to(previous_app)
            if not old.is_file() or not current.is_file() or digest(old) != digest(current):
                return False
        elif not str(old).startswith('/Applications/Xcode.app/Contents/Developer/'):
            raise ValueError('Unexpected external compiler dependency: ' + str(old))
    return True

def scoped_input_key(origin, relative):
    """Match compiler ../ aliases to manifest keys without following links."""
    value=Path(relative)
    normalized=posixpath.normpath(str(value))
    if value.is_absolute() or normalized in ('.','..') or normalized.startswith('../'):
        raise ValueError('Retained compiler input escapes its application')
    base=origin.resolve(strict=True)
    path=base
    for part in value.parts:
        path=path/part
        if path.is_symlink():raise ValueError('Retained compiler input uses a symbolic link')
    resolved=path.resolve(strict=True)
    if not resolved.is_relative_to(base):raise ValueError('Retained compiler input escapes its application')
    return str(resolved.relative_to(base))


def retained_unit(previous, record, name, app_build, digest):
    """Follow only an unchanged object's hash recorded by the successful build.

    A prior incremental build may retain five objects locally and reference
    the other 59 in its predecessor. Its disposable combined library is not
    required: original object bytes and dependencies are checked again.
    """
    directory = previous / 'DerivedData/Build/Intermediates.noindex/PlayGTA5Native.build/Release-iphoneos/PlayGTA5Native.build/Objects-normal/arm64'
    obj, deps = directory / (name + '.o'), directory / (name + '.d')
    if obj.is_file() and deps.is_file():
        return obj, deps, previous / 'AppRoot'
    entries = [r for r in record.get('generated_object_reuse', {}).get('reused_units', []) if r.get('source') == name + '.c']
    if len(entries) != 1:
        raise ValueError('Preserved compilation unit unavailable: ' + name)
    entry = entries[0]; obj = Path(entry['object']); deps = obj.with_suffix('.d')
    relative = obj.relative_to(app_build)
    expected_tail = Path('DerivedData/Build/Intermediates.noindex/PlayGTA5Native.build/Release-iphoneos/PlayGTA5Native.build/Objects-normal/arm64') / (name + '.o')
    if not obj.is_absolute() or Path(*relative.parts[1:]) != expected_tail:
        raise ValueError('Unexpected retained object path')
    origin = app_build / relative.parts[0] / 'AppRoot'
    for item in (obj, deps):
        if not item.is_file() or any(p.is_symlink() for p in (item, *item.parents)):
            raise ValueError('Retained object or dependency unavailable')
    if digest(obj) != entry['object_sha256'] or digest(deps) != entry['dependencies_sha256']:
        raise ValueError('Retained object integrity differs')
    actual = {str(p.relative_to(origin)): digest(p) for p in dependencies(deps) if p.is_relative_to(origin)}
    if actual != entry['app_inputs']:
        raise ValueError('Retained compiler inputs differ')
    # The successful immediately previous build must attest the same inputs.
    for rel, sha in actual.items():
        key = scoped_input_key(origin, rel)
        known = record['input_hashes'].get(key)
        if known == sha:
            continue
        # Bundled compiler headers are attested in app_inputs rather than the
        # staged application manifest. Verify the immediately previous copy.
        tools = previous / 'AppRoot/Tools'; header = previous / 'AppRoot' / key
        if known is None and key.startswith('Tools/') and header.resolve().is_relative_to(tools.resolve()) and header.is_file() and digest(header) == sha:
            continue
        raise ValueError('Retained input not attested by previous build: ' + rel)
    return obj, deps, origin


def same_generated_compiler_settings(old_spec, new_spec):
    """Only the reviewed Swift UI gate may differ; C flags remain per-unit inputs."""
    if old_spec['settings'] != new_spec['settings']:
        return False
    old = dict(old_spec['targets']['PlayGTA5Native']['settings'])
    new = dict(new_spec['targets']['PlayGTA5Native']['settings'])
    old_base, new_base = dict(old['base']), dict(new['base'])
    key = 'SWIFT_ACTIVE_COMPILATION_CONDITIONS'
    gate = ['$(inherited)', 'ZGTA_NATIVE_RECOVERY_QA']
    if key not in old_base and new_base.get(key) == gate:
        new_base.pop(key)
    old['base'], new['base'] = old_base, new_base
    return old == new


def prepare(run, previous, receipt, staged_sources, digest_file):
    from build_experimental import APP, REPO
    if previous.parent != APP.absolute() / 'Build' or receipt.parent != previous or previous == run:
        raise ValueError('Use a distinct preserved isolated build and its receipt')
    record = json.loads(receipt.read_text())
    if (record.get('format') != 'zema-engine-lan-build-v1' or record.get('exit_code') != 0
            or record.get('input_hashes') != staged_sources(previous)):
        raise ValueError('Preserved build source/receipt mismatch')
    old_app = previous / 'AppRoot'
    binary = previous / 'DerivedData/Build/Products/Release-iphoneos/PlayGTA5Native.app/PlayGTA5Native'
    if digest_file(binary) != record['app_executable_sha256']:
        raise ValueError('Preserved successful executable changed')
    subprocess.run(['git', 'merge-base', '--is-ancestor', record['tool_head'], 'HEAD'], cwd=REPO, check=True)
    app = run / 'AppRoot'
    old_spec = json.loads((old_app / 'project.experimental.json').read_text())
    new_spec = json.loads((app / 'project.experimental.json').read_text())
    if not same_generated_compiler_settings(old_spec, new_spec):
        raise ValueError('Compiler settings changed; compile all engine units')
    cache = {}
    def digest(path):
        if path not in cache:
            cache[path] = digest_file(path)
        return cache[path]
    reused = []
    for number in range(64):
        name = 'game_' + str(number)
        obj, deps, object_app = retained_unit(previous, record, name, APP.absolute() / 'Build', digest)
        if obj.is_symlink() or deps.is_symlink() or not obj.is_file() or not deps.is_file():
            raise ValueError('Preserved compilation unit unavailable: ' + name)
        with obj.open('rb') as source:
            magic, cpu, subtype, kind = struct.unpack('<IIII', source.read(16))
        if (magic, cpu, kind) != (0xfeedfacf, 0x100000c, 1):
            raise ValueError('Expected thin ARM64 Mach-O object: ' + name)
        inputs = dependencies(deps)
        if object_app / ('Generated/' + name + '.c') not in inputs:
            raise ValueError('Source missing from compiler dependencies: ' + name)
        if unit_flags(old_spec, name) == unit_flags(new_spec, name) and matching_dependencies(inputs, object_app, app, digest):
            reused.append({'source': name + '.c', 'object': str(obj), 'object_sha256': digest(obj),
                           'dependencies_sha256': digest(deps),
                           'app_inputs': {str(p.relative_to(object_app)): digest(p) for p in inputs if p.is_relative_to(object_app)}})
    if not reused:
        raise ValueError('No dependency-matched engine units; use a normal full build')
    directory = run / 'GeneratedObjectCache'
    library = directory / 'libunchanged_engine.a'
    observation = {'format': 'zema-generated-object-reuse-v1', 'previous_build_receipt_sha256': digest(receipt),
                   'previous_source_revision': record['tool_head'], 'reused_units': reused,
                   'recompile_units': ['game_' + str(n) + '.c' for n in range(64) if 'game_' + str(n) + '.c' not in [x['source'] for x in reused]]}
    preserved=record.get('generated_object_reuse')
    if preserved and (Path(preserved['library']).parent!=previous/'GeneratedObjectCache'
                      or preserved.get('reused_units')!=reused
                      or preserved.get('recompile_units')!=observation['recompile_units']):
        preserved=None
    observation = materialize_cache(directory, [x['object'] for x in reused], observation, digest_file, preserved)
    return ['EXCLUDED_SOURCE_FILE_NAMES=' + ' '.join(x['source'] for x in reused),
            'OTHER_LDFLAGS=$(inherited) -Wl,-force_load,' + str(library)], observation
