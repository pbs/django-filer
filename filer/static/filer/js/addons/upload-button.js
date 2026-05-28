// #UPLOAD BUTTON#
// This script implements the upload button logic
'use strict';

import Dropzone from 'dropzone';

/* globals Cl */

const DEBUG_PREFIX = '[Filer Upload]';

document.addEventListener('DOMContentLoaded', () => {
    console.log(`${DEBUG_PREFIX} DOMContentLoaded fired, initializing upload button...`);

    let submitNum = 0;
    let maxSubmitNum = 1;
    const uploadButton = document.querySelector('.js-upload-button');
    if (!uploadButton) {
        console.warn(`${DEBUG_PREFIX} Upload button element (.js-upload-button) NOT found in DOM. Aborting.`);
        return;
    }
    console.log(`${DEBUG_PREFIX} Upload button element found:`, uploadButton);

    const uploadButtonDisabled = document.querySelector('.js-upload-button-disabled');
    const uploadUrl = uploadButton.dataset.url;
    console.log(`${DEBUG_PREFIX} Upload URL: ${uploadUrl}`);
    console.log(`${DEBUG_PREFIX} Upload button dataset:`, JSON.stringify(uploadButton.dataset));

    if (!uploadUrl) {
        console.error(`${DEBUG_PREFIX} Upload URL is missing! Check data-url attribute on .js-upload-button`);
    }

    const uploadWelcome = document.querySelector('.js-filer-dropzone-upload-welcome');
    const uploadInfoContainer = document.querySelector('.js-filer-dropzone-upload-info-container');
    const uploadInfo = document.querySelector('.js-filer-dropzone-upload-info');
    const uploadNumber = document.querySelector('.js-filer-dropzone-upload-number');
    const uploadFileNameSelector = '.js-filer-dropzone-file-name';
    const uploadProgressSelector = '.js-filer-dropzone-progress';
    const uploadSuccess = document.querySelector('.js-filer-dropzone-upload-success');
    const uploadCanceled = document.querySelector('.js-filer-dropzone-upload-canceled');
    const uploadCancel = document.querySelector('.js-filer-dropzone-cancel');
    const infoMessage = document.querySelector('.js-filer-dropzone-info-message');
    const hiddenClass = 'hidden';
    const maxUploaderConnections = parseInt(uploadButton.dataset.maxUploaderConnections || 3, 10);
    const maxFilesize = parseInt(uploadButton.dataset.maxFilesize || 0, 10);
    let hasErrors = false;

    console.log(`${DEBUG_PREFIX} Config: maxUploaderConnections=${maxUploaderConnections}, maxFilesize=${maxFilesize}MB`);
    console.log(`${DEBUG_PREFIX} DOM elements found: uploadWelcome=${!!uploadWelcome}, uploadInfoContainer=${!!uploadInfoContainer}, uploadInfo=${!!uploadInfo}, uploadCancel=${!!uploadCancel}`);

    const updateUploadNumber = () => {
        if (uploadNumber) {
            uploadNumber.textContent = `${maxSubmitNum - submitNum}/${maxSubmitNum}`;
        }
    };

    const removeButton = () => {
        if (uploadButton) {
            uploadButton.remove();
        }
    };

    // utility
    const updateQuery = (uri, key, value) => {
        const re = new RegExp(`([?&])${key}=.*?(&|$)`, 'i');
        const separator = uri.indexOf('?') !== -1 ? '&' : '?';
        const hash = window.location.hash;
        uri = uri.replace(/#.*$/, '');
        if (uri.match(re)) {
            return uri.replace(re, `$1${key}=${value}$2`) + hash;
        } else {
            return uri + separator + key + '=' + value + hash;
        }
    };

    const reloadOrdered = () => {
        const uri = window.location.toString();
        window.location.replace(updateQuery(uri, 'order_by', '-modified_at'));
    };

    Cl.mediator.subscribe('filer-upload-in-progress', removeButton);

    // Initialize Dropzone on the upload button
    Dropzone.autoDiscover = false;
    console.log(`${DEBUG_PREFIX} Creating Dropzone instance...`);

    let dropzone;
    try {
        dropzone = new Dropzone(uploadButton, {
            url: uploadUrl,
            paramName: 'file',
            maxFilesize: maxFilesize,  // already in MB
            parallelUploads: maxUploaderConnections,
            clickable: uploadButton,
            previewTemplate: '<div></div>',
            addRemoveLinks: false,
            autoProcessQueue: true
        });
        console.log(`${DEBUG_PREFIX} Dropzone instance created successfully.`);
    } catch (e) {
        console.error(`${DEBUG_PREFIX} Failed to create Dropzone instance:`, e);
        return;
    }

    dropzone.on('addedfile', (file) => {
        console.log(`${DEBUG_PREFIX} File added: "${file.name}" (${file.size} bytes, type: ${file.type})`);
        Cl.mediator.remove('filer-upload-in-progress', removeButton);
        Cl.mediator.publish('filer-upload-in-progress');
        submitNum++;

        maxSubmitNum = dropzone.files.length;
        console.log(`${DEBUG_PREFIX} Queue: submitNum=${submitNum}, maxSubmitNum=${maxSubmitNum}, totalFiles=${dropzone.files.length}`);

        if (infoMessage) {
            infoMessage.classList.remove(hiddenClass);
        }
        if (uploadWelcome) {
            uploadWelcome.classList.add(hiddenClass);
        }
        if (uploadSuccess) {
            uploadSuccess.classList.add(hiddenClass);
        }
        if (uploadInfoContainer) {
            uploadInfoContainer.classList.remove(hiddenClass);
        }
        if (uploadCancel) {
            uploadCancel.classList.remove(hiddenClass);
        }
        if (uploadCanceled) {
            uploadCanceled.classList.add(hiddenClass);
        }

        updateUploadNumber();
    });

    dropzone.on('sending', (file, xhr, formData) => {
        console.log(`${DEBUG_PREFIX} Sending file: "${file.name}" to ${uploadUrl}`);
        console.log(`${DEBUG_PREFIX} XHR readyState: ${xhr.readyState}`);
    });

    dropzone.on('uploadprogress', (file, progress) => {
        const percent = Math.round(progress);
        console.log(`${DEBUG_PREFIX} Upload progress: "${file.name}" ${percent}%`);
        const fileId = `file-${encodeURIComponent(file.name)}${file.size}${file.lastModified}`;
        const fileItem = document.getElementById(fileId);
        let uploadInfoClone;

        if (fileItem) {
            const progressBar = fileItem.querySelector(uploadProgressSelector);
            if (progressBar) {
                progressBar.style.width = `${percent}%`;
            }
        } else if (uploadInfo) {
            uploadInfoClone = uploadInfo.cloneNode(true);

            const fileNameEl = uploadInfoClone.querySelector(uploadFileNameSelector);
            if (fileNameEl) {
                fileNameEl.textContent = file.name;
            }
            const progressEl = uploadInfoClone.querySelector(uploadProgressSelector);
            if (progressEl) {
                progressEl.style.width = `${percent}%`;
            }
            uploadInfoClone.classList.remove(hiddenClass);
            uploadInfoClone.setAttribute('id', fileId);
            if (uploadInfoContainer) {
                uploadInfoContainer.appendChild(uploadInfoClone);
            }
        }
    });

    dropzone.on('success', (file, response) => {
        console.log(`${DEBUG_PREFIX} Upload SUCCESS: "${file.name}"`, response);
        const fileId = `file-${encodeURIComponent(file.name)}${file.size}${file.lastModified}`;
        const fileEl = document.getElementById(fileId);
        if (fileEl) {
            fileEl.remove();
        }

        if (response.error) {
            hasErrors = true;
            console.error(`${DEBUG_PREFIX} Server returned error for "${file.name}": ${response.error}`);
            window.filerShowError(`${file.name}: ${response.error}`);
        }

        submitNum--;
        updateUploadNumber();
        console.log(`${DEBUG_PREFIX} Remaining uploads: ${submitNum}`);

        if (submitNum === 0) {
            console.log(`${DEBUG_PREFIX} All uploads complete. hasErrors=${hasErrors}. Reloading...`);
            maxSubmitNum = 1;

            if (uploadWelcome) {
                uploadWelcome.classList.add(hiddenClass);
            }
            if (uploadNumber) {
                uploadNumber.classList.add(hiddenClass);
            }
            if (uploadCanceled) {
                uploadCanceled.classList.add(hiddenClass);
            }
            if (uploadCancel) {
                uploadCancel.classList.add(hiddenClass);
            }
            if (uploadSuccess) {
                uploadSuccess.classList.remove(hiddenClass);
            }

            if (hasErrors) {
                setTimeout(reloadOrdered, 1000);
            } else {
                reloadOrdered();
            }
        }
    });

    dropzone.on('error', (file, errorMessage) => {
        console.error(`${DEBUG_PREFIX} Upload ERROR: "${file.name}"`, errorMessage);
        const fileId = `file-${encodeURIComponent(file.name)}${file.size}${file.lastModified}`;
        const fileEl = document.getElementById(fileId);
        if (fileEl) {
            fileEl.remove();
        }

        hasErrors = true;
        window.filerShowError(`${file.name}: ${errorMessage}`);

        submitNum--;
        updateUploadNumber();
        console.log(`${DEBUG_PREFIX} Remaining uploads after error: ${submitNum}`);

        if (submitNum === 0) {
            console.log(`${DEBUG_PREFIX} All uploads complete (with errors). Reloading...`);
            maxSubmitNum = 1;

            if (uploadWelcome) {
                uploadWelcome.classList.add(hiddenClass);
            }
            if (uploadNumber) {
                uploadNumber.classList.add(hiddenClass);
            }
            if (uploadCanceled) {
                uploadCanceled.classList.add(hiddenClass);
            }
            if (uploadCancel) {
                uploadCancel.classList.add(hiddenClass);
            }
            if (uploadSuccess) {
                uploadSuccess.classList.remove(hiddenClass);
            }

            setTimeout(reloadOrdered, 1000);
        }
    });

    dropzone.on('canceled', (file) => {
        console.warn(`${DEBUG_PREFIX} Upload CANCELED: "${file.name}"`);
    });

    dropzone.on('complete', (file) => {
        console.log(`${DEBUG_PREFIX} Upload COMPLETE: "${file.name}" status=${file.status}`);
    });

    if (uploadCancel) {
        uploadCancel.addEventListener('click', (clickEvent) => {
            clickEvent.preventDefault();
            uploadCancel.classList.add(hiddenClass);
            if (uploadNumber) {
                uploadNumber.classList.add(hiddenClass);
            }
            if (uploadInfoContainer) {
                uploadInfoContainer.classList.add(hiddenClass);
            }
            if (uploadCanceled) {
                uploadCanceled.classList.remove(hiddenClass);
            }

            setTimeout(() => {
                window.location.reload();
            }, 1000);
        });
    }

    if (uploadButtonDisabled && Cl.filerTooltip) {
        Cl.filerTooltip();
    }

    // Fire custom event after scripts have been executed
    console.log(`${DEBUG_PREFIX} Dispatching filer-upload-scripts-executed event.`);
    document.dispatchEvent(new Event('filer-upload-scripts-executed'));
});
