chrome.runtime.onMessage.addListener((message) => {
  if (message.type === "APPLY") {
    fetch("http://localhost:8000/applications/trigger", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: message.url }),
    });
  }
});
