"""Keep new portable mod/config folders private on POSIX and Windows NTFS.

Windows validation uses SIDs, never localized account names. No existing ACL is
repaired automatically. Only a newly created application folder is restricted.
"""
import json
import os
import subprocess


def valid_acl(data):
    if not isinstance(data,dict) or data.get('owner')!=data.get('user') or not isinstance(data.get('user'),str):return False
    rules=data.get('allow')
    return isinstance(rules,list) and bool(rules) and set(rules)<={data['user'],'S-1-5-18','S-1-5-32-544'} and data['user'] in rules


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
    if len(result.stdout)>8192 or not valid_acl(json.loads(result.stdout.decode('utf-8-sig'))):raise ValueError('Choose an owned, private NTFS folder for ZGTA V data. Existing permissions were preserved.')
