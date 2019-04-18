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

    CKEDITOR.config.allowedContent = true;
    CKEDITOR.config.height = 500;

    CKEDITOR.on('dialogDefinition', function( ev ) {
	  var diagName = ev.data.name;
	  var diagDefn = ev.data.definition;

	  if(diagName === 'table') {
	    var infoTab = diagDefn.getContents('info');

	    var width = infoTab.get('txtWidth');
	    width['default'] = "100%";

	    var cellSpacing = infoTab.get('txtCellSpace');
        cellSpacing['default'] = "0";
        var cellPadding = infoTab.get('txtCellPad');
        cellPadding['default'] = "0";
	  }
    });

    CKEDITOR.replace( 'id_value', {
            extraPlugins: ['justify', 'filebrowser', 'font'],
            font_names: '',
        }
    );


   if (false) {
    //       let csrftoken = getCookie('csrftoken')
    //       let l = ['#id_value']
    //       l.forEach(function(e){
    //          ckEditor =  ClassicEditor
    //               .create( document.querySelector(e),
    //               {
    //                  plugins: [
    //                    "Alignment",
    //                    "Essentials",
    //                    //"UploadAdapter",
    //                    "Autoformat",
    //                    "Bold",
    //                    "Italic",
    //                    "BlockQuote",
    //                    "CKFinder",
    //                    //"EasyImage",
    //                    "Heading",
    //                    //"Image",
    //                    //"ImageCaption",
    //                    //"ImageStyle",
    //                    //"ImageToolbar",
    //                    //"ImageUpload",
    //                    "Link",
    //                    "List",
    //                    //"MediaEmbed",
    //                    "Paragraph",
    //                    "PasteFromOffice",
    //                    "Table",
    //                    "TableToolbar",
    //                    "Font"
    //],
    //                  toolbar: ['heading',
    //                            '|',
    //                            'bold',
    //                            'italic',
    //                            'fontSize',
    //                            'alignment:left', 'alignment:right', 'alignment:center', 'alignment:justify',
    //                            'link',
    //                            'bulletedList',
    //                            'numberedList',
    //                            //'imageUpload',
    //                            'blockQuote',
    //                            'insertTable',
    //                            'mediaEmbed',
    //                            'undo',
    //                            'redo',],
    //                    table: {
    //                        contentToolbar: [ 'tableColumn', 'tableRow', 'mergeTableCells' ]
    //                    },
    //                    alignment: {options: [ 'left', 'right' ,'center','justify'] },
    //                    fontSize: {
    //                    options: [
    //                        9,
    //                        11,
    //                        13,
    //                        'default',
    //                        17,
    //                        19,
    //                        21,
    //			23,
    //			25,
    //                    ]
    //                },
    //
    //                  heading: {
    //                  options: [
    //                      { model: 'paragraph', title: 'Paragraph', class: 'ck-heading_paragraph' },
    //                      { model: 'heading1', view: 'h1', title: 'Heading 1', class: 'ck-heading_heading1' },
    //                      { model: 'heading2', view: 'h2', title: 'Heading 2', class: 'ck-heading_heading2' },
    //                      { model: 'heading3', view: 'h3', title: 'Heading 3', class: 'ck-heading_heading3' },
    //                      { model: 'heading4', view: 'h4', title: 'Heading 4', class: 'ck-heading_heading4' },
    //                      { model: 'heading5', view: 'h5', title: 'Heading 5', class: 'ck-heading_heading5' },
    //                      { model: 'heading6', view: 'h6', title: 'Heading 6', class: 'ck-heading_heading6' }]
    //                  },
    //
    //                   //plugins: [ Essentials, Paragraph, Bold, Italic ],
    //                   //toolbar: [ 'bold', 'italic' ]
    //               }
    //
    //                   )
    //               .then( editor => {
    //                   console.log( editor );
    //               } )
    //               .catch( error => {
    //                   console.error( error );
    //               } );
    //});
   }

}

document.addEventListener('DOMContentLoaded', initEditor, false);