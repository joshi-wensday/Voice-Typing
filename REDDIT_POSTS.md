# Reddit Posts for Vype Launch

## r/opensource Post

**Title:** `I made a free, open-source voice typing app because I was tired of cloud-based dictation`

**Body:**

```markdown
Hey everyone! 👋

I just released **Vype** - a voice typing app that actually respects your privacy.

**Why I built this:**

I got tired of paying $30/month for Dragon NaturallySpeaking and sending my voice to random servers. Turns out OpenAI's Whisper model works great locally, so I wrapped it in a friendly interface.

**What it does:**

- Press hotkey (Ctrl+Shift+Space), talk, press again → text appears
- Works in any Windows app
- Has a neat circular audio visualizer (because why not make it pretty?)
- Voice commands like "new line", "period", etc.
- Everything runs on your PC - no internet needed after setup

**The nerdy bits:**

- Python + faster-whisper for speedy inference
- Tkinter UI with custom widgets
- ~2-3 second latency (even on CPU)
- MIT licensed
- Actually documented (I know, shocking)

**What it's NOT:**

- Not cross-platform yet (Windows only, Win32 APIs for hotkeys)
- Not perfect - it's v1.0, so expect rough edges
- Not going to replace Dragon for professional transcriptionists (yet?)

**GitHub:** https://github.com/joshi-wensday/Voice-Typing

**Download:** Windows installer in the releases

I built this mostly for myself, but figured others might find it useful. Happy to answer questions or take feature requests!

Also, if anyone wants to help port it to Linux/Mac, that would be amazing - the architecture is pretty modular.

---

*PS: Yes, the circular visualizer was way harder to build than the actual speech recognition. No regrets.*
```

---

## r/selfhosted Post

**Title:** `Voice typing that actually stays on your computer - Vype v1.0`

**Body:**

```markdown
Hey r/selfhosted! 👋

Made a thing you might like: **Vype** - local voice typing for Windows.

**The pitch:**

You know how every voice typing service wants to send your audio to their servers? Yeah, this doesn't do that.

Press Ctrl+Shift+Space, talk into your mic, press again → text appears. All processing happens on your PC using OpenAI's Whisper model.

**Privacy stuff:**

✅ All processing local  
✅ No telemetry, no tracking  
✅ No internet needed (after downloading the AI model)  
✅ Open source (MIT) - check the code yourself  

**Features:**

- Works in any Windows application
- Real-time audio visualizer (looks cool in screenshots)
- Voice commands ("new line", "period", etc.)
- Choose between tiny (39MB) to large (1.5GB) AI models
- Fast - ~2-3 second latency even on CPU
- GPU support for even faster transcription

**Tech stack:**

- Python
- Whisper (via faster-whisper/CTranslate2)
- Runs entirely on your hardware

**Limitations:**

- Windows only (for now - uses Win32 APIs)
- Not as polished as commercial software
- First release, so bugs are expected

**Use cases:**

- Writing emails/docs without typing
- Accessibility
- Dictating when your hands are busy
- Not wanting Big Tech to have recordings of your voice

**GitHub:** https://github.com/joshi-wensday/Voice-Typing  
**Download:** Installer in releases (77MB)

I built this because I wanted voice typing without the subscription or privacy concerns. Turns out local AI is pretty capable these days!

Questions welcome. Also open to contributions if anyone wants to help improve it.

---

*Obligatory note: Yes, it requires downloading a ~150MB AI model on first run. But then it's fully offline!*
```

---

## Quick Tips for Posting

**Timing:**
- Post Tuesday-Thursday, 8-10 AM EST for best visibility

**After Posting:**
- Check back every 30 minutes for the first 2 hours
- Answer questions quickly and enthusiastically
- Thank people for feedback
- Be honest about limitations

**If someone asks about:**
- **"Why not use Windows built-in?"** → "Good question! This gives you more control, works offline, and you can customize it. Plus the built-in one sends everything to Microsoft's servers."
- **"Will it work on Linux?"** → "Not yet - currently uses Win32 APIs for global hotkeys. Would love help porting it though!"
- **"How accurate is it?"** → "Pretty good! Uses the same Whisper model as many commercial apps. Accuracy depends on which model you choose - larger = more accurate but slower."
- **"Can I use it for [specific use case]?"** → "Give it a try! It works in any Windows app that accepts text input."

**Engagement Ideas:**
- Share a funny mistake the AI made
- Ask for feature suggestions
- Be genuinely curious about how others might use it

**Don't:**
- Get defensive if someone criticizes it
- Compare it too aggressively to commercial products
- Oversell - be honest about it being a v1.0

---

## Bonus: Short One-Liner Responses

If people ask "What is this?" in the comments:

> "Voice typing app that runs on your PC instead of sending your audio to the cloud. Press hotkey → talk → get text. Open source!"

If they ask "Is it better than Dragon?":

> "Different goals! Dragon is way more polished. This is free, open source, and privacy-focused. Choose your trade-offs 😊"

If they say "Cool, I'll try it!":

> "Awesome! Let me know how it goes. First release so I'm sure there's bugs I haven't found yet 😅"


