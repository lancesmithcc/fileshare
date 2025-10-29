(async () => {
  const messengerDock = document.querySelector('[data-messenger-dock]');
  const messengerTray = document.querySelector('[data-messenger-tray]');
  if (!messengerDock || !messengerTray) {
    return;
  }

  messengerTray.dataset.state = 'idle';
  messengerTray.dataset.pendingRecipient = '';

  let windowRail = document.querySelector('.chat-window-rail');
  if (!windowRail) {
    windowRail = document.createElement('div');
    windowRail.className = 'chat-window-rail';
    document.body.append(windowRail);
  }

  const previewMap = new Map();
  const threadLookup = new Map();
  const threadHistory = new Map();
  const windowMap = new Map();

  let onlineUsers = [];
  let onlineCircles = [];
  let selectedCircle = 'all';
  let trayNotice = '';
  let trayNoticeTone = 'info';
  let lastOnlineFetch = 0;
  let onlineRefreshTimer = null;
  const ONLINE_REFRESH_MS = 45000;
  const GROUP_MEMBER_LIMIT = 16;
  let groupBuilderOpen = false;
  let groupBuilderName = '';
  const groupBuilderMembers = new Set();
  let groupBuilderError = '';
  let groupBuilderSubmitting = false;
  let currentUserId = null;
  let showOffline = false;
  let allRecipients = [];
  let offlineFetchState = 'idle';
  const DEFAULT_AVATAR = document.body?.dataset.defaultAvatar || '/static/img/triple.svg.png';

  let state = 'locked';
  let threadIds = [];
  let currentThreadId = null;
  let maxLength = 2000;
  let messageList = null;
  let composeForm = null;

  let wsPath = '/chat/ws';
  let socket = null;
  let reconnectTimer = null;
  const subscribedThreads = new Set();

  function renderMessageBody(text) {
    if (!text) return '';
    const escapeHtml = (str) => {
      const div = document.createElement('div');
      div.textContent = str;
      return div.innerHTML;
    };
    let html = escapeHtml(text);
    html = html.replace(/\[GIF:\s*(https?:\/\/[^\]]+)\]/gi, (match, url) => {
      const cleanUrl = url.trim();
      return `<img src="${cleanUrl}" alt="GIF" class="chat-gif" loading="lazy">`;
    });
    html = html.replace(/\n/g, '<br>');
    return html;
  }

  const context = await loadContext();
  if (!context) {
    return;
  }

  state = context.state;
  currentUserId = typeof context.currentUserId === 'number' ? context.currentUserId : null;
  threadIds = Array.from(new Set(context.threadIds || []));
  currentThreadId = context.currentThreadId;
  maxLength = context.maxLength;
  messageList = context.messageList;
  composeForm = context.composeForm;

  context.threads.forEach((thread) => {
    threadLookup.set(thread.id, {
      label: thread.display_name || 'Conversation',
      preview: thread.preview || '',
      unread: thread.unread_count || 0,
      isGroup: !!thread.is_group,
      ownerId: typeof thread.owner_id === 'number' ? thread.owner_id : null,
    });
  });

  if (!threadIds.length) {
    threadIds = Array.from(threadLookup.keys());
  }

  if (context.domThreads) {
    context.domThreads.forEach((thread) => {
      const info = threadLookup.get(thread.id) || {
        label: thread.display_name || 'Conversation',
        preview: thread.preview || '',
        unread: thread.unread_count || 0,
        isGroup: !!thread.is_group,
        ownerId: typeof thread.owner_id === 'number' ? thread.owner_id : null,
      };
      info.preview = thread.preview ?? info.preview;
      info.unread = typeof thread.unread_count === 'number' ? thread.unread_count : info.unread;
      if (typeof thread.owner_id === 'number') {
        info.ownerId = thread.owner_id;
      }
      threadLookup.set(thread.id, info);
      previewMap.set(thread.id, {
        container: thread.element,
        preview: thread.element.querySelector('[data-thread-preview]'),
        unread: thread.element.querySelector('[data-thread-unread]'),
      });
    });
  }

  renderTray();

  if (composeForm) {
    composeForm.addEventListener('submit', (event) => {
      event.preventDefault();
      submitForm(composeForm);
    });
    attachComposeShortcuts(composeForm);
  }

  windowRail.addEventListener('submit', (event) => {
    // Check if the event target is itself the form with data-popover-form
    const targetIsPopoverForm = event.target.matches && event.target.matches('[data-popover-form]');
    const form = targetIsPopoverForm ? event.target : event.target.closest('[data-popover-form]');

    console.log('[chat] submit event:', {
      target: event.target,
      targetIsPopoverForm,
      form,
      hasAttribute: form && form.hasAttribute('data-popover-form')
    });

    if (!form) {
      return;
    }
    event.preventDefault();
    submitForm(form);
  });

  windowRail.addEventListener('click', (event) => {
    const deleteButton = event.target.closest('[data-message-delete]');
    if (deleteButton) {
      event.preventDefault();
      const threadId = parseInt(deleteButton.dataset.threadId || '', 10);
      const messageId = parseInt(deleteButton.dataset.messageId || '', 10);
      const isGroup = deleteButton.dataset.isGroup === '1';
      if (Number.isNaN(threadId) || Number.isNaN(messageId)) {
        return;
      }

      let deleteScope = 'all';
      if (!isGroup) {
        // For one-on-one chats, ask user if they want to delete for self or both
        const choice = window.confirm('Delete this message?\n\nClick OK to delete for everyone\nClick Cancel to delete for you only');
        deleteScope = choice ? 'all' : 'self';
      } else {
        // For group chats, ask with better wording
        const choice = window.confirm('Delete this message?\n\nClick OK to delete for everyone\nClick Cancel to delete for you only');
        deleteScope = choice ? 'all' : 'self';
      }

      deleteButton.disabled = true;
      deleteMessage(threadId, messageId, deleteScope).finally(() => {
        deleteButton.disabled = false;
      });
      return;
    }
    const closeButton = event.target.closest('.chat-popover-close');
    if (!closeButton) {
      return;
    }
    const container = closeButton.closest('.chat-popover');
    if (!container) {
      return;
    }
    container.classList.remove('is-visible');
    const threadId = parseInt(container.dataset.chatWindow || '0', 10);
    windowMap.delete(threadId);
    setTimeout(() => container.remove(), 250);
  });

  if (messageList) {
    messageList.addEventListener('click', (event) => {
      const deleteButton = event.target.closest('[data-message-delete]');
      if (!deleteButton) {
        return;
      }
      event.preventDefault();
      const threadId = currentThreadId != null ? currentThreadId : parseInt(deleteButton.dataset.threadId || '', 10);
      const messageId = parseInt(deleteButton.dataset.messageId || '', 10);
      const isGroup = deleteButton.dataset.isGroup === '1';
      if (Number.isNaN(threadId) || Number.isNaN(messageId)) {
        return;
      }

      let deleteScope = 'all';
      if (!isGroup) {
        // For one-on-one chats, ask user if they want to delete for self or both
        const choice = window.confirm('Delete this message?\n\nClick OK to delete for everyone\nClick Cancel to delete for you only');
        deleteScope = choice ? 'all' : 'self';
      } else {
        // For group chats, ask with better wording
        const choice = window.confirm('Delete this message?\n\nClick OK to delete for everyone\nClick Cancel to delete for you only');
        deleteScope = choice ? 'all' : 'self';
      }

      deleteButton.disabled = true;
      deleteMessage(threadId, messageId, deleteScope).finally(() => {
        deleteButton.disabled = false;
      });
    });
  }

  messengerDock.addEventListener('click', () => {
    const willOpen = !messengerTray.classList.contains('is-open');
    messengerDock.classList.remove('is-active');
    messengerDock.dataset.activeThread = '';
    if (window.__chatTone && typeof window.__chatTone.stop === 'function') {
      window.__chatTone.stop();
    }
    if (willOpen) {
      groupBuilderOpen = false;
      resetGroupBuilderState();
      messengerTray.classList.add('is-open');
      messengerTray.dataset.state = onlineUsers.length ? 'ready' : 'loading';
      messengerTray.dataset.pendingRecipient = '';
      setTrayNotice('', 'info');
      renderTray();
      fetchOnlineUsers();
      startOnlineRefresh();
    } else {
      groupBuilderOpen = false;
      resetGroupBuilderState();
      messengerTray.classList.remove('is-open');
      messengerTray.dataset.state = 'idle';
      messengerTray.dataset.pendingRecipient = '';
      setTrayNotice('', 'info');
      stopOnlineRefresh();
    }
  });

  document.addEventListener('click', (event) => {
    if (!messengerTray.classList.contains('is-open')) {
      return;
    }
    const path = typeof event.composedPath === 'function' ? event.composedPath() : null;
    if (
      (path && (path.includes(messengerDock) || path.includes(messengerTray))) ||
      event.target.closest('[data-messenger-dock]') ||
      event.target.closest('[data-messenger-tray]')
    ) {
      return;
    }
    messengerTray.classList.remove('is-open');
    messengerTray.dataset.state = 'idle';
    messengerTray.dataset.pendingRecipient = '';
    setTrayNotice('', 'info');
    stopOnlineRefresh();
    groupBuilderOpen = false;
    resetGroupBuilderState();
  });

  document.addEventListener('click', (event) => {
    const maximizeButton = event.target.closest('[data-maximize-chat]');
    if (maximizeButton) {
      event.preventDefault();
      const threadId = maximizeButton.dataset.threadId;
      if (threadId) {
        window.location.href = `/chat?thread=${threadId}`;
      }
      return;
    }

    const blockButton = event.target.closest('[data-block-user]');
    if (blockButton) {
      event.preventDefault();
      const userId = parseInt(blockButton.dataset.userId || '', 10);
      if (Number.isNaN(userId)) {
        return;
      }
      if (!window.confirm('Block this user? You will not be able to message each other.')) {
        return;
      }
      blockUser(userId);
      return;
    }

    const unblockButton = event.target.closest('[data-unblock-user]');
    if (unblockButton) {
      event.preventDefault();
      const userId = parseInt(unblockButton.dataset.userId || '', 10);
      if (Number.isNaN(userId)) {
        return;
      }
      if (!window.confirm('Unblock this user?')) {
        return;
      }
      unblockUser(userId);
      return;
    }

    const kickButton = event.target.closest('[data-kick-member]');
    if (kickButton) {
      event.preventDefault();
      const threadId = parseInt(kickButton.dataset.threadId || '', 10);
      const userId = parseInt(kickButton.dataset.userId || '', 10);
      if (Number.isNaN(threadId) || Number.isNaN(userId)) {
        return;
      }
      if (!window.confirm('Remove this member from the group?')) {
        return;
      }
      kickMember(threadId, userId);
      return;
    }

    const addMembersButton = event.target.closest('[data-add-members]');
    if (addMembersButton) {
      event.preventDefault();
      const threadId = parseInt(addMembersButton.dataset.threadId || '', 10);
      if (Number.isNaN(threadId)) {
        return;
      }
      showAddMembersModal(threadId);
      return;
    }

    const actionButton = event.target.closest('[data-thread-action]');
    if (!actionButton) {
      return;
    }
    const threadId = parseInt(actionButton.dataset.threadId || '', 10);
    if (Number.isNaN(threadId)) {
      return;
    }
    const action = actionButton.dataset.threadAction || 'delete';
    event.preventDefault();
    handleThreadAction(threadId, action);
  });

  wsPath = context.wsPath || '/chat/ws';
  connectSocket();

  // Function to convert GIF markers to actual images (for server-rendered messages)
  function processGifMarkers(element) {
    const gifRegex = /\[GIF:\s*(https?:\/\/[^\]]+)\]/gi;
    const messageBodyElements = element ? element.querySelectorAll('.chat-message-body') : document.querySelectorAll('.chat-message-body');

    messageBodyElements.forEach(body => {
      const text = body.textContent;
      if (text.includes('[GIF:')) {
        const html = text.replace(gifRegex, (_, url) => {
          const cleanUrl = url.trim();
          return `<img src="${cleanUrl}" alt="GIF" class="chat-gif" loading="lazy">`;
        });
        body.innerHTML = html;
      }
    });
  }

  if (messageList) {
    messageList.scrollTop = messageList.scrollHeight;
    messageList.addEventListener('mouseenter', () => {
      if (currentThreadId != null) {
        clearUnread(currentThreadId);
      }
    });

    // Process GIF markers on initial load
    processGifMarkers();
  }

  // Add resize functionality to main chat window
  const mainChatResize = document.querySelector('[data-main-chat-resize]');
  const chatWindow = document.querySelector('.chat-window');
  if (mainChatResize && chatWindow) {
    let isResizing = false;
    let startY = 0;
    let startHeight = 0;

    mainChatResize.addEventListener('mousedown', (e) => {
      isResizing = true;
      startY = e.clientY;
      startHeight = chatWindow.offsetHeight;
      e.preventDefault();
      document.body.style.userSelect = 'none';
      chatWindow.classList.add('is-resizing');
    });

    document.addEventListener('mousemove', (e) => {
      if (!isResizing) return;
      const deltaY = e.clientY - startY;
      const newHeight = Math.max(400, Math.min(900, startHeight + deltaY));
      chatWindow.style.height = `${newHeight}px`;
    });

    document.addEventListener('mouseup', () => {
      if (isResizing) {
        isResizing = false;
        document.body.style.userSelect = '';
        chatWindow.classList.remove('is-resizing');
      }
    });
  }

  async function loadContext() {
    const root = document.querySelector('[data-chat-root]');
    if (root) {
      let ids;
      try {
        ids = JSON.parse(root.dataset.threadIds || '[]');
      } catch (err) {
        ids = [];
      }
      const currentId = parseInt(root.dataset.currentThreadId || '', 10);
      const currentUserRaw = parseInt(root.dataset.currentUserId || '', 10);
      const maxLen = parseInt(root.dataset.maxLength || '0', 10) || 4000;
      const domThreads = Array.from(document.querySelectorAll('[data-thread-id]')).map((element) => {
        const id = parseInt(element.dataset.threadId || '0', 10);
        const nameEl = element.querySelector('.chat-thread-name');
        const label = nameEl ? nameEl.textContent.replace(/^([\u2600-\u27BF]|\p{Emoji_Presentation})+/gu, '').trim() || nameEl.textContent.trim() : 'Conversation';
        const previewEl = element.querySelector('[data-thread-preview]');
        const unreadEl = element.querySelector('[data-thread-unread]');
        const unread = unreadEl && unreadEl.textContent.trim() ? parseInt(unreadEl.textContent.trim(), 10) || 0 : 0;
        const ownerId = parseInt(element.dataset.ownerId || '', 10);
        return {
          id,
          display_name: label,
          preview: previewEl ? previewEl.textContent.trim() : '',
          unread_count: unread,
          is_group: element.dataset.isGroup === '1',
          owner_id: Number.isNaN(ownerId) ? null : ownerId,
          element,
        };
      });
      return {
        state: root.dataset.state || 'locked',
        threadIds: ids,
        currentThreadId: Number.isNaN(currentId) ? null : currentId,
        maxLength: maxLen,
        messageList: document.querySelector('[data-message-list]'),
        composeForm: document.querySelector('[data-compose-form]'),
        threads: domThreads.map(({ element, ...rest }) => rest),
        domThreads,
        wsPath: root.dataset.wsPath || '/chat/ws',
        currentUserId: Number.isNaN(currentUserRaw) ? null : currentUserRaw,
      };
    }

    try {
      const response = await fetch('/chat/api/context', {
        headers: { Accept: 'application/json' },
        credentials: 'same-origin',
      });
      if (!response.ok) {
        return null;
      }
      const data = await response.json();
      return {
        state: data.state || 'locked',
        threadIds: (data.threads || []).map((thread) => thread.id),
        currentThreadId: null,
        maxLength: data.max_length || 4000,
        messageList: null,
        composeForm: null,
        threads: data.threads || [],
        domThreads: [],
        wsPath: '/chat/ws',
        currentUserId: typeof data.current_user_id === 'number' ? data.current_user_id : null,
      };
    } catch (err) {
      console.error('[chat] failed to load context', err);
      return null;
    }
  }

  function renderTray() {
    normalizeSelectedCircle();
    const state = messengerTray.dataset.state || 'idle';
    messengerTray.innerHTML = '';
    if (showOffline && offlineFetchState === 'idle') {
      fetchRecipients();
    }

    const onlineSection = document.createElement('section');
    onlineSection.className = 'messenger-section messenger-section-online';
    messengerTray.append(onlineSection);

    const visibleUsers = onlineUsers.filter((user) => {
      if (selectedCircle === 'all') {
        return true;
      }
      if (selectedCircle === 'unaffiliated') {
        return !user.circle;
      }
      return user.circle && String(user.circle.id) === selectedCircle;
    });

    // Don't remove members from groupBuilderMembers - they may be offline users
    // that were explicitly added via search

    const header = document.createElement('header');
    header.className = 'messenger-section-header';
    const title = document.createElement('span');
    title.textContent = 'Online Now';
    header.append(title);
    const count = document.createElement('span');
    count.className = 'messenger-count';
    count.textContent = String(visibleUsers.length);
    header.append(count);
    onlineSection.append(header);

    const hasFilter = onlineCircles.length > 0 || onlineUsers.some((user) => !user.circle);
    if (hasFilter) {
      const controls = document.createElement('div');
      controls.className = 'messenger-controls';

      const label = document.createElement('label');
      label.className = 'sr-only';
      label.setAttribute('for', 'messenger-circle-filter');
      label.textContent = 'Filter by circle';
      controls.append(label);

      const select = document.createElement('select');
      select.id = 'messenger-circle-filter';
      select.className = 'messenger-filter';

      const allOption = document.createElement('option');
      allOption.value = 'all';
      allOption.textContent = 'all one circle';
      if (selectedCircle === 'all') {
        allOption.selected = true;
      }
      select.append(allOption);

      onlineCircles.forEach((circle) => {
        const option = document.createElement('option');
        const optionValue =
          circle.id === null || circle.id === undefined ? 'all' : String(circle.id);
        option.value = optionValue;
        const suffix =
          typeof circle.online_count === 'number' && circle.online_count > 0
            ? ` (${circle.online_count})`
            : '';
        option.textContent = `${circle.name}${suffix}`;
        if (optionValue === selectedCircle) {
          option.selected = true;
        }
        select.append(option);
      });

      const includesunaffiliated = onlineCircles.some((circle) => circle.id === 'unaffiliated');
      if (!includesunaffiliated && onlineUsers.some((user) => !user.circle)) {
        const option = document.createElement('option');
        option.value = 'unaffiliated';
        option.textContent = 'all one circle';
        if (selectedCircle === 'unaffiliated') {
          option.selected = true;
        }
        select.append(option);
      }

      select.disabled = state === 'loading';
      select.addEventListener('change', (event) => {
        selectedCircle = event.target.value || 'all';
        renderTray();
      });

      controls.append(select);
      onlineSection.append(controls);
    }

    const actions = document.createElement('div');
    actions.className = 'messenger-actions';
    const groupButton = document.createElement('button');
    groupButton.type = 'button';
    groupButton.className = 'messenger-action';
    groupButton.textContent = groupBuilderOpen ? 'Cancel group setup' : 'New group whisper';
    groupButton.disabled = state === 'loading';
    groupButton.addEventListener('click', () => {
      if (groupBuilderOpen) {
        groupBuilderOpen = false;
        resetGroupBuilderState();
      } else {
        resetGroupBuilderState();
        groupBuilderOpen = true;
        // Fetch all recipients to enable adding offline users
        if (!allRecipients.length && offlineFetchState !== 'loading') {
          fetchRecipients();
        }
      }
      renderTray();
    });
    actions.append(groupButton);

    const offlineButton = document.createElement('button');
    offlineButton.type = 'button';
    offlineButton.className = 'messenger-action-secondary';
    offlineButton.textContent = showOffline ? 'Hide offline' : 'Show offline';
    offlineButton.addEventListener('click', () => {
      toggleOfflineVisibility();
    });
    actions.append(offlineButton);
    onlineSection.append(actions);

    if (groupBuilderOpen) {
      onlineSection.append(buildGroupBuilder(visibleUsers));
    }

    const list = document.createElement('div');
    list.className = 'messenger-list messenger-list-online';
    onlineSection.append(list);

    if (state === 'loading') {
      const status = document.createElement('div');
      status.className = 'messenger-status';
      status.textContent = 'Summoning online members…';
      list.append(status);
    } else if (state === 'error') {
      const status = document.createElement('div');
      status.className = 'messenger-status is-error';
      status.textContent = 'Unable to load online members.';
      list.append(status);
      const retry = document.createElement('button');
      retry.type = 'button';
      retry.className = 'messenger-retry';
      retry.textContent = 'Retry';
      retry.addEventListener('click', () => fetchOnlineUsers(true));
      list.append(retry);
    } else if (!visibleUsers.length) {
      const status = document.createElement('div');
      status.className = 'messenger-status';
      status.textContent =
        lastOnlineFetch === 0
          ? 'Open the whispers dock to check who is online.'
          : selectedCircle === 'all'
            ? 'No members are online right now.'
            : 'No members are online in this circle.';
      list.append(status);
    } else {
      visibleUsers.forEach((user) => {
        list.append(buildOnlineUserButton(user));
      });
    }

    if (trayNotice) {
      const note = document.createElement('p');
      note.className = `messenger-notice messenger-notice-${trayNoticeTone}`;
      note.textContent = trayNotice;
      onlineSection.append(note);
    }

    if (showOffline) {
      const offlineSection = document.createElement('section');
      offlineSection.className = 'messenger-section messenger-section-offline';
      messengerTray.append(offlineSection);

      const offlineHeader = document.createElement('header');
      offlineHeader.className = 'messenger-section-header';
      offlineHeader.innerHTML = '<span>Offline Members</span>';
      offlineSection.append(offlineHeader);

      const offlineList = document.createElement('div');
      offlineList.className = 'messenger-list messenger-list-offline';
      offlineSection.append(offlineList);

      if (offlineFetchState === 'loading') {
        const status = document.createElement('div');
        status.className = 'messenger-status';
        status.textContent = 'Gathering the rest of the circle…';
        offlineList.append(status);
      } else if (offlineFetchState === 'error') {
        const status = document.createElement('div');
        status.className = 'messenger-status is-error';
        status.textContent = 'Unable to load offline members.';
        offlineList.append(status);
      } else {
        const offlineEntries = offlineUsersForDisplay();
        if (!offlineEntries.length) {
          const status = document.createElement('div');
          status.className = 'messenger-status';
          status.textContent = 'No offline members are available.';
          offlineList.append(status);
        } else {
          offlineEntries.forEach((user) => {
            offlineList.append(buildOnlineUserButton(user, { offline: true }));
          });
        }
      }
    }

    if (!threadLookup.size) {
      return;
    }

    const historySection = document.createElement('section');
    historySection.className = 'messenger-section messenger-section-threads';
    messengerTray.append(historySection);

    const historyHeader = document.createElement('header');
    historyHeader.className = 'messenger-section-header';
    const historyTitle = document.createElement('span');
    historyTitle.textContent = 'Recent Whispers';
    historyHeader.append(historyTitle);
    historySection.append(historyHeader);

    const entries = Array.from(threadLookup.entries()).sort((a, b) =>
      a[1].label.localeCompare(b[1].label)
    );
    const historyList = document.createElement('div');
    historyList.className = 'messenger-list messenger-list-threads';
    historySection.append(historyList);

    if (!entries.length) {
      const empty = document.createElement('div');
      empty.className = 'messenger-status';
      empty.textContent = 'No conversations yet.';
      historyList.append(empty);
      return;
    }

    entries.forEach(([id, info]) => {
      const threadId = Number(id);
      const item = document.createElement('div');
      item.className = 'messenger-tray-item';
      item.dataset.threadId = String(threadId);
      const ownerId = typeof info.ownerId === 'number' ? info.ownerId : null;
      const isOwner = ownerId != null && currentUserId != null && ownerId === currentUserId;
      const actionType = info.isGroup ? (isOwner ? 'delete' : 'leave') : 'delete';
      const actionLabel = info.isGroup
        ? actionType === 'delete'
          ? 'Delete this group for everyone'
          : 'Leave this group'
        : 'Remove this conversation';

      const openButton = document.createElement('button');
      openButton.type = 'button';
      openButton.className = 'messenger-tray-open';
      openButton.addEventListener('click', () => {
        messengerTray.classList.remove('is-open');
        stopOnlineRefresh();
        openThread(threadId);
      });

      const avatar = document.createElement('span');
      avatar.className = 'messenger-tray-avatar';
      if (info.isGroup) {
        avatar.classList.add('is-group');
        avatar.textContent = '👥';
      } else {
        const initial = (info.label || 'Direct Message').trim().charAt(0).toUpperCase();
        avatar.textContent = initial || '💬';
      }
      openButton.append(avatar);

      const textWrap = document.createElement('span');
      textWrap.className = 'messenger-tray-text';

      const headerRow = document.createElement('span');
      headerRow.className = 'messenger-tray-row';

      const titleWrap = document.createElement('span');
      titleWrap.className = 'messenger-tray-title';

      const nameLabel = document.createElement('span');
      nameLabel.className = 'messenger-tray-main';
      nameLabel.textContent = info.label || 'Conversation';
      titleWrap.append(nameLabel);

      if (info.isGroup) {
        const badge = document.createElement('span');
        badge.className = 'messenger-tray-badge';
        badge.textContent = 'Group';
        titleWrap.append(badge);
      }

      headerRow.append(titleWrap);

      const unread = document.createElement('span');
      unread.className = 'messenger-tray-unread';
      if (info.unread) {
        unread.textContent = String(info.unread);
      } else {
        unread.classList.add('is-hidden');
      }
      headerRow.append(unread);

      textWrap.append(headerRow);

      const preview = document.createElement('span');
      preview.className = 'messenger-tray-preview';
      const previewText = truncateBody(info.preview || '');
      preview.textContent = previewText || (info.isGroup ? 'No recent group messages yet.' : 'No recent messages yet.');
      textWrap.append(preview);

      openButton.append(textWrap);

      item.append(openButton);

      const deleteButton = document.createElement('button');
      deleteButton.type = 'button';
      deleteButton.className = 'messenger-thread-delete';
      deleteButton.setAttribute('aria-label', actionLabel);
      deleteButton.title = actionLabel;
      deleteButton.dataset.threadAction = actionType;
      deleteButton.dataset.threadId = String(threadId);
      deleteButton.innerHTML = actionType === 'leave' ? '&larr;' : '&times;';
      deleteButton.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        handleThreadAction(threadId, actionType);
      });
      item.append(deleteButton);

      historyList.append(item);
    });
  }

  function normalizeSelectedCircle() {
    if (selectedCircle === 'all') {
      return;
    }
    if (selectedCircle === 'unaffiliated') {
      if (!onlineUsers.some((user) => !user.circle)) {
        selectedCircle = 'all';
      }
      return;
    }
    const exists = onlineCircles.some((circle) => String(circle.id) === selectedCircle);
    if (!exists) {
      selectedCircle = 'all';
    }
  }

  function buildOnlineUserButton(user, options = {}) {
    const isOffline = !!options.offline;
    const item = document.createElement('button');
    item.type = 'button';
    item.className = 'messenger-user';
    if (user.same_circle) {
      item.classList.add('is-highlighted');
    }
    if (isOffline) {
      item.classList.add('is-offline');
    }

    const pendingId = messengerTray.dataset.pendingRecipient || '';
    if (pendingId && pendingId === String(user.id)) {
      item.classList.add('is-busy');
      item.disabled = true;
    }

    const dot = document.createElement('span');
    dot.className = 'messenger-user-dot';
    item.append(dot);

    const avatar = document.createElement('span');
    avatar.className = 'messenger-user-avatar';
    const avatarImg = document.createElement('img');
    avatarImg.src = user.avatar_url || DEFAULT_AVATAR;
    avatarImg.alt = `${user.username || 'Member'} avatar`;
    avatar.append(avatarImg);
    item.append(avatar);

    const body = document.createElement('span');
    body.className = 'messenger-user-body';
    const name = document.createElement('span');
    name.className = 'messenger-user-name';
    name.textContent = user.username || 'Member';
    body.append(name);

    const meta = document.createElement('span');
    meta.className = 'messenger-user-meta';
    if (user.has_chat_keys) {
      if (isOffline) {
        meta.textContent = user.circle ? `${user.circle.name} · offline` : 'Offline';
      } else {
        meta.textContent = user.circle ? user.circle.name : 'all one circle';
      }
    } else {
      meta.textContent = 'Whispers locked';
      item.classList.add('is-locked');
      item.disabled = true;
    }
    body.append(meta);
    item.append(body);

    if (user.has_chat_keys && !item.disabled) {
      item.addEventListener('click', () => startDirectMessage(user));
    }

    return item;
  }

  function buildGroupBuilder(visibleUsers) {
    const form = document.createElement('form');
    form.className = 'messenger-group-builder';
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      submitGroupBuilder();
    });

    const nameInput = document.createElement('input');
    nameInput.type = 'text';
    nameInput.className = 'messenger-group-name';
    nameInput.placeholder = 'Circle name (optional)';
    nameInput.value = groupBuilderName;
    nameInput.maxLength = 120;
    nameInput.addEventListener('input', (event) => {
      groupBuilderName = event.target.value.slice(0, 120);
    });
    form.append(nameInput);

    const hint = document.createElement('p');
    hint.className = 'messenger-group-hint';
    hint.textContent = 'Search and add members to start a shared whisper.';
    form.append(hint);

    // Combine online and offline users for group creation
    const onlineIds = new Set(onlineUsers.map(u => u.id));
    const offlineFiltered = allRecipients.filter(u => !onlineIds.has(u.id));
    const allAvailableUsers = [...visibleUsers, ...offlineFiltered];

    // Selected members chips container
    const selectedChipsWrap = document.createElement('div');
    selectedChipsWrap.className = 'messenger-group-selected';

    function renderSelectedChips() {
      selectedChipsWrap.innerHTML = '';
      if (groupBuilderMembers.size === 0) {
        selectedChipsWrap.innerHTML = '<p class="muted" style="font-size: 13px; margin: 8px 0;">No members selected yet</p>';
        return;
      }
      groupBuilderMembers.forEach(userId => {
        const user = allAvailableUsers.find(u => u.id === userId);
        if (!user) return;

        const chip = document.createElement('div');
        chip.className = 'messenger-group-chip';
        chip.innerHTML = `
          <span>${user.username}</span>
          <button type="button" class="messenger-group-chip-remove" data-user-id="${userId}">×</button>
        `;
        chip.querySelector('.messenger-group-chip-remove').addEventListener('click', () => {
          groupBuilderMembers.delete(userId);
          renderTray();
        });
        selectedChipsWrap.append(chip);
      });
    }

    renderSelectedChips();
    form.append(selectedChipsWrap);

    // Search input wrapper
    const searchWrap = document.createElement('div');
    searchWrap.className = 'messenger-group-search-wrap';

    const searchInput = document.createElement('input');
    searchInput.type = 'text';
    searchInput.className = 'messenger-group-search';
    searchInput.placeholder = 'Type to search users...';
    searchWrap.append(searchInput);

    const resultsWrap = document.createElement('div');
    resultsWrap.className = 'messenger-group-search-results';
    searchWrap.append(resultsWrap);

    form.append(searchWrap);

    // Search functionality
    let searchTimeout;
    searchInput.addEventListener('input', () => {
      clearTimeout(searchTimeout);
      const query = searchInput.value.trim().toLowerCase();

      if (!query) {
        resultsWrap.innerHTML = '';
        resultsWrap.style.display = 'none';
        return;
      }

      searchTimeout = setTimeout(() => {
        const matches = allAvailableUsers.filter(user => {
          // Don't filter by has_chat_keys - allow adding all users
          if (groupBuilderMembers.has(user.id)) return false;
          return user.username.toLowerCase().includes(query);
        });

        if (matches.length === 0) {
          resultsWrap.innerHTML = '<div class="messenger-group-search-empty">No users found</div>';
          resultsWrap.style.display = 'block';
          return;
        }

        resultsWrap.innerHTML = '';
        matches.slice(0, 10).forEach(user => {
          const result = document.createElement('div');
          result.className = 'messenger-group-search-result';
          if (!user.has_chat_keys) {
            result.classList.add('is-locked');
          }
          const circleText = user.circle ? ` · ${user.circle.name}` : ' · all one circle';
          const onlineStatus = onlineIds.has(user.id) ? '' : ' (offline)';
          const lockStatus = !user.has_chat_keys ? ' 🔒' : '';
          result.innerHTML = `
            <span class="messenger-group-search-result-name">${user.username}${lockStatus}</span>
            <span class="messenger-group-search-result-meta">${circleText}${onlineStatus}${!user.has_chat_keys ? ' · Whispers locked' : ''}</span>
          `;
          result.addEventListener('click', () => {
            console.log('[chat] Adding user to group:', user.username, 'has_chat_keys:', user.has_chat_keys);
            // Check if user has chat keys before adding
            if (!user.has_chat_keys) {
              alert(`${user.username} must unlock whispers before joining a group.`);
              return;
            }
            if (groupBuilderMembers.size >= GROUP_MEMBER_LIMIT - 1) {
              groupBuilderError = `Group whispers are limited to ${GROUP_MEMBER_LIMIT} members.`;
              console.log('[chat] Group member limit reached');
              renderTray();
              return;
            }
            console.log('[chat] Adding user ID to group:', user.id);
            groupBuilderMembers.add(user.id);
            searchInput.value = '';
            resultsWrap.innerHTML = '';
            resultsWrap.style.display = 'none';
            if (groupBuilderError && groupBuilderError.startsWith('Group whispers are limited')) {
              groupBuilderError = '';
            }
            renderTray();
          });
          resultsWrap.append(result);
        });
        resultsWrap.style.display = 'block';
      }, 200);
    });

    // Hide results when clicking outside
    document.addEventListener('click', (e) => {
      if (!searchWrap.contains(e.target)) {
        resultsWrap.style.display = 'none';
      }
    });

    if (groupBuilderError) {
      const errorMsg = document.createElement('p');
      errorMsg.className = 'messenger-group-error';
      errorMsg.textContent = groupBuilderError;
      form.append(errorMsg);
    }

    const actions = document.createElement('div');
    actions.className = 'messenger-group-actions';

    const cancelButton = document.createElement('button');
    cancelButton.type = 'button';
    cancelButton.className = 'messenger-action-secondary';
    cancelButton.textContent = 'Cancel';
    cancelButton.disabled = groupBuilderSubmitting;
    cancelButton.addEventListener('click', () => {
      groupBuilderOpen = false;
      resetGroupBuilderState();
      renderTray();
    });
    actions.append(cancelButton);

    const submitButton = document.createElement('button');
    submitButton.type = 'submit';
    submitButton.className = 'messenger-group-create';
    submitButton.textContent = groupBuilderSubmitting ? 'Creating…' : 'Create group';
    submitButton.disabled = groupBuilderSubmitting || !groupBuilderMembers.size;
    actions.append(submitButton);

    form.append(actions);
    return form;
  }

  function setTrayNotice(message, tone = 'info', shouldRender = false) {
    trayNotice = message || '';
    trayNoticeTone = tone || 'info';
    if (shouldRender) {
      renderTray();
    }
  }

  function resetGroupBuilderState() {
    groupBuilderName = '';
    groupBuilderMembers.clear();
    groupBuilderError = '';
    groupBuilderSubmitting = false;
  }

  function offlineUsersForDisplay() {
    const onlineIds = new Set(onlineUsers.map((user) => user.id));
    return allRecipients.filter((user) => user.has_chat_keys && !onlineIds.has(user.id));
  }

  function toggleOfflineVisibility() {
    showOffline = !showOffline;
    if (showOffline && !allRecipients.length && offlineFetchState !== 'loading') {
      fetchRecipients();
      return;
    }
    renderTray();
  }

  async function fetchRecipients(force = false) {
    if (!force) {
      if (offlineFetchState === 'loading') {
        return;
      }
      if (allRecipients.length) {
        offlineFetchState = 'ready';
        renderTray();
        return;
      }
    }
    offlineFetchState = 'loading';
    renderTray();
    try {
      const response = await fetch('/chat/api/recipients', {
        headers: { Accept: 'application/json' },
        credentials: 'same-origin',
      });
      if (!response.ok) {
        throw new Error(`status ${response.status}`);
      }
      const data = await response.json();
      allRecipients = Array.isArray(data.users) ? data.users : [];
      offlineFetchState = 'ready';
    } catch (err) {
      console.error('[chat] recipient fetch failed', err);
      offlineFetchState = 'error';
    }
    renderTray();
  }

  function resolveUserLink(user, preference) {
    if (!user) {
      return null;
    }
    if (preference === 'message' && user.message_url) {
      return user.message_url;
    }
    if (preference === 'profile' && user.profile_url) {
      return user.profile_url;
    }
    return user.profile_url || user.message_url || null;
  }

  function createUserChipElement(user, { label, size = 'xs', linkPreference = 'profile' } = {}) {
    if (!user) {
      return document.createTextNode(label || 'Unknown');
    }
    const linkTarget = resolveUserLink(user, linkPreference);
    const element = linkTarget ? document.createElement('a') : document.createElement('span');
    element.className = `user-chip user-chip-${size}`;
    if (linkTarget) {
      element.href = linkTarget;
    }

    const avatarWrap = document.createElement('span');
    avatarWrap.className = 'user-chip-avatar';
    const avatar = document.createElement('img');
    avatar.src = user.avatar_url || DEFAULT_AVATAR;
    avatar.alt = `${label || user.username || 'Member'} avatar`;
    avatarWrap.append(avatar);

    const name = document.createElement('span');
    name.className = 'user-chip-name';
    name.textContent = label || user.username || 'Member';

    element.append(avatarWrap, name);
    return element;
  }

  async function fetchOnlineUsers(force = false) {
    const now = Date.now();
    if (!force && onlineUsers.length && now - lastOnlineFetch < 15000) {
      messengerTray.dataset.state = 'ready';
      renderTray();
      return;
    }
    messengerTray.dataset.state = 'loading';
    renderTray();
    try {
      const response = await fetch('/chat/api/online', {
        headers: { Accept: 'application/json' },
        credentials: 'same-origin',
      });
      if (!response.ok) {
        throw new Error(`status ${response.status}`);
      }
      const data = await response.json();
      onlineUsers = Array.isArray(data.users) ? data.users : [];
      onlineCircles = Array.isArray(data.circles) ? data.circles : [];
      lastOnlineFetch = now;
      messengerTray.dataset.state = 'ready';
      messengerTray.dataset.pendingRecipient = '';
      setTrayNotice('', 'info');
    } catch (err) {
      console.error('[chat] online fetch failed', err);
      messengerTray.dataset.state = 'error';
      messengerTray.dataset.pendingRecipient = '';
      if (!trayNotice) {
        setTrayNotice('Unable to load online members. Try again in a moment.', 'danger');
      }
    }
    renderTray();
  }

  function startOnlineRefresh() {
    stopOnlineRefresh();
    onlineRefreshTimer = window.setInterval(() => fetchOnlineUsers(true), ONLINE_REFRESH_MS);
  }

  function stopOnlineRefresh() {
    if (onlineRefreshTimer) {
      clearInterval(onlineRefreshTimer);
      onlineRefreshTimer = null;
    }
    messengerTray.dataset.pendingRecipient = '';
  }

  async function startDirectMessage(user) {
    if (!user || !user.id) {
      return;
    }
    if (!user.has_chat_keys) {
      setTrayNotice(
        `${user.username || 'That member'} has not unlocked whispers yet.`,
        'warning',
        true,
      );
      return;
    }
    messengerTray.dataset.pendingRecipient = String(user.id);
    setTrayNotice('Opening whispers…', 'info', true);
    try {
      const payload = new URLSearchParams();
      payload.append('recipient_id', String(user.id));
      const response = await fetch('/chat/threads/dm', {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'same-origin',
        body: payload,
      });
      messengerTray.dataset.pendingRecipient = '';
      if (!response.ok) {
        let message = 'Unable to open whispers with that member.';
        let tone = 'danger';
        if (response.status === 409) {
          message = `${user.username || 'That member'} has not unlocked whispers yet.`;
          tone = 'warning';
        } else if (response.status === 404) {
          message = 'That member is not available right now.';
        }
        setTrayNotice(message, tone, true);
        return;
      }
      const data = await response.json().catch(() => null);
      if (!data?.ok || !data.thread_id) {
        setTrayNotice('Unable to open whispers with that member.', 'danger', true);
        return;
      }
      const threadId = Number(data.thread_id);
      if (!threadLookup.has(threadId)) {
        const ownerFromResponse = typeof data.owner_id === 'number' ? data.owner_id : currentUserId;
        threadLookup.set(threadId, {
          label: data.display_name || user.username || 'Conversation',
          preview: '',
          unread: 0,
          isGroup: false,
          ownerId: ownerFromResponse,
        });
      }
      if (!threadIds.includes(threadId)) {
        threadIds.push(threadId);
        subscribeToThread(threadId);
      }
      setTrayNotice('', 'info');
      renderTray();
      messengerTray.classList.remove('is-open');
      stopOnlineRefresh();
      openThread(threadId);
    } catch (err) {
      console.error('[chat] whisper start failed', err);
      messengerTray.dataset.pendingRecipient = '';
      setTrayNotice('Unable to open whispers with that member.', 'danger', true);
    }
  }

  async function submitGroupBuilder() {
    if (groupBuilderSubmitting) {
      return;
    }
    if (!groupBuilderMembers.size) {
      groupBuilderError = 'Select at least one member to invite.';
      renderTray();
      return;
    }
    groupBuilderSubmitting = true;
    groupBuilderError = '';
    renderTray();
    try {
      const payload = new URLSearchParams();
      payload.append('name', groupBuilderName.trim());
      groupBuilderMembers.forEach((id) => payload.append('members', String(id)));
      const response = await fetch('/chat/threads/group', {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'same-origin',
        body: payload,
      });
      groupBuilderSubmitting = false;
      if (!response.ok) {
        const result = await response.json().catch(() => null);
        groupBuilderError = (result && result.error) || 'Unable to create that circle.';
        renderTray();
        return;
      }
      const data = await response.json().catch(() => null);
      if (!data?.ok || !data.thread_id) {
        groupBuilderError = 'Unable to create that circle.';
        renderTray();
        return;
      }
      const threadId = Number(data.thread_id);
      const info = threadLookup.get(threadId) || {
        preview: '',
        unread: 0,
      };
      info.label = data.display_name || groupBuilderName.trim() || 'Grove Room';
      info.preview = '';
      info.unread = 0;
      info.isGroup = !!data.is_group;
      const ownerFromResponse = typeof data.owner_id === 'number' ? data.owner_id : currentUserId;
      info.ownerId = ownerFromResponse;
      threadLookup.set(threadId, info);
      if (!threadIds.includes(threadId)) {
        threadIds.push(threadId);
        subscribeToThread(threadId);
      }
      resetGroupBuilderState();
      groupBuilderOpen = false;
      setTrayNotice('New circle whisper created.', 'info');
      renderTray();
      messengerTray.classList.remove('is-open');
      stopOnlineRefresh();
      openThread(threadId);
    } catch (err) {
      console.error('[chat] group creation failed', err);
      groupBuilderSubmitting = false;
      groupBuilderError = 'Unable to create that circle.';
      renderTray();
    }
  }

  function handleThreadAction(threadId, action) {
    if (!threadId) {
      return;
    }
    const normalized = action === 'leave' ? 'leave' : 'delete';
    const info = threadLookup.get(threadId);
    let message;
    if (normalized === 'leave') {
      message = 'Leave this group channel?';
    } else if (info?.isGroup) {
      message = 'Delete this group for everyone?';
    } else {
      message = 'Remove this conversation?';
    }
    if (!window.confirm(message)) {
      return;
    }
    if (normalized === 'leave') {
      leaveThread(threadId);
    } else {
      deleteThread(threadId);
    }
  }

  async function leaveThread(threadId) {
    if (!threadId) {
      return;
    }
    const showTray = messengerTray.classList.contains('is-open');
    if (showTray) {
      setTrayNotice('Leaving group…', 'info', true);
    }
    try {
      const response = await fetch(`/chat/threads/${threadId}/leave`, {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'same-origin',
      });
      if (!response.ok) {
        const result = await response.json().catch(() => null);
        const error = (result && result.error) || 'Unable to leave that group.';
        if (showTray) {
          setTrayNotice(error, 'danger', true);
        } else {
          window.alert(error);
        }
        return;
      }
      const wasCurrent = currentThreadId === threadId;
      removeThreadState(threadId);
      if (showTray) {
        setTrayNotice('You left the group.', 'info', true);
      }
      if (wasCurrent) {
        window.location.href = '/chat/';
      }
    } catch (err) {
      console.error('[chat] leave group failed', err);
      if (showTray) {
        setTrayNotice('Unable to leave that group.', 'danger', true);
      } else {
        window.alert('Unable to leave that group.');
      }
    }
  }

  async function deleteThread(threadId) {
    if (!threadId) {
      return;
    }
    const info = threadLookup.get(threadId);
    const showTray = messengerTray.classList.contains('is-open');
    if (showTray) {
      setTrayNotice(info?.isGroup ? 'Deleting group…' : 'Removing whisper…', 'info', true);
    }
    try {
      const response = await fetch(`/chat/threads/${threadId}/delete`, {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'same-origin',
      });
      if (!response.ok) {
        const result = await response.json().catch(() => null);
        const error = (result && result.error) || 'Unable to remove that whisper.';
        if (showTray) {
          setTrayNotice(error, 'danger', true);
        } else {
          window.alert(error);
        }
        return;
      }
      const wasCurrent = currentThreadId === threadId;
      removeThreadState(threadId);
      if (showTray) {
        setTrayNotice(info?.isGroup ? 'Group removed.' : 'Whisper removed.', 'info', true);
      }
      if (wasCurrent) {
        window.location.href = '/chat/';
      }
    } catch (err) {
      console.error('[chat] whisper delete failed', err);
      if (showTray) {
        setTrayNotice('Unable to remove that whisper.', 'danger', true);
      } else {
        window.alert('Unable to remove that whisper.');
      }
    }
  }

  async function blockUser(userId) {
    if (!userId) {
      return;
    }
    try {
      const response = await fetch(`/chat/block/${userId}`, {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'same-origin',
      });
      if (!response.ok) {
        const result = await response.json().catch(() => null);
        const error = (result && result.error) || 'Unable to block that user.';
        window.alert(error);
        return;
      }
      window.location.reload();
    } catch (err) {
      console.error('[chat] block user failed', err);
      window.alert('Unable to block that user.');
    }
  }

  async function unblockUser(userId) {
    if (!userId) {
      return;
    }
    try {
      const response = await fetch(`/chat/unblock/${userId}`, {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'same-origin',
      });
      if (!response.ok) {
        const result = await response.json().catch(() => null);
        const error = (result && result.error) || 'Unable to unblock that user.';
        window.alert(error);
        return;
      }
      window.location.reload();
    } catch (err) {
      console.error('[chat] unblock user failed', err);
      window.alert('Unable to unblock that user.');
    }
  }

  async function kickMember(threadId, userId) {
    if (!threadId || !userId) {
      return;
    }
    try {
      const response = await fetch(`/chat/threads/${threadId}/kick/${userId}`, {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'same-origin',
      });
      if (!response.ok) {
        const result = await response.json().catch(() => null);
        const error = (result && result.error) || 'Unable to remove that member.';
        window.alert(error);
        return;
      }
      // Reload the page to reflect the change
      window.location.reload();
    } catch (err) {
      console.error('[chat] kick member failed', err);
      window.alert('Unable to remove that member.');
    }
  }

  function showAddMembersModal(threadId) {
    // Try to find modal in chat popover first, then in main chat window
    const popover = document.querySelector(`[data-chat-window="${threadId}"]`);
    const modal = popover
      ? popover.querySelector('[data-add-members-modal]')
      : document.querySelector('[data-add-members-modal]');

    if (!modal) {
      return;
    }

    modal.style.display = 'block';
    modal.dataset.threadId = threadId;

    const searchInput = modal.querySelector('[data-add-members-search]');
    const resultsDiv = modal.querySelector('[data-add-members-results]');
    const closeButton = modal.querySelector('[data-add-members-close]');
    const overlay = modal.querySelector('[data-add-members-overlay]');

    if (searchInput) {
      searchInput.value = '';
      searchInput.focus();
    }
    if (resultsDiv) {
      resultsDiv.innerHTML = '<p class="add-members-empty">Type to search for members to add</p>';
    }

    const hideModal = () => {
      modal.style.display = 'none';
      if (searchInput) searchInput.value = '';
      if (resultsDiv) resultsDiv.innerHTML = '';
    };

    if (closeButton) {
      closeButton.onclick = hideModal;
    }
    if (overlay) {
      overlay.onclick = hideModal;
    }

    if (searchInput) {
      let searchTimeout;
      searchInput.oninput = () => {
        clearTimeout(searchTimeout);
        const query = searchInput.value.trim().toLowerCase();

        if (!query) {
          resultsDiv.innerHTML = '<p class="add-members-empty">Type to search for members to add</p>';
          return;
        }

        searchTimeout = setTimeout(() => searchAddMembers(threadId, query, resultsDiv), 300);
      };
    }
  }

  async function searchAddMembers(threadId, query, resultsDiv) {
    if (!resultsDiv) return;

    resultsDiv.innerHTML = '<p class="add-members-empty">Searching...</p>';

    try {
      const response = await fetch(`/api/v1/users/search?q=${encodeURIComponent(query)}`);
      if (!response.ok) {
        resultsDiv.innerHTML = '<p class="add-members-empty">Error searching users</p>';
        return;
      }

      const data = await response.json();
      const users = data.users || [];

      if (users.length === 0) {
        resultsDiv.innerHTML = '<p class="add-members-empty">No users found</p>';
        return;
      }

      resultsDiv.innerHTML = '';
      users.slice(0, 10).forEach(user => {
        const resultDiv = document.createElement('div');
        resultDiv.className = 'add-member-result';
        if (!user.has_chat_keys) {
          resultDiv.classList.add('is-locked');
        }

        const infoDiv = document.createElement('div');
        infoDiv.className = 'add-member-result-info';

        const nameSpan = document.createElement('div');
        nameSpan.className = 'add-member-result-name';
        nameSpan.textContent = user.username + (!user.has_chat_keys ? ' 🔒' : '');

        const metaSpan = document.createElement('div');
        metaSpan.className = 'add-member-result-meta';
        metaSpan.textContent = !user.has_chat_keys ? 'Whispers locked' : 'Available';

        infoDiv.append(nameSpan, metaSpan);

        if (user.has_chat_keys) {
          const addBtn = document.createElement('button');
          addBtn.className = 'add-member-result-btn';
          addBtn.textContent = 'Add';
          addBtn.onclick = () => addMemberToGroup(threadId, user.id);
          resultDiv.append(infoDiv, addBtn);
        } else {
          resultDiv.append(infoDiv);
        }

        resultsDiv.append(resultDiv);
      });
    } catch (err) {
      console.error('[chat] search add members failed', err);
      resultsDiv.innerHTML = '<p class="add-members-empty">Error searching users</p>';
    }
  }

  async function addMemberToGroup(threadId, userId) {
    if (!threadId || !userId) {
      return;
    }

    try {
      const payload = new URLSearchParams();
      payload.append('user_id', userId);

      const response = await fetch(`/chat/threads/${threadId}/add-member`, {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'same-origin',
        body: payload,
      });

      if (!response.ok) {
        const result = await response.json().catch(() => null);
        const error = (result && result.error) || 'Unable to add that member.';
        window.alert(error);
        return;
      }

      const modal = document.querySelector('[data-add-members-modal]');
      if (modal) {
        modal.style.display = 'none';
      }

      // Reload to show the new member
      window.location.reload();
    } catch (err) {
      console.error('[chat] add member failed', err);
      window.alert('Unable to add that member.');
    }
  }

  async function deleteMessage(threadId, messageId, scope = 'all') {
    if (!threadId || !messageId) {
      return;
    }
    try {
      const payload = new URLSearchParams();
      payload.append('scope', scope);

      const response = await fetch(`/chat/messages/${messageId}/delete`, {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'same-origin',
        body: payload,
      });
      if (!response.ok) {
        const result = await response.json().catch(() => null);
        const error = (result && result.error) || 'Unable to remove that message.';
        if (messengerTray.classList.contains('is-open')) {
          setTrayNotice(error, 'danger', true);
        } else {
          window.alert(error);
        }
        return;
      }

      const result = await response.json().catch(() => null);
      if (result && result.scope === 'self') {
        // For "delete for self", just hide the message locally
        const messageEl = messageList?.querySelector(`[data-message-id="${messageId}"]`);
        if (messageEl) {
          messageEl.remove();
        }
        const popoverMessageEl = document.querySelector(`.chat-popover[data-chat-window="${threadId}"] [data-message-id="${messageId}"]`);
        if (popoverMessageEl) {
          popoverMessageEl.remove();
        }
      }
    } catch (err) {
      console.error('[chat] message delete failed', err);
      if (messengerTray.classList.contains('is-open')) {
        setTrayNotice('Unable to remove that message.', 'danger', true);
      } else {
        window.alert('Unable to remove that message.');
      }
    }
  }

  function removeThreadState(threadId) {
    threadLookup.delete(threadId);
    threadHistory.delete(threadId);
    previewMap.delete(threadId);
    threadIds = threadIds.filter((id) => id !== threadId);
    subscribedThreads.delete(threadId);
    const windowInfo = windowMap.get(threadId);
    if (windowInfo?.container) {
      windowInfo.container.remove();
    }
    windowMap.delete(threadId);
    if (currentThreadId === threadId) {
      currentThreadId = null;
    }
    if (messengerDock.dataset.activeThread === String(threadId)) {
      messengerDock.dataset.activeThread = '';
      const dockLabel = messengerDock.querySelector('.dock-label');
      if (dockLabel) {
        dockLabel.textContent = 'Messages';
      }
    }
    const threadRow = document.querySelector(`[data-thread-id="${threadId}"]`);
    if (threadRow) {
      threadRow.remove();
    }
    renderTray();
  }

  function handleMessageDeleted(threadId, messageId) {
    const numericThreadId = Number(threadId);
    const numericMessageId = Number(messageId);
    if (!numericThreadId || !numericMessageId) {
      return;
    }
    const history = threadHistory.get(numericThreadId) || [];
    const index = history.findIndex((entry) => entry.id === numericMessageId);
    let removed;
    if (index >= 0) {
      [removed] = history.splice(index, 1);
      threadHistory.set(numericThreadId, history);
    }

    if (currentThreadId === numericThreadId && messageList) {
      const node = messageList.querySelector(`[data-message-id="${numericMessageId}"]`);
      if (node) {
        node.remove();
      }
    }

    const windowInfo = windowMap.get(numericThreadId);
    if (windowInfo) {
      windowInfo.messageIds.delete(numericMessageId);
      const bubble = windowInfo.body?.querySelector(`[data-message-id="${numericMessageId}"]`);
      if (bubble) {
        bubble.remove();
      }
    }

    const info = threadLookup.get(numericThreadId);
    if (info) {
      if (
        removed &&
        !removed.is_self &&
        numericThreadId !== currentThreadId &&
        info.unread
      ) {
        info.unread = Math.max((info.unread || 0) - 1, 0);
      }
      const latest = history.length ? history[history.length - 1] : null;
      const previewText = latest ? latest.body || '' : 'No messages yet.';
      applyThreadPreview(numericThreadId, previewText);
      const entry = previewMap.get(numericThreadId);
      if (entry?.unread) {
        if (info.unread) {
          entry.unread.textContent = String(info.unread);
          entry.unread.classList.remove('is-hidden');
        } else {
          entry.unread.textContent = '';
          entry.unread.classList.add('is-hidden');
        }
      }
      threadLookup.set(numericThreadId, info);
    }

    if (
      messengerDock.dataset.activeThread === String(numericThreadId) &&
      (!info || !info.unread)
    ) {
      messengerDock.dataset.activeThread = '';
      messengerDock.classList.remove('is-active');
      const dockLabel = messengerDock.querySelector('.dock-label');
      if (dockLabel) {
        dockLabel.textContent = 'Messages';
      }
    }

    renderTray();
  }

  function openThread(threadId) {
    const info = threadLookup.get(threadId) || { label: 'Conversation', isGroup: false };
    const windowInfo = ensureWindow(threadId, info.label);
    const history = threadHistory.get(threadId);
    if (history && windowInfo && !windowInfo.messageIds.size) {
      history.forEach((message) => appendWindowMessage(threadId, info.label, message));
    }
    clearUnread(threadId);
  }

  function ensureWindow(threadId, label) {
    if (windowMap.has(threadId)) {
      const existing = windowMap.get(threadId);
      existing.container.classList.add('is-visible');
      return existing;
    }

    const info = threadLookup.get(threadId);
    const isGroupOwner = info && info.isGroup && info.ownerId === currentUserId;

    const container = document.createElement('div');
    container.className = 'chat-popover';
    container.dataset.chatWindow = String(threadId);
    container.innerHTML = `
      <div class="chat-popover-resize-handle" data-resize-handle></div>
      <header class="chat-popover-header">
        <span class="chat-popover-title">${label || 'Conversation'}</span>
        <div class="chat-popover-header-actions">
          ${isGroupOwner ? `<button type="button" class="chat-popover-add-members" data-add-members data-thread-id="${threadId}" title="Add members" aria-label="Add members">➕</button>` : ''}
          <button type="button" class="chat-popover-maximize" data-maximize-chat data-thread-id="${threadId}" title="Open full screen" aria-label="Maximize">⛶</button>
          <button type="button" class="chat-popover-close" aria-label="Close">×</button>
        </div>
      </header>
      <section class="chat-popover-body" data-popover-messages></section>
      <form class="chat-popover-compose" data-popover-form>
        <input type="hidden" name="thread_id" value="${threadId}">
        <textarea name="body" rows="2" placeholder="Type a message…" maxlength="${maxLength || 2000}" required></textarea>
        <div class="chat-compose-actions">
          <button type="button" class="chat-icon-btn emoji-picker-btn" data-emoji-picker-btn title="Add emoji">
            <span class="emoji-icon">😊</span>
          </button>
          <button type="button" class="chat-icon-btn gif-picker-btn" data-gif-picker-btn title="Add GIF">
            <span class="gif-icon">🎬</span>
          </button>
          <button type="submit" class="btn btn-primary btn-compact chat-send-btn">Send</button>
        </div>
      </form>
    `;

    // Add the add members modal if user is group owner
    if (isGroupOwner) {
      const modalHTML = `
        <div class="add-members-modal" data-add-members-modal style="display: none;">
          <div class="add-members-overlay" data-add-members-overlay></div>
          <div class="add-members-content">
            <div class="add-members-header">
              <h3>Add Members to Group</h3>
              <button type="button" class="add-members-close" data-add-members-close>×</button>
            </div>
            <div class="add-members-body">
              <input type="text" class="add-members-search" placeholder="Search users..." data-add-members-search>
              <div class="add-members-results" data-add-members-results></div>
            </div>
          </div>
        </div>
      `;
      container.insertAdjacentHTML('beforeend', modalHTML);
    }

    windowRail.append(container);
    requestAnimationFrame(() => container.classList.add('is-visible'));
    const windowInfo = {
      container,
      body: container.querySelector('[data-popover-messages]'),
      form: container.querySelector('[data-popover-form]'),
      messageIds: new Set(),
    };
    if (windowInfo.form && !(windowInfo.form.getAttribute('action') || '').trim()) {
      windowInfo.form.setAttribute('action', composeForm?.getAttribute('action') || '/chat/send');
    }
    if (windowInfo.form) {
      attachComposeShortcuts(windowInfo.form);
    }

    // Add resize functionality
    const resizeHandle = container.querySelector('[data-resize-handle]');
    if (resizeHandle) {
      attachResizeHandler(container, resizeHandle);
    }

    windowMap.set(threadId, windowInfo);
    return windowInfo;
  }

  function attachResizeHandler(container, handle) {
    let isResizing = false;
    let startY = 0;
    let startHeight = 0;

    handle.addEventListener('mousedown', (e) => {
      isResizing = true;
      startY = e.clientY;
      startHeight = container.offsetHeight;
      e.preventDefault();
      document.body.style.userSelect = 'none';
      container.classList.add('is-resizing');
    });

    document.addEventListener('mousemove', (e) => {
      if (!isResizing) return;
      const deltaY = startY - e.clientY;
      const newHeight = Math.max(300, Math.min(800, startHeight + deltaY));
      container.style.height = `${newHeight}px`;
    });

    document.addEventListener('mouseup', () => {
      if (isResizing) {
        isResizing = false;
        document.body.style.userSelect = '';
        container.classList.remove('is-resizing');
      }
    });
  }

  function highlightDock(threadId, label, message) {
    messengerDock.classList.add('is-active');
    messengerDock.dataset.activeThread = String(threadId);
    setTrayNotice('', 'info');
    const dockLabel = messengerDock.querySelector('.dock-label');
    if (dockLabel) {
      dockLabel.textContent = label || 'Messages';
    }
    appendWindowMessage(threadId, label, message);
    if (window.__chatTone && typeof window.__chatTone.play === 'function') {
      window.__chatTone.play();
    }
  }

  function buildDeleteButton(threadId, messageId) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'chat-message-delete';
    button.dataset.messageDelete = '1';
    button.dataset.threadId = String(threadId);
    button.dataset.messageId = String(messageId);
    button.setAttribute('aria-label', 'Delete message');
    button.title = 'Delete message';
    button.textContent = '×';
    return button;
  }

  function appendWindowMessage(threadId, label, message) {
    if (!message) {
      return;
    }
    const info = ensureWindow(threadId, label);
    if (!info || !info.body) {
      return;
    }
    if (info.messageIds.has(message.id)) {
      return;
    }
    info.messageIds.add(message.id);

    const bubble = document.createElement('article');
    bubble.className = 'chat-popover-message';
    bubble.dataset.messageId = String(message.id);
    if (message.is_self) {
      bubble.classList.add('chat-popover-message-self');
    }
    const header = document.createElement('header');
    const senderChip = createUserChipElement(message.sender, {
      label: message.is_self ? 'You' : null,
      size: 'xs',
      linkPreference: message.is_self ? 'profile' : 'message',
    });
    header.append(senderChip);

    const tools = document.createElement('div');
    tools.className = 'chat-popover-tools';
    const timestamp = document.createElement('time');
    if (message.created_at) {
      timestamp.dateTime = message.created_at;
    }
    timestamp.textContent = message.created_label || '';
    tools.append(timestamp);
    if (message.can_delete) {
      tools.append(buildDeleteButton(threadId, message.id));
    }
    header.append(tools);
    bubble.append(header);

    const body = document.createElement('div');
    body.innerHTML = renderMessageBody(message.body || '');
    bubble.append(body);

    info.body.append(bubble);
    info.body.scrollTop = info.body.scrollHeight;
  }

  function appendMainMessage(threadId, message) {
    if (!messageList || !message) {
      return;
    }
    if (messageList.querySelector(`[data-message-id="${message.id}"]`)) {
      return;
    }

    const article = document.createElement('article');
    article.className = 'chat-message';
    if (message.is_self) {
      article.classList.add('chat-message-self');
    }
    article.dataset.messageId = message.id;

    const meta = document.createElement('div');
    meta.className = 'chat-message-meta';

    const chip = createUserChipElement(message.sender, {
      label: message.is_self ? 'You' : null,
      size: 'xs',
      linkPreference: message.is_self ? 'profile' : 'message',
    });
    meta.append(chip);

    const tools = document.createElement('div');
    tools.className = 'chat-message-tools';
    const timestamp = document.createElement('time');
    if (message.created_at) {
      timestamp.dateTime = message.created_at;
    }
    timestamp.textContent = message.created_label || '';
    tools.append(timestamp);
    if (message.can_delete) {
      tools.append(buildDeleteButton(threadId, message.id));
    }
    meta.append(tools);

    const body = document.createElement('div');
    body.className = 'chat-message-body';
    body.innerHTML = renderMessageBody(message.body || '');

    article.append(meta, body);
    messageList.append(article);
    messageList.scrollTop = messageList.scrollHeight;
    updateThreadPreview(threadId, message);
  }

  function markUnread(threadId, message) {
    const entry = previewMap.get(threadId);
    if (entry?.preview) {
      entry.preview.textContent = truncateBody(message.body || '');
    }

    const info = threadLookup.get(threadId) || {
      label: message.sender?.username || 'Conversation',
      preview: '',
      unread: 0,
      isGroup: false,
      ownerId: null,
    };
    info.preview = message.body || info.preview;

    if (threadId === currentThreadId || message.is_self) {
      info.unread = 0;
      if (entry?.unread) {
        entry.unread.textContent = '';
        entry.unread.classList.add('is-hidden');
      }
    } else {
      info.unread = (info.unread || 0) + 1;
      if (entry?.unread) {
        entry.unread.textContent = String(info.unread);
        entry.unread.classList.remove('is-hidden');
      }
      const label = info.label;
      highlightDock(threadId, label, message);
    }

    threadLookup.set(threadId, info);
    renderTray();
  }

  function clearUnread(threadId) {
    const info = threadLookup.get(threadId);
    if (info) {
      info.unread = 0;
      threadLookup.set(threadId, info);
    }
    const entry = previewMap.get(threadId);
    if (entry?.unread) {
      entry.unread.textContent = '';
      entry.unread.classList.add('is-hidden');
    }
    renderTray();
  }

  function applyThreadPreview(threadId, previewText) {
    const info = threadLookup.get(threadId);
    if (info) {
      info.preview = previewText;
      threadLookup.set(threadId, info);
    }
    const entry = previewMap.get(threadId);
    if (entry?.preview) {
      entry.preview.textContent = truncateBody(previewText || '');
    }
  }

  function updateThreadPreview(threadId, message) {
    if (!message) {
      return;
    }
    applyThreadPreview(threadId, message.body || '');
    renderTray();
  }

  function handleSubscribed(data) {
    const threadId = data.thread_id;
    const label = data.display_name || getThreadLabel(threadId);
    const ownerFromPayload = typeof data.owner_id === 'number' ? data.owner_id : null;
    let info = threadLookup.get(threadId);
    if (info) {
      info.label = label;
      info.isGroup = !!data.is_group;
      if (ownerFromPayload != null) {
        info.ownerId = ownerFromPayload;
      }
      threadLookup.set(threadId, info);
    } else {
      info = {
        label,
        preview: '',
        unread: 0,
        isGroup: !!data.is_group,
        ownerId: ownerFromPayload,
      };
      threadLookup.set(threadId, info);
      if (!threadIds.includes(threadId)) {
        threadIds.push(threadId);
      }
    }

    if (Array.isArray(data.messages)) {
      threadHistory.set(threadId, data.messages.slice());
      if (messageList && currentThreadId === threadId && !messageList.children.length) {
        data.messages.forEach((message) => appendMainMessage(threadId, message));
        clearUnread(threadId);
      } else if (data.messages.length) {
        const last = data.messages[data.messages.length - 1];
        applyThreadPreview(threadId, last.body || '');
      } else {
        applyThreadPreview(threadId, 'No messages yet.');
      }
    }
    renderTray();
  }

  function handleIncomingMessage(threadId, message) {
    if (!message) {
      return;
    }
    const history = threadHistory.get(threadId) || [];
    if (!history.find((entry) => entry.id === message.id)) {
      history.push(message);
      threadHistory.set(threadId, history);
    }
    markUnread(threadId, message);
    if (currentThreadId === threadId) {
      appendMainMessage(threadId, message);
      clearUnread(threadId);
    } else {
      const label = getThreadLabel(threadId);
      appendWindowMessage(threadId, label, message);
    }
  }

  function getThreadLabel(threadId) {
    const info = threadLookup.get(threadId);
    if (info) {
      return info.label;
    }
    const entry = previewMap.get(threadId);
    if (entry?.container) {
      const nameEl = entry.container.querySelector('.chat-thread-name');
      if (nameEl) {
        return nameEl.textContent.trim();
      }
    }
    return 'Conversation';
  }

  function connectSocket() {
    if (!threadIds.length) {
      return;
    }
    if (state === 'provisioning') {
      return;
    }
    const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
    socket = new WebSocket(`${scheme}://${window.location.host}${wsPath}`);
    socket.addEventListener('open', onSocketOpen);
    socket.addEventListener('message', onSocketMessage);
    socket.addEventListener('close', onSocketClose);
    socket.addEventListener('error', () => socket && socket.close());
  }

  function onSocketOpen() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    subscribedThreads.clear();
    threadIds.forEach((id) => subscribeToThread(id));
  }

  function onSocketMessage(event) {
    let data;
    try {
      data = JSON.parse(event.data);
    } catch (err) {
      return;
    }

    switch (data.type) {
      case 'message':
        handleIncomingMessage(data.thread_id, data.message);
        break;
      case 'message_deleted':
        handleMessageDeleted(data.thread_id, data.message_id);
        break;
      case 'subscribed':
        handleSubscribed(data);
        break;
      case 'unsubscribed':
        subscribedThreads.delete(data.thread_id);
        break;
      case 'welcome':
      case 'refreshed':
      case 'pong':
        break;
      case 'error':
        console.error('[chat]', data.message);
        break;
      default:
        break;
    }
  }

  function onSocketClose() {
    if (reconnectTimer) {
      return;
    }
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      connectSocket();
    }, 4000);
  }

  function subscribeToThread(threadId) {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      return;
    }
    if (subscribedThreads.has(threadId)) {
      return;
    }
    subscribedThreads.add(threadId);
    socket.send(JSON.stringify({ action: 'subscribe', thread_id: threadId }));
  }

  async function submitForm(form) {
    console.log('[chat] submitForm called with form:', form);
    const submitButton = form.querySelector('button[type="submit"]');
    console.log('[chat] submitButton:', submitButton);
    if (submitButton) {
      submitButton.disabled = true;
    }
    try {
      const formData = new FormData(form);
      const action = form.getAttribute('action') || composeForm?.getAttribute('action') || '/chat/send';
      console.log('[chat] submitting to:', action);
      console.log('[chat] form data entries:', Array.from(formData.entries()));

      // Create an AbortController for timeout
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout

      const response = await fetch(action, {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'same-origin',
        body: formData,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);
      console.log('[chat] response status:', response.status, response.statusText);

      if (response.ok) {
        const result = await response.json().catch(() => null);
        console.log('[chat] response result:', result);
        if (result && result.ok) {
          form.reset();
        }
      } else if (response.status === 403) {
        console.log('[chat] 403 forbidden, reloading...');
        window.location.reload();
      } else {
        console.warn('[chat] non-ok response:', response.status);
      }
    } catch (err) {
      if (err.name === 'AbortError') {
        console.error('[chat] send timed out after 10 seconds');
        window.alert('Message send timed out. Please try again.');
      } else {
        console.error('[chat] send failed', err);
        window.alert('Failed to send message: ' + err.message);
      }
    } finally {
      if (submitButton) {
        submitButton.disabled = false;
      }
    }
  }

  function truncateBody(body) {
    if (typeof body !== 'string') {
      return '';
    }
    if (!maxLength || body.length <= 140) {
      return body;
    }
    return `${body.slice(0, 140)}…`;
  }

  function attachComposeShortcuts(form) {
    const textarea = form.querySelector('textarea');
    if (!textarea) {
      return;
    }
    textarea.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter' || event.shiftKey || event.isComposing) {
        return;
      }
      event.preventDefault();
      if (form.requestSubmit) {
        form.requestSubmit();
      } else {
        form.submit();
      }
    });
  }
})();
