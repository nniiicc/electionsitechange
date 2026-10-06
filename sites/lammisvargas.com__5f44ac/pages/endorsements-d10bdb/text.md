Skip to content Skip to footer
document.cookie = 'nitroCachedPage=' + (!window.NITROPACK_STATE ?
'0' : '1') + '; path=/; SameSite=Lax';
if (!window.NITROPACK_STATE || window.NITROPACK_STATE != 'FRESH') {
var proxyPurgeOnly = 0;
if (typeof navigator.sendBeacon !== 'undefined') {
var nitroData = new FormData(); nitroData.append('nitroBeaconUrl', 'aHR0cHM6Ly9sYW1taXN2YXJnYXMuY29tL2VuZG9yc2VtZW50cy8='); nitroData.append('nitroBeaconCookies', 'W10='); nitroData.append('nitroBeaconHash', '30e1aee17df5eb2ff886137877fc8e71a8b8f33c4625e26159844c2b9d719925e4a028d230bc06310505bd6b42c9cc96b98261667419991f91bc751df3b186bd'); nitroData.append('proxyPurgeOnly', ''); nitroData.append('layout', 'page'); navigator.sendBeacon(location.href, nitroData);
} else {
var xhr = new XMLHttpRequest(); xhr.open('POST', location.href, true); xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded'); xhr.send('nitroBeaconUrl=aHR0cHM6Ly9sYW1taXN2YXJnYXMuY29tL2VuZG9yc2VtZW50cy8=&nitroBeaconCookies=W10=&nitroBeaconHash=30e1aee17df5eb2ff886137877fc8e71a8b8f33c4625e26159844c2b9d719925e4a028d230bc06310505bd6b42c9cc96b98261667419991f91bc751df3b186bd&proxyPurgeOnly=&layout=page');
}
}
