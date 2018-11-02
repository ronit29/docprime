 var $ = django.jQuery;

$( document ).ready(function(){
    if ($("div.field-cancel_type") && $("div.field-cancellation_reason") && $("div.field-cancellation_comments")){
        $("div.field-cancel_type").hide();
        $("div.field-cancellation_reason").hide();
        $("div.field-cancellation_comments").hide();
        var status = $("div.field-status select option:selected").val();
        if(status==6){
                $("div.field-cancel_type").show();
                $("div.field-cancellation_reason").show();
                $("div.field-cancellation_comments").show();
        }
        else{
                $("div.field-cancel_type").hide();
                $("div.field-cancellation_reason").hide();
                $("div.field-cancellation_comments").hide();
        }
        $('div.field-status select').change(function(){
            var status = $("div.field-status select option:selected").val();
            if(status==6){
                    $("div.field-cancel_type").show();
                    $("div.field-cancellation_reason").show();
                    $("div.field-cancellation_comments").show();
            }
            else{
                    $("div.field-cancel_type").hide();
                    $("div.field-cancellation_reason").hide();
                    $("div.field-cancellation_comments").hide();
            }
        });
    }
	$('body').on('change','#doctormobile_set-group .field-is_primary input', function() {
	    $(this).closest('#doctormobile_set-group').find('.field-is_primary input').not(this).prop('checked',false)
	 });

	$('body').on('change','#doctoremail_set-group .field-is_primary input', function() {
	    $(this).closest('#doctoremail_set-group').find('.field-is_primary input').not(this).prop('checked',false)
	 });


});
