var $ = django.jQuery;

$( document ).ready(function(){

$('body').on('change','#doctormobile_set-group .field-is_primary input', function() {
    $(this).closest('#doctormobile_set-group').find('.field-is_primary input').not(this).prop('checked',false) 
 });

$('body').on('change','#doctoremail_set-group .field-is_primary input', function() {
    $(this).closest('#doctoremail_set-group').find('.field-is_primary input').not(this).prop('checked',false) 
 });


});
