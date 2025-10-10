#!/usr/bin/env python3
"""
Test script for UI modernization features.

This script allows you to visually test the modernized overlay and settings window
without running the full Voice Typing application.
"""

import tkinter as tk
import math
import random
from src.voice_typing.ui.overlay import Overlay
from src.voice_typing.ui.settings_window import SettingsWindow
from src.voice_typing.config.manager import ConfigManager


def test_overlay():
    """Test the modernized overlay with simulated audio levels."""
    print("Testing Overlay...")
    
    root = tk.Tk()
    root.withdraw()
    
    # Simulated audio level (0.0 to 1.0)
    audio_level = [0.0]
    phase = [0.0]
    
    def get_simulated_level():
        """Simulate varying audio levels for testing."""
        phase[0] += 0.1
        # Create realistic audio variation
        base = (math.sin(phase[0] * 0.5) + 1) / 2
        variation = random.random() * 0.3
        audio_level[0] = min(1.0, base * 0.7 + variation)
        return audio_level[0]
    
    # Create overlay
    overlay = Overlay(
        get_level=get_simulated_level,
        size=120,
        opacity=0.9,
        position=(100, 100),
        root=root,
    )
    
    # Test state changes
    def cycle_states():
        """Cycle through different states for testing."""
        states = ["idle", "recording", "processing"]
        current_state = [0]
        
        def next_state():
            current_state[0] = (current_state[0] + 1) % len(states)
            state = states[current_state[0]]
            print(f"Changing state to: {state}")
            overlay.set_state(state)
            root.after(3000, next_state)  # Change every 3 seconds
        
        # Start cycling after 1 second
        root.after(1000, next_state)
    
    # Create control panel
    control = tk.Toplevel(root)
    control.title("Overlay Test Controls")
    control.geometry("300x200")
    
    tk.Label(control, text="Overlay State Control", font=("Arial", 12, "bold")).pack(pady=10)
    
    tk.Button(
        control,
        text="Set to IDLE",
        command=lambda: overlay.set_state("idle")
    ).pack(pady=5)
    
    tk.Button(
        control,
        text="Set to RECORDING",
        command=lambda: overlay.set_state("recording")
    ).pack(pady=5)
    
    tk.Button(
        control,
        text="Set to PROCESSING",
        command=lambda: overlay.set_state("processing")
    ).pack(pady=5)
    
    tk.Button(
        control,
        text="Auto-cycle States",
        command=cycle_states
    ).pack(pady=5)
    
    tk.Button(
        control,
        text="Close",
        command=root.quit
    ).pack(pady=10)
    
    # Show overlay
    overlay.show()
    
    print("Overlay test started!")
    print("- Try dragging the overlay")
    print("- Click it to trigger ripple effect")
    print("- Use control panel to change states")
    print("- Hover over it to see hover effect")
    
    root.mainloop()


def test_settings():
    """Test the modernized settings window."""
    print("Testing Settings Window...")
    
    root = tk.Tk()
    root.withdraw()
    
    # Create config manager
    cfgm = ConfigManager()
    
    # Create settings window
    settings = SettingsWindow(cfgm, root=root)
    
    # Create control panel
    control = tk.Toplevel(root)
    control.title("Settings Test Controls")
    control.geometry("300x150")
    
    tk.Label(control, text="Settings Window Test", font=("Arial", 12, "bold")).pack(pady=10)
    
    tk.Button(
        control,
        text="Open Settings",
        command=settings.show
    ).pack(pady=10)
    
    tk.Button(
        control,
        text="Close Test",
        command=root.quit
    ).pack(pady=10)
    
    print("Settings window test started!")
    print("- Click 'Open Settings' to view the modernized window")
    print("- Test all tabs (General, Audio, Streaming, Decoding)")
    print("- Try saving settings to see the success animation")
    print("- Check hover effects on buttons")
    
    # Auto-show settings
    settings.show()
    
    root.mainloop()


