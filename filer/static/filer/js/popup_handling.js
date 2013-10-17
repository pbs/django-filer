(function($) {
	dismissPopupAndReload = function(win) {
		document.location.reload();
		win.close();
	};
	cropdusterCheckAndDismiss = function(win, cropduster_url, size_set, chosenId, chosenThumbnailUrl, chosenDescriptionTxt){
		if (cropduster_url && size_set) {
                    var url = cropduster_url + "?pop=1&size_set=" + size_set + "&next_stage=crop_images&image=" + chosenId;
                    var new_win = window.open(url, '', 'height=500,width=800,resizable=yes,scrollbars=yes');
                    new_win.dismissRelatedImageLookupPopup = opener.dismissRelatedImageLookupPopup;
                    new_win.focus();
                    win.close();
		} else {
                        opener.dismissRelatedImageLookupPopup(win, chosenId, chosenThumbnailUrl, chosenDescriptionTxt);
                }
            return false;
        };
	dismissRelatedImageLookupPopup = function(win, chosenId, chosenThumbnailUrl, chosenDescriptionTxt) {
		var name = windowname_to_id(win.name);
		var img_name = name + '_thumbnail_img';
		var txt_name = name + '_description_txt';
		var clear_name = name + '_clear';
		var elem = document.getElementById(name);
		document.getElementById(name).value = chosenId;
		document.getElementById(img_name).src = chosenThumbnailUrl;
		document.getElementById(txt_name).innerHTML = chosenDescriptionTxt;
		document.getElementById(clear_name).style.display = 'inline';
		win.close();
	};
	dismissRelatedFolderLookupPopup = function(win, chosenId, chosenName) {
		var id = windowname_to_id(win.name);
		var id_name = id + '_description_txt';
		document.getElementById(id).value = chosenId;
		document.getElementById(id_name).innerHTML = chosenName;
		win.close();
	};
})(jQuery);
