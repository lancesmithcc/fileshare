(() => {
  if (!document.body) {
    return;
  }
  let canvas = document.querySelector('[data-poly-canvas]');
  if (!canvas) {
    canvas = document.createElement('canvas');
    canvas.className = 'site-poly-canvas';
    canvas.dataset.polyCanvas = 'true';
    canvas.setAttribute('aria-hidden', 'true');
    document.body.prepend(canvas);
  }
  const ctx = canvas.getContext('2d');
  if (!ctx) {
    return;
  }

  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const NODE_COUNT = 42;
  const NEIGHBOR_COUNT = 3;
  let width = 0;
  let height = 0;
  let nodes = [];
  let animationId = 0;

  function createNode() {
    return {
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 0.35,
      vy: (Math.random() - 0.5) * 0.35,
      radius: 1.3 + Math.random() * 1.1,
    };
  }

  function initNodes() {
    nodes = Array.from({ length: NODE_COUNT }, createNode);
  }

  function resize() {
    const dpr = window.devicePixelRatio || 1;
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.scale(dpr, dpr);
    initNodes();
    renderFrame();
  }

  function stepNodes() {
    const drift = 0.002;
    nodes.forEach((node) => {
      node.vx += (Math.random() - 0.5) * drift;
      node.vy += (Math.random() - 0.5) * drift;
      node.x += node.vx;
      node.y += node.vy;

      if (node.x < -80) node.x = width + 80;
      else if (node.x > width + 80) node.x = -80;
      if (node.y < -80) node.y = height + 80;
      else if (node.y > height + 80) node.y = -80;

      node.vx = Math.max(Math.min(node.vx, 0.45), -0.45);
      node.vy = Math.max(Math.min(node.vy, 0.45), -0.45);
    });
  }

  function nearestIndexes(index, count) {
    const base = nodes[index];
    const distances = nodes
      .map((node, idx) => {
        if (idx === index) {
          return { idx, distance: Number.POSITIVE_INFINITY };
        }
        const dx = base.x - node.x;
        const dy = base.y - node.y;
        return { idx, distance: dx * dx + dy * dy };
      })
      .sort((a, b) => a.distance - b.distance);
    return distances.slice(0, count).map((item) => item.idx);
  }

  function drawTriangle(a, b, c) {
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.lineTo(c.x, c.y);
    ctx.closePath();
    const gradient = ctx.createLinearGradient(a.x, a.y, c.x, c.y);
    gradient.addColorStop(0, 'rgba(114, 213, 114, 0.05)');
    gradient.addColorStop(1, 'rgba(111, 194, 228, 0.08)');
    ctx.fillStyle = gradient;
    ctx.fill();
  }

  function renderTriangles() {
    const drawn = new Set();
    nodes.forEach((_, index) => {
      const neighbors = nearestIndexes(index, NEIGHBOR_COUNT);
      for (let i = 0; i < neighbors.length - 1; i += 1) {
        for (let j = i + 1; j < neighbors.length; j += 1) {
          const trio = [index, neighbors[i], neighbors[j]].sort((a, b) => a - b);
          const key = trio.join('-');
          if (drawn.has(key)) {
            continue;
          }
          drawn.add(key);
          drawTriangle(nodes[trio[0]], nodes[trio[1]], nodes[trio[2]]);
        }
      }
    });
  }

  function renderConnections() {
    ctx.lineWidth = 0.6;
    ctx.strokeStyle = 'rgba(114, 213, 114, 0.22)';
    nodes.forEach((node, index) => {
      nearestIndexes(index, 2).forEach((neighborIdx) => {
        const neighbor = nodes[neighborIdx];
        ctx.beginPath();
        ctx.moveTo(node.x, node.y);
        ctx.lineTo(neighbor.x, neighbor.y);
        ctx.stroke();
      });
    });
  }

  function renderNodes() {
    nodes.forEach((node) => {
      ctx.beginPath();
      ctx.arc(node.x, node.y, node.radius + 0.6, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(18, 28, 24, 0.38)';
      ctx.fill();

      ctx.beginPath();
      ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(114, 213, 114, 0.72)';
      ctx.fill();

      ctx.beginPath();
      ctx.arc(node.x, node.y, node.radius * 0.45, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(255, 255, 255, 0.85)';
      ctx.fill();
    });
  }

  function renderFrame() {
    ctx.clearRect(0, 0, width, height);
    renderTriangles();
    renderConnections();
    renderNodes();
  }

  function tick() {
    if (prefersReducedMotion.matches) {
      renderFrame();
      return;
    }
    stepNodes();
    renderFrame();
    animationId = window.requestAnimationFrame(tick);
  }

  function start() {
    if (animationId) {
      cancelAnimationFrame(animationId);
      animationId = 0;
    }
    if (prefersReducedMotion.matches) {
      renderFrame();
    } else {
      animationId = window.requestAnimationFrame(tick);
    }
  }

  resize();
  start();

  window.addEventListener('resize', () => {
    resize();
    start();
  });

  const handlePreferenceChange = () => {
    start();
  };
  if (typeof prefersReducedMotion.addEventListener === 'function') {
    prefersReducedMotion.addEventListener('change', handlePreferenceChange);
  } else if (typeof prefersReducedMotion.addListener === 'function') {
    prefersReducedMotion.addListener(handlePreferenceChange);
  }

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      if (animationId) {
        cancelAnimationFrame(animationId);
        animationId = 0;
      }
    } else if (!prefersReducedMotion.matches && !animationId) {
      animationId = window.requestAnimationFrame(tick);
    }
  });
})();
