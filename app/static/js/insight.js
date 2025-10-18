document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("insight-form");
  const output = document.getElementById("insight-output");
  const submitBtn = form?.querySelector("button[type='submit']");
  const promptField = form?.querySelector("textarea[name='prompt']");

  if (!form || !output || !submitBtn || !promptField) {
    return;
  }

  let typingTimer;

  const setButtonState = (state) => {
    submitBtn.dataset.state = state;
    if (state === "loading") {
      submitBtn.disabled = true;
      submitBtn.classList.add("is-loading");
    } else {
      submitBtn.disabled = false;
      submitBtn.classList.remove("is-loading");
    }
  };

  const typeInsight = (text) => {
    clearTimeout(typingTimer);
    output.textContent = "";

    const reduceMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;
    const shouldAnimate = !reduceMotion && text.length <= 240;

    if (!shouldAnimate) {
      output.textContent = text;
      return;
    }

    let index = 0;
    const chunkSize = text.length > 120 ? 3 : 2;

    const tick = () => {
      if (index >= text.length) {
        return;
      }

      output.textContent += text.slice(index, index + chunkSize);
      index += chunkSize;
      typingTimer = setTimeout(tick, 6);
    };

    tick();
  };

  const showMessage = (message) => {
    clearTimeout(typingTimer);
    output.textContent = message;
  };

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(form);
    const prompt = String(formData.get("prompt") || "").trim();
    if (!prompt) {
      promptField.focus();
      return;
    }

    output.classList.remove("hidden");
    showMessage("Consulting the archdruid...");
    setButtonState("loading");

    const controller = new AbortController();
    const abortTimer = setTimeout(() => {
      controller.abort();
    }, 70000);

    let slowNoticeTimer = setTimeout(() => {
      showMessage(
        "This is taking longer than usual, but I'm still listening. Stay with me while I sift through the grove's whispers..."
      );
    }, 12000);

    try {
      const response = await fetch("/ai/insight", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        signal: controller.signal,
        body: JSON.stringify({ prompt }),
      });

      const payload = await response.json();
      if (!response.ok || !payload?.insight) {
        throw new Error(payload?.error || "Unknown error");
      }

      clearTimeout(slowNoticeTimer);
      typeInsight(payload.insight);
    } catch (error) {
      console.error(error);
      if (error.name === "AbortError") {
        showMessage("Archdruid Eldara is still drawing breath. Give me another nudge if the grove stays quiet.");
      } else {
        showMessage(
          "The spirits are quiet at the moment. Ensure the local model is configured and reachable."
        );
      }
    } finally {
      clearTimeout(abortTimer);
      clearTimeout(slowNoticeTimer);
      setButtonState("idle");
    }
  });
});
