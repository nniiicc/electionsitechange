Skip to content Skip to footer
document.cookie = 'nitroCachedPage=' + (!window.NITROPACK_STATE ?
'0' : '1') + '; path=/; SameSite=Lax';
if (!window.NITROPACK_STATE || window.NITROPACK_STATE != 'FRESH') {
var proxyPurgeOnly = 0;
if (typeof navigator.sendBeacon !== 'undefined') {
var nitroData = new FormData(); nitroData.append('nitroBeaconUrl', 'aHR0cHM6Ly9sYW1taXN2YXJnYXMuY29tL3RlYW0vYW1hbGdhbWF0ZWQtdHJhbnNpdC11bmlvbi1sb2NhbC02MTgv'); nitroData.append('nitroBeaconCookies', 'W10='); nitroData.append('nitroBeaconHash', '1bdf152ca0f0bc8b0920bb022432361b81c71fffbd7cf364de93fe88d3c6032e2847b709782140d54e3757918ba308183f100b89b8554da67425e34ed4f451b4'); nitroData.append('proxyPurgeOnly', ''); nitroData.append('layout', 'cpt_team'); navigator.sendBeacon(location.href, nitroData);
} else {
var xhr = new XMLHttpRequest(); xhr.open('POST', location.href, true); xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded'); xhr.send('nitroBeaconUrl=aHR0cHM6Ly9sYW1taXN2YXJnYXMuY29tL3RlYW0vYW1hbGdhbWF0ZWQtdHJhbnNpdC11bmlvbi1sb2NhbC02MTgv&nitroBeaconCookies=W10=&nitroBeaconHash=1bdf152ca0f0bc8b0920bb022432361b81c71fffbd7cf364de93fe88d3c6032e2847b709782140d54e3757918ba308183f100b89b8554da67425e34ed4f451b4&proxyPurgeOnly=&layout=cpt_team');
}
}
