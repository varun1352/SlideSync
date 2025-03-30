// DOM Elements
document.addEventListener('DOMContentLoaded', function() {
    const video = document.getElementById('video');
    const canvas = document.getElementById('canvas');
    const captureButton = document.getElementById('capture');
    const capturedImage = document.getElementById('capturedImage');
    const saveToDocButton = document.getElementById('saveToDoc');
    const retakeButton = document.getElementById('retake');
    const ocrResults = document.getElementById('ocrResults');
    const extractedText = document.getElementById('extractedText');
    const processingOverlay = document.getElementById('processingOverlay');
    const processingMessage = document.getElementById('processingMessage');
    const switchCameraButton = document.getElementById('switchCamera');
    const createDocBtn = document.getElementById('createDocBtn');
    const uploadForm = document.getElementById('uploadForm');
    const imageUpload = document.getElementById('imageUpload');

    // Camera settings
    let currentStream = null;
    let facingMode = "environment"; // Start with back camera
    
    // Document ID (will be set after creation if needed)
    let currentDocId = null;
    
    // Initialize camera when on camera tab
    async function initCamera() {
        try {
            const constraints = {
                video: {
                    facingMode: facingMode,
                    width: { ideal: 1920 },
                    height: { ideal: 1080 }
                }
            };
            
            if (currentStream) {
                currentStream.getTracks().forEach(track => track.stop());
            }
            
            const stream = await navigator.mediaDevices.getUserMedia(constraints);
            currentStream = stream;
            video.srcObject = stream;
        } catch (err) {
            console.error('Error accessing camera:', err);
            alert('Error accessing camera: ' + err.message);
        }
    }

    // Initialize camera on page load if on camera tab
    if (document.getElementById('camera-tab')) {
        document.getElementById('camera-tab').addEventListener('shown.bs.tab', initCamera);
        
        if (document.getElementById('camera-tab').classList.contains('active')) {
            initCamera();
        }
    } else {
        // If there are no tabs, just initialize camera
        initCamera();
    }

    // Switch between front and back cameras
    if (switchCameraButton) {
        switchCameraButton.addEventListener('click', () => {
            facingMode = facingMode === "environment" ? "user" : "environment";
            initCamera();
        });
    }

    // Create document button
    if (createDocBtn) {
        createDocBtn.addEventListener('click', () => {
            // Show processing overlay
            processingOverlay.style.display = 'flex';
            processingMessage.textContent = 'Creating document...';
            
            // Get event ID if available
            const eventId = createDocBtn.dataset.eventId || null;
            
            fetch('/create-slidesync-doc', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ 
                    event_id: eventId
                })
            })
            .then(response => response.json())
            .then(data => {
                processingOverlay.style.display = 'none';
                if (data.success) {
                    // Update the UI with the new document
                    const docInfo = document.getElementById('docInfo');
                    if (docInfo) {
                        docInfo.innerHTML = `
                            <a href="${data.doc_url}" 
                               target="_blank" 
                               class="btn btn-outline-primary btn-sm"
                               data-doc-id="${data.doc_id}">
                                Open class notes: ${data.doc_name}
                            </a>
                        `;
                    }
                    
                    // Create a hidden element to store doc ID
                    const docData = document.createElement('div');
                    docData.id = 'documentData';
                    docData.dataset.docId = data.doc_id;
                    docData.style.display = 'none';
                    document.body.appendChild(docData);
                    
                    // Update the current doc ID
                    currentDocId = data.doc_id;
                    
                    alert('Document created successfully!');
                } else {
                    alert('Error creating document: ' + (data.error || 'Unknown error'));
                }
            })
            .catch(error => {
                console.error('Error creating document:', error);
                processingOverlay.style.display = 'none';
                alert('Error creating document. Please try again.');
            });
        });
    }

    // Capture slide with camera
    if (captureButton) {
        captureButton.addEventListener('click', () => {
            // Set canvas dimensions to match video
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            
            // Draw video frame to canvas
            canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
            
            // Display captured image
            capturedImage.src = canvas.toDataURL('image/png');
            capturedImage.style.display = 'block';
            
            // Show buttons and hide capture
            video.style.display = 'none';
            captureButton.style.display = 'none';
            saveToDocButton.style.display = 'inline-block';
            retakeButton.style.display = 'inline-block';
            
            // Process image
            processImage(capturedImage.src);
        });
    }

    // Handle image upload
    if (uploadForm) {
        uploadForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const file = imageUpload.files[0];
            if (!file) {
                alert('Please select an image to upload');
                return;
            }
            
            // Show processing overlay
            processingOverlay.style.display = 'flex';
            processingMessage.textContent = 'Processing uploaded image...';
            
            // Create a FormData object
            const formData = new FormData();
            formData.append('image', file);
            
            // Send the image to the server
            fetch('/upload-image', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                // Hide processing overlay
                processingOverlay.style.display = 'none';
                
                if (data.success) {
                    // Display the processed image
                    capturedImage.src = data.processed_image;
                    capturedImage.style.display = 'block';
                    
                    // Display OCR results
                    if (data.text) {
                        extractedText.textContent = data.text;
                        ocrResults.style.display = 'block';
                    } else {
                        extractedText.textContent = 'No text could be extracted.';
                        ocrResults.style.display = 'block';
                    }
                    
                    // Show the save/retake buttons
                    saveToDocButton.style.display = 'inline-block';
                    retakeButton.style.display = 'inline-block';
                    
                    // Switch to the results view
                    if (document.getElementById('camera-tab') && document.getElementById('upload-tab')) {
                        document.getElementById('camera-tab').classList.remove('active');
                        document.getElementById('upload-tab').classList.remove('active');
                        document.getElementById('camera').classList.remove('show', 'active');
                        document.getElementById('upload').classList.remove('show', 'active');
                    }
                } else {
                    alert('Error processing image: ' + (data.error || 'Unknown error'));
                }
            })
            .catch(error => {
                console.error('Error processing uploaded image:', error);
                processingOverlay.style.display = 'none';
                alert('Error processing image. Please try again.');
            });
        });
    }

    // Process the captured image
    function processImage(imageData) {
        // Show processing overlay
        processingOverlay.style.display = 'flex';
        processingMessage.textContent = 'Processing slide...';
        
        // Send to server for processing
        fetch('/process-slide', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ image: imageData })
        })
        .then(response => response.json())
        .then(data => {
            // Hide processing overlay
            processingOverlay.style.display = 'none';
            
            // Display OCR results
            if (data.text) {
                extractedText.textContent = data.text;
                ocrResults.style.display = 'block';
            } else {
                extractedText.textContent = 'No text could be extracted.';
                ocrResults.style.display = 'block';
            }
            
            // Update image with processed version if available
            if (data.processed_image) {
                capturedImage.src = data.processed_image;
            }
        })
        .catch(error => {
            console.error('Error processing image:', error);
            processingOverlay.style.display = 'none';
            alert('Error processing image. Please try again.');
        });
    }

    // Retake photo
    if (retakeButton) {
        retakeButton.addEventListener('click', () => {
            // Check which tab was active
            const cameraTab = document.getElementById('camera-tab');
            const uploadTab = document.getElementById('upload-tab');
            
            if (cameraTab && uploadTab) {
                if (cameraTab.classList.contains('active')) {
                    // Reset camera view
                    video.style.display = 'block';
                    captureButton.style.display = 'block';
                    capturedImage.style.display = 'none';
                    saveToDocButton.style.display = 'none';
                    retakeButton.style.display = 'none';
                    ocrResults.style.display = 'none';
                } else if (uploadTab.classList.contains('active')) {
                    // Reset upload view
                    capturedImage.style.display = 'none';
                    saveToDocButton.style.display = 'none';
                    retakeButton.style.display = 'none';
                    ocrResults.style.display = 'none';
                    imageUpload.value = '';
                } else {
                    // If no tab is active, reset both
                    cameraTab.classList.add('active');
                    document.getElementById('camera').classList.add('show', 'active');
                    video.style.display = 'block';
                    captureButton.style.display = 'block';
                    capturedImage.style.display = 'none';
                    saveToDocButton.style.display = 'none';
                    retakeButton.style.display = 'none';
                    ocrResults.style.display = 'none';
                    imageUpload.value = '';
                    initCamera();
                }
            } else {
                // No tabs, just reset camera view
                video.style.display = 'block';
                captureButton.style.display = 'block';
                capturedImage.style.display = 'none';
                saveToDocButton.style.display = 'none';
                retakeButton.style.display = 'none';
                ocrResults.style.display = 'none';
                if (imageUpload) imageUpload.value = '';
                initCamera();
            }
        });
    }

    // Save to document
    if (saveToDocButton) {
        saveToDocButton.addEventListener('click', () => {
            // Show processing overlay
            processingOverlay.style.display = 'flex';
            processingMessage.textContent = 'Saving to document...';
            
            // Get the document ID from data attribute
            let docId = null;
            
            // Check both places where we might store the doc_id
            const docLink = document.querySelector('[data-doc-id]');
            const docData = document.getElementById('documentData');
            
            if (docLink) {
                docId = docLink.dataset.docId;
            } else if (docData) {
                docId = docData.dataset.docId;
            } else if (currentDocId) {
                docId = currentDocId;
            }
            
            if (!docId) {
                // No document yet, create one first
                processingMessage.textContent = 'Creating document...';
                
                // Get event ID if available
                const createBtn = document.getElementById('createDocBtn');
                const eventId = createBtn ? createBtn.dataset.eventId : null;
                
                fetch('/create-slidesync-doc', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ 
                        event_id: eventId
                    })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Use the new document ID
                        currentDocId = data.doc_id;
                        
                        // Update the UI
                        const docInfo = document.getElementById('docInfo');
                        if (docInfo) {
                            docInfo.innerHTML = `
                                <a href="${data.doc_url}" 
                                target="_blank" 
                                class="btn btn-outline-primary btn-sm"
                                data-doc-id="${data.doc_id}">
                                    Open class notes: ${data.doc_name}
                                </a>
                            `;
                        }
                        
                        // Now save the image to the new document
                        saveImageToDoc(data.doc_id);
                    } else {
                        processingOverlay.style.display = 'none';
                        alert('Error creating document: ' + (data.error || 'Unknown error'));
                    }
                })
                .catch(error => {
                    console.error('Error creating document:', error);
                    processingOverlay.style.display = 'none';
                    alert('Error creating document. Please try again.');
                });
            } else {
                // We have a document ID, save directly
                saveImageToDoc(docId);
            }
        });
    }
    
    // Helper function to save image to document
    function saveImageToDoc(docId) {
        processingMessage.textContent = 'Saving to document...';
        
        fetch('/save-to-doc', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                image: capturedImage.src,
                text: extractedText.textContent,
                doc_id: docId
            })
        })
        .then(response => response.json())
        .then(data => {
            processingOverlay.style.display = 'none';
            if (data.success) {
                // Instead of showing an alert, directly reset to camera view
                console.log('Slide saved successfully');
                
                // Reset to camera view
                resetToCameraView();
            } else {
                alert('Error saving to document: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error saving to document:', error);
            processingOverlay.style.display = 'none';
            alert('Error saving to document. Please try again.');
        });
    }

    // New function to reset directly to camera view
    function resetToCameraView() {
        // Check which tab was active and reset to camera tab
        const cameraTab = document.getElementById('camera-tab');
        
        if (cameraTab) {
            // Activate camera tab
            cameraTab.classList.add('active');
            document.getElementById('camera').classList.add('show', 'active');
            
            // Deactivate upload tab if it exists
            const uploadTab = document.getElementById('upload-tab');
            if (uploadTab) {
                uploadTab.classList.remove('active');
            }
            
            const uploadPane = document.getElementById('upload');
            if (uploadPane) {
                uploadPane.classList.remove('show', 'active');
            }
        }
        
        // Reset UI elements
        if (video) video.style.display = 'block';
        if (captureButton) captureButton.style.display = 'block';
        if (capturedImage) capturedImage.style.display = 'none';
        if (saveToDocButton) saveToDocButton.style.display = 'none';
        if (retakeButton) retakeButton.style.display = 'none';
        if (ocrResults) ocrResults.style.display = 'none';
        
        // Reset file input if it exists
        const imageUpload = document.getElementById('imageUpload');
        if (imageUpload) imageUpload.value = '';
        
        // Reinitialize camera
        initCamera();
    }
});