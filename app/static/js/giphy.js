(() => {
  const gifPickerBtn = document.querySelector('[data-gif-picker-btn]');
  const gifPickerModal = document.querySelector('[data-gif-picker-modal]');
  const gifPickerOverlay = document.querySelector('[data-gif-picker-overlay]');
  const gifPickerClose = document.querySelector('[data-gif-picker-close]');
  const gifSearchInput = document.querySelector('[data-gif-search-input]');
  const gifResultsContainer = document.querySelector('[data-gif-results]');

  if (!gifPickerBtn || !gifPickerModal || !gifPickerOverlay || !gifPickerClose || !gifSearchInput || !gifResultsContainer) {
    return;
  }

  let searchTimeout;

  gifPickerBtn.addEventListener('click', () => {
    gifPickerModal.style.display = 'block';
    gifSearchInput.focus();
  });

  gifPickerOverlay.addEventListener('click', () => {
    gifPickerModal.style.display = 'none';
  });

  gifPickerClose.addEventListener('click', () => {
    gifPickerModal.style.display = 'none';
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
        const composeTextarea = document.querySelector('.chat-compose textarea');
        if (composeTextarea) {
          composeTextarea.value += `[GIF: ${gif.url}]`;
          gifPickerModal.style.display = 'none';
        }
      });
      gifResultsContainer.appendChild(img);
    });
  }
})();