"""Real-time audio spectrum analyzer using FFT."""

from __future__ import annotations

import numpy as np
from typing import List


class SpectrumAnalyzer:
    """Analyzes audio data using FFT to extract frequency bands.
    
    Features:
    - Real-time FFT analysis
    - Logarithmic frequency scaling for better visual distribution
    - Exponential moving average for smooth transitions
    - Configurable number of frequency bands
    """
    
    def __init__(self, sample_rate: int = 16000, num_bands: int = 48, smoothing: float = 0.3):
        """Initialize the spectrum analyzer.
        
        Args:
            sample_rate: Audio sample rate in Hz
            num_bands: Number of frequency bands to extract (typically 32-64)
            smoothing: Smoothing factor for exponential moving average (0-1)
        """
        self.sample_rate = sample_rate
        self.num_bands = num_bands
        self.smoothing = smoothing
        
        # Previous band values for smoothing
        self._previous_bands = np.zeros(num_bands)
        
        # Frequency ranges for each band (logarithmic scale)
        # Human hearing: ~20Hz to 20kHz, but focus on voice range: 85Hz to 8kHz
        self.min_freq = 85  # Hz - low end of human voice
        self.max_freq = min(8000, sample_rate // 2)  # Hz - high end, limited by Nyquist
        
        # Calculate logarithmic frequency boundaries for each band
        self._calculate_band_frequencies()
    
    def _calculate_band_frequencies(self):
        """Calculate frequency boundaries for each band using logarithmic scale."""
        # Logarithmic spacing provides better perceptual distribution
        log_min = np.log10(self.min_freq)
        log_max = np.log10(self.max_freq)
        
        # Create band edges (num_bands + 1 edges for num_bands bands)
        log_edges = np.linspace(log_min, log_max, self.num_bands + 1)
        self.band_frequencies = 10 ** log_edges
    
    def analyze(self, audio_chunk: np.ndarray) -> List[float]:
        """Analyze audio chunk and return normalized frequency band magnitudes.
        
        Args:
            audio_chunk: 1D numpy array of audio samples (float32, mono)
        
        Returns:
            List of normalized magnitudes (0.0 to 1.0) for each frequency band
        """
        if audio_chunk.size == 0:
            return [0.0] * self.num_bands
        
        # Apply windowing to reduce spectral leakage
        window = np.hanning(len(audio_chunk))
        windowed = audio_chunk * window
        
        # Perform FFT
        fft_result = np.fft.rfft(windowed)
        magnitudes = np.abs(fft_result)
        
        # Get frequency bins
        freqs = np.fft.rfftfreq(len(audio_chunk), 1.0 / self.sample_rate)
        
        # Extract band magnitudes
        band_mags = []
        for i in range(self.num_bands):
            freq_low = self.band_frequencies[i]
            freq_high = self.band_frequencies[i + 1]
            
            # Find indices in this frequency range
            mask = (freqs >= freq_low) & (freqs < freq_high)
            
            if np.any(mask):
                # Take the maximum magnitude in this band
                band_mag = np.max(magnitudes[mask])
            else:
                band_mag = 0.0
            
            band_mags.append(band_mag)
        
        # Convert to numpy array
        band_mags = np.array(band_mags)
        
        # Apply logarithmic scaling for better dynamic range
        # This makes quiet sounds more visible while preventing loud sounds from dominating
        band_mags = np.log1p(band_mags * 100) / np.log1p(100)
        
        # Normalize to 0-1 range with aggressive exponential weighting
        if band_mags.max() > 0.01:  # Lower threshold
            # First normalize
            normalized = band_mags / band_mags.max()
            # Apply exponential weighting (power > 1 emphasizes louder sounds, suppresses quiet/noise)
            # This creates a more dramatic difference between loud and quiet sounds
            band_mags = normalized ** 2.5  # Power > 1 suppresses smaller values, emphasizes larger ones
        
        # Apply exponential moving average for smoothing
        smoothed_bands = (self.smoothing * self._previous_bands + 
                          (1 - self.smoothing) * band_mags)
        
        self._previous_bands = smoothed_bands
        
        # Apply spatial smoothing for smoother curves (average with neighbors)
        # This creates smoother transitions between adjacent frequency bands
        spatially_smoothed = smoothed_bands.copy()
        for i in range(1, len(smoothed_bands) - 1):
            # Weighted average with neighbors for smoother curves
            spatially_smoothed[i] = (
                smoothed_bands[i-1] * 0.15 +  # Previous band
                smoothed_bands[i] * 0.7 +      # Current band (dominant)
                smoothed_bands[i+1] * 0.15     # Next band
            )
        
        # Return as list, clamped to [0, 1]
        return np.clip(spatially_smoothed, 0.0, 1.0).tolist()
    
    def reset(self):
        """Reset the analyzer state."""
        self._previous_bands = np.zeros(self.num_bands)


class SimpleSpectrumVisualizer:
    """Simplified spectrum analyzer for when we just need basic visualization."""
    
    def __init__(self, num_bars: int = 48):
        """Initialize simple visualizer.
        
        Args:
            num_bars: Number of visualization bars
        """
        self.num_bars = num_bars
        self._values = [0.0] * num_bars
    
    def update_from_level(self, audio_level: float, animation_frame: int) -> List[float]:
        """Create pseudo-spectrum from overall audio level.
        
        This creates variation across bars using sine waves, providing
        a spectrum-like effect without actual FFT analysis.
        
        Args:
            audio_level: Overall audio level (0.0 to 1.0)
            animation_frame: Current animation frame number
        
        Returns:
            List of values (0.0 to 1.0) for each bar
        """
        values = []
        for i in range(self.num_bars):
            # Create variation using sine waves with different phases
            phase_offset = (i / self.num_bars) * 2 * np.pi
            variation = (np.sin(animation_frame * 0.1 + phase_offset) + 1) / 2
            
            # Mix the variation with the audio level
            value = audio_level * (0.3 + variation * 0.7)
            values.append(value)
        
        # Smooth transitions
        for i in range(self.num_bars):
            self._values[i] = self._values[i] * 0.7 + values[i] * 0.3
        
        return self._values

