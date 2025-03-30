// slidesync.js - Consolidated and cleaned up version

// Declare global variables and functions that need to be accessed across event handlers
let currentDocId = null;
let currentStream = null;
let facingMode = "environment"; // Start with back camera

// Function to show create event modal with default times
function showCreateEventModal() {
    const eventModal = new bootstrap.Modal(document.getElementById('createEventModal'));
    eventModal.show();
    
    // Initialize datetime picker for the event
    const startTimeInput = document.getElementById('eventStartTime');
    const endTimeInput = document.getElementById('eventEndTime');
    
    // Set default values (current time, rounded to nearest half hour)
    const now = new Date();
    now.setMinutes(Math.ceil(now.getMinutes() / 30) * 30); // Round up to nearest 30min
    
    const later = new Date(now);
    later.setHours(later.getHours() + 1); // Default 1 hour event
    
    // Format for datetime-local input
    const formatDateTime = (date) => {
        return date.toISOString().slice(0, 16); // Format: YYYY-MM-DDThh:mm
    };
    
    startTimeInput.value = formatDateTime(now);
    endTimeInput.value = formatDateTime(later);
}

// Toast notification function available globally
function showToast(message, type = 'info') {
    // Create toast container if it doesn't exist
    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        document.body.appendChild(toastContainer);
    }
    
    // Create a unique ID for this toast
    const toastId = 'toast-' + Date.now();
    
    // Set icon based on type
    let icon = '';
    let bgColor = '';
    
    switch(type) {
        case 'success':
            icon = '<i class="bi bi-check-circle-fill me-2"></i>';
            bgColor = 'bg-success';
            break;
        case 'error':
            icon = '<i class="bi bi-exclamation-circle-fill me-2"></i>';
            bgColor = 'bg-danger';
            break;
        case 'warning':
            icon = '<i class="bi bi-exclamation-triangle-fill me-2"></i>';
            bgColor = 'bg-warning';
            break;
        default:
            icon = '<i class="bi bi-info-circle-fill me-2"></i>';
            bgColor = 'bg-info';
    }
    
    // Create toast HTML
    const toastHTML = `
        <div id="${toastId}" class="toast align-items-center ${bgColor} text-white border-0" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body">
                    ${icon}${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        </div>
    `;
    
    // Append toast to container
    toastContainer.innerHTML += toastHTML;
    
    // Initialize and show the toast
    const toastElement = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastElement, { delay: 3000 });
    toast.show();
    
    // Remove toast from DOM after it's hidden
    toastElement.addEventListener('hidden.bs.toast', function() {
        toastElement.remove();
    });
}

// Initialize camera function (defined globally for access by navigation handlers)
async function initCamera() {
    const video = document.getElementById('video');
    if (!video) return; // Exit if video element doesn't exist
    
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
        
        // Show friendly error message
        const cameraContainer = document.querySelector('.camera-container');
        if (cameraContainer) {
            cameraContainer.innerHTML = `
                <div class="text-center p-4">
                    <i class="bi bi-camera-video-off" style="font-size: 3rem; color: var(--error-color);"></i>
                    <h4 class="mt-3">Camera Access Error</h4>
                    <p class="text-muted mb-3">${err.message}</p>
                    <p>Please check your camera permissions or try the Upload tab instead.</p>
                    <button id="tryAgainBtn" class="btn btn-primary mt-2">Try Again</button>
                </div>
            `;
            
            // Add event listener to try again button
            const tryAgainBtn = document.getElementById('tryAgainBtn');
            if (tryAgainBtn) {
                tryAgainBtn.addEventListener('click', initCamera);
            }
        }
    }
}

