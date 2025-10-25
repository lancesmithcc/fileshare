(() => {
  const emojiPickerBtn = document.querySelector('[data-emoji-picker-btn]');
  const emojiPickerModal = document.querySelector('[data-emoji-picker-modal]');
  const emojiPickerOverlay = document.querySelector('[data-emoji-picker-overlay]');
  const emojiPickerClose = document.querySelector('[data-emoji-picker-close]');
  const emojiGrid = document.querySelector('[data-emoji-grid]');

  if (!emojiPickerBtn || !emojiPickerModal || !emojiPickerOverlay || !emojiPickerClose || !emojiGrid) {
    return;
  }

  const emojis = [
    '😊', '😂', '😍', '🤔', '😎', '😭', '😡', '👍', '👎', '❤️', '🔥', '🎉', '💯',
    '👋', '🙏', '🙌', '👀', '✨', '🚀', '💡', '✅', '❌', '💰', '📈', '📉',
  ];

  emojiPickerBtn.addEventListener('click', () => {
    emojiPickerModal.style.display = 'block';
    renderEmojis();
  });

  emojiPickerOverlay.addEventListener('click', () => {
    emojiPickerModal.style.display = 'none';
  });

  emojiPickerClose.addEventListener('click', () => {
    emojiPickerModal.style.display = 'none';
  });

  function renderEmojis() {
    emojiGrid.innerHTML = '';
    emojis.forEach(emoji => {
      const emojiSpan = document.createElement('span');
      emojiSpan.textContent = emoji;
      emojiSpan.classList.add('emoji');
      emojiSpan.addEventListener('click', () => {
        const composeTextarea = document.querySelector('.chat-compose textarea');
        if (composeTextarea) {
          composeTextarea.value += emoji;
          emojiPickerModal.style.display = 'none';
        }
      });
      emojiGrid.appendChild(emojiSpan);
    });
  }
})();