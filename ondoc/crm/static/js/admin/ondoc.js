var jQuery = django.jQuery
jQuery(document).ready(function(){
    if (jQuery("div.field-cancel_type") && jQuery("div.field-cancellation_reason") && jQuery("div.field-cancellation_comments")){
        jQuery("div.field-cancel_type").hide();
        jQuery("div.field-cancellation_reason").hide();
        jQuery("div.field-cancellation_comments").hide();
        var status = jQuery("div.field-status select option:selected").val();
        var cancelled_status = jQuery("div.field-status div.readonly").text();
        console.log(cancelled_status);

        if(status==6){
                jQuery("div.field-cancel_type").show();
                jQuery("div.field-cancellation_reason").show();
                jQuery("div.field-cancellation_comments").show();
        }
        else{
                jQuery("div.field-cancel_type").hide();
                jQuery("div.field-cancellation_reason").hide();
                jQuery("div.field-cancellation_comments").hide();
        }
        jQuery('div.field-status select').change(function(){
            var status = jQuery("div.field-status select option:selected").val();
            if(status==6){
                    jQuery("div.field-cancel_type").show();
                    jQuery("div.field-cancellation_reason").show();
                    jQuery("div.field-cancellation_comments").show();
            }
            else{
                    jQuery("div.field-cancel_type").hide();
                    jQuery("div.field-cancellation_reason").hide();
                    jQuery("div.field-cancellation_comments").hide();
            }
        });
        if(cancelled_status.toLowerCase() == 'cancelled'){
        console.log('test');
                jQuery("div.field-cancellation_reason").show();
                jQuery("div.field-cancellation_comments").show();
        }
    }
	jQuery('body').on('change','#doctormobile_set-group .field-is_primary input', function() {
	    jQuery(this).closest('#doctormobile_set-group').find('.field-is_primary input').not(this).prop('checked',false)
	 });

	jQuery('body').on('change','#doctoremail_set-group .field-is_primary input', function() {
	    jQuery(this).closest('#doctoremail_set-group').find('.field-is_primary input').not(this).prop('checked',false)
	 });


});
