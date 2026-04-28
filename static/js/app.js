const chatForm = document.getElementById("chatForm");
const messageInput = document.getElementById("messageInput");
const chatMessages = document.getElementById("chatMessages");
const statusBanner = document.getElementById("statusBanner");
const sendButton = document.getElementById("sendButton");
const resetButton = document.getElementById("resetButton");
const urgentPanel = document.getElementById("urgentPanel");
const moodForm = document.getElementById("moodForm");
const moodSelect = document.getElementById("moodSelect");
const stressRange = document.getElementById("stressRange");
const energyRange = document.getElementById("energyRange");
const sleepSelect = document.getElementById("sleepSelect");
const moodNote = document.getElementById("moodNote");
const moodSummary = document.getElementById("moodSummary");
const useMoodInChatButton = document.getElementById("useMoodInChat");
const moodChips = document.querySelectorAll(".mood-chip");
const historyTrack = document.getElementById("historyTrack");
const todayMoodHeading = document.getElementById("todayMoodHeading");
const todayMoodTime = document.getElementById("todayMoodTime");
const todayStressValue = document.getElementById("todayStressValue");
const todayEnergyValue = document.getElementById("todayEnergyValue");
const todaySleepValue = document.getElementById("todaySleepValue");

const MOOD_STORAGE_KEY = "carebuddy-mood-check";
const MOOD_HISTORY_STORAGE_KEY = "carebuddy-mood-history";

