const chatForm = document.getElementById("chatForm");
const messageInput = document.getElementById("messageInput");
const chatMessages = document.getElementById("chatMessages");
const statusBanner = document.getElementById("statusBanner");
const sendButton = document.getElementById("sendButton");
const resetButton = document.getElementById("resetButton");

function addMessage(role, text, extraClass = "") {
  const article = document.createElement("article");
  article.className = `message ${role} ${extraClass}`.trim();

  const paragraph = document.createElement("p");
  paragraph.textContent = text;

  article.appendChild(paragraph);
  chatMessages.appendChild(article);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function setLoading(isLoading) {
  sendButton.disabled = isLoading;
  resetButton.disabled = isLoading;
  sendButton.textContent = isLoading ? "Thinking..." : "Send";
}

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const message = messageInput.value.trim();
  if (!message) {
    statusBanner.textContent = "Please describe what you're feeling so CareBuddy can respond.";
    return;
  }

  addMessage("user", message);
  messageInput.value = "";
  statusBanner.textContent = "CareBuddy is reviewing your message carefully.";
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
      statusBanner.textContent = "Urgent warning: please seek immediate real-world support.";
      return;
    }

    addMessage("assistant", data.reply);
    statusBanner.textContent = "CareBuddy replied with general guidance, not a diagnosis.";
  } catch (error) {
    addMessage(
      "assistant",
      error.message || "CareBuddy hit an unexpected problem. Please try again.",
      "emergency"
    );
    statusBanner.textContent =
      "An error occurred. If you feel worse or unsafe, contact a professional now.";
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
      "New chat started. Tell me what symptoms or feelings you’ve noticed and when they began."
    );
    statusBanner.textContent = "Conversation cleared. CareBuddy will ask follow-up questions first.";
  } catch (error) {
    statusBanner.textContent = "Could not reset the chat right now.";
  } finally {
    setLoading(false);
  }
});
