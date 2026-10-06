Skip to content Skip to footer
document.cookie = 'nitroCachedPage=' + (!window.NITROPACK_STATE ?
'0' : '1') + '; path=/; SameSite=Lax';
if (!window.NITROPACK_STATE || window.NITROPACK_STATE != 'FRESH') {
var proxyPurgeOnly = 0;
if (typeof navigator.sendBeacon !== 'undefined') {
var nitroData = new FormData(); nitroData.append('nitroBeaconUrl', 'aHR0cHM6Ly9sYW1taXN2YXJnYXMuY29tL2RvbmF0aW9uLw=='); nitroData.append('nitroBeaconCookies', 'W10='); nitroData.append('nitroBeaconHash', 'f7f9d02954183860a0523f646593707bb5b2e699b64ab7931e570cb17ba1362955acdf5ca899492731cca140d908a0803ee5bbcf792a63476e90ad595aecf906'); nitroData.append('proxyPurgeOnly', ''); nitroData.append('layout', 'page'); navigator.sendBeacon(location.href, nitroData);
} else {
var xhr = new XMLHttpRequest(); xhr.open('POST', location.href, true); xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded'); xhr.send('nitroBeaconUrl=aHR0cHM6Ly9sYW1taXN2YXJnYXMuY29tL2RvbmF0aW9uLw==&nitroBeaconCookies=W10=&nitroBeaconHash=f7f9d02954183860a0523f646593707bb5b2e699b64ab7931e570cb17ba1362955acdf5ca899492731cca140d908a0803ee5bbcf792a63476e90ad595aecf906&proxyPurgeOnly=&layout=page');
}
}
