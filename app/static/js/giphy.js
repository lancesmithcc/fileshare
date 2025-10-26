(() => {
  const pickerRegistry = [];
  const registryMap = new Map();

  document.querySelectorAll('[data-gif-picker-modal]').forEach((modal) => {
    const overlay = modal.querySelector('[data-gif-picker-overlay]');
    const close = modal.querySelector('[data-gif-picker-close]');
    const searchInput = modal.querySelector('[data-gif-search-input]');
    const results = modal.querySelector('[data-gif-results]');
    if (!overlay || !close || !searchInput || !results) {
      return;
    }
    const registry = { modal, overlay, close, searchInput, results };
    pickerRegistry.push(registry);
    registryMap.set(modal, registry);
  });

  if (!pickerRegistry.length) {
    return;
  }

  let searchTimeout;
  let currentTextarea = null;
  let activePicker = null;

  function hidePicker(registry) {
    if (!registry) {
      return;
    }
    registry.modal.style.display = 'none';
    if (activePicker === registry) {
      activePicker = null;
      currentTextarea = null;
    }
  }

  function positionPicker(trigger, registry) {
    const chatWindow = trigger.closest('.chat-window');
    const tray = trigger.closest('[data-messenger-tray]');

    if (chatWindow && chatWindow.contains(registry.modal)) {
      registry.modal.classList.add('in-chat');
      registry.modal.classList.remove('in-popover');
    } else if (tray) {
      registry.modal.classList.add('in-popover');
      registry.modal.classList.remove('in-chat');
      if (registry.modal.parentElement !== tray) {
        tray.appendChild(registry.modal);
      }
    } else {
      registry.modal.classList.remove('in-chat');
      registry.modal.classList.remove('in-popover');
      if (registry.modal.parentElement !== document.body) {
        document.body.appendChild(registry.modal);
      }
    }
  }

  function resolvePickerForButton(button) {
    const chatWindow = button.closest('.chat-window');
    if (chatWindow) {
      const modal = chatWindow.querySelector('[data-gif-picker-modal]');
      if (modal && registryMap.has(modal)) {
        return registryMap.get(modal);
      }
    }
    return pickerRegistry[0];
  }

  function openPicker(registry, trigger) {
    if (!registry) {
      return;
    }

    if (activePicker && activePicker !== registry) {
      hidePicker(activePicker);
    }

    activePicker = registry;
    positionPicker(trigger, registry);
    registry.searchInput.value = '';
    registry.results.innerHTML = '<p>Type to search GIPHY…</p>';
    registry.modal.style.display = 'block';
    registry.searchInput.focus();
  }

  pickerRegistry.forEach((registry) => {
    registry.overlay.addEventListener('click', () => hidePicker(registry));
    registry.close.addEventListener('click', () => hidePicker(registry));
    registry.searchInput.addEventListener('input', () => {
      if (activePicker !== registry) {
        return;
      }
      clearTimeout(searchTimeout);
      const query = registry.searchInput.value.trim();
      if (!query) {
        registry.results.innerHTML = '<p>Type to search GIPHY…</p>';
        return;
      }
      searchTimeout = setTimeout(() => {
        searchGifs(query);
      }, 500);
    });
  });

  // Use event delegation for dynamically created buttons
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-gif-picker-btn]');
    if (btn) {
      e.preventDefault();
      // Find the nearest textarea
      const form = btn.closest('form');
      currentTextarea = form ? form.querySelector('textarea') : null;

      const registry = resolvePickerForButton(btn);
      openPicker(registry, btn);
    }
  });

  async function searchGifs(query) {
    if (!activePicker) {
      return;
    }

    const resultsContainer = activePicker.results;
    resultsContainer.innerHTML = '<p>Loading...</p>';
    try {
      const response = await fetch(`/api/v1/giphy/search?q=${encodeURIComponent(query)}`);
      if (!response.ok) {
        throw new Error('Giphy search failed');
      }
      const data = await response.json();
      renderGifs(data.gifs);
    } catch (error) {
      if (activePicker) {
        activePicker.results.innerHTML = '<p>Error loading GIFs. Please try again.</p>';
      }
      console.error(error);
    }
  }

  function renderGifs(gifs) {
    if (!activePicker) {
      return;
    }

    const container = activePicker.results;
    container.innerHTML = '';
    if (!gifs || gifs.length === 0) {
      container.innerHTML = '<p>No GIFs found.</p>';
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
          hidePicker(activePicker);
        }
      });
      container.appendChild(img);
    });
  }
})();
