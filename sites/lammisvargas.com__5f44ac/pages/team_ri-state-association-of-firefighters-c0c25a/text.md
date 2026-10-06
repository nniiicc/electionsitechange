Skip to content Skip to footer
document.cookie = 'nitroCachedPage=' + (!window.NITROPACK_STATE ?
'0' : '1') + '; path=/; SameSite=Lax';
if (!window.NITROPACK_STATE || window.NITROPACK_STATE != 'FRESH') {
var proxyPurgeOnly = 0;
if (typeof navigator.sendBeacon !== 'undefined') {
var nitroData = new FormData(); nitroData.append('nitroBeaconUrl', 'aHR0cHM6Ly9sYW1taXN2YXJnYXMuY29tL3RlYW0vcmktc3RhdGUtYXNzb2NpYXRpb24tb2YtZmlyZWZpZ2h0ZXJzLw=='); nitroData.append('nitroBeaconCookies', 'W10='); nitroData.append('nitroBeaconHash', 'a2ab26f1dbf2ed924514946dc397c57203332d2933636eb20b96c297bb4356a1d14b16f04537e623648934622b725eb1865ebe561e341293ed88ddac28435f3e'); nitroData.append('proxyPurgeOnly', ''); nitroData.append('layout', 'cpt_team'); navigator.sendBeacon(location.href, nitroData);
} else {
var xhr = new XMLHttpRequest(); xhr.open('POST', location.href, true); xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded'); xhr.send('nitroBeaconUrl=aHR0cHM6Ly9sYW1taXN2YXJnYXMuY29tL3RlYW0vcmktc3RhdGUtYXNzb2NpYXRpb24tb2YtZmlyZWZpZ2h0ZXJzLw==&nitroBeaconCookies=W10=&nitroBeaconHash=a2ab26f1dbf2ed924514946dc397c57203332d2933636eb20b96c297bb4356a1d14b16f04537e623648934622b725eb1865ebe561e341293ed88ddac28435f3e&proxyPurgeOnly=&layout=cpt_team');
}
}
