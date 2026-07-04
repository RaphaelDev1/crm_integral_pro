/* ==============================================================================
 *  WIDGET CHATBOT IA CONSEIL — script autonome, sans dépendance, à intégrer
 *  sur n'importe quel site :
 *
 *  <script src="https://votre-api/widget/chatbot_widget.js" data-api-url="https://votre-api"></script>
 * ============================================================================== */
(function () {
  "use strict";

  var scriptTag = document.currentScript;
  var API_URL = (scriptTag && scriptTag.getAttribute("data-api-url")) || "";
  if (!API_URL) {
    console.error("[IA Conseil Chatbot] data-api-url manquant sur la balise <script>.");
    return;
  }

  var STORAGE_KEY = "ia_conseil_chatbot_session_id";
  var sessionId = localStorage.getItem(STORAGE_KEY);
  if (!sessionId) {
    sessionId = (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random());
    localStorage.setItem(STORAGE_KEY, sessionId);
  }

  var css = "" +
    "#iac-bubble{position:fixed;bottom:20px;right:20px;width:60px;height:60px;border-radius:50%;" +
    "background:#1a56db;color:#fff;border:none;box-shadow:0 4px 12px rgba(0,0,0,.2);cursor:pointer;" +
    "font-size:26px;z-index:999999;}" +
    "#iac-window{position:fixed;bottom:92px;right:20px;width:340px;max-width:92vw;height:460px;" +
    "max-height:75vh;background:#fff;border-radius:12px;box-shadow:0 8px 30px rgba(0,0,0,.25);" +
    "display:none;flex-direction:column;overflow:hidden;font-family:system-ui,sans-serif;z-index:999999;}" +
    "#iac-window.iac-open{display:flex;}" +
    "#iac-header{background:#1a56db;color:#fff;padding:12px 14px;font-weight:600;font-size:14px;}" +
    "#iac-messages{flex:1;overflow-y:auto;padding:12px;font-size:14px;line-height:1.4;}" +
    ".iac-msg{margin-bottom:10px;max-width:85%;padding:8px 11px;border-radius:10px;white-space:pre-wrap;}" +
    ".iac-msg-bot{background:#f0f2f5;color:#111;border-top-left-radius:2px;}" +
    ".iac-msg-user{background:#1a56db;color:#fff;margin-left:auto;border-top-right-radius:2px;}" +
    "#iac-form{display:flex;border-top:1px solid #eee;}" +
    "#iac-input{flex:1;border:none;padding:10px;font-size:14px;outline:none;}" +
    "#iac-send{border:none;background:#1a56db;color:#fff;padding:0 16px;cursor:pointer;font-size:14px;}" +
    "#iac-send:disabled{opacity:.5;cursor:default;}";
  var styleTag = document.createElement("style");
  styleTag.textContent = css;
  document.head.appendChild(styleTag);

  var bubble = document.createElement("button");
  bubble.id = "iac-bubble";
  bubble.setAttribute("aria-label", "Ouvrir le chat");
  bubble.textContent = "💬";

  var win = document.createElement("div");
  win.id = "iac-window";
  win.innerHTML =
    '<div id="iac-header">IA Conseil — Diagnostic express</div>' +
    '<div id="iac-messages"></div>' +
    '<form id="iac-form">' +
    '  <input id="iac-input" type="text" placeholder="Écrivez votre message…" autocomplete="off" />' +
    '  <button id="iac-send" type="submit">Envoyer</button>' +
    "</form>";

  document.body.appendChild(bubble);
  document.body.appendChild(win);

  var messagesEl = win.querySelector("#iac-messages");
  var formEl = win.querySelector("#iac-form");
  var inputEl = win.querySelector("#iac-input");
  var sendEl = win.querySelector("#iac-send");
  var termine = false;
  var premiereOuverture = true;

  function ajouterMessage(texte, role) {
    var div = document.createElement("div");
    div.className = "iac-msg " + (role === "user" ? "iac-msg-user" : "iac-msg-bot");
    div.textContent = texte;
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  bubble.addEventListener("click", function () {
    win.classList.toggle("iac-open");
    if (win.classList.contains("iac-open") && premiereOuverture) {
      premiereOuverture = false;
      ajouterMessage(
        "Bonjour ! Je peux vous aider à estimer vos économies possibles sur vos factures " +
        "Télécom, Énergie ou Abonnements. Sur quel sujet souhaitez-vous qu'on regarde en priorité ?",
        "bot"
      );
    }
  });

  formEl.addEventListener("submit", function (evt) {
    evt.preventDefault();
    var texte = inputEl.value.trim();
    if (!texte || termine) return;
    ajouterMessage(texte, "user");
    inputEl.value = "";
    inputEl.disabled = true;
    sendEl.disabled = true;

    fetch(API_URL + "/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message: texte }),
    })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        ajouterMessage(data.reply || "Désolé, une erreur est survenue.", "bot");
        if (data.termine) {
          termine = true;
          inputEl.placeholder = "Un conseiller va vous recontacter très prochainement.";
        }
      })
      .catch(function () {
        ajouterMessage("Impossible de contacter le service pour le moment. Merci de réessayer.", "bot");
      })
      .finally(function () {
        inputEl.disabled = termine;
        sendEl.disabled = termine;
        if (!termine) inputEl.focus();
      });
  });
})();
