(function($) {
    dismissPopupAndReload = function(win) {
        document.location.reload();
        win.close();
    };
    dismissRelatedImageLookupPopup = function(win, chosenId, chosenThumbnailUrl, chosenDescriptionTxt, file_url) {
        var name = windowname_to_id(win.name);
        var img_name = name + '_thumbnail_img';
        var txt_name = name + '_description_txt';
        var clear_name = name + '_clear';
        var link_name = name + '_link_to_file';
        var elem = document.getElementById(name);
        document.getElementById(name).value = chosenId;
        var img_element = document.getElementById(img_name);
        var use_full_image = img_element.attributes["data-use-full-image"];
        if (!use_full_image || !file_url) {
            img_element.src = chosenThumbnailUrl;
        } else {
            img_element.src = file_url;
        }
        img_element.classList.remove("no-filer-image")
        var description = document.getElementById(txt_name);
        if (description) {
            description.innerHTML = chosenDescriptionTxt;
        }
        document.getElementById(clear_name).style.display = 'inline';
        var link = document.getElementById(link_name);
        if (link && file_url) {
            link.href = file_url;
        }
        win.close();
    };
    dismissRelatedFolderLookupPopup = function(win, chosenId, chosenName) {
        var id = windowname_to_id(win.name);
        var id_name = id + '_description_txt';
        document.getElementById(id).value = chosenId;
        document.getElementById(id_name).innerHTML = chosenName;
        document.getElementById(id + '_clear').style.display = 'inline';
        win.close();
    };
    showRelatedFilerObjectLookupPopup = function(triggerlink){
        if (typeof current_site !== 'undefined' && current_site == parseInt(current_site)){
            if (triggerlink.href.indexOf("current_site=") == -1){
                var new_link;
                if (triggerlink.href.search(/\?/) >= 0) {
                    new_link = triggerlink.href + '&current_site=' + current_site;
                } else {
                    new_link = triggerlink.href + '?current_site=' + current_site;
                }
                triggerlink.href = new_link;
            }
        }
        return _showRelatedObjectLookupPopup(triggerlink);
    };
    _showRelatedObjectLookupPopup = function (triggeringLink) {
    var name = triggeringLink.id.replace(/^lookup_/, '');
    name = id_to_windowname(name);
    var href;
    if (triggeringLink.href.search(/\?/) >= 0) {
        href = triggeringLink.href + '&_popup=1';
    } else {
        href = triggeringLink.href + '?_popup=1';
    }
    var win = window.open(href, name, 'height=500,width=1120,resizable=yes,scrollbars=yes');
    win.focus();
    return false;
    };
})(jQuery);

