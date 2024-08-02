frappe.ui.form.on('Web Form', {
    refresh: function (frm) {
        let editor = Jodit.instances.jeditor_webform
        if (editor) {
            editor.value = frm.doc.introduction_text || "";
        }
        frm.trigger("load_custom_editor");   
    },

    onload: function (frm) {
        frm.trigger("load_custom_editor");   
    },
    load_custom_editor: function(frm){
        if (!Jodit.instances.jeditor_webform) {
           
            $('<textarea id="jeditor_webform"></textarea>').appendTo(frm.fields_dict.jodit_editor.wrapper);
            var ele = document.getElementById('jeditor_webform');
            var editor = new Jodit(ele);
            

            editor.value = frm.doc.introduction_text || "";
            ele.addEventListener('change', function () {
                frm.set_value("introduction_text", this.value);
            });
        }
    }
});