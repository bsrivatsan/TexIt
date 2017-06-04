// these sizes are based on recommendations from MathPix as best uses for their API
var MAX_WIDTH = 500;
var MAX_HEIGHT = 250;

/* The ACE editor is an open source JavaScript based editor.
*
* https://ace.c9.io/
*
* The implementation code is based on the tutorial found on their website.
*
*
* */

var editor = ace.edit("editor");
editor.setTheme("ace/theme/sqlserver");
editor.getSession().setMode("ace/mode/latex");
editor.getSession().setUseWrapMode(true);
editor.setShowPrintMargin(false);
editor.setOption("minLines", 10);
editor.setAutoScrollEditorIntoView(true);

var fixHeight = function() {
  $('#editor').height($(window).height() - 64);
};
fixHeight();

/* JCrop is an open source plugin designed for image editors.
*
* This code is largely taken from an example template provided by the vendor.
*
* Changes specific to this project are found in the modified clearCoords funciton.
* */
var jcrop_api;
var snackbarContainer = document.querySelector('#demo-toast-example');

// Set up general jcrop instance.
// Because the image is loaded dynamically, there may be problems with finding the size of the image.
// That's why this code is borrowed from http://stackoverflow.com/questions/318630/get-the-real-width-and-height-of-an-image-with-javascript-in-safari-chrome
var img = $("img")[0]; // Get my img elem
var pic_real_width, pic_real_height;
$("<img/>")
    .attr("src", $(img).attr("src"))
    .load(function() {
        pic_real_width = this.width;
        pic_real_height = this.height;
    });

jQuery(function($){
    $('#target').Jcrop({
        onChange:   showCoords,
        onSelect:   showCoords,
        maxSize: [ MAX_WIDTH, MAX_HEIGHT ]
    },function(){
        jcrop_api = this;
    });

    $('#coords').on('change','input',function(e){
        var x1 = $('#x1').val(),
            x2 = $('#x2').val(),
            y1 = $('#y1').val(),
            y2 = $('#y2').val();
        jcrop_api.setSelect([x1,y1,x2,y2]);
    });
});
var x;
var y;
var w;
var h;
// Simple event handler, called from onChange and onSelect
// event handlers, as per the Jcrop invocation above


function showCoords(c)
{
    x = c.x;
    y = c.y;
    w = c.w;
    h = c.h;
    console.log(x);
};
// Handle submission of new box
function clearCoords(upload_id, image_url, latex_url)
{
    // snackbar code is taken from examples on the Material Design Lite website.
    if (w == 0 || h == 0 || !x) {
        var data = {
            message: 'You must select a box first',
            timeout: 1500,
        };
        snackbarContainer.MaterialSnackbar.showSnackbar(data);
        return;
    }
    console.log("clear");
    jcrop_api.release();
    width = $(img).width();
    height = $(img).height();
    x = (x / width) * pic_real_width;
    y = (y / height) * pic_real_height;
    w = (w / width) * pic_real_width;
    h = (h / height) * pic_real_height;
    var form = document.createElement("form");
    form.setAttribute("method", 'POST');
    form.setAttribute("action", "/box_upload/");

    // this workaround from http://stackoverflow.com/questions/133925/javascript-post-request-like-a-form-submit
    // it is a convenient means of submitting a complex post request without worrying about AJax asynchronus calls.
    var hiddenField = document.createElement("input");
    hiddenField.setAttribute("type", "hidden");
    hiddenField.setAttribute("name", "x");
    hiddenField.setAttribute("value", x);
    form.appendChild(hiddenField);

    hiddenField = document.createElement("input");
    hiddenField.setAttribute("type", "hidden");
    hiddenField.setAttribute("name", "y");
    hiddenField.setAttribute("value", y);
    form.appendChild(hiddenField);

    hiddenField = document.createElement("input");
    hiddenField.setAttribute("type", "hidden");
    hiddenField.setAttribute("name", "w");
    hiddenField.setAttribute("value", w);
    form.appendChild(hiddenField);

    hiddenField = document.createElement("input");
    hiddenField.setAttribute("type", "hidden");
    hiddenField.setAttribute("name", "h");
    hiddenField.setAttribute("value", h);
    form.appendChild(hiddenField);

    hiddenField = document.createElement("input");
    hiddenField.setAttribute("type", "hidden");
    hiddenField.setAttribute("name", "upload_id");
    hiddenField.setAttribute("value", upload_id);
    form.appendChild(hiddenField);

    hiddenField = document.createElement("input");
    hiddenField.setAttribute("type", "hidden");
    hiddenField.setAttribute("name", "image_url");
    hiddenField.setAttribute("value", image_url);
    form.appendChild(hiddenField);

    hiddenField = document.createElement("input");
    hiddenField.setAttribute("type", "hidden");
    hiddenField.setAttribute("name", "latex_url");
    hiddenField.setAttribute("value", latex_url);
    form.appendChild(hiddenField);

    document.body.appendChild(form);
    form.submit();

    $("#editor-cover").toggleClass("hidden");
    setTimeout(function(){
        $("#editor-cover").toggleClass("hidden");
        var data = {
            message: 'LaTeX Updated',
            timeout: 1500,
            actionHandler: showCoords,
            actionText: 'Undo'
        };
        snackbarContainer.MaterialSnackbar.showSnackbar(data);
    }, 1000);
};