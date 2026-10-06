Skip to content Skip to footer
document.cookie = 'nitroCachedPage=' + (!window.NITROPACK_STATE ?
'0' : '1') + '; path=/; SameSite=Lax';
if (!window.NITROPACK_STATE || window.NITROPACK_STATE != 'FRESH') {
var proxyPurgeOnly = 0;
if (typeof navigator.sendBeacon !== 'undefined') {
var nitroData = new FormData(); nitroData.append('nitroBeaconUrl', 'aHR0cHM6Ly9sYW1taXN2YXJnYXMuY29tL3RlYW0vcmktbGFib3JlcnMtZGlzdHJpY3QtY291bmNpbC8='); nitroData.append('nitroBeaconCookies', 'W10='); nitroData.append('nitroBeaconHash', '763f0033de4e57fd01094e5e07cd90ec6b6e878ec951434028545f21c4393f13732856bf8119077e9ffb5b5babb511a8ce493cf215522f67b259f3ef4fc4528f'); nitroData.append('proxyPurgeOnly', ''); nitroData.append('layout', 'cpt_team'); navigator.sendBeacon(location.href, nitroData);
} else {
var xhr = new XMLHttpRequest(); xhr.open('POST', location.href, true); xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded'); xhr.send('nitroBeaconUrl=aHR0cHM6Ly9sYW1taXN2YXJnYXMuY29tL3RlYW0vcmktbGFib3JlcnMtZGlzdHJpY3QtY291bmNpbC8=&nitroBeaconCookies=W10=&nitroBeaconHash=763f0033de4e57fd01094e5e07cd90ec6b6e878ec951434028545f21c4393f13732856bf8119077e9ffb5b5babb511a8ce493cf215522f67b259f3ef4fc4528f&proxyPurgeOnly=&layout=cpt_team');
}
}
