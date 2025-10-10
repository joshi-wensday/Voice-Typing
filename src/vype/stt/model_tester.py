"""Model testing and benchmarking utilities."""

from __future__ import annotations

import time
import numpy as np
from dataclasses import dataclass
from typing import List, Optional, Callable, Dict
from pathlib import Path

from .whisper_engine import FasterWhisperEngine


@dataclass
class TestResult:
    """Results from testing a single model."""
    model_name: str
    audio_duration: float  # seconds
    transcription_time: float  # seconds
    speed_ratio: float  # transcription_time / audio_duration
    text_output: str
    memory_used_mb: Optional[float] = None
    success: bool = True
    error_message: Optional[str] = None


class ModelTester:
    """Test and benchmark Whisper models."""
    
    def __init__(self):
        """Initialize the model tester."""
        self.test_audio_samples: List[np.ndarray] = []
        self.sample_durations: List[float] = []
        self.sample_rate = 16000
    
    def create_test_samples(self, durations: List[float] = [5.0, 15.0, 30.0]) -> None:
        """Create silent test audio samples of specified durations.
        
        Args:
            durations: List of durations in seconds for test samples
        """
        self.test_audio_samples = []
        self.sample_durations = durations
        
        for duration in durations:
            # Create silent audio (in real use, would use actual recorded audio)
            num_samples = int(duration * self.sample_rate)
            audio = np.zeros(num_samples, dtype=np.float32)
            self.test_audio_samples.append(audio)
    
    def set_test_audio(self, audio: np.ndarray, sample_rate: int = 16000) -> None:
        """Set a custom audio sample for testing.
        
        Args:
            audio: Audio data as numpy array
            sample_rate: Sample rate of the audio
        """
        self.sample_rate = sample_rate
        duration = len(audio) / sample_rate
        
        # Create 3 versions: full, half, quarter
        self.test_audio_samples = [
            audio,  # Full
            audio[:len(audio)//2],  # Half
            audio[:len(audio)//4],  # Quarter
        ]
        
        self.sample_durations = [
            duration,
            duration / 2,
            duration / 4
        ]
    
    def test_model(
        self,
        model_name: str,
        device: str = "auto",
        compute_type: str = "float16",
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> List[TestResult]:
        """Test a single model with all test samples.
        
        Args:
            model_name: Name of the model to test
            device: Device to use (auto, cpu, cuda)
            compute_type: Compute type (float16, float32, int8)
            progress_callback: Optional callback for progress updates
        
        Returns:
            List of TestResult for each test sample
        """
        results = []
        
        if not self.test_audio_samples:
            self.create_test_samples()
        
        try:
            if progress_callback:
                progress_callback(f"Loading model {model_name}...")
            
            # Initialize engine
            engine = FasterWhisperEngine(
                model=model_name,
                device=device,
                compute_type=compute_type
            )
            engine.preload()
            
            # Test with each sample
            for i, (audio, duration) in enumerate(zip(self.test_audio_samples, self.sample_durations)):
                if progress_callback:
                    progress_callback(f"Testing {model_name} with {duration:.1f}s sample...")
                
                try:
                    start_time = time.time()
                    result = engine.transcribe(audio, sample_rate=self.sample_rate)
                    end_time = time.time()
                    
                    transcription_time = end_time - start_time
                    speed_ratio = transcription_time / duration if duration > 0 else 0
                    
                    test_result = TestResult(
                        model_name=model_name,
                        audio_duration=duration,
                        transcription_time=transcription_time,
                        speed_ratio=speed_ratio,
                        text_output=result.text,
                        success=True
                    )
                    results.append(test_result)
                    
                except Exception as e:
                    results.append(TestResult(
                        model_name=model_name,
                        audio_duration=duration,
                        transcription_time=0.0,
                        speed_ratio=0.0,
                        text_output="",
                        success=False,
                        error_message=str(e)
                    ))
            
        except Exception as e:
            # Model failed to load
            for duration in self.sample_durations:
                results.append(TestResult(
                    model_name=model_name,
                    audio_duration=duration,
                    transcription_time=0.0,
                    speed_ratio=0.0,
                    text_output="",
                    success=False,
                    error_message=f"Model loading failed: {str(e)}"
                ))
        
        return results
    
    def test_all_models(
        self,
        model_names: List[str],
        device: str = "auto",
        compute_type: str = "float16",
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> Dict[str, List[TestResult]]:
        """Test multiple models and return comparison results.
        
        Args:
            model_names: List of model names to test
            device: Device to use
            compute_type: Compute type
            progress_callback: Optional callback for progress
        
        Returns:
            Dictionary mapping model names to their test results
        """
        all_results = {}
        
        for i, model_name in enumerate(model_names):
            if progress_callback:
                progress_callback(f"Testing model {i+1}/{len(model_names)}: {model_name}")
            
            results = self.test_model(model_name, device, compute_type, progress_callback)
            all_results[model_name] = results
        
        return all_results
    
    def get_recommendation(self, results: Dict[str, List[TestResult]]) -> Optional[str]:
        """Analyze test results and recommend the best model.
        
        Args:
            results: Dictionary of test results from test_all_models
        
        Returns:
            Recommended model name, or None if no valid results
        """
        # Find models that successfully transcribed
        successful_models = []
        
        for model_name, test_results in results.items():
            if all(r.success for r in test_results):
                # Calculate average speed ratio
                avg_speed = sum(r.speed_ratio for r in test_results) / len(test_results)
                successful_models.append((model_name, avg_speed))
        
        if not successful_models:
            return None
        
        # Recommend based on speed
        # Prefer models that can transcribe faster than real-time (speed_ratio < 1.0)
        realtime_models = [(name, speed) for name, speed in successful_models if speed < 1.0]
        
        if realtime_models:
            # Among real-time capable models, prefer the one with best quality (largest model)
            model_sizes = {"tiny": 1, "base": 2, "small": 3, "medium": 4, "large-v2": 5, "large-v3": 6}
            realtime_models.sort(key=lambda x: model_sizes.get(x[0].split('.')[0], 0), reverse=True)
            return realtime_models[0][0]
        else:
            # No real-time models, recommend the fastest one
            successful_models.sort(key=lambda x: x[1])
            return successful_models[0][0]
    
    def format_results_table(self, results: Dict[str, List[TestResult]]) -> str:
        """Format test results as a readable table.
        
        Args:
            results: Dictionary of test results
        
        Returns:
            Formatted string table
        """
        lines = []
        lines.append("Model Performance Comparison")
        lines.append("=" * 80)
        lines.append(f"{'Model':<15} {'Duration':<12} {'Time':<12} {'Speed':<12} {'Status':<10}")
        lines.append("-" * 80)
        
        for model_name, test_results in sorted(results.items()):
            for result in test_results:
                if result.success:
                    duration_str = f"{result.audio_duration:.1f}s"
                    time_str = f"{result.transcription_time:.2f}s"
                    speed_str = f"{result.speed_ratio:.2f}x"
                    status = "✓ OK"
                else:
                    duration_str = f"{result.audio_duration:.1f}s"
                    time_str = "N/A"
                    speed_str = "N/A"
                    status = "✗ Failed"
                
                lines.append(f"{model_name:<15} {duration_str:<12} {time_str:<12} {speed_str:<12} {status:<10}")
        
        lines.append("=" * 80)
        lines.append("\nSpeed Ratio: Lower is better (< 1.0 means faster than real-time)")
        
        # Add recommendation
        recommendation = self.get_recommendation(results)
        if recommendation:
            lines.append(f"\nRecommended model for your system: {recommendation}")
        
        return "\n".join(lines)