function addMessage(role, text, extraClass = "") {
  const article = document.createElement("article");
  article.className = `message ${role} ${extraClass}`.trim();

  const paragraph = document.createElement("p");
  paragraph.textContent = text;

  article.appendChild(paragraph);
  chatMessages.appendChild(article);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function setStatus(message, type = "default") {
  statusBanner.textContent = message;
  statusBanner.classList.remove("urgent", "error");

  if (type === "urgent") {
    statusBanner.classList.add("urgent");
  }

  if (type === "error") {
    statusBanner.classList.add("error");
  }
}

function showUrgentPanel(visible) {
  urgentPanel.classList.toggle("hidden", !visible);
  document.body.classList.toggle("emergency-active", visible);
}

function setLoading(isLoading) {
  sendButton.disabled = isLoading;
  resetButton.disabled = isLoading;
  sendButton.textContent = isLoading ? "Thinking..." : "Send";
}

function buildMoodSummary(data) {
  const notePart = data.note ? ` Note: ${data.note}` : "";
  return `Mood: ${data.mood}. Stress: ${data.stress}/10. Energy: ${data.energy}/10. Sleep: ${data.sleep}.${notePart}`;
}

function updateMoodChips(value) {
  moodChips.forEach((chip) => {
    chip.classList.toggle("is-active", chip.dataset.mood === value);
  });
}

function formatMoodHeading(mood) {
  return mood.charAt(0).toUpperCase() + mood.slice(1);
}

function formatTimestamp(timestamp) {
  return new Date(timestamp).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function renderMoodHistory(history) {
  if (!history.length) {
    historyTrack.innerHTML =
      '<div class="history-empty">Your recent mood check-ins will appear here.</div>';
    return;
  }

  historyTrack.innerHTML = history
    .map(
      (entry) => `
        <article class="history-card mood-${entry.mood}">
          <p class="history-day">${formatTimestamp(entry.timestamp)}</p>
          <strong>${formatMoodHeading(entry.mood)}</strong>
          <span>Stress ${entry.stress}/10</span>
          <span>Energy ${entry.energy}/10</span>
        </article>
      `
    )
    .join("");
}

function updateTodayCard(data) {
  if (!data) {
    todayMoodHeading.textContent = "No check-in saved yet";
    todayMoodTime.textContent = "Stored only in this browser";
    todayStressValue.textContent = "-";
    todayEnergyValue.textContent = "-";
    todaySleepValue.textContent = "-";
    return;
  }

  todayMoodHeading.textContent = `${formatMoodHeading(data.mood)} check-in saved`;
  todayMoodTime.textContent = formatTimestamp(data.timestamp);
  todayStressValue.textContent = `${data.stress}/10`;
  todayEnergyValue.textContent = `${data.energy}/10`;
  todaySleepValue.textContent = formatMoodHeading(data.sleep);
}

function loadMoodCheck() {
  const saved = localStorage.getItem(MOOD_STORAGE_KEY);
  const history = JSON.parse(localStorage.getItem(MOOD_HISTORY_STORAGE_KEY) || "[]");

  renderMoodHistory(history);

  if (!saved) {
    moodSummary.textContent = "No check-in saved yet for this browser session.";
    updateMoodChips(moodSelect.value);
    updateTodayCard(null);
    return;
  }

  const data = JSON.parse(saved);
  moodSelect.value = data.mood;
  stressRange.value = data.stress;
  energyRange.value = data.energy;
  sleepSelect.value = data.sleep;
  moodNote.value = data.note;
  moodSummary.textContent = buildMoodSummary(data);
  updateMoodChips(data.mood);
  updateTodayCard(data);
}

function saveMoodCheck() {
  const data = {
    mood: moodSelect.value,
    stress: stressRange.value,
    energy: energyRange.value,
    sleep: sleepSelect.value,
    note: moodNote.value.trim(),
    timestamp: new Date().toISOString(),
  };

  localStorage.setItem(MOOD_STORAGE_KEY, JSON.stringify(data));

  const history = JSON.parse(localStorage.getItem(MOOD_HISTORY_STORAGE_KEY) || "[]");
  history.unshift(data);
  localStorage.setItem(MOOD_HISTORY_STORAGE_KEY, JSON.stringify(history.slice(0, 7)));

  moodSummary.textContent = buildMoodSummary(data);
  updateTodayCard(data);
  renderMoodHistory(history.slice(0, 7));
  updateMoodChips(data.mood);
  setStatus("Mood check-in saved in this browser only.", "default");
}

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const message = messageInput.value.trim();
  if (!message) {
    setStatus("Please describe what you're feeling so CareBuddy can respond.");
    return;
  }

  addMessage("user", message);
  messageInput.value = "";
  setStatus("CareBuddy is deciding whether a brief follow-up question is needed.");
  showUrgentPanel(false);
  setLoading(true);

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ message }),
    });

    const data = await response.json();

    if (!response.ok) {
      const details = data.details ? `\n\nDetails: ${data.details}` : "";
      throw new Error((data.error || "Something went wrong.") + details);
    }

    if (data.isEmergency) {
      addMessage("assistant", data.reply, "emergency");
      setStatus("Urgent warning: seek immediate real-world support now.", "urgent");
      showUrgentPanel(true);
      return;
    }

    addMessage("assistant", data.reply);
    setStatus("CareBuddy replied with general guidance, not a diagnosis.");
  } catch (error) {
    addMessage(
      "assistant",
      error.message || "CareBuddy hit an unexpected problem. Please try again.",
      "emergency"
    );
    setStatus(
      "An error occurred. If you feel worse or unsafe, contact a professional now.",
      "error"
    );
  } finally {
    setLoading(false);
  }
});

resetButton.addEventListener("click", async () => {
  setLoading(true);

  try {
    await fetch("/api/reset", { method: "POST" });
    chatMessages.innerHTML = "";
    addMessage(
      "assistant",
      "New chat started. Tell me what is going on and what kind of help you need right now."
    );
    setStatus("Conversation cleared. CareBuddy will ask brief questions only when needed.");
    showUrgentPanel(false);
  } catch (error) {
    setStatus("Could not reset the chat right now.", "error");
  } finally {
    setLoading(false);
  }
});

moodForm.addEventListener("submit", (event) => {
  event.preventDefault();
  saveMoodCheck();
});

moodChips.forEach((chip) => {
  chip.addEventListener("click", () => {
    moodSelect.value = chip.dataset.mood;
    updateMoodChips(chip.dataset.mood);
  });
});

useMoodInChatButton.addEventListener("click", () => {
  const saved = localStorage.getItem(MOOD_STORAGE_KEY);
  if (!saved) {
    setStatus("Save a mood check-in first, then you can send it into the chat.", "default");
    return;
  }

  const data = JSON.parse(saved);
  messageInput.value = `Mood check-in: ${buildMoodSummary(data)} Please use this as extra context while giving me practical guidance and keeping follow-up questions brief.`;
  messageInput.focus();
  setStatus("Your mood check-in was added to the chat box.", "default");
});

loadMoodCheck();
