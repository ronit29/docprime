function initEditor(){

            ClassicEditor
                .create( document.querySelector('#id_body'),
                {
                   ckfinder: {
                        uploadUrl: '/articles/upload-image'
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