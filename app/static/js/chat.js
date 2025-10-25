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
    const form = event.target.closest('[data-popover-form]');
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
      if (Number.isNaN(threadId) || Number.isNaN(messageId)) {
        return;
      }
      if (!window.confirm('Delete this message?')) {
        return;
      }
      deleteButton.disabled = true;
      deleteMessage(threadId, messageId).finally(() => {
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
      if (Number.isNaN(threadId) || Number.isNaN(messageId)) {
        return;
      }
      if (!window.confirm('Delete this message?')) {
        return;
      }
      deleteButton.disabled = true;
      deleteMessage(threadId, messageId).finally(() => {
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
    if (event.target.closest('[data-messenger-dock]') || event.target.closest('[data-messenger-tray]')) {
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

  if (messageList) {
    messageList.scrollTop = messageList.scrollHeight;
    messageList.addEventListener('mouseenter', () => {
      if (currentThreadId != null) {
        clearUnread(currentThreadId);
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

    const availableIds = new Set(onlineUsers.map((user) => user.id));
    Array.from(groupBuilderMembers).forEach((id) => {
      if (!availableIds.has(id)) {
        groupBuilderMembers.delete(id);
      }
    });

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
      allOption.textContent = 'All circles';
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

      const includesUnaffiliated = onlineCircles.some((circle) => circle.id === 'unaffiliated');
      if (!includesUnaffiliated && onlineUsers.some((user) => !user.circle)) {
        const option = document.createElement('option');
        option.value = 'unaffiliated';
        option.textContent = 'Unaffiliated';
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

      const label = document.createElement('span');
      label.className = 'messenger-tray-main';
      label.textContent = `${info.isGroup ? '👥' : '💬'} ${info.label}`;
      openButton.append(label);

      const preview = document.createElement('span');
      preview.className = 'messenger-tray-preview';
      preview.textContent = truncateBody(info.preview || '');
      openButton.append(preview);

      const unread = document.createElement('span');
      unread.className = 'messenger-tray-unread';
      if (info.unread) {
        unread.textContent = String(info.unread);
      } else {
        unread.classList.add('is-hidden');
      }
      openButton.append(unread);

      item.append(openButton);

      const deleteButton = document.createElement('button');
      deleteButton.type = 'button';
      deleteButton.className = 'messenger-thread-delete';
      deleteButton.setAttribute('aria-label', actionLabel);
      deleteButton.title = actionLabel;
      deleteButton.dataset.threadAction = actionType;
      deleteButton.dataset.threadId = String(threadId);
      deleteButton.textContent = actionType === 'leave' ? '⤴' : '×';
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
        meta.textContent = user.circle ? user.circle.name : 'Unaffiliated';
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
    hint.textContent = 'Invite members to start a shared whisper.';
    form.append(hint);

    const membersWrap = document.createElement('div');
    membersWrap.className = 'messenger-group-members';

    let selectableCount = 0;
    visibleUsers.forEach((user) => {
      const entry = document.createElement('label');
      entry.className = 'messenger-group-member';

      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.value = String(user.id);
      checkbox.checked = groupBuilderMembers.has(user.id);
      checkbox.disabled = !user.has_chat_keys;
      checkbox.addEventListener('change', (event) => {
        const memberId = user.id;
        if (event.target.checked) {
          if (groupBuilderMembers.size >= GROUP_MEMBER_LIMIT - 1) {
            groupBuilderError = `Group whispers are limited to ${GROUP_MEMBER_LIMIT} members.`;
            event.target.checked = false;
          } else {
            groupBuilderMembers.add(memberId);
            if (groupBuilderError && groupBuilderError.startsWith('Group whispers are limited')) {
              groupBuilderError = '';
            }
          }
        } else {
          groupBuilderMembers.delete(memberId);
          if (groupBuilderError && groupBuilderMembers.size > 0) {
            groupBuilderError = '';
          }
        }
        renderTray();
      });
      entry.append(checkbox);

      const descriptor = document.createElement('span');
      descriptor.className = 'messenger-group-member-label';
      descriptor.textContent = user.username + (user.circle ? ` · ${user.circle.name}` : ' · Unaffiliated');
      entry.append(descriptor);

      if (!checkbox.disabled) {
        selectableCount += 1;
      } else {
        entry.classList.add('is-locked');
      }

      membersWrap.append(entry);
    });

    if (!membersWrap.children.length) {
      const empty = document.createElement('p');
      empty.className = 'messenger-status';
      empty.textContent = 'No members are available right now.';
      membersWrap.append(empty);
    } else if (!selectableCount) {
      const note = document.createElement('p');
      note.className = 'messenger-status';
      note.textContent = 'Members must unlock whispers before joining a group.';
      membersWrap.append(note);
    }

    form.append(membersWrap);

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

  async function deleteMessage(threadId, messageId) {
    if (!threadId || !messageId) {
      return;
    }
    try {
      const response = await fetch(`/chat/messages/${messageId}/delete`, {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'same-origin',
      });
      if (!response.ok) {
        const result = await response.json().catch(() => null);
        const error = (result && result.error) || 'Unable to remove that message.';
        if (messengerTray.classList.contains('is-open')) {
          setTrayNotice(error, 'danger', true);
        } else {
          window.alert(error);
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
    const container = document.createElement('div');
    container.className = 'chat-popover';
    container.dataset.chatWindow = String(threadId);
    container.innerHTML = `
      <header class="chat-popover-header">
        <span class="chat-popover-title">${label || 'Conversation'}</span>
        <button type="button" class="chat-popover-close" aria-label="Close">×</button>
      </header>
      <section class="chat-popover-body" data-popover-messages></section>
      <form class="chat-popover-compose" data-popover-form>
        <input type="hidden" name="thread_id" value="${threadId}">
        <textarea name="body" rows="2" placeholder="Type a message…" maxlength="${maxLength || 2000}" required></textarea>
        <button type="submit" class="btn btn-primary btn-compact">Send</button>
      </form>
    `;
    windowRail.append(container);
    requestAnimationFrame(() => container.classList.add('is-visible'));
    const info = {
      container,
      body: container.querySelector('[data-popover-messages]'),
      form: container.querySelector('[data-popover-form]'),
      messageIds: new Set(),
    };
    if (info.form && !(info.form.getAttribute('action') || '').trim()) {
      info.form.setAttribute('action', composeForm?.getAttribute('action') || '/chat/send');
    }
    if (info.form) {
      attachComposeShortcuts(info.form);
    }
    windowMap.set(threadId, info);
    return info;
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
    const submitButton = form.querySelector('button[type="submit"]');
    if (submitButton) {
      submitButton.disabled = true;
    }
    try {
      const formData = new FormData(form);
      const response = await fetch(form.getAttribute('action') || composeForm?.getAttribute('action') || '/chat/send', {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'same-origin',
        body: formData,
      });
      if (response.ok) {
        const result = await response.json().catch(() => null);
        if (result && result.ok) {
          form.reset();
        }
      } else if (response.status === 403) {
        window.location.reload();
      }
    } catch (err) {
      console.error('[chat] send failed', err);
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
