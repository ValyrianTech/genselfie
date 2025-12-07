// GenSelfie Frontend Application

document.addEventListener('DOMContentLoaded', function() {
    // State
    let state = {
        platform: 'twitter',
        handle: '',
        imageUrl: null,
        uploadedFile: null,
        paymentMethod: null,
        paymentId: null,
        promoCode: null,
        generationId: null
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
    const resultImg = document.getElementById('result-img');
    const downloadBtn = document.getElementById('download-btn');
    const newSelfieBtn = document.getElementById('new-selfie');

    // Platform help text
    const platformHelp = {
        twitter: 'Enter your Twitter/X username without @',
        bluesky: 'Enter your Bluesky handle (e.g., user.bsky.social)',
        github: 'Enter your GitHub username',
        mastodon: 'Enter your full Mastodon handle (user@instance.social)'
    };

    const platformPlaceholders = {
        twitter: 'username',
        bluesky: 'user.bsky.social',
        github: 'username',
        mastodon: 'user@instance.social'
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
            try {
                const formData = new FormData();
                formData.append('payment_type', 'stripe');
                
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
            try {
                const formData = new FormData();
                formData.append('payment_type', 'lightning');
                
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
                
                invoiceDiv.style.display = 'block';
                requestInput.value = data.payment_request;
                
                // Generate QR code (using a simple library or API)
                // For now, just show the text
                
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

    // New selfie button
    if (newSelfieBtn) {
        newSelfieBtn.addEventListener('click', () => {
            // Reset state
            state = {
                platform: 'twitter',
                handle: '',
                imageUrl: null,
                uploadedFile: null,
                paymentMethod: null,
                paymentId: null,
                promoCode: null,
                generationId: null
            };
            
            // Reset UI
            imagePreview.style.display = 'none';
            stepGenerate.style.display = 'none';
            stepResult.style.display = 'none';
            loading.style.display = 'block';
            result.style.display = 'none';
            
            if (promoCodeInput) promoCodeInput.value = '';
            if (codeStatus) codeStatus.innerHTML = '';
            if (handleInput) handleInput.value = '';
            if (photoUpload) photoUpload.value = '';
            if (generateBtn) {
                generateBtn.disabled = false;
                generateBtn.textContent = 'Generate Selfie';
            }
        });
    }
});