def test_both():
    """Test both overlay and settings window together."""
    print("Testing Both Components...")
    
    root = tk.Tk()
    root.withdraw()
    
    # Config
    cfgm = ConfigManager()
    
    # Audio simulation
    audio_level = [0.0]
    phase = [0.0]
    
    def get_simulated_level():
        phase[0] += 0.1
        base = (math.sin(phase[0] * 0.5) + 1) / 2
        variation = random.random() * 0.3
        audio_level[0] = min(1.0, base * 0.7 + variation)
        return audio_level[0]
    
    # Create components
    overlay = Overlay(
        get_level=get_simulated_level,
        size=120,
        opacity=0.9,
        position=(100, 100),
        root=root,
        config_manager=cfgm,
    )
    
    settings = SettingsWindow(cfgm, root=root)
    
    # Connect overlay to settings
    overlay.on_settings = settings.show
    
    # Control panel
    control = tk.Toplevel(root)
    control.title("Complete UI Test")
    control.geometry("320x300")
    
    tk.Label(control, text="Voice Typing UI Test", font=("Arial", 14, "bold")).pack(pady=10)
    
    tk.Label(control, text="Overlay Controls:").pack(pady=5)
    
    state_frame = tk.Frame(control)
    state_frame.pack(pady=5)
    
    tk.Button(state_frame, text="Idle", command=lambda: overlay.set_state("idle")).pack(side=tk.LEFT, padx=2)
    tk.Button(state_frame, text="Recording", command=lambda: overlay.set_state("recording")).pack(side=tk.LEFT, padx=2)
    tk.Button(state_frame, text="Processing", command=lambda: overlay.set_state("processing")).pack(side=tk.LEFT, padx=2)
    
    tk.Label(control, text="").pack()  # Spacer
    tk.Label(control, text="Settings:").pack(pady=5)
    
    tk.Button(
        control,
        text="Open Settings",
        command=settings.show,
        bg="#8b5cf6",
        fg="white",
        font=("Arial", 10, "bold")
    ).pack(pady=5)
    
    tk.Label(control, text="").pack()  # Spacer
    tk.Label(control, text="Instructions:", font=("Arial", 10, "bold")).pack(pady=5)
    
    instructions = tk.Text(control, height=6, width=35, wrap=tk.WORD)
    instructions.pack(pady=5)
    instructions.insert("1.0", 
        "• Right-click overlay to open settings\n"
        "• Left-click overlay for ripple effect\n"
        "• Drag overlay to move it\n"
        "• Hover over overlay for highlight\n"
        "• Test all state transitions\n"
        "• Check settings animations"
    )
    instructions.config(state=tk.DISABLED)
    
    tk.Button(
        control,
        text="Exit",
        command=root.quit,
        bg="#ef4444",
        fg="white"
    ).pack(pady=10)
    
    # Show overlay
    overlay.show()
    
    print("\n" + "="*50)
    print("COMPLETE UI TEST STARTED")
    print("="*50)
    print("\nTesting:")
    print("  ✓ Modern overlay with gradients")
    print("  ✓ Circular waveform visualization")
    print("  ✓ State transitions (idle/recording/processing)")
    print("  ✓ Glassmorphism settings window")
    print("  ✓ Interactive effects and animations")
    print("\nUse the control panel to test all features!")
    print("="*50 + "\n")
    
    root.mainloop()


if __name__ == "__main__":
    import sys
    
    print("\n" + "="*60)
    print("VOICE TYPING - UI MODERNIZATION TEST SUITE")
    print("="*60)
    print("\nChoose a test:")
    print("  1. Test Overlay only")
    print("  2. Test Settings Window only")
    print("  3. Test Both (Complete Test)")
    print("="*60)
    
    choice = input("\nEnter choice (1-3, or press Enter for complete test): ").strip()
    
    if choice == "1":
        test_overlay()
    elif choice == "2":
        test_settings()
    else:
        test_both()
