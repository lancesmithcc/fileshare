(() => {
  const gifPickerModal = document.querySelector('[data-gif-picker-modal]');
  const gifPickerOverlay = document.querySelector('[data-gif-picker-overlay]');
  const gifPickerClose = document.querySelector('[data-gif-picker-close]');
  const gifSearchInput = document.querySelector('[data-gif-search-input]');
  const gifResultsContainer = document.querySelector('[data-gif-results]');

  if (!gifPickerModal || !gifPickerOverlay || !gifPickerClose || !gifSearchInput || !gifResultsContainer) {
    return;
  }

  let searchTimeout;
  let currentTextarea = null;

  // Use event delegation for dynamically created buttons
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-gif-picker-btn]');
    if (btn) {
      e.preventDefault();
      // Find the nearest textarea
      const form = btn.closest('form');
      currentTextarea = form ? form.querySelector('textarea') : null;

      // Check if button is inside messenger popover
      const messengerTray = btn.closest('[data-messenger-tray]');

      if (messengerTray) {
        // Position inside the popover
        gifPickerModal.classList.add('in-popover');
        // Append to messenger tray temporarily
        messengerTray.appendChild(gifPickerModal);
      } else {
        // Position on page
        gifPickerModal.classList.remove('in-popover');
        // Make sure it's back in the body
        if (gifPickerModal.parentElement !== document.body) {
          document.body.appendChild(gifPickerModal);
        }
      }

      gifPickerModal.style.display = 'block';
      gifSearchInput.focus();
    }
  });

  gifPickerOverlay.addEventListener('click', () => {
    gifPickerModal.style.display = 'none';
    currentTextarea = null;
  });

  gifPickerClose.addEventListener('click', () => {
    gifPickerModal.style.display = 'none';
    currentTextarea = null;
  });

  gifSearchInput.addEventListener('input', () => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      const query = gifSearchInput.value.trim();
      if (query) {
        searchGifs(query);
      }
    }, 500);
  });

  async function searchGifs(query) {
    gifResultsContainer.innerHTML = '<p>Loading...</p>';
    try {
      const response = await fetch(`/api/v1/giphy/search?q=${encodeURIComponent(query)}`);
      if (!response.ok) {
        throw new Error('Giphy search failed');
      }
      const data = await response.json();
      renderGifs(data.gifs);
    } catch (error) {
      gifResultsContainer.innerHTML = '<p>Error loading GIFs. Please try again.</p>';
      console.error(error);
    }
  }

  function renderGifs(gifs) {
    gifResultsContainer.innerHTML = '';
    if (!gifs || gifs.length === 0) {
      gifResultsContainer.innerHTML = '<p>No GIFs found.</p>';
      return;
    }

    gifs.forEach(gif => {
      const img = document.createElement('img');
      img.src = gif.preview_url;
      img.alt = gif.title;
      img.classList.add('gif-preview');
      img.addEventListener('click', () => {
        if (currentTextarea) {
          currentTextarea.value += `[GIF: ${gif.url}]`;
          currentTextarea.focus();
          gifPickerModal.style.display = 'none';
        }
      });
      gifResultsContainer.appendChild(img);
    });
  }
})();