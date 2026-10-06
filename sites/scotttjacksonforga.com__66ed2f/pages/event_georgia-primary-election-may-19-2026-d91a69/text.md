This listing has been expired.
Skip to content
This listing has been expired.
jQuery(document).ready(function() {
jQuery('.wpem_related_events-slider').slick({
arrow: true,
infinite: false,
slidesToShow: 3,
slidesToScroll: 1,
responsive: [
{
breakpoint: 1024,
settings: {
slidesToShow: 2
}
},
{
breakpoint: 767,
settings: {
slidesToShow: 1
}
}
]
});
});
jQuery(document).ready(function() {
jQuery('.wpem-single-event-slider').slick({
dots: true,
infinite: true,
speed: 500,
fade: true,
cssEase: 'linear',
adaptiveHeight: true,
responsive: [{
breakpoint: 992,
settings: {
dots: true,
infinite: true,
speed: 500,
fade: true,
cssEase: 'linear',
adaptiveHeight: true
}
}]
});
/* Get iframe src attribute value i.e.
YouTube video url
and store it in a variable */
var url = jQuery("#wpem-youtube-modal-popup .wpem-modal-content iframe").attr('src');
/* Assign empty url value to the iframe src attribute when
modal hide, which stop the video playing */
jQuery(".wpem-modal-close").on('click', function() {
jQuery("#wpem-youtube-modal-popup .wpem-modal-content iframe").attr('src', '');
});
jQuery(".wpem-modal-overlay").on('click', function() {
jQuery("#wpem-youtube-modal-popup .wpem-modal-content iframe").attr('src', '');
});
/* Assign the initially stored url back to the iframe src
attribute when modal is displayed again */
jQuery("#event-youtube-button").on('click', function() {
jQuery("#wpem-youtube-modal-popup .wpem-modal-content iframe").attr('src', url);
});
});
