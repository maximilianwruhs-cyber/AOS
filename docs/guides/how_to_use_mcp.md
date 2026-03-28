# How to use: MCP Server Connections in AntiGravity

Diese Anleitung beschreibt die drei Model Context Protocol (MCP) Verbindungen, die in der `mcp_config.json` eingerichtet sind. Jede Verbindung verleiht deinem KI-Agenten (wie AntiGravity) spezielle, neue Fähigkeiten.

---

## 1. Google Workspace (google-workspace)
Richtet eine sichere und nahtlose Verbindung zu deinen Google-Diensten ein.
- **Funktionsweise:** Der Server nutzt `npx google-workspace-mcp serve`, um auf deine Google Drive-Dateien, Docs und E-Mails zuzugreifen (falls durch OAuth autorisiert).
- **Möglichkeiten:** 
  - Du kannst den Agenten bitten: "Durchsuche mein Google Drive nach Projektplänen aus 2025."
  - "Lies das verlinkte Google Doc und fasse es zusammen."
  - Erstellen von direkten Berichten basierend auf deinen Cloud-Inhalten.

## 2. NotebookLM (notebooklm)
Verbindet sich direkt mit deinem Google NotebookLM-Konto.
- **Funktionsweise:** Nutzt das Kommandozeilen-Tool `notebooklm-mcp-cli`. NotebookLM verknüpft Dokumente, Audio und Videos mithilfe von Gemini 1.5 Pro für extrem fundierte Antworten.
- **Möglichkeiten:** 
  - Du kannst sagen: "Nutze das NotebookLM-Tool und durchsuche mein Notizbuch 'Prompt Agent engineering'."
  - Automatisches Erstellen von Struktur-Analysen, Präsentationen oder Berichten auf Basis tausender Seiten an Notizen.
  - Generieren von FAQ-Listen, Mindmaps oder Podcasts direkt aus deinen hochgeladenen Quellen in NotebookLM.

## 3. LM Studio (lm-studio)
Ermöglicht dem Agenten, auf lokal gehostete, private Open-Source-Sprachmodelle (wie Llama 3 oder Qwen) zuzugreifen.
- **Funktionsweise:** Ein Python-Skript (`lm_studio_mcp.py`), das lokal über `uv` ausgeführt wird und als Brücke zum LM Studio-Server (Port 1234) fungiert. 
- **Möglichkeiten:** 
  - **100% Datenschutz:** Sende sensible Codeschnipsel oder Daten, die die Cloud nicht sehen darf, gezielt an dein lokales Modell: "Frag LM Studio, was dieser Code macht."
  - **Hybride Intelligenz:** Der schnelle Cloud-Agent (AntiGravity) plant die Aufgaben, delegiert aber rechenintensive oder private Code-Generations-Schritte an dein lokales, kostenloses Modell in LM Studio.

---
###  Wichtiger Hinweis zur Nutzung:
Falls du AntiGravity gerade erst konfiguriert hast, stelle sicher, dass du das Fenster deiner IDE einmal neu lädst (Reload Window), damit die `mcp_config.json` frisch eingelesen wird. LM Studio muss im Hintergrund laufen und der "Local Server" auf `ON` stehen (Port 1234), damit die Verbindung funktioniert.
