const statusText = document.querySelector("#server-status");
const checkButton = document.querySelector("#check-status");

async function checkStatus() {
  checkButton.disabled = true;
  statusText.textContent = "Verbindung wird geprüft …";
  statusText.dataset.state = "loading";

  try {
    const response = await fetch(checkButton.dataset.url, { cache: "no-store" });
    if (!response.ok) {
      throw new Error("Statusprüfung fehlgeschlagen");
    }

    const data = await response.json();
    if (data.status !== "ok" || data.database !== "ok") {
      throw new Error("Dienst ist nicht bereit");
    }

    statusText.textContent = "Server und Datenbank sind erreichbar.";
    statusText.dataset.state = "success";
  } catch (error) {
    statusText.textContent = "Die Verbindung konnte nicht hergestellt werden.";
    statusText.dataset.state = "error";
  } finally {
    checkButton.disabled = false;
  }
}

checkButton.addEventListener("click", checkStatus);
checkStatus();
