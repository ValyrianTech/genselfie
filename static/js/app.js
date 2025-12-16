// GenSelfie Frontend Application

// Check server status
async function checkServerStatus() {
    const indicator = document.getElementById('status-indicator');
    const statusText = document.getElementById('status-text');
    const queueInfo = document.getElementById('queue-info');
    const generateSection = document.getElementById('generate-section');
    const offlineMessage = document.getElementById('offline-message');
    
    if (!indicator || !statusText) return;
    
    try {
        const response = await fetch('/api/server-status');
        const data = await response.json();
        
        if (data.online) {
            indicator.className = 'status-indicator online';
            statusText.textContent = 'Server Online';
            if (data.queue_total > 0) {
                queueInfo.textContent = `Queue: ${data.queue_total} job${data.queue_total > 1 ? 's' : ''}`;
            } else {
                queueInfo.textContent = 'Queue: Empty';
            }
            // Show form, hide offline message
            if (generateSection) generateSection.style.display = 'block';
            if (offlineMessage) offlineMessage.style.display = 'none';
        } else {
            indicator.className = 'status-indicator offline';
            statusText.textContent = 'Server Offline';
            queueInfo.textContent = '';
            // Hide form, show offline message
            if (generateSection) generateSection.style.display = 'none';
            if (offlineMessage) offlineMessage.style.display = 'block';
        }
    } catch (error) {
        indicator.className = 'status-indicator offline';
        statusText.textContent = 'Server Unavailable';
        queueInfo.textContent = '';
        // Hide form, show offline message
        if (generateSection) generateSection.style.display = 'none';
        if (offlineMessage) offlineMessage.style.display = 'block';
    }
}

