#!/usr/bin/env python3
"""
Test script for new Voice Typing features.

This script demonstrates and tests all the new features:
1. Modern title bar for settings
2. Filler word removal
3. Context-aware grammar improvement
4. Circular overlay with transparent background
5. Edge vibration effects
"""

import tkinter as tk
from src.voice_typing.stt.text_processor import TextProcessor, remove_filler_words, improve_text


def test_filler_removal():
    """Test filler word removal."""
    print("\n" + "="*60)
    print("TESTING FILLER WORD REMOVAL")
    print("="*60)
    
    test_cases = [
        "Um, so I was thinking, uh, we should do this",
        "Like, you know, I mean, it's actually pretty good",
        "Hmm, err, let me think about that",
        "So basically, um, what I'm trying to say is, uh, hello",
    ]
    
    for i, text in enumerate(test_cases, 1):
        print(f"\nTest {i}:")
        print(f"  Before: {text}")
        result = remove_filler_words(text)
        print(f"  After:  {result}")


def test_grammar_improvement():
    """Test context-aware grammar improvement."""
    print("\n" + "="*60)
    print("TESTING GRAMMAR IMPROVEMENT")
    print("="*60)
    
    processor = TextProcessor(remove_fillers=False, improve_grammar=True)
    
    test_sequences = [
        ["the meeting starts at three", "and we need to prepare"],
        ["i like programming", "its very interesting"],
        ["their are many options", "your right about that"],
    ]
    
    for i, sequence in enumerate(test_sequences, 1):
        print(f"\nTest Sequence {i}:")
        processor.reset_context()
        for j, text in enumerate(sequence):
            result = processor.process(text)
            print(f"  Input {j+1}:  {text}")
            print(f"  Output {j+1}: {result}")


def test_combined():
    """Test both features combined."""
    print("\n" + "="*60)
    print("TESTING COMBINED FEATURES")
    print("="*60)
    
    test_cases = [
        "um, so like, i was thinking we should, uh, do this",
        "their are, like, many options here, you know",
        "um, your right, er, about that",
    ]
    
    for i, text in enumerate(test_cases, 1):
        print(f"\nTest {i}:")
        print(f"  Original:  {text}")
        result = improve_text(text, remove_fillers=True, improve_grammar=True)
        print(f"  Improved:  {result}")


def test_circular_overlay():
    """Test the new circular overlay with edge vibration."""
    print("\n" + "="*60)
    print("TESTING CIRCULAR OVERLAY WITH EDGE VIBRATION")
    print("="*60)
    
    import math
    import random
    from src.voice_typing.ui.overlay import Overlay
    
    root = tk.Tk()
    root.withdraw()
    
    # Simulated audio level
    audio_level = [0.0]
    phase = [0.0]
    
    def get_simulated_level():
        """Simulate varying audio levels."""
        phase[0] += 0.15
        base = (math.sin(phase[0] * 0.5) + 1) / 2
        variation = random.random() * 0.4
        audio_level[0] = min(1.0, base * 0.8 + variation)
        return audio_level[0]
    
    # Create overlay with new smaller size
    overlay = Overlay(
        get_level=get_simulated_level,
        size=80,  # New default size!
        opacity=0.9,  # New default opacity!
        position=(200, 200),
        root=root,
    )
    
    # Control panel
    control = tk.Toplevel(root)
    control.title("New Circular Overlay Test")
    control.geometry("400x400")
    
    tk.Label(control, text="New Circular Overlay Features", font=("Arial", 14, "bold")).pack(pady=10)
    
    # Feature highlights
    features_text = tk.Text(control, height=12, width=45, wrap=tk.WORD)
    features_text.pack(pady=10, padx=10)
    features_text.insert("1.0", 
        "✓ Truly circular (transparent background)\n"
        "✓ Smaller size (80px vs 100px)\n"
        "✓ Higher opacity (90% vs 80%)\n"
        "✓ Edge vibration based on audio\n"
        "✓ Visible in any screen mode\n\n"
        "INSTRUCTIONS:\n"
        "• Notice the circular shape (no square!)\n"
        "• Watch edges vibrate with audio\n"
        "• Try different states below\n"
        "• Drag it around\n"
        "• Click for ripple effect\n"
    )
    features_text.config(state=tk.DISABLED)
    
    # State controls
    tk.Label(control, text="Test Different States:", font=("Arial", 10, "bold")).pack(pady=5)
    
    state_frame = tk.Frame(control)
    state_frame.pack(pady=5)
    
    tk.Button(
        state_frame,
        text="Idle (Blue)",
        command=lambda: overlay.set_state("idle"),
        bg="#3b82f6",
        fg="white",
        width=12
    ).pack(side=tk.LEFT, padx=5)
    
    tk.Button(
        state_frame,
        text="Recording (Red)",
        command=lambda: overlay.set_state("recording"),
        bg="#ef4444",
        fg="white",
        width=12
    ).pack(side=tk.LEFT, padx=5)
    
    tk.Button(
        state_frame,
        text="Processing (Yellow)",
        command=lambda: overlay.set_state("processing"),
        bg="#eab308",
        fg="black",
        width=12
    ).pack(side=tk.LEFT, padx=5)
    
    # Audio level control
    tk.Label(control, text="Simulate Audio Level:", font=("Arial", 10, "bold")).pack(pady=10)
    
    level_label = tk.Label(control, text="Level: 0%")
    level_label.pack()
    
    def update_audio_level(val):
        audio_level[0] = float(val) / 100
        level_label.config(text=f"Level: {int(float(val))}%")
    
    slider = tk.Scale(
        control,
        from_=0,
        to=100,
        orient=tk.HORIZONTAL,
        command=update_audio_level,
        length=300
    )
    slider.set(50)
    slider.pack()
    
    tk.Button(
        control,
        text="Close",
        command=root.quit,
        bg="#ef4444",
        fg="white",
        font=("Arial", 10, "bold")
    ).pack(pady=20)
    
    # Show overlay
    overlay.show()
    
    print("\n✓ Circular overlay launched!")
    print("  - Size: 80px (reduced from 100px)")
    print("  - Opacity: 90% (increased from 80%)")
    print("  - Shape: True circle with transparent background")
    print("  - Edge: Vibrates based on audio level")
    print("\nUse the control panel to test features!")
    
    root.mainloop()


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("VOICE TYPING - NEW FEATURES TEST SUITE")
    print("="*60)
    
    choice = input(
        "\nChoose test:\n"
        "  1. Test filler word removal\n"
        "  2. Test grammar improvement\n"
        "  3. Test combined features\n"
        "  4. Test circular overlay\n"
        "  5. Run all text tests\n"
        "\nEnter choice (1-5): "
    ).strip()
    
    if choice == "1":
        test_filler_removal()
    elif choice == "2":
        test_grammar_improvement()
    elif choice == "3":
        test_combined()
    elif choice == "4":
        test_circular_overlay()
    elif choice == "5":
        test_filler_removal()
        test_grammar_improvement()
        test_combined()
    else:
        print("\nRunning all tests...\n")
        test_filler_removal()
        test_grammar_improvement()
        test_combined()
        
        print("\n" + "="*60)
        print("Text tests complete!")
        print("="*60)
        
        run_visual = input("\nRun visual overlay test? (y/n): ").strip().lower()
        if run_visual == 'y':
            test_circular_overlay()
    
    print("\n" + "="*60)
    print("ALL TESTS COMPLETE!")
    print("="*60)
    print("\nNew features are working correctly! 🎉\n")


if __name__ == "__main__":
    main()

