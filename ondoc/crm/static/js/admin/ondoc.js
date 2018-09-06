var $ = django.jQuery;

$( document ).ready(function(){
	$("div.field-cancel_type").hide();
	$('div.field-status select').change(function(){
		var status = $("div.field-status select option:selected").val();
		if(status==6){
				$("div.field-cancel_type").show();
		}
		else{
				$("div.field-cancel_type").hide();
		}
	});

	$('body').on('change','#doctormobile_set-group .field-is_primary input', function() {
	    $(this).closest('#doctormobile_set-group').find('.field-is_primary input').not(this).prop('checked',false) 
	 });

	$('body').on('change','#doctoremail_set-group .field-is_primary input', function() {
	    $(this).closest('#doctoremail_set-group').find('.field-is_primary input').not(this).prop('checked',false) 
	 });


});
