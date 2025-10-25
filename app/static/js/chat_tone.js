(() => {
  const AudioContext = window.AudioContext || window.webkitAudioContext;
  if (!AudioContext) {
    return;
  }

  let ctx;
  let oscillators = [];
  let envelopeGain;
  let fadeTimer = null;

  function ensureContext() {
    if (!ctx) {
      ctx = new AudioContext();
      envelopeGain = ctx.createGain();
      envelopeGain.gain.value = 0;
      envelopeGain.connect(ctx.destination);
    }
  }

  function stopTone() {
    if (!ctx || !envelopeGain) {
      return;
    }
    if (fadeTimer) {
      clearTimeout(fadeTimer);
      fadeTimer = null;
    }
    envelopeGain.gain.cancelScheduledValues(ctx.currentTime);
    envelopeGain.gain.setTargetAtTime(0, ctx.currentTime, 0.4);
    oscillators.forEach((osc) => {
      osc.stop(ctx.currentTime + 0.5);
    });
    oscillators = [];
  }

  function playTone() {
    ensureContext();
    if (!ctx) {
      return;
    }
    if (oscillators.length) {
      stopTone();
    }

    const freqs = [132, 134.5, 137];
    freqs.forEach((freq, index) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.value = freq + (Math.random() * 1.5 - 0.75);
      gain.gain.value = index === 0 ? 0.6 : index === 1 ? 0.25 : 0.15;
      osc.connect(gain).connect(envelopeGain);
      osc.start();
      oscillators.push(osc);
    });

    envelopeGain.gain.cancelScheduledValues(ctx.currentTime);
    envelopeGain.gain.setTargetAtTime(0.15, ctx.currentTime + 0.05, 0.5);

    fadeTimer = setTimeout(() => {
      stopTone();
    }, 3200);
  }

  window.__chatTone = {
    play: () => {
      ensureContext();
      if (!ctx) {
        return;
      }
      if (ctx.state === 'suspended') {
        ctx
          .resume()
          .then(playTone)
          .catch(() => {});
      } else {
        playTone();
      }
    },
    stop: stopTone,
  };

  function primeContext() {
    ensureContext();
    if (ctx && ctx.state === 'suspended') {
      ctx.resume().catch(() => {});
    }
  }

  window.addEventListener(
    'pointerdown',
    () => {
      primeContext();
    },
    { once: true, passive: true },
  );
  window.addEventListener(
    'keydown',
    () => {
      primeContext();
    },
    { once: true },
  );
})();
