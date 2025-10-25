(() => {
  const LAMPORTS_PER_SOL = 1_000_000_000;

  const ready = () => {
    const root = document.querySelector("[data-neod-root]");
    if (!root || typeof window === "undefined") {
      return;
    }

    const detectProvider = () => {
      if (window.phantom && window.phantom.solana && window.phantom.solana.isPhantom) {
        return window.phantom.solana;
      }
      if (window.solana && (window.solana.isPhantom || window.solana.isSolflare)) {
        return window.solana;
      }
      if (window.solflare && window.solflare.isSolflare) {
        return window.solflare;
      }
      return null;
    };

    const provider = detectProvider();
    const connectButton = root.querySelector("[data-neod-connect]");
    const sendButton = root.querySelector("[data-neod-send]");
    const statusEl = root.querySelector("[data-neod-status]");
    const amountInput = root.querySelector("[data-neod-amount]");
    const quoteEl = root.querySelector("[data-neod-quote]");

    const treasury = root.dataset.treasury || "";
    const rpcUrl = root.dataset.rpcUrl || "https://api.mainnet-beta.solana.com";
    const fallbackRpc = root.dataset.defaultRpc || "https://api.mainnet-beta.solana.com";
    const proxyRpc = root.dataset.rpcProxy || "";
    const bufferSrc = root.dataset.bufferSrc || "";
    const blockhashUrl = root.dataset.blockhashUrl || "/api/v1/neod/blockhash";
    const minSol = Number.parseFloat(root.dataset.priceSol || "0");
    const minLamports = Number.parseInt(root.dataset.priceLamports || "0", 10);
    const tokensPerPurchase = Number.parseInt(root.dataset.tokensPerPurchase || "1", 10) || 1;
    const purchaseUrl = root.dataset.purchaseUrl || "/api/v1/neod/purchase";

    let web3Promise = null;
    let bufferPromise = null;
    const candidateRpcEndpoints = Array.from(
      new Set(
        [rpcUrl, proxyRpc, fallbackRpc, "https://api.mainnet-beta.solana.com"].filter(
          (value) => typeof value === "string" && value.length > 0
        )
      )
    );

    const setStatus = (message, tone = "muted") => {
      if (!statusEl) {
        return;
      }
      statusEl.textContent = message || "";
      if (tone) {
        statusEl.dataset.tone = tone;
      } else {
        delete statusEl.dataset.tone;
      }
    };

    const shortKey = (value) => {
      if (!value || typeof value !== "string") {
        return "";
      }
      return `${value.slice(0, 4)}…${value.slice(-4)}`;
    };

    const formatSol = (value) => {
      if (!Number.isFinite(value)) {
        return "0";
      }
      const fixed = value.toFixed(6);
      return Number.parseFloat(fixed).toString();
    };

    const toLamports = (amountSol) => {
      if (!Number.isFinite(amountSol)) {
        return 0;
      }
      return Math.round(amountSol * LAMPORTS_PER_SOL);
    };

    const hasBuffer = () =>
      typeof window !== "undefined" &&
      window.Buffer &&
      typeof window.Buffer.from === "function" &&
      typeof window.Buffer.alloc === "function" &&
      typeof window.Buffer.isBuffer === "function";

    const promoteBuffer = () => {
      if (typeof window === "undefined") {
        return false;
      }
      if (hasBuffer()) {
        return true;
      }
      if (window.buffer && window.buffer.Buffer) {
        window.Buffer = window.buffer.Buffer;
        return hasBuffer();
      }
      return false;
    };

    const loadScript = (src, marker) =>
      new Promise((resolve, reject) => {
        if (!src) {
          reject(new Error(`Missing ${marker || "script"} src`));
          return;
        }
        const selector = marker ? `script[data-${marker}]` : `script[src="${src}"]`;
        const existing = document.querySelector(selector);
        if (existing) {
          existing.addEventListener("load", resolve, { once: true });
          existing.addEventListener("error", () => reject(new Error(`${marker || "script"} failed to load`)), {
            once: true,
          });
          return;
        }
        const script = document.createElement("script");
        script.src = src;
        script.async = true;
        script.crossOrigin = "anonymous";
        if (marker) {
          script.dataset[marker] = "1";
        }
        script.onload = resolve;
        script.onerror = () => reject(new Error(`${marker || "script"} failed to load`));
        document.head.appendChild(script);
      });

    const ensureBuffer = () => {
      if (promoteBuffer()) {
        return Promise.resolve(window.Buffer);
      }
      if (typeof window === "undefined") {
        return Promise.resolve(null);
      }
      if (bufferPromise) {
        return bufferPromise;
      }
      bufferPromise = loadScript(bufferSrc, "bufferPolyfill")
        .then(() => {
          if (!promoteBuffer()) {
            throw new Error("Buffer polyfill loaded without Buffer global.");
          }
          return window.Buffer;
        })
        .catch((error) => {
          console.error("[NEOD] Buffer polyfill failed", error);
          bufferPromise = null;
          throw error;
        });
      return bufferPromise;
    };

    const fetchBlockhashViaBackend = async () => {
      if (!blockhashUrl) {
        return null;
      }
      try {
        const response = await fetch(blockhashUrl, {
          method: "GET",
          credentials: "same-origin",
          headers: {
            "Accept": "application/json",
          },
        });
        if (!response.ok) {
          const text = await response.text().catch(() => "");
          throw new Error(`Blockhash API ${response.status} ${text || response.statusText || ""}`.trim());
        }
        const payload = await response.json();
        if (payload && typeof payload.blockhash === "string" && payload.blockhash.length > 0) {
          return {
            blockhash: payload.blockhash,
            lastValidBlockHeight:
              typeof payload.last_valid_block_height === "number"
                ? payload.last_valid_block_height
                : null,
          };
        }
        const warning = payload?.error || "Unexpected response from blockhash API.";
        throw new Error(String(warning));
      } catch (error) {
        console.warn("[NEOD] Blockhash backend fetch failed", error);
        return null;
      }
    };

    const requestJsonRpc = async (endpoint, body) => {
      const payload = JSON.stringify(body);
      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "same-origin",
        body: payload,
      });
      if (!response.ok) {
        const text = await response.text().catch(() => "");
        throw new Error(`RPC ${response.status} ${text || response.statusText || ""}`.trim());
      }
      return response.json();
    };

    const fetchLatestBlockhash = async () => {
      const backendBlockhash = await fetchBlockhashViaBackend();
      if (backendBlockhash) {
        return backendBlockhash;
      }

      const primaryRequest = {
        jsonrpc: "2.0",
        id: "neod-blockhash",
        method: "getLatestBlockhash",
        params: [{ commitment: "confirmed" }],
      };
      for (const endpoint of candidateRpcEndpoints) {
        try {
          const result = await requestJsonRpc(endpoint, primaryRequest);
          const value = result?.result?.value || result?.result;
          const blockhash = value?.blockhash;
          if (typeof blockhash === "string" && blockhash.length > 0) {
            return {
              blockhash,
              lastValidBlockHeight:
                typeof value?.lastValidBlockHeight === "number"
                  ? value.lastValidBlockHeight
                  : null,
              endpoint,
            };
          }
          console.warn("[NEOD] Missing blockhash in getLatestBlockhash response", {
            endpoint,
            result,
          });
        } catch (error) {
          console.warn("[NEOD] getLatestBlockhash failed", endpoint, error);
        }
      }

      const fallbackRequest = {
        jsonrpc: "2.0",
        id: "neod-recent-blockhash",
        method: "getRecentBlockhash",
        params: [{ commitment: "confirmed" }],
      };
      for (const endpoint of candidateRpcEndpoints) {
        try {
          const result = await requestJsonRpc(endpoint, fallbackRequest);
          const value = result?.result?.value || result?.result;
          const blockhash = value?.blockhash;
          if (typeof blockhash === "string" && blockhash.length > 0) {
            return {
              blockhash,
              lastValidBlockHeight: null,
              endpoint,
            };
          }
          console.warn("[NEOD] Missing blockhash in getRecentBlockhash response", {
            endpoint,
            result,
          });
        } catch (error) {
          console.warn("[NEOD] getRecentBlockhash failed", endpoint, error);
        }
      }

      throw new Error("Unable to fetch a recent blockhash. Please try again shortly.");
    };

    const ensureWeb3 = () => {
      if (typeof window.solanaWeb3 === "object" && window.solanaWeb3.SystemProgram) {
        return Promise.resolve(window.solanaWeb3);
      }
      if (web3Promise) {
        return web3Promise;
      }
      const src = root.dataset.web3Src || "https://unpkg.com/@solana/web3.js@1.87.6/lib/index.iife.min.js";
      web3Promise = ensureBuffer()
        .then(() =>
          new Promise((resolve, reject) => {
            const script = document.createElement("script");
            script.src = src;
            script.async = true;
            script.crossOrigin = "anonymous";
            script.onload = () => {
              if (typeof window.solanaWeb3 === "object" && window.solanaWeb3.SystemProgram) {
                resolve(window.solanaWeb3);
              } else {
                reject(new Error("Solana web3 library initialised without expected exports."));
              }
            };
            script.onerror = () => reject(new Error("Unable to download the Solana web3 library."));
            document.head.appendChild(script);
          })
        )
        .catch((error) => {
          console.error("[NEOD] Failed to initialise Solana web3", error);
        web3Promise = null;
        throw error;
      });
      return web3Promise;
    };

    if (!treasury || !minLamports) {
      if (connectButton) {
        connectButton.disabled = true;
      }
      if (sendButton) {
        sendButton.disabled = true;
      }
      setStatus("Treasury configuration unavailable. Please check back soon.", "danger");
      return;
    }

    if (!provider) {
      if (connectButton) {
        connectButton.disabled = true;
        connectButton.textContent = "Install a Solana Wallet";
      }
      if (sendButton) {
        sendButton.disabled = true;
      }
      setStatus("No Solana wallet detected. Install Phantom or Solflare to continue.", "danger");
      return;
    }

    let publicKey = null;
    setStatus("Connect your wallet to begin the exchange.", "muted");

    const updateQuote = () => {
      if (!amountInput) {
        return;
      }
      const amountSol = Number.parseFloat(amountInput.value || "0");
      const lamports = toLamports(amountSol);
      const multiplier = minLamports > 0 ? Math.floor(lamports / minLamports) : 0;
      const tokens = Math.max(0, multiplier * tokensPerPurchase);

      if (quoteEl) {
        quoteEl.textContent = tokens.toString();
      }

      if (sendButton) {
        const displayAmount =
          Number.isFinite(amountSol) && amountSol > 0 ? amountSol : minSol;
        const buttonLabel = formatSol(displayAmount);
        sendButton.textContent = `Send ${buttonLabel} SOL`;
        sendButton.disabled = !publicKey || tokens <= 0;
      }
      return { amountSol, lamports, tokens };
    };

    const ensureConnected = async () => {
      if (publicKey) {
        return publicKey;
      }
      const response = await provider.connect();
      const key = response?.publicKey?.toString() || response?.toString();
      if (!key) {
        throw new Error("Wallet connection failed.");
      }
      publicKey = key;
      if (connectButton) {
        connectButton.textContent = `Connected: ${shortKey(key)}`;
        connectButton.disabled = true;
      }
      if (sendButton) {
        sendButton.disabled = true;
      }
      setStatus("Wallet connected. Choose an amount and proceed when ready.", "success");
      updateQuote();
      return publicKey;
    };

    const handleSend = async () => {
      if (!sendButton) {
        return;
      }
      try {
        const owner = await ensureConnected();
        const { amountSol, lamports, tokens } = updateQuote() || {};
        if (!Number.isFinite(amountSol) || lamports < minLamports) {
          throw new Error(`Minimum offering is ${formatSol(minSol)} SOL for 1 NEOD.`);
        }
        if (!lamports || !tokens) {
          throw new Error("Increase the SOL amount to receive at least one NEOD.");
        }
        
        sendButton.disabled = true;
        sendButton.dataset.loading = "1";
        setStatus(`Preparing ${formatSol(amountSol)} SOL transfer...`, "muted");
        
        // Ensure lamports is a safe integer
        const lamportsInt = Math.floor(lamports);
        
        // Load web3 library
        const web3 = await ensureWeb3();
        
        setStatus(`Fetching recent blockhash...`, "muted");

        const fromPubkey = new web3.PublicKey(owner);
        const toPubkey = new web3.PublicKey(treasury);

        const { blockhash, lastValidBlockHeight } = await fetchLatestBlockhash();
        setStatus(`Creating transaction...`, "muted");

        const transactionConfig = {
          recentBlockhash: blockhash,
          feePayer: fromPubkey,
        };
        const transaction = new web3.Transaction(transactionConfig);
        if (typeof lastValidBlockHeight === "number" && Number.isFinite(lastValidBlockHeight)) {
          transaction.lastValidBlockHeight = lastValidBlockHeight;
        }
        
        // Add transfer instruction using SystemProgram
        transaction.add(
          web3.SystemProgram.transfer({
            fromPubkey: fromPubkey,
            toPubkey: toPubkey,
            lamports: lamportsInt,
          })
        );

        setStatus(`Awaiting approval in Phantom...`, "muted");

        // Sign and send via Phantom
        const { signature } = await provider.signAndSendTransaction(transaction);
        setStatus(`Transaction sent: ${shortKey(signature)}. Confirming...`, "muted");

        // Wait for confirmation
        await new Promise(resolve => setTimeout(resolve, 3000));

        // Call our backend to verify and send NEOD
        const response = await fetch(purchaseUrl, {
          method: "POST",
          headers: { 
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest"
          },
          credentials: "same-origin",
          body: JSON.stringify({
            signature,
            recipient: owner,
          }),
        });
        
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
          const message = payload?.error || "Treasury could not deliver NEOD. Contact support with your signature: " + signature;
          throw new Error(message);
        }

        const tokenSig = payload.neod_transfer_signature;
        const minted = payload.tokens || tokens;
        setStatus(
          `Blessings received! ${minted} NEOD on the way. Token transfer ${shortKey(tokenSig)}.`,
          "success",
        );
      } catch (error) {
        console.error("[NEOD] Transaction initiation failed", error);
        const message =
          error && typeof error === "object" && "message" in error
            ? error.message
            : "Unable to complete the exchange. Please try again.";
        setStatus(String(message), "danger");
      } finally {
        if (sendButton) {
          delete sendButton.dataset.loading;
          sendButton.disabled = !publicKey || (updateQuote()?.tokens || 0) <= 0;
        }
      }
    };

    const handleConnect = async (event) => {
      event?.preventDefault();
      try {
        await ensureConnected();
      } catch (error) {
        const message =
          error && typeof error === "object" && "message" in error ? error.message : "Wallet connection failed.";
        setStatus(String(message), "danger");
      }
    };

    if (connectButton) {
      connectButton.addEventListener("click", handleConnect);
    }
    if (sendButton) {
      sendButton.addEventListener("click", (event) => {
        event.preventDefault();
        handleSend();
      });
    }
    if (amountInput) {
      amountInput.addEventListener("input", updateQuote);
      amountInput.addEventListener("change", updateQuote);
    }

    if (typeof provider.on === "function") {
      provider.on("accountChanged", (pubkey) => {
        publicKey = pubkey ? pubkey.toString() : null;
        if (!publicKey) {
          if (connectButton) {
            connectButton.textContent = "Connect Wallet";
            connectButton.disabled = false;
          }
          if (sendButton) {
            sendButton.disabled = true;
          }
          setStatus("Wallet disconnected.", "muted");
        } else {
          if (connectButton) {
            connectButton.textContent = `Connected: ${shortKey(publicKey)}`;
            connectButton.disabled = true;
          }
          setStatus("Wallet switched. Ready for the next exchange.", "success");
        }
        updateQuote();
      });
    }

    const alreadyConnected =
      (typeof provider.isConnected === "boolean" && provider.isConnected) ||
      (typeof provider.connected === "boolean" && provider.connected);

    if (alreadyConnected) {
      provider
        .connect({ onlyIfTrusted: true })
        .then(() => ensureConnected())
        .catch(() => {
          updateQuote();
        });
    } else {
      updateQuote();
    }
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", ready, { once: true });
  } else {
    ready();
  }
})();