// Main initialization code
document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
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
    const resultsSection = document.getElementById('resultsSection');
    const createEventForm = document.getElementById('createEventForm');

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
        // First check if there's no current event to show event modal instead
        if (createDocBtn && !createDocBtn.dataset.eventId) {
            createDocBtn.innerHTML = '<i class="bi bi-calendar-plus me-2"></i>Create Event & Doc';
            createDocBtn.addEventListener('click', function(e) {
                e.preventDefault();
                showCreateEventModal();
            });
        } else {
            // Normal document creation for existing event
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
                                   class="btn btn-primary"
                                   data-doc-id="${data.doc_id}">
                                    <i class="bi bi-journal-text me-2"></i>Open Class Notes
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
                        
                        // Show success toast instead of alert
                        showToast('Document created successfully!', 'success');
                    } else {
                        showToast('Error creating document: ' + (data.error || 'Unknown error'), 'error');
                    }
                })
                .catch(error => {
                    console.error('Error creating document:', error);
                    processingOverlay.style.display = 'none';
                    showToast('Error creating document. Please try again.', 'error');
                });
            });
        }
    }

    // Capture slide with camera
    if (captureButton) {
        captureButton.addEventListener('click', () => {
            console.log("Capture button clicked");
            
            // Check if video is playing
            if (!video || !video.videoWidth) {
                console.error("Video not ready or no dimensions available");
                showToast("Camera not ready. Please wait or refresh the page.", "error");
                return;
            }
            
            // Set canvas dimensions to match video
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            
            console.log(`Canvas dimensions set to: ${canvas.width}x${canvas.height}`);
            
            // Draw video frame to canvas
            canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
            
            // Get image data and explicitly set it on the image element
            const imageData = canvas.toDataURL('image/png');
            
            // Set captured image source
            capturedImage.src = imageData;
            capturedImage.style.display = 'block';
            
            // Make sure results section is visible and properly styled
            resultsSection.style.display = 'block';
            
            // Hide camera view elements
            document.getElementById('captureTabContent').style.display = 'none';
            document.querySelector('.nav-tabs').style.display = 'none';
            
            // Process image
            processImage(imageData);
        });
    }

    // Handle image upload
    if (uploadForm) {
        uploadForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const file = imageUpload.files[0];
            if (!file) {
                showToast('Please select an image to upload', 'warning');
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
                    
                    // Show results section and hide capture tabs
                    resultsSection.style.display = 'block';
                    document.getElementById('captureTabContent').style.display = 'none';
                    document.querySelector('.nav-tabs').style.display = 'none';
                    
                    // Display OCR results
                    if (data.text) {
                        extractedText.textContent = data.text;
                    } else {
                        extractedText.textContent = 'No text could be extracted.';
                    }
                } else {
                    showToast('Error processing image: ' + (data.error || 'Unknown error'), 'error');
                }
            })
            .catch(error => {
                console.error('Error processing uploaded image:', error);
                processingOverlay.style.display = 'none';
                showToast('Error processing image. Please try again.', 'error');
            });
        });
    }

    // Process the captured image
    function processImage(imageData) {
        // Show processing overlay
        processingOverlay.style.display = 'flex';
        processingMessage.textContent = 'Processing slide...';
        
        // Make sure image is still displayed during processing
        capturedImage.src = imageData;
        capturedImage.style.display = 'block';
        
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
            } else {
                extractedText.textContent = 'No text could be extracted.';
            }
            
            // Update image with processed version if available
            if (data.processed_image) {
                capturedImage.src = data.processed_image;
                capturedImage.style.display = 'block';
            }
            
            // Make sure the results section is fully visible
            resultsSection.style.display = 'block';
        })
        .catch(error => {
            console.error('Error processing image:', error);
            processingOverlay.style.display = 'none';
            showToast('Error processing image. Please try again.', 'error');
        });
    }

    // Retake photo
    if (retakeButton) {
        retakeButton.addEventListener('click', () => {
            // Show tabs again
            document.getElementById('captureTabContent').style.display = 'block';
            document.querySelector('.nav-tabs').style.display = 'flex';
            
            // Hide results section
            resultsSection.style.display = 'none';
            
            // Reset file input if on upload tab
            if (document.getElementById('upload-tab').classList.contains('active')) {
                if (imageUpload) imageUpload.value = '';
            } else {
                // Reinitialize camera if on camera tab
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
                                class="btn btn-primary"
                                data-doc-id="${data.doc_id}">
                                    <i class="bi bi-journal-text me-2"></i>Open Class Notes
                                </a>
                            `;
                        }
                        
                        // Now save the image to the new document
                        saveImageToDoc(data.doc_id);
                    } else {
                        processingOverlay.style.display = 'none';
                        showToast('Error creating document: ' + (data.error || 'Unknown error'), 'error');
                    }
                })
                .catch(error => {
                    console.error('Error creating document:', error);
                    processingOverlay.style.display = 'none';
                    showToast('Error creating document. Please try again.', 'error');
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
                // Show success message
                showToast('Slide saved successfully!', 'success');
                
                // Reset to camera view after a short delay
                setTimeout(resetToCameraView, 1000);
            } else {
                showToast('Error saving to document: ' + (data.error || 'Unknown error'), 'error');
            }
        })
        .catch(error => {
            console.error('Error saving to document:', error);
            processingOverlay.style.display = 'none';
            showToast('Error saving to document. Please try again.', 'error');
        });
    }

    // Reset to camera view
    function resetToCameraView() {
        // Show tabs again
        const captureTabContent = document.getElementById('captureTabContent');
        const navTabs = document.querySelector('.nav-tabs');
        
        if (captureTabContent) captureTabContent.style.display = 'block';
        if (navTabs) navTabs.style.display = 'flex';
        
        // Hide results section
        if (resultsSection) resultsSection.style.display = 'none';
        
        // Activate camera tab
        const cameraTab = document.getElementById('camera-tab');
        if (cameraTab) {
            const bsTab = new bootstrap.Tab(cameraTab);
            bsTab.show();
        }
        
        // Reset file input
        if (imageUpload) imageUpload.value = '';
        
        // Reinitialize camera
        initCamera();
    }

    // Event creation form handling
    if (createEventForm) {
        createEventForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // Show processing overlay
            processingOverlay.style.display = 'flex';
            processingMessage.textContent = 'Creating event and document...';
            
            const eventName = document.getElementById('eventName').value;
            let eventStartTime = document.getElementById('eventStartTime').value;
            let eventEndTime = document.getElementById('eventEndTime').value;

            // Ensure the date format is correct for Google Calendar API (RFC 3339)
            if (eventStartTime && !eventStartTime.endsWith('Z')) {
                const startDate = new Date(eventStartTime);
                eventStartTime = startDate.toISOString();
            }

            if (eventEndTime && !eventEndTime.endsWith('Z')) {
                const endDate = new Date(eventEndTime);
                eventEndTime = endDate.toISOString();
            }

            console.log('Formatted start time:', eventStartTime);
            console.log('Formatted end time:', eventEndTime);
                        
            // Send to server to create event and doc
            fetch('/create-event-and-doc', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    name: eventName,
                    start_time: eventStartTime,
                    end_time: eventEndTime
                })
            })
            .then(response => response.json())
            .then(data => {
                processingOverlay.style.display = 'none';
                
                if (data.success) {
                    // Close modal
                    const eventModal = bootstrap.Modal.getInstance(document.getElementById('createEventModal'));
                    eventModal.hide();
                    
                    // Format dates for display
                    const startDate = new Date(data.event.start.dateTime);
                    const endDate = new Date(data.event.end.dateTime);
                    const formattedStart = startDate.toLocaleString();
                    const formattedEnd = endDate.toLocaleString();
                    
                    // If there's a current class card, update it
                    const currentClassCard = document.querySelector('.current-class-card');
                    if (currentClassCard) {
                        // Check for the inner structure
                        const currentClassDetails = document.getElementById('currentClassDetails');
                        
                        if (currentClassDetails) {
                            // Update existing details
                            currentClassDetails.innerHTML = `
                                <h4 class="mb-2">${data.event.summary}</h4>
                                <p class="text-muted mb-3">
                                    ${formattedStart} to ${formattedEnd}
                                </p>
                                <div id="docInfo">
                                    <a href="${data.doc_url}" 
                                    target="_blank" 
                                    class="btn btn-primary"
                                    data-doc-id="${data.doc_id}">
                                        <i class="bi bi-journal-text me-2"></i>Open Class Notes
                                    </a>
                                </div>
                            `;
                        } else {
                            // Create new details structure if it doesn't exist
                            currentClassCard.innerHTML = `
                                <div class="card-body p-4">
                                    <div class="d-flex align-items-start mb-2">
                                        <div class="feature-icon">
                                            <i class="bi bi-mortarboard"></i>
                                        </div>
                                        <div>
                                            <h3 class="mb-1">Current Class</h3>
                                            <div id="currentClassDetails">
                                                <h4 class="mb-2">${data.event.summary}</h4>
                                                <p class="text-muted mb-3">
                                                    ${formattedStart} to ${formattedEnd}
                                                </p>
                                                <div id="docInfo">
                                                    <a href="${data.doc_url}" 
                                                    target="_blank" 
                                                    class="btn btn-primary"
                                                    data-doc-id="${data.doc_id}">
                                                        <i class="bi bi-journal-text me-2"></i>Open Class Notes
                                                    </a>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            `;
                        }
                    }
                    
                    // Remove the "Create Event & Doc" button if it exists
                    const createDocBtn = document.getElementById('createDocBtn');
                    if (createDocBtn) {
                        createDocBtn.parentNode.removeChild(createDocBtn);
                    }
                    
                    // Update document ID
                    currentDocId = data.doc_id;
                    
                    // Show success toast
                    showToast('Event and document created successfully!', 'success');
                } else {
                    showToast('Error: ' + (data.error || 'Unknown error'), 'error');
                }
            })
            .catch(error => {
                console.error('Error creating event:', error);
                processingOverlay.style.display = 'none';
                showToast('Error creating event. Please try again.', 'error');
            });
        });
    }

    // Fix for Open Camera and SlideSync navigation
    const openCameraButtons = document.querySelectorAll('.open-camera-btn, a[href="/slidesync"]');
    
    openCameraButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            // Don't prevent default for nav links - we still want to navigate
            if (!this.hasAttribute('href')) {
                e.preventDefault();
            }
            
            // Initialize camera on next render cycle (after navigation completes)
            setTimeout(function() {
                const cameraTab = document.getElementById('camera-tab');
                if (cameraTab) {
                    // Activate camera tab if it exists
                    const bsTab = new bootstrap.Tab(cameraTab);
                    bsTab.show();
                    
                    // Initialize camera
                    initCamera();
                }
            }, 100);
        });
    });
});