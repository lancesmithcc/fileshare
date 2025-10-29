(() => {
  const ready = (fn) => {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn, { once: true });
    } else {
      fn();
    }
  };

  ready(() => {
    const nav = document.querySelector(".nav");
    const toggle = nav?.querySelector("[data-nav-toggle]");
    const links = nav?.querySelector("[data-nav-links]");
    const overlay = nav?.querySelector("[data-nav-overlay]");
    const icon = toggle?.querySelector("[data-nav-icon]");
    const OPEN_ICON = "&#9776;";
    const CLOSE_ICON = "&#10005;";

    if (!nav || !toggle || !links) {
      return;
    }

    const syncAria = () => {
      const isOpen = links.classList.contains("is-open");
      links.setAttribute("aria-hidden", isOpen ? "false" : "true");
    };

    const setOpenState = (isOpen) => {
      links.classList.toggle("is-open", isOpen);
      toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
      toggle.classList.toggle("is-active", isOpen);
      document.body.classList.toggle("nav-is-open", isOpen);
      if (overlay) {
        overlay.classList.toggle("is-visible", isOpen);
        overlay.setAttribute("aria-hidden", isOpen ? "false" : "true");
      }
      if (icon) {
        icon.innerHTML = isOpen ? CLOSE_ICON : OPEN_ICON;
      }
      syncAria();
      links.style.pointerEvents = isOpen ? "auto" : "";
    };

    const closeMenu = () => setOpenState(false);

    if (icon) {
      icon.innerHTML = OPEN_ICON;
    }
    syncAria();

    const handleToggle = (event) => {
      event.preventDefault();
      const willOpen = !links.classList.contains("is-open");
      setOpenState(willOpen);
      if (willOpen) {
        const firstFocusable = links.querySelector("a, button, [tabindex]:not([tabindex='-1'])");
        firstFocusable?.focus();
      } else {
        toggle.focus();
      }
    };

    toggle.addEventListener("click", handleToggle);

    overlay?.addEventListener("click", closeMenu);

    links.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof Element)) {
        return;
      }
      if (links.classList.contains("is-open") && (target.closest("a") || target.closest("button"))) {
        closeMenu();
      }
    });

    document.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof Element)) {
        return;
      }
      if (!links.classList.contains("is-open")) {
        return;
      }
      if (!nav.contains(target)) {
        closeMenu();
      }
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && links.classList.contains("is-open")) {
        closeMenu();
        toggle.focus();
      }
    });

    window.addEventListener(
      "resize",
      () => {
        // Menu always uses hamburger toggle on all screen sizes
        syncAria();
      },
      { passive: true }
    );
  });
})();
