(() => {
  const ready = (fn) => {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn, { once: true });
    } else {
      fn();
    }
  };

  const GRID = {
    marginX: 40,
    marginY: 40,
    stepX: 140,
    stepY: 160,
    snap: 20,
  };

  ready(() => {
    const desktop = document.getElementById("desktop-surface");
    const dropzone = document.getElementById("hollow-dropzone");
    const uploadForm = document.getElementById("hollow-upload-form");
    const fileInput = uploadForm ? uploadForm.querySelector("input[type='file']") : null;
    const folderForm = document.getElementById("folder-create-form");
    const folderToggle = document.querySelector("[data-toggle-folder]");
    const pickerTriggers = Array.from(document.querySelectorAll("[data-open-picker]"));

    if (!desktop || !uploadForm || !fileInput) {
      return;
    }

    const icons = Array.from(desktop.querySelectorAll(".desktop-icon"));
    const state = {
      active: null,
      pointerId: null,
      offsetX: 0,
      offsetY: 0,
      startX: 0,
      startY: 0,
      dragging: false,
      desktopRect: desktop.getBoundingClientRect(),
      downIcon: null,
    };

    const selected = { current: null };

    const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
    const snap = (value) => Math.round(value / GRID.snap) * GRID.snap;

    const layoutIcon = (icon, x, y) => {
      icon.style.setProperty("--x", `${x}px`);
      icon.style.setProperty("--y", `${y}px`);
      icon.style.left = `${x}px`;
      icon.style.top = `${y}px`;
      icon.dataset.posX = String(x);
      icon.dataset.posY = String(y);
    };

    const getIconPosition = (icon) => ({
      x: parseFloat(icon.dataset.posX || "0") || 0,
      y: parseFloat(icon.dataset.posY || "0") || 0,
    });

    const nextGridPosition = (() => {
      let column = 0;
      let row = 0;
      return () => {
        const rect = desktop.getBoundingClientRect();
        const maxRows = Math.max(1, Math.floor((rect.height - GRID.marginY * 2) / GRID.stepY));
        const x = GRID.marginX + column * GRID.stepX;
        const y = GRID.marginY + row * GRID.stepY;
        row += 1;
        if (row >= maxRows) {
          row = 0;
          column += 1;
        }
        return { x, y };
      };
    })();

    const deselectAll = () => {
      if (selected.current) {
        selected.current.classList.remove("is-selected");
      }
      selected.current = null;
    };

    const selectIcon = (icon) => {
      if (selected.current === icon) {
        return;
      }
      deselectAll();
      icon.classList.add("is-selected");
      selected.current = icon;
    };

    const showRenameForm = (icon, form) => {
      form.classList.remove("hidden");
      selectIcon(icon);
      const input = form.querySelector("input[name='name']");
      requestAnimationFrame(() => {
        if (input) {
          input.focus();
          input.select();
        }
      });
    };

    const hideRenameForm = (icon, form) => {
      form.classList.add("hidden");
    };

    const persistPosition = (() => {
      const timers = new Map();
      return (icon, x, y) => {
        icon.dataset.posX = String(x);
        icon.dataset.posY = String(y);
        const payload = {
          type: icon.dataset.fileId ? "file" : "folder",
          id: icon.dataset.fileId || icon.dataset.folderId,
          x,
          y,
        };
        const existing = timers.get(icon);
        if (existing) {
          clearTimeout(existing);
        }
        const timeout = setTimeout(() => {
          timers.delete(icon);
          fetch("/files/position", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          }).catch(() => {});
        }, 120);
        timers.set(icon, timeout);
      };
    })();

    const moveFileToFolder = (icon, folderId) => {
      const form = icon.querySelector(".move-form");
      if (!form) {
        return;
      }
      const input = form.querySelector("input[name='folder_id']");
      if (input) {
        input.value = folderId || "";
      }
      form.submit();
    };

    const clearDropHighlights = () => {
      document.querySelectorAll(".folder-icon.is-drop-target, .crumb.is-drop-target").forEach((el) => el.classList.remove("is-drop-target"));
    };

    const supportsSaveFilePicker =
      typeof window.showSaveFilePicker === "function" && typeof window.isSecureContext === "boolean"
        ? window.isSecureContext
        : typeof window.showSaveFilePicker === "function";

    const downloadIcon = async (icon) => {
      const url = icon.dataset.downloadUrl;
      if (!url) {
        return;
      }
      if (icon.dataset.downloading === "1") {
        return;
      }
      icon.dataset.downloading = "1";
      const label = icon.querySelector("[data-label]");
      const fallback = () => {
        window.location.href = url;
      };

      try {
        if (!supportsSaveFilePicker) {
          fallback();
          return;
        }
        const response = await fetch(url, { credentials: "include" });
        if (!response.ok || !response.body) {
          throw new Error(`Download failed with status ${response.status}`);
        }
        const suggestedName = (label?.textContent || "").trim() || (icon.dataset.ext ? `download.${icon.dataset.ext.toLowerCase()}` : "download");
        const pickerHandle = await window.showSaveFilePicker({ suggestedName });
        const writable = await pickerHandle.createWritable();
        const reader = response.body.getReader();
        try {
          // Stream the file to the selected destination to avoid loading large files in memory.
          while (true) {
            const { value, done } = await reader.read();
            if (done) {
              break;
            }
            if (value) {
              await writable.write(value);
            }
          }
        } finally {
          await writable.close();
        }
      } catch (error) {
        if (!(error instanceof DOMException && (error.name === "AbortError" || error.name === "NotAllowedError"))) {
          fallback();
        }
      } finally {
        delete icon.dataset.downloading;
      }
    };

    const detectDropTarget = (clientX, clientY, dragged) => {
      const elements = document.elementsFromPoint(clientX, clientY);
      if (dragged.dataset.fileId) {
        const folderEl = elements.find((el) => el instanceof HTMLElement && el.closest(".folder-icon"));
        if (folderEl instanceof HTMLElement) {
          const folderIcon = folderEl.closest(".folder-icon");
          if (folderIcon && folderIcon !== dragged && folderIcon.dataset.folderId) {
            return { type: "folder", id: folderIcon.dataset.folderId };
          }
        }
        const crumbEl = elements.find((el) => el instanceof HTMLElement && el.closest(".crumb[data-folder-target]"));
        if (crumbEl instanceof HTMLElement) {
          const crumb = crumbEl.closest(".crumb[data-folder-target]");
          if (crumb) {
            return { type: "crumb", id: crumb.dataset.folderTarget || "" };
          }
        }
      }
      return { type: "desktop" };
    };

    const updateDropHighlights = (clientX, clientY, dragged) => {
      clearDropHighlights();
      if (!dragged || !dragged.dataset.fileId) {
        return;
      }
      const elements = document.elementsFromPoint(clientX, clientY);
      const folderEl = elements.find((el) => el instanceof HTMLElement && el.closest(".folder-icon"));
      if (folderEl instanceof HTMLElement) {
        folderEl.closest(".folder-icon")?.classList.add("is-drop-target");
      }
      const crumbEl = elements.find((el) => el instanceof HTMLElement && el.closest(".crumb[data-folder-target]"));
      if (crumbEl instanceof HTMLElement) {
        crumbEl.closest(".crumb")?.classList.add("is-drop-target");
      }
    };

    const beginDrag = (icon, event) => {
    state.active = icon;
    state.pointerId = typeof event.pointerId === "number" ? event.pointerId : null;
    state.dragging = false;
    state.desktopRect = desktop.getBoundingClientRect();
      const { x, y } = getIconPosition(icon);
      state.startX = x;
      state.startY = y;
      state.offsetX = event.clientX;
      state.offsetY = event.clientY;
    };

    const registerRenameForm = (form) => {
      if (form.dataset.bound === "1") {
        return;
      }
      form.dataset.bound = "1";
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        const icon = form.closest(".desktop-icon");
        const input = form.querySelector("input[name='name']");
        if (!icon || !input) {
          return;
        }
        const newName = input.value.trim();
        if (!newName) {
          return;
        }
        fetch(form.action, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: newName }),
        })
          .then((response) => response.json())
          .then((data) => {
            if (data?.status === "ok") {
              const label = icon.querySelector("[data-label]");
              if (label) {
                label.textContent = newName;
              }
              hideRenameForm(icon, form);
            } else if (data?.message) {
              alert(data.message);
            }
          })
          .catch(() => form.submit());
      });
    };

    const contextMenu = document.getElementById("desktop-context-menu");
    const contextState = { icon: null };
    const menuItems = {};

    if (contextMenu) {
      contextMenu.querySelectorAll("[data-context-action]").forEach((button) => {
        menuItems[button.dataset.contextAction] = button;
      });
    }

    const hideContextMenu = () => {
      if (!contextMenu) {
        return;
      }
      contextMenu.classList.add("hidden");
      contextMenu.setAttribute("aria-hidden", "true");
      contextMenu.style.left = "-9999px";
      contextMenu.style.top = "-9999px";
      contextState.icon = null;
    };

    const updateContextMenuItems = (icon) => {
      if (!contextMenu) {
        return;
      }
      const isFolder = Boolean(icon.dataset.folderId);
      const hasDownload = Boolean(icon.dataset.downloadUrl);
      const shareState =
        icon.dataset.shareState || (icon.dataset.fileId ? "disabled" : "none");
      const hasShareUrl = Boolean(icon.dataset.shareUrl);

      if (menuItems.open) {
        menuItems.open.hidden = !isFolder;
      }
      if (menuItems.download) {
        menuItems.download.hidden = !hasDownload;
      }
      if (menuItems.rename) {
        menuItems.rename.hidden = false;
      }
      if (menuItems.shareCopy) {
        menuItems.shareCopy.hidden = shareState !== "enabled" || !hasShareUrl;
      }
      if (menuItems.shareEnable) {
        const form = icon.querySelector("[data-share-enable-form]");
        menuItems.shareEnable.hidden =
          shareState !== "disabled" || !form || !icon.dataset.fileId;
      }
      if (menuItems.shareRotate) {
        const form = icon.querySelector("[data-share-rotate-form]");
        menuItems.shareRotate.hidden =
          shareState !== "enabled" || !form || !icon.dataset.fileId;
      }
      if (menuItems.shareDisable) {
        const form = icon.querySelector("[data-share-disable-form]");
        menuItems.shareDisable.hidden =
          shareState !== "enabled" || !form || !icon.dataset.fileId;
      }
      if (menuItems.delete) {
        menuItems.delete.hidden = !icon.querySelector("[data-delete-form]");
      }
    };

    const showContextMenu = (event, icon) => {
      if (!contextMenu) {
        return;
      }
      event.preventDefault();
      hideContextMenu();
      selectIcon(icon);
      updateContextMenuItems(icon);
      contextState.icon = icon;
      contextMenu.classList.remove("hidden");
      contextMenu.setAttribute("aria-hidden", "false");
      contextMenu.style.left = "-9999px";
      contextMenu.style.top = "-9999px";
      requestAnimationFrame(() => {
        const rect = contextMenu.getBoundingClientRect();
        const margin = 12;
        const maxX = Math.max(margin, window.innerWidth - rect.width - margin);
        const maxY = Math.max(margin, window.innerHeight - rect.height - margin);
        const x = clamp(event.clientX, margin, maxX);
        const y = clamp(event.clientY, margin, maxY);
        contextMenu.style.left = `${x}px`;
        contextMenu.style.top = `${y}px`;
      });
    };

    if (contextMenu) {
      desktop.addEventListener("contextmenu", (event) => {
        if (!(event.target instanceof HTMLElement)) {
          return;
        }
        const icon = event.target.closest(".desktop-icon");
        if (!icon) {
          hideContextMenu();
          return;
        }
        showContextMenu(event, icon);
      });
    }

    const handleContextAction = (action, icon) => {
      switch (action) {
        case "open":
          if (icon.dataset.openUrl) {
            window.location.href = icon.dataset.openUrl;
          }
          break;
        case "download":
          downloadIcon(icon);
          break;
        case "rename": {
          const form = icon.querySelector(
            icon.dataset.fileId ? "[data-file-rename]" : "[data-folder-rename]",
          );
          if (form) {
            showRenameForm(icon, form);
          }
          break;
        }
        case "share-copy":
          if (icon.dataset.shareUrl) {
            const url = icon.dataset.shareUrl;
            if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
              navigator.clipboard.writeText(url).catch(() => {
                window.prompt("Copy link", url);
              });
            } else {
              window.prompt("Copy link", url);
            }
          }
          break;
        case "share-enable": {
          const form = icon.querySelector("[data-share-enable-form]");
          if (form) {
            form.submit();
          }
          break;
        }
        case "share-rotate": {
          const form = icon.querySelector("[data-share-rotate-form]");
          if (form) {
            form.submit();
          }
          break;
        }
        case "share-disable": {
          const form = icon.querySelector("[data-share-disable-form]");
          if (form) {
            form.submit();
          }
          break;
        }
        case "delete": {
          const form = icon.querySelector("[data-delete-form]");
          if (form) {
            form.submit();
          }
          break;
        }
        default:
          break;
      }
    };

    const registerIcon = (icon) => {
      const form = icon.querySelector(".rename-form");
      if (form) {
        registerRenameForm(form);
      }
      const label = icon.querySelector(".icon-label");
      if (label && !label.dataset.bound) {
        label.dataset.bound = "1";
        label.addEventListener("click", (event) => {
          if (state.dragging) {
            return;
          }
          event.preventDefault();
          event.stopPropagation();
          hideContextMenu();
          const renameForm = icon.querySelector(icon.dataset.fileId ? "[data-file-rename]" : "[data-folder-rename]");
          if (renameForm) {
            showRenameForm(icon, renameForm);
          }
        });
      }
      const hit = icon.querySelector(".icon-hit");
      if (hit && !hit.dataset.bound) {
        hit.dataset.bound = "1";
        hit.addEventListener("click", (event) => event.preventDefault());
        hit.addEventListener("dblclick", (event) => {
          event.preventDefault();
          openIcon(icon);
        });
      }
      if (!icon.dataset.boundDbl) {
        icon.dataset.boundDbl = "1";
        icon.addEventListener("dblclick", (event) => {
          event.preventDefault();
          event.stopPropagation();
          openIcon(icon);
        });
      }
    };

    if (contextMenu) {
      contextMenu.addEventListener("click", (event) => {
        const button = event.target.closest("button[data-context-action]");
        if (!button) {
          return;
        }
        event.preventDefault();
        if (contextState.icon) {
          handleContextAction(button.dataset.contextAction, contextState.icon);
        }
        hideContextMenu();
      });
    }

    document.addEventListener(
      "click",
      (event) => {
        if (!contextMenu || contextMenu.classList.contains("hidden")) {
          return;
        }
        if (event.target instanceof HTMLElement && event.target.closest(".desktop-context-menu")) {
          return;
        }
        hideContextMenu();
      },
      { capture: true },
    );

    window.addEventListener("blur", hideContextMenu);
    window.addEventListener("resize", hideContextMenu);
    document.addEventListener("scroll", hideContextMenu, true);
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        hideContextMenu();
      }
    });

    icons.forEach((icon) => {
      const { x, y } = getIconPosition(icon);
      if (x === 0 && y === 0) {
        const pos = nextGridPosition();
        layoutIcon(icon, pos.x, pos.y);
      } else {
        layoutIcon(icon, x, y);
      }
      registerIcon(icon);
    });

    desktop.addEventListener("pointerdown", (event) => {
      if (!(event.target instanceof HTMLElement)) {
        hideContextMenu();
        return;
      }
      if (event.target.closest(".desktop-context-menu")) {
        return;
      }
      hideContextMenu();
      const icon = event.target.closest(".desktop-icon");
      if (!icon) {
        deselectAll();
        return;
      }
      const interactingWithUi = event.target.closest(".rename-form, form, button, input, textarea");
      if (interactingWithUi) {
        state.downIcon = null;
        selectIcon(icon);
        return;
      }
      const labelHit = event.target.closest(".icon-label");
      if (labelHit) {
        state.downIcon = null;
        selectIcon(icon);
        return;
      }
      if (event.button === 2) {
        state.downIcon = null;
        selectIcon(icon);
        return;
      }
      if (event.button !== 0) {
        state.downIcon = null;
        return;
      }
      selectIcon(icon);
      state.downIcon = icon;
      beginDrag(icon, event);
    });

    const openIcon = (icon) => {
      if (icon.dataset.folderId && icon.dataset.openUrl) {
        window.location.href = icon.dataset.openUrl;
      } else if (icon.dataset.downloadUrl) {
        downloadIcon(icon);
      }
    };

    const handlePointerMove = (event) => {
      if (!state.active) {
        return;
      }
      if (state.pointerId !== null && event.pointerId !== undefined && state.pointerId !== event.pointerId) {
        return;
      }
      const dx = event.clientX - state.offsetX;
      const dy = event.clientY - state.offsetY;
      if (!state.dragging && Math.hypot(dx, dy) > 4) {
        state.dragging = true;
        state.downIcon = null;
        if (typeof state.active.setPointerCapture === "function" && state.pointerId !== null) {
          try {
            state.active.setPointerCapture(state.pointerId);
          } catch (error) {
            // ignore pointer capture failures
          }
        }
        state.active.classList.add("is-dragging");
      }
      if (!state.dragging) {
        return;
      }
      event.preventDefault();
      const width = state.active.offsetWidth;
      const height = state.active.offsetHeight;
      const x = clamp(state.startX + dx, 12, state.desktopRect.width - width - 12);
      const y = clamp(state.startY + dy, 12, state.desktopRect.height - height - 12);
      layoutIcon(state.active, x, y);
      updateDropHighlights(event.clientX, event.clientY, state.active);
    };

    window.addEventListener("pointermove", handlePointerMove, { passive: false });

    const handlePointerUp = (event) => {
      if (!state.active) {
        return;
      }
      if (state.pointerId !== null && event.pointerId !== undefined && state.pointerId !== event.pointerId) {
        return;
      }
      const icon = state.active;
      if (typeof icon.releasePointerCapture === "function" && state.pointerId !== null) {
        try {
          icon.releasePointerCapture(state.pointerId);
        } catch (error) {
          // ignore pointer capture release failures
        }
      }
      icon.classList.remove("is-dragging");
      const wasDragging = state.dragging;
      state.active = null;
      state.pointerId = null;

      if (!wasDragging) {
        state.dragging = false;
        state.downIcon = null;
        return;
      }

      const desktopRect = desktop.getBoundingClientRect();
      const currentX = clamp(parseFloat(icon.dataset.posX || "0"), 12, desktopRect.width - icon.offsetWidth - 12);
      const currentY = clamp(parseFloat(icon.dataset.posY || "0"), 12, desktopRect.height - icon.offsetHeight - 12);
      const snappedX = clamp(snap(currentX), 12, desktopRect.width - icon.offsetWidth - 12);
      const snappedY = clamp(snap(currentY), 12, desktopRect.height - icon.offsetHeight - 12);

      const dropTarget = detectDropTarget(event.clientX, event.clientY, icon);
      clearDropHighlights();

      if (dropTarget.type === "folder" && icon.dataset.fileId) {
        moveFileToFolder(icon, dropTarget.id);
        state.dragging = false;
        return;
      }

      if (dropTarget.type === "crumb" && icon.dataset.fileId) {
        moveFileToFolder(icon, dropTarget.id);
        state.dragging = false;
        return;
      }

      layoutIcon(icon, snappedX, snappedY);
      persistPosition(icon, snappedX, snappedY);
      state.dragging = false;
      state.downIcon = null;
    };

    window.addEventListener("pointerup", handlePointerUp);
    window.addEventListener("pointercancel", handlePointerUp);

    desktop.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) {
        return;
      }
      if (!target.closest(".desktop-icon")) {
        deselectAll();
        hideContextMenu();
      }
      const cancel = target.closest("[data-cancel-rename]");
      if (cancel) {
        event.preventDefault();
        const form = cancel.closest(".rename-form");
        const icon = cancel.closest(".desktop-icon");
        if (icon && form) {
          hideRenameForm(icon, form);
        }
      }
    });

    if (pickerTriggers.length && fileInput) {
      const openPicker = (event) => {
        event.preventDefault();
        fileInput.click();
      };
      pickerTriggers.forEach((trigger) => {
        trigger.addEventListener("click", openPicker);
        trigger.addEventListener("keydown", (event) => {
          if (event.key === "Enter" || event.key === " ") {
            openPicker(event);
          }
        });
      });
    }

    const generateFolderName = () => {
      const names = new Set(
        Array.from(desktop.querySelectorAll(".folder-icon [data-label]")).map((el) => el.textContent?.trim().toLowerCase()).filter(Boolean),
      );
      const base = "New Folder";
      if (!names.has(base.toLowerCase())) {
        return base;
      }
      let counter = 2;
      let candidate = `${base} ${counter}`;
      while (names.has(candidate.toLowerCase())) {
        counter += 1;
        candidate = `${base} ${counter}`;
      }
      return candidate;
    };

    const addFolderIcon = (folder) => {
      const article = document.createElement("article");
      article.className = "desktop-icon folder-icon";
      article.dataset.folderId = String(folder.id);
      article.dataset.openUrl = `${window.location.pathname}?folder=${folder.id}`;
      article.dataset.posX = String(folder.pos_x || 0);
      article.dataset.posY = String(folder.pos_y || 0);
      article.innerHTML = `
        <a class="icon-hit" href="${article.dataset.openUrl}" draggable="false"></a>
        <div class="icon-visual folder-visual" aria-hidden="true">
          <span class="folder-tab"></span>
          <span class="folder-body"></span>
        </div>
        <div class="icon-label" data-label>${folder.name}</div>
        <form method="post" action="/files/folders/${folder.id}/rename" class="rename-form hidden" data-folder-rename="${folder.id}">
          <input type="hidden" name="current_folder_id" value="${desktop.dataset.folderId || ''}">
          <label class="sr-only" for="rename-folder-${folder.id}">Rename ${folder.name}</label>
          <input id="rename-folder-${folder.id}" type="text" name="name" value="${folder.name}" maxlength="120" required>
          <div class="rename-actions">
            <button type="submit" class="pill pill-accent">Save</button>
            <button type="button" class="pill pill-ghost" data-cancel-rename>Cancel</button>
          </div>
        </form>
        <form method="post" action="/files/folders/${folder.id}/delete" class="icon-hidden-form" data-delete-form="folder">
          <input type="hidden" name="current_folder_id" value="${desktop.dataset.folderId || ''}">
        </form>
      `;
      desktop.append(article);
      icons.push(article);
      const pos = folder.pos_x || folder.pos_y ? { x: folder.pos_x, y: folder.pos_y } : nextGridPosition();
      layoutIcon(article, pos.x, pos.y);
      persistPosition(article, pos.x, pos.y);
      registerIcon(article);
    };

    const createFolder = (name) => {
      if (!folderForm) {
        return;
      }
      fetch(folderForm.action, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      })
        .then((response) => response.json())
        .then((data) => {
          if (data?.status !== "ok" || !data.folder) {
            folderForm.submit();
            return;
          }
          addFolderIcon(data.folder);
        })
        .catch(() => folderForm.submit());
    };


    if (folderToggle) {
      folderToggle.addEventListener("click", (event) => {
        event.preventDefault();
        const name = generateFolderName();
        const input = folderForm?.querySelector("input[name='name']");
        if (input) {
          input.value = name;
        }
        createFolder(name);
      });
    }

    const isFileDrag = (event) => {
      if (!event.dataTransfer) {
        return false;
      }
      const types = Array.from(event.dataTransfer.types || []);
      if (
        types.some((type) =>
          ["Files", "public.file-url", "application/x-moz-file", "text/uri-list"].includes(type)
        )
      ) {
        return true;
      }
      const items = event.dataTransfer.items ? Array.from(event.dataTransfer.items) : [];
      return items.some((item) => item.kind === "file");
    };

    const handleExternalDrag = (event) => {
      if (!isFileDrag(event)) {
        return;
      }
      event.preventDefault();
      dropzone?.classList.add("is-dragging");
    };

    const clearExternalDrag = () => {
      dropzone?.classList.remove("is-dragging");
    };

    ["dragenter", "dragover"].forEach((type) => desktop.addEventListener(type, handleExternalDrag));
    ["dragleave", "drop"].forEach((type) => desktop.addEventListener(type, clearExternalDrag));

    ["dragenter", "dragover"].forEach((type) =>
      window.addEventListener(
        type,
        (event) => {
          if (!isFileDrag(event)) {
            return;
          }
          event.preventDefault();
          dropzone?.classList.add("is-dragging");
        },
        { passive: false },
      ),
    );

    ["dragleave", "drop"].forEach((type) =>
      window.addEventListener(
        type,
        (event) => {
          if (!isFileDrag(event)) {
            return;
          }
          event.preventDefault();
          if (type === "drop") {
            dropzone?.classList.remove("is-dragging");
          } else if (!event.relatedTarget || !(event.relatedTarget instanceof HTMLElement)) {
            dropzone?.classList.remove("is-dragging");
          }
        },
        { passive: false },
      ),
    );

    const uploadFiles = (files) => {
      if (!files.length) {
        return;
      }
      const formData = new FormData(uploadForm);
      formData.delete("file");
      formData.append("file", files[0]);
      fetch(uploadForm.action, {
        method: "POST",
        body: formData,
      })
        .then(() => window.location.reload())
        .catch(() => uploadForm.submit());
    };

    desktop.addEventListener("drop", (event) => {
      if (event.dataTransfer && event.dataTransfer.files.length) {
        event.preventDefault();
        uploadFiles(event.dataTransfer.files);
      }
    });

    fileInput.addEventListener("change", () => {
      if (fileInput.files && fileInput.files.length) {
        uploadFiles(fileInput.files);
      }
    });

    window.addEventListener(
      "drop",
      (event) => {
        if (!isFileDrag(event)) {
          return;
        }
        event.preventDefault();
        const targetEl = event.target instanceof HTMLElement ? event.target : null;
        if (targetEl && targetEl.closest("#desktop-surface")) {
          return;
        }
        uploadFiles(event.dataTransfer.files);
      },
      { passive: false },
    );
  });
})();
