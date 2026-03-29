# How to use: MCP Server Connections in AOS

Diese Anleitung beschreibt die Model Context Protocol (MCP) Verbindungen, die in der `mcp_config.json` eingerichtet sind. Jede Verbindung verleiht deinem KI-Agenten spezielle, neue Fähigkeiten.

AOS unterstützt **zwei Editoren**, die beide dieselbe MCP-Konfiguration nutzen:

| Editor | Zweck | KI-Backend |
|---|---|---|
| **VS Codium + Continue.dev** | Primärer Editor für Kunden | LM Studio (lokal, privat) |
| **Antigravity (VS Code)** | Setup & Entwicklung | Google Gemini (Cloud) |

---

## 1. Google Workspace (google-workspace)
Richtet eine sichere und nahtlose Verbindung zu deinen Google-Diensten ein.
- **Funktionsweise:** Der Server nutzt `npx google-workspace-mcp serve`, um auf deine Google Drive-Dateien, Docs und E-Mails zuzugreifen (falls durch OAuth autorisiert).
- **Möglichkeiten:** 
  - Du kannst den Agenten bitten: "Durchsuche mein Google Drive nach Projektplänen aus 2025."
  - "Lies das verlinkte Google Doc und fasse es zusammen."
  - Erstellen von direkten Berichten basierend auf deinen Cloud-Inhalten.
- **Hinweis:** Benötigt Google-Account-Authentifizierung.

## 2. NotebookLM (notebooklm)
Verbindet sich direkt mit deinem Google NotebookLM-Konto.
- **Funktionsweise:** Nutzt das Kommandozeilen-Tool `notebooklm-mcp-cli`. NotebookLM verknüpft Dokumente, Audio und Videos mithilfe von Gemini 1.5 Pro für extrem fundierte Antworten.
- **Möglichkeiten:** 
  - Du kannst sagen: "Nutze das NotebookLM-Tool und durchsuche mein Notizbuch 'Prompt Agent engineering'."
  - Automatisches Erstellen von Struktur-Analysen, Präsentationen oder Berichten auf Basis tausender Seiten an Notizen.
  - Generieren von FAQ-Listen, Mindmaps oder Podcasts direkt aus deinen hochgeladenen Quellen in NotebookLM.
- **Hinweis:** Benötigt Google-Account-Authentifizierung (`nlm login`).

## 3. LM Studio (lm-studio)
Ermöglicht dem Agenten, auf lokal gehostete, private Open-Source-Sprachmodelle (wie Llama 3 oder Qwen) zuzugreifen.
- **Funktionsweise:** Ein Python-Skript (`lm_studio_mcp.py`), das lokal über `uv` ausgeführt wird und als Brücke zum LM Studio-Server (Port 1234) fungiert. Das Skript liegt unter `~/.config/aos/lm_studio_mcp.py`.
- **Möglichkeiten:** 
  - **100% Datenschutz:** Sende sensible Codeschnipsel oder Daten, die die Cloud nicht sehen darf, gezielt an dein lokales Modell: "Frag LM Studio, was dieser Code macht."
  - **Hybride Intelligenz:** Der schnelle Cloud-Agent plant die Aufgaben, delegiert aber rechenintensive oder private Code-Generations-Schritte an dein lokales, kostenloses Modell in LM Studio.

---

## 4. Continue.dev (VS Codium)
Continue.dev ist die KI-Coding-Erweiterung für VS Codium und bietet:
- **Chat-Sidebar:** Direkte Konversation mit deinem lokalen LM Studio Modell
- **Tab-Autocomplete:** Intelligente Code-Vervollständigung über LM Studio
- **Inline-Edit:** Code direkt im Editor bearbeiten lassen

### Konfiguration
Die Continue.dev-Konfiguration liegt unter `~/.continue/config.json` und zeigt automatisch auf LM Studio (`localhost:1234`). Es wird kein Cloud-Account benötigt.

---

## Konfigurationsdateien

| Datei | Pfad | Zweck |
|---|---|---|
| MCP Config (Antigravity) | `~/.gemini/settings.json` | MCP-Server für Antigravity |
| MCP Config (VS Codium) | `~/.config/VSCodium/User/mcp.json` | MCP-Server für VS Codium |
| Continue.dev Config | `~/.continue/config.json` | AI-Coding über LM Studio |
| LM Studio Bridge | `~/.config/aos/lm_studio_mcp.py` | MCP-Brücke zu LM Studio |

---

### Wichtiger Hinweis zur Nutzung:
Nach der Installation stelle sicher, dass du das Fenster deiner IDE einmal neu lädst (Reload Window), damit die MCP-Konfiguration frisch eingelesen wird. LM Studio muss im Hintergrund laufen und der "Local Server" auf `ON` stehen (Port 1234), damit die Verbindung funktioniert.
