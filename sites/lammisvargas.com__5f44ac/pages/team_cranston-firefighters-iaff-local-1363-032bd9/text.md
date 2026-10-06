Skip to content Skip to footer
document.cookie = 'nitroCachedPage=' + (!window.NITROPACK_STATE ?
'0' : '1') + '; path=/; SameSite=Lax';
if (!window.NITROPACK_STATE || window.NITROPACK_STATE != 'FRESH') {
var proxyPurgeOnly = 0;
if (typeof navigator.sendBeacon !== 'undefined') {
var nitroData = new FormData(); nitroData.append('nitroBeaconUrl', 'aHR0cHM6Ly9sYW1taXN2YXJnYXMuY29tL3RlYW0vY3JhbnN0b24tZmlyZWZpZ2h0ZXJzLWlhZmYtbG9jYWwtMTM2My8='); nitroData.append('nitroBeaconCookies', 'W10='); nitroData.append('nitroBeaconHash', '7c3fe7dda4108038ebb3731d199e342e40c374882896a3cda8aac9e94bd4b2cc0ceaa97e838d38ea6474cacf776f9d1813b3e187ab34cfdcbc14c57940f08a30'); nitroData.append('proxyPurgeOnly', ''); nitroData.append('layout', 'cpt_team'); navigator.sendBeacon(location.href, nitroData);
} else {
var xhr = new XMLHttpRequest(); xhr.open('POST', location.href, true); xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded'); xhr.send('nitroBeaconUrl=aHR0cHM6Ly9sYW1taXN2YXJnYXMuY29tL3RlYW0vY3JhbnN0b24tZmlyZWZpZ2h0ZXJzLWlhZmYtbG9jYWwtMTM2My8=&nitroBeaconCookies=W10=&nitroBeaconHash=7c3fe7dda4108038ebb3731d199e342e40c374882896a3cda8aac9e94bd4b2cc0ceaa97e838d38ea6474cacf776f9d1813b3e187ab34cfdcbc14c57940f08a30&proxyPurgeOnly=&layout=cpt_team');
}
}
