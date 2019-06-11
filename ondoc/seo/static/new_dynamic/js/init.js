$ = django.jQuery;
$( document ).ready(function() {
    var div = document.createElement("ul");
    div.setAttribute("id", "custom_dropdown");
    var div_elem = document.getElementsByClassName('field-url_value');
    div_elem[0].appendChild(div);
    console.log($('ul#custom_dropdown li'));
    $(document).on('click', 'ul#custom_dropdown li',function(e){
        var clicked_li = $(this).html();
        $('input#id_url_value').val(clicked_li);
        document.getElementById('custom_dropdown').innerHTML = '';
    });

    //$("#id_url_value").on('change', function(e){
    $(document).on('change keyup paste', "#id_url_value", function(e) {
    
    var query = $(this).val();
        $.ajax({
                    type: "GET",
                    url:  '/api/v1/common/entity-compare-autocomplete',
                    data: {"query": query},
                    success: function(response) {
                        document.getElementById('custom_dropdown').innerHTML = '';
                         if(response){
                             var data = response;
                              $.each(data, function(k, v) {
                               var li_elem = '<li>'+v+'</li>';
                                $(li_elem).appendTo('#custom_dropdown');
                              });
                          }
                    },
                    error: function (request, status, error) {
                        console.log(error);
                    }
               });
    } );
});

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
   let l = ['#id_top_content', '#id_bottom_content']
   l.forEach(function(e){
          ckEditor =  ClassicEditor
               .create( document.querySelector(e),
               {
                  heading: {
                  options: [
                      { model: 'paragraph', title: 'Paragraph', class: 'ck-heading_paragraph' },
                      { model: 'heading1', view: 'h1', title: 'Heading 1', class: 'ck-heading_heading1' },
                      { model: 'heading2', view: 'h2', title: 'Heading 2', class: 'ck-heading_heading2' },
                      { model: 'heading3', view: 'h3', title: 'Heading 3', class: 'ck-heading_heading3' },
                      { model: 'heading4', view: 'h4', title: 'Heading 4', class: 'ck-heading_heading4' },
                      { model: 'heading5', view: 'h5', title: 'Heading 5', class: 'ck-heading_heading5' },
                      { model: 'heading6', view: 'h6', title: 'Heading 6', class: 'ck-heading_heading6' }]
                  },

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
});

}

document.addEventListener('DOMContentLoaded', initEditor, false);

//border: 1px solid #f2f2f2;
//    height: 200px;
//    overflow: auto;
//    width: 320px;