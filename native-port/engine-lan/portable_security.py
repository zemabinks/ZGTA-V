"""Keep new portable mod/config folders private on POSIX and Windows NTFS.

Windows validation uses SIDs, never localized account names. No existing ACL is
repaired automatically. Only a newly created application folder is restricted.
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


def windows_private(path,new=False):
    setup='''
$u=[System.Security.Principal.WindowsIdentity]::GetCurrent().User
$a=New-Object System.Security.AccessControl.DirectorySecurity
$a.SetOwner($u);$a.SetAccessRuleProtection($true,$false)
$r=New-Object System.Security.AccessControl.FileSystemAccessRule($u,'FullControl','ContainerInherit,ObjectInherit','None','Allow')
$a.AddAccessRule($r);Set-Acl -LiteralPath $env:ZGTA_PRIVATE_PATH -AclObject $a
''' if new else ''
    script='''$ErrorActionPreference='Stop';[Console]::OutputEncoding=[System.Text.Encoding]::UTF8
'''+setup+'''
$a=Get-Acl -LiteralPath $env:ZGTA_PRIVATE_PATH
$u=[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$o=$a.GetOwner([System.Security.Principal.SecurityIdentifier]).Value
$r=@($a.Access | Where-Object {$_.AccessControlType -eq 'Allow'} | ForEach-Object {$_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value})
@{user=$u;owner=$o;allow=$r}|ConvertTo-Json -Compress
'''
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],env=dict(os.environ,ZGTA_PRIVATE_PATH=str(path)),capture_output=True,timeout=10,check=True)
    if len(result.stdout)>8192:raise ValueError('Unexpected ACL response.')
    data=json.loads(result.stdout.decode('utf-8-sig'))
    if not valid_acl(data):raise ValueError('Choose an owned, private NTFS folder for ZGTA V data. Existing permissions were preserved.'+acl_detail(data))
