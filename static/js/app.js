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
        customPrompt: null
    };

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
                state.uploadedFile = file;
                state.imageUrl = null;
                
                const reader = new FileReader();
                reader.onload = (e) => {
                    previewImg.src = e.target.result;
                    imagePreview.style.display = 'block';
                    checkReadyToGenerate();
                };
                reader.readAsDataURL(file);
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
            try {
                const formData = new FormData();
                formData.append('payment_type', 'stripe');
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
                
                // Initialize Stripe
                const stripe = Stripe(data.publishable_key);
                
                // Redirect to Stripe Checkout or use Elements
                // For simplicity, we'll use Payment Element
                const { error } = await stripe.confirmPayment({
                    clientSecret: data.client_secret,
                    confirmParams: {
                        return_url: window.location.href
                    }
                });
                
                if (error) {
                    alert(error.message);
                }
            } catch (error) {
                alert('Payment error: ' + error.message);
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
                    loading.innerHTML = '<p class="alert alert-error">Generation failed. Please try again.</p>';
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

});
