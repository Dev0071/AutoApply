document.getElementById("apply-btn").addEventListener("click", async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  chrome.runtime.sendMessage({ type: "APPLY", url: tab.url });
  document.getElementById("status").textContent = "Queued...";
});