document.addEventListener('DOMContentLoaded', function() {
    // Check status on load and periodically
    checkServerStatus();
    setInterval(checkServerStatus, 10000); // Every 10 seconds

    // State
    let state = {
        platform: 'twitter',
        handle: '',
        imageUrl: null,
        uploadedFile: null,
        paymentMethod: null,
        paymentId: null,
        promoCode: null,
        generationId: null,
        presetId: null,
        customPrompt: null,
        pendingId: null  // For Stripe: tracks stored image/prompt across redirect
    };
    
    // Check for Stripe return
    const urlParams = new URLSearchParams(window.location.search);
    const paymentStatus = urlParams.get('payment');
    const sessionId = urlParams.get('session_id');
    const presetIdFromUrl = urlParams.get('preset_id');
    const pendingIdFromUrl = urlParams.get('pending_id');
    
    if (paymentStatus === 'success' && sessionId) {
        // User returned from successful Stripe payment
        state.paymentMethod = 'stripe';
        state.paymentId = sessionId;
        if (presetIdFromUrl) {
            state.presetId = presetIdFromUrl;
        }
        if (pendingIdFromUrl) {
            state.pendingId = pendingIdFromUrl;
        }
        
        // Show success message
        const codeStatus = document.getElementById('code-status');
        if (codeStatus) {
            codeStatus.innerHTML = '<span class="alert alert-success">Payment successful! Restoring your session...</span>';
        }
        
        // Clean URL without reloading
        window.history.replaceState({}, document.title, window.location.pathname);
        
        // Auto-select the preset if specified
        if (presetIdFromUrl) {
            const presetRadio = document.querySelector(`input[name="preset_id"][value="${presetIdFromUrl}"]`);
            if (presetRadio) {
                presetRadio.checked = true;
                const presetOption = presetRadio.closest('.preset-option');
                if (presetOption) {
                    document.querySelectorAll('.preset-option').forEach(o => o.classList.remove('selected'));
                    presetOption.classList.add('selected');
                }
            }
        }
        
        // Restore session data (image, prompt) from server if pending_id exists
        if (pendingIdFromUrl) {
            fetch(`/api/pending-session/${pendingIdFromUrl}`)
                .then(res => res.json())
                .then(data => {
                    if (data.found) {
                        // Restore custom prompt if available
                        if (data.custom_prompt) {
                            state.customPrompt = data.custom_prompt;
                            const promptInput = document.getElementById('custom-prompt');
                            if (promptInput) {
                                promptInput.value = data.custom_prompt;
                            }
                        }
                        
                        // Restore image preview if available
                        if (data.image_url) {
                            state.imageUrl = data.image_url;
                            const imagePreview = document.getElementById('image-preview');
                            const previewImg = document.getElementById('preview-img');
                            if (imagePreview && previewImg) {
                                previewImg.src = data.image_url;
                                imagePreview.style.display = 'block';
                            }
                            
                            // Update status message
                            if (codeStatus) {
                                codeStatus.innerHTML = '<span class="alert alert-success">Payment successful! Click Generate to create your selfie.</span>';
                            }
                        }
                        
                        // Restore platform/handle if it was a social media fetch
                        if (data.platform && data.handle) {
                            state.platform = data.platform;
                            state.handle = data.handle;
                        }
                    }
                })
                .catch(err => console.error('Failed to restore session:', err));
        }
    } else if (paymentStatus === 'cancelled') {
        // User cancelled payment
        alert('Payment was cancelled. Please try again.');
        window.history.replaceState({}, document.title, window.location.pathname);
    }
    
    // Defer checkReadyToGenerate call until after elements are set up
    const stripePaymentReady = paymentStatus === 'success' && sessionId;

    // Elements
    const tabs = document.querySelectorAll('.tab');
    const tabContents = document.querySelectorAll('.tab-content');
    const platformSelect = document.getElementById('platform');
    const handleInput = document.getElementById('handle');
    const handleHelp = document.getElementById('handle-help');
    const fetchProfileBtn = document.getElementById('fetch-profile');
    const photoUpload = document.getElementById('photo-upload');
    const imagePreview = document.getElementById('image-preview');
    const previewImg = document.getElementById('preview-img');
    const promoCodeInput = document.getElementById('promo-code');
    const validateCodeBtn = document.getElementById('validate-code');
    const codeStatus = document.getElementById('code-status');
    const payStripeBtn = document.getElementById('pay-stripe');
    const payLightningBtn = document.getElementById('pay-lightning');
    const stepGenerate = document.getElementById('step-generate');
    const generateBtn = document.getElementById('generate-btn');
    const stepResult = document.getElementById('step-result');
    const loading = document.getElementById('loading');
    const result = document.getElementById('result');
    const examplesGallery = document.getElementById('examples-gallery');
    const lightbox = document.getElementById('lightbox');
    const lightboxImg = document.getElementById('lightbox-img');
    const lightboxClose = document.querySelector('.lightbox-close');
    const resultImg = document.getElementById('result-img');
    const downloadBtn = document.getElementById('download-btn');
    const shareBtn = document.getElementById('share-btn');
    const shareOptions = document.getElementById('share-options');
    const shareTwitter = document.getElementById('share-twitter');
    const shareFacebook = document.getElementById('share-facebook');
    const shareLinkedin = document.getElementById('share-linkedin');
    const shareCopy = document.getElementById('share-copy');

    // Platform help text
    const platformHelp = {
        twitter: 'Enter your Twitter/X username without @',
        bluesky: 'Enter your Bluesky handle (e.g., user.bsky.social)',
        github: 'Enter your GitHub username',
        mastodon: 'Enter your full Mastodon handle (user@instance.social)',
        nostr: 'Enter your npub, hex pubkey, or NIP-05 identifier'
    };

    const platformPlaceholders = {
        twitter: 'username',
        bluesky: 'user.bsky.social',
        github: 'username',
        mastodon: 'user@instance.social',
        nostr: 'npub1... or user@domain.com'
    };

    // Tab switching
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const tabId = tab.dataset.tab;
            
            tabs.forEach(t => t.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            
            tab.classList.add('active');
            document.getElementById(`tab-${tabId}`).classList.add('active');
        });
    });

    // Platform change
    if (platformSelect) {
        platformSelect.addEventListener('change', () => {
            const platform = platformSelect.value;
            state.platform = platform;
            handleHelp.textContent = platformHelp[platform] || '';
            handleInput.placeholder = platformPlaceholders[platform] || 'username';
        });
    }

    // Fetch profile
    if (fetchProfileBtn) {
        fetchProfileBtn.addEventListener('click', async () => {
            const platform = platformSelect.value;
            const handle = handleInput.value.trim();
            
            if (!handle) {
                alert('Please enter a handle');
                return;
            }
            
            fetchProfileBtn.disabled = true;
            fetchProfileBtn.textContent = 'Fetching...';
            
            try {
                const formData = new FormData();
                formData.append('platform', platform);
                formData.append('handle', handle);
                
                const response = await fetch('/api/fetch-profile', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (data.success) {
                    state.imageUrl = data.image_url;
                    state.platform = platform;
                    state.handle = handle;
                    state.uploadedFile = null;
                    
                    previewImg.src = data.image_url;
                    imagePreview.style.display = 'block';
                    checkReadyToGenerate();
                } else {
                    alert(data.error || 'Could not fetch profile image');
                }
            } catch (error) {
                alert('Error fetching profile: ' + error.message);
            } finally {
                fetchProfileBtn.disabled = false;
                fetchProfileBtn.textContent = 'Fetch Profile Photo';
            }
        });
    }

    // Photo upload
    if (photoUpload) {
        photoUpload.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) {
                handleFileUpload(file);
            }
        });
    }
    
    // Handle file upload (shared between input and drag-drop)
    function handleFileUpload(file) {
        state.uploadedFile = file;
        state.imageUrl = null;
        state.platform = null;
        state.handle = null;
        
        const reader = new FileReader();
        reader.onload = (e) => {
            previewImg.src = e.target.result;
            imagePreview.style.display = 'block';
            checkReadyToGenerate();
        };
        reader.readAsDataURL(file);
    }
    
    // Drag and drop for fan upload
    const fanDropZone = document.getElementById('fan-drop-zone');
    if (fanDropZone) {
        fanDropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            fanDropZone.classList.add('drag-over');
        });
        
        fanDropZone.addEventListener('dragleave', (e) => {
            e.preventDefault();
            fanDropZone.classList.remove('drag-over');
        });
        
        fanDropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            fanDropZone.classList.remove('drag-over');
            if (e.dataTransfer.files.length > 0) {
                const file = e.dataTransfer.files[0];
                if (file.type.startsWith('image/')) {
                    handleFileUpload(file);
                }
            }
        });
    }

    // Preset selection
    const presetOptions = document.querySelectorAll('.preset-option');
    const priceDisplay = document.getElementById('price-display');
    const stepPrompt = document.getElementById('step-prompt');
    const customPromptInput = document.getElementById('custom-prompt');
    
    function updatePresetUI(option) {
        // Update price display
        const priceCents = parseInt(option.dataset.price) || 0;
        if (priceDisplay) {
            priceDisplay.textContent = (priceCents / 100).toFixed(2) + ' ' + (priceDisplay.textContent.split(' ').pop() || 'USD');
        }
        
        // Update prompt editing visibility
        const allowPrompt = option.dataset.allowPrompt === 'true';
        const defaultPrompt = option.dataset.prompt || '';
        
        if (stepPrompt) {
            if (allowPrompt) {
                stepPrompt.style.display = 'block';
                if (customPromptInput) {
                    customPromptInput.value = defaultPrompt;
                    state.customPrompt = defaultPrompt;
                }
            } else {
                stepPrompt.style.display = 'none';
                state.customPrompt = null;
            }
        }
    }
    
    if (presetOptions.length > 0) {
        // Set initial preset from first checked radio
        const checkedPreset = document.querySelector('.preset-option input[type="radio"]:checked');
        if (checkedPreset) {
            state.presetId = checkedPreset.value;
            // Load examples for initial preset
            refreshExamples(state.presetId);
            // Update UI for initial preset
            const initialOption = checkedPreset.closest('.preset-option');
            if (initialOption) {
                updatePresetUI(initialOption);
            }
        }
        
        presetOptions.forEach(option => {
            option.addEventListener('click', () => {
                // Update visual selection
                presetOptions.forEach(o => o.classList.remove('selected'));
                option.classList.add('selected');
                
                // Update state
                const radio = option.querySelector('input[type="radio"]');
                if (radio) {
                    radio.checked = true;
                    state.presetId = radio.value;
                    refreshExamples(state.presetId);
                    updatePresetUI(option);
                }
            });
        });
    }
    
    // Track custom prompt changes
    if (customPromptInput) {
        customPromptInput.addEventListener('input', () => {
            state.customPrompt = customPromptInput.value;
        });
    }

    async function refreshExamples(presetId) {
        try {
            const url = presetId ? `/api/examples?preset_id=${encodeURIComponent(presetId)}` : '/api/examples';
            const res = await fetch(url);
            const data = await res.json();
            const gallery = document.getElementById('examples-gallery');
            const section = document.getElementById('examples-section');
            if (!gallery || !section) return;
            gallery.innerHTML = '';
            if (data.examples && data.examples.length) {
                data.examples.forEach(ex => {
                    const item = document.createElement('div');
                    item.className = 'gallery-item';
                    const img = document.createElement('img');
                    img.src = ex.url;
                    img.alt = 'Example selfie';
                    item.appendChild(img);
                    gallery.appendChild(item);
                });
                section.style.display = 'block';
            } else {
                section.style.display = 'none';
            }
        } catch (e) {
            console.error('Failed to load examples', e);
        }
    }

    // Lightbox
    function openLightbox(src) {
        if (!lightbox || !lightboxImg) return;
        lightboxImg.src = src;
        lightbox.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }

    function closeLightbox() {
        if (!lightbox) return;
        lightbox.style.display = 'none';
        document.body.style.overflow = '';
        if (lightboxImg) lightboxImg.src = '';
    }

    if (examplesGallery) {
        examplesGallery.addEventListener('click', (e) => {
            const target = e.target;
            if (target && target.tagName === 'IMG') {
                openLightbox(target.src);
            }
        });
    }
    if (lightboxClose) {
        lightboxClose.addEventListener('click', closeLightbox);
    }
    if (lightbox) {
        lightbox.addEventListener('click', (e) => {
            if (e.target === lightbox) {
                closeLightbox();
            }
        });
    }
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeLightbox();
    });

    // Validate promo code
    if (validateCodeBtn) {
        validateCodeBtn.addEventListener('click', async () => {
            const code = promoCodeInput.value.trim();
            
            if (!code) {
                codeStatus.innerHTML = '<span class="alert alert-error">Please enter a code</span>';
                return;
            }
            
            try {
                const formData = new FormData();
                formData.append('code', code);
                
                const response = await fetch('/api/validate-code', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (data.valid) {
                    state.paymentMethod = 'code';
                    state.promoCode = code;
                    codeStatus.innerHTML = '<span class="alert alert-success">Code valid! Ready to generate.</span>';
                    checkReadyToGenerate();
                } else {
                    state.paymentMethod = null;
                    state.promoCode = null;
                    codeStatus.innerHTML = `<span class="alert alert-error">${data.error}</span>`;
                }
            } catch (error) {
                codeStatus.innerHTML = `<span class="alert alert-error">Error: ${error.message}</span>`;
            }
        });
    }

    // Stripe payment
    if (payStripeBtn) {
        payStripeBtn.addEventListener('click', async () => {
            if (!state.presetId) {
                alert('Please select a style first');
                return;
            }
            
            payStripeBtn.disabled = true;
            payStripeBtn.textContent = 'Preparing...';
            
            try {
                const formData = new FormData();
                formData.append('payment_type', 'stripe');
                formData.append('preset_id', state.presetId);
                
                // Include image and prompt so they persist across Stripe redirect
                if (state.uploadedFile) {
                    formData.append('uploaded_image', state.uploadedFile);
                }
                if (state.platform) {
                    formData.append('platform', state.platform);
                }
                if (state.handle) {
                    formData.append('handle', state.handle);
                }
                if (state.customPrompt) {
                    formData.append('custom_prompt', state.customPrompt);
                }
                
                payStripeBtn.textContent = 'Redirecting...';
                
                const response = await fetch('/api/create-payment', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (data.error) {
                    alert(data.error);
                    payStripeBtn.disabled = false;
                    payStripeBtn.textContent = 'Pay Now';
                    return;
                }
                
                // Redirect to Stripe Checkout
                if (data.checkout_url) {
                    window.location.href = data.checkout_url;
                } else {
                    alert('Failed to create checkout session');
                    payStripeBtn.disabled = false;
                    payStripeBtn.textContent = 'Pay Now';
                }
            } catch (error) {
                alert('Payment error: ' + error.message);
                payStripeBtn.disabled = false;
                payStripeBtn.textContent = 'Pay Now';
            }
        });
    }

    // Lightning payment
    if (payLightningBtn) {
        payLightningBtn.addEventListener('click', async () => {
            if (!state.presetId) {
                alert('Please select a style first');
                return;
            }
            try {
                const formData = new FormData();
                formData.append('payment_type', 'lightning');
                formData.append('preset_id', state.presetId);
                
                const response = await fetch('/api/create-payment', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (data.error) {
                    alert(data.error);
                    return;
                }
                
                // Show invoice
                const invoiceDiv = document.getElementById('lightning-invoice');
                const requestInput = document.getElementById('lightning-request');
                const qrImg = document.getElementById('lightning-qr');
                
                invoiceDiv.style.display = 'flex';
                requestInput.value = data.payment_request;
                
                // Display server-generated QR code
                if (qrImg && data.qr_code) {
                    qrImg.src = data.qr_code;
                }
                
                state.paymentId = data.checking_id;
                
                // Start polling for payment
                pollLightningPayment(data.checking_id);
            } catch (error) {
                alert('Payment error: ' + error.message);
            }
        });
    }

    // Copy lightning invoice
    const copyInvoiceBtn = document.getElementById('copy-invoice');
    if (copyInvoiceBtn) {
        copyInvoiceBtn.addEventListener('click', () => {
            const requestInput = document.getElementById('lightning-request');
            requestInput.select();
            document.execCommand('copy');
            copyInvoiceBtn.textContent = 'Copied!';
            setTimeout(() => {
                copyInvoiceBtn.textContent = 'Copy';
            }, 2000);
        });
    }

    // Poll for lightning payment
    async function pollLightningPayment(checkingId) {
        const poll = async () => {
            try {
                const response = await fetch(`/api/payment-status/${checkingId}?payment_type=lightning`);
                const data = await response.json();
                
                if (data.paid) {
                    state.paymentMethod = 'lightning';
                    state.paymentId = checkingId;
                    document.getElementById('lightning-invoice').innerHTML = 
                        '<span class="alert alert-success">Payment received!</span>';
                    checkReadyToGenerate();
                } else {
                    // Continue polling
                    setTimeout(poll, 3000);
                }
            } catch (error) {
                console.error('Polling error:', error);
                setTimeout(poll, 5000);
            }
        };
        
        poll();
    }

    // Check if ready to generate
    function checkReadyToGenerate() {
        const hasImage = state.imageUrl || state.uploadedFile;
        const hasPaid = state.paymentMethod !== null;
        
        if (hasImage && hasPaid) {
            stepGenerate.style.display = 'block';
        } else {
            stepGenerate.style.display = 'none';
        }
    }

    // Generate selfie
    if (generateBtn) {
        generateBtn.addEventListener('click', async () => {
            generateBtn.disabled = true;
            generateBtn.textContent = 'Starting...';
            
            try {
                const formData = new FormData();
                formData.append('payment_method', state.paymentMethod);
                
                if (state.paymentId) {
                    formData.append('payment_id', state.paymentId);
                }
                if (state.promoCode) {
                    formData.append('promo_code', state.promoCode);
                }
                if (state.platform) {
                    formData.append('platform', state.platform);
                }
                if (state.handle) {
                    formData.append('handle', state.handle);
                }
                if (state.uploadedFile) {
                    formData.append('uploaded_image', state.uploadedFile);
                }
                if (state.presetId) {
                    formData.append('preset_id', state.presetId);
                }
                if (state.customPrompt) {
                    formData.append('custom_prompt', state.customPrompt);
                }
                if (state.pendingId) {
                    formData.append('pending_id', state.pendingId);
                }
                
                const response = await fetch('/api/generate', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (data.success) {
                    state.generationId = data.generation_id;
                    
                    // Show result section
                    stepGenerate.style.display = 'none';
                    stepResult.style.display = 'block';
                    loading.style.display = 'block';
                    result.style.display = 'none';
                    
                    // Poll for result
                    pollGenerationStatus(data.generation_id);
                } else {
                    throw new Error(data.detail || 'Generation failed');
                }
            } catch (error) {
                alert('Error: ' + error.message);
                generateBtn.disabled = false;
                generateBtn.textContent = 'Generate Selfie';
            }
        });
    }

    // Poll for generation status
    async function pollGenerationStatus(generationId) {
        const poll = async () => {
            try {
                const response = await fetch(`/api/generation-status/${generationId}`);
                const data = await response.json();
                
                if (data.status === 'completed' && data.result_url) {
                    loading.style.display = 'none';
                    result.style.display = 'block';
                    resultImg.src = data.result_url;
                    downloadBtn.href = data.result_url;
                    downloadBtn.download = 'selfie.png';
                } else if (data.status === 'failed') {
                    let errorMessage = '<p class="alert alert-error">Generation failed.</p>';
                    if (data.retry_code) {
                        errorMessage = `
                            <div class="alert alert-error">
                                <p><strong>Generation failed.</strong></p>
                                <p>Use this code to try again for free:</p>
                                <p class="retry-code"><strong>${data.retry_code}</strong></p>
                                <button type="button" class="btn btn-secondary btn-small" onclick="navigator.clipboard.writeText('${data.retry_code}'); this.textContent='Copied!';">Copy Code</button>
                            </div>
                        `;
                    }
                    loading.innerHTML = errorMessage;
                } else {
                    // Continue polling
                    setTimeout(poll, 3000);
                }
            } catch (error) {
                console.error('Polling error:', error);
                setTimeout(poll, 5000);
            }
        };
        
        poll();
    }
    
    // If user returned from Stripe payment, check if ready to generate
    if (stripePaymentReady) {
        checkReadyToGenerate();
    }
    
    // Share functionality
    if (shareBtn) {
        shareBtn.addEventListener('click', () => {
            // Toggle share options visibility
            if (shareOptions.style.display === 'none') {
                shareOptions.style.display = 'flex';
                
                // Get the image URL (full URL for sharing)
                const imageUrl = resultImg.src;
                const pageUrl = window.location.origin + window.location.pathname;
                const shareText = 'Check out my AI-generated selfie!';
                
                // Update share links
                if (shareTwitter) {
                    shareTwitter.href = `https://twitter.com/intent/tweet?text=${encodeURIComponent(shareText)}&url=${encodeURIComponent(pageUrl)}`;
                }
                if (shareFacebook) {
                    shareFacebook.href = `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(pageUrl)}`;
                }
                if (shareLinkedin) {
                    shareLinkedin.href = `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(pageUrl)}`;
                }
            } else {
                shareOptions.style.display = 'none';
            }
        });
    }
    
    // Copy link functionality
    if (shareCopy) {
        shareCopy.addEventListener('click', async () => {
            const imageUrl = resultImg.src;
            try {
                await navigator.clipboard.writeText(imageUrl);
                const originalText = shareCopy.innerHTML;
                shareCopy.innerHTML = '<span class="share-icon">✓</span> Copied!';
                setTimeout(() => {
                    shareCopy.innerHTML = originalText;
                }, 2000);
            } catch (err) {
                // Fallback for older browsers
                const textArea = document.createElement('textarea');
                textArea.value = imageUrl;
                document.body.appendChild(textArea);
                textArea.select();
                document.execCommand('copy');
                document.body.removeChild(textArea);
                
                const originalText = shareCopy.innerHTML;
                shareCopy.innerHTML = '<span class="share-icon">✓</span> Copied!';
                setTimeout(() => {
                    shareCopy.innerHTML = originalText;
                }, 2000);
            }
        });
    }

});
