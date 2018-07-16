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

   let url = '/articles/upload-image?csrf_token='+csrftoken;
          ckEditor =  ClassicEditor
               .create( document.querySelector('#id_body'),
               {
                  ckfinder: {
                       uploadUrl: url
                   }

                   //plugins: [ Essentials, Paragraph, Bold, Italic ],
                   //toolbar: [ 'bold', 'italic' ]
               }

                   )
               .then( editor => {
                   console.log( editor );
               } )
               .catch( error => {
                   console.error( error );
               } );
}

document.addEventListener('DOMContentLoaded', initEditor, false);