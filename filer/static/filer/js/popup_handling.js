(function($) {
	dismissPopupAndReload = function(win) {
		document.location.reload();
		win.close();
	};
    fixMetadata = function (alt, caption, credit) {
		$('#id_alt_text').val(alt != 'None' ? alt : '');
		$('#id_caption_text').val(caption != 'None' ? caption : '');
		$('#id_credit_text').val(credit != 'None' ? credit : '');
	};
	updateImagePluginMetadata = function(chosenId) {
    	$.ajax({url: '/cmsplugin_filer_image/fetch_image_metadata',
    		data: {id : chosenId},
            beforeSend : function (xhr, settings) {
                $('#filerimage_form div.form-row.field-image').after('<div class="form-row temp-text-fetch-meta"><p class="help">Fetching metadata ... </p></div>');
            },
    		success : function (data) {
    			if (data) {
    				fixMetadata(data.alt, data.caption, data.credit);
    				$('#filerimage_form div.form-row.temp-text-fetch-meta').remove();
    			}
    		},
    		error: function(xhr){
    			$('#filerimage_form div.form-row.temp-text-fetch-meta').remove();
    		},
    	});
    };
	dismissRelatedImageLookupPopup = function(win, chosenId, chosenThumbnailUrl, chosenDescriptionTxt) {
		var name = windowname_to_id(win.name);
		var img_name = name + '_thumbnail_img';
		var txt_name = name + '_description_txt';
		var clear_name = name + '_clear';
		var elem = document.getElementById(name);
		var imgChanged = (document.getElementById(name).value != chosenId);
		document.getElementById(name).value = chosenId;
		document.getElementById(img_name).src = chosenThumbnailUrl;
		document.getElementById(txt_name).innerHTML = chosenDescriptionTxt;
		document.getElementById(clear_name).style.display = 'inline';
		win.close();
		if (imgChanged) {
			updateImagePluginMetadata(chosenId);
		}
	};
	dismissRelatedFolderLookupPopup = function(win, chosenId, chosenName) {
		var id = windowname_to_id(win.name);
		var id_name = id + '_description_txt';
		document.getElementById(id).value = chosenId;
		document.getElementById(id_name).innerHTML = chosenName;
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
		return showRelatedObjectLookupPopup(triggerlink);
	};
})(jQuery);
