"""Text processing utilities for STT output improvement.

This module provides utilities for improving speech-to-text output including:
- Filler word removal (um, uh, etc.)
- Context-aware grammar improvement
- Sentence boundary detection and correction
"""

from __future__ import annotations

import re
from typing import List, Tuple


# Common filler words and variations
FILLER_WORDS = {
    # Basic fillers
    "um", "uh", "er", "ah", "eh", "mm", "hmm", "hm",
    # Extended fillers
    "umm", "uhh", "err", "ahh", "ehh", "mmm", "hmmm",
    # Thinking sounds
    "like", "you know", "i mean", "actually", "basically",
    # British variations
    "erm",
}

# Patterns for filler word detection (case-insensitive)
FILLER_PATTERN = re.compile(
    r'\b(' + '|'.join(re.escape(word) for word in FILLER_WORDS) + r')\b',
    re.IGNORECASE
)

# Sentence starters that should be capitalized
SENTENCE_STARTERS = {
    'i', 'the', 'a', 'an', 'this', 'that', 'these', 'those',
    'we', 'they', 'he', 'she', 'it', 'you'
}


class TextProcessor:
    """Process and improve STT transcription output."""
    
    def __init__(self, remove_fillers: bool = False, improve_grammar: bool = False):
        """Initialize text processor.
        
        Args:
            remove_fillers: Whether to remove filler words
            improve_grammar: Whether to apply grammar improvements
        """
        self.remove_fillers = remove_fillers
        self.improve_grammar = improve_grammar
        self._context_buffer: List[str] = []
        self._max_context_sentences = 5
    
    def process(self, text: str) -> str:
        """Process text with configured improvements.
        
        Args:
            text: Raw transcription text
        
        Returns:
            Processed text
        """
        if not text:
            return text
        
        result = text
        
        # Remove filler words if enabled
        if self.remove_fillers:
            result = self._remove_filler_words(result)
        
        # Improve grammar if enabled
        if self.improve_grammar:
            result = self._improve_grammar(result)
        
        # Update context buffer
        self._update_context(result)
        
        return result
    
    def _remove_filler_words(self, text: str) -> str:
        """Remove filler words from text.
        
        Args:
            text: Input text
        
        Returns:
            Text with filler words removed
        """
        # Remove standalone filler words
        result = FILLER_PATTERN.sub('', text)
        
        # Clean up multiple spaces
        result = re.sub(r'\s+', ' ', result)
        
        # Clean up spaces before punctuation
        result = re.sub(r'\s+([.,!?;:])', r'\1', result)
        
        # Trim
        result = result.strip()
        
        return result
    
    def _improve_grammar(self, text: str) -> str:
        """Apply context-aware grammar improvements.
        
        Args:
            text: Input text
        
        Returns:
            Text with grammar improvements
        """
        if not text:
            return text
        
        result = text
        
        # DISABLED: Context-based improvements can cause hallucinations
        # Only do basic capitalization - no context usage
        
        # Fix capitalization (basic only)
        result = self._fix_capitalization_basic(result)
        
        return result
    
    def _fix_common_errors(self, text: str) -> str:
        """Fix common speech recognition errors.
        
        Args:
            text: Input text
        
        Returns:
            Text with common errors fixed
        """
        # Common homophones and errors
        replacements = {
            r'\btheir\s+are\b': 'there are',
            r'\btheir\s+is\b': 'there is',
            r'\bthere\s+going\b': "they're going",
            r'\bits\s+a\s+lot\b': "it's a lot",
            r'\byour\s+welcome\b': "you're welcome",
            r'\byour\s+right\b': "you're right",
        }
        
        result = text
        for pattern, replacement in replacements.items():
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        
        return result
    
    def _improve_sentence_boundaries(self, text: str) -> str:
        """Improve sentence boundary detection and punctuation.
        
        This uses context from the buffer to determine if text should
        continue the previous sentence or start a new one.
        
        Args:
            text: Input text
        
        Returns:
            Text with improved sentence boundaries
        """
        if not self._context_buffer:
            # First sentence, ensure it starts with capital
            return text[0].upper() + text[1:] if text else text
        
        # Get last context sentence
        last_sentence = self._context_buffer[-1] if self._context_buffer else ""
        
        # Check if this looks like it should continue the previous sentence
        if last_sentence and not last_sentence.rstrip().endswith(('.', '!', '?')):
            # Previous sentence didn't end with punctuation
            # Check if current text looks like a continuation
            if text and text[0].islower():
                # Starts with lowercase, likely a continuation
                # Check for connecting words
                connecting_words = ['and', 'but', 'or', 'so', 'because', 'when', 'if', 'while']
                first_word = text.split()[0].lower() if text.split() else ''
                
                if first_word in connecting_words:
                    # This is clearly a continuation
                    return text
        
        # Looks like a new sentence - ensure it starts with capital
        return text[0].upper() + text[1:] if text else text
    
    def _fix_capitalization_basic(self, text: str) -> str:
        """Fix capitalization issues (basic, no context).
        
        Args:
            text: Input text
        
        Returns:
            Text with fixed capitalization
        """
        if not text:
            return text
        
        result = text
        
        # Capitalize "I"
        result = re.sub(r'\bi\b', 'I', result)
        
        # Capitalize after sentence-ending punctuation
        result = re.sub(
            r'([.!?]\s+)([a-z])',
            lambda m: m.group(1) + m.group(2).upper(),
            result
        )
        
        return result
    
    def _fix_capitalization(self, text: str) -> str:
        """Fix capitalization issues.
        
        Args:
            text: Input text
        
        Returns:
            Text with fixed capitalization
        """
        if not text:
            return text
        
        # Ensure first letter is capitalized
        result = text[0].upper() + text[1:] if len(text) > 1 else text.upper()
        
        # Capitalize after sentence-ending punctuation
        result = re.sub(
            r'([.!?]\s+)([a-z])',
            lambda m: m.group(1) + m.group(2).upper(),
            result
        )
        
        # Capitalize "I"
        result = re.sub(r'\bi\b', 'I', result)
        
        return result
    
    def _update_context(self, text: str) -> None:
        """Update context buffer with processed text.
        
        Args:
            text: Processed text to add to context
        """
        if not text:
            return
        
        # Split into sentences
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        # Add to buffer
        self._context_buffer.extend(sentences)
        
        # Keep only recent context
        if len(self._context_buffer) > self._max_context_sentences:
            self._context_buffer = self._context_buffer[-self._max_context_sentences:]
    
    def reset_context(self) -> None:
        """Reset the context buffer."""
        self._context_buffer.clear()
    
    def get_context(self) -> List[str]:
        """Get current context buffer.
        
        Returns:
            List of recent sentences
        """
        return self._context_buffer.copy()


def remove_filler_words(text: str) -> str:
    """Convenience function to remove filler words from text.
    
    Args:
        text: Input text
    
    Returns:
        Text with filler words removed
    """
    processor = TextProcessor(remove_fillers=True, improve_grammar=False)
    return processor.process(text)


def improve_text(text: str, remove_fillers: bool = True, improve_grammar: bool = True) -> str:
    """Convenience function to improve text with all features.
    
    Args:
        text: Input text
        remove_fillers: Whether to remove filler words
        improve_grammar: Whether to improve grammar
    
    Returns:
        Improved text
    """
    processor = TextProcessor(remove_fillers=remove_fillers, improve_grammar=improve_grammar)
    return processor.process(text)

