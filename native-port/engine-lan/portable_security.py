"""Keep portable mod/config folders private on POSIX and Windows NTFS.

Windows validation uses SIDs, never localized account names. Only a folder the
current account owns is re-hardened: that is this application's own data folder,
which an earlier build may have created with inherited permissions. A folder
owned by another account is reported and never changed.
"""
import json
import os
import subprocess

# ACEs a private folder may carry besides the owner's own SID. SYSTEM and
# Administrators are trusted by definition; CREATOR OWNER (S-1-3-0) and OWNER
# RIGHTS (S-1-3-4) only ever grant the object's owner, which valid_acl already
# requires to be the current user. Windows also substitutes OWNER RIGHTS for the
# owner's SID when inheritance is removed, which is why the user's SID is often
# absent from an otherwise private folder.
PRIVATE_ACES = frozenset({'S-1-5-18', 'S-1-5-32-544', 'S-1-3-0', 'S-1-3-4'})
OWNER_ACES = frozenset({'S-1-3-0', 'S-1-3-4'})

# A cold PowerShell start can exceed ten seconds with antivirus enabled.
ACL_TIMEOUT = 30
ACL_LIMIT = 8192

HEAD = '''$ErrorActionPreference='Stop';[Console]::OutputEncoding=[System.Text.Encoding]::UTF8
'''
# Give the folder an owner-only DACL. No ACE is copied from the parent, so an
# inherited Users/Authenticated Users grant cannot survive the rewrite.
HARDEN = '''
$u=[System.Security.Principal.WindowsIdentity]::GetCurrent().User
$s=New-Object System.Security.AccessControl.DirectorySecurity
$s.SetOwner($u);$s.SetAccessRuleProtection($true,$false)
$n=New-Object System.Security.AccessControl.FileSystemAccessRule($u,'FullControl','ContainerInherit,ObjectInherit','None','Allow')
$s.AddAccessRule($n);Set-Acl -LiteralPath $env:ZGTA_PRIVATE_PATH -AclObject $s
'''
REPORT = '''
$a=Get-Acl -LiteralPath $env:ZGTA_PRIVATE_PATH
$u=[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$o=$a.GetOwner([System.Security.Principal.SecurityIdentifier]).Value
$r=@($a.Access | Where-Object {$_.AccessControlType -eq 'Allow'} | ForEach-Object {$_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value})
@{user=$u;owner=$o;allow=$r}|ConvertTo-Json -Compress
'''


def acl_rules(rules):
    """Return the allowed SIDs, or None when the value is unusable.

    Windows PowerShell 5.1 serializes a single-ACE list as a bare string.
    """
    if isinstance(rules, str):rules = [rules]
    if not isinstance(rules, list) or not rules or any(not isinstance(rule, str) for rule in rules):
        return None
    return rules


def valid_acl(data):
    if not isinstance(data, dict) or data.get('owner') != data.get('user') or not isinstance(data.get('user'), str):return False
    rules = acl_rules(data.get('allow'))
    if rules is None or not set(rules) <= PRIVATE_ACES | {data['user']}:return False
    return data['user'] in rules or any(rule in OWNER_ACES for rule in rules)


def acl_detail(data):
    """Bounded, path-free description of a rejected ACL for the error message."""
    if not isinstance(data, dict):return ''
    owner = data.get('owner')
    rules = acl_rules(data.get('allow')) or []
    allowed = ','.join(str(rule) for rule in rules)[:512]
    return ' Owner '+str(owner)[:64]+', allowed '+(allowed or 'none')+'.'


def windows_acl(path, repair=False):
    """Read the folder's ACL, optionally replacing it with an owner-only DACL."""
    script = HEAD + (HARDEN if repair else '') + REPORT
    try:
        result = subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],env=dict(os.environ,ZGTA_PRIVATE_PATH=str(path)),capture_output=True,timeout=ACL_TIMEOUT,check=True)
    except (OSError, subprocess.SubprocessError) as error:
        raise ValueError('Windows could not read the ZGTA V folder permissions. Keep ZGTA V data on a local NTFS drive and make sure Windows PowerShell is available; no permissions were changed.') from error
    if len(result.stdout)>ACL_LIMIT:raise ValueError('Unexpected ACL response.')
    try:return json.loads(result.stdout.decode('utf-8-sig'))
    except (UnicodeDecodeError, ValueError) as error:
        raise ValueError('Windows returned an unreadable folder permission report; no permissions were changed.') from error


def windows_private(path,new=False):
    data = windows_acl(path,repair=new)
    if valid_acl(data):return
    # A folder this account owns is ours to fix: earlier launchers created it with
    # inherited permissions, which blocked every later start with the NTFS error.
    if isinstance(data, dict) and isinstance(data.get('user'), str) and data.get('owner') == data['user']:
        data = windows_acl(path,repair=True)
        if valid_acl(data):return
    raise ValueError('ZGTA V could not keep its Windows data folder private. A folder owned by another account is never changed, and a drive without NTFS permissions cannot restrict one. Sign in as the owning account or store ZGTA V data on a local NTFS drive.'+acl_detail(data))
