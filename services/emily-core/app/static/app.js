const form = document.querySelector("#chat-form");
const input = document.querySelector("#message-input");
const sendButton = document.querySelector("#send-button");
const messages = document.querySelector("#messages");
const loading = document.querySelector("#loading");
const errorBox = document.querySelector("#error");
const clearButton = document.querySelector("#clear-button");
const refreshButton = document.querySelector("#refresh-status");
const statusDot = document.querySelector("#status-dot");
const statusText = document.querySelector("#status-text");
const refreshDevicesButton = document.querySelector("#refresh-devices");
const devicesStatus = document.querySelector("#devices-status");
const devicesMode = document.querySelector("#devices-mode");
const entityCount = document.querySelector("#entity-count");
const deviceSearch = document.querySelector("#device-search");
const domainCounts = document.querySelector("#domain-counts");
const deviceList = document.querySelector("#device-list");
const refreshMusicButton = document.querySelector("#refresh-music");
const musicStatus = document.querySelector("#music-status");
const musicMode = document.querySelector("#music-mode");
const musicCount = document.querySelector("#music-count");
const musicList = document.querySelector("#music-list");
let entitySearchTimer;

function showError(message) {
  errorBox.textContent = message;
  errorBox.hidden = false;
}

function clearError() {
  errorBox.hidden = true;
  errorBox.textContent = "";
}

function addMessage(author, text, tool) {
  const article = document.createElement("article");
  article.className = `message ${author === "Emily" ? "assistant" : "user"}`;

  const label = document.createElement("span");
  label.className = "message-label";
  label.textContent = author;

  const paragraph = document.createElement("p");
  paragraph.textContent = text;

  article.append(label, paragraph);
  if (tool) {
    const indicator = document.createElement("small");
    indicator.className = "tool-indicator";
    indicator.textContent = `${tool.startsWith("music_") || tool === "play_music" || tool === "list_music_players" ? "Music Assistant" : "Home Assistant"} • ${tool}`;
    article.append(indicator);
  }
  messages.append(article);
  messages.scrollTop = messages.scrollHeight;
}

async function loadMusic() {
  refreshMusicButton.disabled = true;
  musicStatus.textContent = "Loading Music Assistant status…";
  try {
    const [statusResponse, playersResponse, coreResponse] = await Promise.all([
      fetch("/api/music/status", {headers: {Accept: "application/json"}}),
      fetch("/api/music/players", {headers: {Accept: "application/json"}}),
      fetch("/api/status", {headers: {Accept: "application/json"}}),
    ]);
    const status = await statusResponse.json();
    const playerData = playersResponse.ok ? await playersResponse.json() : {players: []};
    const core = coreResponse.ok ? await coreResponse.json() : {};
    musicCount.textContent = `(${playerData.count || 0})`;
    musicStatus.textContent = status.connected ? status.message : status.message || "Music Assistant is unavailable.";
    musicMode.textContent = `Mode: ${status.mode === "mock" ? "Mock" : status.configured ? "Authenticated" : "Not configured"} • Control: ${core.music_assistant_control_enabled ? "enabled" : "disabled"}${core.music_default_player ? ` • Default: ${core.music_default_player}` : ""}`;
    musicList.replaceChildren();
    playerData.players.forEach((player) => {
      const item = document.createElement("li");
      const name = document.createElement("strong");
      name.textContent = player.name;
      const detail = document.createElement("span");
      detail.textContent = `${player.available ? player.state : "unavailable"} • ${player.volume_percent}%${player.current_item ? ` • ${player.current_item}${player.current_artist ? ` — ${player.current_artist}` : ""}` : ""}`;
      item.append(name, detail);
      musicList.append(item);
    });
  } catch (_error) {
    musicStatus.textContent = "Music Assistant status is unavailable.";
  } finally {
    refreshMusicButton.disabled = false;
  }
}

function renderDevices(data) {
  entityCount.textContent = `(${data.count})`;
  devicesStatus.textContent = data.count ? "Available supported entities" : "No supported entities found.";
  domainCounts.replaceChildren();
  Object.entries(data.supported_counts || {}).forEach(([domain, count]) => {
    const chip = document.createElement("span");
    chip.textContent = `${domain}: ${count}`;
    domainCounts.append(chip);
  });
  deviceList.replaceChildren();
  data.entities.forEach((entity) => {
    const item = document.createElement("li");
    const name = document.createElement("strong");
    name.textContent = entity.friendly_name;
    const detail = document.createElement("span");
    detail.textContent = `${entity.entity_id} • ${entity.domain} • ${entity.state}`;
    item.append(name, detail);
    deviceList.append(item);
  });
}

async function loadDevices(refresh = false) {
  refreshDevicesButton.disabled = true;
  devicesStatus.textContent = "Loading device list…";
  try {
    const search = deviceSearch.value.trim();
    const query = search ? `?search=${encodeURIComponent(search)}` : "";
    const response = await fetch(refresh ? "/api/entities/refresh" : `/api/entities${query}`, {
      method: refresh ? "POST" : "GET",
      headers: {Accept: "application/json"},
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Could not load devices.");
    renderDevices(data);
  } catch (error) {
    entityCount.textContent = "—";
    domainCounts.replaceChildren();
    deviceList.replaceChildren();
    devicesStatus.textContent = error.message || "Home Assistant devices are unavailable.";
  } finally {
    refreshDevicesButton.disabled = false;
  }
}

async function refreshStatus() {
  statusDot.className = "status-dot pending";
  statusText.textContent = "Checking status";
  try {
    const response = await fetch("/api/status", {headers: {Accept: "application/json"}});
    if (!response.ok) throw new Error("Status request failed");
    const data = await response.json();
    statusDot.className = "status-dot online";
    statusText.textContent = data.home_assistant.connected
      ? data.home_assistant_mock ? "Core + Home Assistant mock" : "Core + Home Assistant online"
      : "Core online";
    refreshButton.title = data.home_assistant.message;
    devicesMode.textContent = `Home Assistant: ${data.home_assistant_mock ? "Mock mode" : data.home_assistant.connected ? "Authenticated" : data.home_assistant.message} • Control: ${data.home_assistant_control_enabled ? "enabled" : "disabled"}`;
  } catch (_error) {
    statusDot.className = "status-dot offline";
    statusText.textContent = "Core unavailable";
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message) return;

  clearError();
  addMessage("You", message);
  input.value = "";
  input.disabled = true;
  sendButton.disabled = true;
  loading.hidden = false;

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: {"Content-Type": "application/json", Accept: "application/json"},
      body: JSON.stringify({message}),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(response.status === 422 ? "Please enter a shorter, valid message." : "Emily could not process that message.");
    }
    addMessage("Emily", data.reply, data.tool);
    if (data.tool) { loadDevices(); loadMusic(); }
  } catch (error) {
    showError(error.message || "Could not reach Emily Core. Check the server connection and try again.");
  } finally {
    input.disabled = false;
    sendButton.disabled = false;
    loading.hidden = true;
    input.focus();
  }
});

clearButton.addEventListener("click", () => {
  messages.replaceChildren();
  clearError();
  addMessage("Emily", "Conversation cleared. How can I help?");
});

refreshButton.addEventListener("click", refreshStatus);
refreshDevicesButton.addEventListener("click", () => loadDevices(true));
refreshMusicButton.addEventListener("click", loadMusic);
deviceSearch.addEventListener("input", () => {
  clearTimeout(entitySearchTimer);
  entitySearchTimer = setTimeout(() => loadDevices(), 250);
});
refreshStatus();
loadDevices();
loadMusic();
