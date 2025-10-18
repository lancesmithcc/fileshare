(() => {
  const init = () => {
    const field = document.getElementById("hex-field");
    if (!field) {
      return;
    }

    const reduceMotionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (reduceMotionQuery.matches) {
      return;
    }

    const HEX_WIDTH = 72;
    const HEX_HEIGHT = Math.sqrt(3) * (HEX_WIDTH / 2);
    const HORIZ_STEP = HEX_WIDTH * 0.75;
    const VERT_STEP = HEX_HEIGHT * 0.88;
    const ROW_OFFSET = HEX_WIDTH / 2;

    let cells = [];
    const cellLookup = new Map();

    const buildGrid = () => {
      const fragment = document.createDocumentFragment();
      cells = [];
      cellLookup.clear();
      field.textContent = "";

      const cols = Math.ceil((window.innerWidth + HEX_WIDTH) / HORIZ_STEP) + 4;
      const rows = Math.ceil((window.innerHeight + HEX_HEIGHT) / VERT_STEP) + 4;

      for (let row = -2; row < rows; row += 1) {
        const offsetX = (row & 1) ? ROW_OFFSET : 0;
        for (let col = -2; col < cols; col += 1) {
          const x = col * HORIZ_STEP + offsetX;
          const y = row * VERT_STEP;
          const hex = document.createElement("span");
          hex.className = "hex-cell";
          hex.style.setProperty("--tx", `${x}px`);
          hex.style.setProperty("--ty", `${y}px`);
          hex.style.setProperty("--drift-x", `${(Math.random() - 0.5) * 22}px`);
          hex.style.setProperty("--drift-y", `${(Math.random() - 0.5) * 22}px`);
          hex.style.setProperty("--drift-delay", `${(Math.random() * 18).toFixed(2)}s`);
          hex.dataset.col = String(col);
          hex.dataset.row = String(row);
          fragment.appendChild(hex);

          const cell = {
            element: hex,
            col,
            row,
            cx: x + HEX_WIDTH / 2,
            cy: y + HEX_HEIGHT / 2,
            timeoutId: null,
          };
          cells.push(cell);
          cellLookup.set(`${col}:${row}`, cell);
        }
      }

      field.appendChild(fragment);
    };

    const neighborOffsetsEven = [
      [1, 0],
      [0, 1],
      [-1, 1],
      [-1, 0],
      [-1, -1],
      [0, -1],
    ];

    const neighborOffsetsOdd = [
      [1, 0],
      [1, 1],
      [0, 1],
      [-1, 0],
      [0, -1],
      [1, -1],
    ];

    const activateCell = (cell, delay = 0) => {
      if (!cell) {
        return;
      }
      window.setTimeout(() => {
        cell.element.classList.add("is-active");
        if (cell.timeoutId) {
          window.clearTimeout(cell.timeoutId);
        }
        cell.timeoutId = window.setTimeout(() => {
          cell.element.classList.remove("is-active");
          cell.timeoutId = null;
        }, 460);
      }, delay);
    };

    let lastKey = null;
    let rafId = null;
    let pendingEvent = null;

    const processPointer = (event) => {
      rafId = null;
      pendingEvent = null;
      const rect = field.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;

      let nearest = null;
      let nearestDistance = Infinity;

      for (const cell of cells) {
        const dx = x - cell.cx;
        const dy = y - cell.cy;
        const candidate = dx * dx + dy * dy;
        if (candidate < nearestDistance) {
          nearestDistance = candidate;
          nearest = cell;
        }
      }

      if (!nearest) {
        return;
      }

      const key = `${nearest.col}:${nearest.row}`;
      if (key === lastKey) {
        return;
      }
      lastKey = key;

      activateCell(nearest, 0);

      const parity = (nearest.row & 1) === 0 ? 0 : 1;
      const offsets = parity === 0 ? neighborOffsetsEven : neighborOffsetsOdd;

      offsets.forEach(([dc, dr], index) => {
        const neighbor = cellLookup.get(`${nearest.col + dc}:${nearest.row + dr}`);
        if (neighbor) {
          activateCell(neighbor, (index + 1) * 70);
        }
      });
    };

    const pointerMoveHandler = (event) => {
      if (event.pointerType && event.pointerType !== "mouse" && event.pointerType !== "pen") {
        return;
      }
      pendingEvent = event;
      if (rafId) {
        return;
      }
      rafId = window.requestAnimationFrame(() => {
        if (pendingEvent) {
          processPointer(pendingEvent);
        }
      });
    };

    const pointerLeaveHandler = (event) => {
      if (!event.relatedTarget && !event.toElement) {
        lastKey = null;
      }
    };

    let resizeTimeout = null;
    const resizeHandler = () => {
      if (resizeTimeout) {
        window.clearTimeout(resizeTimeout);
      }
      resizeTimeout = window.setTimeout(() => {
        buildGrid();
      }, 180);
    };

    buildGrid();

    document.addEventListener("pointermove", pointerMoveHandler, { passive: true });
    window.addEventListener("mouseout", pointerLeaveHandler);
    window.addEventListener("resize", resizeHandler);
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();
