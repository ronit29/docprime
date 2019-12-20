function initEditor(){

    var tnc_value = document.getElementById("id_tnc").value
    CKEDITOR.config.allowedContent = true;
    CKEDITOR.config.height = 500;

    CKEDITOR.replace( 'id_tnc', {
            extraPlugins: ['justify', 'font'],
            font_names: '',
        }
    );
    CKEDITOR.instances.id_tnc.on('instanceReady', function() {
       CKEDITOR.instances.id_tnc.setData( tnc_value );
    });
}

document.addEventListener('DOMContentLoaded', initEditor, false);