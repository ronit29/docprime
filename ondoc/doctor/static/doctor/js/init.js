function getCookie(name) {
   var cookieValue = null;
   if (document.cookie && document.cookie !== '') {
       var cookies = document.cookie.split(';');
       for (var i = 0; i < cookies.length; i++) {
           var cookie = django.jQuery.trim(cookies[i]);
           // Does this cookie string begin with the name we want?
           if (cookie.substring(0, name.length + 1) === (name + '=')) {
               cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
               break;
           }
       }
   }
   return cookieValue;
}

function initEditor(){
    let csrftoken = getCookie('csrftoken')
    let url = '/api/v1/admin/articles/upload-image?type=Files&csrf_token='+csrftoken;

    CKEDITOR.config.allowedContent = true;
    CKEDITOR.config.height = 500;

    CKEDITOR.replace( 'id_new_about', {
            extraPlugins: ['justify', 'font'],
            font_names: '',
        }
    );
}

document.addEventListener('DOMContentLoaded', initEditor, false);