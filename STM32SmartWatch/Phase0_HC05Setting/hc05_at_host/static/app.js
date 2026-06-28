let lastSeq = 0;
let connected = false;
let lineCount = 0;

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.message || response.statusText);
  }
  return data;
}

function setState(state) {
  connected = Boolean(state.connected);
  $("statusText").textContent = state.status || (connected ? "Connected" : "Disconnected");
  $("statusPill").classList.toggle("connected", connected);
  $("connectBtn").disabled = connected;
  $("disconnectBtn").disabled = !connected;
  $("sendBtn").disabled = !connected;
  document.querySelectorAll("[data-command]").forEach((button) => {
    button.disabled = !connected;
  });
}

function appendLog(entry) {
  const view = $("logView");
  const span = document.createElement("span");
  span.className = `log-${entry.source}`;

  const prefix = entry.source === "stm32" ? "" : `[${entry.source.toUpperCase()}] `;
  span.textContent = `${prefix}${entry.text}`;
  view.appendChild(span);
  view.scrollTop = view.scrollHeight;

  lineCount += entry.text.split("\n").filter(Boolean).length || 1;
  $("logMeta").textContent = `${lineCount} lines`;
}

async function refreshPorts() {
  try {
    const data = await api("/api/ports");
    const select = $("portSelect");
    const previous = select.value;
    select.innerHTML = "";

    data.ports.forEach((port) => {
      const option = document.createElement("option");
      option.value = port.device;
      option.textContent = port.label;
      select.appendChild(option);
    });

    if (previous) {
      select.value = previous;
    }

    $("portHint").textContent = data.ports.length
      ? `已发现 ${data.ports.length} 个串口`
      : "没有发现串口，确认 STM32 USB 已连接";
    setState(data.state);
  } catch (error) {
    $("portHint").textContent = error.message;
  }
}

async function connect() {
  const port = $("portSelect").value;
  try {
    const data = await api("/api/connect", {
      method: "POST",
      body: JSON.stringify({ port }),
    });
    setState(data.state);
  } catch (error) {
    alert(error.message);
  }
}

async function disconnect() {
  try {
    const data = await api("/api/disconnect", { method: "POST", body: "{}" });
    setState(data.state);
  } catch (error) {
    alert(error.message);
  }
}

async function sendLine(line) {
  try {
    const data = await api("/api/send", {
      method: "POST",
      body: JSON.stringify({ line }),
    });
    setState(data.state);
  } catch (error) {
    alert(error.message);
  }
}

async function sendCurrentCommand() {
  const input = $("commandInput");
  const line = input.value.trim();
  if (!line) {
    return;
  }
  await sendLine(line);
  input.select();
}

async function pollLogs() {
  try {
    const data = await api(`/api/logs?after=${lastSeq}`);
    data.logs.forEach((entry) => {
      lastSeq = Math.max(lastSeq, entry.seq);
      appendLog(entry);
    });
    setState(data.state);
  } catch (_error) {
  } finally {
    setTimeout(pollLogs, 180);
  }
}

async function clearLogs() {
  await api("/api/logs/clear", { method: "POST", body: "{}" });
  $("logView").textContent = "";
  lineCount = 0;
  $("logMeta").textContent = "0 lines";
}

function bindEvents() {
  $("refreshBtn").addEventListener("click", refreshPorts);
  $("connectBtn").addEventListener("click", connect);
  $("disconnectBtn").addEventListener("click", disconnect);
  $("sendBtn").addEventListener("click", sendCurrentCommand);
  $("clearBtn").addEventListener("click", clearLogs);
  $("commandInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      sendCurrentCommand();
    }
  });

  document.querySelectorAll("[data-command]").forEach((button) => {
    button.addEventListener("click", () => sendLine(button.dataset.command));
  });
}

bindEvents();
refreshPorts();
pollLogs();
